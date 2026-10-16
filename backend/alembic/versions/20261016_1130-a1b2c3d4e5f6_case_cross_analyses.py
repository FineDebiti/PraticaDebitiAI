"""case_cross_analyses table for cross-document synthesis

Revision ID: a1b2c3d4e5f6
Revises: 6f1aa56b9e85
Create Date: 2026-10-16 11:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6f1aa56b9e85'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'case_cross_analyses',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('case_id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='completed'),
        sa.Column('incongruenze', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('duplicazioni', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('dati_mancanti', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('scenari', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('richieste_prioritarie', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('note_per_il_titolare', sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column('raw_response', sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column('duration_s', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_case_cross_analyses_case_id'), 'case_cross_analyses', ['case_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_case_cross_analyses_case_id'), table_name='case_cross_analyses')
    op.drop_table('case_cross_analyses')

