import pytest
from app.models import RealEstate, TaxDebtStatement, TaxDebtItem, FieldEdit
from app.services.corrections import apply_corrections, CorrectionError


def test_apply_corrections_real_estate(db_session, sample_case):
    re = RealEstate(
        case_id=sample_case.id,
        kind="Fabbricato A/2",
        category="A/2",
        cadastral_income=500.0,
        cadastral_value=63000.0,
        is_primary_residence=False,
    )
    db_session.add(re)
    db_session.commit()

    # Apply correction: toggle primary residence
    updated = apply_corrections(
        db_session, sample_case.id, "real_estate", re.id,
        changes={"is_primary_residence": True},
        reason="Correzione operatore: prima casa",
        operator="Operatore Test"
    )

    assert updated.is_primary_residence is True
    # Cadastral value recomputed with prima casa multiplier 110: 500 * 1.05 * 110 = 57,750.0
    assert updated.cadastral_value == 57750.0

    # Audit check in FieldEdit table
    edits = db_session.query(FieldEdit).filter_by(entity_id=re.id).all()
    assert len(edits) == 1
    assert edits[0].field == "is_primary_residence"
    assert edits[0].old_value == "False"
    assert edits[0].new_value == "True"
    assert edits[0].reason == "Correzione operatore: prima casa"


def test_apply_corrections_invalid_type(db_session, sample_case):
    with pytest.raises(CorrectionError):
        apply_corrections(db_session, sample_case.id, "invalid_type", "123", {"field": "val"})
