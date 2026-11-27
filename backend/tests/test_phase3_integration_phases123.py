"""Test d'integrazione end-to-end fra Fase 1, Fase 2 e Fase 3 su output reali dei moduli."""

from __future__ import annotations

from app.models.entities import (
    Case,
    Company,
    CreditExposure,
    CreditReportSummary,
    DebtPosition,
    Document,
    FieldEdit,
    FinancialStatement,
    GuaranteeGiven,
    TaxDebtItem,
    TaxDebtStatement,
)
from app.services.protocols.ccii_matrix import evaluate_ccii_matrix
from app.services.protocols.classifier import classify_case_dimensions
from app.services.protocols.debt_ledger import build_debt_ledger
from app.services.protocols.formula_engine import run_formula_engine
from app.services.protocols.gate0 import evaluate_gate0
from app.services.protocols.service import confirm_case_protocol, get_ccii_matrix_simulation


def _create_case(
    db_session,
    *,
    name: str = "Società Alfa S.r.l.",
    legal_form: str = "S.r.l.",
    company_type: str = "capitali",
    constitution_date: str = "2018-01-15",
) -> tuple[Case, Company]:
    case = Case(client_name=name, status="ready")
    db_session.add(case)
    db_session.flush()
    comp = Company(
        case_id=case.id,
        role="cliente",
        name=name,
        legal_form=legal_form,
        company_type=company_type,
        vat="12345678901",
        rea="PA-123456",
        constitution_date=constitution_date,
    )
    db_session.add(comp)
    db_session.flush()
    return case, comp


def _add_fs(
    db_session,
    comp: Company,
    *,
    year: str,
    attivo: float | None,
    ricavi: float | None,
    debiti: float | None,
    equity: float = 60000.0,
    statement_type: str = "bilancio_annuale",
    fornitori: float | None = 40000.0,
    banche: float | None = 80000.0,
    tfr: float | None = 20000.0,
    tributari: float | None = 50000.0,
    include_sp: bool = True,
) -> FinancialStatement:
    raw: dict = {
        "conto_economico": {
            "valore_produzione": ricavi if ricavi is not None else 0.0,
            "ricavi_vendite": ricavi if ricavi is not None else 0.0,
            "costi_produzione": (ricavi - 30000.0) if ricavi is not None else 0.0,
            "differenza_valore_costi": 30000.0,
            "ammortamento_immateriali": 5000.0,
            "ammortamento_materiali": 10000.0,
            "svalutazioni_immobilizzazioni": 0.0,
            "svalutazione_crediti": 0.0,
            "accantonamenti_rischi": 0.0,
            "altri_accantonamenti": 0.0,
        }
    }
    if include_sp:
        raw["stato_patrimoniale"] = {
            "totale_attivo": attivo,
            "patrimonio_netto": equity,
            "fondi_rischi": 0.0,
            "tfr": tfr if tfr is not None else 0.0,
            "debiti_totali": debiti,
            "ratei_risconti_passivi": 0.0,
            "totale_passivo": attivo,
            "disponibilita_liquide": 15000.0,
            "crediti_commerciali": 40000.0,
            "rimanenze": 10000.0,
            "debiti_breve": {"banche": banche or 0.0},
            "debiti_oltre": {"banche": 0.0},
            "debiti_leasing_breve": 0.0,
            "debiti_leasing_oltre": 0.0,
            "debiti_commerciali_non_correnti": 0.0,
            "mezzi_equivalenti_cassa": 0.0,
        }
        deb_nat: dict = {}
        if fornitori is not None:
            deb_nat["fornitori"] = {"importo": fornitori}
        if banche is not None:
            deb_nat["banche"] = {"importo": banche}
            deb_nat["banche_breve"] = {"importo": banche}
            deb_nat["banche_oltre"] = {"importo": 0.0}
        if tfr is not None:
            deb_nat["tfr"] = {"importo": tfr}
        if tributari is not None:
            deb_nat["tributari"] = {"importo": tributari}
        raw["debiti_per_natura"] = deb_nat

    fs = FinancialStatement(
        company_id=comp.id,
        case_id=comp.case_id,
        fiscal_year_end=f"{year}-12-31",
        statement_type=statement_type,
        revenues=ricavi if ricavi is not None else 0.0,
        total_assets=attivo if attivo is not None else 0.0,
        total_debts=debiti if debiti is not None else 0.0,
        equity=equity,
        net_result=18000.0,
        raw_extraction=raw,
    )
    db_session.add(fs)
    return fs


