"""Provider Claude (Anthropic Messages API), PDF nativo via document block."""
import base64
import mimetypes
from app.config import settings
from app.services.llm_providers.base import LLMProvider, ExtractionResult, parse_json, post_with_retry


class ClaudeProvider(LLMProvider):
    name = "claude"

    def available(self) -> bool:
        return bool(settings.anthropic_api_key)

    def extract(self, file_path, mime, prompt, model) -> ExtractionResult:
        content = []
        if file_path:
            mt = mime or mimetypes.guess_type(file_path)[0] or "application/pdf"
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            if mt == "application/pdf":
                content.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}})
            else:
                content.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": b64}})
        content.append({"type": "text", "text": prompt})
        body = {"model": model, "max_tokens": 8000, "messages": [{"role": "user", "content": content}]}
        headers = {"x-api-key": settings.anthropic_api_key, "anthropic-version": "2023-06-01",
                   "content-type": "application/json"}
        try:
            r = post_with_retry("https://api.anthropic.com/v1/messages", body, headers=headers, timeout=120)
            j = r.json()
            txt = "".join(b.get("text", "") for b in j.get("content", []) if b.get("type") == "text")
            data = parse_json(txt)
            if data is None:
                return ExtractionResult({}, self.name, model, False, "output non JSON", raw_text=txt)
            return ExtractionResult(data, self.name, model, True, raw_text=txt, usage=j.get("usage"))
        except Exception as e:
            return ExtractionResult({}, self.name, model, False, str(e))
