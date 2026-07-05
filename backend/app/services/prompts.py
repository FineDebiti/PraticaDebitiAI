"""MODULO PONTE (compatibilita).

I prompt sono stati riorganizzati nel pacchetto `doc_prompts/`, un file per
tipo di documento. Questo modulo ri-esporta tutto, cosi gli import esistenti
(`from app.services.prompts import ...`) continuano a funzionare senza modifiche.

Per lavorare su un documento, apri il suo file in `doc_prompts/`.
"""
from app.services.doc_prompts import (  # noqa: F401
    CLASSIFY_PROMPT,
    _COMMON_RULES,
    GENERIC_EXTRACT_PROMPT,
    EXTRACT_PROMPT,
    EXTRACT_PROMPTS,
    DOC_TYPES,
    get_extract_prompt,
)
