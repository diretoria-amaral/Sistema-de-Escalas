"""add_workload_driver_to_governance_activity

Revision ID: 078b938bd94f
Revises: eabafd2cc723
Create Date: 2026-01-11 23:52:45.721157

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '078b938bd94f'
down_revision: Union[str, Sequence[str], None] = 'eabafd2cc723'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Adiciona campo workload_driver à tabela governance_activities."""
    op.execute("DO $$ BEGIN CREATE TYPE workloaddriver AS ENUM ('VARIABLE', 'CONSTANT'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.add_column(
        'governance_activities',
        sa.Column(
            'workload_driver',
            sa.Enum('VARIABLE', 'CONSTANT', name='workloaddriver'),
            nullable=False,
            server_default='VARIABLE'
        )
    )


def downgrade() -> None:
    """Remove campo workload_driver da tabela governance_activities."""
    op.drop_column('governance_activities', 'workload_driver')
    op.execute("DROP TYPE workloaddriver")
