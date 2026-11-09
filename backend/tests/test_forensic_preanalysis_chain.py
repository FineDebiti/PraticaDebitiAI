import pytest
from app.services.forensic_preanalysis_chain import (
    get_forensic_chain,
    parse_forensic_output,
    SYSTEM_PROMPT_FORENSIC_PREANALYSIS,
    HUMAN_PROMPT_TEMPLATE,
)


def test_forensic_chain_prompt_and_template():
    # Verifica che il prompt contenga le regole e i divieti del protocollo
    assert "Senior Restructuring Advisor" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "[D] Documentato" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "[R] Riferito" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "[C] Calcolato" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "[S] Stimato" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "[H] Ipotesi" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "di cui INPS" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "rigo RG5" in SYSTEM_PROMPT_FORENSIC_PREANALYSIS
    assert "Art. 2740 c.c." in SYSTEM_PROMPT_FORENSIC_PREANALYSIS

    # Verifica variabili template
    assert "{nome_cliente}" in HUMAN_PROMPT_TEMPLATE
    assert "{data_analisi}" in HUMAN_PROMPT_TEMPLATE
    assert "{documenti_testo}" in HUMAN_PROMPT_TEMPLATE

    # Verifica chain
    chain = get_forensic_chain(temperature=0.1)
    assert chain is not None


def test_parse_forensic_output():
    sample_output = """
PARTE 1: [MATRICE_ESTRAZIONE_JSON]
```json
{
  "qualifica_ccii": "Ditta individuale non minore",
  "ricavi_gestionali_ultimo_anno": 493094.0,
  "ebitda_gestionale_ultimo_anno": -43440.0,
  "ebitda_infrannuale_x3": 1202.0,
  "debito_ader_residuo_totale": 386695.79,
  "debito_ader_di_cui_inps": 210604.29,
  "cr_ultimo_saldo_utilizzato": 133460.0,
  "coobbligazioni_quantificate": 2945.0,
  "cumulo_principale_documentato": 523100.79,
  "debiti_riferiti_range": [290000.0, 360000.0],
  "totale_misto_indicativo": [813100.79, 883100.79],
  "realizzo_concorsuale_netto_range": [20000.0, 65000.0],
  "dati_non_disponibili": ["saldo_findomestic", "inventario_officina"]
}
```

PARTE 2: [RELAZIONE_PREANALISI_CLIENTE]
01 / PROFILO E CONTO ECONOMICO
Attività artigiana di produzione infissi a Palermo.
02 / INDEBITAMENTO RICOSTRUITO
Esposizioni principali quantificate per € 523.100,79.
"""

    matrix, report_text = parse_forensic_output(sample_output)
    assert matrix.get("ricavi_gestionali_ultimo_anno") == 493094.0
    assert matrix.get("cumulo_principale_documentato") == 523100.79
    assert matrix.get("debito_ader_residuo_totale") == 386695.79
    assert matrix.get("debito_ader_di_cui_inps") == 210604.29
    assert "PROFILO E CONTO ECONOMICO" in report_text
    assert "523.100,79" in report_text
