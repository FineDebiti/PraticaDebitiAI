"""Seed di una pratica DIMOSTRATIVA completa (dati fittizi).

Popola tutte le sezioni della scheda cliente usando direttamente l'ORM dell'app,
così da esercitare anche le sezioni senza endpoint di creazione manuale
(Centrale Rischi, estratto di ruolo AER, bilancio d'impresa + indici).

Eseguibile in modo idempotente: se esiste già una pratica con lo stesso `code`
viene prima rimossa (cascade) e ricreata.
"""
from datetime import datetime, date

from app.db import SessionLocal
from app.models import (
    Organization, Case, Debtor, RealEstate, Vehicle,
    Company, CompanyMember, FinancialStatement, FinancialIndicator,
    CreditExposure, GuaranteeGiven, CreditReportSummary,
    TaxDebtStatement, TaxDebtItem, Creditor, DebtPosition,
)

DEMO_CODE = "DEMO-0001"
CF = "BNCMRC68H15F205Z"   # formato persona fisica (16 char) — fittizio
PIVA = "12345678901"      # formato P.IVA (11 cifre) — fittizio


def run():
    db = SessionLocal()
    try:
        # --- idempotenza: rimuovi una eventuale demo precedente ---
        old = db.query(Case).filter_by(code=DEMO_CODE).all()
        for c in old:
            # cancella manualmente i figli non in cascade dal Case
            for st in db.query(TaxDebtStatement).filter_by(case_id=c.id).all():
                db.delete(st)
            db.delete(c)
        db.commit()

        org = db.query(Organization).first()
        if not org:
            org = Organization(name="Studio Legale Demo")
            db.add(org)
            db.flush()

        # ----------------------------------------------------------------
        # PRATICA + DEBITORE (anagrafica, nucleo, economia, situazioni)
        # ----------------------------------------------------------------
        case = Case(
            organization_id=org.id, code=DEMO_CODE,
            client_name="Marco Bianchi", client_tax_code=CF,
            status="in_lavorazione",
            priority="alta", referent="Avv. Laura Conti",
            tags="sovraindebitamento,impresa,garante",
            next_deadline="2026-07-31",
            notes="Pratica dimostrativa con dati fittizi per presentazione cliente.",
        )
        db.add(case)
        db.flush()

        debtor = Debtor(
            case_id=case.id,
            first_name="Marco", last_name="Bianchi", tax_code=CF,
            birth_date="1968-06-15", birth_place="Milano (MI)",
            residence="Via Palmanova 12, 20132 Milano (MI)",
            domicile="Via Palmanova 12, 20132 Milano (MI)",
            phone="+39 348 1122334", email="marco.bianchi@example.it",
            pec="marco.bianchi@pec.example.it",
            marital_status="coniugato", profession="Imprenditore edile",
            employer="Bianchi Costruzioni S.r.l.", client_type="privato",
            household_composition="Coniuge (a carico) + 2 figli minori",
            dependents=3,
            monthly_net_income=2800.0, annual_income=36400.0,
            income_sources="Compenso amministratore + redditi diversi",
            monthly_expenses=1500.0, rent_or_mortgage=650.0,
            bank_accounts="C/C Intesa Sanpaolo IT60X..., C/C BPER IT44Y...",
            has_ongoing_garnishment=True,
            has_salary_assignment=False,
            has_payment_delegation=False,
            notes="Pignoramento presso terzi in corso sul compenso amministratore.",
        )
        db.add(debtor)
        db.flush()

        # ----------------------------------------------------------------
        # IMMOBILI (prima casa con ipoteca + secondo immobile aggredibile)
        # ----------------------------------------------------------------
        db.add_all([
            RealEstate(
                case_id=case.id, kind="Fabbricato abitativo", category="A/2",
                address="Via Palmanova 12, 20132 Milano (MI)",
                cadastral_data="Milano, Fg. 215, Part. 88, Sub. 12",
                ownership_share="1/1", ownership_right="Proprietà",
                surface_mq=95.0, cadastral_income=850.0,
                cadastral_value=157500.0, commercial_value=285000.0,
                is_primary_residence=True, has_mortgage=True,
                provenance="Acquisto 2011", source="manuale",
                notes="Abitazione principale, ipoteca a garanzia mutuo Intesa.",
            ),
            RealEstate(
                case_id=case.id, kind="Fabbricato abitativo", category="A/3",
                address="Via Roma 5, 28021 Borgomanero (NO)",
                cadastral_data="Borgomanero, Fg. 12, Part. 340, Sub. 4",
                ownership_share="1/2", ownership_right="Proprietà",
                surface_mq=70.0, cadastral_income=520.0,
                cadastral_value=63000.0, commercial_value=95000.0,
                is_primary_residence=False, has_mortgage=False,
                other_owners="Coniuge (1/2)", provenance="Successione 2014",
                source="manuale", notes="Seconda casa ereditata, quota 50%.",
            ),
            RealEstate(
                case_id=case.id, kind="Box / autorimessa", category="C/6",
                address="Via Palmanova 12, 20132 Milano (MI)",
                cadastral_data="Milano, Fg. 215, Part. 88, Sub. 40",
                ownership_share="1/1", ownership_right="Proprietà",
                surface_mq=18.0, cadastral_income=120.0,
                cadastral_value=18000.0, commercial_value=22000.0,
                is_primary_residence=False, has_mortgage=False,
                source="manuale",
            ),
        ])

        # ----------------------------------------------------------------
        # VEICOLI
        # ----------------------------------------------------------------
        db.add_all([
            Vehicle(case_id=case.id, kind="auto", plate="EX123YZ",
                    make_model="Audi A4 Avant 2.0 TDI", year="2019",
                    estimated_value=18000.0, source="manuale"),
            Vehicle(case_id=case.id, kind="moto", plate="FG456AB",
                    make_model="BMW R 1200 GS", year="2017",
                    estimated_value=7000.0, source="manuale",
                    notes="Uso saltuario."),
        ])

        # ----------------------------------------------------------------
        # AZIENDA CLIENTE (S.r.l.) + SOCI + BILANCIO + INDICI
        # ----------------------------------------------------------------
        company = Company(
            case_id=case.id, role="cliente",
            name="Bianchi Costruzioni S.r.l.",
            legal_form="S.r.l.", company_type="capitali",
            tax_code=PIVA, vat=PIVA, rea="MI-1234567", cciaa="Milano Monza Brianza Lodi",
            pec="bianchicostruzioni@pec.example.it",
            legal_address="Via Palmanova 12, 20132 Milano (MI)",
            status="attiva", constitution_date="2010-03-12",
            capital=50000.0,
            ateco="41.20.00 — Costruzione di edifici residenziali e non",
            fatturato=1250000.0, dipendenti=8, patrimonio_netto=180000.0,
            anno_bilancio="2024",
            business_summary="Impresa di costruzioni edili. Cliente amministratore unico e socio di maggioranza.",
        )
        db.add(company)
        db.flush()

        db.add_all([
            CompanyMember(company_id=company.id, name="Marco Bianchi", tax_code=CF,
                          is_client=True, roles="Amministratore Unico", is_legal_rep=True,
                          quota_value=30000.0, quota_percent=60.0),
            CompanyMember(company_id=company.id, name="Laura Verdi", tax_code="VRDLRA72D55F205K",
                          is_client=False, roles="Socio", is_legal_rep=False,
                          quota_value=20000.0, quota_percent=40.0),
        ])

        fs = FinancialStatement(
            company_id=company.id, case_id=case.id,
            fiscal_year_end="2024-12-31", statement_type="abbreviato",
            ateco="41.20.00",
            total_assets=920000.0, equity=180000.0, total_debts=610000.0,
            revenues=1250000.0, net_result=42000.0,
            debts_secured=True, privileged_debts=85000.0,
            llm_provider="stub", llm_model="demo", crosscheck_status="not_run",
            raw_extraction={"nota": "Dati di bilancio dimostrativi (fittizi)."},
        )
        db.add(fs)
        db.flush()

        db.add_all([
            FinancialIndicator(statement_id=fs.id, code="current_ratio",
                               label="Current ratio", group="liquidità",
                               value_cur=1.18, value_prev=1.05, fmt="ratio",
                               trend="up", status="amber",
                               note="Attivo corrente / passivo corrente."),
            FinancialIndicator(statement_id=fs.id, code="roe",
                               label="ROE", group="redditività",
                               value_cur=23.3, value_prev=15.1, fmt="pct",
                               trend="up", status="green",
                               note="Utile netto / patrimonio netto."),
            FinancialIndicator(statement_id=fs.id, code="ros",
                               label="ROS", group="redditività",
                               value_cur=3.4, value_prev=2.9, fmt="pct",
                               trend="up", status="amber"),
            FinancialIndicator(statement_id=fs.id, code="leverage",
                               label="Leva finanziaria", group="struttura",
                               value_cur=3.39, value_prev=3.8, fmt="ratio",
                               trend="down", status="amber",
                               note="Totale attivo / patrimonio netto."),
            FinancialIndicator(statement_id=fs.id, code="debt_equity",
                               label="Debiti / patrimonio netto", group="struttura",
                               value_cur=3.39, value_prev=4.1, fmt="ratio",
                               trend="down", status="red"),
        ])

        # ----------------------------------------------------------------
        # CENTRALE RISCHI (esposizioni + garanzie + sintesi)
        # ----------------------------------------------------------------
        db.add_all([
            CreditExposure(case_id=case.id, intermediary="Intesa Sanpaolo S.p.A.",
                           category="Rischi a scadenza", accordato=200000.0,
                           utilizzato=142000.0, importo_garantito=0.0,
                           status="in sofferenza", is_critical=True,
                           reference_month="2025-08"),
            CreditExposure(case_id=case.id, intermediary="BPER Banca S.p.A.",
                           category="Rischi a revoca (fido c/c)", accordato=50000.0,
                           utilizzato=48500.0, importo_garantito=0.0,
                           status="utilizzo oltre l'80%", is_critical=True,
                           reference_month="2025-08"),
            CreditExposure(case_id=case.id, intermediary="Findomestic Banca S.p.A.",
                           category="Credito al consumo", accordato=20000.0,
                           utilizzato=15000.0, importo_garantito=0.0,
                           status="regolare", is_critical=False,
                           reference_month="2025-08"),
        ])
        db.add(GuaranteeGiven(
            case_id=case.id, intermediary="Intesa Sanpaolo S.p.A.",
            guaranteed_subject="Bianchi Costruzioni S.r.l.",
            valore_garanzia=150000.0, importo_garantito=100000.0,
            status="attiva (fideiussione)"))

        db.add(CreditReportSummary(
            case_id=case.id, period_from="2024-01", period_to="2025-08",
            most_recent_month="2025-08", num_intermediaries=3,
            total_exposure=205500.0, total_guarantees=100000.0,
            has_sofferenze=True, has_criticita=True,
            criticita=[
                {"mese": "2025-03", "evento": "Primo sconfino persistente fido BPER"},
                {"mese": "2025-06", "evento": "Classificazione a sofferenza Intesa Sanpaolo"},
            ],
            llm_provider="stub", llm_model="demo", crosscheck_status="not_run",
        ))

        # ----------------------------------------------------------------
        # ESTRATTO DI RUOLO AER (cartelle / avvisi)
        # ----------------------------------------------------------------
        items = [
            dict(numero_documento="2020/0012345", tipo_documento="Cartella di pagamento",
                 ente_creditore="Agenzia delle Entrate", ente_categoria="erariale",
                 data_notifica="2020-03-15", carico_affidato=21000.0, gia_pagato=2500.0,
                 residuo_carico=18500.0, interessi_mora=2800.0, oneri_diritti=400.0,
                 totale_residuo=21700.0, totale_residuo_netto=18500.0,
                 proc_attive=True, rateizzato=False, def_agevolata=False),
            dict(numero_documento="2021/0098877", tipo_documento="Cartella di pagamento",
                 ente_creditore="INPS", ente_categoria="previdenziale",
                 data_notifica="2021-06-10", carico_affidato=12300.0, gia_pagato=0.0,
                 residuo_carico=12300.0, interessi_mora=1500.0, oneri_diritti=200.0,
                 totale_residuo=14000.0, totale_residuo_netto=12300.0,
                 proc_attive=False, rateizzato=True, def_agevolata=False),
            dict(numero_documento="2022/0033221", tipo_documento="Avviso di accertamento",
                 ente_creditore="Comune di Milano", ente_categoria="locale",
                 data_notifica="2022-01-20", carico_affidato=3400.0, gia_pagato=0.0,
                 residuo_carico=3400.0, interessi_mora=300.0, oneri_diritti=80.0,
                 totale_residuo=3780.0, totale_residuo_netto=3400.0,
                 proc_attive=False, rateizzato=False, def_agevolata=False),
            dict(numero_documento="2019/0076540", tipo_documento="Cartella di pagamento",
                 ente_creditore="Agenzia delle Entrate", ente_categoria="erariale",
                 data_notifica="2019-11-05", carico_affidato=9800.0, gia_pagato=0.0,
                 residuo_carico=9800.0, interessi_mora=1900.0, oneri_diritti=250.0,
                 totale_residuo=11950.0, totale_residuo_netto=9800.0,
                 proc_attive=True, rateizzato=False, def_agevolata=True),
            dict(numero_documento="2023/0011002", tipo_documento="Cartella di pagamento",
                 ente_creditore="Regione Lombardia", ente_categoria="bollo",
                 data_notifica="2023-04-02", carico_affidato=1200.0, gia_pagato=0.0,
                 residuo_carico=1200.0, interessi_mora=120.0, oneri_diritti=40.0,
                 totale_residuo=1360.0, totale_residuo_netto=1200.0,
                 proc_attive=False, rateizzato=False, def_agevolata=False),
        ]
        stmt = TaxDebtStatement(
            case_id=case.id, owner_kind="person", debtor_id=debtor.id,
            codice_fiscale=CF, denominazione="Marco Bianchi",
            data_elaborazione="2025-09-30",
            total_residuo=round(sum(i["totale_residuo"] for i in items), 2),
            total_residuo_netto=round(sum(i["totale_residuo_netto"] for i in items), 2),
            total_carico_affidato=round(sum(i["carico_affidato"] for i in items), 2),
            count_proc_attive=sum(1 for i in items if i["proc_attive"]),
            quadrature_ok=True, extraction_method="parser",
            raw_extraction={"nota": "Estratto di ruolo dimostrativo (fittizio)."},
        )
        db.add(stmt)
        db.flush()
        for it in items:
            db.add(TaxDebtItem(statement_id=stmt.id, **it))

        # ----------------------------------------------------------------
        # POSIZIONI DEBITORIE (riepilogo creditori)
        # ----------------------------------------------------------------
        db.add_all([
            Creditor(case_id=case.id, name="Intesa Sanpaolo S.p.A.", kind="banca"),
            Creditor(case_id=case.id, name="BPER Banca S.p.A.", kind="banca"),
            Creditor(case_id=case.id, name="Findomestic Banca S.p.A.", kind="finanziaria"),
            Creditor(case_id=case.id, name="Agenzia Entrate Riscossione", kind="erario"),
        ])
        db.add_all([
            DebtPosition(case_id=case.id, creditor_name="Intesa Sanpaolo S.p.A.",
                         debt_type="Mutuo ipotecario", original_amount=200000.0,
                         residual_amount=142000.0, overdue_amount=8500.0,
                         monthly_installment=850.0, status="in sofferenza",
                         confidence=0.95, validated=True),
            DebtPosition(case_id=case.id, creditor_name="BPER Banca S.p.A.",
                         debt_type="Fido di conto corrente", original_amount=50000.0,
                         residual_amount=48500.0, overdue_amount=48500.0,
                         monthly_installment=0.0, status="revocato",
                         confidence=0.9, validated=True),
            DebtPosition(case_id=case.id, creditor_name="Findomestic Banca S.p.A.",
                         debt_type="Prestito personale", original_amount=20000.0,
                         residual_amount=15000.0, overdue_amount=960.0,
                         monthly_installment=320.0, status="in ritardo",
                         confidence=0.88, validated=False),
            DebtPosition(case_id=case.id, creditor_name="Agenzia Entrate Riscossione",
                         debt_type="Debito erariale/esattoriale (AER)", original_amount=47700.0,
                         residual_amount=45390.0, overdue_amount=45390.0,
                         monthly_installment=0.0, status="a ruolo",
                         confidence=1.0, validated=True),
        ])

        db.commit()
        print("OK pratica demo creata:")
        print("  case_id =", case.id)
        print("  code    =", case.code)
        print("  cliente =", case.client_name, "/", case.client_tax_code)
    finally:
        db.close()


if __name__ == "__main__":
    run()
