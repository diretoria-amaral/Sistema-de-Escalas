from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Time, Text, ForeignKey, JSON, SmallInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Enum as SQLEnum
from app.database import Base
import enum


class ProgramWeekStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    LOCKED = "locked"


class ProgramItemSource(str, enum.Enum):
    AUTO = "auto"
    MANUAL = "manual"


class ActivityProgramWeek(Base):
    __tablename__ = "activity_program_weeks"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=False, index=True)
    week_start = Column(Date, nullable=False, index=True)
    status = Column(SQLEnum(ProgramWeekStatus), default=ProgramWeekStatus.DRAFT, nullable=False)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('sector_id', 'forecast_run_id', 'week_start', name='uq_sector_run_week'),
    )

    sector = relationship("Sector")
    forecast_run = relationship("ForecastRun")
    items = relationship("ActivityProgramItem", back_populates="program_week", cascade="all, delete-orphan")


class ActivityProgramItem(Base):
    __tablename__ = "activity_program_items"

    id = Column(Integer, primary_key=True, index=True)
    program_week_id = Column(Integer, ForeignKey("activity_program_weeks.id"), nullable=False, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("governance_activities.id"), nullable=False, index=True)
    op_date = Column(Date, nullable=False, index=True)
    window_start = Column(Time, nullable=True)
    window_end = Column(Time, nullable=True)
    quantity = Column(Integer, default=1, nullable=False)
    workload_minutes = Column(Integer, nullable=True)
    priority = Column(SmallInteger, default=3, nullable=False)
    source = Column(SQLEnum(ProgramItemSource), default=ProgramItemSource.MANUAL, nullable=False)
    drivers_json = Column(JSON, default=dict)
    notes = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_by = Column(String(100), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    program_week = relationship("ActivityProgramWeek", back_populates="items")
    sector = relationship("Sector")
    activity = relationship("GovernanceActivity")
