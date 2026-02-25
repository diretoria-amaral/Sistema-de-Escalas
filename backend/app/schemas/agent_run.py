from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import date, datetime
from enum import Enum


class RunType(str, Enum):
    FORECAST = "FORECAST"
    DEMAND = "DEMAND"
    SCHEDULE = "SCHEDULE"
    CONVOCATIONS = "CONVOCATIONS"
    FULL_PIPELINE = "FULL_PIPELINE"


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class AgentTraceStepCreate(BaseModel):
    step_order: int
    step_key: str = Field(..., max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    applied_rules: Optional[List[str]] = None
    calculations: Optional[Dict[str, Any]] = None
    constraints_violated: Optional[List[str]] = None


class AgentTraceStepResponse(BaseModel):
    id: int
    run_id: int
    step_order: int
    step_key: str
    description: Optional[str]
    applied_rules: Optional[List[str]]
    calculations: Optional[Dict[str, Any]]
    constraints_violated: Optional[List[str]]
    created_at: datetime

    class Config:
        from_attributes = True


class AgentRunCreate(BaseModel):
    setor_id: int
    week_start: date
    run_type: RunType
    inputs_snapshot: Optional[Dict[str, Any]] = None


class AgentRunUpdate(BaseModel):
    status: Optional[RunStatus] = None
    outputs_summary: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    finished_at: Optional[datetime] = None


class AgentRunResponse(BaseModel):
    id: int
    setor_id: int
    week_start: date
    run_type: RunType
    status: RunStatus
    inputs_snapshot: Optional[Dict[str, Any]]
    outputs_summary: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class AgentRunDetailResponse(AgentRunResponse):
    trace_steps: List[AgentTraceStepResponse]


class AgentRunListResponse(BaseModel):
    items: List[AgentRunResponse]
    total: int


class CalculationMemoryResponse(BaseModel):
    run_id: int
    setor_id: int
    week_start: date
    run_type: RunType
    status: RunStatus
    inputs_snapshot: Optional[Dict[str, Any]]
    outputs_summary: Optional[Dict[str, Any]]
    trace_steps: List[AgentTraceStepResponse]
    rules_applied_summary: Dict[str, int]
    constraints_violated_summary: List[str]
