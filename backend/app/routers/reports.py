import os
import io
import csv
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.database import get_db
from app.models.report_type import ReportType
from app.models.report_upload import ReportUpload, UploadStatus
from app.models.occupancy_data import OccupancyForecast, OccupancyActual
from app.models.audit_log import AuditLog, AuditAction
from app.models.convocation import Convocation, ConvocationStatus, ConvocationOrigin
from app.models.employee import Employee
from app.models.sector import Sector
from app.models.governance_activity import GovernanceActivity
from app.models.weekly_schedule import WeeklySchedule
from app.models.daily_shift import DailyShift
from app.models.rules import SectorOperationalRules
from app.schemas.report import (
    ReportTypeCreate, ReportTypeUpdate, ReportTypeResponse,
    ReportUploadResponse, ReportUploadListResponse,
    OccupancyForecastCreate, OccupancyForecastResponse,
    OccupancyActualCreate, OccupancyActualResponse
)
from app.datalayer import ReportProcessor
report_processor = ReportProcessor()

router = APIRouter(prefix="/reports", tags=["Reports"])

UPLOAD_DIR = "uploads/reports"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "xlsx", "xls", "csv"}


def get_file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@router.get("/types", response_model=List[ReportTypeResponse])
def list_report_types(
    is_active: Optional[bool] = True,
    db: Session = Depends(get_db)
):
    query = db.query(ReportType)
    if is_active is not None:
        query = query.filter(ReportType.is_active == is_active)
    return query.all()


@router.post("/types", response_model=ReportTypeResponse)
def create_report_type(report_type: ReportTypeCreate, db: Session = Depends(get_db)):
    existing = db.query(ReportType).filter(ReportType.name == report_type.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Report type with this name already exists")
    
    db_report_type = ReportType(**report_type.model_dump())
    db.add(db_report_type)
    db.commit()
    db.refresh(db_report_type)
    
    audit = AuditLog(
        action=AuditAction.SETTINGS_CHANGE,
        entity_type="report_type",
        entity_id=db_report_type.id,
        description=f"Created report type: {report_type.name}",
        new_values=report_type.model_dump()
    )
    db.add(audit)
    db.commit()
    
    return db_report_type


@router.put("/types/{type_id}", response_model=ReportTypeResponse)
def update_report_type(type_id: int, report_type: ReportTypeUpdate, db: Session = Depends(get_db)):
    db_type = db.query(ReportType).filter(ReportType.id == type_id).first()
    if not db_type:
        raise HTTPException(status_code=404, detail="Report type not found")
    
    old_values = {
        "name": db_type.name,
        "sectors": db_type.sectors,
        "indicators": db_type.indicators
    }
    
    update_data = report_type.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_type, key, value)
    
    audit = AuditLog(
        action=AuditAction.SETTINGS_CHANGE,
        entity_type="report_type",
        entity_id=type_id,
        description=f"Updated report type: {db_type.name}",
        old_values=old_values,
        new_values=update_data
    )
    db.add(audit)
    db.commit()
    db.refresh(db_type)
    
    return db_type


