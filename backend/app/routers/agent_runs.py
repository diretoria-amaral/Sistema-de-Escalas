from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List
from datetime import date, datetime, timezone

from app.database import get_db
from app.models import Sector, AgentRun, AgentTraceStep, RunType, RunStatus
from app.schemas.agent_run import (
    AgentRunCreate, AgentRunUpdate, AgentRunResponse,
    AgentRunDetailResponse, AgentRunListResponse,
    AgentTraceStepCreate, AgentTraceStepResponse,
    CalculationMemoryResponse
)
from app.services.explain_service import ExplainService

router = APIRouter(prefix="/api/agent-runs", tags=["Agent Runs"])


@router.get("", response_model=AgentRunListResponse)
def list_agent_runs(
    setor_id: Optional[int] = Query(None, description="Filtrar por setor"),
    week_start: Optional[date] = Query(None, description="Filtrar por semana"),
    run_type: Optional[RunType] = Query(None, description="Filtrar por tipo de execucao"),
    status: Optional[RunStatus] = Query(None, description="Filtrar por status"),
    limit: int = Query(50, ge=1, le=200, description="Limite de resultados"),
    offset: int = Query(0, ge=0, description="Offset para paginacao"),
    db: Session = Depends(get_db)
):
    query = db.query(AgentRun)

    if setor_id:
        query = query.filter(AgentRun.setor_id == setor_id)
    if week_start:
        query = query.filter(AgentRun.week_start == week_start)
    if run_type:
        query = query.filter(AgentRun.run_type == run_type)
    if status:
        query = query.filter(AgentRun.status == status)

    total = query.count()
    query = query.order_by(desc(AgentRun.created_at)).offset(offset).limit(limit)

    runs = query.all()
    return AgentRunListResponse(items=runs, total=total)


@router.get("/{run_id}", response_model=AgentRunDetailResponse)
def get_agent_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")
    return run


@router.get("/{run_id}/memory", response_model=CalculationMemoryResponse)
def get_calculation_memory(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    rules_count = {}
    all_violated = []
    for step in run.trace_steps:
        if step.applied_rules:
            for rule_code in step.applied_rules:
                rules_count[rule_code] = rules_count.get(rule_code, 0) + 1
        if step.constraints_violated:
            all_violated.extend(step.constraints_violated)

    return CalculationMemoryResponse(
        run_id=run.id,
        setor_id=run.setor_id,
        week_start=run.week_start,
        run_type=run.run_type,
        status=run.status,
        inputs_snapshot=run.inputs_snapshot,
        outputs_summary=run.outputs_summary,
        trace_steps=[AgentTraceStepResponse.model_validate(s) for s in run.trace_steps],
        rules_applied_summary=rules_count,
        constraints_violated_summary=list(set(all_violated))
    )


@router.post("", response_model=AgentRunResponse, status_code=201)
def create_agent_run(data: AgentRunCreate, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == data.setor_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")

    run = AgentRun(**data.model_dump())
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.put("/{run_id}", response_model=AgentRunResponse)
def update_agent_run(run_id: int, data: AgentRunUpdate, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(run, key, value)

    db.commit()
    db.refresh(run)
    return run


@router.post("/{run_id}/complete")
def complete_agent_run(
    run_id: int,
    success: bool = True,
    outputs_summary: Optional[dict] = None,
    error_message: Optional[str] = None,
    db: Session = Depends(get_db)
):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    run.status = RunStatus.SUCCESS if success else RunStatus.FAILED
    run.finished_at = datetime.now(timezone.utc)
    if outputs_summary:
        run.outputs_summary = outputs_summary
    if error_message:
        run.error_message = error_message

    db.commit()
    db.refresh(run)
    return {"message": "Execucao finalizada", "status": run.status.value, "finished_at": run.finished_at}


@router.post("/{run_id}/steps", response_model=AgentTraceStepResponse, status_code=201)
def add_trace_step(run_id: int, data: AgentTraceStepCreate, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    step = AgentTraceStep(
        run_id=run_id,
        **data.model_dump()
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


@router.get("/{run_id}/steps", response_model=List[AgentTraceStepResponse])
def list_trace_steps(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    return run.trace_steps


@router.delete("/{run_id}")
def delete_agent_run(run_id: int, db: Session = Depends(get_db)):
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execucao nao encontrada")

    db.delete(run)
    db.commit()
    return {"message": "Execucao excluida com sucesso", "id": run_id}


@router.get("/latest/{setor_id}", response_model=AgentRunDetailResponse)
def get_latest_run(setor_id: int, run_type: Optional[RunType] = None, db: Session = Depends(get_db)):
    query = db.query(AgentRun).filter(AgentRun.setor_id == setor_id)
    if run_type:
        query = query.filter(AgentRun.run_type == run_type)
    query = query.order_by(desc(AgentRun.created_at))

    run = query.first()
    if not run:
        raise HTTPException(status_code=404, detail="Nenhuma execucao encontrada para este setor")
    return run


@router.get("/week/{setor_id}/{week_start}", response_model=List[AgentRunResponse])
def get_runs_for_week(setor_id: int, week_start: date, db: Session = Depends(get_db)):
    runs = db.query(AgentRun).filter(
        AgentRun.setor_id == setor_id,
        AgentRun.week_start == week_start
    ).order_by(desc(AgentRun.created_at)).all()

    return runs


@router.get("/{run_id}/explain")
def get_explanation(run_id: int, db: Session = Depends(get_db)):
    """
    Retorna explicação completa de uma execução.
    
    Inclui:
    - text: Resumo descritivo
    - math: Cálculos numéricos
    - rules_applied: Regras aplicadas em ordem
    - rules_violated: Regras violadas com justificativa
    - timeline: Linha do tempo dos passos
    """
    run = db.query(AgentRun).filter(AgentRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Execução não encontrada")
    
    explain_service = ExplainService(db)
    explanation = explain_service.explain_trace(run)
    
    return {
        "run_id": run_id,
        "run_type": run.run_type.value if run.run_type else None,
        "sector_id": run.setor_id,
        "week_start": run.week_start.isoformat() if run.week_start else None,
        "status": run.status.value if run.status else None,
        "explanation": explanation
    }


@router.get("/explain/latest")
def get_latest_explanation(
    sector_id: int,
    week_start: date,
    run_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Retorna explicação da execução mais recente.
    
    Parâmetros:
    - sector_id: ID do setor
    - week_start: Início da semana
    - run_type: Tipo de execução (opcional)
    """
    explain_service = ExplainService(db)
    explanation = explain_service.explain_latest(sector_id, week_start, run_type)
    
    return {
        "sector_id": sector_id,
        "week_start": week_start.isoformat(),
        "run_type": run_type,
        "explanation": explanation
    }
