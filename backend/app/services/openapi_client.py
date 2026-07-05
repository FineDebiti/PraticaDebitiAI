"""
Client per Visengine 2.0 di Openapi.com.

Flusso reale (asincrono):
  1. POST /richiesta            -> crea richiesta, ritorna _id e stato
  2. GET  /richiesta/{_id}      -> polling finche stato_richiesta == "Visura evasa"
                                   (i dati strutturati sono in ricerche[].json_risultato / json_mappato)
  3. GET  /documento/{_id}      -> (opzionale) scarica il file allegato, se serve

Doc: https://console.openapi.com/apis/visengine/documentation
Autenticazione: header "Authorization: Bearer <token>"
"""
import time
import json
import httpx
from app.config import settings

# Hash VERI dal catalogo Visengine sandbox di Giuseppe (GET /visure, giu 2026).
# NB: la camerale ordinaria NON e in questo catalogo sandbox — da cercare con token/prodotto
# diverso (vedi memoria). Quelli sotto sono confermati presenti in sandbox.
VISURE = {
    # Disponibili e CONFERMATI in sandbox
    "centrale_rischi_pf":      "526b6c8415936433f5a217d2bf7d2a72",  # Visura Centrale Rischi persona fisica
    "centrale_rischi_pg":      "8e238ef3e28fd887c014879179ece1b0",  # Visura Centrale Rischi Persona Giuridica
    "experian":                "b56c410cdfd569bfc0160821d4b3b26b",  # Visura Experian
    "veicoli_pra_proprietari": "89031e957e9cebc4f6e64948f2353727",  # Visura Proprietari PRA
    "relazione_immobiliare_light":     "155e32c7eafa9bf45fd65f8647a9a623",
    "relazione_immobiliare_intermedia":"fc9c42046d8a25706dda92e5521f1e24",
    "relazione_immobiliare_plus":      "761733d82c59112d91302e82aa97177f",
    "isee":                    "6aa0789f5ba34684b2bc5ccf364f8929",  # ISEE
    "cud_pensionati":          "df66c5f10a4ce1162c56f762c562d79c",
    "obis_m":                  "bc74d769203eb5c33f2a40e91c076ec3",  # cedolino pensione
    # Camerale: NON presente in sandbox. Hash da configurare quando disponibile (prod/altro token).
    "camerale_individuale":    "",
    "camerale_capitale":       "",
    "camerale_persone":        "",
}


class OpenapiError(Exception):
    pass


def _headers():
    if not settings.openapi_token:
        raise OpenapiError("Token Openapi mancante: imposta OPENAPI_TOKEN nel .env")
    return {"Authorization": f"Bearer {settings.openapi_token}", "Content-Type": "application/json"}


def list_visure() -> list[dict]:
    """GET /visure: catalogo reale delle visure disponibili sul TUO account/ambiente.
    Ritorna [{nome_visura, nome_categoria, hash_visura}, ...].
    Serve a scoprire gli HASH VERI (quelli nel dict VISURE sono placeholder da doc generica)."""
    with httpx.Client(base_url=settings.openapi_base_url, timeout=30) as c:
        r = c.get("/visure", headers=_headers())
        r.raise_for_status()
        return r.json().get("data", []) or []


def get_visura_detail(hash_visura: str) -> dict:
    """GET /visure/{hash}: dettaglio di una visura (campi di input richiesti, prezzo, sincrona).
    Utile per sapere ESATTAMENTE quali parametri servono ($0, $1...) e il costo."""
    with httpx.Client(base_url=settings.openapi_base_url, timeout=30) as c:
        r = c.get(f"/visure/{hash_visura}", headers=_headers())
        r.raise_for_status()
        return r.json().get("data", {}) or {}


def request_visura(hash_visura: str, json_visura: dict, test: bool = False) -> str:
    """POST /richiesta. Ritorna l'_id della richiesta creata."""
    body = {"hash_visura": hash_visura, "json_visura": json_visura}
    if test:
        body["test"] = True
    with httpx.Client(base_url=settings.openapi_base_url, timeout=30) as c:
        r = c.post("/richiesta", headers=_headers(), json=body)
        if r.status_code == 402:
            raise OpenapiError("Credito insufficiente sull'account Openapi (HTTP 402)")
        r.raise_for_status()
        data = r.json().get("data", {})
        _id = data.get("_id")
        if not _id:
            raise OpenapiError(f"Risposta senza _id: {r.text[:300]}")
        return _id


