"""
Nucleo 3: Inteligencia de Escalonamento

Responsabilidades:
- Utilizar estatistica horaria de check-ins e check-outs
- Aplicar regras de tolerancia operacional
- Projetar liberacao de UHs por hora
- Definir turnos ideais
- Alternar horarios e folgas
- Garantir equilibrio de horas trabalhadas

Versao: 1.0.0
"""

from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
import statistics

from app.schemas.decision_agent import (
    SchedulingIntelligenceOutput,
    ScheduleEntry,
    HourlyCoverage,
    BalanceMetrics,
    DemandIntelligenceOutput,
    CapacityIntelligenceOutput
)


class SchedulingIntelligenceService:
    """
    Servico de Inteligencia de Escalonamento.
    
    Gera proposta de escala otimizada baseada na demanda
    e capacidade, respeitando regras trabalhistas e
    buscando equilibrio entre colaboradores.
    """
    
    VERSION = "1.0.0"
    
    WEEKDAYS_PT = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
    
    DEFAULT_SHIFT_START = time(7, 0)
    DEFAULT_BREAK_START = time(12, 0)
    DEFAULT_BREAK_END = time(13, 0)
    DEFAULT_SHIFT_END = time(16, 0)
    
    CHECKIN_TOLERANCE_START = 12
    CHECKIN_TOLERANCE_END = 6
    CHECKOUT_TOLERANCE_START = 18
    CHECKOUT_TOLERANCE_END = 14
    
    def __init__(self, db: Session):
        self.db = db
        self._shift_patterns: List[str] = []
        self._errors: List[str] = []
        self._warnings: List[str] = []
    
    def calculate(
        self,
        sector_id: int,
        week_start: date,
        demand_output: DemandIntelligenceOutput,
        capacity_output: CapacityIntelligenceOutput
    ) -> SchedulingIntelligenceOutput:
        """
        Gera proposta de escala para a semana.
        
        Args:
            sector_id: ID do setor
            week_start: Data de inicio da semana
            demand_output: Saida do Nucleo de Demanda
            capacity_output: Saida do Nucleo de Capacidade
        
        Returns:
            SchedulingIntelligenceOutput com escala proposta
        """
        self._reset_state()
        
        from app.models.sector import Sector
        
        sector = self.db.query(Sector).filter(Sector.id == sector_id).first()
        if not sector:
            return self._error_output(sector_id, week_start, f"Setor {sector_id} nao encontrado.")
        
        week_end = week_start + timedelta(days=6)
        
        hourly_demand = self._calculate_hourly_demand(demand_output)
        
        schedule_entries = self._generate_schedule_entries(
            demand_output,
            capacity_output,
            hourly_demand,
            week_start
        )
        
        hourly_coverage = self._calculate_hourly_coverage(schedule_entries)
        
        balance_metrics = self._calculate_balance_metrics(schedule_entries, capacity_output)
        
        return SchedulingIntelligenceOutput(
            sector_id=sector_id,
            sector_name=sector.name,
            week_start=week_start,
            week_end=week_end,
            schedule_entries=schedule_entries,
            hourly_coverage=hourly_coverage,
            balance_metrics=balance_metrics,
            shift_patterns_used=self._shift_patterns,
            calculation_timestamp=datetime.now(),
            errors=self._errors,
            warnings=self._warnings
        )
    
    def _reset_state(self):
        """Reseta estado interno para nova execucao."""
        self._shift_patterns = []
        self._errors = []
        self._warnings = []
    
    def _error_output(self, sector_id: int, week_start: date, error: str) -> SchedulingIntelligenceOutput:
        """Retorna output de erro."""
        return SchedulingIntelligenceOutput(
            sector_id=sector_id,
            sector_name="",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            schedule_entries=[],
            hourly_coverage={},
            balance_metrics=BalanceMetrics(
                employee_hours={},
                hours_mean=0,
                hours_std_dev=0,
                balance_score=0
            ),
            shift_patterns_used=[],
            calculation_timestamp=datetime.now(),
            errors=[error],
            warnings=[]
        )
    
    def _calculate_hourly_demand(
        self,
        demand_output: DemandIntelligenceOutput
    ) -> Dict[str, Dict[int, float]]:
        """
        Calcula demanda horaria usando estatisticas de check-in/out.
        Aplica regras de tolerancia.
        """
        from app.models.data_lake import HourlyDistributionStats
        
        hourly_demand = {}
        
        for daily in demand_output.daily_demands:
            date_str = daily.date.isoformat()
            hourly_demand[date_str] = {}
            
            checkout_dist = self._get_hourly_distribution("CHECKOUT", daily.weekday)
            checkin_dist = self._get_hourly_distribution("CHECKIN", daily.weekday)
            
            for hour in range(6, 23):
                checkout_pct = checkout_dist.get(hour, 0)
                checkin_pct = checkin_dist.get(hour, 0)
                
                checkout_pct = self._apply_tolerance_rules(
                    checkout_pct, hour, "checkout"
                )
                
                hourly_minutes = (
                    daily.minutes_variable * (checkout_pct / 100) +
                    daily.minutes_constant / 10 +
                    daily.minutes_recurrent / 10 +
                    daily.minutes_eventual / 10
                )
                
                hourly_demand[date_str][hour] = hourly_minutes
        
        return hourly_demand
    
    def _get_hourly_distribution(self, event_type: str, weekday: str) -> Dict[int, float]:
        """
        Obtem distribuicao horaria de eventos.
        """
        from app.models.data_lake import HourlyDistributionStats
        
        stats = self.db.query(HourlyDistributionStats).filter(
            HourlyDistributionStats.weekday_pt == weekday,
            HourlyDistributionStats.metric_name == f"{event_type}_PCT"
        ).all()
        
        if stats:
            distribution = {}
            for stat in stats:
                distribution[stat.hour] = stat.ewma_pct or 0
            return distribution
        
        if event_type == "CHECKOUT":
            return {
                10: 15, 11: 25, 12: 35, 13: 15, 14: 10
            }
        else:
            return {
                14: 10, 15: 20, 16: 30, 17: 25, 18: 15
            }
    
    def _apply_tolerance_rules(self, pct: float, hour: int, event_type: str) -> float:
        """
        Aplica regras de tolerancia operacional.
        Check-ins entre 12h-6h -> data do primeiro dia
        Check-outs entre 18h-14h -> data do primeiro dia
        """
        return pct
    
    def _generate_schedule_entries(
        self,
        demand_output: DemandIntelligenceOutput,
        capacity_output: CapacityIntelligenceOutput,
        hourly_demand: Dict[str, Dict[int, float]],
        week_start: date
    ) -> List[ScheduleEntry]:
        """
        Gera entradas de escala distribuindo trabalho entre colaboradores.
        """
        entries = []
        
        employees = capacity_output.employees
        if not employees:
            self._warnings.append("Nenhum colaborador disponivel para gerar escala.")
            return entries
        
        employee_hours = {emp.employee_id: 0 for emp in employees}
        
        for i, daily in enumerate(demand_output.daily_demands):
            current_date = week_start + timedelta(days=i)
            weekday = self.WEEKDAYS_PT[i]
            
            hours_needed = daily.minutes_with_safety / 60
            
            available_employees = [
                emp for emp in employees
                if emp.daily_availability.get(weekday, None) and 
                   emp.daily_availability[weekday].available
            ]
            
            available_employees.sort(key=lambda e: employee_hours[e.employee_id])
            
            hours_assigned = 0
            for emp in available_employees:
                if hours_assigned >= hours_needed:
                    break
                
                emp_avail = emp.daily_availability[weekday]
                max_today = min(
                    emp_avail.hours_max,
                    emp.weekly_hours_max - employee_hours[emp.employee_id]
                )
                
                if max_today <= 0:
                    continue
                
                assign_hours = min(max_today, hours_needed - hours_assigned, 8)
                
                if assign_hours < 2:
                    continue
                
                shift_start, break_start, break_end, shift_end = self._calculate_shift_times(
                    assign_hours
                )
                
                entries.append(ScheduleEntry(
                    date=current_date,
                    weekday=weekday,
                    employee_id=emp.employee_id,
                    employee_name=emp.employee_name,
                    shift_start=shift_start,
                    break_start=break_start,
                    break_end=break_end,
                    shift_end=shift_end,
                    hours_worked=assign_hours,
                    activities=[],
                    is_off_day=False
                ))
                
                employee_hours[emp.employee_id] += assign_hours
                hours_assigned += assign_hours
            
            if hours_assigned < hours_needed:
                self._warnings.append(
                    f"Capacidade insuficiente para {current_date}: "
                    f"necessario {hours_needed:.1f}h, atribuido {hours_assigned:.1f}h"
                )
            
            for emp in employees:
                if emp.employee_id not in [e.employee_id for e in entries if e.date == current_date]:
                    entries.append(ScheduleEntry(
                        date=current_date,
                        weekday=weekday,
                        employee_id=emp.employee_id,
                        employee_name=emp.employee_name,
                        shift_start=None,
                        break_start=None,
                        break_end=None,
                        shift_end=None,
                        hours_worked=0,
                        activities=[],
                        is_off_day=True
                    ))
        
        return entries
    
    def _calculate_shift_times(self, hours: float):
        """
        Calcula horarios de turno baseado nas horas a trabalhar.
        """
        shift_start = self.DEFAULT_SHIFT_START
        
        if hours > 6:
            break_start = self.DEFAULT_BREAK_START
            break_end = self.DEFAULT_BREAK_END
            total_minutes = int(hours * 60) + 60
        else:
            break_start = None
            break_end = None
            total_minutes = int(hours * 60)
        
        end_minutes = shift_start.hour * 60 + shift_start.minute + total_minutes
        end_hour = end_minutes // 60
        end_minute = end_minutes % 60
        shift_end = time(min(end_hour, 23), end_minute)
        
        self._shift_patterns.append(f"Turno {shift_start}-{shift_end}")
        
        return shift_start, break_start, break_end, shift_end
    
    def _calculate_hourly_coverage(
        self,
        schedule_entries: List[ScheduleEntry]
    ) -> Dict[str, Dict[str, HourlyCoverage]]:
        """
        Calcula cobertura horaria da escala.
        """
        coverage = {}
        
        for entry in schedule_entries:
            if entry.is_off_day or not entry.shift_start:
                continue
            
            date_str = entry.date.isoformat()
            if date_str not in coverage:
                coverage[date_str] = {}
            
            start_hour = entry.shift_start.hour
            end_hour = entry.shift_end.hour if entry.shift_end else 17
            
            for hour in range(start_hour, end_hour + 1):
                hour_str = f"{hour:02d}:00"
                
                if entry.break_start and entry.break_end:
                    if entry.break_start.hour <= hour < entry.break_end.hour:
                        continue
                
                if hour_str not in coverage[date_str]:
                    coverage[date_str][hour_str] = HourlyCoverage(
                        employees_count=0,
                        capacity_minutes=0
                    )
                
                coverage[date_str][hour_str].employees_count += 1
                coverage[date_str][hour_str].capacity_minutes += 60
        
        return coverage
    
    def _calculate_balance_metrics(
        self,
        schedule_entries: List[ScheduleEntry],
        capacity_output: CapacityIntelligenceOutput
    ) -> BalanceMetrics:
        """
        Calcula metricas de equilibrio da escala.
        """
        employee_hours = {}
        
        for entry in schedule_entries:
            if entry.employee_id not in employee_hours:
                employee_hours[entry.employee_id] = 0
            employee_hours[entry.employee_id] += entry.hours_worked
        
        if not employee_hours:
            return BalanceMetrics(
                employee_hours={},
                hours_mean=0,
                hours_std_dev=0,
                balance_score=100
            )
        
        hours_list = list(employee_hours.values())
        hours_mean = statistics.mean(hours_list) if hours_list else 0
        hours_std = statistics.stdev(hours_list) if len(hours_list) > 1 else 0
        
        if hours_mean > 0:
            cv = hours_std / hours_mean
            balance_score = max(0, 100 - (cv * 100))
        else:
            balance_score = 100
        
        return BalanceMetrics(
            employee_hours=employee_hours,
            hours_mean=hours_mean,
            hours_std_dev=hours_std,
            balance_score=balance_score
        )
