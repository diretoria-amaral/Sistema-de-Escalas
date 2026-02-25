from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class PeriodicityType(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    FORTNIGHTLY = "FORTNIGHTLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    CUSTOM = "CUSTOM"


class IntervalUnit(str, enum.Enum):
    DAYS = "DAYS"
    MONTHS = "MONTHS"
    YEARS = "YEARS"


class AnchorPolicy(str, enum.Enum):
    SAME_DAY = "SAME_DAY"
    LAST_DAY_IF_MISSING = "LAST_DAY_IF_MISSING"


class ActivityPeriodicity(Base):
    """
    Cadastro de periodicidades para atividades recorrentes.
    Define a frequência com que uma atividade deve ser executada.
    """
    __tablename__ = "activity_periodicities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    tipo = Column(
        SQLEnum(PeriodicityType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True
    )
    intervalo_dias = Column(Integer, nullable=False, default=1)
    interval_unit = Column(
        SQLEnum(IntervalUnit, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=IntervalUnit.DAYS,
        server_default="DAYS"
    )
    interval_value = Column(Integer, nullable=False, default=1, server_default="1")
    anchor_policy = Column(
        SQLEnum(AnchorPolicy, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=AnchorPolicy.SAME_DAY,
        server_default="SAME_DAY"
    )
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    activities = relationship("GovernanceActivity", back_populates="periodicity")
