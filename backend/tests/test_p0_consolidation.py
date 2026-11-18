"""Test di verifica P0 (Autonomia delle pratiche, Motore Unico, Semantica NULL rigorosa)."""

import io
import json
import pdfplumber
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import (
    Case,
    Company,
    CreditExposure,
    CreditReportSummary,
    Debtor,
    Document,
    FinancialStatement,
    TaxDebtItem,
    TaxDebtStatement,
)
from app.services.case_indicators import compute_case_indicators
from app.services.forensic_audit_engine import (
    build_complete_technical_dossier,
    export_audit_execution_csv,
    export_audit_execution_json,
    verify_inferences,
)
from app.services.indicators import compute_indicators
from app.services.pdf_report_generator import generate_preanalysis_pdf
from app.services.pipeline_service import _parse_vehicles_from_text
from app.services.preanalysis_report import build_preanalysis_report
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    calculate_test_pratico_ministeriale,
    check_ccii_soglie_impresa_minore,
    evaluate_pfn_ebitda,
    evaluate_risanabilita_diagnosi,
)
from app.services.technical_dossier_pdf_generator import generate_technical_dossier_pdf


def test_p0_1_no_client_name_hardcoding_or_damico_leakage(db_session):
    """Un cliente omonimo ('Mario D'Amico S.r.l.') privo di documenti D'Amico non deve MAI ereditare cifre benchmark."""
    case = Case(client_name="Mario D'Amico S.r.l.", client_tax_code="01234567890")
    db_session.add(case)
    db_session.flush()
    db_session.add(Company(case_id=case.id, role="cliente", name="Mario D'Amico S.r.l.", legal_form="S.r.l.", tax_code="01234567890"))
    db_session.commit()

    report = build_preanalysis_report(db_session, case.id)
    serialized = json.dumps(report, ensure_ascii=False)

    for forbidden in ("DMCLRZ95B68G273O", "493.094", "523.100,79", "386.695,79", "133.460", "2.945", "130382", "RG5 €63.256", "reddito €237"):
        assert forbidden not in serialized, f"Contaminazione D'Amico rilevata: {forbidden}"

    # Verifica che in assenza di documenti il dossier tecnico rilevi fonte mancante e Quality Gate rosso
    td = report["technical_dossier"]
    assert td["quality_gate"]["gate_status"] == "BLOCCO_QUALITATIVO_ROSSO"
    assert td["decimal_audit"]["all_quadrature_ok"] is False

    # Anche JSON / CSV e PDF su questo caso non devono contenere dati D'Amico
    audit_json = export_audit_execution_json([], report)
    assert "133460.00" not in audit_json
    assert "386695.79" not in audit_json

    pdf_client = generate_preanalysis_pdf(report, orientation="portrait")
    pdf_dossier = generate_technical_dossier_pdf(report)
    with pdfplumber.open(io.BytesIO(pdf_client)) as pc:
        assert len(pc.pages) == 7
        txt_c = "\n".join(p.extract_text() or "" for p in pc.pages)
        assert "Mario D'Amico S.r.l." in txt_c
        assert "523.100,79" not in txt_c
    with pdfplumber.open(io.BytesIO(pdf_dossier)) as pd:
        assert len(pd.pages) == 7
        txt_d = "\n".join(p.extract_text() or "" for p in pd.pages)
        assert "Mario D'Amico S.r.l." in txt_d
        assert "210.604,29" not in txt_d
        assert "Caso Critico Rigo RG5" not in txt_d


def test_p0_1_vehicles_parser_no_hardcoded_plates_or_values():
    """Il parser veicoli non contiene targhe o valori forfettari hardcodati."""
    sample_text = "ELENCO BENI MOBILI\nAutovettura Fiat Punto 2018 AB123CD\n"
    vehs = _parse_vehicles_from_text(sample_text)
    assert len(vehs) == 1
    assert vehs[0]["plate"] == "AB123CD"
    assert vehs[0]["estimated_value"] is None

    # Se nel testo compaiono stringhe libere non tabellate non devono spuntare targhe hardcoded
    empty_vehs = _parse_vehicles_from_text("ELENCO BENI MOBILI\nNessun mezzo elencato.")
    assert empty_vehs == []


