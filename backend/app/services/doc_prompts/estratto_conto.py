"""Prompt + schema per l'ESTRATTO CONTO bancario.

FALLBACK: usato solo se il parser tabellare deterministico (estratto_conto_parser.py)
fallisce (PDF scansionato / layout anomalo). Modello Flash: lista movimenti da leggere.
Lo schema deve combaciare con quello del parser.
Mapping (worker): entrate/uscite medie mensili -> stima reddito autonomi (proposto).
"""

ESTRATTO_CONTO_PROMPT = """Sei un assistente che legge un ESTRATTO CONTO bancario italiano.
È una tabella di movimenti: una riga per operazione (data, descrizione, dare/avere, saldo).

REGOLE SPECIFICHE ESTRATTO CONTO:
- Numeri puliti: formato italiano 1.234,56 -> 1234.56. Niente simbolo euro né separatori migliaia.
- "dare" = addebito/uscita (numero positivo); "avere" = accredito/entrata (numero positivo).
- Date in "AAAA-MM-GG"; se mancante usa null.
- Leggi TUTTE le pagine e TUTTE le righe movimento.
- "saldo_finale" = ultimo saldo disponibile, se riportato; altrimenti null.

{rules}

Rispondi SOLO con questo JSON:
{{
  "doc_type": "estratto_conto",
  "intestatario": <str|null>,
  "iban": <str|null>,
  "periodo": {{ "da": <str|null>, "a": <str|null> }},
  "movimenti": [
    {{ "data": <str|null>, "descrizione": <str>, "dare": <number>, "avere": <number>, "saldo": <number|null> }}
  ],
  "saldo_finale": <number|null>
}}

DOCUMENTO:
{text}
"""
