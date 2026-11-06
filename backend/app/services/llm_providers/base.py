"""Interfaccia comune ai provider LLM multimodali (Gemini, Claude, OpenAI)."""
import json
import re
import time
from dataclasses import dataclass

# Stati HTTP transienti: vale la pena riprovare (sovraccarico/limiti temporanei).
RETRY_STATUS = {429, 500, 502, 503, 504}


def post_with_retry(url, body, headers=None, params=None, timeout=120, attempts=6):
    """POST con retry e backoff esponenziale sugli errori transienti. Comune a tutti i provider."""
    import httpx
    delay = 3.0
    last_exc = None
    for i in range(attempts):
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
    provider: str                   # "gemini" | "claude" | "openai"
    model: str
    ok: bool
    error: str | None = None
    raw_text: str | None = None     # risposta grezza, per diagnostica
    usage: dict | None = None       # token in/out per costi


def parse_json(raw: str):
    """Estrae il primo oggetto JSON dalla risposta (togliendo eventuali fence, commenti e virgole residue)."""
    if not raw:
        return None
    # 1. Rimuove blocchi thinking/reasoning
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # 2. Rimuove markdown fences
    raw = re.sub(r"```(?:json)?", "", raw)
    # 3. Rimuove commenti stile C++/JS (es. // A1, // Totale A) che mandano in crash json.loads
    raw = re.sub(r"(?<!:)\s*//[^\n\r]*", "", raw)

    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    candidate = m.group(0).strip()

    # Tentativo 1: parsing diretto
    try:
        return json.loads(candidate)
    except Exception:
        pass

    # Tentativo 2: pulizia trailing commas (es. {"a": 1,} o [1, 2,])
    try:
        no_trailing = re.sub(r',\s*([\]}])', r'\1', candidate)
        return json.loads(no_trailing)
    except Exception:
        pass

    # Tentativo 3: bilanciamento graffe aperte se l'output e' stato troncato alla fine
    try:
        open_b = candidate.count("{")
        close_b = candidate.count("}")
        if open_b > close_b:
            repaired = candidate + ("}" * (open_b - close_b))
            repaired = re.sub(r',\s*([\]}])', r'\1', repaired)
            return json.loads(repaired)
    except Exception:
        pass

    return None


class LLMProvider:
    name: str = "base"

    def available(self) -> bool:
        """True se la chiave del provider è configurata."""
        return False

    def extract(self, file_path: str | None, mime: str, prompt: str, model: str) -> ExtractionResult:
        """Estrazione multimodale (file) o testuale (file_path=None). Ritorna ExtractionResult."""
        raise NotImplementedError
