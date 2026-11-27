"""DebtLedger deterministico unificato (Fase 2 Protocolli Metodologici A/B).

Riconcilia in aritmetica Decimal esatta tutte le posizioni debitorie del fascicolo
evitando qualsiasi doppio conteggio tra fonti diverse (Bilancio, AdER, Centrale Rischi,
DebtPosition/CTC/CRIF, Garanzie).

Distingue tassativamente 7 categorie:
1. tributari_contributivi
2. bancari_finanziari
3. fornitori_dipendenti
4. coobbligazioni_garanzie
5. contestate_eventuali_non_quantificate
6. cessioni_credito
7. estinte_e_piani_pagamento

Mantiene separati:
- esposizioni certe per cassa vs esposizioni di firma/garanzie
- posizioni documentate vs posizioni soltanto riferite/non validate
- posizioni estinte (residuo attivo 0) vs piani di pagamento (conteggiati una sola volta)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.entities import (
    Case,
    Company,
    CreditExposure,
    CreditReportSummary,
    DebtPosition,
    FinancialStatement,
    GuaranteeGiven,
    TaxDebtStatement,
)
from app.services.protocols.classifier import _is_interim_fs

BUCKET_NAMES = (
    "tributari_contributivi",
    "bancari_finanziari",
    "fornitori_dipendenti",
    "coobbligazioni_garanzie",
    "contestate_eventuali_non_quantificate",
    "cessioni_credito",
    "estinte_e_piani_pagamento",
)

_CESSIONE_TOKENS = (
    "amco",
    "dovalue",
    "hoist",
    "intrum",
    "kruk",
    "cerved",
    "ifis npl",
    "spv",
    "cession",
    "cedut",
    "cartolarizz",
    "servicer",
)
_FIRMA_TOKENS = ("firma", "garanz", "fideiuss", "avall", "cauzion", "coobblig")
_ESTINTO_TOKENS = ("estint", "saldat", "chius", "sgravat", "annullat")
_CONTESTATO_TOKENS = ("contestat", "sospes", "eventual", "contenzios", "oppost", "da_quantificare")
_PIANO_TOKENS = ("rateizz", "piano", "rottam", "definizione_agevolata")
_TRIB_TOKENS = ("erar", "tribut", "fisc", "ader", "agenzia", "inps", "inail", "cartella", "impost", "iva")
_BANC_TOKENS = ("banc", "mutu", "finanziament", "prestit", "leasing", "fido", "carta", "crif", "ctc")


def _d(val: Any) -> Optional[Decimal]:
    if val is None or val == "" or isinstance(val, bool):
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _as_float(val: Optional[Decimal]) -> Optional[float]:
    return float(_q2(val)) if val is not None else None


def _is_cession_text(text: str) -> bool:
    t = text.lower()
    return any(tok in t for tok in _CESSIONE_TOKENS)


def _latest_closed_client_fs(db: Session, case: Case) -> Optional[FinancialStatement]:
    client_ids = [c.id for c in (case.companies or []) if (c.role or "cliente") == "cliente"]
    if not client_ids:
        return None
    statements = (
        db.query(FinancialStatement)
        .filter(FinancialStatement.company_id.in_(client_ids))
        .all()
    )
    if not statements:
        return None
    closed = [fs for fs in statements if not _is_interim_fs(fs)]
    pool = closed or statements
    return sorted(pool, key=lambda s: (str(s.fiscal_year_end or ""), str(s.id or "")), reverse=True)[0]


def _entry(
    *,
    source: str,
    creditor: str,
    description: str,
    amount: Optional[Decimal],
    exposure_kind: str,  # cassa | firma_garanzia | contestata_non_quantificata | estinta | piano_pagamento
    evidence_level: str,  # documentata | riferita
    status: str,
    reference_id: str = "",
    notes: str = "",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source": source,
        "creditor": creditor or "Non specificato",
        "description": description,
        "amount": _as_float(amount),
        "amount_exact": str(_q2(amount)) if amount is not None else None,
        "exposure_kind": exposure_kind,
        "evidence_level": evidence_level,
        "status": status,
        "reference_id": reference_id,
        "notes": notes,
    }
    if extra:
        out.update(extra)
    return out


def build_debt_ledger(db: Session, case: Case) -> dict[str, Any]:
    """Costruisce la riconciliazione debitoria unificata per i 7 bucket senza duplicazioni."""
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKET_NAMES}
    deduplication_log: list[dict[str, Any]] = []
    reconciliation_notes: list[str] = []

    tax_statements: list[TaxDebtStatement] = list(case.tax_debt_statements or [])
    credit_exposures: list[CreditExposure] = list(case.credit_exposures or [])
    cr_summaries: list[CreditReportSummary] = list(case.cr_summaries or [])
    guarantees: list[GuaranteeGiven] = list(case.guarantees_given or [])
    positions: list[DebtPosition] = list(case.positions or [])
    latest_fs = _latest_closed_client_fs(db, case)

    # ------------------------------------------------------------------
    # 1. Fonti AdER deduplicate per (codice_fiscale, owner_kind)
    # ------------------------------------------------------------------
    latest_aer: dict[tuple[str, str], TaxDebtStatement] = {}
    for st in sorted(
        tax_statements,
        key=lambda t: (str(t.data_elaborazione or ""), str(t.created_at or ""), str(t.id or "")),
        reverse=True,
    ):
        key = ((st.codice_fiscale or "").strip().upper() or st.id, (st.owner_kind or "person").lower())
        if key in latest_aer:
            deduplication_log.append({
                "key": f"AdER:{key[0]}:{key[1]}",
                "kept_source": f"TaxDebtStatement:{latest_aer[key].id}",
                "dropped_source": f"TaxDebtStatement:{st.id}",
                "dropped_amount": _as_float(_d(st.total_residuo)),
                "reason": "Estratto di ruolo precedente sullo stesso CF: evitata somma duplicata.",
            })
            continue
        latest_aer[key] = st

    has_aer_source = bool(latest_aer)
    seen_cartelle: set[str] = set()
    aer_cash_total = Decimal("0.00")

    for st in latest_aer.values():
        items = list(st.items or [])
        if items:
            for it in items:
                doc_num = (it.numero_documento or "").strip()
                if doc_num:
                    dedup_key = f"{(st.codice_fiscale or '').upper()}:{doc_num}"
                    if dedup_key in seen_cartelle:
                        deduplication_log.append({
                            "key": f"Cartella:{dedup_key}",
                            "kept_source": st.id,
                            "dropped_source": it.id,
                            "dropped_amount": _as_float(_d(it.totale_residuo)),
                            "reason": "Numero documento duplicato tra estratti AdER.",
                        })
                        continue
                    seen_cartelle.add(dedup_key)

                tot_res = _d(it.totale_residuo) or Decimal("0.00")
                susp = _d(it.importo_sospeso) or Decimal("0.00")
                net_col = _d(it.totale_residuo_netto)
                if net_col is not None and (net_col > 0 or (susp > 0 and tot_res == susp)):
                    net_res = net_col
                else:
                    net_res = max(Decimal("0.00"), tot_res - susp)

                if susp > 0:
                    buckets["contestate_eventuali_non_quantificate"].append(_entry(
                        source="AdER (importo sospeso/contestato)",
                        creditor=it.ente_creditore or "Agenzia delle Entrate-Riscossione",
                        description=f"Cartella {doc_num or it.id} — quota sospesa",
                        amount=susp,
                        exposure_kind="contestata_non_quantificata",
                        evidence_level="documentata",
                        status="sospeso",
                        reference_id=it.id,
                    ))

                if net_res == 0 and not it.rateizzato and not it.def_agevolata:
                    buckets["estinte_e_piani_pagamento"].append(_entry(
                        source="AdER",
                        creditor=it.ente_creditore or "Agenzia delle Entrate-Riscossione",
                        description=f"Cartella estinta/sgravata {doc_num or it.id}",
                        amount=Decimal("0.00"),
                        exposure_kind="estinta",
                        evidence_level="documentata",
                        status="estinto",
                        reference_id=it.id,
                        extra={"carico_originario": _as_float(_d(it.carico_affidato))},
                    ))
                elif it.rateizzato or it.def_agevolata:
                    if net_res > 0:
                        aer_cash_total += net_res
                        buckets["estinte_e_piani_pagamento"].append(_entry(
                            source="AdER (piano di pagamento)",
                            creditor=it.ente_creditore or "Agenzia delle Entrate-Riscossione",
                            description=f"Cartella {'in definizione agevolata' if it.def_agevolata else 'rateizzata'} {doc_num or it.id}",
                            amount=net_res,
                            exposure_kind="piano_pagamento",
                            evidence_level="documentata",
                            status="piano_pagamento",
                            reference_id=it.id,
                            extra={"carico_originario": _as_float(_d(it.carico_affidato))},
                        ))
                elif net_res > 0:
                    aer_cash_total += net_res
                    buckets["tributari_contributivi"].append(_entry(
                        source="AdER",
                        creditor=it.ente_creditore or "Agenzia delle Entrate-Riscossione",
                        description=f"Cartella {doc_num or it.id} ({it.ente_categoria or 'erariale'})",
                        amount=net_res,
                        exposure_kind="cassa",
                        evidence_level="documentata",
                        status="attivo",
                        reference_id=it.id,
                    ))
        else:
            # TaxDebtStatement privo di righe di dettaglio (solo riepilogo testata)
            susp_stmt = Decimal("0.00")
            res_netto = _d(st.total_residuo_netto)
            res_lordo = _d(st.total_residuo) or Decimal("0.00")
            effective_res = res_netto if (res_netto is not None and res_netto > 0) else res_lordo
            if res_netto is not None and res_lordo > res_netto:
                susp_stmt = _q2(res_lordo - res_netto)
                buckets["contestate_eventuali_non_quantificate"].append(_entry(
                    source="AdER (differenza lordo-netto sospesa)",
                    creditor=st.denominazione or "Agenzia delle Entrate-Riscossione",
                    description="Quota sospesa risultante dal prospetto sintetico AdER",
                    amount=susp_stmt,
                    exposure_kind="contestata_non_quantificata",
                    evidence_level="documentata",
                    status="sospeso",
                    reference_id=st.id,
                ))
            if effective_res > 0:
                aer_cash_total += effective_res
                buckets["tributari_contributivi"].append(_entry(
                    source="AdER (riepilogo estratto)",
                    creditor=st.denominazione or "Agenzia delle Entrate-Riscossione",
                    description=f"Estratto di ruolo {st.codice_fiscale or st.id}",
                    amount=effective_res,
                    exposure_kind="cassa",
                    evidence_level="documentata",
                    status="attivo",
                    reference_id=st.id,
                ))

    # ------------------------------------------------------------------
    # 2. Centrale Rischi & Garanzie (senza sommare CreditReportSummary + CreditExposure)
    # ------------------------------------------------------------------
    cr_cash_total = Decimal("0.00")
    cr_intermediaries_seen: set[str] = set()
    has_cr_source = bool(credit_exposures or cr_summaries)

    if credit_exposures:
        for exp in credit_exposures:
            cat_stat = f"{exp.category or ''} {exp.status or ''}".lower()
            interm = (exp.intermediary or "").strip()
            if interm:
                cr_intermediaries_seen.add(interm.lower())
            ut = _d(exp.utilizzato) or Decimal("0.00")
            acc = _d(exp.accordato) or Decimal("0.00")

            if any(tok in cat_stat for tok in _ESTINTO_TOKENS):
                buckets["estinte_e_piani_pagamento"].append(_entry(
                    source="Centrale Rischi",
                    creditor=interm or "Intermediario CR",
                    description=f"Posizione estinta/chiusa ({exp.category or 'CR'})",
                    amount=Decimal("0.00"),
                    exposure_kind="estinta",
                    evidence_level="documentata",
                    status="estinto",
                    reference_id=exp.id,
                ))
                continue

            if any(tok in cat_stat for tok in _FIRMA_TOKENS):
                firma_val = ut if ut > 0 else acc
                if firma_val > 0:
                    buckets["coobbligazioni_garanzie"].append(_entry(
                        source="Centrale Rischi (rischi di firma)",
                        creditor=interm or "Intermediario CR",
                        description=exp.category or "Rischi di firma / garanzie",
                        amount=firma_val,
                        exposure_kind="firma_garanzia",
                        evidence_level="documentata",
                        status="firma",
                        reference_id=exp.id,
                    ))
                continue

            if _is_cession_text(f"{interm} {exp.category or ''} {exp.status or ''}"):
                if ut > 0:
                    cr_cash_total += ut
                    buckets["cessioni_credito"].append(_entry(
                        source="Centrale Rischi (cessionario)",
                        creditor=interm,
                        description=exp.category or "Credito ceduto segnalato in CR",
                        amount=ut,
                        exposure_kind="cassa",
                        evidence_level="documentata",
                        status="attivo",
                        reference_id=exp.id,
                    ))
                continue

            if ut > 0:
                cr_cash_total += ut
                buckets["bancari_finanziari"].append(_entry(
                    source="Centrale Rischi (Banca d'Italia)",
                    creditor=interm or "Intermediario CR",
                    description=exp.category or "Esposizione per cassa",
                    amount=ut,
                    exposure_kind="cassa",
                    evidence_level="documentata",
                    status="attivo",
                    reference_id=exp.id,
                    extra={"accordato_informativo": _as_float(acc)},
                ))
        if cr_summaries:
            deduplication_log.append({
                "key": "CR:SummaryVsExposures",
                "kept_source": f"CreditExposure ({len(credit_exposures)} righe)",
                "dropped_source": "CreditReportSummary.total_exposure",
                "dropped_amount": _as_float(_d(cr_summaries[0].total_exposure)),
                "reason": "Dettaglio analitico CreditExposure già presente: evitata somma doppia con il riepilogo CR.",
            })
    elif cr_summaries:
        latest_cr = sorted(
            cr_summaries,
            key=lambda c: (c.most_recent_month or "", c.id or ""),
            reverse=True,
        )[0]
        cr_exp = _d(latest_cr.total_exposure) or Decimal("0.00")
        cr_gar = _d(latest_cr.total_guarantees) or Decimal("0.00")
        if cr_exp > 0:
            cr_cash_total += cr_exp
            buckets["bancari_finanziari"].append(_entry(
                source="Centrale Rischi (sintesi)",
                creditor="Intermediari segnalanti CR",
                description=f"Esposizione per cassa al {latest_cr.most_recent_month or 'n/d'}",
                amount=cr_exp,
                exposure_kind="cassa",
                evidence_level="documentata",
                status="attivo",
                reference_id=latest_cr.id,
            ))
        if cr_gar > 0 and not guarantees:
            buckets["coobbligazioni_garanzie"].append(_entry(
                source="Centrale Rischi (garanzie sintesi)",
                creditor="Intermediari CR",
                description="Garanzie prestate da riepilogo CR",
                amount=cr_gar,
                exposure_kind="firma_garanzia",
                evidence_level="documentata",
                status="firma",
                reference_id=latest_cr.id,
            ))

    for g in guarantees:
        st_txt = str(g.status or "").lower()
        if any(tok in st_txt for tok in _ESTINTO_TOKENS):
            buckets["estinte_e_piani_pagamento"].append(_entry(
                source="Garanzie (CR/contratti)",
                creditor=g.intermediary or "Istituto",
                description=f"Garanzia estinta a favore di {g.guaranteed_subject or 'terzo'}",
                amount=Decimal("0.00"),
                exposure_kind="estinta",
                evidence_level="documentata",
                status="estinto",
                reference_id=g.id,
            ))
            continue
        gar_amt = _d(g.valore_garanzia) or _d(g.importo_garantito) or Decimal("0.00")
        if gar_amt > 0:
            buckets["coobbligazioni_garanzie"].append(_entry(
                source="Garanzie prestate",
                creditor=g.intermediary or "Istituto",
                description=f"Garanzia/fideiussione per {g.guaranteed_subject or 'terzo'}",
                amount=gar_amt,
                exposure_kind="firma_garanzia",
                evidence_level="documentata",
                status="firma",
                reference_id=g.id,
            ))

    # ------------------------------------------------------------------
    # 3. DebtPosition (CTC/CRIF/Cessioni/Contestate/Riferite) senza duplicare AdER/CR
    # ------------------------------------------------------------------
    fs_raw = (latest_fs.raw_extraction or {}) if (latest_fs and isinstance(latest_fs.raw_extraction, dict)) else {}
    fs_deb = fs_raw.get("debiti_per_natura") if isinstance(fs_raw.get("debiti_per_natura"), dict) else {}

    cedente_amounts_handled: set[Decimal] = set()
    # Prima registra eventuali cessioni in DebtPosition per evitare di contare sia cedente sia cessionario
    for pos in positions:
        text_pos = f"{pos.creditor_name or ''} {pos.debt_type or ''} {pos.status or ''}"
        st_lower = (pos.status or "").lower()
        ev_lvl = "documentata" if ((pos.source_document_id or "").strip() or bool(pos.validated)) else "riferita"
        res_amt = _d(pos.residual_amount)

        if any(tok in st_lower for tok in _ESTINTO_TOKENS) or (res_amt == 0 and not pos.monthly_installment and not any(tok in st_lower for tok in _CONTESTATO_TOKENS)):
            buckets["estinte_e_piani_pagamento"].append(_entry(
                source="Posizione debitoria fascicolo",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Posizione estinta/saldata",
                amount=Decimal("0.00"),
                exposure_kind="estinta",
                evidence_level=ev_lvl,
                status="estinto",
                reference_id=pos.id,
            ))
            continue

        if any(tok in st_lower for tok in _CONTESTATO_TOKENS) or res_amt is None or res_amt < 0:
            buckets["contestate_eventuali_non_quantificate"].append(_entry(
                source="Posizione debitoria fascicolo",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Posizione contestata / non quantificata",
                amount=res_amt if (res_amt is not None and res_amt > 0) else None,
                exposure_kind="contestata_non_quantificata",
                evidence_level=ev_lvl,
                status="contestato" if (res_amt is not None and res_amt > 0) else "non_quantificato",
                reference_id=pos.id,
            ))
            continue

        if _is_cession_text(text_pos):
            cedente_amounts_handled.add(_q2(res_amt))
            buckets["cessioni_credito"].append(_entry(
                source="Posizione ceduta (SPV / Servicer)",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Credito oggetto di cessione",
                amount=res_amt,
                exposure_kind="cassa",
                evidence_level=ev_lvl,
                status="attivo",
                reference_id=pos.id,
                notes="Verificare notifica ex art. 1264 c.c. / G.U. ex art. 58 TUB e assenza duplicazione con cedente.",
            ))
            continue

        if any(tok in f"{pos.debt_type or ''} {pos.status or ''}".lower() for tok in _FIRMA_TOKENS):
            buckets["coobbligazioni_garanzie"].append(_entry(
                source="Posizione coobbligazione/garanzia",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Coobbligazione / Garanzia",
                amount=res_amt,
                exposure_kind="firma_garanzia",
                evidence_level=ev_lvl,
                status="firma",
                reference_id=pos.id,
            ))
            continue

        if any(tok in st_lower for tok in _PIANO_TOKENS):
            buckets["estinte_e_piani_pagamento"].append(_entry(
                source="Piano di pagamento / rateizzazione",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Piano di rientro",
                amount=res_amt,
                exposure_kind="piano_pagamento",
                evidence_level=ev_lvl,
                status="piano_pagamento",
                reference_id=pos.id,
            ))
            continue

        if any(tok in f"{pos.creditor_name or ''} {pos.debt_type or ''}".lower() for tok in _TRIB_TOKENS):
            if has_aer_source:
                deduplication_log.append({
                    "key": f"TaxPosition:{pos.id}",
                    "kept_source": "AdER (TaxDebtStatement)",
                    "dropped_source": f"DebtPosition:{pos.id} ({pos.creditor_name})",
                    "dropped_amount": _as_float(res_amt),
                    "reason": "Debito tributario già coperto dagli estratti AdER: evitata doppia somma.",
                })
                continue
            buckets["tributari_contributivi"].append(_entry(
                source="Posizione fiscale/contributiva",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Debito tributario/previdenziale",
                amount=res_amt,
                exposure_kind="cassa",
                evidence_level=ev_lvl,
                status="attivo",
                reference_id=pos.id,
            ))
            continue

        if any(tok in f"{pos.creditor_name or ''} {pos.debt_type or ''}".lower() for tok in _BANC_TOKENS):
            cred_norm = (pos.creditor_name or "").strip().lower()
            if _q2(res_amt) in cedente_amounts_handled:
                deduplication_log.append({
                    "key": f"CedenteVsCessionario:{res_amt}",
                    "kept_source": "Cessione credito (SPV/Servicer)",
                    "dropped_source": f"DebtPosition:{pos.id} ({pos.creditor_name})",
                    "dropped_amount": _as_float(res_amt),
                    "reason": "Posizione originaria già rappresentata dalla cessione del credito di pari importo.",
                })
                continue
            if cred_norm and cred_norm in cr_intermediaries_seen:
                deduplication_log.append({
                    "key": f"CRVsDebtPos:{cred_norm}",
                    "kept_source": f"CreditExposure CR ({pos.creditor_name})",
                    "dropped_source": f"DebtPosition:{pos.id}",
                    "dropped_amount": _as_float(res_amt),
                    "reason": "Intermediario già rilevato in Centrale Rischi: evitato doppio conteggio.",
                })
                continue
            buckets["bancari_finanziari"].append(_entry(
                source="CTC / CRIF / Finanziamenti",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Finanziamento / credito",
                amount=res_amt,
                exposure_kind="cassa",
                evidence_level=ev_lvl,
                status="attivo",
                reference_id=pos.id,
            ))
            continue

        # Commerciali / dipendenti / fornitori / altro
        buckets["fornitori_dipendenti"].append(_entry(
            source="Posizione commerciale / personale",
            creditor=pos.creditor_name,
            description=pos.debt_type or "Debito commerciale / dipendenti / altro",
            amount=res_amt,
            exposure_kind="cassa",
            evidence_level=ev_lvl,
            status="attivo",
            reference_id=pos.id,
        ))

    # ------------------------------------------------------------------
    # 4. Integrazione e riconciliazione con il Bilancio d'esercizio più recente
    # ------------------------------------------------------------------
    def _fs_nat_val(key: str) -> Optional[Decimal]:
        v = fs_deb.get(key)
        if isinstance(v, dict):
            return _d(v.get("importo") if v.get("importo") is not None else v.get("corrente"))
        return _d(v)

    balance_sheet_comparison: dict[str, Any] = {}
    if latest_fs is not None:
        fs_period = str(latest_fs.fiscal_year_end or "n/d")
        fs_trib = (_fs_nat_val("tributari") or Decimal("0.00")) + (_fs_nat_val("previdenziali") or Decimal("0.00"))
        fs_banche = _fs_nat_val("banche")
        fs_forn = _fs_nat_val("fornitori")
        fs_tfr = _fs_nat_val("tfr") or _d((fs_raw.get("stato_patrimoniale") or {}).get("tfr"))
        fs_dip = _fs_nat_val("dipendenti")
        fs_soci = _fs_nat_val("soci_finanziamenti")
        fs_altri = _fs_nat_val("altri")

        # Tributari/previdenziali: se AdER presente, riconcilia senza sommare!
        if has_aer_source:
            if fs_trib > 0:
                delta_trib = _q2(aer_cash_total - fs_trib)
                balance_sheet_comparison["tributari_ader_vs_bilancio"] = {
                    "ader_netto": _as_float(aer_cash_total),
                    "bilancio": _as_float(fs_trib),
                    "delta": _as_float(delta_trib),
                }
                if abs(delta_trib) > Decimal("1.00"):
                    reconciliation_notes.append(
                        f"Scostamento tributario/previdenziale ({fs_period}): AdER netto € {aer_cash_total:,.2f} "
                        f"vs bilancio € {fs_trib:,.2f} (delta € {delta_trib:,.2f}); assunta AdER senza doppia somma."
                    )
                deduplication_log.append({
                    "key": "Tributari:AdERVsBilancio",
                    "kept_source": "AdER (estratti di ruolo)",
                    "dropped_source": f"Bilancio {fs_period} (tributari+previdenziali)",
                    "dropped_amount": _as_float(fs_trib),
                    "reason": "Debito tributario/previdenziale già rilevato tramite AdER.",
                })
        elif fs_trib > 0:
            buckets["tributari_contributivi"].append(_entry(
                source=f"Bilancio ({fs_period})",
                creditor="Erario e Enti Previdenziali",
                description="Debiti tributari e previdenziali da bilancio (AdER assente)",
                amount=fs_trib,
                exposure_kind="cassa",
                evidence_level="documentata",
                status="attivo",
                reference_id=latest_fs.id,
            ))

        # Banche: se CR presente, riconcilia senza sommare!
        if has_cr_source:
            if fs_banche is not None and fs_banche > 0:
                delta_banche = _q2(cr_cash_total - fs_banche)
                balance_sheet_comparison["bancari_cr_vs_bilancio"] = {
                    "cr_cassa": _as_float(cr_cash_total),
                    "bilancio_banche": _as_float(fs_banche),
                    "delta": _as_float(delta_banche),
                }
                if abs(delta_banche) > Decimal("1.00"):
                    reconciliation_notes.append(
                        f"Scostamento bancario ({fs_period}): CR per cassa € {cr_cash_total:,.2f} "
                        f"vs bilancio banche € {fs_banche:,.2f} (delta € {delta_banche:,.2f}); evitata doppia somma."
                    )
                deduplication_log.append({
                    "key": "Banche:CRVsBilancio",
                    "kept_source": "Centrale Rischi (cassa)",
                    "dropped_source": f"Bilancio {fs_period} (banche)",
                    "dropped_amount": _as_float(fs_banche),
                    "reason": "Esposizione bancaria già rilevata tramite Centrale Rischi.",
                })
        elif fs_banche is not None and fs_banche > 0:
            buckets["bancari_finanziari"].append(_entry(
                source=f"Bilancio ({fs_period})",
                creditor="Banche e Istituti finanziari",
                description="Debiti verso banche da bilancio (CR assente)",
                amount=fs_banche,
                exposure_kind="cassa",
                evidence_level="documentata",
                status="attivo",
                reference_id=latest_fs.id,
            ))

        # Fornitori, TFR, dipendenti e soci da bilancio (solo se non già coperti da DebtPosition commerciale)
        existing_comm = sum(
            ((_d(e["amount_exact"]) or Decimal("0.00")) for e in buckets["fornitori_dipendenti"]),
            Decimal("0.00"),
        )
        if existing_comm == Decimal("0.00"):
            if fs_forn is not None and fs_forn > 0:
                buckets["fornitori_dipendenti"].append(_entry(
                    source=f"Bilancio ({fs_period})",
                    creditor="Fornitori",
                    description="Debiti verso fornitori (SP / debiti per natura)",
                    amount=fs_forn,
                    exposure_kind="cassa",
                    evidence_level="documentata",
                    status="attivo",
                    reference_id=latest_fs.id,
                ))
            if fs_tfr is not None and fs_tfr > 0:
                buckets["fornitori_dipendenti"].append(_entry(
                    source=f"Bilancio ({fs_period})",
                    creditor="Personale dipendente (TFR)",
                    description="Trattamento di Fine Rapporto accantonato",
                    amount=fs_tfr,
                    exposure_kind="cassa",
                    evidence_level="documentata",
                    status="attivo",
                    reference_id=latest_fs.id,
                ))
            if fs_dip is not None and fs_dip > 0:
                buckets["fornitori_dipendenti"].append(_entry(
                    source=f"Bilancio ({fs_period})",
                    creditor="Personale dipendente (retribuzioni)",
                    description="Debiti verso dipendenti / istituti connessi",
                    amount=fs_dip,
                    exposure_kind="cassa",
                    evidence_level="documentata",
                    status="attivo",
                    reference_id=latest_fs.id,
                ))
        if fs_soci is not None and fs_soci > 0:
            buckets["fornitori_dipendenti"].append(_entry(
                source=f"Bilancio ({fs_period})",
                creditor="Soci (finanziamenti)",
                description="Finanziamenti soci — verificare eventuale postergazione ex art. 2467 c.c.",
                amount=fs_soci,
                exposure_kind="cassa",
                evidence_level="documentata",
                status="attivo",
                reference_id=latest_fs.id,
                extra={"sub_category": "finanziamenti_soci"},
            ))
        if fs_altri is not None and fs_altri > 0:
            buckets["fornitori_dipendenti"].append(_entry(
                source=f"Bilancio ({fs_period})",
                creditor="Altri creditori di bilancio",
                description="Altre passività / debiti diversi risultanti da bilancio",
                amount=fs_altri,
                exposure_kind="cassa",
                evidence_level="documentata",
                status="attivo",
                reference_id=latest_fs.id,
            ))

        # Se il bilancio ha solo total_debts aggregato senza breakdown per natura né AdER/CR
        fs_tot_debts = _d(latest_fs.total_debts)
        if fs_tot_debts is not None:
            balance_sheet_comparison["bilancio_debiti_totali"] = _as_float(fs_tot_debts)

    # ------------------------------------------------------------------
    # 5. Calcolo totali in Decimal esatto con separazioni obbligatorie
    # ------------------------------------------------------------------
    all_entries = [item for lst in buckets.values() for item in lst]
    has_any_debt_source = bool(all_entries or latest_fs is not None or has_aer_source or has_cr_source or positions or guarantees)

    def _sum_entries(filter_fn) -> Decimal:
        total = Decimal("0.00")
        for it in all_entries:
            if filter_fn(it):
                val = _d(it["amount_exact"])
                if val is not None:
                    total += val
        return _q2(total)

    cash_kinds = {"cassa", "piano_pagamento"}
    total_cassa_certe = _sum_entries(lambda it: it["exposure_kind"] in cash_kinds)
    total_firma_garanzie = _sum_entries(lambda it: it["exposure_kind"] == "firma_garanzia")
    total_contestate_sospese = _sum_entries(lambda it: it["exposure_kind"] == "contestata_non_quantificata")
    non_quantificate_count = sum(
        1 for it in buckets["contestate_eventuali_non_quantificate"]
        if it["amount_exact"] is None
    )
    total_piani_pagamento = _sum_entries(lambda it: it["exposure_kind"] == "piano_pagamento")
    total_doc_cassa = _sum_entries(
        lambda it: it["exposure_kind"] in cash_kinds and it["evidence_level"] == "documentata"
    )
    total_rif_cassa = _sum_entries(
        lambda it: it["exposure_kind"] in cash_kinds and it["evidence_level"] == "riferita"
    )

    # Fallback se bilancio ha SOLO latest_fs.total_debts e nessun dettaglio per natura / fonti esterne
    if (
        latest_fs is not None
        and total_cassa_certe == Decimal("0.00")
        and _d(latest_fs.total_debts) is not None
        and _d(latest_fs.total_debts) > 0
        and not has_aer_source
        and not has_cr_source
    ):
        fs_tot = _d(latest_fs.total_debts)
        buckets["fornitori_dipendenti"].append(_entry(
            source=f"Bilancio ({latest_fs.fiscal_year_end or 'n/d'})",
            creditor="Massa debitoria aggregata di bilancio",
            description="Debiti totali da bilancio (dettaglio per natura assente)",
            amount=fs_tot,
            exposure_kind="cassa",
            evidence_level="documentata",
            status="attivo",
            reference_id=latest_fs.id,
        ))
        total_cassa_certe = _q2(fs_tot)
        total_doc_cassa = _q2(fs_tot)

    if total_rif_cassa > 0:
        reconciliation_notes.append(
            f"Presenti € {total_rif_cassa:,.2f} in posizioni debitorie soltanto riferite/non validate: "
            "acquisire supporto documentale."
        )

    if total_firma_garanzie > 0:
        reconciliation_notes.append(
            f"Garanzie e rischi di firma (€ {total_firma_garanzie:,.2f}) mantenuti separati dal debito per cassa."
        )

    bucket_totals = {
        name: _as_float(_q2(sum(((_d(it["amount_exact"]) or Decimal("0.00")) for it in lst), Decimal("0.00"))))
        for name, lst in buckets.items()
    }

    return {
        "stato_dato": "VERIFICATO" if has_any_debt_source else "NON_VERIFICABILE_NULL",
        "buckets": buckets,
        "bucket_totals": bucket_totals,
        "totals": {
            "esposizioni_per_cassa_certe": _as_float(total_cassa_certe) if has_any_debt_source else None,
            "esposizioni_per_cassa_certe_exact": str(total_cassa_certe) if has_any_debt_source else "NULL",
            "esposizioni_di_firma_e_garanzie": _as_float(total_firma_garanzie) if has_any_debt_source else None,
            "posizioni_contestate_sospese": _as_float(total_contestate_sospese) if has_any_debt_source else None,
            "posizioni_non_quantificate_count": non_quantificate_count,
            "piani_pagamento_residui": _as_float(total_piani_pagamento) if has_any_debt_source else None,
            "posizioni_documentate_cassa": _as_float(total_doc_cassa) if has_any_debt_source else None,
            "posizioni_riferite_cassa": _as_float(total_rif_cassa) if has_any_debt_source else None,
        },
        "deduplication_log": deduplication_log,
        "reconciliation_notes": reconciliation_notes,
        "balance_sheet_comparison": balance_sheet_comparison,
    }
