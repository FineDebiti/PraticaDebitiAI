# RAPPORTO COMPARATIVO E BENCHMARK TECNICO
## DossierLex (PraticaDebitiAI) vs. Preanalisi Crisi v1.0 (Qwen 3.8 27B / LM Studio)

**Destinatario:** Avv. Aurelio Bentivegna (Responsabile Sviluppo & Governance)  
**Mittente:** Giuseppe (Collaudo Ambienti & Benchmark Operativo)  
**Data:** 09 Ottobre 2026  
**Oggetto:** Confronto prestazionale, accuratezza estrattiva e tenuta forense sullo stesso fascicolo aziendale (*SM Costruzioni Generali di Matarrese Salvatore*)  
**Documenti Testati:**  
1. Visura Camerale Ordinaria CCIAA Bari (17/03/2026)  
2. Bilancio d'Esercizio a 4 sezioni al 31/12/2025  
3. Bilancio Provvisorio Infra-annuale a 4 sezioni al 27/07/2026  

---

## 1. Executive Summary del Confronto

Entrambe le piattaforme sono state sottoposte al medesimo fascicolo contabile-documentale. L'analisi comparativa evidenzia due approcci architetturali differenti con esiti operativi marcatamente divergenti:

* **Preanalisi Crisi v1.0 (approccio locale: Tesseract OCR + Qwen 3.8 27B):**  
  Adotta un'eccellente logica di salvaguardia difensiva (*Human Gate*), ma soffre del collo di bottiglia dell'**OCR testuale tradizionale**: il testo contabile scansionato viene sporcato da artefatti grafici, costringendo il codice a **scartare 8 dati su 9** per mancato riscontro letterale, con un tempo di inferenza di **236,53 secondi (~4 minuti)** e mancata lettura della visura camerale.
* **DossierLex / PraticaDebitiAI (approccio multimodale: Gemini 3.8 Flash + Supabase Cloud):**  
  Grazie alla **visione multimodale nativa diretta**, supera alla radice il problema dell'OCR testuale: interpreta le tabelle contabili a 4 sezioni estraendo **il 100% dei dati al centesimo esatto**, elabora la visura camerale in automatico (individuando la responsabilità illimitata ex art. 2740 c.c.) e calcola in tempo reale gli indici di crisi CNDCEC, completando l'elaborazione in circa **15-30 secondi**.

---

## 2. Tabella di Confronto Diretto Parametro per Parametro

