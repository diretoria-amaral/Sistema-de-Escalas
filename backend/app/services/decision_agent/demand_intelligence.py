"""
Nucleo 1: Inteligencia de Demanda

Responsabilidades:
- Consumir HP diario (mes corrente + proximo)
- Diferenciar dados historicos vs previsoes
- Aplicar estatistica de variacao
- Incorporar margem de seguranca
- Calcular demanda total semanal

Versao: 1.0.0
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.schemas.decision_agent import (
    DemandIntelligenceOutput,
    DailyDemand,
    WeeklyTotals,
    RuleApplied,
    DataSourceUsed,
    HPSourceType,
    RuleType
)


class DemandIntelligenceService:
    """
    Servico de Inteligencia de Demanda.
    
    Calcula a demanda total de trabalho para uma semana,
    considerando todas as fontes de demanda e aplicando
    ajustes estatisticos e margens de seguranca.
    """
    
    VERSION = "1.0.0"
    
    def __init__(self, db: Session):
        self.db = db
        self._rules_applied: List[RuleApplied] = []
        self._data_sources: List[DataSourceUsed] = []
        self._errors: List[str] = []
        self._warnings: List[str] = []
    
    def calculate(
        self,
        sector_id: int,
        week_start: date,
        eventual_activities: Optional[List[Dict[str, Any]]] = None
    ) -> DemandIntelligenceOutput:
        """
        Calcula a demanda completa para uma semana.
        
        Args:
            sector_id: ID do setor
            week_start: Data de inicio da semana (segunda-feira)
            eventual_activities: Lista de atividades eventuais (input do usuario)
        
        Returns:
            DemandIntelligenceOutput com demanda detalhada
        """
        self._reset_state()
        
        from app.models.sector import Sector
        from app.models.governance_module import SectorOperationalParameters
        
        sector = self.db.query(Sector).filter(Sector.id == sector_id).first()
        if not sector:
            return self._error_output(sector_id, week_start, f"Setor {sector_id} nao encontrado.")
        
        params = self.db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == sector_id
        ).first()
        if not params:
            return self._error_output(sector_id, week_start, f"Parametros operacionais do setor nao configurados.")
        
        week_end = week_start + timedelta(days=6)
        today = date.today()
        
        daily_demands = []
        for i in range(7):
            current_date = week_start + timedelta(days=i)
            weekday = self._get_weekday_pt(current_date)
            
            hp_source = HPSourceType.HISTORICO if current_date < today else HPSourceType.PREVISAO
            
            total_rooms = params.total_rooms if params.total_rooms else 100
            hp_data = self._get_hp_data(sector_id, current_date, total_rooms)
            
            minutes_variable = self._calculate_variable_minutes(hp_data, params)
            minutes_constant = self._calculate_constant_minutes(sector_id, current_date)
            minutes_recurrent = self._calculate_recurrent_minutes(sector_id, current_date)
            minutes_eventual = self._calculate_eventual_minutes(
                eventual_activities, current_date
            ) if eventual_activities else 0
            
            minutes_raw = minutes_variable + minutes_constant + minutes_recurrent + minutes_eventual
            
            variance_factor = self._get_variance_factor(sector_id, weekday)
            minutes_with_variance = minutes_raw * (1 + variance_factor)
            
            safety_margin = params.buffer_pct / 100 if params.buffer_pct else 0
            minutes_with_safety = minutes_with_variance * (1 + safety_margin)
            
            daily_demands.append(DailyDemand(
                date=current_date,
                weekday=weekday,
                hp_source=hp_source,
                occupancy_pct=hp_data.get("occupancy_pct", 0),
                occupancy_rooms=hp_data.get("occupancy_rooms", 0),
                departures=hp_data.get("departures", 0),
                arrivals=hp_data.get("arrivals", 0),
                stayovers=hp_data.get("stayovers", 0),
                minutes_variable=minutes_variable,
                minutes_constant=minutes_constant,
                minutes_recurrent=minutes_recurrent,
                minutes_eventual=minutes_eventual,
                minutes_raw=minutes_raw,
                minutes_with_variance=minutes_with_variance,
                minutes_with_safety=minutes_with_safety,
                variance_applied=variance_factor,
                safety_margin_applied=safety_margin
            ))
        
        weekly_totals = WeeklyTotals(
            minutes_variable=sum(d.minutes_variable for d in daily_demands),
            minutes_constant=sum(d.minutes_constant for d in daily_demands),
            minutes_recurrent=sum(d.minutes_recurrent for d in daily_demands),
            minutes_eventual=sum(d.minutes_eventual for d in daily_demands),
            minutes_total=sum(d.minutes_with_safety for d in daily_demands),
            hours_total=sum(d.minutes_with_safety for d in daily_demands) / 60
        )
        
        self._apply_demand_rules(sector_id, daily_demands, weekly_totals)
        
        return DemandIntelligenceOutput(
            sector_id=sector_id,
            sector_name=sector.name,
            week_start=week_start,
            week_end=week_end,
            daily_demands=daily_demands,
            weekly_totals=weekly_totals,
            rules_applied=self._rules_applied,
            data_sources=self._data_sources,
            calculation_timestamp=datetime.now(),
            errors=self._errors,
            warnings=self._warnings
        )
    
    def _reset_state(self):
        """Reseta estado interno para nova execucao."""
        self._rules_applied = []
        self._data_sources = []
        self._errors = []
        self._warnings = []
    
    def _error_output(self, sector_id: int, week_start: date, error: str) -> DemandIntelligenceOutput:
        """Retorna output de erro."""
        return DemandIntelligenceOutput(
            sector_id=sector_id,
            sector_name="",
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            daily_demands=[],
            weekly_totals=WeeklyTotals(
                minutes_variable=0,
                minutes_constant=0,
                minutes_recurrent=0,
                minutes_eventual=0,
                minutes_total=0,
                hours_total=0
            ),
            rules_applied=[],
            data_sources=[],
            calculation_timestamp=datetime.now(),
            errors=[error],
            warnings=[]
        )
    
    def _get_weekday_pt(self, d: date) -> str:
        """Retorna dia da semana em portugues."""
        weekdays = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
        return weekdays[d.weekday()]
    
    def _get_hp_data(self, sector_id: int, target_date: date, total_rooms: int = 100) -> Dict[str, Any]:
        """
        Obtem dados de HP para uma data.
        Diferencia dados historicos (realizados) de previsoes.
        Usa dados de frontdesk events quando disponiveis.
        """
        from app.models.data_lake import OccupancyLatest, FrontdeskEventsHourlyAgg, EventType
        from sqlalchemy import func
        
        hp = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date == target_date
        ).first()
        
        is_historical = False
        occupancy_pct = 0
        occupancy_rooms = 0
        
        if hp:
            self._data_sources.append(DataSourceUsed(
                source_name="OccupancyLatest",
                source_type="HP",
                records_count=1,
                date_range_start=target_date,
                date_range_end=target_date
            ))
            
            is_historical = hp.latest_real_occupancy_pct is not None
            occupancy_pct = hp.latest_real_occupancy_pct if is_historical else (hp.latest_forecast_occupancy_pct or 0)
            occupancy_rooms = int((occupancy_pct or 0) * total_rooms / 100) if occupancy_pct else 0
        
        departures = self.db.query(func.sum(FrontdeskEventsHourlyAgg.count_events)).filter(
            FrontdeskEventsHourlyAgg.op_date == target_date,
            FrontdeskEventsHourlyAgg.event_type == EventType.CHECKOUT
        ).scalar()
        
        arrivals = self.db.query(func.sum(FrontdeskEventsHourlyAgg.count_events)).filter(
            FrontdeskEventsHourlyAgg.op_date == target_date,
            FrontdeskEventsHourlyAgg.event_type == EventType.CHECKIN
        ).scalar()
        
        departures = int(departures) if departures else 0
        arrivals = int(arrivals) if arrivals else 0
        
        if departures == 0 and occupancy_rooms > 0:
            weekday = self._get_weekday_pt(target_date)
            departures = self._estimate_departures(occupancy_rooms, weekday)
        
        if arrivals == 0 and occupancy_rooms > 0:
            weekday = self._get_weekday_pt(target_date)
            arrivals = self._estimate_arrivals(occupancy_rooms, weekday)
        
        stayovers = max(0, occupancy_rooms - departures)
        
        if departures > 0 or arrivals > 0:
            self._data_sources.append(DataSourceUsed(
                source_name="FrontdeskEventsHourlyAgg",
                source_type="EVENTOS",
                records_count=1,
                date_range_start=target_date,
                date_range_end=target_date
            ))
        
        if not hp:
            self._warnings.append(f"Dados de HP nao encontrados para {target_date}")
        
        return {
            "occupancy_pct": occupancy_pct or 0,
            "occupancy_rooms": occupancy_rooms,
            "departures": departures,
            "arrivals": arrivals,
            "stayovers": stayovers,
            "is_historical": is_historical
        }
    
    def _estimate_departures(self, occupancy_rooms: int, weekday: str) -> int:
        """Estima checkouts baseado em turnover rate tipico."""
        from app.models.data_lake import WeekdayBiasStats
        
        bias = self.db.query(WeekdayBiasStats).filter(
            WeekdayBiasStats.metric_name == "TURNOVER_RATE",
            WeekdayBiasStats.weekday_pt == weekday
        ).first()
        
        turnover_rate = 0.25
        if bias and bias.bias_pp:
            turnover_rate = min(max(0.15, 0.25 + (bias.bias_pp / 100)), 0.40)
        
        return max(1, int(occupancy_rooms * turnover_rate))
    
    def _estimate_arrivals(self, occupancy_rooms: int, weekday: str) -> int:
        """Estima checkins baseado em estatisticas."""
        return max(1, int(occupancy_rooms * 0.20))
    
    def _calculate_variable_minutes(self, hp_data: Dict, params) -> float:
        """
        Calcula minutos de limpeza variavel baseada em ocupacao.
        LVS (Vago Sujo) + LET (Estadia)
        """
        departures = hp_data.get("departures", 0)
        stayovers = hp_data.get("stayovers", 0)
        
        time_lvs = params.cleaning_time_vago_sujo_min if params.cleaning_time_vago_sujo_min else 30
        time_let = params.cleaning_time_estadia_min if params.cleaning_time_estadia_min else 15
        
        minutes_lvs = departures * time_lvs
        minutes_let = stayovers * time_let
        
        return minutes_lvs + minutes_let
    
    def _calculate_constant_minutes(self, sector_id: int, target_date: date) -> float:
        """
        Calcula minutos de atividades constantes programadas.
        """
        from app.models.governance_activity import GovernanceActivity, ActivityClassification
        
        activities = self.db.query(GovernanceActivity).filter(
            GovernanceActivity.sector_id == sector_id,
            GovernanceActivity.is_active == True,
            GovernanceActivity.workload_driver == "CONSTANT"
        ).all()
        
        total_minutes = 0
        for activity in activities:
            total_minutes += activity.average_time_minutes or 0
        
        return total_minutes
    
    def _calculate_recurrent_minutes(self, sector_id: int, target_date: date) -> float:
        """
        Calcula minutos de atividades recorrentes para a data.
        Considera periodicidade e tolerancia.
        """
        from app.models.governance_activity import GovernanceActivity, ActivityClassification
        from app.models.activity_periodicity import ActivityPeriodicity
        
        recurrent_activities = self.db.query(GovernanceActivity).filter(
            GovernanceActivity.sector_id == sector_id,
            GovernanceActivity.is_active == True,
            GovernanceActivity.classificacao_atividade == "RECORRENTE"
        ).all()
        
        total_minutes = 0
        for activity in recurrent_activities:
            if self._is_activity_due(activity, target_date):
                total_minutes += activity.average_time_minutes or 0
        
        return total_minutes
    
    def _is_activity_due(self, activity, target_date: date) -> bool:
        """
        Verifica se uma atividade recorrente deve ser executada na data.
        """
        if not activity.periodicidade_id:
            return False
        
        from app.models.activity_periodicity import ActivityPeriodicity
        
        periodicity = self.db.query(ActivityPeriodicity).filter(
            ActivityPeriodicity.id == activity.periodicidade_id
        ).first()
        
        if not periodicity:
            return False
        
        if periodicity.tipo == "DAILY":
            return True
        
        if not activity.data_primeira_execucao:
            return False
        
        first_exec = activity.data_primeira_execucao
        days_since = (target_date - first_exec).days
        
        if days_since < 0:
            return False
        
        interval = periodicity.intervalo_dias or 1
        
        if days_since % interval == 0:
            return True
        
        tolerance = activity.tolerancia_dias or 0
        if tolerance > 0:
            for t in range(1, tolerance + 1):
                if (days_since - t) >= 0 and (days_since - t) % interval == 0:
                    return True
        
        return False
    
    def _calculate_eventual_minutes(
        self,
        eventual_activities: List[Dict[str, Any]],
        target_date: date
    ) -> float:
        """
        Calcula minutos de atividades eventuais informadas pelo usuario.
        """
        if not eventual_activities:
            return 0
        
        total_minutes = 0
        for activity in eventual_activities:
            activity_date = activity.get("date")
            if isinstance(activity_date, str):
                activity_date = date.fromisoformat(activity_date)
            
            if activity_date == target_date:
                total_minutes += activity.get("minutes", 0)
        
        return total_minutes
    
    def _get_variance_factor(self, sector_id: int, weekday: str) -> float:
        """
        Obtem fator de variancia estatistica para o dia da semana.
        """
        from app.models.data_lake import WeekdayBiasStats
        
        bias = self.db.query(WeekdayBiasStats).filter(
            WeekdayBiasStats.weekday_pt == weekday
        ).first()
        
        if bias and bias.ewma_bias:
            self._data_sources.append(DataSourceUsed(
                source_name="WeekdayBiasStats",
                source_type="ESTATISTICA",
                records_count=1
            ))
            return bias.ewma_bias / 100
        
        return 0
    
    def _apply_demand_rules(
        self,
        sector_id: int,
        daily_demands: List[DailyDemand],
        weekly_totals: WeeklyTotals
    ):
        """
        Aplica regras de calculo de demanda definidas para o setor.
        """
        from app.models.regra_calculo_setor import RegraCalculoSetor, RegraEscopo
        
        rules = self.db.query(RegraCalculoSetor).filter(
            RegraCalculoSetor.setor_id == sector_id,
            RegraCalculoSetor.escopo == RegraEscopo.DEMANDA,
            RegraCalculoSetor.ativo == True
        ).order_by(RegraCalculoSetor.prioridade.asc()).all()
        
        for rule in rules:
            self._rules_applied.append(RuleApplied(
                rule_id=rule.id,
                rule_name=rule.nome,
                rule_type=RuleType.SECTOR,
                priority=rule.prioridade,
                action_taken=f"Regra de demanda aplicada: {rule.acao_json.get('tipo', 'desconhecido') if rule.acao_json else 'N/A'}"
            ))
