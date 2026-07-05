"""Calcolo DETERMINISTICO degli indici di bilancio (mai l'AI).

Input: i blocchi estratti stato_patrimoniale (sp), conto_economico (ce),
debiti_per_natura (deb). Ogni voce SP/CE è {"corrente": x, "precedente": y} o null.
Output: lista di dict indicatore (code, label, group, value_cur, value_prev, fmt,
trend, status, note) pronti per persistenza e frontend.
"""
from app.services.indicator_thresholds import thresholds_for, status_for


def _safe(n, d):
    if d in (None, 0):
        return None
    return n / d


def _pct(x):
    return None if x is None else x * 100


def _trend(c, p):
    if c is None or p is None:
        return "na"
    if abs(c - p) < 1e-9:
        return "flat"
    return "up" if c > p else "down"


def compute_indicators(sp, ce, deb, ateco=None) -> list[dict]:
    sp, ce, deb = sp or {}, ce or {}, deb or {}
    thr = thresholds_for(ateco)
    out = []

    def cur(key, blk=sp):
        v = blk.get(key)
        return v.get("corrente") if isinstance(v, dict) else None

    def prv(key, blk=sp):
        v = blk.get(key)
        return v.get("precedente") if isinstance(v, dict) else None

    def add(code, label, group, fc, fp, fmt, note, status_cur=None):
        spec = thr.get(code)
        status = status_cur if status_cur is not None else (status_for(spec, fc) if fc is not None else "na")
        out.append({
            "code": code, "label": label, "group": group,
            "value_cur": fc, "value_prev": fp, "fmt": fmt,
            "trend": _trend(fc, fp), "status": status, "note": note,
        })

    # ---- LIQUIDITÀ ----
    add("current_ratio", "Current ratio", "liquidita",
        _safe(cur("totale_attivo_circolante"), cur("debiti_entro")),
        _safe(prv("totale_attivo_circolante"), prv("debiti_entro")),
        "ratio", "attivo circolante / debiti a breve")

    add("acid_test", "Acid test (quick ratio)", "liquidita",
        _safe((cur("totale_attivo_circolante") or 0) - (cur("rimanenze") or 0), cur("debiti_entro")),
        _safe((prv("totale_attivo_circolante") or 0) - (prv("rimanenze") or 0), prv("debiti_entro")),
        "ratio", "(circolante − rimanenze) / debiti a breve")

    add("liquidita_immediata", "Liquidità immediata", "liquidita",
        _safe(cur("disponibilita_liquide"), cur("debiti_entro")),
        _safe(prv("disponibilita_liquide"), prv("debiti_entro")),
        "ratio", "liquidità / debiti a breve")

    # ---- STRUTTURA / SOLIDITÀ ----
    pn_c, pn_p = cur("patrimonio_netto"), prv("patrimonio_netto")
    add("indip_fin", "Indipendenza finanziaria", "struttura",
        _pct(_safe(pn_c, cur("totale_attivo"))), _pct(_safe(pn_p, prv("totale_attivo"))),
        "pct", "PN / totale attivo")

    add("cop_immob", "Copertura immobilizzazioni", "struttura",
        _safe(pn_c, cur("totale_immobilizzazioni")) if (pn_c or 0) > 0 else None,
        _safe(pn_p, prv("totale_immobilizzazioni")) if (pn_p or 0) > 0 else None,
        "ratio", "PN / immobilizzazioni (n.s. se PN≤0)")

    add("leva", "Leva finanziaria (Debiti/PN)", "struttura",
        _safe(cur("debiti_totali"), pn_c) if (pn_c or 0) > 0 else None,
        _safe(prv("debiti_totali"), pn_p) if (pn_p or 0) > 0 else None,
        "ratio", "debiti / PN (n.s. se PN≤0)")

    ms_c = (pn_c or 0) - (cur("totale_immobilizzazioni") or 0)
    ms_p = (pn_p or 0) - (prv("totale_immobilizzazioni") or 0)
    add("margine_struttura", "Margine di struttura", "struttura", ms_c, ms_p, "eur",
        "PN − immobilizzazioni", status_cur=("green" if ms_c >= 0 else "amber"))

    # ---- REDDITIVITÀ ----
    add("roe", "ROE", "redditivita",
        _pct(_safe(cur("utile_perdita", ce), pn_c)) if (pn_c or 0) > 0 else None,
        _pct(_safe(prv("utile_perdita", ce), pn_p)) if (pn_p or 0) > 0 else None,
        "pct", "utile / PN (n.s. se PN≤0)")

    add("ros", "ROS (EBIT/ricavi)", "redditivita",
        _pct(_safe(cur("differenza_valore_costi", ce), cur("ricavi_vendite", ce))),
        _pct(_safe(prv("differenza_valore_costi", ce), prv("ricavi_vendite", ce))),
        "pct", "margine operativo sulle vendite")

    add("roi", "ROI (EBIT/attivo)", "redditivita",
        _pct(_safe(cur("differenza_valore_costi", ce), cur("totale_attivo"))),
        _pct(_safe(prv("differenza_valore_costi", ce), prv("totale_attivo"))),
        "pct", "redditività del capitale investito")

    # ---- SOSTENIBILITÀ DEL DEBITO ----
    pfn_c = (cur("debiti_totali") or 0) - (cur("disponibilita_liquide") or 0)
    pfn_p = (prv("debiti_totali") or 0) - (prv("disponibilita_liquide") or 0)
    add("pfn", "Posizione finanziaria netta", "debito", pfn_c, pfn_p, "eur",
        "debiti − liquidità (lettura contestuale)", status_cur="amber")

    ebit_c, ebit_p = cur("differenza_valore_costi", ce), prv("differenza_valore_costi", ce)
    add("oneri_ebit", "Oneri finanziari / EBIT", "debito",
        _pct(_safe(cur("oneri_finanziari", ce), ebit_c)) if (ebit_c or 0) > 0 else None,
        _pct(_safe(prv("oneri_finanziari", ce), ebit_p)) if (ebit_p or 0) > 0 else None,
        "pct", "quota di margine assorbita dal debito (n.s. se EBIT≤0)")

    def _imp(nat):
        b = deb.get(nat)
        return (b.get("importo") or 0) if isinstance(b, dict) else 0
    priv = _imp("tributari") + _imp("previdenziali")
    add("incid_priv", "Incidenza debiti privilegiati", "debito",
        _pct(_safe(priv, cur("debiti_totali"))), None, "pct",
        "erario+previdenza / debiti totali")

    return out
