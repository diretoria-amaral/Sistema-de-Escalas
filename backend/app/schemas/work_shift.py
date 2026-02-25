from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from datetime import time
from enum import Enum

class ShiftTimeConstraint(str, Enum):
    MANDATORY = "MANDATORY"
    FLEXIBLE = "FLEXIBLE"

class WorkShiftDayRuleBase(BaseModel):
    weekday: int
    start_time: Optional[time] = None
    break_out_time: Optional[time] = None
    break_in_time: Optional[time] = None
    end_time: Optional[time] = None
    start_constraint: ShiftTimeConstraint = ShiftTimeConstraint.FLEXIBLE
    end_constraint: ShiftTimeConstraint = ShiftTimeConstraint.FLEXIBLE

    @field_validator('weekday')
    @classmethod
    def validate_weekday(cls, v):
        if not (1 <= v <= 7):
            raise ValueError('Weekday must be between 1 and 7 (ISO)')
        return v

    @model_validator(mode='after')
    def validate_coherence(self) -> 'WorkShiftDayRuleBase':
        if self.start_time is not None or self.end_time is not None:
            if self.start_time is None or self.end_time is None:
                raise ValueError('Both start_time and end_time must be defined if one is present')
            
            if self.end_time <= self.start_time:
                raise ValueError('end_time must be after start_time')

        has_break_out = self.break_out_time is not None
        has_break_in = self.break_in_time is not None
        if has_break_out != has_break_in:
            raise ValueError('Both break_out_time and break_in_time must be defined or both null')

        if has_break_out:
            if not (self.start_time < self.break_out_time < self.break_in_time < self.end_time):
                raise ValueError('Invalid interval sequence: start < break_out < break_in < end')

        return self

class WorkShiftDayRuleCreate(WorkShiftDayRuleBase):
    pass

class WorkShiftDayRuleResponse(WorkShiftDayRuleBase):
    id: int
    class Config:
        from_attributes = True

class WorkShiftCreate(BaseModel):
    sector_id: int
    name: str
    days: List[WorkShiftDayRuleCreate]

class WorkShiftUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    days: Optional[List[WorkShiftDayRuleCreate]] = None

class WorkShiftResponse(BaseModel):
    id: int
    sector_id: int
    name: str
    is_active: bool
    day_rules: List[WorkShiftDayRuleResponse]

    class Config:
        from_attributes = True
