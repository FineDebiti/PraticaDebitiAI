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
from sqlalchemy.orm import Session

from app.models import (
    Case, Debtor, RealEstate, Vehicle, Company,
    CreditReportSummary, CreditExposure, GuaranteeGiven,
    FinancialStatement, TaxDebtStatement, DebtPosition, Document, Extraction,
    CaseCrossAnalysis,
)
from app.services.llm_providers import REGISTRY
from app.services.llm_providers.base import parse_json
from app.config import settings

logger = logging.getLogger("dossierlex.cross_analysis")


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

    # Elenco documenti e campioni di testo
    doc_list = []
    for d in docs:
        ext = db.query(Extraction).filter_by(document_id=d.id).first()
        snippet = (ext.raw_text[:1200] if ext and ext.raw_text else "")
        doc_list.append({
            "nome_file": d.original_filename,
            "tipo": d.doc_type,
            "pagine": d.num_pages,
            "estratto_testo": snippet,
        })

    return {
        "pratica": {
            "codice": case.code,
            "cliente": case.client_name,
            "codice_fiscale": case.client_tax_code,
            "stato": case.status,
            "note": case.notes,
        },
        "anagrafica_economica": {
            "tipo_cliente": debtor.client_type if debtor else "privato",
            "reddito_netto_mensile": debtor.monthly_net_income if debtor else 0,
            "reddito_annuo": debtor.annual_income if debtor else 0,
            "spese_mensili": debtor.monthly_expenses if debtor else 0,
            "affitto_o_mutuo": debtor.rent_or_mortgage if debtor else 0,
            "pignoramenti_in_corso": debtor.has_ongoing_garnishment if debtor else False,
            "cessione_quinto": debtor.has_salary_assignment if debtor else False,
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
            "esposizione_totale": cr.total_exposure if cr else 0,
            "garanzie_totali": cr.total_guarantees if cr else 0,
            "intermediari_segnalanti": cr.num_intermediaries if cr else 0,
            "sofferenze": cr.has_sofferenze if cr else False,
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
            "totale_residuo": sum(s.total_residuo for s in statements),
            "totale_carico": sum(s.total_carico_affidato for s in statements),
            "cartelle": [
                {
                    "numero": i.numero_documento,
                    "ente": i.ente_creditore,
                    "notifica": i.data_notifica,
                    "residuo": i.totale_residuo,
                    "rateizzato": i.rateizzato,
                    "proc_attive": i.proc_attive,
                }
                for s in statements for i in s.items[:25]
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
    }


def build_cross_analysis_prompt(dossier: dict) -> str:
    """Costruisce il prompt di sintesi trasversale per Qwen."""
    dossier_json = json.dumps(dossier, indent=2, ensure_ascii=False)
    return f"""Sei un consulente esperto in diritto della crisi d'impresa e sovraindebitamento (Codice della Crisi d'Impresa e dell'Insolvenza - CCII) che opera a supporto dell'Avv. Aurelio Bentivegna.

Il tuo compito è condurre una SINTESI TRASVERSALE E RILEVAMENTO CRITICITÀ incrociando TUTTI i dati e documenti del fascicolo del cliente sotto riportato.

FASCICOLO CONSOLIDATO DEL CLIENTE:
{dossier_json}

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


def execute_cross_analysis(db: Session, case_id: str) -> CaseCrossAnalysis:
    """Esegue la sintesi trasversale interrogando il modello locale (Qwen su LM Studio) e persiste il risultato."""
    t0 = time.time()
    dossier = assemble_case_dossier(db, case_id)
    prompt = build_cross_analysis_prompt(dossier)

    # Invoca il provider configurato (lmstudio come primario)
    prov = REGISTRY.get(settings.llm_provider) or REGISTRY.get("lmstudio")
    if not prov:
        raise RuntimeError("Nessun provider LLM disponibile per l'analisi trasversale.")

    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"
    logger.info("Avvio Super-Analisi Trasversale per caso %s su provider=%s modello=%s", case_id, prov.name, target_model)

    res = prov.extract(file_path=None, mime="text/plain", prompt=prompt, model=target_model)
    duration = round(time.time() - t0, 2)

    if not res.ok:
        logger.error("Super-Analisi fallita per caso %s: %s", case_id, res.error)
        rec = CaseCrossAnalysis(
            case_id=case_id,
            status="error",
            note_per_il_titolare=[f"Errore durante l'elaborazione del modello: {res.error}"],
            duration_s=duration,
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return rec

    data = res.data or {}
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

