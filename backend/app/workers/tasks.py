import logging
from app.workers.celery_app import celery_app
from app.db import SessionLocal
from app.services.pipeline_service import process_document_pipeline, _valore_catastale  # noqa: F401

logger = logging.getLogger("dossierlex.workers")


@celery_app.task(name="app.workers.tasks.process_document")
def process_document(document_id: str):
    """Celery task per l'elaborazione asincrona di un documento.
    Delega l'esecuzione alla pipeline documentale modulare."""
    db = SessionLocal()
    try:
        process_document_pipeline(db, document_id)
    except Exception as e:
        logger.error("Celery task process_document fallito per doc %s: %s", document_id, e)
    finally:
        db.close()
