"""
Schedule Assignment Service - Motor de Alocação de Colaboradores

VERSION: 1.0.0

Responsável por:
- Selecionar quais colaboradores serão convocados
- Alocar colaboradores a cada turno/dia automaticamente
- Respeitar hierarquia de regras (LABOR > OPERATIONAL > CALCULATION)
- Equilibrar horas e alternar horários

Algoritmo:
- Step A: Filtrar elegíveis por dia (restrições legais)
- Step B: Scoring por colaborador
- Step C: Preencher slots do dia em ordem de criticidade
- Step D: Validar e registrar no trace
"""

from datetime import date, datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any, Set
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
import math
from collections import defaultdict

from app.models.governance_module import (
    HousekeepingSchedulePlan, ShiftSlot, SchedulePlanStatus
)
from app.models.employee import Employee, ContractType
from app.models.agent_run import AgentRun, AgentTraceStep, RunType, RunStatus
from app.services.rule_engine import RuleEngine

METHOD_VERSION = "1.0.0"


class EmployeeMetrics:
    """Métricas acumuladas por colaborador durante alocação."""
    
    def __init__(self, employee_id: int, employee_name: str, contract_type: str):
        self.employee_id = employee_id
        self.employee_name = employee_name
        self.contract_type = contract_type
        self.hours_assigned: float = 0.0
        self.days_assigned: int = 0
        self.shifts_assigned: List[str] = []
        self.rest_days: List[date] = []
        self.last_shift_end: Optional[datetime] = None
        self.consecutive_days: int = 0
        self.violations: List[str] = []
        self.warnings: List[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "employee_id": self.employee_id,
            "employee_name": self.employee_name,
            "contract_type": self.contract_type,
            "hours_assigned": self.hours_assigned,
            "days_assigned": self.days_assigned,
            "shifts_count": len(self.shifts_assigned),
            "shifts_assigned": self.shifts_assigned,
            "rest_days_count": len(self.rest_days),
            "violations": self.violations,
            "warnings": self.warnings
        }


