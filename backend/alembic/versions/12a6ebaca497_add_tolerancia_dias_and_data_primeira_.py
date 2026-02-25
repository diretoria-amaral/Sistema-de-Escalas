"""add tolerancia_dias and data_primeira_execucao to governance_activities

Revision ID: 12a6ebaca497
Revises: b2c3d4e5f6g7
Create Date: 2026-01-14 01:30:52.278679

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '12a6ebaca497'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6g7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add tolerancia_dias and data_primeira_execucao columns."""
    op.add_column('governance_activities', sa.Column('tolerancia_dias', sa.Integer(), nullable=True))
    op.add_column('governance_activities', sa.Column('data_primeira_execucao', sa.Date(), nullable=True))


def downgrade() -> None:
    """Remove tolerancia_dias and data_primeira_execucao columns."""
    op.drop_column('governance_activities', 'data_primeira_execucao')
    op.drop_column('governance_activities', 'tolerancia_dias')
