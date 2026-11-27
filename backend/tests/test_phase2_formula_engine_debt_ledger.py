"""Test di accettazione Fase 2 — Formula Engine consolidato, DebtLedger, Protocolli A/B e fix bug."""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models.entities import (
    Case,
    Company,
    CreditExposure,
    CreditReportSummary,
    DebtPosition,
    Debtor,
    Document,
    Extraction,
    FieldEdit,
    FinancialStatement,
    GuaranteeGiven,
    RealEstate,
    TaxDebtItem,
    TaxDebtStatement,
    Vehicle,
)
from app.services.case_indicators import compute_case_indicators
from app.services.forensic_audit_engine import build_complete_technical_dossier
from app.services.indicators import compute_indicators
from app.services.preanalysis_report import build_preanalysis_report
from app.services.protocols import (
    build_debt_ledger,
    classify_case_dimensions,
    get_deterministic_analysis,
)
from app.services.protocols.formula_engine import run_formula_engine
from app.services.statutory_knowledge import calculate_ebitda_oic12, calculate_pfn_esma


def _mk_case(db_session, *, code="F2-TEST", client_name="Azienda Fase 2", tax_code="01234567890"):
    case = Case(code=code, client_name=client_name, client_tax_code=tax_code, status="nuova")
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)
    return case


def _mk_company(db_session, case, *, name="Alfa Beta", legal_form="S.r.l.", company_type="capitali"):
    comp = Company(
        case_id=case.id,
        role="cliente",
        name=name,
        legal_form=legal_form,
        company_type=company_type,
        vat="01234567890",
        rea="PA-111222",
        constitution_date="2018-03-01",
    )
    db_session.add(comp)
    db_session.commit()
    db_session.refresh(comp)
    return comp


def test_formula_engine_unitarie_ebitda_ebit_sp_ccn_pfn_variazioni():
    """Verifica formule EBITDA CNDCEC 2024 (con B10d/B12/B13 visibili) e PFN ESMA pura vs gestionale."""
    ce = {
        "valore_produzione": 600000.0,
        "ricavi_vendite": 580000.0,
        "costi_produzione": 530000.0,  # A - B = 70.000 (EBIT)
        "ammortamento_immateriali": 8000.0,   # B10a
        "ammortamento_materiali": 22000.0,    # B10b
        "svalutazioni_immobilizzazioni": 5000.0,  # B10c
        "svalutazione_crediti": 6000.0,       # B10d (visibile, NON sommato ad EBITDA)
        "accantonamenti_rischi": 4000.0,      # B12 (visibile, NON sommato ad EBITDA)
        "altri_accantonamenti": 2500.0,       # B13 (visibile, NON sommato ad EBITDA)
    }
    eb = calculate_ebitda_oic12(ce)
    assert eb["ebit_differenza_a_b"] == 70000.0
    assert eb["ammortamenti_b10a_b10b_b10c"] == 35000.0
    assert eb["ebitda_standard"] == 105000.0  # 70k + 35k (esclude B10d/B12/B13)
    assert eb["svalutazione_crediti_b10d"] == 6000.0
    assert eb["accantonamenti_rischi_b12"] == 4000.0
    assert eb["altri_accantonamenti_b13"] == 2500.0
    raccordo = eb["raccordo_bilancio"]["voci_visibili_non_neutralizzate"]
    assert raccordo["B10d_svalutazione_crediti"] == 6000.0
    assert raccordo["B12_accantonamenti_rischi"] == 4000.0
    assert raccordo["B13_altri_accantonamenti"] == 2500.0

    pfn = calculate_pfn_esma(
        debiti_bancari_breve=40000.0,
        debiti_bancari_medio_lungo=110000.0,
        disponibilita_liquide=25000.0,
        tfr_fondo=20000.0,
        finanziamenti_soci=15000.0,
        debiti_tributari_scaduti=30000.0,
        debiti_fornitori_scaduti_90gg=5000.0,
    )
    assert pfn["pfn_finanziaria_pura_esma"] == 125000.0  # (40k + 110k) - 25k
    assert pfn["pfn_gestionale_con_debt_like"] == 195000.0  # 125k + 70k debt-like
    assert pfn["pfn_totale"] == 195000.0
    assert pfn["riconciliazione_pfn"]["delta_riconciliazione"] == 70000.0


