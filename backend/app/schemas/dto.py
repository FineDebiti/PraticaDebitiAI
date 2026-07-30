from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime


class CaseCreate(BaseModel):
    client_kind: str = "persona"     # "persona" | "azienda"
    first_name: str = ""
    last_name: str = ""
    denomination: str = ""
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
    documents: List[DocumentOut] = []
    positions: List[PositionOut] = []


class IncomeDocumentOut(BaseModel):
    document_id: str
    doc_type: str
    original_filename: str
    status: str
    created_at: str
    data: Dict[str, Any] = {}


class RelatedCaseOut(BaseModel):
    case_id: str
    case_label: str
    cf: str
    n_documenti: int
    n_visure: int
    ultima_attivita: str


class IndicatorItemOut(BaseModel):
    code: str
    label: str
    area: str
    value: Optional[Any] = None
    unit: str
    formula_human: str
    kind: str = "det"
    status: str = "na"
    criterion: Optional[str] = None
    source_section: str = ""
    source_tab: str = "riepilogo"
    detail: Optional[List[Dict[str, Any]]] = None


class CaseIndicatorsOut(BaseModel):
    macro: List[IndicatorItemOut] = []
    indicators: List[IndicatorItemOut] = []


class FieldEditOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    field: str
    old_value: str
    new_value: str
    reason: str
    created_at: str

    class Config:
        from_attributes = True


class EnrichmentRequestOut(BaseModel):
    id: str
    source: str
    query: str
    status: str
    sandbox: bool
    error: str
    mapped_data: Dict[str, Any] = {}
    raw_response: Dict[str, Any] = {}
    created_at: str
