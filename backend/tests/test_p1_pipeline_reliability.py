"""Test di verifica P1 (Affidabilità OCR pagina-per-pagina, JSON strict, Idempotenza pipeline, Regole/Telemetria)."""

from unittest.mock import MagicMock, patch
from fpdf import FPDF

from app.models import (
    Case,
    Company,
    CompanyMember,
    CreditExposure,
    CreditReportSummary,
    DebtPosition,
    Document,
    Extraction,
    RealEstate,
    StudioRule,
)
from app.services import ocr
from app.services.cross_analysis import assemble_case_dossier
from app.services.forensic_preanalysis_chain import (
    SYSTEM_PROMPT_FORENSIC_PREANALYSIS,
    parse_forensic_output,
)
from app.services.llm_providers.base import parse_json, parse_json_with_status
from app.services.llm_providers.lmstudio import LMStudioProvider
from app.services.pipeline_service import _normalize_and_save_entities, process_document_pipeline
from app.services.rule_engine import get_active_rules


def test_p1_json_no_silent_truncation_repair():
    """Il parser JSON non deve mai chiudere silenziosamente parentesi di un JSON troncato."""
    assert parse_json('{"a": 1, "b": 2,}') == {"a": 1, "b": 2}

    truncated = '{"ricavi": 100000, "costi": {"personale": 50000'
    assert parse_json(truncated) is None
    data, err = parse_json_with_status(truncated)
    assert data is None
    assert err == "truncated_json"


