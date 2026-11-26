"""Pipeline LangChain per la Pre-Analisi Forense della Crisi d'Impresa (DossierLex).

Attua permanentemente il protocollo metodologico a 5 step, la classificazione
epistemica [D], [R], [C], [S], [H] e i divieti di calcolo periti (AdER, CR, CTC,
ditta individuale art. 2740 c.c., raccordo RG5, realizzo concorsuale a lotti).
"""
import json
import logging
import re
from typing import Dict, Any, Tuple, Optional

_HAS_LANGCHAIN = False

from app.config import settings

logger = logging.getLogger("dossierlex.forensic_chain")

# ==============================================================================
# SYSTEM PROMPT PERMANENTE — PROTOCOLLO METODOLOGICO FORENSE
# ==============================================================================

SYSTEM_PROMPT_FORENSIC_PREANALYSIS = """Sei un Senior Restructuring Advisor e Analista Forense specializzato nella pre-analisi della crisi d'impresa e nell'applicazione del CCII (D.Lgs. 14/2019 e succ. mod.).
Il tuo compito è analizzare i documenti aziendali, contabili, bancari e fiscali forniti e produrre una diagnosi oggettiva, tracciabile e prudenziale, utile per proporre un eventuale incarico professionale successivo (non redigere un piano di risanamento o una perizia).

SEGUI TASSATIVAMENTE IL SEGUENTE PROTOCOLLO METODOLOGICO:

1. CLASSIFICAZIONE EPISTEMICA (REGOLA ANTI-ALLUCINAZIONE):
Ogni singolo valore, saldo o affermazione DEVE recare una di queste etichette:
- [D] Documentato: presente in un atto o estratto ufficiale con data, fonte e pagina esplicite.
- [R] Riferito: dichiarato verbalmente o in riunione, non provato da contabilità/atti terzi.
- [C] Calcolato: risultato di una formula aritmetica replicabile su dati certi.
- [S] Stimato: intervallo euristico o giudizio professionale motivato (mai spacciato per perizia).
- [H] Ipotesi: simulazione condizionale "what-if".

2. DIVIETI DI CALCOLO E TRATTAMENTO DATI (ZERO ERRORI CRITICI):
- Ditta Individuale (Art. 2740 c.c.): Responsabilità patrimoniale illimitata. Censire sia i debiti d'impresa sia quelli personali e le coobbligazioni (CTC/Banche per rate residue), specificando la componente di regresso.
- Riconciliazione AdER: Prendere sempre il 'Totale Residuo' (netto di sgravi, pagamenti e stralci). La voce 'di cui INPS' è una sottocomponente GIA' INCLUSA: NON risommarla. Escludere i carichi saldati e NON sommare le rate dei piani di rottamazione allo stock del debito.
- Centrale Rischi (CR): Prendere unicamente l'ultimo mese disponibile per lo stock utilizzato. NON sommare i mesi storici tra loro e NON sommare crediti ceduti all'utilizzato del cessionario senza contratti.
- Credito al Consumo (CTC): Le coobbligazioni si valutano per le rate residue. Se un rapporto (es. carta revolving Findomestic) espone solo una rata mensile in scadenza, NON prenderla come intero debito e NON usare il fido: indicare 'saldo complessivo non noto'.
- Trattamento Assenze / Lacune: Cespiti, cassa, crediti e magazzino non inventariati vanno indicati come 'n.r.' o 'non quantificabile'. È VIETATO impostare 0. Non inventare uno stato patrimoniale civilistico su contabilità semplificate.
- Raccordo Fiscale vs Gestionale: Il rigo RG5 (ricavi non annotati) spiega solo la differenza tra perdita contabile e reddito fiscale dichiarato: NON è liquidità incassata né fatturato gestionale.
- Infrannuale: Il periodo parziale moltiplicato per n (es. quadrimestre x 3) è 'riparametrato', MAI 'previsionale' o 'budget'.

3. PROTOCOLLO DEI 5 STEP OPERATIVI:
- Step 1 (Economia): Conto economico comparato (anni chiusi + infrannuale riparametrato x3). Calcola EBITDA gestionale, incidenza acquisti e personale, isola proventi straordinari e riconcilia il quadro RG.
- Step 2 (Debito): Quantifica il debito documentato certo (AdER residuo + CR ultimo mese + coobbligazioni quantificate). Separa i debiti riferiti (fornitori, TFR, locazioni). Genera il totale misto indicativo ed esplicita le divergenze aperte.
- Step 3 (Patrimonio e Realizzo): Ricognizione catastale (assenza risultanze != certezza di nullità), PRA ed elenco beni. Formula solo una stima concorsuale esplorativa a lotti (intervallo prudente vs favorevole) al netto di spese dirette (10-20%), dichiarando l'assenza di perizia.
- Step 4 (Continuità): Test diagnostici di sensitività (canoni locazione storici non registrati, costo teorico personale post-riduzione). Distingui sempre l'EBITDA dal flusso di cassa e confrontalo con il servizio del debito stimato. Non calcolare DSCR puntuali senza scadenziario.
- Step 5 (CCII): Verifica qualifica ditta individuale e soglie art. 2, co. 1, lett. d) CCII (se ricavi > 200k, escludi il concordato minore). Valuta prioritariamente la verifica di fattibilità della Composizione Negoziata (CNC ex artt. 12 ss.), mantenendo la Liquidazione Giudiziale (art. 121) come benchmark alternativo.

FORMATO DI RISPOSTA OBBLIGATORIO:
La risposta di Qwen deve sempre comporsi di due sezioni:

PARTE 1: [MATRICE_ESTRAZIONE_JSON]
Genera un blocco JSON con i valori estratti (usa `null` per OGNI campo non documentato o non quantificato nei documenti acquisiti, MAI `0.0` se il dato manca):
```json
{{
  "qualifica_ccii": "...",
  "ricavi_gestionali_ultimo_anno": null,
  "ebitda_gestionale_ultimo_anno": null,
  "ebitda_infrannuale_x3": null,
  "debito_ader_residuo_totale": null,
  "debito_ader_di_cui_inps": null,
  "cr_ultimo_saldo_utilizzato": null,
  "coobbligazioni_quantificate": null,
  "cumulo_principale_documentato": null,
  "debiti_riferiti_range": [null, null],
  "totale_misto_indicativo": [null, null],
  "realizzo_concorsuale_netto_range": [null, null],
  "dati_non_disponibili": []
}}
```

PARTE 2: [RELAZIONE_PREANALISI_CLIENTE]
Relazione strutturata secondo la mappa del documento in 7 capitoli (Executive Summary con 4 numeri chiave, Profilo e Conto Economico, Indebitamento Ricostruito, Patrimonio e Confronto Liquidatorio, Redditività e Continuità, Inquadramento CCII, Conclusioni e Proposta di Incarico)."""

