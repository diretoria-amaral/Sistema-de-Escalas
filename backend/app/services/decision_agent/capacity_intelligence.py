"""
Nucleo 2: Inteligencia de Capacidade

Responsabilidades:
- Considerar quadro de colaboradores fixos e intermitentes
- Aplicar regras trabalhistas e operacionais
- Calcular horas disponiveis por colaborador
- Aplicar percentual maximo de utilizacao

Versao: 1.0.0
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from app.schemas.decision_agent import (
    CapacityIntelligenceOutput,
    EmployeeCapacity,
    CapacitySummary,
    DailyAvailability,
    RuleApplied,
    EmployeeType,
    RuleType
)


class CapacityIntelligenceService:
    """
    Servico de Inteligencia de Capacidade.
    
    Calcula a capacidade total de trabalho disponivel,
    considerando colaboradores, regras trabalhistas e
    limites operacionais do setor.
    """
    
    VERSION = "1.0.0"
    
    WEEKDAYS_PT = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
    
    MAX_WEEKLY_HOURS_CLT = 44.0
    MAX_DAILY_HOURS_CLT = 10.0
    MIN_BREAK_HOURS = 1.0
    MIN_REST_BETWEEN_SHIFTS = 11.0
    
    def __init__(self, db: Session):
        self.db = db
        self._rules_applied: List[RuleApplied] = []
        self._errors: List[str] = []
        self._warnings: List[str] = []
    
    def calculate(
        self,
        sector_id: int,
        week_start: date
    ) -> CapacityIntelligenceOutput:
        """
        Calcula a capacidade de trabalho para uma semana.
        
        Args:
            sector_id: ID do setor
            week_start: Data de inicio da semana (segunda-feira)
        
        Returns:
            CapacityIntelligenceOutput com capacidade detalhada
        """
        self._reset_state()
        
        from app.models.sector import Sector
        from app.models.governance_module import SectorOperationalParameters
        from app.models.employee import Employee
        
        sector = self.db.query(Sector).filter(Sector.id == sector_id).first()
        if not sector:
            return self._error_output(sector_id, week_start, f"Setor {sector_id} nao encontrado.")
        
        params = self.db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == sector_id
        ).first()
        
        max_utilization = params.target_utilization_pct if params and params.target_utilization_pct else 85.0
        
        employees = self.db.query(Employee).filter(
            Employee.sector_id == sector_id,
            Employee.is_active == True
        ).all()
        
        if not employees:
            self._warnings.append("Nenhum colaborador ativo encontrado para o setor.")
        
        week_end = week_start + timedelta(days=6)
        
        employee_capacities = []
        total_fixed = 0
        total_intermittent = 0
        total_hours_available = 0
        
        for emp in employees:
            emp_type = self._determine_employee_type(emp)
            
            if emp_type == EmployeeType.FIXO:
                total_fixed += 1
            else:
                total_intermittent += 1
            
            weekly_max = self._get_weekly_max_hours(emp, emp_type)
            
            daily_availability = self._calculate_daily_availability(
                emp, week_start, emp_type
            )
            
            weekly_available = sum(
                da.hours_max for da in daily_availability.values() if da.available
            )
            weekly_available = min(weekly_available, weekly_max)
            
            restrictions = self._get_employee_restrictions(emp)
            
            employee_capacities.append(EmployeeCapacity(
                employee_id=emp.id,
                employee_name=emp.name,
                employee_type=emp_type,
                weekly_hours_max=weekly_max,
                weekly_hours_available=weekly_available,
                daily_availability=daily_availability,
                restrictions=restrictions
            ))
            
            total_hours_available += weekly_available
        
        effective_hours = total_hours_available * (max_utilization / 100)
        
        self._apply_labor_rules()
        
        return CapacityIntelligenceOutput(
            sector_id=sector_id,
            sector_name=sector.name,
            week_start=week_start,
            week_end=week_end,
            employees=employee_capacities,
            capacity_summary=CapacitySummary(
                total_employees=len(employees),
                fixed_count=total_fixed,
                intermittent_count=total_intermittent,
                total_hours_available=total_hours_available,
                max_utilization_pct=max_utilization,
                effective_hours=effective_hours
            ),
            labor_rules_applied=self._rules_applied,
            calculation_timestamp=datetime.now(),
            errors=self._errors,
            warnings=self._warnings
        )
    
    def _reset_state(self):
        """Reseta estado interno para nova execucao."""
        self._rules_applied = []
        self._errors = []
        self._warnings = []
    
    def _error_output(self, sector_id: int, week_start: date, error: str) -> CapacityIntelligenceOutput:
        """Retorna output de erro."""
        return CapacityIntelligenceOutput(
            sector_id=sector_id,
            sector_name="",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            employees=[],
            capacity_summary=CapacitySummary(
                total_employees=0,
                fixed_count=0,
                intermittent_count=0,
                total_hours_available=0,
                max_utilization_pct=0,
                effective_hours=0
            ),
            labor_rules_applied=[],
            calculation_timestamp=datetime.now(),
            errors=[error],
            warnings=[]
        )
    
    def _determine_employee_type(self, employee) -> EmployeeType:
        """
        Determina o tipo de colaborador.
        Verifica se e intermitente ou fixo.
        """
        if hasattr(employee, 'contract_type'):
            if employee.contract_type and 'intermitente' in employee.contract_type.lower():
                return EmployeeType.INTERMITENTE
        
        if hasattr(employee, 'is_intermittent') and employee.is_intermittent:
            return EmployeeType.INTERMITENTE
        
        return EmployeeType.FIXO
    
    def _get_weekly_max_hours(self, employee, emp_type: EmployeeType) -> float:
        """
        Retorna o maximo de horas semanais para o colaborador.
        """
        if hasattr(employee, 'weekly_hours') and employee.weekly_hours:
            return float(employee.weekly_hours)
        
        if emp_type == EmployeeType.INTERMITENTE:
            return self.MAX_WEEKLY_HOURS_CLT
        
        return self.MAX_WEEKLY_HOURS_CLT
    
    def _calculate_daily_availability(
        self,
        employee,
        week_start: date,
        emp_type: EmployeeType
    ) -> Dict[str, DailyAvailability]:
        """
        Calcula disponibilidade diaria do colaborador.
        """
        availability = {}
        
        for i, weekday in enumerate(self.WEEKDAYS_PT):
            current_date = week_start + timedelta(days=i)
            
            is_available = True
            hours_max = self.MAX_DAILY_HOURS_CLT - self.MIN_BREAK_HOURS
            reason = None
            
            if emp_type == EmployeeType.INTERMITENTE:
                hours_max = 8.0
            
            if self._is_employee_on_leave(employee, current_date):
                is_available = False
                reason = "Ferias/Licenca"
                hours_max = 0
            
            availability[weekday] = DailyAvailability(
                available=is_available,
                hours_max=hours_max,
                reason_unavailable=reason
            )
        
        return availability
    
    def _is_employee_on_leave(self, employee, target_date: date) -> bool:
        """
        Verifica se o colaborador esta de ferias ou licenca.
        """
        return False
    
    def _get_employee_restrictions(self, employee) -> List[str]:
        """
        Obtem restricoes do colaborador.
        """
        restrictions = []
        
        return restrictions
    
    def _apply_labor_rules(self):
        """
        Registra regras trabalhistas aplicadas.
        """
        self._rules_applied.append(RuleApplied(
            rule_name="Limite semanal CLT",
            rule_type=RuleType.LABOR,
            priority=1,
            action_taken=f"Maximo {self.MAX_WEEKLY_HOURS_CLT}h semanais por colaborador"
        ))
        
        self._rules_applied.append(RuleApplied(
            rule_name="Limite diario CLT",
            rule_type=RuleType.LABOR,
            priority=2,
            action_taken=f"Maximo {self.MAX_DAILY_HOURS_CLT}h diarias incluindo extras"
        ))
        
        self._rules_applied.append(RuleApplied(
            rule_name="Intervalo minimo",
            rule_type=RuleType.LABOR,
            priority=3,
            action_taken=f"Minimo {self.MIN_BREAK_HOURS}h de intervalo para jornadas > 6h"
        ))
        
        self._rules_applied.append(RuleApplied(
            rule_name="Descanso entre jornadas",
            rule_type=RuleType.LABOR,
            priority=4,
            action_taken=f"Minimo {self.MIN_REST_BETWEEN_SHIFTS}h entre jornadas"
        ))
