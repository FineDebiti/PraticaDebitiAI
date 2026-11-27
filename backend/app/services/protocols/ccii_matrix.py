"""Motore giuridico-decisionale parametrico CCII (Fase 3 — modalità simulazione read-only).

Caratteristiche vincolanti:
- Sola lettura (nessuna scrittura o commit su DB).
- Riferimento temporale deterministico esplicito tramite `assessment_date` (mai `date.today()`).
- Piena coerenza con gli stati reali di Gate 0 (`PREANALISI_SU_FASCICOLO_CONFERMATO`,
  `DIAGNOSI_PRELIMINARE_DELIMITATA`) e Formula Engine (`PFN_ESMA_CONFORME` con
  `validation_status == "VERIFICATO"`).
- Nessuna attivazione automatica di regole in `PENDING_APPROVAL` o `SUSPENDED`.
- Nessuna raccomandazione procedurale automatica: ogni scheda distingue i presupposti
  soggettivi, dimensionali, oggettivi, procedurali e le valutazioni riservate al professionista.
"""

from __future__ import annotations

import calendar
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.services.protocols.classifier import ClassificationResult, protocol_code_for_profile
from app.services.protocols.gate0 import Gate0Result

DEFAULT_CATALOG_PATH = Path(__file__).with_name("ccii_rules_catalog.json")

VALID_GATE0_CONCLUSIVITY_STATES = frozenset({
    "PREANALISI_SU_FASCICOLO_CONFERMATO",
    "DIAGNOSI_PRELIMINARE_DELIMITATA",
})

VALID_OUTCOMES = frozenset({"VERIFICATO", "NON_SODDISFATTO", "NON_DETERMINABILE"})
ApprovalStatus = Literal["PENDING_APPROVAL", "APPROVED", "SUSPENDED", "SUPERSEDED"]
RuleOutcome = Literal["VERIFICATO", "NON_SODDISFATTO", "NON_DETERMINABILE"]

OUTCOME_DISCLAIMER = (
    "L'esito 'VERIFICATO' attesta esclusivamente i requisiti formali/documentali controllabili "
    "sulle fonti disponibili alla data di valutazione e NON costituisce ammissione certa né "
    "raccomandazione procedurale automatica (decisione riservata al professionista — Human Gate)."
)


class CciiRuleDefinition(BaseModel):
    """Schema validato di una singola scheda normativa del catalogo CCII."""

    model_config = ConfigDict(extra="forbid")

    rule_code: str = Field(min_length=3)
    procedure_or_instrument: str = Field(min_length=3)
    normative_reference: str = Field(min_length=3)
    official_source_citation: str = Field(min_length=3)
    official_source_url: str = Field(min_length=8)
    normative_text_summary: str = Field(min_length=10)
    effective_from: date
    admitted_subjects: list[str] = Field(min_length=1)
    objective_and_subjective_requirements: list[str] = Field(min_length=1)
    required_data: list[str] = Field(min_length=1)
    deterministic_checks: list[str] = Field(min_length=1)
    interpretive_considerations: list[str] = Field(min_length=1)
    blocking_conditions: list[str] = Field(min_length=1)
    exceptions_and_transitional: list[str] = Field(default_factory=list)
    possible_outcomes: list[RuleOutcome] = Field(min_length=1)
    professional_approval_status: ApprovalStatus = "PENDING_APPROVAL"
    active_in_production: bool = False
    normative_version: str = Field(min_length=3)
    rule_version: str = Field(min_length=1)
    verified_at: date
    approved_by: Optional[str] = None
    approved_at: Optional[date] = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("active_in_production")
    @classmethod
    def _validate_active_consistency(cls, v: bool, info: Any) -> bool:
        status = (info.data or {}).get("professional_approval_status")
        if v and status != "APPROVED":
            raise ValueError(
                f"Una regola con stato '{status}' non può avere active_in_production=True."
            )
        return v


class SuspendedLegislativeItem(BaseModel):
    """Novità normativa non definitiva o non verificata mantenuta sospesa."""

    model_config = ConfigDict(extra="forbid")

    rule_code: str
    title: str
    normative_reference: str
    official_source_citation: str
    official_source_url: str
    professional_approval_status: Literal["SUSPENDED"] = "SUSPENDED"
    active_in_production: bool = False
    normative_version: str
    verified_at: date
    suspension_reason: str


class CciiRulesCatalog(BaseModel):
    """Schema validato del catalogo parametrico CCII."""

    model_config = ConfigDict(extra="forbid")

    catalog_version: str = Field(min_length=3)
    normative_snapshot_date: date
    default_execution_mode: str = "SIMULAZIONE_NON_ATTIVA_IN_PRODUZIONE"
    official_sources_registry: dict[str, dict[str, str]]
    rules: list[CciiRuleDefinition] = Field(min_length=1)
    suspended_legislative_rules: list[SuspendedLegislativeItem] = Field(default_factory=list)


class ProceduralFactRecord(BaseModel):
    """Fatto procedurale strutturato utilizzabile dalla matrice solo se tracciato e verificato."""

    model_config = ConfigDict(extra="ignore")

    fact_code: str = Field(min_length=2)
    value: Any
    source: str = Field(min_length=2)
    fact_date: date
    document_date: date
    verification_status: Literal["VERIFICATO", "DA_VERIFICARE", "NON_VERIFICATO", "CONTESTATO"]
    professional_confirmed: bool = False
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[date] = None
    notes: Optional[str] = None

    @field_validator("source")
    @classmethod
    def _strip_source(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("La fonte del fatto procedurale non può essere vuota.")
        return cleaned

    def is_usable_for_certification(self) -> bool:
        """Restituisce True solo se il fatto è verificato o confermato dal professionista."""
        return self.verification_status == "VERIFICATO" or bool(self.professional_confirmed)


def load_ccii_catalog(catalog_path: Optional[Path | str] = None) -> tuple[CciiRulesCatalog, str]:
    """Carica, valida e calcola l'impronta SHA-256 del catalogo normativo JSON."""
    path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG_PATH
    raw_bytes = path.read_bytes()
    sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
    payload = json.loads(raw_bytes.decode("utf-8"))
    catalog = CciiRulesCatalog.model_validate(payload)
    return catalog, sha256_hex


def parse_assessment_date(value: Any) -> date:
    """Converte esplicitamente assessment_date in `datetime.date`; rifiuta valori mancanti/invalidi."""
    if value is None or value == "" or isinstance(value, bool):
        raise ValueError("assessment_date è obbligatoria e deve essere una data esplicita (YYYY-MM-DD).")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        txt = value.strip()
        try:
            return date.fromisoformat(txt[:10])
        except ValueError as exc:
            raise ValueError(f"assessment_date non valida: '{value}'. Atteso formato YYYY-MM-DD.") from exc
    raise ValueError(f"Tipo non valido per assessment_date: {type(value).__name__}")


def _parse_opt_date(val: Any) -> Optional[date]:
    if val is None or val == "" or isinstance(val, bool):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        txt = val.strip()
        for candidate in (txt[:10], txt):
            try:
                return date.fromisoformat(candidate)
            except ValueError:
                pass
        for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(txt[:10], fmt).date()
            except ValueError:
                pass
    return None


def _add_calendar_months(start: date, months: int) -> date:
    month_idx = start.month - 1 + months
    year = start.year + month_idx // 12
    month = month_idx % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(start.day, last_day))


def _coerce_facts(
    procedural_facts: Optional[list[ProceduralFactRecord | dict[str, Any]]],
) -> tuple[dict[str, ProceduralFactRecord], list[dict[str, Any]]]:
    """Valida i fatti procedurali: accetta solo record verificati/confermati e completi di fonte e date."""
    usable: dict[str, ProceduralFactRecord] = {}
    rejected: list[dict[str, Any]] = []

    for raw in procedural_facts or []:
        try:
            rec = raw if isinstance(raw, ProceduralFactRecord) else ProceduralFactRecord.model_validate(raw)
        except ValidationError as exc:
            rejected.append({
                "raw": raw if isinstance(raw, dict) else str(raw),
                "reason": "Struttura incompleta (obbligatori fact_code, source, fact_date, document_date, verification_status).",
                "errors": [e.get("msg") for e in exc.errors()],
            })
            continue

        if not rec.is_usable_for_certification():
            rejected.append({
                "fact_code": rec.fact_code,
                "verification_status": rec.verification_status,
                "professional_confirmed": rec.professional_confirmed,
                "source": rec.source,
                "fact_date": rec.fact_date.isoformat(),
                "document_date": rec.document_date.isoformat(),
                "reason": "Fatto non verificato né confermato dal professionista: non utilizzabile per certificare requisiti.",
            })
            continue

        usable[rec.fact_code] = rec

    return usable, rejected


def _inspect_gate0(gate0: Gate0Result) -> dict[str, Any]:
    level = getattr(gate0, "conclusivity_level", None)
    valid = level in VALID_GATE0_CONCLUSIVITY_STATES
    confirmed = level == "PREANALISI_SU_FASCICOLO_CONFERMATO"
    anomaly: Optional[str] = None
    if not valid:
        anomaly = (
            f"Stato Gate 0 non riconosciuto ('{level}'): ammessi esclusivamente "
            f"{sorted(VALID_GATE0_CONCLUSIVITY_STATES)}."
        )
    return {
        "conclusivity_level": level,
        "valid_state": valid,
        "dossier_confirmed": confirmed,
        "anomaly": anomaly,
        "missing_p0": [
            item.get("title") or item.get("code")
            for item in (getattr(gate0, "documenti_indispensabili_p0", None) or [])
            if item.get("status") != "presente"
        ],
        "anomalies": list(getattr(gate0, "anomalie_gate0", None) or []),
        "suspended_decisions": list(getattr(gate0, "decisioni_sospese", None) or []),
    }


def _inspect_pfn_esma(formula_engine: dict[str, Any]) -> dict[str, Any]:
    annual_periods = list(formula_engine.get("annual_periods") or [])
    latest = annual_periods[-1] if annual_periods else {}
    pfn_esma = latest.get("pfn_esma") or {}
    pfn_fin_gest = latest.get("pfn_finanziaria_gestionale") or {}
    pfn_gest = latest.get("pfn_gestionale") or {}

    code_ok = pfn_esma.get("code") == "PFN_ESMA_CONFORME"
    status_ok = pfn_esma.get("validation_status") == "VERIFICATO"
    value_ok = pfn_esma.get("value") is not None
    esma_inputs = pfn_esma.get("inputs") or {}
    fin_inputs = pfn_fin_gest.get("inputs") or {}
    components_ok = isinstance(esma_inputs.get("componenti_esma"), dict) and not esma_inputs.get("esma_missing_components")
    flag_ok = fin_inputs.get("esma_compliant") is not False

    compliant = bool(latest and code_ok and status_ok and value_ok and components_ok and flag_ok)
    return {
        "period": latest.get("period"),
        "esma_compliant": compliant,
        "pfn_esma_code": pfn_esma.get("code"),
        "pfn_esma_validation_status": pfn_esma.get("validation_status"),
        "pfn_esma_value": pfn_esma.get("value") if compliant else None,
        "pfn_esma_missing_components": list(esma_inputs.get("esma_missing_components") or []),
        "pfn_gestionale_value": pfn_gest.get("value"),
        "pfn_gestionale_status": pfn_gest.get("validation_status"),
        "ebitda_value": (latest.get("ebitda") or {}).get("value"),
        "ebitda_validation_status": (latest.get("ebitda") or {}).get("validation_status"),
    }


def _classify_fiscal_debt_buckets(debt_ledger: dict[str, Any]) -> dict[str, Any]:
    """Classifica i carichi tributari/contributivi presenti nel DebtLedger senza duplicazioni."""
    buckets = debt_ledger.get("buckets") or {}
    trib_entries = list(buckets.get("tributari_contributivi") or [])
    payment_plans = [
        e for e in (buckets.get("estinte_e_piani_pagamento") or [])
        if e.get("exposure_kind") == "piano_pagamento"
    ]

    ader_cash = 0.0
    non_ader_tax = 0.0
    local_regional_tax = 0.0
    inps_total = 0.0
    inail_total = 0.0
    eu_own_resources = 0.0
    unclassified_tax = 0.0

    for item in trib_entries + payment_plans:
        amt = float(item.get("amount") or 0.0)
        if amt <= 0.0:
            continue
        src = (item.get("source") or "").lower()
        cred = (item.get("creditor") or "").lower()
        desc = (item.get("description") or "").lower()
        sub = (item.get("sub_category") or "").lower()
        text = f"{src} {cred} {desc} {sub}"

        if "dazi" in text or "risorse proprie" in text or "dogana" in text:
            eu_own_resources += amt
        elif "inps" in text:
            inps_total += amt
        elif "inail" in text:
            inail_total += amt
        elif any(k in text for k in ("imu", "tari", "comune", "provincia", "regione", "città metropolitana", "citta metropolitana", "tributo locale", "addizionale regionale")):
            if "ader" in src:
                ader_cash += amt
            local_regional_tax += amt
        elif "non affidat" in text or "non iscritto a ruolo" in text or "dichiarazione" in text or "lipe" in text:
            non_ader_tax += amt
        elif "ader" in src:
            ader_cash += amt
        elif "bilancio" in src:
            unclassified_tax += amt
        else:
            unclassified_tax += amt

    return {
        "ader_cash_eur": round(ader_cash, 2),
        "non_ader_tax_eur": round(non_ader_tax, 2),
        "local_regional_tax_eur": round(local_regional_tax, 2),
        "inps_total_eur": round(inps_total, 2),
        "inail_total_eur": round(inail_total, 2),
        "eu_own_resources_eur": round(eu_own_resources, 2),
        "unclassified_tax_eur": round(unclassified_tax, 2),
    }


