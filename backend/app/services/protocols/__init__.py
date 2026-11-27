"""Fase 1 Protocolli Metodologici A/B: classificazione 3D e Gate 0."""

from app.services.protocols.classifier import (
    ACCOUNTING_REGIMES,
    CCII_SIZE_QUALIFICATIONS,
    CCII_THRESHOLDS,
    DOSSIER_COMPLETENESS_STATUSES,
    LEGAL_FORM_PROFILES,
    ClassificationResult,
    classify_case_dimensions,
    protocol_code_for_profile,
)
from app.services.protocols.gate0 import Gate0Result, evaluate_gate0
from app.services.protocols.ccii_matrix import (
    CciiRuleDefinition,
    CciiRulesCatalog,
    ProceduralFactRecord,
    evaluate_ccii_matrix,
    load_ccii_catalog,
)
from app.services.protocols.debt_ledger import build_debt_ledger
from app.services.protocols.formula_engine import run_formula_engine
from app.services.protocols.service import (
    confirm_case_protocol,
    get_ccii_matrix_simulation,
    get_deterministic_analysis,
    get_protocol_assessment,
)

__all__ = [
    "ACCOUNTING_REGIMES",
    "CCII_SIZE_QUALIFICATIONS",
    "CCII_THRESHOLDS",
    "DOSSIER_COMPLETENESS_STATUSES",
    "LEGAL_FORM_PROFILES",
    "ClassificationResult",
    "Gate0Result",
    "CciiRuleDefinition",
    "CciiRulesCatalog",
    "ProceduralFactRecord",
    "classify_case_dimensions",
    "protocol_code_for_profile",
    "evaluate_gate0",
    "build_debt_ledger",
    "run_formula_engine",
    "evaluate_ccii_matrix",
    "load_ccii_catalog",
    "get_protocol_assessment",
    "get_deterministic_analysis",
    "get_ccii_matrix_simulation",
    "confirm_case_protocol",
]
