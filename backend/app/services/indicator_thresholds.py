"""Soglie semaforo degli indicatori di bilancio.

Versione universale (manualistica). Gancio per override per macro-settore ATECO,
da affinare in fase 2 senza toccare il resto.
"""

# dir: "high" = più alto è meglio; "low" = più basso è meglio.
# Per le percentuali le soglie sono in punti % (es. ROS green >=8).
UNIVERSAL = {
    "current_ratio":        {"green": 1.5, "amber": 1.0, "dir": "high"},
    "acid_test":            {"green": 1.0, "amber": 0.7, "dir": "high"},
    "liquidita_immediata":  {"green": 0.5, "amber": 0.2, "dir": "high"},
    "indip_fin":            {"green": 33,  "amber": 15,  "dir": "high"},
    "cop_immob":            {"green": 1.0, "amber": 0.66, "dir": "high"},
    "leva":                 {"green": 2.0, "amber": 4.0, "dir": "low"},
    "roe":                  {"green": 8,   "amber": 0,   "dir": "high"},
    "ros":                  {"green": 8,   "amber": 2,   "dir": "high"},
    "roi":                  {"green": 8,   "amber": 3,   "dir": "high"},
    "oneri_ebit":           {"green": 30,  "amber": 50,  "dir": "low"},
    "incid_priv":           {"green": 25,  "amber": 40,  "dir": "low"},
}

# GANCIO FUTURO: override per macro-settore (primi 2 caratteri ATECO).
# Es. ristorazione (56) lavora con liquidità fisiologicamente bassa.
SECTOR_OVERRIDES = {}  # vuoto in fase 1


def thresholds_for(ateco: str | None) -> dict:
    base = {k: dict(v) for k, v in UNIVERSAL.items()}
    if ateco:
        macro = str(ateco).strip()[:2]
        for code, ov in SECTOR_OVERRIDES.get(macro, {}).items():
            base.setdefault(code, {}).update(ov)
    return base


def status_for(spec: dict, value):
    """Ritorna green|amber|red|na dato lo spec soglia e il valore."""
    if spec is None or value is None:
        return "na"
    green, amber, direction = spec.get("green"), spec.get("amber"), spec.get("dir", "high")
    if direction == "low":
        if value <= green:
            return "green"
        if value <= amber:
            return "amber"
        return "red"
    # high
    if value >= green:
        return "green"
    if value >= amber:
        return "amber"
    return "red"
