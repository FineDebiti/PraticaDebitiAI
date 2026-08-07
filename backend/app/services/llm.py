"""Astrazione LLM multi-provider con resilienza.

- classify(text): riconosce il tipo di documento (catena di fallback, testo).
- extract(text, doc_type): estrazione da testo (catena di fallback).
- extract_from_file(path, doc_type): estrazione MULTIMODALE (il modello legge
  direttamente PDF/immagine).

Resilienza:
- FALLBACK (tutti i doc): catena di provider (default gemini -> claude -> openai).
  Se il primario fallisce si prova il successivo; i provider senza chiave sono
  saltati (degradazione graziosa). La pratica viene sempre lavorata.
- CROSS-CHECK (solo bilancio, centrale_rischi): due provider diversi estraggono
  lo stesso documento; se gli importi chiave divergono si segnala all'operatore
  (human-in-the-loop), MAI scelta automatica del vincitore.

I metadati di provenienza (_llm_provider, _llm_model) e l'esito del cross-check
(_crosscheck) vengono aggiunti al dict restituito, così il worker li persiste.
"""
import json
import mimetypes
from app.config import settings
from app.services.llm_routing import model_for_provider
from app.services.llm_providers import REGISTRY
from app.services.llm_providers.base import ExtractionResult, parse_json
from app.services import llm_crosscheck as cc
from app.services.prompts import (
    CLASSIFY_PROMPT, get_extract_prompt, GENERIC_EXTRACT_PROMPT, _COMMON_RULES,
)


# ============================ API pubblica ============================
def classify(text: str) -> dict:
    prompt = CLASSIFY_PROMPT.format(text=text[:6000])
    res = _run_fallback(None, "", prompt, doc_type=None, what="classify")
    data = (res.data if res and res.ok else None) or {}
    return {
        "doc_type": data.get("doc_type", "altro"),
        "confidence": float(data.get("confidence", 0.0) or 0.0),
    }


def extract(text: str, doc_type: str, client_cf: str = "") -> dict:
    """Estrazione da TESTO gia estratto (parser/OCR), con catena di fallback."""
    prompt = _build_prompt(doc_type, client_cf, text=text)
    if cc.needs_crosscheck(doc_type):
        return _run_crosscheck(None, "", prompt, doc_type)
    res = _run_fallback(None, "", prompt, doc_type, what="extract")
    return _result_to_data(res, doc_type)


def extract_from_file(file_path: str, doc_type: str, client_cf: str = "") -> dict:
    """Estrazione MULTIMODALE: il file (PDF/immagine) va direttamente al modello."""
    prompt = _build_prompt(doc_type, client_cf, text="(vedi documento allegato)")
    mime = mimetypes.guess_type(file_path)[0] or "application/pdf"
    if cc.needs_crosscheck(doc_type):
        return _run_crosscheck(file_path, mime, prompt, doc_type)
    res = _run_fallback(file_path, mime, prompt, doc_type, what="extract_from_file")
    return _result_to_data(res, doc_type)


# ============================ Catena di provider ============================
def _chain() -> list:
    return [p.strip() for p in (settings.llm_fallback_chain or "gemini").split(",") if p.strip()]


def _available_providers() -> list:
    """[(nome, provider)] nell'ordine della catena, solo quelli con chiave configurata."""
    if settings.llm_provider == "stub":
        return []
    out = []
    for name in _chain():
        prov = REGISTRY.get(name)
        if prov and prov.available():
            out.append((name, prov))
    return out


def _run_fallback(file_path, mime, prompt, doc_type, what="extract") -> ExtractionResult:
    """Prova i provider in ordine finché uno riesce. Ritorna l'ExtractionResult vincente
    (o l'ultimo fallito). Se nessun provider ha chiave, ricade sullo stub (dev)."""
    provs = _available_providers()
    if not provs:
        txt = _stub(prompt)
        return ExtractionResult(parse_json(txt) or {}, "stub", "", True, raw_text=txt)
    last = None
    for name, prov in provs:
        model = model_for_provider(name, doc_type)
        print(f"[llm] {what} doc_type={doc_type} provider={name} model={model}", flush=True)
        res = prov.extract(file_path, mime, prompt, model)
        if res.ok:
            return res
        last = res
        print(f"[llm] provider {name} FALLITO: {res.error} -> provo il successivo", flush=True)
    return last


