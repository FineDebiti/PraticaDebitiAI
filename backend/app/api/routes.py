import os
import uuid
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.config import settings
from app.models import Case, Document, Organization
from app.schemas.dto import CaseCreate, CaseOut, CaseDetail, DocumentOut
from app.workers.tasks import process_document
from app.services import fiscal_code as fc

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "ocr": settings.ocr_provider, "llm": settings.llm_provider}


@router.post("/cases", response_model=CaseOut)
def create_case(payload: CaseCreate, db: Session = Depends(get_db)):
    """Crea la pratica E il debitore (unica fonte di verita per i dati anagrafici).
    Gestisce persona fisica (nome+cognome+CF) e azienda (denominazione+P.IVA)."""
    from app.models import Debtor

    # Il codice fiscale / P.IVA e il PUNTO FERMO: obbligatorio e validato.
    cf = fc.normalize(payload.client_tax_code)
    if not cf:
        raise HTTPException(422, "Il codice fiscale / partita IVA e obbligatorio.")
    if not fc.is_valid_format(cf):
        raise HTTPException(422, "Codice fiscale/P.IVA non valido: 16 caratteri (persona) o 11 cifre (azienda).")

    kind = payload.client_kind if payload.client_kind in ("persona", "azienda") else "persona"
    if kind == "persona":
        last = (payload.last_name or "").strip()
        first = (payload.first_name or "").strip()
        if not last:
            raise HTTPException(422, "Il cognome e obbligatorio per una persona fisica.")
        display_name = f"{first} {last}".strip()
        debtor_kwargs = dict(first_name=first, last_name=last, tax_code=cf, client_type="privato")
    else:  # azienda
        denom = (payload.denomination or "").strip()
        if not denom:
            raise HTTPException(422, "La denominazione e obbligatoria per un'azienda.")
        display_name = denom
        # per l'azienda mettiamo la denominazione in last_name cosi _full_name la usa come $0
        debtor_kwargs = dict(first_name="", last_name=denom, tax_code=cf, client_type="societa")

    org = db.query(Organization).first()
    if not org:
        org = Organization(); db.add(org); db.commit()
    code = payload.code or f"PRAT-{uuid.uuid4().hex[:6].upper()}"
    case = Case(
        organization_id=org.id, code=code, client_name=display_name,
        client_tax_code=cf, notes=payload.notes,
    )
    db.add(case)
    db.flush()  # serve l'id per il debtor
    db.add(Debtor(case_id=case.id, **debtor_kwargs))  # crea SUBITO il debitore
    db.commit()
    db.refresh(case)
    return case


@router.get("/cases", response_model=list[CaseOut])
def list_cases(db: Session = Depends(get_db)):
    return db.query(Case).order_by(Case.created_at.desc()).all()


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Pratica non trovata")
    return case


@router.post("/cases/{case_id}/documents")
def upload_document(case_id: str, file: UploadFile = File(...),
                    doc_type: str = Form(""), db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Pratica non trovata")
    # se l'upload arriva da un tasto dedicato (es. "Carica bilancio"), il tipo è
    # gia noto -> lo imponiamo e il worker salta la classificazione AI.
    from app.services.doc_prompts import DOC_TYPES
    from app.services.storage import get_storage, make_key, sha256_bytes
    forced = doc_type if doc_type in DOC_TYPES else "da_classificare"

    data = file.file.read()
    digest = sha256_bytes(data)
    # DEDUPLICA: stesso file già nella pratica -> non riprocessare, avvisa.
    existing = db.query(Document).filter_by(case_id=case_id, sha256=digest).first()
    if existing:
        return {"id": existing.id, "duplicate": True,
                "original_filename": existing.original_filename, "status": existing.status,
                "doc_type": existing.doc_type}

    store = get_storage()
    key = make_key(case_id, forced, file.filename or "documento")
    store.save(key, data, content_type=file.content_type or "")
    doc = Document(
        case_id=case_id, original_filename=file.filename or "documento",
        storage_path=store.local_path(key), storage_uri=key,
        content_type=file.content_type or "", size_bytes=len(data), sha256=digest,
        status="caricato", doc_type=forced,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    process_document.delay(doc.id)
    return {"id": doc.id, "duplicate": False, "original_filename": doc.original_filename,
            "status": doc.status, "doc_type": doc.doc_type}


@router.get("/cases/{case_id}/documents", response_model=list[DocumentOut])
def list_documents(case_id: str, db: Session = Depends(get_db)):
    return db.query(Document).filter_by(case_id=case_id).order_by(Document.created_at.desc()).all()


@router.delete("/cases/{case_id}/documents/{doc_id}")
def delete_document(case_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Elimina un documento (record + file). I dati già estratti nelle sezioni
    (AER/CR/bilancio) restano: il documento è solo la fonte caricata."""
    from app.services.storage import get_storage
    doc = db.get(Document, doc_id)
    if not doc or doc.case_id != case_id:
        raise HTTPException(404, "Documento non trovato")
    if doc.storage_uri:
        try:
            get_storage().delete(doc.storage_uri)
        except Exception:
            pass
    db.delete(doc)
    db.commit()
    return {"ok": True}


@router.get("/cases/{case_id}/documents/{doc_id}/file")
def download_document(case_id: str, doc_id: str, db: Session = Depends(get_db)):
    """Ri-scarica il file ORIGINALE. Locale: stream; GCS: redirect a signed URL."""
    from fastapi.responses import Response, RedirectResponse, FileResponse
    from app.services.storage import get_storage
    doc = db.get(Document, doc_id)
    if not doc or doc.case_id != case_id:
        raise HTTPException(404, "Documento non trovato")
    store = get_storage()
    media = doc.content_type or "application/octet-stream"
    if doc.storage_uri:
        signed = store.url(doc.storage_uri)
        if signed:                      # GCS: redirect al link temporaneo
            return RedirectResponse(signed)
        data = store.load(doc.storage_uri)
        return Response(content=data, media_type=media,
                        headers={"Content-Disposition": f'inline; filename="{doc.original_filename}"'})
    # documenti vecchi (pre-storage): serviti dal path locale legacy
    if doc.storage_path and os.path.exists(doc.storage_path):
        return FileResponse(doc.storage_path, media_type=media, filename=doc.original_filename)
    raise HTTPException(410, "File originale non più disponibile")