HUMAN_PROMPT_TEMPLATE = """Avvia la pre-analisi forense ed economico-finanziaria per il seguente cliente:

CLIENTE: {nome_cliente}
DATA ANALISI: {data_analisi}

DOCUMENTI E FONTI DISPONIBILI:
{documenti_testo}

Esegui il protocollo dei 5 step con classificazione epistemica [D], [R], [C], [S], [H] e genera rigorosamente:
PARTE 1: [MATRICE_ESTRAZIONE_JSON]
PARTE 2: [RELAZIONE_PREANALISI_CLIENTE]"""


from pydantic import BaseModel, ConfigDict, Field
from app.services.llm_providers.base import parse_json_with_status


class ForensicMatrixSchema(BaseModel):
    """Schema validato per PARTE 1 della catena forense (accetta null per dati assenti)."""
    model_config = ConfigDict(extra="allow")

    qualifica_ccii: Optional[str] = None
    ricavi_gestionali_ultimo_anno: Optional[float] = None
    ebitda_gestionale_ultimo_anno: Optional[float] = None
    ebitda_infrannuale_x3: Optional[float] = None
    debito_ader_residuo_totale: Optional[float] = None
    debito_ader_di_cui_inps: Optional[float] = None
    cr_ultimo_saldo_utilizzato: Optional[float] = None
    coobbligazioni_quantificate: Optional[float] = None
    cumulo_principale_documentato: Optional[float] = None
    debiti_riferiti_range: Optional[list] = None
    totale_misto_indicativo: Optional[list] = None
    realizzo_concorsuale_netto_range: Optional[list] = None
    dati_non_disponibili: list = Field(default_factory=list)


