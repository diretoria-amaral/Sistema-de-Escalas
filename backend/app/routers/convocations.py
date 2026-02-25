from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime

from app.database import get_db
from app.models.convocation import Convocation, ConvocationStatus
from app.models.employee import Employee
from app.models.sector import Sector
from app.models.governance_activity import GovernanceActivity
from app.services.convocation_service import ConvocationService
from app.schemas.convocation import (
    ConvocationCreate, ConvocationResponse, ConvocationAcceptDecline,
    ConvocationCancel, GenerateConvocationsRequest, GenerateConvocationsResponse,
    ConvocationStats, RescheduleResult
)

router = APIRouter(prefix="/api/convocations", tags=["convocations"])


def _convocation_to_response(conv: Convocation, db: Session) -> dict:
    employee = db.query(Employee).filter(Employee.id == conv.employee_id).first()
    sector = db.query(Sector).filter(Sector.id == conv.sector_id).first()
    activity = None
    if conv.activity_id:
        activity = db.query(GovernanceActivity).filter(GovernanceActivity.id == conv.activity_id).first()
    
    return {
        "id": conv.id,
        "employee_id": conv.employee_id,
        "sector_id": conv.sector_id,
        "activity_id": conv.activity_id,
        "daily_shift_id": conv.daily_shift_id,
        "weekly_schedule_id": conv.weekly_schedule_id,
        "forecast_run_id": conv.forecast_run_id,
        "date": conv.date,
        "start_time": conv.start_time,
        "end_time": conv.end_time,
        "break_minutes": conv.break_minutes,
        "total_hours": conv.total_hours,
        "status": conv.status.value,
        "generated_from": conv.generated_from.value,
        "sent_at": conv.sent_at,
        "response_deadline": conv.response_deadline,
        "responded_at": conv.responded_at,
        "operational_justification": conv.operational_justification,
        "decline_reason": conv.decline_reason,
        "response_notes": conv.response_notes,
        "replaced_convocation_id": conv.replaced_convocation_id,
        "replacement_convocation_id": conv.replacement_convocation_id,
        "legal_validation_passed": conv.legal_validation_passed,
        "legal_validation_errors": conv.legal_validation_errors,
        "legal_validation_warnings": conv.legal_validation_warnings,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
        "employee_name": employee.name if employee else None,
        "sector_name": sector.name if sector else None,
        "activity_name": activity.name if activity else None
    }


@router.get("/", response_model=List[dict])
def list_convocations(
    sector_id: Optional[int] = Query(None),
    employee_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    week_start: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Convocation)
    
    if sector_id:
        query = query.filter(Convocation.sector_id == sector_id)
    if employee_id:
        query = query.filter(Convocation.employee_id == employee_id)
    if status:
        try:
            status_enum = ConvocationStatus(status)
            query = query.filter(Convocation.status == status_enum)
        except ValueError:
            pass
    if date_from:
        query = query.filter(Convocation.date >= date_from)
    if date_to:
        query = query.filter(Convocation.date <= date_to)
    if week_start:
        from datetime import timedelta
        week_end = week_start + timedelta(days=6)
        query = query.filter(Convocation.date >= week_start, Convocation.date <= week_end)
    
    convocations = query.order_by(Convocation.date.desc(), Convocation.created_at.desc()).all()
    
    return [_convocation_to_response(c, db) for c in convocations]


