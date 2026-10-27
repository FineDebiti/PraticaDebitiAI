import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_db
from app.models import Case, Company, Document, Extraction, CasePreanalysisReport


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


def test_preanalysis_initial_and_regenerate(client, db_session):
    # Setup a mock case with company and visura document
    case = Case(
        client_name="Test Company Srl",
        client_tax_code="12345678901",
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    company = Company(
        case_id=case.id,
        name="Test Company Srl",
        vat="12345678901",
        rea="",
        legal_address="",
        ateco="",
    )
    db_session.add(company)

    doc = Document(
        case_id=case.id,
        original_filename="Visura.pdf",
        doc_type="visura_camerale",
        status="completed",
        storage_path="/tmp/fake_visura.pdf",
    )
    db_session.add(doc)
    db_session.commit()

    extraction = Extraction(
        document_id=doc.id,
        json_output={
            "document_type": "visura_camerale",
            "impresa": {
                "denominazione": "Test Company Srl",
                "numero_rea": "RM - 998877",
                "sede_legale": "Roma (RM) Via Flaminia 1",
            },
            "dati_secondari": {
                "classificazione_ateco": "62.01.00",
            },
            "soci": [
                {
                    "denominazione": "Mario Rossi",
                    "codice_fiscale": "RSSMRA80A01H501U",
                    "quota_percentuale": 100.0,
                    "cariche": ["amministratore unico", "socio"],
                }
            ],
        },
    )
    db_session.add(extraction)
    db_session.commit()

    # 1. Test GET /preanalysis-report -> should create v1
    res = client.get(f"/api/cases/{case.id}/preanalysis-report")
    assert res.status_code == 200
    data = res.json()
    assert "_meta" in data
    assert data["_meta"]["version"] == 1
    assert data["capitolo_2_profilo"]["rea"] == "RM - 998877"
    assert data["capitolo_2_profilo"]["sede_legale"] == "Roma (RM) Via Flaminia 1"
    assert data["capitolo_2_profilo"]["codice_ateco"] == "62.01.00"
    soci = data["capitolo_2_profilo"]["soci"]
    assert len(soci) == 1
    assert soci[0]["nome"] == "MARIO ROSSI"
    assert soci[0]["quota_pct"] == 100.0

    # 2. Test POST /preanalysis-report/regenerate -> should bump to v2
    regen_res = client.post(
        f"/api/cases/{case.id}/preanalysis-report/regenerate",
        json={"instructions": ["Verifica conformità"], "scope": "cap_2"},
    )
    assert regen_res.status_code == 200
    regen_data = regen_res.json()
    assert regen_data["success"] is True
    assert regen_data["version"] == 2
    assert regen_data["report"]["capitolo_2_profilo"]["rea"] == "RM - 998877"

    # 3. Test GET PDF -> should return valid PDF
    pdf_res = client.get(f"/api/cases/{case.id}/preanalysis-report/pdf")
    assert pdf_res.status_code == 200
    assert pdf_res.headers.get("content-type") == "application/pdf"
    assert len(pdf_res.content) > 1000

    # 4. Test POST reset -> should bump version with reset baseline
    reset_res = client.post(f"/api/cases/{case.id}/preanalysis-report/reset")
    assert reset_res.status_code == 200
    reset_data = reset_res.json()
    assert reset_data["success"] is True
    assert reset_data["version"] == 3
