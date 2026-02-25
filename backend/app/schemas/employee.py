from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from app.models.employee import ContractType, WorkRegime


class EmployeeBase(BaseModel):
    name: str
    cpf: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    sector_id: int
    role_id: int
    cbo_code: Optional[str] = None
    contract_type: ContractType = ContractType.INTERMITTENT
    work_regime: Optional[WorkRegime] = None
    monthly_hours_target: float = 176.0
    velocidade_limpeza_vago_sujo: float = 25.0
    velocidade_limpeza_estada: float = 10.0
    carga_horaria_max_semana: float = 44.0
    unavailable_days: List[str] = []
    time_off_preferences: List[str] = []
    restrictions: List[str] = []
    hire_date: Optional[date] = None
    is_active: bool = True


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    cpf: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    sector_id: Optional[int] = None
    role_id: Optional[int] = None
    cbo_code: Optional[str] = None
    contract_type: Optional[ContractType] = None
    work_regime: Optional[WorkRegime] = None
    monthly_hours_target: Optional[float] = None
    velocidade_limpeza_vago_sujo: Optional[float] = None
    velocidade_limpeza_estada: Optional[float] = None
    carga_horaria_max_semana: Optional[float] = None
    unavailable_days: Optional[List[str]] = None
    time_off_preferences: Optional[List[str]] = None
    restrictions: Optional[List[str]] = None
    last_full_week_off: Optional[date] = None
    vacation_period_start: Optional[date] = None
    vacation_period_end: Optional[date] = None
    hours_history: Optional[List[dict]] = None
    shifts_history: Optional[List[dict]] = None
    convocation_history: Optional[List[dict]] = None
    hire_date: Optional[date] = None
    is_active: Optional[bool] = None


class EmployeeResponse(EmployeeBase):
    id: int
    last_full_week_off: Optional[date] = None
    vacation_period_start: Optional[date] = None
    vacation_period_end: Optional[date] = None
    hours_history: List[dict] = []
    shifts_history: List[dict] = []
    convocation_history: List[dict] = []
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class EmployeeListResponse(BaseModel):
    id: int
    name: str
    sector_id: int
    sector_name: Optional[str] = None
    role_id: int
    role_name: Optional[str] = None
    contract_type: ContractType
    is_active: bool

    class Config:
        from_attributes = True
