"""add_employment_type_to_roles

Revision ID: eabafd2cc723
Revises: 
Create Date: 2026-01-11 23:25:21.148262

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'eabafd2cc723'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add employment_type column to roles table."""
    # Create the enum type using lowercase values (matches Python EmploymentType enum values)
    employment_type_enum = sa.Enum('intermitente', 'efetivo', name='employmenttype')
    employment_type_enum.create(op.get_bind(), checkfirst=True)
    
    # Add the column with a default value
    op.add_column('roles', sa.Column('employment_type', 
        sa.Enum('intermitente', 'efetivo', name='employmenttype'),
        nullable=True
    ))
    
    # Set default value for existing rows
    op.execute("UPDATE roles SET employment_type = 'efetivo' WHERE employment_type IS NULL")
    
    # Make column NOT NULL after setting defaults
    op.alter_column('roles', 'employment_type', nullable=False)


def downgrade() -> None:
    """Remove employment_type column from roles table."""
    op.drop_column('roles', 'employment_type')
    
    # Drop the enum type
    employment_type_enum = sa.Enum('intermitente', 'efetivo', name='employmenttype')
    employment_type_enum.drop(op.get_bind(), checkfirst=True)
