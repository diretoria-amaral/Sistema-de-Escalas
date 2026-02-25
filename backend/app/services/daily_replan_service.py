from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.governance_module import (
    SectorOperationalParameters, ForecastRun, ForecastDaily,
    HousekeepingSchedulePlan, ReplanSuggestion
)
from app.models.data_lake import OccupancyLatest, WeekdayBiasStats

METHOD_VERSION = "1.0.1"

WEEKDAYS_PT = {
    0: "SEGUNDA-FEIRA",
    1: "TERÇA-FEIRA",
    2: "QUARTA-FEIRA",
    3: "QUINTA-FEIRA",
    4: "SEXTA-FEIRA",
    5: "SÁBADO",
    6: "DOMINGO"
}


class DailyReplanService:
    
    def __init__(self, db: Session):
        self.db = db
    
    def suggest_daily_adjustments(
        self,
        date_today: date,
        sector_id: int
    ) -> Dict:
        """
        Compara forecast original (da sexta) com dados mais recentes
        e sugere ajustes se variação exceder threshold.
        
        Args:
            date_today: Data de hoje
            sector_id: ID do setor
        
        Returns:
            Dict com sugestões de ajuste
        """
        result = {
            "success": False,
            "date_today": date_today.isoformat(),
            "suggestions": [],
            "summary": {},
            "errors": []
        }
        
        try:
            params = self._get_sector_parameters(sector_id)
            if not params:
                result["errors"].append(f"Parâmetros não encontrados para setor {sector_id}")
                return result
            
            threshold = params.replan_threshold_pp or 5.0
            
            schedule_plan = self._get_active_schedule_plan(sector_id, date_today)
            if not schedule_plan:
                result["errors"].append("Nenhuma escala ativa encontrada para a semana")
                return result
            
            if not schedule_plan.forecast_run_id:
                result["errors"].append("Escala não possui forecast associado")
                return result
            
            original_forecasts = self.db.query(ForecastDaily).filter(
                ForecastDaily.forecast_run_id == schedule_plan.forecast_run_id,
                ForecastDaily.target_date >= date_today
            ).all()
            
            suggestions = []
            
            for original in original_forecasts:
                current_occ = self._get_current_occupancy(original.target_date)
                
                if current_occ is None:
                    continue
                
                original_adj = original.occ_adj or 0
                delta = current_occ - original_adj
                
                if abs(delta) >= threshold:
                    existing = self._check_existing_suggestion(
                        schedule_plan.id, 
                        original.target_date,
                        current_occ
                    )
                    
                    if existing:
                        suggestions.append({
                            "target_date": original.target_date.isoformat(),
                            "weekday_pt": original.weekday_pt,
                            "original_occ_adj": round(original_adj, 2),
                            "current_occ": round(current_occ, 2),
                            "delta_pp": round(delta, 2),
                            "suggestion_type": existing.suggestion_type,
                            "reason": existing.reason,
                            "priority": existing.priority,
                            "status": "existing"
                        })
                        continue
                    
                    suggestion = self._create_suggestion(
                        schedule_plan_id=schedule_plan.id,
                        target_date=original.target_date,
                        original_value=original_adj,
                        current_value=current_occ,
                        delta=delta,
                        threshold=threshold
                    )
                    
                    self.db.add(suggestion)
                    
                    suggestions.append({
                        "target_date": original.target_date.isoformat(),
                        "weekday_pt": original.weekday_pt,
                        "original_occ_adj": round(original_adj, 2),
                        "current_occ": round(current_occ, 2),
                        "delta_pp": round(delta, 2),
                        "suggestion_type": suggestion.suggestion_type,
                        "reason": suggestion.reason,
                        "priority": suggestion.priority,
                        "status": "new"
                    })
            
            self.db.commit()
            
            result["suggestions"] = suggestions
            result["summary"] = {
                "schedule_plan_id": schedule_plan.id,
                "week_start": schedule_plan.week_start.isoformat(),
                "threshold_pp": threshold,
                "total_suggestions": len(suggestions),
                "high_priority": len([s for s in suggestions if s["priority"] == "high"]),
                "medium_priority": len([s for s in suggestions if s["priority"] == "medium"])
            }
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
    
    def _get_active_schedule_plan(self, sector_id: int, date_ref: date) -> Optional[HousekeepingSchedulePlan]:
        """Obtém escala ativa que cobre a data de referência."""
        return self.db.query(HousekeepingSchedulePlan).filter(
            HousekeepingSchedulePlan.sector_id == sector_id,
            HousekeepingSchedulePlan.week_start <= date_ref,
            HousekeepingSchedulePlan.week_end >= date_ref
        ).order_by(HousekeepingSchedulePlan.created_at.desc()).first()
    
    def _check_existing_suggestion(
        self, 
        schedule_plan_id: int, 
        target_date: date, 
        current_value: float
    ) -> Optional[ReplanSuggestion]:
        """
        Verifica se já existe sugestão pendente para a mesma data com valor similar.
        Evita duplicação de sugestões quando o cenário não mudou significativamente.
        """
        existing = self.db.query(ReplanSuggestion).filter(
            ReplanSuggestion.schedule_plan_id == schedule_plan_id,
            ReplanSuggestion.target_date == target_date,
            ReplanSuggestion.is_accepted.is_(None)
        ).order_by(ReplanSuggestion.created_at.desc()).first()
        
        if existing:
            value_diff = abs(existing.suggested_value - current_value)
            if value_diff < 2.0:
                return existing
        
        return None
    
    def _get_current_occupancy(self, target_date: date) -> Optional[float]:
        """Obtém ocupação mais recente para a data."""
        latest = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date == target_date
        ).first()
        
        if not latest:
            return None
        
        if latest.latest_forecast_occupancy_pct is not None:
            return latest.latest_forecast_occupancy_pct
        
        return latest.occupancy_pct
    
    def _create_suggestion(
        self,
        schedule_plan_id: int,
        target_date: date,
        original_value: float,
        current_value: float,
        delta: float,
        threshold: float
    ) -> ReplanSuggestion:
        """Cria sugestão de ajuste."""
        if delta > 0:
            suggestion_type = "INCREASE_HEADCOUNT"
            reason = f"Ocupação aumentou {delta:.1f}pp desde a geração da escala. Considere adicionar mais camareiras."
        else:
            suggestion_type = "DECREASE_HEADCOUNT"
            reason = f"Ocupação diminuiu {abs(delta):.1f}pp desde a geração da escala. Considere reduzir equipe ou redistribuir."
        
        if abs(delta) >= threshold * 2:
            priority = "high"
        elif abs(delta) >= threshold * 1.5:
            priority = "medium"
        else:
            priority = "low"
        
        return ReplanSuggestion(
            schedule_plan_id=schedule_plan_id,
            target_date=target_date,
            suggestion_type=suggestion_type,
            original_value=original_value,
            suggested_value=current_value,
            delta=delta,
            reason=reason,
            priority=priority,
            justification_json={
                "threshold_pp": threshold,
                "delta_pp": delta,
                "original_occ_adj": original_value,
                "current_occ": current_value,
                "method_version": METHOD_VERSION
            }
        )
    
    def accept_suggestion(self, suggestion_id: int, accepted_by: str = None) -> Dict:
        """Marca sugestão como aceita."""
        suggestion = self.db.query(ReplanSuggestion).filter(
            ReplanSuggestion.id == suggestion_id
        ).first()
        
        if not suggestion:
            return {"success": False, "error": "Sugestão não encontrada"}
        
        suggestion.is_accepted = True
        suggestion.accepted_at = datetime.now()
        suggestion.accepted_by = accepted_by
        
        self.db.commit()
        
        return {
            "success": True,
            "suggestion_id": suggestion_id,
            "status": "accepted"
        }
    
    def reject_suggestion(self, suggestion_id: int, rejected_by: str = None) -> Dict:
        """Marca sugestão como rejeitada."""
        suggestion = self.db.query(ReplanSuggestion).filter(
            ReplanSuggestion.id == suggestion_id
        ).first()
        
        if not suggestion:
            return {"success": False, "error": "Sugestão não encontrada"}
        
        suggestion.is_accepted = False
        suggestion.accepted_at = datetime.now()
        suggestion.accepted_by = rejected_by
        
        self.db.commit()
        
        return {
            "success": True,
            "suggestion_id": suggestion_id,
            "status": "rejected"
        }
    
    def get_pending_suggestions(self, sector_id: int) -> List[Dict]:
        """Lista sugestões pendentes do setor."""
        plans = self.db.query(HousekeepingSchedulePlan.id).filter(
            HousekeepingSchedulePlan.sector_id == sector_id
        ).subquery()
        
        suggestions = self.db.query(ReplanSuggestion).filter(
            ReplanSuggestion.schedule_plan_id.in_(plans),
            ReplanSuggestion.is_accepted.is_(None)
        ).order_by(
            ReplanSuggestion.target_date,
            ReplanSuggestion.priority.desc()
        ).all()
        
        return [
            {
                "id": s.id,
                "target_date": s.target_date.isoformat(),
                "suggestion_type": s.suggestion_type,
                "original_value": s.original_value,
                "suggested_value": s.suggested_value,
                "delta": s.delta,
                "reason": s.reason,
                "priority": s.priority,
                "created_at": s.created_at.isoformat() if s.created_at else None
            }
            for s in suggestions
        ]
