"""Provider OpenAI (Responses API), PDF/immagini via input_file/input_image."""
import base64
import mimetypes
from app.config import settings
from app.services.llm_providers.base import LLMProvider, ExtractionResult, parse_json, post_with_retry


class OpenAIProvider(LLMProvider):
    name = "openai"

    def available(self) -> bool:
        return bool(settings.openai_api_key)

    def extract(self, file_path, mime, prompt, model) -> ExtractionResult:
        content = [{"type": "input_text", "text": prompt}]
        if file_path:
            mt = mime or mimetypes.guess_type(file_path)[0] or "application/pdf"
            with open(file_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            data_uri = f"data:{mt};base64,{b64}"
            if mt == "application/pdf":
                content.append({"type": "input_file", "filename": "documento.pdf", "file_data": data_uri})
            else:
                content.append({"type": "input_image", "image_url": data_uri})
        body = {
            "model": model,
            "input": [{"role": "user", "content": content}],
            "text": {"format": {"type": "json_object"}},
        }
        headers = {"Authorization": f"Bearer {settings.openai_api_key}", "content-type": "application/json"}
        try:
            r = post_with_retry("https://api.openai.com/v1/responses", body, headers=headers, timeout=120)
            j = r.json()
            txt = j.get("output_text") or _dig_output_text(j)
            data = parse_json(txt or "")
            if data is None:
                return ExtractionResult({}, self.name, model, False, "output non JSON", raw_text=txt)
            return ExtractionResult(data, self.name, model, True, raw_text=txt, usage=j.get("usage"))
        except Exception as e:
            return ExtractionResult({}, self.name, model, False, str(e))


def _dig_output_text(j: dict) -> str:
    """Estrae il testo dall'array output[] della Responses API."""
    out = []
    for item in j.get("output", []) or []:
        for c in item.get("content", []) or []:
            if c.get("type") in ("output_text", "text") and c.get("text"):
                out.append(c["text"])
    return "".join(out)
