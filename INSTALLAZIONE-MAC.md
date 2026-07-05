# Pratica Debiti AI — Installazione su Mac (locale, offline)

Questa guida installa l'applicazione **sul computer del cliente**. I dati (pratiche,
documenti) **restano sul computer**: non vengono inviati su internet. L'estrazione
dei documenti usa un OCR locale; l'AI gira in modalità dimostrativa (vedi ultima
sezione per l'estrazione AI reale offline).

---

## 1. Requisiti

- **macOS 12 (Monterey) o successivo** — Mac con chip Apple (M1/M2/M3/M4) o Intel
- **8 GB di RAM** (consigliati 16 GB)
- **~5 GB di spazio libero** su disco
- **Docker Desktop** (gratuito)

## 2. Installare Docker Desktop (una volta sola)

1. Scarica Docker Desktop da: https://www.docker.com/products/docker-desktop/
   (scegli la versione giusta: **Apple Silicon** per Mac M1/M2/M3/M4, **Intel** per i Mac più vecchi.
   Non sai quale hai? Menu  → "Informazioni su questo Mac": se c'è scritto "Apple M…" è Apple Silicon).
2. Apri il file `.dmg` scaricato e trascina **Docker** nella cartella **Applicazioni**.
3. Apri **Docker** dalle Applicazioni e concedi i permessi richiesti al primo avvio.
4. Aspetta che l'icona della balena nella barra dei menu sia **ferma** (Engine running). Lascialo aperto.

## 3. Copiare l'applicazione

Copia l'intera cartella `pratica-debiti-ai-mvp` sul computer, ad esempio nella
cartella **Documenti** o direttamente nella Home.

## 4. Primo avvio

1. Assicurati che **Docker Desktop sia avviato** (icona della balena nella barra dei menu).
2. Entra nella cartella e fai **doppio clic su `avvia.command`**.
3. La **prima volta** macOS potrebbe chiedere conferma perché il file arriva da
   un altro computer: se compare l'avviso, fai **clic destro sul file → Apri → Apri**
   (basta una volta sola; vale anche per `ferma.command` e `popola-demo.command`).
4. La **prima volta** scarica e prepara tutto: può richiedere **diversi minuti**.
   Le volte successive l'avvio è in pochi secondi.
5. Al termine si apre da solo il browser su **http://localhost:3000**.

Se il browser non si apre da solo, aprilo a mano e vai su `http://localhost:3000`.

> Se il doppio clic non funziona proprio (il file si apre come testo o non parte),
> apri il **Terminale**, trascina dentro il file `avvia.command` e premi INVIO.

## 5. Uso quotidiano

- **Avviare:** doppio clic su `avvia.command` (con Docker Desktop aperto).
- **Spegnere:** doppio clic su `ferma.command`. I dati restano salvati.
- **Caricare una pratica di esempio:** doppio clic su `popola-demo.command`
  (crea la pratica fittizia `DEMO-0001` per fare una dimostrazione).

## 6. Dove finiscono i dati

Database e documenti sono salvati in **volumi Docker** sul computer e sopravvivono
allo spegnimento e ai riavvii. Restano finché non vengono cancellati di proposito.

- **Backup:** vedi sezione 8.
- **Azzerare tutto** (cancella pratiche e documenti):
  ```
  docker compose -f docker-compose.local.yml down -v
  ```
  ⚠️ Il flag `-v` elimina anche i dati. Usalo solo per ripartire da zero.

## 7. Problemi comuni

| Sintomo | Soluzione |
|---|---|
| "Docker non risulta in esecuzione" | Apri Docker Desktop e aspetta la balena ferma, poi rilancia `avvia.command`. |
| macOS blocca il file (".command non può essere aperto") | Clic destro sul file → **Apri** → **Apri**. Serve solo la prima volta. |
| La pagina `localhost:3000` non si apre | Aspetta 1 minuto al primo avvio; ricarica. Verifica che Docker sia avviato. |
| Porta 3000 o 8000 occupata | Chiudi il programma che la usa, oppure chiedici di cambiare porta. |
| Voglio ripartire pulito | `docker compose -f docker-compose.local.yml down -v` poi `avvia.command`. |

## 8. Backup e ripristino (facoltativo)

I comandi vanno eseguiti nel **Terminale**, dentro la cartella dell'app, con l'app avviata.

Backup del database:
```
docker compose -f docker-compose.local.yml exec db pg_dump -U pratica pratica_debiti > backup.sql
```
Ripristino:
```
docker compose -f docker-compose.local.yml exec -T db psql -U pratica pratica_debiti < backup.sql
```

---

## Nota tecnica — Estrazione AI reale in modalità offline

In questa configurazione l'AI è in modalità **`stub`**: l'app mostra l'intero flusso
(caricamento documento → OCR locale → scheda compilata) ma i campi estratti dal
documento sono **simulati**. L'OCR (lettura del testo) è invece reale e locale.

Per un'estrazione AI **vera senza internet** serve un modello linguistico **locale**
(es. tramite **Ollama**): è una piccola estensione di codice (un nuovo "provider" LLM).
Va valutata la qualità sui documenti reali e un computer adeguato (più RAM, idealmente GPU).
Chiedici questa estensione se la demo deve mostrare estrazioni reali completamente
offline.
