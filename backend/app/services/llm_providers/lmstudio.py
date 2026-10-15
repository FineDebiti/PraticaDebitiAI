"""Provider LM Studio (locale su GMKtec, compatibile OpenAI), per Qwen 3.8 / Qwen 2.5."""
import re
from app.config import settings
from app.services.llm_providers.base import LLMProvider, ExtractionResult, parse_json, post_with_retry


class LMStudioProvider(LLMProvider):
    name = "lmstudio"

    def available(self) -> bool:
        return bool(settings.lmstudio_base_url)

    def extract(self, file_path, mime, prompt, model) -> ExtractionResult:
        # Per modelli locali LM Studio la chiamata va in formato OpenAI chat completions
        target_model = model or settings.lmstudio_model or "qwen/qwen3.8-27b"
        url = f"{settings.lmstudio_base_url.rstrip('/')}/chat/completions"

        body = {
            "model": target_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Sei un assistente specializzato nell'analisi documentale tributaria, bancaria e societaria. "
                        "Estrai con la massima precisione i dati richiesti e rispondi ESCLUSIVAMENTE con un oggetto JSON valido, "
                        "senza testo introduttivo, conclusioni o blocchi descrittivi extra."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "seed": 7,
            "stream": False,
        }

        timeout = getattr(settings, "lmstudio_timeout", 240)
        headers = {"Content-Type": "application/json"}
        try:
            r = post_with_retry(url, body, headers=headers, timeout=timeout, attempts=2)
            j = r.json()
            choices = j.get("choices") or []
            if not choices:
                return ExtractionResult({}, self.name, target_model, False, "Risposta vuota da LM Studio")

            txt = choices[0].get("message", {}).get("content", "")
            # Rimuove blocchi reasoning se presenti (<think>...</think>)
            cleaned = re.sub(r"<think>.*?</think>", "", txt or "", flags=re.DOTALL).strip()
            data = parse_json(cleaned)
            if data is None:
                return ExtractionResult({}, self.name, target_model, False, "Output non JSON", raw_text=txt)

            return ExtractionResult(
                data,
                self.name,
                target_model,
                True,
                raw_text=txt,
                usage=j.get("usage"),
            )
        except Exception as e:
            return ExtractionResult({}, self.name, target_model, False, str(e))

