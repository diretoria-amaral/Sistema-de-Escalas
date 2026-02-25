from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session
from typing import Optional, List, Dict
from datetime import date, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models.governance_module import (
    SectorOperationalParameters, ForecastRun, HousekeepingSchedulePlan,
    SchedulePlanStatus, ScheduleOverrideLog, ShiftSlot
)
from app.models.governance_activity import GovernanceActivity
from app.models.activity_program import ActivityProgramWeek, ActivityProgramItem
from app.models.sector import Sector
from app.services.governance_forecast_service import GovernanceForecastService
from app.services.governance_demand_service import GovernanceDemandService
from app.services.governance_schedule_generator import GovernanceScheduleGenerator
from app.services.daily_replan_service import DailyReplanService
from app.services.turnover_stats_service import TurnoverStatsService
from app.services.recurrence_expansion_service import (
    expand_recurring_activities,
    get_recurring_activities_summary
)
from app.services.schedule_assignment_service import ScheduleAssignmentService
from app.services.agenda_generation_service import AgendaGenerationService

router = APIRouter(prefix="/api/governance", tags=["Governance"])


def _calculate_iso_week(target_date: date) -> int:
    """Calcula o número da semana ISO (1-52)."""
    return target_date.isocalendar()[1]


def _get_week_monday(target_date: date) -> date:
    """Retorna a segunda-feira da semana da data especificada."""
    days_since_monday = target_date.weekday()
    return target_date - timedelta(days=days_since_monday)


class ParametersCreate(BaseModel):
    sector_id: int
    target_utilization_pct: float = 85.0
    buffer_pct: float = 10.0
    cleaning_time_vago_sujo_min: float = 25.0
    cleaning_time_estadia_min: float = 10.0
    safety_pp_by_weekday: dict = None
    shift_templates: list = None
    lunch_rules: dict = None
    constraints_json: dict = None
    total_rooms: int = 100
    replan_threshold_pp: float = 5.0


class ParametersUpdate(BaseModel):
    target_utilization_pct: Optional[float] = None
    buffer_pct: Optional[float] = None
    cleaning_time_vago_sujo_min: Optional[float] = None
    cleaning_time_estadia_min: Optional[float] = None
    safety_pp_by_weekday: Optional[dict] = None
    shift_templates: Optional[list] = None
    lunch_rules: Optional[dict] = None
    constraints_json: Optional[dict] = None
    total_rooms: Optional[int] = None
    replan_threshold_pp: Optional[float] = None


@router.get("/parameters")
def get_parameters(
    sector_id: int = Query(..., description="ID do setor"),
    db: Session = Depends(get_db)
):
    """Obtém parâmetros operacionais vigentes do setor."""
    params = db.query(SectorOperationalParameters).filter(
        SectorOperationalParameters.sector_id == sector_id,
        SectorOperationalParameters.is_current == True
    ).first()
    
    if not params:
        return {"exists": False, "message": "Parâmetros não configurados para este setor"}
    
    return {
        "exists": True,
        "id": params.id,
        "sector_id": params.sector_id,
        "target_utilization_pct": params.target_utilization_pct,
        "buffer_pct": params.buffer_pct,
        "cleaning_time_vago_sujo_min": params.cleaning_time_vago_sujo_min,
        "cleaning_time_estadia_min": params.cleaning_time_estadia_min,
        "safety_pp_by_weekday": params.safety_pp_by_weekday,
        "shift_templates": params.shift_templates,
        "lunch_rules": params.lunch_rules,
        "constraints_json": params.constraints_json,
        "total_rooms": params.total_rooms,
        "replan_threshold_pp": params.replan_threshold_pp,
        "is_current": params.is_current,
        "created_at": params.created_at.isoformat() if params.created_at else None,
        "updated_at": params.updated_at.isoformat() if params.updated_at else None
    }