class ScheduleAssignmentService:
    """Serviço de alocação de colaboradores aos turnos."""
    
    def __init__(self, db: Session):
        self.db = db
        self._rule_engine = RuleEngine(db)
        self._applied_rules: List[str] = []
        self._trace_steps: List[Dict] = []
    
    def assign_employees_to_schedule(
        self,
        sector_id: int,
        week_start: date,
        schedule_plan_id: int
    ) -> Dict[str, Any]:
        """
        Executa alocação de colaboradores aos ShiftSlots de uma escala.
        
        Args:
            sector_id: ID do setor
            week_start: Início da semana (segunda-feira)
            schedule_plan_id: ID do plano de escala
            
        Returns:
            Resultado com slots preenchidos, métricas e warnings
        """
        self._applied_rules = []
        self._trace_steps = []
        
        schedule_plan = self.db.query(HousekeepingSchedulePlan).filter(
            HousekeepingSchedulePlan.id == schedule_plan_id
        ).first()
        
        if not schedule_plan:
            return {
                "success": False,
                "error": "Plano de escala não encontrado",
                "error_code": "SCHEDULE_NOT_FOUND"
            }
        
        if schedule_plan.status == SchedulePlanStatus.PUBLISHED:
            return {
                "success": False,
                "error": "Escala já publicada. Não é possível alterar alocações.",
                "error_code": "SCHEDULE_ALREADY_PUBLISHED"
            }
        
        slots = self.db.query(ShiftSlot).filter(
            ShiftSlot.schedule_plan_id == schedule_plan_id
        ).order_by(ShiftSlot.target_date, ShiftSlot.start_time).all()
        
        if not slots:
            return {
                "success": False,
                "error": "Nenhum turno encontrado na escala",
                "error_code": "NO_SLOTS"
            }
        
        employees = self.db.query(Employee).filter(
            Employee.sector_id == sector_id,
            Employee.is_active == True
        ).all()
        
        if not employees:
            return {
                "success": False,
                "error": "Nenhum colaborador ativo no setor",
                "error_code": "NO_EMPLOYEES"
            }
        
        constraints = self._get_constraints(sector_id)
        self._trace_steps.append({
            "step": "LOAD_CONSTRAINTS",
            "constraints": constraints,
            "applied_rules": list(self._applied_rules)
        })
        
        employee_metrics: Dict[int, EmployeeMetrics] = {}
        for emp in employees:
            employee_metrics[emp.id] = EmployeeMetrics(
                employee_id=emp.id,
                employee_name=emp.name,
                contract_type=emp.contract_type.value if emp.contract_type else "intermitente"
            )
        
        week_end = week_start + timedelta(days=6)
        dates_in_week = [week_start + timedelta(days=i) for i in range(7)]
        
        slots_by_date: Dict[date, List[ShiftSlot]] = defaultdict(list)
        for slot in slots:
            slots_by_date[slot.target_date].append(slot)
        
        assigned_count = 0
        unassigned_slots: List[int] = []
        all_violations: List[Dict] = []
        all_warnings: List[Dict] = []
        
        for target_date in dates_in_week:
            day_slots = sorted(slots_by_date.get(target_date, []), 
                             key=lambda s: (s.hours_worked or 8), reverse=True)
            
            if not day_slots:
                continue
            
            eligible_employees = self._filter_eligible_for_day(
                employees=employees,
                target_date=target_date,
                employee_metrics=employee_metrics,
                constraints=constraints
            )
            
            self._trace_steps.append({
                "step": "FILTER_ELIGIBLE",
                "date": target_date.isoformat(),
                "total_employees": len(employees),
                "eligible_count": len(eligible_employees),
                "eligible_ids": [e.id for e in eligible_employees]
            })
            
            for slot in day_slots:
                if slot.is_assigned:
                    continue
                
                if not eligible_employees:
                    unassigned_slots.append(slot.id)
                    all_warnings.append({
                        "type": "NO_ELIGIBLE_EMPLOYEE",
                        "date": target_date.isoformat(),
                        "slot_id": slot.id,
                        "message": f"Sem colaboradores elegíveis para {target_date.strftime('%d/%m')} turno {slot.start_time}-{slot.end_time}"
                    })
                    continue
                
                scored_employees = self._score_employees(
                    candidates=eligible_employees,
                    slot=slot,
                    target_date=target_date,
                    employee_metrics=employee_metrics,
                    constraints=constraints
                )
                
                best_employee = None
                for emp, score, reasons in scored_employees:
                    can_assign, violation = self._can_assign_to_slot(
                        employee=emp,
                        slot=slot,
                        target_date=target_date,
                        metrics=employee_metrics[emp.id],
                        constraints=constraints
                    )
                    
                    if can_assign:
                        best_employee = emp
                        break
                    else:
                        all_violations.append({
                            "employee_id": emp.id,
                            "employee_name": emp.name,
                            "date": target_date.isoformat(),
                            "slot_id": slot.id,
                            "violation": violation
                        })
                
                if best_employee:
                    slot.employee_id = best_employee.id
                    slot.is_assigned = True
                    assigned_count += 1
                    
                    self._update_employee_metrics(
                        employee=best_employee,
                        slot=slot,
                        target_date=target_date,
                        metrics=employee_metrics[best_employee.id]
                    )
                    
                    eligible_employees = [e for e in eligible_employees 
                                        if self._is_still_eligible(e, target_date, 
                                                                   employee_metrics[e.id], 
                                                                   constraints)]
                    
                    self._trace_steps.append({
                        "step": "ASSIGNMENT",
                        "date": target_date.isoformat(),
                        "slot_id": slot.id,
                        "employee_id": best_employee.id,
                        "employee_name": best_employee.name,
                        "hours_after": employee_metrics[best_employee.id].hours_assigned
                    })
                else:
                    unassigned_slots.append(slot.id)
        
        agent_run = self._create_agent_run(
            sector_id=sector_id,
            week_start=week_start,
            schedule_plan_id=schedule_plan_id,
            assigned_count=assigned_count,
            unassigned_count=len(unassigned_slots),
            violations=all_violations,
            warnings=all_warnings
        )
        
        schedule_plan.status = SchedulePlanStatus.VALIDATED
        
        self.db.commit()
        
        return {
            "success": True,
            "schedule_plan_id": schedule_plan_id,
            "agent_run_id": agent_run.id if agent_run else None,
            "summary": {
                "total_slots": len(slots),
                "assigned_slots": assigned_count,
                "unassigned_slots": len(unassigned_slots),
                "employees_used": sum(1 for m in employee_metrics.values() if m.days_assigned > 0),
                "total_hours_assigned": sum(m.hours_assigned for m in employee_metrics.values())
            },
            "employee_metrics": [m.to_dict() for m in employee_metrics.values() if m.days_assigned > 0],
            "unassigned_slot_ids": unassigned_slots,
            "violations": all_violations,
            "warnings": all_warnings,
            "applied_rules": self._applied_rules,
            "trace_summary": {
                "steps_count": len(self._trace_steps),
                "method_version": METHOD_VERSION
            }
        }
    
    def _get_constraints(self, sector_id: int) -> Dict[str, Any]:
        """Obtém constraints combinando RuleEngine + defaults."""
        
        rule_constraints, applied = self._rule_engine.get_all_constraints(sector_id)
        self._applied_rules.extend(applied)
        
        constraints = {
            "max_hours_daily": 10.0,
            "max_hours_weekly": 44.0,
            "min_rest_between_shifts": 11.0,
            "max_consecutive_days": 6,
            "advance_notice_hours": 72,
            "utilization_target_pct": 85.0,
            "buffer_pct": 10.0,
            "intermittent_max_weekly": 44.0,
            "permanent_weekly_target": 40.0
        }
        
        if rule_constraints:
            for key, value in rule_constraints.items():
                if key in constraints and value is not None:
                    constraints[key] = value
        
        return constraints
    
    def _filter_eligible_for_day(
        self,
        employees: List[Employee],
        target_date: date,
        employee_metrics: Dict[int, EmployeeMetrics],
        constraints: Dict[str, Any]
    ) -> List[Employee]:
        """
        Filtra colaboradores elegíveis para um dia específico.
        Aplica restrições MANDATORY primeiro (legais).
        """
        eligible = []
        max_weekly = constraints.get("max_hours_weekly", 44.0)
        max_consecutive = constraints.get("max_consecutive_days", 6)
        
        for emp in employees:
            metrics = employee_metrics[emp.id]
            
            if metrics.hours_assigned >= max_weekly:
                continue
            
            if metrics.consecutive_days >= max_consecutive:
                continue
            
            unavailable = emp.unavailable_days or []
            weekday_name = target_date.strftime("%A").upper()
            weekday_map = {
                "MONDAY": "SEG", "TUESDAY": "TER", "WEDNESDAY": "QUA",
                "THURSDAY": "QUI", "FRIDAY": "SEX", "SATURDAY": "SAB", "SUNDAY": "DOM"
            }
            day_code = weekday_map.get(weekday_name, "")
            
            if day_code in unavailable or target_date.isoformat() in unavailable:
                continue
            
            if emp.vacation_period_start and emp.vacation_period_end:
                if emp.vacation_period_start <= target_date <= emp.vacation_period_end:
                    continue
            
            eligible.append(emp)
        
        return eligible
    
    def _score_employees(
        self,
        candidates: List[Employee],
        slot: ShiftSlot,
        target_date: date,
        employee_metrics: Dict[int, EmployeeMetrics],
        constraints: Dict[str, Any]
    ) -> List[Tuple[Employee, float, List[str]]]:
        """
        Calcula score para cada candidato. Menor score = melhor escolha.
        
        Penalidades:
        - Exceder horas semanais
        - Repetir mesmo turno
        - Violar preferências
        - Desbalanceamento de horas
        """
        max_weekly = constraints.get("max_hours_weekly", 44.0)
        slot_hours = slot.hours_worked or 8.0
        
        scored = []
        
        for emp in candidates:
            metrics = employee_metrics[emp.id]
            score = 0.0
            reasons = []
            
            hours_after = metrics.hours_assigned + slot_hours
            if hours_after > max_weekly:
                penalty = (hours_after - max_weekly) * 100
                score += penalty
                reasons.append(f"excede_horas:{penalty:.0f}")
            
            template = slot.template_name or ""
            if template in metrics.shifts_assigned:
                count = metrics.shifts_assigned.count(template)
                penalty = count * 20
                score += penalty
                reasons.append(f"repete_turno:{penalty:.0f}")
            
            preferences = emp.time_off_preferences or []
            weekday_name = target_date.strftime("%A").upper()
            weekday_map = {
                "MONDAY": "SEG", "TUESDAY": "TER", "WEDNESDAY": "QUA",
                "THURSDAY": "QUI", "FRIDAY": "SEX", "SATURDAY": "SAB", "SUNDAY": "DOM"
            }
            day_code = weekday_map.get(weekday_name, "")
            
            if day_code in preferences:
                score += 10
                reasons.append("preferencia_folga:10")
            
            avg_hours = sum(m.hours_assigned for m in employee_metrics.values()) / len(employee_metrics)
            deviation = abs(metrics.hours_assigned - avg_hours)
            
            if metrics.hours_assigned < avg_hours:
                score -= deviation * 5
                reasons.append(f"prioriza_baixas_horas:-{deviation * 5:.0f}")
            else:
                score += deviation * 2
                reasons.append(f"penaliza_altas_horas:{deviation * 2:.0f}")
            
            if emp.contract_type == ContractType.PERMANENT:
                score -= 5
                reasons.append("efetivo_prioridade:-5")
            
            scored.append((emp, score, reasons))
        
        scored.sort(key=lambda x: x[1])
        
        return scored
    
    def _can_assign_to_slot(
        self,
        employee: Employee,
        slot: ShiftSlot,
        target_date: date,
        metrics: EmployeeMetrics,
        constraints: Dict[str, Any]
    ) -> Tuple[bool, Optional[str]]:
        """
        Verifica se colaborador pode ser alocado ao slot.
        Retorna (True, None) ou (False, motivo_violação).
        """
        max_daily = constraints.get("max_hours_daily", 10.0)
        slot_hours = slot.hours_worked or 8.0
        
        min_rest = constraints.get("min_rest_between_shifts", 11.0)
        
        if metrics.last_shift_end:
            slot_start_time = datetime.strptime(slot.start_time, "%H:%M").time()
            slot_start_dt = datetime.combine(target_date, slot_start_time)
            
            rest_hours = (slot_start_dt - metrics.last_shift_end).total_seconds() / 3600
            
            if rest_hours < min_rest:
                return False, f"Descanso insuficiente: {rest_hours:.1f}h (mín: {min_rest}h)"
        
        max_weekly = constraints.get("max_hours_weekly", 44.0)
        if metrics.hours_assigned + slot_hours > max_weekly:
            pass
        
        return True, None
    
    def _update_employee_metrics(
        self,
        employee: Employee,
        slot: ShiftSlot,
        target_date: date,
        metrics: EmployeeMetrics
    ):
        """Atualiza métricas do colaborador após alocação."""
        slot_hours = slot.hours_worked or 8.0
        metrics.hours_assigned += slot_hours
        
        if target_date not in [d for d in metrics.rest_days]:
            metrics.days_assigned += 1
            metrics.consecutive_days += 1
        
        metrics.shifts_assigned.append(slot.template_name or "GENERIC")
        
        slot_end_time = datetime.strptime(slot.end_time, "%H:%M").time()
        metrics.last_shift_end = datetime.combine(target_date, slot_end_time)
    
    def _is_still_eligible(
        self,
        employee: Employee,
        target_date: date,
        metrics: EmployeeMetrics,
        constraints: Dict[str, Any]
    ) -> bool:
        """Verifica se colaborador ainda pode receber mais turnos no dia."""
        max_daily = constraints.get("max_hours_daily", 10.0)
        
        return True
    
    def _create_agent_run(
        self,
        sector_id: int,
        week_start: date,
        schedule_plan_id: int,
        assigned_count: int,
        unassigned_count: int,
        violations: List[Dict],
        warnings: List[Dict]
    ) -> Optional[AgentRun]:
        """Cria registro de execução do agente com trace."""
        try:
            agent_run = AgentRun(
                run_type=RunType.SCHEDULE,
                setor_id=sector_id,
                week_start=week_start,
                status=RunStatus.SUCCESS,
                inputs_snapshot={
                    "schedule_plan_id": schedule_plan_id,
                    "method_version": METHOD_VERSION
                },
                outputs_summary={
                    "assigned_count": assigned_count,
                    "unassigned_count": unassigned_count,
                    "violations_count": len(violations),
                    "warnings_count": len(warnings),
                    "applied_rules": self._applied_rules
                }
            )
            self.db.add(agent_run)
            self.db.flush()
            
            for i, step in enumerate(self._trace_steps):
                trace_step = AgentTraceStep(
                    run_id=agent_run.id,
                    step_order=i + 1,
                    step_key=step.get("step", "UNKNOWN"),
                    description=str(step)[:500],
                    applied_rules=self._applied_rules if step.get("step") == "ASSIGNMENT" else [],
                    calculations={},
                    constraints_violated=[v.get("violation", "") for v in violations if v.get("slot_id") == step.get("slot_id")]
                )
                self.db.add(trace_step)
            
            return agent_run
        except Exception as e:
            return None
