"""Servizio di Super-Analisi Trasversale del Fascicolo.

Analisi incrociata tra tutti i documenti caricati nella pratica:
- Rilevamento incongruenze e discrepanze tra documenti (es. Bilancio vs Centrale Rischi vs AER)
- Individuazione duplicazioni di debiti e rate (per evitare di gonfiare la massa passiva)
- Segnalazione dati e documenti mancanti
- Valutazione preliminare degli scenari di risanamento ex CCII
- Note strategiche per l'Avv. Aurelio Bentivegna
"""
import time
import json
import logging
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.models import (
    Case, Debtor, RealEstate, Vehicle, Company,
    CreditReportSummary, CreditExposure, GuaranteeGiven,
    TaxDebtStatement, DebtPosition, Document, Extraction,
    CaseCrossAnalysis,
)
from app.services.rule_engine import build_active_rules_prompt_block
from app.services.llm_providers import REGISTRY
from app.config import settings

logger = logging.getLogger("dossierlex.cross_analysis")
LOCAL_PROVIDERS = {"lmstudio"}


class IncongruenzaItem(BaseModel):
    descrizione: str = Field(..., min_length=1)
    gravita: str = "SOSTANZIALE"
    documenti_coinvolti: str = ""
    azione_consigliata: str = ""


class DuplicazioneItem(BaseModel):
    partita: str = Field(..., min_length=1)
    importo: Any = None
    documenti_coinvolti: str = ""
    calcolo_consigliato: str = ""
    motivazione: str = ""


class DatoMancanteItem(BaseModel):
    dato_mancante: str = Field(..., min_length=1)
    perche_serve: str = ""
    priorita: str = "MEDIA"


class ScenarioItem(BaseModel):
    scenario: str = Field(..., min_length=1)
    fattibilita: str = "NON VALUTABILE"
    motivazione: str = ""
    dati_chiave: str = ""


class CrossAnalysisOutputSchema(BaseModel):
    incongruenze: List[IncongruenzaItem] = Field(default_factory=list)
    duplicazioni: List[DuplicazioneItem] = Field(default_factory=list)
    dati_mancanti: List[DatoMancanteItem] = Field(default_factory=list)
    scenari: List[ScenarioItem] = Field(default_factory=list)
    richieste_prioritarie: List[Any] = Field(default_factory=list)
    note_per_il_titolare: List[str] = Field(default_factory=list)


