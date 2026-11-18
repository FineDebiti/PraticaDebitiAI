"""Test P2 (P2.1 routing locale & telemetria, P2.2 contesto multi-pass & copertura, P2.3 JSON strict)
e Matrice di Collaudo Sezione 7 (12 prove su fascicoli sintetici differenti).
"""

import json
from unittest.mock import MagicMock, patch
import pytest

from app.config import settings
from app.models import (
    Case,
    CaseCrossAnalysis,
    Company,
    CreditExposure,
    CreditReportSummary,
    Document,
    Extraction,
    FieldEdit,
    FinancialStatement,
    RealEstate,
    StudioRule,
    TaxDebtStatement,
)
from app.services import llm
from app.services.cross_analysis import (
    CrossAnalysisOutputSchema,
    assemble_case_dossier,
    execute_cross_analysis,
)
from app.services.forensic_audit_engine import (
    _build_dynamic_decimal_audit,
    build_complete_technical_dossier,
    verify_inferences,
)
from app.services.forensic_preanalysis_chain import run_forensic_preanalysis_chain
from app.services.llm_providers.base import ExtractionResult
from app.services.pipeline_service import process_document_pipeline
from app.services.preanalysis_report import build_preanalysis_report
from app.services.corrections import apply_corrections


@pytest.fixture(autouse=True)
def _mock_live_forensic_chain_http(request):
    """Evita timeout HTTP reali verso LM Studio nei test su build_preanalysis_report."""
    if "prova_10" in request.node.name:
        yield
        return
    with patch(
        "app.services.preanalysis_report.run_forensic_preanalysis_chain",
        return_value={"raw_output": "", "json_matrix": {}, "client_report_text": "", "telemetry": {"validation_status": "mocked"}},
    ):
        yield


def _seed_synthetic_srl_case(db_session, name="ALFA MECCANICA S.R.L.", cf="09876543210", aer_residuo=125000.0):
    case = Case(client_name=name, client_tax_code=cf)
    db_session.add(case)
    db_session.flush()
    comp = Company(case_id=case.id, role="cliente", name=name, legal_form="S.r.l.", tax_code=cf, vat=cf)
    db_session.add(comp)
    db_session.flush()
    db_session.add(
        FinancialStatement(
            company_id=comp.id,
            case_id=case.id,
            fiscal_year_end="2024-12-31",
            statement_type="bilancio_ordinario",
            revenues=420000.0,
            net_result=12000.0,
            total_assets=510000.0,
            total_debts=310000.0,
            privileged_debts=aer_residuo,
            equity=85000.0,
            raw_extraction={
                "ricavi": 420000.0,
                "costi_produzione": 360000.0,
                "ebitda": 60000.0,
            },
        )
    )
    doc = Document(
        case_id=case.id,
        original_filename="Estratto_Ruolo_Alfa.pdf",
        storage_path="/tmp/Estratto_Ruolo_Alfa.pdf",
        doc_type="cartella_aer",
        num_pages=3,
        status="normalizzato",
        sha256="a" * 64,
    )
    db_session.add(doc)
    db_session.flush()
    db_session.add(
        Extraction(
            document_id=doc.id,
            ocr_provider="pypdf",
            llm_provider="lmstudio",
            raw_text="Estratto di ruolo Agenzia Entrate Riscossione carico residuo.",
            json_output={
                "_ocr_meta": {"provider": "pypdf", "pages_total": 3, "unreadable_pages": 0, "page_coverage_pct": 100.0},
                "_validation_status": "valid",
            },
        )
    )
    db_session.add(
        TaxDebtStatement(
            case_id=case.id,
            source_document_id=doc.id,
            total_carico_affidato=aer_residuo + 25000.0,
            total_residuo=aer_residuo,
            data_elaborazione="2025-10-01",
            items=[],
        )
    )
    db_session.add(CreditReportSummary(case_id=case.id, total_exposure=80000.0, total_guarantees=0.0, num_intermediaries=1, has_sofferenze=False))
    db_session.add(CreditExposure(case_id=case.id, intermediary="BANCA BETA S.P.A.", category="Finanziamenti", accordato=100000.0, utilizzato=80000.0))
    db_session.commit()
    return case, doc


