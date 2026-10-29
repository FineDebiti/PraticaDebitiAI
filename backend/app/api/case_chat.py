"""Router per la chat di assistenza tecnica e spiegazione dell'analisi di pratica (LLM locale)."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.models import Case
from app.services import case_chat_service

router = APIRouter()


class ChatMessageOut(BaseModel):
    id: str
    case_id: str
    sender: str
    content: str
    context_meta: Optional[Dict[str, Any]] = None
    created_at: datetime


class SendChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Domanda o richiesta di chiarimento dell'operatore")


class SendChatMessageResponse(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut


class ChatHistoryResponse(BaseModel):
    case_id: str
    total: int
    messages: List[ChatMessageOut]


@router.get("/cases/{case_id}/chat", response_model=ChatHistoryResponse)
def get_chat_history(case_id: str, db: Session = Depends(get_db)):
    """Restituisce la cronologia completa dei messaggi scambiati tra l'operatore e l'AI per questa pratica."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Pratica non trovata")

    msgs = case_chat_service.get_case_chat_history(db, case_id)
    return {
        "case_id": case_id,
        "total": len(msgs),
        "messages": msgs,
    }


@router.post("/cases/{case_id}/chat", response_model=SendChatMessageResponse)
def send_chat_message(case_id: str, req: SendChatMessageRequest, db: Session = Depends(get_db)):
    """Invia un messaggio all'LLM locale con il contesto completo del fascicolo e restituisce la spiegazione."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Pratica non trovata")

    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Il messaggio non può essere vuoto.")

    user_msg, asst_msg = case_chat_service.ask_case_chat(db, case_id, req.message.strip())
    return {
        "user_message": user_msg,
        "assistant_message": asst_msg,
    }


@router.delete("/cases/{case_id}/chat")
def clear_chat_history(case_id: str, db: Session = Depends(get_db)):
    """Cancella la cronologia della chat per questa specifica pratica."""
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Pratica non trovata")

    deleted = case_chat_service.clear_case_chat_history(db, case_id)
    return {
        "success": True,
        "deleted_count": deleted,
    }