def assemble_case_dossier(db: Session, case_id: str) -> dict:
    """Consolida tutti i dati strutturati e i metadati documentali della pratica."""
    case = db.get(Case, case_id)
    if not case:
        return {}

    debtor = db.query(Debtor).filter_by(case_id=case_id).first()
    real_estates = db.query(RealEstate).filter_by(case_id=case_id).all()
    vehicles = db.query(Vehicle).filter_by(case_id=case_id).all()
    companies = db.query(Company).filter_by(case_id=case_id).all()
    cr = db.query(CreditReportSummary).filter_by(case_id=case_id).order_by(CreditReportSummary.id.desc()).first()
    exposures = db.query(CreditExposure).filter_by(case_id=case_id).all()
    guarantees = db.query(GuaranteeGiven).filter_by(case_id=case_id).all()
    statements = db.query(TaxDebtStatement).filter_by(case_id=case_id).all()
    debt_positions = db.query(DebtPosition).filter_by(case_id=case_id).all()
    docs = db.query(Document).filter_by(case_id=case_id).all()

    # Raccoglie i bilanci depositati o situazioni contabili
    financial_data = []
    for comp in companies:
        for fs in sorted(comp.financial_statements, key=lambda x: x.fiscal_year_end, reverse=True):
            financial_data.append({
                "azienda": comp.name,
                "anno": fs.fiscal_year_end,
                "tipo": fs.statement_type,
                "ricavi": fs.revenues,
                "utile_netto": fs.net_result,
                "patrimonio_netto": fs.equity,
                "totale_attivo": fs.total_assets,
                "debiti_totali": fs.total_debts,
                "debiti_tributari_previdenziali": fs.privileged_debts,
            })

    # Elenco documenti e campioni di testo (head + tail) con metriche reali di copertura OCR/troncamento
    doc_list = []
    docs_no_ext = []
    docs_error = []
    docs_unreadable = []
    docs_truncated = []
    max_doc_chars = 6000
    for d in docs:
        ext = db.query(Extraction).filter_by(document_id=d.id).first()
        full_txt = (ext.raw_text or "") if ext else ""
        ocr_meta = (ext.json_output or {}).get("_ocr_meta", {}) if (ext and isinstance(ext.json_output, dict)) else {}
        unreadable_pgs = int(ocr_meta.get("unreadable_pages") or 0)
        is_trunc = len(full_txt) > max_doc_chars
        if ext is None or not full_txt.strip():
            docs_no_ext.append(d.original_filename)
        if getattr(d, "status", "") == "errore":
            docs_error.append(d.original_filename)
        if unreadable_pgs > 0:
            docs_unreadable.append(f"{d.original_filename} ({unreadable_pgs} pagg. illeggibili)")
        if is_trunc:
            docs_truncated.append(f"{d.original_filename} ({len(full_txt)} caratteri)")
        excerpt = (
            full_txt
            if not is_trunc
            else (full_txt[:3600] + "\n...[SEGMENTO CENTRALE OMESSO PER CONTESTO]...\n" + full_txt[-2400:])
        )
        doc_list.append({
            "document_id": str(d.id),
            "nome_file": d.original_filename,
            "tipo": d.doc_type,
            "stato": getattr(d, "status", ""),
            "pagine": d.num_pages,
            "ocr_meta": ocr_meta,
            "lunghezza_totale_caratteri": len(full_txt),
            "testo_troncato": is_trunc,
            "estratto_testo": excerpt,
        })

    all_aer_items = [i for s in statements for i in (s.items or [])]
    max_aer_sample = 100
    aer_truncated = len(all_aer_items) > max_aer_sample
    coverage_warnings = []
    if docs_no_ext:
        coverage_warnings.append(f"Documenti privi di testo estratto ({len(docs_no_ext)}): {', '.join(docs_no_ext[:5])}")
    if docs_error:
        coverage_warnings.append(f"Documenti con errore di pipeline ({len(docs_error)}): {', '.join(docs_error[:5])}")
    if docs_unreadable:
        coverage_warnings.append(f"Documenti con pagine OCR illeggibili ({len(docs_unreadable)}): {', '.join(docs_unreadable[:5])}")
    if docs_truncated:
        coverage_warnings.append(f"Documenti campionati parzialmente nel contesto ({len(docs_truncated)}): {', '.join(docs_truncated[:5])}")
    if aer_truncated:
        coverage_warnings.append(f"Cartelle AdER campionate a {max_aer_sample} su {len(all_aer_items)} righe totali (totali calcolati su tutte le cartelle).")

    copertura_analisi = {
        "documenti_totali": len(docs),
        "documenti_senza_estrazione": len(docs_no_ext),
        "documenti_in_errore": len(docs_error),
        "documenti_pagine_illeggibili": len(docs_unreadable),
        "documenti_testo_troncato": len(docs_truncated),
        "cartelle_aer_troncate": aer_truncated,
        "copertura_integrale": len(coverage_warnings) == 0,
        "fonti_non_coperte_integralmente": docs_no_ext + docs_error + docs_unreadable + docs_truncated,
        "avvisi_copertura": coverage_warnings,
    }

    return {
        "pratica": {
            "codice": case.code,
            "cliente": case.client_name,
            "codice_fiscale": case.client_tax_code,
            "stato": case.status,
            "note": case.notes,
        },
        "anagrafica_economica": {
            "presente": debtor is not None,
            "tipo_cliente": debtor.client_type if debtor else None,
            "reddito_netto_mensile": debtor.monthly_net_income if debtor else None,
            "reddito_annuo": debtor.annual_income if debtor else None,
            "spese_mensili": debtor.monthly_expenses if debtor else None,
            "affitto_o_mutuo": debtor.rent_or_mortgage if debtor else None,
            "pignoramenti_in_corso": debtor.has_ongoing_garnishment if debtor else None,
            "cessione_quinto": debtor.has_salary_assignment if debtor else None,
        },
        "immobili": [
            {
                "indirizzo": r.address,
                "dati_catastali": r.cadastral_data,
                "categoria": r.category,
                "rendita_catastale": r.cadastral_income,
                "valore_catastale": r.cadastral_value,
                "valore_commerciale": r.commercial_value,
                "quota": r.ownership_share,
                "prima_casa": r.is_primary_residence,
                "ipoteca": r.has_mortgage,
            }
            for r in real_estates
        ],
        "veicoli": [
            {"modello": v.make_model, "targa": v.plate, "anno": v.year, "valore_stimato": v.estimated_value}
            for v in vehicles
        ],
        "aziende_collegate": [
            {
                "nome": c.name,
                "forma_giuridica": c.legal_form,
                "piva": c.vat,
                "cf": c.tax_code,
                "stato": c.status,
                "capitale": c.capital,
                "soci": [{"nome": m.name, "quota_pct": m.quota_percent, "legale_rappr": m.is_legal_rep} for m in c.members],
            }
            for c in companies
        ],
        "centrale_rischi": {
            "presente": cr is not None,
            "esposizione_totale": cr.total_exposure if cr else None,
            "garanzie_totali": cr.total_guarantees if cr else None,
            "intermediari_segnalanti": cr.num_intermediaries if cr else None,
            "sofferenze": cr.has_sofferenze if cr else None,
            "dettaglio_banche": [
                {"banca": e.intermediary, "categoria": e.category, "accordato": e.accordato, "utilizzato": e.utilizzato}
                for e in exposures
            ],
            "garanzie_prestate": [
                {"banca": g.intermediary, "soggetto_garantito": g.guaranteed_subject, "importo": g.valore_garanzia}
                for g in guarantees
            ],
        },
        "bilanci_e_contabilita": financial_data,
        "estratto_ruolo_aer": {
            "presente": bool(statements),
            "totale_residuo": sum(s.total_residuo for s in statements) if statements else None,
            "totale_carico": sum(s.total_carico_affidato for s in statements) if statements else None,
            "totale_cartelle": len(all_aer_items),
            "cartelle_troncate": len(all_aer_items) > max_aer_sample,
            "cartelle": [
                {
                    "numero": i.numero_documento,
                    "ente": i.ente_creditore,
                    "notifica": i.data_notifica,
                    "residuo": i.totale_residuo,
                    "rateizzato": i.rateizzato,
                    "proc_attive": i.proc_attive,
                }
                for i in all_aer_items[:max_aer_sample]
            ],
        },
        "posizioni_debitorie_e_rate": [
            {
                "creditore": d.creditor_name,
                "tipo": d.debt_type,
                "importo_originario": d.original_amount,
                "importo_residuo": d.residual_amount,
                "rata_mensile": d.monthly_installment,
            }
            for d in debt_positions
        ],
        "documenti_fascicolo": doc_list,
        "copertura_analisi": copertura_analisi,
    }