# ---------------------------------------------------------------------------
# P2.1 / P2.2 / P2.3
# ---------------------------------------------------------------------------

def test_p2_1_local_routing_blocks_implicit_cloud_fallback(monkeypatch):
    """Con llm_provider='lmstudio' e allow_cloud_llm_fallback=False non deve inviare dati a Gemini/Claude/OpenAI."""
    monkeypatch.setattr(settings, "llm_provider", "lmstudio")
    monkeypatch.setattr(settings, "allow_cloud_llm_fallback", False)
    monkeypatch.setattr(settings, "llm_fallback_chain", "lmstudio,gemini,claude,openai")
    monkeypatch.setattr(settings, "gemini_api_key", "fake-gem-key")
    monkeypatch.setattr(settings, "openai_api_key", "fake-oai-key")

    provs = [name for name, _ in llm._available_providers()]
    assert provs == ["lmstudio"]

    fake_fail = ExtractionResult({}, "lmstudio", "qwen-test", False, "LM Studio offline", retries=1, duration_s=0.42, validation_status="provider_error")
    with patch("app.services.llm_providers.lmstudio.LMStudioProvider.extract", return_value=fake_fail):
        out = llm.extract("Testo riservato pratica alfa", "altro")
    assert out["_llm_provider"] == "lmstudio"
    assert out["_llm_telemetry"]["fallback_used"] is False
    assert out["_llm_telemetry"]["retries"] == 1
    assert out["_llm_telemetry"]["validation_status"] == "provider_error"
    assert out["_llm_telemetry"]["error"] == "LM Studio offline"


# ---------------------------------------------------------------------------
# SEZIONE 7 — LE 12 PROVE DI COLLAUDO SU FASCICOLI DIFFERENTI
# ---------------------------------------------------------------------------

def test_collaudo_s7_prova_01_alterazione_controllata_debito(db_session):
    """Prova 1: alterazione controllata di un debito attiva quadratura ERRORE."""
    case, doc = _seed_synthetic_srl_case(db_session, aer_residuo=125000.0)
    report = build_preanalysis_report(db_session, case.id)
    # Righe documentate complete (AdER 125k + Banche 80k = 205k) e alterazione controllata (+50k) sul totale esposto
    t53 = report["capitolo_5_indebitamento"]["tabella_5_3_sintesi"]
    t53["righe"] = [r for r in t53["righe"] if r.get("importo_stimato") is not None]
    t53["totale_stimato"] = 255000.00
    dec = _build_dynamic_decimal_audit(report)
    assert dec["all_quadrature_ok"] is False
    assert any("ERRORE" in q.get("esito", "") for q in dec["quadrature"])


def test_collaudo_s7_prova_02_mancanza_documento_essenziale(db_session):
    """Prova 2: assenza di documento essenziale blocca il Quality Gate in ROSSO."""
    case, _ = _seed_synthetic_srl_case(db_session)
    report = build_preanalysis_report(db_session, case.id)
    docs = db_session.query(Document).filter_by(case_id=case.id).all()
    td = build_complete_technical_dossier(docs, report, removed_source_ids=["DOC-01"])
    assert any(a["severita"] == "ROSSO" and "DOC-01" in a.get("fonte", "") for a in td["anomaly_register"])
    assert td["quality_gate"]["gate_status"] == "BLOCCO_QUALITATIVO_ROSSO"


def test_collaudo_s7_prova_03_presenza_dati_contrastanti(db_session):
    """Prova 3: dati contrastanti (es. Bilancio vs CR) da cross-analysis vengono riflessi nell'audit."""
    case, _ = _seed_synthetic_srl_case(db_session)
    db_session.add(
        CaseCrossAnalysis(
            case_id=case.id,
            status="completed",
            incongruenze=[{
                "descrizione": "Debiti bancari bilancio EUR 180.000 vs Centrale Rischi EUR 80.000",
                "gravita": "SOSTANZIALE",
                "documenti_coinvolti": "Bilancio 2024 vs Centrale Rischi",
                "azione_consigliata": "Richiedere mastrino mutui bancari",
            }],
        )
    )
    db_session.commit()
    report = build_preanalysis_report(db_session, case.id)
    td = report["technical_dossier"]
    assert any("Debiti bancari bilancio" in a["descrizione"] and a["severita"] == "ROSSO" for a in td["anomaly_register"])


