"""add title field to sector_rules

Revision ID: d8152a33c84f
Revises: c3d4e5f6g7h8
Create Date: 2026-01-22 02:44:50.159964

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'd8152a33c84f'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6g7h8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sector_rules', sa.Column('title', sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column('sector_rules', 'title')
