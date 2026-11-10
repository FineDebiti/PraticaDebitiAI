# DOSSIERLEX — MANUALE TECNICO UFFICIALE & ARCHITETTURA DI SISTEMA
### Piattaforma di Pre-Analisi Documentale, Forense ed Econometrica ex CCII (D.Lgs. 14/2019)
**Studio Legale Avv. Aurelio Bentivegna — Palermo**  
*Versione Piattaforma:* **1.2.0-Production**  
*Data Rilascio Ufficiale:* **Novembre 2026**  
*Branch di riferimento:* `DossierLex_1`

---

## 1. Executive Summary & Missione di Progetto

**DossierLex** è la piattaforma proprietaria di intelligenza aumentata e audit forense sviluppata per lo **Studio Legale dell'Avv. Aurelio Bentivegna**, specializzato in diritto della crisi d'impresa, risanamento aziendale e procedure di sovraindebitamento.

### 🎯 Obiettivo Strategico
Ridurre dell'**80% i tempi di istruttoria preliminare** di una pratica debitoria complessa, trasformando una mole disorganizzata di documenti eterogenei (cartelle esattoriali, centrali rischi, bilanci, visure camerali e catastali) in:
1. Una **ricognizione patrimoniale e debitoria oggettiva**, riconciliata e priva di duplicazioni;
2. Un **quadro econometrico rigoroso** conforme agli schemi **OIC 12**, agli orientamenti **ESMA 2021** (PFN) e alle linee guida **CNDCEC marzo 2024**;
3. Una **diagnosi di risanabilità e semaforo di crisi** calibrata sugli artt. 2, 3 e 12 del **Codice della Crisi d'Impresa e dell'Insolvenza (CCII - D.Lgs. 14/2019)**;
4. Un **Dossier Istruttorio Istituzionale** a doppio canale: cruscotto web interattivo a 11 capitoli e **Report Peritale PDF ufficiale di 7 pagine esatte** pronto per l'incontro con il cliente o il deposito presso l'Organismo di Composizione della Crisi (OCC) / Tribunale.

### 🛡️ Principio Fondamentale di Sovranità e Riservatezza (Zero Cloud Leakage)
A differenza dei software basati su API cloud pubbliche (OpenAI, Anthropic, Google Cloud esterni), DossierLex opera su un'**architettura 100% locale e on-premise**:
* **Modello Neurale Offline**: Esecuzione locale di **Qwen 2.5 (27B/32B)** su runtime ottimizzato **LM Studio** all'interno dell'hardware dello studio.
* **Nessun dato all'esterno**: Nessun codice fiscale, bilancio, cartella esattoriale o estratto bancario lascia fisicamente il server dello studio.
* **Conformità GDPR e Segreto Professionale Forense**: Piena aderenza ai più stringenti doveri deontologici di riservatezza e custodia dei dati sensibili del cliente.
* **Zero Costi Ricorrenti**: Nessun costo a consumo o canone per token consumati.

---

## 2. Architettura di Sistema & Stack Tecnologico

DossierLex è ingegnerizzato come un'applicazione a **microservizi containerizzati (Docker Compose)**, orchestrata per garantire isolamento, scalabilità e riproducibilità.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        POSTAZIONI OPERATORI (CLIENT LEGGERI)                           │
│     Wi-Fi Studio: http://192.168.1.31:3001  |  VPN Remota: http://100.80.46.116:3001   │
│           (Nessuna installazione richiesta: Google Chrome / Edge / Safari)             │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ HTTP / WebSockets
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                  FRONTEND WEB INTERATTIVO (Next.js 14.2 / React 18)                    │
│   • UI "Institutional Heritage" (Design System CSS, Tavolozza Navy / Sand / Crimson)   │
│   • Cruscotto Pratiche, Timeline Documentale, Upload con Drag & Drop                   │
│   • Scheda Analisi 11 Capitoli reattiva, Audit Trail e Visualizzatore PDF Integrato     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ REST API (JSON) - Porta 8000
┌───────────────────────────────────────────▼────────────────────────────────────────────┐
│                    CORE BACKEND SERVICES (FastAPI / Python 3.12)                       │
│   • Validazione Fiscale Stringente (CF / P.IVA con check digit e omocodie)              │
│   • Engine di Pre-Analisi Forense & Indicatori CCII (OIC 12, PFN ESMA, Test Pratico)   │
│   • Generatore Report Ufficiale 7 Pagine (FPDF2 Engine calibrato al millimetro)        │
│   • Ingestion Pipeline Orchestrator & Rule Engine                                      │
└───────┬───────────────────┬───────────────────────────┬────────────────────────┬───────┘
        │                   │                           │                        │