def test_p1_lmstudio_detects_finish_reason_length():
    """LMStudioProvider deve marcare ok=False se finish_reason=='length' o JSON troncato."""
    fake_resp = MagicMock()
    fake_resp.json.return_value = {
        "model": "qwen-test",
        "choices": [{"finish_reason": "length", "message": {"content": '{"ricavi": 123'}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 8192, "total_tokens": 8292},
    }
    prov = LMStudioProvider()
    with patch("app.services.llm_providers.lmstudio.post_with_retry", return_value=fake_resp):
        res = prov.extract(None, "text/plain", "prompt", "qwen-test")
    assert res.ok is False
    assert "troncata" in (res.error or "").lower()
    assert res.usage["completion_tokens"] == 8192


def test_p1_ocr_mixed_pdf_runs_ocr_on_scanned_page_only(tmp_path):
    """Un PDF misto (pag 1 testo nativo, pag 2 senza testo) deve eseguire OCR sulla pag 2 senza saltarla."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Pagina 1 nativa con testo digitale abbondante oltre la soglia di 30 caratteri.")
    pdf.add_page()  # Pagina 2 priva di testo selezionabile (simula scansione)
    pdf_path = tmp_path / "mixed.pdf"
    pdf.output(str(pdf_path))

    with patch("app.services.ocr._ocr_pdf_pages", return_value=({1: "Testo recuperato via OCR da pagina 2"}, [0.94], "paddleocr")) as mock_ocr:
        text, pages, meta = ocr.extract_text_with_meta(str(pdf_path))

    mock_ocr.assert_called_once()
    called_indices = mock_ocr.call_args[0][1]
    assert called_indices == [1]
    assert pages == 2
    assert meta["pages_native"] == 1
    assert meta["pages_ocr"] == 1
    assert meta["unreadable_pages"] == 0
    assert meta["page_coverage_pct"] == 100.0
    assert meta["ocr_mean_confidence"] == 0.94
    assert "Pagina 1 nativa" in text
    assert "Testo recuperato via OCR da pagina 2" in text


def test_p1_pipeline_idempotent_no_duplicates_and_full_raw_text(db_session, tmp_path):
    """La normalizzazione ripetuta sullo stesso documento è idempotente (zero duplicati) e salva testo > 20k."""
    case = Case(client_name="Gamma S.r.l.", client_tax_code="11223344556")
    db_session.add(case)
    db_session.flush()

    fpath = tmp_path / "visura_gamma.pdf"
    fpath.write_bytes(b"%PDF-1.4")
    doc = Document(
        case_id=case.id,
        original_filename="visura_gamma.pdf",
        storage_path=str(fpath),
        doc_type="visura_camerale",
        status="caricato",
    )
    db_session.add(doc)
    db_session.commit()

    long_text = "VISURA CAMERALE " + ("A" * 25000)
    ocr_meta = {"provider": "native_pdf", "total_pages": 5, "pages_native": 5, "pages_ocr": 0, "unreadable_pages": 0, "page_coverage_pct": 100.0}
    extracted = {
        "_llm_provider": "lmstudio",
        "_llm_model": "qwen-test",
        "impresa": {"denominazione": "Gamma S.r.l.", "codice_fiscale": "11223344556", "partita_iva": "11223344556", "capitale_conferimenti": 10000.0},
        "soci": [{"denominazione": "Rossi Luca", "codice_fiscale": "RSSLUC80A01H501X", "quota_percentuale": 100.0}],
        "immobili": [{"comune": "Roma", "foglio": "12", "particella": "34", "subalterno": "5", "categoria": "A/2", "rendita_catastale": 800.0}],
        "credit_positions": [{"creditor": "Banca Test", "debt_type": "Mutuo", "residual_amount": 50000.0}],
        "esposizione_attuale": [{"intermediario": "Banca CR", "accordato": 60000.0, "utilizzato": 40000.0}],
        "totali": {"esposizione_totale_utilizzata": 40000.0},
    }

    with patch("app.services.ocr.extract_text_with_meta", return_value=(long_text, 5, ocr_meta)), \
         patch("app.services.llm.extract", return_value=dict(extracted)):
        process_document_pipeline(db_session, doc.id)
        process_document_pipeline(db_session, doc.id)

    ext = db_session.query(Extraction).filter_by(document_id=doc.id).one()
    assert len(ext.raw_text) > 20000
    assert ext.llm_provider == "lmstudio"
    assert ext.json_output["_ocr_meta"]["total_pages"] == 5

    assert db_session.query(Company).filter_by(case_id=case.id).count() == 1
    assert db_session.query(CompanyMember).count() == 1
    assert db_session.query(RealEstate).filter_by(case_id=case.id).count() == 1
    assert db_session.query(DebtPosition).filter_by(case_id=case.id).count() == 1
    assert db_session.query(CreditExposure).filter_by(case_id=case.id).count() == 1
    assert db_session.query(CreditReportSummary).filter_by(case_id=case.id).count() == 1


def test_p1_studio_rules_case_isolation_and_cross_analysis_nulls(db_session):
    """Le regole legate a una pratica A non devono contaminare la pratica B."""
    c_a = Case(client_name="Pratica A")
    c_b = Case(client_name="Pratica B")
    db_session.add_all([c_a, c_b])
    db_session.flush()

    db_session.add(StudioRule(case_id=None, scope="global", rule_title="Globale", rule_prompt="Regola globale studio"))
    db_session.add(StudioRule(case_id=c_a.id, scope="global", rule_title="Specifica A", rule_prompt="Solo pratica A"))
    db_session.commit()

    rules_b = get_active_rules(db_session, case_id=c_b.id)
    assert [r.rule_title for r in rules_b] == ["Globale"]

    dossier_b = assemble_case_dossier(db_session, c_b.id)
    assert dossier_b["anagrafica_economica"]["presente"] is False
    assert dossier_b["anagrafica_economica"]["reddito_annuo"] is None
    assert dossier_b["centrale_rischi"]["presente"] is False
    assert dossier_b["centrale_rischi"]["esposizione_totale"] is None
    assert dossier_b["estratto_ruolo_aer"]["presente"] is False
    assert dossier_b["estratto_ruolo_aer"]["totale_residuo"] is None


def test_p1_forensic_chain_null_schema_and_validation():
    """Il prompt schema usa null per campi assenti e parse_forensic_output valida JSON troncato."""
    assert '"ricavi_gestionali_ultimo_anno": null' in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    bad = 'PARTE 1: [MATRICE_ESTRAZIONE_JSON]\n```json\n{"qualifica_ccii": "S.r.l.", "ricavi_gestionali_ultimo_anno": 1000\n```'
    mat, _ = parse_forensic_output(bad)
    assert "_validation_error" in mat
