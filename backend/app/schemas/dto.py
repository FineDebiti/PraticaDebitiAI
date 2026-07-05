from pydantic import BaseModel
from datetime import datetime


class CaseCreate(BaseModel):
    client_kind: str = "persona"     # "persona" | "azienda"
    # Persona fisica
    first_name: str = ""
    last_name: str = ""
    # Azienda
    denomination: str = ""
    # Comune a entrambi: codice fiscale (persona) o partita IVA (azienda)
    client_tax_code: str = ""
    code: str = ""
    notes: str = ""


class CaseOut(BaseModel):
    id: str
    code: str
    client_name: str
    client_tax_code: str
    status: str
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DocumentOut(BaseModel):
    id: str
    case_id: str
    original_filename: str
    doc_type: str
    classification_confidence: float
    status: str
    num_pages: int
    error: str
    content_type: str = ""
    size_bytes: int = 0
    sha256: str = ""
    created_at: datetime

    class Config:
        from_attributes = True


class PositionOut(BaseModel):
    id: str
    creditor_name: str
    debt_type: str
    original_amount: float
    residual_amount: float
    overdue_amount: float
    monthly_installment: float
    status: str
    confidence: float
    validated: bool
    source_document_id: str
    source_page: int

    class Config:
        from_attributes = True


class CaseDetail(CaseOut):
    documents: list[DocumentOut] = []
    positions: list[PositionOut] = []
