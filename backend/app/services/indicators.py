"""Calcolo DETERMINISTICO degli indici di bilancio (mai l'AI).

Input: i blocchi estratti stato_patrimoniale (sp), conto_economico (ce),
debiti_per_natura (deb). Ogni voce SP/CE è {"corrente": x, "precedente": y} o null.
Output: lista di dict indicatore (code, label, group, value_cur, value_prev, fmt,
trend, status, note) pronti per persistenza e frontend.
"""
from typing import Dict, Any, List, Optional
from app.services.indicator_thresholds import thresholds_for, status_for


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

    # ---- SOSTENIBILITÀ DEL DEBITO ----
    pfn_c = (cur("debiti_totali") or 0.0) - (cur("disponibilita_liquide") or 0.0) if cur("debiti_totali") is not None else None
    pfn_p = (prv("debiti_totali") or 0.0) - (prv("disponibilita_liquide") or 0.0) if prv("debiti_totali") is not None else None
    add("pfn", "Posizione finanziaria netta", "debito", pfn_c, pfn_p, "eur",
        "debiti − liquidità (lettura contestuale)", status_cur="amber" if pfn_c is not None else "na")

    ebit_c, ebit_p = cur("differenza_valore_costi", ce), prv("differenza_valore_costi", ce)
    add("oneri_ebit", "Oneri finanziari / EBIT", "debito",
        _pct(_safe_div(cur("oneri_finanziari", ce), ebit_c)) if (ebit_c or 0.0) > 0 else None,
        _pct(_safe_div(prv("oneri_finanziari", ce), ebit_p)) if (ebit_p or 0.0) > 0 else None,
        "pct", "quota di margine assorbita dal debito (n.s. se EBIT≤0)")

    def _imp(nat: str) -> float:
        b = deb.get(nat)
        if isinstance(b, dict):
            try:
                return float(b.get("importo") or 0.0)
            except (TypeError, ValueError):
                return 0.0
        return 0.0

    priv = _imp("tributari") + _imp("previdenziali")
    add("incid_priv", "Incidenza debiti privilegiati", "debito",
        _pct(_safe_div(priv, cur("debiti_totali"))) if cur("debiti_totali") is not None else None, None, "pct",
        "erario+previdenza / debiti totali")

    return out
