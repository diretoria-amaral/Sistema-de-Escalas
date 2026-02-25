from sqlalchemy import Column, Integer, String, Date, Float, Boolean, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class HolidayType(str, enum.Enum):
    NATIONAL = "NATIONAL"
    STATE = "STATE"
    MUNICIPAL = "MUNICIPAL"
    INTERNAL = "INTERNAL"


class CalendarScope(str, enum.Enum):
    GLOBAL = "GLOBAL"
    SECTOR = "SECTOR"


class OperationalCalendar(Base):
    __tablename__ = "operational_calendar"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    holiday_type = Column(SQLEnum(HolidayType, values_callable=lambda e: [m.value for m in e]), nullable=False)
    scope = Column(SQLEnum(CalendarScope, values_callable=lambda e: [m.value for m in e]), nullable=False, default=CalendarScope.GLOBAL)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True)
    productivity_factor = Column(Float, default=1.0)
    demand_factor = Column(Float, default=1.0)
    block_convocations = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sector = relationship("Sector", backref="calendar_events")
