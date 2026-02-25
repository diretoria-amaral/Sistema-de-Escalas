from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date, Time, Float, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ShiftPeriod(str, enum.Enum):
    MORNING = "manha"
    AFTERNOON = "tarde"
    NIGHT = "noite"


class DailyShift(Base):
    __tablename__ = "daily_shifts"

    id = Column(Integer, primary_key=True, index=True)
    weekly_schedule_id = Column(Integer, ForeignKey("weekly_schedules.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    date = Column(Date, nullable=False, index=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    shift_period = Column(SQLEnum(ShiftPeriod), nullable=False)
    
    planned_hours = Column(Float, nullable=False)
    actual_hours = Column(Float, nullable=True)
    
    assigned_activities = Column(JSON, default=list)
    notes = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    weekly_schedule = relationship("WeeklySchedule", back_populates="daily_shifts")
    employee = relationship("Employee", back_populates="daily_shifts")
    convocation = relationship("Convocation", back_populates="daily_shift", uselist=False)