@router.get("/uploads", response_model=List[ReportUploadListResponse])
def list_uploads(
    status: Optional[UploadStatus] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(ReportUpload).order_by(desc(ReportUpload.created_at))
    
    if status:
        query = query.filter(ReportUpload.status == status)
    if date_from:
        query = query.filter(ReportUpload.date_start >= date_from)
    if date_to:
        query = query.filter(ReportUpload.date_end <= date_to)
    
    uploads = query.offset(skip).limit(limit).all()
    
    result = []
    for upload in uploads:
        report_type_name = None
        if upload.report_type:
            report_type_name = upload.report_type.name
        
        result.append(ReportUploadListResponse(
            id=upload.id,
            original_filename=upload.original_filename,
            file_type=upload.file_type,
            report_type_name=report_type_name,
            date_start=upload.date_start,
            date_end=upload.date_end,
            status=upload.status,
            sectors_affected=upload.sectors_affected or [],
            created_at=upload.created_at
        ))
    
    return result


@router.get("/uploads/{upload_id}", response_model=ReportUploadResponse)
def get_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(ReportUpload).filter(ReportUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    report_type_name = None
    if upload.report_type:
        report_type_name = upload.report_type.name
    
    return ReportUploadResponse(
        id=upload.id,
        filename=upload.filename,
        original_filename=upload.original_filename,
        file_type=upload.file_type,
        file_size=upload.file_size,
        report_type_id=upload.report_type_id,
        report_type_name=report_type_name,
        auto_detected=upload.auto_detected,
        detection_confidence=upload.detection_confidence,
        date_start=upload.date_start,
        date_end=upload.date_end,
        status=upload.status,
        processing_notes=upload.processing_notes,
        error_message=upload.error_message,
        indicators_found=upload.indicators_found or [],
        sectors_affected=upload.sectors_affected or [],
        uploaded_by=upload.uploaded_by,
        processed_at=upload.processed_at,
        created_at=upload.created_at
    )


@router.post("/upload")
async def upload_report(
    file: UploadFile = File(...),
    date_start: Optional[str] = Form(None),
    date_end: Optional[str] = Form(None),
    report_type_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    file_ext = get_file_extension(file.filename)
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    file_content = await file.read()
    file_size = len(file_content)
    
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    db_upload = ReportUpload(
        filename=unique_filename,
        original_filename=file.filename,
        file_path=file_path,
        file_type=file_ext,
        file_size=file_size,
        status=UploadStatus.PROCESSING
    )
    
    if date_start:
        try:
            db_upload.date_start = datetime.strptime(date_start, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    if date_end:
        try:
            db_upload.date_end = datetime.strptime(date_end, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    if report_type_id:
        report_type = db.query(ReportType).filter(ReportType.id == report_type_id).first()
        if report_type:
            db_upload.report_type_id = report_type_id
            db_upload.auto_detected = False
    
    db.add(db_upload)
    db.commit()
    db.refresh(db_upload)
    
    try:
        result = report_processor.process_file(file_content, file.filename, file_ext)
        
        if not db_upload.report_type_id and result["detected_type"] != "desconhecido":
            existing_type = db.query(ReportType).filter(
                ReportType.name == result["detected_type"]
            ).first()
            
            if existing_type:
                db_upload.report_type_id = existing_type.id
            else:
                new_type = ReportType(
                    name=result["detected_type"],
                    indicators=result["indicators"],
                    sectors=result["sectors"]
                )
                db.add(new_type)
                db.commit()
                db.refresh(new_type)
                db_upload.report_type_id = new_type.id
            
            db_upload.auto_detected = True
        
        db_upload.detection_confidence = result["confidence"]
        db_upload.indicators_found = result["indicators"]
        db_upload.sectors_affected = result["sectors"]
        
        if not db_upload.date_start and result["date_start"]:
            db_upload.date_start = result["date_start"]
        if not db_upload.date_end and result["date_end"]:
            db_upload.date_end = result["date_end"]
        
        if result["extracted_data"]:
            db_upload.extracted_data = result["extracted_data"]
            
            if "occupancy" in result["extracted_data"]:
                for occ_data in result["extracted_data"]["occupancy"]:
                    occ_date = occ_data.get("date")
                    if occ_date:
                        existing = db.query(OccupancyForecast).filter(
                            OccupancyForecast.date == occ_date
                        ).first()
                        
                        if not existing:
                            forecast = OccupancyForecast(
                                date=occ_date,
                                day_of_week=occ_date.weekday(),
                                occupancy_rate_forecast=occ_data.get("occupancy_rate"),
                                rooms_occupied_forecast=occ_data.get("rooms_occupied"),
                                arrivals_forecast=occ_data.get("arrivals", 0),
                                departures_forecast=occ_data.get("departures", 0),
                                source_report_id=db_upload.id
                            )
                            db.add(forecast)
        
        db_upload.status = UploadStatus.COMPLETED
        db_upload.processed_at = datetime.now()
        
    except Exception as e:
        db_upload.status = UploadStatus.FAILED
        db_upload.error_message = str(e)
    
    audit = AuditLog(
        action=AuditAction.REPORT_UPLOAD,
        entity_type="report_upload",
        entity_id=db_upload.id,
        description=f"Uploaded report: {file.filename}",
        new_values={
            "filename": file.filename,
            "file_type": file_ext,
            "status": db_upload.status.value
        }
    )
    db.add(audit)
    db.commit()
    db.refresh(db_upload)
    
    return {
        "id": db_upload.id,
        "status": db_upload.status.value,
        "detected_type": db_upload.report_type.name if db_upload.report_type else None,
        "auto_detected": db_upload.auto_detected,
        "confidence": db_upload.detection_confidence,
        "indicators_found": db_upload.indicators_found,
        "sectors_affected": db_upload.sectors_affected,
        "date_start": db_upload.date_start,
        "date_end": db_upload.date_end,
        "message": "Report processed successfully" if db_upload.status == UploadStatus.COMPLETED else db_upload.error_message
    }


@router.put("/uploads/{upload_id}/type")
def assign_report_type(
    upload_id: int,
    report_type_id: int,
    db: Session = Depends(get_db)
):
    upload = db.query(ReportUpload).filter(ReportUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    report_type = db.query(ReportType).filter(ReportType.id == report_type_id).first()
    if not report_type:
        raise HTTPException(status_code=404, detail="Report type not found")
    
    old_type_id = upload.report_type_id
    upload.report_type_id = report_type_id
    upload.auto_detected = False
    upload.sectors_affected = report_type.sectors
    upload.indicators_found = report_type.indicators
    
    audit = AuditLog(
        action=AuditAction.REPORT_PROCESS,
        entity_type="report_upload",
        entity_id=upload_id,
        description=f"Manually assigned report type: {report_type.name}",
        old_values={"report_type_id": old_type_id},
        new_values={"report_type_id": report_type_id}
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Report type assigned successfully"}


@router.delete("/uploads/{upload_id}")
def delete_upload(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(ReportUpload).filter(ReportUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload not found")
    
    if os.path.exists(upload.file_path):
        try:
            os.remove(upload.file_path)
        except Exception:
            pass
    
    db.delete(upload)
    db.commit()
    
    return {"message": "Upload deleted successfully"}


@router.get("/occupancy/forecasts", response_model=List[OccupancyForecastResponse])
def list_forecasts(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(OccupancyForecast).order_by(OccupancyForecast.date)
    
    if date_from:
        query = query.filter(OccupancyForecast.date >= date_from)
    if date_to:
        query = query.filter(OccupancyForecast.date <= date_to)
    
    return query.all()


@router.post("/occupancy/forecasts", response_model=OccupancyForecastResponse)
def create_forecast(forecast: OccupancyForecastCreate, db: Session = Depends(get_db)):
    existing = db.query(OccupancyForecast).filter(
        OccupancyForecast.date == forecast.date
    ).first()
    
    if existing:
        for key, value in forecast.model_dump().items():
            if value is not None:
                setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    
    db_forecast = OccupancyForecast(
        **forecast.model_dump(),
        day_of_week=forecast.date.weekday()
    )
    db.add(db_forecast)
    db.commit()
    db.refresh(db_forecast)
    return db_forecast


@router.get("/occupancy/actuals", response_model=List[OccupancyActualResponse])
def list_actuals(
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db)
):
    query = db.query(OccupancyActual).order_by(OccupancyActual.date)
    
    if date_from:
        query = query.filter(OccupancyActual.date >= date_from)
    if date_to:
        query = query.filter(OccupancyActual.date <= date_to)
    
    return query.all()


@router.post("/occupancy/actuals", response_model=OccupancyActualResponse)
def create_actual(actual: OccupancyActualCreate, db: Session = Depends(get_db)):
    existing = db.query(OccupancyActual).filter(
        OccupancyActual.date == actual.date
    ).first()
    
    if existing:
        for key, value in actual.model_dump().items():
            if value is not None:
                setattr(existing, key, value)
        db.commit()
        db.refresh(existing)
        return existing
    
    db_actual = OccupancyActual(
        **actual.model_dump(),
        day_of_week=actual.date.weekday()
    )
    db.add(db_actual)
    db.commit()
    db.refresh(db_actual)
    return db_actual


@router.get("/convocations/by-employee")
def get_convocations_by_employee(
    employee_id: Optional[int] = Query(None),
    sector_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Convocation).join(Employee)
    
    if employee_id:
        query = query.filter(Convocation.employee_id == employee_id)
    if sector_id:
        query = query.filter(Convocation.sector_id == sector_id)
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
    
    convocations = query.order_by(Convocation.date.desc()).all()
    
    total = len(convocations)
    accepted = sum(1 for c in convocations if c.status == ConvocationStatus.ACCEPTED)
    declined = sum(1 for c in convocations if c.status == ConvocationStatus.DECLINED)
    expired = sum(1 for c in convocations if c.status == ConvocationStatus.EXPIRED)
    
    acceptance_rate = (accepted / total * 100) if total > 0 else 0.0
    decline_rate = (declined / total * 100) if total > 0 else 0.0
    
    results = []
    for conv in convocations:
        employee = db.query(Employee).filter(Employee.id == conv.employee_id).first()
        sector = db.query(Sector).filter(Sector.id == conv.sector_id).first()
        activity = None
        if conv.activity_id:
            activity = db.query(GovernanceActivity).filter(GovernanceActivity.id == conv.activity_id).first()
        
        results.append({
            "id": conv.id,
            "date": conv.date,
            "employee_id": conv.employee_id,
            "employee_name": employee.name if employee else None,
            "sector_id": conv.sector_id,
            "sector_name": sector.name if sector else None,
            "activity_name": activity.name if activity else None,
            "start_time": conv.start_time.isoformat() if conv.start_time else None,
            "end_time": conv.end_time.isoformat() if conv.end_time else None,
            "total_hours": conv.total_hours,
            "status": conv.status.value,
            "generated_from": conv.generated_from.value if conv.generated_from else None,
            "response_deadline": conv.response_deadline.isoformat() if conv.response_deadline else None,
            "responded_at": conv.responded_at.isoformat() if conv.responded_at else None,
            "decline_reason": conv.decline_reason,
            "replaced_convocation_id": conv.replaced_convocation_id,
            "replacement_convocation_id": conv.replacement_convocation_id
        })
    
    return {
        "summary": {
            "total": total,
            "accepted": accepted,
            "declined": declined,
            "expired": expired,
            "acceptance_rate": round(acceptance_rate, 1),
            "decline_rate": round(decline_rate, 1)
        },
        "convocations": results
    }


@router.get("/convocations/by-sector")
def get_convocations_by_sector(
    sector_id: int = Query(...),
    week_start: Optional[date] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Convocation).filter(Convocation.sector_id == sector_id)
    
    if week_start:
        week_end = week_start + timedelta(days=6)
        query = query.filter(
            Convocation.date >= week_start,
            Convocation.date <= week_end
        )
    if date_from:
        query = query.filter(Convocation.date >= date_from)
    if date_to:
        query = query.filter(Convocation.date <= date_to)
    
    convocations = query.order_by(Convocation.date).all()
    
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    
    total_convocations = len(convocations)
    total_hours_convoked = sum(c.total_hours or 0 for c in convocations)
    accepted_hours = sum(c.total_hours or 0 for c in convocations if c.status == ConvocationStatus.ACCEPTED)
    declined_hours = sum(c.total_hours or 0 for c in convocations if c.status == ConvocationStatus.DECLINED)
    
    daily_breakdown = {}
    for conv in convocations:
        day_key = conv.date.isoformat()
        if day_key not in daily_breakdown:
            daily_breakdown[day_key] = {
                "date": conv.date,
                "total_convocations": 0,
                "hours_convoked": 0,
                "hours_accepted": 0,
                "hours_declined": 0,
                "pending": 0,
                "accepted": 0,
                "declined": 0,
                "expired": 0
            }
        
        daily_breakdown[day_key]["total_convocations"] += 1
        daily_breakdown[day_key]["hours_convoked"] += conv.total_hours or 0
        
        if conv.status == ConvocationStatus.ACCEPTED:
            daily_breakdown[day_key]["hours_accepted"] += conv.total_hours or 0
            daily_breakdown[day_key]["accepted"] += 1
        elif conv.status == ConvocationStatus.DECLINED:
            daily_breakdown[day_key]["hours_declined"] += conv.total_hours or 0
            daily_breakdown[day_key]["declined"] += 1
        elif conv.status == ConvocationStatus.PENDING:
            daily_breakdown[day_key]["pending"] += 1
        elif conv.status == ConvocationStatus.EXPIRED:
            daily_breakdown[day_key]["expired"] += 1
    
    return {
        "sector_id": sector_id,
        "sector_name": sector.name if sector else None,
        "summary": {
            "total_convocations": total_convocations,
            "total_hours_convoked": round(total_hours_convoked, 1),
            "hours_accepted": round(accepted_hours, 1),
            "hours_declined": round(declined_hours, 1)
        },
        "daily_breakdown": list(daily_breakdown.values())
    }


@router.get("/planned-vs-executed")
def get_planned_vs_executed(
    sector_id: int = Query(...),
    week_start: date = Query(...),
    db: Session = Depends(get_db)
):
    week_end = week_start + timedelta(days=6)
    
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")
    
    schedules = db.query(WeeklySchedule).filter(
        WeeklySchedule.sector_id == sector_id,
        WeeklySchedule.week_start == week_start
    ).all()
    
    shifts = []
    for schedule in schedules:
        shifts.extend(
            db.query(DailyShift).filter(
                DailyShift.weekly_schedule_id == schedule.id
            ).all()
        )
    
    convocations = db.query(Convocation).filter(
        Convocation.sector_id == sector_id,
        Convocation.date >= week_start,
        Convocation.date <= week_end
    ).all()
    
    daily_data = {}
    current_date = week_start
    while current_date <= week_end:
        day_key = current_date.isoformat()
        day_shifts = [s for s in shifts if s.date == current_date]
        day_convocations = [c for c in convocations if c.date == current_date]
        
        planned_hours = sum(s.planned_hours or 0 for s in day_shifts)
        convoked_hours = sum(c.total_hours or 0 for c in day_convocations)
        accepted_hours = sum(c.total_hours or 0 for c in day_convocations if c.status == ConvocationStatus.ACCEPTED)
        declined_hours = sum(c.total_hours or 0 for c in day_convocations if c.status == ConvocationStatus.DECLINED)
        
        deficit = planned_hours - accepted_hours
        
        deviation_reasons = []
        if declined_hours > 0:
            deviation_reasons.append(f"Recusas: {declined_hours:.1f}h")
        adjustment_convs = [c for c in day_convocations if c.generated_from == ConvocationOrigin.ADJUSTMENT]
        if adjustment_convs:
            deviation_reasons.append(f"Ajustes: {len(adjustment_convs)}")
        
        weekday_names = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
        
        daily_data[day_key] = {
            "date": current_date,
            "weekday": weekday_names[current_date.weekday()],
            "planned_hours": round(planned_hours, 1),
            "convoked_hours": round(convoked_hours, 1),
            "accepted_hours": round(accepted_hours, 1),
            "declined_hours": round(declined_hours, 1),
            "deficit": round(max(0, deficit), 1),
            "surplus": round(max(0, -deficit), 1),
            "deviation_reasons": deviation_reasons
        }
        current_date += timedelta(days=1)
    
    total_planned = sum(d["planned_hours"] for d in daily_data.values())
    total_convoked = sum(d["convoked_hours"] for d in daily_data.values())
    total_accepted = sum(d["accepted_hours"] for d in daily_data.values())
    total_declined = sum(d["declined_hours"] for d in daily_data.values())
    
    return {
        "sector_id": sector_id,
        "sector_name": sector.name,
        "week_start": week_start,
        "week_end": week_end,
        "summary": {
            "total_planned_hours": round(total_planned, 1),
            "total_convoked_hours": round(total_convoked, 1),
            "total_accepted_hours": round(total_accepted, 1),
            "total_declined_hours": round(total_declined, 1),
            "execution_rate": round((total_accepted / total_planned * 100) if total_planned > 0 else 0, 1)
        },
        "daily_breakdown": list(daily_data.values())
    }


@router.get("/forecast-accuracy")
def get_forecast_accuracy(
    sector_id: Optional[int] = Query(None),
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db)
):
    from app.models.data_lake import OccupancySnapshot
    
    results = []
    current_date = date_from
    weekday_names = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
    
    while current_date <= date_to:
        forecasts = db.query(OccupancySnapshot).filter(
            OccupancySnapshot.target_date == current_date,
            OccupancySnapshot.origin == 'forecast'
        ).order_by(OccupancySnapshot.generated_at.desc()).first()
        
        actuals = db.query(OccupancySnapshot).filter(
            OccupancySnapshot.target_date == current_date,
            OccupancySnapshot.origin == 'real'
        ).order_by(OccupancySnapshot.generated_at.desc()).first()
        
        forecast_pct = forecasts.occupancy_pct if forecasts else None
        actual_pct = actuals.occupancy_pct if actuals else None
        
        error_pct = None
        if forecast_pct is not None and actual_pct is not None:
            error_pct = actual_pct - forecast_pct
        
        results.append({
            "date": current_date,
            "weekday": weekday_names[current_date.weekday()],
            "weekday_num": current_date.weekday(),
            "forecast_occupancy": round(forecast_pct, 1) if forecast_pct else None,
            "actual_occupancy": round(actual_pct, 1) if actual_pct else None,
            "error_pct": round(error_pct, 1) if error_pct is not None else None
        })
        
        current_date += timedelta(days=1)
    
    weekday_errors = {}
    for r in results:
        if r["error_pct"] is not None:
            wd = r["weekday_num"]
            if wd not in weekday_errors:
                weekday_errors[wd] = []
            weekday_errors[wd].append(abs(r["error_pct"]))
    
    weekday_mae = {}
    for wd, errors in weekday_errors.items():
        weekday_mae[weekday_names[wd]] = round(sum(errors) / len(errors), 1) if errors else None
    
    all_errors = [r["error_pct"] for r in results if r["error_pct"] is not None]
    overall_mae = round(sum(abs(e) for e in all_errors) / len(all_errors), 1) if all_errors else None
    
    return {
        "period": {
            "date_from": date_from,
            "date_to": date_to
        },
        "summary": {
            "overall_mae": overall_mae,
            "weekday_mae": weekday_mae,
            "total_days_with_data": len([r for r in results if r["error_pct"] is not None])
        },
        "daily_data": results
    }


@router.get("/sector-indicators")
def get_sector_indicators(
    sector_id: int = Query(...),
    week_start: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor nao encontrado")
    
    op_rules = db.query(SectorOperationalRules).filter(
        SectorOperationalRules.sector_id == sector_id,
        SectorOperationalRules.is_active == True
    ).first()
    
    query = db.query(Convocation).filter(Convocation.sector_id == sector_id)
    if week_start:
        week_end = week_start + timedelta(days=6)
        query = query.filter(
            Convocation.date >= week_start,
            Convocation.date <= week_end
        )
    
    convocations = query.all()
    
    total_hours_convoked = sum(c.total_hours or 0 for c in convocations)
    accepted_hours = sum(c.total_hours or 0 for c in convocations if c.status == ConvocationStatus.ACCEPTED)
    
    utilization_target = op_rules.utilization_target_pct if op_rules else 85.0
    actual_utilization = (accepted_hours / total_hours_convoked * 100) if total_hours_convoked > 0 else 0
    
    productivity_params = op_rules.productivity_params_json if op_rules else {}
    rooms_per_hour = productivity_params.get("rooms_per_hour", 2.5) if productivity_params else 2.5
    
    buffer_pct = op_rules.buffer_pct if op_rules else 10.0
    estimated_unproductive = total_hours_convoked * (buffer_pct / 100)
    
    return {
        "sector_id": sector_id,
        "sector_name": sector.name,
        "period": {
            "week_start": week_start
        },
        "indicators": {
            "average_productivity_rooms_hour": rooms_per_hour,
            "utilization_target_pct": utilization_target,
            "actual_utilization_pct": round(actual_utilization, 1),
            "utilization_gap_pct": round(utilization_target - actual_utilization, 1),
            "estimated_unproductive_hours": round(estimated_unproductive, 1),
            "total_hours_convoked": round(total_hours_convoked, 1),
            "total_hours_accepted": round(accepted_hours, 1)
        },
        "operational_rules": {
            "buffer_pct": buffer_pct,
            "alternancia_horarios": op_rules.alternancia_horarios if op_rules else False,
            "modo_conservador": op_rules.modo_conservador if op_rules else False
        }
    }


@router.get("/employee-legal-timeline")
def get_employee_legal_timeline(
    employee_id: int = Query(...),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador nao encontrado")
    
    query = db.query(Convocation).filter(Convocation.employee_id == employee_id)
    if date_from:
        query = query.filter(Convocation.date >= date_from)
    if date_to:
        query = query.filter(Convocation.date <= date_to)
    
    convocations = query.order_by(Convocation.date.desc(), Convocation.created_at.desc()).all()
    
    timeline = []
    for conv in convocations:
        sector = db.query(Sector).filter(Sector.id == conv.sector_id).first()
        
        advance_hours = None
        if conv.sent_at and conv.start_time and conv.date:
            shift_start = datetime.combine(conv.date, conv.start_time)
            advance_hours = (shift_start - conv.sent_at).total_seconds() / 3600
        
        entry = {
            "convocation_id": conv.id,
            "date": conv.date,
            "sector_name": sector.name if sector else None,
            "start_time": conv.start_time.isoformat() if conv.start_time else None,
            "end_time": conv.end_time.isoformat() if conv.end_time else None,
            "total_hours": conv.total_hours,
            "status": conv.status.value,
            "generated_from": conv.generated_from.value if conv.generated_from else None,
            "legal_compliance": {
                "sent_at": conv.sent_at.isoformat() if conv.sent_at else None,
                "response_deadline": conv.response_deadline.isoformat() if conv.response_deadline else None,
                "responded_at": conv.responded_at.isoformat() if conv.responded_at else None,
                "advance_hours": round(advance_hours, 1) if advance_hours else None,
                "met_72h_requirement": advance_hours >= 72 if advance_hours else None,
                "validation_passed": conv.legal_validation_passed,
                "validation_errors": conv.legal_validation_errors,
                "validation_warnings": conv.legal_validation_warnings
            },
            "replacement_chain": {
                "replaced_convocation_id": conv.replaced_convocation_id,
                "replacement_convocation_id": conv.replacement_convocation_id
            },
            "response": {
                "decline_reason": conv.decline_reason,
                "response_notes": conv.response_notes
            }
        }
        timeline.append(entry)
    
    audit_events = db.query(AuditLog).filter(
        AuditLog.entity_type == "convocation",
        AuditLog.entity_id.in_([c.id for c in convocations])
    ).order_by(AuditLog.created_at.desc()).all()
    
    audit_timeline = []
    for event in audit_events:
        audit_timeline.append({
            "timestamp": event.created_at.isoformat() if event.created_at else None,
            "action": event.action.value if event.action else None,
            "entity_id": event.entity_id,
            "description": event.description,
            "user_id": event.user_id
        })
    
    return {
        "employee_id": employee_id,
        "employee_name": employee.name,
        "contract_type": employee.contract_type.value if employee.contract_type else None,
        "sector_name": employee.sector.name if employee.sector else None,
        "summary": {
            "total_convocations": len(convocations),
            "accepted": sum(1 for c in convocations if c.status == ConvocationStatus.ACCEPTED),
            "declined": sum(1 for c in convocations if c.status == ConvocationStatus.DECLINED),
            "expired": sum(1 for c in convocations if c.status == ConvocationStatus.EXPIRED),
            "legal_violations": sum(1 for c in convocations if not c.legal_validation_passed)
        },
        "convocation_timeline": timeline,
        "audit_events": audit_timeline
    }


@router.get("/audit-log")
def get_audit_log_report(
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    user_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog)
    
    if action:
        try:
            action_enum = AuditAction(action)
            query = query.filter(AuditLog.action == action_enum)
        except ValueError:
            pass
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if user_id:
        query = query.filter(AuditLog.user_id == user_id)
    if date_from:
        query = query.filter(func.date(AuditLog.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(AuditLog.created_at) <= date_to)
    
    total = query.count()
    
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    
    results = []
    for log in logs:
        results.append({
            "id": log.id,
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "action": log.action.value if log.action else None,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "description": log.description,
            "user_id": log.user_id,
            "old_values": log.old_values,
            "new_values": log.new_values
        })
    
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": results
    }


@router.get("/export/convocations-excel")
def export_convocations_excel(
    employee_id: Optional[int] = Query(None),
    sector_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    import pandas as pd
    
    data = get_convocations_by_employee(
        employee_id=employee_id,
        sector_id=sector_id,
        date_from=date_from,
        date_to=date_to,
        db=db
    )
    
    df = pd.DataFrame(data["convocations"])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df = pd.DataFrame([data["summary"]])
        summary_df.to_excel(writer, sheet_name='Resumo', index=False)
        
        df.to_excel(writer, sheet_name='Convocacoes', index=False)
    
    output.seek(0)
    
    filename = f"convocacoes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/planned-vs-executed-excel")
def export_planned_vs_executed_excel(
    sector_id: int = Query(...),
    week_start: date = Query(...),
    db: Session = Depends(get_db)
):
    import pandas as pd
    
    data = get_planned_vs_executed(sector_id=sector_id, week_start=week_start, db=db)
    
    df = pd.DataFrame(data["daily_breakdown"])
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary_df = pd.DataFrame([{
            "Setor": data["sector_name"],
            "Semana": str(data["week_start"]),
            **data["summary"]
        }])
        summary_df.to_excel(writer, sheet_name='Resumo', index=False)
        
        df.to_excel(writer, sheet_name='Diario', index=False)
    
    output.seek(0)
    
    filename = f"planejado_executado_{sector_id}_{week_start}.xlsx"
    
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/export/audit-log-csv")
def export_audit_log_csv(
    action: Optional[str] = Query(None),
    entity_type: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    data = get_audit_log_report(
        action=action,
        entity_type=entity_type,
        date_from=date_from,
        date_to=date_to,
        limit=10000,
        db=db
    )
    
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "id", "timestamp", "action", "entity_type", "entity_id", 
        "description", "user_id", "old_values", "new_values"
    ])
    writer.writeheader()
    for log in data["logs"]:
        writer.writerow(log)
    
    output.seek(0)
    
    filename = f"audit_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
