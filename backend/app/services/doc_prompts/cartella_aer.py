"""Prompt + schema per l'ESTRATTO DI RUOLO Agenzia delle Entrate-Riscossione (AER).

FALLBACK: usato solo se il parser tabellare deterministico (aer_parser.py) fallisce
(PDF scansionato / layout anomalo). Modello Flash (NON Pro/GPT): il documento è una
semplice tabella da leggere. Lo schema deve combaciare con quello del parser.
"""

CARTELLA_AER_PROMPT = """Sei un assistente che legge l'ESTRATTO DI RUOLO dell'Agenzia delle Entrate-Riscossione
("Elenco cartelle/avvisi"). È una tabella a 17 colonne, una riga per cartella/avviso.

REGOLE SPECIFICHE AER:
- Numeri puliti: niente separatori migliaia, niente euro. Formato italiano 1.158,32 -> 1158.32.
- Date in formato gg-mm-aaaa -> "AAAA-MM-GG"; se mancante usa null.
- Booleani (Rateiz., Proc. Attive, Def. age.): "Sì"->true, "No"->false.
- Per ogni riga vale: residuo_carico = carico_affidato - sgravio - gia_pagato - stralcio_def_agevolata;
  totale_residuo = residuo_carico + interessi_mora + oneri_diritti;
  totale_residuo_netto = totale_residuo - importo_sospeso. Se non torna, metti needs_review=true.
- "proc_attive" indica fermi/ipoteche/procedure cautelari-esecutive in corso (colonna P): è la più importante.
- Leggi TUTTE le pagine e TUTTE le righe; non perderne nessuna. Leggi anche la riga TOTALI.
- Estrai dalla testata Codice Fiscale e Denominazione/Cognome Nome.

{rules}

Rispondi SOLO con questo JSON:
{{
  "doc_type": "cartella_aer",
  "intestatario": {{ "codice_fiscale": <str|null>, "denominazione": <str|null> }},
  "data_elaborazione": <str|null>,
  "righe": [
    {{
      "numero_documento": <str>, "tipo_documento": <str>, "ente_creditore": <str>,
      "data_notifica": <str|null>,
      "carico_affidato": <number>, "sgravio": <number>, "gia_pagato": <number>,
      "stralcio_def_agevolata": <number>, "residuo_carico": <number>,
      "interessi_mora": <number>, "oneri_diritti": <number>,
      "totale_residuo": <number>, "importo_sospeso": <number>, "totale_residuo_netto": <number>,
      "rateizzato": <bool>, "proc_attive": <bool>, "def_agevolata": <bool>,
      "needs_review": <bool>
    }}
  ],
  "totali": {{
    "carico_affidato": <number>, "sgravio": <number>, "gia_pagato": <number>,
    "stralcio_def_agevolata": <number>, "residuo_carico": <number>,
    "interessi_mora": <number>, "oneri_diritti": <number>,
    "totale_residuo": <number>, "totale_residuo_netto": <number>
  }},
  "quadrature_ok": <bool>
}}

DOCUMENTO:
{text}
"""
