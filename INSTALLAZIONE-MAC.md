# Guida Passo-Passo all'Installazione e Uso di DossierLex per macOS

Questa guida è pensata per rendere l'installazione e il test della piattaforma **DossierLex** facili ed immediati su qualsiasi Mac, anche per chi non ha competenze tecniche o informatiche avanzate.

---

## 📌 Concetti Chiave Spiegati in Modo Semplice

- **Cos'è Docker Desktop?**  
  Docker è un programma gratuito che permette a DossierLex di funzionare sul tuo Mac. Docker crea al suo interno un piccolo ambiente riservato (basato su motore Linux) che contiene il database, l'algoritmo di analisi documentale e l'interfaccia grafica dell'applicazione.
- **Serve installare Linux manualmente?**  
  **NO.** **Docker Desktop fa tutto in automatico.** Non devi installare o configurare Linux a mano: basta aprire Docker Desktop ed esso gestirà il motore sottostante in totale trasparenza.
- **I miei dati sono sicuri?**  
  **SÌ, al 100%.** L'applicazione lavora **esclusivamente offline e in locale** sul tuo Mac. Nessun documento o dato cliente viene inviato a server esterni o terze parti.

---

## 📋 Requisiti Minimi
- **Computer:** Qualsiasi Mac con sistema operativo macOS 12 (Monterey) o superiore (sia Mac con processore Apple M1/M2/M3/M4 sia Mac Intel).
- **RAM:** Almeno 8 GB.
- **Spazio libero:** 5 GB su disco.
- **Connessione Internet:** Necessaria **solo la prima volta** per scaricare Docker Desktop.

---

## 🛠️ PASSO 1: Installare Docker Desktop (Solo la prima volta)

### 1.1 Scaricare l'installatore
1. Apri il browser (Safari o Chrome) e vai su questo link:  
   👉 **https://www.docker.com/products/docker-desktop/**
2. Troverai due pulsanti per il download. Scegli quello adatto al tuo Mac:
   - **Mac with Apple Chip:** Se il tuo Mac ha un processore Apple M1, M2, M3 o M4.
   - **Mac with Intel Chip:** Se il tuo Mac è un modello più datato con processore Intel.
   *(Se non sai quale processore possiedi: clicca in alto a sinistra sul simbolo della mela  -> **Informazioni su questo Mac**).*

### 1.2 Installa il programma
1. Vai nella cartella **Download** del Mac e fai doppio clic sul file scaricato (`Docker.dmg`).
2. Si aprirà una finestra: **trascina l'icona di Docker nella cartella Applicazioni**.
3. Attendi che il completamento del tracciamento sia ultimato (circa 1 minuto).

### 1.3 Avvia Docker Desktop
1. Vai nella cartella **Applicazioni** del Mac ed apri **Docker**.
2. Al primo avvio ti verrà chiesto di accettare le condizioni d'uso: clicca su **Accept**.
3. Se macOS ti chiede la password del Mac per installare i componenti di rete, inseriscila e conferma.
4. **IMPORTANTE:** In alto a destra nella barra dei menu del Mac apparirà una piccola **balenottera** 🐋.
5. Attendi circa 30-60 secondi finché l'icona della balenottera non diventa fissa con la scritta **Engine Running**.  
   *(Lascia Docker aperto in background).*

---

## 🚀 PASSO 2: Avviare DossierLex in 1 Clic

1. Estrai la cartella **`PraticaDebitiAI`** (la cartella fornita) e copiala dove preferisci (es. sul *Desktop* o in *Documenti*).
2. Apri la cartella `PraticaDebitiAI`.
3. Fai **doppio clic sul file `avvia.command`**.

### ⚠️ Nota di Sicurezza al Primo Avvio:
La prima volta che fai doppio clic su `avvia.command`, macOS potrebbe mostrare questo avviso:  
*"Impossibile aprire avvia.command perché proviene da uno sviluppatore non identificato"*.

