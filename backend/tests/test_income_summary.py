import pytest
from app.models import Document, Extraction
from app.services.income_summary import compute_income_summary, _normalize, _annual_equiv


def test_annual_equiv():
    # Mensile dipendente (13 mensilità)
    assert _annual_equiv("mensile", 1500, 1500, "lavoro_dipendente") == 19500.0
    # Mensile rendita (12 mensilità)
    assert _annual_equiv("mensile", 500, 500, "rendite") == 6000.0
    # Annuo (dichiarazione)
    assert _annual_equiv("annuo", 24000, 2000, "lavoro_dipendente") == 24000.0
    # Indicatore ISEE (nessun equivalente annuo significativo)
    assert _annual_equiv("indicatore", 15000, None, "indicatore") is None


def test_normalize_busta_paga(sample_case):
    doc = Document(case_id=sample_case.id, original_filename="busta.pdf", doc_type="busta_paga", status="normalizzato")
    data = {"retribuzione_netta": 1650.50, "periodo": "10/2023", "datore_lavoro": "ACME SpA"}
    res = _normalize(doc, data)
    assert len(res) == 1
    assert res[0]["monthly_equiv"] == 1650.50
    assert res[0]["category"] == "lavoro_dipendente"
    assert res[0]["annual_equiv"] == round(1650.50 * 13, 2)


def test_normalize_dichiarazione(sample_case):
    doc = Document(case_id=sample_case.id, original_filename="730.pdf", doc_type="dichiarazione_redditi", status="normalizzato")
    data = {
        "anno_imposta": "2022",
        "riepilogo_RN": {"reddito_complessivo": 24000.0},
        "quadri": {
            "RC_lavoro_dipendente": {"presente": True, "reddito": 20000.0},
            "RB_fabbricati": {"presente": True, "reddito": 4000.0, "canoni_percepiti": 4000.0, "n_immobili_locati": 1}
        }
    }
    res = _normalize(doc, data)
    assert len(res) == 2
    cats = {r["category"]: r["monthly_equiv"] for r in res}
    assert cats["lavoro_dipendente"] == round(20000.0 / 12, 2)
    assert cats["rendite"] == round(4000.0 / 12, 2)


def test_compute_income_summary_empty(db_session, sample_case):
    res = compute_income_summary(db_session, sample_case.id)
    assert res["has_data"] is False
    assert res["proposed_monthly"] == 0.0
    assert len(res["sources"]) == 0
