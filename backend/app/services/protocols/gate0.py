"""Gate 0 metodologico: inventario fonti, deduplica SHA-256 e checklist P0/P1/P2.

Adatta dinamicamente le richieste documentali a:
- forma giuridica / protocollo effettivo (A vs B vs profili esclusi/incerti)
- regime contabile effettivo (ordinaria vs semplificata vs altro_regime vs non_documentato)

Garantisce la separazione netta tra:
- dati verificati da fonti
- dati non disponibili
- anomalie Gate 0
- decisioni sospese
e distingue DIAGNOSI_PRELIMINARE_DELIMITATA vs PREANALISI_SU_FASCICOLO_CONFERMATO.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.entities import Case, Company, CreditReportSummary, Document, FinancialStatement, TaxDebtStatement
from app.services.protocols.classifier import (
    ClassificationResult,
    protocol_code_for_profile,
)


@dataclass
class Gate0Result:
    conclusivity_level: str  # DIAGNOSI_PRELIMINARE_DELIMITATA | PREANALISI_SU_FASCICOLO_CONFERMATO
    dossier_completeness_status: str
    effective_legal_form_profile: str
    effective_accounting_regime: str
    effective_protocol_code: Optional[str]
    source_inventory: dict[str, Any]
    duplicate_groups: list[dict[str, Any]]
    documenti_indispensabili_p0: list[dict[str, Any]] = field(default_factory=list)
    documenti_p1_p2: list[dict[str, Any]] = field(default_factory=list)
    dati_verificati_fonti: list[str] = field(default_factory=list)
    dati_non_disponibili: list[str] = field(default_factory=list)
    anomalie_gate0: list[str] = field(default_factory=list)
    decisioni_sospese: list[str] = field(default_factory=list)


def _doc_types_present(docs: list[Document]) -> tuple[set[str], set[str]]:
    """Restituisce (doc_types_pronti, doc_types_in_coda)."""
    ready: set[str] = set()
    pending: set[str] = set()
    for doc in docs:
        dt = (doc.doc_type or "altro").strip().lower()
        st = (doc.status or "").strip().lower()
        if st in ("elaborato", "normalizzato"):
            ready.add(dt)
        elif st in ("caricato", "in_elaborazione"):
            pending.add(dt)
    return ready, pending


def _item_status(
    required_doc_types: tuple[str, ...],
    ready_types: set[str],
    pending_types: set[str],
    extra_satisfied: bool = False,
) -> str:
    if extra_satisfied or any(dt in ready_types for dt in required_doc_types):
        return "presente"
    if any(dt in pending_types for dt in required_doc_types):
        return "in_elaborazione"
    return "mancante"


def _build_checklist(
    effective_profile: str,
    effective_regime: str,
    effective_protocol: Optional[str],
    case: Case,
    statements: list[FinancialStatement],
    docs: list[Document],
    tax_statements: list[TaxDebtStatement],
    credit_reports: list[CreditReportSummary],
    client_companies: list[Company],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ready_types, pending_types = _doc_types_present(docs)
    has_aer = bool(tax_statements) or ("cartella_esattoriale" in ready_types) or ("ruoli_ader" in ready_types)
    has_cr = bool(credit_reports) or ("cr_banca_italia" in ready_types)
    has_visura = ("visura_camerale" in ready_types) or any(
        bool((c.rea or "").strip() or (c.vat or "").strip()) for c in client_companies
    )
    has_id_cf = bool(
        (case.client_tax_code or "").strip()
        or (case.debtor and (case.debtor.tax_code or "").strip())
        or ("documento_identita" in ready_types)
    )
    has_tax_returns = ("dichiarazione_redditi" in ready_types) or ("modello_redditi" in ready_types)
    has_fs = bool(statements) or ("bilancio" in ready_types)

    p0: list[dict[str, Any]] = []
    p1_p2: list[dict[str, Any]] = []

    if effective_protocol == "A":
        # Protocollo A: Impresa individuale / ditta individuale
        p0.extend([
            {
                "code": "A-P0-ANAG",
                "priority": "P0",
                "title": "Identificazione titolare e visura camerale / iscrizione RI",
                "status": "presente" if (has_id_cf and has_visura) else (
                    "in_elaborazione" if "visura_camerale" in pending_types else "mancante"
                ),
                "note": "Necessari CF titolare, P.IVA/REA e data iscrizione o cessazione attività.",
            },
            {
                "code": "A-P0-FISC",
                "priority": "P0",
                "title": "Estratto di ruolo / AdER / situazione fiscale e previdenziale",
                "status": "presente" if has_aer else (
                    "in_elaborazione" if any(t in pending_types for t in ("cartella_esattoriale", "ruoli_ader")) else "mancante"
                ),
                "note": "Posizione debiti fiscali, contributivi INPS/INAIL e notifiche.",
            },
            {
                "code": "A-P0-BANC",
                "priority": "P0",
                "title": "Centrale Rischi Banca d'Italia e affidamenti bancari",
                "status": "presente" if has_cr else (
                    "in_elaborazione" if "cr_banca_italia" in pending_types else "mancante"
                ),
                "note": "CR degli ultimi 12-36 mesi o verifica posizioni affidate/garanzie.",
            },
        ])
        if effective_regime == "ordinaria":
            p0.append({
                "code": "A-P0-CONT-ORD",
                "priority": "P0",
                "title": "Situazioni contabili / bilanci ultimi 3 anni (SP + CE) e Modello Redditi PF (Quadro RF)",
                "status": "presente" if (has_fs or len(statements) >= 1) else _item_status(
                    ("bilancio", "dichiarazione_redditi"), ready_types, pending_types
                ),
                "note": "Regime ordinario documentato: richiesti Stato Patrimoniale, Conto Economico e Quadro RF.",
            })
            p1_p2.append({
                "code": "A-P1-ORD",
                "priority": "P1",
                "title": "Libro cespiti, estratti conto bancari e partitari clienti/fornitori",
                "status": _item_status(("estratto_conto",), ready_types, pending_types),
                "note": "Supporto a verifica attivo realizzo e PFN.",
            })
        elif effective_regime == "semplificata":
            p0.append({
                "code": "A-P0-CONT-SEMPL",
                "priority": "P0",
                "title": "Modello Redditi PF (Quadro RG), dichiarazioni IVA / LIPE ultimi 3 anni",
                "status": "presente" if has_tax_returns else _item_status(
                    ("dichiarazione_redditi", "modello_redditi"), ready_types, pending_types
                ),
                "note": "Regime semplificato: nessun bilancio civilistico/SP richiesto; verifica flussi su Quadro RG e IVA.",
            })
            p1_p2.append({
                "code": "A-P1-SEMPL",
                "priority": "P1",
                "title": "Prospetto crediti/debiti commerciali, registri IVA ed estratti conto bancari",
                "status": _item_status(("estratto_conto",), ready_types, pending_types),
                "note": "Necessario per ricostruire l'esposizione di cassa e le soglie CCII ove mancanti in Quadro RG.",
            })
        elif effective_regime == "altro_regime":
            p0.append({
                "code": "A-P0-CONT-ALTRO",
                "priority": "P0",
                "title": "Modello Redditi PF (Quadro LM/RE) e prospetto incassi/costi ultimi 3 anni",
                "status": "presente" if has_tax_returns else _item_status(
                    ("dichiarazione_redditi", "modello_redditi"), ready_types, pending_types
                ),
                "note": "Regime forfettario/altro: verifica compatibilità margini netti reali.",
            })
        else:
            p0.append({
                "code": "A-P0-REGIME-ND",
                "priority": "P0",
                "title": "Documentazione fiscale/contabile minima per accertare il regime (Redditi PF RG/RF/LM o bilancio)",
                "status": "presente" if (has_fs or has_tax_returns) else "mancante",
                "note": "Regime contabile NON DOCUMENTATO: acquisire dichiarazioni dei redditi o bilanci prima dell'analisi.",
            })
        p1_p2.extend([
            {
                "code": "A-P1-FAM",
                "priority": "P1",
                "title": "Spese familiari, stato di famiglia, immobili e veicoli",
                "status": "presente" if (case.real_estates or case.vehicles or "isee" in ready_types) else "mancante",
                "note": "Distinzione tra sfera personale/familiare e attivo d'impresa.",
            },
            {
                "code": "A-P2-LEG",
                "priority": "P2",
                "title": "Atti giudiziari, pignoramenti, decreti ingiuntivi e fideiussioni prestate",
                "status": _item_status(("decreto_ingiuntivo", "contratto"), ready_types, pending_types),
                "note": "Ricognizione azioni esecutive e garanzie personali.",
            },
        ])

    elif effective_protocol == "B":
        # Protocollo B: Società di capitali (S.r.l. / S.r.l.s.)
        p0.extend([
            {
                "code": "B-P0-VIS",
                "priority": "P0",
                "title": "Visura camerale ordinaria/storica aggiornata e compagine sociale",
                "status": "presente" if has_visura else (
                    "in_elaborazione" if "visura_camerale" in pending_types else "mancante"
                ),
                "note": "Verifica natura giuridica (S.r.l./S.r.l.s.), organo amministrativo, poteri e sede.",
            },
            {
                "code": "B-P0-BIL",
                "priority": "P0",
                "title": "Bilanci depositati / situazioni contabili ultimi 3 esercizi (SP, CE, Nota Integrativa)",
                "status": "presente" if len(statements) >= 3 else (
                    "in_elaborazione" if "bilancio" in pending_types else "mancante"
                ),
                "note": f"Documentati {len(statements)} bilanci/prospetti; per test triennale CCII ed EBITDA CNDCEC occorrono 3 esercizi.",
            },
            {
                "code": "B-P0-FISC",
                "priority": "P0",
                "title": "Estratto di ruolo AdER / posizione INPS-INAIL / cassetto fiscale",
                "status": "presente" if has_aer else (
                    "in_elaborazione" if any(t in pending_types for t in ("cartella_esattoriale", "ruoli_ader")) else "mancante"
                ),
                "note": "Debiti erariali, IVA, ritenute e contributi (con verifica soglie allerta).",
            },
            {
                "code": "B-P0-CR",
                "priority": "P0",
                "title": "Centrale Rischi Banca d'Italia e posizioni bancarie/leasing",
                "status": "presente" if has_cr else (
                    "in_elaborazione" if "cr_banca_italia" in pending_types else "mancante"
                ),
                "note": "Linee accordate, utilizzati, sconfini, sofferenze e garanzie rilasciate.",
            },
        ])
        if effective_regime == "non_documentato":
            p0.append({
                "code": "B-P0-REGIME-ND",
                "priority": "P0",
                "title": "Evidenza contabile effettiva (bilanci XBRL/situazioni contabili di verifica/Redditi SC)",
                "status": "presente" if has_fs else "mancante",
                "note": "Il regime contabile della S.r.l. non risulta ancora documentato da bilanci o situazioni contabili.",
            })
        p1_p2.extend([
            {
                "code": "B-P1-PART",
                "priority": "P1",
                "title": "Bilanci di verifica dettagliati, scadenzari clienti/fornitori e cespiti",
                "status": _item_status(("estratto_conto",), ready_types, pending_types),
                "note": "Raccordo voci B10a/b/c/d, B12, B13, crediti deteriorati e circolante.",
            },
            {
                "code": "B-P2-GOV",
                "priority": "P2",
                "title": "Contratti di finanziamento/garanzia soci, contenziosi e verbali assembleari",
                "status": _item_status(("decreto_ingiuntivo", "contratto"), ready_types, pending_types),
                "note": "Verifica finanziamenti postergati ex art. 2467 c.c. e passività potenziali.",
            },
        ])
    else:
        # Profili esclusi o forma_incerta: nessuna attivazione silente A/B
        p0.append({
            "code": "GEN-P0-PROF",
            "priority": "P0",
            "title": "Conferma qualificazione giuridica e documentazione identificativa di base",
            "status": "mancante" if effective_profile == "forma_incerta" else (
                "presente" if (has_id_cf or has_visura or docs) else "mancante"
            ),
            "note": f"Profilo '{effective_profile}' privo di protocollo A/B operativo: richiesta verifica preliminare prima di qualsiasi inquadramento.",
        })
        p1_p2.append({
            "code": "GEN-P1-DOCS",
            "priority": "P1",
            "title": "Documentazione debitoria (AdER, CR/banche) e reddituale/contabile",
            "status": "presente" if (has_aer or has_cr or has_tax_returns or has_fs) else "mancante",
            "note": "Raccolta base in attesa di profilo dedicato.",
        })

    return p0, p1_p2


def evaluate_gate0(
    case: Case,
    classification: ClassificationResult,
    statements: list[FinancialStatement],
    client_companies: list[Company],
) -> Gate0Result:
    """Esegue Gate 0 deterministico sullo stato reale del fascicolo."""
    docs: list[Document] = list(case.documents or [])
    tax_statements: list[TaxDebtStatement] = list(case.tax_debt_statements or [])
    credit_reports: list[CreditReportSummary] = list(case.cr_summaries or [])

    eff_profile = case.debtor_profile_confirmed or classification.legal_form_profile
    eff_regime = case.accounting_regime_confirmed or classification.accounting_regime
    eff_protocol = protocol_code_for_profile(eff_profile)
    completeness = case.dossier_completeness_status or "in_raccolta"

    # Inventario fonti + deduplica SHA-256
    docs_ready = sum(1 for d in docs if (d.status or "").lower() in ("elaborato", "normalizzato"))
    docs_pending = sum(1 for d in docs if (d.status or "").lower() in ("caricato", "in_elaborazione"))
    docs_error = sum(1 for d in docs if (d.status or "").lower() == "errore")

    by_sha: dict[str, list[Document]] = defaultdict(list)
    for d in docs:
        sha = (d.sha256 or "").strip()
        if sha:
            by_sha[sha].append(d)
    duplicate_groups = [
        {
            "sha256": sha,
            "count": len(group),
            "document_ids": [d.id for d in group],
            "filenames": [d.original_filename for d in group],
        }
        for sha, group in by_sha.items()
        if len(group) > 1
    ]

    source_inventory = {
        "documents_total": len(docs),
        "documents_ready": docs_ready,
        "documents_pending": docs_pending,
        "documents_error": docs_error,
        "financial_statements_count": len(statements),
        "tax_debt_statements_count": len(tax_statements),
        "credit_reports_count": len(credit_reports),
        "companies_client_count": len(client_companies),
        "duplicate_groups_count": len(duplicate_groups),
    }

    p0_items, p1_p2_items = _build_checklist(
        eff_profile,
        eff_regime,
        eff_protocol,
        case,
        statements,
        docs,
        tax_statements,
        credit_reports,
        client_companies,
    )

    # Quattro sezioni obbligatorie Gate 0
    dati_verificati: list[str] = []
    if docs_ready:
        dati_verificati.append(f"{docs_ready}/{len(docs)} documenti acquisiti ed elaborati/normalizzati.")
    if statements:
        years = sorted({str(fs.fiscal_year_end or "n/d") for fs in statements})
        dati_verificati.append(f"{len(statements)} bilanci/prospetti registrati (esercizi: {', '.join(years)}).")
    if tax_statements:
        dati_verificati.append(f"{len(tax_statements)} prospetti debitori AdER registrati.")
    if credit_reports:
        dati_verificati.append(f"{len(credit_reports)} riepiloghi Centrale Rischi Banca d'Italia registrati.")
    dati_verificati.extend(classification.legal_form_evidence)
    dati_verificati.extend(classification.accounting_regime_evidence)
    dati_verificati.extend(classification.ccii_size_evidence)

    dati_non_disponibili: list[str] = []
    for item in p0_items:
        if item["status"] != "presente":
            dati_non_disponibili.append(f"[{item['priority']}] {item['title']} ({item['status']}).")
    if eff_regime == "non_documentato":
        dati_non_disponibili.append("Regime contabile effettivo NON DOCUMENTATO dai documenti/bilanci presenti.")
    if classification.ccii_size_qualification == "non_determinabile":
        dati_non_disponibili.append("Qualificazione dimensionale CCII NON DETERMINABILE sui dati attualmente disponibili.")

    anomalie: list[str] = list(classification.anomalies)
    for dup in duplicate_groups:
        anomalies_names = ", ".join(dup["filenames"])
        anomalie.append(
            f"Documenti duplicati (SHA-256 {dup['sha256'][:12]}...): {dup['count']} file ({anomalies_names})."
        )
    if docs_error:
        anomalie.append(f"{docs_error} documento/i in stato 'errore' di elaborazione/OCR.")
    if docs_pending:
        anomalie.append(f"{docs_pending} documento/i ancora in elaborazione.")

    decisioni_sospese: list[str] = list(classification.suspended_reasons)

    # Livello di conclusività
    p0_all_ready = bool(p0_items) and all(item["status"] == "presente" for item in p0_items)
    profile_confirmed = bool(case.debtor_profile_confirmed)
    if (
        completeness == "fascicolo_confermato"
        and profile_confirmed
        and eff_protocol in ("A", "B")
        and p0_all_ready
        and docs_error == 0
    ):
        conclusivity = "PREANALISI_SU_FASCICOLO_CONFERMATO"
    else:
        conclusivity = "DIAGNOSI_PRELIMINARE_DELIMITATA"
        reasons: list[str] = []
        if completeness != "fascicolo_confermato":
            reasons.append("stato fascicolo='in_raccolta'")
        if not profile_confirmed:
            reasons.append("profilo non ancora confermato dall'operatore")
        if eff_protocol not in ("A", "B"):
            reasons.append(f"profilo '{eff_profile}' senza protocollo A/B operativo")
        if not p0_all_ready:
            reasons.append("documenti indispensabili P0 mancanti o in elaborazione")
        if docs_error > 0:
            reasons.append(f"{docs_error} documenti con errore OCR/estrazione")
        decisioni_sospese.append(
            f"Output delimitato a DIAGNOSI_PRELIMINARE_DELIMITATA ({'; '.join(reasons)})."
        )

    return Gate0Result(
        conclusivity_level=conclusivity,
        dossier_completeness_status=completeness,
        effective_legal_form_profile=eff_profile,
        effective_accounting_regime=eff_regime,
        effective_protocol_code=eff_protocol,
        source_inventory=source_inventory,
        duplicate_groups=duplicate_groups,
        documenti_indispensabili_p0=p0_items,
        documenti_p1_p2=p1_p2_items,
        dati_verificati_fonti=dati_verificati,
        dati_non_disponibili=dati_non_disponibili,
        anomalie_gate0=anomalie,
        decisioni_sospese=decisioni_sospese,
    )
