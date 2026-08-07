# DossierLex — Guida all'Installazione e Uso su macOS (Locale & Offline)

Questa guida passo-passo consente al cliente di installare ed eseguire la piattaforma **DossierLex** in totale autonomia sul proprio Mac, **senza inviare dati a server esterni** (100% riservato ed offline).

L'applicazione viene fornita già con i due profili di test caricati ed analizzati:
1. **Persona Fisica:** Alessandro Traietti (con 12 documenti reali allegati)
2. **Azienda:** Planeta S.r.l. (con 6 documenti contabili/camerali allegati)

---

## 1. Requisiti di Sistema
- **Mac OS:** macOS 12 (Monterey) o versione successiva (Chip Apple Silicon M1/M2/M3/M4 o Intel).
- **RAM:** Minimo 8 GB (Consigliati 16 GB).
- **Spazio su Disco:** Almeno 5 GB liberi.
- **Docker Desktop per Mac:** (Gratuito, istruzioni al punto 2).

---

## 2. Installazione di Docker Desktop (Da fare solo la prima volta)

1. **Scarica il file di installazione:**
   - Apri il browser e vai su: **https://www.docker.com/products/docker-desktop/**
   - Scegli la versione corretta per il tuo Mac:
     - **Mac con Apple Silicon** (se il tuo Mac ha un chip M1, M2, M3 o M4).
     - **Mac con chip Intel** (per i modelli Mac più datati).
     *(Se non sai quale chip hai: clicca in alto a sinistra sul simbolo della mela  -> "Informazioni su questo Mac").*

2. **Installa l'applicazione:**
   - Fai doppio clic sul file `.dmg` scaricato.
   - Trascina l'icona di **Docker** nella cartella **Applicazioni**.

3. **Primo avvio di Docker:**
   - Apri **Docker** dalla cartella Applicazioni.
   - Accetta i termini di licenza e fornisci i permessi richiesti.
   - Nella barra dei menu in alto al Mac comparirà un'icona a forma di balena 🐋.
   - **IMPORTANTE:** Attendi finché l'icona della balena non diventa stazionaria (stato: *Engine Running*). Lascia Docker aperto.

---

## 3. Avvio di DossierLex con i Dati di Prova

1. Copia la cartella del progetto (`PraticaDebitiAI`) sul desktop o nella cartella Documenti del tuo Mac.
2. Apri la cartella `PraticaDebitiAI`.
3. Fai **doppio clic sul file `avvia.command`**.
   *(Nota: Se macOS mostra un avviso di sicurezza la prima volta, fai **Clic Destro sul file -> Apri -> Apri**).*
4. Si aprirà una finestra di terminale che installerà e preparerà l'ambiente.
   *(La prima volta può richiedere 2-3 minuti per compilare i servizi. Le volte successive si avvierà in pochi secondi).*
5. Non appena completato, il browser del Mac si aprirà automaticamente sull'indirizzo **`http://localhost:3000`**.

---

## 4. Come Testare le Pratiche già Caricate

Al primo accesso su `http://localhost:3000` troverai già presenti le due anagrafiche:

- **Alessandro Traietti (Persona Fisica):**
  - Clicca su **Dati** per visualizzare i quadri dei redditi, spese e i 12 documenti PDF allegati ed estratti tramite OCR.
  - Clicca su **Valutazione** per esaminare gli indici di rischio, DTI Ratio e i grafici econometrici.
  - Clicca su **Report** per visualizzare ed esportare in PDF la scheda finale.

- **Planeta S.r.l. (Azienda):**
  - Clicca sui rispettivi moduli per esaminare la Visura Camerale, i Bilanci 2023, 2024, 2025 e i debiti di ruolo ADeR.

---

## 5. Come Creare e Testare Nuove Pratiche

Puoi testare l'inserimento di nuovi clienti e l'analisi di nuovi documenti in qualsiasi momento:

1. **Torna nella schermata principale Pratiche (`/`):**
2. **Nel box "Nuova Pratica":**
   - Seleziona **Persona fisica** ed inserisci *Nome*, *Cognome* e *Codice Fiscale* (16 caratteri).
   - Oppure seleziona **Azienda** ed inserisci *Ragione Sociale* e *Partita IVA* (11 cifre).
   - Clicca su **Crea anagrafica**.
3. **Carica i Documenti:**
   - Dalla riga del nuovo cliente appena creato, clicca su **Dati** (o **Scheda**).
   - Nella sezione *Pannello Documentale*, trascina i file PDF che vuoi far analizzare (es. Visure, Dichiarazioni, Estratti).
   - L'OCR elaborerà il file ed aggiornerà la scheda.

---

## 6. Spegnimento e Uso Quotidiano

- **Per chiudere l'app a fine lavoro:** Fai doppio clic su `ferma.command`. Tutti i dati creati rimarranno salvati sul Mac.
- **Per riaprire l'app nei giorni successivi:** Apri Docker Desktop e fai doppio clic su `avvia.command`.

---

## 7. Risoluzione Problemi Comuni

| Problema | Soluzione |
|---|---|
| *"Docker non risulta in esecuzione"* | Apri Docker Desktop dalla cartella Applicazioni e attendi che la balena sia nello stato *Engine Running*. |
| macOS dice *"Impossibile aprire avvia.command"* | Fai **clic destro** sul file `avvia.command` -> scegli **Apri** dal menu -> conferma **Apri**. |
| La pagina `localhost:3000` non si carica | Attendi circa 1 minuto al primo avvio. Ricarica la pagina nel browser (`Cmd + R`). |
