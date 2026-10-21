import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db


@pytest.fixture
def client(db_session):
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    json_data = response.json()
    assert json_data["status"] == "ok"


def test_create_case_persona(client):
    payload = {
        "client_kind": "persona",
        "first_name": "Giuseppe",
        "last_name": "Verdi",
        "client_tax_code": "VRDGRS85M01H501Z",
        "notes": "Pratica test persona"
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["client_name"] == "Giuseppe Verdi"
    assert data["client_tax_code"] == "VRDGRS85M01H501Z"


def test_create_case_invalid_tax_code(client):
    payload = {
        "client_kind": "persona",
        "first_name": "Giuseppe",
        "last_name": "Verdi",
        "client_tax_code": "INVALID_CODE",
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 422


def test_get_card(client, sample_case):
    response = client.get(f"/api/cases/{sample_case.id}/card")
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == sample_case.id
    assert data["debtor"]["first_name"] == "Mario"


def test_get_indicators(client, sample_case):
    response = client.get(f"/api/cases/{sample_case.id}/indicators")
    assert response.status_code == 200
    data = response.json()
    assert "macro" in data
    assert "indicators" in data


def test_get_edits_empty(client, sample_case):
    response = client.get(f"/api/cases/{sample_case.id}/edits")
    assert response.status_code == 200
    assert response.json() == []


def test_get_preanalysis_report(client, sample_case):
    response = client.get(f"/api/cases/{sample_case.id}/preanalysis-report")
    assert response.status_code == 200
    data = response.json()
    assert "header" in data
    assert "capitolo_1_premessa" in data
    assert "capitolo_5_indebitamento" in data
    assert "capitolo_11_conclusione" in data


def test_get_preanalysis_report_pdf(client, sample_case):
    # Test portrait download
    response = client.get(f"/api/cases/{sample_case.id}/preanalysis-report/pdf?orientation=portrait&action=download")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment;" in response.headers.get("content-disposition", "")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000

    # Test landscape inline
    response_l = client.get(f"/api/cases/{sample_case.id}/preanalysis-report/pdf?orientation=landscape&action=inline")
    assert response_l.status_code == 200
    assert response_l.headers["content-type"] == "application/pdf"
    assert "inline" in response_l.headers.get("content-disposition", "")
    assert response_l.content.startswith(b"%PDF")

