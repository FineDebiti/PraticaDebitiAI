"""Test endpoint /api/auth/ticket, riscatto monouso, /api/embed/cases, CSP Lovable e ticket_auth."""

import time
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Case
from app.services import ticket_auth


@pytest.fixture()
def api_client(db_session):
    def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_embed_cases_csp_and_readonly_method_guard(api_client, db_session, monkeypatch):
    """Verifica CSP Lovable aggiornata, assenza X-Frame-Options, Cache-Control e solo GET."""
    monkeypatch.setattr(settings, "dossierlex_server_secret", "")
    db_session.add(Case(client_name="Test Embed SRL", client_tax_code="01234567890", status="in_lavorazione"))
    db_session.commit()

    r = api_client.get("/api/embed/cases")
    assert r.status_code == 200
    assert r.json()[0]["client_name"] == "Test Embed SRL"

    csp = r.headers.get("content-security-policy", "")
    assert "frame-ancestors 'self'" in csp
    assert "https://flow-canvas-automations.lovable.app" in csp
    assert "https://preview--flow-canvas-automations.lovable.app" in csp
    assert "https://id-preview--49092334-bbfd-47c6-9334-7ba579814b60.lovable.app" in csp
    assert "https://lovable.dev" in csp
    assert "x-frame-options" not in {k.lower() for k in r.headers.keys()}
    assert "no-cache" in r.headers.get("cache-control", "")
    assert "no-store" in r.headers.get("cache-control", "")

    assert api_client.post("/api/embed/cases", json={}).status_code == 405
    assert api_client.delete("/api/embed/cases").status_code == 405


def test_cors_pna_corp_preflight_and_get_headers(api_client, db_session, monkeypatch):
    """Verifica header OPTIONS PNA/CORS/Credentials e Cross-Origin-Resource-Policy su GET."""
    monkeypatch.setattr(settings, "dossierlex_server_secret", "")
    db_session.commit()
    origin = "https://preview--flow-canvas-automations.lovable.app"

    r_opt = api_client.options(
        "/api/embed/cases",
        headers={
            "Origin": origin,
            "Access-Control-Request-Private-Network": "true",
        },
    )
    assert r_opt.status_code in (200, 204)
    assert r_opt.headers.get("access-control-allow-origin") == origin
    assert r_opt.headers.get("access-control-allow-methods") == "GET, POST, OPTIONS"
    assert "Access-Control-Request-Private-Network" in (r_opt.headers.get("access-control-allow-headers") or "")
    assert r_opt.headers.get("access-control-allow-private-network") == "true"
    assert r_opt.headers.get("access-control-allow-credentials") == "true"

    r_get = api_client.get("/api/embed/cases", headers={"Origin": origin})
    assert r_get.status_code == 200
    assert r_get.headers.get("access-control-allow-origin") == origin
    assert r_get.headers.get("access-control-allow-private-network") == "true"
    assert r_get.headers.get("access-control-allow-credentials") == "true"
    assert r_get.headers.get("cross-origin-resource-policy") == "cross-origin"


def test_embed_cases_local_http_vs_external_https(api_client, db_session, monkeypatch):
    """HTTP locale diretto su localhost consente consultazione; HTTPS esterno/testserver richiede cookie embed."""
    monkeypatch.setattr(settings, "dossierlex_server_secret", "srv-secret-local-test")
    db_session.add(Case(client_name="Locale Check SRL", client_tax_code="11223344556", status="in_lavorazione"))
    db_session.commit()

    # Richiesta esterna / TestClient di default senza cookie -> 401
    assert api_client.get("/api/embed/cases").status_code == 401

    # Host HTTP locale diretto -> 200
    r_local = api_client.get("/api/embed/cases", headers={"Host": "localhost:3001"})
    assert r_local.status_code == 200

    # Ma se arriva via proxy HTTPS (x-forwarded-proto=https), anche con Host localhost richiede cookie -> 401
    r_https = api_client.get(
        "/api/embed/cases",
        headers={"Host": "localhost:3001", "X-Forwarded-Proto": "https"},
    )
    assert r_https.status_code == 401

    # Host spoofing prefix come 192.168.1.evil.com non passa -> 401
    r_spoof = api_client.get("/api/embed/cases", headers={"Host": "192.168.1.evil.com"})
    assert r_spoof.status_code == 401


