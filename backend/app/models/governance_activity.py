from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, ForeignKey, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class WorkloadDriver(str, enum.Enum):
    """
    Define como a atividade afeta o cálculo de demanda:
    - VARIABLE: Demanda varia com ocupação (LVS, LET)
    - CONSTANT: Demanda fixa independente de ocupação (limpeza AC, áreas comuns)
    """
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"


class ActivityClassification(str, enum.Enum):
    """
    Classificação da atividade que define seu comportamento na programação:
    - CALCULADA_PELO_AGENTE: Demanda calculada automaticamente pelo sistema (ex: LVS, LET)
    - RECORRENTE: Executada em intervalos regulares conforme periodicidade cadastrada
    - EVENTUAL: Agendada manualmente quando necessário
    """
    CALCULADA_PELO_AGENTE = "CALCULADA_PELO_AGENTE"
    RECORRENTE = "RECORRENTE"
    EVENTUAL = "EVENTUAL"


class GovernanceActivity(Base):
    """
    Atividade de um setor específico.
    PROMPT 5: Agora vinculada obrigatoriamente a um setor.
    ATUALIZAÇÃO: Adicionado workload_driver para distinguir atividades variáveis/constantes.
    ATUALIZAÇÃO: Adicionado classificacao_atividade e periodicidade_id para controle de recorrência.
    """
    __tablename__ = "governance_activities"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=False)
    description = Column(String(500), nullable=True)
    average_time_minutes = Column(Float, nullable=False)
    unit_type = Column(String(50), nullable=True)
    workload_driver = Column(
        SQLEnum(WorkloadDriver, values_callable=lambda x: [e.value for e in x]),
        default=WorkloadDriver.VARIABLE,
        nullable=False,
        server_default="VARIABLE"
    )
    classificacao_atividade = Column(
        SQLEnum(ActivityClassification, values_callable=lambda x: [e.value for e in x]),
        default=ActivityClassification.CALCULADA_PELO_AGENTE,
        nullable=False,
        server_default="CALCULADA_PELO_AGENTE",
        index=True
    )
    periodicidade_id = Column(Integer, ForeignKey("activity_periodicities.id"), nullable=True, index=True)
    tolerancia_dias = Column(Integer, nullable=True)
    data_primeira_execucao = Column(Date, nullable=True)
    difficulty_level = Column(Integer, default=1)
    requires_training = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector", back_populates="activities")
    role_activities = relationship("RoleActivity", back_populates="activity")
    periodicity = relationship("ActivityPeriodicity", back_populates="activities")


class RoleActivity(Base):
    """
    Mapeamento Role <-> Activity.
    Permite definir quais atividades cada função pode executar.
    """
    __tablename__ = "role_activities"

    id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("governance_activities.id"), nullable=False, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    role = relationship("Role", back_populates="role_activities")
    activity = relationship("GovernanceActivity", back_populates="role_activities")