def _add_doc(db_session, case: Case, *, doc_type: str, filename: str, status: str = "elaborato", sha: str = "h1") -> None:
    db_session.add(Document(
        case_id=case.id,
        doc_type=doc_type,
        original_filename=filename,
        storage_path=f"/tmp/{filename}",
        status=status,
        sha256=sha,
    ))


def _run_real_pipeline(db_session, case: Case, *, assessment_date: str = "2026-11-27", facts: list[dict] | None = None) -> tuple[dict, dict, dict, dict]:
    db_session.expire_all()
    case = db_session.get(Case, case.id)
    clients = [c for c in case.companies if (c.role or "cliente") == "cliente"]
    fss = db_session.query(FinancialStatement).filter(FinancialStatement.company_id.in_([c.id for c in clients])).all()

    cls = classify_case_dimensions(
        db_session,
        case,
        effective_profile_override=case.debtor_profile_confirmed,
        effective_regime_override=case.accounting_regime_confirmed,
    )
    gate0 = evaluate_gate0(case, cls, fss, clients)
    ledger = build_debt_ledger(db_session, case)
    formula = run_formula_engine(db_session, case, cls, ledger)
    matrix = evaluate_ccii_matrix(
        cls,
        gate0,
        ledger,
        formula,
        assessment_date=assessment_date,
        effective_legal_form=gate0.effective_legal_form_profile,
        effective_accounting_regime=gate0.effective_accounting_regime,
        procedural_facts=facts,
        simulation_mode=True,
    )
    return {"cls": cls, "gate0": gate0}, ledger, formula, matrix


def test_e2e_1_impresa_sotto_soglia_completa_3_esercizi(db_session):
    case, comp = _create_case(db_session, name="Beta S.r.l.", constitution_date="2019-01-10")
    for idx, yr in enumerate(("2024", "2025", "2026")):
        _add_fs(db_session, comp, year=yr, attivo=210000.0, ricavi=165000.0, debiti=190000.0, fornitori=60000.0, banche=80000.0, tfr=0.0, tributari=50000.0)
        _add_doc(db_session, case, doc_type="bilancio", filename=f"bilancio_{yr}.pdf", sha=f"bil-{idx}")

    _add_doc(db_session, case, doc_type="visura_camerale", filename="visura.pdf", sha="vis-1")
    _add_doc(db_session, case, doc_type="ruoli_ader", filename="ader.pdf", sha="ader-1")
    _add_doc(db_session, case, doc_type="cr_banca_italia", filename="cr.pdf", sha="cr-1")

    st = TaxDebtStatement(case_id=case.id, codice_fiscale="12345678901", total_residuo=50000.0, total_residuo_netto=50000.0, quadrature_ok=True, cf_mismatch=False)
    db_session.add(st)
    db_session.flush()
    db_session.add(TaxDebtItem(statement_id=st.id, numero_documento="CRT-001", ente_categoria="erariale", ente_creditore="AdER", totale_residuo=50000.0, totale_residuo_netto=50000.0))
    db_session.add(CreditReportSummary(case_id=case.id, most_recent_month="2026-10", total_exposure=80000.0, total_guarantees=0.0))
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Uno", category="rischi_autoliquidanti", reference_month="2026-10", accordato=100000.0, utilizzato=80000.0))
    db_session.commit()

    confirm_case_protocol(
        db_session, case.id,
        debtor_profile_confirmed="societa_capitali_srl",
        accounting_regime_confirmed="ordinaria",
        dossier_completeness_status="fascicolo_confermato",
        operator="Avv. Reviewer",
        reason="Verifica fascicolo",
    )

    p1, ledger, formula, matrix = _run_real_pipeline(db_session, case, assessment_date="2026-11-27")
    assert p1["cls"].ccii_size_qualification == "impresa_minore"
    assert p1["gate0"].conclusivity_level == "PREANALISI_SU_FASCICOLO_CONFERMATO"
    assert ledger["stato_dato"] == "VERIFICATO"
    assert formula["annual_periods"][-1]["pfn_esma"]["validation_status"] == "VERIFICATO"
    assert matrix["automatic_recommendation"] is None
    assert matrix["profile_snapshot"]["protocol_code"] == "B"
    assert matrix["profile_snapshot"]["debt_perimeter"]["debiti_complessivi_ricostruzione_affidabile"] is True
    assert matrix["profile_snapshot"]["debt_perimeter"]["debiti_complessivi_anche_non_scaduti_eur"] == 190000.0

    cards = {s["rule_code"]: s for s in matrix["schede_valutazione"]}
    assert cards["CCII-DIM-01"]["deterministic_outcome"] == "VERIFICATO"
    assert cards["CCII-ADR-01"]["deterministic_outcome"] == "NON_SODDISFATTO"
    assert cards["CCII-PRO-CP"]["deterministic_outcome"] == "NON_SODDISFATTO"


