"""Interfaccia comune ai provider LLM multimodali (Gemini, Claude, OpenAI)."""
import json
import re
import threading
import time
from dataclasses import dataclass

# Stati HTTP transienti: vale la pena riprovare (sovraccarico/limiti temporanei).
RETRY_STATUS = {429, 500, 502, 503, 504}
_RETRY_STATE = threading.local()


def reset_last_retry_count() -> None:
    _RETRY_STATE.count = 0


def get_last_retry_count() -> int:
    return int(getattr(_RETRY_STATE, "count", 0) or 0)


def post_with_retry(url, body, headers=None, params=None, timeout=120, attempts=6):
    """POST con retry e backoff esponenziale sugli errori transienti. Comune a tutti i provider."""
    import httpx
    delay = 3.0
    last_exc = None
    reset_last_retry_count()
    for i in range(attempts):
        _RETRY_STATE.count = i
        try:
            r = httpx.post(url, json=body, headers=headers, params=params, timeout=timeout)
            if r.status_code in RETRY_STATUS and i < attempts - 1:
                if r.status_code == 429 and ("quota" in r.text.lower() or "resource_exhausted" in r.text.lower()):
                    r.raise_for_status()
                time.sleep(delay); delay *= 2; continue
            r.raise_for_status()
            return r
        except httpx.TransportError as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(delay); delay *= 2; continue
            raise
    if last_exc:
        raise last_exc


@dataclass
class ExtractionResult:
    data: dict                      # JSON estratto (gia parsato)
    provider: str                   # "lmstudio" | "gemini" | "claude" | "openai"
    model: str
    ok: bool
    error: str | None = None
    raw_text: str | None = None     # risposta grezza, per diagnostica
    usage: dict | None = None       # token in/out per costi
    retries: int = 0
    duration_s: float = 0.0
    fallback_used: bool = False
    fallback_errors: list | None = None
    validation_status: str = "valid"


def parse_json_with_status(raw: str) -> tuple[dict | None, str | None]:
    """Estrae il primo oggetto JSON valido senza chiudere silenziosamente JSON troncati."""
    if not raw:
        return None, "empty_output"
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    raw = re.sub(r"```(?:json)?", "", raw)
    raw = re.sub(r"(?<!:)\s*//[^\n\r]*", "", raw)

    start_idx = raw.find("{")
    if start_idx == -1:
        return None, "no_json_object"

    m = re.search(r"\{.*\}", raw[start_idx:], re.DOTALL)
    if not m:
        return None, "truncated_json"

    candidate = m.group(0).strip()

    try:
        return json.loads(candidate), None
    except Exception:
        pass

    try:
        no_trailing = re.sub(r',\s*([\]}])', r'\1', candidate)
        return json.loads(no_trailing), None
    except Exception:
        pass

    # Segnala esplicitamente troncamento se le parentesi risultano sbilanciate (mai riparazione silenziosa)
    if candidate.count("{") > candidate.count("}") or candidate.count("[") > candidate.count("]"):
        return None, "truncated_json"

    return None, "invalid_json"


def parse_json(raw: str):
    """Estrae il primo oggetto JSON valido dalla risposta (mai autoriparazione silenziosa di JSON troncati)."""
    data, _ = parse_json_with_status(raw)
    return data


class LLMProvider:
    name: str = "base"

    def available(self) -> bool:
        """True se la chiave del provider è configurata."""
        return False

    def extract(self, file_path: str | None, mime: str, prompt: str, model: str) -> ExtractionResult:
        """Estrazione multimodale (file) o testuale (file_path=None). Ritorna ExtractionResult."""
        raise NotImplementedError
