# Come attivare Gemini (estrazione AI reale)

L'app è già pronta per usare Gemini. Per accenderlo servono 3 passi.

## 1. Ottieni la chiave API Gemini (gratis per iniziare)

1. Vai su **https://aistudio.google.com/apikey** (accedi col tuo account Google).
2. Clicca **"Create API key"** / "Crea chiave API".
3. Copia la chiave (una stringa lunga tipo `AIza...`). Tienila riservata.

Nota: Google AI Studio ha un piano gratuito con limiti generosi per i test.
Per uso intensivo/produzione si passa al piano a pagamento (vedi il modello costi).

## 2. Inserisci la chiave nel file `.env`

Apri `pratica-debiti-ai-mvp/.env` e imposta queste righe:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=incolla-qui-la-tua-chiave
LLM_MODEL=gemini-2.5-flash
```

(La riga `LLM_MODEL` è già presente; basta cambiare le altre due.)

## 3. Riavvia i container

Nel terminale, dalla cartella `pratica-debiti-ai-mvp`:

```
docker compose up -d --build
```

(Solo backend e worker leggono il `.env`, quindi non serve `down -v`:
non abbiamo cambiato il database.)

## Come provarlo

1. Apri una pratica → scheda cliente.
2. Nel pannello documenti, carica una **visura catastale** (PDF o immagine).
3. Attendi: lo stato passa da `caricato` → `in_elaborazione` → `elaborato`.
4. Gli **immobili estratti** compaiono nella sezione Patrimonio della scheda.

La visura catastale usa l'estrazione **multimodale**: Gemini legge direttamente
il PDF/immagine, quindi funziona anche con scansioni, senza OCR separato.

## ⚠ Privacy

Con Gemini attivo, il documento caricato **esce dal tuo computer** e va sui
server di Google per l'elaborazione. Per i test coi tuoi documenti va bene.
Per i documenti dei clienti servirà anonimizzazione + clausole privacy (Fase 0).

## Se qualcosa non va

- **"GEMINI_API_KEY mancante"** → la chiave non è nel `.env` o il container non è
  stato riavviato dopo averla messa.
- **Documento resta su `errore`** → guarda i log: `docker compose logs worker --tail 30`.
- **Estrazione imprecisa** → normale alla prima visura: il prompt in
  `backend/app/services/prompts.py` (sezione VISURA_CATASTALE) va rifinito sui
  campi reali del tuo documento. Manda l'output e lo tariamo insieme.
