from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.work_shift import WorkShift, WorkShiftDayRule
from app.schemas.work_shift import WorkShiftCreate, WorkShiftUpdate, WorkShiftResponse

router = APIRouter(prefix="/api/work-shifts", tags=["Work Shifts"])

work_shifts_router = router  # Export for main.py

@router.get("", response_model=List[WorkShiftResponse])
def list_work_shifts(
    sector_id: int = Query(...),
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db)
):
    query = db.query(WorkShift).filter(WorkShift.sector_id == sector_id)
    if not include_inactive:
        query = query.filter(WorkShift.is_active == True)
    return query.all()

@router.post("", response_model=WorkShiftResponse)
def create_work_shift(payload: WorkShiftCreate, db: Session = Depends(get_db)):
    db_shift = WorkShift(sector_id=payload.sector_id, name=payload.name)
    db.add(db_shift)
    db.flush()

    for day_data in payload.days:
        day_rule = WorkShiftDayRule(
            work_shift_id=db_shift.id,
            **day_data.model_dump()
        )
        db.add(day_rule)
    
    db.commit()
    db.refresh(db_shift)
    return db_shift

@router.get("/{id}", response_model=WorkShiftResponse)
def get_work_shift(id: int, db: Session = Depends(get_db)):
    db_shift = db.query(WorkShift).filter(WorkShift.id == id).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Work shift not found")
    return db_shift

@router.put("/{id}", response_model=WorkShiftResponse)
def update_work_shift(id: int, payload: WorkShiftUpdate, db: Session = Depends(get_db)):
    db_shift = db.query(WorkShift).filter(WorkShift.id == id).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Work shift not found")
    
    if payload.name is not None:
        db_shift.name = payload.name
    if payload.is_active is not None:
        db_shift.is_active = payload.is_active
    
    if payload.days is not None:
        # Simple implementation: delete and recreate day rules
        db.query(WorkShiftDayRule).filter(WorkShiftDayRule.work_shift_id == id).delete()
        for day_data in payload.days:
            day_rule = WorkShiftDayRule(
                work_shift_id=id,
                **day_data.model_dump()
            )
            db.add(day_rule)
            
    db.commit()
    db.refresh(db_shift)
    return db_shift

@router.delete("/{id}")
def delete_work_shift(id: int, db: Session = Depends(get_db)):
    db_shift = db.query(WorkShift).filter(WorkShift.id == id).first()
    if not db_shift:
        raise HTTPException(status_code=404, detail="Work shift not found")
    db_shift.is_active = False
    db.commit()
    return {"message": "Work shift deactivated"}
