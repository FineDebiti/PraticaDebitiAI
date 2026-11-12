"""Calcolo DETERMINISTICO degli indici di bilancio (mai l'AI).

Input: i blocchi estratti stato_patrimoniale (sp), conto_economico (ce),
debiti_per_natura (deb). Ogni voce SP/CE è {"corrente": x, "precedente": y} o null.
Output: lista di dict indicatore (code, label, group, value_cur, value_prev, fmt,
trend, status, note) pronti per persistenza e frontend.
"""
from typing import Dict, Any, List, Optional
from app.services.indicator_thresholds import thresholds_for, status_for
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    evaluate_pfn_ebitda,
)


def _safe_div(n: Optional[float], d: Optional[float]) -> Optional[float]:
    if n is None or d is None or d == 0.0:
        return None
    return n / d


def _pct(x: Optional[float]) -> Optional[float]:
    return None if x is None else x * 100.0


def _trend(c: Optional[float], p: Optional[float]) -> str:
    if c is None or p is None:
        return "na"
    if abs(c - p) < 1e-9:
        return "flat"
    return "up" if c > p else "down"


def compute_indicators(sp: Dict[str, Any], ce: Dict[str, Any], deb: Dict[str, Any], ateco: Optional[str] = None) -> List[dict]:
    sp, ce, deb = sp or {}, ce or {}, deb or {}
    thr = thresholds_for(ateco)
    out = []

    def cur(key: str, blk: Dict[str, Any] = sp) -> Optional[float]:
        v = blk.get(key)
        if isinstance(v, dict):
            val = v.get("corrente")
            try:
                return float(val) if val not in (None, "") else None
            except (TypeError, ValueError):
                return None
        elif v is not None and not isinstance(v, (list, tuple)):
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
        return None

    def prv(key: str, blk: Dict[str, Any] = sp) -> Optional[float]:
        v = blk.get(key)
        if isinstance(v, dict):
            val = v.get("precedente")
            try:
                return float(val) if val not in (None, "") else None
            except (TypeError, ValueError):
                return None
        return None

    def add(code: str, label: str, group: str, fc: Optional[float], fp: Optional[float], fmt: str, note: str, status_cur: Optional[str] = None) -> None:
        spec = thr.get(code)
        status = status_cur if status_cur is not None else (status_for(spec, fc) if fc is not None else "na")
        fc_val = round(fc, 4) if fc is not None else None
        fp_val = round(fp, 4) if fp is not None else None
        out.append({
            "code": code, "label": label, "group": group,
            "value_cur": fc_val, "value_prev": fp_val, "fmt": fmt,
            "trend": _trend(fc_val, fp_val), "status": status, "note": note,
        })

    # ---- LIQUIDITÀ ----
    add("current_ratio", "Current ratio", "liquidita",
        _safe_div(cur("totale_attivo_circolante"), cur("debiti_entro")),
        _safe_div(prv("totale_attivo_circolante"), prv("debiti_entro")),
        "ratio", "attivo circolante / debiti a breve")

    acid_cur_n = (cur("totale_attivo_circolante") or 0.0) - (cur("rimanenze") or 0.0)
    acid_prv_n = (prv("totale_attivo_circolante") or 0.0) - (prv("rimanenze") or 0.0)
    add("acid_test", "Acid test (quick ratio)", "liquidita",
        _safe_div(acid_cur_n, cur("debiti_entro")) if cur("totale_attivo_circolante") is not None else None,
        _safe_div(acid_prv_n, prv("debiti_entro")) if prv("totale_attivo_circolante") is not None else None,
        "ratio", "(circolante − rimanenze) / debiti a breve")

    add("liquidita_immediata", "Liquidità immediata", "liquidita",
        _safe_div(cur("disponibilita_liquide"), cur("debiti_entro")),
        _safe_div(prv("disponibilita_liquide"), prv("debiti_entro")),
        "ratio", "liquidità / debiti a breve")

    # ---- STRUTTURA / SOLIDITÀ ----
    pn_c, pn_p = cur("patrimonio_netto"), prv("patrimonio_netto")
    add("indip_fin", "Indipendenza finanziaria", "struttura",
        _pct(_safe_div(pn_c, cur("totale_attivo"))),
        _pct(_safe_div(pn_p, prv("totale_attivo"))),
        "pct", "PN / totale attivo")

    add("cop_immob", "Copertura immobilizzazioni", "struttura",
        _safe_div(pn_c, cur("totale_immobilizzazioni")) if (pn_c or 0.0) > 0 else None,
        _safe_div(pn_p, prv("totale_immobilizzazioni")) if (pn_p or 0.0) > 0 else None,
        "ratio", "PN / immobilizzazioni (n.s. se PN≤0)")

    add("leva", "Leva finanziaria (Debiti/PN)", "struttura",
        _safe_div(cur("debiti_totali"), pn_c) if (pn_c or 0.0) > 0 else None,
        _safe_div(prv("debiti_totali"), pn_p) if (pn_p or 0.0) > 0 else None,
        "ratio", "debiti / PN (n.s. se PN≤0)")

    ms_c = (pn_c or 0.0) - (cur("totale_immobilizzazioni") or 0.0) if pn_c is not None else None
    ms_p = (pn_p or 0.0) - (prv("totale_immobilizzazioni") or 0.0) if pn_p is not None else None
    add("margine_struttura", "Margine di struttura", "struttura", ms_c, ms_p, "eur",
        "PN − immobilizzazioni", status_cur=("green" if (ms_c or 0) >= 0 else "amber") if ms_c is not None else "na")

    # ---- REDDITIVITÀ ----
    add("roe", "ROE", "redditivita",
        _pct(_safe_div(cur("utile_perdita", ce), pn_c)) if (pn_c or 0.0) > 0 else None,
        _pct(_safe_div(prv("utile_perdita", ce), pn_p)) if (pn_p or 0.0) > 0 else None,
        "pct", "utile / PN (n.s. se PN≤0)")

    add("ros", "ROS (EBIT/ricavi)", "redditivita",
        _pct(_safe_div(cur("differenza_valore_costi", ce), cur("ricavi_vendite", ce))),
        _pct(_safe_div(prv("differenza_valore_costi", ce), prv("ricavi_vendite", ce))),
        "pct", "margine operativo sulle vendite")

    add("roi", "ROI (EBIT/attivo)", "redditivita",
        _pct(_safe_div(cur("differenza_valore_costi", ce), cur("totale_attivo"))),
        _pct(_safe_div(prv("differenza_valore_costi", ce), prv("totale_attivo"))),
        "pct", "redditività del capitale investito")

    # EBITDA / MOL Standard Civilistico OIC 12 & CNDCEC
    eb_cur = calculate_ebitda_oic12(
        {
            "ricavi_vendite": cur("ricavi_vendite", ce),
            "valore_produzione": cur("valore_produzione", ce),
            "costi_produzione": cur("costi_produzione", ce),
            "differenza_valore_costi": cur("differenza_valore_costi", ce),
            "ammortamenti": cur("ammortamenti", ce),
            "B10a": cur("ammortamento_immateriali", ce),
            "B10b": cur("ammortamento_materiali", ce),
            "B10c": cur("svalutazioni_immobilizzazioni", ce),
        }
    )
    eb_prv = calculate_ebitda_oic12(
        {
            "ricavi_vendite": prv("ricavi_vendite", ce),
            "valore_produzione": prv("valore_produzione", ce),
            "costi_produzione": prv("costi_produzione", ce),
            "differenza_valore_costi": prv("differenza_valore_costi", ce),
            "ammortamenti": prv("ammortamenti", ce),
            "B10a": prv("ammortamento_immateriali", ce),
            "B10b": prv("ammortamento_materiali", ce),
            "B10c": prv("svalutazioni_immobilizzazioni", ce),
        }
    )
    add("ebitda", "MOL / EBITDA standard (OIC 12)", "redditivita",
        eb_cur["ebitda_standard"], eb_prv["ebitda_standard"], "eur",
        "EBIT + B10a (Amm. immat.) + B10b (Amm. mat.) + B10c (Sval. imm.) [CNDCEC 2024]",
        status_cur="green" if (eb_cur["ebitda_standard"] or 0) > 0 else "red")

    add("ebitda_margin", "Margine EBITDA %", "redditivita",
        eb_cur["ebitda_margin_pct"], eb_prv["ebitda_margin_pct"], "pct",
        "MOL / Valore della Produzione")

    # ---- SOSTENIBILITÀ DEL DEBITO ----
    def _imp_opt(nat: str) -> Optional[float]:
        b = deb.get(nat)
        if isinstance(b, dict):
            val = b.get("importo")
            if val not in (None, ""):
                try:
                    return float(val)
                except (TypeError, ValueError):
                    return None
        elif b not in (None, "") and not isinstance(b, (list, tuple)):
            try:
                return float(b)
            except (TypeError, ValueError):
                return None
        return None

    def _imp(nat: str) -> float:
        v = _imp_opt(nat)
        return v if v is not None else 0.0

    # Verifica presenza reale di dati patrimoniali/debitori (regola NULL vs Zero: mai zero automatico se SP assente)
    has_sp_or_deb = any(
        x is not None
        for x in (
            cur("debiti_totali"),
            cur("debiti_entro"),
            cur("debiti_oltre"),
            cur("disponibilita_liquide"),
            cur("tfr"),
            _imp_opt("banche"),
            _imp_opt("tributari"),
            _imp_opt("previdenziali"),
            _imp_opt("fornitori"),
            _imp_opt("soci_finanziamenti"),
        )
    )

    if has_sp_or_deb:
        deb_banche = _imp("banche")
        tfr_val = cur("tfr") or 0.0
        fin_soci = _imp("soci_finanziamenti")
        trib_scad = _imp("tributari")
        forn_scad = _imp("fornitori_scaduti")

        pfn_esma_res = calculate_pfn_esma(
            debiti_bancari_breve=deb_banche,
            debiti_bancari_medio_lungo=cur("debiti_oltre") or 0.0,
            disponibilita_liquide=cur("disponibilita_liquide") or 0.0,
            tfr_fondo=tfr_val,
            finanziamenti_soci=fin_soci,
            debiti_tributari_scaduti=trib_scad,
            debiti_fornitori_scaduti_90gg=forn_scad,
        )
        pfn_c: Optional[float] = pfn_esma_res["pfn_totale"]
        pfn_status = "green" if (pfn_c or 0) <= 0 else ("amber" if (pfn_c or 0) < 500000 else "red")
        pfn_note = "Debiti Finanziari + Debt-like items (TFR, tributi, soci) − Liquidità [ESMA / CNDCEC]"
    else:
        pfn_c = None
        pfn_status = "na"
        pfn_note = "Non calcolabile: assenza di Stato Patrimoniale / liquidità e debiti contabili (mai zero automatico)"

    pfn_p = (
        (prv("debiti_totali") or 0.0) - (prv("disponibilita_liquide") or 0.0)
        if (prv("debiti_totali") is not None or prv("disponibilita_liquide") is not None)
        else None
    )

    add("pfn", "Posizione finanziaria netta (ESMA 2021)", "debito", pfn_c, pfn_p, "eur",
        pfn_note,
        status_cur=pfn_status)

    # Rapporto PFN / EBITDA (Anni di rimborso del debito) & Soglie Bancarie
    if pfn_c is not None and eb_cur["ebitda_standard"] is not None:
        pfn_eb_eval = evaluate_pfn_ebitda(pfn_c, eb_cur["ebitda_standard"])
        ratio_val = pfn_eb_eval["ratio"]
        status_map = {"ok": "green", "warn": "amber", "danger": "red"}
        add("pfn_ebitda", "PFN / EBITDA (Anni rimborso)", "debito",
            ratio_val, None, "ratio",
            pfn_eb_eval["valutazione_bancaria"],
            status_cur=status_map.get(pfn_eb_eval["status"], "na"))
    else:
        add("pfn_ebitda", "PFN / EBITDA (Anni rimborso)", "debito",
            None, None, "ratio",
            "Non calcolabile per assenza di PFN contabile certificata",
            status_cur="na")

    ebit_c, ebit_p = cur("differenza_valore_costi", ce), prv("differenza_valore_costi", ce)
    add("oneri_ebit", "Oneri finanziari / EBIT", "debito",
        _pct(_safe_div(cur("oneri_finanziari", ce), ebit_c)) if (ebit_c or 0.0) > 0 else None,
        _pct(_safe_div(prv("oneri_finanziari", ce), ebit_p)) if (ebit_p or 0.0) > 0 else None,
        "pct", "quota di margine assorbita dal debito (n.s. se EBIT≤0)")

    priv = _imp("tributari") + _imp("previdenziali")
    add("incid_priv", "Incidenza debiti privilegiati", "debito",
        _pct(_safe_div(priv, cur("debiti_totali"))) if cur("debiti_totali") is not None else None, None, "pct",
        "erario+previdenza / debiti totali")

    return out
