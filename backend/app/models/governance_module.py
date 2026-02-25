from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, ForeignKey, Date, JSON, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ForecastRunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ForecastRunType(str, enum.Enum):
    BASELINE = "baseline"
    DAILY_UPDATE = "daily_update"
    MANUAL = "manual"


class SchedulePlanStatus(str, enum.Enum):
    DRAFT = "draft"
    FINAL = "final"
    ADJUSTED = "adjusted"
    CANCELLED = "cancelled"


class SchedulePlanKind(str, enum.Enum):
    BASELINE = "baseline"
    ADJUSTMENT = "adjustment"


class SectorOperationalParameters(Base):
    """
    Parâmetros operacionais por setor (versionável por semana).
    Substitui/complementa GovernanceRules para configuração específica por setor.
    """
    __tablename__ = "sector_operational_parameters"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    
    target_utilization_pct = Column(Float, default=85.0)
    buffer_pct = Column(Float, default=10.0)
    
    cleaning_time_vago_sujo_min = Column(Float, default=25.0)
    cleaning_time_estadia_min = Column(Float, default=10.0)
    
    safety_pp_by_weekday = Column(JSON, default={
        "SEGUNDA-FEIRA": 0.0,
        "TERÇA-FEIRA": 0.0,
        "QUARTA-FEIRA": 0.0,
        "QUINTA-FEIRA": 0.0,
        "SEXTA-FEIRA": 2.0,
        "SÁBADO": 3.0,
        "DOMINGO": 2.0
    })
    
    shift_templates = Column(JSON, default=[
        {"name": "Manhã", "start_time": "07:00", "end_time": "15:00", "hours": 8.0},
        {"name": "Tarde", "start_time": "14:00", "end_time": "22:00", "hours": 8.0}
    ])
    
    lunch_rules = Column(JSON, default={
        "duration_min": 60,
        "window_start": "11:00",
        "window_end": "14:00",
        "min_hours_before": 3.0,
        "max_hours_before": 5.0
    })
    
    constraints_json = Column(JSON, default={
        "min_hours_per_day": 4.0,
        "max_hours_per_day": 8.0,
        "min_rest_between_shifts": 11.0,
        "max_consecutive_days": 6
    })
    
    total_rooms = Column(Integer, default=100)
    
    replan_threshold_pp = Column(Float, default=5.0)
    
    active_from = Column(Date, nullable=True)
    week_start = Column(Date, nullable=True, index=True)
    is_current = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector")


class ForecastRun(Base):
    """
    Execução de forecast semanal.
    - BASELINE: gerado na sexta-feira, pode ser travado (locked)
    - DAILY_UPDATE: atualização diária para comparar com baseline
    - MANUAL: rodada manual sob demanda
    """
    __tablename__ = "forecast_runs"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    
    run_type = Column(SQLEnum(ForecastRunType), default=ForecastRunType.MANUAL, nullable=False, index=True)
    
    run_date = Column(Date, nullable=False, index=True)
    run_datetime = Column(DateTime(timezone=True), server_default=func.now())
    horizon_start = Column(Date, nullable=False, index=True)
    horizon_end = Column(Date, nullable=False)
    
    as_of_datetime = Column(DateTime(timezone=True), nullable=True)
    
    status = Column(SQLEnum(ForecastRunStatus), default=ForecastRunStatus.RUNNING)
    
    is_locked = Column(Boolean, default=False, index=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    
    method_version = Column(String(20), default="1.0.0")
    bias_method = Column(String(20), default="EWMA")
    bias_params_json = Column(JSON, default={"alpha": 0.2})
    params_json = Column(JSON, default={})
    
    superseded_by_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=True)
    
    notes = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_by = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector")
    daily_forecasts = relationship("ForecastDaily", back_populates="forecast_run", cascade="all, delete-orphan")
    superseded_by = relationship("ForecastRun", remote_side=[id], foreign_keys=[superseded_by_run_id])


