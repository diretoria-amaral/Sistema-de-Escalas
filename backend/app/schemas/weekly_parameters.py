from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
from app.models.weekly_parameters import DayType


class DayParameters(BaseModel):
    ocupacao_prevista: float = 0.0
    quartos_vagos_sujos: int = 0
    quartos_estada: int = 0
    tipo_dia: DayType = DayType.NORMAL


class WeeklyParametersBase(BaseModel):
    sector_id: Optional[int] = None
    semana_inicio: date
    seg_ocupacao_prevista: float = 0.0
    seg_quartos_vagos_sujos: int = 0
    seg_quartos_estada: int = 0
    seg_tipo_dia: DayType = DayType.NORMAL
    ter_ocupacao_prevista: float = 0.0
    ter_quartos_vagos_sujos: int = 0
    ter_quartos_estada: int = 0
    ter_tipo_dia: DayType = DayType.NORMAL
    qua_ocupacao_prevista: float = 0.0
    qua_quartos_vagos_sujos: int = 0
    qua_quartos_estada: int = 0
    qua_tipo_dia: DayType = DayType.NORMAL
    qui_ocupacao_prevista: float = 0.0
    qui_quartos_vagos_sujos: int = 0
    qui_quartos_estada: int = 0
    qui_tipo_dia: DayType = DayType.NORMAL
    sex_ocupacao_prevista: float = 0.0
    sex_quartos_vagos_sujos: int = 0
    sex_quartos_estada: int = 0
    sex_tipo_dia: DayType = DayType.NORMAL
    sab_ocupacao_prevista: float = 0.0
    sab_quartos_vagos_sujos: int = 0
    sab_quartos_estada: int = 0
    sab_tipo_dia: DayType = DayType.NORMAL
    dom_ocupacao_prevista: float = 0.0
    dom_quartos_vagos_sujos: int = 0
    dom_quartos_estada: int = 0
    dom_tipo_dia: DayType = DayType.NORMAL


class WeeklyParametersCreate(WeeklyParametersBase):
    pass


class WeeklyParametersUpdate(BaseModel):
    seg_ocupacao_prevista: Optional[float] = None
    seg_quartos_vagos_sujos: Optional[int] = None
    seg_quartos_estada: Optional[int] = None
    seg_tipo_dia: Optional[DayType] = None
    ter_ocupacao_prevista: Optional[float] = None
    ter_quartos_vagos_sujos: Optional[int] = None
    ter_quartos_estada: Optional[int] = None
    ter_tipo_dia: Optional[DayType] = None
    qua_ocupacao_prevista: Optional[float] = None
    qua_quartos_vagos_sujos: Optional[int] = None
    qua_quartos_estada: Optional[int] = None
    qua_tipo_dia: Optional[DayType] = None
    qui_ocupacao_prevista: Optional[float] = None
    qui_quartos_vagos_sujos: Optional[int] = None
    qui_quartos_estada: Optional[int] = None
    qui_tipo_dia: Optional[DayType] = None
    sex_ocupacao_prevista: Optional[float] = None
    sex_quartos_vagos_sujos: Optional[int] = None
    sex_quartos_estada: Optional[int] = None
    sex_tipo_dia: Optional[DayType] = None
    sab_ocupacao_prevista: Optional[float] = None
    sab_quartos_vagos_sujos: Optional[int] = None
    sab_quartos_estada: Optional[int] = None
    sab_tipo_dia: Optional[DayType] = None
    dom_ocupacao_prevista: Optional[float] = None
    dom_quartos_vagos_sujos: Optional[int] = None
    dom_quartos_estada: Optional[int] = None
    dom_tipo_dia: Optional[DayType] = None


class WeeklyParametersResponse(WeeklyParametersBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
