from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, JSON, Enum as SAEnum, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class RunType(str, enum.Enum):
    FORECAST = "FORECAST"
    DEMAND = "DEMAND"
    SCHEDULE = "SCHEDULE"
    CONVOCATIONS = "CONVOCATIONS"
    FULL_PIPELINE = "FULL_PIPELINE"


class RunStatus(str, enum.Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    setor_id = Column(Integer, ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False)
    week_start = Column(Date, nullable=False)
    run_type = Column(SAEnum(RunType), nullable=False)
    status = Column(SAEnum(RunStatus), default=RunStatus.RUNNING, nullable=False)
    inputs_snapshot = Column(JSON, nullable=True)
    outputs_summary = Column(JSON, nullable=True)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    sector = relationship("Sector", back_populates="agent_runs")
    trace_steps = relationship("AgentTraceStep", back_populates="agent_run", cascade="all, delete-orphan", order_by="AgentTraceStep.step_order")

    __table_args__ = (
        Index('ix_agent_runs_sector_week', 'setor_id', 'week_start'),
        Index('ix_agent_runs_status', 'status'),
    )


class AgentTraceStep(Base):
    __tablename__ = "agent_trace_steps"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    step_key = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    applied_rules = Column(JSON, nullable=True)
    calculations = Column(JSON, nullable=True)
    constraints_violated = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    agent_run = relationship("AgentRun", back_populates="trace_steps")

    __table_args__ = (
        Index('ix_agent_trace_steps_run_order', 'run_id', 'step_order'),
    )