class ForecastDaily(Base):
    """
    Projeção ajustada de ocupação por dia.
    occ_adj = clamp(occ_raw + bias_pp + safety_pp, 0, 100)
    """
    __tablename__ = "forecast_daily"

    id = Column(Integer, primary_key=True, index=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=False, index=True)
    
    target_date = Column(Date, nullable=False, index=True)
    weekday_pt = Column(String(20), nullable=False)
    
    occ_raw = Column(Float, nullable=True)
    bias_pp_used = Column(Float, default=0.0)
    safety_pp_used = Column(Float, default=0.0)
    occ_adj = Column(Float, nullable=True)
    
    data_source = Column(String(50), default="occupancy_latest")
    source_generated_at = Column(DateTime(timezone=True), nullable=True)
    source_snapshot_id = Column(Integer, ForeignKey("occupancy_snapshots.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    forecast_run = relationship("ForecastRun", back_populates="daily_forecasts")


class HousekeepingDemandDaily(Base):
    """
    Demanda diária de limpeza calculada a partir do forecast.
    """
    __tablename__ = "housekeeping_demand_daily"

    id = Column(Integer, primary_key=True, index=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=False, index=True)
    
    target_date = Column(Date, nullable=False, index=True)
    weekday_pt = Column(String(20), nullable=False)
    
    occupied_rooms = Column(Integer, default=0)
    departures_count = Column(Integer, default=0)
    arrivals_count = Column(Integer, default=0)
    stayovers_estimated = Column(Integer, default=0)
    
    minutes_required_raw = Column(Float, default=0.0)
    minutes_required_buffered = Column(Float, default=0.0)
    hours_productive_required = Column(Float, default=0.0)
    hours_total_required = Column(Float, default=0.0)
    
    headcount_required = Column(Float, default=0.0)
    headcount_rounded = Column(Integer, default=0)
    
    calculation_breakdown = Column(JSON, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    forecast_run = relationship("ForecastRun")


class HousekeepingSchedulePlan(Base):
    """
    Plano de escala semanal para governança.
    
    PROMPT 3: Suporta plan_kind para diferenciar escala BASELINE (original)
    de ADJUSTMENT (ajustes diários baseados em daily updates).
    """
    __tablename__ = "housekeeping_schedule_plans"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=True, index=True)
    
    week_start = Column(Date, nullable=False, index=True)
    week_end = Column(Date, nullable=False)
    
    plan_kind = Column(SQLEnum(SchedulePlanKind), default=SchedulePlanKind.BASELINE, nullable=False)
    baseline_plan_id = Column(Integer, ForeignKey("housekeeping_schedule_plans.id"), nullable=True)
    
    status = Column(SQLEnum(SchedulePlanStatus), default=SchedulePlanStatus.DRAFT)
    
    total_headcount_planned = Column(Integer, default=0)
    total_hours_planned = Column(Float, default=0.0)
    
    summary_json = Column(JSON, default={})
    
    coverage_by_hour = Column(JSON, default={})
    
    validations_json = Column(JSON, default=[])
    
    version = Column(Integer, default=1)
    parent_plan_id = Column(Integer, ForeignKey("housekeeping_schedule_plans.id"), nullable=True)
    
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector")
    forecast_run = relationship("ForecastRun")
    parent_plan = relationship("HousekeepingSchedulePlan", remote_side=[id], foreign_keys=[parent_plan_id])
    baseline_plan = relationship("HousekeepingSchedulePlan", remote_side=[id], foreign_keys=[baseline_plan_id])
    shift_slots = relationship("ShiftSlot", back_populates="schedule_plan", cascade="all, delete-orphan")


class ShiftSlot(Base):
    """
    Vaga de turno na escala (pode ser atribuída a um colaborador ou ficar aberta).
    """
    __tablename__ = "shift_slots"

    id = Column(Integer, primary_key=True, index=True)
    schedule_plan_id = Column(Integer, ForeignKey("housekeeping_schedule_plans.id"), nullable=False, index=True)
    
    target_date = Column(Date, nullable=False, index=True)
    weekday_pt = Column(String(20), nullable=False)
    
    template_name = Column(String(50), nullable=False)
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)
    
    lunch_start = Column(String(5), nullable=True)
    lunch_end = Column(String(5), nullable=True)
    
    hours_worked = Column(Float, default=8.0)
    
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    is_assigned = Column(Boolean, default=False)
    
    notes = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    schedule_plan = relationship("HousekeepingSchedulePlan", back_populates="shift_slots")
    employee = relationship("Employee")


class TurnoverRateStats(Base):
    """
    Estatísticas de turnover por dia da semana.
    
    PROMPT 4: Calcula turnover_rate = checkouts_reais / rooms_occupied_real
    por dia da semana usando histórico do Data Lake.
    """
    __tablename__ = "turnover_rate_stats"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True, index=True)
    
    weekday_pt = Column(String(20), nullable=False, index=True)
    weekday_num = Column(Integer, nullable=False)
    
    rate = Column(Float, nullable=False)
    n = Column(Integer, default=0)
    std = Column(Float, nullable=True)
    min_rate = Column(Float, nullable=True)
    max_rate = Column(Float, nullable=True)
    
    method = Column(String(20), default="EWMA")
    alpha = Column(Float, default=0.2)
    params_json = Column(JSON, default={})
    
    fallback_used = Column(Boolean, default=False)
    fallback_reason = Column(String(200), nullable=True)
    
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sector = relationship("Sector")


