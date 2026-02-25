from pydantic import BaseModel, Field
from datetime import date, time, datetime
from typing import Optional, List
from enum import Enum


class ConvocationStatusEnum(str, Enum):
    PENDING = "pendente"
    ACCEPTED = "aceita"
    DECLINED = "recusada"
    EXPIRED = "expirada"
    CANCELLED = "cancelada"


class ConvocationOriginEnum(str, Enum):
    BASELINE = "baseline"
    ADJUSTMENT = "ajuste"
    RESCHEDULE = "reescala"
    MANUAL = "manual"


class ConvocationBase(BaseModel):
    employee_id: int
    sector_id: int
    activity_id: Optional[int] = None
    date: date
    start_time: time
    end_time: time
    break_minutes: int = 60
    total_hours: float
    operational_justification: Optional[str] = None


class ConvocationCreate(ConvocationBase):
    daily_shift_id: Optional[int] = None
    weekly_schedule_id: Optional[int] = None
    forecast_run_id: Optional[int] = None
    generated_from: ConvocationOriginEnum = ConvocationOriginEnum.MANUAL
    response_deadline: datetime


class ConvocationResponse(BaseModel):
    id: int
    employee_id: int
    sector_id: int
    activity_id: Optional[int] = None
    daily_shift_id: Optional[int] = None
    weekly_schedule_id: Optional[int] = None
    forecast_run_id: Optional[int] = None
    date: date
    start_time: time
    end_time: time
    break_minutes: int
    total_hours: float
    status: ConvocationStatusEnum
    generated_from: ConvocationOriginEnum
    sent_at: Optional[datetime] = None
    response_deadline: datetime
    responded_at: Optional[datetime] = None
    operational_justification: Optional[str] = None
    decline_reason: Optional[str] = None
    response_notes: Optional[str] = None
    replaced_convocation_id: Optional[int] = None
    replacement_convocation_id: Optional[int] = None
    legal_validation_passed: bool
    legal_validation_errors: Optional[str] = None
    legal_validation_warnings: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    employee_name: Optional[str] = None
    sector_name: Optional[str] = None
    activity_name: Optional[str] = None

    class Config:
        from_attributes = True


class ConvocationAcceptDecline(BaseModel):
    action: str = Field(..., pattern="^(accept|decline)$")
    decline_reason: Optional[str] = None
    response_notes: Optional[str] = None


class ConvocationCancel(BaseModel):
    cancellation_reason: str


class GenerateConvocationsRequest(BaseModel):
    weekly_schedule_id: int
    response_deadline_hours: int = 72


class GenerateConvocationsResponse(BaseModel):
    success: bool
    convocations_created: int
    convocations_blocked: int
    errors: List[str]
    warnings: List[str]
    created_convocation_ids: List[int]


class ConvocationListFilters(BaseModel):
    sector_id: Optional[int] = None
    employee_id: Optional[int] = None
    status: Optional[ConvocationStatusEnum] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    week_start: Optional[date] = None


class ConvocationStats(BaseModel):
    total: int
    pending: int
    accepted: int
    declined: int
    expired: int
    cancelled: int
    acceptance_rate: float


class RescheduleResult(BaseModel):
    success: bool
    original_convocation_id: int
    replacement_convocation_id: Optional[int] = None
    eligible_employees_found: int
    message: str
    errors: List[str]
