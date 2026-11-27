"""Formula Engine deterministico per i Protocolli Metodologici A e B (Fase 2).

Consolidamento auditabile e senza duplicazioni rispetto a statutory_knowledge.py:
- EBITDA ordinario CNDCEC 2024 ((A - B) + B10a + B10b + B10c), lasciando visibili B10d, B12, B13.
- EBIT (A - B) e Risultato netto d'esercizio distinti da EBITDA.
- Variazioni economiche triennali (assolute e percentuali).
- Patrimonio netto e quadratura Stato Patrimoniale (solo se SP documentato; mai inventato in semplificata).
- CCN operativo (Rimanenze + Crediti commerciali - Debiti fornitori) e CCN civilistico.
- PFN finanziaria pura ESMA vs PFN gestionale (con debt-like) e riconciliazione, senza duplicazioni.
- Controlli di coerenza tra bilancio, dichiarazioni fiscali e prospetti CR/AdER.
- Viste dedicate Protocollo A (Impresa individuale) e Protocollo B (S.r.l./S.r.l.s.).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.entities import (
    Case,
    Company,
    Debtor,
    Document,
    FinancialStatement,
    RealEstate,
    Vehicle,
)
from app.services.protocols.classifier import (
    ClassificationResult,
    _is_interim_fs,
    _parse_year,
    protocol_code_for_profile,
)
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    evaluate_pfn_ebitda,
    extract_bank_debt_split,
)


def _d(val: Any) -> Optional[Decimal]:
    if val is None or val == "" or isinstance(val, bool) or val in ("n.r.", "N/D", "NULL"):
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, dict):
        for sub in ("corrente", "importo", "valore", "value"):
            if sub in val and val[sub] not in (None, ""):
                return _d(val[sub])
        return None
    try:
        return Decimal(str(val))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _first_not_none(*vals: Optional[Decimal]) -> Optional[Decimal]:
    """Return the first value that is not None (preserving documented Decimal('0'))."""
    for val in vals:
        if val is not None:
            return val
    return None


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _f(val: Optional[Decimal]) -> Optional[float]:
    return float(_q2(val)) if val is not None else None


def _formula_record(
    *,
    code: str,
    label: str,
    formula: str,
    inputs: dict[str, Any],
    source: str,
    period: str,
    value: Optional[Decimal],
    validation_status: str,
    notes: str = "",
) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "formula": formula,
        "inputs": inputs,
        "source": source,
        "period": period,
        "value": _f(value),
        "value_exact": str(_q2(value)) if value is not None else "NULL",
        "validation_status": validation_status,
        "notes": notes,
    }


def _extract_fiscal_revenues_from_docs(docs: list[Document]) -> list[dict[str, Any]]:
    """Estrae eventuali ricavi documentati da dichiarazioni fiscali (Redditi PF/SC/IVA)."""
    out: list[dict[str, Any]] = []
    for doc in docs:
        dt = (doc.doc_type or "").lower()
        if dt not in ("dichiarazione_redditi", "modello_redditi", "iva"):
            continue
        ext = getattr(doc, "extraction", None)
        if not ext or not isinstance(ext.json_output, dict):
            continue
        jo = ext.json_output
        rev: Optional[Decimal] = None
        for key in ("ricavi", "ricavi_vendite", "volume_affari", "componenti_positivi", "ricavi_totali", "rg2", "rf4"):
            cand = _d(jo.get(key))
            if cand is not None:
                rev = cand
                break
        yr = _parse_year(str(jo.get("anno") or jo.get("periodo") or doc.original_filename or ""))
        out.append({
            "document_id": doc.id,
            "filename": doc.original_filename,
            "year": str(yr) if yr else "n/d",
            "ricavi": _f(rev),
            "regime_citato": jo.get("regime_contabile") or jo.get("quadro_fiscale"),
            "stato": "VERIFICATO" if rev is not None else "NON_VERIFICABILE_NULL",
        })
    return out


def _evaluate_period_formulas(
    fs: FinancialStatement,
    *,
    period_label: str,
    source_label: str,
    is_semplificata: bool,
    is_latest_period: bool,
    debt_ledger: dict[str, Any],
) -> dict[str, Any]:
    raw = fs.raw_extraction if isinstance(fs.raw_extraction, dict) else {}
    ce = raw.get("conto_economico") if isinstance(raw.get("conto_economico"), dict) else {}
    sp = raw.get("stato_patrimoniale") if isinstance(raw.get("stato_patrimoniale"), dict) else {}
    deb = raw.get("debiti_per_natura") if isinstance(raw.get("debiti_per_natura"), dict) else {}

    # Normalizza eventuali campi CE dai totali top-level di FinancialStatement se mancanti nel JSON
    ce_in = dict(ce)
    if "ricavi_vendite" not in ce_in and "A1" not in ce_in and fs.revenues is not None:
        ce_in["ricavi_vendite"] = fs.revenues
    if "valore_produzione" not in ce_in and "A" not in ce_in and fs.revenues is not None:
        # Solo se il CE ha anche costi_produzione o differenza_valore_costi non presumiamo A = ricavi se manca B
        pass

    eb_res = calculate_ebitda_oic12(ce_in)
    ebit_dec = _d(eb_res.get("ebit_differenza_a_b"))
    ebitda_dec = _d(eb_res.get("ebitda_standard"))
    b10abc_dec = _d(eb_res.get("ammortamenti_b10a_b10b_b10c"))
    b10d_dec = _d(eb_res.get("svalutazione_crediti_b10d"))
    b12_dec = _d(eb_res.get("accantonamenti_rischi_b12"))
    b13_dec = _d(eb_res.get("altri_accantonamenti_b13"))

    ebit_status = "VERIFICATO" if ebit_dec is not None else "NON_VERIFICABILE_NULL"
    has_b10_det = bool(eb_res.get("b10_dettaglio_disponibile"))
    b10_agg_usato = bool(eb_res.get("b10_aggregato_usato"))
    b10d_escl = bool(eb_res.get("b10d_escludibile"))
    b10_missing = list(eb_res.get("b10_missing_fields") or [])

    if ebit_dec is None or ebitda_dec is None:
        ebitda_val_out: Optional[Decimal] = None
        ebitda_status = "NON_VERIFICABILE_NULL"
        ebitda_note = "Conto Economico insufficiente (NULL)."
    elif has_b10_det:
        ebitda_val_out = ebitda_dec
        ebitda_status = "PARZIALE_CON_AVVISO" if b10_missing else "VERIFICATO"
        ebitda_note = (
            "B10d, B12 e B13 restano visibili nel raccordo e mai neutralizzati automaticamente."
            if not b10_missing
            else f"Componenti B10 assenti ({', '.join(b10_missing)}); B10d/B12/B13 mai neutralizzati."
        )
    elif b10_agg_usato and not b10d_escl:
        # B10 generico senza dettaglio B10a/b/c né B10d -> NON può attestare EBITDA ordinario verificato
        ebitda_val_out = None
        ebitda_status = "NON_VERIFICABILE_NULL"
        ebitda_note = (
            f"Disponibile solo l'aggregato B10 ({eb_res.get('b10_aggregato_valore')}) senza dettaglio "
            f"{', '.join(b10_missing)}: impossibile escludere B10d (svalutazione crediti). EBITDA non verificabile."
        )
    elif b10_agg_usato and b10d_escl:
        ebitda_val_out = ebitda_dec
        ebitda_status = "PARZIALE_CON_AVVISO"
        ebitda_note = (
            f"Calcolato da B10 aggregato al netto di B10d documentato; mancano {', '.join(b10_missing)}."
        )
    else:
        # Nessuna voce B10 disponibile
        ebitda_val_out = ebitda_dec if is_semplificata else None
        ebitda_status = "PARZIALE_CON_AVVISO" if is_semplificata else "NON_VERIFICABILE_NULL"
        ebitda_note = (
            "Regime semplificato privo di dettaglio ammortamenti B10a/b/c: margine esposto pari a EBIT."
            if is_semplificata
            else f"Mancano le componenti {', '.join(b10_missing)} per calcolare l'EBITDA ordinario."
        )

    ebit_rec = _formula_record(
        code="EBIT",
        label="EBIT civilistico (A − B)",
        formula="EBIT = Valore della produzione (A) − Costi della produzione (B)",
        inputs={
            "A_valore_produzione": eb_res.get("valore_produzione_a"),
            "B_costi_produzione": eb_res.get("costi_produzione_b"),
        },
        source=source_label,
        period=period_label,
        value=ebit_dec,
        validation_status=ebit_status,
        notes="Distinto dall'EBITDA (non include reintegro ammortamenti).",
    )

    ebitda_rec = _formula_record(
        code="EBITDA_ORDINARIO",
        label="EBITDA ordinario (CNDCEC 2024)",
        formula="EBITDA = (A − B) + B10a + B10b + B10c",
        inputs={
            "EBIT_A_meno_B": _f(ebit_dec),
            "ammortamenti_B10a_B10b_B10c": _f(b10abc_dec) if has_b10_det else None,
            "B10_aggregato_non_disaggregato": eb_res.get("b10_aggregato_valore"),
            "missing_fields": b10_missing,
            "B10d_svalutazione_crediti_visibile": _f(b10d_dec),
            "B12_accantonamenti_rischi_visibile": _f(b12_dec),
            "B13_altri_accantonamenti_visibile": _f(b13_dec),
        },
        source=source_label,
        period=period_label,
        value=ebitda_val_out,
        validation_status=ebitda_status,
        notes=ebitda_note,
    )

    net_res_dec = _d(ce_in.get("utile_perdita"))
    if net_res_dec is None:
        net_res_dec = _d(fs.net_result)
    net_rec = _formula_record(
        code="RISULTATO_NETTO",
        label="Risultato economico netto dell'esercizio",
        formula="Utile / (Perdita) dell'esercizio [voce 21 art. 2425 c.c.]",
        inputs={"utile_perdita_ce": _f(_d(ce_in.get("utile_perdita"))), "net_result_fs": _f(_d(fs.net_result))},
        source=source_label,
        period=period_label,
        value=net_res_dec,
        validation_status="VERIFICATO" if net_res_dec is not None else "NON_VERIFICABILE_NULL",
    )

    # Stato Patrimoniale, Patrimonio Netto e Quadratura SP (vietato inventare SP in semplificata!)
    sp_quad_aggregata_rec = None
    sp_quad_analitica_rec = None
    if is_semplificata:
        pn_rec = _formula_record(
            code="PATRIMONIO_NETTO",
            label="Patrimonio netto",
            formula="Non applicabile in contabilità semplificata (assenza Stato Patrimoniale ex art. 2424 c.c.)",
            inputs={},
            source=source_label,
            period=period_label,
            value=None,
            validation_status="NON_VERIFICABILE_NULL",
            notes="Regime semplificato: nessun Stato Patrimoniale inventato.",
        )
        sp_quad_rec = _formula_record(
            code="QUADRATURA_SP",
            label="Quadratura Stato Patrimoniale",
            formula="Totale Attivo == Patrimonio Netto + Fondi + TFR + Debiti + Ratei/Risconti Passivi",
            inputs={},
            source=source_label,
            period=period_label,
            value=None,
            validation_status="NON_VERIFICABILE_NULL",
            notes="Non verificabile in contabilità semplificata.",
        )
        sp_quad_aggregata_rec = sp_quad_rec
        sp_quad_analitica_rec = sp_quad_rec
        ccn_op_rec = _formula_record(
            code="CCN_OPERATIVO",
            label="Capitale Circolante Netto Operativo",
            formula="CCN Operativo = Rimanenze + Crediti commerciali − Debiti verso fornitori",
            inputs={},
            source=source_label,
            period=period_label,
            value=None,
            validation_status="NON_VERIFICABILE_NULL",
            notes="Non calcolabile in assenza di Stato Patrimoniale.",
        )
        pfn_esma_rec = _formula_record(
            code="PFN_ESMA_CONFORME",
            label="PFN Conforme ESMA 32-382-1138",
            formula="(Debiti fin. correnti + leasing + m/l + comm. non corr.) − (Liquidità + mezzi equivalenti + att. fin. corr.)",
            inputs={},
            source=source_label,
            period=period_label,
            value=None,
            validation_status="NON_VERIFICABILE_NULL",
            notes="Contabilità semplificata priva di SP.",
        )
        pfn_fin_gest_rec = _formula_record(
            code="PFN_GESTIONALE_SEMPLIFICATA",
            label="PFN finanziaria gestionale semplificata",
            formula="Debiti bancari / finanziari disponibili − Disponibilità liquide",
            inputs={},
            source=source_label,
            period=period_label,
            value=None,
            validation_status="NON_VERIFICABILE_NULL",
            notes="Contabilità semplificata priva di SP.",
        )
        pfn_gest_rec = _formula_record(
            code="PFN_GESTIONALE_DEBT_LIKE",
            label="PFN Gestionale (con debt-like)",
            formula="PFN finanziaria + TFR + Finanziamenti soci + Tributari scaduti + Fornitori oltre 90gg",
            inputs={},
            source=source_label,
            period=period_label,
            value=None,
            validation_status="NON_VERIFICABILE_NULL",
            notes="Contabilità semplificata priva di SP.",
        )
    else:
        tot_att = _d(sp.get("totale_attivo"))
        if tot_att is None and fs.total_assets is not None and (fs.total_assets != 0.0 or bool(sp)):
            tot_att = _d(fs.total_assets)
        pn_dec = _d(sp.get("patrimonio_netto"))
        if pn_dec is None and fs.equity is not None and (fs.equity != 0.0 or bool(sp)):
            pn_dec = _d(fs.equity)
        pn_rec = _formula_record(
            code="PATRIMONIO_NETTO",
            label="Patrimonio netto",
            formula="Capitale + Riserve + Utili/(Perdite) portate a nuovo + Risultato d'esercizio",
            inputs={"patrimonio_netto_sp": _f(_d(sp.get("patrimonio_netto"))), "equity_fs": _f(_d(fs.equity))},
            source=source_label,
            period=period_label,
            value=pn_dec,
            validation_status="VERIFICATO" if pn_dec is not None else "NON_VERIFICABILE_NULL",
        )

        # NULL != 0: mai trasformare fondi, TFR o ratei/risconti passivi mancanti in 0.00!
        fondi_opt = _d(sp.get("fondi_rischi"))
        tfr_opt_sp = _d(sp.get("tfr"))
        debiti_sp_opt = _d(sp.get("debiti_totali"))
        if debiti_sp_opt is None and fs.total_debts is not None and (fs.total_debts != 0.0 or bool(sp)):
            debiti_sp_opt = _d(fs.total_debts)
        ratei_p_opt = _d(sp.get("ratei_risconti_passivi"))
        tot_pass_esplicito = _d(sp.get("totale_passivo"))

        # A) Verifica aggregata (Totale Attivo == Totale Passivo esplicito)
        if tot_att is not None and tot_pass_esplicito is not None:
            scarto_agg = _q2(tot_att - tot_pass_esplicito)
            agg_ok = abs(scarto_agg) <= Decimal("1.00")
            sp_quad_aggregata_rec = _formula_record(
                code="QUADRATURA_SP_AGGREGATA",
                label="Verifica aggregata Stato Patrimoniale",
                formula="Totale Attivo − Totale Passivo esplicito == 0",
                inputs={"totale_attivo": _f(tot_att), "totale_passivo": _f(tot_pass_esplicito)},
                source=source_label,
                period=period_label,
                value=scarto_agg,
                validation_status="VERIFICATO" if agg_ok else "ANOMALIA_QUADRATURA",
                notes="Verifica dei soli totali aggregati di SP.",
            )
        else:
            sp_quad_aggregata_rec = _formula_record(
                code="QUADRATURA_SP_AGGREGATA",
                label="Verifica aggregata Stato Patrimoniale",
                formula="Totale Attivo − Totale Passivo esplicito == 0",
                inputs={"totale_attivo": _f(tot_att), "totale_passivo": _f(tot_pass_esplicito)},
                source=source_label,
                period=period_label,
                value=None,
                validation_status="NON_VERIFICABILE_NULL",
                notes="Totale Attivo o Totale Passivo esplicito non documentato.",
            )

        # B) Quadratura analitica delle componenti (richiede tutte le 5 voci del passivo non NULL)
        sp_missing: list[str] = []
        for k_name, v_opt in (
            ("totale_attivo", tot_att),
            ("patrimonio_netto", pn_dec),
            ("fondi_rischi", fondi_opt),
            ("tfr", tfr_opt_sp),
            ("debiti_totali", debiti_sp_opt),
            ("ratei_risconti_passivi", ratei_p_opt),
        ):
            if v_opt is None:
                sp_missing.append(k_name)

        if not sp_missing:
            passivo_analitico = _q2(pn_dec + fondi_opt + tfr_opt_sp + debiti_sp_opt + ratei_p_opt)
            scarto_an = _q2(tot_att - passivo_analitico)
            an_ok = abs(scarto_an) <= Decimal("1.00")
            sp_quad_analitica_rec = _formula_record(
                code="QUADRATURA_SP_ANALITICA",
                label="Quadratura analitica Stato Patrimoniale",
                formula="Totale Attivo − (PN + Fondi rischi + TFR + Debiti + Ratei/Risconti passivi) == 0",
                inputs={
                    "totale_attivo": _f(tot_att),
                    "patrimonio_netto": _f(pn_dec),
                    "fondi_rischi": _f(fondi_opt),
                    "tfr": _f(tfr_opt_sp),
                    "debiti_totali": _f(debiti_sp_opt),
                    "ratei_risconti_passivi": _f(ratei_p_opt),
                    "totale_passivo_analitico": _f(passivo_analitico),
                },
                source=source_label,
                period=period_label,
                value=scarto_an,
                validation_status="VERIFICATO" if an_ok else "ANOMALIA_QUADRATURA",
                notes="Tutte le componenti analitiche del passivo sono documentate (NULL != 0).",
            )
        else:
            sp_quad_analitica_rec = _formula_record(
                code="QUADRATURA_SP_ANALITICA",
                label="Quadratura analitica Stato Patrimoniale",
                formula="Totale Attivo − (PN + Fondi rischi + TFR + Debiti + Ratei/Risconti passivi) == 0",
                inputs={
                    "totale_attivo": _f(tot_att),
                    "patrimonio_netto": _f(pn_dec),
                    "fondi_rischi": _f(fondi_opt),
                    "tfr": _f(tfr_opt_sp),
                    "debiti_totali": _f(debiti_sp_opt),
                    "ratei_risconti_passivi": _f(ratei_p_opt),
                    "missing_components": sp_missing,
                },
                source=source_label,
                period=period_label,
                value=None,
                validation_status="NON_VERIFICABILE_NULL",
                notes=f"Quadratura analitica non eseguibile (NULL != 0): mancano {', '.join(sp_missing)}.",
            )

        # C) Riepilogo quadratura_sp con distinzione modalità
        if sp_quad_analitica_rec["validation_status"] == "ANOMALIA_QUADRATURA" or sp_quad_aggregata_rec["validation_status"] == "ANOMALIA_QUADRATURA":
            anom_src = sp_quad_analitica_rec if sp_quad_analitica_rec["validation_status"] == "ANOMALIA_QUADRATURA" else sp_quad_aggregata_rec
            sp_quad_rec = _formula_record(
                code="QUADRATURA_SP",
                label="Quadratura Stato Patrimoniale",
                formula=anom_src["formula"],
                inputs={**anom_src["inputs"], "verification_mode": "ANOMALIA"},
                source=source_label,
                period=period_label,
                value=_d(anom_src["value_exact"]),
                validation_status="ANOMALIA_QUADRATURA",
                notes=anom_src["notes"],
            )
        elif sp_quad_analitica_rec["validation_status"] == "VERIFICATO":
            sp_quad_rec = _formula_record(
                code="QUADRATURA_SP",
                label="Quadratura Stato Patrimoniale (Analitica completa)",
                formula=sp_quad_analitica_rec["formula"],
                inputs={**sp_quad_analitica_rec["inputs"], "verification_mode": "ANALITICA_COMPLETA"},
                source=source_label,
                period=period_label,
                value=_d(sp_quad_analitica_rec["value_exact"]),
                validation_status="VERIFICATO",
                notes="Quadratura SP analitica verificata su tutte le componenti (tolleranza € 1,00).",
            )
        elif sp_quad_aggregata_rec["validation_status"] == "VERIFICATO":
            sp_quad_rec = _formula_record(
                code="QUADRATURA_SP",
                label="Quadratura Stato Patrimoniale (Solo aggregata)",
                formula=sp_quad_aggregata_rec["formula"],
                inputs={**sp_quad_aggregata_rec["inputs"], "verification_mode": "AGGREGATA_SOLO_TOTALI", "missing_analytical": sp_missing},
                source=source_label,
                period=period_label,
                value=_d(sp_quad_aggregata_rec["value_exact"]),
                validation_status="PARZIALE_CON_AVVISO",
                notes=f"Quadra il solo totale aggregato Attivo == Passivo; mancano voci analitiche ({', '.join(sp_missing)}).",
            )
        else:
            sp_quad_rec = _formula_record(
                code="QUADRATURA_SP",
                label="Quadratura Stato Patrimoniale",
                formula="Totale Attivo − Passivo analitico == 0",
                inputs={"missing_components": sp_missing, "verification_mode": "NON_VERIFICABILE"},
                source=source_label,
                period=period_label,
                value=None,
                validation_status="NON_VERIFICABILE_NULL",
                notes=f"Componenti SP insufficienti (NULL != 0): mancano {', '.join(sp_missing)}.",
            )

        # CCN Operativo = Rimanenze + Crediti commerciali - Debiti fornitori
        rim_dec = _d(sp.get("rimanenze"))
        cred_comm = _d(sp.get("crediti_clienti")) or _d(sp.get("crediti_commerciali")) or _d(sp.get("crediti_entro"))
        deb_forn = _d(sp.get("debiti_fornitori")) or _d(deb.get("fornitori"))
        if rim_dec is not None and cred_comm is not None and deb_forn is not None:
            ccn_val = _q2(rim_dec + cred_comm - deb_forn)
            ccn_status = "VERIFICATO"
            ccn_note = "CCN operativo calcolato su rimanenze, crediti commerciali e debiti fornitori."
        else:
            ccn_val = None
            ccn_status = "NON_VERIFICABILE_NULL"
            ccn_note = "Richiede tutte e 3 le componenti (Rimanenze, Crediti commerciali, Debiti fornitori)."
        ccn_op_rec = _formula_record(
            code="CCN_OPERATIVO",
            label="Capitale Circolante Netto Operativo",
            formula="CCN Operativo = Rimanenze + Crediti commerciali − Debiti fornitori",
            inputs={
                "rimanenze": _f(rim_dec),
                "crediti_commerciali": _f(cred_comm),
                "debiti_fornitori": _f(deb_forn),
            },
            source=source_label,
            period=period_label,
            value=ccn_val,
            validation_status=ccn_status,
            notes=ccn_note,
        )

        # PFN conforme ESMA vs PFN finanziaria gestionale semplificata vs PFN gestionale con debt-like
        liq_dec = _d(sp.get("disponibilita_liquide"))
        deb_b_breve, deb_b_ml, bank_split_note = extract_bank_debt_split(sp, deb)
        mezzi_eq_dec = _d(sp.get("mezzi_equivalenti_cassa"))
        titoli_fin_dec = _first_not_none(_d(sp.get("titoli_e_crediti_finanziari_correnti")), _d(sp.get("attivita_finanziarie_correnti")))
        leas_b_dec = _first_not_none(_d(deb.get("leasing_breve")), _d(sp.get("debiti_leasing_breve")))
        leas_ml_dec = _first_not_none(_d(deb.get("leasing_oltre")), _d(sp.get("debiti_leasing_oltre")))
        comm_nc_dec = _first_not_none(_d(sp.get("debiti_commerciali_non_correnti")), _d(deb.get("fornitori_oltre")))

        tfr_val_opt = float(tfr_opt_sp) if tfr_opt_sp is not None else None
        fin_soci_dec = _d(deb.get("soci_finanziamenti"))
        fin_soci_in_fin = bool(deb.get("finanziamenti_soci_in_debito_finanziario"))
        forn_90_dec = _d(deb.get("fornitori_scaduti"))

        trib_fs_dec = (_d(deb.get("tributari")) or Decimal("0.00")) + (_d(deb.get("previdenziali")) or Decimal("0.00"))
        if is_latest_period and debt_ledger.get("bucket_totals", {}).get("tributari_contributivi"):
            trib_scad = float(debt_ledger["bucket_totals"]["tributari_contributivi"])
        else:
            trib_scad = float(trib_fs_dec)

        esma_complete = (
            bank_split_note == "split_esplicito_banche"
            and (mezzi_eq_dec is not None or titoli_fin_dec is not None)
            and (leas_b_dec is not None and leas_ml_dec is not None)
            and (comm_nc_dec is not None)
        )

        if liq_dec is not None and (deb_b_breve is not None or deb_b_ml is not None):
            pfn_res = calculate_pfn_esma(
                debiti_bancari_breve=deb_b_breve,
                debiti_bancari_medio_lungo=deb_b_ml,
                disponibilita_liquide=float(liq_dec),
                tfr_fondo=tfr_val_opt,
                finanziamenti_soci=float(fin_soci_dec) if fin_soci_dec is not None else None,
                debiti_tributari_scaduti=trib_scad,
                debiti_fornitori_scaduti_90gg=float(forn_90_dec) if forn_90_dec is not None else None,
                titoli_e_crediti_finanziari_correnti=float(titoli_fin_dec) if titoli_fin_dec is not None else 0.0,
                mezzi_equivalenti_cassa=float(mezzi_eq_dec) if mezzi_eq_dec is not None else None,
                debiti_leasing_breve=float(leas_b_dec) if leas_b_dec is not None else None,
                debiti_leasing_ml=float(leas_ml_dec) if leas_ml_dec is not None else None,
                debiti_commerciali_non_correnti=float(comm_nc_dec) if comm_nc_dec is not None else None,
                finanziamenti_soci_in_debito_finanziario=fin_soci_in_fin,
                esma_schema_completo=esma_complete,
            )
            pfn_esma_dec = _d(pfn_res.get("pfn_esma_conforme"))
            pfn_fin_sempl_dec = _d(pfn_res.get("pfn_finanziaria_gestionale_semplificata"))
            pfn_gest_dec = _d(pfn_res.get("pfn_gestionale_con_debt_like"))

            if esma_complete and pfn_esma_dec is not None:
                pfn_esma_rec = _formula_record(
                    code="PFN_ESMA_CONFORME",
                    label="PFN Conforme ESMA 32-382-1138",
                    formula="(A+B+C+D + J+K+L incluso leasing) − (A+B+C+D liquidità e attività fin. correnti)",
                    inputs={
                        "debiti_bancari_breve": pfn_res.get("debiti_finanziari_breve"),
                        "debiti_bancari_ml": pfn_res.get("debiti_finanziari_medio_lungo"),
                        "componenti_esma": pfn_res.get("componenti_esma"),
                        "disponibilita_liquide": pfn_res.get("disponibilita_liquide"),
                    },
                    source=source_label,
                    period=period_label,
                    value=pfn_esma_dec,
                    validation_status="VERIFICATO",
                    notes="Schema ESMA 32-382-1138 verificato su tutte le componenti pertinenti.",
                )
            else:
                pfn_esma_rec = _formula_record(
                    code="PFN_ESMA_CONFORME",
                    label="PFN Conforme ESMA 32-382-1138",
                    formula="(A+B+C+D + J+K+L) − Liquidità e attività finanziarie correnti ESMA",
                    inputs={
                        "esma_missing_components": pfn_res.get("esma_missing_components"),
                        "metodo_split_banche": bank_split_note,
                        "disponibilita_liquide": pfn_res.get("disponibilita_liquide"),
                    },
                    source=source_label,
                    period=period_label,
                    value=None,
                    validation_status="NON_VERIFICABILE_NULL",
                    notes=(
                        "Dataset incompleto per dichiarare piena conformità ESMA (mancano: "
                        + ", ".join(pfn_res.get("esma_missing_components") or [])
                        + "). Utilizzare PFN_GESTIONALE_SEMPLIFICATA per il solo saldo finanziario documentato."
                    ),
                )

            pfn_fin_gest_rec = _formula_record(
                code="PFN_GESTIONALE_SEMPLIFICATA",
                label="PFN finanziaria gestionale semplificata (non pienamente ESMA)" if not esma_complete else "PFN finanziaria netta gestionale",
                formula="Debiti bancari/finanziari disponibili − Disponibilità liquide",
                inputs={
                    "debiti_bancari_breve": pfn_res.get("debiti_finanziari_breve"),
                    "debiti_bancari_ml": pfn_res.get("debiti_finanziari_medio_lungo"),
                    "disponibilita_liquide": pfn_res.get("disponibilita_liquide"),
                    "metodo_split_banche": bank_split_note,
                    "esma_compliant": esma_complete,
                },
                source=source_label,
                period=period_label,
                value=pfn_fin_sempl_dec,
                validation_status="VERIFICATO" if esma_complete else "PARZIALE_CON_AVVISO",
                notes="Distinta dalla PFN ESMA conforme finché lo schema ESMA completo non è documentato." if not esma_complete else "",
            )

            pfn_gest_rec = _formula_record(
                code="PFN_GESTIONALE_DEBT_LIKE",
                label="PFN Gestionale (con debt-like e riconciliazione)",
                formula="PFN finanziaria base + Debt-like documentati (senza duplicare finanziamenti soci)",
                inputs={
                    "pfn_base_nome": "PFN_ESMA_CONFORME" if esma_complete else "PFN_GESTIONALE_SEMPLIFICATA",
                    "pfn_base_valore": _f(pfn_fin_sempl_dec),
                    "debt_like_items": pfn_res.get("debt_like_items"),
                    "riconciliazione_pfn": pfn_res.get("riconciliazione_pfn"),
                },
                source=source_label,
                period=period_label,
                value=pfn_gest_dec,
                validation_status="VERIFICATO" if esma_complete else "PARZIALE_CON_AVVISO",
            )
        else:
            pfn_esma_rec = _formula_record(
                code="PFN_ESMA_CONFORME",
                label="PFN Conforme ESMA 32-382-1138",
                formula="(A+B+C+D + J+K+L) − Liquidità e attività fin. correnti",
                inputs={"disponibilita_liquide": _f(liq_dec), "deb_b_breve": deb_b_breve, "deb_b_ml": deb_b_ml},
                source=source_label,
                period=period_label,
                value=None,
                validation_status="NON_VERIFICABILE_NULL",
                notes="Disponibilità liquide o passività finanziarie mancanti (NULL).",
            )
            pfn_fin_gest_rec = _formula_record(
                code="PFN_GESTIONALE_SEMPLIFICATA",
                label="PFN finanziaria gestionale semplificata",
                formula="Debiti finanziari disponibili − Disponibilità liquide",
                inputs={"disponibilita_liquide": _f(liq_dec)},
                source=source_label,
                period=period_label,
                value=None,
                validation_status="NON_VERIFICABILE_NULL",
                notes="Disponibilità liquide o passività finanziarie mancanti (NULL).",
            )
            pfn_gest_rec = _formula_record(
                code="PFN_GESTIONALE_DEBT_LIKE",
                label="PFN Gestionale (con debt-like)",
                formula="PFN base + Debt-like items",
                inputs={},
                source=source_label,
                period=period_label,
                value=None,
                validation_status="NON_VERIFICABILE_NULL",
                notes="Disponibilità liquide o passività finanziarie mancanti (NULL).",
            )

    ric_a1 = _d(ce_in.get("ricavi_vendite") if "ricavi_vendite" in ce_in else ce_in.get("A1")) or _d(fs.revenues)
    val_prod_dec = _d(eb_res.get("valore_produzione_a"))

    return {
        "period": period_label,
        "fiscal_year_end": fs.fiscal_year_end,
        "statement_type": fs.statement_type,
        "ricavi_a1": _f(ric_a1),
        "valore_produzione_a": _f(val_prod_dec),
        "ebit": ebit_rec,
        "ebitda": ebitda_rec,
        "risultato_netto": net_rec,
        "patrimonio_netto": pn_rec,
        "quadratura_sp": sp_quad_rec,
        "quadratura_sp_aggregata": sp_quad_aggregata_rec,
        "quadratura_sp_analitica": sp_quad_analitica_rec,
        "ccn_operativo": ccn_op_rec,
        "pfn_esma": pfn_esma_rec,
        "pfn_esma_pura": pfn_esma_rec,
        "pfn_finanziaria_gestionale": pfn_fin_gest_rec,
        "pfn_gestionale": pfn_gest_rec,
        "ebitda_raccordo": eb_res.get("raccordo_bilancio"),
    }


def _compute_triennial_variations(annual_periods: list[dict[str, Any]]) -> dict[str, Any]:
    if len(annual_periods) < 2:
        return {
            "status": "NON_VERIFICABILE_NULL",
            "periods_compared": [p["period"] for p in annual_periods],
            "series": {},
            "notes": "Servono almeno 2 esercizi annuali chiusi per calcolare variazioni economiche.",
        }

    def _extract_metric(p: dict[str, Any], key: str) -> Optional[Decimal]:
        val = p.get(key)
        if isinstance(val, dict):
            return _d(val.get("value_exact"))
        return _d(val)

    metrics = ("ricavi_a1", "valore_produzione_a", "ebit", "ebitda", "risultato_netto")
    series: dict[str, Any] = {}
    for m in metrics:
        yoy: list[dict[str, Any]] = []
        for idx in range(1, len(annual_periods)):
            prev_p = annual_periods[idx - 1]
            cur_p = annual_periods[idx]
            v_prev = _extract_metric(prev_p, m)
            v_cur = _extract_metric(cur_p, m)
            delta = _q2(v_cur - v_prev) if (v_cur is not None and v_prev is not None) else None
            pct = (
                round(float(delta / abs(v_prev) * Decimal("100")), 2)
                if (delta is not None and v_prev is not None and v_prev != 0)
                else None
            )
            yoy.append({
                "from_period": prev_p["period"],
                "to_period": cur_p["period"],
                "from_value": _f(v_prev),
                "to_value": _f(v_cur),
                "delta_eur": _f(delta),
                "delta_pct": pct,
                "stato": "VERIFICATO" if delta is not None else "NON_VERIFICABILE_NULL",
            })

        first_val = _extract_metric(annual_periods[0], m)
        last_val = _extract_metric(annual_periods[-1], m)
        span_delta = _q2(last_val - first_val) if (first_val is not None and last_val is not None) else None
        span_pct = (
            round(float(span_delta / abs(first_val) * Decimal("100")), 2)
            if (span_delta is not None and first_val is not None and first_val != 0)
            else None
        )
        series[m] = {
            "yoy": yoy,
            "period_span": {
                "from_period": annual_periods[0]["period"],
                "to_period": annual_periods[-1]["period"],
                "delta_eur": _f(span_delta),
                "delta_pct": span_pct,
                "stato": "VERIFICATO" if span_delta is not None else "NON_VERIFICABILE_NULL",
            },
        }

    return {
        "status": "VERIFICATO",
        "periods_compared": [p["period"] for p in annual_periods],
        "series": series,
    }


def _build_coherence_checks(
    annual_periods: list[dict[str, Any]],
    fiscal_revs: list[dict[str, Any]],
    debt_ledger: dict[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    # 1. COH-QUAD-01: Distinzione EBIT vs EBITDA coerente (EBITDA - EBIT == B10abc)
    if annual_periods:
        last_p = annual_periods[-1]
        ebit_v = _d(last_p["ebit"].get("value_exact"))
        ebitda_v = _d(last_p["ebitda"].get("value_exact"))
        b10_v = _d((last_p["ebitda"].get("inputs") or {}).get("ammortamenti_B10a_B10b_B10c")) or Decimal("0.00")
        if ebit_v is not None and ebitda_v is not None:
            diff = _q2((ebitda_v - ebit_v) - b10_v)
            ok = abs(diff) <= Decimal("0.01")
            checks.append({
                "check_id": "COH-QUAD-01",
                "title": f"Distinzione EBIT vs EBITDA ordinario ({last_p['period']})",
                "status": "VERIFICATO" if ok else "ANOMALIA_QUADRATURA",
                "delta": float(diff),
                "detail": f"EBIT={ebit_v}, B10abc={b10_v}, EBITDA={ebitda_v}.",
            })
        else:
            checks.append({
                "check_id": "COH-QUAD-01",
                "title": f"Distinzione EBIT vs EBITDA ordinario ({last_p['period']})",
                "status": "NON_VERIFICABILE_NULL",
                "delta": None,
                "detail": "Dati CE insufficienti per la verifica EBIT/EBITDA.",
            })

    # 2. COH-BIL-FISC: Ricavi bilancio vs dichiarazioni fiscali
    matched_fisc = False
    if annual_periods and fiscal_revs:
        by_yr = {str(p["period"]): p for p in annual_periods}
        for fr in fiscal_revs:
            if fr["year"] in by_yr and fr["ricavi"] is not None and by_yr[fr["year"]]["ricavi_a1"] is not None:
                matched_fisc = True
                delta_rev = round(by_yr[fr["year"]]["ricavi_a1"] - fr["ricavi"], 2)
                checks.append({
                    "check_id": f"COH-BIL-FISC-{fr['year']}",
                    "title": f"Coerenza ricavi bilancio vs dichiarazione fiscale ({fr['year']})",
                    "status": "VERIFICATO" if abs(delta_rev) <= 1.0 else "PARZIALE_CON_AVVISO",
                    "delta": delta_rev,
                    "detail": f"Bilancio A1={by_yr[fr['year']]['ricavi_a1']:,.2f} vs Fisco={fr['ricavi']:,.2f}.",
                })
    if not matched_fisc:
        checks.append({
            "check_id": "COH-BIL-FISC",
            "title": "Coerenza ricavi bilancio vs dichiarazioni fiscali",
            "status": "NON_VERIFICABILE_NULL",
            "delta": None,
            "detail": "Mancano ricavi estratti comparabili nello stesso esercizio tra bilancio e dichiarazioni fiscali.",
        })

    # 3. COH-BIL-CR e COH-BIL-ADER da DebtLedger
    comp = debt_ledger.get("balance_sheet_comparison") or {}
    if "bancari_cr_vs_bilancio" in comp:
        bc = comp["bancari_cr_vs_bilancio"]
        checks.append({
            "check_id": "COH-BIL-CR",
            "title": "Coerenza debiti bancari bilancio vs Centrale Rischi",
            "status": "VERIFICATO" if abs(bc["delta"]) <= 1.0 else "PARZIALE_CON_AVVISO",
            "delta": bc["delta"],
            "detail": f"CR cassa={bc['cr_cassa']:,.2f} vs Bilancio banche={bc['bilancio_banche']:,.2f}.",
        })
    if "tributari_ader_vs_bilancio" in comp:
        bt = comp["tributari_ader_vs_bilancio"]
        checks.append({
            "check_id": "COH-BIL-ADER",
            "title": "Coerenza debiti tributari bilancio vs estratto AdER",
            "status": "VERIFICATO" if abs(bt["delta"]) <= 1.0 else "PARZIALE_CON_AVVISO",
            "delta": bt["delta"],
            "detail": f"AdER netto={bt['ader_netto']:,.2f} vs Bilancio tributari/prev.={bt['bilancio']:,.2f}.",
        })

    return checks


def _build_protocol_view(
    db: Session,
    case: Case,
    effective_profile: str,
    effective_regime: str,
    classification: ClassificationResult,
    annual_periods: list[dict[str, Any]],
    fiscal_revs: list[dict[str, Any]],
    debt_ledger: dict[str, Any],
) -> dict[str, Any]:
    effective_protocol = protocol_code_for_profile(effective_profile)
    latest_p = annual_periods[-1] if annual_periods else None

    if effective_protocol == "A":
        debtor: Optional[Debtor] = case.debtor
        real_estates: list[RealEstate] = list(case.real_estates or [])
        vehicles: list[Vehicle] = list(case.vehicles or [])
        re_cad = round(sum(float(r.cadastral_value) for r in real_estates if r.cadastral_value), 2) if real_estates else None
        re_comm = round(sum(float(r.commercial_value) for r in real_estates if r.commercial_value), 2) if any(r.commercial_value for r in real_estates) else None
        veh_val = round(sum(float(v.estimated_value) for v in vehicles if v.estimated_value), 2) if any(v.estimated_value for v in vehicles) else None

        # Adattamento al regime contabile effettivo (ordinaria vs semplificata vs altro/nd)
        if effective_regime == "semplificata":
            economy_block = {
                "metodo_ricostruzione": "CONTABILITA_SEMPLIFICATA_SENZA_SP",
                "nota": "Regime semplificato ex art. 18 DPR 600: nessuno Stato Patrimoniale inventato; economia ricostruita su flussi e dichiarazioni fiscali.",
                "prospetti_fiscali_estratti": fiscal_revs,
                "esercizi_contabili": [
                    {
                        "period": p["period"],
                        "ricavi_a1": p["ricavi_a1"],
                        "ebit": p["ebit"]["value"],
                        "ebitda": p["ebitda"]["value"],
                        "risultato_netto": p["risultato_netto"]["value"],
                        "patrimonio_netto": None,
                    }
                    for p in annual_periods
                ],
            }
        else:
            economy_block = {
                "metodo_ricostruzione": f"REGIME_{effective_regime.upper()}",
                "esercizi_contabili": [
                    {
                        "period": p["period"],
                        "ricavi_a1": p["ricavi_a1"],
                        "ebit": p["ebit"]["value"],
                        "ebitda": p["ebitda"]["value"],
                        "risultato_netto": p["risultato_netto"]["value"],
                        "patrimonio_netto": p["patrimonio_netto"]["value"],
                        "ccn_operativo": p["ccn_operativo"]["value"],
                        "pfn_gestionale": p["pfn_gestionale"]["value"],
                    }
                    for p in annual_periods
                ],
            }

        return {
            "protocol": "A",
            "title": "Protocollo A — Impresa individuale / Ditta individuale",
            "status": "ATTIVO",
            "accounting_regime": effective_regime,
            "ccii_size_qualification": classification.ccii_size_qualification,
            "economia_attivita": economy_block,
            "debiti_pertinenti": {
                "totale_cassa_riconciliato": debt_ledger["totals"]["esposizioni_per_cassa_certe"],
                "bucket_totals": debt_ledger["bucket_totals"],
                "coobbligazioni_garanzie_separate": debt_ledger["totals"]["esposizioni_di_firma_e_garanzie"],
                "nota_art_2740_cc": "Nell'impresa individuale non vi è separazione patrimoniale perfetta ex art. 2740 c.c.: i debiti d'impresa e personali vanno mappati congiuntamente senza doppi conteggi.",
            },
            "patrimonio_e_capacita_imprenditore": {
                "immobili_count": len(real_estates),
                "immobili_valore_catastale": re_cad,
                "immobili_valore_commerciale_dichiarato": re_comm,
                "veicoli_count": len(vehicles),
                "veicoli_valore_stimato_dichiarato": veh_val,
                "reddito_mensile_netto_dichiarato": debtor.monthly_net_income if (debtor and debtor.monthly_net_income) else None,
                "spese_mensili_dichiarate": debtor.monthly_expenses if (debtor and debtor.monthly_expenses) else None,
            },
        }

    if effective_protocol == "B":
        # Protocollo B — S.r.l. / S.r.l.s. (invariante rispetto a soglie CCII!)
        pfn_gest = latest_p["pfn_gestionale"]["value"] if latest_p else None
        ebitda_last = latest_p["ebitda"]["value"] if latest_p else None
        pfn_ebitda_eval = evaluate_pfn_ebitda(pfn_gest, ebitda_last)

        fin_soci_items = [
            it for it in debt_ledger["buckets"]["fornitori_dipendenti"]
            if it.get("sub_category") == "finanziamenti_soci"
        ]
        fin_soci_tot = round(sum(float(it["amount"] or 0.0) for it in fin_soci_items), 2) if fin_soci_items else None

        return {
            "protocol": "B",
            "title": "Protocollo B — Società di capitali (S.r.l. / S.r.l.s.)",
            "status": "ATTIVO",
            "societa_capitali_srl_invariante": True,
            "accounting_regime": effective_regime,
            "ccii_size_qualification": classification.ccii_size_qualification,
            "nota_invarianza_forma": (
                "La S.r.l./S.r.l.s. conserva la qualificazione di società di capitali ex Protocollo B "
                f"indipendentemente dalla qualificazione dimensionale CCII ('{classification.ccii_size_qualification}')."
            ),
            "sintesi_bilanci": [
                {
                    "period": p["period"],
                    "ricavi_a1": p["ricavi_a1"],
                    "ebit": p["ebit"]["value"],
                    "ebitda_ordinario": p["ebitda"]["value"],
                    "risultato_netto": p["risultato_netto"]["value"],
                    "patrimonio_netto": p["patrimonio_netto"]["value"],
                    "quadratura_sp": p["quadratura_sp"]["validation_status"],
                    "ccn_operativo": p["ccn_operativo"]["value"],
                    "pfn_esma_conforme": p["pfn_esma"]["value"],
                    "pfn_finanziaria_gestionale": p["pfn_finanziaria_gestionale"]["value"],
                    "pfn_gestionale": p["pfn_gestionale"]["value"],
                }
                for p in annual_periods
            ],
            "debiti_sociali": {
                "totale_cassa_riconciliato": debt_ledger["totals"]["esposizioni_per_cassa_certe"],
                "bucket_totals": debt_ledger["bucket_totals"],
                "finanziamenti_soci": {
                    "importo": fin_soci_tot,
                    "voci": fin_soci_items,
                    "nota_art_2467_cc": "Verificare condizioni di postergazione ex art. 2467 c.c.",
                },
            },
            "garanzie_personali_e_firma_separate": {
                "totale_garanzie_firma": debt_ledger["totals"]["esposizioni_di_firma_e_garanzie"],
                "posizioni": debt_ledger["buckets"]["coobbligazioni_garanzie"],
                "nota": "Mantenute separate dai debiti sociali per cassa (non sommate due volte).",
            },
            "sostenibilita_finanziaria": {
                "pfn_gestionale": pfn_gest,
                "ebitda_ordinario": ebitda_last,
                "pfn_su_ebitda": pfn_ebitda_eval,
            },
        }

    return {
        "protocol": None,
        "status": "SOSPESO_PROFILO_NON_SUPPORTATO",
        "effective_profile": effective_profile,
        "accounting_regime": effective_regime,
        "ccii_size_qualification": classification.ccii_size_qualification,
        "reason": (
            f"Il profilo '{effective_profile}' non attiva automaticamente né il Protocollo A né il Protocollo B; "
            "sono disponibili i dati di ricognizione nel DebtLedger senza forzature giuridiche."
        ),
    }


def run_formula_engine(
    db: Session,
    case: Case,
    classification: ClassificationResult,
    debt_ledger: dict[str, Any],
) -> dict[str, Any]:
    """Esegue il Formula Engine deterministico (sola lettura, aritmetica Decimal per tutte le formule)."""
    client_companies: list[Company] = [c for c in (case.companies or []) if (c.role or "cliente") == "cliente"]
    company_ids = [c.id for c in client_companies]
    statements: list[FinancialStatement] = []
    if company_ids:
        statements = (
            db.query(FinancialStatement)
            .filter(FinancialStatement.company_id.in_(company_ids))
            .all()
        )

    eff_profile = case.debtor_profile_confirmed or classification.legal_form_profile
    eff_regime = case.accounting_regime_confirmed or classification.accounting_regime
    is_semplificata = (eff_regime == "semplificata")

    annual_fs = [fs for fs in statements if not _is_interim_fs(fs)]
    interim_fs = [fs for fs in statements if _is_interim_fs(fs)]

    annual_fs_sorted = sorted(annual_fs, key=lambda s: (str(s.fiscal_year_end or ""), str(s.id or "")))[-3:]
    annual_periods: list[dict[str, Any]] = []
    for idx, fs in enumerate(annual_fs_sorted):
        yr = _parse_year(fs.fiscal_year_end)
        p_label = str(yr) if yr else (fs.fiscal_year_end or f"Es.{idx + 1}")
        annual_periods.append(
            _evaluate_period_formulas(
                fs,
                period_label=p_label,
                source_label=f"Bilancio {p_label} (FinancialStatement:{fs.id})",
                is_semplificata=is_semplificata,
                is_latest_period=(idx == len(annual_fs_sorted) - 1),
                debt_ledger=debt_ledger,
            )
        )

    interim_periods: list[dict[str, Any]] = []
    for fs in sorted(interim_fs, key=lambda s: (str(s.fiscal_year_end or ""), str(s.id or ""))):
        p_label = f"{fs.fiscal_year_end or 'infrannuale'} (riparametrato)"
        res_int = _evaluate_period_formulas(
            fs,
            period_label=p_label,
            source_label=f"Situazione infrannuale {fs.fiscal_year_end} (non previsionale)",
            is_semplificata=is_semplificata,
            is_latest_period=False,
            debt_ledger=debt_ledger,
        )
        res_int["qualifica_temporale"] = "riparametrato"
        interim_periods.append(res_int)

    docs: list[Document] = list(case.documents or [])
    fiscal_revs = _extract_fiscal_revenues_from_docs(docs)
    triennial_variations = _compute_triennial_variations(annual_periods)
    coherence_checks = _build_coherence_checks(annual_periods, fiscal_revs, debt_ledger)
    protocol_view = _build_protocol_view(
        db,
        case,
        eff_profile,
        eff_regime,
        classification,
        annual_periods,
        fiscal_revs,
        debt_ledger,
    )

    return {
        "engine_version": "ProtocolFormulaEngine-v2-Fase2",
        "ebitda_policy": "CNDCEC_2024: EBITDA = (A - B) + B10a + B10b + B10c; B10d, B12 e B13 visibili non neutralizzati",
        "pfn_policy": "ESMA_2021_v39: PFN_PURA vs PFN_GESTIONALE riconciliate; zero duplicazione banche/AdER",
        "annual_periods": annual_periods,
        "interim_periods": interim_periods,
        "triennial_variations": triennial_variations,
        "fiscal_revenues_extracted": fiscal_revs,
        "coherence_checks": coherence_checks,
        "protocol_view": protocol_view,
    }
