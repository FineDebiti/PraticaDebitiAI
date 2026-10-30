# DossierLex — Guida alla Distribuzione nello Studio Legale
### Architettura Server Centrale e Configurazione Postazioni Client (Operatori / Colleghi)
**Studio Legale Avv. Aurelio Bentivegna**

---

## 1. Riepilogo Esecutivo per l'Avvocato e lo Studio

DossierLex è una piattaforma professionale per l'audit documentale, la ricognizione debitoria e la redazione del **Report di Pre-Analisi ex CCII (Codice della Crisi d'Impresa e dell'Insolvenza)**. 

### Caratteristiche Chiave di Sicurezza e Riservatezza:
1. **100% Riservato e Conforme GDPR**: Tutti i documenti (visure, bilanci, estratti di ruolo AdER, Centrale Rischi) e i calcoli dell'Intelligenza Artificiale (**Qwen 27B**) rimangono **esclusivamente all'interno dello studio**. Nessun dato o cifra aziendale viene mai inviato a server esterni, cloud pubblici o API di terze parti.
2. **Database Centralizzato Unico**: Tutte le pratiche inserite, i documenti caricati e le revisioni dei report sono salvati in un archivio centrale comune. Se un collaboratore carica un bilancio o modifica un'anagrafica, l'aggiornamento è visibile in tempo reale a tutti i membri dello studio.
3. **Zero Costi Ricorrenti di API**: L'elaborazione neurale sfrutta l'accelerazione hardware della macchina dello studio senza costi a consumo.

---

## 2. Come Funziona l'Architettura (Server vs Colleghi)

L'infrastruttura è strutturata con il modello **Server di Studio + Client Leggeri**:

```
                  ┌──────────────────────────────────────────────┐
                  │          PC SERVER CENTRALE (Giuseppe)       │
                  │   - Database centrale PostgreSQL             │
                  │   - Backend FastAPI e Worker Celery          │
                  │   - Modello AI Qwen 27B locale (LM Studio)   │
                  │   - Archivio documenti delle pratiche        │
                  └──────────────────────┬───────────────────────┘
                                         │
                         Rete Locale Studio (Wi-Fi o Cavo)
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
    ┌─────────────────────────┐                     ┌─────────────────────────┐
    │      PC COLLEGA A       │                     │      PC COLLEGA B       │
    │   (Portatile / Fisso)   │                     │      (Avvocato / Mac)   │
    │  ❌ ZERO codice         │                     │  ❌ ZERO codice         │
    │  ❌ ZERO Docker         │                     │  ❌ ZERO Docker         │
    │  ❌ ZERO LM Studio      │                     │  ❌ ZERO LM Studio      │
    │  🌐 Solo Google Chrome  │                     │  🌐 Solo Google Chrome  │
    └─────────────────────────┘                     └─────────────────────────┘
```

> [!IMPORTANT]
> **I colleghi NON devono avere la cartella con il codice di DossierLex!**
> Dare il codice sorgente agli operatori sarebbe rischioso e controproducente:
> - Creerebbe database separati (le pratiche del collega non si vedrebbero sul tuo PC).
> - Obbligherebbe ogni computer a installare Docker, Python e occupare 30+ GB di modelli AI.
> - Esporrebbe i file di codice a cancellazioni accidentali.
> 
> Ai colleghi serve **SOLO un collegamento Desktop da 1 KB** che apre DossierLex nel loro browser Google Chrome.

---

## 3. Guida per la Macchina Server (Il tuo PC)

Il tuo computer funge da "motore centrale" dello studio.

### Come avviare DossierLex:
- Fai doppio clic sull'icona **DossierLex** presente sul tuo Desktop.
- Il launcher automatico (`launch_dossierlex.pyw`):
  1. Avvia Docker Desktop in background se è spento.
  2. Inizializza i container (Database, Redis, Backend, Frontend).
  3. Apre automaticamente DossierLex come nuova scheda nel tuo **Google Chrome** già aperto.

### Come conoscere l'indirizzo IP locale da dare ai colleghi:
1. Premi `Tasto Windows + R`, scrivi `cmd` e premi Invio.
2. Digita: `ipconfig` e premi Invio.
3. Cerca la voce **Indirizzo IPv4** (ad esempio: `192.168.1.150` oppure `192.168.1.85`).
4. L'indirizzo di DossierLex per l'ufficio sarà:
   `http://192.168.1.150:3001`

---

## 4. Guida per le Postazioni degli Operatori / Colleghi

Configurare il computer di un collaboratore richiede **meno di 1 minuto**:

### Opzione A: Creazione Automatica dell'Icona (Consigliata)
Nella cartella principale di DossierLex trovi il file:
`Crea_Collegamento_Colleghi.bat`

1. Copia sul computer del collega solo due piccoli file:
   - `Crea_Collegamento_Colleghi.bat`
   - `DossierLex.ico`
2. Fai doppio clic su `Crea_Collegamento_Colleghi.bat`.
3. Inserisci l'indirizzo IP del PC Server (es. `192.168.1.150`).
4. Sul Desktop del collega apparirà l'icona ufficiale di **DossierLex**:
   - Cliccandoci, DossierLex si apre all'istante nel suo browser senza che il collega debba installare o configurare alcunché!

### Opzione B: Accesso Diretto via Browser
Senza installare nulla:
1. Il collega apre Google Chrome (o Edge/Safari).
2. Digita nella barra degli indirizzi: `http://192.168.1.150:3001`
3. Aggiunge la pagina ai preferiti della barra dei segnalibri.

---

## 5. Lavoro da Remoto / Smart Working (Fuori Ufficio)

Se un collaboratore o l'Avvocato deve utilizzare DossierLex da casa o da un portatile in trasferta senza essere fisicamente collegato al Wi-Fi dello studio:

1. **Soluzione Consigliata (Zero Costi, Massima Sicurezza)**: **Tailscale**
   - Si installa Tailscale sul PC Server dello studio e sul portatile del collega.
   - Crea una rete privata virtuale protetta e crittografata end-to-end.
   - Il collega da casa digita l'indirizzo IP sicuro di Tailscale (es. `http://100.x.y.z:3001`) e lavora sulle pratiche dello studio con la stessa fluidità dell'ufficio.
   - **Vantaggio**: Nessun dato esposto su internet pubblico, nessuna apertura di porte sul router dello studio.

---

## 6. Riepilogo File e Strumenti del Progetto

| File | Scopo | Dove va usato |
|---|---|---|
| `launch_dossierlex.pyw` | Launcher con auto-avvio Docker e apertura in Chrome | **Solo sul PC Server** |
| `DossierLex.ico` | Icona ufficiale ad alta risoluzione (Verde e Oro) | PC Server e PC Colleghi |
| `Crea_Collegamento_Desktop.bat` | Crea il collegamento sul Desktop del PC Server | **Solo sul PC Server** |
| `Crea_Collegamento_Colleghi.bat` | Crea il collegamento per le postazioni remote | **Sui PC dei Colleghi** |
| `docker-compose.local.yml` | Configurazione container offline (DB, Backend, Frontend) | **Solo sul PC Server** |