def build_cross_analysis_prompt(dossier: dict, rules_block: str = "", multipass_digests: Optional[List[dict]] = None) -> str:
    """Costruisce il prompt di sintesi trasversale per Qwen, integrando regole di studio e stato copertura."""
    dossier_json = json.dumps(dossier, indent=2, ensure_ascii=False)
    digest_block = ""
    if multipass_digests:
        digest_block = (
            "\nSINTESI MULTI-PASSAGGIO DELLE SEZIONI CENTRALI DEI DOCUMENTI LUNGHI:\n"
            + json.dumps(multipass_digests, indent=2, ensure_ascii=False)
            + "\n"
        )
    cov = dossier.get("copertura_analisi") or {}
    cov_rule = ""
    if cov and not cov.get("copertura_integrale", True):
        cov_rule = (
            "\nATTENZIONE COPERTURA PARZIALE: Alcuni documenti non sono stati letti integralmente "
            f"({'; '.join(cov.get('avvisi_copertura') or [])}). "
            "È VIETATO formulare conclusioni di completezza assoluta sull'intero fascicolo: "
            "segnala espressamente queste fonti non coperte integralmente in 'dati_mancanti'.\n"
        )
    return f"""Sei un consulente esperto in diritto della crisi d'impresa e sovraindebitamento (Codice della Crisi d'Impresa e dell'Insolvenza - CCII) che opera a supporto dell'Avv. Aurelio Bentivegna e del team di analisi.

Il tuo compito è condurre una SINTESI TRASVERSALE E RILEVAMENTO CRITICITÀ incrociando TUTTI i dati e documenti del fascicolo del cliente sotto riportato.
{rules_block}{cov_rule}
FASCICOLO CONSOLIDATO DEL CLIENTE:
{dossier_json}
{digest_block}

LINEE GUIDA RIGOROSE:
1. Rileva tutte le INCONGRUENZE dimostrabili: discrepanze o contraddizioni numeriche/temporali tra documenti diversi (es. debiti a bilancio vs Centrale Rischi, debiti contabili vs cartelle AER, incoerenze di date o quote).
2. Rileva tutte le DUPLICAZIONI di debito: partite che compaiono in più documenti (es. cartella esattoriale generale vs prospetto delle rate concordate vs ricevuta singola rata, oppure contratto di finanziamento originario vs debito residuo in Centrale Rischi). Indica la regola di calcolo per evitare che l'avvocato sommi due volte lo stesso debito.
3. Rileva i DATI O DOCUMENTI MANCANTI CRITICI necessari per completare una pre-analisi di crisi accurata (es. bilanci mancanti, visure non aggiornate, estratti conto non reperiti).
4. Valuta gli SCENARI GIURIDICI PRELIMINARI ex CCII (Ristrutturazione dei debiti, Concordato semplificato / transazione fiscale, Liquidazione controllata / liquidazione del patrimonio, Continuità aziendale), indicando fattibilità oggettiva e motivazioni legali/numeriche.
5. Formula NOTE E RACCOMANDAZIONI STRATEGICHE concrete per l'Avv. Bentivegna.

SCHEMA OBBLIGATORIO DI RISPOSTA:
Rispondi ESCLUSIVAMENTE con un oggetto JSON valido privo di testo prima o dopo, conforme a questo schema:
{{
  "incongruenze": [
    {{
      "descrizione": "Spiegazione analitica e chiara della discrepanza riscontrata",
      "gravita": "SOSTANZIALE" o "MINORE",
      "documenti_coinvolti": "Es. Bilancio 2023 vs Centrale Rischi Banca d'Italia",
      "azione_consigliata": "Cosa deve verificare o richiedere l'avvocato"
    }}
  ],
  "duplicazioni": [
    {{
      "partita": "Identificativo o nome del debito / credito",
      "importo": "Importo coinvolto (es. € 37.863,71)",
      "documenti_coinvolti": "Es. Approvazione rate vs Situazione debitoria",
      "calcolo_consigliato": "Regola pratica (es. Non sommare: conteggiare solo il residuo netto dell'estratto di ruolo)",
      "motivazione": "Spiegazione per cui si tratta della stessa partita"
    }}
  ],
  "dati_mancanti": [
    {{
      "dato_mancante": "Nome del documento o dato mancante",
      "perche_serve": "Motivo contabile o giuridico",
      "priorita": "ALTA" o "MEDIA" o "BASSA"
    }}
  ],
  "scenari": [
    {{
      "scenario": "Nome dello scenario ex CCII",
      "fattibilita": "ALTA" o "MEDIA" o "BASSA" o "NON VALUTABILE",
      "motivazione": "Analisi motivata in base a reddito, patrimonio e passivo rilevati",
      "dati_chiave": "Elementi numerici determinanti"
    }}
  ],
  "note_per_il_titolare": [
    "Osservazione strategica o suggerimento operativo per l'Avv. Bentivegna"
  ]
}}
"""


