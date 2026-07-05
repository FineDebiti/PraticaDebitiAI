"""Seed di una pratica DIMOSTRATIVA con scenario SANO (dati fittizi).

Contrasto con le pratiche critiche: reddito solido, patrimonio che copre il
debito (Debito/patrimonio < 1), nessuna sofferenza nè procedura attiva, indici
di bilancio verdi. Popola tutte le sezioni via ORM.

Idempotente: rimuove e ricrea la pratica con lo stesso `code`.
"""
from app.db import SessionLocal
from app.models import (
    Organization, Case, Debtor, RealEstate, Vehicle,
    Company, CompanyMember, FinancialStatement, FinancialIndicator,
    CreditExposure, GuaranteeGiven, CreditReportSummary,
    TaxDebtStatement, TaxDebtItem, Creditor, DebtPosition,
)

DEMO_CODE = "DEMO-0003"
CF = "FRRLNE80A41F205D"   # formato persona fisica (16 char) — fittizio
PIVA = "11223344556"      # P.IVA studio (11 cifre) — fittizio


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
        # PRATICA + DEBITORE (situazione economica solida, nessuna criticità)
        # ----------------------------------------------------------------
        case = Case(
            organization_id=org.id, code=DEMO_CODE,
            client_name="Elena Ferrari", client_tax_code=CF,
            status="in_lavorazione", priority="bassa",
            referent="Avv. Laura Conti",
            tags="consulenza,situazione-sostenibile",
            next_deadline="2026-10-31",
            notes="Pratica dimostrativa con scenario SANO (dati fittizi).",
        )
        db.add(case); db.flush()

        debtor = Debtor(
            case_id=case.id,
            first_name="Elena", last_name="Ferrari", tax_code=CF,
            birth_date="1980-01-01", birth_place="Milano (MI)",
            residence="Viale Certosa 145, 20151 Milano (MI)",
            domicile="Viale Certosa 145, 20151 Milano (MI)",
            phone="+39 335 7766554", email="elena.ferrari@example.it",
            pec="elena.ferrari@pec.example.it",
            marital_status="coniugata", profession="Dottore commercialista",
            employer="Studio Ferrari & Associati", client_type="privato",
            household_composition="Coniuge (reddito proprio) + 1 figlio",
            dependents=1,
            monthly_net_income=5500.0, annual_income=71500.0,
            income_sources="Reddito da lavoro autonomo (studio professionale)",
            monthly_expenses=2000.0, rent_or_mortgage=700.0,
            bank_accounts="C/C Intesa Sanpaolo IT11A..., deposito titoli",
            has_ongoing_garnishment=False,
            has_salary_assignment=False,
            has_payment_delegation=False,
            notes="Nessuna procedura esecutiva in corso. Posizione regolare.",
        )
        db.add(debtor); db.flush()

        # ----------------------------------------------------------------
        # IMMOBILI (prima casa libera + immobile da reddito, senza ipoteche)
        # ----------------------------------------------------------------
        db.add_all([
            RealEstate(
                case_id=case.id, kind="Fabbricato abitativo", category="A/2",
                address="Viale Certosa 145, 20151 Milano (MI)",
                cadastral_data="Milano, Fg. 120, Part. 55, Sub. 8",
                ownership_share="1/1", ownership_right="Proprietà",
                surface_mq=110.0, cadastral_income=1100.0,
                cadastral_value=210000.0, commercial_value=420000.0,
                is_primary_residence=True, has_mortgage=False,
                provenance="Acquisto 2015 (mutuo quasi estinto)", source="manuale",
                notes="Abitazione principale, mutuo residuo modesto."),
            RealEstate(
                case_id=case.id, kind="Fabbricato abitativo", category="A/3",
                address="Via Mazzini 22, 20066 Melzo (MI)",
                cadastral_data="Melzo, Fg. 9, Part. 210, Sub. 3",
                ownership_share="1/1", ownership_right="Proprietà",
                surface_mq=75.0, cadastral_income=620.0,
                cadastral_value=98000.0, commercial_value=185000.0,
                is_primary_residence=False, has_mortgage=False,
                provenance="Acquisto 2019", source="manuale",
                notes="Immobile locato (rendita da affitto)."),
        ])

        # ----------------------------------------------------------------
        # VEICOLI
        # ----------------------------------------------------------------
        db.add(Vehicle(case_id=case.id, kind="auto", plate="GK789LM",
                       make_model="Volvo XC60 Recharge", year="2022",
                       estimated_value=38000.0, source="manuale"))

        # ----------------------------------------------------------------
        # AZIENDA / STUDIO (S.r.l.) — bilancio in salute, indici verdi
        # ----------------------------------------------------------------
        company = Company(
            case_id=case.id, role="cliente",
            name="Ferrari & Associati S.r.l. STP",
            legal_form="S.r.l.", company_type="capitali",
            tax_code=PIVA, vat=PIVA, rea="MI-2233445",
            cciaa="Milano Monza Brianza Lodi", pec="ferrariassociati@pec.example.it",
            legal_address="Viale Certosa 145, 20151 Milano (MI)",
            status="attiva", constitution_date="2016-01-15",
            capital=30000.0,
            ateco="69.20.11 — Servizi di consulenza contabile e tributaria",
            fatturato=480000.0, dipendenti=4, patrimonio_netto=220000.0,
            anno_bilancio="2024",
            business_summary="Studio professionale (STP). Bilancio solido, nessun debito finanziario rilevante.",
        )
        db.add(company); db.flush()

        db.add_all([
            CompanyMember(company_id=company.id, name="Elena Ferrari", tax_code=CF,
                          is_client=True, roles="Amministratore Unico", is_legal_rep=True,
                          quota_value=21000.0, quota_percent=70.0),
            CompanyMember(company_id=company.id, name="Paolo Neri", tax_code="NREPLA78T20F205Q",
                          is_client=False, roles="Socio", is_legal_rep=False,
                          quota_value=9000.0, quota_percent=30.0),
        ])

        fs = FinancialStatement(
            company_id=company.id, case_id=case.id,
            fiscal_year_end="2024-12-31", statement_type="abbreviato", ateco="69.20.11",
            total_assets=300000.0, equity=220000.0, total_debts=60000.0,
            revenues=480000.0, net_result=65000.0,
            debts_secured=False, privileged_debts=0.0,
            llm_provider="stub", llm_model="demo", crosscheck_status="not_run",
            raw_extraction={"nota": "Dati di bilancio dimostrativi (fittizi)."})
        db.add(fs); db.flush()

        db.add_all([
            FinancialIndicator(statement_id=fs.id, code="current_ratio", label="Current ratio",
                               group="liquidità", value_cur=2.4, value_prev=2.1, fmt="ratio",
                               trend="up", status="green", note="Ampia copertura del passivo corrente."),
            FinancialIndicator(statement_id=fs.id, code="roe", label="ROE", group="redditività",
                               value_cur=29.5, value_prev=24.0, fmt="pct", trend="up", status="green"),
            FinancialIndicator(statement_id=fs.id, code="ros", label="ROS", group="redditività",
                               value_cur=13.5, value_prev=11.8, fmt="pct", trend="up", status="green"),
            FinancialIndicator(statement_id=fs.id, code="leverage", label="Leva finanziaria",
                               group="struttura", value_cur=1.36, value_prev=1.45, fmt="ratio",
                               trend="up", status="green", note="Bassa dipendenza dal debito."),
            FinancialIndicator(statement_id=fs.id, code="debt_equity", label="Debiti / patrimonio netto",
                               group="struttura", value_cur=0.27, value_prev=0.34, fmt="ratio",
                               trend="up", status="green"),
        ])

        # ----------------------------------------------------------------
        # CENTRALE RISCHI — esposizione contenuta, tutto regolare
        # ----------------------------------------------------------------
        db.add_all([
            CreditExposure(case_id=case.id, intermediary="Intesa Sanpaolo S.p.A.",
                           category="Mutuo ipotecario (rischi a scadenza)", accordato=150000.0,
                           utilizzato=42000.0, importo_garantito=0.0,
                           status="regolare", is_critical=False, reference_month="2025-08"),
            CreditExposure(case_id=case.id, intermediary="American Express",
                           category="Carta di credito", accordato=15000.0,
                           utilizzato=2300.0, importo_garantito=0.0,
                           status="regolare", is_critical=False, reference_month="2025-08"),
        ])
        db.add(CreditReportSummary(
            case_id=case.id, period_from="2024-01", period_to="2025-08",
            most_recent_month="2025-08", num_intermediaries=2,
            total_exposure=44300.0, total_guarantees=0.0,
            has_sofferenze=False, has_criticita=False, criticita=[],
            llm_provider="stub", llm_model="demo", crosscheck_status="not_run"))

        # ----------------------------------------------------------------
        # ESTRATTO DI RUOLO AER — una sola cartella, rateizzata e sotto controllo
        # ----------------------------------------------------------------
        items = [
            dict(numero_documento="2024/0123987", tipo_documento="Cartella di pagamento",
                 ente_creditore="Agenzia delle Entrate", ente_categoria="erariale",
                 data_notifica="2024-05-10", carico_affidato=4800.0, gia_pagato=800.0,
                 residuo_carico=4000.0, interessi_mora=150.0, oneri_diritti=50.0,
                 totale_residuo=4200.0, totale_residuo_netto=4000.0,
                 proc_attive=False, rateizzato=True, def_agevolata=False),
        ]
        stmt = TaxDebtStatement(
            case_id=case.id, owner_kind="person", debtor_id=debtor.id,
            codice_fiscale=CF, denominazione="Elena Ferrari", data_elaborazione="2025-09-30",
            total_residuo=round(sum(i["totale_residuo"] for i in items), 2),
            total_residuo_netto=round(sum(i["totale_residuo_netto"] for i in items), 2),
            total_carico_affidato=round(sum(i["carico_affidato"] for i in items), 2),
            count_proc_attive=0, quadrature_ok=True, extraction_method="parser",
            raw_extraction={"nota": "Estratto di ruolo dimostrativo (fittizio)."})
        db.add(stmt); db.flush()
        for it in items:
            db.add(TaxDebtItem(statement_id=stmt.id, **it))

        # ----------------------------------------------------------------
        # POSIZIONI DEBITORIE — poche, tutte regolari
        # ----------------------------------------------------------------
        db.add_all([
            Creditor(case_id=case.id, name="Intesa Sanpaolo S.p.A.", kind="banca"),
            Creditor(case_id=case.id, name="Agenzia Entrate Riscossione", kind="erario"),
        ])
        db.add_all([
            DebtPosition(case_id=case.id, creditor_name="Intesa Sanpaolo S.p.A.",
                         debt_type="Mutuo ipotecario prima casa", original_amount=150000.0,
                         residual_amount=42000.0, overdue_amount=0.0,
                         monthly_installment=700.0, status="regolare",
                         confidence=0.97, validated=True),
            DebtPosition(case_id=case.id, creditor_name="Agenzia Entrate Riscossione",
                         debt_type="Debito erariale (AER) — rateizzato", original_amount=4800.0,
                         residual_amount=4000.0, overdue_amount=0.0,
                         monthly_installment=120.0, status="in regola con il piano",
                         confidence=1.0, validated=True),
        ])

        db.commit()
        print("OK pratica demo SANA creata:")
        print("  case_id =", case.id)
        print("  code    =", case.code)
        print("  cliente =", case.client_name, "/", case.client_tax_code)
    finally:
        db.close()


if __name__ == "__main__":
    run()