def test_debt_ledger_7_buckets_separazione_cassa_firma_documentate_riferite(db_session):
    """DebtLedger: 7 categorie, anti-duplicazione, cassa vs firma e documentate vs riferite."""
    case = _mk_case(db_session, code="DL-7B", client_name="Multi Debiti")

    # 1. AdER duplicato sullo stesso CF (solo il più recente deve contare) + cartelle estinta, sospesa, rateizzata, attiva
    st_old = TaxDebtStatement(
        case_id=case.id, codice_fiscale="01234567890", owner_kind="company",
        data_elaborazione="2025-01-01", total_residuo=99000.0, total_residuo_netto=99000.0,
    )
    st_new = TaxDebtStatement(
        case_id=case.id, codice_fiscale="01234567890", owner_kind="company",
        data_elaborazione="2026-03-01", total_residuo=50000.0, total_residuo_netto=35000.0,
    )
    db_session.add_all([st_old, st_new])
    db_session.flush()
    db_session.add_all([
        TaxDebtItem(statement_id=st_new.id, numero_documento="C-ATT", ente_creditore="AdE",
                    ente_categoria="erariale", totale_residuo=20000.0, importo_sospeso=0.0, totale_residuo_netto=20000.0),
        TaxDebtItem(statement_id=st_new.id, numero_documento="C-SOSP", ente_creditore="AdE",
                    ente_categoria="erariale", totale_residuo=15000.0, importo_sospeso=15000.0, totale_residuo_netto=0.0),
        TaxDebtItem(statement_id=st_new.id, numero_documento="C-RATE", ente_creditore="INPS",
                    ente_categoria="previdenziale", carico_affidato=18000.0, totale_residuo=10000.0,
                    totale_residuo_netto=10000.0, rateizzato=True),
        TaxDebtItem(statement_id=st_new.id, numero_documento="C-EST", ente_creditore="Comune",
                    ente_categoria="locale", carico_affidato=5000.0, totale_residuo=0.0, totale_residuo_netto=0.0),
    ])

    # 2. Centrale Rischi: CreditExposure omogenea al 2026-02 (cassa 45k + firma 100k) + CreditReportSummary che non va sommato!
    db_session.add(CreditReportSummary(case_id=case.id, most_recent_month="2026-02", total_exposure=45000.0, total_guarantees=100000.0))
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Intesa", category="rischi a scadenza Contr. FIDO-88",
                                  accordato=60000.0, utilizzato=45000.0, reference_month="2026-02"))
    db_session.add(CreditExposure(case_id=case.id, intermediary="Banca Intesa", category="rischi di firma / fideiussioni",
                                  accordato=100000.0, utilizzato=100000.0, reference_month="2026-02"))

    # 3. DebtPosition con riferimenti contrattuali univoci per la deduplicazione deterministica
    db_session.add_all([
        DebtPosition(case_id=case.id, creditor_name="AMCO S.p.A. (cessionaria)", debt_type="finanziamento ceduto Contr. MT-2021-100",
                     residual_amount=30000.0, status="attivo", source_document_id="doc-amco", validated=True),
        DebtPosition(case_id=case.id, creditor_name="Banca Cedente Originaria", debt_type="mutuo bancario Contr. MT-2021-100",
                     residual_amount=30000.0, status="attivo", source_document_id="doc-orig", validated=True),
        DebtPosition(case_id=case.id, creditor_name="Banca Intesa", debt_type="finanziamento CR Contr. FIDO-88",
                     residual_amount=45000.0, status="attivo", source_document_id="doc-cr", validated=True),
        DebtPosition(case_id=case.id, creditor_name="Fornitore Alfa", debt_type="decreto opposto",
                     residual_amount=12000.0, status="contestato", source_document_id="", validated=False),
        DebtPosition(case_id=case.id, creditor_name="Fornitore Beta", debt_type="fatture commerciali",
                     residual_amount=8000.0, status="attivo", source_document_id="", validated=False),  # riferita!
        DebtPosition(case_id=case.id, creditor_name="Finanziaria Gamma", debt_type="prestito",
                     residual_amount=0.0, status="estinto", source_document_id="doc-est", validated=True),
    ])
    db_session.commit()

    ledger = build_debt_ledger(db_session, case)
    assert ledger["stato_dato"] == "VERIFICATO"
    bt = ledger["bucket_totals"]
    assert bt["tributari_contributivi"] == 20000.0  # C-ATT (C-RATE in piani, C-SOSP in contestate, C-EST 0)
    assert bt["bancari_finanziari"] == 45000.0      # Banca Intesa (no somma con Summary o DebtPosition duplicata)
    assert bt["fornitori_dipendenti"] == 8000.0     # Fornitore Beta (riferita)
    assert bt["coobbligazioni_garanzie"] == 100000.0  # rischi di firma
    assert bt["contestate_eventuali_non_quantificate"] == 27000.0  # 15k AdER sospeso + 12k contestato
    assert bt["cessioni_credito"] == 30000.0        # AMCO (cedente 30k deduplicato!)

    totals = ledger["totals"]
    # Cassa certa = 20k (trib) + 10k (rateizzato piano) + 45k (banca) + 30k (AMCO) + 8k (fornitore Beta) = 113.000
    assert totals["esposizioni_per_cassa_certe"] == 113000.0
    assert totals["esposizioni_di_firma_e_garanzie"] == 100000.0
    assert totals["posizioni_contestate_sospese"] == 27000.0
    assert totals["piani_pagamento_residui"] == 10000.0
    assert totals["posizioni_documentate_cassa"] == 105000.0
    assert totals["posizioni_riferite_cassa"] == 8000.0
    assert len(ledger["deduplication_log"]) >= 3


