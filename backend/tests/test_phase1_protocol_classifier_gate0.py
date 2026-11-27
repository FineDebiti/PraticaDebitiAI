"""Test di accettazione Fase 1 — Classificazione 3D, Gate 0, Conferma API e migrazione Alembic."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect

from app.db import get_db
from app.main import app
from app.models.entities import (
    Case,
    Company,
    CreditExposure,
    CreditReportSummary,
    Debtor,
    Document,
    Extraction,
    FieldEdit,
    FinancialStatement,
    GuaranteeGiven,
    TaxDebtItem,
    TaxDebtStatement,
)
from app.services.protocols import classify_case_dimensions, get_protocol_assessment


def _make_case(db_session, *, code="PR-TEST", client_name="Cliente Test", tax_code="01234567890"):
    case = Case(code=code, client_name=client_name, client_tax_code=tax_code, status="nuova")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


def _add_company(db_session, case, *, name="Alfa Test", legal_form="S.r.l.", company_type="capitali",
                 vat="01234567890", rea="PA-123456", role="cliente", constitution_date="2015-01-15"):
    comp = Company(
        case_id=case.id,
        role=role,
        name=name,
        legal_form=legal_form,
        company_type=company_type,
        vat=vat,
        rea=rea,
        constitution_date=constitution_date,
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    return comp


def _add_fs(db_session, company, *, year="2024", total_assets=None, revenues=None,
            total_debts=None, equity=None, statement_type="ordinario"):
    fs = FinancialStatement(
        company_id=company.id,
        fiscal_year_end=f"{year}-12-31",
        statement_type=statement_type,
        total_assets=total_assets,
        revenues=revenues,
        total_debts=total_debts,
        equity=equity,
    )
    db_session.add(fs)
    db_session.commit()
    return fs


def _add_doc(db_session, case, *, filename="doc.pdf", doc_type="visura_camerale",
             status="elaborato", sha256="", raw_text="", json_output=None):
    doc = Document(
        case_id=case.id,
        original_filename=filename,
        storage_path=f"/tmp/{filename}",
        doc_type=doc_type,
        status=status,
        sha256=sha256,
    )
    db_session.add(doc)
    db_session.flush()
    if raw_text or json_output is not None:
        db_session.add(Extraction(
            document_id=doc.id,
            raw_text=raw_text,
            json_output=json_output,
        ))
    db_session.commit()
    db_session.refresh(doc)
    return doc


def test_srl_ordinaria_sopra_soglia(db_session):
    case = _make_case(db_session, client_name="Beta Holding")
    comp = _add_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    _add_fs(db_session, comp, year="2022", total_assets=250000, revenues=180000, total_debts=300000, equity=40000)
    _add_fs(db_session, comp, year="2023", total_assets=420000, revenues=290000, total_debts=620000, equity=-15000)
    _add_fs(db_session, comp, year="2024", total_assets=390000, revenues=240000, total_debts=590000, equity=-50000)

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "societa_capitali_srl"
    assert res.protocol_code == "B"
    assert res.supported_by_protocol is True
    assert res.accounting_regime == "ordinaria"
    assert res.ccii_size_qualification == "non_minore"


def test_srl_ordinaria_sotto_soglia_resta_societa_capitali(db_session):
    """Vincolo obbligatorio: una S.r.l. sotto soglia CCII resta societa_capitali_srl (Protocollo B)."""
    case = _make_case(db_session, client_name="Gamma Micro")
    comp = _add_company(db_session, case, legal_form="S.r.l.s.", company_type="capitali")
    _add_fs(db_session, comp, year="2022", total_assets=120000, revenues=95000, total_debts=180000, equity=12000)
    _add_fs(db_session, comp, year="2023", total_assets=135000, revenues=110000, total_debts=210000, equity=10000)
    _add_fs(db_session, comp, year="2024", total_assets=140000, revenues=125000, total_debts=240000, equity=5000)

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "societa_capitali_srl"
    assert res.protocol_code == "B"
    assert res.accounting_regime == "ordinaria"
    assert res.ccii_size_qualification == "impresa_minore"


def test_srl_senza_documenti_contabili_regime_non_documentato(db_session):
    """Vincolo obbligatorio: mai presumere il regime ordinario dalla sola forma S.r.l."""
    case = _make_case(db_session, client_name="Delta Senza Bilanci")
    _add_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    _add_doc(db_session, case, filename="visura.pdf", doc_type="visura_camerale", status="elaborato")

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "societa_capitali_srl"
    assert res.protocol_code == "B"
    assert res.accounting_regime == "non_documentato"
    assert res.ccii_size_qualification == "non_determinabile"


def test_impresa_individuale_ordinaria(db_session):
    case = _make_case(db_session, client_name="Ditta Rossi", tax_code="RSSMRA80A01H501Z")
    db_session.add(Debtor(case_id=case.id, client_type="ditta_individuale", tax_code="RSSMRA80A01H501Z"))
    db_session.commit()
    comp = _add_company(db_session, case, name="Rossi Impresa", legal_form="Impresa individuale", company_type="individuale")
    _add_fs(db_session, comp, year="2022", total_assets=90000, revenues=110000, total_debts=150000, equity=15000)
    _add_fs(db_session, comp, year="2023", total_assets=95000, revenues=120000, total_debts=160000, equity=14000)
    _add_fs(db_session, comp, year="2024", total_assets=98000, revenues=130000, total_debts=170000, equity=12000)

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "impresa_individuale"
    assert res.protocol_code == "A"
    assert res.accounting_regime == "ordinaria"
    assert res.ccii_size_qualification == "impresa_minore"


def test_impresa_individuale_semplificata_ccii_non_determinabile(db_session):
    case = _make_case(db_session, client_name="Ditta Bianchi", tax_code="BNCLGU75B02F205K")
    db_session.add(Debtor(case_id=case.id, client_type="ditta_individuale", tax_code="BNCLGU75B02F205K"))
    db_session.commit()
    _add_doc(
        db_session,
        case,
        filename="redditi_2024.pdf",
        doc_type="dichiarazione_redditi",
        raw_text="Modello Redditi PF 2024 Quadro RG impresa in contabilita semplificata art. 18 DPR 600.",
    )

    assessment = get_protocol_assessment(db_session, case.id)
    assert assessment["detected"]["legal_form_profile"] == "impresa_individuale"
    assert assessment["detected"]["protocol_code"] == "A"
    assert assessment["detected"]["accounting_regime"] == "semplificata"
    assert assessment["detected"]["ccii_size_qualification"] == "non_determinabile"

    # Gate 0 deve adattare la checklist al regime semplificato e distinguere i 3 livelli:
    # 1 sola dichiarazione acquisita+elaborata => document_acquired=True, document_processed_verified=True,
    # content_sufficient=False ("parziale", NON "presente"!)
    p0_by_code = {item["code"]: item for item in assessment["gate0"]["documenti_indispensabili_p0"]}
    assert "A-P0-CONT-SEMPL" in p0_by_code
    assert "A-P0-CONT-ORD" not in p0_by_code
    sempl_item = p0_by_code["A-P0-CONT-SEMPL"]
    assert sempl_item["document_acquired"] is True
    assert sempl_item["document_processed_verified"] is True
    assert sempl_item["content_sufficient"] is False
    assert sempl_item["status"] == "parziale"

    # Con 3 annualità distinte -> content_sufficient=True e status="presente"
    _add_doc(
        db_session, case, filename="redditi_2023.pdf", doc_type="dichiarazione_redditi",
        raw_text="Modello Redditi PF 2023 Quadro RG contabilita semplificata.",
    )
    _add_doc(
        db_session, case, filename="redditi_2022.pdf", doc_type="dichiarazione_redditi",
        raw_text="Modello Redditi PF 2022 Quadro RG contabilita semplificata.",
    )
    assessment_3y = get_protocol_assessment(db_session, case.id)
    sempl_3y = {i["code"]: i for i in assessment_3y["gate0"]["documenti_indispensabili_p0"]}["A-P0-CONT-SEMPL"]
    assert sempl_3y["content_sufficient"] is True
    assert sempl_3y["status"] == "presente"


def test_impresa_individuale_senza_documenti_contabili(db_session):
    case = _make_case(db_session, client_name="Ditta Senza Conti")
    db_session.add(Debtor(case_id=case.id, client_type="ditta_individuale"))
    db_session.commit()

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "impresa_individuale"
    assert res.protocol_code == "A"
    assert res.accounting_regime == "non_documentato"
    assert res.ccii_size_qualification == "non_determinabile"


def test_consumatore_non_assimilato_a_impresa_individuale(db_session):
    case = _make_case(db_session, client_name="Mario Verdi")
    db_session.add(Debtor(case_id=case.id, client_type="privato", annual_income=26000, monthly_net_income=1800))
    db_session.commit()
    _add_doc(db_session, case, filename="busta_paga.pdf", doc_type="busta_paga")

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "persona_fisica_non_imprenditore"
    assert res.protocol_code is None
    assert res.supported_by_protocol is False
    assert res.ccii_size_qualification == "non_applicabile"


def test_societa_persone_e_spa_non_assimilate_a_srl(db_session):
    # S.n.c. -> societa_persone, mai societa_capitali_srl
    case_snc = _make_case(db_session, code="SNC-1", client_name="F.lli Test S.n.c.")
    _add_company(db_session, case_snc, legal_form="S.n.c.", company_type="persone")
    res_snc = classify_case_dimensions(db_session, case_snc)
    assert res_snc.legal_form_profile == "societa_persone"
    assert res_snc.protocol_code is None
    assert res_snc.supported_by_protocol is False

    # S.a.s. -> societa_persone
    case_sas = _make_case(db_session, code="SAS-1", client_name="Alba S.a.s.")
    _add_company(db_session, case_sas, legal_form="S.a.s.", company_type="persone")
    res_sas = classify_case_dimensions(db_session, case_sas)
    assert res_sas.legal_form_profile == "societa_persone"
    assert res_sas.protocol_code is None

    # S.p.A. -> altra_forma_giuridica
    case_spa = _make_case(db_session, code="SPA-1", client_name="Grande S.p.A.")
    _add_company(db_session, case_spa, legal_form="S.p.A.", company_type="capitali")
    res_spa = classify_case_dimensions(db_session, case_spa)
    assert res_spa.legal_form_profile == "altra_forma_giuridica"
    assert res_spa.protocol_code is None


def test_forme_ambigue_o_contraddittorie_restano_forma_incerta(db_session):
    # Caso A: consumatore con reddito da dipendente + azienda cliente S.r.l.
    case_mix = _make_case(db_session, code="MIX-1", client_name="Misto")
    db_session.add(Debtor(case_id=case_mix.id, client_type="privato", annual_income=32000))
    db_session.commit()
    _add_company(db_session, case_mix, legal_form="S.r.l.", company_type="capitali")
    res_mix = classify_case_dimensions(db_session, case_mix)
    assert res_mix.legal_form_profile == "forma_incerta"
    assert res_mix.protocol_code is None

    # Caso B: due aziende cliente con forma giuridica incompatibile
    case_two = _make_case(db_session, code="MIX-2", client_name="Doppia")
    _add_company(db_session, case_two, name="Uno", legal_form="S.r.l.", company_type="capitali")
    _add_company(db_session, case_two, name="Due", legal_form="Ditta individuale", company_type="individuale")
    res_two = classify_case_dimensions(db_session, case_two)
    assert res_two.legal_form_profile == "forma_incerta"
    assert res_two.protocol_code is None

    # Caso C: societa generica senza legal_form specifica
    case_gen = _make_case(db_session, code="GEN-1", client_name="Generica")
    db_session.add(Debtor(case_id=case_gen.id, client_type="societa"))
    db_session.commit()
    res_gen = classify_case_dimensions(db_session, case_gen)
    assert res_gen.legal_form_profile == "forma_incerta"
    assert res_gen.protocol_code is None


def test_nessuna_dipendenza_dai_nomi_anagrafici(db_session):
    """Nomi contenenti S.r.l. / S.n.c. / Ditta Individuale non devono mai falsare la classificazione."""
    case = _make_case(db_session, code="NAME-INV", client_name="Mario S.r.l. S.n.c. Ditta Individuale")
    db_session.add(Debtor(
        case_id=case.id,
        first_name="Impresa Individuale",
        last_name="Rossi S.r.l.",
        client_type="privato",
        annual_income=22000,
    ))
    db_session.commit()

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "persona_fisica_non_imprenditore"
    assert res.protocol_code is None
    assert res.accounting_regime == "non_documentato"


def test_gate0_duplicati_sha256_p0_e_conclusivita(db_session):
    case = _make_case(db_session, client_name="Omega S.r.l.")
    comp = _add_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    _add_fs(db_session, comp, year="2022", total_assets=150000, revenues=120000, total_debts=200000, equity=10000)
    _add_fs(db_session, comp, year="2023", total_assets=160000, revenues=130000, total_debts=220000, equity=8000)
    _add_fs(db_session, comp, year="2024", total_assets=170000, revenues=140000, total_debts=250000, equity=5000)

    # Due file con stesso sha256 -> devono apparire nei duplicati Gate 0
    _add_doc(db_session, case, filename="visura_1.pdf", doc_type="visura_camerale", sha256="abc123dup")
    _add_doc(db_session, case, filename="visura_2.pdf", doc_type="visura_camerale", sha256="abc123dup")

    # Prima della conferma e senza AdER/CR: DIAGNOSI_PRELIMINARE_DELIMITATA
    g0_partial = get_protocol_assessment(db_session, case.id)
    assert g0_partial["gate0"]["conclusivity_level"] == "DIAGNOSI_PRELIMINARE_DELIMITATA"
    assert len(g0_partial["gate0"]["duplicate_groups"]) == 1
    assert g0_partial["gate0"]["duplicate_groups"][0]["count"] == 2
    assert any("Documenti duplicati" in a for a in g0_partial["gate0"]["anomalie_gate0"])
    assert len(g0_partial["gate0"]["decisioni_sospese"]) >= 1

    # Aggiungi AdER + CR + conferma operatore -> PREANALISI_SU_FASCICOLO_CONFERMATO
    db_session.add(TaxDebtStatement(case_id=case.id, denominazione="Omega S.r.l.", codice_fiscale="01234567890", total_residuo=85000, quadrature_ok=True, cf_mismatch=False))
    db_session.add(CreditReportSummary(case_id=case.id, most_recent_month="2025-12", total_exposure=90000))
    case.debtor_profile_confirmed = "societa_capitali_srl"
    case.accounting_regime_confirmed = "ordinaria"
    case.protocol_code = "B"
    case.dossier_completeness_status = "fascicolo_confermato"
    db_session.commit()

    g0_full = get_protocol_assessment(db_session, case.id)
    assert g0_full["gate0"]["conclusivity_level"] == "PREANALISI_SU_FASCICOLO_CONFERMATO"
    assert g0_full["confirmed"]["operator_identity_authenticated"] is False
    assert "non autenticata" in g0_full["confirmed"]["operator_audit_disclaimer"].lower()


def test_ccii_distingue_cassa_firma_sospesi_e_riconciliazione(db_session):
    """Revisione 2.A: garanzie CR e accordato non utilizzato non sono debito per cassa;
    AdER deduplicato + sospesi separati; bilanci infrannuali/obsoleti esclusi; conflitto non riconciliato -> non_determinabile."""
    # Caso 1: CR ha garanzie 450k + accordato 600k (utilizzato 150k), AdER ha 2 estratti duplicati (100k + 20k sospesi)
    case = _make_case(db_session, code="CCII-REV-1", client_name="Epsilon")
    comp = _add_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    _add_fs(db_session, comp, year="2023", total_assets=180000, revenues=150000, total_debts=260000, equity=20000)
    _add_fs(db_session, comp, year="2024", total_assets=190000, revenues=160000, total_debts=270000, equity=25000)
    _add_fs(db_session, comp, year="2025", total_assets=200000, revenues=170000, total_debts=280000, equity=30000)
    # Bilancio infrannuale 2026-06-30 non deve falsare la serie
    _add_fs(db_session, comp, year="2026", total_assets=210000, revenues=90000, total_debts=275000, statement_type="infrannuale")
    # Sostituisci con data non 12-31 esplicita sull'ultimo FS infrannuale
    interim = db_session.query(FinancialStatement).filter(
        FinancialStatement.company_id == comp.id,
        FinancialStatement.statement_type == "infrannuale",
    ).first()
    interim.fiscal_year_end = "2026-06-30"

    # Due AdER stesso CF -> solo il più recente (100k netti, 20k sospesi) deve valere
    st_old = TaxDebtStatement(case_id=case.id, codice_fiscale="01234567890", owner_kind="company",
                              data_elaborazione="2025-01-10", total_residuo=480000, total_residuo_netto=480000)
    st_new = TaxDebtStatement(case_id=case.id, codice_fiscale="01234567890", owner_kind="company",
                              data_elaborazione="2026-02-15", total_residuo=120000, total_residuo_netto=100000)
    db_session.add_all([st_old, st_new])
    db_session.flush()
    db_session.add(TaxDebtItem(statement_id=st_new.id, totale_residuo=120000, importo_sospeso=20000, totale_residuo_netto=100000))

    # CR: cassa 150k, accordato 600k (margine non usato 450k), garanzia firma 450k -> cassa effettiva 150k
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Alpha", category="rischi a scadenza",
                                  accordato=600000, utilizzato=150000, reference_month="2026-02"))
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Alpha", category="rischi di firma / garanzie",
                                  accordato=450000, utilizzato=450000, reference_month="2026-02"))
    db_session.add(GuaranteeGiven(case_id=case.id, intermediary="Banca Alpha", valore_garanzia=450000))
    db_session.commit()

    res = classify_case_dimensions(db_session, case)
    assert res.legal_form_profile == "societa_capitali_srl"
    assert res.ccii_size_qualification == "impresa_minore"
    assert res.ccii_external_breakdown["aer_netto_effettivo"] == 100000.0
    assert res.ccii_external_breakdown["aer_sospeso_contestato"] == 20000.0
    assert res.ccii_external_breakdown["cr_cassa_effettiva"] == 150000.0
    assert res.ccii_external_breakdown["cr_garanzie_e_firma"] == 450000.0
    assert res.ccii_external_breakdown["cr_accordato_informativo"] == 450000.0

    # Caso 2: conflitto non riconciliato (bilancio debiti 250k vs AdER netto 550k) -> non_determinabile con anomalia
    case_conf = _make_case(db_session, code="CCII-REV-2", client_name="Conflitto")
    comp2 = _add_company(db_session, case_conf, legal_form="S.r.l.", company_type="capitali")
    for yr in ("2023", "2024", "2025"):
        _add_fs(db_session, comp2, year=yr, total_assets=150000, revenues=120000, total_debts=250000)
    db_session.add(TaxDebtStatement(case_id=case_conf.id, codice_fiscale="99999999999",
                                    total_residuo=550000, total_residuo_netto=550000))
    db_session.commit()

    res_conf = classify_case_dimensions(db_session, case_conf)
    assert res_conf.ccii_size_qualification == "non_determinabile"
    assert any("riconciliazione" in a.lower() for a in res_conf.anomalies)

    # Caso 3: bilanci obsoleti (2019-2021) -> non_determinabile
    case_old = _make_case(db_session, code="CCII-REV-3", client_name="Obsoleti")
    comp3 = _add_company(db_session, case_old, legal_form="S.r.l.", company_type="capitali")
    for yr in ("2019", "2020", "2021"):
        _add_fs(db_session, comp3, year=yr, total_assets=100000, revenues=90000, total_debts=80000)
    res_old = classify_case_dimensions(db_session, case_old)
    assert res_old.ccii_size_qualification == "non_determinabile"
    assert any("antecedente" in a.lower() for a in res_old.anomalies)


def test_gate0_solo_un_bilancio_resta_parziale_e_blocca_fascicolo_confermato(db_session):
    """Revisione 2.B: la presenza di 1 solo bilancio non attesta la sufficienza P0 (3 esercizi)."""
    case = _make_case(db_session, code="G0-PART", client_name="Parziale Srl")
    comp = _add_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    _add_fs(db_session, comp, year="2024", total_assets=150000, revenues=120000, total_debts=180000)
    db_session.add(TaxDebtStatement(case_id=case.id, total_residuo=20000, quadrature_ok=True, cf_mismatch=False))
    db_session.add(CreditReportSummary(case_id=case.id, most_recent_month="2025-12", total_exposure=30000))
    case.debtor_profile_confirmed = "societa_capitali_srl"
    case.protocol_code = "B"
    case.dossier_completeness_status = "fascicolo_confermato"
    db_session.commit()

    assessment = get_protocol_assessment(db_session, case.id)
    p0_bil = next(i for i in assessment["gate0"]["documenti_indispensabili_p0"] if i["code"] == "B-P0-BIL")
    assert p0_bil["document_acquired"] is True
    assert p0_bil["document_processed_verified"] is True
    assert p0_bil["content_sufficient"] is False
    assert p0_bil["status"] == "parziale"
    assert assessment["gate0"]["conclusivity_level"] == "DIAGNOSI_PRELIMINARE_DELIMITATA"


def test_api_get_readonly_and_patch_override_audit(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        case = _make_case(db_session, client_name="Sigma Test")
        _add_company(db_session, case, legal_form="S.r.l.", company_type="capitali")

        # GET in sola lettura: non modifica i campi confermati né crea FieldEdit
        r_get = client.get(f"/api/cases/{case.id}/protocol-assessment")
        assert r_get.status_code == 200
        body = r_get.json()
        assert body["detected"]["legal_form_profile"] == "societa_capitali_srl"
        assert body["confirmed"]["debtor_profile_confirmed"] is None
        assert db_session.query(FieldEdit).filter(FieldEdit.case_id == case.id).count() == 0

        # PATCH conferma/override: protocol_code derivato dal profilo, con audit FieldEdit
        r_patch = client.patch(
            f"/api/cases/{case.id}/protocol-confirmation",
            json={
                "debtor_profile_confirmed": "impresa_individuale",
                "accounting_regime_confirmed": "semplificata",
                "dossier_completeness_status": "in_raccolta",
                "operator": "Dott. Test",
                "reason": "Verifica visura reale ditta",
            },
        )
        assert r_patch.status_code == 200
        patched = r_patch.json()
        assert patched["confirmed"]["debtor_profile_confirmed"] == "impresa_individuale"
        assert patched["confirmed"]["accounting_regime_confirmed"] == "semplificata"
        assert patched["confirmed"]["protocol_code"] == "A"
        assert patched["effective"]["protocol_code"] == "A"

        edits = db_session.query(FieldEdit).filter(
            FieldEdit.case_id == case.id,
            FieldEdit.entity_type == "case_protocol",
        ).all()
        assert len(edits) == 3  # profile, regime, protocol_code (dossier status era gia in_raccolta)
        assert {e.field for e in edits} == {
            "debtor_profile_confirmed",
            "accounting_regime_confirmed",
            "protocol_code",
        }

        # Valori invalidi -> 422
        r_bad = client.patch(
            f"/api/cases/{case.id}/protocol-confirmation",
            json={"debtor_profile_confirmed": "profilo_inventato"},
        )
        assert r_bad.status_code == 422

        # Pratica inesistente -> 404
        r_missing = client.get("/api/cases/non-esiste-id/protocol-assessment")
        assert r_missing.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_alembic_e5f6a7b8c9d0_reversibility_on_isolated_sqlite(tmp_path, monkeypatch):
    """Verifica upgrade/downgrade/upgrade Alembic su SQLite temporaneo isolato (mai Postgres live)."""
    from sqlalchemy import text
    from app.config import settings

    db_file = tmp_path / "alembic_reversibility.db"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setattr(settings, "database_url", db_url)
    assert settings.database_url.startswith("sqlite:///")

    # Prepara la tabella cases nello schema precedente d4e5f6a7b8c9 (evita vecchie DDL Postgres)
    eng_init = create_engine(db_url)
    try:
        with eng_init.begin() as conn:
            conn.execute(text("""
                CREATE TABLE cases (
                    id VARCHAR PRIMARY KEY,
                    organization_id VARCHAR,
                    code VARCHAR,
                    client_name VARCHAR,
                    client_tax_code VARCHAR,
                    status VARCHAR,
                    notes TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    priority VARCHAR,
                    referent VARCHAR,
                    tags VARCHAR,
                    next_deadline VARCHAR
                )
            """))
    finally:
        eng_init.dispose()

    backend_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    expected_cols = {
        "debtor_profile_detected",
        "debtor_profile_confirmed",
        "accounting_regime_detected",
        "accounting_regime_confirmed",
        "protocol_code",
        "dossier_completeness_status",
        "protocol_confirmed_at",
    }

    command.stamp(alembic_cfg, "d4e5f6a7b8c9")
    command.upgrade(alembic_cfg, "e5f6a7b8c9d0")
    eng = create_engine(db_url)
    try:
        cols_up = {c["name"] for c in inspect(eng).get_columns("cases")}
        assert expected_cols.issubset(cols_up)
    finally:
        eng.dispose()

    command.downgrade(alembic_cfg, "d4e5f6a7b8c9")
    eng = create_engine(db_url)
    try:
        cols_down = {c["name"] for c in inspect(eng).get_columns("cases")}
        assert expected_cols.isdisjoint(cols_down)
    finally:
        eng.dispose()

    command.upgrade(alembic_cfg, "e5f6a7b8c9d0")
    eng = create_engine(db_url)
    try:
        cols_reup = {c["name"] for c in inspect(eng).get_columns("cases")}
        assert expected_cols.issubset(cols_reup)
    finally:
        eng.dispose()
