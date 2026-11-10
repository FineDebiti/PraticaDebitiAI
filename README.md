# DossierLex — Studio Legale Avv. Aurelio Bentivegna
**Piattaforma di Pre-Analisi Documentale, Forense ed Econometrica ex CCII (D.Lgs. 14/2019)**

Ambiente completo con Intelligenza Artificiale Locale (**Qwen 2.5 27B/32B offline via LM Studio**), database centralizzato PostgreSQL 16 con pgvector, pipeline documentale ibrida (PaddleOCR + parser vettoriali deterministici), motore econometrico ex OIC 12 / CNDCEC e redazione automatica del report di preanalisi a doppio canale (cruscotto interattivo a 11 capitoli + report PDF ufficiale di 7 pagine esatte).

---

## 📚 Documentazione Completa & Guide di Riferimento

| Documento | Destinatari e Scopo |
|---|---|
| 📖 [**DOCUMENTAZIONE_UFFICIALE_DOSSIERLEX.md**](DOCUMENTAZIONE_UFFICIALE_DOSSIERLEX.md) | **Manuale Tecnico Completo**: architettura a microservizi, pipeline documentale end-to-end, protocollo forense a 5 step, divieti aritmetici, regole contabilità semplificata vs ordinaria, mappa dei file e manutenzione. |
| 🏢 [**GUIDA_DISTRIBUZIONE_STUDIO_E_COLLEGHI.md**](GUIDA_DISTRIBUZIONE_STUDIO_E_COLLEGHI.md) | **Guida di Rete e Postazioni**: configurazione del PC Server centrale di studio e accesso per i colleghi tramite Wi-Fi (`http://192.168.1.31:3001`) e da remoto via Tailscale VPN (`http://100.80.46.116:3001`). Zero installazioni sui computer dei colleghi. |
| ⚖️ [**REPORT_COLLAUDO_DOSSIERLEX_BENTIVEGNA.md**](REPORT_COLLAUDO_DOSSIERLEX_BENTIVEGNA.md) | **Verbale di Collaudo Operativo**: test sul caso pilota D'Amico Lucrezia, confronto econometrico e verifica del benchmark peritale a 7 pagine. |

---

## 🏗️ Architettura e Stack Tecnologico

* **Frontend**: Next.js 14.2 (App Router) + React 18, Design System *"Institutional Heritage"* (palette Navy / Sand / Crimson).
* **Backend Core**: FastAPI (Python 3.12), SQLAlchemy 2.0, Pydantic v2.
* **Database**: PostgreSQL 16 + estensione `pgvector` (24 tabelle relazionali normalizzate, migrazioni Alembic).
* **Code & Background Tasks**: Redis 7 + Celery 5.4 (concurrency impostata a 1 per preservare le risorse di calcolo locale).
* **Storage Documenti**: Volume Docker persistente protetto con deduplica e hashing SHA-256.
* **Motori OCR Ibridi**: `pdfplumber` deterministico per documenti vettoriali nativi + PaddleOCR v4 / Tesseract per scansioni raster.
* **Motore Neurale Forense**: LM Studio locale con **Qwen 2.5 Instruct (27B/32B)** su porta `1234` a temperatura 0.1/0.2 (100% offline, zero invio dati all'esterno, zero costi a consumo).
* **Motore PDF Ufficiale**: FPDF2 engine con rendering tipografico esatto conforme al benchmark cliente di 7 pagine.

---

## 🚀 Avvio Rapido (Ambiente Server)

### Prerequisiti
* **Docker Desktop** (con Linux Containers abilitati).
* **LM Studio** con modello `Qwen 2.5 27B / 32B Instruct` caricato e server locale avviato su porta `1234`.

### Avvio in 2 comandi
```bash
# 1. Avvia tutti i container microservizi
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d

# 2. Apri il browser su:
# - Frontend Web: http://localhost:3001
# - API Swagger Docs: http://localhost:8000/docs
```

---

## 💻 Accesso dalle Postazioni dei Colleghi

* **In Studio (Rete LAN Wi-Fi / Cavo)**: `http://192.168.1.31:3001`
* **Da Remoto / Smart Working (Tailscale VPN)**: `http://100.80.46.116:3001`

> [!NOTE]
> I computer dei collaboratori e dell'Avvocato **non necessitano di Docker, né di codice sorgente, né di modelli AI**. Operano direttamente via browser web Google Chrome o Edge.

---

## 🔍 Il Flusso di Pre-Analisi ex CCII

1. **Creazione Pratica**: inserimento anagrafica persona fisica o ditta/società con validazione formale di Codice Fiscale e Partita IVA.
2. **Caricamento Documentale**: upload in bulk di cartelle AdER ("Da saldare"), visure camerali, visure catastali, Centrale Rischi Banca d'Italia, contratti di finanziamento/CRIF/CTC, bilanci o situazioni economiche provvisorie, visure PRA ed elenchi veicoli.
3. **Elaborazione & Normalizzazione**: la pipeline estrae automaticamente i dati, riconcilia i carichi AdER (bloccando duplicazioni su *"di cui INPS"* e rottamazioni), seleziona l'ultimo mese della Centrale Rischi, censisce i veicoli e verifica gli accertamenti catastali.
4. **Motore Econometrico Forense**: calcolo automatico di:
   * Valore della Produzione ($A$), Costi ($B$) ed EBITDA/MOL ex OIC 12;
   * Posizione Finanziaria Netta (PFN) Orientamento ESMA 2021;
   * Rapporto PFN / EBITDA e Test Pratico Ministeriale di Risanabilità (D.D. 23 aprile 2026);
   * Soglie dimensionali impresa minore (art. 2 CCII) e segnali d'allarme (art. 3 co. 4 CCII).
5. **Dossier Finale**: visualizzazione immediata a video su 11 capitoli navigabili e download con un clic del **Report Peritale PDF di 7 pagine**.

---

## 🧪 Esecuzione Test Automatizzati di Regressione

La piattaforma dispone di una suite di collaudo automatizzata a presidio della stabilità dei calcoli e della pipeline:

```bash
docker exec praticadebitiai-backend-1 pytest
```
*Tutti i 43 test di regressione (indicatori, AdER parser, catena forense, benchmark PDF, API) sono eseguiti in isolamento transazionale.*
