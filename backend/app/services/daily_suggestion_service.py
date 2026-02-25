from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from app.models import (
    DailySuggestion, SuggestionType, SuggestionStatus, SuggestionImpactCategory,
    Sector, Convocation, ConvocationStatus, OccupancyLatest, OccupancySnapshot,
    HousekeepingDemandDaily, HousekeepingSchedulePlan, ForecastRun, ForecastRunType,
    OperationalCalendar, AuditLog, AuditAction
)


class DailySuggestionService:
    """
    PROMPT 17: Serviço de Sugestões Diárias (Copiloto)
    
    Gera recomendações baseadas em dados novos:
    - Mudanças de ocupação (novos HPs)
    - Recusas de convocação
    - Eventos de calendário
    - Desvios históricos
    
    NUNCA executa ações automaticamente - apenas sugere.
    """
    
    @staticmethod
    def generate_suggestions_for_date(
        db: Session,
        sector_id: int,
        target_date: date
    ) -> List[DailySuggestion]:
        """Gera sugestões para um setor/data específico."""
        suggestions = []
        
        sector = db.query(Sector).filter(Sector.id == sector_id).first()
        if not sector:
            return []
        
        existing = db.query(DailySuggestion).filter(
            and_(
                DailySuggestion.sector_id == sector_id,
                DailySuggestion.date == target_date,
                DailySuggestion.status == SuggestionStatus.OPEN
            )
        ).all()
        existing_types = {s.suggestion_type for s in existing}
        
        occupancy_suggestions = DailySuggestionService._check_occupancy_changes(
            db, sector_id, target_date
        )
        for s in occupancy_suggestions:
            if s.suggestion_type not in existing_types:
                suggestions.append(s)
                existing_types.add(s.suggestion_type)
        
        refusal_suggestions = DailySuggestionService._check_convocation_refusals(
            db, sector_id, target_date
        )
        for s in refusal_suggestions:
            if s.suggestion_type not in existing_types:
                suggestions.append(s)
                existing_types.add(s.suggestion_type)
        
        calendar_suggestions = DailySuggestionService._check_calendar_events(
            db, sector_id, target_date
        )
        for s in calendar_suggestions:
            if s.suggestion_type not in existing_types:
                suggestions.append(s)
                existing_types.add(s.suggestion_type)
        
        for suggestion in suggestions:
            db.add(suggestion)
            DailySuggestionService._log_suggestion_created(db, suggestion)
        
        db.commit()
        
        for suggestion in suggestions:
            db.refresh(suggestion)
        
        return suggestions
    
    @staticmethod
    def _check_occupancy_changes(
        db: Session,
        sector_id: int,
        target_date: date
    ) -> List[DailySuggestion]:
        """Verifica mudanças de ocupação que podem exigir ajustes."""
        suggestions = []
        
        latest = db.query(OccupancyLatest).filter(
            OccupancyLatest.date == target_date
        ).first()
        
        if not latest:
            return suggestions
        
        demand = db.query(HousekeepingDemandDaily).filter(
            and_(
                HousekeepingDemandDaily.sector_id == sector_id,
                HousekeepingDemandDaily.date == target_date
            )
        ).first()
        
        if demand and latest:
            current_rooms = latest.occupied_rooms or 0
            forecast_rooms = demand.checkouts + demand.stayovers if demand else 0
            
            if forecast_rooms > 0:
                deviation = abs(current_rooms - forecast_rooms) / forecast_rooms
                
                if current_rooms > forecast_rooms * 1.15:
                    suggestions.append(DailySuggestion(
                        sector_id=sector_id,
                        date=target_date,
                        suggestion_type=SuggestionType.TEAM_REINFORCEMENT,
                        description=f"Ocupação atual ({current_rooms} quartos) está {deviation*100:.0f}% acima do previsto ({forecast_rooms}). Considere reforçar a equipe.",
                        impact_category=SuggestionImpactCategory.OPERATIONAL,
                        impact_json={
                            "current_rooms": current_rooms,
                            "forecast_rooms": forecast_rooms,
                            "deviation_pct": round(deviation * 100, 1),
                            "estimated_extra_hours": round((current_rooms - forecast_rooms) * 0.5, 1)
                        },
                        source_data={"source": "occupancy_change", "latest_id": latest.id},
                        priority=3
                    ))
                
                elif current_rooms < forecast_rooms * 0.85:
                    suggestions.append(DailySuggestion(
                        sector_id=sector_id,
                        date=target_date,
                        suggestion_type=SuggestionType.HOURS_REDUCTION,
                        description=f"Ocupação atual ({current_rooms} quartos) está {deviation*100:.0f}% abaixo do previsto ({forecast_rooms}). Considere reduzir horas.",
                        impact_category=SuggestionImpactCategory.FINANCIAL,
                        impact_json={
                            "current_rooms": current_rooms,
                            "forecast_rooms": forecast_rooms,
                            "deviation_pct": round(deviation * 100, 1),
                            "potential_savings_hours": round((forecast_rooms - current_rooms) * 0.5, 1)
                        },
                        source_data={"source": "occupancy_change", "latest_id": latest.id},
                        priority=2
                    ))
        
        return suggestions
    
    @staticmethod
    def _check_convocation_refusals(
        db: Session,
        sector_id: int,
        target_date: date
    ) -> List[DailySuggestion]:
        """Verifica recusas de convocação que exigem substituição."""
        suggestions = []
        
        refusals = db.query(Convocation).filter(
            and_(
                Convocation.sector_id == sector_id,
                func.date(Convocation.shift_date) == target_date,
                Convocation.status == ConvocationStatus.DECLINED
            )
        ).all()
        
        if refusals:
            suggestions.append(DailySuggestion(
                sector_id=sector_id,
                date=target_date,
                suggestion_type=SuggestionType.PREVENTIVE_SUBSTITUTION,
                description=f"{len(refusals)} convocação(ões) recusada(s) para este dia. Sugestão de substituição preventiva.",
                impact_category=SuggestionImpactCategory.OPERATIONAL,
                impact_json={
                    "refusal_count": len(refusals),
                    "employee_ids": [c.employee_id for c in refusals]
                },
                source_data={"source": "convocation_refusals", "convocation_ids": [c.id for c in refusals]},
                priority=4
            ))
        
        return suggestions
    
    @staticmethod
    def _check_calendar_events(
        db: Session,
        sector_id: int,
        target_date: date
    ) -> List[DailySuggestion]:
        """Verifica eventos de calendário que podem impactar operação."""
        suggestions = []
        
        events = db.query(OperationalCalendar).filter(
            and_(
                OperationalCalendar.start_date <= target_date,
                OperationalCalendar.end_date >= target_date,
                OperationalCalendar.is_active == True
            )
        ).all()
        
        for event in events:
            if event.demand_factor and event.demand_factor > 1.2:
                suggestions.append(DailySuggestion(
                    sector_id=sector_id,
                    date=target_date,
                    suggestion_type=SuggestionType.TEAM_REINFORCEMENT,
                    description=f"Evento '{event.name}' com fator de demanda {event.demand_factor}x. Considere reforço de equipe.",
                    impact_category=SuggestionImpactCategory.OPERATIONAL,
                    impact_json={
                        "event_name": event.name,
                        "demand_factor": float(event.demand_factor),
                        "estimated_extra_load": f"{(event.demand_factor - 1) * 100:.0f}%"
                    },
                    source_data={"source": "calendar_event", "event_id": event.id},
                    priority=3
                ))
        
        return suggestions
    
    @staticmethod
    def apply_suggestion(
        db: Session,
        suggestion_id: int,
        user_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Aplica uma sugestão, gerando Adjustment Run."""
        suggestion = db.query(DailySuggestion).filter(
            DailySuggestion.id == suggestion_id
        ).first()
        
        if not suggestion:
            return {"success": False, "error": "Sugestão não encontrada"}
        
        if suggestion.status != SuggestionStatus.OPEN:
            return {"success": False, "error": f"Sugestão já está {suggestion.status.value}"}
        
        adjustment_run = ForecastRun(
            sector_id=suggestion.sector_id,
            week_start=suggestion.date - timedelta(days=suggestion.date.weekday()),
            run_type=ForecastRunType.DAILY_UPDATE,
            notes=f"Ajuste gerado da sugestão #{suggestion.id}: {suggestion.description}"
        )
        db.add(adjustment_run)
        db.flush()
        
        suggestion.status = SuggestionStatus.APPLIED
        suggestion.resolved_at = datetime.utcnow()
        suggestion.resolved_by = user_id
        suggestion.resolution_notes = notes
        suggestion.adjustment_run_id = adjustment_run.id
        
        DailySuggestionService._log_suggestion_applied(db, suggestion, adjustment_run.id)
        
        db.commit()
        
        return {
            "success": True,
            "adjustment_run_id": adjustment_run.id,
            "message": "Sugestão aplicada com sucesso. Adjustment Run criado."
        }
    
    @staticmethod
    def ignore_suggestion(
        db: Session,
        suggestion_id: int,
        user_id: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ignora uma sugestão (decisão humana registrada)."""
        suggestion = db.query(DailySuggestion).filter(
            DailySuggestion.id == suggestion_id
        ).first()
        
        if not suggestion:
            return {"success": False, "error": "Sugestão não encontrada"}
        
        if suggestion.status != SuggestionStatus.OPEN:
            return {"success": False, "error": f"Sugestão já está {suggestion.status.value}"}
        
        suggestion.status = SuggestionStatus.IGNORED
        suggestion.resolved_at = datetime.utcnow()
        suggestion.resolved_by = user_id
        suggestion.resolution_notes = notes
        
        DailySuggestionService._log_suggestion_ignored(db, suggestion)
        
        db.commit()
        
        return {"success": True, "message": "Sugestão ignorada e registrada."}
    
    @staticmethod
    def get_suggestions(
        db: Session,
        sector_id: Optional[int] = None,
        target_date: Optional[date] = None,
        status: Optional[SuggestionStatus] = None,
        limit: int = 50
    ) -> List[DailySuggestion]:
        """Lista sugestões com filtros."""
        query = db.query(DailySuggestion)
        
        if sector_id:
            query = query.filter(DailySuggestion.sector_id == sector_id)
        
        if target_date:
            query = query.filter(DailySuggestion.date == target_date)
        
        if status:
            query = query.filter(DailySuggestion.status == status)
        
        return query.order_by(
            DailySuggestion.priority.desc(),
            DailySuggestion.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def _log_suggestion_created(db: Session, suggestion: DailySuggestion):
        log = AuditLog(
            action=AuditAction.SUGGESTION_CREATED,
            entity_type="DailySuggestion",
            entity_id=suggestion.id,
            description=f"Sugestão criada: {suggestion.suggestion_type.value}",
            new_values={
                "type": suggestion.suggestion_type.value,
                "sector_id": suggestion.sector_id,
                "date": str(suggestion.date),
                "description": suggestion.description
            }
        )
        db.add(log)
    
    @staticmethod
    def _log_suggestion_applied(db: Session, suggestion: DailySuggestion, adjustment_id: int):
        log = AuditLog(
            action=AuditAction.SUGGESTION_APPLIED,
            entity_type="DailySuggestion",
            entity_id=suggestion.id,
            user_id=suggestion.resolved_by,
            description=f"Sugestão aplicada, Adjustment Run #{adjustment_id} criado",
            new_values={
                "adjustment_run_id": adjustment_id,
                "resolved_by": suggestion.resolved_by,
                "notes": suggestion.resolution_notes
            }
        )
        db.add(log)
        
        log2 = AuditLog(
            action=AuditAction.ADJUSTMENT_CREATED_FROM_SUGGESTION,
            entity_type="ForecastRun",
            entity_id=adjustment_id,
            user_id=suggestion.resolved_by,
            description=f"Adjustment Run criado a partir da sugestão #{suggestion.id}",
            new_values={"suggestion_id": suggestion.id}
        )
        db.add(log2)
    
    @staticmethod
    def _log_suggestion_ignored(db: Session, suggestion: DailySuggestion):
        log = AuditLog(
            action=AuditAction.SUGGESTION_IGNORED,
            entity_type="DailySuggestion",
            entity_id=suggestion.id,
            user_id=suggestion.resolved_by,
            description=f"Sugestão ignorada: {suggestion.suggestion_type.value}",
            new_values={
                "resolved_by": suggestion.resolved_by,
                "notes": suggestion.resolution_notes
            }
        )
        db.add(log)