def test_collaudo_s7_prova_04_doppio_conteggio_idempotente(db_session, tmp_path):
    """Prova 4: ri-elaborazione sullo stesso documento non produce duplicati di immobili o debiti."""
    p = tmp_path / "visura_alfa.pdf"
    p.write_bytes(b"%PDF-1.4\n%fake\n")
    case = Case(client_name="BETA IMMOBILIARE SRL", client_tax_code="11223344556")
    db_session.add(case)
    db_session.flush()
    doc = Document(
        case_id=case.id,
        original_filename="visura_alfa.pdf",
        storage_path=str(p),
        doc_type="visura_catastale",
        status="caricato",
        sha256="b" * 64,
    )
    db_session.add(doc)
    db_session.commit()

    fake_meta = {"provider": "pypdf", "pages_total": 1, "pages_native": 1, "pages_ocr": 0, "unreadable_pages": 0, "page_coverage_pct": 100.0}
    fake_ext = {
        "immobili": [{"indirizzo": "Via Roma 10, Milano", "dati_catastali": "Fg 4 Part 120 Sub 3", "rendita_catastale": 850.0, "valore_catastale": 107100.0}],
        "_llm_provider": "lmstudio",
        "_llm_telemetry": {"provider": "lmstudio", "model": "qwen", "duration_s": 0.5, "retries": 0, "validation_status": "valid"},
    }
    with patch("app.services.ocr.extract_text_with_meta", return_value=("Visura catastale Via Roma 10", 1, fake_meta)), \
         patch("app.services.pipeline_service._extract_structured_data", return_value=fake_ext):
        process_document_pipeline(db_session, doc.id)
        process_document_pipeline(db_session, doc.id)

    assert db_session.query(RealEstate).filter_by(case_id=case.id).count() == 1
    assert db_session.query(Extraction).filter_by(document_id=doc.id).count() == 1


def test_collaudo_s7_prova_05_mancanza_liquidita_documentata_mai_zero(db_session):
    """Prova 5: in assenza di estratto conto o cassa in bilancio, la liquidità resta NULL mai EUR 0,00."""
    case, _ = _seed_synthetic_srl_case(db_session)
    report = build_preanalysis_report(db_session, case.id)
    pfn = report["capitolo_5_indebitamento"]["tabella_pfn_esma"]
    assert pfn["disponibilita_liquide"] is None
    assert pfn["pfn_totale"] is None
    assert report["technical_dossier"]["inference_audit"]["all_passed"] is True


def test_collaudo_s7_prova_06_errore_ocr_rilevato(db_session):
    """Prova 6: pagine illeggibili OCR devono risultare esplicitamente in audit e copertura cross-analysis."""
    case, doc = _seed_synthetic_srl_case(db_session)
    ext = db_session.query(Extraction).filter_by(document_id=doc.id).first()
    ext.json_output = {
        "_ocr_meta": {"provider": "rapidocr", "pages_total": 4, "pages_native": 1, "pages_ocr": 1, "unreadable_pages": 2, "page_coverage_pct": 50.0},
        "_validation_status": "valid",
    }
    db_session.commit()

    dossier = assemble_case_dossier(db_session, case.id)
    assert dossier["copertura_analisi"]["copertura_integrale"] is False
    assert dossier["copertura_analisi"]["documenti_pagine_illeggibili"] == 1

    report = build_preanalysis_report(db_session, case.id)
    assert any(a["area"] == "Qualità OCR / Copertura Pagine" and a["severita"] == "ARANCIO" for a in report["technical_dossier"]["anomaly_register"])


