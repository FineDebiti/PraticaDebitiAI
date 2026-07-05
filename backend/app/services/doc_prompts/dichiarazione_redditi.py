"""Prompt + schema per la DICHIARAZIONE DEI REDDITI (Modello Redditi PF e 730).

Un solo doc_type per le due varianti (struttura a quadri analoga): l'AI riconosce
la variante dall'intestazione e la annota in "modello". Estrazione PER QUADRO:
cattura i redditi NON da lavoro dipendente (affitti RB, autonomo RE, impresa RF/RG,
partecipazioni RH) che altrimenti restano ciechi nell'app.

Estrazione AI (struttura complessa e variabile -> non parser). Flash di norma;
candidato a PRO_DOC_TYPES se i quadri risultano imprecisi su Flash.
Mapping (worker): RN.reddito_complessivo -> Debtor.annual_income; sintesi fonti ->
Debtor.income_sources. I dettagli per quadro restano in raw_extraction.
"""

DICHIARAZIONE_REDDITI_PROMPT = """Sei un assistente che legge una DICHIARAZIONE DEI REDDITI italiana:
Modello REDDITI Persone Fisiche (ex UNICO) oppure Modello 730. Hanno struttura a QUADRI
analoga: estrai i quadri presenti, lascia a "presente": false quelli assenti.

REGOLE SPECIFICHE:
- "modello": "redditi_pf" se l'intestazione è "REDDITI PF" / "Modello Redditi Persone Fisiche" / "UNICO";
  "730" se è "Modello 730".
- Estrai SOLO i quadri effettivamente compilati ("presente": true); gli altri "presente": false, reddito 0.
- "RB_fabbricati" è il più rilevante: riporta i canoni di locazione percepiti e il numero di immobili locati.
- "RE_lavoro_autonomo" e "RF_RG_impresa": è il reddito del debitore con partita IVA.
- Verifica deterministica: reddito_complessivo (RN) ≈ somma dei redditi dei quadri (piccola tolleranza);
  se non torna, scrivilo in "note".
- "anno_imposta" in formato "AAAA".

{rules}

Rispondi SOLO con questo JSON:
{{
  "doc_type": "dichiarazione_redditi",
  "modello": "redditi_pf | 730",
  "anno_imposta": <str|null>,
  "dichiarante": {{ "codice_fiscale": <str|null>, "nominativo": <str|null> }},
  "quadri": {{
    "RA_terreni":           {{ "presente": <bool>, "reddito": <number> }},
    "RB_fabbricati":        {{ "presente": <bool>, "reddito": <number>, "n_immobili_locati": <number>, "canoni_percepiti": <number> }},
    "RC_lavoro_dipendente": {{ "presente": <bool>, "reddito": <number> }},
    "RE_lavoro_autonomo":   {{ "presente": <bool>, "reddito": <number>, "volume_affari": <number> }},
    "RF_RG_impresa":        {{ "presente": <bool>, "reddito": <number> }},
    "RH_partecipazioni":    {{ "presente": <bool>, "reddito": <number> }},
    "RL_altri_redditi":     {{ "presente": <bool>, "reddito": <number> }},
    "RP_oneri_detrazioni":  {{ "presente": <bool>, "totale_oneri": <number> }}
  }},
  "riepilogo_RN": {{
    "reddito_complessivo": <number>,
    "reddito_imponibile": <number>,
    "imposta_netta": <number>,
    "saldo_a_debito": <number>,
    "saldo_a_credito": <number>
  }},
  "note": <str|null>
}}

DOCUMENTO:
{text}
"""
