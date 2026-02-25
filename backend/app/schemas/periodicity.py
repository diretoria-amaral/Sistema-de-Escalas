from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class PeriodicityType(str, Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    FORTNIGHTLY = "FORTNIGHTLY"
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    YEARLY = "YEARLY"
    CUSTOM = "CUSTOM"


class IntervalUnit(str, Enum):
    DAYS = "DAYS"
    MONTHS = "MONTHS"
    YEARS = "YEARS"


class AnchorPolicy(str, Enum):
    SAME_DAY = "SAME_DAY"
    LAST_DAY_IF_MISSING = "LAST_DAY_IF_MISSING"


class PeriodicityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Nome da periodicidade")
    tipo: Optional[PeriodicityType] = Field(None, description="Tipo da periodicidade (opcional, inferido do intervalo)")
    interval_unit: IntervalUnit = Field(IntervalUnit.DAYS, description="Unidade do intervalo: DAYS, MONTHS ou YEARS")
    interval_value: int = Field(1, ge=1, description="Valor do intervalo (ex: 3 para trimestral)")
    anchor_policy: AnchorPolicy = Field(AnchorPolicy.SAME_DAY, description="Politica para datas invalidas (ex: 31/jan + 1 mes)")
    description: Optional[str] = Field(None, max_length=500, description="Descrição opcional")
    is_active: bool = Field(True, description="Se a periodicidade está ativa")


class PeriodicityCreate(PeriodicityBase):
    intervalo_dias: Optional[int] = Field(None, ge=1, description="Intervalo em dias (retrocompatibilidade, use interval_unit+interval_value)")
    
    def model_post_init(self, __context):
        if self.intervalo_dias is not None and self.interval_unit == IntervalUnit.DAYS and self.interval_value == 1:
            object.__setattr__(self, 'interval_value', self.intervalo_dias)


class PeriodicityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tipo: Optional[PeriodicityType] = None
    interval_unit: Optional[IntervalUnit] = None
    interval_value: Optional[int] = Field(None, ge=1)
    anchor_policy: Optional[AnchorPolicy] = None
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None
    intervalo_dias: Optional[int] = Field(None, ge=1, description="Intervalo em dias (retrocompatibilidade)")
    
    def model_post_init(self, __context):
        if self.intervalo_dias is not None and self.interval_unit is None and self.interval_value is None:
            object.__setattr__(self, 'interval_unit', IntervalUnit.DAYS)
            object.__setattr__(self, 'interval_value', self.intervalo_dias)


class PeriodicityResponse(PeriodicityBase):
    id: int
    intervalo_dias: int = Field(description="Intervalo aproximado em dias (para retrocompatibilidade)")
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
