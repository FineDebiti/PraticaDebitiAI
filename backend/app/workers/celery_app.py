from celery import Celery
from app.config import settings

celery_app = Celery("pratica_debiti", broker=settings.redis_url, backend=settings.redis_url)

# Coda unica "default" per TUTTI i task (documenti + Openapi).
# task_default_queue cattura ogni task che non ha un routing esplicito,
# cosi nuovi moduli worker non finiscono per sbaglio in code non consumate.
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_routes = {"app.workers.*": {"queue": "default"}}

import app.workers.tasks  # noqa: E402,F401  (registra i task)
import app.workers.openapi_tasks  # noqa: E402,F401