| Parametro Analizzato | Preanalisi Crisi v1.0 (Qwen 3.8 27B) | DossierLex / PraticaDebitiAI (Gemini 3.8 Flash) | Valutazione & Impatto Forense |
|---|---|---|---|
| **Tecnologia di Lettura** | OCR tradizionale a testo grezzo (`pdfplumber` + Tesseract) | **AI Multimodale Nativa** (Visione diretta layout PDF) | DossierLex non degrada la tabella in testo grezzo e non perde la struttura delle colonne. |
| **Tempo di Inferenza** | **236,53 secondi** (3 min e 56 sec) | **15 - 30 secondi** a documento | **DossierLex è oltre 8 volte più veloce** nell'elaborazione del fascicolo. |
| **Requisiti Hardware** | Hardware pesante: PC 32 GB RAM, GPU dedicata, file GGUF da 16,8 GB | **Cloud-ready leggero:** gira su qualsiasi PC/Mac via browser | DossierLex è scalabile su più operatori dello studio senza costi hardware per postazione. |
| **Totale Attivo (Bilancio 2025)** | **NON RISCONTRATO** (letto `1.136.436` per confusione grafica tra 9 e 3) | **RISCONTRATO AL CENTESIMO:** `€ 1.136.496,23` | DossierLex previene l'errore tipico dell'OCR su scansioni numeriche. |
| **Ricavi delle Vendite (2025)** | **NON RISCONTRATO** (l'OCR ha letto `1.8e .791,71`) | **RISCONTRATO AL CENTESIMO:** `€ 1.882.761,71` | DossierLex comprende il numero anche in presenza di righe o timbri. |
| **Valore e Costi Produzione** | **MANCANTE** (non disponibile) | **COMPLETO:** Valore € 2.253.871,04, Costi € 2.151.228,71 | DossierLex estrae interamente il Conto Economico. |
| **Debiti Complessivi** | **NON RISCONTRATO** (proposto parziale € 990.269,55) | **ACQUISITO:** `€ 1.185.963,93` (e dettaglio fornitori € 1.027.442,20) | DossierLex riconosce la reale dimensione dell'esposizione debitoria. |
| **Lettura Visura Camerale** | **NON PREVISTA** (*"inserimento manuale"*) | **AUTOMATICA AL 100%:** Anagrafica, REA, ATECO, Titolare e Sede | Risparmio immediato di tempo di data-entry per la segreteria dello studio. |
| **Inquadramento Giuridico** | Non valorizzato in automatico | **ATTIVO:** Riconoscimento Ditta Individuale e alert art. 2740 c.c. | Supporto strategico immediato all'avvocato sulla responsabilità personale. |
| **Calcolo Indici CNDCEC** | **Non calcolati** (bloccati per assenza di dati validati) | **CALCOLATI E STORICIZZATI:** Current Ratio (0.76), Liquidità (0.009), PFN | Base analitica pronta per la perizia e per il piano di risanamento ex CCII. |
| **Persistenza e Database** | File locali JSON/TXT | **Database PostgreSQL relazionale (Supabase)** su 22 tabelle | Dati sincronizzati, sicuri e accessibili per generare report futuri. |

---

## 3. Analisi Dettagliata delle Divergenze Chiave

### 1. La Fragilità dell'OCR a Testo Grezzo vs la Potenza Multimodale
Il collaudo di Preanalisi Crisi su hardware GMKtec ha certificato un problema strutturale classico dei sistemi OCR basati su testo grezzo:
* Nella scansione del bilancio 2025, Tesseract ha letto `1.8e .791,71` invece di `1.882.761,71` e `12 1 15.3s` invece di `12.115,35`.
* Per proteggere l'avvocato da errori, il codice deterministico di Preanalisi Crisi ha correttamente rigettato quasi tutti i dati. Il risultato pratico, però, è che **l'istruttoria non si è conclusa** e il sistema ha dovuto richiedere il bilancio in formato Excel.
* **DossierLex ha risolto questo problema alla radice:** non convertendo il PDF in stringhe di testo grezzo frammentate, ma inviando le pagine come immagini visive al modello Gemini 3.8 Flash, che "vede" la tabella come la vedrebbe l'occhio umano di un commercialista, leggendo esattamente `1.882.761,71 €` e `1.136.496,23 €` senza alcuna esitazione.

### 2. Automazione della Visura Camerale
* In Preanalisi Crisi, la visura camerale è archiviata come file ma la compilazione dell'anagrafica aziendale è demandata all'inserimento manuale.
* In DossierLex, il modulo camerale ha estratto istantaneamente:
  * Denominazione esatta, P.IVA `08106270724`, Codice Fiscale `MTRSVT89L15A285I`, REA `BA-604501`.
  * La qualifica di impresa artigiana e piccolo imprenditore.
  * Il codice ATECO `41.00.00` per il benchmarking delle soglie di crisi.
  * La sospensione dell'Albo Gestori Ambientali per mancato pagamento diritti.

### 3. Usabilità Operativa e Scalabilità dello Studio
* **Preanalisi Crisi (LM Studio Locale):** Richiede una macchina dedicata con configurazioni complesse (disattivazione del reasoning loop di Qwen per evitare overflow di token, gestione di 17 GB di modelli in memoria, tempi di attesa di 4 minuti per pratica).
* **DossierLex (Microservizi Docker + API):** Si apre con un URL nel browser (`localhost:3000` o dominio di studio). Qualsiasi collaboratore o perito può accedere contemporaneamente, caricare i documenti e visualizzare i cruscotti in pochi secondi.

---

## 4. I Punti di Forza Riconosciuti a Preanalisi Crisi v1.0

Va dato atto alla soluzione Preanalisi Crisi di Aurelio di alcuni meriti architetturali di grande valore:
1. **L'eccellenza del filtro difensivo ("Human Gate"):** L'idea di bloccare i dati non perfettamente riscontrati alla lettera è un principio forense sano, che impedisce all'avvocato di depositare dati errati.
2. **Capacità diagnostica del modello Qwen:** Nel testo descrittivo, Qwen ha saputo riconoscere autonomamente che la mancata quadratura dipendeva dall'utile d'esercizio (102.642,33 €) e ha formulato richieste di chiarimento sensate.

---

## 5. Raccomandazione Strategica Conclusiva per l'Avv. Aurelio Bentivegna

L'esperimento dimostra che la combinazione ideale per portare la governance al massimo livello consiste in:

1. **Adottare DossierLex come motore principale di ingestione ed estrazione:**  
   Elimina il collo di bottiglia dell'OCR, azzera i tempi di attesa (da 4 minuti a 20 secondi) e acquisisce automaticamente sia i bilanci sia le visure camerali.
2. **Mantenere il rigore della validazione a doppio controllo (Human-in-the-loop):**  
   DossierLex implementa già la tabella di audit (`field_edits`) dove ogni dato contabile estratto può essere verificato e confermato dal perito prima del deposito finale.
3. **Completare le Milestone 3 e 4:**  
   Integrare nel report stampabile di DossierLex i grafici radar della crisi d'impresa e il layout formale PDF/A per il deposito telematico presso l'OCC o il Tribunale.

