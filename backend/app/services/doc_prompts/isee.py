"""Prompt + schema per l'ATTESTAZIONE ISEE (DSU) / Indicatore Situazione Economica.

Doppio canale: questo prompt serve al canale UPLOAD (AI Flash). Il canale API
(Visengine, hash isee 6aa0789f...) passa invece dal flusso EnrichmentRequest.
Mapping (worker): nota sintetica in Debtor.income_sources (l'ISEE non è un reddito,
è un indicatore di situazione economica del nucleo).
"""

ISEE_PROMPT = """Sei un assistente che legge un'ATTESTAZIONE ISEE (Indicatore della Situazione
Economica Equivalente, esito DSU) italiana.

REGOLE SPECIFICHE ISEE:
- "isee_ordinario" = valore ISEE ordinario in euro.
- "isr" = Indicatore Situazione Reddituale; "ise" = Indicatore Situazione Economica (se presenti, altrimenti null).
- "componenti_nucleo" = numero di componenti del nucleo familiare.
- "anno" = anno di riferimento/validità in formato "AAAA".
- "scadenza" = data di scadenza dell'attestazione in formato "AAAA-MM-GG" se presente, altrimenti null.

{rules}

Rispondi SOLO con questo JSON:
{{
  "doc_type": "isee",
  "anno": <str|null>,
  "isee_ordinario": <number>,
  "isr": <number|null>,
  "ise": <number|null>,
  "componenti_nucleo": <number|null>,
  "scadenza": <str|null>
}}

DOCUMENTO:
{text}
"""
