"""
Worker per le richieste Openapi (visure) — ASINCRONO e in BACKGROUND.

Flusso:
  1. start_enrichment(req_id): legge la EnrichmentRequest, chiama Openapi (POST /richiesta),
     salva l'_id ritornato, poi accoda il primo poll.
  2. poll_enrichment(req_id, attempt): UN controllo. Se evasa -> mappa e salva (status=done).
     Se non ancora pronta -> si ri-accoda dopo qualche secondo (fino a max tentativi).

Cosi la richiesta NON e mai persa (e a pagamento) e l'utente non aspetta bloccato.
La risposta GREZZA viene sempre salvata (raw_response) per diagnostica e taratura mapping.
"""
from app.workers.celery_app import celery_app
from app.db import SessionLocal
from app.models import EnrichmentRequest
from app.services import openapi_client as oa

MAX_POLLS = 30        # tentativi massimi
POLL_DELAY = 6        # secondi tra un tentativo e l'altro (30 x 6 = 3 min max)

# source -> hash visura (camerale individuale come default per il test)
SOURCE_TO_HASH = {
    # Fonti CONFERMATE in sandbox (testabili subito)
    "centrale_rischi": oa.VISURE["centrale_rischi_pf"],
    "centrale_rischi_pg": oa.VISURE["centrale_rischi_pg"],
    "experian": oa.VISURE["experian"],
    "veicoli": oa.VISURE["veicoli_pra_proprietari"],
    "immobili": oa.VISURE["relazione_immobiliare_light"],
    "isee": oa.VISURE["isee"],
    # Camerale: hash vuoto finche non disponibile (vedi VISURE). Gestito con errore chiaro.
    "camerale": oa.VISURE["camerale_individuale"],
    "camerale_capitale": oa.VISURE["camerale_capitale"],
    "camerale_persone": oa.VISURE["camerale_persone"],
}


def _full_name(req, db) -> str:
    """Nome completo del cliente: preferisce first+last name del Debtor (scheda),
    altrimenti il client_name della pratica. Il PRA vuole nome E cognome."""
    from app.models import Debtor
    deb = db.query(Debtor).filter_by(case_id=req.case_id).first() if req.case_id else None
    if deb and (deb.first_name or deb.last_name):
        return f"{deb.first_name} {deb.last_name}".strip()
    return (req.case.client_name or "").strip() if req.case else ""


def _build_json_visura(req, db) -> dict:
    """Costruisce il json_visura coi campi posizionali ($0, $1, ...) richiesti
    da ogni visura (vedi GET /visure/{hash}). Alcune vogliono piu campi:
    es. PRA Proprietari validazione "$0 && $1" = Nome E Codice Fiscale."""
    cf = req.query
    name = _full_name(req, db)
    p = req.input_params or {}
    if req.source == "veicoli":
        # PRA: $0 = Nome e Cognome / Denominazione, $1 = CF/P.IVA (entrambi obbligatori)
        return {"$0": name or cf, "$1": cf}
    if req.source == "immobili":
        # Relazione Immobiliare: $0 = CF, $1 = Comune (codice catastale), $2 = contatto (email/tel)
        return {"$0": cf, "$1": p.get("comune", ""), "$2": p.get("contatto", "")}
    if req.source in ("centrale_rischi", "centrale_rischi_pg", "experian", "isee"):
        # tipicamente vogliono nome + CF; al primo test reale verifichiamo dalla json_struttura
        return {"$0": name or cf, "$1": cf}
    # default: un solo soggetto (P.IVA o CF)
    return {"$0": cf}


@celery_app.task(name="app.workers.openapi_tasks.start_enrichment")
def start_enrichment(req_id: str):
    db = SessionLocal()
    try:
        req = db.get(EnrichmentRequest, req_id)
        if not req:
            return
        hash_visura = SOURCE_TO_HASH.get(req.source)
        if not hash_visura:
            if req.source.startswith("camerale"):
                msg = ("Visura camerale non disponibile in questo ambiente/token. "
                       "Configura l'hash camerale (prod o token con prodotto Camerali).")
            else:
                msg = f"Fonte non supportata o hash non configurato: {req.source}"
            req.status = "error"; req.error = msg; db.commit(); return
        try:
            json_visura = _build_json_visura(req, db)
            _id = oa.request_visura(hash_visura, json_visura)
            req.openapi_request_id = _id
            req.status = "pending"
            db.commit()
            poll_enrichment.apply_async((req_id, 1), countdown=POLL_DELAY)
        except oa.OpenapiError as e:
            req.status = "error"; req.error = str(e); db.commit()
        except Exception as e:
            req.status = "error"; req.error = f"Errore avvio: {e}"; db.commit()
    finally:
        db.close()


@celery_app.task(name="app.workers.openapi_tasks.poll_enrichment")
def poll_enrichment(req_id: str, attempt: int):
    db = SessionLocal()
    try:
        req = db.get(EnrichmentRequest, req_id)
        if not req or req.status in ("done", "error"):
            return
        try:
            res = oa.check_once(req.openapi_request_id)
        except Exception as e:
            # errore transitorio: riprova se ci sono tentativi
            if attempt < MAX_POLLS:
                poll_enrichment.apply_async((req_id, attempt + 1), countdown=POLL_DELAY)
            else:
                req.status = "error"; req.error = f"Polling fallito: {e}"; db.commit()
            return

        # salva sempre la risposta grezza (diagnostica)
        req.raw_response = res.get("data", {})

        if res["annullata"]:
            req.status = "error"; req.error = "Richiesta annullata da Openapi"; db.commit(); return

        if res["evasa"]:
            from app.services import openapi_parser as op
            structured = oa.extract_structured(res["data"])
            if req.source.startswith("camerale"):
                req.mapped_data = oa.map_camerale(structured)
            elif req.source == "veicoli":
                items = [it for s in structured for it in op.map_vehicles(s)]
                req.mapped_data = {"kind": "veicoli", "items": items}
            elif req.source == "immobili":
                items = [it for s in structured for it in op.map_real_estate(s)]
                req.mapped_data = {"kind": "immobili", "items": items}
            elif req.source == "isee":
                mapped = {}
                for s in structured:
                    mapped = op.map_isee(s) or mapped
                    if mapped:
                        break
                req.mapped_data = {"kind": "isee", **mapped}
                # come il canale upload: l'ISEE estratto PROPONE una nota in income_sources
                if mapped.get("isee_ordinario"):
                    from app.workers.tasks import _apply_income_to_debtor
                    _apply_income_to_debtor(db, req.case_id, "isee", mapped)
            else:
                req.mapped_data = {"items": structured}
            req.status = "done"
            db.commit()
            return

        # non ancora pronta: ri-accoda o timeout
        if attempt < MAX_POLLS:
            db.commit()  # salva comunque la raw parziale
            poll_enrichment.apply_async((req_id, attempt + 1), countdown=POLL_DELAY)
        else:
            req.status = "timeout"
            req.error = "Visura non pronta entro il tempo massimo. Riprova piu tardi."
            db.commit()
    finally:
        db.close()
