from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Date, Time, Boolean, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ConvocationStatus(str, enum.Enum):
    PENDING = "pendente"
    ACCEPTED = "aceita"
    DECLINED = "recusada"
    EXPIRED = "expirada"
    CANCELLED = "cancelada"


class ConvocationOrigin(str, enum.Enum):
    BASELINE = "baseline"
    ADJUSTMENT = "ajuste"
    RESCHEDULE = "reescala"
    MANUAL = "manual"


class Convocation(Base):
    __tablename__ = "convocations"

    id = Column(Integer, primary_key=True, index=True)
    
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("governance_activities.id"), nullable=True)
    
    daily_shift_id = Column(Integer, ForeignKey("daily_shifts.id"), nullable=True)
    weekly_schedule_id = Column(Integer, ForeignKey("weekly_schedules.id"), nullable=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=True)
    
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    break_minutes = Column(Integer, default=60)
    total_hours = Column(Float, nullable=False)
    
    status = Column(SQLEnum(ConvocationStatus), default=ConvocationStatus.PENDING, index=True)
    generated_from = Column(SQLEnum(ConvocationOrigin), default=ConvocationOrigin.BASELINE)
    
    sent_at = Column(DateTime(timezone=True), nullable=True)
    response_deadline = Column(DateTime(timezone=True), nullable=False)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    
    operational_justification = Column(String(1000), nullable=True)
    decline_reason = Column(String(500), nullable=True)
    response_notes = Column(String(500), nullable=True)
    
    replaced_convocation_id = Column(Integer, ForeignKey("convocations.id"), nullable=True)
    replacement_convocation_id = Column(Integer, nullable=True)
    
    legal_validation_passed = Column(Boolean, default=True)
    legal_validation_errors = Column(String(2000), nullable=True)
    legal_validation_warnings = Column(String(2000), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    employee = relationship("Employee", back_populates="convocations")
    sector = relationship("Sector")
    activity = relationship("GovernanceActivity")
    daily_shift = relationship("DailyShift", back_populates="convocation")
    weekly_schedule = relationship("WeeklySchedule")
    replaced_convocation = relationship("Convocation", remote_side=[id], foreign_keys=[replaced_convocation_id])
