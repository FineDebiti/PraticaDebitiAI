"""Pipeline LangChain per la Pre-Analisi Forense della Crisi d'Impresa (DossierLex).

Attua permanentemente il protocollo metodologico a 5 step, la classificazione
epistemica [D], [R], [C], [S], [H] e i divieti di calcolo periti (AdER, CR, CTC,
ditta individuale art. 2740 c.c., raccordo RG5, realizzo concorsuale a lotti).
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

try:
    from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    from langchain_openai import ChatOpenAI
    _HAS_LANGCHAIN = True
except ImportError:
    ChatPromptTemplate = None
    SystemMessagePromptTemplate = None
    HumanMessagePromptTemplate = None
    StrOutputParser = None
    ChatOpenAI = None
    _HAS_LANGCHAIN = False

from app.config import settings
from app.services.statutory_knowledge import (
    calculate_ebitda_oic12,
    calculate_pfn_esma,
    evaluate_pfn_ebitda,
    check_ccii_soglie_impresa_minore,
    calculate_test_pratico_ministeriale,
    evaluate_risanabilita_diagnosi,
    classify_cinque_criticita,
    identify_documenti_indispensabili,
)

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
Genera un blocco JSON con i valori estratti per ancorare la coerenza numerica nella memoria del modello prima della scrittura:
```json
{{
  "qualifica_ccii": "...",
  "ricavi_gestionali_ultimo_anno": 0.0,
  "ebitda_gestionale_ultimo_anno": 0.0,
  "ebitda_infrannuale_x3": 0.0,
  "debito_ader_residuo_totale": 0.0,
  "debito_ader_di_cui_inps": 0.0,
  "cr_ultimo_saldo_utilizzato": 0.0,
  "coobbligazioni_quantificate": 0.0,
  "cumulo_principale_documentato": 0.0,
  "debiti_riferiti_range": [0.0, 0.0],
  "totale_misto_indicativo": [0.0, 0.0],
  "realizzo_concorsuale_netto_range": [0.0, 0.0],
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


class _DirectHttpForensicChain:
    """Fallback compatibile con .invoke() via httpx diretto su endpoint OpenAI/LM Studio."""

    def __init__(self, base_url: str, model: str, temperature: float, timeout: int):
        self.base_url = base_url
        self.model = model
        self.temperature = temperature
        self.timeout = timeout

    def invoke(self, inputs: Dict[str, Any]) -> str:
        import httpx
        sys_msg = SYSTEM_PROMPT_FORENSIC_PREANALYSIS.replace("{{", "{").replace("}}", "}")
        user_msg = HUMAN_PROMPT_TEMPLATE.format(
            nome_cliente=inputs.get("nome_cliente", ""),
            data_analisi=inputs.get("data_analisi", ""),
            documenti_testo=inputs.get("documenti_testo", ""),
        )
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": 1500,
                "messages": [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg},
                ],
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def get_forensic_chain(temperature: float = 0.1):
    """Costruisce la catena LangChain configurata su Qwen (endpoint locale LM Studio)."""
    base_url = settings.lmstudio_base_url.rstrip("/")
    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"
    timeout = 180

    if not _HAS_LANGCHAIN:
        return _DirectHttpForensicChain(base_url, target_model, temperature, timeout)

    llm = ChatOpenAI(
        base_url=base_url,
        model=target_model,
        temperature=temperature,
        api_key="not-needed",
        timeout=timeout,
        max_tokens=1500,
        max_retries=0,
    )

    prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT_FORENSIC_PREANALYSIS),
        HumanMessagePromptTemplate.from_template(HUMAN_PROMPT_TEMPLATE),
    ])

    return prompt | llm | StrOutputParser()


def parse_forensic_output(raw_output: str) -> Tuple[Dict[str, Any], str]:
    """Separa e valida PARTE 1 [MATRICE_ESTRAZIONE_JSON] e PARTE 2 [RELAZIONE_PREANALISI_CLIENTE]."""
    json_matrix = {}
    client_report_text = ""

    # Estrazione blocco JSON (Parte 1)
    json_match = re.search(r"PARTE 1:\s*\[MATRICE_ESTRAZIONE_JSON\]\s*```(?:json)?\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
    if not json_match:
        # Fallback se non ci sono i tag esatti ma un blocco json all'inizio
        json_match = re.search(r"```(?:json)?\s*(\{\s*\"qualifica_ccii\".*?\})\s*```", raw_output, re.DOTALL)

    if json_match:
        try:
            json_matrix = json.loads(json_match.group(1))
        except Exception as e:
            logger.warning(f"Errore parsing JSON matrice preanalisi: {e}")

    # Estrazione testo cliente (Parte 2)
    parte2_split = re.split(r"PARTE 2:\s*\[RELAZIONE_PREANALISI_CLIENTE\]", raw_output, maxsplit=1)
    if len(parte2_split) > 1:
        client_report_text = parte2_split[1].strip()
    else:
        # Se non c'è il marker, prendi tutto ciò che segue il blocco json
        if json_match:
            end_pos = json_match.end()
            client_report_text = raw_output[end_pos:].strip()
        else:
            client_report_text = raw_output.strip()

    return json_matrix, client_report_text


def run_forensic_preanalysis_chain(
    nome_cliente: str,
    data_analisi: str,
    documenti_testo: str,
    temperature: float = 0.1,
) -> Dict[str, Any]:
    """Invocazione completa della catena LangChain Forense per DossierLex."""
    import time
    t0 = time.time()
    logger.info(f"Avvio Forensic Preanalysis Chain per '{nome_cliente}' al {data_analisi}")

    chain = get_forensic_chain(temperature=temperature)

    try:
        raw_output = chain.invoke({
            "nome_cliente": nome_cliente,
            "data_analisi": data_analisi,
            "documenti_testo": documenti_testo[:15000],  # budget tokens safe
        })
    except Exception as e:
        logger.error(f"Errore invocazione LangChain Qwen: {e}")
        raw_output = ""

    elapsed_s = round(time.time() - t0, 1)
    prompt_tokens_est = (len(documenti_testo[:15000]) + len(SYSTEM_PROMPT_FORENSIC_PREANALYSIS)) // 4
    completion_tokens_est = len(raw_output) // 4
    total_tokens_est = prompt_tokens_est + completion_tokens_est

    json_matrix, client_report_text = parse_forensic_output(raw_output)

    logger.info(f"Forensic Preanalysis Chain completata in {elapsed_s}s (~{total_tokens_est} token totali, di cui ~{completion_tokens_est} generati)")

    return {
        "raw_output": raw_output,
        "json_matrix": json_matrix,
        "client_report_text": client_report_text,
        "telemetry": {
            "elapsed_seconds": elapsed_s,
            "prompt_tokens_approx": prompt_tokens_est,
            "completion_tokens_approx": completion_tokens_est,
            "total_tokens_approx": total_tokens_est,
            "model": "qwen/qwen3.8-27b",
            "provider": "lmstudio",
        },
    }
