"""Test endpoint /api/auth/ticket, riscatto monouso, /api/embed/cases e CSP Lovable."""

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import Case


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
    monkeypatch.setattr(settings, "embed_readonly_token", "")
    monkeypatch.setattr(settings, "dossierlex_server_secret", "")
    db_session.add(Case(client_name="Test Embed SRL", client_tax_code="01234567890", status="in_lavorazione"))
    db_session.commit()

    r = api_client.get("/api/embed/cases")
    assert r.status_code == 200
    assert r.json()[0]["client_name"] == "Test Embed SRL"

    csp = r.headers.get("content-security-policy", "")
    assert "frame-ancestors 'self'" in csp
    assert "https://flow-canvas-automations.lovable.app" in csp
    assert "https://id-preview--49092334-bbfd-47c6-9334-7ba579814b60.lovable.app" in csp
    assert "https://lovable.dev" in csp
    assert "x-frame-options" not in {k.lower() for k in r.headers.keys()}
    assert "no-cache" in r.headers.get("cache-control", "")
    assert "no-store" in r.headers.get("cache-control", "")

    assert api_client.post("/api/embed/cases", json={}).status_code == 405
    assert api_client.delete("/api/embed/cases").status_code == 405


def test_one_time_ticket_issue_burn_and_scope_isolation(api_client, db_session, monkeypatch):
    """Ticket monouso TTL 60s: emissione Bearer, bruciatura immediata al 1o uso e isolamento scope."""
    monkeypatch.setattr(settings, "dossierlex_server_secret", "srv-secret-test-xyz")
    monkeypatch.setattr(settings, "embed_readonly_token", "")
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

    # Sessione full NON puo sostituire embed su /api/embed/cases senza token
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