def test_impresa_individuale_ordinaria_vs_semplificata_protocollo_a(db_session):
    """Protocollo A adatta il calcolo al regime: in semplificata NON inventa SP/PN/CCN/PFN."""
    # A1: Impresa individuale in contabilità ordinaria (2 esercizi con SP+CE)
    c_ord = _mk_case(db_session, code="IND-ORD", client_name="Ditta Ordinaria")
    db_session.add(Debtor(case_id=c_ord.id, client_type="ditta_individuale", monthly_net_income=2200.0, monthly_expenses=900.0))
    db_session.add(RealEstate(case_id=c_ord.id, kind="Abitazione", cadastral_value=140000.0))
    db_session.add(Vehicle(case_id=c_ord.id, make_model="Furgone", estimated_value=12000.0))
    comp_ord = _mk_company(db_session, c_ord, name="Ditta Ord", legal_form="Impresa individuale", company_type="individuale")
    db_session.add_all([
        FinancialStatement(
            company_id=comp_ord.id, fiscal_year_end="2024-12-31", statement_type="ordinario",
            total_assets=200000.0, equity=40000.0, total_debts=150000.0, revenues=180000.0, net_result=12000.0,
            raw_extraction={
                "conto_economico": {"valore_produzione": 180000.0, "ricavi_vendite": 180000.0, "costi_produzione": 160000.0, "ammortamento_materiali": 10000.0, "utile_perdita": 12000.0},
                "stato_patrimoniale": {"totale_attivo": 200000.0, "patrimonio_netto": 40000.0, "fondi_rischi": 0.0, "tfr": 10000.0, "debiti_totali": 150000.0, "ratei_risconti_passivi": 0.0,
                                       "disponibilita_liquide": 15000.0, "rimanenze": 20000.0, "crediti_clienti": 45000.0, "debiti_fornitori": 35000.0},
                "debiti_per_natura": {"banche": {"importo": 80000.0}, "fornitori": {"importo": 35000.0}},
            },
        ),
        FinancialStatement(
            company_id=comp_ord.id, fiscal_year_end="2025-12-31", statement_type="ordinario",
            total_assets=210000.0, equity=45000.0, total_debts=155000.0, revenues=200000.0, net_result=15000.0,
            raw_extraction={
                "conto_economico": {"valore_produzione": 200000.0, "ricavi_vendite": 200000.0, "costi_produzione": 175000.0, "ammortamento_materiali": 12000.0, "utile_perdita": 15000.0},
                "stato_patrimoniale": {"totale_attivo": 210000.0, "patrimonio_netto": 45000.0, "fondi_rischi": 0.0, "tfr": 10000.0, "debiti_totali": 155000.0, "ratei_risconti_passivi": 0.0,
                                       "disponibilita_liquide": 20000.0, "rimanenze": 25000.0, "crediti_clienti": 50000.0, "debiti_fornitori": 40000.0},
                "debiti_per_natura": {"banche": {"importo": 75000.0}, "fornitori": {"importo": 40000.0}},
            },
        ),
    ])
    db_session.commit()

    out_ord = get_deterministic_analysis(db_session, c_ord.id)
    fe_ord = out_ord["formula_engine"]
    assert fe_ord["protocol_view"]["protocol"] == "A"
    p_2025 = fe_ord["annual_periods"][-1]
    assert p_2025["ebit"]["value"] == 25000.0
    assert p_2025["ebitda"]["value"] == 37000.0
    assert p_2025["quadratura_sp"]["validation_status"] == "VERIFICATO"
    assert p_2025["ccn_operativo"]["value"] == 35000.0  # 25k + 50k - 40k
    assert p_2025["pfn_finanziaria_gestionale"]["value"] == 55000.0  # PFN gestionale semplificata (dataset ESMA incompleto)
    assert p_2025["pfn_esma"]["value"] is None  # ESMA completo non dichiarato (mancano leasing/comm.nc/mezzi eq.)
    assert p_2025["pfn_gestionale"]["value"] == 65000.0  # 55k + 10k TFR
    assert fe_ord["triennial_variations"]["series"]["ricavi_a1"]["period_span"]["delta_eur"] == 20000.0
    assert fe_ord["protocol_view"]["patrimonio_e_capacita_imprenditore"]["immobili_valore_catastale"] == 140000.0

    # A2: Impresa individuale in contabilità semplificata -> SP/PN/CCN/PFN restano strictly None!
    c_sempl = _mk_case(db_session, code="IND-SEMPL", client_name="Ditta Semplificata")
    db_session.add(Debtor(case_id=c_sempl.id, client_type="ditta_individuale"))
    comp_s = _mk_company(db_session, c_sempl, name="Ditta Sempl", legal_form="Impresa individuale", company_type="individuale")
    doc_rg = Document(case_id=c_sempl.id, original_filename="redditi_2025.pdf", storage_path="/tmp/rg25.pdf",
                      doc_type="dichiarazione_redditi", status="elaborato")
    db_session.add(doc_rg)
    db_session.flush()
    db_session.add(Extraction(
        document_id=doc_rg.id,
        raw_text="Modello Redditi PF 2025 Quadro RG regime semplificato",
        json_output={"anno": 2025, "regime_contabile": "semplificata", "ricavi": 145000.0},
    ))
    db_session.add(FinancialStatement(
        company_id=comp_s.id, fiscal_year_end="2025-12-31", statement_type="semplificato_rg",
        revenues=145000.0, net_result=18000.0,
        raw_extraction={"conto_economico": {"valore_produzione": 145000.0, "ricavi_vendite": 145000.0, "costi_produzione": 127000.0, "utile_perdita": 18000.0}},
    ))
    db_session.commit()

    out_sempl = get_deterministic_analysis(db_session, c_sempl.id)
    fe_sempl = out_sempl["formula_engine"]
    assert fe_sempl["protocol_view"]["protocol"] == "A"
    assert fe_sempl["protocol_view"]["economia_attivita"]["metodo_ricostruzione"] == "CONTABILITA_SEMPLIFICATA_SENZA_SP"
    p_s = fe_sempl["annual_periods"][0]
    assert p_s["ebitda"]["value"] == 18000.0
    assert p_s["patrimonio_netto"]["value"] is None
    assert p_s["patrimonio_netto"]["validation_status"] == "NON_VERIFICABILE_NULL"
    assert p_s["ccn_operativo"]["value"] is None
    assert p_s["pfn_gestionale"]["value"] is None


