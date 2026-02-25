from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import date, datetime
from enum import Enum


class TipoRegra(str, Enum):
    LABOR = "LABOR"
    SYSTEM = "SYSTEM"
    OPERATIONAL = "OPERATIONAL"
    CALCULATION = "CALCULATION"


class NivelRigidez(str, Enum):
    MANDATORY = "MANDATORY"
    DESIRABLE = "DESIRABLE"
    FLEXIBLE = "FLEXIBLE"


class SectorRuleBase(BaseModel):
    setor_id: Optional[int] = None
    is_global: bool = False
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    prioridade: int = Field(default=1, ge=1)
    title: str = Field(..., max_length=200, description="Titulo da regra")
    pergunta: str
    resposta: str
    regra_ativa: bool = True
    validade_inicio: Optional[date] = None
    validade_fim: Optional[date] = None


class SectorRuleCreate(SectorRuleBase):
    pass


class SectorRuleUpdate(BaseModel):
    tipo_regra: Optional[TipoRegra] = None
    nivel_rigidez: Optional[NivelRigidez] = None
    prioridade: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, max_length=200)
    pergunta: Optional[str] = None
    resposta: Optional[str] = None
    regra_ativa: Optional[bool] = None
    validade_inicio: Optional[date] = None
    validade_fim: Optional[date] = None


class SectorRuleResponse(BaseModel):
    id: int
    setor_id: Optional[int] = None
    is_global: bool = False
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    prioridade: int
    codigo_regra: str
    title: Optional[str] = None
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


class SectorRuleListResponse(BaseModel):
    items: List[SectorRuleResponse]
    total: int


class ReorderRequest(BaseModel):
    rule_ids: List[int] = Field(..., description="Lista ordenada de IDs de regras")


class CloneRequest(BaseModel):
    new_title: str = Field(..., max_length=200, description="Novo titulo para a regra clonada")


class RuleHierarchyItem(BaseModel):
    codigo_regra: str
    title: Optional[str] = None
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    prioridade: int
    pergunta: str
    resposta: str
    regra_ativa: bool


class RuleHierarchyResponse(BaseModel):
    setor_id: int
    setor_name: str
    labor_rules: List[RuleHierarchyItem]
    system_rules: List[RuleHierarchyItem]
    operational_rules: List[RuleHierarchyItem]
    calculation_rules: List[RuleHierarchyItem]
    total_rules: int
