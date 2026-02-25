from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, time
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.sector import Sector
from app.models.governance_activity import GovernanceActivity
from app.models.governance_module import ForecastRun
from app.models.activity_program import (
    ActivityProgramWeek, ActivityProgramItem, 
    ProgramWeekStatus, ProgramItemSource
)
from app.services.activity_program_service import ActivityProgramService


router = APIRouter(prefix="/activity-program", tags=["Activity Programming"])


class CreateProgramWeekRequest(BaseModel):
    sector_id: int
    forecast_run_id: int
    week_start: date
    mode: str = Field(default="MANUAL", pattern="^(AUTO|MANUAL)$")


class CreateItemRequest(BaseModel):
    activity_id: int
    op_date: date
    quantity: int = Field(default=1, ge=1)
    workload_minutes: Optional[int] = Field(default=None, ge=0)
    priority: int = Field(default=3, ge=1, le=5)
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    notes: Optional[str] = None


class UpdateItemRequest(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=1)
    workload_minutes: Optional[int] = Field(default=None, ge=0)
    priority: Optional[int] = Field(default=None, ge=1, le=5)
    window_start: Optional[str] = None
    window_end: Optional[str] = None
    notes: Optional[str] = None
    op_date: Optional[date] = None


class CreateAdjustmentRequest(BaseModel):
    reason: str


@router.get("/sectors")
def list_sectors(db: Session = Depends(get_db)):
    sectors = db.query(Sector).filter(Sector.is_active == True).all()
    return [{"id": s.id, "name": s.name} for s in sectors]


@router.get("/weeks")
def list_program_weeks(
    sector_id: Optional[int] = None,
    week_start: Optional[date] = None,
    forecast_run_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ActivityProgramWeek)
    
    if sector_id:
        query = query.filter(ActivityProgramWeek.sector_id == sector_id)
    if week_start:
        query = query.filter(ActivityProgramWeek.week_start == week_start)
    if forecast_run_id:
        query = query.filter(ActivityProgramWeek.forecast_run_id == forecast_run_id)
    
    weeks = query.order_by(ActivityProgramWeek.week_start.desc()).all()
    
    return [{
        "id": w.id,
        "sector_id": w.sector_id,
        "sector_name": w.sector.name if w.sector else None,
        "forecast_run_id": w.forecast_run_id,
        "week_start": w.week_start.isoformat(),
        "status": w.status.value,
        "item_count": len(w.items),
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "created_by": w.created_by
    } for w in weeks]


