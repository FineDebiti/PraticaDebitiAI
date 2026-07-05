"""Seed di una pratica DIMOSTRATIVA intestata a un'AZIENDA (dati fittizi).

Cliente = società di persone (S.n.c.) -> esercita anche il segnale
"responsabilità illimitata dei soci". Popola tutte le sezioni via ORM,
incluse Centrale Rischi, estratto di ruolo AER (owner_kind="company") e
bilancio d'impresa con indici.

Idempotente: rimuove e ricrea la pratica con lo stesso `code`.
"""
from app.db import SessionLocal
from app.models import (
    Organization, Case, Debtor, RealEstate, Vehicle,
    Company, CompanyMember, FinancialStatement, FinancialIndicator,
    CreditExposure, GuaranteeGiven, CreditReportSummary,
    TaxDebtStatement, TaxDebtItem, Creditor, DebtPosition,
)

DEMO_CODE = "DEMO-0002"
PIVA = "09876543210"        # formato P.IVA (11 cifre) — fittizio
DENOM = "Autotrasporti Fratelli Galli S.n.c."


def run():
    db = SessionLocal()
    try:
        # --- idempotenza ---
        for c in db.query(Case).filter_by(code=DEMO_CODE).all():
            for st in db.query(TaxDebtStatement).filter_by(case_id=c.id).all():
                db.delete(st)
            db.delete(c)
        db.commit()

        org = db.query(Organization).first()
        if not org:
            org = Organization(name="Studio Legale Demo")
            db.add(org); db.flush()

        # ----------------------------------------------------------------
        # PRATICA (azienda) + DEBITORE (client_type societa)
        # ----------------------------------------------------------------
        case = Case(
            organization_id=org.id, code=DEMO_CODE,
            client_name=DENOM, client_tax_code=PIVA,
            status="in_lavorazione", priority="alta",
            referent="Avv. Laura Conti",
            tags="impresa,sovraindebitamento,societa-di-persone",
            next_deadline="2026-09-15",
            notes="Pratica dimostrativa AZIENDA con dati fittizi per presentazione cliente.",
        )
        db.add(case); db.flush()

        debtor = Debtor(
            case_id=case.id,
            first_name="", last_name=DENOM, tax_code=PIVA,
            client_type="societa",
            residence="Via dell'Industria 24, 46100 Mantova (MN)",
            domicile="Via dell'Industria 24, 46100 Mantova (MN)",
            phone="+39 0376 998877", email="info@fratelligalli.example.it",
            pec="autotrasportigalli@pec.example.it",
            notes="Società di persone: soci illimitatamente responsabili.",
        )
        db.add(debtor); db.flush()

        # ----------------------------------------------------------------
        # AZIENDA CLIENTE (S.n.c.) + SOCI + BILANCIO + INDICI
        # ----------------------------------------------------------------
        company = Company(
            case_id=case.id, role="cliente", name=DENOM,
            legal_form="S.n.c.", company_type="persone",
            tax_code=PIVA, vat=PIVA, rea="MN-456789",
            cciaa="Mantova", pec="autotrasportigalli@pec.example.it",
            legal_address="Via dell'Industria 24, 46100 Mantova (MN)",
            status="attiva", constitution_date="2005-09-01",
            capital=20000.0,
            ateco="49.41.00 — Trasporto di merci su strada",
            fatturato=2150000.0, dipendenti=14, patrimonio_netto=95000.0,
            anno_bilancio="2024",
            business_summary="Autotrasporto merci conto terzi. Società di persone tra due fratelli.",
        )
        db.add(company); db.flush()

        db.add_all([
            CompanyMember(company_id=company.id, name="Giorgio Galli", tax_code="GLLGRG70A01E897T",
                          is_client=True, roles="Socio amministratore", is_legal_rep=True,
                          quota_value=10000.0, quota_percent=50.0),
            CompanyMember(company_id=company.id, name="Sergio Galli", tax_code="GLLSRG73M12E897P",
                          is_client=True, roles="Socio amministratore", is_legal_rep=True,
                          quota_value=10000.0, quota_percent=50.0),
        ])

        fs = FinancialStatement(
            company_id=company.id, case_id=case.id,
            fiscal_year_end="2024-12-31", statement_type="ordinario", ateco="49.41.00",
            total_assets=1480000.0, equity=95000.0, total_debts=1240000.0,
            revenues=2150000.0, net_result=-38000.0,
            debts_secured=True, privileged_debts=160000.0,
            llm_provider="stub", llm_model="demo", crosscheck_status="not_run",
            raw_extraction={"nota": "Dati di bilancio dimostrativi (fittizi)."},
        )
        db.add(fs); db.flush()

        db.add_all([
            FinancialIndicator(statement_id=fs.id, code="current_ratio", label="Current ratio",
                               group="liquidità", value_cur=0.82, value_prev=0.98, fmt="ratio",
                               trend="down", status="red",
                               note="Attivo corrente / passivo corrente: sotto 1."),
            FinancialIndicator(statement_id=fs.id, code="roe", label="ROE", group="redditività",
                               value_cur=-40.0, value_prev=8.5, fmt="pct", trend="down", status="red",
                               note="Perdita di esercizio."),
            FinancialIndicator(statement_id=fs.id, code="ros", label="ROS", group="redditività",
                               value_cur=-1.8, value_prev=2.1, fmt="pct", trend="down", status="red"),
            FinancialIndicator(statement_id=fs.id, code="leverage", label="Leva finanziaria",
                               group="struttura", value_cur=15.6, value_prev=9.2, fmt="ratio",
                               trend="down", status="red",
                               note="Totale attivo / patrimonio netto: molto elevata."),
            FinancialIndicator(statement_id=fs.id, code="debt_equity", label="Debiti / patrimonio netto",
                               group="struttura", value_cur=13.05, value_prev=7.8, fmt="ratio",
                               trend="down", status="red"),
        ])

        # ----------------------------------------------------------------
        # PATRIMONIO (capannone + automezzi)
        # ----------------------------------------------------------------
        db.add(RealEstate(
            case_id=case.id, kind="Capannone industriale", category="D/1",
            address="Via dell'Industria 24, 46100 Mantova (MN)",
            cadastral_data="Mantova, Fg. 88, Part. 410, Sub. 2",
            ownership_share="1/1", ownership_right="Proprietà",
            surface_mq=1200.0, cadastral_income=9800.0,
            cadastral_value=420000.0, commercial_value=560000.0,
            is_primary_residence=False, has_mortgage=True,
            provenance="Acquisto 2008", source="manuale",
            notes="Sede operativa, ipoteca a garanzia mutuo BPER."))

        db.add_all([
            Vehicle(case_id=case.id, kind="autocarro", plate="GA111LI",
                    make_model="IVECO Stralis 460", year="2018",
                    estimated_value=42000.0, source="manuale"),
            Vehicle(case_id=case.id, kind="autocarro", plate="GA222LI",
                    make_model="MAN TGX 18.500", year="2020",
                    estimated_value=58000.0, source="manuale"),
            Vehicle(case_id=case.id, kind="rimorchio", plate="XA333YZ",
                    make_model="Semirimorchio Schmitz", year="2019",
                    estimated_value=16000.0, source="manuale"),
        ])

        # ----------------------------------------------------------------
        # CENTRALE RISCHI
        # ----------------------------------------------------------------
        db.add_all([
            CreditExposure(case_id=case.id, intermediary="BPER Banca S.p.A.",
                           category="Mutuo ipotecario (rischi a scadenza)", accordato=350000.0,
                           utilizzato=298000.0, importo_garantito=350000.0,
                           status="in sofferenza", is_critical=True, reference_month="2025-08"),
            CreditExposure(case_id=case.id, intermediary="UniCredit S.p.A.",
                           category="Anticipo fatture (rischi autoliquidanti)", accordato=200000.0,
                           utilizzato=185000.0, importo_garantito=0.0,
                           status="sconfino", is_critical=True, reference_month="2025-08"),
            CreditExposure(case_id=case.id, intermediary="Banca Sella S.p.A.",
                           category="Leasing automezzi", accordato=120000.0,
                           utilizzato=96000.0, importo_garantito=0.0,
                           status="regolare", is_critical=False, reference_month="2025-08"),
        ])
        db.add(GuaranteeGiven(
            case_id=case.id, intermediary="BPER Banca S.p.A.",
            guaranteed_subject="Galli Immobiliare S.r.l. (collegata)",
            valore_garanzia=120000.0, importo_garantito=80000.0,
            status="attiva (fideiussione)"))

        db.add(CreditReportSummary(
            case_id=case.id, period_from="2024-01", period_to="2025-08",
            most_recent_month="2025-08", num_intermediaries=3,
            total_exposure=579000.0, total_guarantees=80000.0,
            has_sofferenze=True, has_criticita=True,
            criticita=[
                {"mese": "2025-02", "evento": "Sconfino persistente anticipo fatture UniCredit"},
                {"mese": "2025-05", "evento": "Classificazione a sofferenza mutuo BPER"},
            ],
            llm_provider="stub", llm_model="demo", crosscheck_status="not_run"))

        # ----------------------------------------------------------------
        # ESTRATTO DI RUOLO AER (owner_kind="company")
        # ----------------------------------------------------------------
        items = [
            dict(numero_documento="2021/0044556", tipo_documento="Cartella di pagamento",
                 ente_creditore="Agenzia delle Entrate", ente_categoria="erariale",
                 data_notifica="2021-04-12", carico_affidato=64000.0, gia_pagato=0.0,
                 residuo_carico=64000.0, interessi_mora=8200.0, oneri_diritti=1100.0,
                 totale_residuo=73300.0, totale_residuo_netto=64000.0,
                 proc_attive=True, rateizzato=False, def_agevolata=False),
            dict(numero_documento="2022/0066778", tipo_documento="Cartella di pagamento",
                 ente_creditore="INPS", ente_categoria="previdenziale",
                 data_notifica="2022-02-28", carico_affidato=31000.0, gia_pagato=5000.0,
                 residuo_carico=26000.0, interessi_mora=3100.0, oneri_diritti=500.0,
                 totale_residuo=29600.0, totale_residuo_netto=26000.0,
                 proc_attive=False, rateizzato=True, def_agevolata=False),
            dict(numero_documento="2023/0088990", tipo_documento="Avviso di addebito",
                 ente_creditore="INAIL", ente_categoria="previdenziale",
                 data_notifica="2023-07-19", carico_affidato=8400.0, gia_pagato=0.0,
                 residuo_carico=8400.0, interessi_mora=600.0, oneri_diritti=150.0,
                 totale_residuo=9150.0, totale_residuo_netto=8400.0,
                 proc_attive=False, rateizzato=False, def_agevolata=False),
            dict(numero_documento="2020/0022113", tipo_documento="Cartella di pagamento",
                 ente_creditore="Agenzia delle Entrate", ente_categoria="erariale",
                 data_notifica="2020-01-30", carico_affidato=22000.0, gia_pagato=0.0,
                 residuo_carico=22000.0, interessi_mora=4400.0, oneri_diritti=600.0,
                 totale_residuo=27000.0, totale_residuo_netto=22000.0,
                 proc_attive=True, rateizzato=False, def_agevolata=True),
        ]
        stmt = TaxDebtStatement(
            case_id=case.id, owner_kind="company", company_id=company.id,
            codice_fiscale=PIVA, denominazione=DENOM, data_elaborazione="2025-09-30",
            total_residuo=round(sum(i["totale_residuo"] for i in items), 2),
            total_residuo_netto=round(sum(i["totale_residuo_netto"] for i in items), 2),
            total_carico_affidato=round(sum(i["carico_affidato"] for i in items), 2),
            count_proc_attive=sum(1 for i in items if i["proc_attive"]),
            quadrature_ok=True, extraction_method="parser",
            raw_extraction={"nota": "Estratto di ruolo dimostrativo (fittizio)."})
        db.add(stmt); db.flush()
        for it in items:
            db.add(TaxDebtItem(statement_id=stmt.id, **it))

        # ----------------------------------------------------------------
        # POSIZIONI DEBITORIE
        # ----------------------------------------------------------------
        db.add_all([
            Creditor(case_id=case.id, name="BPER Banca S.p.A.", kind="banca"),
            Creditor(case_id=case.id, name="UniCredit S.p.A.", kind="banca"),
            Creditor(case_id=case.id, name="Banca Sella S.p.A.", kind="finanziaria"),
            Creditor(case_id=case.id, name="Agenzia Entrate Riscossione", kind="erario"),
        ])
        db.add_all([
            DebtPosition(case_id=case.id, creditor_name="BPER Banca S.p.A.",
                         debt_type="Mutuo ipotecario capannone", original_amount=350000.0,
                         residual_amount=298000.0, overdue_amount=24000.0,
                         monthly_installment=2100.0, status="in sofferenza",
                         confidence=0.95, validated=True),
            DebtPosition(case_id=case.id, creditor_name="UniCredit S.p.A.",
                         debt_type="Anticipo fatture", original_amount=200000.0,
                         residual_amount=185000.0, overdue_amount=185000.0,
                         monthly_installment=0.0, status="sconfino",
                         confidence=0.9, validated=True),
            DebtPosition(case_id=case.id, creditor_name="Banca Sella S.p.A.",
                         debt_type="Leasing automezzi", original_amount=120000.0,
                         residual_amount=96000.0, overdue_amount=6400.0,
                         monthly_installment=3200.0, status="in ritardo",
                         confidence=0.88, validated=False),
            DebtPosition(case_id=case.id, creditor_name="Agenzia Entrate Riscossione",
                         debt_type="Debito erariale/esattoriale (AER)", original_amount=125400.0,
                         residual_amount=120400.0, overdue_amount=120400.0,
                         monthly_installment=0.0, status="a ruolo",
                         confidence=1.0, validated=True),
        ])

        db.commit()
        print("OK pratica demo AZIENDA creata:")
        print("  case_id =", case.id)
        print("  code    =", case.code)
        print("  cliente =", case.client_name, "/", case.client_tax_code)
    finally:
        db.close()


if __name__ == "__main__":
    run()
