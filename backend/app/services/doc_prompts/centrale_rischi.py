"""Prompt + schema per la CENTRALE DEI RISCHI (Banca d'Italia)."""

CENTRALE_RISCHI_PROMPT = """Sei un assistente esperto della Centrale dei Rischi (CR) della Banca d'Italia.
Questo documento e la fotografia della posizione creditizia di un soggetto verso il
sistema bancario/finanziario, riportata MESE PER MESE su un lungo arco temporale.

CONTESTO D'USO: serve in una pratica di gestione del debito. NON elencare ogni singolo
mese (sarebbero centinaia di righe ripetitive). Devi SINTETIZZARE cosi:
1. ESPOSIZIONE ATTUALE: prendi la rilevazione mensile PIU RECENTE e, per ogni
   intermediario (banca/finanziaria), riporta l'esposizione corrente.
2. CRITICITA NEL TEMPO: scorri tutta la serie storica e segnala SOLO i momenti critici
   (sofferenze, crediti scaduti/sconfinanti oltre 90 giorni, sconfini), indicando il MESE.
3. GARANZIE PRESTATE dal soggetto a favore di altri (e garante).
4. TOTALI di sintesi.

GLOSSARIO (dalla legenda del documento):
- Intermediario = banca o finanziaria che segnala.
- Categoria: "rischi a scadenza" (mutui/finanziamenti con scadenza), "rischi a revoca"
  (fidi/conto corrente), "garanzie ricevute" (il soggetto e GARANTE per altri), "sofferenze".
- Accordato = credito deliberato. Utilizzato = debito effettivo alla data. Importo garantito.
- Stato rapporto: "crediti diversi da scaduti e sconfinanti" = REGOLARE; "crediti scaduti o
  sconfinanti da piu di 90 gg" = CRITICO; "sofferenza" = molto critico.
- Nelle "garanzie ricevute", il campo "Garantito" indica la societa/soggetto per cui il
  soggetto del documento fa da garante.

{rules}

Schema JSON da restituire:
{{
  "document_type": "centrale_rischi",
  "intestatario": {{"denominazione": <str|null>, "codice_fiscale": <str|null>, "codice_intestatario": <str|null>}},
  "periodo": {{"da": <str|null>, "a": <str|null>}},   // arco temporale del prospetto (es. "2017-01","2026-02")
  "data_riferimento_piu_recente": <str|null>,         // mese piu recente con segnalazioni (es. "2026-02")
  "esposizione_attuale": [                            // dalla rilevazione PIU RECENTE
    {{
      "intermediario": <str|null>,
      "categoria": <str|null>,                        // "rischi a scadenza" | "rischi a revoca" | "garanzie ricevute"
      "accordato": <number|null>,
      "utilizzato": <number|null>,
      "importo_garantito": <number|null>,
      "stato_rapporto": <str|null>,                   // sintesi leggibile
      "e_critico": <bool>,                            // true se scaduto/sconfinante/sofferenza
      "confidence": <0..1>
    }}
  ],
  "criticita": [                                       // SOLO eventi critici nel tempo
    {{
      "mese": <str|null>,                             // es. "2018-01"
      "intermediario": <str|null>,
      "tipo": <str|null>,                             // "scaduto_oltre_90gg" | "sofferenza" | "sconfino"
      "descrizione": <str|null>,
      "importo": <number|null>
    }}
  ],
  "garanzie_prestate": [                              // dove il soggetto e GARANTE per altri
    {{
      "intermediario": <str|null>,
      "soggetto_garantito": <str|null>,              // es. "DADAGIU S.R.L."
      "valore_garanzia": <number|null>,
      "importo_garantito": <number|null>,
      "stato": <str|null>
    }}
  ],
  "totali": {{
    "numero_intermediari": <int|null>,
    "esposizione_totale_utilizzata": <number|null>,   // somma utilizzato dell'esposizione attuale
    "totale_garanzie_prestate": <number|null>,
    "presenza_sofferenze": <bool>,
    "presenza_criticita": <bool>
  }},
  "warnings": [ {{"type": <str>, "message": <str>}} ]
}}

DOCUMENTO:
{text}
"""
