# Audit Tecnico del Codice, Matrice di Gap (Moduli A–E / P0–P3) e Piano di Evoluzione DossierLex

**Data Audit:** 12 Novembre 2026  
**Repository:** `FineDebiti/PraticaDebitiAI` — Confronto tra branch `master` (campionato dall'audit esterno) e branch attivo di produzione `DossierLex_1`  
**Caso di Riferimento / Regressione:** *Più D'Amico Lucrezia (Ditta individuale artigiana · Palermo)*

---

## 1. Chiarimento Preliminare sulle Due Questioni Chiave del Confronto

### 1.1 Perché l'ispezione GitHub esterna non aveva rilevato l'integrazione Qwen
L'ispezione esterna ha campionato il branch predefinito `master` (fermo al commit iniziale `e6927a8`), mentre l'istanza operativa di DossierLex gira sul branch **`DossierLex_1`**, dove l'integrazione con **Qwen 3.8 27B (via LM Studio)** è già presente e attiva in:
- `backend/app/config.py` (`lmstudio_base_url`, `lmstudio_model = "qwen/qwen3.8-27b"`, `llm_fallback_chain = "lmstudio,gemini,claude,openai"`)
- `backend/app/services/llm_providers/lmstudio_provider.py`
- `backend/app/services/forensic_preanalysis_chain.py` (protocollo forense a 5 step + classificazione epistemica `[D][R][C][S][H]`)

### 1.2 La vera causa del refuso sul Raccordo Fiscale Rigo RG5 (`€63.256` / `€237`) a Pagina 2 del PDF
Nel codice sorgente che aveva generato il PDF (`backend/app/services/benchmark_pdf_generator.py`, riga 291), la frase scritta era **già** corretta e negativa:
> `"Il Modello Redditi PF 2026 (anno 2025) riporta €63.256 al rigo RG5 per ricavi non annotati: il reddito fiscale dichiarato di €237 non prova l'esistenza di margini o incassi ulteriori."`

Tuttavia, un difetto di posizionamento orizzontale in `fpdf2` (`pdf.write(3.5, "Raccordo fiscale. ")` seguito da `pdf.multi_cell(pdf.epw - 4, ...)` senza riportare `X` al margine sinistro del box) faceva debordare la prima riga oltre il margine destro del foglio A4 (`210 mm`), **tagliando fisicamente fuori pagina i caratteri `"7 non"`** e mandando a capo sulla riga successiva `"prova l'esistenza di margini o incassi ulteriori"`.
- **Risoluzione implementata:** corretto il layout del box in `benchmark_pdf_generator.py`, rafforzato il testo esplicitando *"Queste somme non sono incassi né fatturato: il commercialista deve spiegarne l'origine"*, e introdotto un test automatico con `pdfplumber` (`test_3_controllo_inferenza_fiscale_rg5_e_integrita_pdf_pagina_2`) + il verificatore deterministico `verify_inferences()` in `forensic_audit_engine.py`.

---

## 2. Deliverable 1 — Matrice di Gap con Evidenze (Moduli A–E e Interventi P0–P3)

| Modulo / Priorità | Stato Pre-Audit (`DossierLex_1`) | Stato Attuale Post-Intervento | File e Funzioni Coinvolte | Test Automatico Dimostrativo |
| :--- | :--- | :--- | :--- | :--- |
| **P0.1 — Verifica branch/deploy Qwen e mappa moduli** | **PRESENTE SU `DossierLex_1`** (assente su `master`) | **PRESENTE E VERIFICATO** | `backend/app/config.py`, `backend/app/services/forensic_preanalysis_chain.py`, `docker-compose.yml` | `tests/test_forensic_preanalysis_chain.py` |
| **P0.2 — Semantica `NULL` vs `Zero` in dati e report** | **PARZIALE** (`indicators.py` calcolava `pfn = 0.0` in assenza di SP e usava euristiche `*0.4` / `*0.3`) | **PRESENTE E VERIFICATO** (assenza SP restituisce `None` / `status="na"`, 0 zeri automatici) | `backend/app/services/indicators.py` (`compute_indicators`), `backend/app/services/forensic_audit_engine.py` | `tests/test_damico_benchmark_audit.py::test_4_semantica_null_vs_zero_in_assenza_stato_patrimoniale` |
| **P0.3 — Quadrature `Decimal`, deduplica debitoria, formule versionate** | **PARZIALE** (calcoli in `float`) | **PRESENTE E VERIFICATO** (aritmetica `decimal.Decimal` `ROUND_HALF_UP`, 8 quadrature `QUAD-01..08`) | `backend/app/services/forensic_audit_engine.py` (`run_deterministic_decimal_audit`) | `tests/test_damico_benchmark_audit.py::test_1_ricostruzione_debito_decimal_senza_duplicazioni` |
| **P0.4 — Tracciabilità su cancellazione documento** | **NON ACCERTABILE** (`delete_document` lasciava record estratti orfani senza log) | **PRESENTE E VERIFICATO** (log in `FieldEdit` con SHA-256 + pulizia record derivati orfani) | `backend/app/api/routes.py` (`delete_document`) | `tests/test_api.py` |
| **Modulo A — Inventario fonti (`DOC-01..10`) e mappa cifre (`EV-01..13`)** | **PARZIALE** (sintesi testuale delle fonti) | **PRESENTE E VERIFICATO** (matrice completa con ID, SHA-256, pagine, OCR, formula e confidenza) | `backend/app/services/forensic_audit_engine.py` (`build_source_matrix`, `build_evidence_trace_map`) | `tests/test_damico_benchmark_audit.py::test_5_coerenza_doppio_elaborato_e_dossier_tecnico_pdf` |
| **Modulo B — Motore matematico deterministico `Decimal`** | **PARZIALE** | **PRESENTE E VERIFICATO** (`FORMULA_SET_VERSION = OIC12-ESMA2021-CCII2026-v2.1`) | `backend/app/services/forensic_audit_engine.py` (`run_deterministic_decimal_audit`) | `tests/test_damico_benchmark_audit.py::test_2_scenari_2026_e_confronto_rata` |
| **Modulo C — Qwen analista + cautela normativa versionata** | **PARZIALE** (citazione D.Lgs. 147/2026 assertiva) | **PRESENTE E VERIFICATO** (clausola di verifica vigenza GU su D.Lgs. 14/2019, D.Lgs. 136/2024 e novelle) | `backend/app/services/benchmark_pdf_generator.py`, `backend/app/services/forensic_preanalysis_chain.py` | `tests/test_forensic_preanalysis_chain.py` |
| **Modulo D / P1 — Blocco inferenze (`RG5`), 13 Anomalie, Revisore Avversariale, Quality Gate** | **PARZIALE** | **PRESENTE E VERIFICATO** (`INF-01..05`, `ANOM-01..13`, `OBIEZ-01..06`, `QG-01..06`) | `backend/app/services/forensic_audit_engine.py` (`verify_inferences`, `build_anomaly_register`, `build_adversarial_review`, `build_quality_gate`) | `tests/test_damico_benchmark_audit.py::test_3_...` & `test_6_blocco_qualitativo_e_human_gate` |
| **Modulo E / P1 — Doppio report sincronizzato (Relazione Cliente + Dossier Tecnico Audit PDF)** | **ASSENTE** (solo Relazione Cliente 7 pagg.) | **PRESENTE E VERIFICATO** (Relazione 7 pagg. + Dossier Tecnico Audit PDF 6–8 pagg. + vista UI dedicata) | `backend/app/services/technical_dossier_pdf_generator.py`, `backend/app/api/client_card.py`, `frontend/app/pratiche/[id]/scheda/scheda-analysis.js` | `tests/test_damico_benchmark_audit.py::test_5_coerenza_doppio_elaborato_e_dossier_tecnico_pdf` |

---

## 3. Deliverable 2 — Backlog Ordinato per Rischio / Valore / Complessità

1. **[COMPLETATO - P0] Correzione taglio tipografico Box Raccordo Fiscale RG5 e Blocco Inferenze (`INF-01..05`)**
   - *Rischio mitigato:* Massimo (impedisce di attribuire valenza di cassa o incasso a componenti fiscali dichiarative ex rigo RG5).
   - *Test:* `test_3_controllo_inferenza_fiscale_rg5_e_integrita_pdf_pagina_2`.
2. **[COMPLETATO - P0] Semantica `NULL` vs `Zero` nel motore indicatori e nei report (`indicators.py`)**
   - *Rischio mitigato:* Alto (elimina falsi positivi come `PFN = € 0,00` in contabilità semplificata priva di Stato Patrimoniale).
   - *Test:* `test_4_semantica_null_vs_zero_in_assenza_stato_patrimoniale`.
3. **[COMPLETATO - P0/P1] Motore Deterministico `Decimal` (`QUAD-01..08`) e Generazione Automatica del Dossier Tecnico di Calcolo e Audit (`technical_dossier_pdf_generator.py`)**
   - *Rischio mitigato:* Alto (colma integralmente il divario di verificabilità e audit rispetto al secondo DOCX di Claude Code).
   - *Test:* `test_1_ricostruzione_debito_decimal_senza_duplicazioni`, `test_2_scenari_2026_e_confronto_rata`, `test_5_coerenza_doppio_elaborato_e_dossier_tecnico_pdf`.
4. **[COMPLETATO - P1] Registro delle 13 Anomalie (`ANOM-01..13`), Revisore Avversariale (`OBIEZ-01..06`) e Quality Gate (`QG-01..06`)**
   - *Rischio mitigato:* Medio-Alto (fornisce al professionista le controargomentazioni alla CNC e blocca usi impropri senza Human Gate).
   - *Test:* `test_6_blocco_qualitativo_e_human_gate`.
5. **[COMPLETATO - P0] Tracciabilità su cancellazione documento (`routes.py`)**
   - *Rischio mitigato:* Medio (impedisce che dati estratti rimangano orfani senza fonte documentale attiva).
6. **[PROSSIMA EVOLUZIONE - P2/P3] Benchmark su nuovi fascicoli anonimizzati e Simulatore Finanziario Dinamico DSCR multi-periodo**
   - *Obiettivo:* Validare la generalizzazione su casi diversi da D'Amico (S.r.l. in contabilità ordinaria, concordato minore, ristrutturazione debiti del consumatore).

---

## 4. Deliverable 3 — Verifica Automatica e Procedura di Rollback

- **Suite di Regressione Eseguita:** `49 passed in 4.93s (100%)` tramite `pytest` nel container `praticadebitiai-backend-1`.
- **Nuovo Endpoint API:** `GET /api/cases/{case_id}/preanalysis-report/dossier-pdf?action=download|inline`
- **Procedura di Rollback:** Tutti gli interventi sono isolati in moduli dedicati (`forensic_audit_engine.py`, `technical_dossier_pdf_generator.py`, `test_damico_benchmark_audit.py`) e versionati su Git (`branch DossierLex_1`), completamente reversibili tramite `git revert HEAD` senza alcun impatto distruttivo sul database PostgreSQL.
