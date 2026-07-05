"""Prompt + schema per il BILANCIO DI ESERCIZIO (deposito CCIAA, tassonomia XBRL ITCC)."""

BILANCIO_PROMPT = """Sei un assistente esperto di bilanci d'esercizio italiani depositati alla CCIAA
(tassonomia XBRL ITCC: stato patrimoniale, conto economico, nota integrativa).

CONTESTO D'USO: pratica di gestione del debito. Servono (a) le voci di bilancio dei DUE
esercizi che il bilancio riporta sempre affiancati (corrente + comparativo), e (b) il
dettaglio dei DEBITI per natura e scadenza dalla nota integrativa (il pezzo centrale).

REGOLE SPECIFICHE BILANCIO:
- Estrai SEMPRE entrambe le colonne (corrente + comparativo). Se una voce manca, usa null (NON 0).
- Numeri puliti: niente separatori migliaia, niente simbolo euro. I valori tra parentesi
  sono NEGATIVI (perdite/decrementi) -> convertili col segno meno.
- Per "oneri_finanziari" usa il VALORE ASSOLUTO dell'onere finanziario netto (serve agli indici).
- "debiti_assistiti_garanzie_reali": true SOLO se la nota indica importi "di cui per
  ipoteche/pegni".
- Validazione interna: totale_attivo == totale_passivo; somma debiti_per_natura ==
  debiti_totali.corrente. Se NON quadra, segnalalo in note_rilevanti.altro.

{rules}

Rispondi SOLO con questo JSON (ogni voce di SP/CE ha forma {{"corrente": <number|null>, "precedente": <number|null>}}):
{{
  "doc_type": "bilancio",
  "azienda": {{
    "denominazione": <str|null>,
    "codice_fiscale": <str|null>,
    "partita_iva": <str|null>,
    "rea": <str|null>,
    "sede": <str|null>,
    "forma_giuridica": <str|null>,
    "ateco": <str|null>,
    "capitale_sociale": <number|null>,
    "in_liquidazione": <bool|null>,
    "socio_unico": <bool|null>
  }},
  "esercizio": {{
    "data_chiusura": <str|null>,              // YYYY-MM-DD esercizio corrente
    "data_chiusura_comparativo": <str|null>,  // YYYY-MM-DD esercizio precedente
    "tipo": <str|null>,                       // "abbreviato" | "ordinario" | "microimpresa"
    "valuta": "EUR"
  }},
  "stato_patrimoniale": {{
    "crediti_soci":            {{"corrente": <number|null>, "precedente": <number|null>}},
    "immob_immateriali":       {{"corrente": <number|null>, "precedente": <number|null>}},
    "immob_materiali":         {{"corrente": <number|null>, "precedente": <number|null>}},
    "immob_finanziarie":       {{"corrente": <number|null>, "precedente": <number|null>}},
    "totale_immobilizzazioni": {{"corrente": <number|null>, "precedente": <number|null>}},
    "rimanenze":               {{"corrente": <number|null>, "precedente": <number|null>}},
    "crediti_circolante":      {{"corrente": <number|null>, "precedente": <number|null>}},
    "crediti_circolante_oltre":{{"corrente": <number|null>, "precedente": <number|null>}},
    "disponibilita_liquide":   {{"corrente": <number|null>, "precedente": <number|null>}},
    "totale_attivo_circolante":{{"corrente": <number|null>, "precedente": <number|null>}},
    "ratei_risconti_attivi":   {{"corrente": <number|null>, "precedente": <number|null>}},
    "totale_attivo":           {{"corrente": <number|null>, "precedente": <number|null>}},
    "capitale":                {{"corrente": <number|null>, "precedente": <number|null>}},
    "riserve":                 {{"corrente": <number|null>, "precedente": <number|null>}},
    "utile_perdita_esercizio": {{"corrente": <number|null>, "precedente": <number|null>}},
    "patrimonio_netto":        {{"corrente": <number|null>, "precedente": <number|null>}},
    "fondi_rischi_oneri":      {{"corrente": <number|null>, "precedente": <number|null>}},
    "tfr":                     {{"corrente": <number|null>, "precedente": <number|null>}},
    "debiti_totali":           {{"corrente": <number|null>, "precedente": <number|null>}},
    "debiti_entro":            {{"corrente": <number|null>, "precedente": <number|null>}},
    "debiti_oltre":            {{"corrente": <number|null>, "precedente": <number|null>}},
    "ratei_risconti_passivi":  {{"corrente": <number|null>, "precedente": <number|null>}},
    "totale_passivo":          {{"corrente": <number|null>, "precedente": <number|null>}}
  }},
  "conto_economico": {{
    "ricavi_vendite":          {{"corrente": <number|null>, "precedente": <number|null>}},
    "valore_produzione":       {{"corrente": <number|null>, "precedente": <number|null>}},
    "costi_produzione":        {{"corrente": <number|null>, "precedente": <number|null>}},
    "differenza_valore_costi": {{"corrente": <number|null>, "precedente": <number|null>}},  // A-B = EBIT
    "costi_personale":         {{"corrente": <number|null>, "precedente": <number|null>}},
    "ammortamenti":            {{"corrente": <number|null>, "precedente": <number|null>}},
    "proventi_oneri_finanziari":{{"corrente": <number|null>, "precedente": <number|null>}},
    "oneri_finanziari":        {{"corrente": <number|null>, "precedente": <number|null>}},  // valore assoluto
    "risultato_ante_imposte":  {{"corrente": <number|null>, "precedente": <number|null>}},
    "imposte":                 {{"corrente": <number|null>, "precedente": <number|null>}},
    "utile_perdita":           {{"corrente": <number|null>, "precedente": <number|null>}}
  }},
  "debiti_per_natura": {{
    "fornitori":      {{"importo": <number|null>, "entro": <number|null>, "oltre": <number|null>, "di_cui_ipoteche": <number|null>, "di_cui_privilegi": <number|null>}},
    "tributari":      {{"importo": <number|null>, "entro": <number|null>, "oltre": <number|null>, "di_cui_ipoteche": <number|null>, "di_cui_privilegi": <number|null>}},
    "previdenziali":  {{"importo": <number|null>, "entro": <number|null>, "oltre": <number|null>, "di_cui_ipoteche": <number|null>, "di_cui_privilegi": <number|null>}},
    "banche":         {{"importo": <number|null>, "entro": <number|null>, "oltre": <number|null>, "di_cui_ipoteche": <number|null>, "di_cui_privilegi": <number|null>}},
    "soci_finanziamenti":{{"importo": <number|null>, "entro": <number|null>, "oltre": <number|null>, "di_cui_ipoteche": <number|null>, "di_cui_privilegi": <number|null>}},
    "altri":          {{"importo": <number|null>, "entro": <number|null>, "oltre": <number|null>, "di_cui_ipoteche": <number|null>, "di_cui_privilegi": <number|null>}},
    "totale":         {{"importo": <number|null>}}
  }},
  "debiti_assistiti_garanzie_reali": <bool>,
  "dettaglio_erariale": {{
    "ires": <number|null>, "irap": <number|null>, "iva": <number|null>, "ritenute": <number|null>
  }},
  "note_rilevanti": {{
    "continuita_aziendale": <str|null>,
    "garanzie_prestate": <str|null>,
    "contenziosi": <str|null>,
    "altro": <str|null>
  }},
  "warnings": [ {{"type": <str>, "message": <str>}} ]
}}

DOCUMENTO:
{text}
"""
