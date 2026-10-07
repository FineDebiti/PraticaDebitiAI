from pydantic import BaseModel
from typing import Optional


class DebtorIn(BaseModel):
    # Anagrafica
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    tax_code: Optional[str] = None
    birth_date: Optional[str] = None
    birth_place: Optional[str] = None
    residence: Optional[str] = None
    domicile: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    pec: Optional[str] = None
    marital_status: Optional[str] = None
    profession: Optional[str] = None
    employer: Optional[str] = None
    client_type: Optional[str] = None
    # Nucleo familiare
    household_composition: Optional[str] = None
    dependents: Optional[int] = None
    # Economici
    monthly_net_income: Optional[float] = None
    annual_income: Optional[float] = None
    income_sources: Optional[str] = None
    monthly_expenses: Optional[float] = None
    rent_or_mortgage: Optional[float] = None
    bank_accounts: Optional[str] = None
    # Situazioni in corso
    has_ongoing_garnishment: Optional[bool] = None
    has_salary_assignment: Optional[bool] = None
    has_payment_delegation: Optional[bool] = None
    notes: Optional[str] = None


class DebtorOut(BaseModel):
    id: str
    case_id: str
    first_name: str = ""
    last_name: str = ""
    tax_code: str = ""
    birth_date: str = ""
    birth_place: str = ""
    residence: str = ""
    domicile: str = ""
    phone: str = ""
    email: str = ""
    pec: str = ""
    marital_status: str = ""
    profession: str = ""
    employer: str = ""
    client_type: str = "privato"
    household_composition: str = ""
    dependents: int = 0
    monthly_net_income: float = 0.0
    annual_income: float = 0.0
    income_sources: str = ""
    monthly_expenses: float = 0.0
    rent_or_mortgage: float = 0.0
    bank_accounts: str = ""
    has_ongoing_garnishment: bool = False
    has_salary_assignment: bool = False
    has_payment_delegation: bool = False
    notes: str = ""

    class Config:
        from_attributes = True


class RealEstateIn(BaseModel):
    kind: str = ""
    address: str = ""
    cadastral_data: str = ""
    ownership_share: str = ""
    ownership_right: str = ""
    surface_mq: float = 0.0
    cadastral_income: float = 0.0
    cadastral_value: float = 0.0
    commercial_value: float = 0.0
    is_primary_residence: bool = False
    category: str = ""
    estimated_value: float = 0.0
    other_owners: str = ""
    provenance: str = ""
    has_mortgage: bool = False
    notes: str = ""
    source: str = "manuale"


class RealEstateOut(RealEstateIn):
    id: str
    class Config:
        from_attributes = True


class VehicleIn(BaseModel):
    kind: str = ""
    plate: str = ""
    make_model: str = ""
    year: str = ""
    estimated_value: float = 0.0
    notes: str = ""
    source: str = "manuale"


class VehicleOut(VehicleIn):
    id: str
    class Config:
        from_attributes = True


class CompanyMemberOut(BaseModel):
    id: str
    name: str = ""
    tax_code: str = ""
    is_client: bool = False
    roles: str = ""
    is_legal_rep: bool = False
    quota_value: float = 0.0
    quota_percent: float = 0.0

    class Config:
        from_attributes = True


class CompanyMemberIn(BaseModel):
    name: str = ""
    tax_code: str = ""
    is_client: bool = False
    roles: str = ""
    is_legal_rep: bool = False
    quota_value: float = 0.0
    quota_percent: float = 0.0


class CompanyIn(BaseModel):
    """Dati azienda editabili dalla scheda (azienda cliente o partecipata)."""
    role: str = "cliente"
    name: str = ""
    legal_form: str = ""
    company_type: str = ""
    tax_code: str = ""
    vat: str = ""
    rea: str = ""
    cciaa: str = ""
    pec: str = ""
    legal_address: str = ""
    status: str = ""
    constitution_date: str = ""
    capital: float = 0.0
    ateco: str = ""
    fatturato: float = 0.0
    dipendenti: int = 0
    patrimonio_netto: float = 0.0
    anno_bilancio: str = ""
    business_summary: str = ""
    members: list[CompanyMemberIn] = []


class FinancialIndicatorOut(BaseModel):
    code: str = ""
    label: str = ""
    group: str = ""
    value_cur: Optional[float] = None
    value_prev: Optional[float] = None
    fmt: str = ""
    trend: str = ""
    status: str = ""
    note: str = ""

    class Config:
        from_attributes = True


