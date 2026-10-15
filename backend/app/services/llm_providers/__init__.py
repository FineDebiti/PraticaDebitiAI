"""Registry dei provider LLM. Un nome -> un'istanza intercambiabile."""
from app.services.llm_providers.base import LLMProvider, ExtractionResult
from app.services.llm_providers.gemini import GeminiProvider
from app.services.llm_providers.claude import ClaudeProvider
from app.services.llm_providers.openai import OpenAIProvider
from app.services.llm_providers.lmstudio import LMStudioProvider

REGISTRY = {
    "lmstudio": LMStudioProvider(),
    "gemini": GeminiProvider(),
    "claude": ClaudeProvider(),
    "openai": OpenAIProvider(),
}
