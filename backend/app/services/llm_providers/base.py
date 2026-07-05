"""Interfaccia comune ai provider LLM multimodali (Gemini, Claude, OpenAI)."""
import json
import re
import time
from dataclasses import dataclass

# Stati HTTP transienti: vale la pena riprovare (sovraccarico/limiti temporanei).
RETRY_STATUS = {429, 500, 502, 503, 504}


def post_with_retry(url, body, headers=None, params=None, timeout=120, attempts=4):
    """POST con retry e backoff esponenziale sugli errori transienti. Comune a tutti i provider."""
    import httpx
    delay = 2.0
    last_exc = None
    for i in range(attempts):
        try:
            r = httpx.post(url, json=body, headers=headers, params=params, timeout=timeout)
            if r.status_code in RETRY_STATUS and i < attempts - 1:
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
    provider: str                   # "gemini" | "claude" | "openai"
    model: str
    ok: bool
    error: str | None = None
    raw_text: str | None = None     # risposta grezza, per diagnostica
    usage: dict | None = None       # token in/out per costi


def parse_json(raw: str):
    """Estrae il primo oggetto JSON dalla risposta (togliendo eventuali fence)."""
    if not raw:
        return None
    raw = re.sub(r"```(?:json)?", "", raw)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


class LLMProvider:
    name: str = "base"

    def available(self) -> bool:
        """True se la chiave del provider è configurata."""
        return False

    def extract(self, file_path: str | None, mime: str, prompt: str, model: str) -> ExtractionResult:
        """Estrazione multimodale (file) o testuale (file_path=None). Ritorna ExtractionResult."""
        raise NotImplementedError
