from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from enum import Enum


class HolidayType(str, Enum):
    NATIONAL = "NATIONAL"
    STATE = "STATE"
    MUNICIPAL = "MUNICIPAL"
    INTERNAL = "INTERNAL"


class CalendarScope(str, Enum):
    GLOBAL = "GLOBAL"
    SECTOR = "SECTOR"


class CalendarEventBase(BaseModel):
    date: date
    name: str
    holiday_type: HolidayType
    scope: CalendarScope = CalendarScope.GLOBAL
    sector_id: Optional[int] = None
    productivity_factor: float = 1.0
    demand_factor: float = 1.0
    block_convocations: bool = False
    notes: Optional[str] = None


class CalendarEventCreate(CalendarEventBase):
    pass


class CalendarEventUpdate(BaseModel):
    date: Optional[date] = None
    name: Optional[str] = None
    holiday_type: Optional[HolidayType] = None
    scope: Optional[CalendarScope] = None
    sector_id: Optional[int] = None
    productivity_factor: Optional[float] = None
    demand_factor: Optional[float] = None
    block_convocations: Optional[bool] = None
    notes: Optional[str] = None


class CalendarEventResponse(CalendarEventBase):
    id: int
    created_at: datetime
    updated_at: datetime
    sector_name: Optional[str] = None

    class Config:
        from_attributes = True


class CalendarFactors(BaseModel):
    productivity_factor: float
    demand_factor: float
    block_convocations: bool
    applied_events: list[str]