@router.get("/stats", response_model=ConvocationStats)
def get_stats(
    sector_id: Optional[int] = Query(None),
    week_start: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    service = ConvocationService(db)
    return service.get_convocation_stats(sector_id=sector_id, week_start=week_start)


@router.get("/{convocation_id}", response_model=dict)
def get_convocation(convocation_id: int, db: Session = Depends(get_db)):
    convocation = db.query(Convocation).filter(Convocation.id == convocation_id).first()
    if not convocation:
        raise HTTPException(status_code=404, detail="Convocação não encontrada")
    return _convocation_to_response(convocation, db)


@router.post("/", response_model=dict)
def create_convocation(data: ConvocationCreate, db: Session = Depends(get_db)):
    service = ConvocationService(db)
    
    from app.models.convocation import ConvocationOrigin
    origin_map = {
        "baseline": ConvocationOrigin.BASELINE,
        "ajuste": ConvocationOrigin.ADJUSTMENT,
        "reescala": ConvocationOrigin.RESCHEDULE,
        "manual": ConvocationOrigin.MANUAL
    }
    generated_from = origin_map.get(data.generated_from.value, ConvocationOrigin.MANUAL)
    
    convocation, validation = service.create_convocation(
        employee_id=data.employee_id,
        sector_id=data.sector_id,
        conv_date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        total_hours=data.total_hours,
        response_deadline=data.response_deadline,
        activity_id=data.activity_id,
        daily_shift_id=data.daily_shift_id,
        weekly_schedule_id=data.weekly_schedule_id,
        forecast_run_id=data.forecast_run_id,
        generated_from=generated_from,
        break_minutes=data.break_minutes,
        operational_justification=data.operational_justification
    )
    
    if not convocation:
        raise HTTPException(status_code=400, detail={
            "message": "Não foi possível criar convocação",
            "validation": validation
        })
    
    db.commit()
    return _convocation_to_response(convocation, db)


@router.post("/{convocation_id}/respond", response_model=dict)
def respond_to_convocation(
    convocation_id: int,
    data: ConvocationAcceptDecline,
    db: Session = Depends(get_db)
):
    service = ConvocationService(db)
    
    if data.action == "accept":
        result = service.accept_convocation(
            convocation_id=convocation_id,
            response_notes=data.response_notes
        )
    else:
        result = service.decline_convocation(
            convocation_id=convocation_id,
            decline_reason=data.decline_reason,
            response_notes=data.response_notes,
            auto_reschedule=True
        )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    response = _convocation_to_response(result["convocation"], db)
    
    if "reschedule_result" in result and result["reschedule_result"]:
        response["reschedule_result"] = result["reschedule_result"]
    
    return response


@router.post("/{convocation_id}/cancel", response_model=dict)
def cancel_convocation(
    convocation_id: int,
    data: ConvocationCancel,
    db: Session = Depends(get_db)
):
    service = ConvocationService(db)
    result = service.cancel_convocation(
        convocation_id=convocation_id,
        cancellation_reason=data.cancellation_reason
    )
    
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return _convocation_to_response(result["convocation"], db)


@router.post("/generate-from-schedule", response_model=GenerateConvocationsResponse)
def generate_from_schedule(
    data: GenerateConvocationsRequest,
    db: Session = Depends(get_db)
):
    service = ConvocationService(db)
    result = service.generate_convocations_from_schedule(
        weekly_schedule_id=data.weekly_schedule_id,
        response_deadline_hours=data.response_deadline_hours
    )
    return result


@router.post("/expire-pending", response_model=dict)
def expire_pending_convocations(db: Session = Depends(get_db)):
    service = ConvocationService(db)
    result = service.expire_pending_convocations()
    return result


@router.post("/{convocation_id}/reschedule", response_model=RescheduleResult)
def trigger_manual_reschedule(convocation_id: int, db: Session = Depends(get_db)):
    convocation = db.query(Convocation).filter(Convocation.id == convocation_id).first()
    if not convocation:
        raise HTTPException(status_code=404, detail="Convocação não encontrada")
    
    if convocation.status not in [ConvocationStatus.DECLINED, ConvocationStatus.EXPIRED, ConvocationStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Apenas convocações recusadas, expiradas ou canceladas podem ser reescaladas")
    
    service = ConvocationService(db)
    result = service.trigger_reschedule(convocation)
    db.commit()
    return result


@router.get("/employee/{employee_id}/history", response_model=List[dict])
def get_employee_convocation_history(
    employee_id: int,
    limit: int = Query(50, le=100),
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado")
    
    convocations = db.query(Convocation).filter(
        Convocation.employee_id == employee_id
    ).order_by(Convocation.date.desc()).limit(limit).all()
    
    return [_convocation_to_response(c, db) for c in convocations]


@router.post("/validate", response_model=dict)
def validate_convocation(data: ConvocationCreate, db: Session = Depends(get_db)):
    service = ConvocationService(db)
    
    validation = service.validate_convocation(
        employee_id=data.employee_id,
        sector_id=data.sector_id,
        conv_date=data.date,
        start_time=data.start_time,
        end_time=data.end_time,
        total_hours=data.total_hours
    )
    
    return validation
