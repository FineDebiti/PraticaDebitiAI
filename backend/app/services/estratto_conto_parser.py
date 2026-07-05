"""Parser deterministico dell'ESTRATTO CONTO bancario.

Lettura locale e gratuita via pdfplumber: "parser propone, regola verifica".
L'AI (Flash) è solo fallback (vedi doc_prompts/estratto_conto.py) quando il parser
non trova movimenti (PDF scansionato / layout non tabellare).

Output allineato allo schema del prompt + aggregazioni utili a stimare il reddito
reale (specie degli autonomi): entrate/uscite medie mensili e saldo.
"""
import re
import pdfplumber


class EstrattoContoParseError(Exception):
    """Il parser non ha trovato movimenti: si ripiega sull'AI."""


# Intestazioni colonna riconosciute (case-insensitive, su substring).
_DATE_HINTS = ("data", "data valuta", "data operazione", "valuta")
_DESC_HINTS = ("descrizione", "causale", "operazione", "dettagli")
_DARE_HINTS = ("dare", "addebit", "uscite", "uscita", "pagamenti")
_AVERE_HINTS = ("avere", "accredit", "entrate", "entrata", "versamenti")
_SALDO_HINTS = ("saldo",)

_DATE_RE = re.compile(r"(\d{2})[-/.](\d{2})[-/.](\d{2,4})")


def _num(s) -> float:
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace("€", "").replace(" ", "").replace("\n", "")
    neg = t.startswith("-") or (t.endswith("-"))
    if t in ("", "-", "—", "/"):
        return 0.0
    # formato italiano 1.234,56 -> 1234.56
    t = t.replace(".", "").replace(",", ".")
    t = re.sub(r"[^\d.\-]", "", t)
    try:
        v = float(t)
    except ValueError:
        return 0.0
    return -abs(v) if (neg and v > 0) else v


def _date(s):
    if not s:
        return None
    m = _DATE_RE.search(str(s))
    if not m:
        return None
    g, mm, a = m.group(1), m.group(2), m.group(3)
    if len(a) == 2:  # anno a 2 cifre -> 20xx
        a = "20" + a
    return f"{a}-{mm}-{g}"


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def _header_colmap(row):
    """Se la riga è un'intestazione, ritorna {ruolo: indice_colonna}; altrimenti None.
    Mappa per ruolo semantico (data/descrizione/dare/avere/saldo), immune a colonne extra."""
    cm = {}
    for idx, cell in enumerate(row):
        c = _clean(cell).lower()
        if not c:
            continue
        if "saldo" not in cm and any(h in c for h in _SALDO_HINTS):
            cm["saldo"] = idx
        elif "dare" not in cm and any(h in c for h in _DARE_HINTS):
            cm["dare"] = idx
        elif "avere" not in cm and any(h in c for h in _AVERE_HINTS):
            cm["avere"] = idx
        elif "data" not in cm and any(h in c for h in _DATE_HINTS):
            cm["data"] = idx
        elif "descrizione" not in cm and any(h in c for h in _DESC_HINTS):
            cm["descrizione"] = idx
    # serve almeno una colonna data e una colonna importo (dare o avere)
    if "data" in cm and ("dare" in cm or "avere" in cm):
        return cm
    return None


def _g(row, cm, role) -> str:
    idx = cm.get(role)
    return _clean(row[idx]) if idx is not None and idx < len(row) else ""


def _map_row(row, cm) -> dict | None:
    data = _date(_g(row, cm, "data"))
    if not data:
        return None
    dare = _num(_g(row, cm, "dare"))
    avere = _num(_g(row, cm, "avere"))
    if dare == 0 and avere == 0:
        return None  # riga senza importo -> non è un movimento
    return {
        "data": data,
        "descrizione": _g(row, cm, "descrizione"),
        "dare": abs(dare),
        "avere": abs(avere),
        "saldo": _num(_g(row, cm, "saldo")) if cm.get("saldo") is not None else None,
    }


def _months_span(dates: list[str]) -> float:
    """Numero di mesi (>=1) coperti dai movimenti, per le medie mensili."""
    ds = sorted(d for d in dates if d)
    if len(ds) < 2:
        return 1.0
    y0, m0 = int(ds[0][:4]), int(ds[0][5:7])
    y1, m1 = int(ds[-1][:4]), int(ds[-1][5:7])
    return max(1.0, (y1 - y0) * 12 + (m1 - m0) + 1)


def _aggregate(movimenti: list[dict], saldo_finale) -> dict:
    entrate = round(sum(m["avere"] for m in movimenti), 2)
    uscite = round(sum(m["dare"] for m in movimenti), 2)
    mesi = _months_span([m["data"] for m in movimenti])
    return {
        "count_movimenti": len(movimenti),
        "mesi_coperti": round(mesi, 1),
        "totale_entrate": entrate,
        "totale_uscite": uscite,
        "entrate_medie_mensili": round(entrate / mesi, 2),
        "uscite_medie_mensili": round(uscite / mesi, 2),
        "saldo_finale": saldo_finale,
    }


def parse_pdf(file_path: str) -> dict:
    """Estrae i movimenti dall'estratto conto. Ritorna schema + aggregazioni.
    Solleva EstrattoContoParseError se non trova movimenti (-> fallback AI)."""
    movimenti = []
    colmap = None
    saldo_finale = None

    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    if not row or len(row) < 3:
                        continue
                    cm = _header_colmap(row)
                    if cm:
                        colmap = cm
                        continue
                    if colmap is None:
                        continue
                    mv = _map_row(row, colmap)
                    if mv:
                        movimenti.append(mv)
                        if mv["saldo"] is not None:
                            saldo_finale = mv["saldo"]

    if not movimenti:
        raise EstrattoContoParseError("Nessun movimento estratto dall'estratto conto")

    movimenti.sort(key=lambda m: m["data"] or "")
    dates = [m["data"] for m in movimenti if m["data"]]
    return {
        "doc_type": "estratto_conto",
        "intestatario": None,
        "iban": None,
        "periodo": {"da": (dates[0] if dates else None), "a": (dates[-1] if dates else None)},
        "movimenti": movimenti,
        "saldo_finale": saldo_finale,
        "aggregazioni": _aggregate(movimenti, saldo_finale),
    }
