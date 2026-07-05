"""Prompt + schema per la BUSTA PAGA / cedolino.

Estrazione AI su Gemini Pro (vedi PRO_DOC_TYPES in llm_routing): il reddito mensile
è un importo critico che alimenta la capacità di rimborso del cruscotto.
Regola deterministica di verifica: netto ≈ lordo − trattenute (tolleranza) -> flag.
Mapping (worker): retribuzione_netta -> Debtor.monthly_net_income (proposto, confermabile).
"""

BUSTA_PAGA_PROMPT = """Sei un assistente che legge una BUSTA PAGA / CEDOLINO italiano.
Estrai i dati retributivi del periodo. È il documento del reddito da lavoro dipendente.

REGOLE SPECIFICHE BUSTA PAGA:
- "retribuzione_netta" = il NETTO IN BUSTA effettivamente percepito nel mese.
- "retribuzione_lorda" = totale competenze lorde del mese (prima delle trattenute).
- "totale_trattenute" = somma di ritenute fiscali (IRPEF) + contributi a carico del lavoratore.
- "periodo" = mese di competenza in formato "AAAA-MM".
- "tipo_contratto" = es. "tempo indeterminato", "determinato", "apprendistato" se indicato, altrimenti null.
- Vale la quadratura: retribuzione_netta ≈ retribuzione_lorda − totale_trattenute (piccola tolleranza).

{rules}

Rispondi SOLO con questo JSON:
{{
  "doc_type": "busta_paga",
  "periodo": <str|null>,
  "datore_lavoro": <str|null>,
  "retribuzione_netta": <number>,
  "retribuzione_lorda": <number>,
  "totale_competenze": <number>,
  "totale_trattenute": <number>,
  "tipo_contratto": <str|null>
}}

DOCUMENTO:
{text}
"""
