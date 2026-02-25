from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import math

from app.models.governance_module import (
    SectorOperationalParameters, ForecastRun, ForecastDaily,
    HousekeepingDemandDaily, TurnoverRateStats
)
from app.models.data_lake import FrontdeskEventsHourlyAgg, EventType
from app.models.operational_calendar import OperationalCalendar, CalendarScope
from app.models.activity_program import ActivityProgramItem, ActivityProgramWeek, ProgramWeekStatus
from app.models.governance_activity import GovernanceActivity, WorkloadDriver
from app.services import regra_calculo_service
from app.services.rule_engine import RuleEngine

METHOD_VERSION = "1.3.0"

DEFAULT_TURNOVER_RATES = {
    "DOMINGO": 0.55,
    "SEGUNDA-FEIRA": 0.35,
    "TERÇA-FEIRA": 0.25,
    "QUARTA-FEIRA": 0.25,
    "QUINTA-FEIRA": 0.30,
    "SEXTA-FEIRA": 0.35,
    "SÁBADO": 0.40
}


class GovernanceDemandService:
    
    def __init__(self, db: Session):
        self.db = db
        self._rule_engine = RuleEngine(db)
        self._applied_rules_trace: List[str] = []

    def get_constraints_from_rule_engine(self, sector_id: int) -> Dict[str, Any]:
        constraints, applied_rules = self._rule_engine.get_all_constraints(sector_id)
        self._applied_rules_trace.extend(applied_rules)
        return constraints

    def get_applied_rules_trace(self) -> List[str]:
        return list(set(self._applied_rules_trace))

    def clear_rules_trace(self):
        self._applied_rules_trace = []
    
    def compute_housekeeping_demand(
        self,
        forecast_run_id: int,
        total_rooms: int = None
    ) -> Dict:
        """
        Calcula demanda de limpeza a partir do forecast.
        
        Args:
            forecast_run_id: ID da execução de forecast
            total_rooms: Total de quartos (override dos parâmetros)
        
        Returns:
            Dict com resultado do cálculo
        """
        result = {
            "success": False,
            "forecast_run_id": forecast_run_id,
            "daily_demands": [],
            "summary": {},
            "applied_rules": [],
            "errors": []
        }

        self.clear_rules_trace()
        
        try:
            forecast_run = self.db.query(ForecastRun).filter(
                ForecastRun.id == forecast_run_id
            ).first()
            
            if not forecast_run:
                result["errors"].append(f"ForecastRun {forecast_run_id} não encontrado")
                return result
            
            params = self._get_sector_parameters(forecast_run.sector_id)
            if not params:
                result["errors"].append(f"Parâmetros não encontrados para setor {forecast_run.sector_id}")
                return result

            rule_constraints = self.get_constraints_from_rule_engine(forecast_run.sector_id)
            
            if total_rooms is None:
                total_rooms = params.total_rooms or 100
            
            daily_forecasts = self.db.query(ForecastDaily).filter(
                ForecastDaily.forecast_run_id == forecast_run_id
            ).order_by(ForecastDaily.target_date).all()
            
            if not daily_forecasts:
                result["errors"].append("Nenhum forecast diário encontrado")
                return result
            
            existing = self.db.query(HousekeepingDemandDaily).filter(
                HousekeepingDemandDaily.forecast_run_id == forecast_run_id
            ).all()
            for e in existing:
                self.db.delete(e)
            
            total_minutes = 0
            total_hours = 0
            total_headcount = 0
            total_minutes_variable = 0
            total_minutes_constant = 0
            
            for forecast in daily_forecasts:
                demand = self._compute_daily_demand(
                    forecast=forecast,
                    params=params,
                    total_rooms=total_rooms,
                    sector_id=forecast_run.sector_id,
                    forecast_run_id=forecast_run_id,
                    rule_constraints=rule_constraints
                )
                
                demand_record = HousekeepingDemandDaily(
                    forecast_run_id=forecast_run_id,
                    target_date=forecast.target_date,
                    weekday_pt=forecast.weekday_pt,
                    occupied_rooms=demand["occupied_rooms"],
                    departures_count=demand["departures_count"],
                    arrivals_count=demand["arrivals_count"],
                    stayovers_estimated=demand["stayovers_estimated"],
                    minutes_required_raw=demand["minutes_required_raw"],
                    minutes_required_buffered=demand["minutes_required_buffered"],
                    hours_productive_required=demand["hours_productive_required"],
                    hours_total_required=demand["hours_total_required"],
                    headcount_required=demand["headcount_required"],
                    headcount_rounded=demand["headcount_rounded"],
                    calculation_breakdown=demand["breakdown"]
                )
                self.db.add(demand_record)
                
                result["daily_demands"].append({
                    "target_date": forecast.target_date.isoformat(),
                    "weekday_pt": forecast.weekday_pt,
                    "occ_adj": round(forecast.occ_adj, 2) if forecast.occ_adj else None,
                    **{k: v for k, v in demand.items() if k != "breakdown"}
                })
                
                total_minutes += demand["minutes_required_buffered"]
                total_hours += demand["hours_total_required"]
                total_headcount += demand["headcount_rounded"]
                total_minutes_variable += demand.get("minutes_variable", 0)
                total_minutes_constant += demand.get("minutes_constant", 0)
            
            self.db.commit()
            
            result["summary"] = {
                "total_rooms": total_rooms,
                "total_minutes_week": round(total_minutes, 1),
                "total_minutes_variable_week": round(total_minutes_variable, 1),
                "total_minutes_constant_week": round(total_minutes_constant, 1),
                "total_hours_week": round(total_hours, 1),
                "total_headcount_week": total_headcount,
                "avg_headcount_daily": round(total_headcount / len(daily_forecasts), 1) if daily_forecasts else 0,
                "params_used": {
                    "cleaning_time_vago_sujo_min": params.cleaning_time_vago_sujo_min,
                    "cleaning_time_estadia_min": params.cleaning_time_estadia_min,
                    "target_utilization_pct": params.target_utilization_pct,
                    "buffer_pct": rule_constraints.get("buffer_pct", params.buffer_pct)
                },
                "applied_rules": self.get_applied_rules_trace(),
                "rule_constraints": rule_constraints
            }

            result["applied_rules"] = self.get_applied_rules_trace()
            result["success"] = True
            
        except Exception as e:
            self.db.rollback()
            result["errors"].append(str(e))
        
        return result
    
    def _compute_daily_demand(
        self,
        forecast: ForecastDaily,
        params: SectorOperationalParameters,
        total_rooms: int,
        sector_id: int = None,
        forecast_run_id: int = None,
        rule_constraints: Dict[str, Any] = None
    ) -> Dict:
        """
        Calcula demanda de um dia específico.
        
        ATUALIZAÇÃO: Fórmula inclui atividades constantes:
        - minutes_variable = departures * tempo_vago_sujo + stayovers * tempo_estadia
        - minutes_constant = soma de atividades constantes programadas
        - minutes_raw = minutes_variable + minutes_constant
        - minutes_buffered = minutes_raw * (1 + buffer_pct/100)
        - hours_productive = minutes_buffered / 60
        - hours_total = hours_productive / (target_utilization / 100)
        - headcount = ceil(hours_total / hours_per_shift)
        """
        occ_adj = forecast.occ_adj or 0
        occupied_rooms = round(total_rooms * occ_adj / 100)
        
        departures_data = self._get_departures_count(
            target_date=forecast.target_date, 
            occupied_rooms=occupied_rooms,
            weekday_pt=forecast.weekday_pt,
            sector_id=sector_id
        )
        departures_count = departures_data["count"]
        departures_source = departures_data["source"]
        turnover_rate_used = departures_data.get("turnover_rate_used")
        
        arrivals_count = self._get_arrivals_count(
            forecast.target_date,
            occupied_rooms=occupied_rooms,
            weekday_pt=forecast.weekday_pt
        )
        
        if departures_count > 0:
            stayovers_estimated = max(occupied_rooms - departures_count, 0)
        else:
            stayovers_estimated = max(occupied_rooms - arrivals_count, 0) if arrivals_count > 0 else occupied_rooms
        
        tempo_vago_sujo = params.cleaning_time_vago_sujo_min or 25.0
        tempo_estadia = params.cleaning_time_estadia_min or 10.0
        
        minutes_variable = (departures_count * tempo_vago_sujo) + (stayovers_estimated * tempo_estadia)
        
        constant_activities_data = self._get_constant_activities_for_date(
            target_date=forecast.target_date,
            sector_id=sector_id,
            forecast_run_id=forecast_run_id
        )
        minutes_constant = constant_activities_data["total_minutes"]
        constant_activities_details = constant_activities_data["activities"]
        
        minutes_required_raw = minutes_variable + minutes_constant
        
        if rule_constraints and "buffer_pct" in rule_constraints:
            buffer_pct = rule_constraints["buffer_pct"]
        else:
            buffer_pct = params.buffer_pct or 10.0
        minutes_required_buffered = minutes_required_raw * (1 + buffer_pct / 100)
        
        calendar_factors = self._get_calendar_factors(forecast.target_date, sector_id)
        demand_factor = calendar_factors["demand_factor"]
        productivity_factor = calendar_factors["productivity_factor"]
        
        minutes_calendar_adjusted = minutes_required_buffered * demand_factor
        
        dias_semana_map = {
            "DOMINGO": "DOM", "SEGUNDA-FEIRA": "SEG", "TERÇA-FEIRA": "TER",
            "QUARTA-FEIRA": "QUA", "QUINTA-FEIRA": "QUI", "SEXTA-FEIRA": "SEX", "SÁBADO": "SAB"
        }
        dia_semana = dias_semana_map.get(forecast.weekday_pt, "SEG")
        
        contexto_regras = {
            "ocupacao": occ_adj / 100,
            "quartos_ocupados": occupied_rooms,
            "checkout": departures_count,
            "checkin": arrivals_count,
            "stayover": stayovers_estimated,
            "dia_semana": dia_semana,
            "total_rooms": total_rooms
        }
        
        regras_demanda_log = []
        regras_ajustes_log = []
        
        if sector_id:
            minutes_with_rules, regras_demanda_log = regra_calculo_service.calcular_demanda_com_regras(
                self.db, sector_id, minutes_calendar_adjusted, contexto_regras
            )
            
            minutes_adjusted, regras_ajustes_log = regra_calculo_service.aplicar_ajustes_com_regras(
                self.db, sector_id, minutes_with_rules, contexto_regras
            )
            
            if regras_demanda_log or regras_ajustes_log:
                minutes_calendar_adjusted = minutes_adjusted
        
        hours_productive_required = minutes_calendar_adjusted / 60
        
        target_utilization = params.target_utilization_pct or 85.0
        adjusted_utilization = target_utilization * productivity_factor
        hours_total_required = hours_productive_required / (adjusted_utilization / 100)
        
        hours_per_shift = self._get_avg_shift_hours(params)
        headcount_required = hours_total_required / hours_per_shift
        headcount_rounded = math.ceil(headcount_required) if headcount_required > 0 else 0
        
        breakdown = {
            "formula": "minutes = (departures*tempo_vago_sujo + stayovers*tempo_estadia) + atividades_constantes",
            "method_version": METHOD_VERSION,
            "inputs": {
                "occ_adj_pct": occ_adj,
                "total_rooms": total_rooms,
                "occupied_rooms": occupied_rooms,
                "departures_count": departures_count,
                "departures_source": departures_source,
                "turnover_rate_used": turnover_rate_used,
                "arrivals_count": arrivals_count,
                "stayovers_estimated": stayovers_estimated,
                "tempo_vago_sujo_min": tempo_vago_sujo,
                "tempo_estadia_min": tempo_estadia,
                "buffer_pct": buffer_pct,
                "target_utilization_pct": target_utilization,
                "adjusted_utilization_pct": round(adjusted_utilization, 2),
                "hours_per_shift": hours_per_shift
            },
            "calendar_factors": {
                "demand_factor": demand_factor,
                "productivity_factor": productivity_factor,
                "block_convocations": calendar_factors["block_convocations"],
                "applied_events": calendar_factors["applied_events"],
                "has_calendar_adjustment": calendar_factors["has_calendar_adjustment"]
            },
            "constant_activities": {
                "total_minutes": round(minutes_constant, 1),
                "count": len(constant_activities_details),
                "activities": constant_activities_details
            },
            "regras_aplicadas": {
                "demanda": regras_demanda_log,
                "ajustes": regras_ajustes_log,
                "total_regras": len(regras_demanda_log) + len(regras_ajustes_log)
            },
            "calculations": {
                "minutes_variable": round(minutes_variable, 1),
                "minutes_constant": round(minutes_constant, 1),
                "minutes_raw": round(minutes_required_raw, 1),
                "minutes_buffered": round(minutes_required_buffered, 1),
                "minutes_calendar_adjusted": round(minutes_calendar_adjusted, 1),
                "hours_productive": round(hours_productive_required, 2),
                "hours_total": round(hours_total_required, 2),
                "headcount_exact": round(headcount_required, 2),
                "headcount_rounded": headcount_rounded
            }
        }
        
        return {
            "occupied_rooms": occupied_rooms,
            "departures_count": departures_count,
            "arrivals_count": arrivals_count,
            "stayovers_estimated": stayovers_estimated,
            "minutes_variable": round(minutes_variable, 1),
            "minutes_constant": round(minutes_constant, 1),
            "minutes_required_raw": round(minutes_required_raw, 1),
            "minutes_required_buffered": round(minutes_required_buffered, 1),
            "hours_productive_required": round(hours_productive_required, 2),
            "hours_total_required": round(hours_total_required, 2),
            "headcount_required": round(headcount_required, 2),
            "headcount_rounded": headcount_rounded,
            "constant_activities_count": len(constant_activities_details),
            "breakdown": breakdown
        }
    
    def _get_sector_parameters(self, sector_id: int) -> Optional[SectorOperationalParameters]:
        """Obtém parâmetros operacionais vigentes do setor."""
        return self.db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == sector_id,
            SectorOperationalParameters.is_current == True
        ).first()
    
    def _get_constant_activities_for_date(
        self,
        target_date: date,
        sector_id: int = None,
        forecast_run_id: int = None
    ) -> Dict:
        """
        Obtém atividades constantes programadas para uma data específica.
        
        Atividades constantes são aquelas com workload_driver = CONSTANT
        que estão programadas no ActivityProgramItem para a data.
        
        Args:
            target_date: Data alvo
            sector_id: ID do setor
            forecast_run_id: ID do forecast run (para buscar programação vinculada)
        
        Returns:
            Dict com total_minutes e lista de atividades detalhadas
        """
        activities = []
        total_minutes = 0.0
        
        if not sector_id:
            return {"total_minutes": 0.0, "activities": []}
        
        base_query = self.db.query(ActivityProgramItem).join(
            GovernanceActivity,
            ActivityProgramItem.activity_id == GovernanceActivity.id
        ).filter(
            ActivityProgramItem.op_date == target_date,
            ActivityProgramItem.sector_id == sector_id,
            GovernanceActivity.workload_driver == WorkloadDriver.CONSTANT,
            GovernanceActivity.is_active == True
        )
        
        if forecast_run_id:
            program_week_ids = self.db.query(ActivityProgramWeek.id).filter(
                ActivityProgramWeek.forecast_run_id == forecast_run_id
            ).subquery()
            
            base_query = base_query.filter(
                ActivityProgramItem.program_week_id.in_(
                    self.db.query(program_week_ids.c.id)
                )
            )
        
        program_items = base_query.distinct().all()
        
        seen_item_ids = set()
        for item in program_items:
            if item.id in seen_item_ids:
                continue
            seen_item_ids.add(item.id)
            
            activity = self.db.query(GovernanceActivity).filter(
                GovernanceActivity.id == item.activity_id
            ).first()
            
            if activity:
                item_minutes = item.workload_minutes if item.workload_minutes else (
                    item.quantity * activity.average_time_minutes
                )
                total_minutes += item_minutes
                
                activities.append({
                    "activity_id": activity.id,
                    "activity_code": activity.code,
                    "activity_name": activity.name,
                    "quantity": item.quantity,
                    "minutes": round(item_minutes, 1),
                    "source": "programmed"
                })
        
        return {
            "total_minutes": round(total_minutes, 1),
            "activities": activities
        }
    
    def _get_calendar_factors(self, target_date: date, sector_id: int = None) -> Dict:
        """
        Obtém fatores do calendário operacional para a data.
        
        PROMPT 13: Integração com calendário operacional
        - Aplica regra GLOBAL primeiro
        - Depois sobrescreve/ajusta com regra do SETOR
        - Retorna fatores finais combinados
        """
        events = self.db.query(OperationalCalendar).filter(
            OperationalCalendar.date == target_date
        ).all()
        
        productivity_factor = 1.0
        demand_factor = 1.0
        block_convocations = False
        applied_events = []
        
        global_events = [e for e in events if e.scope == CalendarScope.GLOBAL]
        for event in global_events:
            productivity_factor *= event.productivity_factor
            demand_factor *= event.demand_factor
            if event.block_convocations:
                block_convocations = True
            applied_events.append({"name": event.name, "scope": "GLOBAL", "type": event.holiday_type.value})
        
        if sector_id:
            sector_events = [e for e in events if e.scope == CalendarScope.SECTOR and e.sector_id == sector_id]
            for event in sector_events:
                productivity_factor *= event.productivity_factor
                demand_factor *= event.demand_factor
                if event.block_convocations:
                    block_convocations = True
                applied_events.append({"name": event.name, "scope": "SECTOR", "type": event.holiday_type.value})
        
        return {
            "productivity_factor": round(productivity_factor, 4),
            "demand_factor": round(demand_factor, 4),
            "block_convocations": block_convocations,
            "applied_events": applied_events,
            "has_calendar_adjustment": len(applied_events) > 0
        }
    
    def _get_departures_count(
        self,
        target_date: date,
        occupied_rooms: int = None,
        weekday_pt: str = None,
        sector_id: int = None
    ) -> Dict:
        """
        Obtém contagem de checkouts do dia.
        
        PROMPT 4: 
        1. Tenta buscar do agregado real (FrontdeskEventsHourlyAgg)
        2. Se não houver, estima usando turnover_rate do TurnoverRateStats
        3. Se não houver estatísticas, usa fallback configurável
        
        Returns:
            Dict com count, source e metadata
        """
        result = self.db.query(func.sum(FrontdeskEventsHourlyAgg.count_events)).filter(
            FrontdeskEventsHourlyAgg.op_date == target_date,
            FrontdeskEventsHourlyAgg.event_type == EventType.CHECKOUT
        ).scalar()
        
        if result and int(result) > 0:
            return {
                "count": int(result),
                "source": "REAL",
                "turnover_rate_used": None,
                "fallback_used": False
            }
        
        if occupied_rooms and weekday_pt:
            stat = self.db.query(TurnoverRateStats).filter(
                TurnoverRateStats.weekday_pt == weekday_pt,
                TurnoverRateStats.sector_id == sector_id
            ).first()
            
            if stat and stat.rate is not None:
                count = round(occupied_rooms * stat.rate)
                return {
                    "count": count,
                    "source": "TURNOVER_STATS",
                    "turnover_rate_used": stat.rate,
                    "fallback_used": stat.fallback_used
                }
            
            default_rate = DEFAULT_TURNOVER_RATES.get(weekday_pt, 0.35)
            count = round(occupied_rooms * default_rate)
            return {
                "count": count,
                "source": "DEFAULT_FALLBACK",
                "turnover_rate_used": default_rate,
                "fallback_used": True
            }
        
        return {
            "count": 0,
            "source": "NO_DATA",
            "turnover_rate_used": None,
            "fallback_used": True
        }
    
    def _get_arrivals_count(self, target_date: date, occupied_rooms: int = None, weekday_pt: str = None) -> int:
        """
        Obtém contagem de checkins do dia operacional.
        1. Tenta buscar do agregado real (FrontdeskEventsHourlyAgg)  
        2. Se não houver, estima baseado na distribuição estatística
        """
        result = self.db.query(func.sum(FrontdeskEventsHourlyAgg.count_events)).filter(
            FrontdeskEventsHourlyAgg.op_date == target_date,
            FrontdeskEventsHourlyAgg.event_type == EventType.CHECKIN
        ).scalar()
        
        if result and int(result) > 0:
            return int(result)
        
        if occupied_rooms and weekday_pt:
            avg_checkin_pct = self._get_estimated_checkin_pct(weekday_pt)
            return round(occupied_rooms * avg_checkin_pct / 100)
        
        return 0
    
    def _get_estimated_checkout_pct(self, weekday_pt: str, sector_id: int = None) -> float:
        """
        Obtém percentual estimado de checkouts em relação aos quartos ocupados.
        
        PROMPT 4: Usa estatísticas de turnover calculadas do histórico real.
        Se não houver estatísticas, usa fallback configurável.
        
        Args:
            weekday_pt: Dia da semana em português
            sector_id: ID do setor (opcional)
        
        Returns:
            Percentual de checkout (0-100)
        """
        stat = self.db.query(TurnoverRateStats).filter(
            TurnoverRateStats.weekday_pt == weekday_pt,
            TurnoverRateStats.sector_id == sector_id
        ).first()
        
        if stat and stat.rate is not None:
            return stat.rate * 100
        
        default_rate = DEFAULT_TURNOVER_RATES.get(weekday_pt, 0.35)
        return default_rate * 100
    
    def _get_estimated_checkin_pct(self, weekday_pt: str) -> float:
        """
        Obtém percentual estimado de checkins em relação aos quartos ocupados.
        
        Retorna um ratio realista baseado em padrões hoteleiros típicos:
        - Sexta/Sábado: alto volume de checkin (início de fim de semana)
        - Domingo/Segunda: moderado
        - Dias úteis: moderado (viajantes de negócios)
        """
        default_pcts = {
            "SEXTA-FEIRA": 50.0,
            "SÁBADO": 45.0,
            "DOMINGO": 30.0,
            "SEGUNDA-FEIRA": 25.0,
            "TERÇA-FEIRA": 30.0,
            "QUARTA-FEIRA": 35.0,
            "QUINTA-FEIRA": 40.0
        }
        return default_pcts.get(weekday_pt, 35.0)
    
    def _get_avg_shift_hours(self, params: SectorOperationalParameters) -> float:
        """Obtém média de horas por turno dos templates."""
        templates = params.shift_templates or []
        if not templates:
            return 8.0
        
        total_hours = sum(t.get("hours", 8.0) for t in templates)
        return total_hours / len(templates)
    
    def get_demand_by_forecast_run(self, forecast_run_id: int) -> List[Dict]:
        """Obtém demanda calculada para um forecast run."""
        demands = self.db.query(HousekeepingDemandDaily).filter(
            HousekeepingDemandDaily.forecast_run_id == forecast_run_id
        ).order_by(HousekeepingDemandDaily.target_date).all()
        
        return [
            {
                "id": d.id,
                "target_date": d.target_date.isoformat(),
                "weekday_pt": d.weekday_pt,
                "occupied_rooms": d.occupied_rooms,
                "departures_count": d.departures_count,
                "arrivals_count": d.arrivals_count,
                "stayovers_estimated": d.stayovers_estimated,
                "minutes_required_raw": d.minutes_required_raw,
                "minutes_required_buffered": d.minutes_required_buffered,
                "hours_productive_required": d.hours_productive_required,
                "hours_total_required": d.hours_total_required,
                "headcount_required": d.headcount_required,
                "headcount_rounded": d.headcount_rounded,
                "breakdown": d.calculation_breakdown
            }
            for d in demands
        ]
