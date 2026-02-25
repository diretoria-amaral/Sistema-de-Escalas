"""Add interval_unit, interval_value, and anchor_policy to activity_periodicities

Revision ID: f1g2h3i4j5k6
Revises: d81f38c22674
Create Date: 2026-01-22 04:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'f1g2h3i4j5k6'
down_revision = 'd81f38c22674'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DO $$ BEGIN CREATE TYPE intervalunit AS ENUM ('DAYS', 'MONTHS', 'YEARS'); EXCEPTION WHEN duplicate_object THEN null; END $$")
    op.execute("DO $$ BEGIN CREATE TYPE anchorpolicy AS ENUM ('SAME_DAY', 'LAST_DAY_IF_MISSING'); EXCEPTION WHEN duplicate_object THEN null; END $$")
    
    intervalunit_enum = postgresql.ENUM('DAYS', 'MONTHS', 'YEARS', name='intervalunit', create_type=False)
    anchorpolicy_enum = postgresql.ENUM('SAME_DAY', 'LAST_DAY_IF_MISSING', name='anchorpolicy', create_type=False)
    
    op.execute("ALTER TABLE activity_periodicities ADD COLUMN IF NOT EXISTS interval_unit intervalunit NOT NULL DEFAULT 'DAYS'")
    op.execute("ALTER TABLE activity_periodicities ADD COLUMN IF NOT EXISTS interval_value INTEGER NOT NULL DEFAULT 1")
    op.execute("ALTER TABLE activity_periodicities ADD COLUMN IF NOT EXISTS anchor_policy anchorpolicy NOT NULL DEFAULT 'SAME_DAY'")
    
    op.execute("""
        UPDATE activity_periodicities 
        SET interval_value = intervalo_dias, interval_unit = 'DAYS' 
        WHERE interval_unit = 'DAYS' AND interval_value = 1 AND intervalo_dias > 1
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE activity_periodicities DROP COLUMN IF EXISTS anchor_policy")
    op.execute("ALTER TABLE activity_periodicities DROP COLUMN IF EXISTS interval_value")
    op.execute("ALTER TABLE activity_periodicities DROP COLUMN IF EXISTS interval_unit")
    op.execute("DROP TYPE IF EXISTS anchorpolicy")
    op.execute("DROP TYPE IF EXISTS intervalunit")
