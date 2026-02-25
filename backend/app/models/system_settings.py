from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, Float
from sqlalchemy.sql import func
from app.database import Base
import enum


class WorkRegimeMode(str, enum.Enum):
    INTERMITENTE = "INTERMITENTE"
    CLT_PADRAO = "CLT_PADRAO"


class SystemSettings(Base):
    """
    Configuracoes globais do sistema.
    Singleton - apenas um registro ativo.
    """
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    
    work_regime_mode = Column(String(20), default=WorkRegimeMode.INTERMITENTE.value)
    
    intermittent_mode_active = Column(Boolean, default=True)
    
    min_advance_notice_hours = Column(Integer, default=72)
    
    block_fixed_schedules = Column(Boolean, default=True)
    block_continuous_patterns = Column(Boolean, default=True)
    require_formal_convocations = Column(Boolean, default=True)
    
    allow_schedule_generation = Column(Boolean, default=True)
    allow_convocation_generation = Column(Boolean, default=True)
    
    production_ready = Column(Boolean, default=False)
    last_readiness_check = Column(DateTime(timezone=True), nullable=True)
    readiness_issues = Column(JSON, nullable=True)
    
    system_version = Column(String(20), default="1.3.0")
    
    notes = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RuleVersion(Base):
    """
    Versionamento de regras - armazena snapshots das regras quando alteradas.
    """
    __tablename__ = "rule_versions"

    id = Column(Integer, primary_key=True, index=True)
    
    rule_type = Column(String(50), nullable=False)
    sector_id = Column(Integer, nullable=True)
    
    version_number = Column(Integer, nullable=False, default=1)
    
    rule_snapshot = Column(JSON, nullable=False)
    
    change_reason = Column(Text, nullable=True)
    changed_by = Column(Integer, nullable=True)
    
    effective_from = Column(DateTime(timezone=True), server_default=func.now())
    effective_until = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ParserVersion(Base):
    """
    Versionamento de parsers do Data Lake.
    """
    __tablename__ = "parser_versions"

    id = Column(Integer, primary_key=True, index=True)
    
    parser_name = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    method_version = Column(String(20), nullable=True)
    
    description = Column(Text, nullable=True)
    
    changes_log = Column(Text, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