def _evaluate_special_category(
    fact_code: str,
    usable_facts: dict[str, ProceduralFactRecord],
    classification: ClassificationResult,
    text_keywords: tuple[str, ...],
) -> dict[str, Any]:
    """Qualifica impresa agricola o startup innovativa solo con fatto procedurale verificato/confermato."""
    rec = usable_facts.get(fact_code)
    if rec is not None:
        return {
            "certified": bool(rec.value),
            "status": "VERIFICATO" if rec.value else "ESCLUSO_DOCUMENTATO",
            "evidence": f"Dato confermato/verificato da fonte '{rec.source}' (doc {rec.document_date.isoformat()}).",
            "hint_only": False,
        }

    evidence_blob = " ".join(
        list(classification.legal_form_evidence or []) + list(classification.accounting_regime_evidence or [])
    ).lower()
    has_hint = any(k in evidence_blob for k in text_keywords)
    if has_hint:
        return {
            "certified": False,
            "status": "INDIZIO_NON_CONFERMATO",
            "evidence": (
                f"Rilevato mero indizio testuale/ATECO per '{fact_code}': la qualifica giuridica "
                "NON può essere presunta da ATECO o denominazione e richiede visura camerale/sezione speciale "
                "o conferma espressa del professionista."
            ),
            "hint_only": True,
        }
    return {
        "certified": False,
        "status": "NON_DOCUMENTATO",
        "evidence": f"Qualifica '{fact_code}' non documentata.",
        "hint_only": False,
    }


def _is_production_active(rule: CciiRuleDefinition) -> bool:
    """Attivazione produttiva richiede contemporaneamente APPROVED e active_in_production=True."""
    return rule.professional_approval_status == "APPROVED" and bool(rule.active_in_production)


def _inspect_total_debt_perimeter(
    classification: ClassificationResult,
    debt_ledger: dict[str, Any],
) -> dict[str, Any]:
    """Distingue le 6 componenti del perimetro debitorio per l'art. 2 CCII (debiti anche non scaduti)."""
    ledger_state = debt_ledger.get("stato_dato") or "NON_VERIFICABILE_NULL"
    debt_totals = debt_ledger.get("totals") or {}
    bucket_totals = debt_ledger.get("bucket_totals") or {}
    bs_comp = debt_ledger.get("balance_sheet_comparison") or {}
    reconciliation_items = list(debt_ledger.get("reconciliation_required") or [])
    ext_bk = dict(getattr(classification, "ccii_external_breakdown", None) or {})
    metrics_years = list(classification.ccii_metrics_by_year or [])

    cassa_certe = debt_totals.get("esposizioni_per_cassa_certe")
    doc_cassa = debt_totals.get("posizioni_documentate_cassa")
    if doc_cassa is None and cassa_certe is not None:
        rif_val = float(debt_totals.get("posizioni_riferite_cassa") or 0.0)
        doc_cassa = max(0.0, round(float(cassa_certe) - rif_val, 2))

    # 2. Esposizioni finanziarie per cassa (distinte dal totale debiti complessivi)
    cr_cassa_bk = (debt_ledger.get("cr_breakdown") or {}).get("cassa_effettiva")
    banche_bucket = float(bucket_totals.get("bancari_finanziari") or 0.0)
    fact_bucket = float(bucket_totals.get("cessioni_credito") or 0.0)
    if bucket_totals and ("bancari_finanziari" in bucket_totals or "cessioni_credito" in bucket_totals):
        esp_finanziarie: Optional[float] = round(banche_bucket + fact_bucket, 2)
    elif cr_cassa_bk is not None:
        esp_finanziarie = round(float(cr_cassa_bk), 2)
    elif ext_bk.get("cr_cassa_effettiva") is not None:
        esp_finanziarie = round(float(ext_bk["cr_cassa_effettiva"]), 2)
    else:
        esp_finanziarie = None

    # 3. Debiti complessivi anche non scaduti (bilancio / serie annuale art. 2 riconciliati con DebtLedger)
    bilancio_deb_opt = bs_comp.get("bilancio_debiti_totali")
    if bilancio_deb_opt is None:
        for m in metrics_years:
            if m.get("debiti") is not None:
                bilancio_deb_opt = float(m["debiti"])
                break

    if bilancio_deb_opt is not None and cassa_certe is not None:
        debiti_complessivi: Optional[float] = round(max(float(bilancio_deb_opt), float(cassa_certe)), 2)
        delta_cassa_bilancio: Optional[float] = round(float(cassa_certe) - float(bilancio_deb_opt), 2)
    elif bilancio_deb_opt is not None and ledger_state != "NON_VERIFICABILE_NULL":
        debiti_complessivi = round(float(bilancio_deb_opt), 2)
        delta_cassa_bilancio = None
    elif cassa_certe is not None and ledger_state != "NON_VERIFICABILE_NULL":
        # Solo cassa da fonti dirette (puo mancare la quota non scaduta/fornitori di bilancio!)
        debiti_complessivi = round(float(cassa_certe), 2)
        delta_cassa_bilancio = None
    else:
        debiti_complessivi = None
        delta_cassa_bilancio = None

    # 4. Passivita contestate / sospese (escluse dal debito certo ma tracciate)
    contestate_val = debt_totals.get("posizioni_contestate_sospese")
    if contestate_val is None and ext_bk.get("aer_sospeso_contestato") is not None:
        contestate_val = float(ext_bk["aer_sospeso_contestato"])

    # 5. Garanzie non escusse / rischi di firma (separate dai debiti per cassa)
    garanzie_val = debt_totals.get("esposizioni_di_firma_e_garanzie")
    if garanzie_val is None and ext_bk.get("cr_garanzie_e_firma") is not None:
        garanzie_val = float(ext_bk["cr_garanzie_e_firma"])

    # 6. Importi non riconciliati
    rif_cassa = float(debt_totals.get("posizioni_riferite_cassa") or 0.0)
    non_quant_cnt = int(debt_totals.get("posizioni_non_quantificate_count") or 0)
    bilancio_understates_cassa = bool(delta_cassa_bilancio is not None and delta_cassa_bilancio > 1.00)
    has_unreconciled = bool(
        reconciliation_items
        or rif_cassa > 0.0
        or non_quant_cnt > 0
        or bilancio_understates_cassa
    )

    non_overdue_perimeter_documented = bilancio_deb_opt is not None
    ricostruzione_affidabile = bool(
        ledger_state == "VERIFICATO"
        and not has_unreconciled
        and debiti_complessivi is not None
        and non_overdue_perimeter_documented
    )

    return {
        "massa_debitoria_documentata_eur": doc_cassa,
        "esposizioni_finanziarie_per_cassa_eur": esp_finanziarie,
        "debiti_complessivi_anche_non_scaduti_eur": debiti_complessivi,
        "passivita_contestate_eur": round(float(contestate_val), 2) if contestate_val is not None else None,
        "garanzie_non_escusse_eur": round(float(garanzie_val), 2) if garanzie_val is not None else None,
        "importi_non_riconciliati": {
            "ledger_stato_dato": ledger_state,
            "reconciliation_required_count": len(reconciliation_items),
            "reconciliation_codes": [str(it.get("code") or "") for it in reconciliation_items],
            "posizioni_riferite_cassa_eur": round(rif_cassa, 2),
            "posizioni_non_quantificate_count": non_quant_cnt,
            "delta_cassa_vs_bilancio_eur": delta_cassa_bilancio,
            "has_unreconciled_amounts": has_unreconciled,
        },
        "non_overdue_debt_perimeter_documented": non_overdue_perimeter_documented,
        "debiti_complessivi_ricostruzione_affidabile": ricostruzione_affidabile,
    }


def _inspect_dimensional_contract(
    classification: ClassificationResult,
    debt_perimeter: dict[str, Any],
    *,
    attivo_max_eur: float = 300000.0,
    ricavi_max_eur: float = 200000.0,
    debiti_max_eur: float = 500000.0,
) -> dict[str, Any]:
    """Allinea la lettura ai campi effettivi di classifier.py (attivo, ricavi, debiti, exceeded)."""
    metrics_years = list(classification.ccii_metrics_by_year or [])
    exceeded_reasons: list[str] = []

    for m in metrics_years:
        yr = str(m.get("year") or "n/d")
        ex_list = list(m.get("exceeded") or [])
        for ex in ex_list:
            exceeded_reasons.append(f"Esercizio {yr}: {ex}")
        if not ex_list:
            att = m.get("attivo")
            ric = m.get("ricavi")
            deb = m.get("debiti")
            if att is not None and float(att) > attivo_max_eur:
                exceeded_reasons.append(f"Esercizio {yr}: attivo={float(att):,.2f} > {attivo_max_eur:,.0f}")
            if ric is not None and float(ric) > ricavi_max_eur:
                exceeded_reasons.append(f"Esercizio {yr}: ricavi={float(ric):,.2f} > {ricavi_max_eur:,.0f}")
            if deb is not None and float(deb) > debiti_max_eur:
                exceeded_reasons.append(f"Esercizio {yr}: debiti={float(deb):,.2f} > {debiti_max_eur:,.0f}")

    tot_deb_comp = debt_perimeter.get("debiti_complessivi_anche_non_scaduti_eur")
    if tot_deb_comp is not None and float(tot_deb_comp) > debiti_max_eur:
        # Verifica che non sia gia solo conflitto bilancio vs fonte esterna rilevato dal classificatore
        if classification.ccii_size_qualification != "non_determinabile":
            exceeded_reasons.append(
                f"Debiti complessivi anche non scaduti (€ {float(tot_deb_comp):,.2f}) > soglia € {debiti_max_eur:,.0f}"
            )

    ext_bk = getattr(classification, "ccii_external_breakdown", None) or {}
    if classification.ccii_size_qualification == "non_minore":
        if ext_bk.get("aer_netto_effettivo") is not None and float(ext_bk["aer_netto_effettivo"]) > debiti_max_eur:
            exceeded_reasons.append(f"Debito netto AdER (€ {float(ext_bk['aer_netto_effettivo']):,.2f}) > € {debiti_max_eur:,.0f}")
        if ext_bk.get("cr_cassa_effettiva") is not None and float(ext_bk["cr_cassa_effettiva"]) > debiti_max_eur:
            exceeded_reasons.append(f"Esposizione CR per cassa (€ {float(ext_bk['cr_cassa_effettiva']):,.2f}) > € {debiti_max_eur:,.0f}")

    # Deduplica mantenendo ordine
    exceeded_reasons = list(dict.fromkeys(exceeded_reasons))

    all_years_complete = bool(metrics_years) and all(
        bool(m.get("complete_for_ccii"))
        or (m.get("attivo") is not None and m.get("ricavi") is not None and m.get("debiti") is not None)
        for m in metrics_years
    )
    young_under_3_years = (
        classification.ccii_size_qualification == "impresa_minore"
        and 1 <= len(metrics_years) < 3
        and all_years_complete
        and not exceeded_reasons
    )
    exercises_verified = bool((len(metrics_years) >= 3 or young_under_3_years) and all_years_complete)

    size_qual = classification.ccii_size_qualification
    deb_reliable = bool(debt_perimeter.get("debiti_complessivi_ricostruzione_affidabile"))
    deb_under_500k = tot_deb_comp is not None and float(tot_deb_comp) <= debiti_max_eur

    if size_qual == "non_determinabile":
        effective_size_qual = "non_determinabile"
    elif size_qual == "non_minore" and exceeded_reasons:
        effective_size_qual = "non_minore"
    elif size_qual == "impresa_minore" and exercises_verified and deb_reliable and deb_under_500k:
        effective_size_qual = "impresa_minore"
    else:
        effective_size_qual = "non_determinabile"

    return {
        "classifier_size_qualification": size_qual,
        "effective_size_qualification": effective_size_qual,
        "exercises_count": len(metrics_years),
        "all_years_complete": all_years_complete,
        "young_company_under_3_years": young_under_3_years,
        "exercises_verified": exercises_verified,
        "exceeded_reasons": exceeded_reasons,
        "certified_minor": effective_size_qual == "impresa_minore",
        "confirmed_non_minor": effective_size_qual == "non_minore",
    }


def _rule_metadata_block(
    rule: CciiRuleDefinition,
    *,
    assessment_date: date,
    simulation_mode: bool,
) -> dict[str, Any]:
    normatively_effective = assessment_date >= rule.effective_from
    prod_active = _is_production_active(rule)
    can_execute = simulation_mode or prod_active
    if not simulation_mode and prod_active:
        exec_mode = "ATTIVA_IN_PRODUZIONE"
    elif simulation_mode:
        exec_mode = "SIMULAZIONE_NON_ATTIVA_IN_PRODUZIONE"
    else:
        exec_mode = "BLOCCATA_NON_ATTIVA_IN_PRODUZIONE"
    return {
        "rule_code": rule.rule_code,
        "procedure_or_instrument": rule.procedure_or_instrument,
        "normative_reference": rule.normative_reference,
        "official_source_citation": rule.official_source_citation,
        "official_source_url": rule.official_source_url,
        "normative_text_summary": rule.normative_text_summary,
        "effective_from": rule.effective_from.isoformat(),
        "normatively_effective_at_assessment_date": normatively_effective,
        "professional_approval_status": rule.professional_approval_status,
        "active_in_production": prod_active,
        "execution_mode": exec_mode,
        "can_execute_under_current_mode": can_execute,
        "normative_version": rule.normative_version,
        "rule_version": rule.rule_version,
        "verified_at": rule.verified_at.isoformat(),
    }


def _combine_outcome(statuses: list[str], *, any_blocking: bool = False) -> RuleOutcome:
    if any_blocking or "NON_SODDISFATTO" in statuses:
        return "NON_SODDISFATTO"
    applicable = [s for s in statuses if s != "NON_APPLICABILE"]
    if not applicable or any(s == "NON_DETERMINABILE" for s in applicable):
        return "NON_DETERMINABILE"
    if all(s == "VERIFICATO" for s in applicable):
        return "VERIFICATO"
    return "NON_DETERMINABILE"


