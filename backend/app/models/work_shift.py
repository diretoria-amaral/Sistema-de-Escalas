from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Time, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class ShiftTimeConstraint(str, enum.Enum):
    MANDATORY = "MANDATORY"
    FLEXIBLE = "FLEXIBLE"

class WorkShift(Base):
    __tablename__ = "work_shifts"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    sector = relationship("Sector")
    day_rules = relationship("WorkShiftDayRule", back_populates="work_shift", cascade="all, delete-orphan")

class WorkShiftDayRule(Base):
    __tablename__ = "work_shift_day_rules"

    id = Column(Integer, primary_key=True, index=True)
    work_shift_id = Column(Integer, ForeignKey("work_shifts.id", ondelete="CASCADE"), nullable=False)
    weekday = Column(Integer, nullable=False)  # 1=Mon, ..., 7=Sun
    start_time = Column(Time, nullable=True)
    break_out_time = Column(Time, nullable=True)
    break_in_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    start_constraint = Column(SAEnum(ShiftTimeConstraint), default=ShiftTimeConstraint.FLEXIBLE, nullable=False)
    end_constraint = Column(SAEnum(ShiftTimeConstraint), default=ShiftTimeConstraint.FLEXIBLE, nullable=False)

    work_shift = relationship("WorkShift", back_populates="day_rules")

    __table_args__ = (
        UniqueConstraint('work_shift_id', 'weekday', name='uq_work_shift_weekday'),
    )
