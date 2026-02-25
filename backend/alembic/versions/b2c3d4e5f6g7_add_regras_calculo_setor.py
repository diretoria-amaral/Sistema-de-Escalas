"""add regras_calculo_setor table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'regras_calculo_setor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('setor_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('descricao', sa.String(length=1000), nullable=True),
        sa.Column('prioridade', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('escopo', sa.String(length=20), nullable=False),
        sa.Column('condicao_json', sa.JSON(), nullable=True),
        sa.Column('acao_json', sa.JSON(), nullable=False),
        sa.Column('ativo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('atualizado_em', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['setor_id'], ['sectors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_regras_calculo_setor_id'), 'regras_calculo_setor', ['id'], unique=False)
    op.create_index(op.f('ix_regras_calculo_setor_setor_id'), 'regras_calculo_setor', ['setor_id'], unique=False)
    op.create_index(op.f('ix_regras_calculo_setor_prioridade'), 'regras_calculo_setor', ['prioridade'], unique=False)
    op.create_index(op.f('ix_regras_calculo_setor_escopo'), 'regras_calculo_setor', ['escopo'], unique=False)
    op.create_index(op.f('ix_regras_calculo_setor_ativo'), 'regras_calculo_setor', ['ativo'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_regras_calculo_setor_ativo'), table_name='regras_calculo_setor')
    op.drop_index(op.f('ix_regras_calculo_setor_escopo'), table_name='regras_calculo_setor')
    op.drop_index(op.f('ix_regras_calculo_setor_prioridade'), table_name='regras_calculo_setor')
    op.drop_index(op.f('ix_regras_calculo_setor_setor_id'), table_name='regras_calculo_setor')
    op.drop_index(op.f('ix_regras_calculo_setor_id'), table_name='regras_calculo_setor')
    op.drop_table('regras_calculo_setor')
