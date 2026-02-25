from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Sector(Base):
    __tablename__ = "sectors"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    roles = relationship("Role", back_populates="sector")
    employees = relationship("Employee", back_populates="sector")
    weekly_schedules = relationship("WeeklySchedule", back_populates="sector")
    activities = relationship("GovernanceActivity", back_populates="sector")
    regras_calculo = relationship("RegraCalculoSetor", back_populates="setor")
    sector_rules = relationship("SectorRule", back_populates="sector", cascade="all, delete-orphan")
    agent_runs = relationship("AgentRun", back_populates="sector", cascade="all, delete-orphan")