┌───────▼────────┐  ┌───────▼──────────────┐   ┌────────▼──────────┐   ┌─────────▼────────┐
│   DATABASE     │  │  CODA ASINCRONA      │   │  FILESTORE LOCALE │   │ MOTORE AI LOCALE │
│ PostgreSQL 16  │  │  Redis 7 + Celery    │   │ Volume Persistente│   │ LM Studio (Qwen) │
│ + pgvector     │  │ Concurrency = 1      │   │ Deduplica SHA-256 │   │ Porta 1234 (v1)  │
│ 24 tabelle     │  │ OCR & NLP background │   │ /data/uploads/    │   │ Temp = 0.1 / 0.2 │
└────────────────┘  └──────────────────────┘   └───────────────────┘   └──────────────────┘
```

### Tabella dei Componenti Software

| Livello | Tecnologia | Versione | Funzione e Note Operative |
|---|---|---|---|
| **Frontend** | Next.js / React | 14.2.15 / 18 | App Router, Server Components e Client Hooks. Design system personalizzato senza framework pesanti esterni. |
| **API Server** | FastAPI / Uvicorn | 0.115 / 0.32 | Endpoint REST asincroni, validazione schemi Pydantic v2, documentazione OpenAPI (`/docs`). |
| **ORM & DB** | SQLAlchemy / Alembic | 2.0.36 / 1.14 | Mappatura relazionale a 24 tabelle, migrazioni versionate, pooling connessioni isolato (`prepare_threshold: None`). |
| **Database** | PostgreSQL + pgvector | 16.0 | RDBMS primario su porta standard 5432, estensione vettoriale per embedding giurisprudenziali futuri. |
| **Broker Code** | Redis | 7.2 | Coda in memoria per la distribuzione dei task asincroni di acquisizione e indicizzazione. |
| **Task Worker** | Celery | 5.4.0 | Elaborazione in background. Concurrency settata rigidamente a 1 per proteggere RAM e VRAM durante le estrazioni pesanti. |
| **OCR Motori** | PaddleOCR v4 + Tesseract | 2.8+ / 5.3+ | Pipeline ibrida: `pdfplumber` per PDF con testo vettoriale nativo; PaddleOCR/Tesseract per scansioni raster e foto. |
| **AI LLM Locale** | Qwen 2.5 Instruct | 27B / 32B | Modello GGUF quantizzato Q4_K_M eseguito su LM Studio. Fornisce l'endpoint compatibile OpenAI a `http://host.docker.internal:1234/v1`. |
| **PDF Reporting**| FPDF2 | 2.8.2 | Motore vettoriale Python ad altissima precisione tipografica per la resa del report ufficiale di 7 pagine. |

---

## 3. Pipeline di Elaborazione Documentale (End-to-End Lifecycle)

Ogni documento caricato in una pratica attraversa una catena di elaborazione a **stati espliciti, modulari e idempotenti**:

