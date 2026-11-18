"""Provider LM Studio (locale su GMKtec, compatibile OpenAI), per Qwen 3.8 / Qwen 2.5."""
import re
import time
from app.config import settings
from app.services.llm_providers.base import (
    LLMProvider,
    ExtractionResult,
    get_last_retry_count,
    parse_json_with_status,
    post_with_retry,
    reset_last_retry_count,
)


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
                        "IMPORTANTE: Non fare ragionamenti lunghi, inizia IMMEDIATAMENTE a scrivere "
                        "direttamente l'oggetto JSON valido richiesto, senza testo introduttivo, conclusioni o blocchi descrittivi extra."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "seed": 7,
            "stream": False,
            "max_tokens": 8192,
        }

        timeout = getattr(settings, "lmstudio_timeout", 240)
        headers = {"Content-Type": "application/json"}
        t0 = time.monotonic()
        reset_last_retry_count()
        try:
            r = post_with_retry(url, body, headers=headers, timeout=timeout, attempts=2)
            retries = get_last_retry_count()
            duration_s = round(time.monotonic() - t0, 3)
            j = r.json()
            choices = j.get("choices") or []
            if not choices:
                return ExtractionResult(
                    {}, self.name, target_model, False, "Risposta vuota da LM Studio",
                    retries=retries, duration_s=duration_s, validation_status="empty_output",
                )

            choice = choices[0]
            finish_reason = choice.get("finish_reason")
            usage = j.get("usage")
            resp_model = j.get("model") or target_model

            txt = choice.get("message", {}).get("content", "")
            if not txt or not txt.strip():
                txt = choice.get("message", {}).get("reasoning_content", "") or ""

            if finish_reason == "length":
                return ExtractionResult(
                    {}, self.name, resp_model, False,
                    "Risposta LLM troncata per raggiungimento limite max_tokens (finish_reason=length)",
                    raw_text=txt, usage=usage,
                    retries=retries, duration_s=duration_s, validation_status="truncated_json",
                )

            cleaned = re.sub(r"<think>.*?</think>", "", txt or "", flags=re.DOTALL).strip()
            data, parse_err = parse_json_with_status(cleaned)
            if data is None:
                err_msg = "Output JSON troncato da LM Studio" if parse_err == "truncated_json" else "Output non JSON"
                return ExtractionResult(
                    {}, self.name, resp_model, False, err_msg,
                    raw_text=txt, usage=usage,
                    retries=retries, duration_s=duration_s, validation_status=parse_err or "invalid_json",
                )

            return ExtractionResult(
                data,
                self.name,
                resp_model,
                True,
                raw_text=txt,
                usage=usage,
                retries=retries,
                duration_s=duration_s,
                validation_status="valid",
            )
        except Exception as e:
            return ExtractionResult(
                {}, self.name, target_model, False, str(e),
                retries=get_last_retry_count(),
                duration_s=round(time.monotonic() - t0, 3),
                validation_status="provider_error",
            )