def _run_crosscheck(file_path, mime, prompt, doc_type) -> dict:
    """Due provider diversi estraggono lo stesso doc; confronto importi chiave."""
    provs = _available_providers()
    if len(provs) < 2:
        # Un solo provider (o stub): nessun cross-check possibile, lavoro comunque.
        res = _run_fallback(file_path, mime, prompt, doc_type, what="crosscheck(1)")
        data = _result_to_data(res, doc_type)
        data["_crosscheck"] = {"status": "not_run",
                               "note": "un solo provider disponibile, cross-check non eseguito",
                               "discrepancies": []}
        return data

    (n1, p1), (n2, p2) = provs[0], provs[1]
    print(f"[llm] crosscheck doc_type={doc_type} provider_a={n1} provider_b={n2}", flush=True)
    r1 = p1.extract(file_path, mime, prompt, model_for_provider(n1, doc_type))
    r2 = p2.extract(file_path, mime, prompt, model_for_provider(n2, doc_type))

    primary = r1 if r1.ok else (r2 if r2.ok else r1)
    data = _result_to_data(primary, doc_type)

    if r1.ok and r2.ok:
        disc = cc.compare(r1.data, r2.data, doc_type)
        data["_crosscheck"] = {
            "status": "discrepancy" if disc else "verified",
            "discrepancies": disc,
            "provider_a": n1, "model_a": r1.model,
            "provider_b": n2, "model_b": r2.model,
        }
        if disc:
            print(f"[llm] crosscheck DISCORDE su {len(disc)} campi -> verifica manuale", flush=True)
        else:
            print(f"[llm] crosscheck CONCORDE ({n1} vs {n2})", flush=True)
    else:
        failed = n1 if not r1.ok else n2
        data["_crosscheck"] = {
            "status": "not_run",
            "note": f"un provider ha fallito ({failed}), cross-check non eseguito",
            "discrepancies": [],
        }
    return data


# ============================ Helper ============================
def _build_prompt(doc_type, client_cf, text) -> str:
    template = get_extract_prompt(doc_type)
    rules = _COMMON_RULES + _client_hint(client_cf)
    return template.format(doc_type=doc_type, text=text[:30000], rules=rules)


def _result_to_data(res: ExtractionResult, doc_type: str) -> dict:
    """ExtractionResult -> dict da restituire, con metadati di provenienza."""
    if res and res.ok:
        data = dict(res.data)
        data["_llm_provider"] = res.provider
        data["_llm_model"] = res.model
        return data
    # Tutti i provider falliti: NON inventare dati, risultato vuoto + warning.
    data = _empty_result(doc_type)
    data["_llm_provider"] = res.provider if res else "none"
    data["_llm_model"] = res.model if res else ""
    if res and res.error:
        data.setdefault("warnings", []).append({"type": "provider_error", "message": res.error})
    return data


def _client_hint(client_cf: str) -> str:
    """Istruzione iniettata nel prompt: indica all'AI il CF del titolare,
    cosi marca con certezza il cliente nei documenti."""
    if not client_cf:
        return ""
    return (
        f"\nIMPORTANTE: il CLIENTE/TITOLARE di questa pratica ha CODICE FISCALE = {client_cf}. "
        "Quando incontri questo codice fiscale (ignorando maiuscole/spazi), marca quel "
        "soggetto come cliente (campi 'e_cliente'/'is_client' a true) e mettilo per primo.\n"
    )


def _empty_result(doc_type: str) -> dict:
    return {"document_type": doc_type, "warnings": [
        {"type": "empty", "message": "Nessun dato estratto: tutti i provider hanno fallito."}]}


# ============================ STUB (offline, nessuna chiave) ============================
def _stub(prompt: str) -> str:
    if "classifica documenti" in prompt.lower():
        text = prompt.split("CONTENUTO:")[-1].lower()
        guess = "altro"
        for kw, t in [
            ("catastale", "visura_catastale"), ("catasto", "visura_catastale"),
            ("bilancio di esercizio", "bilancio"), ("stato patrimoniale", "bilancio"),
            ("conto economico", "bilancio"), ("nota integrativa", "bilancio"),
            ("centrale dei rischi", "centrale_rischi"), ("crif", "crif"),
            ("agenzia delle entrate-riscossione", "cartella_aer"), ("cartella", "cartella_aer"),
            ("busta paga", "busta_paga"), ("cedolino", "busta_paga"),
            ("estratto conto", "estratto_conto"), ("pignoramento", "pignoramento"),
            ("finanziamento", "contratto_finanziamento"), ("prestito", "contratto_finanziamento"),
        ]:
            if kw in text:
                guess = t
                break
        return json.dumps({"doc_type": guess, "confidence": 0.5})
    return json.dumps({"document_type": "stub", "warnings": [
        {"type": "stub", "message": "Estrazione simulata: nessuna chiave LLM configurata."}]})
