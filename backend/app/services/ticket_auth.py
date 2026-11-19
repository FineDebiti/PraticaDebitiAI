"""Gestione ticket monouso (TTL 60s) e sessioni HMAC firmate per integrazione CRM."""

import base64
import hashlib
import hmac
import json
import logging
import secrets
import threading
import time
from typing import Optional

from app.config import settings

logger = logging.getLogger("dossierlex.ticket_auth")

TICKET_TTL_SECONDS = 60
SESSION_TTL_SECONDS = 28800  # 8 ore

_MEM_LOCK = threading.Lock()
_MEM_TICKETS: dict[str, dict] = {}
_REDIS_LOCK = threading.Lock()
_REDIS_CLIENT = None
_REDIS_URL = ""


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64u_decode(val: str) -> bytes:
    pad = "=" * (-len(val) % 4)
    return base64.urlsafe_b64decode(val + pad)


def _reset_redis() -> None:
    global _REDIS_CLIENT, _REDIS_URL
    with _REDIS_LOCK:
        _REDIS_CLIENT = None
        _REDIS_URL = ""


def _get_redis():
    """Restituisce un client Redis singleton riusabile senza ping per-richiesta."""
    global _REDIS_CLIENT, _REDIS_URL
    target_url = (settings.redis_url or "").strip()
    if not target_url:
        return None
    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None and _REDIS_URL == target_url:
            return _REDIS_CLIENT
        try:
            import redis
            client = redis.Redis.from_url(
                target_url,
                decode_responses=True,
                socket_connect_timeout=0.35,
                socket_timeout=0.35,
            )
            client.ping()
            _REDIS_CLIENT = client
            _REDIS_URL = target_url
            return _REDIS_CLIENT
        except Exception as exc:
            logger.debug("Redis non raggiungibile per ticket monouso, uso fallback memoria: %s", exc)
            _REDIS_CLIENT = None
            _REDIS_URL = ""
            return None


def _signing_secret() -> str:
    return (settings.dossierlex_server_secret or "").strip()


def sign_session_token(scope: str, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    """Firma un token di sessione opaco (HMAC-SHA256) privo di secret statici."""
    secret = _signing_secret()
    if not secret:
        raise RuntimeError("DOSSIERLEX_SERVER_SECRET non configurato.")
    payload = {
        "scope": scope,
        "exp": int(time.time()) + ttl_seconds,
        "jti": secrets.token_hex(8),
    }
    payload_b64 = _b64u_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64u_encode(sig)}"


def verify_session_token(token: Optional[str], required_scope: str) -> bool:
    """Verifica firma HMAC, scadenza e scope del cookie di sessione."""
    if not token or "." not in token:
        return False
    secret = _signing_secret()
    if not secret:
        return False
    try:
        payload_b64, sig_b64 = token.split(".", 1)
        expected_sig = _b64u_encode(
            hmac.new(secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(sig_b64, expected_sig):
            return False
        payload = json.loads(_b64u_decode(payload_b64).decode("utf-8"))
        if payload.get("scope") != required_scope:
            return False
        if int(payload.get("exp", 0)) <= int(time.time()):
            return False
        return True
    except Exception:
        return False


def create_one_time_ticket(scope: str) -> dict:
    """Genera e salva in Redis (o memoria fallback) un ticket monouso da 60 secondi."""
    if scope not in ("embed", "full"):
        raise ValueError("Lo scope deve essere 'embed' oppure 'full'.")
    ticket = secrets.token_urlsafe(32)
    record = {"scope": scope, "exp": int(time.time()) + TICKET_TTL_SECONDS}
    r = _get_redis()
    stored_in_redis = False
    if r is not None:
        try:
            r.set(f"dlx:ticket:{ticket}", json.dumps(record), ex=TICKET_TTL_SECONDS)
            stored_in_redis = True
        except Exception as exc:
            logger.warning("Errore scrittura Redis ticket monouso, uso fallback memoria: %s", exc)
            _reset_redis()
    if not stored_in_redis:
        now = time.time()
        with _MEM_LOCK:
            expired = [k for k, v in _MEM_TICKETS.items() if v["exp"] <= now]
            for k in expired:
                _MEM_TICKETS.pop(k, None)
            _MEM_TICKETS[ticket] = record
    return {"ticket": ticket, "expires_in": TICKET_TTL_SECONDS}


def redeem_one_time_ticket(ticket: str, expected_scope: str) -> tuple[bool, str, str]:
    """Consuma (brucia) il ticket al primo utilizzo e genera un cookie di sessione firmato."""
    if not ticket or expected_scope not in ("embed", "full"):
        return False, "Ticket o scope non valido.", ""

    raw_val: Optional[str] = None
    record: Optional[dict] = None
    r = _get_redis()
    if r is not None:
        key = f"dlx:ticket:{ticket}"
        try:
            if hasattr(r, "getdel"):
                raw_val = r.getdel(key)
            else:
                pipe = r.pipeline()
                pipe.get(key)
                pipe.delete(key)
                raw_val, _ = pipe.execute()
            if raw_val:
                record = json.loads(raw_val)
        except Exception as exc:
            logger.warning("Errore lettura/bruciatura Redis ticket monouso: %s", exc)
            _reset_redis()
            record = None

    if record is None:
        with _MEM_LOCK:
            record = _MEM_TICKETS.pop(ticket, None)

    if not record:
        return False, "Ticket inesistente, scaduto o già utilizzato.", ""
    if int(record.get("exp", 0)) <= int(time.time()):
        return False, "Ticket scaduto.", ""
    if record.get("scope") != expected_scope:
        return False, "Scope del ticket non compatibile con la rotta richiesta.", ""

    session_token = sign_session_token(expected_scope)
    return True, "ok", session_token
