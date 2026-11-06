"""Servizio di Rigenerazione Iterativa del Report di Preanalisi ex CCII.

Consente al legale o all'analista di:
1. Applicare le regole attive dello Studio (Playbook) e i commenti correttivi ai dati del report;
2. Riconciliare i dati anagrafici societari con le visure camerali (REA, Sede, ATECO, soci);
3. Utilizzare l'LLM (LM Studio / Qwen / Gemini) per rielaborare i testi, le diagnosi e le conclusioni;
4. Mantenere versioni storicizzate del report (v1, v2, v3...) per iterazioni successive;
5. Garantire che la vista a video e il PDF esportato siano sempre perfettamente sincronizzati.
"""
import copy
import json
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.models import (
    Case,
    Company,
    CompanyMember,
    Document,
    StudioRule,
    CasePreanalysisReport,
)
from app.services.preanalysis_report import build_preanalysis_report
from app.services.rule_engine import get_active_rules
from app.services.llm_providers import REGISTRY
from app.services.llm_providers.base import parse_json
from app.config import settings

logger = logging.getLogger("dossierlex.report_regenerator")


def _normalize_name_tokens(name: str) -> str:
    """Restituisce i token alfabetici del nome ordinati per individuare scambi nome/cognome."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", (name or "").lower())
    tokens = sorted([t for t in cleaned.split() if t])
    return " ".join(tokens)


def _find_visura_extraction(db: Session, case_id: str) -> Optional[Dict[str, Any]]:
    """Cerca e restituisce l'estrazione strutturata della visura camerale se presente tra i documenti."""
    docs = db.query(Document).filter_by(case_id=case_id).all()
    for d in docs:
        is_visura = (
            "visura" in (d.doc_type or "").lower()
            or "visura" in (d.original_filename or "").lower()
        )
        if is_visura and d.extraction and d.extraction.json_output:
            jo = d.extraction.json_output
            if isinstance(jo, dict) and ("impresa" in jo or jo.get("document_type") == "visura_camerale"):
                return jo
    # Fallback su qualsiasi extraction con impresa e numero_rea
    for d in docs:
        if d.extraction and d.extraction.json_output and isinstance(d.extraction.json_output, dict):
            jo = d.extraction.json_output
            if "impresa" in jo and jo["impresa"].get("numero_rea"):
                return jo
    return None


