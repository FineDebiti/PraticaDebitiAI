"""Servizio di Chat e Assistente AI di Pratica DossierLex.

Consente al legale o all'analista di dialogare in linguaggio naturale con l'LLM locale
per comprendere il processo di analisi, audit e riclassificazione documentale:
1. Spiega la provenienza di specifici dati o tabelle del report;
2. Indica i documenti di fonte esatti (bilanci, visure, AdER, CR, ecc.);
3. Dettaglia i calcoli matematici e contabili (MOL, PFN, variazione debiti);
4. Illustra le regole dello studio applicate;
5. Suggerisce formulazioni precise per le istruzioni di revisione.
"""
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import httpx
from sqlalchemy.orm import Session

from app.models import (
    Case,
    Company,
    CompanyMember,
    Debtor,
    Document,
    FinancialStatement,
    CreditExposure,
    CreditReportSummary,
    TaxDebtStatement,
    RealEstate,
    Vehicle,
    StudioRule,
    CasePreanalysisReport,
    CaseChatMessage,
)
from app.services.report_regenerator import get_or_create_preanalysis_report
from app.services.llm_providers import REGISTRY
from app.config import settings

logger = logging.getLogger("dossierlex.case_chat")


def build_case_chat_context(db: Session, case_id: str) -> Dict[str, Any]:
    """Costruisce un quadro informativo mirato e compatto della pratica, ottimizzato per il context window."""
    case = db.get(Case, case_id)
    if not case:
        return {}

    company = db.query(Company).filter_by(case_id=case_id).first()
    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    docs = db.query(Document).filter_by(case_id=case_id).all()
    fss = db.query(FinancialStatement).filter_by(case_id=case_id).order_by(FinancialStatement.fiscal_year_end).all()
    cr = db.query(CreditReportSummary).filter_by(case_id=case_id).first()
    statements = db.query(TaxDebtStatement).filter_by(case_id=case_id).all()
    real_estates = db.query(RealEstate).filter_by(case_id=case_id).all()

    # Report di preanalisi attuale
    rep_record, rep_data = get_or_create_preanalysis_report(db, case_id)

    # Regole studio attive
    rules = db.query(StudioRule).filter(
        (StudioRule.case_id == case_id) | (StudioRule.case_id == None),
        StudioRule.is_active == True,
    ).all()

    # Catalogo compatto dei documenti salienti (evitando dump enormi)
    doc_catalog = []
    seen_files = set()
    for d in docs:
        fname = d.original_filename or f"Doc_{d.id[:6]}"
        if fname in seen_files:
            continue
        seen_files.add(fname)
        doc_catalog.append(f"• [{d.doc_type or 'documento'}] {fname} ({d.num_pages} pag., {d.status})")

    # Sintesi economica per esercizio (dal bilancio)
    esercizi_sintesi = []
    for fs in fss:
        ce = fs.raw_extraction.get("conto_economico", {}) if getattr(fs, "raw_extraction", None) else {}
        esercizi_sintesi.append({
            "esercizio": fs.fiscal_year_end,
            "tipo": fs.statement_type,
            "ricavi_a1": ce.get("ricavi_vendite") or fs.revenues,
            "valore_produzione_a": ce.get("valore_produzione"),
            "costi_produzione_b": ce.get("costi_produzione"),
            "utile_perdita": ce.get("utile_perdita") or fs.net_result,
            "oneri_finanziari": ce.get("oneri_finanziari"),
        })

    # Dati estratti del report preanalisi (solo sezioni chiave)
    c2 = rep_data.get("capitolo_2_profilo", {}) if rep_data else {}
    c5 = rep_data.get("capitolo_5_indebitamento", {}) if rep_data else {}
    table_5_1 = c5.get("tabella_5_1", {})
    deb_rows = [
        {"voce": r.get("voce"), "valori": r.get("valori"), "variazione": r.get("variazione")}
        for r in table_5_1.get("righe", [])
    ]

    return {
        "pratica": {
            "codice": case.code,
            "cliente": case.client_name,
            "cf_piva": case.client_tax_code,
            "priorita": case.priority,
        },
        "anagrafica_report_cap2": {
            "denominazione": c2.get("denominazione"),
            "forma_giuridica": c2.get("forma_giuridica"),
            "rea": c2.get("rea"),
            "sede_legale": c2.get("sede_legale"),
            "codice_ateco": c2.get("codice_ateco"),
            "capitale_sociale": c2.get("capitale_sociale"),
            "soci": c2.get("soci", []),
        },
        "documenti_fascicolo": doc_catalog[:25],
        "bilanci_storici": esercizi_sintesi,
        "debiti_capitolo_5_1": deb_rows,
        "totali_debiti_5_1": table_5_1.get("totali", {}),
        "centrale_rischi": {
            "esposizione_totale": cr.total_exposure if cr else 0.0,
            "garanzie": cr.total_guarantees if cr else 0.0,
            "ha_sofferenze": cr.has_sofferenze if cr else False,
        } if cr else "Nessuna sofferenza segnalata",
        "ader_fiscale": {
            "totale_cartelle": sum(s.total_amount or 0.0 for s in statements),
            "atti": len(statements),
        } if statements else "Nessun ruolo pendente",
        "patrimonio": f"{len(real_estates)} unita immobiliari censite",
        "regole_studio_applicate": [
            f"[{r.scope}] {r.rule_title}: {r.rule_prompt}"
            for r in rules
        ],
    }