def test_srl_sotto_e_sopra_soglia_protocollo_b_invariante(db_session):
    """Protocollo B: S.r.l. resta società di capitali sia sotto sia sopra soglia CCII."""
    for label, rev, att, deb, expected_ccii in (
        ("SRL-SOTTO", 120000.0, 140000.0, 200000.0, "impresa_minore"),
        ("SRL-SOPRA", 420000.0, 500000.0, 750000.0, "non_minore"),
    ):
        case = _mk_case(db_session, code=label, client_name=label)
        comp = _mk_company(db_session, case, name=label, legal_form="S.r.l.", company_type="capitali")
        for yr in ("2023", "2024", "2025"):
            db_session.add(FinancialStatement(
                company_id=comp.id, fiscal_year_end=f"{yr}-12-31", statement_type="ordinario",
                total_assets=att, revenues=rev, total_debts=deb, equity=50000.0, net_result=10000.0,
                raw_extraction={
                    "conto_economico": {"valore_produzione": rev, "ricavi_vendite": rev, "costi_produzione": rev - 30000.0, "ammortamento_materiali": 10000.0, "utile_perdita": 10000.0},
                    "stato_patrimoniale": {"totale_attivo": att, "patrimonio_netto": 50000.0, "debiti_totali": deb, "disponibilita_liquide": 15000.0},
                    "debiti_per_natura": {"banche": {"importo": 90000.0}, "soci_finanziamenti": {"importo": 25000.0}, "fornitori": {"importo": deb - 115000.0}},
                },
            ))
        db_session.add(GuaranteeGiven(case_id=case.id, intermediary="Banca Alpha", guaranteed_subject=label, valore_garanzia=120000.0))
        db_session.commit()

        out = get_deterministic_analysis(db_session, case.id)
        pv = out["formula_engine"]["protocol_view"]
        assert pv["protocol"] == "B"
        assert pv["societa_capitali_srl_invariante"] is True
        assert pv["ccii_size_qualification"] == expected_ccii
        assert pv["debiti_sociali"]["finanziamenti_soci"]["importo"] == 25000.0
        assert pv["garanzie_personali_e_firma_separate"]["totale_garanzie_firma"] == 120000.0


