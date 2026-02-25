from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import date
from app.database import get_db
from app.models.operational_calendar import OperationalCalendar, HolidayType, CalendarScope
from app.models.sector import Sector
from app.models.audit_log import AuditLog, AuditAction
from app.schemas.calendar import (
    CalendarEventCreate, CalendarEventUpdate, CalendarEventResponse, CalendarFactors
)

router = APIRouter(prefix="/calendar", tags=["Operational Calendar"])


def create_audit_log(db: Session, action: AuditAction, entity_id: int, description: str, new_values: dict = None, old_values: dict = None):
    audit = AuditLog(
        action=action,
        entity_type="operational_calendar",
        entity_id=entity_id,
        description=description,
        new_values=new_values,
        old_values=old_values
    )
    db.add(audit)


@router.get("/", response_model=List[CalendarEventResponse])
def list_calendar_events(
    year: Optional[int] = None,
    month: Optional[int] = None,
    sector_id: Optional[int] = None,
    holiday_type: Optional[HolidayType] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(OperationalCalendar)
    
    if year:
        from sqlalchemy import extract
        query = query.filter(extract('year', OperationalCalendar.date) == year)
    
    if month:
        from sqlalchemy import extract
        query = query.filter(extract('month', OperationalCalendar.date) == month)
    
    if sector_id:
        query = query.filter(
            or_(
                OperationalCalendar.scope == CalendarScope.GLOBAL,
                OperationalCalendar.sector_id == sector_id
            )
        )
    
    if holiday_type:
        query = query.filter(OperationalCalendar.holiday_type == holiday_type)
    
    if start_date:
        query = query.filter(OperationalCalendar.date >= start_date)
    
    if end_date:
        query = query.filter(OperationalCalendar.date <= end_date)
    
    events = query.order_by(OperationalCalendar.date).all()
    
    result = []
    for event in events:
        sector_name = None
        if event.sector_id:
            sector = db.query(Sector).filter(Sector.id == event.sector_id).first()
            sector_name = sector.name if sector else None
        
        result.append(CalendarEventResponse(
            id=event.id,
            date=event.date,
            name=event.name,
            holiday_type=event.holiday_type,
            scope=event.scope,
            sector_id=event.sector_id,
            productivity_factor=event.productivity_factor,
            demand_factor=event.demand_factor,
            block_convocations=event.block_convocations,
            notes=event.notes,
            created_at=event.created_at,
            updated_at=event.updated_at,
            sector_name=sector_name
        ))
    
    return result


@router.get("/factors/{target_date}")
def get_calendar_factors(
    target_date: date,
    sector_id: Optional[int] = None,
    db: Session = Depends(get_db)
) -> CalendarFactors:
    events = db.query(OperationalCalendar).filter(
        OperationalCalendar.date == target_date
    ).all()
    
    productivity_factor = 1.0
    demand_factor = 1.0
    block_convocations = False
    applied_events = []
    
    global_events = [e for e in events if e.scope == CalendarScope.GLOBAL]
    for event in global_events:
        productivity_factor *= event.productivity_factor
        demand_factor *= event.demand_factor
        if event.block_convocations:
            block_convocations = True
        applied_events.append(f"{event.name} (Global)")
    
    if sector_id:
        sector_events = [e for e in events if e.scope == CalendarScope.SECTOR and e.sector_id == sector_id]
        for event in sector_events:
            productivity_factor *= event.productivity_factor
            demand_factor *= event.demand_factor
            if event.block_convocations:
                block_convocations = True
            applied_events.append(f"{event.name} (Setor)")
    
    return CalendarFactors(
        productivity_factor=round(productivity_factor, 4),
        demand_factor=round(demand_factor, 4),
        block_convocations=block_convocations,
        applied_events=applied_events
    )


@router.get("/{event_id}", response_model=CalendarEventResponse)
def get_calendar_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(OperationalCalendar).filter(OperationalCalendar.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    
    sector_name = None
    if event.sector_id:
        sector = db.query(Sector).filter(Sector.id == event.sector_id).first()
        sector_name = sector.name if sector else None
    
    return CalendarEventResponse(
        id=event.id,
        date=event.date,
        name=event.name,
        holiday_type=event.holiday_type,
        scope=event.scope,
        sector_id=event.sector_id,
        productivity_factor=event.productivity_factor,
        demand_factor=event.demand_factor,
        block_convocations=event.block_convocations,
        notes=event.notes,
        created_at=event.created_at,
        updated_at=event.updated_at,
        sector_name=sector_name
    )


@router.post("/", response_model=CalendarEventResponse)
def create_calendar_event(event: CalendarEventCreate, db: Session = Depends(get_db)):
    if event.scope == CalendarScope.SECTOR and not event.sector_id:
        raise HTTPException(status_code=400, detail="sector_id is required when scope is SECTOR")
    
    if event.scope == CalendarScope.GLOBAL and event.sector_id:
        raise HTTPException(status_code=400, detail="sector_id must be null when scope is GLOBAL")
    
    if event.sector_id:
        sector = db.query(Sector).filter(Sector.id == event.sector_id).first()
        if not sector:
            raise HTTPException(status_code=404, detail="Sector not found")
    
    db_event = OperationalCalendar(**event.model_dump())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    
    create_audit_log(
        db, AuditAction.CALENDAR_EVENT_CREATED, db_event.id,
        f"Created calendar event: {event.name} on {event.date}",
        new_values=event.model_dump(mode='json')
    )
    db.commit()
    
    sector_name = None
    if db_event.sector_id:
        sector = db.query(Sector).filter(Sector.id == db_event.sector_id).first()
        sector_name = sector.name if sector else None
    
    return CalendarEventResponse(
        id=db_event.id,
        date=db_event.date,
        name=db_event.name,
        holiday_type=db_event.holiday_type,
        scope=db_event.scope,
        sector_id=db_event.sector_id,
        productivity_factor=db_event.productivity_factor,
        demand_factor=db_event.demand_factor,
        block_convocations=db_event.block_convocations,
        notes=db_event.notes,
        created_at=db_event.created_at,
        updated_at=db_event.updated_at,
        sector_name=sector_name
    )


@router.put("/{event_id}", response_model=CalendarEventResponse)
def update_calendar_event(event_id: int, event: CalendarEventUpdate, db: Session = Depends(get_db)):
    db_event = db.query(OperationalCalendar).filter(OperationalCalendar.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    
    old_values = {
        "date": str(db_event.date),
        "name": db_event.name,
        "holiday_type": db_event.holiday_type.value if db_event.holiday_type else None,
        "scope": db_event.scope.value if db_event.scope else None,
        "sector_id": db_event.sector_id,
        "productivity_factor": db_event.productivity_factor,
        "demand_factor": db_event.demand_factor,
        "block_convocations": db_event.block_convocations
    }
    
    update_data = event.model_dump(exclude_unset=True)
    
    new_scope = update_data.get('scope', db_event.scope)
    new_sector_id = update_data.get('sector_id', db_event.sector_id)
    
    if new_scope == CalendarScope.SECTOR and not new_sector_id:
        raise HTTPException(status_code=400, detail="sector_id is required when scope is SECTOR")
    
    if new_scope == CalendarScope.GLOBAL and 'sector_id' not in update_data:
        update_data['sector_id'] = None
    
    for key, value in update_data.items():
        setattr(db_event, key, value)
    
    db.commit()
    db.refresh(db_event)
    
    create_audit_log(
        db, AuditAction.CALENDAR_EVENT_UPDATED, db_event.id,
        f"Updated calendar event: {db_event.name}",
        new_values=update_data,
        old_values=old_values
    )
    db.commit()
    
    sector_name = None
    if db_event.sector_id:
        sector = db.query(Sector).filter(Sector.id == db_event.sector_id).first()
        sector_name = sector.name if sector else None
    
    return CalendarEventResponse(
        id=db_event.id,
        date=db_event.date,
        name=db_event.name,
        holiday_type=db_event.holiday_type,
        scope=db_event.scope,
        sector_id=db_event.sector_id,
        productivity_factor=db_event.productivity_factor,
        demand_factor=db_event.demand_factor,
        block_convocations=db_event.block_convocations,
        notes=db_event.notes,
        created_at=db_event.created_at,
        updated_at=db_event.updated_at,
        sector_name=sector_name
    )


@router.delete("/{event_id}")
def delete_calendar_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(OperationalCalendar).filter(OperationalCalendar.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    
    event_name = db_event.name
    event_date = str(db_event.date)
    
    create_audit_log(
        db, AuditAction.CALENDAR_EVENT_DELETED, event_id,
        f"Deleted calendar event: {event_name} on {event_date}",
        old_values={"name": event_name, "date": event_date}
    )
    
    db.delete(db_event)
    db.commit()
    
    return {"message": "Calendar event deleted successfully"}