@router.post("/week")
def create_program_week(
    request: CreateProgramWeekRequest,
    db: Session = Depends(get_db)
):
    try:
        program_week = ActivityProgramService.create_program_week(
            db=db,
            sector_id=request.sector_id,
            forecast_run_id=request.forecast_run_id,
            week_start=request.week_start,
            mode=request.mode,
            created_by="user"
        )
        
        return {
            "id": program_week.id,
            "sector_id": program_week.sector_id,
            "forecast_run_id": program_week.forecast_run_id,
            "week_start": program_week.week_start.isoformat(),
            "status": program_week.status.value,
            "item_count": len(program_week.items)
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/week/{week_id}")
def get_program_week(week_id: int, db: Session = Depends(get_db)):
    program_week = db.query(ActivityProgramWeek).filter(
        ActivityProgramWeek.id == week_id
    ).first()
    
    if not program_week:
        raise HTTPException(status_code=404, detail="Program week not found")
    
    items_by_day = {}
    for item in program_week.items:
        day_key = item.op_date.isoformat()
        if day_key not in items_by_day:
            items_by_day[day_key] = []
        
        items_by_day[day_key].append({
            "id": item.id,
            "activity_id": item.activity_id,
            "activity_name": item.activity.name if item.activity else None,
            "activity_code": item.activity.code if item.activity else None,
            "op_date": item.op_date.isoformat(),
            "window_start": item.window_start.isoformat() if item.window_start else None,
            "window_end": item.window_end.isoformat() if item.window_end else None,
            "quantity": item.quantity,
            "workload_minutes": item.workload_minutes,
            "priority": item.priority,
            "source": item.source.value,
            "drivers_json": item.drivers_json,
            "notes": item.notes,
            "created_by": item.created_by
        })
    
    return {
        "id": program_week.id,
        "sector_id": program_week.sector_id,
        "sector_name": program_week.sector.name if program_week.sector else None,
        "forecast_run_id": program_week.forecast_run_id,
        "week_start": program_week.week_start.isoformat(),
        "status": program_week.status.value,
        "created_at": program_week.created_at.isoformat() if program_week.created_at else None,
        "created_by": program_week.created_by,
        "updated_at": program_week.updated_at.isoformat() if program_week.updated_at else None,
        "updated_by": program_week.updated_by,
        "items_by_day": items_by_day,
        "total_items": len(program_week.items)
    }


@router.post("/week/{week_id}/items")
def add_item(
    week_id: int,
    request: CreateItemRequest,
    db: Session = Depends(get_db)
):
    try:
        window_start = None
        window_end = None
        
        if request.window_start:
            parts = request.window_start.split(":")
            window_start = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        
        if request.window_end:
            parts = request.window_end.split(":")
            window_end = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        
        item = ActivityProgramService.add_item(
            db=db,
            program_week_id=week_id,
            activity_id=request.activity_id,
            op_date=request.op_date,
            quantity=request.quantity,
            workload_minutes=request.workload_minutes,
            priority=request.priority,
            window_start=window_start,
            window_end=window_end,
            notes=request.notes
        )
        
        return {
            "id": item.id,
            "activity_id": item.activity_id,
            "op_date": item.op_date.isoformat(),
            "quantity": item.quantity,
            "workload_minutes": item.workload_minutes,
            "priority": item.priority,
            "source": item.source.value
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/items/{item_id}")
def update_item(
    item_id: int,
    request: UpdateItemRequest,
    db: Session = Depends(get_db)
):
    try:
        updates = {}
        
        if request.quantity is not None:
            updates["quantity"] = request.quantity
        if request.workload_minutes is not None:
            updates["workload_minutes"] = request.workload_minutes
        if request.priority is not None:
            updates["priority"] = request.priority
        if request.notes is not None:
            updates["notes"] = request.notes
        if request.op_date is not None:
            updates["op_date"] = request.op_date
        
        if request.window_start is not None:
            parts = request.window_start.split(":")
            updates["window_start"] = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        
        if request.window_end is not None:
            parts = request.window_end.split(":")
            updates["window_end"] = time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
        
        item = ActivityProgramService.update_item(db, item_id, updates)
        
        return {
            "id": item.id,
            "activity_id": item.activity_id,
            "op_date": item.op_date.isoformat(),
            "quantity": item.quantity,
            "workload_minutes": item.workload_minutes,
            "priority": item.priority,
            "source": item.source.value
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/items/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db)):
    try:
        success = ActivityProgramService.delete_item(db, item_id)
        if not success:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"deleted": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/week/{week_id}/approve")
def approve_program(week_id: int, db: Session = Depends(get_db)):
    try:
        program = ActivityProgramService.approve_program(db, week_id)
        return {
            "id": program.id,
            "status": program.status.value,
            "message": "Program approved successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/week/{week_id}/lock")
def lock_program(week_id: int, db: Session = Depends(get_db)):
    try:
        program = ActivityProgramService.lock_program(db, week_id)
        return {
            "id": program.id,
            "status": program.status.value,
            "message": "Program locked successfully"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/baseline/{forecast_run_id}/adjustment")
def create_adjustment(
    forecast_run_id: int,
    request: CreateAdjustmentRequest,
    sector_id: int = Query(...),
    db: Session = Depends(get_db)
):
    try:
        result = ActivityProgramService.create_adjustment(
            db=db,
            baseline_forecast_run_id=forecast_run_id,
            sector_id=sector_id,
            reason=request.reason
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inputs")
def get_programming_inputs(
    sector_id: int = Query(...),
    week_start: date = Query(...),
    forecast_run_id: int = Query(...),
    db: Session = Depends(get_db)
):
    result = ActivityProgramService.get_programming_inputs(
        db=db,
        sector_id=sector_id,
        week_start=week_start,
        forecast_run_id=forecast_run_id
    )
    return result


@router.get("/forecast-runs")
def list_forecast_runs(
    sector_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(ForecastRun)
    
    if sector_id:
        query = query.filter(ForecastRun.sector_id == sector_id)
    
    runs = query.order_by(ForecastRun.created_at.desc()).limit(50).all()
    
    return [{
        "id": r.id,
        "sector_id": r.sector_id,
        "run_type": r.run_type.value if r.run_type else None,
        "run_date": r.run_date.isoformat() if r.run_date else None,
        "horizon_start": r.horizon_start.isoformat() if r.horizon_start else None,
        "horizon_end": r.horizon_end.isoformat() if r.horizon_end else None,
        "status": r.status.value if r.status else None,
        "is_locked": r.is_locked,
        "created_at": r.created_at.isoformat() if r.created_at else None
    } for r in runs]


@router.get("/activities")
def list_activities_for_sector(
    sector_id: int = Query(...),
    db: Session = Depends(get_db)
):
    activities = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == sector_id,
        GovernanceActivity.is_active == True
    ).all()
    
    return [{
        "id": a.id,
        "name": a.name,
        "code": a.code,
        "average_time_minutes": a.average_time_minutes
    } for a in activities]
