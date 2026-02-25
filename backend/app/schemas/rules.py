from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class LaborRulesBase(BaseModel):
    min_notice_hours: int = 72
    max_week_hours: float = 44.0
    max_week_hours_with_overtime: float = 48.0
    max_daily_hours: float = 8.0
    min_rest_hours_between_shifts: float = 11.0
    min_break_hours: float = 1.0
    max_break_hours: float = 2.0
    no_break_threshold_hours: float = 4.0
    sundays_off_per_month: int = 1
    vacation_days_annual: int = 30
    allow_vacation_split: bool = True
    max_consecutive_work_days: int = 6
    respect_cbo_activities: bool = True
    overtime_policy_json: Optional[Dict[str, Any]] = None
    intermittent_guardrails_json: Optional[Dict[str, Any]] = None


class LaborRulesUpdate(LaborRulesBase):
    pass


class LaborRulesResponse(LaborRulesBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class SectorOperationalRulesBase(BaseModel):
    utilization_target_pct: float = 85.0
    buffer_pct: float = 10.0
    shift_templates_json: Optional[Dict[str, Any]] = None
    productivity_params_json: Optional[Dict[str, Any]] = None
    indicators_json: Optional[Dict[str, Any]] = None
    alternancia_horarios: bool = True
    alternancia_atividades: bool = True
    regime_preferencial: str = "5x2"
    permitir_alternar_regime: bool = True
    dias_folga_semana: int = 2
    folgas_consecutivas: bool = True
    percentual_max_repeticao_turno: float = 60.0
    percentual_max_repeticao_dia_turno: float = 50.0
    modo_conservador: bool = True
    intervalo_semanas_folga: int = 4


class SectorOperationalRulesCreate(SectorOperationalRulesBase):
    sector_id: int


class SectorOperationalRulesUpdate(SectorOperationalRulesBase):
    pass


class SectorOperationalRulesResponse(SectorOperationalRulesBase):
    id: int
    sector_id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ActivityBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    average_time_minutes: float
    unit_type: Optional[str] = None
    difficulty_level: int = 1
    requires_training: bool = False


class ActivityCreate(ActivityBase):
    sector_id: int


class ActivityUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    average_time_minutes: Optional[float] = None
    unit_type: Optional[str] = None
    difficulty_level: Optional[int] = None
    requires_training: Optional[bool] = None
    sector_id: Optional[int] = None


class ActivityResponse(ActivityBase):
    id: int
    sector_id: int
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    sector_name: Optional[str] = None

    class Config:
        from_attributes = True


class RoleActivityBase(BaseModel):
    role_id: int
    activity_id: int


class RoleActivityCreate(BaseModel):
    activity_id: int


class RoleActivityResponse(RoleActivityBase):
    id: int
    is_active: bool
    created_at: Optional[datetime] = None
    activity_name: Optional[str] = None
    role_name: Optional[str] = None

    class Config:
        from_attributes = True
