"""Add activity periodicities and classification

Revision ID: a1b2c3d4e5f6
Revises: 078b938bd94f
Create Date: 2026-01-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'a1b2c3d4e5f6'
down_revision = '078b938bd94f'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    
    periodicity_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'periodicitytype'")
    ).scalar()
    if not periodicity_exists:
        op.execute("CREATE TYPE periodicitytype AS ENUM ('DAILY', 'WEEKLY', 'FORTNIGHTLY', 'MONTHLY', 'CUSTOM')")
    
    table_exists = conn.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_name = 'activity_periodicities'")
    ).scalar()
    
    if not table_exists:
        op.create_table(
            'activity_periodicities',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(100), nullable=False, unique=True),
            sa.Column('tipo', postgresql.ENUM('DAILY', 'WEEKLY', 'FORTNIGHTLY', 'MONTHLY', 'CUSTOM', name='periodicitytype', create_type=False), nullable=False),
            sa.Column('intervalo_dias', sa.Integer(), nullable=False, server_default='1'),
            sa.Column('description', sa.String(500), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='true'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_activity_periodicities_id', 'activity_periodicities', ['id'])
        op.create_index('ix_activity_periodicities_tipo', 'activity_periodicities', ['tipo'])
    
    classification_exists = conn.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'activityclassification'")
    ).scalar()
    if not classification_exists:
        op.execute("CREATE TYPE activityclassification AS ENUM ('CALCULADA_PELO_AGENTE', 'RECORRENTE', 'EVENTUAL')")
    
    col_exists = conn.execute(
        sa.text("SELECT 1 FROM information_schema.columns WHERE table_name = 'governance_activities' AND column_name = 'classificacao_atividade'")
    ).scalar()
    
    if not col_exists:
        op.add_column(
            'governance_activities',
            sa.Column('classificacao_atividade', postgresql.ENUM('CALCULADA_PELO_AGENTE', 'RECORRENTE', 'EVENTUAL', name='activityclassification', create_type=False), nullable=False, server_default='CALCULADA_PELO_AGENTE')
        )
        op.create_index('ix_governance_activities_classificacao_atividade', 'governance_activities', ['classificacao_atividade'])
    
    periodicity_col_exists = conn.execute(
        sa.text("SELECT 1 FROM information_schema.columns WHERE table_name = 'governance_activities' AND column_name = 'periodicidade_id'")
    ).scalar()
    
    if not periodicity_col_exists:
        op.add_column(
            'governance_activities',
            sa.Column('periodicidade_id', sa.Integer(), nullable=True)
        )
        op.create_foreign_key(
            'fk_governance_activities_periodicidade_id',
            'governance_activities',
            'activity_periodicities',
            ['periodicidade_id'],
            ['id']
        )
        op.create_index('ix_governance_activities_periodicidade_id', 'governance_activities', ['periodicidade_id'])


def downgrade():
    op.drop_index('ix_governance_activities_periodicidade_id', 'governance_activities')
    op.drop_index('ix_governance_activities_classificacao_atividade', 'governance_activities')
    op.drop_column('governance_activities', 'periodicidade_id')
    op.drop_column('governance_activities', 'classificacao_atividade')
    
    op.drop_index('ix_activity_periodicities_tipo', 'activity_periodicities')
    op.drop_index('ix_activity_periodicities_id', 'activity_periodicities')
    op.drop_table('activity_periodicities')
    
    sa.Enum(name='activityclassification').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='periodicitytype').drop(op.get_bind(), checkfirst=True)