def test_p0_2_unified_engine_and_real_document_page_count(db_session):
    """Un fascicolo S.r.l. con propri dati produce report, audit, CSV, JSON e 2 PDF coerenti al centesimo."""
    case = Case(client_name="Alfa Costruzioni S.r.l.", client_tax_code="09876543210")
    db_session.add(case)
    db_session.flush()
    comp = Company(case_id=case.id, role="cliente", name="Alfa Costruzioni S.r.l.", legal_form="Società a responsabilità limitata", company_type="capitali", tax_code="09876543210", capital=50000.0)
    db_session.add(comp)
    db_session.flush()
    doc1 = Document(case_id=case.id, original_filename="Bilancio_Alfa_2025.pdf", storage_path="/tmp/Bilancio_Alfa_2025.pdf", doc_type="bilancio", status="normalizzato", sha256="a" * 64, num_pages=14)
    doc2 = Document(case_id=case.id, original_filename="Estratto_AdER_Alfa.pdf", storage_path="/tmp/Estratto_AdER_Alfa.pdf", doc_type="cartella_aer", status="normalizzato", sha256="b" * 64, num_pages=6)
    db_session.add_all([doc1, doc2])
    db_session.flush()
    db_session.add(FinancialStatement(
        company_id=comp.id,
        case_id=case.id,
        fiscal_year_end="2025-12-31",
        statement_type="ordinario",
        revenues=1200000.0,
        total_assets=950000.0,
        total_debts=620000.0,
        net_result=-15000.0,
        source_document_id=doc1.id,
        raw_extraction={
            "conto_economico": {
                "ricavi_vendite": {"corrente": 1200000.0},
                "valore_produzione": {"corrente": 1220000.0},
                "costi_produzione": {"corrente": 1150000.0},
                "differenza_valore_costi": {"corrente": 70000.0},
                "ammortamenti": {"corrente": 30000.0},
                "utile_perdita": {"corrente": -15000.0},
            },
            "stato_patrimoniale": {"disponibilita_liquide": {"corrente": 45000.0}, "debiti_oltre": {"corrente": 100000.0}},
            "debiti_per_natura": {"fornitori": {"importo": 200000.0}, "banche": {"importo": 180000.0}},
        },
    ))
    stmt = TaxDebtStatement(case_id=case.id, total_residuo=95000.50, total_carico_affidato=88000.00, source_document_id=doc2.id)
    db_session.add(stmt)
    db_session.flush()
    db_session.add(TaxDebtItem(statement_id=stmt.id, ente_categoria="erariale", carico_affidato=88000.0, residuo_carico=85000.50, interessi_mora=10000.0, totale_residuo=95000.50))
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Gamma", accordato=200000.0, utilizzato=150000.25))
    db_session.commit()

    report = build_preanalysis_report(db_session, case.id)
    td = report["technical_dossier"]

    # Controlla copertura pagine reale (14 e 6, mai forzato a 1)
    pages_txt = {s["pagine"] for s in td["sources_matrix"]}
    assert "14 pagg." in pages_txt
    assert "6 pagg." in pages_txt

    # Controlla export CSV e JSON specifici del caso
    csv_txt = export_audit_execution_csv([doc1, doc2], report)
    assert "1220000" in csv_txt
    assert "523100.79" not in csv_txt

    # Controlla rimozione fonte -> revoca VERIFICATO
    mutated = build_complete_technical_dossier([doc1, doc2], report, removed_source_ids=["DOC-01"])
    assert mutated["sources_matrix"][0]["file_attivo"] is False
    assert mutated["quality_gate"]["gate_status"] == "BLOCCO_QUALITATIVO_ROSSO"


def test_p0_3_strict_null_vs_zero_semantics(db_session):
    """Dati mancanti restano NULL / NON_VERIFICABILE / na, mai 0.0 silenzioso; zero documentato resta 0.0."""
    # 1. EBITDA senza CE -> None (NULL)
    eb_empty = calculate_ebitda_oic12({})
    assert eb_empty["ebitda_standard"] is None
    assert eb_empty["stato_dato"] == "NON_VERIFICABILE_NULL"

    # 2. PFN ESMA senza liquidità -> None (NULL)
    pfn_missing_liq = calculate_pfn_esma(debiti_bancari_breve=100000.0, debiti_bancari_medio_lungo=0.0, disponibilita_liquide=None)
    assert pfn_missing_liq["pfn_totale"] is None
    assert pfn_missing_liq["stato_dato"] == "NON_VERIFICABILE_NULL"

    # 3. evaluate_pfn_ebitda con None -> na (mai 'cassa_netta')
    ev_null = evaluate_pfn_ebitda(None, 50000.0)
    assert ev_null["ratio"] is None
    assert ev_null["status"] == "na"
    assert ev_null["classe_merito"] == "non_verificabile"

    # 4. Soglie CCII con dati incompleti -> e_impresa_minore is None
    ccii_null = check_ccii_soglie_impresa_minore([], [], None)
    assert ccii_null["e_impresa_minore"] is None
    assert "Non verificabile" in ccii_null["qualifica_giuridica"]

    # 5. Test pratico ministeriale con debito None -> None / na (mai 'Agevole')
    tp_null = calculate_test_pratico_ministeriale(None)
    assert tp_null["rapporto"] is None
    assert tp_null["status"] == "na"

    # 6. Diagnosi risanabilità con EBITDA None -> Non valutabile
    diag_null = evaluate_risanabilita_diagnosi(None, None, None, None, False, None, False)
    assert diag_null["semaforo"] == "Non valutabile"

    # 7. Indicators senza liquidità -> PFN resta None; ma con liquidità e debiti espliciti 0.0 -> 0.0
    inds_missing = compute_indicators(sp={}, ce={}, deb={"tributari": {"importo": 20000.0}})
    by_c = {i["code"]: i for i in inds_missing}
    assert by_c["pfn"]["value_cur"] is None
    assert by_c["pfn"]["status"] == "na"

    inds_zero_doc = compute_indicators(
        sp={"disponibilita_liquide": {"corrente": 0.0}, "debiti_oltre": {"corrente": 0.0}},
        ce={},
        deb={"banche": {"importo": 0.0}},
    )
    by_z = {i["code"]: i for i in inds_zero_doc}
    assert by_z["pfn"]["value_cur"] == 0.0

    # 8. Case indicators su pratica vuota -> dti_ratio is None e risk_score is None
    empty_case = Case(client_name="Beta S.r.l.")
    db_session.add(empty_case)
    db_session.commit()
    ci_empty = compute_case_indicators(db_session, empty_case.id)
    assert ci_empty["dti_ratio"] is None
    assert ci_empty["risk_score"] is None
    ci_by_code = {i["code"]: i for i in ci_empty["indicators"]}
    assert ci_by_code["ccii_segnali_art3"]["value"] is None
    assert ci_by_code["ccii_segnali_art3"]["status"] == "na"


def test_p0_inference_block_active():
    bad = verify_inferences("Il rigo RG5 € 63.256 dimostra incassi effettivi di cassa.")
    assert bad["all_passed"] is False
    assert "BLOCCATO" in bad["checks"][0]["esito"]
