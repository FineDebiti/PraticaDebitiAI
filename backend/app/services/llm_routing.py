"""Routing del modello Gemini in base al doc_type.

Pro sui documenti ad alta posta in gioco (volume o importi che si propagano),
Flash per tutti gli altri. Un solo punto da toccare per cambiare il routing.
"""
from app.config import settings

# doc_type che vanno su Gemini 2.5 Pro. Tutti gli altri -> default (Flash).
# Devono coincidere ESATTAMENTE con i doc_type del classificatore / EXTRACT_PROMPTS.
PRO_DOC_TYPES = {
    "centrale_rischi",        # molte pagine, serie storica, criticità/garanzie
    "bilancio",              # importi -> indici professionali, l'errore si propaga
    "busta_paga",            # reddito netto -> capacità di rimborso, importo critico
    # NB: dichiarazione_redditi NON è Pro: sul campione le macro-cifre (reddito per
    # quadro, complessivo) sono identiche a Flash; il micro-dettaglio RB non si
    # stabilizza nemmeno su Pro -> Flash multimodale, costo molto più basso.
    # NB: cartella_aer NON è qui di proposito: l'estrazione è il parser tabellare;
    # il fallback AI (raro) usa Flash, non Pro/GPT (risparmio, doc semplice da leggere).
}


def model_for_doc_type(doc_type: str | None) -> str:
    """Nome del modello Gemini da usare per questo doc_type (back-compat)."""
    return model_for_provider("gemini", doc_type)


def model_for_provider(provider: str, doc_type: str | None) -> str:
    """Nome del modello da usare per (provider, doc_type). Pro sui doc ad alta posta."""
    is_pro = bool(doc_type and doc_type in PRO_DOC_TYPES)
    if provider == "gemini":
        default = settings.gemini_model_default or settings.llm_model or "gemini-2.5-flash"
        return (settings.gemini_model_pro or default) if is_pro else default
    if provider == "claude":
        return (settings.claude_model_pro or settings.claude_model) if is_pro else settings.claude_model
    if provider == "openai":
        return settings.openai_model
    # provider sconosciuto: ripiega sul default Gemini
    return settings.gemini_model_default or "gemini-2.5-flash"