```
[File Caricato]
      │
      ▼
1. INGESTIONE & HASHING ────► Calcolo SHA-256, deduplicazione e registrazione su DB (Document)
      │
      ▼
2. ESTRAZIONE TESTO ────────► Verifica testo nativo: se vettoriale -> pdfplumber
      │                       se scansione/immagine -> PaddleOCR locale
      ▼
3. CLASSIFICAZIONE TIPO ────► Identificazione automatica del tipo documento (bilancio, cartella_aer,
      │                       centrale_rischi, visura_camerale, visura_catastale, crif, ecc.)
      ▼
4. PARSING DETERMINISTICO ──► Estrazione tabellare a regole fisse (aer_parser, regex CR, visure)
      │
      ▼
5. NORMALIZZAZIONE DB ──────► Persistenza nelle entità di dominio (Debtor, Company, TaxDebtStatement,
      │                       TaxDebtItem, CreditExposure, Vehicle, RealEstate, FinancialStatement)
      ▼
6. MOTORE ECONOMETRICO ─────► Riclassificazione OIC 12, calcolo PFN ESMA, PFN/EBITDA, indici CNDCEC,
      │                       test pratico ministeriale D.D. 23/04/2026, soglie art. 2 e 3 CCII
      ▼
7. SINTESI FORENSE (QWEN) ──► Invocazione catena LangChain a temp 0.1 con protocollo a 5 step
      │
      ▼
[Dossier Pronto] ───────────► Consultazione a video (11 capitoli) & Download PDF (7 pagine)
```

### Dettaglio dei singoli passaggi

#### Step 1: Ingestione e Storage Sicuro
* Il file viene salvato nel filesystem protetto del server sotto `/data/uploads/cases/{case_id}/{hash}_{nome_file}`.
* Viene calcolato l'hash SHA-256: se il file è già presente nella pratica, viene scartato per prevenire ridondanze e raddoppi dei debiti.

#### Step 2: Estrazione Ibrida del Testo (Parser Vettoriale vs OCR)
* **Livello 1 (Vettoriale)**: Il file viene aperto con `pdfplumber`. Se contiene testo nativo estraibile e ben formattato (es. visure camerali telematiche, estratti di ruolo scaricati dal cassetto fiscale, estratti conto PDF nativi), il testo viene estratto istantaneamente a costo computazionale zero.
* **Livello 2 (Raster / Scansione)**: Se il PDF è una scansione o un'immagine (es. carte d'identità, vecchie cartelle cartacee, fogli scansionati con scanner piani), interviene **PaddleOCR / Tesseract**, che normalizza l'immagine ed esegue il riconoscimento ottico dei caratteri.

#### Step 3 & 4: Parsing Deterministico Specializzato
DossierLex non affida i calcoli critici a un generatore di testo statistico non vincolato. Utilizza **parser deterministici dedicati**:
* **Agenzia delle Entrate Riscossione (`aer_parser.py`)**:
  * Legge l'estratto di ruolo ufficiale "Da Saldare".
  * Isola le colonne: Carico affidato, Sgravi, Pagamenti effettuati, Sospensioni, Stralci, Totale residuo netto.
  * Individua la colonna *"di cui INPS"* e **la vincola come sottocomponente interna**, impedendone la risommatura.
  * Rileva le procedure esecutive/cautelari attive (fermi amministrativi e ipoteche).
  * Esegue la quadratura al centesimo tra la somma delle singole cartelle e il totale indicato nel frontespizio AdER.
* **Centrale Rischi Banca d'Italia**:
  * Individua l'ultimo mese rilevato della serie storica (evitando di sommare mesi progressivi tra loro).
  * Distingue i rischi a revoca, i rischi a scadenza, i crediti di firma e le eventuali sofferenze.
* **Beni Mobili Registrati & PRA**:
  * Estrae automaticamente visure PRA singole (targa, telaio, modello, vincoli/gravami iscritti) ed elenchi manoscritti/dichiarativi di beni mobili (autovetture, autocarri, motoveicoli).