def _reconcile_company_profile(
    db: Session,
    case_id: str,
    cap2: Dict[str, Any],
    rules: List[StudioRule],
) -> Dict[str, Any]:
    """Riconcilia i dati del Cap. 2 (Anagrafica, REA, Sede, ATECO, Soci) incrociando Visura e Regole."""
    visura = _find_visura_extraction(db, case_id)
    vis_imp = (visura.get("impresa") or {}) if visura else {}
    vis_sec = (visura.get("dati_secondari") or {}) if visura else {}
    vis_soci = (visura.get("soci") or []) if visura else []

    # 1. Riconciliazione Anagrafica (REA, Sede Legale, ATECO)
    rea = vis_imp.get("numero_rea") or vis_sec.get("numero_rea")
    sede = vis_imp.get("sede_legale") or vis_sec.get("sede_legale")
    ateco = (
        vis_sec.get("classificazione_ateco")
        or vis_imp.get("classificazione_ateco")
        or vis_sec.get("codice_ateco")
    )
    costituzione = vis_imp.get("data_costituzione") or vis_sec.get("data_costituzione")
    capitale = vis_imp.get("capitale_conferimenti") or vis_imp.get("capitale_sociale")

    # Aggiorna anche la riga Company nel DB per coerenza persistente
    company = db.query(Company).filter_by(case_id=case_id).first()

    # Rilevamento Impresa Individuale e verifica regola Divieto Capitale Sociale
    cap2_fg = (cap2.get("forma_giuridica") or "").lower()
    comp_lf = ((company.legal_form or "") if company else "").lower()
    is_individual = (
        bool(cap2.get("is_ditta_individuale"))
        or any(k in cap2_fg for k in ("individuale", "ditta"))
        or any(k in comp_lf for k in ("individuale", "ditta"))
    )
    has_cap_ban = any("capitale" in (r.rule_title or "").lower() or "ditta" in (r.rule_title or "").lower() for r in rules)

    if is_individual or has_cap_ban:
        cap2["capitale_sociale"] = None
        cap2["capitale_sociale_display"] = "Non applicabile (Impresa individuale: priva di capitale sociale ex lege)"
        if company:
            company.capital = 0.0
            db.add(company)
    elif capitale and (not cap2.get("capitale_sociale") or cap2.get("capitale_sociale") in (0, 0.0, "—")):
        try:
            cap2["capitale_sociale"] = float(capitale)
        except Exception:
            pass

    # Se non c'erano in cap2 o erano '—', valorizziamo dalla visura
    if rea and (not cap2.get("rea") or cap2.get("rea") == "—"):
        if company and company.cciaa and not str(rea).upper().startswith(company.cciaa.upper()[:2]):
            prov_sigla = "PA" if "palermo" in company.cciaa.lower() else (company.cciaa[:2].upper() if len(company.cciaa) == 2 else company.cciaa)
            cap2["rea"] = f"{prov_sigla} - {rea}"
        else:
            cap2["rea"] = rea
    if sede and (not cap2.get("sede_legale") or cap2.get("sede_legale") == "—"):
        cap2["sede_legale"] = sede
    if ateco and (not cap2.get("codice_ateco") or cap2.get("codice_ateco") == "—"):
        cap2["codice_ateco"] = ateco
    if costituzione and (not cap2.get("data_costituzione") or cap2.get("data_costituzione") == "—"):
        cap2["data_costituzione"] = str(costituzione)

    if company:
        if rea and (not company.rea or company.rea.strip() == ""):
            company.rea = rea
        if sede and (not company.legal_address or company.legal_address.strip() == ""):
            company.legal_address = sede
        if ateco and (not company.ateco or company.ateco.strip() == ""):
            company.ateco = ateco
        if costituzione and not company.constitution_date:
            company.constitution_date = str(costituzione)
        if capitale and not company.capital and not (is_individual or has_cap_ban):
            try:
                company.capital = float(capitale)
            except Exception:
                pass
        db.add(company)

    # 2. Riconciliazione e Deduplicazione Soci e Cariche
    soci_raw = cap2.get("soci") or []
    unified_soci: List[Dict[str, Any]] = []

    def _find_matching_socio(nome: str, cf: Optional[str]) -> Optional[Dict[str, Any]]:
        norm_n = _normalize_name_tokens(nome)
        for s in unified_soci:
            s_norm = _normalize_name_tokens(s["nome"])
            s_cf = s.get("codice_fiscale")
            if cf and s_cf and cf == s_cf:
                return s
            if norm_n and s_norm and norm_n == s_norm:
                return s
        return None

    for s in soci_raw:
        nome = (s.get("nome") or "").strip()
        cf = (s.get("codice_fiscale") or s.get("cf") or "").strip().upper()
        if not nome and not cf:
            continue

        q_val = s.get("quota_pct") or s.get("quota") or s.get("quota_percentuale")
        try:
            quota = float(q_val) if q_val not in (None, "—", "") else None
        except Exception:
            quota = None

        ruolo = (s.get("ruolo") or s.get("carica") or "Socio").strip()
        garante = s.get("garante", False) or "fideiussore" in ruolo.lower()

        existing = _find_matching_socio(nome, cf)
        if not existing:
            unified_soci.append({
                "nome": nome.upper(),
                "codice_fiscale": cf if cf and cf != "—" else None,
                "quota_pct": quota,
                "ruolo": ruolo,
                "garante": garante,
            })
        else:
            # Unifica soggetto duplicato (es. GUIDO FAZIO e FAZIO GUIDO)
            if not existing.get("codice_fiscale") and cf and cf != "—":
                existing["codice_fiscale"] = cf
            # Unisci i ruoli
            existing_roles = [r.strip().lower() for r in existing["ruolo"].split(",")]
            new_roles = [r.strip() for r in ruolo.split(",") if r.strip().lower() not in existing_roles]
            if new_roles:
                existing["ruolo"] = f"{existing['ruolo']}, {', '.join(new_roles)}"
            # Quota
            if quota is not None:
                if existing["quota_pct"] is None or quota > existing["quota_pct"]:
                    existing["quota_pct"] = quota
            if garante:
                existing["garante"] = True

    # Se abbiamo la visura ufficiale dei soci, integra o sovrascrivi con i dati ufficiali
    if vis_soci:
        for vs in vis_soci:
            v_nome = (vs.get("denominazione") or vs.get("nome") or "").strip()
            v_cf = (vs.get("codice_fiscale") or "").strip().upper()
            v_quota = vs.get("quota_percentuale")
            try:
                v_quota = float(v_quota) if v_quota is not None else None
            except Exception:
                v_quota = None

            cariche = vs.get("cariche")
            if isinstance(cariche, list):
                v_ruolo = ", ".join(cariche)
            else:
                v_ruolo = str(cariche or "socio")

            match = _find_matching_socio(v_nome, v_cf)
            if match:
                match["nome"] = v_nome.upper()
                if v_cf:
                    match["codice_fiscale"] = v_cf
                if v_quota is not None:
                    match["quota_pct"] = v_quota
                if v_ruolo:
                    match["ruolo"] = v_ruolo
            else:
                unified_soci.append({
                    "nome": v_nome.upper(),
                    "codice_fiscale": v_cf or None,
                    "quota_pct": v_quota,
                    "ruolo": v_ruolo,
                    "garante": vs.get("e_cliente", False),
                })

    # Controllo matematico percentuali: la somma non può mai eccedere il 100%
    # Se la visura camerale indica un socio unico al 100%, rimuovi o azzera quote spurie
    vis_100_socio = next((vs for vs in vis_soci if (vs.get("quota_percentuale") or 0.0) >= 100.0), None)
    if vis_100_socio:
        v_cf = (vis_100_socio.get("codice_fiscale") or "").strip().upper()
        v_name = (vis_100_socio.get("denominazione") or "").strip()
        official_match = _find_matching_socio(v_name, v_cf)
        if official_match:
            official_match["quota_pct"] = 100.0
            # Solo i soci ufficialmente in visura rimangono attivi
            filtered_soci = [official_match]
            for s in unified_soci:
                if s is not official_match and not any(_normalize_name_tokens(s["nome"]) == _normalize_name_tokens(vs.get("denominazione") or "") for vs in vis_soci):
                    # Se non è in visura ma era nel DB, segnalalo solo con quota None
                    s["quota_pct"] = None
                    s["ruolo"] = f"{s['ruolo']} (non presente in visura attuale)"
                    # se era solo un residuo non rilevante possiamo escluderlo per pulizia
            unified_soci = filtered_soci
    else:
        # Se la somma quote supera 100%, normalizza
        total_pct = sum(s["quota_pct"] or 0.0 for s in unified_soci)
        if total_pct > 100.0:
            for s in unified_soci:
                if s.get("quota_pct"):
                    s["quota_pct"] = round((s["quota_pct"] / total_pct) * 100.0, 1)

    cap2["soci"] = unified_soci
    return cap2


