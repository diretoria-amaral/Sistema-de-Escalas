from datetime import time
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import ShiftTemplate, Sector
from app.services.shift_template_service import ShiftTemplateService


router = APIRouter(prefix="/api/shift-templates", tags=["Shift Templates"])


class ShiftTemplateCreate(BaseModel):
    sector_id: int
    name: str
    start_time: str
    end_time: str
    break_minutes: int = 60
    min_hours: int = 4
    max_hours: int = 8
    valid_weekdays: List[int] = [0, 1, 2, 3, 4, 5, 6]
    
    @field_validator('valid_weekdays')
    @classmethod
    def validate_weekdays(cls, v):
        for day in v:
            if day < 0 or day > 6:
                raise ValueError('Dias da semana devem estar entre 0 (seg) e 6 (dom)')
        return v


class ShiftTemplateUpdate(BaseModel):
    name: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    break_minutes: Optional[int] = None
    min_hours: Optional[int] = None
    max_hours: Optional[int] = None
    valid_weekdays: Optional[List[int]] = None


class ShiftTemplateResponse(BaseModel):
    id: int
    sector_id: int
    sector_name: Optional[str] = None
    name: str
    start_time: str
    end_time: str
    break_minutes: int
    min_hours: int
    max_hours: int
    valid_weekdays: List[int]
    is_active: bool
    calculated_hours: Optional[float] = None

    class Config:
        from_attributes = True


class MatchProgrammingRequest(BaseModel):
    sector_id: int
    daily_workload_minutes: dict


def parse_time(time_str: str) -> time:
    parts = time_str.split(":")
    return time(hour=int(parts[0]), minute=int(parts[1]))


def template_to_response(template: ShiftTemplate, db: Session = None) -> dict:
    work_hours = ShiftTemplateService._calculate_work_hours(
        template.start_time, template.end_time, template.break_minutes
    )
    
    sector_name = None
    if db:
        sector = db.query(Sector).filter(Sector.id == template.sector_id).first()
        if sector:
            sector_name = sector.name
    
    return {
        "id": template.id,
        "sector_id": template.sector_id,
        "sector_name": sector_name,
        "name": template.name,
        "start_time": str(template.start_time)[:5],
        "end_time": str(template.end_time)[:5],
        "break_minutes": template.break_minutes,
        "min_hours": template.min_hours,
        "max_hours": template.max_hours,
        "valid_weekdays": template.valid_weekdays or [0, 1, 2, 3, 4, 5, 6],
        "is_active": template.is_active,
        "calculated_hours": round(work_hours, 2)
    }


@router.get("")
def list_templates(
    sector_id: Optional[int] = None,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    if sector_id:
        templates = ShiftTemplateService.get_templates_by_sector(db, sector_id, active_only)
    else:
        templates = ShiftTemplateService.get_all_templates(db, active_only)
    
    return [template_to_response(t, db) for t in templates]


@router.get("/{template_id}")
def get_template(template_id: int, db: Session = Depends(get_db)):
    template = ShiftTemplateService.get_template_by_id(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template não encontrado")
    return template_to_response(template, db)


@router.post("")
def create_template(data: ShiftTemplateCreate, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == data.sector_id).first()
    if not sector:
        raise HTTPException(status_code=400, detail="Setor não encontrado")
    
    start_time = parse_time(data.start_time)
    end_time = parse_time(data.end_time)
    
    result = ShiftTemplateService.create_template(
        db=db,
        sector_id=data.sector_id,
        name=data.name,
        start_time=start_time,
        end_time=end_time,
        break_minutes=data.break_minutes,
        min_hours=data.min_hours,
        max_hours=data.max_hours,
        valid_weekdays=data.valid_weekdays
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail={"errors": result.get("errors", [])})
    
    response = template_to_response(result["template"], db)
    response["warnings"] = result.get("warnings", [])
    return response


@router.put("/{template_id}")
def update_template(template_id: int, data: ShiftTemplateUpdate, db: Session = Depends(get_db)):
    update_data = {}
    
    if data.name is not None:
        update_data["name"] = data.name
    if data.start_time is not None:
        update_data["start_time"] = parse_time(data.start_time)
    if data.end_time is not None:
        update_data["end_time"] = parse_time(data.end_time)
    if data.break_minutes is not None:
        update_data["break_minutes"] = data.break_minutes
    if data.min_hours is not None:
        update_data["min_hours"] = data.min_hours
    if data.max_hours is not None:
        update_data["max_hours"] = data.max_hours
    if data.valid_weekdays is not None:
        update_data["valid_weekdays"] = data.valid_weekdays
    
    result = ShiftTemplateService.update_template(db, template_id, **update_data)
    
    if not result["success"]:
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        raise HTTPException(status_code=400, detail={"errors": result.get("errors", [])})
    
    response = template_to_response(result["template"], db)
    response["warnings"] = result.get("warnings", [])
    return response


@router.post("/{template_id}/disable")
def disable_template(template_id: int, db: Session = Depends(get_db)):
    result = ShiftTemplateService.disable_template(db, template_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Erro ao desativar"))
    
    return {"success": True, "message": "Template desativado"}


@router.post("/{template_id}/enable")
def enable_template(template_id: int, db: Session = Depends(get_db)):
    result = ShiftTemplateService.enable_template(db, template_id)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result.get("error", "Erro ao ativar"))
    
    return {"success": True, "message": "Template ativado"}


@router.post("/match-programming")
def match_programming(data: MatchProgrammingRequest, db: Session = Depends(get_db)):
    result = ShiftTemplateService.match_programming_to_templates(
        db=db,
        sector_id=data.sector_id,
        daily_workload_minutes=data.daily_workload_minutes
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result.get("error", "Erro no matching"))
    
    return result
