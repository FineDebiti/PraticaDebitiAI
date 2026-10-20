from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_db
from app.services import rule_engine

router = APIRouter()


class SynthesizeRuleRequest(BaseModel):
    case_id: Optional[str] = None
    scope: str = Field(default="global", description="Codice ambito/capitolo (es. global, cap_5_1)")
    scope_title: str = Field(default="Generale", description="Titolo leggibile dell'ambito")
    user_comment: str = Field(..., description="Osservazione o correzione dell'operatore")
    current_context_text: Optional[str] = Field(default="", description="Snippet di dati del report/capitolo")
    author: Optional[str] = Field(default="Team Studio Bentivegna")


class CreateRuleRequest(BaseModel):
    case_id: Optional[str] = None
    client_name: Optional[str] = ""
    scope: str = "global"
    scope_title: str = "Generale"
    category: str = "Generale"
    user_comment: str = ""
    rule_title: str
    rule_prompt: str
    is_active: bool = True
    author: Optional[str] = "Team Studio Bentivegna"


class UpdateRuleRequest(BaseModel):
    rule_title: Optional[str] = None
    rule_prompt: Optional[str] = None
    category: Optional[str] = None
    scope: Optional[str] = None
    scope_title: Optional[str] = None
    is_active: Optional[bool] = None
    author: Optional[str] = None


class RuleOut(BaseModel):
    id: str
    case_id: Optional[str] = None
    client_name: str = ""
    scope: str
    scope_title: str
    category: str
    user_comment: str
    rule_title: str
    rule_prompt: str
    is_active: bool
    author: str
    created_at: datetime
    updated_at: datetime


@router.post("/studio-rules/synthesize")
def synthesize_rule(req: SynthesizeRuleRequest, db: Session = Depends(get_db)):
    """Invia il feedback/correzione dell'analista a Qwen per formalizzare una regola operativa di studio."""
    if not req.user_comment.strip():
        raise HTTPException(400, "Il commento o istruzione non può essere vuoto.")
    res = rule_engine.synthesize_rule_from_feedback(
        db=db,
        scope=req.scope,
        scope_title=req.scope_title,
        user_comment=req.user_comment,
        case_id=req.case_id,
        current_context_text=req.current_context_text,
        author=req.author,
    )
    return res


@router.post("/studio-rules", response_model=RuleOut)
def create_rule(req: CreateRuleRequest, db: Session = Depends(get_db)):
    """Salva una nuova regola nel Playbook dello Studio."""
    if not req.rule_prompt.strip() or not req.rule_title.strip():
        raise HTTPException(400, "Titolo e testo della regola sono obbligatori.")
    rule = rule_engine.create_rule(db, req.model_dump())
    return rule


@router.get("/studio-rules")
def get_rules(
    active_only: bool = Query(False),
    scope: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Restituisce l'elenco delle regole salvate con statistiche."""
    all_rules = rule_engine.list_rules(db, active_only=False)
    filtered = rule_engine.list_rules(db, active_only=active_only, scope=scope, category=category)
    active_count = sum(1 for r in all_rules if r.is_active)
    return {
        "total": len(all_rules),
        "active_count": active_count,
        "rules": [
            {
                "id": r.id,
                "case_id": r.case_id,
                "client_name": r.client_name,
                "scope": r.scope,
                "scope_title": r.scope_title,
                "category": r.category,
                "user_comment": r.user_comment,
                "rule_title": r.rule_title,
                "rule_prompt": r.rule_prompt,
                "is_active": r.is_active,
                "author": r.author,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            }
            for r in filtered
        ],
    }


@router.patch("/studio-rules/{rule_id}")
def update_rule(rule_id: str, req: UpdateRuleRequest, db: Session = Depends(get_db)):
    """Aggiorna lo stato (es. attiva/disattiva con toggle) o il testo di una regola."""
    rule = rule_engine.update_rule(db, rule_id, req.model_dump(exclude_unset=True))
    if not rule:
        raise HTTPException(404, "Regola non trovata.")
    return {
        "id": rule.id,
        "is_active": rule.is_active,
        "rule_title": rule.rule_title,
        "rule_prompt": rule.rule_prompt,
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


@router.delete("/studio-rules/{rule_id}")
def delete_rule(rule_id: str, db: Session = Depends(get_db)):
    """Rimuove definitivamente una regola dal Playbook."""
    success = rule_engine.delete_rule(db, rule_id)
    if not success:
        raise HTTPException(404, "Regola non trovata.")
    return {"ok": True, "id": rule_id}
