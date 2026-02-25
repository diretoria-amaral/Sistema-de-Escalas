from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum

from app.models.sector_rule import TipoRegra, NivelRigidez


class RuleCreate(BaseModel):
    setor_id: int
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    prioridade: int = Field(default=1, ge=1)
    codigo_regra: str = Field(..., max_length=50)
    pergunta: str
    resposta: str
    regra_ativa: bool = True
    validade_inicio: Optional[date] = None
    validade_fim: Optional[date] = None
    metadados_json: Optional[Dict[str, Any]] = None


class RuleUpdate(BaseModel):
    pergunta: Optional[str] = None
    resposta: Optional[str] = None
    nivel_rigidez: Optional[NivelRigidez] = None
    prioridade: Optional[int] = Field(default=None, ge=1)
    regra_ativa: Optional[bool] = None
    validade_inicio: Optional[date] = None
    validade_fim: Optional[date] = None
    metadados_json: Optional[Dict[str, Any]] = None


class RuleResponse(BaseModel):
    id: int
    setor_id: Optional[int] = None
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    prioridade: int
    codigo_regra: str
    title: Optional[str] = None
    is_global: bool = False
    pergunta: str
    resposta: str
    regra_ativa: bool
    validade_inicio: Optional[date] = None
    validade_fim: Optional[date] = None
    metadados_json: Optional[Dict[str, Any]] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RuleListResponse(BaseModel):
    items: List[RuleResponse]
    total: int


class ReorderPayload(BaseModel):
    sector_id: int
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    ordered_rule_ids: List[int]


class GroupedRulesResponse(BaseModel):
    labor: Dict[str, List[RuleResponse]] = {}
    operational: Dict[str, List[RuleResponse]] = {}
    calculation: Dict[str, List[RuleResponse]] = {}


class RuleApplicationResponse(BaseModel):
    codigo_regra: str
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    applied: bool
    reason: Optional[str] = None
    params: Dict[str, Any] = {}


class RuleExecutionResultResponse(BaseModel):
    applied_rules: List[RuleApplicationResponse]
    violated_rules: List[RuleApplicationResponse]
    warnings: List[str]
    has_mandatory_violations: bool


class LaborConstraintsResponse(BaseModel):
    max_hours_weekly: int
    max_hours_daily: int
    min_rest_between_shifts: int
    advance_notice_hours: int


class ConsistencyCheckResponse(BaseModel):
    is_valid: bool
    errors: List[str]
