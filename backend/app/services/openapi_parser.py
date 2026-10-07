"""
Parser DIFENSIVO per i risultati Visengine (PRA veicoli, Relazione Immobiliare).

Principi (vedi openapi-mapping-pra-immobiliare.md):
- in sandbox json_risultato è vuoto/null -> ritorna [] senza esplodere;
- nomi campo non certi -> ricerca case-insensitive con alias multipli;
- ogni elemento mappato tiene "_raw" per tarare gli alias sulla prima risposta reale.

Output allineato AI NOSTRI modelli:
- veicoli  -> VehicleIn:    kind, plate, make_model, year, estimated_value, notes
- immobili -> RealEstateIn: kind, address, cadastral_data, ownership_share,
              ownership_right, surface_mq, cadastral_income, category, notes
"""
import json
import re


def parse_json_risultato(raw):
    """json_risultato è una stringa JSON. Ritorna lista di dict (uno per indice_),
    o [] se vuoto (sandbox) / non parsabile."""
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if not isinstance(raw, dict):
        return []
    out = [raw[k] for k in sorted(raw.keys()) if k.startswith("indice_") and isinstance(raw[k], dict)]
    if not out:
        out = [raw]
    return out


def coded(v):
    """Valore leggibile da campo codificato {'!cod':..,'!':..} o da stringa semplice."""
    if isinstance(v, dict):
        return v.get("!") or v.get("!cod")
    return v


def cget(d, *aliases, default=None):
    """Get case-insensitive con alias multipli."""
    if not isinstance(d, dict):
        return default
    lower = {str(k).lower(): val for k, val in d.items()}
    for a in aliases:
        if a.lower() in lower:
            return lower[a.lower()]
    return default


def _num(v):
    """Numero robusto: gestisce None, stringhe con virgola decimale e separatori migliaia."""
    if v in (None, "", False):
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(".", "").replace(",", ".") if re.search(r",\d", str(v)) else str(v).replace(",", "")
    try:
        return float(re.sub(r"[^\d.\-]", "", s) or 0)
    except (TypeError, ValueError):
        return 0.0


def _year(v):
    """Estrae l'anno (4 cifre) da una data tipo gg/mm/aaaa o aaaa-mm-gg."""
    m = re.search(r"(19|20)\d{2}", str(v or ""))
    return m.group(0) if m else ""


def _addr_str(d):
    """Costruisce una stringa indirizzo dal blocco Indirizzo (forma OpenAPI)."""
    ind = cget(d, "Indirizzo", "indirizzo")
    if not isinstance(ind, dict):
        return cget(d, "Ubicazione", "ubicazione", "indirizzo") or ""
    via = " ".join(x for x in [coded(cget(ind, "Toponimo")), cget(ind, "Via")] if x)
    civ = cget(ind, "NCivico", "Civico")
    comune = cget(ind, "Comune")
    prov = coded(cget(ind, "Provincia"))
    parts = [p for p in [f"{via} {civ}".strip(), comune, prov and f"({prov})"] if p]
    return ", ".join(parts)


