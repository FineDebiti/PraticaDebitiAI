from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pratica:pratica@db:5432/pratica_debiti"
    redis_url: str = "redis://redis:6379/0"
    storage_dir: str = "/code/storage"   # (legacy) percorso vecchio, per documenti pre-storage

    # Indice CF cross-pratica (avviso correlati GDPR-safe). Disattivabile.
    cross_case_index_enabled: bool = True

    # Cruscotto indicatori: anni oltre i quali una cartella AER è "datata" (solo per
    # EVIDENZIARE possibile prescrizione: la valutazione resta al legale).
    aer_signal_anni: int = 5

    # --- Storage file originali (astrazione GCS-ready) ---
    storage_backend: str = "local"       # local | gcs
    storage_local_path: str = "/data/uploads"   # volume Docker dedicato e persistente
    gcs_bucket: str = ""                  # (futuro) bucket UE per GCS

    # Provider switch
    ocr_provider: str = "tesseract"   # "docai" | "tesseract"
    llm_provider: str = "stub"        # "gemini" | "openai" | "anthropic" | "stub"
    llm_model: str = ""               # (legacy) modello fisso; se vuoto si usano i due sotto
    # Routing modello per doc_type: Pro sui documenti ad alta posta, Flash per gli altri.
    gemini_model_default: str = "gemini-2.5-flash"
    gemini_model_pro: str = "gemini-2.5-pro"
    # Modelli degli altri provider (usati nella catena di fallback / cross-check).
    claude_model: str = "claude-sonnet-4-6"
    claude_model_pro: str = ""        # se vuoto usa claude_model anche sui doc Pro
    openai_model: str = "gpt-4o"
    # Resilienza multi-provider: catena di fallback e doc_type sottoposti a cross-check.
    llm_fallback_chain: str = "gemini,claude,openai"
    crosscheck_doc_types: str = "bilancio,centrale_rischi"

    # Document AI
    docai_project_id: str = ""
    docai_location: str = "eu"
    docai_processor_id: str = ""
    google_application_credentials: str = ""

    # LLM keys
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # --- Openapi / Visengine (arricchimento scheda da fonti esterne) ---
    # enrichment_mode: "stub" (simulato, gratis) | "openapi" (reale, a pagamento)
    enrichment_mode: str = "stub"
    openapi_token: str = ""
    # dominio: produzione o sandbox di test (test non addebita)
    openapi_base_url: str = "https://test.visengine2.altravia.com"
    # secondi massimi di attesa risultato in polling sincrono
    openapi_poll_timeout: int = 25

    # --- Openapi COMPANY (API sincrona dati azienda IT, 100 req/giorno gratis) ---
    # Prodotto e token DIVERSI da Visengine. Base url: company.openapi.com (prod) / test.company.openapi.com (sandbox)
    company_token: str = ""
    company_base_url: str = "https://test.company.openapi.com"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
