"""Add Case protocol classification and Gate 0 confirmation columns

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-26 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cases", sa.Column("debtor_profile_detected", sa.String(), nullable=True))
    op.add_column("cases", sa.Column("debtor_profile_confirmed", sa.String(), nullable=True))
    op.add_column("cases", sa.Column("accounting_regime_detected", sa.String(), nullable=True))
    op.add_column("cases", sa.Column("accounting_regime_confirmed", sa.String(), nullable=True))
    op.add_column("cases", sa.Column("protocol_code", sa.String(), nullable=True))
    op.add_column(
        "cases",
        sa.Column(
            "dossier_completeness_status",
            sa.String(),
            nullable=False,
            server_default="in_raccolta",
        ),
    )
    op.add_column("cases", sa.Column("protocol_confirmed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cases") as batch_op:
        batch_op.drop_column("protocol_confirmed_at")
        batch_op.drop_column("dossier_completeness_status")
        batch_op.drop_column("protocol_code")
        batch_op.drop_column("accounting_regime_confirmed")
        batch_op.drop_column("accounting_regime_detected")
        batch_op.drop_column("debtor_profile_confirmed")
        batch_op.drop_column("debtor_profile_detected")