# ---------------- VEICOLI (PRA) ----------------
def map_vehicles(raw):
    """PRA -> lista di dict pronti per VehicleIn. Difensivo: [] se vuoto."""
    results = []
    for row in parse_json_risultato(raw):
        veicoli = cget(row, "Veicoli", "veicoli", "elenco_veicoli", "Mezzi", "Veicolo", default=[])
        if isinstance(veicoli, dict):
            veicoli = [veicoli]
        for v in (veicoli or []):
            if not isinstance(v, dict):
                continue
            make_model = (cget(v, "MarcaModello", "Marca Modello", "Marca", "marca", "make_model") or "")
            modello = cget(v, "Modello", "modello")
            if modello and "/" not in str(make_model):
                make_model = f"{make_model}/{modello}".strip("/")
            stato = cget(v, "StatoRuolo", "Stato Ruolo", "Stato", "stato")
            ruolo = cget(v, "DescrizioneRuolo", "Descrizione Ruolo", "ruolo")
            grav = cget(v, "DescrizioneProvvedimento", "Descrizione Provvedimento",
                        "DettagliVincoli", "Tipo Dettagli Vincoli", "Vincoli", "Formalita")
            note = " · ".join(str(x) for x in [ruolo, stato, grav and f"Vincolo: {grav}"] if x)
            results.append({
                "kind": coded(cget(v, "ClasseVeicolo", "Classe Veicolo", "TipoVeicolo", "tipo_veicolo", "Tipo")) or "veicolo",
                "plate": cget(v, "Targa", "targa", "plate") or "",
                "make_model": make_model or "",
                "year": _year(cget(v, "DataPrimaImmatricolazione", "Data Prima Immatricolazione", "DataImmatricolazione")),
                "estimated_value": 0.0,
                "notes": note,
                "_raw": v,
            })
    return results


# ---------------- ISEE (Visengine) ----------------
def map_isee(raw) -> dict:
    """ISEE Visengine -> dict allineato allo schema upload (doc_prompts/isee).
    Difensivo: in sandbox json_risultato è spesso vuoto -> ritorna {} con _raw."""
    rows = parse_json_risultato(raw)
    if not rows:
        return {}
    x = rows[0]
    return {
        "isee_ordinario": _num(cget(x, "ISEE", "Isee", "ValoreIsee", "isee_ordinario", "isee")),
        "isr": _num(cget(x, "ISR", "IndicatoreSituazioneReddituale")) or None,
        "ise": _num(cget(x, "ISE", "IndicatoreSituazioneEconomica")) or None,
        "componenti_nucleo": _num(cget(x, "NumeroComponenti", "ComponentiNucleo", "componenti_nucleo")) or None,
        "anno": _year(cget(x, "Anno", "AnnoRiferimento", "DataPresentazione", "anno")),
        "scadenza": cget(x, "Scadenza", "DataScadenza", "scadenza"),
        "_raw": x,
    }


# ---------------- IMMOBILI (Relazione Immobiliare) ----------------
def map_real_estate(raw):
    """Relazione Immobiliare -> lista di dict pronti per RealEstateIn. Difensivo: [] se vuoto."""
    results = []
    for row in parse_json_risultato(raw):
        immobili = cget(row, "Immobili", "immobili", "elenco_immobili", "Fabbricati", "Immobile", default=[])
        if isinstance(immobili, dict):
            immobili = [immobili]
        for im in (immobili or []):
            if not isinstance(im, dict):
                continue
            cat_obj = cget(im, "Categoria", "categoria")
            # per il ricalcolo valore catastale serve il CODICE (es. "A/2"), non la descrizione
            cat = (cat_obj.get("!cod") if isinstance(cat_obj, dict) else cat_obj) or ""
            comune = cget(im, "Comune", "comune")
            fg = cget(im, "Foglio", "foglio")
            part = cget(im, "Particella", "particella", "Mappale")
            sub = cget(im, "Subalterno", "subalterno", "Sub")
            cad = " ".join(x for x in [
                comune and f"{comune} -",
                fg and f"Fg {fg}", part and f"Part {part}", sub and f"Sub {sub}",
            ] if x)
            results.append({
                "kind": (f"fabbricato {cat}".strip() if cat else "immobile"),
                "category": cat,
                "address": _addr_str(im),
                "cadastral_data": cad,
                "ownership_share": str(cget(im, "Quota", "quota") or ""),
                "ownership_right": coded(cget(im, "DirittoReale", "diritto", "Diritto")) or "",
                "surface_mq": _num(cget(im, "Consistenza", "consistenza", "Superficie", "SuperficieMq")),
                "cadastral_income": _num(cget(im, "Rendita", "rendita", "RenditaCatastale")),
                "estimated_value": 0.0,
                "_raw": im,
            })
    return results
