"""Parser deterministico dell'estratto di ruolo Agenzia delle Entrate-Riscossione.

Formato fisso, tabellare (17 colonne A-Q). L'estrazione è locale e gratuita via
pdfplumber: "parser propone, regola verifica". L'AI è solo fallback (vedi llm.py)
quando il parser non trova righe (PDF scansionato / layout anomalo).
"""
import re
import pdfplumber


class AerParseError(Exception):
    """Il parser tabellare non è riuscito (0 righe): si ripiega sull'AI."""


# ---- mappa ente creditore -> categoria (deterministica, estendibile) ----
def ente_categoria(ente: str) -> str:
    e = (ente or "").upper()
    if "INPS" in e or "INAIL" in e or "PREVID" in e:
        return "previdenziale"
    if "AGENZIA DELLE ENTRATE" in e or "AMMINISTRAZIONE FINANZIARIA" in e or "ENTRATE" in e:
        return "erariale"
    if "REGIONE" in e or "TASSE AUTO" in e or "BOLLO" in e or "ACI" in e:
        return "bollo"
    if "COMUNE" in e or "PREFETTURA" in e:
        return "locale"
    if "CAMERA DI COMMERCIO" in e or "CAMERALE" in e:
        return "camerale"
    if "MULTIENTE" in e or "MULTI ENTE" in e:
        return "misto"
    return "altro"


# ---- parsing celle ----
def _num(s) -> float:
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    t = str(s).strip().replace("€", "").replace(" ", "").replace("\n", "")
    if t in ("", "-", "—", "/"):
        return 0.0
    # formato italiano 1.158,32 -> 1158.32
    t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return 0.0


def _date(s):
    if not s:
        return None
    m = re.search(r"(\d{2})[-/.](\d{2})[-/.](\d{4})", str(s))
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _bool(s) -> bool:
    return str(s or "").strip().lower() in ("sì", "si", "s", "x", "true", "yes", "1")


def _clean(s) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


# Ogni cella d'intestazione contiene il codice colonna tra parentesi, es. "Totale residuo (L)".
# Mappiamo le colonne DAI CODICI A-Q dell'header: così siamo immuni a colonne extra
# (es. "Ambito prov.le") o a riordini di layout, senza dipendere dalla posizione fissa.
_LETTER_RE = re.compile(r"\(([A-Q])\)")
_TOL = 0.01  # 1 centesimo


def _header_colmap(row):
    """Se la riga è l'intestazione, ritorna {lettera: indice_colonna}, altrimenti None."""
    cm = {}
    for idx, cell in enumerate(row):
        m = _LETTER_RE.search(_clean(cell))
        if m:
            cm[m.group(1)] = idx
    return cm if len(cm) >= 10 else None


def _is_total(row) -> bool:
    return _clean(row[0]).upper().startswith("TOTAL") if row else False


def _g(row, cm, letter) -> str:
    idx = cm.get(letter)
    return _clean(row[idx]) if idx is not None and idx < len(row) else ""


def _map_row(row: list, cm: dict) -> dict:
    """Mappa una riga dati nello schema §4 usando la colmap A-Q dell'header."""
    carico = _num(_g(row, cm, "E"))
    sgravio = _num(_g(row, cm, "F"))
    pagato = _num(_g(row, cm, "G"))
    stralcio = _num(_g(row, cm, "H"))
    residuo = _num(_g(row, cm, "I"))
    interessi = _num(_g(row, cm, "J"))
    oneri = _num(_g(row, cm, "K"))
    totale = _num(_g(row, cm, "L"))
    sospeso = _num(_g(row, cm, "M"))
    totale_netto = _num(_g(row, cm, "N"))
    # quadrature deterministiche (§2): se non tornano -> needs_review
    needs = (abs(residuo - (carico - sgravio - pagato - stralcio)) > _TOL
             or abs(totale - (residuo + interessi + oneri)) > _TOL
             or abs(totale_netto - (totale - sospeso)) > _TOL)
    ente = _g(row, cm, "C")
    return {
        "numero_documento": _g(row, cm, "A"), "tipo_documento": _g(row, cm, "B"),
        "ente_creditore": ente, "ente_categoria": ente_categoria(ente),
        "data_notifica": _date(_g(row, cm, "D")),
        "carico_affidato": carico, "sgravio": sgravio, "gia_pagato": pagato,
        "stralcio_def_agevolata": stralcio, "residuo_carico": residuo,
        "interessi_mora": interessi, "oneri_diritti": oneri,
        "totale_residuo": totale, "importo_sospeso": sospeso,
        "totale_residuo_netto": totale_netto,
        "rateizzato": _bool(_g(row, cm, "O")), "proc_attive": _bool(_g(row, cm, "P")),
        "def_agevolata": _bool(_g(row, cm, "Q")),
        "needs_review": needs,
    }