def test_anti_duplicazione_pfn_case_indicators_quad01_e_report_senza_arbitri(db_session):
    """Verifica i fix sui bug identificati: PFN senza doppio banche+debiti_oltre,
    case_indicators senza somma tripla bilancio+AdER+CR, QUAD-01 EBIT!=EBITDA,
    preanalysis_report senza percentuali liquidatorie arbitrarie o proposte CCII preimpostate."""
    # 1. Bug fix duplicazione banche + debiti_oltre in compute_indicators (indicators.py)
    sp = {
        "disponibilita_liquide": {"corrente": 10000.0},
        "debiti_oltre": {"corrente": 100000.0},  # mutuo incluso dentro deb["banche"]!
    }
    deb = {"banche": {"importo": 100000.0}}
    inds = {i["code"]: i for i in compute_indicators(sp, {}, deb)}
    assert inds["pfn"]["value_cur"] == 90000.0  # 100k - 10k, MAI 200k - 10k = 190k!

    # 2. Bug fix case_indicators: Bilancio (banche 100k + fornitori 30k = 130k) + AdER (20k) + CR (100k)
    # Totale riconciliato: 20k (AdER) + 100k (CR) + 30k (fornitori) = 150.000 (MAI 130k + 20k + 100k = 250.000!)
    case = _mk_case(db_session, code="ANTI-DUP", client_name="Anti Duplicazione Srl")
    comp = _mk_company(db_session, case, name="AntiDup", legal_form="S.r.l.", company_type="capitali")
    db_session.add(FinancialStatement(
        case_id=case.id, company_id=comp.id, fiscal_year_end="2025-12-31", statement_type="ordinario",
        total_assets=250000.0, revenues=300000.0, total_debts=130000.0, equity=80000.0, net_result=15000.0,
        raw_extraction={
            "conto_economico": {"valore_produzione": 300000.0, "ricavi_vendite": 300000.0, "costi_produzione": 270000.0, "ammortamento_materiali": 20000.0, "utile_perdita": 15000.0},
            "stato_patrimoniale": {"totale_attivo": 250000.0, "patrimonio_netto": 80000.0, "debiti_totali": 130000.0, "debiti_oltre": 60000.0, "disponibilita_liquide": 10000.0},
            "debiti_per_natura": {"banche": {"importo": 100000.0}, "fornitori": {"importo": 30000.0}},
        },
    ))
    db_session.add(TaxDebtStatement(case_id=case.id, total_residuo=20000.0, total_residuo_netto=20000.0))
    db_session.add(CreditReportSummary(case_id=case.id, most_recent_month="2026-01", total_exposure=100000.0))
    db_session.add(RealEstate(case_id=case.id, kind="Capannone", cadastral_value=200000.0))
    db_session.add(Vehicle(case_id=case.id, make_model="Autocarro", estimated_value=30000.0))
    db_session.commit()

    ci = compute_case_indicators(db_session, case.id)
    macro = {m["code"]: m for m in ci["macro"]}
    assert macro["indebitamento_totale"]["value"] == 150000.0

    # 3. Preanalysis report + Forensic Audit QUAD-01 (distinzione EBIT vs EBITDA) & assenza moltiplicatori arbitrari
    rep = build_preanalysis_report(db_session, case.id)
    c8 = rep["capitolo_8_patrimonio"]
    assert c8["immobilizzazioni_materiali"]["costo_storico_stimato"] is None
    for lotto in c8["lotti_concorsuali"]:
        assert "0.65" not in str(lotto) and "130.000" not in str(lotto["prudente"])
        assert "Da perizia" in lotto["prudente"]
    assert rep["capitolo_9_orientamento_risanamento"]["proposta_coerente"] is None

    td = rep["technical_dossier"]
    quads = td["decimal_audit"]["quadrature"]
    ebit_quad = next(q for q in quads if "EBIT" in q["titolo"] and "EBITDA" not in q["titolo"])
    ebitda_quad = next(q for q in quads if "EBITDA / MOL" in q["titolo"])
    assert Decimal(ebit_quad["valore_calcolato_raw"]) == Decimal("30000.00")   # 300k - 270k
    assert Decimal(ebitda_quad["valore_calcolato_raw"]) == Decimal("50000.00")  # 30k + 20k