def _build_system_prompt(ctx: Dict[str, Any]) -> str:
    """Genera il prompt di sistema strutturato con il contesto completo della pratica."""
    client_name = ctx.get("case", {}).get("client_name") or "Cliente"
    case_code = ctx.get("case", {}).get("code") or "PRATICA"
    ctx_json = json.dumps(ctx, ensure_ascii=False, indent=2)

    return f"""Sei DossierLex AI Assistant, il supervisore e consulente tecnico esperto di analisi economico-finanziaria, audit documentale e diritto della crisi d'impresa (CCII) dello Studio Legale Avv. Aurelio Bentivegna & Partners.

STAI ASSISTENDO L'AVVOCATO O L'ANALISTA SUL FASCICOLO SPECIFICO:
- Cliente: {client_name}
- Codice Pratica: {case_code}

CONTESTO COMPLETO DELLA PRATICA, DEI DOCUMENTI FONTE E DEL REPORT GENERATO:
{ctx_json}

IL TUO RUOLO E LE TUE REGOLE DI RISPOSTA:
1. TRASPARENZA METODOLOGICA ASSOLUTA: Rispondi spiegando esattamente COME e DA QUALE DOCUMENTO è stato ricavato ciascun dato, tabella o conclusione presente nel fascicolo o nel report.
2. CITAZIONE DELLE FONTI ORIGINARIE: Quando citi una cifra o un dato (es. fatturato, debiti tributari, debiti verso banche, nominativo soci, REA, ecc.), menziona SEMPRE il documento originario da cui proviene (es. "Fazio srl - bilancio 2025.pdf", "Fazio srl - Visura Camerale.pdf", "Estratto di ruolo AdER", "Centrale Rischi Banca d'Italia", ecc.) e la specifica voce o quadro.
3. DETTAGLIO DEI CALCOLI E RICLASSIFICAZIONI: Se ti viene chiesto come è stato calcolato un indicatore (es. MOL, variazione debiti, totale indebitamento), esplicita la formula contabile applicata e i singoli addendi numerici.
4. RICONCILIAZIONE E REGOLE DI STUDIO: Se un dato è stato riconciliato tra più fonti (es. unificazione dei nominativi soci tra visura e DB per evitare duplicazioni) o modificato in base a una regola dello studio (es. esclusione fatture proforma dai debiti certi), spiegalo con chiarezza al legale.
5. SUGGERIMENTI OPERATIVI PER IL REPORT: Concludi la risposta, ove utile, fornendo all'operatore la formula o istruzione precisa che può inserire nella sezione Review/Commenti del report (tramite il tasto '+') per perfezionare ulteriormente l'elaborato prima della rigenerazione finale.
6. STILE: Professionale, rigoroso, chiaro, in lingua italiana, utilizzando formattazione Markdown (elenchi puntati, grassetto per importi e documenti).
"""


def _clean_llm_response(text: str) -> str:
    """Rimuove tag di reasoning interno e normalizza il testo."""
    if not text:
        return ""
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()


