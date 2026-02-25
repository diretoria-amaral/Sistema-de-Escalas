"""
Orquestrador do Agente Decisorio

Coordena os 4 nucleos de inteligencia em sequencia:
1. Demanda -> 2. Capacidade -> 3. Escalonamento -> 4. Governanca

Versao: 1.0.0
"""

from datetime import date, datetime
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
import time

from app.schemas.decision_agent import (
    DecisionAgentRequest,
    DecisionAgentResponse,
    GovernanceIntelligenceOutput
)
from .demand_intelligence import DemandIntelligenceService
from .capacity_intelligence import CapacityIntelligenceService
from .scheduling_intelligence import SchedulingIntelligenceService
from .governance_intelligence import GovernanceIntelligenceService


class DecisionAgentOrchestrator:
    """
    Orquestrador central do Agente Decisorio.
    
    Executa o pipeline completo de inteligencia:
    Demanda -> Capacidade -> Escalonamento -> Governanca
    
    Garante que cada nucleo receba os dados necessarios
    do nucleo anterior e registra toda a execucao.
    """
    
    VERSION = "1.0.0"
    
    def __init__(self, db: Session):
        self.db = db
        self.demand_service = DemandIntelligenceService(db)
        self.capacity_service = CapacityIntelligenceService(db)
        self.scheduling_service = SchedulingIntelligenceService(db)
        self.governance_service = GovernanceIntelligenceService(db)
    
    def execute(self, request: DecisionAgentRequest) -> DecisionAgentResponse:
        """
        Executa o pipeline completo do Agente Decisorio.
        
        Args:
            request: Requisicao com setor, semana e parametros
        
        Returns:
            DecisionAgentResponse com resultado completo
        """
        start_time = time.time()
        errors = []
        warnings = []
        
        try:
            demand_output = self.demand_service.calculate(
                sector_id=request.sector_id,
                week_start=request.week_start,
                eventual_activities=request.eventual_activities_input
            )
            
            if demand_output.errors:
                errors.extend(demand_output.errors)
            if demand_output.warnings:
                warnings.extend(demand_output.warnings)
            
            capacity_output = self.capacity_service.calculate(
                sector_id=request.sector_id,
                week_start=request.week_start
            )
            
            if capacity_output.errors:
                errors.extend(capacity_output.errors)
            if capacity_output.warnings:
                warnings.extend(capacity_output.warnings)
            
            scheduling_output = self.scheduling_service.calculate(
                sector_id=request.sector_id,
                week_start=request.week_start,
                demand_output=demand_output,
                capacity_output=capacity_output
            )
            
            if scheduling_output.errors:
                errors.extend(scheduling_output.errors)
            if scheduling_output.warnings:
                warnings.extend(scheduling_output.warnings)
            
            governance_output = self.governance_service.evaluate(
                sector_id=request.sector_id,
                week_start=request.week_start,
                demand_output=demand_output,
                capacity_output=capacity_output,
                scheduling_output=scheduling_output
            )
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return DecisionAgentResponse(
                success=True,
                governance_output=governance_output,
                execution_time_ms=execution_time,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            errors.append(f"Erro na execucao do agente: {str(e)}")
            
            return DecisionAgentResponse(
                success=False,
                governance_output=None,
                execution_time_ms=execution_time,
                errors=errors,
                warnings=warnings
            )
    
    def approve_schedule(
        self,
        governance_output: GovernanceIntelligenceOutput,
        approved_by: str
    ) -> GovernanceIntelligenceOutput:
        """
        Aprova uma escala previamente gerada.
        
        Args:
            governance_output: Output da avaliacao de governanca
            approved_by: Usuario que esta aprovando
        
        Returns:
            GovernanceIntelligenceOutput atualizado
        """
        return self.governance_service.approve(governance_output, approved_by)
    
    def contest_schedule(
        self,
        governance_output: GovernanceIntelligenceOutput,
        contested_by: str,
        reason: str,
        changes_requested: Dict[str, Any]
    ) -> GovernanceIntelligenceOutput:
        """
        Contesta uma escala e solicita recalculo.
        
        Args:
            governance_output: Output da avaliacao de governanca
            contested_by: Usuario que esta contestando
            reason: Motivo da contestacao
            changes_requested: Alteracoes solicitadas
        
        Returns:
            GovernanceIntelligenceOutput atualizado
        """
        return self.governance_service.contest(
            governance_output,
            contested_by,
            reason,
            changes_requested
        )
    
    def recalculate(
        self,
        request: DecisionAgentRequest,
        adjustments: Optional[Dict[str, Any]] = None
    ) -> DecisionAgentResponse:
        """
        Recalcula a escala apos contestacao ou alteracoes.
        
        Args:
            request: Requisicao original
            adjustments: Ajustes a aplicar no recalculo
        
        Returns:
            DecisionAgentResponse com novo resultado
        """
        return self.execute(request)
