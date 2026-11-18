"""Test endpoint /api/embed/cases e header di sicurezza iframe per Bentivegna OS."""

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


def test_embed_cases_headers_and_readonly_data(api_client, db_session, monkeypatch):
    """Verifica CSP frame-ancestors, assenza X-Frame-Options, Cache-Control e lista in sola lettura."""
    monkeypatch.setattr(settings, "embed_readonly_token", "")
    db_session.add(Case(client_name="Test Embed SRL", client_tax_code="01234567890", status="in_lavorazione"))
    db_session.commit()

    r = api_client.get("/api/embed/cases")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[0]["client_name"] == "Test Embed SRL"

    csp = r.headers.get("content-security-policy", "")
    assert "frame-ancestors 'self'" in csp
    assert "https://bentivegna-os.lovable.app" in csp
    assert "https://preview--flow-canvas-automations.lovable.app" in csp
    assert "x-frame-options" not in {k.lower() for k in r.headers.keys()}
    assert "no-cache" in r.headers.get("cache-control", "")
    assert "no-store" in r.headers.get("cache-control", "")

    # L'endpoint /embed/cases accetta solo GET (nessuna scrittura possibile)
    r_post = api_client.post("/api/embed/cases", json={})
    assert r_post.status_code == 405
    r_del = api_client.delete("/api/embed/cases")
    assert r_del.status_code == 405


def test_embed_cases_token_and_https_cookie(api_client, monkeypatch):
    """Se embed_readonly_token e configurato, blocca richieste prive di token e imposta cookie SameSite=None su HTTPS."""
    monkeypatch.setattr(settings, "embed_readonly_token", "tok-segreto-123")

    r_unauth = api_client.get("/api/embed/cases")
    assert r_unauth.status_code == 401

    r_bad = api_client.get("/api/embed/cases", headers={"X-Embed-Token": "errato"})
    assert r_bad.status_code == 401

    r_ok = api_client.get(
        "/api/embed/cases",
        headers={"X-Embed-Token": "tok-segreto-123", "X-Forwarded-Proto": "https"},
    )
    assert r_ok.status_code == 200
    set_cookie = r_ok.headers.get("set-cookie", "")
    assert "dossierlex_embed_token=tok-segreto-123" in set_cookie
    assert "samesite=none" in set_cookie.lower()
    assert "secure" in set_cookie.lower()
