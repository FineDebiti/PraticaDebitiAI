"""Servizio applicativo Fase 1: assessment read-only e conferma operatore con audit."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.entities import Case, Company, FieldEdit, FinancialStatement
from app.services.protocols.classifier import (
    ACCOUNTING_REGIME_LABELS,
    ACCOUNTING_REGIMES,
    CCII_SIZE_LABELS,
    DOSSIER_COMPLETENESS_STATUSES,
    LEGAL_FORM_LABELS,
    LEGAL_FORM_PROFILES,
    classify_case_dimensions,
    protocol_code_for_profile,
)
from app.services.protocols.gate0 import evaluate_gate0


def _load_case_or_404(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Pratica non trovata")
    return case


def _load_client_statements(db: Session, case: Case) -> tuple[list[Company], list[FinancialStatement]]:
    client_companies = [c for c in (case.companies or []) if (c.role or "cliente") == "cliente"]
    company_ids = [c.id for c in client_companies]
    statements: list[FinancialStatement] = []
    if company_ids:
        statements = (
            db.query(FinancialStatement)
            .filter(FinancialStatement.company_id.in_(company_ids))
            .all()
        )
    return client_companies, statements


def get_protocol_assessment(db: Session, case_id: str) -> dict[str, Any]:
    """Calcola classificazione tridimensionale e Gate 0 in sola lettura (zero commit su DB)."""
    case = _load_case_or_404(db, case_id)
    client_companies, statements = _load_client_statements(db, case)

    eff_profile_override = case.debtor_profile_confirmed
    eff_regime_override = case.accounting_regime_confirmed

    cls = classify_case_dimensions(
        db,
        case,
        effective_profile_override=eff_profile_override,
        effective_regime_override=eff_regime_override,
    )
    gate0 = evaluate_gate0(case, cls, statements, client_companies)

    effective_profile = gate0.effective_legal_form_profile
    effective_regime = gate0.effective_accounting_regime
    effective_protocol = gate0.effective_protocol_code

    return {
        "case_id": case.id,
        "detected": {
            "legal_form_profile": cls.legal_form_profile,
            "legal_form_label": cls.legal_form_label,
            "legal_form_confidence": cls.legal_form_confidence,
            "legal_form_evidence": cls.legal_form_evidence,
            "accounting_regime": cls.accounting_regime,
            "accounting_regime_label": cls.accounting_regime_label,
            "accounting_regime_evidence": cls.accounting_regime_evidence,
            "ccii_size_qualification": cls.ccii_size_qualification,
            "ccii_size_label": cls.ccii_size_label,
            "ccii_size_evidence": cls.ccii_size_evidence,
            "ccii_metrics_by_year": cls.ccii_metrics_by_year,
            "protocol_code": protocol_code_for_profile(cls.legal_form_profile),
        },
        "confirmed": {
            "debtor_profile_confirmed": case.debtor_profile_confirmed,
            "accounting_regime_confirmed": case.accounting_regime_confirmed,
            "protocol_code": case.protocol_code,
            "dossier_completeness_status": case.dossier_completeness_status or "in_raccolta",
            "protocol_confirmed_at": case.protocol_confirmed_at.isoformat() if case.protocol_confirmed_at else None,
        },
        "effective": {
            "legal_form_profile": effective_profile,
            "legal_form_label": LEGAL_FORM_LABELS.get(effective_profile, effective_profile),
            "accounting_regime": effective_regime,
            "accounting_regime_label": ACCOUNTING_REGIME_LABELS.get(effective_regime, effective_regime),
            "ccii_size_qualification": cls.ccii_size_qualification,
            "ccii_size_label": CCII_SIZE_LABELS.get(cls.ccii_size_qualification, cls.ccii_size_qualification),
            "protocol_code": effective_protocol,
            "supported_by_protocol": effective_protocol in ("A", "B"),
            "dossier_completeness_status": gate0.dossier_completeness_status,
            "conclusivity_level": gate0.conclusivity_level,
        },
        "gate0": {
            "conclusivity_level": gate0.conclusivity_level,
            "source_inventory": gate0.source_inventory,
            "duplicate_groups": gate0.duplicate_groups,
            "documenti_indispensabili_p0": gate0.documenti_indispensabili_p0,
            "documenti_p1_p2": gate0.documenti_p1_p2,
            "dati_verificati_fonti": gate0.dati_verificati_fonti,
            "dati_non_disponibili": gate0.dati_non_disponibili,
            "anomalie_gate0": gate0.anomalie_gate0,
            "decisioni_sospese": gate0.decisioni_sospese,
        },
    }


def confirm_case_protocol(
    db: Session,
    case_id: str,
    *,
    debtor_profile_confirmed: str,
    accounting_regime_confirmed: Optional[str] = None,
    dossier_completeness_status: str = "in_raccolta",
    operator: str = "operatore",
    reason: str = "",
) -> dict[str, Any]:
    """Salva la conferma/override operatore su Case e registra ogni variazione in FieldEdit."""
    case = _load_case_or_404(db, case_id)

    if debtor_profile_confirmed not in LEGAL_FORM_PROFILES:
        raise HTTPException(422, f"Profilo giuridico non valido: {debtor_profile_confirmed}")
    if accounting_regime_confirmed is not None and accounting_regime_confirmed not in ACCOUNTING_REGIMES:
        raise HTTPException(422, f"Regime contabile non valido: {accounting_regime_confirmed}")
    if dossier_completeness_status not in DOSSIER_COMPLETENESS_STATUSES:
        raise HTTPException(422, f"Stato completezza fascicolo non valido: {dossier_completeness_status}")

    cls = classify_case_dimensions(db, case)
    new_protocol_code = protocol_code_for_profile(debtor_profile_confirmed)
    eff_reason = (reason or "").strip() or "Conferma classificazione metodologica / Gate 0"
    eff_operator = (operator or "").strip() or "operatore"

    changes: list[tuple[str, Any, Any]] = [
        ("debtor_profile_detected", case.debtor_profile_detected, cls.legal_form_profile),
        ("accounting_regime_detected", case.accounting_regime_detected, cls.accounting_regime),
        ("debtor_profile_confirmed", case.debtor_profile_confirmed, debtor_profile_confirmed),
        ("accounting_regime_confirmed", case.accounting_regime_confirmed, accounting_regime_confirmed),
        ("protocol_code", case.protocol_code, new_protocol_code),
        ("dossier_completeness_status", case.dossier_completeness_status, dossier_completeness_status),
    ]

    audited_fields = {
        "debtor_profile_confirmed",
        "accounting_regime_confirmed",
        "protocol_code",
        "dossier_completeness_status",
    }

    for field_name, old_val, new_val in changes:
        if field_name in audited_fields and old_val != new_val:
            db.add(
                FieldEdit(
                    case_id=case.id,
                    entity_type="case_protocol",
                    entity_id=case.id,
                    field=field_name,
                    old_value="" if old_val is None else str(old_val),
                    new_value="" if new_val is None else str(new_val),
                    operator=eff_operator,
                    reason=eff_reason,
                )
            )
        setattr(case, field_name, new_val)

    case.protocol_confirmed_at = datetime.utcnow()
    db.commit()
    db.refresh(case)
    return get_protocol_assessment(db, case.id)
