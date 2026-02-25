"""
Schemas do Agente Decisorio - Contratos de API para os 4 Nucleos de Inteligencia

Versao: 1.0.0
Data: 2026-01-14
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date, datetime, time
from enum import Enum


class HPSourceType(str, Enum):
    """Origem dos dados de HP"""
    HISTORICO = "HISTORICO"
    PREVISAO = "PREVISAO"


class EmployeeType(str, Enum):
    """Tipo de colaborador"""
    FIXO = "FIXO"
    INTERMITENTE = "INTERMITENTE"


class RuleType(str, Enum):
    """Tipo de regra aplicada"""
    LABOR = "LABOR"
    OPERATIONAL = "OPERATIONAL"
    SECTOR = "SECTOR"


class RuleStatus(str, Enum):
    """Status de aplicacao da regra"""
    APPLIED = "APPLIED"
    VIOLATED = "VIOLATED"
    SKIPPED = "SKIPPED"


class ScheduleStatus(str, Enum):
    """Status do workflow de aprovacao"""
    DRAFT = "DRAFT"
    UNDER_REVIEW = "UNDER_REVIEW"
    CONTESTED = "CONTESTED"
    RECALCULATING = "RECALCULATING"
    APPROVED = "APPROVED"
    BLOCKED = "BLOCKED"


class DailyDemand(BaseModel):
    """Demanda diaria calculada"""
    date: date
    weekday: str
    hp_source: HPSourceType
    occupancy_pct: float = Field(ge=0, le=100)
    occupancy_rooms: int = Field(ge=0)
    departures: int = Field(ge=0)
    arrivals: int = Field(ge=0)
    stayovers: int = Field(ge=0)
    minutes_variable: float = Field(ge=0, description="Minutos de limpeza variavel (ocupacao)")
    minutes_constant: float = Field(ge=0, description="Minutos de atividades constantes")
    minutes_recurrent: float = Field(ge=0, description="Minutos de atividades recorrentes")
    minutes_eventual: float = Field(ge=0, description="Minutos de atividades eventuais")
    minutes_raw: float = Field(ge=0, description="Total bruto sem ajustes")
    minutes_with_variance: float = Field(ge=0, description="Total com variancia estatistica")
    minutes_with_safety: float = Field(ge=0, description="Total com margem de seguranca")
    variance_applied: float = Field(description="Fator de variancia aplicado")
    safety_margin_applied: float = Field(description="Margem de seguranca aplicada")


class WeeklyTotals(BaseModel):
    """Totais semanais de demanda"""
    minutes_variable: float = Field(ge=0)
    minutes_constant: float = Field(ge=0)
    minutes_recurrent: float = Field(ge=0)
    minutes_eventual: float = Field(ge=0)
    minutes_total: float = Field(ge=0)
    hours_total: float = Field(ge=0)


class RuleApplied(BaseModel):
    """Regra aplicada no calculo"""
    rule_id: Optional[int] = None
    rule_name: str
    rule_type: RuleType
    priority: int
    action_taken: str
    impact_value: Optional[float] = None


class DataSourceUsed(BaseModel):
    """Fonte de dados utilizada"""
    source_name: str
    source_type: str
    records_count: int
    date_range_start: Optional[date] = None
    date_range_end: Optional[date] = None


class DemandIntelligenceOutput(BaseModel):
    """Saida do Nucleo 1: Inteligencia de Demanda"""
    sector_id: int
    sector_name: str
    week_start: date
    week_end: date
    daily_demands: List[DailyDemand]
    weekly_totals: WeeklyTotals
    rules_applied: List[RuleApplied] = []
    data_sources: List[DataSourceUsed] = []
    calculation_timestamp: datetime
    errors: List[str] = []
    warnings: List[str] = []


class DailyAvailability(BaseModel):
    """Disponibilidade diaria de um colaborador"""
    available: bool
    hours_max: float = Field(ge=0)
    reason_unavailable: Optional[str] = None


class EmployeeCapacity(BaseModel):
    """Capacidade de um colaborador"""
    employee_id: int
    employee_name: str
    employee_type: EmployeeType
    weekly_hours_max: float = Field(ge=0)
    weekly_hours_available: float = Field(ge=0)
    daily_availability: Dict[str, DailyAvailability]
    restrictions: List[str] = []


class CapacitySummary(BaseModel):
    """Resumo de capacidade do setor"""
    total_employees: int = Field(ge=0)
    fixed_count: int = Field(ge=0)
    intermittent_count: int = Field(ge=0)
    total_hours_available: float = Field(ge=0)
    max_utilization_pct: float = Field(ge=0, le=100)
    effective_hours: float = Field(ge=0)


class CapacityIntelligenceOutput(BaseModel):
    """Saida do Nucleo 2: Inteligencia de Capacidade"""
    sector_id: int
    sector_name: str
    week_start: date
    week_end: date
    employees: List[EmployeeCapacity]
    capacity_summary: CapacitySummary
    labor_rules_applied: List[RuleApplied] = []
    calculation_timestamp: datetime
    errors: List[str] = []
    warnings: List[str] = []


class ScheduleEntry(BaseModel):
    """Entrada de escala para um colaborador/dia"""
    date: date
    weekday: str
    employee_id: int
    employee_name: str
    shift_start: Optional[time] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    shift_end: Optional[time] = None
    hours_worked: float = Field(ge=0)
    activities: List[str] = []
    is_off_day: bool = False


class HourlyCoverage(BaseModel):
    """Cobertura horaria"""
    employees_count: int = Field(ge=0)
    capacity_minutes: float = Field(ge=0)


class BalanceMetrics(BaseModel):
    """Metricas de equilibrio da escala"""
    employee_hours: Dict[int, float]
    hours_mean: float
    hours_std_dev: float
    balance_score: float = Field(ge=0, le=100, description="100 = perfeitamente equilibrado")


class SchedulingIntelligenceOutput(BaseModel):
    """Saida do Nucleo 3: Inteligencia de Escalonamento"""
    sector_id: int
    sector_name: str
    week_start: date
    week_end: date
    schedule_entries: List[ScheduleEntry]
    hourly_coverage: Dict[str, Dict[str, HourlyCoverage]]
    balance_metrics: BalanceMetrics
    shift_patterns_used: List[str] = []
    calculation_timestamp: datetime
    errors: List[str] = []
    warnings: List[str] = []


class RuleHierarchyEntry(BaseModel):
    """Entrada na hierarquia de regras"""
    priority: int
    rule_id: Optional[int] = None
    rule_name: str
    rule_type: RuleType
    status: RuleStatus
    impact_description: str
    is_critical: bool = False
    violation_reason: Optional[str] = None


class ContestationEntry(BaseModel):
    """Entrada no historico de contestacoes"""
    contested_at: datetime
    contested_by: str
    reason: str
    changes_requested: Dict[str, Any]
    resolved: bool = False
    resolution_notes: Optional[str] = None


class CalculationMemory(BaseModel):
    """Memoria de calculo completa"""
    demand_output: DemandIntelligenceOutput
    capacity_output: CapacityIntelligenceOutput
    scheduling_output: SchedulingIntelligenceOutput
    execution_timestamp: datetime
    version: int = 1
    parameters_snapshot: Dict[str, Any] = {}


class GovernanceIntelligenceOutput(BaseModel):
    """Saida do Nucleo 4: Inteligencia de Governanca"""
    schedule_id: int
    sector_id: int
    sector_name: str
    week_start: date
    week_end: date
    status: ScheduleStatus
    calculation_memory: CalculationMemory
    rules_hierarchy: List[RuleHierarchyEntry]
    unmet_rules: List[RuleHierarchyEntry] = []
    can_approve: bool
    blocking_reasons: List[str] = []
    contestation_history: List[ContestationEntry] = []
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DecisionAgentRequest(BaseModel):
    """Requisicao para o Agente Decisorio"""
    sector_id: int
    week_start: date
    include_eventual_activities: bool = True
    eventual_activities_input: Optional[List[Dict[str, Any]]] = None
    force_recalculate: bool = False


class DecisionAgentResponse(BaseModel):
    """Resposta completa do Agente Decisorio"""
    success: bool
    governance_output: Optional[GovernanceIntelligenceOutput] = None
    execution_time_ms: int
    errors: List[str] = []
    warnings: List[str] = []