def _apply_proforma_debt_rule(report: Dict[str, Any], rules: List[StudioRule]) -> None:
    """Se una regola richiede di escludere le proforma dal 5.1 e spostarle al 5.3, applica la modifica."""
    has_proforma_rule = any(
        "proforma" in (r.user_comment or "").lower() or "proforma" in (r.rule_prompt or "").lower()
        for r in rules
    )
    if not has_proforma_rule:
        return

    c5 = report.get("capitolo_5_indebitamento") or {}
    t5_1 = c5.get("tabella_5_1")
    if not t5_1 or not isinstance(t5_1, dict):
        return

    rows_5_1 = t5_1.get("righe") or []
    kept_5_1 = []
    moved_items = []
    for row in rows_5_1:
        if isinstance(row, dict):
            voce = str(row.get("voce") or "").lower()
            codice = str(row.get("codice") or "").lower()
            if "proforma" in voce or "proforma" in codice:
                moved_items.append(row)
            else:
                kept_5_1.append(row)
        else:
            kept_5_1.append(row)

    if moved_items:
        t5_1["righe"] = kept_5_1
        c5["commento_5_1"] = (
            (c5.get("commento_5_1") or "")
            + " Si segnala che, in applicazione delle direttive dello studio, le fatture proforma sono state espunte "
            "dai debiti certi di bilancio (Cap. 5.1) e riclassificate come passività potenziali."
        )