* **Catasto Nazionale**:
  * Rileva i dati identificativi (Foglio, Particella, Subalterno, Categoria, Rendita) o certifica l'esito negativo (*"Nessuna corrispondenza trovata"*).

#### Step 5: Normalizzazione e Persistenza a Database
I dati estratti popolano le tabelle relazionali dedicate. Ogni record mantiene la tracciabilità della fonte (`source_document_id` e pagina di provenienza), garantendo la replicabilità forense.

#### Step 6: Motore Econometrico ex CCII
Il backend calcola matematicamente le grandezze peritali:
* **Riclassificazione Conto Economico ex OIC 12 e CNDCEC marzo 2024**: Valore della Produzione ($A$), Costi della Produzione ($B$), Differenza $A - B$, e calcolo rigoroso del Margine Operativo Lordo ($MOL / EBITDA = (A - B) + \text{Ammortamenti} + \text{Svalutazioni}$).
* **Posizione Finanziaria Netta (PFN)** conforme all'Orientamento **ESMA 32-382-1138 (2021) n. 39**: include debiti bancari a breve e M/L termine, passività debt-like (debiti tributari e previdenziali scaduti da oltre 90 giorni), debito verso dipendenti e TFR, al netto delle disponibilità liquide.
* **Rapporto PFN / EBITDA**: misura degli anni di margine operativo necessari a riassorbire l'indebitamento finanziario ed erariale netto.
* **Test Pratico Ministeriale per la Composizione Negoziata (Decreto Dirigenziale 23 aprile 2026)**: calcolo del rapporto tra l'indebitamento da risanare e i flussi annui disponibili, distinguendo l'esito tra risanamento agevole, impegnativo o necessità di concordato liquidatorio.
* **Verifica Soglie Impresa Minore (Art. 2 lett. d CCII)** e **Segnali d'Allarme (Art. 3 co. 4 CCII)**.

#### Step 7: Catena di Pre-Analisi Forense & Redazione Report
* Viene invocata la catena LangChain (`forensic_preanalysis_chain.py`) alimentata con i documenti e le grandezze calcolate.
* Qwen riceve il **System Prompt Peritale Permanente** a temperatura 0.1, compilando le motivazioni qualitative, gli scenari di risanamento e le raccomandazioni strategiche.
* L'output alimenta sia la dashboard web a 11 capitoli, sia il generatore PDF ufficiale a 7 pagine.

---

## 4. Il Protocollo Metodologico Forense (Regole Anti-Allucinazione)

Il cuore qualitativo di DossierLex è costituito dal **Protocollo Metodologico Interno dello Studio Legale Bentivegna**:

