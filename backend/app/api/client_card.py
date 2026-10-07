from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List

from app.db import get_db
from app.config import settings
from app.models import (
    Case, Debtor, RealEstate, Vehicle, Company, CompanyMember,
    CreditExposure, GuaranteeGiven, CreditReportSummary,
    Document, TaxDebtStatement, TaxDebtItem, EnrichmentRequest, AccessLog, FieldEdit,
)
from app.schemas.debtor import (
    DebtorIn, DebtorOut, RealEstateIn, RealEstateOut,
    VehicleIn, VehicleOut, ClientCard, CompanyIn, CompanyOut,
    TaxDebtStatementOut,
)
from app.schemas.dto import (
    IncomeDocumentOut, RelatedCaseOut, CaseIndicatorsOut, FieldEditOut, EnrichmentRequestOut
)
from app.services import fiscal_code as fc

router = APIRouter()


def _get_case(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Pratica non trovata")
    return case


# ---------- Scheda completa ----------
@router.get("/cases/{case_id}/card", response_model=ClientCard)
def get_card(case_id: str, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    cr = db.query(CreditReportSummary).filter_by(case_id=case_id).order_by(
        CreditReportSummary.id.desc()).first()
    return ClientCard(
        case_id=case_id,
        debtor=debtor,
        real_estates=db.query(RealEstate).filter_by(case_id=case_id).all(),
        vehicles=db.query(Vehicle).filter_by(case_id=case_id).all(),
        companies=db.query(Company).filter_by(case_id=case_id).all(),
        credit_exposures=db.query(CreditExposure).filter_by(case_id=case_id).all(),
        guarantees_given=db.query(GuaranteeGiven).filter_by(case_id=case_id).all(),
        credit_report=cr,
        tax_debts=db.query(TaxDebtStatement).filter_by(case_id=case_id).order_by(
            TaxDebtStatement.created_at.desc()).all(),
    )


# ---------- Documenti di reddito (dettaglio estratto) ----------
INCOME_DOC_TYPES = ("busta_paga", "cu", "isee", "estratto_conto", "dichiarazione_redditi")


@router.get("/cases/{case_id}/income/documents", response_model=List[IncomeDocumentOut])
def income_documents(case_id: str, db: Session = Depends(get_db)):
    """Documenti di reddito della pratica con il dettaglio estratto (da Document + Extraction)."""
    _get_case(db, case_id)
    docs = (db.query(Document)
            .filter(Document.case_id == case_id, Document.doc_type.in_(INCOME_DOC_TYPES))
            .order_by(Document.created_at.desc()).all())
    out = []
    for d in docs:
        data = d.extraction.json_output if (d.extraction and d.extraction.json_output) else {}
        out.append(IncomeDocumentOut(
            document_id=d.id,
            doc_type=d.doc_type,
            original_filename=d.original_filename,
            status=d.status,
            created_at=d.created_at.isoformat() if d.created_at else "",
            data=data,
        ))
    return out


@router.get("/cases/{case_id}/income/summary")
def income_summary(case_id: str, db: Session = Depends(get_db)):
    """Riepilogo reddito consolidato: tutte le fonti normalizzate a mensile."""
    from app.services.income_summary import compute_income_summary
    _get_case(db, case_id)
    return compute_income_summary(db, case_id)


# ---------- Indice CF cross-pratica ----------
@router.get("/cases/{case_id}/related", response_model=List[RelatedCaseOut])
def related_cases(case_id: str, db: Session = Depends(get_db)):
    """Sommario delle altre pratiche con lo stesso CF titolare."""
    if not settings.cross_case_index_enabled:
        return []
    case = _get_case(db, case_id)
    cf = fc.normalize(case.client_tax_code)
    if not cf:
        return []
    out = []
    others = db.query(Case).filter(Case.client_tax_code == cf, Case.id != case_id).all()
    for c in others:
        n_doc = db.query(Document).filter_by(case_id=c.id).count()
        n_vis = db.query(EnrichmentRequest).filter_by(case_id=c.id).count()
        last = c.updated_at or c.created_at
        out.append(RelatedCaseOut(
            case_id=c.id,
            case_label=(c.code or "") + (f" — {c.client_name}" if c.client_name else ""),
            cf=cf, n_documenti=n_doc, n_visure=n_vis,
            ultima_attivita=last.isoformat() if last else "",
        ))
    return out


class RelatedOpen(BaseModel):
    to_case_id: str


@router.post("/cases/{case_id}/related/open")
def open_related(case_id: str, payload: RelatedOpen, db: Session = Depends(get_db)):
    """Registra in AccessLog l'apertura di una pratica correlata."""
    case = _get_case(db, case_id)
    target = db.get(Case, payload.to_case_id)
    if not target:
        raise HTTPException(404, "Pratica correlata non trovata")
    db.add(AccessLog(
        from_case_id=case_id, to_case_id=payload.to_case_id,
        cf=fc.normalize(case.client_tax_code), action="open_related",
    ))
    db.commit()
    return {"ok": True}


# ---------- Cruscotto indicatori ----------
@router.get("/cases/{case_id}/indicators", response_model=CaseIndicatorsOut)
def case_indicators(case_id: str, db: Session = Depends(get_db)):
    """Indicatori di sintesi della pratica."""
    from app.services.case_indicators import compute_case_indicators
    _get_case(db, case_id)
    return compute_case_indicators(db, case_id)


# ---------- Correzione tracciata dei dati estratti ----------
class CorrectionIn(BaseModel):
    changes: dict = {}
    reason: str = ""


@router.patch("/cases/{case_id}/records/{entity_type}/{entity_id}")
def correct_record(case_id: str, entity_type: str, entity_id: str,
                   payload: CorrectionIn, db: Session = Depends(get_db)):
    """Corregge un dato estratto: salva il nuovo valore e registra l'audit."""
    from app.services import corrections
    _get_case(db, case_id)
    try:
        corrections.apply_corrections(db, case_id, entity_type, entity_id,
                                      payload.changes or {}, reason=payload.reason or "")
    except corrections.CorrectionError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.get("/cases/{case_id}/edits", response_model=List[FieldEditOut])
def list_edits(case_id: str, db: Session = Depends(get_db)):
    """Storico correzioni della pratica."""
    rows = db.query(FieldEdit).filter_by(case_id=case_id).order_by(FieldEdit.created_at.desc()).all()
    return [FieldEditOut(
        id=r.id, entity_type=r.entity_type, entity_id=r.entity_id,
        field=r.field, old_value=r.old_value, new_value=r.new_value,
        reason=r.reason, created_at=r.created_at.isoformat() if r.created_at else "",
    ) for r in rows]


# ---------- Estratto di ruolo AER (cartelle/avvisi) ----------
@router.post("/cases/{case_id}/aer/upload", response_model=TaxDebtStatementOut)
def upload_aer(case_id: str,
               owner_kind: str = Query("person", pattern="^(person|company)$"),
               entity_id: str = Query(""),
               file: UploadFile = File(...),
               db: Session = Depends(get_db)):
    """Carica un estratto di ruolo AER e lo attribuisce a persona o azienda."""
    from app.services import aer_parser
    from app.services import llm

    _get_case(db, case_id)

    debtor_id, company_id, owner_cf = None, None, ""
    if owner_kind == "company":
        comp = db.get(Company, entity_id) if entity_id else None
        if not comp or comp.case_id != case_id:
            raise HTTPException(404, "Azienda non trovata nella pratica")
        company_id = comp.id
        owner_cf = comp.vat or comp.tax_code or ""
    else:
        debtor = db.query(Debtor).filter_by(case_id=case_id).first()
        debtor_id = debtor.id if debtor else None
        owner_cf = debtor.tax_code if debtor else ""

    from app.services.storage import get_storage, make_key, sha256_bytes
    raw = file.file.read()
    digest = sha256_bytes(raw)
    if db.query(Document).filter_by(case_id=case_id, sha256=digest).first():
        raise HTTPException(409, "Questo estratto di ruolo risulta già caricato nella pratica "
                                 "(stesso file). Elimina il precedente se vuoi ricaricarlo.")
    store = get_storage()
    key = make_key(case_id, "cartella_aer", file.filename or "estratto_aer")
    store.save(key, raw, content_type=file.content_type or "application/pdf")
    stored = store.local_path(key)
    doc = Document(case_id=case_id, original_filename=file.filename or "estratto_aer",
                   storage_path=stored, storage_uri=key, content_type=file.content_type or "",
                   size_bytes=len(raw), sha256=digest,
                   status="in_elaborazione", doc_type="cartella_aer")
    db.add(doc)
    db.flush()

    method = "parser"
    try:
        data = aer_parser.parse_pdf(stored)
    except aer_parser.AerParseError as e:
        method = "ai"
        data = llm.extract_from_file(stored, "cartella_aer", client_cf=owner_cf)

    righe = data.get("righe") or []
    if not righe:
        doc.status = "errore"
        doc.error = "Nessuna riga estratta dall'estratto di ruolo."
        db.commit()
        raise HTTPException(422, "Impossibile estrarre righe dall'estratto di ruolo AER.")

    intest = data.get("intestatario") or {}
    doc_cf = intest.get("codice_fiscale") or ""
    cf_mismatch = bool(doc_cf and owner_cf and not fc.same(doc_cf, owner_cf))

    agg = data.get("aggregazioni") or {}
    totali = data.get("totali") or {}
    stmt = TaxDebtStatement(
        case_id=case_id, owner_kind=owner_kind, debtor_id=debtor_id, company_id=company_id,
        codice_fiscale=doc_cf, denominazione=intest.get("denominazione") or "",
        data_elaborazione=data.get("data_elaborazione") or "",
        total_residuo=_f(totali.get("totale_residuo")),
        total_residuo_netto=_f(totali.get("totale_residuo_netto")),
        total_carico_affidato=_f(totali.get("carico_affidato")),
        count_proc_attive=int(agg.get("count_proc_attive") or sum(1 for r in righe if r.get("proc_attive"))),
        quadrature_ok=bool(data.get("quadrature_ok")),
        extraction_method=method, cf_mismatch=cf_mismatch,
        raw_extraction=data, source_document_id=doc.id,
    )
    db.add(stmt)
    db.flush()
    for r in righe:
        db.add(TaxDebtItem(
            statement_id=stmt.id,
            numero_documento=r.get("numero_documento") or "",
            tipo_documento=r.get("tipo_documento") or "",
            ente_creditore=r.get("ente_creditore") or "",
            ente_categoria=r.get("ente_categoria") or aer_parser.ente_categoria(r.get("ente_creditore") or ""),
            data_notifica=r.get("data_notifica") or "",
            carico_affidato=_f(r.get("carico_affidato")), sgravio=_f(r.get("sgravio")),
            gia_pagato=_f(r.get("gia_pagato")), stralcio=_f(r.get("stralcio_def_agevolata")),
            residuo_carico=_f(r.get("residuo_carico")), interessi_mora=_f(r.get("interessi_mora")),
            oneri_diritti=_f(r.get("oneri_diritti")), totale_residuo=_f(r.get("totale_residuo")),
            importo_sospeso=_f(r.get("importo_sospeso")), totale_residuo_netto=_f(r.get("totale_residuo_netto")),
            rateizzato=bool(r.get("rateizzato")), proc_attive=bool(r.get("proc_attive")),
            def_agevolata=bool(r.get("def_agevolata")), needs_review=bool(r.get("needs_review")),
        ))
    doc.status = "normalizzato"
    doc.num_pages = len(righe)
    db.commit()
    db.refresh(stmt)
    return stmt


@router.delete("/cases/{case_id}/aer/{stmt_id}")
def delete_aer(case_id: str, stmt_id: str, db: Session = Depends(get_db)):
    st = db.get(TaxDebtStatement, stmt_id)
    if not st or st.case_id != case_id:
        raise HTTPException(404, "Estratto AER non trovato")
    db.delete(st)
    db.commit()
    return {"ok": True}


def _f(v) -> float:
    try:
        return float(v) if v is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


# ---------- Debitore (anagrafica + economici) ----------
@router.put("/cases/{case_id}/debtor", response_model=DebtorOut)
@router.patch("/cases/{case_id}/debtor", response_model=DebtorOut)
def upsert_debtor(case_id: str, payload: DebtorIn, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    if not debtor:
        debtor = Debtor(case_id=case_id)
        db.add(debtor)
    # Aggiornamento parziale sicuro: esclude i campi omessi
    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        if v is not None:
            setattr(debtor, k, v)
    first = getattr(debtor, "first_name", "") or ""
    last = getattr(debtor, "last_name", "") or ""
    full = f"{first} {last}".strip()
    if full:
        case.client_name = full
    if getattr(debtor, "tax_code", None):
        case.client_tax_code = debtor.tax_code
    db.commit()
    db.refresh(debtor)
    return debtor


# ---------- Aziende del cliente ----------
def _apply_company(comp: Company, payload: CompanyIn):
    for k, v in payload.model_dump(exclude={"members"}).items():
        setattr(comp, k, v)
    comp.members.clear()
    for m in payload.members:
        comp.members.append(CompanyMember(**m.model_dump()))


def _sync_case_header(case: Case, payload: CompanyIn):
    if payload.role == "cliente":
        if payload.name:
            case.client_name = payload.name
        if payload.vat or payload.tax_code:
            case.client_tax_code = payload.vat or payload.tax_code


@router.put("/cases/{case_id}/company", response_model=CompanyOut)
def upsert_client_company(case_id: str, payload: CompanyIn, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    comp = db.query(Company).filter_by(case_id=case_id, role="cliente").first()
    if not comp:
        comp = Company(case_id=case_id, role="cliente")
        db.add(comp)
    _apply_company(comp, payload)
    _sync_case_header(case, payload)
    db.commit()
    db.refresh(comp)
    return comp


@router.post("/cases/{case_id}/companies", response_model=CompanyOut)
def create_company(case_id: str, payload: CompanyIn, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    comp = Company(case_id=case_id, role=payload.role or "cliente")
    db.add(comp)
    _apply_company(comp, payload)
    _sync_case_header(case, payload)
    db.commit()
    db.refresh(comp)
    return comp


@router.put("/cases/{case_id}/companies/{cid}", response_model=CompanyOut)
def update_company(case_id: str, cid: str, payload: CompanyIn, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    comp = db.get(Company, cid)
    if not comp or comp.case_id != case_id:
        raise HTTPException(404, "Azienda non trovata")
    _apply_company(comp, payload)
    _sync_case_header(case, payload)
    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/cases/{case_id}/companies/{cid}")
def delete_company(case_id: str, cid: str, db: Session = Depends(get_db)):
    comp = db.get(Company, cid)
    if comp and comp.case_id == case_id:
        db.delete(comp)
        db.commit()
    return {"ok": True}


@router.post("/cases/{case_id}/companies/{cid}/promote", response_model=CompanyOut)
def promote_company(case_id: str, cid: str, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    comp = db.get(Company, cid)
    if not comp or comp.case_id != case_id:
        raise HTTPException(404, "Azienda non trovata")
    comp.role = "cliente"
    if comp.name:
        case.client_name = comp.name
    if comp.vat or comp.tax_code:
        case.client_tax_code = comp.vat or comp.tax_code
    db.commit()
    db.refresh(comp)
    return comp


# ---------- Immobili ----------
@router.post("/cases/{case_id}/real-estates", response_model=RealEstateOut)
def add_real_estate(case_id: str, payload: RealEstateIn, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    re = RealEstate(case_id=case_id, **payload.model_dump())
    db.add(re)
    db.commit()
    db.refresh(re)
    return re


@router.delete("/cases/{case_id}/real-estates/{re_id}")
def del_real_estate(case_id: str, re_id: str, db: Session = Depends(get_db)):
    re = db.get(RealEstate, re_id)
    if re:
        db.delete(re)
        db.commit()
    return {"ok": True}


class PrimaryResidenceToggle(BaseModel):
    is_primary_residence: bool


@router.patch("/cases/{case_id}/real-estates/{re_id}/primary-residence", response_model=RealEstateOut)
def set_primary_residence(case_id: str, re_id: str, payload: PrimaryResidenceToggle,
                          db: Session = Depends(get_db)):
    from app.services.pipeline_service import _valore_catastale
    re = db.get(RealEstate, re_id)
    if not re:
        raise HTTPException(404, "Immobile non trovato")
    re.is_primary_residence = payload.is_primary_residence
    re.cadastral_value = _valore_catastale(
        re.cadastral_income, re.category, re.ownership_share, re.is_primary_residence
    )
    db.commit()
    db.refresh(re)
    return re


# ---------- Veicoli ----------
@router.post("/cases/{case_id}/vehicles", response_model=VehicleOut)
def add_vehicle(case_id: str, payload: VehicleIn, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    v = Vehicle(case_id=case_id, **payload.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.delete("/cases/{case_id}/vehicles/{v_id}")
def del_vehicle(case_id: str, v_id: str, db: Session = Depends(get_db)):
    v = db.get(Vehicle, v_id)
    if v:
        db.delete(v)
        db.commit()
    return {"ok": True}


# ---------- Openapi & Visure ----------
class OpenapiSearchRequest(BaseModel):
    source: str = "camerale"
    query: str = ""
    params: dict = {}


@router.post("/cases/{case_id}/openapi/search")
def openapi_search(case_id: str, payload: OpenapiSearchRequest, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    query = fc.normalize(payload.query) or case.client_tax_code
    if not query:
        raise HTTPException(422, "Serve una P.IVA o un codice fiscale.")
    req = EnrichmentRequest(
        case_id=case_id, source=payload.source, query=query,
        input_params=payload.params or {},
        is_sandbox="test." in settings.openapi_base_url, status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    from app.workers.openapi_tasks import start_enrichment
    start_enrichment.delay(req.id)
    return {"request_id": req.id, "status": req.status,
            "sandbox": req.is_sandbox, "message": "Richiesta avviata. Controlla lo stato."}


@router.get("/cases/{case_id}/openapi/requests", response_model=List[EnrichmentRequestOut])
def openapi_list(case_id: str, db: Session = Depends(get_db)):
    _get_case(db, case_id)
    reqs = db.query(EnrichmentRequest).filter_by(case_id=case_id).order_by(
        EnrichmentRequest.created_at.desc()).all()
    return [EnrichmentRequestOut(
        id=r.id, source=r.source, query=r.query, status=r.status,
        sandbox=r.is_sandbox, error=r.error or "",
        mapped_data=r.mapped_data or {}, raw_response=r.raw_response or {},
        created_at=r.created_at.isoformat() if r.created_at else "",
    ) for r in reqs]


@router.get("/openapi/catalogo")
def openapi_catalogo():
    from app.services import openapi_client as oa
    try:
        visure = oa.list_visure()
    except oa.OpenapiError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Errore chiamando Openapi: {e}")
    camerali = [v for v in visure if "camera" in (v.get("nome_categoria", "") + v.get("nome_visura", "")).lower()]
    return {"totale": len(visure), "camerali": camerali, "tutte": visure}


@router.get("/cases/{case_id}/openapi/requests/{req_id}", response_model=EnrichmentRequestOut)
def openapi_get(case_id: str, req_id: str, db: Session = Depends(get_db)):
    r = db.get(EnrichmentRequest, req_id)
    if not r or r.case_id != case_id:
        raise HTTPException(404, "Richiesta non trovata")
    return EnrichmentRequestOut(
        id=r.id, source=r.source, query=r.query, status=r.status,
        sandbox=r.is_sandbox, error=r.error or "",
        mapped_data=r.mapped_data or {}, raw_response=r.raw_response or {},
        created_at=r.created_at.isoformat() if r.created_at else "",
    )


class CompanyFillRequest(BaseModel):
    identifier: str = ""
    level: str = "advanced"


@router.post("/cases/{case_id}/company/fill")
def company_fill(case_id: str, payload: CompanyFillRequest, db: Session = Depends(get_db)):
    from app.services import company_client as cc
    case = _get_case(db, case_id)
    ident = fc.normalize(payload.identifier) or case.client_tax_code
    if not ident:
        raise HTTPException(422, "Manca la partita IVA o il codice fiscale dell'azienda.")
    if not fc.is_valid_format(ident):
        raise HTTPException(422, "Partita IVA / codice fiscale non valido.")
    try:
        raw = cc.fetch_start(ident) if payload.level == "start" else cc.fetch_advanced(ident)
    except cc.CompanyError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(502, f"Errore chiamando Company: {e}")
    mapped = cc.map_company(raw)
    if not mapped:
        raise HTTPException(404, "Nessun dato aziendale trovato per questo identificatore.")
    db.add(EnrichmentRequest(
        case_id=case_id, source="company", query=ident,
        input_params={"level": payload.level},
        status="done", is_sandbox="test." in (settings.company_base_url or ""),
        raw_response=raw,
    ))
    db.commit()
    return {"identifier": ident, "level": payload.level, "data": mapped}


class CompanyImportRequest(BaseModel):
    data: dict = {}


@router.post("/cases/{case_id}/company/import")
def company_import(case_id: str, payload: CompanyImportRequest, db: Session = Depends(get_db)):
    case = _get_case(db, case_id)
    d = payload.data or {}
    if not (d.get("denominazione") or d.get("partita_iva") or d.get("codice_fiscale")):
        raise HTTPException(422, "Dati azienda mancanti.")
    vat = (d.get("partita_iva") or "").strip()
    tax = (d.get("codice_fiscale") or "").strip()
    comp = None
    for c in db.query(Company).filter_by(case_id=case_id, role="cliente").all():
        if (vat and c.vat == vat) or (tax and c.tax_code == tax):
            comp = c
            break
    if not comp:
        comp = Company(case_id=case_id, role="cliente")
        db.add(comp)
    comp.name = d.get("denominazione") or comp.name or ""
    comp.vat = vat
    comp.tax_code = tax
    comp.pec = d.get("pec") or ""
    comp.legal_address = d.get("sede_legale") or ""
    comp.status = d.get("stato_attivita") or ("cessata" if d.get("cessata") else "")
    comp.legal_form = d.get("forma_giuridica") or ""
    comp.ateco = d.get("ateco") or ""
    comp.rea = d.get("rea") or ""
    comp.cciaa = d.get("cciaa") or ""
    comp.capital = _num(d.get("capitale_sociale"))
    comp.fatturato = _num(d.get("fatturato"))
    comp.dipendenti = int(_num(d.get("dipendenti")))
    comp.patrimonio_netto = _num(d.get("patrimonio_netto"))
    comp.anno_bilancio = str(d.get("anno_bilancio") or "")
    comp.members.clear()
    db.flush()
    case_cf = (case.client_tax_code or "").upper()
    for s in d.get("soci") or []:
        scf = (s.get("codice_fiscale") or "")
        comp.members.append(CompanyMember(
            name=s.get("denominazione") or "",
            tax_code=scf,
            quota_percent=_num(s.get("quota_percentuale")),
            is_client=bool(scf) and scf.upper() == case_cf,
        ))
    db.commit()
    db.refresh(comp)
    return {"ok": True, "company_id": comp.id}


def _num(v):
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0