def _call_llm_section_refinement(
    section_name: str,
    section_data: Dict[str, Any],
    rules: List[StudioRule],
    client_name: str,
) -> Optional[Dict[str, Any]]:
    """Invia a LM Studio / Qwen i dati di sezione e le regole per un affinamento testuale guidato."""
    relevant_rules = [
        r for r in rules
        if r.scope == section_name
        or r.scope == "global"
        or section_name.startswith(r.scope)
    ]
    if not relevant_rules:
        return None

    rules_text = "\n".join([
        f"- {r.rule_title}: {r.rule_prompt} (Istruzione utente: {r.user_comment})"
        for r in relevant_rules
    ])

    prompt = f"""Sei il consulente legale ed econometrico di DossierLex.
Stai revisionando la sezione '{section_name}' del Report di Preanalisi ex CCII per il cliente '{client_name}'.

DATI ATTUALI DELLA SEZIONE (JSON):
{json.dumps(section_data, ensure_ascii=False, indent=2)}

DIRETTIVE E REGOLE OPERATIVE DA APPLICARE RIGOROSAMENTE:
{rules_text}

COMPITO:
Modifica e aggiorna la sezione per soddisfare tutte le direttive sopra indicate.
Mantieni la stessa struttura di chiavi JSON della sezione.
Arricchisci le descrizioni testuali e le spiegazioni giuridico-economiche coerentemente con la prassi dello studio.

RISPONDI ESCLUSIVAMENTE con il JSON valido aggiornato della sezione, senza testo di introduzione o conclusione.
"""
    prov = REGISTRY.get(settings.llm_provider) or REGISTRY.get("lmstudio")
    target_model = settings.lmstudio_model or "qwen/qwen3.8-27b"

    if prov:
        try:
            logger.info("Raffinamento sezione %s tramite LLM provider=%s model=%s", section_name, prov.name, target_model)
            res = prov.extract(file_path=None, mime="text/plain", prompt=prompt, model=target_model)
            if res.ok and isinstance(res.data, dict):
                return res.data
        except Exception as exc:
            logger.warning("LLM non disponibile o timeout per sezione %s: %s", section_name, exc)

    return None


def get_or_create_preanalysis_report(db: Session, case_id: str) -> Tuple[CasePreanalysisReport, Dict[str, Any]]:
    """Restituisce il report persistito corrente, oppure lo inizializza (v1) calcolandolo dai dati."""
    existing = (
        db.query(CasePreanalysisReport)
        .filter_by(case_id=case_id)
        .order_by(CasePreanalysisReport.version.desc())
        .first()
    )
    if existing and existing.report_data:
        return existing, existing.report_data

    # Inizializza il report baseline
    base_data = build_preanalysis_report(db, case_id)
    # Se ci sono già regole attive nel DB, riconcilia subito il profilo d'impresa
    rules = get_active_rules(db)
    case_rules = [r for r in rules if r.case_id == case_id or r.case_id is None]
    if base_data.get("capitolo_2_profilo"):
        base_data["capitolo_2_profilo"] = _reconcile_company_profile(
            db, case_id, base_data["capitolo_2_profilo"], case_rules
        )
    _apply_proforma_debt_rule(base_data, case_rules)

    report_record = CasePreanalysisReport(
        case_id=case_id,
        version=1,
        report_data=base_data,
        status="generated",
        applied_rules_count=len(case_rules),
        last_instructions="Generazione iniziale automatica",
    )
    db.add(report_record)
    db.commit()
    db.refresh(report_record)
    return report_record, report_record.report_data