def _ricerche_evase(data: dict) -> bool:
    """True se i risultati strutturati sono gia disponibili: tutte le 'ricerche'
    hanno stato 'Ricerca evasa'. Spesso pronte PRIMA che l'intera visura
    (stato_richiesta) diventi 'Visura evasa' — cosi non aspettiamo il PDF."""
    ric = data.get("ricerche") or []
    if not ric:
        return False
    return all((r.get("stato_ricerca") or "").strip().lower() == "ricerca evasa" for r in ric)


def poll_result(_id: str, timeout: int | None = None) -> dict:
    """GET /richiesta/{_id} in polling finche evasa o timeout.
    Ritorna l'oggetto 'data' completo della richiesta."""
    timeout = timeout or settings.openapi_poll_timeout
    deadline = time.time() + timeout
    last = {}
    with httpx.Client(base_url=settings.openapi_base_url, timeout=30) as c:
        while time.time() < deadline:
            r = c.get(f"/richiesta/{_id}", headers=_headers())
            r.raise_for_status()
            last = r.json().get("data", {})
            stato = last.get("stato_richiesta", "")
            if stato in ("Visura evasa", "Dati disponibili") or last.get("allegati") or _ricerche_evase(last):
                return last
            if stato == "Annullata":
                raise OpenapiError(f"Richiesta annullata. Esito: {last.get('esito')}")
            time.sleep(2)
    # timeout: ritorna comunque lo stato corrente (il chiamante decide)
    last["_timed_out"] = True
    return last


def check_once(_id: str) -> dict:
    """UN solo controllo dello stato (per polling in BACKGROUND, no loop).
    Ritorna {stato, evasa: bool, annullata: bool, data: <oggetto richiesta>}."""
    with httpx.Client(base_url=settings.openapi_base_url, timeout=30) as c:
        r = c.get(f"/richiesta/{_id}", headers=_headers())
        r.raise_for_status()
        data = r.json().get("data", {})
    stato = data.get("stato_richiesta", "")
    return {
        "stato": stato,
        # pronta se la visura e evasa, ha allegati, OPPURE le ricerche sono gia evase
        "evasa": stato in ("Visura evasa", "Dati disponibili") or bool(data.get("allegati")) or _ricerche_evase(data),
        "annullata": stato == "Annullata",
        "data": data,
    }


def extract_structured(richiesta_data: dict) -> list[dict]:
    """Estrae i dati strutturati JSON dalle ricerche evase, senza passare dal PDF."""
    out = []
    for ric in richiesta_data.get("ricerche", []) or []:
        res = ric.get("json_risultato")
        if isinstance(res, str):
            try:
                res = json.loads(res)
            except Exception:
                res = None
        if res:
            out.append(res)
        elif ric.get("json_mappato"):
            out.append(ric["json_mappato"])
    return out


# Mapping camerale: la prima visura reale ci dira i nomi esatti dei campi.
# Per ora best-effort sui nomi plausibili. DA TARARE alla prima risposta vera.
def map_camerale(structured: list[dict]) -> dict:
    if not structured:
        return {}
    x = structured[0]
    return {
        "denominazione": x.get("denominazione") or x.get("ragione_sociale") or x.get("nome"),
        "partita_iva": x.get("partita_iva") or x.get("piva") or x.get("p_iva"),
        "codice_fiscale": x.get("codice_fiscale") or x.get("cf"),
        "pec": x.get("pec") or x.get("indirizzo_pec"),
        "sede_legale": x.get("sede_legale") or x.get("indirizzo") or x.get("sede"),
        "stato_attivita": x.get("stato_attivita") or x.get("stato"),
        "rea": x.get("rea") or x.get("numero_rea"),
        "_raw": x,
    }
