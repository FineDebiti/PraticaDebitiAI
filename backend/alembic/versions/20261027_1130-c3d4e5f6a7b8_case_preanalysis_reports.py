"""case_preanalysis_reports table for persistent preanalysis report versions and continuous feedback regeneration

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-27 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'case_preanalysis_reports',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('case_id', sa.String(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('report_data', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='generated'),
        sa.Column('applied_rules_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_instructions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_preanalysis_reports_case_id'), 'case_preanalysis_reports', ['case_id'], unique=False)
    op.create_index(op.f('ix_case_preanalysis_reports_version'), 'case_preanalysis_reports', ['version'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_case_preanalysis_reports_version'), table_name='case_preanalysis_reports')
    op.drop_index(op.f('ix_case_preanalysis_reports_case_id'), table_name='case_preanalysis_reports')
    op.drop_table('case_preanalysis_reports')