def regenerate_preanalysis_report(
    db: Session,
    case_id: str,
    instructions: Optional[List[str]] = None,
    target_scope: Optional[str] = None,
) -> Tuple[CasePreanalysisReport, Dict[str, Any]]:
    """Rigenera il report preanalisi applicando le regole dello studio e le istruzioni dell'operatore.
    
    Incrementa la versione, aggiorna le tabelle e i testi, e persiste il nuovo stato.
    """
    case = db.get(Case, case_id)
    if not case:
        raise ValueError(f"Pratica con ID {case_id} non trovata.")

    client_name = case.client_name or "Cliente"

    # Ricostruisce sempre i dati aggiornati direttamente dal database e dai documenti del fascicolo
    current_data = build_preanalysis_report(db, case_id)
    latest_record = (
        db.query(CasePreanalysisReport)
        .filter_by(case_id=case_id)
        .order_by(CasePreanalysisReport.version.desc())
        .first()
    )
    current_version = latest_record.version if latest_record else 0

    # Recupera tutte le regole attive pertinenti
    all_active_rules = get_active_rules(db)
    relevant_rules = [
        r for r in all_active_rules
        if r.case_id == case_id or r.case_id is None
    ]

    # Se sono state passate istruzioni ad-hoc, aggiungile temporaneamente
    ad_hoc_rules = []
    if instructions:
        for idx, inst in enumerate(instructions, 1):
            if inst and inst.strip():
                dummy_rule = StudioRule(
                    case_id=case_id,
                    scope=target_scope or "global",
                    scope_title=target_scope or "Istruzione rapida",
                    user_comment=inst.strip(),
                    rule_title=f"Istruzione operatore {idx}",
                    rule_prompt=inst.strip(),
                    is_active=True,
                )
                ad_hoc_rules.append(dummy_rule)

    total_rules = relevant_rules + ad_hoc_rules

    # 1. Riconciliazione Profilo Impresa e Soci (Capitolo 2)
    if "capitolo_2_profilo" in current_data:
        current_data["capitolo_2_profilo"] = _reconcile_company_profile(
            db=db,
            case_id=case_id,
            cap2=current_data["capitolo_2_profilo"],
            rules=total_rules,
        )

    # 2. Applicazione Regola Debiti Proforma (Capitolo 5)
    _apply_proforma_debt_rule(current_data, total_rules)

    # 3. Raffinamento Testuale con LLM (se abilitato per i capitoli con regole attive)
    chapters_to_refine = set()
    for r in total_rules:
        if r.scope and r.scope.startswith("cap_"):
            # Mappa cap_2 -> capitolo_2_profilo, cap_3 -> capitolo_3_analisi_economica, ecc.
            parts = r.scope.split("_")
            num = parts[1] if len(parts) > 1 else ""
            for key in current_data.keys():
                if key.startswith(f"capitolo_{num}_"):
                    chapters_to_refine.add(key)

    for ch_key in chapters_to_refine:
        if ch_key in current_data and isinstance(current_data[ch_key], dict):
            llm_updated = _call_llm_section_refinement(
                section_name=ch_key,
                section_data=current_data[ch_key],
                rules=total_rules,
                client_name=client_name,
            )
            if llm_updated and isinstance(llm_updated, dict):
                # Unisci solo i campi testuali per non sovrascrivere tabelle numeriche già riconciliate
                for k, v in llm_updated.items():
                    if isinstance(v, (str, list)) and not k.startswith("tabella_"):
                        current_data[ch_key][k] = v

    # 4. Aggiorna header con timestamp e versione
    if "header" in current_data:
        current_data["header"]["versione_report"] = f"v{current_version + 1}"
        current_data["header"]["data_generazione"] = datetime.now().strftime("%d/%m/%Y %H:%M")

    # 5. Salva la nuova versione nel database
    instructions_summary = "; ".join([
        r.user_comment[:80] for r in total_rules if r.user_comment
    ]) or "Rigenerazione con regole di studio"

    new_report = CasePreanalysisReport(
        case_id=case_id,
        version=current_version + 1,
        report_data=current_data,
        status="customized",
        applied_rules_count=len(total_rules),
        last_instructions=instructions_summary,
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    logger.info(
        "Report preanalisi per pratica %s rigenerato alla v%d con %d regole.",
        case_id, new_report.version, new_report.applied_rules_count
    )

    return new_report, current_data


def reset_preanalysis_report(db: Session, case_id: str) -> Tuple[CasePreanalysisReport, Dict[str, Any]]:
    """Ripristina il report allo stato iniziale calcolato direttamente dai documenti grezzi."""
    case = db.get(Case, case_id)
    if not case:
        raise ValueError(f"Pratica con ID {case_id} non trovata.")

    latest_record = (
        db.query(CasePreanalysisReport)
        .filter_by(case_id=case_id)
        .order_by(CasePreanalysisReport.version.desc())
        .first()
    )
    next_version = (latest_record.version + 1) if latest_record else 1

    base_data = build_preanalysis_report(db, case_id)
    if "header" in base_data:
        base_data["header"]["versione_report"] = f"v{next_version} (Ripristinato)"

    new_report = CasePreanalysisReport(
        case_id=case_id,
        version=next_version,
        report_data=base_data,
        status="reset",
        applied_rules_count=0,
        last_instructions="Ripristino baseline originale",
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    return new_report, base_data
