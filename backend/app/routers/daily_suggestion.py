from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models import SuggestionType, SuggestionStatus, SuggestionImpactCategory
from app.services.daily_suggestion_service import DailySuggestionService


router = APIRouter(prefix="/api/daily-suggestions", tags=["Daily Suggestions"])


class SuggestionResponse(BaseModel):
    id: int
    sector_id: int
    sector_name: Optional[str] = None
    date: date
    suggestion_type: str
    description: str
    impact_category: str
    impact_json: Optional[dict] = None
    source_data: Optional[dict] = None
    status: str
    priority: int
    adjustment_run_id: Optional[int] = None
    created_at: str
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    
    class Config:
        from_attributes = True


class GenerateSuggestionsRequest(BaseModel):
    sector_id: int
    date: date


class ApplySuggestionRequest(BaseModel):
    user_id: Optional[str] = None
    notes: Optional[str] = None


class IgnoreSuggestionRequest(BaseModel):
    user_id: Optional[str] = None
    notes: Optional[str] = None


def _format_suggestion(suggestion) -> SuggestionResponse:
    return SuggestionResponse(
        id=suggestion.id,
        sector_id=suggestion.sector_id,
        sector_name=suggestion.sector.name if suggestion.sector else None,
        date=suggestion.date,
        suggestion_type=suggestion.suggestion_type.value,
        description=suggestion.description,
        impact_category=suggestion.impact_category.value,
        impact_json=suggestion.impact_json,
        source_data=suggestion.source_data,
        status=suggestion.status.value,
        priority=suggestion.priority,
        adjustment_run_id=suggestion.adjustment_run_id,
        created_at=suggestion.created_at.isoformat() if suggestion.created_at else None,
        resolved_at=suggestion.resolved_at.isoformat() if suggestion.resolved_at else None,
        resolved_by=suggestion.resolved_by,
        resolution_notes=suggestion.resolution_notes
    )


@router.get("", response_model=List[SuggestionResponse])
def list_suggestions(
    sector_id: Optional[int] = Query(None),
    target_date: Optional[date] = Query(None, alias="date"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db)
):
    """Lista sugestões com filtros."""
    status_enum = None
    if status:
        try:
            status_enum = SuggestionStatus(status)
        except ValueError:
            raise HTTPException(400, f"Status inválido: {status}")
    
    suggestions = DailySuggestionService.get_suggestions(
        db,
        sector_id=sector_id,
        target_date=target_date,
        status=status_enum,
        limit=limit
    )
    
    return [_format_suggestion(s) for s in suggestions]


@router.get("/open", response_model=List[SuggestionResponse])
def list_open_suggestions(
    sector_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """Lista apenas sugestões abertas (pendentes de decisão)."""
    suggestions = DailySuggestionService.get_suggestions(
        db,
        sector_id=sector_id,
        status=SuggestionStatus.OPEN,
        limit=100
    )
    return [_format_suggestion(s) for s in suggestions]


@router.post("/generate", response_model=List[SuggestionResponse])
def generate_suggestions(
    request: GenerateSuggestionsRequest,
    db: Session = Depends(get_db)
):
    """Gera novas sugestões para um setor/data."""
    suggestions = DailySuggestionService.generate_suggestions_for_date(
        db,
        sector_id=request.sector_id,
        target_date=request.date
    )
    return [_format_suggestion(s) for s in suggestions]


@router.get("/{suggestion_id}", response_model=SuggestionResponse)
def get_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db)
):
    """Obtém detalhes de uma sugestão."""
    from app.models import DailySuggestion
    suggestion = db.query(DailySuggestion).filter(
        DailySuggestion.id == suggestion_id
    ).first()
    
    if not suggestion:
        raise HTTPException(404, "Sugestão não encontrada")
    
    return _format_suggestion(suggestion)


@router.post("/{suggestion_id}/apply")
def apply_suggestion(
    suggestion_id: int,
    request: ApplySuggestionRequest,
    db: Session = Depends(get_db)
):
    """Aplica uma sugestão, gerando Adjustment Run."""
    result = DailySuggestionService.apply_suggestion(
        db,
        suggestion_id=suggestion_id,
        user_id=request.user_id,
        notes=request.notes
    )
    
    if not result["success"]:
        raise HTTPException(400, result["error"])
    
    return result


@router.post("/{suggestion_id}/ignore")
def ignore_suggestion(
    suggestion_id: int,
    request: IgnoreSuggestionRequest,
    db: Session = Depends(get_db)
):
    """Ignora uma sugestão (decisão humana registrada)."""
    result = DailySuggestionService.ignore_suggestion(
        db,
        suggestion_id=suggestion_id,
        user_id=request.user_id,
        notes=request.notes
    )
    
    if not result["success"]:
        raise HTTPException(400, result["error"])
    
    return result


@router.get("/types/list")
def list_suggestion_types():
    """Lista tipos de sugestão disponíveis."""
    return [
        {"value": t.value, "label": t.value.replace("_", " ").title()}
        for t in SuggestionType
    ]


@router.get("/impact-categories/list")
def list_impact_categories():
    """Lista categorias de impacto."""
    return [
        {"value": c.value, "label": c.value.title()}
        for c in SuggestionImpactCategory
    ]
