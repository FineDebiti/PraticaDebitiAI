# Ricognizione persistenza (spec persistenza-stabilità, punto 3)

Obiettivo: confermare che OGNI documento estratto e OGNI ricerca banca-dati sia salvato e
richiamabile dentro la pratica, con tracciabilità (case_id + created_at + source + raw).

Data ricognizione: 2026-06-14. Schema gestito da Alembic (rev `e84180f2d37b`).

## Esito tabella per tabella

| Tabella | case_id | created_at | source | raw | Note |
|---|---|---|---|---|---|
| organizations | n/a | ✓ | n/a | n/a | tenant, non dato di pratica |
| cases | n/a | ✓ | n/a | n/a | radice della pratica |
| debtors | ✓ (unique) | (updated_at) | n/a | n/a | anagrafica, creata con la pratica |
| real_estates | ✓ | ✓ **(agg.)** | ✓ **(agg.)** | n/a | source = manuale / Catasto (Openapi) |
| vehicles | ✓ | ✓ **(agg.)** | ✓ **(agg.)** | n/a | source = manuale / PRA (Openapi) |
| companies | ✓ | ✓ **(agg.)** | source_document_id | extra | |
| company_members | FK→companies | (eredita) | n/a | n/a | dettaglio soci |
| financial_statements | ✓ | ✓ | source_document_id | raw_extraction | + provider/crosscheck |
| financial_indicators | FK→statement | (eredita) | n/a | n/a | indici calcolati |
| credit_exposures | ✓ | ✓ **(agg.)** | source_document_id | n/a | Centrale Rischi |
| guarantees_given | ✓ | ✓ **(agg.)** | source_document_id | n/a | Centrale Rischi |
| credit_report_summaries | ✓ | ✓ **(agg.)** | source_document_id | criticita + crosscheck_payload | |
| tax_debt_statements | ✓ | ✓ | source_document_id | raw_extraction | AER |
| tax_debt_items | FK→statement | (eredita) | n/a | n/a | dettaglio cartelle |
| creditors | ✓ | ✓ **(agg.)** | source_document_id | n/a | |
| debt_positions | ✓ | ✓ **(agg.)** | source_document_id + source_page | n/a | |
| documents | ✓ | ✓ | storage_uri + sha256 | (extractions) | file originale persistito (punto 2) |
| extractions | FK→document | ✓ | n/a | json_output | output LLM grezzo |
| enrichment_requests | ✓ | ✓ | source (camerale/catasto/veicoli/**company**) | raw_response | ricerche banca-dati |

**(agg.)** = aggiunto in questa ricognizione.

## Buchi trovati e chiusi

1. **Consultazione Company SINCRONA non persistita (spec §3.3).** `POST /company/fill` (chiamata
   a pagamento) restituiva i dati senza salvarli: risultato volatile fino all'eventuale import.
   → Ora crea un `EnrichmentRequest` con `source="company"`, `status="done"`, `raw_response` =
   risposta grezza. Tracciabile come le richieste async, visibile nell'elenco consultazioni.

2. **`created_at` mancante** su 8 tabelle (companies, credit_exposures, guarantees_given,
   credit_report_summaries, creditors, debt_positions, real_estates, vehicles).
   → Aggiunto (migrazione `e84180f2d37b`, server_default `now()` per le righe esistenti).

3. **`source` (provenienza dato) mancante** su real_estates e vehicles (creabili sia da import
   Openapi sia manualmente). → Aggiunto: `manuale` di default, `Catasto (Openapi)` / `PRA (Openapi)`
   quando importati dalla ricerca patrimoniale.

## Già a posto (nessun intervento)

- File originali: persistiti su volume dedicato con sha256, ri-scaricabili (`GET .../file`) — punto 2.
- `raw_extraction`/`raw_response`/`json_output` conservati su tutti i tipi che li producono.
- `GET /cases/{id}/card` aggrega le entità della scheda (debitore, patrimonio, aziende,
  Centrale Rischi, AER). Le consultazioni banca-dati (EnrichmentRequest, incluse ora le sync
  Company) sono richiamabili via `GET /cases/{id}/openapi/requests`.
- Tabelle di dettaglio (company_members, financial_indicators, tax_debt_items) ereditano la
  datazione dal record padre: scelta deliberata, non un buco.

## Verifica

- Cambi schema applicati via Alembic, **nessun dato perso** (estratto AER preservato attraverso
  3 migrazioni).
- `company/fill` → riga in `enrichment_requests` con raw_response.
- Import immobile/veicolo da Openapi → `source` valorizzato.