def test_collaudo_s7_prova_07_json_non_valido_qwen_scartato(db_session, monkeypatch):
    """Prova 7: output JSON Qwen malformato/incompleto su schema viene marcato validation_error, mai completed."""
    monkeypatch.setattr(settings, "llm_provider", "lmstudio")
    monkeypatch.setattr(settings, "allow_cloud_llm_fallback", False)
    case, _ = _seed_synthetic_srl_case(db_session)

    # Manca 'descrizione' obbligatoria e tipo errato su 'scenari'
    invalid_res = ExtractionResult(
        data={"incongruenze": [{"gravita": "SOSTANZIALE"}], "scenari": "NON_UNA_LISTA"},
        provider="lmstudio",
        model="qwen-test",
        ok=True,
        usage={"total_tokens": 120},
        validation_status="valid",
    )
    with patch("app.services.llm_providers.lmstudio.LMStudioProvider.extract", return_value=invalid_res):
        rec = execute_cross_analysis(db_session, case.id)

    assert rec.status == "validation_error"
    assert rec.raw_response["_telemetry"]["validation_status"] == "validation_error"


def test_collaudo_s7_prova_08_indisponibilita_qwen(db_session, monkeypatch):
    """Prova 8: se Qwen/LM Studio non risponde, nessuna chiamata cloud e stato error + telemetria completa."""
    monkeypatch.setattr(settings, "llm_provider", "lmstudio")
    monkeypatch.setattr(settings, "allow_cloud_llm_fallback", False)
    case, _ = _seed_synthetic_srl_case(db_session)

    down_res = ExtractionResult({}, "lmstudio", "qwen-test", False, "Connection refused", retries=1, duration_s=0.15, validation_status="provider_error")
    with patch("app.services.llm_providers.lmstudio.LMStudioProvider.extract", return_value=down_res):
        rec = execute_cross_analysis(db_session, case.id)

    assert rec.status == "error"
    assert rec.raw_response["_telemetry"]["provider"] == "lmstudio"
    assert rec.raw_response["_telemetry"]["fallback_used"] is False
    assert rec.raw_response["_telemetry"]["retries"] == 1
    assert "Connection refused" in rec.raw_response["_telemetry"]["error"]


def test_collaudo_s7_prova_09_inferenza_finanziaria_errata():
    """Prova 9: affermazione che equipara adeguamento fiscale ISA/RG5 a incasso monetario viene bloccata."""
    inf = verify_inferences(
        text_to_check="L'adeguamento ISA dimostra che l'impresa ha generato incassi effettivi non registrati."
    )
    assert inf["all_passed"] is False
    assert inf["checks"][0]["rule_id"] == "INF-01"
    assert "BLOCCATO" in inf["checks"][0]["esito"]


def test_collaudo_s7_prova_10_contesto_troncato_e_multipass(db_session, monkeypatch):
    """Prova 10: documenti parziali segnalati in cross-analysis e multi-pass attivo oltre 30k caratteri."""
    monkeypatch.setattr(settings, "llm_provider", "lmstudio")
    monkeypatch.setattr(settings, "allow_cloud_llm_fallback", False)
    case, doc = _seed_synthetic_srl_case(db_session)
    ext = db_session.query(Extraction).filter_by(document_id=doc.id).first()
    ext.raw_text = "INIZIO BILANCIO 2024\n" + ("Riga movimento contabile 100,00 EUR.\n" * 400) + "\nFINE TOTALI 999.999"
    ext.json_output["_input_truncated"] = True
    db_session.commit()

    valid_cross = ExtractionResult(
        data={
            "incongruenze": [],
            "duplicazioni": [],
            "dati_mancanti": [],
            "scenari": [],
            "richieste_prioritarie": [],
            "note_per_il_titolare": ["Analisi svolta su estratto campionario."],
        },
        provider="lmstudio",
        model="qwen-test",
        ok=True,
        usage={"prompt_tokens": 500, "completion_tokens": 100, "total_tokens": 600},
    )
    with patch("app.services.llm_providers.lmstudio.LMStudioProvider.extract", return_value=valid_cross):
        rec = execute_cross_analysis(db_session, case.id)

    assert rec.raw_response["_telemetry"]["copertura_integrale"] is False
    assert rec.raw_response["_telemetry"]["multi_pass"] is True
    assert any("Copertura parziale fonte" in d["dato_mancante"] for d in rec.dati_mancanti)

    # Verifica multi-pass su run_forensic_preanalysis_chain per testo > 30000 caratteri
    fake_chain = MagicMock()
    fake_chain.last_usage = {"prompt_tokens": 200, "completion_tokens": 50, "total_tokens": 250}
    fake_chain.last_model = "qwen-test"
    fake_chain.last_retries = 0
    fake_chain.last_finish_reason = "stop"
    fake_chain.invoke.return_value = (
        'PARTE 1: [MATRICE_ESTRAZIONE_JSON]\n```json\n'
        '{"qualifica_ccii": "S.r.l.", "ricavi_gestionali_ultimo_anno": 420000.0}\n'
        '```\nPARTE 2: [RELAZIONE_PREANALISI_CLIENTE]\nSintesi consolidata multi-pass.'
    )
    huge_text = "Riga contabile valida 123.\n" * 2000  # ~50.000 caratteri -> 3 passaggi + consolidamento
    with patch("app.services.forensic_preanalysis_chain.get_forensic_chain", return_value=fake_chain):
        res_chain = run_forensic_preanalysis_chain("ALFA SRL", "17/11/2026", huge_text)

    assert res_chain["telemetry"]["multi_pass"] is True
    assert res_chain["telemetry"]["chunks_total"] >= 2
    assert res_chain["telemetry"]["chunks_processed"] == res_chain["telemetry"]["chunks_total"]
    assert res_chain["telemetry"]["validation_status"] == "valid"


