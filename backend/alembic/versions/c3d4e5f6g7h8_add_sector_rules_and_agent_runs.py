"""add sector_rules and agent_runs tables

Revision ID: c3d4e5f6g7h8
Revises: 12a6ebaca497
Create Date: 2026-01-17 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3d4e5f6g7h8'
down_revision: Union[str, Sequence[str], None] = '12a6ebaca497'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tiporegra_enum = postgresql.ENUM('LABOR', 'OPERATIONAL', 'CALCULATION', name='tiporegra', create_type=False)
    nivelrigidez_enum = postgresql.ENUM('MANDATORY', 'DESIRABLE', 'FLEXIBLE', name='nivelrigidez', create_type=False)
    runtype_enum = postgresql.ENUM('FORECAST', 'DEMAND', 'SCHEDULE', 'CONVOCATIONS', 'FULL_PIPELINE', name='runtype', create_type=False)
    runstatus_enum = postgresql.ENUM('RUNNING', 'SUCCESS', 'FAILED', name='runstatus', create_type=False)

    op.execute("DO $$ BEGIN CREATE TYPE tiporegra AS ENUM ('LABOR', 'OPERATIONAL', 'CALCULATION'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE nivelrigidez AS ENUM ('MANDATORY', 'DESIRABLE', 'FLEXIBLE'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE runtype AS ENUM ('FORECAST', 'DEMAND', 'SCHEDULE', 'CONVOCATIONS', 'FULL_PIPELINE'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE runstatus AS ENUM ('RUNNING', 'SUCCESS', 'FAILED'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    op.create_table(
        'sector_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('setor_id', sa.Integer(), nullable=False),
        sa.Column('tipo_regra', tiporegra_enum, nullable=False),
        sa.Column('nivel_rigidez', nivelrigidez_enum, nullable=False),
        sa.Column('prioridade', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('codigo_regra', sa.String(length=50), nullable=False),
        sa.Column('pergunta', sa.Text(), nullable=False),
        sa.Column('resposta', sa.Text(), nullable=False),
        sa.Column('regra_ativa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('validade_inicio', sa.Date(), nullable=True),
        sa.Column('validade_fim', sa.Date(), nullable=True),
        sa.Column('metadados_json', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['setor_id'], ['sectors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('setor_id', 'tipo_regra', 'codigo_regra', name='uq_sector_rule_code')
    )
    op.create_index('ix_sector_rules_id', 'sector_rules', ['id'], unique=False)
    op.create_index('ix_sector_rules_ordering', 'sector_rules', ['setor_id', 'tipo_regra', 'nivel_rigidez', 'prioridade'], unique=False)
    op.create_index('ix_sector_rules_active', 'sector_rules', ['setor_id', 'regra_ativa', 'deleted_at'], unique=False)

    op.create_table(
        'agent_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('setor_id', sa.Integer(), nullable=False),
        sa.Column('week_start', sa.Date(), nullable=False),
        sa.Column('run_type', runtype_enum, nullable=False),
        sa.Column('status', runstatus_enum, nullable=False, server_default='RUNNING'),
        sa.Column('inputs_snapshot', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('outputs_summary', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['setor_id'], ['sectors.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_runs_id', 'agent_runs', ['id'], unique=False)
    op.create_index('ix_agent_runs_sector_week', 'agent_runs', ['setor_id', 'week_start'], unique=False)
    op.create_index('ix_agent_runs_status', 'agent_runs', ['status'], unique=False)

    op.create_table(
        'agent_trace_steps',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('step_key', sa.String(length=100), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('applied_rules', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('calculations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('constraints_violated', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_agent_trace_steps_id', 'agent_trace_steps', ['id'], unique=False)
    op.create_index('ix_agent_trace_steps_run_order', 'agent_trace_steps', ['run_id', 'step_order'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_agent_trace_steps_run_order', table_name='agent_trace_steps')
    op.drop_index('ix_agent_trace_steps_id', table_name='agent_trace_steps')
    op.drop_table('agent_trace_steps')

    op.drop_index('ix_agent_runs_status', table_name='agent_runs')
    op.drop_index('ix_agent_runs_sector_week', table_name='agent_runs')
    op.drop_index('ix_agent_runs_id', table_name='agent_runs')
    op.drop_table('agent_runs')

    op.drop_index('ix_sector_rules_active', table_name='sector_rules')
    op.drop_index('ix_sector_rules_ordering', table_name='sector_rules')
    op.drop_index('ix_sector_rules_id', table_name='sector_rules')
    op.drop_table('sector_rules')

    op.execute("DROP TYPE IF EXISTS runstatus")
    op.execute("DROP TYPE IF EXISTS runtype")
    op.execute("DROP TYPE IF EXISTS nivelrigidez")
    op.execute("DROP TYPE IF EXISTS tiporegra")