@router.post("/parameters")
def create_parameters(data: ParametersCreate, db: Session = Depends(get_db)):
    """Cria novos parâmetros operacionais para o setor."""
    existing = db.query(SectorOperationalParameters).filter(
        SectorOperationalParameters.sector_id == data.sector_id,
        SectorOperationalParameters.is_current == True
    ).first()
    
    if existing:
        existing.is_current = False
    
    params = SectorOperationalParameters(
        sector_id=data.sector_id,
        target_utilization_pct=data.target_utilization_pct,
        buffer_pct=data.buffer_pct,
        cleaning_time_vago_sujo_min=data.cleaning_time_vago_sujo_min,
        cleaning_time_estadia_min=data.cleaning_time_estadia_min,
        safety_pp_by_weekday=data.safety_pp_by_weekday or {
            "SEGUNDA-FEIRA": 0.0,
            "TERÇA-FEIRA": 0.0,
            "QUARTA-FEIRA": 0.0,
            "QUINTA-FEIRA": 0.0,
            "SEXTA-FEIRA": 2.0,
            "SÁBADO": 3.0,
            "DOMINGO": 2.0
        },
        shift_templates=data.shift_templates or [
            {"name": "Manhã", "start_time": "07:00", "end_time": "15:00", "hours": 8.0},
            {"name": "Tarde", "start_time": "14:00", "end_time": "22:00", "hours": 8.0}
        ],
        lunch_rules=data.lunch_rules or {
            "duration_min": 60,
            "window_start": "11:00",
            "window_end": "14:00",
            "min_hours_before": 3.0,
            "max_hours_before": 5.0
        },
        constraints_json=data.constraints_json,
        total_rooms=data.total_rooms,
        replan_threshold_pp=data.replan_threshold_pp,
        is_current=True
    )
    
    db.add(params)
    db.commit()
    db.refresh(params)
    
    return {"success": True, "id": params.id, "message": "Parâmetros criados com sucesso"}


@router.put("/parameters/{params_id}")
def update_parameters(
    params_id: int,
    data: ParametersUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza parâmetros operacionais existentes."""
    params = db.query(SectorOperationalParameters).filter(
        SectorOperationalParameters.id == params_id
    ).first()
    
    if not params:
        raise HTTPException(status_code=404, detail="Parâmetros não encontrados")
    
    update_data = data.dict(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(params, key, value)
    
    db.commit()
    
    return {"success": True, "id": params_id, "message": "Parâmetros atualizados"}


class ForecastRunRequest(BaseModel):
    sector_id: int
    week_start: str
    activity_ids: List[int]
    run_date: Optional[str] = None


@router.get("/forecast/available-activities")
def get_available_activities(
    sector_id: int = Query(..., description="ID do setor"),
    week_start: str = Query(..., description="Data inicial da semana (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Lista atividades disponíveis para o Forecast Run.
    
    Retorna atividades:
    - Vinculadas ao setor selecionado
    - Ativas no cadastro
    - Com programação válida para a semana (se existir)
    
    Validações:
    - Setor deve existir
    - Semana deve estar no formato ISO (1-52)
    """
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(
            status_code=404, 
            detail=f"Setor {sector_id} não encontrado. Verifique o cadastro de setores."
        )
    
    try:
        week_start_parsed = date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail="Data inválida. Use o formato YYYY-MM-DD."
        )
    
    week_monday = _get_week_monday(week_start_parsed)
    iso_week = _calculate_iso_week(week_monday)
    
    activities = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == sector_id,
        GovernanceActivity.is_active == True
    ).order_by(GovernanceActivity.name).all()
    
    if not activities:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhuma atividade cadastrada para o setor '{sector.name}'. "
                   f"Cadastre atividades em Cadastros > Atividades antes de gerar o Forecast."
        )
    
    program_week = db.query(ActivityProgramWeek).filter(
        ActivityProgramWeek.sector_id == sector_id,
        ActivityProgramWeek.week_start == week_monday
    ).first()
    
    programmed_activity_ids = set()
    if program_week:
        program_items = db.query(ActivityProgramItem).filter(
            ActivityProgramItem.program_week_id == program_week.id
        ).all()
        programmed_activity_ids = {item.activity_id for item in program_items}
    
    result = {
        "sector": {"id": sector.id, "name": sector.name},
        "week": {
            "start": week_monday.isoformat(),
            "end": (week_monday + timedelta(days=6)).isoformat(),
            "iso_week": iso_week
        },
        "has_programming": program_week is not None,
        "programming_status": program_week.status.value if program_week else None,
        "activities": []
    }
    
    for activity in activities:
        result["activities"].append({
            "id": activity.id,
            "name": activity.name,
            "code": activity.code,
            "average_time_minutes": activity.average_time_minutes,
            "is_programmed": activity.id in programmed_activity_ids,
            "sector_id": activity.sector_id
        })
    
    return result


