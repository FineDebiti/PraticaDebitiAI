"""studio_rules table for persistent studio knowledge & continuous training

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-20 15:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'studio_rules',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('case_id', sa.String(), nullable=True),
        sa.Column('client_name', sa.String(), nullable=False, server_default=''),
        sa.Column('scope', sa.String(), nullable=False, server_default='global'),
        sa.Column('scope_title', sa.String(), nullable=False, server_default='Generale'),
        sa.Column('category', sa.String(), nullable=False, server_default='Generale'),
        sa.Column('user_comment', sa.Text(), nullable=False, server_default=''),
        sa.Column('rule_title', sa.String(), nullable=False, server_default=''),
        sa.Column('rule_prompt', sa.Text(), nullable=False, server_default=''),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('author', sa.String(), nullable=False, server_default='Team Studio Bentivegna'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_studio_rules_case_id'), 'studio_rules', ['case_id'], unique=False)
    op.create_index(op.f('ix_studio_rules_scope'), 'studio_rules', ['scope'], unique=False)
    op.create_index(op.f('ix_studio_rules_is_active'), 'studio_rules', ['is_active'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_studio_rules_is_active'), table_name='studio_rules')
    op.drop_index(op.f('ix_studio_rules_scope'), table_name='studio_rules')
    op.drop_index(op.f('ix_studio_rules_case_id'), table_name='studio_rules')
    op.drop_table('studio_rules')