def call_chat_llm(messages: List[Dict[str, str]]) -> str:
    """Invia la conversazione multi-turn a LM Studio (Qwen locale) o al provider configurato."""
    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"
    url = f"{settings.lmstudio_base_url.rstrip('/')}/chat/completions"

    body = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1200,
        "stream": False,
    }
    timeout = getattr(settings, "lmstudio_timeout", 180)
    headers = {"Content-Type": "application/json"}

    try:
        logger.info("Invio richiesta chat a LM Studio model=%s", target_model)
        r = httpx.post(url, json=body, headers=headers, timeout=timeout)
        if r.status_code == 200:
            j = r.json()
            choices = j.get("choices") or []
            if choices:
                raw_content = choices[0].get("message", {}).get("content", "")
                return _clean_llm_response(raw_content)
    except Exception as exc:
        logger.warning("LM Studio non raggiungibile o errore chiamata: %s. Tento provider secondario o fallback.", exc)

    # Fallback su Gemini / OpenAI se configurati in fallback chain
    for p_name in ["gemini", "openai", "claude"]:
        prov = REGISTRY.get(p_name)
        if prov and prov.available():
            try:
                logger.info("Fallback chat su provider=%s", p_name)
                # Crea prompt testuale unificato per il provider
                conv_text = "\n\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
                res = prov.extract(file_path=None, mime="text/plain", prompt=conv_text, model="")
                if res.ok and res.raw_text:
                    return _clean_llm_response(res.raw_text)
            except Exception as e:
                logger.warning("Errore fallback provider %s: %s", p_name, e)

    # Fallback analitico deterministico locale se tutti gli LLM sono offline
    return (
        "Non è stato possibile contattare il server LLM locale (LM Studio). "
        "Verifica che LM Studio sia attivo sulla porta 1234 con il modello caricato. "
        "I documenti e le tabelle del fascicolo rimangono comunque consultabili e verificabili nelle schede della pratica."
    )


def get_case_chat_history(db: Session, case_id: str) -> List[CaseChatMessage]:
    """Restituisce la cronologia dei messaggi scambiati per la pratica."""
    return (
        db.query(CaseChatMessage)
        .filter_by(case_id=case_id)
        .order_by(CaseChatMessage.created_at.asc())
        .all()
    )


def ask_case_chat(
    db: Session,
    case_id: str,
    user_message: str,
) -> Tuple[CaseChatMessage, CaseChatMessage]:
    """Elabora un messaggio dell'utente sulla pratica, invoca l'LLM con il contesto del fascicolo e memorizza la risposta."""
    case = db.get(Case, case_id)
    if not case:
        raise ValueError(f"Pratica {case_id} non trovata.")

    # 1. Salva messaggio utente
    user_msg_record = CaseChatMessage(
        case_id=case_id,
        sender="user",
        content=user_message.strip(),
        context_meta={"timestamp": datetime.now().isoformat()},
    )
    db.add(user_msg_record)
    db.commit()
    db.refresh(user_msg_record)

    # 2. Prepara il contesto completo della pratica
    ctx = build_case_chat_context(db, case_id)
    system_prompt = _build_system_prompt(ctx)

    # 3. Recupera gli ultimi messaggi per il contesto multi-turn (ultimi 6 scambi)
    history = (
        db.query(CaseChatMessage)
        .filter_by(case_id=case_id)
        .order_by(CaseChatMessage.created_at.desc())
        .limit(10)
        .all()
    )
    history.reverse()

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({
            "role": "user" if msg.sender == "user" else "assistant",
            "content": msg.content,
        })

    # 4. Invoca l'LLM
    reply_text = call_chat_llm(messages)

    # 5. Salva messaggio assistente
    cited_docs = []
    for d in ctx.get("documents", []):
        if d.get("filename") and d["filename"].lower() in reply_text.lower():
            cited_docs.append(d["filename"])

    assistant_msg_record = CaseChatMessage(
        case_id=case_id,
        sender="assistant",
        content=reply_text,
        context_meta={
            "model": settings.lmstudio_model or "qwen/qwen3.8-27b",
            "cited_documents": cited_docs,
            "report_version": ctx.get("report_preanalisi", {}).get("versione", 1),
        },
    )
    db.add(assistant_msg_record)
    db.commit()
    db.refresh(assistant_msg_record)

    return user_msg_record, assistant_msg_record


def clear_case_chat_history(db: Session, case_id: str) -> int:
    """Cancella la cronologia della chat per la pratica specificata."""
    deleted = (
        db.query(CaseChatMessage)
        .filter_by(case_id=case_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