def test_e2e_2_impresa_sopra_soglia_per_attivo(db_session):
    case, comp = _create_case(db_session, name="Gamma S.r.l.")
    for yr in ("2024", "2025", "2026"):
        _add_fs(db_session, comp, year=yr, attivo=380000.0 if yr == "2026" else 210000.0, ricavi=150000.0, debiti=190000.0, fornitori=190000.0, banche=0.0, tfr=0.0, tributari=0.0)
    db_session.commit()

    p1, _, _, matrix = _run_real_pipeline(db_session, case)
    assert p1["cls"].ccii_size_qualification == "non_minore"
    dim = next(s for s in matrix["schede_valutazione"] if s["rule_code"] == "CCII-DIM-01")
    assert dim["deterministic_outcome"] == "NON_SODDISFATTO"
    assert any("attivo" in m.lower() for m in dim["missing_requirements"])


def test_e2e_3_impresa_sopra_soglia_per_ricavi(db_session):
    case, comp = _create_case(db_session, name="Delta S.r.l.")
    for yr in ("2024", "2025", "2026"):
        _add_fs(db_session, comp, year=yr, attivo=210000.0, ricavi=260000.0 if yr == "2026" else 150000.0, debiti=190000.0, fornitori=190000.0, banche=0.0, tfr=0.0, tributari=0.0)
    db_session.commit()

    p1, _, _, matrix = _run_real_pipeline(db_session, case)
    assert p1["cls"].ccii_size_qualification == "non_minore"
    dim = next(s for s in matrix["schede_valutazione"] if s["rule_code"] == "CCII-DIM-01")
    assert dim["deterministic_outcome"] == "NON_SODDISFATTO"
    assert any("ricavi" in m.lower() for m in dim["missing_requirements"])


def test_e2e_4_impresa_sopra_soglia_per_debiti(db_session):
    case, comp = _create_case(db_session, name="Epsilon S.r.l.")
    for yr in ("2024", "2025", "2026"):
        _add_fs(db_session, comp, year=yr, attivo=210000.0, ricavi=150000.0, debiti=580000.0 if yr == "2026" else 180000.0, fornitori=580000.0 if yr == "2026" else 180000.0, banche=0.0, tfr=0.0, tributari=0.0)
    db_session.commit()

    p1, _, _, matrix = _run_real_pipeline(db_session, case)
    assert p1["cls"].ccii_size_qualification == "non_minore"
    dim = next(s for s in matrix["schede_valutazione"] if s["rule_code"] == "CCII-DIM-01")
    assert dim["deterministic_outcome"] == "NON_SODDISFATTO"
    assert any("debiti" in m.lower() for m in dim["missing_requirements"])


def test_e2e_5_impresa_dati_parziali_non_determinabile(db_session):
    case, comp = _create_case(db_session, name="Zeta S.r.l.", constitution_date="2015-05-01")
    _add_fs(db_session, comp, year="2026", attivo=120000.0, ricavi=100000.0, debiti=90000.0, fornitori=90000.0, banche=0.0, tfr=0.0, tributari=0.0)
    db_session.commit()

    p1, _, _, matrix = _run_real_pipeline(db_session, case)
    assert p1["cls"].ccii_size_qualification == "non_determinabile"
    dim = next(s for s in matrix["schede_valutazione"] if s["rule_code"] == "CCII-DIM-01")
    assert dim["deterministic_outcome"] == "NON_DETERMINABILE"


