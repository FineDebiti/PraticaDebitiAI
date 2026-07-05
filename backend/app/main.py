from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.client_card import router as card_router
import app.models  # noqa: F401 (registra le tabelle)

# Lo schema NON viene più creato qui: lo gestisce Alembic (`alembic upgrade head`
# eseguito all'avvio del container). Così i dati sopravvivono ai cambi di schema,
# senza più ricorrere a `docker compose down -v`.

app = FastAPI(title="DossierLex")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

app.include_router(router, prefix="/api")
app.include_router(card_router, prefix="/api")
