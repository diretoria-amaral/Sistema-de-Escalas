from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from app.models.weekly_schedule import ScheduleStatus


class WeeklyScheduleBase(BaseModel):
    sector_id: int
    week_start: date
    week_end: date
    status: ScheduleStatus = ScheduleStatus.DRAFT
    notes: Optional[str] = None
    expected_occupancy: Optional[int] = None
    expected_rooms_to_clean: Optional[int] = None


class WeeklyScheduleCreate(WeeklyScheduleBase):
    pass


class WeeklyScheduleResponse(WeeklyScheduleBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ScheduleGenerationRequest(BaseModel):
    sector_id: int
    week_start: date
    expected_occupancy: Optional[int] = None
    expected_rooms_to_clean: Optional[int] = None
    notes: Optional[str] = None