class ScheduleOverrideLog(Base):
    """
    Log de overrides manuais em escalas.
    
    PROMPT 4: Auditoria de alterações manuais em headcount ou distribuição.
    """
    __tablename__ = "schedule_override_logs"

    id = Column(Integer, primary_key=True, index=True)
    schedule_plan_id = Column(Integer, ForeignKey("housekeeping_schedule_plans.id"), nullable=False, index=True)
    
    override_type = Column(String(50), nullable=False)
    target_date = Column(Date, nullable=True)
    
    original_value = Column(JSON, default={})
    new_value = Column(JSON, default={})
    
    reason = Column(Text, nullable=True)
    override_by = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    schedule_plan = relationship("HousekeepingSchedulePlan")


class ReplanSuggestion(Base):
    """
    Sugestão de ajuste diário gerada pelo sistema.
    """
    __tablename__ = "replan_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    schedule_plan_id = Column(Integer, ForeignKey("housekeeping_schedule_plans.id"), nullable=False, index=True)
    
    target_date = Column(Date, nullable=False, index=True)
    
    suggestion_type = Column(String(50), nullable=False)
    
    original_value = Column(Float, nullable=True)
    suggested_value = Column(Float, nullable=True)
    delta = Column(Float, nullable=True)
    
    reason = Column(Text, nullable=True)
    justification_json = Column(JSON, default={})
    
    priority = Column(String(20), default="medium")
    
    is_accepted = Column(Boolean, nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    accepted_by = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    schedule_plan = relationship("HousekeepingSchedulePlan")


class ForecastRunSectorSnapshot(Base):
    """
    PROMPT 8: Snapshot de regras e parâmetros por setor no momento do forecast.
    
    Preserva o estado das regras/parâmetros usados na geração do forecast
    para permitir comparações precisas entre baseline e ajustes diários.
    """
    __tablename__ = "forecast_run_sector_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    forecast_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=False, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    
    occ_projection_by_day_json = Column(JSON, default={})
    
    labor_rules_snapshot_json = Column(JSON, default={})
    operational_rules_snapshot_json = Column(JSON, default={})
    weekly_params_snapshot_json = Column(JSON, default={})
    
    sector_config_json = Column(JSON, default={})
    
    snapshot_version = Column(String(20), default="1.0.0")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    forecast_run = relationship("ForecastRun", backref="sector_snapshots")
    sector = relationship("Sector")


class AgendaGenerationStatus(str, enum.Enum):
    DRAFT = "draft"
    GENERATED = "generated"
    APPROVED = "approved"
    CONFLICT = "conflict"


class EmployeeDailyAgenda(Base):
    """
    Agenda diária de um colaborador com atividades distribuídas.
    Vinculada a um ShiftSlot (colaborador+dia+turno).
    """
    __tablename__ = "employee_daily_agendas"

    id = Column(Integer, primary_key=True, index=True)
    schedule_plan_id = Column(Integer, ForeignKey("housekeeping_schedule_plans.id"), nullable=False, index=True)
    shift_slot_id = Column(Integer, ForeignKey("shift_slots.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    
    target_date = Column(Date, nullable=False, index=True)
    
    total_minutes_allocated = Column(Integer, default=0)
    total_minutes_available = Column(Integer, default=0)
    
    shift_start = Column(String(5), nullable=True)
    shift_end = Column(String(5), nullable=True)
    
    status = Column(SQLEnum(AgendaGenerationStatus), default=AgendaGenerationStatus.DRAFT)
    
    has_conflict = Column(Boolean, default=False)
    conflict_reason = Column(String(500), nullable=True)
    
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    schedule_plan = relationship("HousekeepingSchedulePlan")
    shift_slot = relationship("ShiftSlot")
    employee = relationship("Employee")
    sector = relationship("Sector")
    items = relationship("EmployeeDailyAgendaItem", back_populates="agenda", cascade="all, delete-orphan", order_by="EmployeeDailyAgendaItem.order")


class EmployeeDailyAgendaItem(Base):
    """
    Item individual da agenda: uma atividade com duração e ordem.
    """
    __tablename__ = "employee_daily_agenda_items"

    id = Column(Integer, primary_key=True, index=True)
    agenda_id = Column(Integer, ForeignKey("employee_daily_agendas.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_id = Column(Integer, ForeignKey("governance_activities.id"), nullable=False, index=True)
    
    order = Column(Integer, nullable=False)
    minutes = Column(Integer, nullable=False)
    quantity = Column(Float, default=1.0)
    
    classification = Column(String(50), nullable=False)
    
    is_pending = Column(Boolean, default=False)
    pending_reason = Column(String(200), nullable=True)
    
    notes = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    agenda = relationship("EmployeeDailyAgenda", back_populates="items")
    activity = relationship("GovernanceActivity")