@router.post("/forecast/run")
def run_forecast(
    request: ForecastRunRequest = Body(...),
    db: Session = Depends(get_db)
):
    """
    Executa geração de Forecast Run semanal.
    
    Validações obrigatórias:
    1. Setor deve estar definido e existir
    2. Semana deve estar definida (formato YYYY-MM-DD)
    3. Atividades devem ser explicitamente selecionadas
    4. Atividades devem pertencer ao setor selecionado
    5. Atividades devem estar ativas
    
    Erros explicativos são retornados para cada validação falhada.
    """
    errors = []
    
    sector = db.query(Sector).filter(Sector.id == request.sector_id).first()
    if not sector:
        errors.append(f"Setor {request.sector_id} não encontrado.")
    
    try:
        week_start_parsed = date.fromisoformat(request.week_start)
        week_monday = _get_week_monday(week_start_parsed)
        iso_week = _calculate_iso_week(week_monday)
        
        if iso_week < 1 or iso_week > 53:
            errors.append(f"Semana ISO inválida: {iso_week}. Deve estar entre 1 e 53.")
    except ValueError:
        errors.append("Data de início da semana inválida. Use o formato YYYY-MM-DD.")
        week_monday = None
        iso_week = None
    
    if not request.activity_ids or len(request.activity_ids) == 0:
        errors.append(
            "Nenhuma atividade selecionada. "
            "Selecione pelo menos uma atividade para gerar o Forecast."
        )
    else:
        valid_activities = db.query(GovernanceActivity).filter(
            GovernanceActivity.id.in_(request.activity_ids),
            GovernanceActivity.sector_id == request.sector_id,
            GovernanceActivity.is_active == True
        ).all()
        
        valid_activity_ids = {a.id for a in valid_activities}
        invalid_ids = [aid for aid in request.activity_ids if aid not in valid_activity_ids]
        
        if invalid_ids:
            errors.append(
                f"Atividades inválidas para o setor: {invalid_ids}. "
                f"Verifique se as atividades pertencem ao setor e estão ativas."
            )
        
        if len(valid_activities) == 0 and len(request.activity_ids) > 0:
            errors.append(
                "Nenhuma das atividades selecionadas é válida para este setor. "
                "Verifique o vínculo Setor → Atividades."
            )
    
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    
    run_date_parsed = date.fromisoformat(request.run_date) if request.run_date else date.today()
    
    service = GovernanceForecastService(db)
    result = service.generate_weekly_forecast(
        sector_id=request.sector_id,
        run_date=run_date_parsed,
        week_start=week_monday,
        activity_ids=list(valid_activity_ids)
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    result["validated_activities"] = [
        {"id": a.id, "name": a.name, "code": a.code}
        for a in valid_activities
    ]
    result["iso_week"] = iso_week
    result["week_start"] = week_monday.isoformat() if week_monday else None
    
    return result


@router.post("/forecast/run-legacy")
def run_forecast_legacy(
    sector_id: int = Query(..., description="ID do setor"),
    run_date: Optional[str] = Query(None, description="Data de execução (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    [LEGADO] Executa geração de forecast semanal sem validação de atividades.
    Mantido para compatibilidade. Use POST /forecast/run para o novo fluxo.
    """
    run_date_parsed = date.fromisoformat(run_date) if run_date else date.today()
    
    service = GovernanceForecastService(db)
    result = service.generate_weekly_forecast(
        sector_id=sector_id,
        run_date=run_date_parsed
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/forecast/runs")
def list_forecast_runs(
    sector_id: int = Query(..., description="ID do setor"),
    limit: int = Query(10, description="Limite de registros"),
    db: Session = Depends(get_db)
):
    """Lista execuções de forecast do setor."""
    service = GovernanceForecastService(db)
    return service.list_forecast_runs(sector_id=sector_id, limit=limit)


@router.get("/forecast/{run_id}")
def get_forecast_run(run_id: int, db: Session = Depends(get_db)):
    """Obtém detalhes de uma execução de forecast."""
    service = GovernanceForecastService(db)
    result = service.get_forecast_run(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="ForecastRun não encontrado")
    
    return result


@router.post("/demand/compute")
def compute_demand(
    forecast_run_id: int = Query(..., description="ID do ForecastRun"),
    total_rooms: Optional[int] = Query(None, description="Total de quartos (override)"),
    db: Session = Depends(get_db)
):
    """Calcula demanda de limpeza a partir do forecast."""
    service = GovernanceDemandService(db)
    result = service.compute_housekeeping_demand(
        forecast_run_id=forecast_run_id,
        total_rooms=total_rooms
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/demand/{forecast_run_id}")
def get_demand(forecast_run_id: int, db: Session = Depends(get_db)):
    """Obtém demanda calculada para um forecast run."""
    service = GovernanceDemandService(db)
    return service.get_demand_by_forecast_run(forecast_run_id)


@router.post("/schedule/generate")
def generate_schedule(
    week_start: str = Query(..., description="Início da semana (YYYY-MM-DD)"),
    sector_id: int = Query(..., description="ID do setor"),
    forecast_run_id: Optional[int] = Query(None, description="ID do ForecastRun (opcional)"),
    db: Session = Depends(get_db)
):
    """Gera escala de governança para a semana."""
    week_start_parsed = date.fromisoformat(week_start)
    
    service = GovernanceScheduleGenerator(db)
    result = service.generate_housekeeping_schedule(
        week_start=week_start_parsed,
        sector_id=sector_id,
        forecast_run_id=forecast_run_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/schedule/plans")
def list_schedule_plans(
    sector_id: int = Query(..., description="ID do setor"),
    limit: int = Query(10, description="Limite de registros"),
    db: Session = Depends(get_db)
):
    """Lista planos de escala do setor."""
    service = GovernanceScheduleGenerator(db)
    return service.list_schedule_plans(sector_id=sector_id, limit=limit)


@router.get("/schedule/{plan_id}")
def get_schedule_plan(plan_id: int, db: Session = Depends(get_db)):
    """Obtém detalhes de um plano de escala."""
    service = GovernanceScheduleGenerator(db)
    result = service.get_schedule_plan(plan_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Plano de escala não encontrado")
    
    return result


@router.put("/schedule/{plan_id}/status")
def update_schedule_status(
    plan_id: int,
    status: str = Query(..., description="Novo status (draft, final, adjusted, cancelled)"),
    db: Session = Depends(get_db)
):
    """Atualiza status do plano de escala."""
    plan = db.query(HousekeepingSchedulePlan).filter(
        HousekeepingSchedulePlan.id == plan_id
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    try:
        plan.status = SchedulePlanStatus(status)
        db.commit()
        return {"success": True, "status": status}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Status inválido: {status}")


@router.post("/replan/suggest")
def suggest_adjustments(
    date_today: Optional[str] = Query(None, description="Data de hoje (YYYY-MM-DD)"),
    sector_id: int = Query(..., description="ID do setor"),
    db: Session = Depends(get_db)
):
    """Sugere ajustes diários baseado em novos dados."""
    date_parsed = date.fromisoformat(date_today) if date_today else date.today()
    
    service = DailyReplanService(db)
    result = service.suggest_daily_adjustments(
        date_today=date_parsed,
        sector_id=sector_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/replan/suggestions")
def get_pending_suggestions(
    sector_id: int = Query(..., description="ID do setor"),
    db: Session = Depends(get_db)
):
    """Lista sugestões pendentes do setor."""
    service = DailyReplanService(db)
    return service.get_pending_suggestions(sector_id)


@router.post("/replan/suggestions/{suggestion_id}/accept")
def accept_suggestion(
    suggestion_id: int,
    accepted_by: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Aceita uma sugestão de ajuste."""
    service = DailyReplanService(db)
    return service.accept_suggestion(suggestion_id, accepted_by)


@router.post("/replan/suggestions/{suggestion_id}/reject")
def reject_suggestion(
    suggestion_id: int,
    rejected_by: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Rejeita uma sugestão de ajuste."""
    service = DailyReplanService(db)
    return service.reject_suggestion(suggestion_id, rejected_by)


@router.post("/schedule/generate-adjustment")
def generate_adjustment_schedule(
    week_start: str = Query(..., description="Início da semana (YYYY-MM-DD)"),
    sector_id: int = Query(..., description="ID do setor"),
    forecast_run_id: int = Query(..., description="ID do ForecastRun (daily update)"),
    baseline_plan_id: int = Query(..., description="ID do plano baseline"),
    db: Session = Depends(get_db)
):
    """
    Gera escala ADJUSTMENT baseada em um daily update, vinculada a um baseline.
    PROMPT 3: Mantém rastreabilidade baseline → adjustment.
    """
    week_start_parsed = date.fromisoformat(week_start)
    
    service = GovernanceScheduleGenerator(db)
    result = service.generate_adjustment_schedule(
        week_start=week_start_parsed,
        sector_id=sector_id,
        forecast_run_id=forecast_run_id,
        baseline_plan_id=baseline_plan_id
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/schedule/{plan_id}/validate")
def validate_schedule(plan_id: int, db: Session = Depends(get_db)):
    """
    Valida escala contra regras legais de trabalho intermitente.
    PROMPT 3: Retorna erros e warnings de validação.
    """
    service = GovernanceScheduleGenerator(db)
    result = service.validate_schedule_legal(plan_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/schedule/{plan_id}/convocations")
def preview_convocations(plan_id: int, db: Session = Depends(get_db)):
    """
    Gera prévia de convocações por colaborador com status de validação.
    PROMPT 3: Lista por colaboradora com dias, horários, status ok/warning/erro.
    """
    service = GovernanceScheduleGenerator(db)
    result = service.preview_convocations(plan_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


class ScheduleAssignRequest(BaseModel):
    """Request para alocar colaboradores aos turnos da escala."""
    sector_id: int
    week_start: str
    schedule_plan_id: int


@router.post("/schedule/assign")
def assign_employees_to_schedule(
    request: ScheduleAssignRequest,
    db: Session = Depends(get_db)
):
    """
    Aloca colaboradores aos ShiftSlots de uma escala.
    
    Aplica algoritmo de scoring respeitando hierarquia de regras:
    LABOR > OPERATIONAL > CALCULATION
    
    Retorna:
    - slots preenchidos com employee_id
    - lista de convocados por semana
    - métricas por colaborador (horas, dias, turnos, folgas)
    - warnings/violations listados
    - trace de decisões
    """
    try:
        week_start_parsed = date.fromisoformat(request.week_start)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de data inválido. Use YYYY-MM-DD."
        )
    
    service = ScheduleAssignmentService(db)
    result = service.assign_employees_to_schedule(
        sector_id=request.sector_id,
        week_start=week_start_parsed,
        schedule_plan_id=request.schedule_plan_id
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Erro ao alocar colaboradores")
        )
    
    return result


class AgendaGenerateRequest(BaseModel):
    """Request para gerar agendas individuais."""
    sector_id: int
    week_start: str
    schedule_plan_id: int


@router.post("/agenda/generate")
def generate_agendas(
    request: AgendaGenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Gera agendas individuais para cada colaborador escalado.
    
    Distribui atividades programadas (Calculadas, Recorrentes, Eventuais)
    respeitando capacidades e alternância de tarefas.
    
    Retorna:
    - agendas por colaborador/dia
    - atividades distribuídas com duração
    - conflitos (demanda > capacidade)
    - pendências (eventuais sem agendamento)
    - trace de decisões
    """
    try:
        week_start_parsed = date.fromisoformat(request.week_start)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de data inválido. Use YYYY-MM-DD."
        )
    
    service = AgendaGenerationService(db)
    result = service.generate_agendas(
        sector_id=request.sector_id,
        week_start=week_start_parsed,
        schedule_plan_id=request.schedule_plan_id
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Erro ao gerar agendas")
        )
    
    return result


@router.get("/agenda")
def get_agendas(
    sector_id: int,
    week_start: str,
    db: Session = Depends(get_db)
):
    """
    Retorna agendas geradas para a semana.
    
    Parâmetros:
    - sector_id: ID do setor
    - week_start: Data de início da semana (YYYY-MM-DD)
    
    Retorna:
    - Lista de agendas por colaborador/dia
    - Atividades com duração e ordem
    - Utilização percentual
    """
    try:
        week_start_parsed = date.fromisoformat(week_start)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Formato de data inválido. Use YYYY-MM-DD."
        )
    
    service = AgendaGenerationService(db)
    result = service.get_agendas(
        sector_id=sector_id,
        week_start=week_start_parsed
    )
    
    return result


class ScheduleOverrideRequest(BaseModel):
    override_type: str
    target_date: Optional[str] = None
    new_value: Dict
    reason: Optional[str] = None
    override_by: Optional[str] = None


@router.post("/schedule/{plan_id}/override")
def override_schedule(
    plan_id: int,
    data: ScheduleOverrideRequest,
    db: Session = Depends(get_db)
):
    """
    Aplica override manual em uma escala.
    
    PROMPT 4: Permite alterar headcount ou distribuição de um dia específico.
    Registra auditoria em schedule_override_logs APÓS sucesso da operação.
    """
    plan = db.query(HousekeepingSchedulePlan).filter(
        HousekeepingSchedulePlan.id == plan_id
    ).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    
    target_date_parsed = date.fromisoformat(data.target_date) if data.target_date else None
    
    original_value = {}
    slots_modified = False
    
    if data.override_type == "headcount" and target_date_parsed:
        current_slots = db.query(ShiftSlot).filter(
            ShiftSlot.schedule_plan_id == plan_id,
            ShiftSlot.target_date == target_date_parsed
        ).order_by(ShiftSlot.start_time).all()
        
        current_count = len(current_slots)
        original_value = {"headcount": current_count}
        new_headcount = data.new_value.get("headcount", 0)
        
        if new_headcount == current_count:
            return {"success": True, "message": "Nenhuma alteração necessária"}
        
        params = db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == plan.sector_id,
            SectorOperationalParameters.is_current == True
        ).first()
        
        shift_templates = params.shift_templates if params else [
            {"name": "Manhã", "start_time": "07:00", "end_time": "15:00", "hours": 8.0}
        ]
        default_template = shift_templates[0] if shift_templates else {}
        
        weekday_map = {
            0: "SEGUNDA-FEIRA", 1: "TERÇA-FEIRA", 2: "QUARTA-FEIRA",
            3: "QUINTA-FEIRA", 4: "SEXTA-FEIRA", 5: "SÁBADO", 6: "DOMINGO"
        }
        weekday_pt = weekday_map.get(target_date_parsed.weekday(), "SEGUNDA-FEIRA")
        
        try:
            if new_headcount > current_count:
                template = current_slots[0] if current_slots else None
                for i in range(new_headcount - current_count):
                    new_slot = ShiftSlot(
                        schedule_plan_id=plan_id,
                        target_date=target_date_parsed,
                        weekday_pt=template.weekday_pt if template else weekday_pt,
                        template_name=template.template_name if template else default_template.get("name", "Manhã"),
                        start_time=template.start_time if template else default_template.get("start_time", "07:00"),
                        end_time=template.end_time if template else default_template.get("end_time", "15:00"),
                        lunch_start=template.lunch_start if template else None,
                        lunch_end=template.lunch_end if template else None,
                        hours_worked=template.hours_worked if template else default_template.get("hours", 8.0),
                        is_assigned=False
                    )
                    db.add(new_slot)
            elif new_headcount < current_count:
                unassigned_slots = [s for s in current_slots if not s.is_assigned]
                assigned_slots = [s for s in current_slots if s.is_assigned]
                slots_to_remove = current_count - new_headcount
                
                remove_from_unassigned = min(len(unassigned_slots), slots_to_remove)
                for slot in unassigned_slots[:remove_from_unassigned]:
                    db.delete(slot)
                
                remaining = slots_to_remove - remove_from_unassigned
                if remaining > 0:
                    for slot in assigned_slots[:remaining]:
                        db.delete(slot)
            
            slots_modified = True
            
            all_slots = db.query(ShiftSlot).filter(
                ShiftSlot.schedule_plan_id == plan_id
            ).all()
            plan.total_headcount_planned = len(all_slots)
            plan.total_hours_planned = sum(s.hours_worked or 8.0 for s in all_slots)
            plan.status = SchedulePlanStatus.ADJUSTED
            
            db.flush()
            
            log = ScheduleOverrideLog(
                schedule_plan_id=plan_id,
                override_type=data.override_type,
                target_date=target_date_parsed,
                original_value=original_value,
                new_value=data.new_value,
                reason=data.reason,
                override_by=data.override_by
            )
            db.add(log)
            db.flush()
            
            db.commit()
            
            final_slots_count = db.query(ShiftSlot).filter(
                ShiftSlot.schedule_plan_id == plan_id,
                ShiftSlot.target_date == target_date_parsed
            ).count()
            
            if final_slots_count != new_headcount:
                raise HTTPException(
                    status_code=500, 
                    detail=f"Inconsistência: esperado {new_headcount} slots, encontrados {final_slots_count}"
                )
            
            return {
                "success": True,
                "override_id": log.id,
                "message": f"Override aplicado: headcount {current_count} -> {new_headcount}",
                "new_total_headcount": plan.total_headcount_planned,
                "new_total_hours": plan.total_hours_planned
            }
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Erro ao aplicar override: {str(e)}")
    
    return {"success": False, "message": "Tipo de override não suportado ou dados inválidos"}


@router.get("/schedule/{plan_id}/overrides")
def get_schedule_overrides(plan_id: int, db: Session = Depends(get_db)):
    """Lista overrides aplicados em um plano de escala."""
    logs = db.query(ScheduleOverrideLog).filter(
        ScheduleOverrideLog.schedule_plan_id == plan_id
    ).order_by(ScheduleOverrideLog.created_at.desc()).all()
    
    return [
        {
            "id": log.id,
            "override_type": log.override_type,
            "target_date": log.target_date.isoformat() if log.target_date else None,
            "original_value": log.original_value,
            "new_value": log.new_value,
            "reason": log.reason,
            "override_by": log.override_by,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in logs
    ]


@router.post("/turnover/compute")
def compute_turnover_stats(
    sector_id: Optional[int] = Query(None, description="ID do setor (opcional)"),
    lookback_weeks: int = Query(12, description="Semanas de histórico"),
    min_samples: int = Query(4, description="Mínimo de amostras para estatística válida"),
    db: Session = Depends(get_db)
):
    """
    Calcula estatísticas de turnover por dia da semana.
    
    PROMPT 4: turnover_rate(weekday) = checkouts_reais / rooms_occupied_real
    Usa dados históricos do Data Lake para calcular.
    """
    service = TurnoverStatsService(db)
    result = service.compute_turnover_stats(
        sector_id=sector_id,
        lookback_weeks=lookback_weeks,
        min_samples=min_samples
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/turnover/stats")
def get_turnover_stats(
    sector_id: Optional[int] = Query(None, description="ID do setor"),
    db: Session = Depends(get_db)
):
    """Obtém estatísticas de turnover por dia da semana."""
    service = TurnoverStatsService(db)
    return service.get_all_turnover_rates(sector_id=sector_id)


@router.post("/turnover/bootstrap")
def bootstrap_turnover_stats(
    sector_id: Optional[int] = Query(None, description="ID do setor"),
    db: Session = Depends(get_db)
):
    """
    Inicializa estatísticas de turnover com valores default.
    
    Útil quando não há histórico suficiente para cálculo.
    """
    service = TurnoverStatsService(db)
    result = service.bootstrap_from_defaults(sector_id=sector_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/recommendations")
def get_recommendations(
    forecast_run_id: int = Query(..., description="ID do ForecastRun baseline"),
    week_start: str = Query(..., description="Início da semana (YYYY-MM-DD)"),
    as_of: Optional[str] = Query(None, description="Data de referência (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Gera recomendações de ajuste comparando baseline vs projeção atual.
    
    PROMPT 4: Sugere +X/-X camareiras ou mudança de distribuição.
    """
    week_start_parsed = date.fromisoformat(week_start)
    as_of_parsed = date.fromisoformat(as_of) if as_of else date.today()
    
    service = DailyReplanService(db)
    
    forecast_run = db.query(ForecastRun).filter(ForecastRun.id == forecast_run_id).first()
    if not forecast_run:
        raise HTTPException(status_code=404, detail="ForecastRun não encontrado")
    
    result = service.suggest_daily_adjustments(
        date_today=as_of_parsed,
        sector_id=forecast_run.sector_id
    )
    
    return {
        "forecast_run_id": forecast_run_id,
        "week_start": week_start,
        "as_of": as_of_parsed.isoformat(),
        "suggestions": result.get("suggestions", []),
        "summary": result.get("summary", {})
    }


@router.get("/recurring-activities")
def get_recurring_activities(
    sector_id: int = Query(..., description="ID do setor"),
    db: Session = Depends(get_db)
):
    """
    Retorna resumo das atividades recorrentes cadastradas para o setor.
    """
    return get_recurring_activities_summary(db, sector_id)


@router.get("/recurring-activities/expand")
def expand_recurring(
    sector_id: int = Query(..., description="ID do setor"),
    year: int = Query(..., description="Ano ISO"),
    week: int = Query(..., ge=1, le=53, description="Semana ISO (1-53)"),
    db: Session = Depends(get_db)
):
    """
    Expande atividades recorrentes para uma semana específica.
    
    Calcula quais atividades RECORRENTES devem ser executadas na semana
    baseado em sua periodicidade e data de última execução.
    
    Retorna lista de itens a serem adicionados à programação semanal.
    """
    expanded = expand_recurring_activities(db, sector_id, year, week)
    
    return {
        "sector_id": sector_id,
        "year": year,
        "week": week,
        "total_items": len(expanded),
        "items": expanded
    }