**Come procedere in 2 secondi:**
1. Fai **Clic Destro** (oppure premi *Tasto CTRL + Clic*) sul file `avvia.command`.
2. Scegli **Apri** dal menu a tendina.
3. Nella finestra che compare, clicca nuovamente sul pulsante **Apri**.

### Cosa accade ora?
- Si aprirà una finestra nera (il Terminale del Mac) che scaricherà i moduli e preparerà i dati.
- Al primo avvio la procedura richiede circa 2-3 minuti.
- Non appena pronto, **il tuo browser si aprirà automaticamente** all'indirizzo:  
  🌐 **`http://localhost:3000`**

---

## 🔍 PASSO 3: Testare le Pratiche di Prova già Caricate

Al primo avvio troverai già pronti e calcolati due profili completi di test:

### 👤 Pratica 1: Alessandro Traietti (Persona Fisica)
1. Nella tabella principale, individua la riga di **Alessandro Traietti** e clicca su **Dati** (o **Scheda**).
2. **Dati Economici:** Esamina i 12 documenti PDF allegati (CU, Unico, Estratti conto, Visure catastali) con le informazioni di reddito estratte dall'OCR.
3. **Valutazione Econometrica:** Clicca sulla scheda **Valutazione** per consultare l'Indice di Rischio Globale (**84,4 / 100**), il rapporto DTI (Debito/Reddito: **29,6%**) e il quadro patrimonio/debiti.
4. **Report Finale:** Clicca su **Report** per vedere il prospetto riassuntivo stampabile in PDF o stampabile per la pratica.

### 🏢 Pratica 2: Planeta S.r.l. (Azienda / Persona Giuridica)
1. Torna all'elenco pratiche e clicca su **Planeta S.r.l.**.
2. Consulta i documenti allegati: Visura Camerale, Bilanci e Cartelle di ruolo ADeR.
3. Nella sezione **Valutazione**, esamina il punteggio di rischio (**42,0 / 100**) e i debiti fiscali/bancari calcolati.

---

## ➕ PASSO 4: Come Creare e Testare una Nuova Pratica

Puoi testare la creazione di nuovi clienti ed analizzare i tuoi documenti in qualsiasi momento:

1. **Crea l'anagrafica:**
   - Dalla pagina principale (`http://localhost:3000`), vai nel box **Nuova Pratica**.
   - Scegli **Persona fisica** (inserendo Nome, Cognome e Codice Fiscale) oppure **Azienda** (inserendo Ragione Sociale e Partita IVA).
   - Clicca su **Crea anagrafica**.

2. **Carica i documenti:**
   - Clicca sulla nuova pratica creata.
   - Nella sezione **Pannello Documentale**, trascina uno o più file PDF (es. dichiarazioni dei redditi, cartelle esattoriali, estratti di ruolo, visure o bilanci).
   - Il sistema analizzerà i documenti estratti ed aggiornerà la scheda.

---

## 🛑 PASSO 5: Spegnimento e Usi Successivi

- **A fine lavoro (Spegnimento):** Fai doppio clic sul file **`ferma.command`**. Tutti i dati salvati e le pratiche create rimarranno salvati sul Mac.
- **Riapertura nei giorni successivi:**
  1. Assicurati che **Docker Desktop** sia aperto (icona della balenottera in alto a destra).
  2. Fai doppio clic su **`avvia.command`**.
  3. L'applicazione si avvierà in pochi secondi.

---

## ❓ Domande Frequenti e Risoluzione Problemi

| Evento / Messaggio | Soluzione |
|---|---|
| *"Docker non è avviato"* | Apri Docker dalla cartella Applicazioni e attendi la scritta *Engine Running* prima di lanciare `avvia.command`. |
| macOS impedisce l'apertura di `avvia.command` | Fai **Clic Destro** sul file `avvia.command` -> seleziona **Apri** -> conferma **Apri**. |
| La pagina `localhost:3000` mostra errore | Attendi 30-60 secondi (al primo avvio i container stanno caricando il DB) e ricarica la pagina (`Cmd + R`). |