def _resolve_cross_provider():
    """Seleziona il provider rispettando la guardia privacy locale (no invii cloud impliciti)."""
    req_name = settings.llm_provider or "lmstudio"
    if req_name in LOCAL_PROVIDERS and not getattr(settings, "allow_cloud_llm_fallback", False):
        prov = REGISTRY.get("lmstudio")
        return prov, False
    prov = REGISTRY.get(req_name)
    if prov and prov.available():
        return prov, False
    if getattr(settings, "allow_cloud_llm_fallback", False):
        for fb in ("lmstudio", "gemini", "claude", "openai"):
            p = REGISTRY.get(fb)
            if p and p.available():
                return p, True
    return REGISTRY.get("lmstudio"), False


def _run_multipass_doc_digests(db: Session, dossier: dict, prov, target_model: str) -> tuple[list[dict], int]:
    """Per documenti con oltre 12.000 caratteri, estrae un digest della parte centrale in un passaggio dedicato."""
    digests = []
    extra_calls = 0
    for dinfo in (dossier.get("documenti_fascicolo") or []):
        if int(dinfo.get("lunghezza_totale_caratteri") or 0) <= 12000 or not dinfo.get("document_id"):
            continue
        ext = db.query(Extraction).filter_by(document_id=dinfo["document_id"]).first()
        full_txt = (ext.raw_text or "") if ext else ""
        middle = full_txt[3600:-2400].strip()
        if not middle:
            continue
        chunk_prompt = (
            f"Estrai in JSON {{\"fatti_chiave\": [...], \"importi_rilevanti\": [...]}} "
            f"solo i fatti numerici e giuridici essenziali dalla sezione intermedia del documento "
            f"'{dinfo.get('nome_file')}':\n{middle[:12000]}"
        )
        r_mid = prov.extract(file_path=None, mime="text/plain", prompt=chunk_prompt, model=target_model)
        extra_calls += 1
        if r_mid.ok and isinstance(r_mid.data, dict):
            digests.append({
                "nome_file": dinfo.get("nome_file"),
                "digest_intermedio": r_mid.data,
                "troncato_oltre_12k": len(middle) > 12000,
            })
        if extra_calls >= 3:
            break
    return digests, extra_calls