class _DirectHttpForensicChain:
    """Fallback compatibile con .invoke() via httpx diretto su endpoint OpenAI/LM Studio."""

    def __init__(self, base_url: str, model: str, temperature: float, timeout: int):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.last_usage: Dict[str, Any] = {}
        self.last_model: str = model
        self.last_retries: int = 0
        self.last_finish_reason: str | None = None

    def invoke(self, inputs: Dict[str, Any]) -> str:
        from app.services.llm_providers.base import post_with_retry, get_last_retry_count, reset_last_retry_count
        sys_msg = SYSTEM_PROMPT_FORENSIC_PREANALYSIS.replace("{{", "{").replace("}}", "}")
        user_msg = HUMAN_PROMPT_TEMPLATE.format(
            nome_cliente=inputs.get("nome_cliente", ""),
            data_analisi=inputs.get("data_analisi", ""),
            documenti_testo=inputs.get("documenti_testo", ""),
        )
        reset_last_retry_count()
        resp = post_with_retry(
            f"{self.base_url}/chat/completions",
            {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": 4096,
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=self.timeout,
            attempts=2,
        )
        self.last_retries = get_last_retry_count()
        data = resp.json()
        self.last_usage = data.get("usage") or {}
        self.last_model = data.get("model") or self.model
        choice = (data.get("choices") or [{}])[0]
        self.last_finish_reason = choice.get("finish_reason")
        return (choice.get("message") or {}).get("content") or ""


def get_forensic_chain(temperature: float = 0.1):
    """Costruisce la catena HTTP diretta configurata su Qwen (endpoint locale LM Studio)."""
    base_url = settings.lmstudio_base_url.rstrip("/")
    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"
    timeout = 180
    return _DirectHttpForensicChain(base_url, target_model, temperature, timeout)


def parse_forensic_output(raw_output: str) -> Tuple[Dict[str, Any], str]:
    """Separa e valida con Pydantic PARTE 1 [MATRICE_ESTRAZIONE_JSON] e PARTE 2 [RELAZIONE_PREANALISI_CLIENTE]."""
    json_matrix: Dict[str, Any] = {}
    client_report_text = ""

    # Estrazione blocco JSON (Parte 1) con parse_json_with_status (nessuna riparazione silenziosa di troncamenti)
    json_match = re.search(r"PARTE 1:\s*\[MATRICE_ESTRAZIONE_JSON\]\s*```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if not json_match:
        json_match = re.search(r"```(?:json)?\s*(\{\s*\"qualifica_ccii\".*?\})\s*```", raw_output, re.DOTALL)
    if not json_match:
        json_match = re.search(r"(?:PARTE 1:\s*\[MATRICE_ESTRAZIONE_JSON\]\s*)?```(?:json)?\s*(\{.*)", raw_output, re.DOTALL)

    if json_match:
        raw_block = re.split(r"PARTE 2:", json_match.group(1), maxsplit=1)[0].strip()
        raw_block = re.sub(r"```\s*$", "", raw_block).strip()
        parsed, parse_err = parse_json_with_status(raw_block)
        if parsed is not None:
            try:
                validated = ForensicMatrixSchema.model_validate(parsed)
                json_matrix = validated.model_dump()
            except Exception as exc:
                logger.warning("Validazione schema matrice forense fallita: %s", exc)
                json_matrix = {"_validation_error": str(exc), "_raw_parsed": parsed}
        else:
            logger.warning("Errore parsing JSON matrice preanalisi: %s", parse_err)
            json_matrix = {"_validation_error": parse_err or "invalid_json"}

    # Estrazione testo cliente (Parte 2)
    parte2_split = re.split(r"PARTE 2:\s*\[RELAZIONE_PREANALISI_CLIENTE\]", raw_output, maxsplit=1)
    if len(parte2_split) > 1:
        client_report_text = parte2_split[1].strip()
    else:
        if json_match:
            end_pos = json_match.end()
            client_report_text = raw_output[end_pos:].strip()
        else:
            client_report_text = raw_output.strip()

    return json_matrix, client_report_text


def _split_forensic_chunks(documenti_testo: str, max_chunk_chars: int = 24000, max_chunks: int = 6) -> Tuple[list[str], bool]:
    """Suddivide documenti lunghi in blocchi omogenei per analisi multi-passaggio senza tagli muti."""
    if len(documenti_testo) <= max_chunk_chars:
        return [documenti_testo], False
    chunks: list[str] = []
    pos = 0
    total = len(documenti_testo)
    while pos < total and len(chunks) < max_chunks:
        end = min(total, pos + max_chunk_chars)
        if end < total:
            nl = documenti_testo.rfind("\n", pos + int(max_chunk_chars * 0.7), end)
            if nl > pos:
                end = nl + 1
        chunks.append(documenti_testo[pos:end])
        pos = end
    return chunks, pos < total


def _invoke_forensic_once(chain: Any, nome_cliente: str, data_analisi: str, payload_text: str, default_model: str) -> Dict[str, Any]:
    try:
        res_msg = chain.invoke({
            "nome_cliente": nome_cliente,
            "data_analisi": data_analisi,
            "documenti_testo": payload_text,
        })
        if isinstance(res_msg, str):
            return {
                "raw_output": res_msg,
                "usage": getattr(chain, "last_usage", {}) or {},
                "model": getattr(chain, "last_model", default_model) or default_model,
                "retries": int(getattr(chain, "last_retries", 0) or 0),
                "finish_reason": getattr(chain, "last_finish_reason", None),
                "error": None,
            }
        raw_output = getattr(res_msg, "content", "") or ""
        resp_meta = getattr(res_msg, "response_metadata", {}) or {}
        return {
            "raw_output": raw_output,
            "usage": resp_meta.get("token_usage") or getattr(res_msg, "usage_metadata", {}) or {},
            "model": resp_meta.get("model_name") or resp_meta.get("model") or default_model,
            "retries": 0,
            "finish_reason": resp_meta.get("finish_reason"),
            "error": None,
        }
    except Exception as e:
        logger.error(f"Errore invocazione LangChain Qwen: {e}")
        return {
            "raw_output": "",
            "usage": {},
            "model": default_model,
            "retries": int(getattr(chain, "last_retries", 0) or 0),
            "finish_reason": None,
            "error": str(e),
        }


def run_forensic_preanalysis_chain(
    nome_cliente: str,
    data_analisi: str,
    documenti_testo: str,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """Invocazione completa (singola o multi-passaggio) con validazione JSON e telemetria completa."""
    import time
    t0 = time.time()
    logger.info(f"Avvio Forensic Preanalysis Chain per '{nome_cliente}' al {data_analisi}")

    max_input_chars = 30000
    chain = get_forensic_chain(temperature=temperature)
    actual_model = settings.lmstudio_model or ""
    actual_provider = "lmstudio" if (settings.llm_provider or "lmstudio") in ("lmstudio", "stub") else settings.llm_provider

    multi_pass = len(documenti_testo) > max_input_chars
    total_retries = 0
    partial_coverage = False
    if not multi_pass:
        chunks = [documenti_testo]
        inv = _invoke_forensic_once(chain, nome_cliente, data_analisi, documenti_testo, actual_model)
        raw_output = inv["raw_output"]
        actual_usage = inv["usage"]
        actual_model = inv["model"]
        total_retries += inv["retries"]
        inv_error = inv["error"]
        finish_reason = inv["finish_reason"]
        chunks_processed = 1
        chars_sent = len(documenti_testo)
    else:
        chunks, partial_coverage = _split_forensic_chunks(documenti_testo, max_chunk_chars=24000, max_chunks=6)
        partial_summaries: list[str] = []
        chars_sent = 0
        inv_error = None
        finish_reason = None
        actual_usage: Dict[str, Any] = {}
        for idx, ch in enumerate(chunks, 1):
            chars_sent += len(ch)
            sub_res = _invoke_forensic_once(
                chain, nome_cliente, data_analisi,
                f"[PASSAGGIO PARZIALE {idx}/{len(chunks)} - NON CONCLUDERE COME DEFINITIVO]\n{ch}",
                actual_model,
            )
            total_retries += sub_res["retries"]
            if sub_res["error"] and not inv_error:
                inv_error = sub_res["error"]
            mat_sub, rep_sub = parse_forensic_output(sub_res["raw_output"])
            partial_summaries.append(
                f"--- ESTRATTO PASSAGGIO {idx}/{len(chunks)} ---\n"
                f"MATRICE: {json.dumps(mat_sub, ensure_ascii=False)}\n"
                f"NOTE: {rep_sub[:2000]}"
            )
        cov_notice = (
            "[AVVISO COPERTURA PARZIALE: documenti eccedenti la finestra di consolidamento multi-passaggio.]\n"
            if partial_coverage else
            f"[CONSOLIDAMENTO INTEGRALE DI {len(chunks)} PASSAGGI DOCUMENTALI]\n"
        )
        consolidation_payload = cov_notice + "\n\n".join(partial_summaries)
        inv = _invoke_forensic_once(chain, nome_cliente, data_analisi, consolidation_payload[:max_input_chars], actual_model)
        raw_output = inv["raw_output"]
        actual_usage = inv["usage"]
        actual_model = inv["model"]
        total_retries += inv["retries"]
        inv_error = inv["error"] or inv_error
        finish_reason = inv["finish_reason"]
        chunks_processed = len(chunks)

    elapsed_s = round(time.time() - t0, 1)
    json_matrix, client_report_text = parse_forensic_output(raw_output)

    if inv_error:
        validation_status = "provider_error"
    elif finish_reason == "length":
        validation_status = "truncated_output"
        if "_validation_error" not in json_matrix:
            json_matrix["_validation_error"] = "finish_reason=length"
    elif not raw_output.strip():
        validation_status = "empty_output"
    elif "_validation_error" in json_matrix or not json_matrix:
        validation_status = "validation_error"
    else:
        validation_status = "valid"

    logger.info(
        "Forensic Preanalysis Chain completata in %ss (model=%s, status=%s, multi_pass=%s, partial=%s)",
        elapsed_s, actual_model, validation_status, multi_pass, partial_coverage,
    )

    return {
        "raw_output": raw_output,
        "json_matrix": json_matrix,
        "client_report_text": client_report_text,
        "telemetry": {
            "elapsed_seconds": elapsed_s,
            "duration_s": elapsed_s,
            "usage": actual_usage,
            "prompt_tokens": actual_usage.get("prompt_tokens") or actual_usage.get("input_tokens"),
            "completion_tokens": actual_usage.get("completion_tokens") or actual_usage.get("output_tokens"),
            "total_tokens": actual_usage.get("total_tokens"),
            "model": actual_model,
            "provider": actual_provider,
            "retries": total_retries,
            "error": inv_error,
            "fallback_used": False,
            "validation_status": validation_status,
            "input_truncated": partial_coverage,
            "multi_pass": multi_pass,
            "chunks_total": len(chunks),
            "chunks_processed": chunks_processed,
            "partial_coverage": partial_coverage,
            "input_chars_total": len(documenti_testo),
            "input_chars_sent": chars_sent,
        },
    }