class FinancialStatementOut(BaseModel):
    id: str
    fiscal_year_end: str = ""
    statement_type: str = ""
    ateco: str = ""
    total_assets: float = 0.0
    equity: float = 0.0
    total_debts: float = 0.0
    revenues: float = 0.0
    net_result: float = 0.0
    debts_secured: bool = False
    privileged_debts: float = 0.0
    raw_extraction: dict = {}
    raw_corrected: dict = {}
    llm_provider: str = ""
    llm_model: str = ""
    crosscheck_status: str = ""
    crosscheck_payload: dict = {}
    indicators: list[FinancialIndicatorOut] = []

    class Config:
        from_attributes = True


class CompanyOut(BaseModel):
    id: str
    role: str = "cliente"
    name: str = ""
    legal_form: str = ""
    company_type: str = ""
    tax_code: str = ""
    vat: str = ""
    rea: str = ""
    cciaa: str = ""
    pec: str = ""
    legal_address: str = ""
    status: str = ""
    constitution_date: str = ""
    capital: float = 0.0
    business_summary: str = ""
    ateco: str = ""
    fatturato: float = 0.0
    dipendenti: int = 0
    patrimonio_netto: float = 0.0
    anno_bilancio: str = ""
    members: list[CompanyMemberOut] = []
    financial_statements: list[FinancialStatementOut] = []

    class Config:
        from_attributes = True


class CreditExposureOut(BaseModel):
    id: str
    intermediary: str = ""
    category: str = ""
    accordato: float = 0.0
    utilizzato: float = 0.0
    importo_garantito: float = 0.0
    status: str = ""
    is_critical: bool = False
    reference_month: str = ""

    class Config:
        from_attributes = True


class GuaranteeGivenOut(BaseModel):
    id: str
    intermediary: str = ""
    guaranteed_subject: str = ""
    valore_garanzia: float = 0.0
    importo_garantito: float = 0.0
    status: str = ""

    class Config:
        from_attributes = True


class CreditReportSummaryOut(BaseModel):
    id: str
    period_from: str = ""
    period_to: str = ""
    most_recent_month: str = ""
    num_intermediaries: int = 0
    total_exposure: float = 0.0
    total_guarantees: float = 0.0
    has_sofferenze: bool = False
    has_criticita: bool = False
    criticita: list = []
    llm_provider: str = ""
    llm_model: str = ""
    crosscheck_status: str = ""
    crosscheck_payload: dict = {}

    class Config:
        from_attributes = True


class TaxDebtItemOut(BaseModel):
    id: str
    numero_documento: str = ""
    tipo_documento: str = ""
    ente_creditore: str = ""
    ente_categoria: str = ""
    data_notifica: str = ""
    carico_affidato: float = 0.0
    sgravio: float = 0.0
    gia_pagato: float = 0.0
    stralcio: float = 0.0
    residuo_carico: float = 0.0
    interessi_mora: float = 0.0
    oneri_diritti: float = 0.0
    totale_residuo: float = 0.0
    importo_sospeso: float = 0.0
    totale_residuo_netto: float = 0.0
    rateizzato: bool = False
    proc_attive: bool = False
    def_agevolata: bool = False
    needs_review: bool = False

    class Config:
        from_attributes = True


class TaxDebtStatementOut(BaseModel):
    id: str
    owner_kind: str = "person"
    debtor_id: Optional[str] = None
    company_id: Optional[str] = None
    codice_fiscale: str = ""
    denominazione: str = ""
    data_elaborazione: str = ""
    total_residuo: float = 0.0
    total_residuo_netto: float = 0.0
    total_carico_affidato: float = 0.0
    count_proc_attive: int = 0
    quadrature_ok: bool = True
    extraction_method: str = "parser"
    cf_mismatch: bool = False
    raw_extraction: dict = {}
    source_document_id: str = ""
    items: list[TaxDebtItemOut] = []

    class Config:
        from_attributes = True


class ClientCard(BaseModel):
    """Scheda cliente completa: debitore + patrimonio + aziende + Centrale Rischi + AER."""
    case_id: str
    debtor: Optional[DebtorOut] = None
    real_estates: list[RealEstateOut] = []
    vehicles: list[VehicleOut] = []
    companies: list[CompanyOut] = []
    credit_exposures: list[CreditExposureOut] = []
    guarantees_given: list[GuaranteeGivenOut] = []
    credit_report: Optional[CreditReportSummaryOut] = None
    tax_debts: list[TaxDebtStatementOut] = []

