from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Date, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ScheduleStatus(str, enum.Enum):
    DRAFT = "rascunho"
    GENERATED = "gerada"
    PUBLISHED = "publicada"
    COMPLETED = "concluida"
    CANCELLED = "cancelada"


class WeeklySchedule(Base):
    __tablename__ = "weekly_schedules"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False)
    week_start = Column(Date, nullable=False, index=True)
    week_end = Column(Date, nullable=False)
    status = Column(SQLEnum(ScheduleStatus), default=ScheduleStatus.DRAFT)
    notes = Column(String(1000), nullable=True)
    expected_occupancy = Column(Integer, nullable=True)
    expected_rooms_to_clean = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector", back_populates="weekly_schedules")
    daily_shifts = relationship("DailyShift", back_populates="weekly_schedule")