def _extract_header(page) -> dict:
    """CF + denominazione dalla testata (prima pagina)."""
    text = page.extract_text() or ""
    cf = ""
    m = re.search(r"Codice\s*Fiscale[:\s]*([A-Z0-9]{11,16})", text, re.I)
    if m:
        cf = m.group(1).upper()
    denom = ""
    # etichetta tipica: "Denominazione/Cognome Nome: ROSSI MARIO" -> prendi dopo i due punti
    m = re.search(r"(?:Denominazione|Cognome)[^:]*:\s*(.+)", text, re.I)
    if m:
        denom = _clean(m.group(1))
    return {"codice_fiscale": cf, "denominazione": denom}


def _aggregate(righe: list) -> dict:
    """Sintesi §5 calcolate in Python (deterministiche)."""
    per_categoria, per_tipo = {}, {}
    date_notifica = []
    for r in righe:
        cat = r["ente_categoria"]
        pc = per_categoria.setdefault(cat, {"categoria": cat, "count": 0, "totale_residuo": 0.0})
        pc["count"] += 1
        pc["totale_residuo"] += r["totale_residuo"]
        tp = r["tipo_documento"] or "—"
        pt = per_tipo.setdefault(tp, {"tipo": tp, "count": 0, "totale_residuo": 0.0})
        pt["count"] += 1
        pt["totale_residuo"] += r["totale_residuo"]
        if r["data_notifica"]:
            date_notifica.append(r["data_notifica"])
    return {
        "per_categoria": sorted(per_categoria.values(), key=lambda x: -x["totale_residuo"]),
        "per_tipo": sorted(per_tipo.values(), key=lambda x: -x["totale_residuo"]),
        "count_righe": len(righe),
        "count_proc_attive": sum(1 for r in righe if r["proc_attive"]),
        "count_rateizzate": sum(1 for r in righe if r["rateizzato"]),
        "count_def_agevolata": sum(1 for r in righe if r["def_agevolata"]),
        "count_needs_review": sum(1 for r in righe if r["needs_review"]),
        "notifica_piu_vecchia": min(date_notifica) if date_notifica else None,
        "notifica_piu_recente": max(date_notifica) if date_notifica else None,
    }


def parse_pdf(file_path: str) -> dict:
    """Estrae l'estratto di ruolo. Ritorna lo schema §4 + aggregazioni.
    Solleva AerParseError se non trova alcuna riga (-> fallback AI)."""
    righe = []
    header = {"codice_fiscale": "", "denominazione": ""}
    totali_row, totali_cm, colmap = None, None, None

    with pdfplumber.open(file_path) as pdf:
        for pidx, page in enumerate(pdf.pages):
            if pidx == 0:
                header = _extract_header(page)
            for table in page.extract_tables() or []:
                for row in table:
                    if not row or len(row) < 10:
                        continue
                    cm = _header_colmap(row)
                    if cm:                       # riga d'intestazione: aggiorna la mappa colonne
                        colmap = cm
                        continue
                    if colmap is None:           # senza header non sappiamo mappare
                        continue
                    if _is_total(row):
                        totali_row, totali_cm = row, colmap
                        continue
                    if not _g(row, colmap, "A"):  # riga senza numero documento -> non è dato
                        continue
                    righe.append(_map_row(row, colmap))

    if not righe:
        raise AerParseError("Nessuna riga estratta dalla tabella AER")

    # Totali: dalla riga TOTALI se presente, altrimenti somma delle righe.
    if totali_row and totali_cm:
        totali = {
            "carico_affidato": _num(_g(totali_row, totali_cm, "E")),
            "sgravio": _num(_g(totali_row, totali_cm, "F")),
            "gia_pagato": _num(_g(totali_row, totali_cm, "G")),
            "stralcio_def_agevolata": _num(_g(totali_row, totali_cm, "H")),
            "residuo_carico": _num(_g(totali_row, totali_cm, "I")),
            "interessi_mora": _num(_g(totali_row, totali_cm, "J")),
            "oneri_diritti": _num(_g(totali_row, totali_cm, "K")),
            "totale_residuo": _num(_g(totali_row, totali_cm, "L")),
            "totale_residuo_netto": _num(_g(totali_row, totali_cm, "N")),
        }
    else:
        totali = {k: round(sum(r[k] for r in righe), 2) for k in (
            "carico_affidato", "sgravio", "gia_pagato", "stralcio_def_agevolata",
            "residuo_carico", "interessi_mora", "oneri_diritti",
            "totale_residuo", "totale_residuo_netto")}

    # Quadratura globale: nessuna riga in review E somma righe == totali (tolleranza).
    somma_tot = sum(r["totale_residuo"] for r in righe)
    quadrature_ok = (all(not r["needs_review"] for r in righe)
                     and abs(somma_tot - totali["totale_residuo"]) <= max(1.0, len(righe) * _TOL))

    return {
        "doc_type": "cartella_aer",
        "intestatario": header,
        "data_elaborazione": None,
        "righe": righe,
        "totali": totali,
        "aggregazioni": _aggregate(righe),
        "quadrature_ok": quadrature_ok,
    }