def test_api_deterministic_analysis_readonly_and_404(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        case = _mk_case(db_session, code="API-F2", client_name="Api Srl")
        _mk_company(db_session, case, legal_form="S.r.l.", company_type="capitali")

        r_ok = client.get(f"/api/cases/{case.id}/deterministic-analysis")
        assert r_ok.status_code == 200
        body = r_ok.json()
        assert body["case_id"] == case.id
        assert "debt_ledger" in body
        assert "formula_engine" in body
        assert body["debt_ledger"]["stato_dato"] == "NON_VERIFICABILE_NULL"
        assert db_session.query(FieldEdit).filter(FieldEdit.case_id == case.id).count() == 0

        r_404 = client.get("/api/cases/id-inesistente/deterministic-analysis")
        assert r_404.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# 7 TEST OBBLIGATORI DI VALIDAZIONE CONCLUSIVA FASE 2
# ==============================================================================

def test_val_1_due_debiti_distinti_pari_importo_non_eliminati(db_session):
    """1. Due debiti distinti di pari importo NON devono essere eliminati né accorpati."""
    case = _mk_case(db_session, code="VAL-1", client_name="Pari Importo")
    db_session.add_all([
        DebtPosition(case_id=case.id, creditor_name="Banca Alfa", debt_type="mutuo bancario Contr. A-101",
                     residual_amount=25000.0, status="attivo", source_document_id="doc-1", validated=True),
        DebtPosition(case_id=case.id, creditor_name="Finanziaria Beta", debt_type="finanziamento Contr. B-202",
                     residual_amount=25000.0, status="attivo", source_document_id="doc-2", validated=True),
    ])
    db_session.commit()

    ledger = build_debt_ledger(db_session, case)
    assert len(ledger["buckets"]["bancari_finanziari"]) == 2
    assert ledger["bucket_totals"]["bancari_finanziari"] == 50000.0
    assert ledger["totals"]["esposizioni_per_cassa_certe"] == 50000.0
    assert ledger["stato_dato"] == "VERIFICATO"

    # Cessione + posizione originaria di pari importo SENZA contratto condiviso -> conserva entrambe e segnala riconciliazione
    case_ces = _mk_case(db_session, code="VAL-1B", client_name="Pari Importo Cessione")
    db_session.add_all([
        DebtPosition(case_id=case_ces.id, creditor_name="SPV Alpha (cessionaria)", debt_type="credito ceduto",
                     residual_amount=30000.0, status="attivo", source_document_id="doc-c1", validated=True),
        DebtPosition(case_id=case_ces.id, creditor_name="Banca Gamma", debt_type="finanziamento chirografario",
                     residual_amount=30000.0, status="attivo", source_document_id="doc-c2", validated=True),
    ])
    db_session.commit()
    ledger_ces = build_debt_ledger(db_session, case_ces)
    assert len(ledger_ces["buckets"]["cessioni_credito"]) == 1
    assert len(ledger_ces["buckets"]["bancari_finanziari"]) == 1
    assert ledger_ces["totals"]["esposizioni_per_cassa_certe"] == 60000.0
    assert ledger_ces["stato_dato"] == "RICONCILIAZIONE_NECESSARIA"
    assert ledger_ces["riconciliazione_necessaria"] is True


def test_val_2_due_finanziamenti_stesso_istituto_non_accorpati(db_session):
    """2. Due finanziamenti dello stesso istituto non vengono accorpati; se sovrapposti con CR senza ref univoco -> RICONCILIAZIONE_NECESSARIA."""
    case = _mk_case(db_session, code="VAL-2", client_name="Stesso Istituto")
    db_session.add_all([
        DebtPosition(case_id=case.id, creditor_name="Intesa Sanpaolo", debt_type="mutuo ipotecario Contr. 1001",
                     residual_amount=80000.0, status="attivo", source_document_id="doc-m1", validated=True),
        DebtPosition(case_id=case.id, creditor_name="Intesa Sanpaolo", debt_type="fido cassa Contr. 2002",
                     residual_amount=35000.0, status="attivo", source_document_id="doc-m2", validated=True),
    ])
    db_session.commit()

    ledger = build_debt_ledger(db_session, case)
    assert len(ledger["buckets"]["bancari_finanziari"]) == 2
    assert ledger["bucket_totals"]["bancari_finanziari"] == 115000.0

    # Aggiungi CR su Intesa Sanpaolo senza riferimento contrattuale univoco: NON elimina nessuna posizione e segnala riconciliazione
    db_session.add(CreditExposure(
        case_id=case.id, intermediary="Intesa Sanpaolo", category="rischi a scadenza",
        accordato=90000.0, utilizzato=80000.0, reference_month="2026-02",
    ))
    db_session.commit()
    ledger_cr = build_debt_ledger(db_session, case)
    assert len(ledger_cr["buckets"]["bancari_finanziari"]) == 3
    assert ledger_cr["totals"]["esposizioni_per_cassa_certe"] == 195000.0
    assert ledger_cr["stato_dato"] == "RICONCILIAZIONE_NECESSARIA"
    assert any("Intesa Sanpaolo" in r["message"] for r in ledger_cr["reconciliation_required"])


def test_val_3_debiti_tributari_non_ader_non_cancellati(db_session):
    """3. Debiti tributari non affidati alla riscossione (AdER) restano conservati accanto agli estratti AdER."""
    case = _mk_case(db_session, code="VAL-3", client_name="Tributi Misti")
    st = TaxDebtStatement(case_id=case.id, codice_fiscale="01234567890", owner_kind="company",
                          data_elaborazione="2026-02-01", total_residuo=40000.0, total_residuo_netto=40000.0)
    db_session.add(st)
    db_session.flush()
    db_session.add(TaxDebtItem(statement_id=st.id, numero_documento="07920240001234567",
                               ente_creditore="Agenzia Entrate", totale_residuo=40000.0, totale_residuo_netto=40000.0))
    db_session.add(DebtPosition(
        case_id=case.id,
        creditor_name="Agenzia delle Entrate",
        debt_type="Avviso bonario IVA F24 corrente non affidato a riscossione",
        residual_amount=15000.0,
        status="attivo",
        source_document_id="doc-f24",
        validated=True,
    ))
    db_session.commit()

    ledger = build_debt_ledger(db_session, case)
    assert len(ledger["buckets"]["tributari_contributivi"]) == 2
    assert ledger["bucket_totals"]["tributari_contributivi"] == 55000.0
    assert ledger["totals"]["esposizioni_per_cassa_certe"] == 55000.0
    assert ledger["stato_dato"] == "VERIFICATO"


def test_val_4_due_mensilita_cr_non_sommate_e_periodo_mancante_non_verificabile(db_session):
    """4. Due mensilità CR non vengono mai sommate; se manca periodo attendibile -> totale non verificabile."""
    case = _mk_case(db_session, code="VAL-4", client_name="CR Temporale")
    db_session.add_all([
        CreditExposure(case_id=case.id, intermediary="Banca Alpha", category="rischi a revoca",
                       accordato=100000.0, utilizzato=60000.0, reference_month="2025-11"),
        CreditExposure(case_id=case.id, intermediary="Banca Alpha", category="rischi a revoca",
                       accordato=100000.0, utilizzato=75000.0, reference_month="2026-02"),
        CreditExposure(case_id=case.id, intermediary="Banca Alpha", category="rischi di firma",
                       accordato=50000.0, utilizzato=50000.0, reference_month="2026-02"),
    ])
    db_session.commit()

    ledger = build_debt_ledger(db_session, case)
    assert ledger["cr_reference_period"] == "2026-02"
    assert ledger["cr_temporal_status"] == "OMOGENEO_ULTIMA_MENSILITA"
    assert ledger["cr_superseded_periods"] == ["2025-11"]
    assert ledger["cr_breakdown"]["cassa_effettiva"] == 75000.0
    assert ledger["cr_breakdown"]["rischi_di_firma"] == 50000.0
    assert ledger["cr_breakdown"]["accordato_inutilizzato"] == 25000.0
    assert ledger["totals"]["esposizioni_per_cassa_certe"] == 75000.0  # MAI 60k + 75k = 135k!

    # Caso senza alcun periodo CR attendibile -> totale CR NON VERIFICABILE + indicazione fonti da acquisire
    case_nd = _mk_case(db_session, code="VAL-4B", client_name="CR Senza Periodo")
    db_session.add(CreditExposure(case_id=case_nd.id, intermediary="Banca Alpha", category="rischi a scadenza",
                                  accordato=80000.0, utilizzato=50000.0, reference_month=""))
    db_session.commit()

    ledger_nd = build_debt_ledger(db_session, case_nd)
    assert ledger_nd["cr_temporal_status"] == "PERIODO_NON_ATTENDIBILE"
    assert ledger_nd["cr_reference_period"] is None
    assert ledger_nd["stato_dato"] == "NON_VERIFICABILE_NULL"
    assert ledger_nd["totals"]["esposizioni_per_cassa_certe"] is None
    assert len(ledger_nd["missing_sources_to_acquire"]) >= 1


def test_val_5_b10_generico_senza_dettaglio_non_genera_ebitda_verificato(db_session):
    """5. Aggregato B10 senza dettaglio B10a/b/c (e senza B10d) NON genera EBITDA verificato."""
    ce_gen = {
        "valore_produzione": 400000.0,
        "ricavi_vendite": 395000.0,
        "costi_produzione": 350000.0,
        "ammortamenti": 25000.0,  # Solo B10 generico!
    }
    eb_res = calculate_ebitda_oic12(ce_gen)
    assert eb_res["b10_dettaglio_disponibile"] is False
    assert eb_res["b10_aggregato_usato"] is True
    assert eb_res["b10d_escludibile"] is False
    assert eb_res["stato_dato"] == "PARZIALE_B10_NON_DISAGGREGATO"
    assert eb_res["raccordo_bilancio"]["EBITDA_ordinario_CNDCEC_2024"] is None

    case = _mk_case(db_session, code="VAL-5", client_name="Solo B10")
    comp = _mk_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    db_session.add(FinancialStatement(
        case_id=case.id, company_id=comp.id, fiscal_year_end="2025-12-31", statement_type="ordinario",
        total_assets=300000.0, revenues=395000.0, total_debts=200000.0, equity=80000.0,
        raw_extraction={"conto_economico": ce_gen},
    ))
    db_session.commit()

    out = get_deterministic_analysis(db_session, case.id)
    eb_rec = out["formula_engine"]["annual_periods"][0]["ebitda"]
    assert eb_rec["validation_status"] == "NON_VERIFICABILE_NULL"
    assert eb_rec["value"] is None
    assert eb_rec["inputs"]["B10_aggregato_non_disaggregato"] == 25000.0


def test_val_6_pfn_esma_distinta_da_pfn_gestionale_su_dataset_incompleto(db_session):
    """6. Su dataset ESMA incompleto PFN_ESMA_CONFORME resta NULL e viene distinta da PFN_GESTIONALE_SEMPLIFICATA;
    nessuna duplicazione dei finanziamenti soci."""
    # Verifica anti-duplicazione finanziamenti soci in statutory_knowledge
    pfn_soci = calculate_pfn_esma(
        debiti_bancari_breve=20000.0,
        debiti_bancari_medio_lungo=80000.0,
        disponibilita_liquide=10000.0,
        finanziamenti_soci=50000.0,
        finanziamenti_soci_in_debito_finanziario=True,
    )
    assert pfn_soci["pfn_finanziaria_gestionale_semplificata"] == 140000.0  # 20k + 80k + 50k - 10k
    assert pfn_soci["debt_like_items"]["finanziamenti_soci"] == 0.0  # NON contato due volte!
    assert pfn_soci["pfn_gestionale_con_debt_like"] == 140000.0

    # Formula engine con dataset SP incompleto (manca leasing/comm. non correnti/mezzi equivalenti)
    case = _mk_case(db_session, code="VAL-6", client_name="PFN Semplificata")
    comp = _mk_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    db_session.add(FinancialStatement(
        case_id=case.id, company_id=comp.id, fiscal_year_end="2025-12-31", statement_type="ordinario",
        total_assets=200000.0, revenues=180000.0, total_debts=120000.0, equity=50000.0,
        raw_extraction={
            "stato_patrimoniale": {"disponibilita_liquide": 15000.0, "tfr": 10000.0},
            "debiti_per_natura": {"banche": {"importo": 70000.0}},
        },
    ))
    db_session.commit()

    out = get_deterministic_analysis(db_session, case.id)
    p0 = out["formula_engine"]["annual_periods"][0]
    assert p0["pfn_esma"]["code"] == "PFN_ESMA_CONFORME"
    assert p0["pfn_esma"]["validation_status"] == "NON_VERIFICABILE_NULL"
    assert p0["pfn_esma"]["value"] is None
    assert p0["pfn_finanziaria_gestionale"]["code"] == "PFN_GESTIONALE_SEMPLIFICATA"
    assert p0["pfn_finanziaria_gestionale"]["value"] == 55000.0
    assert p0["pfn_finanziaria_gestionale"]["validation_status"] == "PARZIALE_CON_AVVISO"
    assert p0["pfn_gestionale"]["value"] == 65000.0


def test_val_7_sp_componenti_mancanti_non_diventano_zero(db_session):
    """7. Componenti SP mancanti (fondi_rischi, tfr, ratei_risconti_passivi) NON diventano 0.0;
    verifica aggregata distinta dalla quadratura analitica."""
    case = _mk_case(db_session, code="VAL-7", client_name="SP NULL Check")
    comp = _mk_company(db_session, case, legal_form="S.r.l.", company_type="capitali")
    db_session.add(FinancialStatement(
        case_id=case.id, company_id=comp.id, fiscal_year_end="2025-12-31", statement_type="ordinario",
        total_assets=200000.0, revenues=150000.0, total_debts=120000.0, equity=80000.0,
        raw_extraction={
            # Totale attivo 200k e totale passivo 200k quadrano in aggregato, MA mancano fondi_rischi, tfr e ratei!
            "stato_patrimoniale": {
                "totale_attivo": 200000.0,
                "totale_passivo": 200000.0,
                "patrimonio_netto": 80000.0,
                "debiti_totali": 120000.0,
            },
        },
    ))
    db_session.commit()

    out = get_deterministic_analysis(db_session, case.id)
    p0 = out["formula_engine"]["annual_periods"][0]
    assert p0["quadratura_sp_aggregata"]["validation_status"] == "VERIFICATO"
    assert p0["quadratura_sp_aggregata"]["value"] == 0.0
    assert p0["quadratura_sp_analitica"]["validation_status"] == "NON_VERIFICABILE_NULL"
    assert p0["quadratura_sp_analitica"]["value"] is None
    assert set(p0["quadratura_sp_analitica"]["inputs"]["missing_components"]) == {
        "fondi_rischi", "tfr", "ratei_risconti_passivi",
    }
    assert p0["quadratura_sp"]["validation_status"] == "PARZIALE_CON_AVVISO"
    assert p0["quadratura_sp"]["inputs"]["verification_mode"] == "AGGREGATA_SOLO_TOTALI"

