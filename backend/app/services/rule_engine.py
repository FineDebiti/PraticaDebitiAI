"""Servizio di Addestramento Continuo e Playbook dello Studio.

Consente al legale e al responsabile analisi di:
1. Formalizzare regole operative a partire da feedback o correzioni su singoli capitoli o generali;
2. Salvare e gestire le regole nel database PostgreSQL;
3. Iniettare automaticamente le regole attive nei prompt di Qwen (super-analisi, report, pipeline)
   per prevenire la ripetizione di errori passati in contesti analoghi.
"""
import time
import json
import logging
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models import StudioRule, Case
from app.services.llm_providers import REGISTRY
from app.services.llm_providers.base import parse_json
from app.config import settings

logger = logging.getLogger("dossierlex.rule_engine")


def get_active_rules(db: Session, target_scope: Optional[str] = None) -> List[StudioRule]:
    """Recupera le regole attive, filtrando per scope specifico o globale se indicato."""
    query = db.query(StudioRule).filter(StudioRule.is_active == True)
    if target_scope and target_scope != "global":
        query = query.filter((StudioRule.scope == target_scope) | (StudioRule.scope == "global"))
    return query.order_by(StudioRule.created_at.asc()).all()


def build_active_rules_prompt_block(db: Session, target_scope: Optional[str] = None) -> str:
    """Genera la sezione di prompt con le regole e la memoria operativa dello studio da iniettare a Qwen."""
    rules = get_active_rules(db, target_scope)
    if not rules:
        return ""

    lines = [
        "",
        "================================================================================",
        "LINEE GUIDA E MEMORIA OPERATIVA DELLO STUDIO BENTIVEGNA (ADDESTRAMENTO CONTINUO):",
        "Le seguenti regole tassative sono state emanate dall'avvocato e dal responsabile analisi",
        "a partire da correzioni e prassi verificate nei fascicoli precedenti.",
        "DEVI APPLICARE RIGOROSAMENTE queste regole per non ripetere gli errori segnalati:",
        "================================================================================",
    ]

    for idx, r in enumerate(rules, start=1):
        scope_lbl = f"[{r.scope_title}]" if r.scope_title else f"[{r.scope}]"
        cat_lbl = f"({r.category})" if r.category else ""
        lines.append(f"{idx}. {scope_lbl} {cat_lbl} {r.rule_title}:")
        lines.append(f"   DIRETTIVA: {r.rule_prompt}")

    lines.append("================================================================================")
    lines.append("")
    return "\n".join(lines)


