"""
Serviço de Geração de Agendas Individuais
==========================================
Distribui atividades programadas entre colaboradores escalados,
respeitando capacidades individuais e regras de alternância.

Versão: 1.0.0
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import deque
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.governance_module import (
    HousekeepingSchedulePlan, ShiftSlot, SchedulePlanStatus,
    EmployeeDailyAgenda, EmployeeDailyAgendaItem, AgendaGenerationStatus,
    HousekeepingDemandDaily
)
from app.models.governance_activity import (
    GovernanceActivity, ActivityClassification, WorkloadDriver
)
from app.models.activity_program import ActivityProgramWeek, ActivityProgramItem
from app.models.employee import Employee
from app.models.agent_run import AgentRun, AgentTraceStep, RunType, RunStatus
from app.services.rule_engine import RuleEngine
from app.services.recurrence_expansion_service import expand_recurring_activities

METHOD_VERSION = "1.0.0"

WEEKDAY_PT = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA", "SEXTA-FEIRA", "SÁBADO", "DOMINGO"]


class AgendaGenerationService:
    """
    Gera agendas individuais para colaboradores escalados.
    
    Fluxo:
    1. Carregar slots atribuídos (colaboradores por dia)
    2. Calcular demanda total por tipo de atividade
    3. Distribuir atividades respeitando capacidade e alternância
    4. Registrar trace para auditoria
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.rule_engine = RuleEngine(db)
        self._trace_steps: List[Dict] = []
        self._applied_rules: List[Dict] = []
        self._conflicts: List[Dict] = []
        self._pending_items: List[Dict] = []
    
    def generate_agendas(
        self,
        sector_id: int,
        week_start: date,
        schedule_plan_id: int
    ) -> Dict[str, Any]:
        """
        Gera agendas individuais para todos os colaboradores da semana.
        
        Args:
            sector_id: ID do setor
            week_start: Data de início da semana (segunda-feira)
            schedule_plan_id: ID do plano de escala
            
        Returns:
            Dicionário com agendas geradas, métricas e trace
        """
        self._trace_steps = []
        self._applied_rules = []
        self._conflicts = []
        self._pending_items = []
        
        schedule_plan = self.db.query(HousekeepingSchedulePlan).filter(
            HousekeepingSchedulePlan.id == schedule_plan_id
        ).first()
        
        if not schedule_plan:
            return {
                "success": False,
                "error": "Plano de escala não encontrado"
            }
        
        if schedule_plan.sector_id != sector_id:
            return {
                "success": False,
                "error": "Plano de escala não pertence ao setor informado"
            }
        
        assigned_slots = self.db.query(ShiftSlot).filter(
            ShiftSlot.schedule_plan_id == schedule_plan_id,
            ShiftSlot.is_assigned == True,
            ShiftSlot.employee_id.isnot(None)
        ).all()
        
        if not assigned_slots:
            return {
                "success": False,
                "error": "Nenhum colaborador atribuído na escala. Execute a alocação primeiro."
            }
        
        self._add_trace("LOAD_SLOTS", {
            "total_slots": len(assigned_slots),
            "days_covered": len(set(s.target_date for s in assigned_slots))
        })
        
        rules = self.rule_engine.fetch_rules(sector_id)
        self._applied_rules = [
            {"codigo": r.codigo_regra, "tipo": r.tipo.value, "nivel": r.nivel_rigidez.value}
            for r in (rules.get("CALCULATION", []) + rules.get("OPERATIONAL", []))[:10]
        ]
        
        self._add_trace("LOAD_RULES", {
            "calculation_rules": len(rules.get("CALCULATION", [])),
            "operational_rules": len(rules.get("OPERATIONAL", []))
        })
        
        week_end = week_start + timedelta(days=6)
        activities_by_type = self._load_activities_by_type(sector_id, week_start, week_end)
        
        self._add_trace("LOAD_ACTIVITIES", {
            "calculadas": len(activities_by_type.get("CALCULADA_PELO_AGENTE", [])),
            "recorrentes": len(activities_by_type.get("RECORRENTE", [])),
            "eventuais": len(activities_by_type.get("EVENTUAL", []))
        })
        
        demand_by_day = self._load_demand_by_day(sector_id, week_start, week_end)
        
        self.db.query(EmployeeDailyAgenda).filter(
            EmployeeDailyAgenda.schedule_plan_id == schedule_plan_id
        ).delete()
        self.db.flush()
        
        slots_by_day: Dict[date, List[ShiftSlot]] = {}
        for slot in assigned_slots:
            if slot.target_date not in slots_by_day:
                slots_by_day[slot.target_date] = []
            slots_by_day[slot.target_date].append(slot)
        
        agendas_created = []
        
        for target_date, day_slots in sorted(slots_by_day.items()):
            day_agendas = self._generate_day_agendas(
                sector_id=sector_id,
                schedule_plan_id=schedule_plan_id,
                target_date=target_date,
                day_slots=day_slots,
                activities_by_type=activities_by_type,
                demand_by_day=demand_by_day
            )
            agendas_created.extend(day_agendas)
        
        self.db.commit()
        
        agent_run = self._record_agent_run(
            sector_id=sector_id,
            week_start=week_start,
            schedule_plan_id=schedule_plan_id,
            agendas_count=len(agendas_created)
        )
        
        return {
            "success": True,
            "method_version": METHOD_VERSION,
            "agendas_geradas": len(agendas_created),
            "por_dia": self._summarize_by_day(agendas_created),
            "conflitos": self._conflicts,
            "pendencias": self._pending_items,
            "trace": self._trace_steps,
            "applied_rules": self._applied_rules,
            "agent_run_id": agent_run.id if agent_run else None
        }
    
    def _load_activities_by_type(
        self,
        sector_id: int,
        week_start: date,
        week_end: date
    ) -> Dict[str, List[Dict]]:
        """Carrega atividades agrupadas por classificação."""
        
        activities = self.db.query(GovernanceActivity).filter(
            GovernanceActivity.sector_id == sector_id,
            GovernanceActivity.is_active == True
        ).all()
        
        result = {
            "CALCULADA_PELO_AGENTE": [],
            "RECORRENTE": [],
            "EVENTUAL": []
        }
        
        for act in activities:
            classification = act.classificacao_atividade.value if act.classificacao_atividade else "CALCULADA_PELO_AGENTE"
            
            if classification == "RECORRENTE":
                expanded = expand_recurring_activities(
                    self.db, sector_id, week_start, week_end
                )
                for exp in expanded:
                    if exp.get("activity_id") == act.id:
                        result["RECORRENTE"].append({
                            "activity_id": act.id,
                            "name": act.name,
                            "code": act.code,
                            "minutes": act.average_time_minutes,
                            "difficulty": act.difficulty_level,
                            "dates": exp.get("scheduled_dates", [])
                        })
            else:
                result[classification].append({
                    "activity_id": act.id,
                    "name": act.name,
                    "code": act.code,
                    "minutes": act.average_time_minutes,
                    "difficulty": act.difficulty_level,
                    "workload_driver": act.workload_driver.value if act.workload_driver else "VARIABLE"
                })
        
        return result
    
    def _load_demand_by_day(
        self,
        sector_id: int,
        week_start: date,
        week_end: date
    ) -> Dict[date, Dict]:
        """Carrega demanda calculada por dia."""
        
        demands = self.db.query(HousekeepingDemandDaily).filter(
            HousekeepingDemandDaily.sector_id == sector_id,
            HousekeepingDemandDaily.target_date >= week_start,
            HousekeepingDemandDaily.target_date <= week_end
        ).all()
        
        result = {}
        for d in demands:
            result[d.target_date] = {
                "variable_minutes": d.total_minutes_demand or 0,
                "constant_minutes": d.constant_activities_minutes or 0,
                "total_minutes": (d.total_minutes_demand or 0) + (d.constant_activities_minutes or 0)
            }
        
        return result
    
    def _generate_day_agendas(
        self,
        sector_id: int,
        schedule_plan_id: int,
        target_date: date,
        day_slots: List[ShiftSlot],
        activities_by_type: Dict[str, List[Dict]],
        demand_by_day: Dict[date, Dict]
    ) -> List[EmployeeDailyAgenda]:
        """Gera agendas para um dia específico."""
        
        day_demand = demand_by_day.get(target_date, {})
        total_demand_minutes = day_demand.get("total_minutes", 0)
        
        total_capacity_minutes = sum(
            int((slot.hours_worked or 8.0) * 60) for slot in day_slots
        )
        
        has_conflict = total_demand_minutes > total_capacity_minutes
        if has_conflict:
            self._conflicts.append({
                "date": target_date.isoformat(),
                "reason": f"Demanda ({total_demand_minutes} min) excede capacidade ({total_capacity_minutes} min)",
                "deficit_minutes": total_demand_minutes - total_capacity_minutes
            })
        
        calculadas = activities_by_type.get("CALCULADA_PELO_AGENTE", [])
        recorrentes = [
            r for r in activities_by_type.get("RECORRENTE", [])
            if target_date.isoformat() in [str(d) for d in r.get("dates", [])]
        ]
        eventuais = activities_by_type.get("EVENTUAL", [])
        
        all_activities = []
        
        for act in calculadas:
            if act.get("workload_driver") == "VARIABLE":
                proportion = day_demand.get("variable_minutes", 0) / max(total_demand_minutes, 1)
                minutes = int(act.get("minutes", 0) * proportion * len(day_slots))
            else:
                minutes = int(act.get("minutes", 0))
            
            if minutes > 0:
                all_activities.append({
                    **act,
                    "total_minutes": minutes,
                    "classification": "CALCULADA_PELO_AGENTE"
                })
        
        for act in recorrentes:
            all_activities.append({
                **act,
                "total_minutes": int(act.get("minutes", 0)),
                "classification": "RECORRENTE"
            })
        
        all_activities.sort(key=lambda x: x.get("difficulty", 1), reverse=True)
        
        eventual_items_for_pending = []
        for ev in eventuais:
            eventual_items_for_pending.append({
                **ev,
                "classification": "EVENTUAL",
                "is_pending": True
            })
            self._pending_items.append({
                "date": target_date.isoformat(),
                "activity": ev.get("name"),
                "reason": "Atividade EVENTUAL - agendamento manual necessário"
            })
        
        agendas = []
        employee_loads: Dict[int, int] = {slot.employee_id: 0 for slot in day_slots}
        employee_last_difficulty: Dict[int, int] = {slot.employee_id: 0 for slot in day_slots}
        
        difficult_rotation_queue = deque([slot.employee_id for slot in sorted(day_slots, key=lambda s: s.employee_id)])
        
        for slot in day_slots:
            minutes_available = int((slot.hours_worked or 8.0) * 60)
            
            agenda = EmployeeDailyAgenda(
                schedule_plan_id=schedule_plan_id,
                shift_slot_id=slot.id,
                employee_id=slot.employee_id,
                sector_id=sector_id,
                target_date=target_date,
                total_minutes_available=minutes_available,
                shift_start=slot.start_time,
                shift_end=slot.end_time,
                status=AgendaGenerationStatus.GENERATED,
                has_conflict=has_conflict
            )
            self.db.add(agenda)
            self.db.flush()
            agendas.append(agenda)
        
        for activity in all_activities:
            remaining = activity.get("total_minutes", 0)
            is_pending_activity = activity.get("is_pending", False)
            
            while remaining > 0:
                eligible_slots = [
                    s for s in day_slots
                    if employee_loads.get(s.employee_id, 0) < int((s.hours_worked or 8.0) * 60)
                ]
                
                if not eligible_slots:
                    break
                
                activity_difficulty = activity.get("difficulty", 1)
                is_difficult_task = activity_difficulty >= 3
                
                if is_difficult_task:
                    chosen_emp_id = None
                    attempts = 0
                    while attempts < len(difficult_rotation_queue):
                        candidate = difficult_rotation_queue[0]
                        
                        candidate_slot = next((s for s in eligible_slots if s.employee_id == candidate), None)
                        if candidate_slot:
                            chosen_emp_id = candidate
                            difficult_rotation_queue.rotate(-1)
                            break
                        difficult_rotation_queue.rotate(-1)
                        attempts += 1
                    
                    if chosen_emp_id:
                        chosen_slot = next(s for s in day_slots if s.employee_id == chosen_emp_id)
                    else:
                        eligible_slots.sort(key=lambda s: employee_loads.get(s.employee_id, 0))
                        chosen_slot = eligible_slots[0]
                else:
                    eligible_slots.sort(key=lambda s: (
                        employee_loads.get(s.employee_id, 0),
                        abs(employee_last_difficulty.get(s.employee_id, 0) - activity_difficulty)
                    ))
                    chosen_slot = eligible_slots[0]
                
                emp_id = chosen_slot.employee_id
                
                capacity_left = int((chosen_slot.hours_worked or 8.0) * 60) - employee_loads.get(emp_id, 0)
                assign_minutes = min(remaining, capacity_left, 60)
                
                if assign_minutes <= 0:
                    break
                
                agenda = next((a for a in agendas if a.employee_id == emp_id), None)
                if agenda:
                    item_order = len([i for i in agenda.items]) + 1 if hasattr(agenda, 'items') else 1
                    
                    item = EmployeeDailyAgendaItem(
                        agenda_id=agenda.id,
                        activity_id=activity.get("activity_id"),
                        order=item_order,
                        minutes=assign_minutes,
                        quantity=assign_minutes / max(activity.get("minutes", 1), 1),
                        classification=activity.get("classification", "CALCULADA_PELO_AGENTE"),
                        is_pending=is_pending_activity,
                        pending_reason="Agendamento manual necessário" if is_pending_activity else None
                    )
                    self.db.add(item)
                    
                    agenda.total_minutes_allocated = (agenda.total_minutes_allocated or 0) + assign_minutes
                    employee_loads[emp_id] = employee_loads.get(emp_id, 0) + assign_minutes
                    employee_last_difficulty[emp_id] = activity.get("difficulty", 1)
                    
                    self._add_trace("ASSIGN_ACTIVITY", {
                        "date": target_date.isoformat(),
                        "employee_id": emp_id,
                        "activity": activity.get("name"),
                        "minutes": assign_minutes,
                        "difficulty": activity_difficulty,
                        "is_difficult": is_difficult_task,
                        "is_pending": is_pending_activity,
                        "employee_load_after": employee_loads[emp_id],
                        "rotation_used": is_difficult_task,
                        "queue_state": list(difficult_rotation_queue)[:5] if is_difficult_task else None
                    })
                
                remaining -= assign_minutes
        
        self.db.flush()
        
        if eventual_items_for_pending and agendas:
            eventual_queue = deque([a.employee_id for a in agendas])
            for ev_item in eventual_items_for_pending:
                target_emp = eventual_queue[0]
                eventual_queue.rotate(-1)
                
                target_agenda = next((a for a in agendas if a.employee_id == target_emp), None)
                if target_agenda:
                    item_order = len([i for i in target_agenda.items]) + 1 if hasattr(target_agenda, 'items') else 1
                    
                    pending_item = EmployeeDailyAgendaItem(
                        agenda_id=target_agenda.id,
                        activity_id=ev_item.get("activity_id"),
                        order=item_order,
                        minutes=int(ev_item.get("minutes", 0)),
                        quantity=1.0,
                        classification="EVENTUAL",
                        is_pending=True,
                        pending_reason="Agendamento manual necessário"
                    )
                    self.db.add(pending_item)
                    
                    self._add_trace("ASSIGN_PENDING", {
                        "date": target_date.isoformat(),
                        "employee_id": target_emp,
                        "activity": ev_item.get("name"),
                        "classification": "EVENTUAL",
                        "is_pending": True
                    })
            
            self.db.flush()
        
        self._add_trace("GENERATE_DAY", {
            "date": target_date.isoformat(),
            "employees": len(day_slots),
            "activities_distributed": len(all_activities),
            "eventual_pending": len(eventual_items_for_pending),
            "total_demand": total_demand_minutes,
            "total_capacity": total_capacity_minutes,
            "has_conflict": has_conflict
        })
        
        return agendas
    
    def _summarize_by_day(self, agendas: List[EmployeeDailyAgenda]) -> List[Dict]:
        """Resume agendas por dia."""
        by_day: Dict[date, Dict] = {}
        
        for agenda in agendas:
            d = agenda.target_date
            if d not in by_day:
                by_day[d] = {
                    "date": d.isoformat(),
                    "employees": 0,
                    "total_allocated": 0,
                    "total_available": 0,
                    "conflicts": 0
                }
            
            by_day[d]["employees"] += 1
            by_day[d]["total_allocated"] += agenda.total_minutes_allocated or 0
            by_day[d]["total_available"] += agenda.total_minutes_available or 0
            if agenda.has_conflict:
                by_day[d]["conflicts"] += 1
        
        return list(sorted(by_day.values(), key=lambda x: x["date"]))
    
    def _add_trace(self, step: str, data: Dict):
        """Adiciona passo ao trace."""
        self._trace_steps.append({
            "step": step,
            **data
        })
    
    def _record_agent_run(
        self,
        sector_id: int,
        week_start: date,
        schedule_plan_id: int,
        agendas_count: int
    ) -> Optional[AgentRun]:
        """Registra execução do agente."""
        try:
            agent_run = AgentRun(
                run_type=RunType.SCHEDULE,
                setor_id=sector_id,
                week_start=week_start,
                status=RunStatus.SUCCESS,
                inputs_snapshot={
                    "schedule_plan_id": schedule_plan_id,
                    "method_version": METHOD_VERSION,
                    "operation": "AGENDA_GENERATION"
                },
                outputs_summary={
                    "agendas_geradas": agendas_count,
                    "conflitos": len(self._conflicts),
                    "pendencias": len(self._pending_items)
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
                    applied_rules=self._applied_rules if step.get("step") == "LOAD_RULES" else [],
                    calculations=step,
                    constraints_violated=[]
                )
                self.db.add(trace_step)
            
            return agent_run
        except Exception as e:
            print(f"Erro ao registrar AgentRun: {e}")
            return None
    
    def get_agendas(
        self,
        sector_id: int,
        week_start: date
    ) -> Dict[str, Any]:
        """
        Retorna agendas geradas para a semana.
        
        Args:
            sector_id: ID do setor
            week_start: Data de início da semana
            
        Returns:
            Dicionário com agendas por colaborador/dia
        """
        week_end = week_start + timedelta(days=6)
        
        agendas = self.db.query(EmployeeDailyAgenda).filter(
            EmployeeDailyAgenda.sector_id == sector_id,
            EmployeeDailyAgenda.target_date >= week_start,
            EmployeeDailyAgenda.target_date <= week_end
        ).all()
        
        if not agendas:
            return {
                "success": True,
                "agendas": [],
                "message": "Nenhuma agenda encontrada para esta semana"
            }
        
        result = []
        for agenda in agendas:
            employee = self.db.query(Employee).filter(Employee.id == agenda.employee_id).first()
            
            items = self.db.query(EmployeeDailyAgendaItem).filter(
                EmployeeDailyAgendaItem.agenda_id == agenda.id
            ).order_by(EmployeeDailyAgendaItem.order).all()
            
            activities_list = []
            for item in items:
                activity = self.db.query(GovernanceActivity).filter(
                    GovernanceActivity.id == item.activity_id
                ).first()
                
                activities_list.append({
                    "order": item.order,
                    "activity_id": item.activity_id,
                    "activity_name": activity.name if activity else "Desconhecida",
                    "activity_code": activity.code if activity else "",
                    "minutes": item.minutes,
                    "quantity": item.quantity,
                    "classification": item.classification,
                    "is_pending": item.is_pending,
                    "pending_reason": item.pending_reason
                })
            
            result.append({
                "agenda_id": agenda.id,
                "employee_id": agenda.employee_id,
                "employee_name": employee.name if employee else "Desconhecido",
                "date": agenda.target_date.isoformat(),
                "shift_start": agenda.shift_start,
                "shift_end": agenda.shift_end,
                "total_minutes_allocated": agenda.total_minutes_allocated,
                "total_minutes_available": agenda.total_minutes_available,
                "utilization_pct": round(
                    (agenda.total_minutes_allocated or 0) / max(agenda.total_minutes_available or 1, 1) * 100, 1
                ),
                "status": agenda.status.value if agenda.status else "draft",
                "has_conflict": agenda.has_conflict,
                "conflict_reason": agenda.conflict_reason,
                "activities": activities_list
            })
        
        return {
            "success": True,
            "week_start": week_start.isoformat(),
            "sector_id": sector_id,
            "agendas": result,
            "total_agendas": len(result)
        }
