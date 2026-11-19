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
import time
from pydantic import BaseModel, Field
from app.config import settings
from app.services.llm_routing import model_for_provider
from app.services.llm_providers import REGISTRY
from app.services.llm_providers.base import ExtractionResult, parse_json
from app.services import llm_crosscheck as cc
from app.services.prompts import (
    CLASSIFY_PROMPT, get_extract_prompt, _COMMON_RULES,
)

LOCAL_PROVIDERS = {"lmstudio"}


class ClassifySchema(BaseModel):
    doc_type: str = Field(default="altro", min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# ============================ API pubblica ============================
def classify(text: str) -> dict:
    snippet = text if len(text) <= 12000 else (text[:9000] + "\n...[OMISSIS INTERMEDIO]...\n" + text[-3000:])
    prompt = CLASSIFY_PROMPT.format(text=snippet)
    res = _run_fallback(None, "", prompt, doc_type=None, what="classify")
    raw_data = (res.data if res and res.ok else None) or {}
    validation_status = res.validation_status if res else "provider_error"
    try:
        validated = ClassifySchema.model_validate({
            "doc_type": str(raw_data.get("doc_type") or "altro").strip() or "altro",
            "confidence": float(raw_data.get("confidence", 0.0) or 0.0),
        })
    except Exception:
        validated = ClassifySchema(doc_type="altro", confidence=0.0)
        validation_status = "schema_error"
    return {
        "doc_type": validated.doc_type,
        "confidence": validated.confidence,
        "text_truncated": len(text) > 12000,
        "_llm_telemetry": _telemetry_from_result(res, validation_status=validation_status),
    }


def _split_chunks_for_extract(text: str, max_len: int, max_chunks: int = 4) -> tuple[list[str], bool]:
    """Suddivide testi lunghi rispettando i confini di riga; ritorna (chunks, capped)."""
    if len(text) <= max_len:
        return [text], False
    chunks: list[str] = []
    pos = 0
    total = len(text)
    while pos < total and len(chunks) < max_chunks:
        end = min(total, pos + max_len)
        if end < total:
            nl = text.rfind("\n", pos + int(max_len * 0.7), end)
            if nl > pos:
                end = nl + 1
        chunks.append(text[pos:end])
        pos = end
    return chunks, pos < total


def _merge_chunk_results(results: list[dict], doc_type: str) -> dict:
    """Consolida gli output JSON di più passaggi senza inventare dati mancanti."""
    if not results:
        return _empty_result(doc_type)
    merged = dict(results[0])
    all_warnings = list(merged.get("warnings") or [])
    for part in results[1:]:
        for w in (part.get("warnings") or []):
            if w not in all_warnings:
                all_warnings.append(w)
        for k, v in part.items():
            if k.startswith("_") or k == "warnings":
                continue
            if isinstance(v, list) and isinstance(merged.get(k), list):
                existing = merged[k]
                for item in v:
                    if item not in existing:
                        existing.append(item)
            elif merged.get(k) in (None, "", [], {}) and v not in (None, "", [], {}):
                merged[k] = v
    if all_warnings:
        merged["warnings"] = all_warnings
    return merged


def extract(text: str, doc_type: str, client_cf: str = "") -> dict:
    """Estrazione da TESTO gia estratto (parser/OCR), con catena di fallback e multi-pass su testi lunghi."""
    max_len = 150000 if "lmstudio" in (settings.llm_provider or "") or "lmstudio" in (settings.llm_fallback_chain or "") else 30000
    if len(text) <= max_len or cc.needs_crosscheck(doc_type):
        prompt, truncated = _build_prompt(doc_type, client_cf, text=text, return_meta=True)
        if cc.needs_crosscheck(doc_type):
            out = _run_crosscheck(None, "", prompt, doc_type)
        else:
            res = _run_fallback(None, "", prompt, doc_type, what="extract")
            out = _result_to_data(res, doc_type)
        if truncated:
            out["_input_truncated"] = True
            out.setdefault("_llm_telemetry", {})["input_truncated"] = True
            out.setdefault("warnings", []).append({
                "type": "input_truncated",
                "message": f"Testo sorgente ({len(text)} caratteri) eccede il budget contesto prompt.",
            })
        return out

    # Multi-passaggio controllato su documenti eccedenti max_len (es. estratti conto/bilanci lunghi)
    chunks, partial_coverage = _split_chunks_for_extract(text, max_len=max_len, max_chunks=4)
    chunk_outputs: list[dict] = []
    for idx, ch in enumerate(chunks, 1):
        prompt = _build_prompt(
            doc_type, client_cf,
            text=f"[PASSAGGIO {idx}/{len(chunks)}]\n{ch}",
        )
        res = _run_fallback(None, "", prompt, doc_type, what=f"extract_chunk_{idx}/{len(chunks)}")
        chunk_outputs.append(_result_to_data(res, doc_type))

    out = _merge_chunk_results(chunk_outputs, doc_type)
    out["_multi_pass"] = True
    out["_chunks_processed"] = len(chunks)
    if partial_coverage:
        out["_input_truncated"] = True
        out["_partial_coverage"] = True
        out.setdefault("warnings", []).append({
            "type": "input_truncated",
            "message": f"Testo sorgente ({len(text)} caratteri) elaborato in {len(chunks)} passaggi con copertura parziale.",
        })
    if isinstance(out.get("_llm_telemetry"), dict):
        out["_llm_telemetry"]["multi_pass"] = True
        out["_llm_telemetry"]["chunks_processed"] = len(chunks)
        out["_llm_telemetry"]["input_truncated"] = partial_coverage
    return out


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
    """[(nome, provider)] nell'ordine della catena; rispetta guardia privacy locale."""
    if settings.llm_provider == "stub":
        return []
    enforce_local_only = (
        settings.llm_provider in LOCAL_PROVIDERS
        and not getattr(settings, "allow_cloud_llm_fallback", False)
    )
    out = []
    for name in _chain():
        if enforce_local_only and name not in LOCAL_PROVIDERS:
            continue
        prov = REGISTRY.get(name)
        if prov and prov.available():
            out.append((name, prov))
    return out


def _telemetry_from_result(res: ExtractionResult | None, validation_status: str | None = None) -> dict:
    if not res:
        return {
            "provider": "none",
            "model": "",
            "duration_s": 0.0,
            "usage": {},
            "retries": 0,
            "error": "no_result",
            "fallback_used": False,
            "fallback_errors": [],
            "validation_status": validation_status or "provider_error",
        }
    return {
        "provider": res.provider,
        "model": res.model,
        "duration_s": res.duration_s,
        "usage": res.usage or {},
        "retries": res.retries,
        "error": res.error,
        "fallback_used": bool(res.fallback_used),
        "fallback_errors": res.fallback_errors or [],
        "validation_status": validation_status or res.validation_status or ("valid" if res.ok else "provider_error"),
    }


def _run_fallback(file_path, mime, prompt, doc_type, what="extract") -> ExtractionResult:
    """Prova i provider in ordine finché uno riesce, registrando telemetria di retry/errori/fallback."""
    provs = _available_providers()
    if not provs:
        txt = _stub(prompt)
        return ExtractionResult(
            parse_json(txt) or {}, "stub", "", True, raw_text=txt,
            validation_status="stub", duration_s=0.0, retries=0,
        )
    last = None
    fallback_errors: list[dict] = []
    for idx, (name, prov) in enumerate(provs):
        model = model_for_provider(name, doc_type)
        t0 = time.monotonic()
        print(f"[llm] {what} doc_type={doc_type} provider={name} model={model}", flush=True)
        res = prov.extract(file_path, mime, prompt, model)
        if not res.duration_s:
            res.duration_s = round(time.monotonic() - t0, 3)
        if idx > 0 or fallback_errors:
            res.fallback_used = True
            res.fallback_errors = list(fallback_errors)
        if res.ok:
            if not res.validation_status:
                res.validation_status = "valid"
            return res
        fallback_errors.append({
            "provider": name,
            "model": model,
            "error": res.error,
            "retries": res.retries,
            "duration_s": res.duration_s,
            "validation_status": res.validation_status or "provider_error",
        })
        last = res
        print(f"[llm] provider {name} FALLITO: {res.error} -> provo il successivo", flush=True)
    if last is not None:
        last.fallback_errors = list(fallback_errors)
        last.fallback_used = len(provs) > 1
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
def _build_prompt(doc_type, client_cf, text, return_meta: bool = False):
    template = get_extract_prompt(doc_type)
    rules = _COMMON_RULES + _client_hint(client_cf)
    max_len = 150000 if "lmstudio" in (settings.llm_provider or "") or "lmstudio" in (settings.llm_fallback_chain or "") else 30000
    truncated = len(text) > max_len
    txt_body = text[:max_len]
    if truncated:
        txt_body += f"\n\n[AVVERTENZA: documento troncato a {max_len} su {len(text)} caratteri totali]"
    formatted = template.format(doc_type=doc_type, text=txt_body, rules=rules)
    return (formatted, truncated) if return_meta else formatted


def _result_to_data(res: ExtractionResult, doc_type: str) -> dict:
    """ExtractionResult -> dict da restituire, con metadati di provenienza e telemetria completa."""
    if res and res.ok:
        data = dict(res.data)
        data["_llm_provider"] = res.provider
        data["_llm_model"] = res.model
        if res.usage:
            data["_llm_usage"] = res.usage
        data["_llm_telemetry"] = _telemetry_from_result(res)
        return data
    # Tutti i provider falliti: NON inventare dati, risultato vuoto + warning + telemetria.
    data = _empty_result(doc_type)
    data["_llm_provider"] = res.provider if res else "none"
    data["_llm_model"] = res.model if res else ""
    if res and res.usage:
        data["_llm_usage"] = res.usage
    data["_llm_telemetry"] = _telemetry_from_result(res, validation_status=(res.validation_status if res else "provider_error"))
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
