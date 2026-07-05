"""Regole comuni a tutti i prompt e prompt di classificazione."""

_COMMON_RULES = """REGOLE IMPORTANTI:
- NON inventare dati. Se un campo non e presente nel documento, usa null.
- Riporta gli importi come numeri senza simboli ne separatori di migliaia
  (esempio: "1.234,56 EUR" diventa 1234.56).
- Per ogni elemento estratto indica un livello di confidenza tra 0 e 1.
- Indica la pagina di origine quando possibile.
- Rispondi SOLO con JSON valido, senza testo prima o dopo, senza markdown."""

CLASSIFY_PROMPT = """Sei un assistente esperto che classifica documenti italiani per pratiche
di gestione del debito e analisi patrimoniale.

Leggi il contenuto e indica di che tipo di documento si tratta, tra:
- visura_catastale (visura catastale / ipocatastale, immobili, Agenzia delle Entrate Catasto)
- visura_camerale (visura camerale / Registro Imprese / CCIAA / InfoCamere, dati di un'impresa)
- bilancio (bilancio di esercizio depositato CCIAA: stato patrimoniale, conto economico, nota integrativa, tassonomia itcc)
- centrale_rischi (Centrale dei Rischi Banca d'Italia)
- crif (report CRIF / EURISC)
- cartella_aer (cartella di pagamento Agenzia Entrate-Riscossione)
- contratto_finanziamento (prestito, mutuo, cessione del quinto, finanziamento)
- busta_paga (cedolino, busta paga)
- cu (Certificazione Unica, ex CUD, redditi annui da lavoro/pensione)
- isee (attestazione ISEE, esito DSU, indicatore situazione economica del nucleo)
- estratto_conto (estratto conto bancario)
- dichiarazione_redditi (Modello REDDITI PF / UNICO o Modello 730, quadri RA/RB/RC/RE/RH/RN, Agenzia delle Entrate)
- pignoramento (atto di pignoramento, decreto ingiuntivo, precetto)
- altro

Rispondi SOLO con JSON valido, senza testo aggiuntivo:
{{"doc_type": "<uno dei tipi>", "confidence": <numero tra 0 e 1>}}

CONTENUTO:
{text}
"""