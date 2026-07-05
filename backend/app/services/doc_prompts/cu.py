"""Prompt + schema per la CU (Certificazione Unica) / ex CUD.

Estrazione AI su Flash: documento annuale, importi su poche voci chiare.
Mapping (worker): reddito_complessivo -> Debtor.annual_income (proposto, confermabile).
"""

CU_PROMPT = """Sei un assistente che legge una CERTIFICAZIONE UNICA (CU, ex CUD) italiana,
rilasciata dal sostituto d'imposta (datore di lavoro o ente pensionistico).

REGOLE SPECIFICHE CU:
- "reddito_complessivo" = reddito di lavoro dipendente/assimilato o di pensione del periodo (annuo).
- "reddito_imponibile" = imponibile fiscale, se distinto dal complessivo; altrimenti null.
- "ritenute" = ritenute IRPEF operate nell'anno.
- "anno" = anno d'imposta in formato "AAAA".
- "datore_sostituto" = denominazione del sostituto d'imposta (datore/ente).

{rules}

Rispondi SOLO con questo JSON:
{{
  "doc_type": "cu",
  "anno": <str|null>,
  "reddito_complessivo": <number>,
  "reddito_imponibile": <number>,
  "ritenute": <number>,
  "datore_sostituto": <str|null>
}}

DOCUMENTO:
{text}
"""
