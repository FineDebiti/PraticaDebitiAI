import pytest
from app.models import TaxDebtStatement, TaxDebtItem, RealEstate, CreditReportSummary, CreditExposure
from app.services.case_indicators import compute_case_indicators


def test_compute_case_indicators_empty(db_session, sample_case):
    res = compute_case_indicators(db_session, sample_case.id)
    assert "macro" in res
    assert "indicators" in res
    by_code = {i["code"]: i for i in res["indicators"]}
    assert by_code["aer_totale"]["value"] is None
    assert by_code["aer_totale"]["status"] == "na"


def test_compute_case_indicators_with_data(db_session, sample_case):
    # Add AER Tax Debt Statement
    stmt = TaxDebtStatement(case_id=sample_case.id, total_residuo=15000.0)
    db_session.add(stmt)
    db_session.flush()
    db_session.add(TaxDebtItem(
        statement_id=stmt.id,
        ente_categoria="erariale",
        totale_residuo=10000.0,
        proc_attive=True,
        data_notifica="2018-05-10"
    ))
    db_session.add(TaxDebtItem(
        statement_id=stmt.id,
        ente_categoria="previdenziale",
        totale_residuo=5000.0,
        proc_attive=False,
        data_notifica="2021-02-15"
    ))

    # Add Real Estate
    db_session.add(RealEstate(
        case_id=sample_case.id,
        kind="Fabbricato A/2",
        cadastral_value=120000.0,
        commercial_value=150000.0,
        is_primary_residence=False,
    ))

    # Add Credit Report
    db_session.add(CreditReportSummary(
        case_id=sample_case.id,
        total_exposure=25000.0,
        total_guarantees=10000.0,
        num_intermediaries=2,
        has_sofferenze=False,
    ))

    db_session.commit()

    res = compute_case_indicators(db_session, sample_case.id)
    by_code = {i["code"]: i for i in res["indicators"]}
    macro_by_code = {m["code"]: m for m in res["macro"]}

    # AER total
    assert by_code["aer_totale"]["value"] == 15000.0
    # AER procedure attive count
    assert by_code["aer_proc_attive"]["value"] == 1
    # 100% privileged (10k erariale + 5k previdenziale = 15k / 15k = 100%)
    assert by_code["aer_pct_privilegiati"]["value"] == 100.0

    # Macro Total Debt = 15k (AER) + 25k (CR) = 40,000
    assert macro_by_code["indebitamento_totale"]["value"] == 40000.0
    # Patrimonio aggredibile = 150,000 (commercial value)
    assert macro_by_code["patrimonio_aggredibile"]["value"] == 150000.0
    # Debito / patrimonio = 40,000 / 150,000 = 0.27
    assert macro_by_code["debito_su_patrimonio"]["value"] == 0.27