def test_e2e_6_impresa_costituita_meno_di_3_esercizi(db_session):
    case, comp = _create_case(db_session, name="Eta Startup S.r.l.", constitution_date="2025-02-01")
    _add_fs(db_session, comp, year="2025", attivo=140000.0, ricavi=95000.0, debiti=110000.0, fornitori=60000.0, banche=50000.0, tfr=0.0, tributari=0.0)
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Young", category="rischi_a_scadenza", reference_month="2026-10", accordato=50000.0, utilizzato=50000.0))
    db_session.commit()

    p1, _, _, matrix = _run_real_pipeline(db_session, case, assessment_date="2026-11-27")
    assert p1["cls"].ccii_size_qualification == "impresa_minore"
    dim = next(s for s in matrix["schede_valutazione"] if s["rule_code"] == "CCII-DIM-01")
    assert dim["deterministic_outcome"] == "VERIFICATO"
    assert any("meno di 3 anni" in s.lower() for s in dim["satisfied_requirements"])
    assert matrix["profile_snapshot"]["dimensional_contract"]["young_company_under_3_years"] is True


def test_e2e_7_conferma_manuale_profilo_e_simulazione_service(db_session):
    case, comp = _create_case(db_session, name="Theta Impresa Individuale", legal_form="Ditta individuale", company_type="individuale")
    _add_fs(db_session, comp, year="2026", attivo=None, ricavi=240000.0, debiti=None, include_sp=False, statement_type="contabilita_semplificata")
    db_session.commit()

    confirm_case_protocol(
        db_session, case.id,
        debtor_profile_confirmed="impresa_individuale",
        accounting_regime_confirmed="semplificata",
        dossier_completeness_status="in_raccolta",
        operator="Avv. Test",
        reason="Verifica ditta semplificata",
    )
    sim = get_ccii_matrix_simulation(db_session, case.id, assessment_date="2026-11-27", simulation_mode=True)
    m = sim["ccii_matrix"]
    assert m["profile_snapshot"]["legal_form_profile"] == "impresa_individuale"
    assert m["profile_snapshot"]["accounting_regime"] == "semplificata"
    assert m["profile_snapshot"]["protocol_code"] == "A"
    assert m["automatic_recommendation"] is None
    edits = db_session.query(FieldEdit).filter(FieldEdit.case_id == case.id).all()
    assert any(e.field == "debtor_profile_confirmed" and e.new_value == "impresa_individuale" for e in edits)


def test_e2e_8_blocchi_riconciliazione_necessaria_e_non_verificabile_null(db_session):
    # A) RICONCILIAZIONE_NECESSARIA: DebtPosition su stesso intermediario di CR senza reference contrattuale
    case1, comp1 = _create_case(db_session, name="Iota S.r.l.")
    for yr in ("2024", "2025", "2026"):
        _add_fs(db_session, comp1, year=yr, attivo=150000.0, ricavi=120000.0, debiti=150000.0, fornitori=150000.0, banche=0.0, tfr=0.0, tributari=0.0)
    db_session.add(CreditExposure(case_id=case1.id, intermediary="Banca Alpha", category="rischi_autoliquidanti", reference_month="2026-10", accordato=100000.0, utilizzato=80000.0))
    db_session.add(DebtPosition(case_id=case1.id, creditor_name="Banca Alpha", debt_type="mutuo", original_amount=80000.0, residual_amount=80000.0, validated=True))
    db_session.commit()

    _, ledger1, _, matrix1 = _run_real_pipeline(db_session, case1)
    assert ledger1["stato_dato"] == "RICONCILIAZIONE_NECESSARIA"
    assert matrix1["profile_snapshot"]["debt_mass_verified"] is False
    cards1 = {s["rule_code"]: s for s in matrix1["schede_valutazione"]}
    assert cards1["CCII-DIM-01"]["deterministic_outcome"] == "NON_DETERMINABILE"
    assert cards1["CCII-ADR-01"]["deterministic_outcome"] == "NON_DETERMINABILE"

    # B) NON_VERIFICABILE_NULL: CR priva di reference_month omogeneo
    case2, comp2 = _create_case(db_session, name="Kappa S.r.l.")
    for yr in ("2024", "2025", "2026"):
        _add_fs(db_session, comp2, year=yr, attivo=150000.0, ricavi=120000.0, debiti=100000.0, fornitori=100000.0, banche=0.0, tfr=0.0, tributari=0.0)
    db_session.add(CreditExposure(case_id=case2.id, intermediary="Banca Beta", category="rischi_autoliquidanti", reference_month=None, accordato=90000.0, utilizzato=70000.0))
    db_session.commit()

    _, ledger2, _, matrix2 = _run_real_pipeline(db_session, case2)
    assert ledger2["stato_dato"] == "NON_VERIFICABILE_NULL"
    assert matrix2["profile_snapshot"]["debt_mass_verified"] is False
    assert next(s for s in matrix2["schede_valutazione"] if s["rule_code"] == "CCII-DIM-01")["deterministic_outcome"] == "NON_DETERMINABILE"


