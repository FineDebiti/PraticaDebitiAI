import pytest
from app.models import Document, Extraction, RealEstate, Company, Debtor
from app.services.pipeline_service import _unwrap_confidence, _num, _normalize_and_save_entities


def test_unwrap_confidence():
    wrapped = {
        "nome": {"value": "Mario Rossi", "confidence": 0.95, "page": 1},
        "importo": {"value": 1250.0, "confidence": 0.99, "page": 1},
        "lista": [{"value": "item1", "confidence": 1.0}]
    }
    unwrapped = _unwrap_confidence(wrapped)
    assert unwrapped["nome"] == "Mario Rossi"
    assert unwrapped["importo"] == 1250.0
    assert unwrapped["lista"] == ["item1"]


def test_num_coercion():
    assert _num(100) == 100.0
    assert _num("150.50") == 150.50
    assert _num({"value": 200}) == 200.0
    assert _num(None) == 0.0
    assert _num("") == 0.0
    assert _num("invalid") == 0.0


def test_normalize_and_save_entities_real_estate(db_session, sample_case):
    doc = Document(
        case_id=sample_case.id,
        original_filename="catasto.pdf",
        storage_path="/tmp/catasto.pdf",
        doc_type="visura_catastale",
        status="analizzato",
    )
    db_session.add(doc)
    db_session.commit()

    data = {
        "immobili": [{
            "tipo_immobile": "Fabbricato",
            "categoria": "A/2",
            "indirizzo": "Via Roma 10",
            "comune": "Roma",
            "foglio": "12",
            "particella": "34",
            "quota_soggetto": "1/1",
            "diritto_soggetto": "Proprietà",
            "superficie_mq": 85.0,
            "rendita_catastale": 500.0,
        }]
    }

    _normalize_and_save_entities(db_session, doc, data, sample_case.client_tax_code)
    db_session.commit()

    estates = db_session.query(RealEstate).filter_by(case_id=sample_case.id).all()
    assert len(estates) == 1
    assert estates[0].category == "A/2"
    assert estates[0].cadastral_income == 500.0
    assert estates[0].cadastral_value == 63000.0
