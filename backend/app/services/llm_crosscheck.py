"""Cross-check tra due provider sui documenti ad alta posta (bilancio, centrale_rischi).

Due modelli diversi estraggono lo STESSO documento. Se gli importi chiave divergono,
si segnala all'operatore (human-in-the-loop): NON si sceglie un vincitore in automatico.
"""
from app.config import settings

# Campi da confrontare per ciascun doc_type (path con '.' per scendere nei dizionari).
# Devono coincidere con le chiavi prodotte dai prompt di estrazione.
CROSSCHECK_FIELDS = {
    "bilancio": [
        "stato_patrimoniale.totale_attivo.corrente",
        "stato_patrimoniale.patrimonio_netto.corrente",
        "stato_patrimoniale.debiti_totali.corrente",
        "conto_economico.ricavi_vendite.corrente",
        "conto_economico.utile_perdita.corrente",
    ],
    "centrale_rischi": [
        "totali.esposizione_totale_utilizzata",
        "totali.totale_garanzie_prestate",
    ],
}

# Tolleranza relativa: differenze sotto questa soglia sono considerate concordi
# (arrotondamenti/migliaia). 1% -> sopra si segnala.
REL_TOLERANCE = 0.01


def crosscheck_doc_types() -> set:
    raw = settings.crosscheck_doc_types or ""
    return {t.strip() for t in raw.split(",") if t.strip()}


def needs_crosscheck(doc_type: str | None) -> bool:
    return bool(doc_type and doc_type in crosscheck_doc_types())


def _get(d, path):
    cur = d
    for key in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _to_number(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip().replace("€", "").replace(".", "").replace(" ", "").replace(",", ".")
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _diverge(a, b):
    """True se i due valori divergono oltre la tolleranza."""
    na, nb = _to_number(a), _to_number(b)
    if na is not None and nb is not None:
        if na == 0 and nb == 0:
            return False
        denom = max(abs(na), abs(nb), 1.0)
        return abs(na - nb) / denom > REL_TOLERANCE
    # non numerici: confronto stringa normalizzata
    return (str(a).strip().lower() or None) != (str(b).strip().lower() or None)


def compare(data_a: dict, data_b: dict, doc_type: str) -> list:
    """Ritorna l'elenco delle discrepanze [{field, value_a, value_b}]."""
    disc = []
    for path in CROSSCHECK_FIELDS.get(doc_type, []):
        va, vb = _get(data_a, path), _get(data_b, path)
        if va is None and vb is None:
            continue
        if _diverge(va, vb):
            disc.append({"field": path, "value_a": va, "value_b": vb})
    return disc