def test_collaudo_s7_prova_11_assenza_contaminazione_tra_pratiche(db_session):
    """Prova 11: due pratiche distinte non condividono né cifre né regole studio di caso."""
    case_a, _ = _seed_synthetic_srl_case(db_session, name="PRATICA UNO SRL", cf="00011122233", aer_residuo=50000.0)
    case_b, _ = _seed_synthetic_srl_case(db_session, name="PRATICA DUE D'AMICO", cf="99988877766", aer_residuo=175000.0)
    db_session.add(
        StudioRule(
            case_id=case_a.id,
            scope="single_case",
            scope_title=case_a.client_name,
            category="VERIFICA_OBBLIGATORIA",
            rule_title="Regola riservata SOLO Pratica Uno",
            rule_prompt="SEGRETO_ALFA_50000",
            is_active=True,
        )
    )
    db_session.commit()

    rep_a = build_preanalysis_report(db_session, case_a.id)
    rep_b = build_preanalysis_report(db_session, case_b.id)

    assert rep_a["capitolo_5_indebitamento"]["tabella_5_3_sintesi"]["totale_stimato"] == 130000.0
    assert rep_b["capitolo_5_indebitamento"]["tabella_5_3_sintesi"]["totale_stimato"] == 255000.0
    assert any(r["rule_prompt"] == "SEGRETO_ALFA_50000" for r in rep_a["studio_rules"])
    assert not any(r["rule_prompt"] == "SEGRETO_ALFA_50000" for r in rep_b["studio_rules"])


def test_collaudo_s7_prova_12_conservazione_human_gate_e_correzioni(db_session):
    """Prova 12: Human Gate resta separato dall'audit software e la registrazione correzioni è preservata."""
    case, _ = _seed_synthetic_srl_case(db_session)
    re_obj = RealEstate(case_id=case.id, kind="Magazzino", category="C/2", cadastral_income=400.0, cadastral_value=50000.0, is_primary_residence=False)
    db_session.add(re_obj)
    db_session.commit()

    report = build_preanalysis_report(db_session, case.id)
    docs = db_session.query(Document).filter_by(case_id=case.id).all()

    # Verifica assenza auto-approvazione Human Gate
    td_unapproved = build_complete_technical_dossier(docs, report, human_gate_approval=None)
    assert td_unapproved["quality_gate"]["human_gate_approved"] is False

    # Verifica conservazione flusso correzioni FieldEdit
    updated = apply_corrections(
        db_session,
        case.id,
        "real_estate",
        re_obj.id,
        changes={"cadastral_value": 95000.0},
        reason="Visura integrativa",
        operator="Avv. Bentivegna",
    )
    assert updated.cadastral_value == 95000.0
    assert db_session.query(FieldEdit).filter_by(entity_id=re_obj.id).count() == 1

    # Verifica approvazione esplicita Human Gate
    td_approved = build_complete_technical_dossier(
        docs, report,
        human_gate_approval={"approved": True, "professionista": "Avv. Aurelio Bentivegna", "timestamp": "17/11/2026 18:30"},
    )
    assert td_approved["quality_gate"]["human_gate_approved"] is True