### 1. Classificazione Epistemica dei Dati (Regola dei Tag)
Ogni singola cifra o affermazione nel report è etichettata con uno standard probatorio rigido:
* **`[D]` Documentato**: presente in un atto o registro ufficiale terzo (es. estratto AdER, Centrale Rischi Banca d'Italia, visura camerale/catastale, bilancio depositato). Fonte, data e riferimento certi.
* **`[R]` Riferito**: dato dichiarato verbalmente dal cliente nell'incontro preliminare (es. fornitori stimati, canoni di locazione arretrati, accordi informali), privo di riscontro contabile formale.
* **`[C]` Calcolato**: risultato di una formula aritmetica replicabile su dati certi (es. $A - B$, MOL, PFN ESMA, rapporto PFN/EBITDA).
* **`[S]` Stimato**: intervallo prudenziale o giudizio professionale motivato (es. stima concorsuale a realizzo per lotti omogenei di autocarri e veicoli).
* **`[H]` Ipotesi**: simulazione condizionale "what-if" (es. impatto sul margine dell'adeguamento del costo del lavoro o dei canoni di locazione).

### 2. Divieti Aritmetici Tassativi (Zero Errori Critici)
* **Ditta Individuale (Art. 2740 c.c.)**: l'imprenditore risponde con tutto il patrimonio presente e futuro. È fatto divieto di indicare "Capitale Sociale" (inesistente per legge). I debiti personali, le fideiussioni e il credito al consumo (CTC/CRIF) confluiscono direttamente nella massa debitoria.
* **Riconciliazione AdER**: il debito erariale è rappresentato esclusivamente dal **Totale Residuo Netto**. È fatto divieto di risommare la quota *"di cui INPS"* (già ricompresa) e di aggiungere le rate delle rottamazioni allo stock del debito residuo.
* **Centrale Rischi**: si estrae esclusivamente l'ultimo mese disponibile per lo stock utilizzato. È fatto divieto di sommare i mesi della serie storica o di considerare cessioni di credito passate senza i contratti di cessione.
* **Contabilità Semplificata vs Ordinaria**:
  > [!IMPORTANT]
  > Nelle ditte e imprese in contabilità semplificata (prive di Stato Patrimoniale ex art. 2424 c.c.), **è severamente vietato indicare `€ 0,00`** sui debiti fornitori, banche o cespiti. Il valore deve essere sempre indicato come **`n.r.*`** (*non rilevabile da contabilità semplificata*), rimandando l'indebitamento effettivo alle banche dati terze certificate.

---

## 5. Struttura del Report Finale a 11 Capitoli

Sia a video che nell'esportazione documentale, la pre-analisi è articolata in **11 sezioni istituzionali**:

1. **Premessa e Documenti Utilizzati**: censimento della base informativa analizzata e data di riferimento.
2. **Profilo dell'Impresa e Natura della Crisi**: anagrafica, forma giuridica (ditta individuale vs società), data costituzione, codice ATECO, numero addetti e regime di responsabilità patrimoniale.
3. **Analisi Economica Pluriennale**: serie storica del Conto Economico a 3 esercizi comparati ex OIC 12, con evidenziazione del Valore della Produzione, Costi di Acquisto, Servizi, Godimento Beni Terzi, Personale, EBITDA/MOL, Ammortamenti, EBIT, Oneri Finanziari e Risultato Netto.
4. **Dato Economico Corrente e Proiezione**: analisi dell'infrannuale con annualizzazione prudenziale (quadrimestre $\times 3$) e divieto di proiezioni ottimistiche prive di stagionalità.
5. **Analisi dell'Indebitamento e Massa Passiva**:
   * *5.1 Debiti da Bilancio*: struttura contabile (o indicazione `n.r.*` in semplificata);
   * *5.2 Banche Dati Esterne*: estratto AdER netto e Centrale Rischi Banca d'Italia;
   * *5.3 Sintesi Massa Debitoria*: consolidamento trasversale senza duplicazioni (documentato + riferito);
   * *5.4 Indicatori Finanziari & PFN*: Posizione Finanziaria Netta ESMA 2021, PFN/EBITDA e Test Pratico Ministeriale di Risanabilità.
6. **Punti di Attenzione e Discrepanze**: confronto analitico tra contabilità sociale e banche dati esterne (incongruenze banca/CR, debiti tributari dichiarati vs ruoli).
7. **Diagnosi di Risanabilità e Semaforo di Crisi**: elementi favorevoli, criticità dominanti e giudizio di vitalità della gestione caratteristica.
8. **Patrimonio e Confronto Liquidatorio**:
   * *8.1 Immobili*: accertamento catastale e valore rivalutato (o attestazione formale di accertamento negativo);
   * *8.2 Beni Mobili Registrati (Veicoli)*: censimento PRA/elenco mezzi e stima esplorativa per lotti omogenei concorsuali (prudente vs favorevole);
   * *8.3 Cespiti di Bilancio*: immobilizzazioni materiali e attrezzature d'officina;
   * *8.4 Esposizione Personale*: regime ex art. 2740 c.c. o garanzie personali/fideiussioni dei soci.
9. **Orientamento verso una Soluzione di Risanamento ex CCII**: analisi di fattibilità comparata tra Composizione Negoziata della Crisi (art. 12 CCII), Accordi di Ristrutturazione (art. 57 CCII), Concordato Semplificato Liquidatorio (art. 160 CCII) e Liquidazione Giudiziale.
10. **Documentazione Integrativa Indispensabile**: checklist delle pezze d'appoggio mancanti (estratti conto bancari 12 mesi, contratti mutuo, libro cespiti, partitario fornitori analitico).
11. **Conclusioni e Raccomandazioni Strategiche**: indicazioni operative per l'Avvocato per orientare la proposta di incarico professionale assistito.

---

## 6. Mappa del Repository & Organizzazione dei File

```
PraticaDebitiAI/
├── docker-compose.yml              # Configurazione microservizi produzione/staging
├── docker-compose.local.yml        # Override locale (LM Studio endpoint, porte)
├── README.md                       # Guida rapida e panoramica
├── DOCUMENTAZIONE_UFFICIALE_DOSSIERLEX.md # [QUESTO DOCUMENTO] Manuale completo
├── GUIDA_DISTRIBUZIONE_STUDIO_E_COLLEGHI.md # Manuale rete LAN e VPN colleghi
│
├── backend/
│   ├── Dockerfile                  # Container backend FastAPI (Python 3.12)
│   ├── requirements.txt            # Dipendenze Python (FastAPI, SQLAlchemy, Celery, fpdf2, ecc.)
│   ├── alembic/                    # Script e migrazioni del database PostgreSQL
│   ├── app/
│   │   ├── main.py                 # Inizializzazione FastAPI e middleware CORS
│   │   ├── config.py               # Parametri d'ambiente (DATABASE_URL, LM_STUDIO_URL)
│   │   ├── db.py                   # Engine SQLAlchemy con connect_args anti-collisione
│   │   ├── api/
│   │   │   ├── routes.py           # Endpoint REST: pratiche, documenti, report, PDF
│   │   │   ├── client_card.py      # Scheda cliente e integrazione Openapi
│   │   │   └── case_chat.py        # Chatbot interattivo sul fascicolo
│   │   ├── models/
│   │   │   └── entities.py         # 24 modelli relazionali (Case, Document, Vehicle, ecc.)
│   │   ├── schemas/
│   │   │   ├── dto.py              # Pydantic DTO per request/response
│   │   │   └── debtor.py           # Schemi validazione anagrafica
│   │   ├── services/
│   │   │   ├── pipeline_service.py # Pipeline ingestion, OCR, parsing deterministico e normalizzazione
│   │   │   ├── aer_parser.py       # Parser specialistico estratti AdER da saldare
│   │   │   ├── ocr.py              # Adapter OCR (PaddleOCR, Tesseract, PDFPlumber)
│   │   │   ├── preanalysis_protocol.py # Protocollo forense a 5 step e prompt peritali
│   │   │   ├── preanalysis_report.py   # Compilatore del report a 11 capitoli e indici CCII
│   │   │   ├── forensic_preanalysis_chain.py # Catena LangChain per invocazione Qwen locale
│   │   │   ├── benchmark_pdf_generator.py # Motore vettoriale PDF ufficiale a 7 pagine
│   │   │   ├── statutory_knowledge.py  # Conoscenza codicistica (OIC 12, CCII)
│   │   │   ├── case_indicators.py  # Calcolo indici patrimoniali e reddituali
│   │   │   └── fiscal_code.py      # Algoritmo validazione e omocodie Codice Fiscale
│   │   └── workers/
│   │       ├── celery_app.py       # Configurazione Celery e Redis broker
│   │       └── tasks.py            # Task asincroni: process_document, run_cross_analysis
│   └── tests/                      # Suite di collaudo automatizzata (43 test unitari)
│
└── frontend/
    ├── Dockerfile.prod             # Build multi-stage ottimizzata Next.js per produzione
    ├── package.json                # Dipendenze Node.js (Next.js 14, React 18)
    └── app/
        ├── layout.js               # Layout globale e font "Hanken Grotesk"
        ├── globals.css             # Design System istituzionale "Institutional Heritage"
        └── pratiche/
            ├── page.js             # Cruscotto elenco pratiche con filtri e ricerca
            └── [id]/
                └── scheda/
                    ├── page.js     # Router a schede della pratica
                    ├── scheda-analysis.js    # Visualizzatore reattivo del Report 11 Capitoli
                    ├── scheda-documents.js   # Gestione upload documenti e stato OCR
                    ├── scheda-debiti.js      # Dettaglio posizioni debitorie AdER/Banche
                    └── scheda-patrimonio.js  # Gestione beni immobili e autoveicoli
```

---

## 7. Infrastruttura di Rete & Distribuzione dello Studio

DossierLex è configurato con un modello **Server Centrale + Postazioni Client Leggere**:

```
                       ┌──────────────────────────────────────────────┐
                       │          PC SERVER CENTRALE (Giuseppe)       │
                       │   - Database centrale PostgreSQL             │
                       │   - Backend FastAPI e Worker Celery          │
                       │   - Modello AI Qwen 27B locale (LM Studio)   │
                       │   - Storage documenti delle pratiche         │
                       └──────────────────────┬───────────────────────┘
                                              │
                              Rete Studio (LAN) o VPN (Tailscale)
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
         ┌─────────────────────────┐                     ┌─────────────────────────┐
         │     POSTAZIONE STUDIO   │                     │   SMART WORKING / CASA  │
         │   (Colleghi in Wi-Fi)   │                     │   (Avvocato su Mac/PC)  │
         │  http://192.168.1.31:3001│                     │ http://100.80.46.116:3001│
         │  ❌ Zero codice          │                     │  ❌ Zero codice         │
         │  ❌ Zero Docker          │                     │  ❌ Zero Docker         │
         │  🌐 Solo Google Chrome   │                     │  🌐 Solo Google Chrome  │
         └─────────────────────────┘                     └─────────────────────────┘
```

* **Server dello Studio**: ospita Docker, i dati e LM Studio.
* **Postazioni dei Colleghi**: non installano nulla. Aprono semplicemente il browser Google Chrome all'indirizzo locale `http://192.168.1.31:3001`.
* **Accesso Remoto**: collegandosi alla VPN privata sicura **Tailscale**, la piattaforma risponde all'IP fisso `http://100.80.46.116:3001` da qualsiasi luogo, mantenendo i dati protetti all'interno della rete criptata dello studio.

---

## 8. Guida Operativa & Manutenzione

### 1. Avvio e Controllo dei Servizi
```bash
# Avvio di tutti i container microservizi in background
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# Verifica dello stato di salute dei container
docker ps

# Visualizzazione dei log in tempo reale del backend
docker logs -f praticadebitiai-backend-1

# Visualizzazione dei log del worker asincrono
docker logs -f praticadebitiai-worker-1
```

### 2. Esecuzione dei Test Automatizzati
```bash
# Esecuzione della suite completa di collaudo (43 test di regressione)
docker exec praticadebitiai-backend-1 pytest
```

### 3. Ricompilazione Frontend dopo modifiche grafiche
```bash
# Build dell'immagine di produzione Next.js
docker compose -f docker-compose.yml -f docker-compose.local.yml build frontend

# Riavvio a caldo del container frontend
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d --no-deps frontend
```

### 4. Backup del Database PostgreSQL
```bash
# Dump di sicurezza completo del database
docker exec -t legal_rag_postgres pg_dump -U postgres legal_rag > backup_dossierlex_$(date +%Y%m%d).sql
```

---

*Documento approvato per l'integrazione ufficiale nel repository e a presidio della qualità operativa dello Studio Legale Avv. Aurelio Bentivegna.*
