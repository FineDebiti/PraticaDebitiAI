"""Provider Gemini (Google Generative Language API), multimodale via inline_data."""
import base64
import mimetypes
from app.config import settings
from app.services.llm_providers.base import LLMProvider, ExtractionResult, parse_json, post_with_retry

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def available(self) -> bool:
        return bool(settings.gemini_api_key)

    def extract(self, file_path, mime, prompt, model) -> ExtractionResult:
        parts = [{"text": prompt}]
        if file_path:
            mt = mime or mimetypes.guess_type(file_path)[0] or "application/pdf"
            with open(file_path, "rb") as f:
                parts.append({"inline_data": {"mime_type": mt, "data": base64.b64encode(f.read()).decode()}})
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        try:
            r = post_with_retry(f"{_BASE}/{model}:generateContent", body,
                                params={"key": settings.gemini_api_key},
                                timeout=120 if file_path else 90)
            j = r.json()
            txt = j["candidates"][0]["content"]["parts"][0]["text"]
            data = parse_json(txt)
            if data is None:
                return ExtractionResult({}, self.name, model, False, "output non JSON", raw_text=txt)
            return ExtractionResult(data, self.name, model, True, raw_text=txt,
                                    usage=j.get("usageMetadata"))
        except Exception as e:
            return ExtractionResult({}, self.name, model, False, str(e))
