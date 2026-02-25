from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey, JSON, Enum as SAEnum, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class TipoRegra(str, enum.Enum):
    LABOR = "LABOR"
    SYSTEM = "SYSTEM"
    OPERATIONAL = "OPERATIONAL"
    CALCULATION = "CALCULATION"


class NivelRigidez(str, enum.Enum):
    MANDATORY = "MANDATORY"
    DESIRABLE = "DESIRABLE"
    FLEXIBLE = "FLEXIBLE"


class SectorRule(Base):
    __tablename__ = "sector_rules"

    id = Column(Integer, primary_key=True, index=True)
    setor_id = Column(Integer, ForeignKey("sectors.id", ondelete="CASCADE"), nullable=True)
    is_global = Column(Boolean, default=False, nullable=False)
    tipo_regra = Column(SAEnum(TipoRegra), nullable=False)
    nivel_rigidez = Column(SAEnum(NivelRigidez), nullable=False)
    prioridade = Column(Integer, nullable=False, default=1)
    codigo_regra = Column(String(50), nullable=False)
    title = Column(String(200), nullable=True)
    pergunta = Column(Text, nullable=False)
    resposta = Column(Text, nullable=False)
    regra_ativa = Column(Boolean, default=True, nullable=False)
    validade_inicio = Column(Date, nullable=True)
    validade_fim = Column(Date, nullable=True)
    metadados_json = Column(JSON, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    sector = relationship("Sector", back_populates="sector_rules")

    __table_args__ = (
        UniqueConstraint('setor_id', 'tipo_regra', 'codigo_regra', name='uq_sector_rule_code'),
        Index('ix_sector_rules_ordering', 'setor_id', 'tipo_regra', 'nivel_rigidez', 'prioridade'),
        Index('ix_sector_rules_active', 'setor_id', 'regra_ativa', 'deleted_at'),
        Index('ix_sector_rules_global', 'is_global', 'tipo_regra', 'nivel_rigidez', 'prioridade'),
    )
