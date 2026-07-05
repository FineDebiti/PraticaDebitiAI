# Pratica Debiti AI — MVP locale

Ambiente completo che gira **interamente sul tuo computer** con Docker.
OCR e AI sono **configurabili**: di default girano in modalità offline/stub
(zero costi, zero dati fuori); con una riga di `.env` passi ai provider cloud.

## Cosa contiene

- **backend/** — API Python (FastAPI), modelli dati, pipeline OCR + AI, worker async
- **frontend/** — interfaccia web (Next.js): lista pratiche, dettaglio, upload, dati estratti
- **docker-compose.yml** — avvia tutto: database, code, backend, worker, frontend

## Requisiti

Solo **Docker Desktop** installato. Niente altro.

## Avvio in 3 comandi

```bash
cp .env.example .env        # 1. crea la configurazione (default: offline/stub)
docker compose up --build   # 2. avvia tutto (la prima volta ci mette qualche minuto)
# 3. apri il browser su http://localhost:3000
```

Backend API: http://localhost:8000/docs (documentazione interattiva)

## Come si usa

1. Crea una pratica (nome cliente).
2. Apri la pratica e carica un documento (PDF o immagine).
3. Il documento viene elaborato in automatico: OCR → classificazione → estrazione.
4. Dopo qualche secondo compaiono tipo documento e posizioni debitorie estratte.
   Le righe a bassa confidenza sono evidenziate in giallo (da verificare).

## Le 3 modalità di test (la parte importante)

Apri `.env` e cambia due righe:

### Modalità A — Offline / stub (default)
```
OCR_PROVIDER=tesseract
LLM_PROVIDER=stub
```
Tutto sul tuo computer, zero costi, zero dati fuori. L'estrazione è **simulata**
(trova gli importi col testo ma non "ragiona"). Serve a provare il flusso e l'interfaccia.

### Modalità B — OCR locale + AI cloud
```
OCR_PROVIDER=tesseract
LLM_PROVIDER=gemini
GEMINI_API_KEY=la-tua-chiave
```
L'estrazione usa l'AI vera. Buon compromesso per iniziare i test di accuratezza.

### Modalità C — Cloud completo (come in produzione)
```
OCR_PROVIDER=docai
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
DOCAI_PROJECT_ID=...
DOCAI_PROCESSOR_ID=...
DOCAI_LOCATION=eu
GOOGLE_APPLICATION_CREDENTIALS=/code/gcp-key.json
```
Misura l'accuratezza reale dei provider che userai dal vivo.
**Usa solo documenti ANONIMIZZATI** in questa modalità.

> Per la Modalità C va aggiunto `google-cloud-documentai` a `backend/requirements.txt`.
> Il codice di integrazione è già pronto in `backend/app/services/ocr.py`.

## Dove mettere mano (i file che contano)

| Voglio… | File |
|---|---|
| Migliorare i prompt di estrazione | `backend/app/services/prompts.py` |
| Cambiare/aggiungere provider OCR | `backend/app/services/ocr.py` |
| Cambiare/aggiungere provider AI | `backend/app/services/llm.py` |
| Modificare il modello dati | `backend/app/models/entities.py` |
| Aggiungere endpoint | `backend/app/api/routes.py` |

## Privacy

In modalità A (default) nessun dato esce dal computer. In modalità B/C i documenti
vengono inviati ai provider scelti: usa **solo documenti anonimizzati** per i test,
come previsto dal Piano Fase 0.

## Scheda cliente e ricerca da fonti esterne (Openapi)

La **scheda cliente** è il cuore dell'app: anagrafica, dati economici, nucleo
familiare, situazioni in corso, immobili e veicoli. Si apre dal pulsante
"📋 Apri scheda cliente" nella pagina pratica.

Ogni sezione del patrimonio (immobili, veicoli) e i dati azienda hanno un
**box di ricerca 🔎**: inserisci il codice fiscale / P.IVA, premi Cerca, e i
risultati pre-compilano i campi. Confermi con Importa, poi Salva.

Configurazione ricerca nel `.env`:

```
ENRICHMENT_MODE=stub        # stub = simulato e gratis | openapi = reale a pagamento
OPENAPI_TOKEN=              # il tuo token da console.openapi.com/oauth
OPENAPI_BASE_URL=https://test.visengine2.altravia.com   # sandbox (non addebita)
# produzione (visure reali a pagamento): https://visengine2.altravia.com
```

Note sull'integrazione Openapi/Visengine:
- Le visure sono **asincrone** (richiesta → attesa → risultato) e **a pagamento**.
- Restituiscono dati strutturati JSON (non solo PDF).
- Il mapping dei campi risposta→scheda (`backend/app/services/enrichment.py`,
  funzioni `_map_vehicle` / `_map_real_estate`) va rifinito alla prima visura reale.
- La **PEC** non è in Visengine: serve un'altra API del catalogo Openapi.

## ⚠ Modifiche al database

Quando cambi i modelli dati (`backend/app/models/entities.py`), il database
esistente NON si aggiorna da solo. Serve ripartire pulito:

```
docker compose down -v   # cancella il DB (perdi i dati di test)
docker compose up --build
```

In futuro andrà aggiunto un sistema di migrazioni (Alembic) per aggiornare
il database senza perdere i dati. Per ora, in fase di test, va bene così.

## Stato

MVP di test funzionante: pratiche, scheda cliente dettagliata, ricerca/import
da Openapi (in stub), pipeline OCR+AI (in pausa nella UI ma attiva nel codice).
Mancano (volutamente, per la Fase 0): autenticazione/login, multi-utente,
report PDF/Excel, gestione ruoli, migrazioni DB. Da aggiungere nella fase MVP
vera dopo la validazione.
