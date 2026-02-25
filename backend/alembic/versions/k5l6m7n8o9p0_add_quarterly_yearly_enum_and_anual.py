"""Add QUARTERLY and YEARLY enum values and Anual periodicity

Revision ID: k5l6m7n8o9p0
Revises: f1g2h3i4j5k6
Create Date: 2026-01-22

"""
from alembic import op
import sqlalchemy as sa


revision = 'k5l6m7n8o9p0'
down_revision = 'f1g2h3i4j5k6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    existing_vals = conn.execute(
        sa.text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'periodicitytype'::regtype")
    ).fetchall()
    existing_labels = {row[0] for row in existing_vals}
    
    if 'QUARTERLY' not in existing_labels:
        op.execute("ALTER TYPE periodicitytype ADD VALUE IF NOT EXISTS 'QUARTERLY'")
    if 'YEARLY' not in existing_labels:
        op.execute("ALTER TYPE periodicitytype ADD VALUE IF NOT EXISTS 'YEARLY'")
    
    conn.execute(sa.text("COMMIT"))
    
    existing_anual = conn.execute(
        sa.text("SELECT id FROM activity_periodicities WHERE LOWER(name) = 'anual'")
    ).fetchone()
    
    if existing_anual:
        conn.execute(sa.text("""
            UPDATE activity_periodicities 
            SET is_active = true, tipo = 'YEARLY', interval_unit = 'YEARS', 
                interval_value = 1, intervalo_dias = 365, deleted_at = NULL
            WHERE LOWER(name) = 'anual'
        """))
    else:
        conn.execute(sa.text("""
            INSERT INTO activity_periodicities (name, tipo, interval_unit, interval_value, intervalo_dias, is_active, description)
            VALUES ('Anual', 'YEARLY', 'YEARS', 1, 365, true, 'A cada 1 ano')
        """))


def downgrade():
    pass
