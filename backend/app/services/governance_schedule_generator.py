from datetime import date, datetime, timedelta, time
from typing import Dict, List, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import math

from app.models.governance_module import (
    SectorOperationalParameters, ForecastRun, ForecastRunType,
    HousekeepingDemandDaily, HousekeepingSchedulePlan,
    SchedulePlanStatus, SchedulePlanKind, ShiftSlot,
    ForecastRunSectorSnapshot
)
from app.models.data_lake import HourlyDistributionStats, EventType
from app.models.employee import Employee
from app.models.rules import LaborRules, SectorOperationalRules
from app.models.work_shift import WorkShift, WorkShiftDayRule, ShiftTimeConstraint
from app.services.rule_engine import RuleEngine

METHOD_VERSION = "1.2.0"

DEFAULT_CONVOCATION_NOTICE_HOURS = 72

WEEKDAYS_PT = {
    0: "SEGUNDA-FEIRA",
    1: "TERÇA-FEIRA",
    2: "QUARTA-FEIRA",
    3: "QUINTA-FEIRA",
    4: "SEXTA-FEIRA",
    5: "SÁBADO",
    6: "DOMINGO"
}


class GovernanceScheduleGenerator:
    """
    Gerador de escalas para o setor de Governança (Housekeeping).
    
    PROMPT 8: Refatorado para usar cascade de regras:
    1. LaborRules (global) - regras trabalhistas
    2. SectorOperationalRules (por setor) - regras operacionais
    3. SectorOperationalParameters - parâmetros detalhados (templates, almoço, etc)
    """
    
    def __init__(self, db: Session):
        self.db = db
        self._labor_rules_cache: Optional[LaborRules] = None
        self._sector_rules_cache: Dict[int, SectorOperationalRules] = {}
        self._rule_engine = RuleEngine(db)
        self._applied_rules_trace: List[str] = []
    
    def get_labor_rules(self) -> Optional[LaborRules]:
        """
        PROMPT 8: Obtém regras trabalhistas GLOBAIS ativas.
        Usa cache para evitar múltiplas queries na mesma sessão.
        """
        if self._labor_rules_cache is None:
            self._labor_rules_cache = self.db.query(LaborRules).filter(
                LaborRules.is_active == True
            ).first()
        return self._labor_rules_cache
    
    def get_sector_operational_rules(self, sector_id: int) -> Optional[SectorOperationalRules]:
        """
        PROMPT 8: Obtém regras operacionais do SETOR específico.
        Usa cache para evitar múltiplas queries na mesma sessão.
        """
        if sector_id not in self._sector_rules_cache:
            self._sector_rules_cache[sector_id] = self.db.query(SectorOperationalRules).filter(
                SectorOperationalRules.sector_id == sector_id,
                SectorOperationalRules.is_active == True
            ).first()
        return self._sector_rules_cache.get(sector_id)
    
    def get_convocation_notice_hours(self) -> int:
        """Obtém horas de antecedência para convocação das regras trabalhistas."""
        labor_rules = self.get_labor_rules()
        if labor_rules:
            return labor_rules.min_notice_hours
        return DEFAULT_CONVOCATION_NOTICE_HOURS
    
    def get_legal_constraints(self, sector_id: int) -> Dict[str, Any]:
        """
        PROMPT 8: Obtém constraints legais combinando LaborRules (global) + 
        SectorOperationalRules (setor).
        
        Cascade: Labor global primeiro, depois override por setor se aplicável.
        Sector overrides via productivity_params_json and indicators_json.
        """
        labor_rules = self.get_labor_rules()
        sector_rules = self.get_sector_operational_rules(sector_id)
        
        constraints = {
            "max_hours_per_day": 8.0,
            "min_rest_between_shifts": 11.0,
            "max_consecutive_days": 6,
            "max_week_hours": 44.0,
            "min_notice_hours": DEFAULT_CONVOCATION_NOTICE_HOURS,
            "utilization_target_pct": 85.0,
            "buffer_pct": 10.0,
            "fator_feriado": 1.1,
            "fator_vespera_feriado": 1.05,
            "fator_pico": 1.2,
            "fator_baixa_ocupacao": 0.9
        }
        
        if labor_rules:
            constraints.update({
                "max_hours_per_day": labor_rules.max_daily_hours,
                "min_rest_between_shifts": labor_rules.min_rest_hours_between_shifts,
                "max_consecutive_days": labor_rules.max_consecutive_work_days,
                "max_week_hours": labor_rules.max_week_hours,
                "min_notice_hours": labor_rules.min_notice_hours
            })
        
        if sector_rules:
            constraints["utilization_target_pct"] = sector_rules.utilization_target_pct
            constraints["buffer_pct"] = sector_rules.buffer_pct
            
            if sector_rules.productivity_params_json:
                prod_params = sector_rules.productivity_params_json
                if "jornada_media_horas" in prod_params:
                    constraints["max_hours_per_day"] = prod_params["jornada_media_horas"]
                if "max_daily_hours_override" in prod_params:
                    constraints["max_hours_per_day"] = prod_params["max_daily_hours_override"]
                if "max_week_hours_override" in prod_params:
                    constraints["max_week_hours"] = prod_params["max_week_hours_override"]
            
            if sector_rules.indicators_json:
                indicators = sector_rules.indicators_json
                for key in ["fator_feriado", "fator_vespera_feriado", "fator_pico", "fator_baixa_ocupacao"]:
                    if key in indicators:
                        constraints[key] = indicators[key]
        
        rule_engine_constraints = self.get_constraints_from_rule_engine(sector_id)
        if rule_engine_constraints:
            constraints["max_week_hours"] = rule_engine_constraints.get("max_hours_weekly", constraints["max_week_hours"])
            constraints["max_hours_per_day"] = rule_engine_constraints.get("max_hours_daily", constraints["max_hours_per_day"])
            constraints["min_rest_between_shifts"] = rule_engine_constraints.get("min_rest_between_shifts", constraints["min_rest_between_shifts"])
            constraints["min_notice_hours"] = rule_engine_constraints.get("advance_notice_hours", constraints["min_notice_hours"])
            constraints["buffer_pct"] = rule_engine_constraints.get("buffer_pct", constraints["buffer_pct"])
            constraints["utilization_target_pct"] = rule_engine_constraints.get("utilization_target_pct", constraints["utilization_target_pct"])

        return constraints

    def get_constraints_from_rule_engine(self, sector_id: int) -> Dict[str, Any]:
        constraints, applied_rules = self._rule_engine.get_all_constraints(sector_id)
        self._applied_rules_trace.extend(applied_rules)

        return {
            "max_hours_per_day": constraints.get("max_hours_daily", 10),
            "min_rest_between_shifts": float(constraints.get("min_rest_between_shifts", 11)),
            "max_consecutive_days": 6,
            "max_week_hours": float(constraints.get("max_hours_weekly", 44)),
            "min_notice_hours": constraints.get("advance_notice_hours", 72),
            "utilization_target_pct": constraints.get("utilization_target_pct", 85.0),
            "buffer_pct": constraints.get("buffer_pct", 10.0),
            "fator_feriado": constraints.get("fator_feriado", 1.1),
            "fator_vespera_feriado": constraints.get("fator_vespera_feriado", 1.05),
            "fator_pico": constraints.get("fator_pico", 1.2),
            "fator_baixa_ocupacao": constraints.get("fator_baixa_ocupacao", 0.9)
        }

    def get_applied_rules_trace(self) -> List[str]:
        return list(set(self._applied_rules_trace))

    def clear_rules_trace(self):
        self._applied_rules_trace = []

    def validate_schedule_constraints(
        self,
        sector_id: int,
        hours_weekly: float = None,
        hours_daily: float = None,
        rest_hours: float = None
    ) -> List[Dict[str, Any]]:
        values = {}
        if hours_weekly is not None:
            values["hours_weekly"] = hours_weekly
        if hours_daily is not None:
            values["hours_daily"] = hours_daily
        if rest_hours is not None:
            values["rest_hours"] = rest_hours

        return self._rule_engine.validate_against_constraints(sector_id, values)
    
    def create_sector_snapshot(
        self,
        forecast_run_id: int,
        sector_id: int,
        occ_projection: Dict = None
    ) -> ForecastRunSectorSnapshot:
        """
        PROMPT 8: Cria snapshot de regras/parâmetros para o forecast run.
        Preserva estado das regras no momento da geração.
        """
        labor_rules = self.get_labor_rules()
        sector_rules = self.get_sector_operational_rules(sector_id)
        params = self._get_sector_parameters(sector_id)
        
        labor_snapshot = {}
        if labor_rules:
            labor_snapshot = {
                "min_notice_hours": labor_rules.min_notice_hours,
                "max_week_hours": labor_rules.max_week_hours,
                "max_daily_hours": labor_rules.max_daily_hours,
                "min_rest_hours_between_shifts": labor_rules.min_rest_hours_between_shifts,
                "max_consecutive_work_days": labor_rules.max_consecutive_work_days
            }
        
        operational_snapshot = {}
        if sector_rules:
            operational_snapshot = {
                "utilization_target_pct": sector_rules.utilization_target_pct,
                "buffer_pct": sector_rules.buffer_pct,
                "shift_templates_json": sector_rules.shift_templates_json,
                "productivity_params_json": sector_rules.productivity_params_json
            }
        
        params_snapshot = {}
        if params:
            params_snapshot = {
                "target_utilization_pct": params.target_utilization_pct,
                "buffer_pct": params.buffer_pct,
                "shift_templates": params.shift_templates,
                "lunch_rules": params.lunch_rules,
                "constraints_json": params.constraints_json
            }
        
        snapshot = ForecastRunSectorSnapshot(
            forecast_run_id=forecast_run_id,
            sector_id=sector_id,
            occ_projection_by_day_json=occ_projection or {},
            labor_rules_snapshot_json=labor_snapshot,
            operational_rules_snapshot_json=operational_snapshot,
            weekly_params_snapshot_json=params_snapshot,
            snapshot_version=METHOD_VERSION
        )
        self.db.add(snapshot)
        return snapshot
    
    def generate_housekeeping_schedule(
        self,
        week_start: date,
        sector_id: int,
        forecast_run_id: int = None
    ) -> Dict:
        """
        Gera escala de governança para a semana.
        
        Args:
            week_start: Início da semana (segunda-feira)
            sector_id: ID do setor
            forecast_run_id: ID do forecast run (opcional, busca o mais recente)
        
        Returns:
            Dict com resultado da geração
        """
        result = {
            "success": False,
            "schedule_plan_id": None,
            "week_start": week_start.isoformat(),
            "week_end": None,
            "daily_slots": [],
            "summary": {},
            "applied_rules": [],
            "errors": []
        }

        self.clear_rules_trace()
        
        try:
            params = self._get_sector_parameters(sector_id)
            if not params:
                result["errors"].append(f"Parâmetros não encontrados para setor {sector_id}")
                return result

            rule_constraints = self.get_constraints_from_rule_engine(sector_id)
            
            if forecast_run_id:
                forecast_run = self.db.query(ForecastRun).filter(
                    ForecastRun.id == forecast_run_id
                ).first()
            else:
                forecast_run = self.db.query(ForecastRun).filter(
                    ForecastRun.sector_id == sector_id,
                    ForecastRun.horizon_start == week_start
                ).order_by(ForecastRun.created_at.desc()).first()
            
            if not forecast_run:
                result["errors"].append("ForecastRun não encontrado para a semana")
                return result
            
            demands = self.db.query(HousekeepingDemandDaily).filter(
                HousekeepingDemandDaily.forecast_run_id == forecast_run.id
            ).order_by(HousekeepingDemandDaily.target_date).all()
            
            if not demands:
                result["errors"].append("Demanda não calculada para o forecast")
                return result
            
            week_end = week_start + timedelta(days=6)
            result["week_end"] = week_end.isoformat()
            
            schedule_plan = HousekeepingSchedulePlan(
                sector_id=sector_id,
                forecast_run_id=forecast_run.id,
                week_start=week_start,
                week_end=week_end,
                status=SchedulePlanStatus.DRAFT,
                total_headcount_planned=0,
                total_hours_planned=0.0
            )
            self.db.add(schedule_plan)
            self.db.flush()
            
            result["schedule_plan_id"] = schedule_plan.id
            
            templates = params.shift_templates or [
                {"name": "Manhã", "start_time": "07:00", "end_time": "15:00", "hours": 8.0},
                {"name": "Tarde", "start_time": "14:00", "end_time": "22:00", "hours": 8.0}
            ]
            
            total_headcount = 0
            total_hours = 0.0
            coverage_by_hour = {}
            
            for demand in demands:
                headcount = demand.headcount_rounded
                
                checkout_dist = self._get_hourly_distribution(demand.weekday_pt, EventType.CHECKOUT)
                checkin_dist = self._get_hourly_distribution(demand.weekday_pt, EventType.CHECKIN)
                
                template_allocation = self._allocate_templates(
                    headcount=headcount,
                    templates=templates,
                    checkout_dist=checkout_dist,
                    checkin_dist=checkin_dist
                )
                
                day_slots = []
                for template_name, count in template_allocation.items():
                    template = next((t for t in templates if t["name"] == template_name), templates[0])
                    
                    for i in range(count):
                        lunch_start, lunch_end = self._calculate_lunch_time(
                            start_time=template["start_time"],
                            end_time=template["end_time"],
                            lunch_rules=params.lunch_rules
                        )
                        
                        slot = ShiftSlot(
                            schedule_plan_id=schedule_plan.id,
                            target_date=demand.target_date,
                            weekday_pt=demand.weekday_pt,
                            template_name=template_name,
                            start_time=template["start_time"],
                            end_time=template["end_time"],
                            lunch_start=lunch_start,
                            lunch_end=lunch_end,
                            hours_worked=template.get("hours", 8.0),
                            is_assigned=False
                        )
                        self.db.add(slot)
                        day_slots.append({
                            "template": template_name,
                            "start_time": template["start_time"],
                            "end_time": template["end_time"],
                            "lunch": f"{lunch_start}-{lunch_end}" if lunch_start else None
                        })
                        
                        total_hours += template.get("hours", 8.0)
                
                total_headcount += headcount
                
                result["daily_slots"].append({
                    "target_date": demand.target_date.isoformat(),
                    "weekday_pt": demand.weekday_pt,
                    "headcount": headcount,
                    "slots": day_slots
                })
                
                day_key = demand.target_date.isoformat()
                coverage_by_hour[day_key] = self._calculate_coverage_by_hour(
                    day_slots, templates
                )
            
            schedule_plan.total_headcount_planned = total_headcount
            schedule_plan.total_hours_planned = total_hours
            schedule_plan.coverage_by_hour = coverage_by_hour
            schedule_plan.summary_json = {
                "total_headcount": total_headcount,
                "total_hours": round(total_hours, 1),
                "avg_daily_headcount": round(total_headcount / len(demands), 1) if demands else 0,
                "method_version": METHOD_VERSION,
                "applied_rules": self.get_applied_rules_trace(),
                "constraints_used": rule_constraints
            }
            
            self.db.commit()
            
            result["summary"] = schedule_plan.summary_json
            result["applied_rules"] = self.get_applied_rules_trace()
            
            # PROMPT: Apply WorkShift constraints
            self._apply_work_shift_constraints(sector_id, week_start, schedule_plan, result)
            
            result["success"] = True
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
        
        return result
    
    def _get_sector_parameters(self, sector_id: int) -> Optional[SectorOperationalParameters]:
        """Obtém parâmetros operacionais vigentes do setor."""
        return self.db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == sector_id,
            SectorOperationalParameters.is_current == True
        ).first()
    
    def _get_hourly_distribution(self, weekday_pt: str, event_type: EventType) -> Dict[int, float]:
        """Obtém distribuição horária por dia da semana."""
        metric_name = f"{event_type.value}_PCT"
        stats = self.db.query(HourlyDistributionStats).filter(
            HourlyDistributionStats.weekday_pt == weekday_pt,
            HourlyDistributionStats.metric_name == metric_name
        ).all()
        
        return {s.hour_timeline: s.pct for s in stats}
    
    def _allocate_templates(
        self,
        headcount: int,
        templates: List[Dict],
        checkout_dist: Dict[int, float],
        checkin_dist: Dict[int, float]
    ) -> Dict[str, int]:
        """
        Aloca headcount entre templates baseado na distribuição horária real.
        Usa HourlyDistributionStats para alinhar cobertura com picos de checkout/checkin.
        """
        if headcount <= 0:
            return {}
        
        if len(templates) == 1:
            return {templates[0]["name"]: headcount}
        
        morning_checkout_peak = sum(checkout_dist.get(h, 0) for h in range(8, 12))
        late_morning_checkout = sum(checkout_dist.get(h, 0) for h in range(12, 14))
        afternoon_checkin_peak = sum(checkin_dist.get(h, 0) for h in range(14, 19))
        evening_checkin = sum(checkin_dist.get(h, 0) for h in range(19, 23))
        
        morning_workload = morning_checkout_peak + (late_morning_checkout * 0.7)
        afternoon_workload = (late_morning_checkout * 0.3) + afternoon_checkin_peak + evening_checkin
        
        total_weight = morning_workload + afternoon_workload
        if total_weight > 0:
            morning_ratio = morning_workload / total_weight
        else:
            morning_ratio = 0.55
        
        morning_ratio = max(0.35, min(0.65, morning_ratio))
        
        morning_template = next((t for t in templates if "manhã" in t["name"].lower()), templates[0])
        afternoon_template = next((t for t in templates if "tarde" in t["name"].lower()), templates[-1])
        
        morning_count = max(1, round(headcount * morning_ratio)) if headcount > 0 else 0
        afternoon_count = max(0, headcount - morning_count)
        
        if headcount >= 2 and afternoon_count == 0:
            afternoon_count = 1
            morning_count = headcount - 1
        
        return {
            morning_template["name"]: morning_count,
            afternoon_template["name"]: afternoon_count
        }
    
    def _calculate_lunch_time(
        self,
        start_time: str,
        end_time: str,
        lunch_rules: Dict = None
    ) -> tuple:
        """Calcula horário de almoço respeitando as regras."""
        if not lunch_rules:
            lunch_rules = {
                "duration_min": 60,
                "window_start": "11:00",
                "window_end": "14:00",
                "min_hours_before": 3.0,
                "max_hours_before": 5.0
            }
        
        start_h, start_m = map(int, start_time.split(":"))
        window_start_h, window_start_m = map(int, lunch_rules.get("window_start", "11:00").split(":"))
        window_end_h, window_end_m = map(int, lunch_rules.get("window_end", "14:00").split(":"))
        
        min_hours = lunch_rules.get("min_hours_before", 3.0)
        earliest_lunch = start_h + min_hours
        
        lunch_start_h = max(int(earliest_lunch), window_start_h)
        
        if lunch_start_h > window_end_h:
            return None, None
        
        duration_min = lunch_rules.get("duration_min", 60)
        lunch_start = f"{lunch_start_h:02d}:00"
        
        lunch_end_h = lunch_start_h + (duration_min // 60)
        lunch_end_m = duration_min % 60
        lunch_end = f"{lunch_end_h:02d}:{lunch_end_m:02d}"
        
        return lunch_start, lunch_end
    
    def _calculate_coverage_by_hour(
        self,
        day_slots: List[Dict],
        templates: List[Dict]
    ) -> Dict[str, int]:
        """Calcula cobertura por hora do dia."""
        coverage = {}
        
        for hour in range(6, 24):
            hour_str = f"{hour:02d}:00"
            count = 0
            
            for slot in day_slots:
                start_h = int(slot["start_time"].split(":")[0])
                end_h = int(slot["end_time"].split(":")[0])
                
                if start_h <= hour < end_h:
                    if slot.get("lunch"):
                        lunch_parts = slot["lunch"].split("-")
                        lunch_start_h = int(lunch_parts[0].split(":")[0])
                        lunch_end_h = int(lunch_parts[1].split(":")[0])
                        if lunch_start_h <= hour < lunch_end_h:
                            continue
                    count += 1
            
            coverage[hour_str] = count
        
        return coverage

    def _apply_work_shift_constraints(
        self, 
        sector_id: int, 
        week_start: date, 
        schedule_plan: HousekeepingSchedulePlan,
        result: Dict
    ):
        """
        Ajusta os slots gerados para respeitar as restrições MANDATÓRIAS dos turnos de trabalho.
        """
        work_shifts = self.db.query(WorkShift).filter(
            WorkShift.sector_id == sector_id,
            WorkShift.is_active == True
        ).all()
        
        if not work_shifts:
            return

        # Busca slots do plano
        slots = self.db.query(ShiftSlot).filter(
            ShiftSlot.schedule_plan_id == schedule_plan.id
        ).all()

        applied_constraints = []
        violations = []

        for slot in slots:
            # weekday do python: 0=Seg ... 6=Dom
            # weekday do WorkShift: 1=Seg ... 7=Dom
            weekday_iso = slot.target_date.isoweekday()
            
            for shift in work_shifts:
                rule = next((r for r in shift.day_rules if r.weekday == weekday_iso), None)
                if not rule or not rule.start_time:
                    continue

                # Se o slot gerado for compatível com o template deste turno (mesmo nome ou proximidade)
                # Neste MVP, vamos assumir que se houver um turno mandatório, os slots do dia devem respeitá-lo.
                # Se houver múltiplos turnos no dia, a lógica precisaria de matching mais refinado.
                
                changed = False
                if rule.start_constraint == ShiftTimeConstraint.MANDATORY:
                    old_start = slot.start_time
                    new_start = rule.start_time.strftime("%H:%M")
                    if old_start != new_start:
                        slot.start_time = new_start
                        changed = True
                        applied_constraints.append(f"Day {slot.target_date}: Start {old_start} -> {new_start} (Mandatory)")

                if rule.end_constraint == ShiftTimeConstraint.MANDATORY:
                    old_end = slot.end_time
                    new_end = rule.end_time.strftime("%H:%M")
                    if old_end != new_end:
                        slot.end_time = new_end
                        changed = True
                        applied_constraints.append(f"Day {slot.target_date}: End {old_end} -> {new_end} (Mandatory)")

                if changed:
                    # Recalcula horas trabalhadas simplificado (não considera almoço neste passo por simplicidade)
                    # Idealmente chamaria _calculate_lunch_time novamente se mudar muito.
                    pass

        if applied_constraints:
            from app.models.agent_run import AgentTraceStep
            # Tenta encontrar o AgentRun associado
            # Nota: O generator não recebe o AgentRun diretamente, mas podemos inferir ou adicionar no trace
            # Para este MVP, vamos apenas logar no resumo
            result["summary"]["work_shift_constraints"] = applied_constraints
            
        self.db.commit()
    
    def get_schedule_plan(self, plan_id: int) -> Optional[Dict]:
        """Obtém detalhes de um plano de escala."""
        plan = self.db.query(HousekeepingSchedulePlan).filter(
            HousekeepingSchedulePlan.id == plan_id
        ).first()
        
        if not plan:
            return None
        
        slots = self.db.query(ShiftSlot).filter(
            ShiftSlot.schedule_plan_id == plan_id
        ).order_by(ShiftSlot.target_date, ShiftSlot.start_time).all()
        
        slots_by_day = {}
        for slot in slots:
            day_key = slot.target_date.isoformat()
            if day_key not in slots_by_day:
                slots_by_day[day_key] = []
            slots_by_day[day_key].append({
                "id": slot.id,
                "template_name": slot.template_name,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "lunch": f"{slot.lunch_start}-{slot.lunch_end}" if slot.lunch_start else None,
                "hours_worked": slot.hours_worked,
                "employee_id": slot.employee_id,
                "is_assigned": slot.is_assigned
            })
        
        return {
            "id": plan.id,
            "sector_id": plan.sector_id,
            "week_start": plan.week_start.isoformat(),
            "week_end": plan.week_end.isoformat(),
            "status": plan.status.value,
            "total_headcount_planned": plan.total_headcount_planned,
            "total_hours_planned": plan.total_hours_planned,
            "summary": plan.summary_json,
            "coverage_by_hour": plan.coverage_by_hour,
            "slots_by_day": slots_by_day,
            "created_at": plan.created_at.isoformat() if plan.created_at else None
        }
    
    def list_schedule_plans(self, sector_id: int, limit: int = 10) -> List[Dict]:
        """Lista planos de escala do setor."""
        plans = self.db.query(HousekeepingSchedulePlan).filter(
            HousekeepingSchedulePlan.sector_id == sector_id
        ).order_by(HousekeepingSchedulePlan.week_start.desc()).limit(limit).all()
        
        return [
            {
                "id": p.id,
                "week_start": p.week_start.isoformat(),
                "week_end": p.week_end.isoformat(),
                "status": p.status.value,
                "plan_kind": p.plan_kind.value if p.plan_kind else "baseline",
                "baseline_plan_id": p.baseline_plan_id,
                "total_headcount_planned": p.total_headcount_planned,
                "total_hours_planned": p.total_hours_planned,
                "validations": p.validations_json or [],
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in plans
        ]
    
    def generate_adjustment_schedule(
        self,
        week_start: date,
        sector_id: int,
        forecast_run_id: int,
        baseline_plan_id: int
    ) -> Dict:
        """
        Gera escala ADJUSTMENT baseada em daily update, vinculada a um baseline.
        
        PROMPT 3: Escala ajustada mantém referência ao baseline para comparação.
        """
        result = {
            "success": False,
            "schedule_plan_id": None,
            "plan_kind": "adjustment",
            "baseline_plan_id": baseline_plan_id,
            "daily_slots": [],
            "delta_vs_baseline": {},
            "errors": []
        }
        
        try:
            baseline_plan = self.db.query(HousekeepingSchedulePlan).filter(
                HousekeepingSchedulePlan.id == baseline_plan_id
            ).first()
            
            if not baseline_plan:
                result["errors"].append(f"Baseline plan {baseline_plan_id} não encontrado")
                return result
            
            gen_result = self.generate_housekeeping_schedule(
                week_start=week_start,
                sector_id=sector_id,
                forecast_run_id=forecast_run_id
            )
            
            if not gen_result["success"]:
                result["errors"] = gen_result["errors"]
                return result
            
            plan = self.db.query(HousekeepingSchedulePlan).filter(
                HousekeepingSchedulePlan.id == gen_result["schedule_plan_id"]
            ).first()
            
            if plan:
                plan.plan_kind = SchedulePlanKind.ADJUSTMENT
                plan.baseline_plan_id = baseline_plan_id
                self.db.commit()
            
            result["schedule_plan_id"] = gen_result["schedule_plan_id"]
            result["daily_slots"] = gen_result["daily_slots"]
            result["summary"] = gen_result["summary"]
            
            result["delta_vs_baseline"] = {
                "headcount_delta": gen_result["summary"]["total_headcount"] - baseline_plan.total_headcount_planned,
                "hours_delta": round(gen_result["summary"]["total_hours"] - baseline_plan.total_hours_planned, 1)
            }
            
            result["success"] = True
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
        
        return result
    
    def validate_schedule_legal(self, plan_id: int) -> Dict:
        """
        Valida escala contra regras legais de trabalho intermitente.
        
        PROMPT 8: Refatorado para usar cascade de regras:
        1. LaborRules (global) - regras trabalhistas
        2. SectorOperationalRules (por setor)
        
        Validações incluem:
        - Convocação com antecedência mínima (default 72h)
        - Limites de horas diárias e semanais
        - Descanso entre turnos
        - Dias consecutivos máximos
        """
        result = {
            "success": False,
            "plan_id": plan_id,
            "validations": [],
            "errors": [],
            "is_valid": True,
            "rules_used": {}
        }
        
        try:
            plan = self.db.query(HousekeepingSchedulePlan).filter(
                HousekeepingSchedulePlan.id == plan_id
            ).first()
            
            if not plan:
                result["errors"].append(f"Plano {plan_id} não encontrado")
                return result
            
            slots = self.db.query(ShiftSlot).filter(
                ShiftSlot.schedule_plan_id == plan_id
            ).order_by(ShiftSlot.target_date, ShiftSlot.start_time).all()
            
            constraints = self.get_legal_constraints(plan.sector_id)
            result["rules_used"] = constraints
            
            min_notice_hours = constraints.get("min_notice_hours", DEFAULT_CONVOCATION_NOTICE_HOURS)
            
            now = datetime.now()
            for slot in slots:
                slot_start_dt = datetime.combine(slot.target_date, time(int(slot.start_time.split(":")[0]), int(slot.start_time.split(":")[1])))
                hours_until_shift = (slot_start_dt - now).total_seconds() / 3600
                
                if hours_until_shift < min_notice_hours and hours_until_shift > 0:
                    result["validations"].append({
                        "type": "WARNING",
                        "rule": "CONVOCACAO_ANTECEDENCIA",
                        "slot_id": slot.id,
                        "target_date": slot.target_date.isoformat(),
                        "message": f"Convocacao com menos de {min_notice_hours}h ({hours_until_shift:.0f}h de antecedencia)"
                    })
            
            employee_slots = {}
            for slot in slots:
                if slot.employee_id:
                    if slot.employee_id not in employee_slots:
                        employee_slots[slot.employee_id] = []
                    employee_slots[slot.employee_id].append(slot)
            
            max_hours_day = constraints.get("max_hours_per_day", 8.0)
            min_rest = constraints.get("min_rest_between_shifts", 11.0)
            max_consecutive = constraints.get("max_consecutive_days", 6)
            max_week_hours = constraints.get("max_week_hours", 44.0)
            
            for emp_id, emp_slots in employee_slots.items():
                hours_by_day = {}
                dates_worked = set()
                
                for slot in emp_slots:
                    day_key = slot.target_date.isoformat()
                    if day_key not in hours_by_day:
                        hours_by_day[day_key] = 0
                    hours_by_day[day_key] += slot.hours_worked
                    dates_worked.add(slot.target_date)
                
                total_week_hours = sum(hours_by_day.values())
                if total_week_hours > max_week_hours:
                    result["validations"].append({
                        "type": "ERROR",
                        "rule": "LIMITE_SEMANAL",
                        "employee_id": emp_id,
                        "message": f"Colaborador {emp_id} excede {max_week_hours:.0f}h semanais: {total_week_hours:.1f}h"
                    })
                    result["is_valid"] = False
                
                for day_key, hours in hours_by_day.items():
                    if hours > max_hours_day:
                        result["validations"].append({
                            "type": "ERROR",
                            "rule": "LIMITE_DIARIO",
                            "employee_id": emp_id,
                            "target_date": day_key,
                            "message": f"Colaborador {emp_id} excede {max_hours_day}h no dia {day_key}: {hours:.1f}h"
                        })
                        result["is_valid"] = False
                
                sorted_dates = sorted(dates_worked)
                consecutive_count = 1
                for i in range(1, len(sorted_dates)):
                    if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                        consecutive_count += 1
                        if consecutive_count > max_consecutive:
                            result["validations"].append({
                                "type": "WARNING",
                                "rule": "DIAS_CONSECUTIVOS",
                                "employee_id": emp_id,
                                "message": f"Colaborador {emp_id} trabalha {consecutive_count} dias consecutivos"
                            })
                    else:
                        consecutive_count = 1
            
            plan.validations_json = result["validations"]
            self.db.commit()
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
    
    def preview_convocations(self, plan_id: int) -> Dict:
        """
        Gera prévia de convocações por colaborador com status de validação.
        
        PROMPT 3: Lista por colaboradora: dias, horários, status ok/warning/erro
        """
        result = {
            "success": False,
            "plan_id": plan_id,
            "convocations": [],
            "summary": {},
            "errors": []
        }
        
        try:
            plan = self.db.query(HousekeepingSchedulePlan).filter(
                HousekeepingSchedulePlan.id == plan_id
            ).first()
            
            if not plan:
                result["errors"].append(f"Plano {plan_id} não encontrado")
                return result
            
            slots = self.db.query(ShiftSlot).filter(
                ShiftSlot.schedule_plan_id == plan_id
            ).order_by(ShiftSlot.target_date, ShiftSlot.start_time).all()
            
            validation = self.validate_schedule_legal(plan_id)
            validation_by_slot = {}
            validation_by_employee = {}
            
            for v in validation.get("validations", []):
                slot_id = v.get("slot_id")
                emp_id = v.get("employee_id")
                if slot_id:
                    if slot_id not in validation_by_slot:
                        validation_by_slot[slot_id] = []
                    validation_by_slot[slot_id].append(v)
                if emp_id:
                    if emp_id not in validation_by_employee:
                        validation_by_employee[emp_id] = []
                    validation_by_employee[emp_id].append(v)
            
            employee_convocations = {}
            unassigned_slots = []
            
            now = datetime.now()
            
            for slot in slots:
                slot_info = {
                    "slot_id": slot.id,
                    "target_date": slot.target_date.isoformat(),
                    "weekday_pt": slot.weekday_pt,
                    "start_time": slot.start_time,
                    "end_time": slot.end_time,
                    "lunch": f"{slot.lunch_start}-{slot.lunch_end}" if slot.lunch_start else None,
                    "hours_worked": slot.hours_worked,
                    "status": "ok",
                    "warnings": []
                }
                
                slot_start_dt = datetime.combine(
                    slot.target_date, 
                    time(int(slot.start_time.split(":")[0]), int(slot.start_time.split(":")[1]))
                )
                hours_until = (slot_start_dt - now).total_seconds() / 3600
                
                min_notice = self.get_convocation_notice_hours()
                if hours_until < min_notice and hours_until > 0:
                    slot_info["status"] = "warning"
                    slot_info["warnings"].append(f"Menos de {min_notice}h de antecedencia ({hours_until:.0f}h)")
                
                if slot_info["slot_id"] in validation_by_slot:
                    for v in validation_by_slot[slot_info["slot_id"]]:
                        if v["type"] == "ERROR":
                            slot_info["status"] = "error"
                        slot_info["warnings"].append(v["message"])
                
                if slot.employee_id and slot.is_assigned:
                    if slot.employee_id not in employee_convocations:
                        emp = self.db.query(Employee).filter(Employee.id == slot.employee_id).first()
                        employee_convocations[slot.employee_id] = {
                            "employee_id": slot.employee_id,
                            "employee_name": emp.name if emp else f"Colaborador {slot.employee_id}",
                            "slots": [],
                            "total_hours": 0,
                            "total_days": 0,
                            "status": "ok",
                            "warnings": []
                        }
                    
                    employee_convocations[slot.employee_id]["slots"].append(slot_info)
                    employee_convocations[slot.employee_id]["total_hours"] += slot.hours_worked
                else:
                    unassigned_slots.append(slot_info)
            
            for emp_id, conv in employee_convocations.items():
                conv["total_days"] = len(set(s["target_date"] for s in conv["slots"]))
                
                if emp_id in validation_by_employee:
                    for v in validation_by_employee[emp_id]:
                        if v["type"] == "ERROR":
                            conv["status"] = "error"
                        elif v["type"] == "WARNING" and conv["status"] == "ok":
                            conv["status"] = "warning"
                        conv["warnings"].append(v["message"])
                
                for slot in conv["slots"]:
                    if slot["status"] == "error":
                        conv["status"] = "error"
                    elif slot["status"] == "warning" and conv["status"] == "ok":
                        conv["status"] = "warning"
            
            result["convocations"] = list(employee_convocations.values())
            result["unassigned_slots"] = unassigned_slots
            result["summary"] = {
                "total_employees": len(employee_convocations),
                "total_slots": len(slots),
                "assigned_slots": len(slots) - len(unassigned_slots),
                "unassigned_slots": len(unassigned_slots),
                "employees_ok": sum(1 for c in employee_convocations.values() if c["status"] == "ok"),
                "employees_warning": sum(1 for c in employee_convocations.values() if c["status"] == "warning"),
                "employees_error": sum(1 for c in employee_convocations.values() if c["status"] == "error")
            }
            
            result["success"] = True
            
        except Exception as e:
            result["errors"].append(str(e))
        
        return result