def _blocked_rule_result(rule: CciiRuleDefinition, *, assessment_date: date, simulation_mode: bool) -> dict[str, Any]:
    meta = _rule_metadata_block(rule, assessment_date=assessment_date, simulation_mode=simulation_mode)
    if rule.professional_approval_status == "APPROVED" and not rule.active_in_production:
        exec_status = "APPROVATA_NON_ATTIVA_IN_PRODUZIONE"
        reason_msg = (
            f"Regola '{rule.rule_code}' in stato APPROVED ma con active_in_production=False: "
            "esecuzione produttiva bloccata fino ad attivazione esplicita."
        )
    elif rule.professional_approval_status == "SUSPENDED":
        exec_status = "SOSPESA_NORMA_NON_DEFINITIVA"
        reason_msg = f"Regola '{rule.rule_code}' in stato SUSPENDED."
    else:
        exec_status = "BLOCCATA_IN_ATTESA_APPROVAZIONE"
        reason_msg = (
            f"Regola '{rule.rule_code}' in stato '{rule.professional_approval_status}': "
            "esecuzione produttiva bloccata fino ad approvazione professionale e active_in_production=True."
        )
    return {
        **meta,
        "deterministic_outcome": "NON_DETERMINABILE",
        "execution_status": exec_status,
        "subjective_requirement_status": "NON_DETERMINABILE",
        "dimensional_requirement_status": "NON_DETERMINABILE",
        "objective_requirement_status": "NON_DETERMINABILE",
        "procedural_requirement_status": "NON_DETERMINABILE",
        "professional_evaluation_required": True,
        "outcome_disclaimer": OUTCOME_DISCLAIMER,
        "satisfied_requirements": [],
        "missing_requirements": [],
        "indeterminable_requirements": [reason_msg],
        "blocking_conditions_verified": [],
        "blocking_conditions_unverified": list(rule.blocking_conditions),
        "missing_documents": [],
        "interpretive_considerations": list(rule.interpretive_considerations),
        "reserved_to_professional": [
            f"Validazione normativa e attivazione esplicita della regola {rule.rule_code}."
        ],
        "suspended_decisions": [f"Valutazione {rule.procedure_or_instrument} sospesa in attesa attivazione."],
        "exceptions_and_transitional": list(rule.exceptions_and_transitional),
    }


def _make_evaluation(
    rule: CciiRuleDefinition,
    *,
    assessment_date: date,
    simulation_mode: bool,
    subjective_status: str,
    dimensional_status: str,
    objective_status: str,
    procedural_status: str,
    satisfied: list[str],
    missing: list[str],
    indeterminable: list[str],
    blocking_verified: list[str],
    blocking_unverified: list[str],
    missing_docs: list[str],
    reserved: list[str],
    suspended: list[str],
    interpretive_notes: Optional[list[str]] = None,
    transitional_notes: Optional[list[str]] = None,
    outcome_override: Optional[RuleOutcome] = None,
) -> dict[str, Any]:
    meta = _rule_metadata_block(rule, assessment_date=assessment_date, simulation_mode=simulation_mode)
    if not meta["normatively_effective_at_assessment_date"]:
        outcome: RuleOutcome = "NON_SODDISFATTO"
        missing = list(missing) + [
            f"Norma non ancora in vigore alla assessment_date ({assessment_date.isoformat()} < {rule.effective_from.isoformat()})."
        ]
    elif outcome_override is not None:
        outcome = outcome_override
    else:
        outcome = _combine_outcome(
            [subjective_status, dimensional_status, objective_status, procedural_status],
            any_blocking=bool(blocking_verified),
        )

    return {
        **meta,
        "deterministic_outcome": outcome,
        "execution_status": "SIMULAZIONE_VALUTATA" if simulation_mode else "ATTIVA_VALUTATA",
        "subjective_requirement_status": subjective_status,
        "dimensional_requirement_status": dimensional_status,
        "objective_requirement_status": objective_status,
        "procedural_requirement_status": procedural_status,
        "professional_evaluation_required": True,
        "outcome_disclaimer": OUTCOME_DISCLAIMER,
        "satisfied_requirements": satisfied,
        "missing_requirements": missing,
        "indeterminable_requirements": indeterminable,
        "blocking_conditions_verified": blocking_verified,
        "blocking_conditions_unverified": blocking_unverified,
        "missing_documents": list(dict.fromkeys(missing_docs)),
        "interpretive_considerations": list(interpretive_notes or rule.interpretive_considerations),
        "reserved_to_professional": reserved or ["Valutazione giuridico-strategica finale riservata al professionista (Human Gate)."],
        "suspended_decisions": suspended,
        "exceptions_and_transitional": list(transitional_notes or rule.exceptions_and_transitional),
    }


