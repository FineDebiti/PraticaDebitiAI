"""DebtLedger deterministico unificato (Fase 2 — Validazione Conclusiva).

Riconcilia in aritmetica Decimal esatta tutte le posizioni debitorie del fascicolo:
- Deduplica ESCLUSIVAMENTE per identificativo dell'obbligazione (numero cartella/documento,
  riferimento contrattuale univoco, snapshot temporale sul medesimo codice fiscale).
- NON deduplica mai in base al solo importo, al solo nome del creditore/intermediario,
  alla mera presenza di un estratto AdER o di una posizione CR.
- Conserva i debiti tributari/contributivi non affidati alla riscossione accanto ad AdER.
- Garantisce l'omogeneità temporale della Centrale Rischi (non somma mai mensilità differenti;
  se manca un periodo attendibile dichiara la massa CR non verificabile).
- Separa esposizioni certe per cassa, rischi di firma/garanzie, contestate/non quantificate,
  cessioni del credito, posizioni estinte e piani di pagamento.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.entities import (
    Case,
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
_TRIB_TOKENS = ("erar", "tribut", "fisc", "ader", "agenzia", "inps", "inail", "cartella", "impost", "iva", "f24")
_NON_ADER_TAX_TOKENS = (
    "non affidat",
    "non a ruolo",
    "avviso bonario",
    "bonario",
    "corrente",
    "autoliquid",
    "dichiarativ",
    "f24",
    "comunicazione irregolarit",
    "accertamento non iscritto",
)
_ADER_ROLE_TOKENS = ("ader", "cartella", "ruolo", "riscossione", "intimazione")
_BANC_TOKENS = ("banc", "mutu", "finanziament", "prestit", "leasing", "fido", "carta", "crif", "ctc")

_CONTRACT_REF_RE = re.compile(
    r"(?:contratto|contr\.?|rif\.?|pratica|prat\.?|rapporto|iban|id|n\.?|nr\.?)\s*[:#°\- ]*\s*([A-Z0-9][A-Z0-9\-\/_.]{2,})",
    re.IGNORECASE,
)
_CARTELLA_NUM_RE = re.compile(r"\b(\d{12,22})\b")

_MONTH_NAMES = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
    "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
    "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
}


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


def _extract_contract_refs(*texts: str) -> set[str]:
    """Estrae solo riferimenti contrattuali/identificativi univoci (richiede almeno una cifra)."""
    refs: set[str] = set()
    blob = " ".join(t for t in texts if t)
    for m in _CONTRACT_REF_RE.finditer(blob):
        cand = m.group(1).strip(" .,:;").upper()
        if any(ch.isdigit() for ch in cand):
            refs.add(cand)
    for m in _CARTELLA_NUM_RE.finditer(blob):
        refs.add(m.group(1))
    return refs


def _normalize_cr_month(raw: Optional[str]) -> Optional[str]:
    """Normalizza una mensilità CR in formato canonico YYYY-MM; None se non attendibile."""
    if not raw:
        return None
    s = str(raw).strip().lower()
    if not s:
        return None
    m_ym = re.match(r"^((?:19|20)\d{2})[-/](\d{1,2})(?:[-/]\d{1,2})?$", s)
    if m_ym:
        yr, mo = int(m_ym.group(1)), int(m_ym.group(2))
        if 1 <= mo <= 12:
            return f"{yr:04d}-{mo:02d}"
    m_my = re.match(r"^(\d{1,2})[-/]((?:19|20)\d{2})$", s)
    if m_my:
        mo, yr = int(m_my.group(1)), int(m_my.group(2))
        if 1 <= mo <= 12:
            return f"{yr:04d}-{mo:02d}"
    for name, num in _MONTH_NAMES.items():
        if name in s:
            ym = re.search(r"((?:19|20)\d{2})", s)
            if ym:
                return f"{ym.group(1)}-{num}"
    return None


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
    """Costruisce la riconciliazione debitoria unificata per i 7 bucket senza deduplicazioni euristiche."""
    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in BUCKET_NAMES}
    deduplication_log: list[dict[str, Any]] = []
    reconciliation_notes: list[str] = []
    reconciliation_required: list[dict[str, Any]] = []
    missing_sources_to_acquire: list[str] = []

    tax_statements: list[TaxDebtStatement] = list(case.tax_debt_statements or [])
    credit_exposures: list[CreditExposure] = list(case.credit_exposures or [])
    cr_summaries: list[CreditReportSummary] = list(case.cr_summaries or [])
    guarantees: list[GuaranteeGiven] = list(case.guarantees_given or [])
    positions: list[DebtPosition] = list(case.positions or [])
    latest_fs = _latest_closed_client_fs(db, case)

    # ------------------------------------------------------------------
    # 1. Fonti AdER deduplicate per (codice_fiscale, owner_kind) + numero cartella
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
                "reason": "Snapshot AdER precedente sullo stesso codice fiscale: mantenuta estrazione più recente.",
            })
            continue
        latest_aer[key] = st

    has_aer_source = bool(latest_aer)
    seen_cartelle: set[str] = set()
    seen_cartella_raw_nums: set[str] = set()
    aer_cash_total = Decimal("0.00")

    for st in latest_aer.values():
        items = list(st.items or [])
        if items:
            for it in items:
                doc_num = (it.numero_documento or "").strip()
                if doc_num:
                    dedup_key = f"{(st.codice_fiscale or '').upper()}:{doc_num.upper()}"
                    if dedup_key in seen_cartelle:
                        deduplication_log.append({
                            "key": f"Cartella:{dedup_key}",
                            "kept_source": st.id,
                            "dropped_source": it.id,
                            "dropped_amount": _as_float(_d(it.totale_residuo)),
                            "reason": "Identico numero documento/cartella presente su estratti AdER.",
                        })
                        continue
                    seen_cartelle.add(dedup_key)
                    seen_cartella_raw_nums.add(doc_num.upper())

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
    # 2. Centrale Rischi: omogeneità temporale + 4 categorie distinte
    # ------------------------------------------------------------------
    cr_cash_total = Decimal("0.00")
    cr_firma_total = Decimal("0.00")
    cr_garanzie_total = Decimal("0.00")
    cr_accordato_unused_total = Decimal("0.00")

    cr_contract_refs: set[str] = set()
    cr_exact_signatures: set[tuple[str, str, str, str]] = set()
    cr_intermediary_cash: dict[str, Decimal] = {}

    has_cr_source = bool(credit_exposures or cr_summaries)
    cr_reference_period: Optional[str] = None
    cr_temporal_status = "ASSENTE"
    cr_superseded_periods: list[str] = []
    cr_period_unverifiable = False

    if credit_exposures:
        dated_pairs = [(exp, _normalize_cr_month(exp.reference_month)) for exp in credit_exposures]
        valid_months = sorted({m for _, m in dated_pairs if m})
        undated_exps = [exp for exp, m in dated_pairs if m is None]

        summary_months = sorted({
            m for s in cr_summaries
            for m in [_normalize_cr_month(s.most_recent_month)]
            if m
        })

        active_exposures: list[CreditExposure] = []
        if valid_months:
            cr_reference_period = valid_months[-1]
            cr_superseded_periods = [m for m in valid_months if m != cr_reference_period]
            active_exposures = [exp for exp, m in dated_pairs if m == cr_reference_period]
            if cr_superseded_periods:
                cr_temporal_status = "OMOGENEO_ULTIMA_MENSILITA"
                deduplication_log.append({
                    "key": "CR:MensilitaPrecedenti",
                    "kept_source": f"Centrale Rischi periodo {cr_reference_period}",
                    "dropped_source": f"Mensilità anteriori CR: {', '.join(cr_superseded_periods)}",
                    "dropped_amount": None,
                    "reason": "Selezionata esclusivamente la mensilità CR omogenea più recente per evitare somma di snapshot temporali diversi.",
                })
            else:
                cr_temporal_status = "OMOGENEO"

            if undated_exps:
                reconciliation_required.append({
                    "code": "RICONCILIAZIONE_CR_RIGHE_SENZA_DATA",
                    "area": "Centrale Rischi",
                    "message": (
                        f"Presenti {len(undated_exps)} righe CR prive di mensilità accanto al periodo {cr_reference_period}: "
                        "escluse dal totale per garantire omogeneità temporale."
                    ),
                })
        elif len(summary_months) == 1:
            cr_reference_period = summary_months[0]
            cr_temporal_status = "OMOGENEO_DA_RIEPILOGO"
            active_exposures = list(credit_exposures)
        else:
            cr_temporal_status = "PERIODO_NON_ATTENDIBILE"
            cr_period_unverifiable = True
            missing_sources_to_acquire.append(
                "Centrale Rischi Banca d'Italia con indicazione esplicita della mensilità di riferimento (periodo omogeneo)."
            )
            reconciliation_notes.append(
                "Centrale Rischi priva di mensilità attendibile o con mensilità ambigue: totale CR dichiarato NON VERIFICABILE."
            )

        for exp in active_exposures:
            cat_stat = f"{exp.category or ''} {exp.status or ''}".lower()
            interm = (exp.intermediary or "").strip()
            ut = _d(exp.utilizzato) or Decimal("0.00")
            acc = _d(exp.accordato) or Decimal("0.00")
            cr_contract_refs.update(_extract_contract_refs(interm, exp.category or "", exp.status or ""))
            if (exp.source_document_id or "").strip():
                cr_exact_signatures.add((
                    exp.source_document_id.strip(),
                    interm.lower(),
                    (exp.category or "").strip().lower(),
                    str(_q2(ut)),
                ))

            if any(tok in cat_stat for tok in _ESTINTO_TOKENS):
                buckets["estinte_e_piani_pagamento"].append(_entry(
                    source="Centrale Rischi",
                    creditor=interm or "Intermediario CR",
                    description=f"Posizione estinta/chiusa ({exp.category or 'CR'}) [{cr_reference_period}]",
                    amount=Decimal("0.00"),
                    exposure_kind="estinta",
                    evidence_level="documentata",
                    status="estinto",
                    reference_id=exp.id,
                    extra={"reference_month": cr_reference_period},
                ))
                continue

            if any(tok in cat_stat for tok in _FIRMA_TOKENS):
                firma_val = ut if ut > 0 else acc
                if firma_val > 0:
                    cr_firma_total += firma_val
                    buckets["coobbligazioni_garanzie"].append(_entry(
                        source="Centrale Rischi (rischi di firma)",
                        creditor=interm or "Intermediario CR",
                        description=f"{exp.category or 'Rischi di firma / garanzie'} [{cr_reference_period}]",
                        amount=firma_val,
                        exposure_kind="firma_garanzia",
                        evidence_level="documentata",
                        status="firma",
                        reference_id=exp.id,
                        extra={"reference_month": cr_reference_period, "firma_subkind": "rischi_di_firma"},
                    ))
                continue

            if _is_cession_text(f"{interm} {exp.category or ''} {exp.status or ''}"):
                if ut > 0:
                    cr_cash_total += ut
                    buckets["cessioni_credito"].append(_entry(
                        source="Centrale Rischi (cessionario)",
                        creditor=interm,
                        description=f"{exp.category or 'Credito ceduto segnalato in CR'} [{cr_reference_period}]",
                        amount=ut,
                        exposure_kind="cassa",
                        evidence_level="documentata",
                        status="attivo",
                        reference_id=exp.id,
                        extra={"reference_month": cr_reference_period},
                    ))
                continue

            if acc > ut:
                cr_accordato_unused_total += (acc - ut)

            if ut > 0:
                cr_cash_total += ut
                if interm:
                    cr_intermediary_cash[interm.lower()] = cr_intermediary_cash.get(interm.lower(), Decimal("0.00")) + ut
                buckets["bancari_finanziari"].append(_entry(
                    source="Centrale Rischi (Banca d'Italia)",
                    creditor=interm or "Intermediario CR",
                    description=f"{exp.category or 'Esposizione per cassa'} [{cr_reference_period}]",
                    amount=ut,
                    exposure_kind="cassa",
                    evidence_level="documentata",
                    status="attivo",
                    reference_id=exp.id,
                    extra={
                        "reference_month": cr_reference_period,
                        "accordato_totale": _as_float(acc),
                        "accordato_inutilizzato": _as_float(max(Decimal("0.00"), acc - ut)),
                    },
                ))

        if cr_summaries and not cr_period_unverifiable:
            deduplication_log.append({
                "key": "CR:SummaryVsExposures",
                "kept_source": f"CreditExposure CR ({len(active_exposures)} righe al {cr_reference_period})",
                "dropped_source": "CreditReportSummary.total_exposure",
                "dropped_amount": _as_float(_d(cr_summaries[0].total_exposure)),
                "reason": "Dettaglio analitico CreditExposure omogeneo già presente per il periodo selezionato.",
            })
    elif cr_summaries:
        dated_summaries = [
            (s, _normalize_cr_month(s.most_recent_month))
            for s in cr_summaries
        ]
        valid_sum_months = sorted({m for _, m in dated_summaries if m})
        if valid_sum_months:
            cr_reference_period = valid_sum_months[-1]
            cr_superseded_periods = [m for m in valid_sum_months if m != cr_reference_period]
            cr_temporal_status = "OMOGENEO_ULTIMA_MENSILITA" if cr_superseded_periods else "OMOGENEO"
            latest_cr = sorted(
                [s for s, m in dated_summaries if m == cr_reference_period],
                key=lambda c: str(c.id or ""),
                reverse=True,
            )[0]
            cr_exp = _d(latest_cr.total_exposure) or Decimal("0.00")
            cr_gar = _d(latest_cr.total_guarantees) or Decimal("0.00")
            if cr_exp > 0:
                cr_cash_total += cr_exp
                buckets["bancari_finanziari"].append(_entry(
                    source="Centrale Rischi (sintesi)",
                    creditor="Intermediari segnalanti CR",
                    description=f"Esposizione per cassa al {cr_reference_period}",
                    amount=cr_exp,
                    exposure_kind="cassa",
                    evidence_level="documentata",
                    status="attivo",
                    reference_id=latest_cr.id,
                    extra={"reference_month": cr_reference_period},
                ))
            if cr_gar > 0 and not guarantees:
                cr_garanzie_total += cr_gar
                buckets["coobbligazioni_garanzie"].append(_entry(
                    source="Centrale Rischi (garanzie sintesi)",
                    creditor="Intermediari CR",
                    description=f"Garanzie prestate da riepilogo CR [{cr_reference_period}]",
                    amount=cr_gar,
                    exposure_kind="firma_garanzia",
                    evidence_level="documentata",
                    status="firma",
                    reference_id=latest_cr.id,
                    extra={"reference_month": cr_reference_period, "firma_subkind": "garanzie_prestate"},
                ))
        else:
            cr_temporal_status = "PERIODO_NON_ATTENDIBILE"
            cr_period_unverifiable = True
            missing_sources_to_acquire.append(
                "Centrale Rischi Banca d'Italia con indicazione esplicita della mensilità di riferimento."
            )
            reconciliation_notes.append(
                "Riepilogo Centrale Rischi privo di mensilità attendibile: totale CR non verificabile."
            )

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
            cr_garanzie_total += gar_amt
            buckets["coobbligazioni_garanzie"].append(_entry(
                source="Garanzie prestate",
                creditor=g.intermediary or "Istituto",
                description=f"Garanzia/fideiussione per {g.guaranteed_subject or 'terzo'}",
                amount=gar_amt,
                exposure_kind="firma_garanzia",
                evidence_level="documentata",
                status="firma",
                reference_id=g.id,
                extra={"firma_subkind": "garanzie_prestate"},
            ))

    # ------------------------------------------------------------------
    # 3. DebtPosition: deduplica SOLO su identificativi univoci dell'obbligazione
    # ------------------------------------------------------------------
    cession_records: list[tuple[DebtPosition, set[str], Decimal]] = []
    non_cession_bank_positions: list[tuple[DebtPosition, set[str], Decimal, str, str]] = []

    for pos in positions:
        text_pos = f"{pos.creditor_name or ''} {pos.debt_type or ''} {pos.status or ''}"
        st_lower = (pos.status or "").lower()
        ev_lvl = "documentata" if ((pos.source_document_id or "").strip() or bool(pos.validated)) else "riferita"
        res_amt = _d(pos.residual_amount)
        pos_refs = _extract_contract_refs(pos.creditor_name or "", pos.debt_type or "", pos.status or "")

        if any(tok in st_lower for tok in _ESTINTO_TOKENS) or (
            res_amt == 0 and not pos.monthly_installment and not any(tok in st_lower for tok in _CONTESTATO_TOKENS)
        ):
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
            cession_records.append((pos, pos_refs, _q2(res_amt)))
            buckets["cessioni_credito"].append(_entry(
                source="Posizione ceduta (SPV / Servicer)",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Credito oggetto di cessione",
                amount=res_amt,
                exposure_kind="cassa",
                evidence_level=ev_lvl,
                status="attivo",
                reference_id=pos.id,
                notes="Verificare notifica ex art. 1264 c.c. / G.U. ex art. 58 TUB e identità rispetto al cedente.",
                extra={"contract_refs": sorted(pos_refs)},
            ))
            continue

        if any(tok in f"{pos.debt_type or ''} {pos.status or ''}".lower() for tok in _FIRMA_TOKENS):
            cr_garanzie_total += res_amt
            buckets["coobbligazioni_garanzie"].append(_entry(
                source="Posizione coobbligazione/garanzia",
                creditor=pos.creditor_name,
                description=pos.debt_type or "Coobbligazione / Garanzia",
                amount=res_amt,
                exposure_kind="firma_garanzia",
                evidence_level=ev_lvl,
                status="firma",
                reference_id=pos.id,
                extra={"firma_subkind": "garanzie_prestate"},
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

        text_lower = f"{pos.creditor_name or ''} {pos.debt_type or ''} {pos.status or ''}".lower()
        if any(tok in text_lower for tok in _TRIB_TOKENS):
            # Deduplica SOLO per numero documento/cartella riconducibile ad AdER;
            # i debiti tributari non affidati alla riscossione restano sempre conservati!
            is_explicit_non_ader = any(tok in text_lower for tok in _NON_ADER_TAX_TOKENS)
            matched_cartelle = pos_refs.intersection(seen_cartella_raw_nums)
            if has_aer_source and matched_cartelle:
                deduplication_log.append({
                    "key": f"TaxCartella:{','.join(sorted(matched_cartelle))}",
                    "kept_source": "AdER (TaxDebtStatement)",
                    "dropped_source": f"DebtPosition:{pos.id} ({pos.creditor_name})",
                    "dropped_amount": _as_float(res_amt),
                    "reason": "Identico numero cartella già presente nell'estratto AdER.",
                })
                continue

            if has_aer_source and (not is_explicit_non_ader) and any(tok in text_lower for tok in _ADER_ROLE_TOKENS):
                reconciliation_required.append({
                    "code": f"RICONCILIAZIONE_ADER_{pos.id}",
                    "area": "Debiti tributari / AdER",
                    "message": (
                        f"Posizione tributaria '{pos.creditor_name}' (€ {res_amt:,.2f}) richiama ruoli/AdER senza "
                        "numero cartella riconducibile agli estratti AdER acquisiti: conservate entrambe in attesa di riconciliazione."
                    ),
                })

            buckets["tributari_contributivi"].append(_entry(
                source="Posizione fiscale/contributiva" + (" (non affidata ad AdER)" if is_explicit_non_ader else ""),
                creditor=pos.creditor_name,
                description=pos.debt_type or "Debito tributario/previdenziale",
                amount=res_amt,
                exposure_kind="cassa",
                evidence_level=ev_lvl,
                status="attivo",
                reference_id=pos.id,
                extra={"non_affidato_ader": is_explicit_non_ader, "contract_refs": sorted(pos_refs)},
            ))
            continue

        if any(tok in text_lower for tok in _BANC_TOKENS):
            non_cession_bank_positions.append((pos, pos_refs, _q2(res_amt), ev_lvl, text_lower))
            continue

        # Posizioni commerciali / fornitori / dipendenti (mai deduplicate per solo importo)
        buckets["fornitori_dipendenti"].append(_entry(
            source="Posizione commerciale / personale",
            creditor=pos.creditor_name,
            description=pos.debt_type or "Debito commerciale / dipendenti / altro",
            amount=res_amt,
            exposure_kind="cassa",
            evidence_level=ev_lvl,
            status="attivo",
            reference_id=pos.id,
            extra={"contract_refs": sorted(pos_refs)},
        ))

    # Valuta le DebtPosition bancarie con criterio rigoroso di identità (contratto/sigla doc, MAI solo nome o importo!)
    for pos, pos_refs, res_amt, ev_lvl, _txt in non_cession_bank_positions:
        # 1) Cessione credito: deduplica SOLO se riferimento contrattuale coincidente!
        matched_cession = next(
            ((c_pos, c_refs) for c_pos, c_refs, _c_amt in cession_records if pos_refs and pos_refs.intersection(c_refs)),
            None,
        )
        if matched_cession is not None:
            c_pos, c_refs = matched_cession
            shared = sorted(pos_refs.intersection(c_refs))
            deduplication_log.append({
                "key": f"CedenteVsCessionario:{','.join(shared)}",
                "kept_source": f"DebtPosition:{c_pos.id} ({c_pos.creditor_name})",
                "dropped_source": f"DebtPosition:{pos.id} ({pos.creditor_name})",
                "dropped_amount": _as_float(res_amt),
                "reason": f"Identico riferimento contrattuale {', '.join(shared)} tra cedente e cessionario.",
            })
            continue

        # Se non condividono riferimento contrattuale ma l'importo coincide con una cessione,
        # CONSERVA entrambe le posizioni e segnala RICONCILIAZIONE_NECESSARIA!
        possible_amt_cession = any(c_amt == res_amt for _cp, _cr, c_amt in cession_records)
        if possible_amt_cession:
            reconciliation_required.append({
                "code": f"RICONCILIAZIONE_CESSIONE_{pos.id}",
                "area": "Cessioni del credito",
                "message": (
                    f"Posizione '{pos.creditor_name}' (€ {res_amt:,.2f}) ha pari importo rispetto a una cessione credito "
                    "ma nessun riferimento contrattuale condiviso: conservate entrambe, richiesta riconciliazione."
                ),
            })

        # 2) Centrale Rischi: deduplica SOLO con riferimento contrattuale condiviso o firma esatta documento+istituto+categoria+importo
        cred_norm = (pos.creditor_name or "").strip().lower()
        shared_cr_refs = pos_refs.intersection(cr_contract_refs)
        exact_sig = (
            (pos.source_document_id or "").strip(),
            cred_norm,
            (pos.debt_type or "").strip().lower(),
            str(_q2(res_amt)),
        )
        if shared_cr_refs or ((pos.source_document_id or "").strip() and exact_sig in cr_exact_signatures):
            deduplication_log.append({
                "key": f"CRVsDebtPosRef:{','.join(sorted(shared_cr_refs)) or pos.source_document_id}",
                "kept_source": f"CreditExposure CR ({cr_reference_period or 'CR'})",
                "dropped_source": f"DebtPosition:{pos.id} ({pos.creditor_name})",
                "dropped_amount": _as_float(res_amt),
                "reason": "Identificativo contrattuale o documento sorgente coincidente con Centrale Rischi.",
            })
            continue

        # Stesso intermediario in CR senza riferimento contrattuale univoco:
        # NON accorpare né eliminare automaticamente -> conserva entrambe e richiedi riconciliazione
        if not cr_period_unverifiable and cred_norm and cred_norm in cr_intermediary_cash:
            reconciliation_required.append({
                "code": f"RICONCILIAZIONE_BANCA_CR_{pos.id}",
                "area": "Bancari e finanziari",
                "message": (
                    f"Posizione '{pos.creditor_name}' (€ {res_amt:,.2f}) insiste su intermediario già segnalato in CR "
                    f"({cr_reference_period}) senza identificativo contrattuale univoco: conservate entrambe le posizioni "
                    "in attesa di riconciliazione."
                ),
            })

        buckets["bancari_finanziari"].append(_entry(
            source="CTC / CRIF / Finanziamenti",
            creditor=pos.creditor_name,
            description=pos.debt_type or "Finanziamento / credito",
            amount=res_amt,
            exposure_kind="cassa",
            evidence_level=ev_lvl,
            status="attivo",
            reference_id=pos.id,
            extra={"contract_refs": sorted(pos_refs)},
        ))

    # ------------------------------------------------------------------
    # 4. Integrazione e riconciliazione con il Bilancio d'esercizio più recente
    # ------------------------------------------------------------------
    fs_raw = (latest_fs.raw_extraction or {}) if (latest_fs and isinstance(latest_fs.raw_extraction, dict)) else {}
    fs_deb = fs_raw.get("debiti_per_natura") if isinstance(fs_raw.get("debiti_per_natura"), dict) else {}

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

        if has_aer_source:
            if fs_trib > 0:
                delta_trib = _q2(aer_cash_total - fs_trib)
                balance_sheet_comparison["tributari_ader_vs_bilancio"] = {
                    "ader_netto": _as_float(aer_cash_total),
                    "bilancio": _as_float(fs_trib),
                    "delta": _as_float(delta_trib),
                }
                if abs(delta_trib) > Decimal("1.00"):
                    msg_t = (
                        f"Scostamento tributario/previdenziale ({fs_period}): AdER netto € {aer_cash_total:,.2f} "
                        f"vs bilancio € {fs_trib:,.2f} (delta € {delta_trib:,.2f})."
                    )
                    reconciliation_notes.append(msg_t)
                    reconciliation_required.append({
                        "code": "RICONCILIAZIONE_TRIBUTARI_ADER_BILANCIO",
                        "area": "Debiti tributari",
                        "message": msg_t,
                    })
                deduplication_log.append({
                    "key": "Tributari:AdERVsBilancio",
                    "kept_source": "AdER (estratti di ruolo)",
                    "dropped_source": f"Bilancio {fs_period} (tributari+previdenziali)",
                    "dropped_amount": _as_float(fs_trib),
                    "reason": "Confronto AdER vs voce aggregata tributari di bilancio.",
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

        if has_cr_source and not cr_period_unverifiable:
            if fs_banche is not None and fs_banche > 0:
                delta_banche = _q2(cr_cash_total - fs_banche)
                balance_sheet_comparison["bancari_cr_vs_bilancio"] = {
                    "cr_cassa": _as_float(cr_cash_total),
                    "bilancio_banche": _as_float(fs_banche),
                    "delta": _as_float(delta_banche),
                }
                if abs(delta_banche) > Decimal("1.00"):
                    msg_b = (
                        f"Scostamento bancario ({fs_period}): CR cassa € {cr_cash_total:,.2f} "
                        f"vs bilancio banche € {fs_banche:,.2f} (delta € {delta_banche:,.2f})."
                    )
                    reconciliation_notes.append(msg_b)
                    reconciliation_required.append({
                        "code": "RICONCILIAZIONE_BANCHE_CR_BILANCIO",
                        "area": "Bancari e finanziari",
                        "message": msg_b,
                    })
                deduplication_log.append({
                    "key": "Banche:CRVsBilancio",
                    "kept_source": f"Centrale Rischi ({cr_reference_period})",
                    "dropped_source": f"Bilancio {fs_period} (banche)",
                    "dropped_amount": _as_float(fs_banche),
                    "reason": "Confronto CR omogenea vs voce aggregata banche di bilancio.",
                })
        elif fs_banche is not None and fs_banche > 0:
            buckets["bancari_finanziari"].append(_entry(
                source=f"Bilancio ({fs_period})",
                creditor="Banche e Istituti finanziari",
                description="Debiti verso banche da bilancio",
                amount=fs_banche,
                exposure_kind="cassa",
                evidence_level="documentata",
                status="attivo",
                reference_id=latest_fs.id,
            ))

        # Debiti commerciali / TFR / dipendenti / soci da bilancio
        existing_comm = sum(
            ((_d(e["amount_exact"]) or Decimal("0.00")) for e in buckets["fornitori_dipendenti"]),
            Decimal("0.00"),
        )
        if existing_comm > Decimal("0.00") and (fs_forn or Decimal("0.00")) > Decimal("0.00"):
            reconciliation_required.append({
                "code": "RICONCILIAZIONE_FORNITORI_BILANCIO_VS_POSIZIONI",
                "area": "Fornitori e commerciali",
                "message": (
                    f"Presenti sia posizioni analitiche fornitori/commerciali (€ {existing_comm:,.2f}) sia voce "
                    f"aggregata fornitori di bilancio (€ {fs_forn:,.2f}): richiesta riconciliazione puntuale."
                ),
            })
        elif fs_forn is not None and fs_forn > 0:
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

        fs_tot_debts = _d(latest_fs.total_debts)
        if fs_tot_debts is not None:
            balance_sheet_comparison["bilancio_debiti_totali"] = _as_float(fs_tot_debts)

    # ------------------------------------------------------------------
    # 5. Calcolo totali in Decimal esatto e determinazione stato_dato
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

    if cr_period_unverifiable:
        stato_dato = "NON_VERIFICABILE_NULL"
        cassa_out = None
        cassa_exact_out = "NULL"
        doc_cassa_out = None
        rif_cassa_out = None
    elif not has_any_debt_source:
        stato_dato = "NON_VERIFICABILE_NULL"
        cassa_out = None
        cassa_exact_out = "NULL"
        doc_cassa_out = None
        rif_cassa_out = None
    elif reconciliation_required:
        stato_dato = "RICONCILIAZIONE_NECESSARIA"
        cassa_out = _as_float(total_cassa_certe)
        cassa_exact_out = str(total_cassa_certe)
        doc_cassa_out = _as_float(total_doc_cassa)
        rif_cassa_out = _as_float(total_rif_cassa)
    else:
        stato_dato = "VERIFICATO"
        cassa_out = _as_float(total_cassa_certe)
        cassa_exact_out = str(total_cassa_certe)
        doc_cassa_out = _as_float(total_doc_cassa)
        rif_cassa_out = _as_float(total_rif_cassa)

    bucket_totals = {
        name: _as_float(_q2(sum(((_d(it["amount_exact"]) or Decimal("0.00")) for it in lst), Decimal("0.00"))))
        for name, lst in buckets.items()
    }

    return {
        "stato_dato": stato_dato,
        "riconciliazione_necessaria": bool(reconciliation_required),
        "reconciliation_required": reconciliation_required,
        "missing_sources_to_acquire": missing_sources_to_acquire,
        "cr_reference_period": cr_reference_period,
        "cr_temporal_status": cr_temporal_status,
        "cr_superseded_periods": cr_superseded_periods,
        "cr_breakdown": {
            "cassa_effettiva": _as_float(cr_cash_total) if (has_cr_source and not cr_period_unverifiable) else None,
            "rischi_di_firma": _as_float(cr_firma_total) if (has_cr_source and not cr_period_unverifiable) else None,
            "garanzie_prestate": _as_float(cr_garanzie_total) if (has_cr_source or guarantees) and not cr_period_unverifiable else None,
            "accordato_inutilizzato": _as_float(cr_accordato_unused_total) if (credit_exposures and not cr_period_unverifiable) else None,
        },
        "buckets": buckets,
        "bucket_totals": bucket_totals,
        "totals": {
            "esposizioni_per_cassa_certe": cassa_out,
            "esposizioni_per_cassa_certe_exact": cassa_exact_out,
            "esposizioni_di_firma_e_garanzie": _as_float(total_firma_garanzie) if (has_any_debt_source and not cr_period_unverifiable) else None,
            "posizioni_contestate_sospese": _as_float(total_contestate_sospese) if has_any_debt_source else None,
            "posizioni_non_quantificate_count": non_quantificate_count,
            "piani_pagamento_residui": _as_float(total_piani_pagamento) if has_any_debt_source else None,
            "posizioni_documentate_cassa": doc_cassa_out,
            "posizioni_riferite_cassa": rif_cassa_out,
        },
        "deduplication_log": deduplication_log,
        "reconciliation_notes": reconciliation_notes,
        "balance_sheet_comparison": balance_sheet_comparison,
    }