def synthesize_rule_from_feedback(
    db: Session,
    scope: str,
    scope_title: str,
    user_comment: str,
    case_id: Optional[str] = None,
    current_context_text: Optional[str] = None,
    author: Optional[str] = None,
) -> Dict[str, Any]:
    """Invia il feedback/correzione a Qwen per formalizzare una regola operativa per il Playbook dello Studio."""
    client_name = ""
    if case_id:
        case = db.get(Case, case_id)
        if case:
            client_name = case.client_name or ""

    author_name = author or "Responsabile Analisi / Avv. Bentivegna"

    prompt = f"""Sei il supervisore del Playbook dello Studio Legale Avv. Aurelio Bentivegna & Partners, specializzato in diritto della crisi d'impresa e sovraindebitamento (CCII).

Un componente del team ({author_name}) ha inserito un'osservazione/correzione per addestrare il sistema a non ripetere più errori su questa tipologia di dati.

AMBITO / CAPITOLO DI RIFERIMENTO:
{scope_title} (Codice: {scope})

FASCICOLO ATTUALE (se applicabile):
{client_name or "Generale"}

CONTESTO ATTUALE RILEVATO:
{current_context_text or "Dati e tabelle del fascicolo analizzato"}

INDICAZIONE / ISTRUZIONE CORRETTIVA DATA DALL'ANALISTA:
"{user_comment}"

COMPITO:
Analizza l'errore o l'istruzione segnalata e formalizza una REGOLA OPERATIVA GENERALE per lo Studio, chiara e priva di ambiguità, che guiderà le future estrazioni, riclassificazioni o sintesi del modello AI.

RISPONDI ESCLUSIVAMENTE con un oggetto JSON valido privo di altri testi, secondo questo schema esatto:
{{
  "rule_title": "Titolo sintetico ed esplicativo della regola (max 8-10 parole)",
  "rule_prompt": "Testo tassativo della direttiva da iniettare nel prompt per guidare l'AI in situazioni analoghe (2-4 frasi chiare e pratiche)",
  "category": "Bilancio" | "Fiscale/AER" | "Banche/CR" | "Soci/Garanzie" | "CCII/Scenari" | "Generale",
  "reasoning": "Breve spiegazione del perché questa regola evita errori futuri e quale prassi dello studio adotta"
}}
"""

    prov = REGISTRY.get(settings.llm_provider) or REGISTRY.get("lmstudio")
    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"

    synthesized = None
    if prov:
        try:
            logger.info("Sintesi regola tramite LLM provider=%s model=%s scope=%s", prov.name, target_model, scope)
            res = prov.extract(file_path=None, mime="text/plain", prompt=prompt, model=target_model)
            if res.ok and isinstance(res.data, dict):
                synthesized = res.data
        except Exception as exc:
            logger.warning("Errore durante sintesi regola con LLM: %s. Uso fallback euristico.", exc)

    # Fallback sicuro se l'LLM è offline o restituisce errore: non blocchiamo l'utente!
    if not synthesized or not synthesized.get("rule_prompt"):
        cat = "Generale"
        if "bilanc" in scope.lower() or "5.1" in scope:
            cat = "Bilancio"
        elif "ader" in scope.lower() or "5.2" in scope or "fisc" in scope.lower():
            cat = "Fiscale/AER"
        elif "cr" in scope.lower() or "banc" in scope.lower():
            cat = "Banche/CR"

        synthesized = {
            "rule_title": f"Regola su {scope_title}",
            "rule_prompt": f"Su {scope_title}: {user_comment.strip()}",
            "category": cat,
            "reasoning": "Regola creata direttamente dalle indicazioni dell'operatore.",
        }

    return {
        "case_id": case_id,
        "client_name": client_name,
        "scope": scope,
        "scope_title": scope_title,
        "user_comment": user_comment,
        "rule_title": synthesized.get("rule_title", f"Regola su {scope_title}"),
        "rule_prompt": synthesized.get("rule_prompt", user_comment),
        "category": synthesized.get("category", "Generale"),
        "reasoning": synthesized.get("reasoning", ""),
        "author": author_name,
    }


def list_rules(
    db: Session,
    active_only: bool = False,
    scope: Optional[str] = None,
    category: Optional[str] = None,
) -> List[StudioRule]:
    """Elenco completo delle regole salvate nel Playbook dello Studio."""
    query = db.query(StudioRule)
    if active_only:
        query = query.filter(StudioRule.is_active == True)
    if scope:
        query = query.filter(StudioRule.scope == scope)
    if category:
        query = query.filter(StudioRule.category == category)
    return query.order_by(StudioRule.created_at.desc()).all()


def create_rule(db: Session, data: Dict[str, Any]) -> StudioRule:
    """Persiste una nuova regola operativa nel Playbook."""
    rule = StudioRule(
        case_id=data.get("case_id"),
        client_name=data.get("client_name") or "",
        scope=data.get("scope") or "global",
        scope_title=data.get("scope_title") or "Generale",
        category=data.get("category") or "Generale",
        user_comment=data.get("user_comment") or "",
        rule_title=data.get("rule_title") or "Nuova Regola",
        rule_prompt=data.get("rule_prompt") or "",
        is_active=data.get("is_active", True),
        author=data.get("author") or "Team Studio Bentivegna",
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    logger.info("Creata nuova regola di studio id=%s scope=%s title=%s", rule.id, rule.scope, rule.rule_title)
    return rule


def update_rule(db: Session, rule_id: str, data: Dict[str, Any]) -> Optional[StudioRule]:
    """Aggiorna testo o stato attivo/inattivo di una regola esistente."""
    rule = db.get(StudioRule, rule_id)
    if not rule:
        return None

    for field in ("rule_title", "rule_prompt", "category", "scope", "scope_title", "is_active", "author"):
        if field in data and data[field] is not None:
            setattr(rule, field, data[field])

    db.commit()
    db.refresh(rule)
    logger.info("Aggiornata regola di studio id=%s (is_active=%s)", rule.id, rule.is_active)
    return rule


def delete_rule(db: Session, rule_id: str) -> bool:
    """Rimuove definitivamente una regola dal Playbook."""
    rule = db.get(StudioRule, rule_id)
    if not rule:
        return False
    db.delete(rule)
    db.commit()
    logger.info("Eliminata regola di studio id=%s", rule_id)
    return True

