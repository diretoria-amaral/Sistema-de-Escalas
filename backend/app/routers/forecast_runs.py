"""
API Routes para Forecast Runs (Baseline + Updates).
Fase 2: Planejamento formal com comparativo Planejado x Atualizado x Real.
"""
from datetime import date, datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import csv
import io

from app.database import get_db
from app.services.forecast_run_service import ForecastRunService
from app.services.governance_demand_service import GovernanceDemandService
from app.services.governance_schedule_generator import GovernanceScheduleGenerator
from app.models.governance_module import ForecastRun, HousekeepingSchedulePlan

router = APIRouter(prefix="/api/forecast-runs", tags=["Forecast Runs"])


@router.get("/prerequisites")
def check_prerequisites(
    sector_id: int = Query(..., description="ID do setor"),
    week_start: Optional[date] = Query(None, description="Segunda-feira da semana (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Verifica pré-requisitos obrigatórios antes de gerar Baseline.
    
    Validações:
    1. Setor existe no sistema
    2. Parâmetros operacionais do setor configurados
    3. Atividades de governança cadastradas para o setor
    4. Dados históricos de ocupação (HP) disponíveis
    
    Se can_generate=False, a geração será bloqueada com mensagens explicativas.
    """
    service = ForecastRunService(db)
    return service.check_prerequisites(sector_id=sector_id, week_start=week_start)


class CreateBaselineRequest(BaseModel):
    sector_id: int
    week_start: Optional[date] = None
    safety_pp_by_weekday: Optional[dict] = None
    alpha: float = Field(default=0.2, ge=0.01, le=1.0)
    notes: Optional[str] = None


class CreateDailyUpdateRequest(BaseModel):
    sector_id: int
    week_start: Optional[date] = None


class LockRunRequest(BaseModel):
    pass


@router.post("/baseline")
def create_baseline(
    request: CreateBaselineRequest,
    db: Session = Depends(get_db)
):
    """
    Cria um Forecast Run do tipo BASELINE.
    Tipicamente executado na sexta-feira para a semana seguinte (Seg-Dom).
    
    VALIDAÇÕES OBRIGATÓRIAS:
    1. Setor deve existir
    2. Parâmetros operacionais do setor devem estar configurados
    3. Atividades de governança devem estar cadastradas
    4. Dados históricos de ocupação (HP) devem estar disponíveis
    
    Se qualquer pré-requisito estiver faltando, a geração é BLOQUEADA.
    """
    service = ForecastRunService(db)
    
    prerequisites = service.check_prerequisites(
        sector_id=request.sector_id,
        week_start=request.week_start
    )
    
    if not prerequisites["can_generate"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Pré-requisitos não atendidos para geração do Baseline.",
                "blocking_errors": prerequisites["blocking_errors"],
                "prerequisites": prerequisites["prerequisites"]
            }
        )
    
    result = service.create_baseline(
        sector_id=request.sector_id,
        week_start=request.week_start,
        safety_pp_by_weekday=request.safety_pp_by_weekday,
        alpha=request.alpha,
        notes=request.notes
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    result["prerequisites_checked"] = True
    result["warnings"] = prerequisites.get("warnings", [])
    
    return result


@router.post("/daily-update")
def create_daily_update(
    request: CreateDailyUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Cria um Forecast Run do tipo DAILY_UPDATE.
    Usa o baseline ativo como referência.
    """
    service = ForecastRunService(db)
    result = service.create_daily_update(
        sector_id=request.sector_id,
        week_start=request.week_start
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.post("/{run_id}/lock")
def lock_run(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Trava um Forecast Run do tipo BASELINE.
    Após travado, torna-se imutável e é a referência oficial para a semana.
    """
    service = ForecastRunService(db)
    result = service.lock_run(run_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("")
def list_forecast_runs(
    sector_id: int,
    week_start: Optional[date] = None,
    run_type: Optional[str] = Query(None, regex="^(baseline|daily_update|manual)$"),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Lista Forecast Runs com filtros opcionais.
    """
    service = ForecastRunService(db)
    return service.list_runs(
        sector_id=sector_id,
        week_start=week_start,
        run_type=run_type,
        limit=limit
    )


@router.get("/active-baseline")
def get_active_baseline(
    sector_id: int,
    week_start: date,
    db: Session = Depends(get_db)
):
    """
    Retorna o baseline ativo (locked) para a semana especificada.
    """
    service = ForecastRunService(db)
    result = service.get_active_baseline(sector_id, week_start)
    
    if not result:
        raise HTTPException(status_code=404, detail="Nenhum baseline ativo encontrado para esta semana")
    
    return result


@router.get("/{run_id}")
def get_forecast_run(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtém detalhes completos de um Forecast Run.
    """
    service = ForecastRunService(db)
    result = service.get_run_detail(run_id)
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Forecast Run {run_id} não encontrado")
    
    return result


@router.get("/{run_id}/comparison/latest")
def get_comparison_with_latest(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Compara um baseline com o daily_update mais recente da mesma semana.
    """
    service = ForecastRunService(db)
    result = service.get_comparison_with_latest(run_id)
    
    if not result.get("success", False) and result.get("errors"):
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/{run_id}/errors")
def get_forecast_errors(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Calcula erros do forecast comparando com valores reais.
    Apenas para dias já passados que tenham dados reais disponíveis.
    """
    service = ForecastRunService(db)
    result = service.compute_forecast_errors(run_id)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.post("/compare")
def compare_runs(
    run_id_a: int,
    run_id_b: int,
    db: Session = Depends(get_db)
):
    """
    Compara dois Forecast Runs e retorna diffs por dia.
    """
    service = ForecastRunService(db)
    result = service.compare_runs(run_id_a, run_id_b)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.get("/{run_id}/summary")
def get_executive_summary(
    run_id: int,
    threshold_pp: float = Query(2.0, ge=0.5, le=10.0, description="Limiar em pp para mudança relevante"),
    db: Session = Depends(get_db)
):
    """
    Gera resumo executivo do forecast run com recomendações textuais.
    
    Inclui:
    - Tabela com SEG..DOM: baseline_adj, daily_adj, delta_pp
    - Flags de mudança relevante
    - Recomendações de ajuste de escala
    """
    service = ForecastRunService(db)
    result = service.get_executive_summary(run_id, threshold_pp)
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["errors"])
    
    return result


@router.post("/{forecast_run_id}/generate-governance-schedule")
def generate_governance_schedule(
    forecast_run_id: int,
    db: Session = Depends(get_db)
):
    """
    FASE 5: Gera escala de Governança automaticamente a partir de um Forecast Run.
    
    Fluxo end-to-end:
    1. Busca o ForecastRun (baseline ou daily_update)
    2. Calcula demanda diária (quartos_vago_sujo, estadias, headcount)
    3. Gera distribuição de turnos (templates, horários almoço)
    4. Persiste em HousekeepingSchedulePlan + ShiftSlots
    5. Retorna estrutura completa para UI
    
    Args:
        forecast_run_id: ID do ForecastRun (baseline ou daily_update)
    
    Returns:
        Escala completa com resumo por dia e turnos por colaboradora
    """
    forecast_run = db.query(ForecastRun).filter(
        ForecastRun.id == forecast_run_id
    ).first()
    
    if not forecast_run:
        raise HTTPException(status_code=404, detail=f"ForecastRun {forecast_run_id} não encontrado")
    
    demand_service = GovernanceDemandService(db)
    demand_result = demand_service.compute_housekeeping_demand(forecast_run_id=forecast_run_id)
    
    if not demand_result.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=f"Erro ao calcular demanda: {demand_result.get('errors', [])}"
        )
    
    schedule_service = GovernanceScheduleGenerator(db)
    schedule_result = schedule_service.generate_housekeeping_schedule(
        week_start=forecast_run.horizon_start,
        sector_id=forecast_run.sector_id,
        forecast_run_id=forecast_run_id
    )
    
    if not schedule_result.get("success"):
        raise HTTPException(
            status_code=400, 
            detail=f"Erro ao gerar escala: {schedule_result.get('errors', [])}"
        )
    
    schedule_plan = db.query(HousekeepingSchedulePlan).filter(
        HousekeepingSchedulePlan.id == schedule_result["schedule_plan_id"]
    ).first()
    
    return {
        "success": True,
        "forecast_run_id": forecast_run_id,
        "forecast_run_type": forecast_run.run_type.value if forecast_run.run_type else "manual",
        "week_start": forecast_run.horizon_start.isoformat(),
        "week_end": forecast_run.horizon_end.isoformat(),
        "schedule_plan_id": schedule_result["schedule_plan_id"],
        "demand_summary": demand_result.get("summary", {}),
        "daily_demands": demand_result.get("daily_demands", []),
        "schedule_summary": {
            "total_headcount": schedule_plan.total_headcount_planned if schedule_plan else 0,
            "total_hours": schedule_plan.total_hours_planned if schedule_plan else 0.0,
            "status": schedule_plan.status.value if schedule_plan else "draft"
        },
        "daily_slots": schedule_result.get("daily_slots", []),
        "message": f"Escala gerada com sucesso a partir do ForecastRun #{forecast_run_id}"
    }


@router.get("/{forecast_run_id}/convocations/export")
def export_convocations(
    forecast_run_id: int,
    format: str = Query("csv", regex="^(csv|json)$"),
    db: Session = Depends(get_db)
):
    """
    FASE 5: Exporta convocações como CSV ou JSON.
    
    Gera arquivo com dados de convocação por colaborador:
    - Nome, dias e horários de trabalho
    - Total de horas semanais
    - Status de validação legal
    
    Args:
        forecast_run_id: ID do ForecastRun
        format: Formato de saída (csv ou json)
    """
    forecast_run = db.query(ForecastRun).filter(
        ForecastRun.id == forecast_run_id
    ).first()
    
    if not forecast_run:
        raise HTTPException(status_code=404, detail=f"ForecastRun {forecast_run_id} não encontrado")
    
    schedule_plan = db.query(HousekeepingSchedulePlan).filter(
        HousekeepingSchedulePlan.forecast_run_id == forecast_run_id
    ).order_by(HousekeepingSchedulePlan.created_at.desc()).first()
    
    if not schedule_plan:
        raise HTTPException(
            status_code=404, 
            detail="Nenhuma escala gerada para este ForecastRun. Execute generate-governance-schedule primeiro."
        )
    
    schedule_service = GovernanceScheduleGenerator(db)
    convocations_result = schedule_service.preview_convocations(schedule_plan.id)
    
    if not convocations_result.get("success"):
        raise HTTPException(status_code=400, detail=convocations_result.get("errors", []))
    
    convocations = convocations_result.get("convocations", [])
    
    if format == "json":
        return {
            "forecast_run_id": forecast_run_id,
            "schedule_plan_id": schedule_plan.id,
            "week_start": forecast_run.horizon_start.isoformat(),
            "week_end": forecast_run.horizon_end.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "convocations": convocations,
            "summary": convocations_result.get("summary", {})
        }
    
    string_output = io.StringIO()
    writer = csv.writer(string_output, delimiter=';')
    
    writer.writerow([
        "Colaborador",
        "Total Dias",
        "Total Horas",
        "Status",
        "Dias/Horários",
        "Alertas"
    ])
    
    for conv in convocations:
        dias_horarios = " | ".join([
            f"{s.get('weekday_pt', '')[:3]} {s.get('start_time', '')}-{s.get('end_time', '')}"
            for s in conv.get("slots", [])
        ])
        alertas = ", ".join(conv.get("warnings", []))
        
        writer.writerow([
            conv.get("employee_name", f"Colaborador #{conv.get('employee_id', 'N/A')}"),
            conv.get("total_days", 0),
            f"{conv.get('total_hours', 0):.1f}",
            conv.get("status", "").upper(),
            dias_horarios,
            alertas
        ])
    
    csv_content = string_output.getvalue().encode('utf-8-sig')
    output = io.BytesIO(csv_content)
    
    filename = f"convocacoes_fr{forecast_run_id}_{forecast_run.horizon_start.strftime('%Y%m%d')}.csv"
    
    return StreamingResponse(
        output,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Content-Length": str(len(csv_content))
        }
    )