def execute_cross_analysis(db: Session, case_id: str) -> CaseCrossAnalysis:
    """Esegue la sintesi trasversale su Qwen locale, valida lo schema JSON e salva la telemetria."""
    t0 = time.time()
    dossier = assemble_case_dossier(db, case_id)
    rules_block = build_active_rules_prompt_block(db, case_id=case_id)

    prov, fallback_used = _resolve_cross_provider()
    if not prov:
        raise RuntimeError("Nessun provider LLM disponibile per l'analisi trasversale.")

    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"
    multipass_digests, pass_extra = _run_multipass_doc_digests(db, dossier, prov, target_model)
    prompt = build_cross_analysis_prompt(dossier, rules_block=rules_block, multipass_digests=multipass_digests)

    logger.info("Avvio Super-Analisi Trasversale per caso %s su provider=%s modello=%s", case_id, prov.name, target_model)

    res = prov.extract(file_path=None, mime="text/plain", prompt=prompt, model=target_model)
    duration = round(time.time() - t0, 2)
    cov = dossier.get("copertura_analisi") or {}
    telemetry = {
        "provider": res.provider or prov.name,
        "model": res.model or target_model,
        "usage": res.usage or {},
        "duration_s": duration,
        "retries": getattr(res, "retries", 0) or 0,
        "error": res.error,
        "fallback_used": bool(fallback_used or getattr(res, "fallback_used", False)),
        "validation_status": getattr(res, "validation_status", "valid" if res.ok else "provider_error"),
        "prompt_chars": len(prompt),
        "multi_pass": pass_extra > 0,
        "passes_executed": 1 + pass_extra,
        "copertura_integrale": bool(cov.get("copertura_integrale", True)),
        "avvisi_copertura": cov.get("avvisi_copertura") or [],
    }

    if not res.ok:
        logger.error("Super-Analisi fallita per caso %s: %s", case_id, res.error)
        rec = CaseCrossAnalysis(
            case_id=case_id,
            status="error",
            note_per_il_titolare=[f"Errore durante l'elaborazione del modello: {res.error}"],
            raw_response={"error": res.error, "_telemetry": telemetry},
            duration_s=duration,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    raw_data = dict(res.data or {})
    try:
        validated = CrossAnalysisOutputSchema.model_validate(raw_data)
        data = validated.model_dump()
        telemetry["validation_status"] = "valid"
    except ValidationError as exc:
        logger.warning("Validazione Pydantic Super-Analisi fallita per caso %s: %s", case_id, exc)
        telemetry["validation_status"] = "validation_error"
        telemetry["error"] = str(exc)
        rec = CaseCrossAnalysis(
            case_id=case_id,
            status="validation_error",
            dati_mancanti=[
                {
                    "dato_mancante": "Output Qwen non conforme allo schema JSON atteso",
                    "perche_serve": str(exc)[:300],
                    "priorita": "ALTA",
                }
            ],
            note_per_il_titolare=["Output del modello scartato dalla validazione schema Pydantic."],
            raw_response={"_raw_invalid": raw_data, "_validation_error": str(exc), "_telemetry": telemetry},
            duration_s=duration,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    # Se la copertura del fascicolo non è integrale, garantisci segnalazione esplicita nei dati mancanti
    if not cov.get("copertura_integrale", True):
        existing_labels = {str(x.get("dato_mancante", "")).lower() for x in data["dati_mancanti"]}
        for w in (cov.get("avvisi_copertura") or []):
            if w.lower() not in existing_labels:
                data["dati_mancanti"].append({
                    "dato_mancante": f"Copertura parziale fonte: {w}",
                    "perche_serve": "Il modello non può formulare conclusioni definitive sull'intero fascicolo su fonti parziali o illeggibili.",
                    "priorita": "ALTA",
                })

    data["_telemetry"] = telemetry
    data["_copertura_analisi"] = cov
    rec = CaseCrossAnalysis(
        case_id=case_id,
        status="completed",
        incongruenze=data.get("incongruenze") or [],
        duplicazioni=data.get("duplicazioni") or [],
        dati_mancanti=data.get("dati_mancanti") or [],
        scenari=data.get("scenari") or [],
        richieste_prioritarie=data.get("richieste_prioritarie") or [],
        note_per_il_titolare=data.get("note_per_il_titolare") or [],
        raw_response=data,
        duration_s=duration,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    logger.info("Super-Analisi completata con successo in %s s per caso %s", duration, case_id)
    return rec

