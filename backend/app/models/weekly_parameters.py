from sqlalchemy import Column, Integer, Float, Boolean, Date, String, Enum as SQLEnum, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class DayType(str, enum.Enum):
    NORMAL = "normal"
    FERIADO = "feriado"
    VESPERA_FERIADO = "vespera_feriado"


class WeeklyParameters(Base):
    """
    Parâmetros operacionais da semana para cálculo de mão de obra.
    Uma entrada por semana POR SETOR, identificada pela data de início (segunda-feira).
    
    PROMPT 8: Adicionado sector_id para suporte multi-setor.
    """
    __tablename__ = "weekly_parameters"
    __table_args__ = (
        UniqueConstraint('sector_id', 'semana_inicio', name='uq_weekly_params_sector_week'),
    )

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True, index=True)
    semana_inicio = Column(Date, nullable=False, index=True)  # Segunda-feira da semana
    
    # Segunda-feira
    seg_ocupacao_prevista = Column(Float, default=0.0)
    seg_quartos_vagos_sujos = Column(Integer, default=0)
    seg_quartos_estada = Column(Integer, default=0)
    seg_tipo_dia = Column(SQLEnum(DayType), default=DayType.NORMAL)
    
    # Terça-feira
    ter_ocupacao_prevista = Column(Float, default=0.0)
    ter_quartos_vagos_sujos = Column(Integer, default=0)
    ter_quartos_estada = Column(Integer, default=0)
    ter_tipo_dia = Column(SQLEnum(DayType), default=DayType.NORMAL)
    
    # Quarta-feira
    qua_ocupacao_prevista = Column(Float, default=0.0)
    qua_quartos_vagos_sujos = Column(Integer, default=0)
    qua_quartos_estada = Column(Integer, default=0)
    qua_tipo_dia = Column(SQLEnum(DayType), default=DayType.NORMAL)
    
    # Quinta-feira
    qui_ocupacao_prevista = Column(Float, default=0.0)
    qui_quartos_vagos_sujos = Column(Integer, default=0)
    qui_quartos_estada = Column(Integer, default=0)
    qui_tipo_dia = Column(SQLEnum(DayType), default=DayType.NORMAL)
    
    # Sexta-feira
    sex_ocupacao_prevista = Column(Float, default=0.0)
    sex_quartos_vagos_sujos = Column(Integer, default=0)
    sex_quartos_estada = Column(Integer, default=0)
    sex_tipo_dia = Column(SQLEnum(DayType), default=DayType.NORMAL)
    
    # Sábado
    sab_ocupacao_prevista = Column(Float, default=0.0)
    sab_quartos_vagos_sujos = Column(Integer, default=0)
    sab_quartos_estada = Column(Integer, default=0)
    sab_tipo_dia = Column(SQLEnum(DayType), default=DayType.NORMAL)
    
    # Domingo
    dom_ocupacao_prevista = Column(Float, default=0.0)
    dom_quartos_vagos_sujos = Column(Integer, default=0)
    dom_quartos_estada = Column(Integer, default=0)
    dom_tipo_dia = Column(SQLEnum(DayType), default=DayType.NORMAL)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector")