def evaluate_ccii_matrix(
    classification: ClassificationResult,
    gate0: Gate0Result,
    debt_ledger: dict[str, Any],
    formula_engine: dict[str, Any],
    *,
    assessment_date: date | str,
    effective_legal_form: Optional[str] = None,
    effective_accounting_regime: Optional[str] = None,
    procedural_facts: Optional[list[ProceduralFactRecord | dict[str, Any]]] = None,
    simulation_mode: bool = True,
    catalog_path: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Valuta in sola lettura la matrice giuridico-decisionale CCII senza raccomandazioni automatiche."""
    eval_date = parse_assessment_date(assessment_date)
    catalog, catalog_sha256 = load_ccii_catalog(catalog_path)
    usable_facts, rejected_facts = _coerce_facts(procedural_facts)

    legal_form = effective_legal_form or getattr(gate0, "effective_legal_form_profile", None) or classification.legal_form_profile
    accounting_regime = effective_accounting_regime or getattr(gate0, "effective_accounting_regime", None) or classification.accounting_regime
    protocol_code = protocol_code_for_profile(legal_form)

    gate0_info = _inspect_gate0(gate0)
    pfn_info = _inspect_pfn_esma(formula_engine)
    ledger_state = debt_ledger.get("stato_dato") or "NON_VERIFICABILE_NULL"
    debt_totals = debt_ledger.get("totals") or {}
    cassa_certe = debt_totals.get("esposizioni_per_cassa_certe")
    missing_sources = list(debt_ledger.get("missing_sources_to_acquire") or [])
    reconciliation_items = list(debt_ledger.get("reconciliation_required") or [])
    fiscal_buckets = _classify_fiscal_debt_buckets(debt_ledger)
    debt_perimeter = _inspect_total_debt_perimeter(classification, debt_ledger)
    debt_mass_verified = ledger_state == "VERIFICATO"
    dim_contract = _inspect_dimensional_contract(classification, debt_perimeter)
    size_qual = dim_contract["effective_size_qualification"]
    raw_classifier_size_qual = classification.ccii_size_qualification

    agricola_cat = _evaluate_special_category(
        "impresa_agricola_camerale",
        usable_facts,
        classification,
        ("agricol", "coltivatore diretto", "ateco 01", "ateco 02", "ateco 03"),
    )
    startup_cat = _evaluate_special_category(
        "startup_innovativa_sezione_speciale",
        usable_facts,
        classification,
        ("startup innovativa", "start-up innovativa", "sezione speciale startup"),
    )

    is_entrepreneurial_profile = legal_form in {
        "impresa_individuale",
        "societa_capitali_srl",
        "societa_persone",
        "altra_forma_giuridica",
    }
    is_consumer_profile = legal_form == "persona_fisica_non_imprenditore"
    is_uncertain_profile = legal_form not in (
        {"impresa_individuale", "societa_capitali_srl", "societa_persone", "altra_forma_giuridica", "persona_fisica_non_imprenditore"}
    )

    # Verifica iscrizione / cancellazione dal Registro Imprese (art. 33 co. 4 / co. 1-bis)
    ri_status_fact = usable_facts.get("stato_registro_imprese")
    ri_cancelled: Optional[bool] = None
    ri_cancellation_date: Optional[date] = None
    if ri_status_fact is not None:
        val_str = str(ri_status_fact.value or "").strip().lower()
        if val_str in ("cancellata", "cancellato", "cessata_cancellata"):
            ri_cancelled = True
            ri_cancellation_date = ri_status_fact.fact_date
        elif val_str in ("attiva", "attivo", "iscritta", "in_liquidazione"):
            ri_cancelled = False

    # Controllo art. 25-quinquies da fatti procedurali verificati
    pending_debtor_filing_fact = usable_facts.get("domanda_regolazione_debitore_pendente")
    third_party_lg_fact = usable_facts.get("istanza_lg_terzi_pendente")
    waiver_fact = usable_facts.get("rinuncia_domande_regolazione")

    # Controllo CNC / Art. 25-sexies / Art. 19 / D.Lgs. 147/2026 date pendenti
    cnc_active_fact = usable_facts.get("cnc_attiva_o_avviata")
    cnc_started_date = cnc_active_fact.fact_date if (cnc_active_fact and cnc_active_fact.value) else None
    cnc_final_report_fact = usable_facts.get("relazione_finale_esperto_cnc")
    cnc_good_faith_fact = usable_facts.get("attestazione_correttezza_buona_fede_esperto")
    cnc_art23_unfeasible_fact = usable_facts.get("attestazione_impraticabilita_art23")
    mp_pub_fact = usable_facts.get("pubblicazione_ri_misure_protettive")
    mp_petition_fact = usable_facts.get("ricorso_tribunale_misure_protettive")
    mp_order_fact = usable_facts.get("ordinanza_tribunale_misure_protettive")
    procedure_started_fact = usable_facts.get("data_avvio_procedura_o_cnc")
    procedure_started_date = procedure_started_fact.fact_date if procedure_started_fact else cnc_started_date

    local_tax_ext_effective = eval_date >= date(2026, 8, 12)
    pending_before_dlgs147 = bool(procedure_started_date and procedure_started_date < date(2026, 8, 12))

    # Valutazione per ciascuna delle 14 schede
    schede: list[dict[str, Any]] = []
    for rule in catalog.rules:
        if not simulation_mode and not _is_production_active(rule):
            schede.append(_blocked_rule_result(rule, assessment_date=eval_date, simulation_mode=simulation_mode))
            continue

        rc = rule.rule_code

        # ------------------------------------------------------------------
        # 1) CCII-DIM-01 — Art. 2 co. 1 lett. d)
        # ------------------------------------------------------------------
        if rc == "CCII-DIM-01":
            if is_consumer_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_APPLICABILE",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[],
                    missing=["Profilo classificato come persona fisica non imprenditore (consumatore)."],
                    indeterminable=[],
                    blocking_verified=["Soggetto non imprenditore escluso dalla qualificazione d'impresa minore."],
                    blocking_unverified=[],
                    missing_docs=[],
                    reserved=["Verificare l'assenza di attività d'impresa o debiti misti residui."],
                    suspended=["Qualificazione dimensionale art. 2 co. 1 lett. d) non applicabile al consumatore."],
                ))
                continue

            if is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_DETERMINABILE",
                    dimensional_status="NON_DETERMINABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_DETERMINABILE",
                    satisfied=[],
                    missing=[],
                    indeterminable=["Forma giuridica incerta: impossibile qualificare l'impresa ex art. 2 CCII."],
                    blocking_verified=[],
                    blocking_unverified=list(rule.blocking_conditions),
                    missing_docs=gate0_info["missing_p0"] + ["Visura CCIAA / conferma profilo giuridico"],
                    reserved=["Conferma forma giuridica tramite Human Gate."],
                    suspended=["Qualificazione dimensionale sospesa fino a identificazione certa del soggetto."],
                ))
                continue

            sat, miss, indet, blk_ver, mdocs = [], [], [], [], list(gate0_info["missing_p0"])
            if dim_contract["young_company_under_3_years"]:
                sat.append(
                    f"Impresa costituita da meno di 3 anni: valutati tutti i {dim_contract['exercises_count']} "
                    "esercizi disponibili completi (attivo, ricavi, debiti) ex art. 2 co. 1 lett. d)."
                )
            elif dim_contract["exercises_verified"]:
                sat.append(
                    f"Esercizi rilevanti esaminati ({dim_contract['exercises_count']} esercizi con attivo, ricavi e debiti documentati)."
                )
            else:
                indet.append(
                    f"Verifica esercizi rilevanti incompleta ({dim_contract['exercises_count']}/3 esercizi completi per attivo/ricavi/debiti) "
                    "o serie non consecutiva/pertinente."
                )
                mdocs.extend(list(classification.ccii_required_verifications or []))
                mdocs.append("Bilanci/dichiarazioni dei 3 esercizi antecedenti o visura data costituzione (< 3 anni).")

            deb_tot_eur = debt_perimeter["debiti_complessivi_anche_non_scaduti_eur"]
            esp_fin_eur = debt_perimeter["esposizioni_finanziarie_per_cassa_eur"]
            cont_eur = debt_perimeter["passivita_contestate_eur"]
            gar_eur = debt_perimeter["garanzie_non_escusse_eur"]
            non_ric = debt_perimeter["importi_non_riconciliati"]

            if debt_perimeter["debiti_complessivi_ricostruzione_affidabile"] and deb_tot_eur is not None:
                sat.append(
                    f"Debiti complessivi (anche non scaduti) ricostruiti in via affidabile pari a € {deb_tot_eur:,.2f} "
                    f"(esposizioni finanziarie per cassa distinte: € {(esp_fin_eur or 0.0):,.2f})."
                )
            elif deb_tot_eur is not None:
                indet.append(
                    f"Perimetro dei debiti complessivi (anche non scaduti) pari a € {deb_tot_eur:,.2f} NON certificabile "
                    f"(stato DebtLedger={ledger_state}, perimetro non scaduti documentato="
                    f"{debt_perimeter['non_overdue_debt_perimeter_documented']}, "
                    f"importi non riconciliati={non_ric['has_unreconciled_amounts']})."
                )
                mdocs.extend(missing_sources)
                if not debt_perimeter["non_overdue_debt_perimeter_documented"]:
                    mdocs.append("Situazione patrimoniale / partitario debiti complessivi (anche non scaduti verso fornitori e terzi).")
            else:
                indet.append("Ammontare dei debiti complessivi (anche non scaduti) non determinabile (NULL).")
                mdocs.extend(missing_sources)

            if cont_eur is not None and cont_eur > 0:
                indet.append(
                    f"Presenti passività contestate/sospese per € {cont_eur:,.2f} (escluse dal debito certo ma da verificare per eventuale impatto su soglia € 500k)."
                )
            if gar_eur is not None and gar_eur > 0:
                sat.append(
                    f"Garanzie non escusse / rischi di firma (€ {gar_eur:,.2f}) mantenute distinte dal debito complessivo art. 2 CCII."
                )

            if dim_contract["certified_minor"]:
                dim_st = "VERIFICATO"
                sat.append("Tutti e tre i requisiti cumulativi art. 2 co. 1 lett. d) rispettati: qualifica IMPRESA MINORE.")
                if legal_form == "societa_capitali_srl":
                    sat.append("Invarianza forma: S.r.l. sotto soglia resta soggetta al Protocollo B economico-contabile.")
            elif dim_contract["confirmed_non_minor"]:
                dim_st = "NON_SODDISFATTO"
                miss.extend(dim_contract["exceeded_reasons"])
                miss.append("Soglia dimensionale art. 2 co. 1 lett. d) superata su fonte documentata → Impresa NON MINORE (non equivale a insolvenza).")
            else:
                dim_st = "NON_DETERMINABILE"
                for anom in (classification.anomalies or []):
                    if anom not in indet:
                        indet.append(anom)

            dim_card = _make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status="VERIFICATO",
                dimensional_status=dim_st,
                objective_status="VERIFICATO" if dim_st == "VERIFICATO" else dim_st,
                procedural_status="VERIFICATO" if gate0_info["dossier_confirmed"] else "NON_DETERMINABILE",
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[] if dim_st != "NON_DETERMINABILE" else ["Completezza esercizi pertinenti e ricostruzione affidabile debiti anche non scaduti"],
                missing_docs=mdocs,
                reserved=[
                    "Verifica di eventuali componenti straordinarie, passività contestate, garanzie escutibili o data inizio attività.",
                    "Accertamento autonomo dello stato di crisi/insolvenza (il superamento delle soglie non determina insolvenza).",
                ],
                suspended=[] if dim_st != "NON_DETERMINABILE" else ["Qualificazione dimensionale art. 2 co. 1 lett. d) sospesa."],
                outcome_override="NON_DETERMINABILE" if dim_st == "NON_DETERMINABILE" else ("VERIFICATO" if dim_st == "VERIFICATO" else "NON_SODDISFATTO"),
            )
            dim_card["debt_perimeter_breakdown"] = debt_perimeter
            schede.append(dim_card)

        # ------------------------------------------------------------------
        # 2) CCII-ALL-01 — Art. 3 co. 4 lett. a-d
        # ------------------------------------------------------------------
        elif rc == "CCII-ALL-01":
            if is_consumer_profile or is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO" if is_consumer_profile else "NON_DETERMINABILE",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[], missing=["Non applicabile al consumatore puro."] if is_consumer_profile else [],
                    indeterminable=["Profilo giuridico non identificato."] if is_uncertain_profile else [],
                    blocking_verified=[], blocking_unverified=[], missing_docs=[],
                    reserved=["Verifica obblighi di monitoraggio assetti ex art. 2086 c.c. e art. 3 CCII."],
                    suspended=["Screening segnali d'allarme non applicabile/sospeso."],
                ))
                continue

            sat, miss, indet, mdocs = [], [], [], []
            letter_states: dict[str, str] = {}

            # Lett. a) retribuzioni
            ret_f = usable_facts.get("retribuzioni_scadute_30gg")
            monte_f = usable_facts.get("monte_salari_mensile")
            if ret_f and monte_f and float(monte_f.value or 0) > 0:
                if float(ret_f.value or 0) > float(monte_f.value) * 0.5:
                    letter_states["a_retribuzioni"] = "VERIFICATO"
                    sat.append("Art. 3 co. 4 lett. a): retribuzioni scadute >= 30gg oltre la metà del monte salari mensile.")
                else:
                    letter_states["a_retribuzioni"] = "NON_SODDISFATTO"
            else:
                letter_states["a_retribuzioni"] = "NON_DETERMINABILE"
                indet.append("Lett. a) Retribuzioni scadute >=30gg / monte salari mensile non documentati (NULL).")
                mdocs.append("Libro Unico / prospetto paghe scadute >= 30gg e monte salari mensile.")

            # Lett. b) fornitori
            forn_scad_f = usable_facts.get("debiti_fornitori_scaduti_90gg")
            forn_non_f = usable_facts.get("debiti_fornitori_non_scaduti")
            if forn_scad_f and forn_non_f:
                if float(forn_scad_f.value or 0) > float(forn_non_f.value or 0):
                    letter_states["b_fornitori"] = "VERIFICATO"
                    sat.append("Art. 3 co. 4 lett. b): debiti fornitori scaduti >= 90gg superiori ai non scaduti.")
                else:
                    letter_states["b_fornitori"] = "NON_SODDISFATTO"
            else:
                letter_states["b_fornitori"] = "NON_DETERMINABILE"
                indet.append("Lett. b) Partitario fornitori scaduti >=90gg vs non scaduti non documentato (NULL).")
                mdocs.append("Scadenzario fornitori distinto tra scaduto >= 90gg e non scaduto.")

            # Lett. c) banche (>=60gg e >=5% totale esposizioni)
            bank_60_f = usable_facts.get("esposizioni_banche_scadute_o_sconfinate_60gg")
            bank_tot_f = usable_facts.get("totale_esposizioni_bancarie_art3")
            cr_cash = (debt_ledger.get("cr_breakdown") or {}).get("cassa_effettiva")
            if bank_60_f and (bank_tot_f or cr_cash):
                tot_exp = float((bank_tot_f.value if bank_tot_f else cr_cash) or 0.0)
                over_60 = float(bank_60_f.value or 0.0)
                if tot_exp > 0 and (over_60 / tot_exp * 100.0) >= 5.0:
                    letter_states["c_banche"] = "VERIFICATO"
                    sat.append("Art. 3 co. 4 lett. c): esposizioni bancarie scadute/sconfinate >= 60gg pari ad almeno il 5% delle esposizioni.")
                else:
                    letter_states["c_banche"] = "NON_SODDISFATTO"
            else:
                letter_states["c_banche"] = "NON_DETERMINABILE"
                indet.append("Lett. c) Anzianità scaduti/sconfinamenti bancari >=60gg non documentata (NULL).")
                mdocs.append("Centrale Rischi omogenea con evidenza scaduti/sconfinamenti >= 60gg rispetto al totale affidato/utilizzato.")

            # Lett. d) creditori pubblici qualificati (AdER se certo supera soglia forma giuridica)
            ader_thr = rule_cpq_thr = {"impresa_individuale": 100000.0, "societa_persone": 200000.0}.get(legal_form, 500000.0)
            ader_90_f = usable_facts.get("ader_scaduti_oltre_90gg")
            inps_f = usable_facts.get("inps_segnalazione_art25novies")
            inail_f = usable_facts.get("inail_segnalazione_art25novies")
            iva_f = usable_facts.get("ade_iva_segnalazione_art25novies")
            if ader_90_f and float(ader_90_f.value or 0) > ader_thr:
                letter_states["d_cpq"] = "VERIFICATO"
                sat.append(f"Art. 3 co. 4 lett. d): AdER scaduti >90gg (€ {float(ader_90_f.value):,.2f}) oltre soglia € {rule_cpq_thr:,.0f}.")
            elif any(f and bool(f.value) for f in (inps_f, inail_f, iva_f)):
                letter_states["d_cpq"] = "VERIFICATO"
                sat.append("Art. 3 co. 4 lett. d): rilevata esposizione oltre soglia ex art. 25-novies.")
            elif ader_90_f and inps_f and inail_f and iva_f:
                letter_states["d_cpq"] = "NON_SODDISFATTO"
            else:
                letter_states["d_cpq"] = "NON_DETERMINABILE"
                indet.append("Lett. d) Verifica completa dei 4 enti ex art. 25-novies parziale/mancante (NULL).")
                mdocs.append("Dettaglio anzianità scadenze AdER >90gg ed estratti INPS/INAIL/LIPE IVA.")

            has_any_signal = any(v == "VERIFICATO" for v in letter_states.values())
            all_negative = all(v == "NON_SODDISFATTO" for v in letter_states.values())
            if has_any_signal:
                obj_st = "VERIFICATO"
            elif all_negative:
                obj_st = "NON_SODDISFATTO"
            else:
                obj_st = "NON_DETERMINABILE"

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status="VERIFICATO",
                dimensional_status="NON_APPLICABILE",
                objective_status=obj_st,
                procedural_status="VERIFICATO" if (has_any_signal or all_negative) else "NON_DETERMINABILE",
                satisfied=sat + [f"Stato analitico lettere art. 3 co. 4: {letter_states}"],
                missing=miss,
                indeterminable=indet,
                blocking_verified=[],
                blocking_unverified=[],
                missing_docs=mdocs,
                reserved=[
                    "Valutazione adeguatezza assetti organizzativi/amministrativi/contabili ex art. 2086 c.c.",
                    "Verifica sostenibilità dei debiti sui 12 mesi successivi alla assessment_date.",
                ],
                suspended=[] if obj_st != "NON_DETERMINABILE" else ["Accertamento negativo integrale dei segnali art. 3 co. 4 sospeso per dati mancanti."],
                outcome_override=obj_st,
            ))

        # ------------------------------------------------------------------
        # 3) CCII-CPQ-01 — Art. 25-novies
        # ------------------------------------------------------------------
        elif rc == "CCII-CPQ-01":
            if is_consumer_profile or is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO" if is_consumer_profile else "NON_DETERMINABILE",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[], missing=["Consumatore escluso da segnalazioni d'impresa ex art. 25-novies."] if is_consumer_profile else [],
                    indeterminable=["Forma giuridica incerta: soglia AdER (100k/200k/500k) non determinabile."] if is_uncertain_profile else [],
                    blocking_verified=[], blocking_unverified=[],
                    missing_docs=[] if is_consumer_profile else ["Conferma forma giuridica per selezione soglia AdER"],
                    reserved=["Verifica eventuali avvisi PEC ricevuti dagli enti pubblici."],
                    suspended=["Verifica soglie creditori pubblici qualificati sospesa."],
                ))
                continue

            ader_thr_map = rule.parameters.get("ader_thresholds_eur", {})
            ader_thr = float(ader_thr_map.get(legal_form, 500000.0))
            sat, indet, mdocs = [f"Soglia AdER applicabile alla forma '{legal_form}': € {ader_thr:,.2f} (scaduto > 90gg)."], [], []
            entity_statuses: dict[str, str] = {}

            # 1. AdER
            ader_90_f = usable_facts.get("ader_scaduti_oltre_90gg")
            if ader_90_f is not None:
                val = float(ader_90_f.value or 0.0)
                if val > ader_thr:
                    entity_statuses["AdER"] = "VERIFICATO"
                    sat.append(f"AdER scaduto >90gg verificato pari a € {val:,.2f} > € {ader_thr:,.2f}.")
                else:
                    entity_statuses["AdER"] = "NON_SODDISFATTO"
                    sat.append(f"AdER scaduto >90gg pari a € {val:,.2f} <= soglia € {ader_thr:,.2f}.")
            else:
                entity_statuses["AdER"] = "NON_DETERMINABILE"
                indet.append("Anzianità >90gg dei carichi AdER affidati (autodichiarati/definitivi) non documentata in fatto verificato.")
                mdocs.append("Estratto analitico AdER con date notifica/affidamento >90gg rispetto a assessment_date.")

            # 2. INPS
            inps_90_f = usable_facts.get("inps_scaduti_oltre_90gg")
            inps_has_emp_f = usable_facts.get("inps_ha_dipendenti")
            inps_prev_f = usable_facts.get("inps_contributi_anno_precedente")
            if inps_90_f is not None and inps_has_emp_f is not None:
                v_inps = float(inps_90_f.value or 0.0)
                if bool(inps_has_emp_f.value):
                    if inps_prev_f is not None and float(inps_prev_f.value or 0.0) > 0:
                        pct = (v_inps / float(inps_prev_f.value)) * 100.0
                        hit = v_inps > 15000.0 and pct > 30.0
                        entity_statuses["INPS"] = "VERIFICATO" if hit else "NON_SODDISFATTO"
                        sat.append(f"INPS (con dipendenti): € {v_inps:,.2f} ({pct:.1f}% anno prec.) vs >30% e >€15.000.")
                    elif v_inps <= 15000.0:
                        entity_statuses["INPS"] = "NON_SODDISFATTO"
                        sat.append(f"INPS (con dipendenti): € {v_inps:,.2f} <= €15.000.")
                    else:
                        entity_statuses["INPS"] = "NON_DETERMINABILE"
                        indet.append("INPS: mancante dato contributi dovuti anno precedente per calcolo soglia >30%.")
                        mdocs.append("Prospetto contributi INPS dovuti nell'anno precedente.")
                else:
                    hit = v_inps > 5000.0
                    entity_statuses["INPS"] = "VERIFICATO" if hit else "NON_SODDISFATTO"
                    sat.append(f"INPS (senza dipendenti): € {v_inps:,.2f} vs soglia €5.000.")
            else:
                entity_statuses["INPS"] = "NON_DETERMINABILE"
                indet.append("Posizione INPS scaduta >90gg o presenza lavoratori subordinati/parasubordinati non documentata.")
                mdocs.append("Estratto contributivo INPS / DURC con ritardo >90gg e stato dipendenti.")

            # 3. INAIL
            inail_90_f = usable_facts.get("inail_premi_scaduti_oltre_90gg")
            if inail_90_f is not None:
                v_inail = float(inail_90_f.value or 0.0)
                entity_statuses["INAIL"] = "VERIFICATO" if v_inail > 5000.0 else "NON_SODDISFATTO"
                sat.append(f"INAIL premi scaduti >90gg: € {v_inail:,.2f} vs soglia €5.000.")
            else:
                entity_statuses["INAIL"] = "NON_DETERMINABILE"
                indet.append("Posizione INAIL premi scaduti >90gg non documentata.")
                mdocs.append("Estratto conto assicurativo INAIL (>90gg).")

            # 4. AdE IVA (LIPE)
            iva_f = usable_facts.get("ade_iva_lipe_scaduta")
            turn_f = usable_facts.get("volume_affari_anno_precedente")
            if iva_f is not None:
                v_iva = float(iva_f.value or 0.0)
                if v_iva > 20000.0:
                    entity_statuses["AdE_IVA"] = "VERIFICATO"
                    sat.append(f"AdE IVA LIPE scaduta: € {v_iva:,.2f} oltre soglia assoluta €20.000.")
                elif v_iva <= 5000.0:
                    entity_statuses["AdE_IVA"] = "NON_SODDISFATTO"
                    sat.append(f"AdE IVA LIPE scaduta: € {v_iva:,.2f} <= €5.000.")
                elif turn_f is not None and float(turn_f.value or 0.0) > 0:
                    pct_turn = (v_iva / float(turn_f.value)) * 100.0
                    hit = pct_turn >= 10.0
                    entity_statuses["AdE_IVA"] = "VERIFICATO" if hit else "NON_SODDISFATTO"
                    sat.append(f"AdE IVA LIPE scaduta: € {v_iva:,.2f} ({pct_turn:.1f}% vol. affari prec.) vs >=10% e >€5.000.")
                else:
                    entity_statuses["AdE_IVA"] = "NON_DETERMINABILE"
                    indet.append("AdE IVA LIPE tra €5.000 e €20.000: manca volume d'affari dichiarazione anno precedente.")
                    mdocs.append("Dichiarazione IVA anno precedente (volume d'affari) + comunicazioni LIPE.")
            else:
                entity_statuses["AdE_IVA"] = "NON_DETERMINABILE"
                indet.append("Debito IVA risultante da LIPE non documentato.")
                mdocs.append("Comunicazioni LIPE e prospetto versamenti IVA.")

            any_triggered = any(v == "VERIFICATO" for v in entity_statuses.values())
            all_clear = all(v == "NON_SODDISFATTO" for v in entity_statuses.values())
            cpq_outcome: RuleOutcome = "VERIFICATO" if any_triggered else ("NON_SODDISFATTO" if all_clear else "NON_DETERMINABILE")

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status="VERIFICATO",
                dimensional_status="NON_APPLICABILE",
                objective_status=cpq_outcome,
                procedural_status=cpq_outcome,
                satisfied=sat + [f"Esito per ente art. 25-novies: {entity_statuses}"],
                missing=[],
                indeterminable=indet,
                blocking_verified=[],
                blocking_unverified=[],
                missing_docs=mdocs,
                reserved=[
                    "Verifica di eventuali rateizzazioni attive, sospensioni o definizioni agevolate escludenti la segnalazione.",
                    "Verifica di avvenuta ricezione segnalazioni PEC da parte di organo di controllo o imprenditore.",
                ],
                suspended=[] if cpq_outcome != "NON_DETERMINABILE" else ["Verifica completa soglie art. 25-novies parzialmente sospesa."],
                outcome_override=cpq_outcome,
            ))

        # ------------------------------------------------------------------
        # 4) CCII-CNC-01 & 5) CCII-CNC-02 — Composizione Negoziata (Sopra vs Sotto Soglia)
        # ------------------------------------------------------------------
        elif rc in ("CCII-CNC-01", "CCII-CNC-02"):
            wants_minor = rc == "CCII-CNC-02"
            if is_consumer_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_SODDISFATTO",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[], missing=["Soggetto consumatore non imprenditore: CNC non accessibile."],
                    indeterminable=[], blocking_verified=["Soggetto non iscritto / non imprenditore."], blocking_unverified=[],
                    missing_docs=[], reserved=["Valutare gli strumenti del consumatore ex art. 67 o 268 CCII."], suspended=[],
                ))
                continue

            if is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_DETERMINABILE",
                    dimensional_status="NON_DETERMINABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_DETERMINABILE",
                    satisfied=[], missing=[],
                    indeterminable=["Forma giuridica incerta: impossibile verificare il presupposto soggettivo CNC."],
                    blocking_verified=[], blocking_unverified=list(rule.blocking_conditions),
                    missing_docs=gate0_info["missing_p0"] + ["Visura CCIAA"],
                    reserved=["Identificazione e conferma forma giuridica (Human Gate)."],
                    suspended=[f"Accessibilità {rule.procedure_or_instrument} sospesa."],
                ))
                continue

            sat = [f"Profilo imprenditoriale coerente ({legal_form})."]
            if legal_form == "societa_capitali_srl" and protocol_code == "B":
                sat.append("Invarianza forma/protocollo: S.r.l. resta nel Protocollo B economico-contabile.")
            miss, indet, blk_ver, blk_unver, mdocs = [], [], [], [], list(gate0_info["missing_p0"])

            # Verifica iscrizione / cancellazione R.I.
            if ri_cancelled is True:
                blk_ver.append(f"Impresa cancellata dal Registro Imprese (data {ri_cancellation_date.isoformat() if ri_cancellation_date else 'n.d.'}).")
                subj_st = "NON_SODDISFATTO"
            elif ri_cancelled is False:
                sat.append("Iscrizione attiva nel Registro delle Imprese verificata.")
                subj_st = "VERIFICATO"
            else:
                subj_st = "NON_DETERMINABILE"
                indet.append("Stato iscrizione attiva / non cancellazione dal Registro Imprese non verificato con fatto procedurale.")
                mdocs.append("Visura CCIAA aggiornata o attestazione iscrizione attiva R.I.")

            # Verifica dimensionale per instradamento tra art. 12 e art. 25-quater
            if wants_minor:
                if size_qual == "impresa_minore" and debt_mass_verified:
                    dim_st = "VERIFICATO"
                    sat.append("Qualifica dimensionale IMPRESA MINORE confermata su DebtLedger VERIFICATO (art. 25-quater).")
                elif size_qual == "non_minore":
                    dim_st = "NON_SODDISFATTO"
                    miss.append("Impresa NON MINORE: si applica la CNC ordinaria ex artt. 12 ss. (CCII-CNC-01), non l'art. 25-quater.")
                else:
                    dim_st = "NON_DETERMINABILE"
                    indet.append("Qualifica dimensionale non determinabile (atteso esito bivio tra art. 12 e art. 25-quater).")
            else:
                if size_qual == "non_minore":
                    dim_st = "VERIFICATO"
                    sat.append("Qualifica dimensionale NON MINORE accertata (CNC ex artt. 12 ss.).")
                elif size_qual == "impresa_minore" and debt_mass_verified:
                    dim_st = "NON_SODDISFATTO"
                    miss.append("Impresa MINORE: si applica la disciplina sotto soglia ex art. 25-quater (CCII-CNC-02).")
                else:
                    dim_st = "NON_DETERMINABILE"
                    indet.append("Qualifica dimensionale non determinabile (atteso completamento soglie art. 2).")

            # Oggettivo: squilibrio/crisi + attenzione a non inferire continuità da solo EBITDA
            if debt_mass_verified and pfn_info["ebitda_validation_status"] == "VERIFICATO":
                sat.append(
                    f"Dati economico-finanziari verificati (EBITDA={pfn_info['ebitda_value']}, "
                    f"PFN_ESMA_conforme={pfn_info['esma_compliant']}); ragionevole perseguibilità del risanamento "
                    "rimessa al giudizio professionale."
                )
                obj_st = "VERIFICATO"
            else:
                obj_st = "NON_DETERMINABILE"
                if not debt_mass_verified:
                    indet.append(f"Massa debitoria non accertata (DebtLedger={ledger_state}).")
                    mdocs.extend(missing_sources)
                if pfn_info["ebitda_validation_status"] != "VERIFICATO":
                    indet.append("EBITDA OIC 12 / situazione economica non pienamente verificati.")

            # Procedurale: Art. 25-quinquies rispetto ad assessment_date
            proc_st = "VERIFICATO"
            if pending_debtor_filing_fact is not None and bool(pending_debtor_filing_fact.value):
                proc_st = "NON_SODDISFATTO"
                blk_ver.append(
                    "Art. 25-quinquies CCII: pendenza di domanda di accesso a strumento di regolazione "
                    "(o art. 44/54/74) presentata dall'imprenditore."
                )
            elif pending_debtor_filing_fact is None:
                proc_st = "NON_DETERMINABILE"
                indet.append("Art. 25-quinquies CCII: assenza di domande pendenti presentate dal debitore non documentata.")
                blk_unver.append("Assenza domande di regolazione pendenti presentate dal debitore (art. 25-quinquies)")

            if waiver_fact is not None and bool(waiver_fact.value):
                waiver_cutoff = _add_calendar_months(waiver_fact.fact_date, 4)
                if eval_date <= waiver_cutoff:
                    proc_st = "NON_SODDISFATTO"
                    blk_ver.append(
                        f"Art. 25-quinquies CCII: rinuncia a domanda di regolazione del {waiver_fact.fact_date.isoformat()} "
                        f"entro i 4 mesi rispetto ad assessment_date ({eval_date.isoformat()} <= {waiver_cutoff.isoformat()})."
                    )
                else:
                    sat.append(
                        f"Art. 25-quinquies CCII: decorso il blocco di 4 mesi dalla rinuncia "
                        f"({eval_date.isoformat()} > {waiver_cutoff.isoformat()})."
                    )
            elif waiver_fact is None:
                if proc_st == "VERIFICATO":
                    proc_st = "NON_DETERMINABILE"
                indet.append("Art. 25-quinquies CCII: eventuale rinuncia a domande nei 4 mesi precedenti non verificata.")
                blk_unver.append("Assenza di rinunce nei 4 mesi precedenti (art. 25-quinquies)")

            if third_party_lg_fact is not None and bool(third_party_lg_fact.value):
                sat.append(
                    "Istanza di liquidazione giudiziale promossa da terzi pendente: ai sensi dell'art. 25-quinquies "
                    "(post D.Lgs. 136/2024) NON preclude l'accesso alla CNC."
                )

            extra_trans = list(rule.exceptions_and_transitional)
            if agricola_cat["hint_only"] and wants_minor:
                extra_trans.append(agricola_cat["evidence"])

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status=subj_st,
                dimensional_status=dim_st,
                objective_status=obj_st,
                procedural_status=proc_st,
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver, blocking_unverified=blk_unver,
                missing_docs=mdocs,
                reserved=[
                    "Valutazione di ragionevole perseguibilità del risanamento e continuità aziendale (EBITDA positivo NON equivale a risanabilità).",
                    "Analisi strategica rispetto a strumenti giudiziali alternativi.",
                ],
                suspended=[] if (subj_st == "VERIFICATO" and dim_st == "VERIFICATO" and proc_st == "VERIFICATO") else [
                    f"Verifica definitiva accesso {rule.rule_code} subordinata ai dati mancanti e alla valutazione di risanabilità."
                ],
                transitional_notes=extra_trans,
            ))

        # ------------------------------------------------------------------
        # 6) CCII-CNC-MP — Artt. 18-19 Misure protettive (mai automatiche!)
        # ------------------------------------------------------------------
        elif rc == "CCII-CNC-MP":
            if is_consumer_profile or is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO" if is_consumer_profile else "NON_DETERMINABILE",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_DETERMINABILE",
                    satisfied=[], missing=["Consumatore escluso dalla CNC e dalle misure ex artt. 18-19."] if is_consumer_profile else [],
                    indeterminable=["Profilo giuridico incerto."] if is_uncertain_profile else [],
                    blocking_verified=[], blocking_unverified=[], missing_docs=[],
                    reserved=["Valutare eventuali misure protettive proprie del sovraindebitamento."], suspended=[],
                ))
                continue

            sat, miss, indet, blk_ver, blk_unver, mdocs = [], [], [], [], [], []
            proc_st = "NON_DETERMINABILE"
            if mp_pub_fact is not None and bool(mp_pub_fact.value):
                pub_date = mp_pub_fact.fact_date
                sat.append(f"Istanza misure protettive pubblicata nel R.I. in data {pub_date.isoformat()}.")
                petition_cutoff = date.fromordinal(pub_date.toordinal() + 1)
                max_end_date = date.fromordinal(pub_date.toordinal() + 240)
                if mp_petition_fact is not None and bool(mp_petition_fact.value):
                    if mp_petition_fact.fact_date <= petition_cutoff:
                        sat.append(
                            f"Ricorso al Tribunale depositato tempestivamente il {mp_petition_fact.fact_date.isoformat()} "
                            f"(entro il giorno successivo {petition_cutoff.isoformat()} ex art. 19 co. 1)."
                        )
                        if eval_date > max_end_date:
                            proc_st = "NON_SODDISFATTO"
                            blk_ver.append(
                                f"Superato il limite massimo legale di 240 giorni alla assessment_date "
                                f"({eval_date.isoformat()} > {max_end_date.isoformat()})."
                            )
                        elif mp_order_fact is not None:
                            if bool(mp_order_fact.value):
                                proc_st = "VERIFICATO"
                                sat.append("Ordinanza giudiziale di conferma del Tribunale documentata.")
                            else:
                                proc_st = "NON_SODDISFATTO"
                                blk_ver.append("Misure protettive non confermate o revocate dal Tribunale.")
                        else:
                            proc_st = "NON_DETERMINABILE"
                            indet.append("Esito del procedimento di conferma innanzi al Tribunale non ancora documentato.")
                            mdocs.append("Ordinanza del Tribunale ex art. 19 CCII.")
                    else:
                        proc_st = "NON_SODDISFATTO"
                        blk_ver.append(
                            f"Ricorso depositato oltre il giorno successivo alla pubblicazione R.I. "
                            f"({mp_petition_fact.fact_date.isoformat()} > {petition_cutoff.isoformat()}): misure inefficaci ex art. 19 co. 1."
                        )
                else:
                    if eval_date > petition_cutoff:
                        indet.append(
                            f"Pubblicazione R.I. del {pub_date.isoformat()} priva di prova di deposito del ricorso al Tribunale "
                            f"entro {petition_cutoff.isoformat()} (rischio inefficacia ex art. 19 co. 1)."
                        )
                    else:
                        indet.append("Deposito del ricorso al Tribunale ex art. 19 co. 1 non ancora documentato.")
                    mdocs.append("Ricevuta deposito ricorso al Tribunale entro il giorno successivo ex art. 19 co. 1.")
            else:
                indet.append(
                    "Le misure protettive NON sono automatiche con la CNC: nessuna istanza pubblicata nel R.I. "
                    "e nessun ricorso al Tribunale documentati."
                )
                mdocs.append("Istanza misure protettive pubblicata R.I. + ricorso Tribunale entro il giorno successivo.")

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status="VERIFICATO",
                dimensional_status="NON_APPLICABILE",
                objective_status="NON_DETERMINABILE" if proc_st == "NON_DETERMINABILE" else proc_st,
                procedural_status=proc_st,
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[] if proc_st != "NON_SODDISFATTO" else ["Conferma giudiziale ex art. 19 CCII"],
                missing_docs=mdocs,
                reserved=[
                    "Valutazione sull'opportunità di chiedere misure protettive selettive o generali e sostenibilità verso il ceto bancario.",
                    "Ricordare che i diritti di credito dei lavoratori sono esclusi ex lege (art. 18 co. 3).",
                ],
                suspended=["Verifica efficacia delle misure protettive rimessa ad istanza, Tribunale e professionista."],
            ))

        # ------------------------------------------------------------------
        # 7) CCII-CNC-PREM — Art. 25-bis Misure premiali (solo AdE, non esperto, non a ruolo)
        # ------------------------------------------------------------------
        elif rc == "CCII-CNC-PREM":
            if is_consumer_profile or is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO" if is_consumer_profile else "NON_DETERMINABILE",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[], missing=["Non applicabile al consumatore."] if is_consumer_profile else [],
                    indeterminable=["Profilo giuridico incerto."] if is_uncertain_profile else [],
                    blocking_verified=[], blocking_unverified=[], missing_docs=[],
                    reserved=["Verifica strumenti ordinari/sovraindebitamento."], suspended=[],
                ))
                continue

            non_ader = fiscal_buckets["non_ader_tax_eur"]
            ader_cash = fiscal_buckets["ader_cash_eur"]
            unclass = fiscal_buckets["unclassified_tax_eur"]
            sat, miss, indet, blk_ver, mdocs = [], [], [], [], []
            if not debt_mass_verified:
                obj_st = "NON_DETERMINABILE"
                indet.append(
                    f"Perimetro tributario non definitivamente accertato (DebtLedger.stato_dato={ledger_state}): "
                    "impossibile distinguere con certezza tributi non a ruolo vs carichi AdER."
                )
                mdocs.extend(missing_sources)
            elif non_ader > 0.0:
                obj_st = "VERIFICATO"
                sat.append(
                    f"Individuati tributi non ancora iscritti a ruolo pari a € {non_ader:,.2f}: "
                    "la concessione della rateazione (72 rate, o 120 rate con firma dell'esperto) spetta "
                    "all'Agenzia delle Entrate (e MAI direttamente all'esperto)."
                )
            elif ader_cash > 0.0 and unclass == 0.0 and non_ader == 0.0:
                obj_st = "NON_SODDISFATTO"
                miss.append(
                    "Tutti i debiti erariali documentati risultano già iscritti a ruolo AdER: la rateazione speciale "
                    "ex art. 25-bis co. 4 (fino a 72/120 rate) riguarda i soli debiti non ancora iscritti a ruolo."
                )
                blk_ver.append("Assenza di debiti tributari non ancora iscritti a ruolo AdER.")
            else:
                obj_st = "NON_DETERMINABILE"
                indet.append("Manca la separazione documentale tra tributi dovuti non ancora iscritti a ruolo e carichi affidati ad AdER.")
                mdocs.append("Cassetto fiscale / comunicazioni irregolarità non iscritte a ruolo distinto da estratto AdER.")

            cnc_ok_fact = usable_facts.get("esito_idoneo_cnc_art25bis")
            if cnc_ok_fact is not None:
                proc_st = "VERIFICATO" if bool(cnc_ok_fact.value) else "NON_SODDISFATTO"
                if proc_st == "VERIFICATO":
                    sat.append("Esito idoneo della CNC documentato ai sensi dell'art. 25-bis CCII.")
                else:
                    miss.append("Esito CNC non rientrante nelle fattispecie agevolate ex art. 25-bis CCII.")
            else:
                proc_st = "NON_DETERMINABILE"
                indet.append("Esito idoneo della CNC (contratto/accordi pubblicati nel R.I.) non ancora documentato.")

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status="VERIFICATO",
                dimensional_status="NON_APPLICABILE",
                objective_status=obj_st,
                procedural_status=proc_st,
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=["Raggiungimento di esito idoneo CNC e approvazione AdE"],
                missing_docs=mdocs,
                reserved=[
                    "Verifica di 'comprovata e grave situazione di difficoltà' per eventuale estensione a 120 rate ex art. 25-bis co. 4.",
                    "Valutazione discrezionale rimessa all'Agenzia delle Entrate (Circ. 5/E 2026); l'esperto sottoscrive l'istanza ma non concede il beneficio.",
                ],
                suspended=["Applicabilità effettiva delle misure premiali subordinata all'esito della CNC e all'AdE."],
            ))

        # ------------------------------------------------------------------
        # 8) CCII-CNC-TF — Art. 23 co. 2-bis + Art. 4 D.Lgs. 147/2026
        # ------------------------------------------------------------------
        elif rc == "CCII-CNC-TF":
            if is_consumer_profile or is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO" if is_consumer_profile else "NON_DETERMINABILE",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[], missing=["Non applicabile al consumatore."] if is_consumer_profile else [],
                    indeterminable=["Profilo giuridico incerto."] if is_uncertain_profile else [],
                    blocking_verified=[], blocking_unverified=[], missing_docs=[],
                    reserved=["Verifica strumenti applicabili al profilo."], suspended=[],
                ))
                continue

            sat, miss, indet, blk_ver, mdocs = [], [], [], [], []
            trans_notes = list(rule.exceptions_and_transitional)
            eligible_tax = fiscal_buckets["ader_cash_eur"] + fiscal_buckets["non_ader_tax_eur"]
            local_tax = fiscal_buckets["local_regional_tax_eur"]
            inps_inail = fiscal_buckets["inps_total_eur"] + fiscal_buckets["inail_total_eur"]
            eu_res = fiscal_buckets["eu_own_resources_eur"]
            unclass_tax = fiscal_buckets["unclassified_tax_eur"]

            if local_tax_ext_effective:
                sat.append(
                    f"Alla assessment_date ({eval_date.isoformat()} >= 2026-08-12) vige l'Art. 4 D.Lgs. 147/2026 "
                    "(estensione accordo art. 23 co. 2-bis ai tributi di Regioni, Comuni, Province e Città metropolitane)."
                )
                if pending_before_dlgs147:
                    trans_notes.append(
                        f"ATTENZIONE REGIME TEMPORALE: CNC/procedura avviata il {procedure_started_date.isoformat()} "
                        "(anteriore al 12/08/2026): rimettere al professionista la verifica sull'applicabilità pendente "
                        "e sull'organo competente alla sottoscrizione per ciascun ente territoriale."
                    )
            else:
                trans_notes.append(
                    f"Alla assessment_date ({eval_date.isoformat()} < 2026-08-12) NON vige ancora l'Art. 4 D.Lgs. 147/2026: "
                    "tributi regionali e locali esclusi dall'art. 23 co. 2-bis."
                )

            if inps_inail > 0.0:
                sat.append(
                    f"Contributi INPS/INAIL (€ {inps_inail:,.2f}) ESCLUSI ex art. 23 co. 2-bis CCII "
                    "(non trattabili nell'accordo tributario endo-CNC)."
                )
            if eu_res > 0.0:
                sat.append(f"Tributi risorse proprie UE (€ {eu_res:,.2f}) ESCLUSI per legge dall'accordo.")

            if not debt_mass_verified:
                obj_st = "NON_DETERMINABILE"
                indet.append(
                    f"Base debitoria fiscale non accertata (DebtLedger.stato_dato={ledger_state}): "
                    "impossibile qualificare il perimetro dell'accordo ex art. 23 co. 2-bis."
                )
                mdocs.extend(missing_sources)
            else:
                effective_eligible = eligible_tax + (local_tax if local_tax_ext_effective else 0.0)
                if effective_eligible > 0.0:
                    obj_st = "VERIFICATO"
                    sat.append(
                        f"Individuato perimetro tributario astrattamente proponibile in CNC pari a € {effective_eligible:,.2f} "
                        "(accordo consensuale SENZA cram-down)."
                    )
                elif unclass_tax > 0.0:
                    obj_st = "NON_DETERMINABILE"
                    indet.append(
                        f"Debiti tributari/previdenziali aggregati di bilancio (€ {unclass_tax:,.2f}) privi di "
                        "distinzione tra Agenzie fiscali, enti locali, INPS/INAIL e risorse proprie UE."
                    )
                    mdocs.append("Dettaglio analitico codici tributo ed enti impositori.")
                elif inps_inail > 0.0 or eu_res > 0.0 or (local_tax > 0.0 and not local_tax_ext_effective):
                    obj_st = "NON_SODDISFATTO"
                    miss.append("Le sole passività rilevate (INPS/INAIL, risorse UE o locali ante 12/08/2026) non sono negoziabili ex art. 23 co. 2-bis.")
                    blk_ver.append("Passività interamente fuori perimetro art. 23 co. 2-bis CCII.")
                else:
                    obj_st = "NON_SODDISFATTO"
                    miss.append("Nessun debito tributario negoziabile documentato nel DebtLedger.")

            rel_indip = usable_facts.get("relazione_convenienza_art23_co2bis")
            rel_rev = usable_facts.get("relazione_veridicita_revisore_art23_co2bis")
            if rel_indip and bool(rel_indip.value) and rel_rev and bool(rel_rev.value):
                proc_st = "VERIFICATO"
                sat.append("Documentate entrambe le relazioni obbligatorie (convenienza + veridicità revisore legale).")
            elif (rel_indip and not bool(rel_indip.value)) or (rel_rev and not bool(rel_rev.value)):
                proc_st = "NON_SODDISFATTO"
                blk_ver.append("Mancanza o esito negativo di una delle due relazioni obbligatorie ex art. 23 co. 2-bis.")
            else:
                proc_st = "NON_DETERMINABILE"
                indet.append(
                    "Mancano le relazioni obbligatorie ex art. 23 co. 2-bis (professionista indipendente su convenienza "
                    "vs LG + revisore legale su completezza e veridicità dati aziendali)."
                )
                mdocs.append("Relazione di convenienza ex art. 23 co. 2-bis + relazione di veridicità del revisore legale.")

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status="VERIFICATO",
                dimensional_status="NON_APPLICABILE",
                objective_status=obj_st,
                procedural_status=proc_st,
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[
                    "Assenza di cram-down: richiesto consenso espresso dell'Amministrazione Finanziaria / ente locale",
                ],
                missing_docs=mdocs,
                reserved=[
                    "Convenienza della proposta rispetto alla liquidazione giudiziale e gestione separata dei debiti INPS/INAIL.",
                    "Per tributi locali (Art. 4 D.Lgs. 147/2026): verifica organo competente alla sottoscrizione e profili transitori se CNC ante 12/08/2026.",
                ],
                suspended=["Praticabilità effettiva della transazione tributaria in CNC subordinata a consenso ente e relazioni."],
                transitional_notes=trans_notes,
            ))

        # ------------------------------------------------------------------
        # 9) CCII-CS-01 — Art. 25-sexies Concordato Semplificato
        # ------------------------------------------------------------------
        elif rc == "CCII-CS-01":
            if is_consumer_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_SODDISFATTO",
                    procedural_status="NON_SODDISFATTO",
                    satisfied=[], missing=["Consumatore escluso dal concordato semplificato ex art. 25-sexies."],
                    indeterminable=[], blocking_verified=["Soggetto non imprenditore."], blocking_unverified=[],
                    missing_docs=[], reserved=["Valutare procedure da sovraindebitamento del consumatore."], suspended=[],
                ))
                continue

            sat, miss, indet, blk_ver, mdocs = [], [], [], [], []
            peremptory_days = int(rule.parameters.get("peremptory_filing_days", 60))

            if cnc_final_report_fact is not None:
                if not bool(cnc_final_report_fact.value):
                    proc_st = "NON_SODDISFATTO"
                    miss.append("Nessuna CNC conclusa con relazione finale dell'esperto: accesso diretto al concordato semplificato vietato.")
                    blk_ver.append("Assenza di previa CNC conclusa ex art. 17 co. 8 CCII.")
                else:
                    comm_date = cnc_final_report_fact.document_date
                    days_elapsed = (eval_date - comm_date).days
                    sat.append(f"Relazione finale dell'esperto comunicata il {comm_date.isoformat()} ({days_elapsed} gg alla assessment_date).")
                    if days_elapsed < 0:
                        proc_st = "NON_DETERMINABILE"
                        indet.append("Data comunicazione relazione finale successiva ad assessment_date.")
                    elif days_elapsed > peremptory_days:
                        proc_st = "NON_SODDISFATTO"
                        blk_ver.append(
                            f"Decadenza dal termine perentorio di {peremptory_days} giorni ex art. 25-sexies co. 1 "
                            f"({days_elapsed} giorni dalla comunicazione al {eval_date.isoformat()})."
                        )
                    elif cnc_good_faith_fact is None or cnc_art23_unfeasible_fact is None:
                        proc_st = "NON_DETERMINABILE"
                        indet.append(
                            "Mancano le attestazioni espresse dell'esperto nella relazione finale su "
                            "(a) correttezza e buona fede e (b) impraticabilità soluzioni ex art. 23 co. 1 e 2 lett. a) e b)."
                        )
                        mdocs.append("Testo integrale relazione finale dell'esperto ex art. 17 co. 8 CCII.")
                    elif not bool(cnc_good_faith_fact.value) or not bool(cnc_art23_unfeasible_fact.value):
                        proc_st = "NON_SODDISFATTO"
                        blk_ver.append(
                            "Relazione finale priva di attestazione positiva di correttezza/buona fede o di impraticabilità soluzioni art. 23."
                        )
                    else:
                        proc_st = "VERIFICATO"
                        sat.append(
                            f"Attestazioni dell'esperto verificate ed entro il termine perentorio di {peremptory_days} giorni."
                        )
            elif cnc_active_fact is not None and bool(cnc_active_fact.value):
                proc_st = "NON_DETERMINABILE"
                indet.append("CNC in corso: relazione finale dell'esperto ex art. 17 co. 8 non ancora emessa.")
                mdocs.append("Relazione finale dell'esperto a conclusione delle trattative CNC.")
            else:
                proc_st = "NON_SODDISFATTO"
                miss.append(
                    "Concordato semplificato (art. 25-sexies) NON accessibile in via diretta: nessuna CNC svolta/documentata."
                )
                blk_ver.append("Mancanza di previa Composizione Negoziata svolta (art. 25-sexies co. 1 CCII).")

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status="NON_DETERMINABILE" if is_uncertain_profile else "VERIFICATO",
                dimensional_status="NON_APPLICABILE",
                objective_status="NON_DETERMINABILE" if proc_st == "VERIFICATO" else proc_st,
                procedural_status=proc_st,
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[] if proc_st == "NON_SODDISFATTO" else ["Utilità per ciascun creditore e non pregiudizio rispetto a LG"],
                missing_docs=mdocs,
                reserved=[
                    "Verifica dell'utilità ritraibile per ciascun creditore e comparazione rispetto alla liquidazione giudiziale/controllata.",
                    "Predisposizione proposta per cessione dei beni, piano di liquidazione e documenti art. 39 entro 60 giorni.",
                ],
                suspended=["Accesso al concordato semplificato subordinato a relazione finale esperto conforme e termine perentorio."],
            ))

        # ------------------------------------------------------------------
        # 10) CCII-ADR-01 — Artt. 57, 60, 61, 63 + Art. 4 D.Lgs. 147/2026
        # ------------------------------------------------------------------
        elif rc == "CCII-ADR-01":
            if is_consumer_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_SODDISFATTO",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[], missing=["Consumatore escluso da ADR ex artt. 57-63 CCII."],
                    indeterminable=[], blocking_verified=["Soggetto non imprenditore."], blocking_unverified=[],
                    missing_docs=[], reserved=["Valutare strumenti del consumatore."], suspended=[],
                ))
                continue

            sat, miss, indet, blk_ver, mdocs = [], [], [], [], list(gate0_info["missing_p0"])
            trans_notes = list(rule.exceptions_and_transitional)
            if local_tax_ext_effective:
                sat.append("Dal 12/08/2026 (Art. 4 D.Lgs. 147/2026) l'art. 63 e il relativo cram-down si estendono anche a Regioni ed enti locali.")
                if pending_before_dlgs147:
                    trans_notes.append(
                        f"Procedura/trattativa con data anteriore al 12/08/2026 ({procedure_started_date.isoformat()}): verificare regime temporale applicabile."
                    )

            if ri_cancelled is True:
                blk_ver.append("Art. 33 co. 4 CCII: domanda di omologazione ADR presentata da imprenditore cancellato dal R.I. inammissibile.")

            if is_uncertain_profile:
                subj_st = "NON_DETERMINABILE"
                dim_st = "NON_DETERMINABILE"
                indet.append("Forma giuridica incerta.")
            elif size_qual == "non_minore":
                subj_st = "VERIFICATO" if ri_cancelled is False else ("NON_SODDISFATTO" if ri_cancelled is True else "NON_DETERMINABILE")
                dim_st = "VERIFICATO"
                sat.append("Imprenditore non minore legittimato ad ADR ex art. 57 CCII.")
            elif size_qual == "impresa_minore":
                if agricola_cat["certified"]:
                    subj_st = "VERIFICATO" if ri_cancelled is not True else "NON_SODDISFATTO"
                    dim_st = "VERIFICATO"
                    sat.append("Impresa minore agricola certificata da fonte camerale/documentale: ammessa ad ADR ex art. 57 co. 1 e art. 25-quater co. 4.")
                elif agricola_cat["hint_only"]:
                    subj_st = "NON_DETERMINABILE"
                    dim_st = "NON_DETERMINABILE"
                    indet.append(agricola_cat["evidence"])
                    mdocs.append("Visura CCIAA attestante qualifica di imprenditore agricolo (non solo codice ATECO).")
                else:
                    subj_st = "NON_SODDISFATTO" if ri_cancelled is not True else "NON_SODDISFATTO"
                    dim_st = "NON_SODDISFATTO"
                    miss.append("Imprenditore commerciale minore (non agricolo) escluso da ADR ex artt. 57 ss.")
                    blk_ver.append("Imprenditore commerciale sotto soglia ex art. 2 co. 1 lett. d).")
            else:
                subj_st = "VERIFICATO" if ri_cancelled is False else ("NON_SODDISFATTO" if ri_cancelled is True else "NON_DETERMINABILE")
                dim_st = "NON_DETERMINABILE"
                indet.append("Qualifica dimensionale non determinabile: verifica soglie art. 2 necessaria per ADR.")

            if ri_cancelled is None and not is_uncertain_profile and subj_st != "NON_SODDISFATTO":
                indet.append("Assenza di cancellazione dal R.I. (art. 33 co. 4) non verificata su fatto documentale.")
                mdocs.append("Visura CCIAA aggiornata.")

            if debt_mass_verified and pfn_info["ebitda_validation_status"] == "VERIFICATO":
                obj_st = "VERIFICATO"
                sat.append(
                    f"Massa debitoria VERIFICATA (€ {cassa_certe:,.2f}) per calcolo base maggioranze (60%/30%) e quota fiscale/contributiva art. 63."
                )
            else:
                obj_st = "NON_DETERMINABILE"
                if not debt_mass_verified:
                    indet.append(f"Massa debitoria non accertata (DebtLedger.stato_dato={ledger_state}): impossibile calcolare maggioranze 60%/30% e convenienza art. 63.")
                    mdocs.extend(missing_sources)
                if pfn_info["ebitda_validation_status"] != "VERIFICATO":
                    indet.append("Situazione economica / EBITDA non pienamente verificati per sostenibilità pagamento integrale estranei.")

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status=subj_st,
                dimensional_status=dim_st,
                objective_status=obj_st,
                procedural_status="NON_DETERMINABILE" if not blk_ver else "NON_SODDISFATTO",
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[] if blk_ver else ["Adesioni creditori >=60% (o 30%), pagamento integrale estranei e attestazione indipendente"],
                missing_docs=mdocs + ["Piano finanziario con copertura integrale creditori estranei", "Perizia attivo per test convenienza art. 63"],
                reserved=[
                    "Valutazione fattibilità negoziale delle adesioni (60%/30%) ed eventuale efficacia estesa art. 61.",
                    "Verifica requisiti specifici cram-down fiscale/contributivo/locale ex art. 63 co. 4.",
                ],
                suspended=["Omologabilità ADR e transazione art. 63 rimesse a negoziazione, attestazione e Tribunale."],
                transitional_notes=trans_notes,
            ))

        # ------------------------------------------------------------------
        # 11) CCII-PRO-CP — Artt. 64-bis, 84, 88, 112 + Art. 4 D.Lgs. 147/2026
        # ------------------------------------------------------------------
        elif rc == "CCII-PRO-CP":
            if is_consumer_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_SODDISFATTO",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[], missing=["Consumatore escluso da PRO e Concordato Preventivo."],
                    indeterminable=[], blocking_verified=["Soggetto non imprenditore."], blocking_unverified=[],
                    missing_docs=[], reserved=["Valutare strumenti del consumatore."], suspended=[],
                ))
                continue

            sat, miss, indet, blk_ver, mdocs = [], [], [], [], list(gate0_info["missing_p0"])
            trans_notes = list(rule.exceptions_and_transitional)
            if local_tax_ext_effective:
                sat.append("Dal 12/08/2026 (Art. 4 D.Lgs. 147/2026) artt. 64-bis e 88 includono anche tributi regionali e locali.")
                if pending_before_dlgs147:
                    trans_notes.append(
                        f"Procedura anteriore al 12/08/2026 ({procedure_started_date.isoformat()}): verificare regime pendente ante Art. 4 D.Lgs. 147/2026."
                    )

            if ri_cancelled is True:
                blk_ver.append("Art. 33 co. 4 CCII: domanda di concordato preventivo presentata da imprenditore cancellato dal R.I. inammissibile.")

            if agricola_cat["certified"]:
                blk_ver.append("Impresa agricola certificata: esclusa dal Concordato Preventivo e dalla Liquidazione Giudiziale.")
            elif agricola_cat["hint_only"]:
                indet.append(agricola_cat["evidence"])
                mdocs.append("Visura CCIAA per verifica natura commerciale vs agricola.")

            if is_uncertain_profile:
                subj_st = "NON_DETERMINABILE"
                dim_st = "NON_DETERMINABILE"
                indet.append("Forma giuridica incerta.")
            elif size_qual == "impresa_minore":
                subj_st = "NON_SODDISFATTO"
                dim_st = "NON_SODDISFATTO"
                miss.append("Impresa minore non assoggettabile a liquidazione giudiziale: PRO e Concordato Preventivo ordinario esclusi.")
                blk_ver.append("Impresa sotto soglia ex art. 2 co. 1 lett. d).")
            elif size_qual == "non_minore":
                subj_st = "NON_SODDISFATTO" if (ri_cancelled is True or agricola_cat["certified"]) else ("VERIFICATO" if ri_cancelled is False else "NON_DETERMINABILE")
                dim_st = "VERIFICATO"
                sat.append("Qualifica dimensionale NON MINORE compatibile con perimetro PRO / Concordato Preventivo (salva verifica agricola/R.I.).")
            else:
                subj_st = "NON_DETERMINABILE"
                dim_st = "NON_DETERMINABILE"
                indet.append("Qualifica dimensionale non determinabile.")

            if debt_mass_verified:
                sat.append(f"Massa debitoria VERIFICATA (€ {cassa_certe:,.2f}) disponibile per formazione classi art. 85/88/112.")
                obj_st = "VERIFICATO" if pfn_info["ebitda_validation_status"] == "VERIFICATO" else "NON_DETERMINABILE"
                if obj_st != "VERIFICATO":
                    indet.append("EBITDA non pienamente verificato: continuità aziendale non inferibile senza piano industriale/finanziario.")
            else:
                obj_st = "NON_DETERMINABILE"
                indet.append(f"Massa debitoria non accertata (DebtLedger.stato_dato={ledger_state}).")
                mdocs.extend(missing_sources)

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status=subj_st,
                dimensional_status=dim_st,
                objective_status=obj_st,
                procedural_status="NON_DETERMINABILE" if not blk_ver else "NON_SODDISFATTO",
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[] if blk_ver else ["Piano ex art. 87, classamento creditori e attestazione professionista indipendente"],
                missing_docs=mdocs + ["Piano economico-finanziario e formazione classi creditori", "Relazione di stima del valore di liquidazione"],
                reserved=[
                    "Scelta fra Concordato Preventivo in continuità (diretta/indiretta), Concordato liquidatorio (10%/20%) e PRO (art. 64-bis).",
                    "Valutazione sostenibilità del piano e condizioni ex artt. 88 e 112 CCII (un EBITDA positivo non dimostra continuità).",
                ],
                suspended=["Accessibilità concreta e scelta dello strumento giudiziale rimesse al professionista."],
                transitional_notes=trans_notes,
            ))

        # ------------------------------------------------------------------
        # 12) CCII-PERI-CM — Art. 74 ss. + Art. 33 co. 4 (Perimetro)
        # ------------------------------------------------------------------
        elif rc == "CCII-PERI-CM":
            sat, miss, indet, blk_ver, mdocs = [], [], [], [], []
            if is_consumer_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_SODDISFATTO",
                    procedural_status="NON_SODDISFATTO",
                    satisfied=[], missing=["Art. 74 CCII esclude espressamente il consumatore."],
                    indeterminable=[], blocking_verified=["Qualifica persona fisica consumatore."], blocking_unverified=[],
                    missing_docs=[], reserved=["Valutare Ristrutturazione debiti del consumatore (art. 67)."], suspended=[],
                ))
                continue

            if ri_cancelled is True:
                blk_ver.append(
                    "Art. 33, comma 4, CCII: la domanda di concordato minore presentata dall'imprenditore cancellato "
                    "dal Registro delle Imprese è inammissibile in ogni caso (anche individuale e liquidatorio)."
                )

            if is_uncertain_profile:
                subj_st, dim_st = "NON_DETERMINABILE", "NON_DETERMINABILE"
                indet.append("Forma giuridica incerta.")
            elif size_qual == "non_minore":
                if agricola_cat["certified"] or startup_cat["certified"]:
                    subj_st = "VERIFICATO" if ri_cancelled is False else ("NON_SODDISFATTO" if ri_cancelled is True else "NON_DETERMINABILE")
                    dim_st = "VERIFICATO"
                    sat.append("Qualifica speciale certificata da fonte documentale/camerale: soggetta a verifica concordato minore ex art. 74.")
                else:
                    subj_st = "NON_SODDISFATTO"
                    dim_st = "NON_SODDISFATTO"
                    miss.append("Imprenditore commerciale NON MINORE: escluso dal concordato minore ex art. 74 CCII.")
                    blk_ver.append("Superamento soglie ex art. 2 co. 1 lett. d) su impresa commerciale.")
                    if agricola_cat["hint_only"]:
                        indet.append(agricola_cat["evidence"])
                    if startup_cat["hint_only"]:
                        indet.append(startup_cat["evidence"])
            elif size_qual == "impresa_minore" and debt_mass_verified:
                subj_st = "NON_SODDISFATTO" if ri_cancelled is True else ("VERIFICATO" if ri_cancelled is False else "NON_DETERMINABILE")
                dim_st = "VERIFICATO"
                sat.append(
                    "Perimetro informativo concordato minore (art. 74 CCII): impresa minore non fallibile — "
                    "strumento fuori dai Protocolli operativi A/B, da approfondire a cura del professionista."
                )
            else:
                subj_st = "NON_SODDISFATTO" if ri_cancelled is True else "NON_DETERMINABILE"
                dim_st = "NON_DETERMINABILE"
                indet.append("Qualifica dimensionale o stato iscrizione/cancellazione R.I. non determinabile.")
                mdocs.append("Visura CCIAA storica/aggiornata + verifica soglie art. 2 CCII.")

            if agricola_cat["hint_only"]:
                mdocs.append("Certificazione camerale impresa agricola (ATECO insufficiente da solo).")
            if startup_cat["hint_only"]:
                mdocs.append("Visura CCIAA sezione speciale start-up innovative.")

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status=subj_st,
                dimensional_status=dim_st,
                objective_status="NON_DETERMINABILE" if not blk_ver else "NON_SODDISFATTO",
                procedural_status="NON_SODDISFATTO" if ri_cancelled is True else "NON_DETERMINABILE",
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[] if blk_ver else ["Verifica assenza atti in frode (art. 77) e continuità / risorse esterne"],
                missing_docs=mdocs,
                reserved=[
                    "Inquadramento nel perimetro sovraindebitamento (OCC) e scelta tra CNC sotto soglia (art. 25-quater) e Concordato Minore (art. 74).",
                    "Verifica puntuale della continuità aziendale/professionale o dell'apporto esterno nel concordato liquidatorio.",
                ],
                suspended=["Perimetro non supportato da motore piani A/B in Fase 3: valutazione rimessa al professionista."],
            ))

        # ------------------------------------------------------------------
        # 13) CCII-PERI-CONS — Art. 67 ss. Ristrutturazione consumatore (Perimetro)
        # ------------------------------------------------------------------
        elif rc == "CCII-PERI-CONS":
            if is_consumer_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="VERIFICATO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_DETERMINABILE",
                    satisfied=[
                        "Profilo 'persona_fisica_non_imprenditore' separato dai Protocolli A/B: "
                        "rientra nel perimetro informativo dell'art. 67 CCII (OCC)."
                    ],
                    missing=[],
                    indeterminable=[
                        "Origine integralmente consumeristica dei debiti e requisiti soggettivi ex art. 69 CCII "
                        "(assenza colpa grave/malafede/frode) da verificare con OCC e professionista."
                    ],
                    blocking_verified=[],
                    blocking_unverified=["Verifica assenza debiti d'impresa/promiscui e requisito meritevolezza art. 69 CCII"],
                    missing_docs=["Relazione particolareggiata OCC ex art. 68 CCII e verifica origine singole posizioni debitorie"],
                    reserved=[
                        "Verifica qualificazione di consumatore puro ex art. 2 co. 1 lett. e) in presenza di eventuali fideiussioni societarie.",
                        "Valutazione meritevolezza ex art. 69 CCII (mai assimilabile a Protocollo A/B).",
                    ],
                    suspended=["Perimetro consumatore non coperto da Protocolli A/B in Fase 3."],
                ))
            elif is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_DETERMINABILE",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_DETERMINABILE",
                    satisfied=[], missing=[], indeterminable=["Forma giuridica incerta."],
                    blocking_verified=[], blocking_unverified=[], missing_docs=["Conferma profilo giuridico"],
                    reserved=["Accertare se persona fisica non imprenditore o soggetto collettivo/individuale."],
                    suspended=["Perimetro consumatore sospeso."],
                ))
            else:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_APPLICABILE",
                    objective_status="NON_SODDISFATTO",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[],
                    missing=[f"Profilo '{legal_form}' non è una persona fisica consumatore ex art. 2 co. 1 lett. e) CCII."],
                    indeterminable=[],
                    blocking_verified=["Soggetto esercente attività d'impresa o ente collettivo (escluso da art. 67 CCII)."],
                    blocking_unverified=[],
                    missing_docs=[],
                    reserved=["Verifica solo per eventuale persona fisica coobbligata/socio con debiti esclusivamente personali."],
                    suspended=[],
                ))

        # ------------------------------------------------------------------
        # 14) CCII-PERI-LC — Art. 268 ss. Liquidazione Controllata (Perimetro)
        # ------------------------------------------------------------------
        elif rc == "CCII-PERI-LC":
            sat, miss, indet, blk_ver, mdocs = [], [], [], [], []
            petitioner_fact = usable_facts.get("soggetto_istante_liquidazione_controllata")
            occ_incap_fact = usable_facts.get("attestazione_occ_incapienza_art268_co3")
            overdue_debt_fact = usable_facts.get("debiti_scaduti_non_pagati_art268_co2")
            cred_min_eur = float(rule.parameters.get("creditor_petition_min_overdue_debt_eur", 50000.0))

            if is_uncertain_profile:
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_DETERMINABILE",
                    dimensional_status="NON_DETERMINABILE",
                    objective_status="NON_DETERMINABILE",
                    procedural_status="NON_DETERMINABILE",
                    satisfied=[], missing=[], indeterminable=["Forma giuridica incerta."],
                    blocking_verified=[], blocking_unverified=[], missing_docs=["Visura CCIAA / conferma profilo"],
                    reserved=["Verifica perimetro Liquidazione Controllata vs Liquidazione Giudiziale."],
                    suspended=["Delimitazione liquidatoria sospesa."],
                ))
                continue

            if not is_consumer_profile and size_qual == "non_minore" and not (agricola_cat["certified"] or startup_cat["certified"]):
                schede.append(_make_evaluation(
                    rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                    subjective_status="NON_SODDISFATTO",
                    dimensional_status="NON_SODDISFATTO",
                    objective_status="NON_SODDISFATTO",
                    procedural_status="NON_APPLICABILE",
                    satisfied=[],
                    missing=[
                        "Imprenditore commerciale NON MINORE: soggetto a Liquidazione Giudiziale (art. 121 CCII), "
                        "non a Liquidazione Controllata (art. 268 CCII)."
                    ],
                    indeterminable=[],
                    blocking_verified=["Soggetto assoggettabile a Liquidazione Giudiziale."],
                    blocking_unverified=[],
                    missing_docs=[],
                    reserved=["Benchmark liquidatorio da riferire alla Liquidazione Giudiziale ex art. 121 CCII."],
                    suspended=[],
                ))
                continue

            # Soggetto sovraindebitato (consumatore o impresa minore / agricola verificata) o qualifica non determinabile
            if is_consumer_profile or (size_qual == "impresa_minore" and debt_mass_verified) or agricola_cat["certified"]:
                subj_st = "VERIFICATO"
                dim_st = "NON_APPLICABILE" if is_consumer_profile else "VERIFICATO"
                sat.append(
                    "Ramo A — Istanza del DEBITORE (art. 268 co. 1): legittimazione aperta senza alcuna soglia minima di debito "
                    "(accessibile anche all'imprenditore individuale persona fisica cancellato ex art. 33 co. 1-bis)."
                )
            else:
                subj_st = "VERIFICATO" if is_entrepreneurial_profile else "NON_DETERMINABILE"
                dim_st = "NON_DETERMINABILE"
                indet.append("Qualifica non fallibile (impresa minore vs non minore) non ancora definita per distinguere Liquidazione Controllata vs Giudiziale.")
                mdocs.extend(missing_sources)

            # Distinzione esplicita Ramo B (istanza creditore/PM)
            if petitioner_fact is not None and str(petitioner_fact.value or "").strip().lower() in ("creditore", "pm", "terzo"):
                sat.append("Ramo B — Istanza di CREDITORE / PM (art. 268 co. 2–3): richiesti insolvenza e debiti scaduti >= € 50.000.")
                if occ_incap_fact is not None and bool(occ_incap_fact.value) and legal_form in ("persona_fisica_non_imprenditore", "impresa_individuale"):
                    proc_st = "NON_SODDISFATTO"
                    obj_st = "NON_SODDISFATTO"
                    blk_ver.append(
                        "Art. 268 co. 3 CCII: attestazione OCC che non è possibile acquisire attivo distribuibile "
                        "preclude l'apertura su istanza del creditore contro persona fisica."
                    )
                elif overdue_debt_fact is not None:
                    scad_val = float(overdue_debt_fact.value or 0.0)
                    if scad_val < cred_min_eur:
                        proc_st = "NON_SODDISFATTO"
                        obj_st = "NON_SODDISFATTO"
                        blk_ver.append(
                            f"Art. 268 co. 2 CCII: debiti scaduti e non pagati (€ {scad_val:,.2f}) inferiori alla soglia "
                            f"legale di € {cred_min_eur:,.2f} per istanza del creditore."
                        )
                    else:
                        proc_st = "NON_DETERMINABILE"
                        obj_st = "NON_DETERMINABILE"
                        sat.append(
                            f"Soglia di procedibilità su istanza creditore (€ {scad_val:,.2f} >= € {cred_min_eur:,.2f}) soddisfatta."
                        )
                        indet.append("Verifica dello stato di insolvenza e di eventuale attestazione OCC ex art. 268 co. 3 rimessa al professionista.")
                else:
                    proc_st = "NON_DETERMINABILE"
                    obj_st = "NON_DETERMINABILE"
                    indet.append("Ammontare dei soli debiti scaduti e non pagati ex art. 268 co. 2 non documentato per istanza del creditore.")
                    mdocs.append("Dettaglio debiti scaduti e non pagati per filtro € 50.000 su istanza creditore.")
            elif petitioner_fact is not None and str(petitioner_fact.value or "").strip().lower() == "debitore":
                obj_st = "VERIFICATO" if subj_st == "VERIFICATO" else "NON_DETERMINABILE"
                proc_st = "NON_DETERMINABILE"
                sat.append("Ramo A — Istanza del DEBITORE documentata: nessuna soglia minima di debito applicabile ex art. 268 co. 1.")
                indet.append("Verifica dello stato di sovraindebitamento e relazione OCC riservata al professionista.")
            else:
                obj_st = "NON_DETERMINABILE"
                proc_st = "NON_DETERMINABILE"
                indet.append(
                    "Soggetto istante non specificato: per istanza del debitore nessuna soglia minima (art. 268 co. 1); "
                    "per istanza di creditore/PM occorrono debiti scaduti >= € 50.000, insolvenza e verifica OCC ex co. 2–3."
                )

            schede.append(_make_evaluation(
                rule, assessment_date=eval_date, simulation_mode=simulation_mode,
                subjective_status=subj_st,
                dimensional_status=dim_st,
                objective_status=obj_st,
                procedural_status=proc_st,
                satisfied=sat, missing=miss, indeterminable=indet,
                blocking_verified=blk_ver,
                blocking_unverified=[] if blk_ver else ["Relazione OCC (art. 269) e verifica presupposti esdebitazione (solo persona fisica)"],
                missing_docs=mdocs,
                reserved=[
                    "Valutazione comparata tra Liquidazione Controllata e soluzioni conservative (CNC sotto soglia / Concordato Minore / art. 67).",
                    "Verifica accesso all'esdebitazione ex art. 282 o art. 283 CCII (esclusivamente per persona fisica, mai per S.r.l.).",
                ],
                suspended=["Perimetro informativo: apertura e strategia liquidatoria riservate al professionista e all'OCC."],
            ))

    # Classificazione della rosa delle alternative (NESSUNA raccomandazione automatica!)
    potenzialmente_approfondire: list[dict[str, Any]] = []
    esclusi: list[dict[str, Any]] = []
    sospesi_dati: list[dict[str, Any]] = []
    perimetro_sovra: list[dict[str, Any]] = []
    allerta_cards: list[dict[str, Any]] = []

    for ev in schede:
        code = ev["rule_code"]
        entry = {
            "rule_code": code,
            "procedure_or_instrument": ev["procedure_or_instrument"],
            "normative_reference": ev["normative_reference"],
            "deterministic_outcome": ev["deterministic_outcome"],
            "professional_approval_status": ev["professional_approval_status"],
            "active_in_production": ev["active_in_production"],
            "execution_mode": ev["execution_mode"],
            "subjective_requirement_status": ev["subjective_requirement_status"],
            "dimensional_requirement_status": ev["dimensional_requirement_status"],
            "objective_requirement_status": ev["objective_requirement_status"],
            "procedural_requirement_status": ev["procedural_requirement_status"],
            "reserved_to_professional": ev["reserved_to_professional"],
        }
        if code in ("CCII-ALL-01", "CCII-CPQ-01"):
            allerta_cards.append(entry)
        elif code in ("CCII-PERI-CM", "CCII-PERI-CONS", "CCII-PERI-LC"):
            perimetro_sovra.append(entry)
        elif ev["deterministic_outcome"] == "NON_SODDISFATTO":
            esclusi.append(entry)
        elif ev["deterministic_outcome"] == "VERIFICATO":
            potenzialmente_approfondire.append(entry)
        else:
            sospesi_dati.append(entry)

    novita_normative = [
        {
            "norm": "Art. 4, D.Lgs. 7 agosto 2026, n. 147 (G.U. n. 185 dell'11/08/2026)",
            "effective_from": "2026-08-12",
            "applicable_at_assessment_date": local_tax_ext_effective,
            "transitional_warning": pending_before_dlgs147,
            "scope": "Estensione accordi/transazione fiscale e cram-down (artt. 23 co. 2-bis, 63, 64-bis, 88, 245, 284-bis CCII) ai tributi di Regioni, Comuni, Province e Città metropolitane.",
        }
    ]

    return {
        "matrix_version": "DossierLex-CCII-Matrix-v3.0-Simulation",
        "execution_mode": "SIMULAZIONE_NON_ATTIVA_IN_PRODUZIONE" if simulation_mode else "CONTROLLO_APPROVAZIONE_ATTIVO",
        "simulation_mode": simulation_mode,
        "assessment_date": eval_date.isoformat(),
        "normative_version": catalog.catalog_version,
        "normative_snapshot_date": catalog.normative_snapshot_date.isoformat(),
        "catalog_sha256": catalog_sha256,
        "catalog_approval_summary": {
            "total_rules": len(catalog.rules),
            "pending_approval_count": sum(1 for r in catalog.rules if r.professional_approval_status == "PENDING_APPROVAL"),
            "approved_count": sum(1 for r in catalog.rules if r.professional_approval_status == "APPROVED"),
            "approved_but_inactive_count": sum(
                1 for r in catalog.rules if r.professional_approval_status == "APPROVED" and not r.active_in_production
            ),
            "active_in_production_count": sum(1 for r in catalog.rules if _is_production_active(r)),
            "suspended_legislative_count": len(catalog.suspended_legislative_rules),
            "any_rule_active_in_production": any(_is_production_active(r) for r in catalog.rules),
        },
        "automatic_recommendation": None,
        "human_gate_required": True,
        "outcome_disclaimer": OUTCOME_DISCLAIMER,
        "profile_snapshot": {
            "legal_form_profile": legal_form,
            "accounting_regime": accounting_regime,
            "ccii_size_qualification": size_qual,
            "classifier_size_qualification": raw_classifier_size_qual,
            "dimensional_contract": dim_contract,
            "protocol_code": protocol_code,
            "gate0": gate0_info,
            "debt_ledger_status": ledger_state,
            "debt_mass_verified": debt_mass_verified,
            "debt_cassa_certe": cassa_certe,
            "debt_perimeter": debt_perimeter,
            "reconciliation_required_count": len(reconciliation_items),
            "pfn_esma": pfn_info,
            "fiscal_debt_buckets": fiscal_buckets,
            "special_categories": {
                "impresa_agricola": agricola_cat,
                "startup_innovativa": startup_cat,
            },
        },
        "schede_valutazione": schede,
        "strumenti_con_presupposti_formali_da_approfondire": potenzialmente_approfondire,
        "strumenti_esclusi_su_fatti_documentati": esclusi,
        "strumenti_sospesi_dati_insufficienti": sospesi_dati,
        "perimetro_non_supportato_sovraindebitamento": perimetro_sovra,
        "allerta_e_segnalazioni": allerta_cards,
        "novita_normative_applicabili": novita_normative,
        "regole_sospese_non_definitive": [item.model_dump(mode="json") for item in catalog.suspended_legislative_rules],
        "rejected_or_unverified_procedural_facts": rejected_facts,
        "reserved_professional_decisions": [
            "Scelta finale dello strumento giuridico (nessuna raccomandazione automatica emessa dal sistema).",
            "Validazione di ragionevole perseguibilità del risanamento, continuità aziendale e fattibilità dei flussi (EBITDA positivo non costituisce prova di risanabilità).",
            "Approvazione formale delle schede normative nel catalogo prima di qualsiasi attivazione in produzione.",
        ],
    }
