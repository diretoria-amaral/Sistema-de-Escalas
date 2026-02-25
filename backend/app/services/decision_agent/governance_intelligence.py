"""
Nucleo 4: Inteligencia de Governanca

Responsabilidades:
- Gerar escala semanal SUGESTIVA
- Exibir memoria de calculo completa
- Indicar hierarquia de regras aplicadas
- Indicar regras nao atendidas
- Permitir ciclo de aprovacao/contestacao
- Bloquear aprovacao se regras criticas violadas

Versao: 1.0.0
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session

from app.schemas.decision_agent import (
    GovernanceIntelligenceOutput,
    CalculationMemory,
    RuleHierarchyEntry,
    ContestationEntry,
    DemandIntelligenceOutput,
    CapacityIntelligenceOutput,
    SchedulingIntelligenceOutput,
    ScheduleStatus,
    RuleType,
    RuleStatus
)


class GovernanceIntelligenceService:
    """
    Servico de Inteligencia de Governanca.
    
    Orquestra os outros nucleos e gerencia o workflow
    de aprovacao de escalas, mantendo memoria de calculo
    e auditoria de decisoes.
    """
    
    VERSION = "1.0.0"
    
    CRITICAL_RULES = [
        "Limite semanal CLT",
        "Intervalo minimo entre jornadas",
        "Folga semanal obrigatoria",
        "Antecedencia minima convocacao intermitente"
    ]
    
    def __init__(self, db: Session):
        self.db = db
        self._errors: List[str] = []
        self._warnings: List[str] = []
    
    def evaluate(
        self,
        sector_id: int,
        week_start: date,
        demand_output: DemandIntelligenceOutput,
        capacity_output: CapacityIntelligenceOutput,
        scheduling_output: SchedulingIntelligenceOutput,
        schedule_id: Optional[int] = None
    ) -> GovernanceIntelligenceOutput:
        """
        Avalia a escala gerada e prepara para aprovacao.
        
        Args:
            sector_id: ID do setor
            week_start: Data de inicio da semana
            demand_output: Saida do Nucleo de Demanda
            capacity_output: Saida do Nucleo de Capacidade
            scheduling_output: Saida do Nucleo de Escalonamento
            schedule_id: ID da escala (se ja existir)
        
        Returns:
            GovernanceIntelligenceOutput com avaliacao completa
        """
        self._reset_state()
        
        from app.models.sector import Sector
        
        sector = self.db.query(Sector).filter(Sector.id == sector_id).first()
        if not sector:
            return self._error_output(sector_id, week_start, f"Setor {sector_id} nao encontrado.")
        
        week_end = week_start + timedelta(days=6)
        
        calculation_memory = CalculationMemory(
            demand_output=demand_output,
            capacity_output=capacity_output,
            scheduling_output=scheduling_output,
            execution_timestamp=datetime.now(),
            version=1,
            parameters_snapshot=self._capture_parameters_snapshot(sector_id)
        )
        
        rules_hierarchy = self._build_rules_hierarchy(
            demand_output,
            capacity_output,
            scheduling_output
        )
        
        unmet_rules = [r for r in rules_hierarchy if r.status == RuleStatus.VIOLATED]
        
        blocking_reasons = self._check_blocking_conditions(
            demand_output,
            capacity_output,
            scheduling_output,
            rules_hierarchy
        )
        
        can_approve = len(blocking_reasons) == 0
        
        status = ScheduleStatus.BLOCKED if not can_approve else ScheduleStatus.DRAFT
        
        if not schedule_id:
            schedule_id = self._generate_schedule_id()
        
        return GovernanceIntelligenceOutput(
            schedule_id=schedule_id,
            sector_id=sector_id,
            sector_name=sector.name,
            week_start=week_start,
            week_end=week_end,
            status=status,
            calculation_memory=calculation_memory,
            rules_hierarchy=rules_hierarchy,
            unmet_rules=unmet_rules,
            can_approve=can_approve,
            blocking_reasons=blocking_reasons,
            contestation_history=[],
            approved_by=None,
            approved_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def approve(
        self,
        governance_output: GovernanceIntelligenceOutput,
        approved_by: str
    ) -> GovernanceIntelligenceOutput:
        """
        Aprova a escala se todas as condicoes forem atendidas.
        """
        if not governance_output.can_approve:
            governance_output.status = ScheduleStatus.BLOCKED
            self._errors.append("Escala nao pode ser aprovada: existem regras criticas violadas.")
            return governance_output
        
        governance_output.status = ScheduleStatus.APPROVED
        governance_output.approved_by = approved_by
        governance_output.approved_at = datetime.now()
        governance_output.updated_at = datetime.now()
        
        return governance_output
    
    def contest(
        self,
        governance_output: GovernanceIntelligenceOutput,
        contested_by: str,
        reason: str,
        changes_requested: Dict[str, Any]
    ) -> GovernanceIntelligenceOutput:
        """
        Registra contestacao e solicita recalculo.
        """
        contestation = ContestationEntry(
            contested_at=datetime.now(),
            contested_by=contested_by,
            reason=reason,
            changes_requested=changes_requested,
            resolved=False
        )
        
        governance_output.contestation_history.append(contestation)
        governance_output.status = ScheduleStatus.CONTESTED
        governance_output.updated_at = datetime.now()
        
        return governance_output
    
    def _reset_state(self):
        """Reseta estado interno para nova execucao."""
        self._errors = []
        self._warnings = []
    
    def _error_output(self, sector_id: int, week_start: date, error: str) -> GovernanceIntelligenceOutput:
        """Retorna output de erro."""
        empty_demand = DemandIntelligenceOutput(
            sector_id=sector_id,
            sector_name="",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            daily_demands=[],
            weekly_totals=None,
            rules_applied=[],
            data_sources=[],
            calculation_timestamp=datetime.now(),
            errors=[error],
            warnings=[]
        )
        empty_capacity = CapacityIntelligenceOutput(
            sector_id=sector_id,
            sector_name="",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            employees=[],
            capacity_summary=None,
            labor_rules_applied=[],
            calculation_timestamp=datetime.now(),
            errors=[error],
            warnings=[]
        )
        empty_scheduling = SchedulingIntelligenceOutput(
            sector_id=sector_id,
            sector_name="",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            schedule_entries=[],
            hourly_coverage={},
            balance_metrics=None,
            shift_patterns_used=[],
            calculation_timestamp=datetime.now(),
            errors=[error],
            warnings=[]
        )
        
        return GovernanceIntelligenceOutput(
            schedule_id=0,
            sector_id=sector_id,
            sector_name="",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            status=ScheduleStatus.BLOCKED,
            calculation_memory=CalculationMemory(
                demand_output=empty_demand,
                capacity_output=empty_capacity,
                scheduling_output=empty_scheduling,
                execution_timestamp=datetime.now(),
                version=1
            ),
            rules_hierarchy=[],
            unmet_rules=[],
            can_approve=False,
            blocking_reasons=[error],
            contestation_history=[],
            approved_by=None,
            approved_at=None,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
    
    def _generate_schedule_id(self) -> int:
        """Gera ID temporario para nova escala."""
        return int(datetime.now().timestamp())
    
    def _capture_parameters_snapshot(self, sector_id: int) -> Dict[str, Any]:
        """Captura snapshot dos parametros do setor."""
        from app.models.governance_module import SectorOperationalParameters
        
        params = self.db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == sector_id
        ).first()
        
        if params:
            return {
                "total_rooms": params.total_rooms,
                "cleaning_time_vago_sujo_min": params.cleaning_time_vago_sujo_min,
                "cleaning_time_estadia_min": params.cleaning_time_estadia_min,
                "buffer_pct": params.buffer_pct,
                "target_utilization_pct": params.target_utilization_pct,
                "shift_templates": params.shift_templates
            }
        
        return {}
    
    def _build_rules_hierarchy(
        self,
        demand_output: DemandIntelligenceOutput,
        capacity_output: CapacityIntelligenceOutput,
        scheduling_output: SchedulingIntelligenceOutput
    ) -> List[RuleHierarchyEntry]:
        """
        Constroi hierarquia de todas as regras aplicadas.
        """
        hierarchy = []
        priority = 1
        
        for rule in capacity_output.labor_rules_applied:
            is_critical = rule.rule_name in self.CRITICAL_RULES
            
            hierarchy.append(RuleHierarchyEntry(
                priority=priority,
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                status=RuleStatus.APPLIED,
                impact_description=rule.action_taken,
                is_critical=is_critical
            ))
            priority += 1
        
        for rule in demand_output.rules_applied:
            hierarchy.append(RuleHierarchyEntry(
                priority=priority,
                rule_id=rule.rule_id,
                rule_name=rule.rule_name,
                rule_type=rule.rule_type,
                status=RuleStatus.APPLIED,
                impact_description=rule.action_taken,
                is_critical=False
            ))
            priority += 1
        
        weekly_violations = self._check_weekly_hours_violations(scheduling_output)
        for violation in weekly_violations:
            hierarchy.append(RuleHierarchyEntry(
                priority=priority,
                rule_name="Limite semanal CLT",
                rule_type=RuleType.LABOR,
                status=RuleStatus.VIOLATED,
                impact_description=violation,
                is_critical=True,
                violation_reason=violation
            ))
            priority += 1
        
        return hierarchy
    
    def _check_weekly_hours_violations(
        self,
        scheduling_output: SchedulingIntelligenceOutput
    ) -> List[str]:
        """
        Verifica violacoes de limite semanal de horas.
        """
        violations = []
        
        if scheduling_output.balance_metrics:
            for emp_id, hours in scheduling_output.balance_metrics.employee_hours.items():
                if hours > 44:
                    violations.append(
                        f"Colaborador {emp_id} excede limite semanal: {hours:.1f}h (max 44h)"
                    )
        
        return violations
    
    def _check_blocking_conditions(
        self,
        demand_output: DemandIntelligenceOutput,
        capacity_output: CapacityIntelligenceOutput,
        scheduling_output: SchedulingIntelligenceOutput,
        rules_hierarchy: List[RuleHierarchyEntry]
    ) -> List[str]:
        """
        Verifica condicoes que bloqueiam aprovacao.
        """
        blocking = []
        
        critical_violations = [
            r for r in rules_hierarchy 
            if r.is_critical and r.status == RuleStatus.VIOLATED
        ]
        for violation in critical_violations:
            blocking.append(f"Regra critica violada: {violation.rule_name}")
        
        if demand_output.errors:
            blocking.extend(demand_output.errors)
        if capacity_output.errors:
            blocking.extend(capacity_output.errors)
        if scheduling_output.errors:
            blocking.extend(scheduling_output.errors)
        
        if not capacity_output.employees:
            blocking.append("Nenhum colaborador disponivel para o setor.")
        
        if demand_output.weekly_totals:
            demand_hours = demand_output.weekly_totals.hours_total
            capacity_hours = capacity_output.capacity_summary.effective_hours if capacity_output.capacity_summary else 0
            
            if demand_hours > capacity_hours * 1.2:
                blocking.append(
                    f"Demanda ({demand_hours:.1f}h) excede capacidade efetiva ({capacity_hours:.1f}h) em mais de 20%."
                )
        
        return blocking
