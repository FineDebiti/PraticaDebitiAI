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
3. Cerca la voce **Indirizzo IPv4** sotto la scheda Wi-Fi (ad esempio l'attuale: `192.168.1.31`).
4. L'indirizzo di DossierLex per l'ufficio sarà:
   `http://192.168.1.31:3001`
   *(Mentre da remoto con Tailscale è sempre fisso: `http://100.80.46.116:3001`).*

---

## 4. Guida per le Postazioni degli Operatori / Colleghi

Configurare il computer di un collaboratore richiede **meno di 1 minuto**:

### Postazioni Windows:
Nella cartella `C:\Users\Giuseppe\Desktop\DossierLex` trovi:
- `Crea_Collegamento_Colleghi.bat`
- `DossierLex.ico`

1. Passa questi due file al collega.
2. Il collega fa doppio clic su `Crea_Collegamento_Colleghi.bat`.
3. Inserisce l'indirizzo del server (in studio: `192.168.1.31` | da remoto: `100.80.46.116`).
4. Sul Desktop compare l'icona ufficiale di **DossierLex**.

### Postazioni Apple Mac (Avvocato e utenti macOS):
Per gli utenti Mac è disponibile il pacchetto pronto:
📁 **`Kit_DossierLex_Mac.zip`** (presente in `C:\Users\Giuseppe\Desktop\DossierLex`)

1. Invia all'Avvocato il file `Kit_DossierLex_Mac.zip` (via email, WhatsApp o AirDrop).
2. L'Avvocato fa doppio clic sullo zip per estrarlo e poi clicca su:
   👉 **`Configura_DossierLex_Mac.command`**
3. Viene creata all'istante l'applicazione nativa **`DossierLex.app`** sulla sua Scrivania con l'icona ufficiale di studio.
4. **Funzionalità Smart Auto-Switch (Ufficio / Casa)**:
   - Quando l'Avvocato clicca sull'icona `DossierLex`, l'applicazione verifica da sola se si trova in ufficio sul Wi-Fi (`192.168.1.31:3001`) o a casa con Tailscale (`100.80.46.116:3001`) e apre il browser all'indirizzo corretto senza fargli digitare nulla!

---

## 5. Come garantire che DossierLex sia SEMPRE accessibile (In Studio e da Remoto)

Per consentire all'Avvocato e ai collaboratori di accedere in qualsiasi momento (anche la sera o nei weekend da casa), assicurati che sul tuo PC Server siano attive queste tre condizioni:

1. **Il PC Server non deve andare in sospensione (Standby)**:
   - In Windows 11: apri *Impostazioni ➔ Sistema ➔ Arresto e batteria ➔ Schermo e sospensione*.
   - Imposta la voce: *"Quando è collegato alla rete elettrica, metti il dispositivo in stato di sospensione dopo: MAI"*.
   - *(Lo schermo può spegnersi regolarmente dopo 5 o 10 minuti, l'importante è che il computer e la scheda di rete rimangano attivi).*
2. **Tailscale deve rimanere attivo sul PC Server**:
   - Tailscale si avvia da solo all'accensione di Windows (icona rotonda con cerchietti nella barra delle applicazioni in basso a destra).
   - Il tuo indirizzo IP Tailscale fisso dello studio è: **`100.80.46.116`**.
3. **Tailscale sui dispositivi remoti (Mac / PC di casa)**:
   - Quando l'Avvocato è a casa, Tailscale deve essere connesso sul suo Mac.
   - Entrambi i computer devono far parte della stessa rete Tailscale dello studio.

---

## 6. Riepilogo File e Strumenti del Progetto

| File | Scopo | Dove va usato |
|---|---|---|
| `launch_dossierlex.pyw` | Launcher per PC Server con auto-avvio Docker e apertura in Chrome | **Solo sul PC Server** |
| `Kit_DossierLex_Mac.zip` | Pacchetto completo per Mac con installer e icona | **Da inviare all'Avvocato / Mac** |
| `Configura_DossierLex_Mac.command` | Crea `DossierLex.app` sulla Scrivania del Mac con Auto-Switch Ufficio/Casa | Utenti Mac |
| `Avvia_DossierLex_Mac.command` | Avvio rapido a doppio clic per Mac | Utenti Mac |
| `DossierLex.icns` | Icona vettoriale nativa per macOS | Utenti Mac |
| `Crea_Collegamento_Colleghi.bat` | Crea il collegamento sul Desktop dei PC Windows | Postazioni Windows |
| `DossierLex.ico` | Icona ufficiale per Windows | Postazioni Windows |
| `docker-compose.local.yml` | Configurazione container offline (DB, Backend, Frontend) | **Solo sul PC Server** |

---

## 7. Sincronizzazione Dati e Aggiornamenti dell'Applicativo

### A. Nuove pratiche caricate e documenti (Tempo Reale)
Tutti i dati risiedono nel database PostgreSQL centrale sul PC Server. 
- Quando un operatore, tu o l'Avvocato inserite una nuova pratica, caricate una visura o generate un report, **la modifica è memorizzata istantaneamente nel server centrale**.
- Chiunque apra la pagina (o prema `F5` / ricarica) vede all'istante la pratica aggiornata. Non ci sono conflitti di versioni o dati disallineati.

### B. Aggiornamenti del software (Nuove funzionalità, correzioni, grafica)
Quando sviluppi nuove funzionalità su DossierLex e aggiorni il server:
- **I client (Mac dell'Avvocato e PC dei colleghi) non devono scaricare né reinstallare nulla.**
- Poiché l'interfaccia viene erogata dal server, alla successiva apertura o ricarica della pagina web il browser riceve in automatico l'ultima versione del codice.
- L'esperienza è identica a quella di un servizio web moderno: sempre aggiornato all'ultima versione disponibile senza manutenzione sui dispositivi dei singoli utenti.


