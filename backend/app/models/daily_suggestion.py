from sqlalchemy import Column, Integer, String, Date, DateTime, JSON, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class SuggestionType(str, enum.Enum):
    TEAM_REINFORCEMENT = "team_reinforcement"
    HOURS_REDUCTION = "hours_reduction"
    SHIFT_ANTICIPATION = "shift_anticipation"
    SHIFT_POSTPONEMENT = "shift_postponement"
    PREVENTIVE_SUBSTITUTION = "preventive_substitution"
    SCHEDULE_ADJUSTMENT = "schedule_adjustment"


class SuggestionStatus(str, enum.Enum):
    OPEN = "open"
    APPLIED = "applied"
    IGNORED = "ignored"


class SuggestionImpactCategory(str, enum.Enum):
    FINANCIAL = "financial"
    OPERATIONAL = "operational"
    LEGAL = "legal"


class DailySuggestion(Base):
    """
    PROMPT 17: Sugestões Diárias (Copiloto)
    
    Recomendações baseadas em dados novos que NÃO executam ações automaticamente.
    Apenas sugerem ajustes para aprovação humana.
    """
    __tablename__ = "daily_suggestions"

    id = Column(Integer, primary_key=True, index=True)
    
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    suggestion_type = Column(
        SQLEnum(SuggestionType, values_callable=lambda e: [m.value for m in e]),
        nullable=False
    )
    
    description = Column(Text, nullable=False)
    
    impact_category = Column(
        SQLEnum(SuggestionImpactCategory, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SuggestionImpactCategory.OPERATIONAL
    )
    
    impact_json = Column(JSON, nullable=True, default=dict)
    
    source_data = Column(JSON, nullable=True, default=dict)
    
    status = Column(
        SQLEnum(SuggestionStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=SuggestionStatus.OPEN,
        index=True
    )
    
    priority = Column(Integer, default=0)
    
    adjustment_run_id = Column(Integer, ForeignKey("forecast_runs.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_notes = Column(Text, nullable=True)
    
    sector = relationship("Sector", backref="daily_suggestions")
    adjustment_run = relationship("ForecastRun", backref="suggestions")