def test_e2e_9_perimetro_6_componenti_e_blocco_solo_cassa_senza_non_scaduti(db_session):
    # Caso A: 6 componenti complete distinte (cassa doc, finanziarie, complessivi bilancio, contestate AdER, garanzie non escusse, riconciliazione)
    case, comp = _create_case(db_session, name="Lambda S.r.l.")
    for yr in ("2024", "2025", "2026"):
        _add_fs(db_session, comp, year=yr, attivo=250000.0, ricavi=180000.0, debiti=260000.0, fornitori=100000.0, banche=100000.0, tfr=10000.0, tributari=50000.0)
    st = TaxDebtStatement(case_id=case.id, codice_fiscale="99988877766", total_residuo=75000.0, total_residuo_netto=50000.0)
    db_session.add(st)
    db_session.flush()
    db_session.add(TaxDebtItem(statement_id=st.id, numero_documento="CART-99", ente_categoria="erariale", totale_residuo=75000.0, importo_sospeso=25000.0, totale_residuo_netto=50000.0))
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Gamma", category="rischi_a_scadenza", reference_month="2026-10", accordato=120000.0, utilizzato=100000.0))
    db_session.add(GuaranteeGiven(case_id=case.id, intermediary="Banca Gamma", guaranteed_subject="Terzo S.r.l.", valore_garanzia=45000.0, status="attiva"))
    db_session.commit()

    _, _, _, matrix = _run_real_pipeline(db_session, case)
    dp = matrix["profile_snapshot"]["debt_perimeter"]
    assert dp["massa_debitoria_documentata_eur"] == 260000.0
    assert dp["esposizioni_finanziarie_per_cassa_eur"] == 100000.0
    assert dp["debiti_complessivi_anche_non_scaduti_eur"] == 260000.0
    assert dp["passivita_contestate_eur"] == 25000.0
    assert dp["garanzie_non_escusse_eur"] == 45000.0
    assert dp["importi_non_riconciliati"]["has_unreconciled_amounts"] is False
    assert dp["debiti_complessivi_ricostruzione_affidabile"] is True

    # Caso B: solo esposizioni per cassa (AdER + CR <= 500k) senza bilancio debiti complessivi non scaduti -> MAI impresa_minore verificata
    case_only_cash, comp_oc = _create_case(db_session, name="Mu Individuale", legal_form="Ditta individuale", company_type="individuale")
    for yr in ("2024", "2025", "2026"):
        _add_fs(db_session, comp_oc, year=yr, attivo=None, ricavi=120000.0, debiti=None, include_sp=False, statement_type="contabilita_semplificata")
    db_session.add(CreditExposure(case_id=case_only_cash.id, intermediary="Banca Delta", category="rischi_autoliquidanti", reference_month="2026-10", accordato=60000.0, utilizzato=50000.0))
    db_session.commit()

    _, _, _, matrix_oc = _run_real_pipeline(db_session, case_only_cash)
    assert matrix_oc["profile_snapshot"]["debt_perimeter"]["debiti_complessivi_ricostruzione_affidabile"] is False
    assert next(s for s in matrix_oc["schede_valutazione"] if s["rule_code"] == "CCII-DIM-01")["deterministic_outcome"] == "NON_DETERMINABILE"
