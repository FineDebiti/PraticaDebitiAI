"""Prompt generico di fallback per documenti non ancora mappati in dettaglio."""

GENERIC_EXTRACT_PROMPT = """Sei un assistente che estrae dati strutturati da documenti debitori italiani.
Tipo documento: {doc_type}.

{rules}

Estrai le posizioni debitorie presenti. Schema JSON:
{{
  "document_type": "{doc_type}",
  "debtor": {{"name": <str|null>, "tax_code": <str|null>}},
  "credit_positions": [
    {{
      "creditor": <str|null>,
      "debt_type": <str|null>,
      "original_amount": <number|null>,
      "residual_amount": <number|null>,
      "overdue_amount": <number|null>,
      "monthly_installment": <number|null>,
      "status": <str|null>,
      "source_page": <int|null>,
      "confidence": <0..1>
    }}
  ],
  "warnings": [ {{"type": <str>, "message": <str>}} ]
}}

DOCUMENTO:
{text}
"""