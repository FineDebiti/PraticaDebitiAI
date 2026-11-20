import re
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.client_card import router as card_router
from app.api.studio_rules import router as rules_router
from app.api.case_chat import router as chat_router
import app.models  # noqa: F401 (registra le tabelle)

# Lo schema NON viene più creato qui: lo gestisce Alembic (`alembic upgrade head`
# eseguito all'avvio del container). Così i dati sopravvivono ai cambi di schema,
# senza più ricorrere a `docker compose down -v`.

ALLOWED_LOVABLE_ORIGINS = {
    "https://flow-canvas-automations.lovable.app",
    "https://preview--flow-canvas-automations.lovable.app",
    "https://id-preview--49092334-bbfd-47c6-9334-7ba579814b60.lovable.app",
    "https://lovable.dev",
}

_LOCAL_ORIGIN_RE = re.compile(
    r"^https?://(?:localhost|127\.0\.0\.1|\[::1\]|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|100\.\d{1,3}\.\d{1,3}\.\d{1,3}|evo-x2\.tail723056\.ts\.net)(?::\d+)?$",
    re.IGNORECASE,
)

EMBED_CSP = (
    "frame-ancestors 'self' "
    "https://flow-canvas-automations.lovable.app "
    "https://preview--flow-canvas-automations.lovable.app "
    "https://id-preview--49092334-bbfd-47c6-9334-7ba579814b60.lovable.app "
    "https://lovable.dev"
)

app = FastAPI(title="DossierLex")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


def _apply_cors_pna_headers(response: Response, origin: str, path: str = "") -> None:
    is_embed = path == "/api/embed" or path.startswith("/api/embed/")
    response.headers["Access-Control-Allow-Private-Network"] = "true"
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, OPTIONS" if is_embed else "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    )
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, X-DossierLex-Session, Access-Control-Request-Private-Network"
    )
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    if origin in ALLOWED_LOVABLE_ORIGINS or (origin and _LOCAL_ORIGIN_RE.match(origin)):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    elif not is_embed and not response.headers.get("Access-Control-Allow-Origin"):
        response.headers["Access-Control-Allow-Origin"] = "*"


@app.middleware("http")
async def embed_security_headers(request: Request, call_next):
    origin = (request.headers.get("origin") or "").strip()
    if request.method == "OPTIONS":
        response = Response(status_code=204)
        response.headers["Content-Security-Policy"] = EMBED_CSP
        _apply_cors_pna_headers(response, origin, request.url.path)
        return response

    response = await call_next(request)
    response.headers["Content-Security-Policy"] = EMBED_CSP
    if "x-frame-options" in response.headers:
        del response.headers["x-frame-options"]
    _apply_cors_pna_headers(response, origin, request.url.path)
    return response

app.include_router(router, prefix="/api")
app.include_router(card_router, prefix="/api")
app.include_router(rules_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
