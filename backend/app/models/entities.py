import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db import Base


def _id() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    name: Mapped[str] = mapped_column(String, default="Studio Demo")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Case(Base):
    __tablename__ = "cases"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    code: Mapped[str] = mapped_column(String, default="")
    client_name: Mapped[str] = mapped_column(String, default="")
    # indicizzato per il match veloce cross-pratica sullo stesso CF normalizzato
    client_tax_code: Mapped[str] = mapped_column(String, default="", index=True)
    status: Mapped[str] = mapped_column(String, default="nuova")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    # --- Campi organizzativi pratica (sez. 7.2) ---
    priority: Mapped[str] = mapped_column(String, default="media")  # bassa|media|alta
    referent: Mapped[str] = mapped_column(String, default="")
    tags: Mapped[str] = mapped_column(String, default="")  # csv
    next_deadline: Mapped[str] = mapped_column(String, default="")  # ISO date

    documents: Mapped[list["Document"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    creditors: Mapped[list["Creditor"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    positions: Mapped[list["DebtPosition"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    debtor: Mapped["Debtor"] = relationship(back_populates="case", uselist=False, cascade="all, delete-orphan")
    real_estates: Mapped[list["RealEstate"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    companies: Mapped[list["Company"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    credit_exposures: Mapped[list["CreditExposure"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    guarantees_given: Mapped[list["GuaranteeGiven"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    cr_summaries: Mapped[list["CreditReportSummary"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    enrichment_requests: Mapped[list["EnrichmentRequest"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class Debtor(Base):
    """Scheda cliente/debitore dettagliata (sez. 7.2 + 10)."""
    __tablename__ = "debtors"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"), unique=True)

    # --- Anagrafica ---
    first_name: Mapped[str] = mapped_column(String, default="")
    last_name: Mapped[str] = mapped_column(String, default="")
    tax_code: Mapped[str] = mapped_column(String, default="")
    birth_date: Mapped[str] = mapped_column(String, default="")        # ISO date
    birth_place: Mapped[str] = mapped_column(String, default="")
    residence: Mapped[str] = mapped_column(String, default="")
    domicile: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    email: Mapped[str] = mapped_column(String, default="")
    pec: Mapped[str] = mapped_column(String, default="")
    marital_status: Mapped[str] = mapped_column(String, default="")
    profession: Mapped[str] = mapped_column(String, default="")
    employer: Mapped[str] = mapped_column(String, default="")
    client_type: Mapped[str] = mapped_column(String, default="privato")  # privato|ditta_individuale|societa|garante|coobbligato

    # --- Nucleo familiare ---
    household_composition: Mapped[str] = mapped_column(Text, default="")
    dependents: Mapped[int] = mapped_column(Integer, default=0)

    # --- Dati economici ---
    monthly_net_income: Mapped[float] = mapped_column(Float, default=0.0)
    annual_income: Mapped[float] = mapped_column(Float, default=0.0)
    income_sources: Mapped[str] = mapped_column(Text, default="")
    monthly_expenses: Mapped[float] = mapped_column(Float, default=0.0)
    rent_or_mortgage: Mapped[float] = mapped_column(Float, default=0.0)
    bank_accounts: Mapped[str] = mapped_column(Text, default="")

    # --- Situazioni in corso ---
    has_ongoing_garnishment: Mapped[bool] = mapped_column(default=False)   # pignoramenti
    has_salary_assignment: Mapped[bool] = mapped_column(default=False)     # cessione del quinto
    has_payment_delegation: Mapped[bool] = mapped_column(default=False)    # delega di pagamento

    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    case: Mapped["Case"] = relationship(back_populates="debtor")


class RealEstate(Base):
    """Immobile intestato al debitore."""
    __tablename__ = "real_estates"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(String, default="")       # categoria/tipo es. "fabbricato A/2"
    address: Mapped[str] = mapped_column(String, default="")
    cadastral_data: Mapped[str] = mapped_column(String, default="")  # Comune, Fg, Part, Sub
    ownership_share: Mapped[str] = mapped_column(String, default="")  # quota del cliente es. "1/3"
    ownership_right: Mapped[str] = mapped_column(String, default="")  # es. "Proprieta", "Usufrutto"
    surface_mq: Mapped[float] = mapped_column(Float, default=0.0)
    cadastral_income: Mapped[float] = mapped_column(Float, default=0.0)   # rendita catastale (€)
    cadastral_value: Mapped[float] = mapped_column(Float, default=0.0)    # valore catastale calcolato (€)
    commercial_value: Mapped[float] = mapped_column(Float, default=0.0)   # stima valore commerciale (placeholder)
    is_primary_residence: Mapped[bool] = mapped_column(default=False)     # prima casa -> moltiplicatore 110
    category: Mapped[str] = mapped_column(String, default="")             # categoria catastale es. "A/2" (per ricalcolo)
    estimated_value: Mapped[float] = mapped_column(Float, default=0.0)    # legacy/manuale
    other_owners: Mapped[str] = mapped_column(Text, default="")          # altri intestatari (testo)
    provenance: Mapped[str] = mapped_column(String, default="")          # es. "Successione 2014"
    has_mortgage: Mapped[bool] = mapped_column(default=False)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String, default="manuale")        # manuale | Catasto (Openapi) | documento
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="real_estates")


class Vehicle(Base):
    """Veicolo intestato al debitore."""
    __tablename__ = "vehicles"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    kind: Mapped[str] = mapped_column(String, default="")       # auto|moto|altro
    plate: Mapped[str] = mapped_column(String, default="")
    make_model: Mapped[str] = mapped_column(String, default="")
    year: Mapped[str] = mapped_column(String, default="")
    estimated_value: Mapped[float] = mapped_column(Float, default=0.0)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String, default="manuale")        # manuale | PRA (Openapi) | documento
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="vehicles")


class Company(Base):
    """Impresa estratta da una visura camerale.
    role distingue l'impresa del cliente dalle controparti/aziende terze."""
    __tablename__ = "companies"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    role: Mapped[str] = mapped_column(String, default="cliente")  # cliente | controparte
    name: Mapped[str] = mapped_column(String, default="")
    legal_form: Mapped[str] = mapped_column(String, default="")        # forma giuridica
    company_type: Mapped[str] = mapped_column(String, default="")      # persone | capitali | altro
    tax_code: Mapped[str] = mapped_column(String, default="", index=True)
    vat: Mapped[str] = mapped_column(String, default="", index=True)
    rea: Mapped[str] = mapped_column(String, default="")
    cciaa: Mapped[str] = mapped_column(String, default="")
    pec: Mapped[str] = mapped_column(String, default="")
    legal_address: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="")           # attiva|inattiva|cessata...
    constitution_date: Mapped[str] = mapped_column(String, default="")
    capital: Mapped[float] = mapped_column(Float, default=0.0)        # capitale sociale (€)
    business_summary: Mapped[str] = mapped_column(Text, default="")
    # --- dati aggiuntivi da Openapi Company ---
    ateco: Mapped[str] = mapped_column(String, default="")            # codice + descrizione ATECO
    fatturato: Mapped[float] = mapped_column(Float, default=0.0)      # ultimo bilancio (€)
    dipendenti: Mapped[int] = mapped_column(Integer, default=0)
    patrimonio_netto: Mapped[float] = mapped_column(Float, default=0.0)  # (€)
    anno_bilancio: Mapped[str] = mapped_column(String, default="")    # anno del bilancio
    extra: Mapped[dict] = mapped_column(JSON, default=dict)           # dati secondari
    source_document_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="companies")
    members: Mapped[list["CompanyMember"]] = relationship(
        back_populates="company", cascade="all, delete-orphan")
    financial_statements: Mapped[list["FinancialStatement"]] = relationship(
        back_populates="company", cascade="all, delete-orphan")


class FinancialStatement(Base):
    """Bilancio di esercizio (deposito CCIAA) agganciato a una Company."""
    __tablename__ = "financial_statements"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    case_id: Mapped[str] = mapped_column(String, default="")          # comodità per query
    fiscal_year_end: Mapped[str] = mapped_column(String, default="")  # YYYY-MM-DD
    statement_type: Mapped[str] = mapped_column(String, default="")   # abbreviato|ordinario|microimpresa
    ateco: Mapped[str] = mapped_column(String, default="")
    raw_extraction: Mapped[dict] = mapped_column(JSON, default=dict)  # schema §2 completo: FONTE, immutabile
    raw_corrected: Mapped[dict] = mapped_column(JSON, default=dict)   # voci corrette dall'operatore (override)
    # voci chiave denormalizzate (esercizio corrente) per query rapida
    total_assets: Mapped[float] = mapped_column(Float, default=0.0)
    equity: Mapped[float] = mapped_column(Float, default=0.0)
    total_debts: Mapped[float] = mapped_column(Float, default=0.0)
    revenues: Mapped[float] = mapped_column(Float, default=0.0)
    net_result: Mapped[float] = mapped_column(Float, default=0.0)
    debts_secured: Mapped[bool] = mapped_column(default=False)
    privileged_debts: Mapped[float] = mapped_column(Float, default=0.0)  # erario+previdenza
    source_document_id: Mapped[str] = mapped_column(String, default="")
    # Provenienza estrazione (resilienza multi-provider) + esito cross-check.
    llm_provider: Mapped[str] = mapped_column(String, default="")        # gemini|claude|openai|stub
    llm_model: Mapped[str] = mapped_column(String, default="")
    crosscheck_status: Mapped[str] = mapped_column(String, default="")   # verified|discrepancy|not_run
    crosscheck_payload: Mapped[dict] = mapped_column(JSON, default=dict)  # discrepanze + provider a/b
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    company: Mapped["Company"] = relationship(back_populates="financial_statements")
    indicators: Mapped[list["FinancialIndicator"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan")


class FinancialIndicator(Base):
    """Indice di bilancio calcolato (deterministico), storicizzato e auditabile."""
    __tablename__ = "financial_indicators"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    statement_id: Mapped[str] = mapped_column(ForeignKey("financial_statements.id"))
    code: Mapped[str] = mapped_column(String, default="")
    label: Mapped[str] = mapped_column(String, default="")
    group: Mapped[str] = mapped_column(String, default="")
    value_cur: Mapped[float | None] = mapped_column(Float, nullable=True)   # null = n.s.
    value_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    fmt: Mapped[str] = mapped_column(String, default="")                    # ratio|pct|eur
    trend: Mapped[str] = mapped_column(String, default="")                  # up|down|flat|na
    status: Mapped[str] = mapped_column(String, default="")                 # green|amber|red|na
    note: Mapped[str] = mapped_column(Text, default="")
    statement: Mapped["FinancialStatement"] = relationship(back_populates="indicators")


class CompanyMember(Base):
    """Socio / titolare di carica di una Company."""
    __tablename__ = "company_members"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"))
    name: Mapped[str] = mapped_column(String, default="")
    tax_code: Mapped[str] = mapped_column(String, default="")
    is_client: Mapped[bool] = mapped_column(default=False)            # e il cliente della pratica
    roles: Mapped[str] = mapped_column(String, default="")           # cariche, csv
    is_legal_rep: Mapped[bool] = mapped_column(default=False)
    quota_value: Mapped[float] = mapped_column(Float, default=0.0)
    quota_percent: Mapped[float] = mapped_column(Float, default=0.0)
    company: Mapped["Company"] = relationship(back_populates="members")


class CreditExposure(Base):
    """Esposizione verso una banca/finanziaria (da Centrale Rischi)."""
    __tablename__ = "credit_exposures"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    intermediary: Mapped[str] = mapped_column(String, default="")       # banca/finanziaria
    category: Mapped[str] = mapped_column(String, default="")           # rischi a scadenza/revoca...
    accordato: Mapped[float] = mapped_column(Float, default=0.0)
    utilizzato: Mapped[float] = mapped_column(Float, default=0.0)
    importo_garantito: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="")
    is_critical: Mapped[bool] = mapped_column(default=False)
    reference_month: Mapped[str] = mapped_column(String, default="")    # mese piu recente
    source_document_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="credit_exposures")


class GuaranteeGiven(Base):
    """Garanzia prestata dal cliente a favore di un terzo (da Centrale Rischi)."""
    __tablename__ = "guarantees_given"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    intermediary: Mapped[str] = mapped_column(String, default="")
    guaranteed_subject: Mapped[str] = mapped_column(String, default="")  # societa garantita
    valore_garanzia: Mapped[float] = mapped_column(Float, default=0.0)
    importo_garantito: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="")
    source_document_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="guarantees_given")


class CreditReportSummary(Base):
    """Sintesi della Centrale Rischi: totali + criticita nel tempo (JSON)."""
    __tablename__ = "credit_report_summaries"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    period_from: Mapped[str] = mapped_column(String, default="")
    period_to: Mapped[str] = mapped_column(String, default="")
    most_recent_month: Mapped[str] = mapped_column(String, default="")
    num_intermediaries: Mapped[int] = mapped_column(Integer, default=0)
    total_exposure: Mapped[float] = mapped_column(Float, default=0.0)
    total_guarantees: Mapped[float] = mapped_column(Float, default=0.0)
    has_sofferenze: Mapped[bool] = mapped_column(default=False)
    has_criticita: Mapped[bool] = mapped_column(default=False)
    criticita: Mapped[list] = mapped_column(JSON, default=list)          # eventi critici nel tempo
    source_document_id: Mapped[str] = mapped_column(String, default="")
    # Provenienza estrazione (resilienza multi-provider) + esito cross-check.
    llm_provider: Mapped[str] = mapped_column(String, default="")        # gemini|claude|openai|stub
    llm_model: Mapped[str] = mapped_column(String, default="")
    crosscheck_status: Mapped[str] = mapped_column(String, default="")   # verified|discrepancy|not_run
    crosscheck_payload: Mapped[dict] = mapped_column(JSON, default=dict)  # discrepanze + provider a/b
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="cr_summaries")


class EnrichmentRequest(Base):
    """Richiesta di visura a Openapi (asincrona, a pagamento). Salvata per non perderla."""
    __tablename__ = "enrichment_requests"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    source: Mapped[str] = mapped_column(String, default="")           # "camerale" | "catasto" | "veicoli"
    query: Mapped[str] = mapped_column(String, default="")            # P.IVA o CF interrogato
    input_params: Mapped[dict] = mapped_column(JSON, default=dict)    # parametri extra ($1,$2..) es. comune, contatto
    openapi_request_id: Mapped[str] = mapped_column(String, default="")  # _id ritornato da Openapi
    status: Mapped[str] = mapped_column(String, default="pending")    # pending|done|error|timeout
    is_sandbox: Mapped[bool] = mapped_column(default=True)
    raw_response: Mapped[dict] = mapped_column(JSON, default=dict)     # risposta GREZZA (per diagnostica/taratura)
    mapped_data: Mapped[dict] = mapped_column(JSON, default=dict)      # dati mappati per la scheda
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)
    case: Mapped["Case"] = relationship(back_populates="enrichment_requests")


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    original_filename: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    # --- File originale persistito (astrazione storage GCS-ready) ---
    storage_uri: Mapped[str] = mapped_column(String, default="")      # key nello storage backend
    content_type: Mapped[str] = mapped_column(String, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str] = mapped_column(String, default="")           # integrità / dedup
    doc_type: Mapped[str] = mapped_column(String, default="da_classificare")
    classification_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="caricato")  # caricato|in_elaborazione|elaborato|errore
    num_pages: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    case: Mapped["Case"] = relationship(back_populates="documents")
    extraction: Mapped["Extraction"] = relationship(back_populates="document", uselist=False, cascade="all, delete-orphan")


class Extraction(Base):
    __tablename__ = "extractions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"))
    ocr_provider: Mapped[str] = mapped_column(String, default="")
    llm_provider: Mapped[str] = mapped_column(String, default="")
    raw_text: Mapped[str] = mapped_column(Text, default="")
    json_output: Mapped[dict] = mapped_column(JSON, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    document: Mapped["Document"] = relationship(back_populates="extraction")


class Creditor(Base):
    __tablename__ = "creditors"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    name: Mapped[str] = mapped_column(String, default="")
    kind: Mapped[str] = mapped_column(String, default="")
    source_document_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="creditors")


class DebtPosition(Base):
    __tablename__ = "debt_positions"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    creditor_name: Mapped[str] = mapped_column(String, default="")
    debt_type: Mapped[str] = mapped_column(String, default="")
    original_amount: Mapped[float] = mapped_column(Float, default=0.0)
    residual_amount: Mapped[float] = mapped_column(Float, default=0.0)
    overdue_amount: Mapped[float] = mapped_column(Float, default=0.0)
    monthly_installment: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    validated: Mapped[bool] = mapped_column(default=False)
    source_document_id: Mapped[str] = mapped_column(String, default="")
    source_page: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    case: Mapped["Case"] = relationship(back_populates="positions")


class TaxDebtStatement(Base):
    """Un estratto di ruolo AER. Attribuito a una persona (Debtor) o a una Company,
    a seconda della scheda da cui parte l'upload (owner_kind)."""
    __tablename__ = "tax_debt_statements"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id"))
    owner_kind: Mapped[str] = mapped_column(String, default="person")  # person|company
    debtor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    company_id: Mapped[str | None] = mapped_column(String, nullable=True)
    codice_fiscale: Mapped[str] = mapped_column(String, default="")    # dalla testata del PDF
    denominazione: Mapped[str] = mapped_column(String, default="")
    data_elaborazione: Mapped[str] = mapped_column(String, default="")  # ISO date o ""
    total_residuo: Mapped[float] = mapped_column(Float, default=0.0)     # totale residuo (L)
    total_residuo_netto: Mapped[float] = mapped_column(Float, default=0.0)  # (N)
    total_carico_affidato: Mapped[float] = mapped_column(Float, default=0.0)
    count_proc_attive: Mapped[int] = mapped_column(Integer, default=0)
    quadrature_ok: Mapped[bool] = mapped_column(default=True)
    extraction_method: Mapped[str] = mapped_column(String, default="parser")  # parser|ai
    cf_mismatch: Mapped[bool] = mapped_column(default=False)
    raw_extraction: Mapped[dict] = mapped_column(JSON, default=dict)     # schema §4 + aggregazioni
    source_document_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    items: Mapped[list["TaxDebtItem"]] = relationship(
        back_populates="statement", cascade="all, delete-orphan")


class TaxDebtItem(Base):
    """Una cartella/avviso dell'estratto di ruolo."""
    __tablename__ = "tax_debt_items"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    statement_id: Mapped[str] = mapped_column(ForeignKey("tax_debt_statements.id"))
    numero_documento: Mapped[str] = mapped_column(String, default="")
    tipo_documento: Mapped[str] = mapped_column(String, default="")
    ente_creditore: Mapped[str] = mapped_column(String, default="")
    ente_categoria: Mapped[str] = mapped_column(String, default="")  # previdenziale|erariale|locale|bollo|camerale|misto|altro
    data_notifica: Mapped[str] = mapped_column(String, default="")   # ISO date o ""
    carico_affidato: Mapped[float] = mapped_column(Float, default=0.0)
    sgravio: Mapped[float] = mapped_column(Float, default=0.0)
    gia_pagato: Mapped[float] = mapped_column(Float, default=0.0)
    stralcio: Mapped[float] = mapped_column(Float, default=0.0)
    residuo_carico: Mapped[float] = mapped_column(Float, default=0.0)
    interessi_mora: Mapped[float] = mapped_column(Float, default=0.0)
    oneri_diritti: Mapped[float] = mapped_column(Float, default=0.0)
    totale_residuo: Mapped[float] = mapped_column(Float, default=0.0)
    importo_sospeso: Mapped[float] = mapped_column(Float, default=0.0)
    totale_residuo_netto: Mapped[float] = mapped_column(Float, default=0.0)
    rateizzato: Mapped[bool] = mapped_column(default=False)
    proc_attive: Mapped[bool] = mapped_column(default=False)
    def_agevolata: Mapped[bool] = mapped_column(default=False)
    needs_review: Mapped[bool] = mapped_column(default=False)
    statement: Mapped["TaxDebtStatement"] = relationship(back_populates="items")


class FieldEdit(Base):
    """Audit di una correzione manuale su un dato estratto (AI/API -> operatore).
    La fonte (raw_extraction) resta immutabile; qui si traccia chi/cosa/prima->dopo/quando."""
    __tablename__ = "field_edits"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    case_id: Mapped[str] = mapped_column(String, default="", index=True)
    entity_type: Mapped[str] = mapped_column(String, default="", index=True)  # financial_statement|tax_debt_item|...
    entity_id: Mapped[str] = mapped_column(String, default="", index=True)
    field: Mapped[str] = mapped_column(String, default="")
    old_value: Mapped[str] = mapped_column(Text, default="")
    new_value: Mapped[str] = mapped_column(Text, default="")
    operator: Mapped[str] = mapped_column(String, default="")     # utente (no auth ora)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class AccessLog(Base):
    """Audit: accesso a dati correlati cross-pratica (stesso CF in altra pratica).
    Per un'app legale è buona prassi tracciare chi/cosa/quando."""
    __tablename__ = "access_logs"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    operator: Mapped[str] = mapped_column(String, default="")          # utente (no auth ora -> vuoto)
    cf: Mapped[str] = mapped_column(String, default="", index=True)    # CF normalizzato oggetto dell'accesso
    from_case_id: Mapped[str] = mapped_column(String, default="")      # pratica di partenza
    to_case_id: Mapped[str] = mapped_column(String, default="")        # pratica correlata aperta
    action: Mapped[str] = mapped_column(String, default="open_related")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
