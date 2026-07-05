"""Prompt + schema per la VISURA CATASTALE (per soggetto)."""

VISURA_CATASTALE_PROMPT = """Sei un assistente esperto di visure catastali italiane dell'Agenzia delle Entrate.
Estrai i dati in modo strutturato dal documento seguente, che e una VISURA PER SOGGETTO
(elenca tutti gli immobili intestati a una persona).

STRUTTURA TIPICA di questo documento:
- In alto, il SOGGETTO RICHIESTO/INDIVIDUATO (nome, data e luogo di nascita, codice fiscale):
  e il cliente della pratica, la persona di cui ci interessano gli immobili.
- Poi gli immobili sono RAGGRUPPATI PER COMUNE (es. "Unita Immobiliari site nel Comune di X").
- Ogni unita immobiliare ha: Sezione Urbana, Foglio, Particella, Subalterno, Zona Censuaria,
  Categoria (es. A/2, A/7, C/2), Classe, Consistenza (vani o m²), Superficie catastale (m²),
  Rendita (in Euro), Indirizzo/ubicazione e piano.
- Dopo ogni gruppo c'e "Intestazione degli immobili": elenca TUTTI gli intestatari di quegli
  immobili con codice fiscale e i DIRITTI E ONERI REALI (es. "Proprieta per 1/3", "Usufrutto").
  La QUOTA puo essere diversa per gruppo di immobili.
- In fondo: "Totale Generale" con vani, m², rendita complessiva e numero unita immobiliari.

REGOLA CHIAVE sulle quote: per ogni immobile devi identificare la QUOTA E IL DIRITTO DEL
SOGGETTO RICHIESTO (il cliente in alto), distinguendola dagli altri comproprietari.

{rules}

Schema JSON da restituire:
{{
  "document_type": "visura_catastale",
  "tipo_visura": <str|null>,            // es. "per soggetto", "per immobile", "storica"
  "ufficio_provinciale": <str|null>,    // es. "Palermo"
  "numero_visura": <str|null>,
  "data_visura": <str|null>,            // formato YYYY-MM-DD
  "soggetto": {{                        // la persona di cui sono intestati gli immobili
    "denominazione": <str|null>,
    "codice_fiscale": <str|null>,
    "data_nascita": <str|null>,
    "luogo_nascita": <str|null>
  }},
  "immobili": [
    {{
      "tipo_immobile": <str|null>,      // "fabbricato" | "terreno"
      "categoria": <str|null>,          // es. "A/2", "A/7", "C/2"
      "classe": <str|null>,
      "comune": <str|null>,
      "sezione_urbana": <str|null>,
      "foglio": <str|null>,
      "particella": <str|null>,         // detta anche mappale
      "subalterno": <str|null>,
      "zona_censuaria": <str|null>,
      "indirizzo": <str|null>,
      "piano": <str|null>,
      "consistenza": <str|null>,        // es. "7 vani", "41 m²"
      "superficie_mq": <number|null>,   // superficie catastale totale in m²
      "rendita_catastale": <number|null>,  // in euro
      "quota_soggetto": <str|null>,     // QUOTA del soggetto richiesto, es. "1/3", "1/1"
      "diritto_soggetto": <str|null>,   // es. "Proprieta", "Usufrutto", "Nuda proprieta"
      "altri_intestatari": [            // gli ALTRI comproprietari (non il soggetto)
        {{"denominazione": <str|null>, "codice_fiscale": <str|null>, "quota": <str|null>, "diritto": <str|null>}}
      ],
      "provenienza": <str|null>,        // es. "Successione", "Compravendita", + data se presente
      "source_page": <int|null>,
      "confidence": <0..1>
    }}
  ],
  "totali": {{
    "numero_immobili": <int|null>,
    "rendita_totale": <number|null>,
    "vani_totali": <number|null>
  }},
  "warnings": [ {{"type": <str>, "message": <str>}} ]
}}

DOCUMENTO:
{text}
"""