"""Gate 0 metodologico: inventario fonti, deduplica SHA-256 e checklist P0/P1/P2.

Adatta dinamicamente le richieste documentali a:
- forma giuridica / protocollo effettivo (A vs B vs profili esclusi/incerti)
- regime contabile effettivo (ordinaria vs semplificata vs altro_regime vs non_documentato)

Distingue rigorosamente tre livelli per ogni requisito documentale:
1. document_acquired (documento acquisito al fascicolo)
2. document_processed_verified (documento effettivamente elaborato/normalizzato e verificato)
3. content_sufficient (contenuto documentale sufficiente per eseguire il controllo richiesto)

Garantisce la separazione netta tra:
- dati verificati da fonti
- dati non disponibili
- anomalie Gate 0
- decisioni sospese
e distingue DIAGNOSI_PRELIMINARE_DELIMITATA vs PREANALISI_SU_FASCICOLO_CONFERMATO.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.entities import Case, Company, CreditReportSummary, Document, FinancialStatement, TaxDebtStatement
from app.services.protocols.classifier import (
    ClassificationResult,
    _is_interim_fs,
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


def _doc_types_by_stage(docs: list[Document]) -> tuple[set[str], set[str], set[str], set[str]]:
    """Restituisce (acquired_types, ready_types, pending_types, error_types)."""
    acquired: set[str] = set()
    ready: set[str] = set()
    pending: set[str] = set()
    errors: set[str] = set()
    for doc in docs:
        dt = (doc.doc_type or "altro").strip().lower()
        st = (doc.status or "").strip().lower()
        acquired.add(dt)
        if st in ("elaborato", "normalizzato"):
            ready.add(dt)
        elif st == "errore":
            errors.add(dt)
        else:
            pending.add(dt)
    return acquired, ready, pending, errors


def _make_item(
    *,
    code: str,
    priority: str,
    title: str,
    note: str,
    document_acquired: bool,
    document_processed_verified: bool,
    content_sufficient: bool,
    missing_details: Optional[list[str]] = None,
) -> dict[str, Any]:
    details = list(missing_details or [])
    if document_acquired and document_processed_verified and content_sufficient:
        stage = "sufficiente"
        status = "presente"
    elif document_acquired and document_processed_verified:
        stage = "elaborato_verificato"
        status = "parziale"
    elif document_acquired:
        stage = "acquisito"
        status = "in_elaborazione"
    else:
        stage = "mancante"
        status = "mancante"

    return {
        "code": code,
        "priority": priority,
        "title": title,
        "status": status,
        "document_acquired": document_acquired,
        "document_processed_verified": document_processed_verified,
        "content_sufficient": content_sufficient,
        "verification_stage": stage,
        "missing_details": details,
        "note": note,
    }


def _count_ready_docs(docs: list[Document], doc_types: tuple[str, ...]) -> list[Document]:
    return [
        d for d in docs
        if (d.doc_type or "").strip().lower() in doc_types
        and (d.status or "").strip().lower() in ("elaborato", "normalizzato")
    ]


def _extract_tax_return_years(docs: list[Document]) -> set[str]:
    years: set[str] = set()
    for d in _count_ready_docs(docs, ("dichiarazione_redditi", "modello_redditi")):
        ext = getattr(d, "extraction", None)
        blob = f"{d.original_filename or ''} {(ext.raw_text[:2000] if ext and ext.raw_text else '')}"
        found = re.findall(r"\b(20\d{2})\b", blob)
        if found:
            years.add(max(found))
        else:
            years.add(d.id)
    return years


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
    acquired_types, ready_types, pending_types, _ = _doc_types_by_stage(docs)

    annual_fs_complete = [
        fs for fs in statements
        if not _is_interim_fs(fs)
        and fs.total_assets is not None
        and fs.revenues is not None
        and fs.total_debts is not None
    ]
    distinct_complete_fs_years = {
        str(fs.fiscal_year_end or fs.id)[:4]
        for fs in annual_fs_complete
    }

    # Evidenze fiscali / AdER
    aer_acq = bool(tax_statements) or any(t in acquired_types for t in ("cartella_esattoriale", "ruoli_ader"))
    aer_proc = (
        (bool(tax_statements) and all(bool(s.quadrature_ok) for s in tax_statements))
        or (not tax_statements and any(t in ready_types for t in ("cartella_esattoriale", "ruoli_ader")))
    )
    aer_suff = (
        bool(tax_statements)
        and all(bool(s.quadrature_ok) and not bool(s.cf_mismatch) and s.total_residuo is not None for s in tax_statements)
    )
    aer_missing: list[str] = []
    if not aer_acq:
        aer_missing.append("Estratto di ruolo AdER non ancora acquisito.")
    elif not aer_proc:
        aer_missing.append("Estratto AdER non ancora elaborato/verificato (quadratura in attesa).")
    elif not aer_suff:
        aer_missing.append("Dati AdER privi di prospetto normalizzato o con CF discordante.")

    # Evidenze Centrale Rischi / banche
    cr_exposures = list(getattr(case, "credit_exposures", None) or [])
    cr_acq = bool(credit_reports) or ("cr_banca_italia" in acquired_types)
    cr_proc = bool(credit_reports) or ("cr_banca_italia" in ready_types)
    cr_suff = bool(credit_reports) and any(
        bool((c.most_recent_month or "").strip()) or c.total_exposure is not None
        for c in credit_reports
    )
    if not cr_suff and cr_exposures:
        cr_suff = True
    cr_missing: list[str] = []
    if not cr_acq:
        cr_missing.append("Centrale Rischi Banca d'Italia non acquisita.")
    elif not cr_proc:
        cr_missing.append("Centrale Rischi non ancora elaborata.")
    elif not cr_suff:
        cr_missing.append("Contenuto CR privo di riepilogo mensile o esposizioni quantificate.")

    # Visura / anagrafica impresa
    visura_acq = ("visura_camerale" in acquired_types) or any(
        bool((c.legal_form or "").strip() or (c.vat or "").strip() or (c.rea or "").strip())
        for c in client_companies
    )
    visura_proc = ("visura_camerale" in ready_types) or any(
        bool((c.legal_form or "").strip() and ((c.vat or "").strip() or (c.rea or "").strip()))
        for c in client_companies
    )
    has_cf_titolare = bool(
        (case.client_tax_code or "").strip()
        or (case.debtor and (case.debtor.tax_code or "").strip())
        or ("documento_identita" in ready_types)
    )
    has_company_ids = any(
        bool((c.legal_form or "").strip() and ((c.vat or "").strip() or (c.rea or "").strip()))
        for c in client_companies
    )
    visura_suff = has_company_ids and (has_cf_titolare if effective_protocol == "A" else True)
    visura_missing: list[str] = []
    if not has_company_ids:
        visura_missing.append("Mancano forma giuridica e P.IVA/REA verificati da visura camerale.")
    if effective_protocol == "A" and not has_cf_titolare:
        visura_missing.append("Manca codice fiscale verificato del titolare.")

    # Dichiarazioni redditi
    tax_ret_acq = any(t in acquired_types for t in ("dichiarazione_redditi", "modello_redditi"))
    tax_ret_proc = any(t in ready_types for t in ("dichiarazione_redditi", "modello_redditi"))
    tax_ret_years = _extract_tax_return_years(docs)

    # Bilanci
    fs_acq = bool(statements) or ("bilancio" in acquired_types)
    fs_proc = bool(statements) or ("bilancio" in ready_types)

    p0: list[dict[str, Any]] = []
    p1_p2: list[dict[str, Any]] = []

    if effective_protocol == "A":
        p0.extend([
            _make_item(
                code="A-P0-ANAG",
                priority="P0",
                title="Identificazione titolare e visura camerale / iscrizione RI",
                note="Necessari CF titolare, P.IVA/REA e data iscrizione o cessazione attività.",
                document_acquired=visura_acq or bool((case.client_tax_code or "").strip()),
                document_processed_verified=visura_proc,
                content_sufficient=visura_suff,
                missing_details=visura_missing,
            ),
            _make_item(
                code="A-P0-FISC",
                priority="P0",
                title="Estratto di ruolo / AdER / situazione fiscale e previdenziale",
                note="Posizione debiti fiscali, contributivi INPS/INAIL e notifiche.",
                document_acquired=aer_acq,
                document_processed_verified=aer_proc,
                content_sufficient=aer_suff,
                missing_details=aer_missing,
            ),
            _make_item(
                code="A-P0-BANC",
                priority="P0",
                title="Centrale Rischi Banca d'Italia e affidamenti bancari",
                note="CR degli ultimi 12-36 mesi o verifica posizioni affidate/garanzie.",
                document_acquired=cr_acq,
                document_processed_verified=cr_proc,
                content_sufficient=cr_suff,
                missing_details=cr_missing,
            ),
        ])

        if effective_regime == "ordinaria":
            fs_suff = len(distinct_complete_fs_years) >= 3
            fs_missing: list[str] = []
            if not fs_acq:
                fs_missing.append("Nessun bilancio/situazione contabile acquisito.")
            elif not fs_proc:
                fs_missing.append("Bilancio in attesa di elaborazione/normalizzazione.")
            elif not fs_suff:
                fs_missing.append(
                    f"Completi solo {len(distinct_complete_fs_years)}/3 esercizi annuali con SP+CE (attivo, ricavi, debiti)."
                )
            p0.append(_make_item(
                code="A-P0-CONT-ORD",
                priority="P0",
                title="Situazioni contabili / bilanci ultimi 3 anni (SP + CE) e Modello Redditi PF (Quadro RF)",
                note="Regime ordinario documentato: richiesti Stato Patrimoniale, Conto Economico triennali e Quadro RF.",
                document_acquired=fs_acq,
                document_processed_verified=fs_proc,
                content_sufficient=fs_suff,
                missing_details=fs_missing,
            ))
            p1_p2.append(_make_item(
                code="A-P1-ORD",
                priority="P1",
                title="Libro cespiti, estratti conto bancari e partitari clienti/fornitori",
                note="Supporto a verifica attivo realizzo e PFN.",
                document_acquired="estratto_conto" in acquired_types,
                document_processed_verified="estratto_conto" in ready_types,
                content_sufficient="estratto_conto" in ready_types,
            ))
        elif effective_regime == "semplificata":
            sempl_suff = len(tax_ret_years) >= 3
            sempl_missing: list[str] = []
            if not tax_ret_acq:
                sempl_missing.append("Nessun Modello Redditi PF (Quadro RG) acquisito.")
            elif not tax_ret_proc:
                sempl_missing.append("Dichiarazione dei redditi in attesa di elaborazione/estrazione.")
            elif not sempl_suff:
                sempl_missing.append(
                    f"Documentate solo {len(tax_ret_years)}/3 annualità di Modello Redditi PF (Quadro RG); verificare anche IVA/LIPE."
                )
            p0.append(_make_item(
                code="A-P0-CONT-SEMPL",
                priority="P0",
                title="Modello Redditi PF (Quadro RG), dichiarazioni IVA / LIPE ultimi 3 anni",
                note="Regime semplificato: nessun bilancio civilistico/SP richiesto; verifica su 3 annualità RG e IVA.",
                document_acquired=tax_ret_acq,
                document_processed_verified=tax_ret_proc,
                content_sufficient=sempl_suff,
                missing_details=sempl_missing,
            ))
            p1_p2.append(_make_item(
                code="A-P1-SEMPL",
                priority="P1",
                title="Prospetto crediti/debiti commerciali, registri IVA ed estratti conto bancari",
                note="Necessario per ricostruire l'esposizione di cassa e le soglie CCII ove mancanti in Quadro RG.",
                document_acquired="estratto_conto" in acquired_types,
                document_processed_verified="estratto_conto" in ready_types,
                content_sufficient="estratto_conto" in ready_types,
            ))
        elif effective_regime == "altro_regime":
            altro_suff = len(tax_ret_years) >= 3
            p0.append(_make_item(
                code="A-P0-CONT-ALTRO",
                priority="P0",
                title="Modello Redditi PF (Quadro LM/RE) e prospetto incassi/costi ultimi 3 anni",
                note="Regime forfettario/altro: verifica compatibilità margini netti reali.",
                document_acquired=tax_ret_acq,
                document_processed_verified=tax_ret_proc,
                content_sufficient=altro_suff,
                missing_details=[] if altro_suff else [f"Documentate {len(tax_ret_years)}/3 annualità fiscali."],
            ))
        else:
            p0.append(_make_item(
                code="A-P0-REGIME-ND",
                priority="P0",
                title="Documentazione fiscale/contabile minima per accertare il regime (Redditi PF RG/RF/LM o bilancio)",
                note="Regime contabile NON DOCUMENTATO: acquisire dichiarazioni dei redditi o bilanci prima dell'analisi.",
                document_acquired=fs_acq or tax_ret_acq,
                document_processed_verified=fs_proc or tax_ret_proc,
                content_sufficient=False,
                missing_details=["Regime contabile non ancora accertato in modo univoco."],
            ))

        fam_acq = bool(case.real_estates or case.vehicles or "isee" in acquired_types)
        fam_ready = bool(case.real_estates or case.vehicles or "isee" in ready_types)
        p1_p2.extend([
            _make_item(
                code="A-P1-FAM",
                priority="P1",
                title="Spese familiari, stato di famiglia, immobili e veicoli",
                note="Distinzione tra sfera personale/familiare e attivo d'impresa.",
                document_acquired=fam_acq,
                document_processed_verified=fam_ready,
                content_sufficient=fam_ready,
            ),
            _make_item(
                code="A-P2-LEG",
                priority="P2",
                title="Atti giudiziari, pignoramenti, decreti ingiuntivi e fideiussioni prestate",
                note="Ricognizione azioni esecutive e garanzie personali.",
                document_acquired=any(t in acquired_types for t in ("decreto_ingiuntivo", "contratto")),
                document_processed_verified=any(t in ready_types for t in ("decreto_ingiuntivo", "contratto")),
                content_sufficient=any(t in ready_types for t in ("decreto_ingiuntivo", "contratto")),
            ),
        ])

    elif effective_protocol == "B":
        fs_suff = len(distinct_complete_fs_years) >= 3
        fs_missing = []
        if not fs_acq:
            fs_missing.append("Nessun bilancio acquisito.")
        elif not fs_proc:
            fs_missing.append("Bilancio acquisito ma non ancora elaborato/normalizzato.")
        elif not fs_suff:
            fs_missing.append(
                f"Documentati {len(distinct_complete_fs_years)}/3 esercizi annuali chiusi con attivo, ricavi e debiti completi."
            )

        p0.extend([
            _make_item(
                code="B-P0-VIS",
                priority="P0",
                title="Visura camerale ordinaria/storica aggiornata e compagine sociale",
                note="Verifica natura giuridica (S.r.l./S.r.l.s.), organo amministrativo, poteri e sede.",
                document_acquired=visura_acq,
                document_processed_verified=visura_proc,
                content_sufficient=visura_suff,
                missing_details=visura_missing,
            ),
            _make_item(
                code="B-P0-BIL",
                priority="P0",
                title="Bilanci depositati / situazioni contabili ultimi 3 esercizi (SP, CE, Nota Integrativa)",
                note=f"Documentati {len(distinct_complete_fs_years)}/3 esercizi annuali completi per test CCII ed EBITDA CNDCEC.",
                document_acquired=fs_acq,
                document_processed_verified=fs_proc,
                content_sufficient=fs_suff,
                missing_details=fs_missing,
            ),
            _make_item(
                code="B-P0-FISC",
                priority="P0",
                title="Estratto di ruolo AdER / posizione INPS-INAIL / cassetto fiscale",
                note="Debiti erariali, IVA, ritenute e contributi (con verifica soglie allerta).",
                document_acquired=aer_acq,
                document_processed_verified=aer_proc,
                content_sufficient=aer_suff,
                missing_details=aer_missing,
            ),
            _make_item(
                code="B-P0-CR",
                priority="P0",
                title="Centrale Rischi Banca d'Italia e posizioni bancarie/leasing",
                note="Linee accordate, utilizzati, sconfini, sofferenze e garanzie rilasciate.",
                document_acquired=cr_acq,
                document_processed_verified=cr_proc,
                content_sufficient=cr_suff,
                missing_details=cr_missing,
            ),
        ])
        if effective_regime == "non_documentato":
            p0.append(_make_item(
                code="B-P0-REGIME-ND",
                priority="P0",
                title="Evidenza contabile effettiva (bilanci XBRL/situazioni contabili di verifica/Redditi SC)",
                note="Il regime contabile della S.r.l. non risulta ancora documentato da bilanci o situazioni contabili.",
                document_acquired=fs_acq,
                document_processed_verified=fs_proc,
                content_sufficient=fs_suff,
                missing_details=["Mancano evidenze contabili strutturate della società."],
            ))
        p1_p2.extend([
            _make_item(
                code="B-P1-PART",
                priority="P1",
                title="Bilanci di verifica dettagliati, scadenzari clienti/fornitori e cespiti",
                note="Raccordo voci B10a/b/c/d, B12, B13, crediti deteriorati e circolante.",
                document_acquired="estratto_conto" in acquired_types,
                document_processed_verified="estratto_conto" in ready_types,
                content_sufficient="estratto_conto" in ready_types,
            ),
            _make_item(
                code="B-P2-GOV",
                priority="P2",
                title="Contratti di finanziamento/garanzia soci, contenziosi e verbali assembleari",
                note="Verifica finanziamenti postergati ex art. 2467 c.c. e passività potenziali.",
                document_acquired=any(t in acquired_types for t in ("decreto_ingiuntivo", "contratto")),
                document_processed_verified=any(t in ready_types for t in ("decreto_ingiuntivo", "contratto")),
                content_sufficient=any(t in ready_types for t in ("decreto_ingiuntivo", "contratto")),
            ),
        ])
    else:
        gen_acq = bool(has_cf_titolare or visura_acq or docs)
        gen_proc = bool(has_cf_titolare or visura_proc or bool(ready_types))
        p0.append(_make_item(
            code="GEN-P0-PROF",
            priority="P0",
            title="Conferma qualificazione giuridica e documentazione identificativa di base",
            note=f"Profilo '{effective_profile}' privo di protocollo A/B operativo: richiesta verifica preliminare prima di qualsiasi inquadramento.",
            document_acquired=gen_acq,
            document_processed_verified=gen_proc,
            content_sufficient=False if effective_profile == "forma_incerta" else gen_proc,
            missing_details=["Qualificazione giuridica incerta o profilo fuori perimetro A/B."],
        ))
        p1_p2.append(_make_item(
            code="GEN-P1-DOCS",
            priority="P1",
            title="Documentazione debitoria (AdER, CR/banche) e reddituale/contabile",
            note="Raccolta base in attesa di profilo dedicato.",
            document_acquired=aer_acq or cr_acq or tax_ret_acq or fs_acq,
            document_processed_verified=aer_proc or cr_proc or tax_ret_proc or fs_proc,
            content_sufficient=False,
        ))

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
        if not item["content_sufficient"]:
            detail_str = f" — {'; '.join(item['missing_details'])}" if item["missing_details"] else ""
            dati_non_disponibili.append(
                f"[{item['priority']}] {item['title']} (stato={item['status']}, fase={item['verification_stage']}{detail_str})."
            )
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
    decisioni_sospese.extend(classification.ccii_required_verifications)

    p0_all_sufficient = bool(p0_items) and all(
        item["document_acquired"] and item["document_processed_verified"] and item["content_sufficient"]
        for item in p0_items
    )
    profile_confirmed = bool(case.debtor_profile_confirmed)
    if (
        completeness == "fascicolo_confermato"
        and profile_confirmed
        and eff_protocol in ("A", "B")
        and p0_all_sufficient
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
        if not p0_all_sufficient:
            reasons.append("requisiti P0 non completamente sufficienti (mancanti, in elaborazione o parziali)")
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