def test_one_time_ticket_issue_burn_expiry_and_scope_isolation(api_client, db_session, monkeypatch):
    """Ticket monouso TTL 60s: emissione Bearer, bruciatura al 1o uso, scadenza <= e isolamento scope."""
    monkeypatch.setattr(settings, "dossierlex_server_secret", "srv-secret-test-xyz")
    db_session.add(Case(client_name="Cliente Ticket", client_tax_code="99887766554", status="in_lavorazione"))
    db_session.commit()

    # Senza Bearer o con Bearer errato -> 401
    assert api_client.post("/api/auth/ticket", json={"scope": "embed"}).status_code == 401
    assert api_client.post(
        "/api/auth/ticket",
        headers={"Authorization": "Bearer wrong-secret"},
        json={"scope": "embed"},
    ).status_code == 401

    # Scope invalido -> 422
    assert api_client.post(
        "/api/auth/ticket",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"scope": "admin_invalid"},
    ).status_code == 422

    # Emissione ticket scope=embed
    res_issue = api_client.post(
        "/api/auth/ticket",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"scope": "embed"},
    )
    assert res_issue.status_code == 200
    body = res_issue.json()
    ticket = body["ticket"]
    assert body["expires_in"] == 60
    assert len(ticket) >= 24

    # Tentativo uso ticket embed sullo scope full -> 401 E il ticket resta consumato
    assert api_client.post(
        "/api/auth/redeem",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"ticket": ticket, "scope": "full"},
    ).status_code == 401

    # Nuovo ticket scope=embed -> riscatto valido e bruciatura al 1o uso
    t_embed = api_client.post(
        "/api/auth/ticket",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"scope": "embed"},
    ).json()["ticket"]

    res_redeem = api_client.post(
        "/api/auth/redeem",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"ticket": t_embed, "scope": "embed"},
    )
    assert res_redeem.status_code == 200
    embed_session = res_redeem.json()["session_token"]

    # Riuso dello stesso ticket -> 401 (bruciato!)
    res_replay = api_client.post(
        "/api/auth/redeem",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"ticket": t_embed, "scope": "embed"},
    )
    assert res_replay.status_code == 401

    # Accesso /api/embed/cases: bloccato senza sessione, consentito con cookie embed_session
    assert api_client.get("/api/embed/cases").status_code == 401
    api_client.cookies.set("dossierlex_embed_session", embed_session)
    assert api_client.get("/api/embed/cases").status_code == 200

    # Sessione full NON puo sostituire embed su /api/embed/cases
    t_full = api_client.post(
        "/api/auth/ticket",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"scope": "full"},
    ).json()["ticket"]
    full_session = api_client.post(
        "/api/auth/redeem",
        headers={"Authorization": "Bearer srv-secret-test-xyz"},
        json={"ticket": t_full, "scope": "full"},
    ).json()["session_token"]
    api_client.cookies.clear()
    api_client.cookies.set("dossierlex_embed_session", full_session)
    assert api_client.get("/api/embed/cases").status_code == 401

    # Verifica scadenza <= exp su fallback memoria e riuso singleton Redis
    with ticket_auth._MEM_LOCK:
        ticket_auth._MEM_TICKETS["exp-now"] = {"scope": "embed", "exp": int(time.time())}
    ok_exp, _, _ = ticket_auth.redeem_one_time_ticket("exp-now", "embed")
    assert ok_exp is False


def test_embed_cases_accepts_session_header_fallback(api_client, db_session, monkeypatch):
    """Verifica fallback header X-DossierLex-Session / Authorization Bearer senza cookie e isolamento scope."""
    monkeypatch.setattr(settings, "dossierlex_server_secret", "srv-secret-header-fallback")
    db_session.add(Case(client_name="Cliente Header SRL", client_tax_code="55443322110", status="in_lavorazione"))
    db_session.commit()

    embed_ticket = api_client.post(
        "/api/auth/ticket",
        headers={"Authorization": "Bearer srv-secret-header-fallback"},
        json={"scope": "embed"},
    ).json()["ticket"]
    embed_session = api_client.post(
        "/api/auth/redeem",
        headers={"Authorization": "Bearer srv-secret-header-fallback"},
        json={"ticket": embed_ticket, "scope": "embed"},
    ).json()["session_token"]

    full_ticket = api_client.post(
        "/api/auth/ticket",
        headers={"Authorization": "Bearer srv-secret-header-fallback"},
        json={"scope": "full"},
    ).json()["ticket"]
    full_session = api_client.post(
        "/api/auth/redeem",
        headers={"Authorization": "Bearer srv-secret-header-fallback"},
        json={"ticket": full_ticket, "scope": "full"},
    ).json()["session_token"]

    api_client.cookies.clear()
    r_x_hdr = api_client.get("/api/embed/cases", headers={"X-DossierLex-Session": embed_session})
    assert r_x_hdr.status_code == 200
    assert r_x_hdr.json()[0]["client_name"] == "Cliente Header SRL"

    r_bearer = api_client.get("/api/embed/cases", headers={"Authorization": f"Bearer {embed_session}"})
    assert r_bearer.status_code == 200

    # Isolamento scope: token full rifiutato su /api/embed/cases anche via header
    r_wrong_scope = api_client.get("/api/embed/cases", headers={"X-DossierLex-Session": full_session})
    assert r_wrong_scope.status_code == 401


def test_local_origin_cors_preflight_and_post_case(api_client, db_session):
    """Verifica preflight OPTIONS e POST /api/cases da origin locale http://localhost:3001."""
    local_origin = "http://localhost:3001"
    r_opt = api_client.options(
        "/api/cases",
        headers={
            "Origin": local_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r_opt.status_code == 204
    assert r_opt.headers.get("access-control-allow-origin") == local_origin
    assert r_opt.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in (r_opt.headers.get("access-control-allow-methods") or "")
    assert "Content-Type" in (r_opt.headers.get("access-control-allow-headers") or "")

    r_post = api_client.post(
        "/api/cases",
        headers={"Origin": local_origin},
        json={
            "client_kind": "persona",
            "first_name": "Mario",
            "last_name": "Rossi",
            "client_tax_code": "RSSMRA80A01H501U",
        },
    )
    assert r_post.status_code == 200
    assert r_post.headers.get("access-control-allow-origin") == local_origin
    body = r_post.json()
    assert body["client_name"] == "Mario Rossi"
    assert body["client_tax_code"] == "RSSMRA80A01H501U"
