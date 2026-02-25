"""
API Router do Agente Decisorio

Endpoints para execucao do pipeline de inteligencia e
gerenciamento do workflow de aprovacao.

Versao: 1.0.0
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import date
from typing import Optional, Dict, Any

from app.database import get_db
from app.schemas.decision_agent import (
    DecisionAgentRequest,
    DecisionAgentResponse,
    ScheduleStatus
)
from app.services.decision_agent import DecisionAgentOrchestrator

router = APIRouter(prefix="/api/decision-agent", tags=["Agente Decisorio"])


@router.post("/execute", response_model=DecisionAgentResponse)
def execute_decision_agent(
    request: DecisionAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Executa o pipeline completo do Agente Decisorio.
    
    Fluxo:
    1. Inteligencia de Demanda
    2. Inteligencia de Capacidade
    3. Inteligencia de Escalonamento
    4. Inteligencia de Governanca
    
    Retorna escala sugestiva com memoria de calculo.
    """
    orchestrator = DecisionAgentOrchestrator(db)
    return orchestrator.execute(request)


@router.post("/approve/{schedule_id}")
def approve_schedule(
    schedule_id: int,
    approved_by: str,
    db: Session = Depends(get_db)
):
    """
    Aprova uma escala previamente gerada.
    
    Requisitos:
    - Escala deve existir e estar em status DRAFT
    - Nao pode haver regras criticas violadas
    """
    return {
        "message": "Funcionalidade de aprovacao sera implementada na Fase 4",
        "schedule_id": schedule_id,
        "status": "pending_implementation"
    }


@router.post("/contest/{schedule_id}")
def contest_schedule(
    schedule_id: int,
    contested_by: str,
    reason: str,
    db: Session = Depends(get_db)
):
    """
    Contesta uma escala e solicita alteracoes.
    
    Apos contestacao, a escala entra em status CONTESTED
    e aguarda recalculo.
    """
    return {
        "message": "Funcionalidade de contestacao sera implementada na Fase 4",
        "schedule_id": schedule_id,
        "status": "pending_implementation"
    }


@router.post("/recalculate/{schedule_id}")
def recalculate_schedule(
    schedule_id: int,
    request: DecisionAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Recalcula uma escala apos alteracoes.
    
    Usado apos contestacao ou quando parametros mudam.
    """
    orchestrator = DecisionAgentOrchestrator(db)
    return orchestrator.execute(request)


@router.get("/status/{schedule_id}")
def get_schedule_status(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna o status atual de uma escala.
    """
    return {
        "schedule_id": schedule_id,
        "status": "draft",
        "message": "Consulta de status sera implementada na Fase 4"
    }


@router.get("/memory/{schedule_id}")
def get_calculation_memory(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna a memoria de calculo de uma escala.
    
    Inclui:
    - Saida de cada nucleo de inteligencia
    - Regras aplicadas e hierarquia
    - Fontes de dados utilizadas
    """
    return {
        "schedule_id": schedule_id,
        "message": "Consulta de memoria sera implementada na Fase 4"
    }


@router.get("/workflow-status")
def get_workflow_status(
    sector_id: int,
    week_start: date,
    db: Session = Depends(get_db)
):
    """
    Verifica o status do workflow para um setor/semana.
    
    Retorna:
    - Se forecast run existe
    - Se planejamento semanal esta consolidado
    - Se escala foi gerada
    - Se escala foi aprovada
    - Se convocacoes foram emitidas
    """
    from app.models.governance_module import ForecastRun
    
    forecast_exists = db.query(ForecastRun).filter(
        ForecastRun.sector_id == sector_id
    ).first() is not None
    
    return {
        "sector_id": sector_id,
        "week_start": week_start.isoformat(),
        "workflow_steps": {
            "forecast_run": {
                "completed": forecast_exists,
                "description": "Simulacao de forecast"
            },
            "weekly_planning": {
                "completed": False,
                "description": "Consolidacao de dados da semana"
            },
            "schedule_generation": {
                "completed": False,
                "description": "Geracao de escala sugestiva"
            },
            "schedule_approval": {
                "completed": False,
                "description": "Aprovacao da escala"
            },
            "convocations": {
                "completed": False,
                "description": "Emissao de convocacoes"
            }
        },
        "can_generate_convocations": False,
        "blocking_step": "weekly_planning"
    }
