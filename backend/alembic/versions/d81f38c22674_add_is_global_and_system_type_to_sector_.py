"""add_is_global_and_system_type_to_sector_rules

Revision ID: d81f38c22674
Revises: d8152a33c84f
Create Date: 2026-01-22 03:01:18.198683

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd81f38c22674'
down_revision: Union[str, Sequence[str], None] = 'd8152a33c84f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('sector_rules', sa.Column('is_global', sa.Boolean(), nullable=False, server_default='false'))
    
    op.alter_column('sector_rules', 'setor_id', nullable=True)
    
    op.execute("ALTER TYPE tiporegra ADD VALUE IF NOT EXISTS 'SYSTEM'")
    
    op.create_index('ix_sector_rules_global', 'sector_rules', 
                    ['is_global', 'tipo_regra', 'nivel_rigidez', 'prioridade'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_sector_rules_global', table_name='sector_rules')
    
    op.alter_column('sector_rules', 'setor_id', nullable=False)
    
    op.drop_column('sector_rules', 'is_global')
