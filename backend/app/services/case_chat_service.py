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
from typing import List, Dict, Any, Tuple
import httpx
from sqlalchemy.orm import Session

from app.models import (
    Case,
    Company,
    Debtor,
    Document,
    FinancialStatement,
    CreditReportSummary,
    TaxDebtStatement,
    RealEstate,
    StudioRule,
    CaseChatMessage,
)
from app.services.report_regenerator import get_or_create_preanalysis_report
from app.services.llm_providers import REGISTRY
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
)
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

    # Sintesi economica per esercizio (dal bilancio) con dettaglio OIC 12 ed esplicitazione MOL
    esercizi_sintesi = []
    for fs in fss:
        ce = fs.raw_extraction.get("conto_economico", {}) if getattr(fs, "raw_extraction", None) else {}
        eb = calculate_ebitda_oic12(ce)
        esercizi_sintesi.append({
            "esercizio": fs.fiscal_year_end,
            "tipo": fs.statement_type,
            "ricavi_a1": eb["ricavi_vendite_a1"],
            "valore_produzione_a": eb["valore_produzione_a"],
            "costi_produzione_b": eb["costi_produzione_b"],
            "ebit_differenza_a_b": eb["ebit_differenza_a_b"],
            "ammortamenti_b10": eb["ammortamenti_b10a_b10b_b10c"],
            "mol_ebitda_standard": eb["ebitda_standard"],
            "mol_pct_valore_produzione": eb["ebitda_margin_pct"],
            "formula_calcolo_mol": eb["formula_applicata"],
            "oneri_finanziari": ce.get("oneri_finanziari"),
            "utile_perdita": ce.get("utile_perdita") or fs.net_result,
        })

    # Dati estratti del report preanalisi (solo sezioni chiave)
    c2 = rep_data.get("capitolo_2_profilo", {}) if rep_data else {}
    c5 = rep_data.get("capitolo_5_indebitamento", {}) if rep_data else {}
    c7 = rep_data.get("capitolo_7_diagnosi_crisi", {}) if rep_data else {}
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
        "bilanci_storici_e_dettaglio_mol": esercizi_sintesi,
        "debiti_capitolo_5_1": deb_rows,
        "totali_debiti_5_1": table_5_1.get("totali", {}),
        "posizione_finanziaria_netta_esma": c5.get("tabella_pfn_esma", {}),
        "valutazione_pfn_ebitda": c5.get("valutazione_pfn_ebitda", {}),
        "inquadramento_ccii_impresa_minore": c7.get("inquadramento_ccii", {}),
        "segnali_allarme_art3_ccii": c7.get("segnali_allarme_art3", {}),
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
    """Genera il prompt di sistema strutturato con il contesto completo della pratica,
    configurato come Analista Economico-Finanziario Senior per la Crisi d'Impresa."""
    prat = ctx.get("pratica", {})
    client_name = prat.get("cliente") or "Cliente"
    case_code = prat.get("codice") or "PRATICA"
    ctx_json = json.dumps(ctx, ensure_ascii=False, indent=2)

    return f"""Sei un Senior Restructuring Advisor e Analista Forense specializzato nella pre-analisi della crisi d'impresa e nell'applicazione del CCII (D.Lgs. 14/2019 e succ. mod.), a supporto dello Studio Legale Avv. Aurelio Bentivegna & Partners.

STAI ASSISTENDO L'AVVOCATO O L'ANALISTA SUL FASCICOLO SPECIFICO:
- Cliente: {client_name}
- Codice Pratica: {case_code}

CONTESTO COMPLETO DELLA PRATICA, DEI DOCUMENTI FONTE, DEI CALCOLI CONTABILI E DEL REPORT:
{ctx_json}

SEGUI TASSATIVAMENTE IL SEGUENTE PROTOCOLLO METODOLOGICO:

1. CLASSIFICAZIONE EPISTEMICA (REGOLA ANTI-ALLUCINAZIONE):
Ogni singolo valore, saldo o affermazione DEVE recare una di queste etichette:
- [D] Documentato: presente in un atto o estratto ufficiale con data, fonte e pagina esplicite.
- [R] Riferito: dichiarato verbalmente o in riunione, non provato da contabilità/atti terzi.
- [C] Calcolato: risultato di una formula aritmetica replicabile su dati certi.
- [S] Stimato: intervallo euristico o giudizio professionale motivato (mai spacciato per perizia).
- [H] Ipotesi: simulazione condizionale "what-if".

2. DIVIETI DI CALCOLO E TRATTAMENTO DATI (ZERO ERRORI CRITICI):
- Ditta Individuale (Art. 2740 c.c.): Responsabilità patrimoniale illimitata. Censire sia i debiti d'impresa sia quelli personali e le coobbligazioni (CTC/Banche per rate residue), specificando la componente di regresso.
- Riconciliazione AdER: Prendere sempre il 'Totale Residuo' (netto di sgravi, pagamenti e stralci). La voce 'di cui INPS' è una sottocomponente GIA' INCLUSA: NON risommarla. Escludere i carichi saldati e NON sommare le rate dei piani di rottamazione allo stock del debito.
- Centrale Rischi (CR): Prendere unicamente l'ultimo mese disponibile per lo stock utilizzato. NON sommare i mesi storici tra loro e NON sommare crediti ceduti all'utilizzato del cessionario senza contratti.
- Credito al Consumo (CTC): Le coobbligazioni si valutano per le rate residue. Se un rapporto (es. carta revolving Findomestic) espone solo una rata mensile in scadenza, NON prenderla come intero debito e NON usare il fido: indicare 'saldo complessivo non noto'.
- Trattamento Assenze / Lacune: Cespiti, cassa, crediti e magazzino non inventariati vanno indicati come 'n.r.' o 'non quantificabile'. È VIETATO impostare 0. Non inventare uno stato patrimoniale civilistico su contabilità semplificate.
- Raccordo Fiscale vs Gestionale: Il rigo RG5 (ricavi non annotati) spiega solo la differenza tra perdita contabile e reddito fiscale dichiarato: NON è liquidità incassata né fatturato gestionale.
- Infrannuale: Il periodo parziale moltiplicato per n (es. quadrimestre x 3) è 'riparametrato', MAI 'previsionale' o 'budget'.

3. PROTOCOLLO DEI 5 STEP OPERATIVI:
- Step 1 (Economia): Conto economico comparato (anni chiusi + infrannuale riparametrato x3). Calcola EBITDA gestionale, incidenza acquisti e personale, isola proventi straordinari e riconcilia il quadro RG.
- Step 2 (Debito): Quantifica il debito documentato certo (AdER residuo + CR ultimo mese + coobbligazioni quantificate). Separa i debiti riferiti (fornitori, TFR, locazioni). Genera il totale misto indicativo ed esplicita le divergenze aperte.
- Step 3 (Patrimonio e Realizzo): Ricognizione catastale (assenza risultanze != certezza di nullità), PRA ed elenco beni. Formula solo una stima concorsuale esplorativa a lotti (intervallo prudente vs favorevole) al netto di spese dirette (10-20%), dichiarando l'assenza di perizia.
- Step 4 (Continuità): Test diagnostici di sensitività (canoni locazione storici non registrati, costo teorico personale post-riduzione). Distingui sempre l'EBITDA dal flusso di cassa e confrontalo con il servizio del debito stimato. Non calcolare DSCR puntuali senza scadenziario.
- Step 5 (CCII): Verifica qualifica ditta individuale e soglie art. 2, co. 1, lett. d) CCII (se ricavi > 200k, escludi il concordato minore). Valuta prioritariamente la verifica di fattibilità della Composizione Negoziata (CNC ex artt. 12 ss.), mantenendo la Liquidazione Giudiziale (art. 121) come benchmark alternativo.

4. REGOLA FINALE HUMAN GATE: Non devi dimostrare a tutti i costi che l'impresa sia risanabile. Devi verificare con rigore se produce reddito, genera cassa e sostiene il debito. La valutazione conclusiva sulla fattibilità e la scelta dello strumento giuridico rimangono riservate in via esclusiva all'Avv. Aurelio Bentivegna.
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


def stream_case_chat(db: Session, case_id: str, user_message: str):
    """Elabora un messaggio dell'utente in modalità streaming SSE, memorizzando la conversazione."""
    case = db.get(Case, case_id)
    if not case:
        yield json.dumps({"type": "error", "error": f"Pratica {case_id} non trovata."})
        return

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

    # 2. Costruisci il contesto e prompt
    ctx = build_case_chat_context(db, case_id)
    system_prompt = _build_system_prompt(ctx)

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

    # 3. Chiamata streaming a LM Studio
    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"
    url = f"{settings.lmstudio_base_url.rstrip('/')}/chat/completions"
    body = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1500,
        "stream": True,
    }
    timeout = getattr(settings, "lmstudio_timeout", 180)
    headers = {"Content-Type": "application/json"}

    full_content = []
    stream_ok = False

    try:
        logger.info("Invio richiesta chat streaming a LM Studio model=%s", target_model)
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", url, json=body, headers=headers) as response:
                if response.status_code == 200:
                    stream_ok = True
                    for line in response.iter_lines():
                        if not line:
                            continue
                        line_str = line.strip()
                        if line_str.startswith("data: "):
                            data_part = line_str[6:].strip()
                            if data_part == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(data_part)
                                choices = chunk_json.get("choices") or []
                                if choices:
                                    delta = choices[0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        full_content.append(content)
                                        yield json.dumps({"type": "delta", "delta": content})
                            except Exception:
                                continue
    except Exception as exc:
        logger.warning("Streaming LM Studio interrotto o fallito: %s", exc)

    final_text = "".join(full_content)
    cleaned_reply = _clean_llm_response(final_text)

    # Fallback se lo stream non ha prodotto testo utile
    if not stream_ok or not cleaned_reply.strip():
        logger.info("Fallback non-streaming su catena provider...")
        fallback_reply = call_chat_llm(messages)
        cleaned_reply = fallback_reply
        yield json.dumps({"type": "delta", "delta": cleaned_reply})

    # 4. Salva messaggio assistente nel DB
    asst_msg_record = CaseChatMessage(
        case_id=case_id,
        sender="assistant",
        content=cleaned_reply,
        context_meta={
            "model": target_model,
            "report_version": ctx.get("report_preanalisi", {}).get("versione", 1),
        },
    )
    db.add(asst_msg_record)
    db.commit()
    db.refresh(asst_msg_record)

    yield json.dumps({
        "type": "done",
        "user_message": {
            "id": user_msg_record.id,
            "case_id": user_msg_record.case_id,
            "sender": user_msg_record.sender,
            "content": user_msg_record.content,
            "context_meta": user_msg_record.context_meta,
            "created_at": user_msg_record.created_at.isoformat(),
        },
        "assistant_message": {
            "id": asst_msg_record.id,
            "case_id": asst_msg_record.case_id,
            "sender": asst_msg_record.sender,
            "content": asst_msg_record.content,
            "context_meta": asst_msg_record.context_meta,
            "created_at": asst_msg_record.created_at.isoformat(),
        },
    })
