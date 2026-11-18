from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.client_card import router as card_router
from app.api.studio_rules import router as rules_router
from app.api.case_chat import router as chat_router
import app.models  # noqa: F401 (registra le tabelle)

# Lo schema NON viene più creato qui: lo gestisce Alembic (`alembic upgrade head`
# eseguito all'avvio del container). Così i dati sopravvivono ai cambi di schema,
# senza più ricorrere a `docker compose down -v`.

EMBED_CSP = (
    "frame-ancestors 'self' "
    "https://bentivegna-os.lovable.app "
    "https://preview--flow-canvas-automations.lovable.app"
)

app = FastAPI(title="DossierLex")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def embed_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = EMBED_CSP
    if "x-frame-options" in response.headers:
        del response.headers["x-frame-options"]
    return response

app.include_router(router, prefix="/api")
app.include_router(card_router, prefix="/api")
app.include_router(rules_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
