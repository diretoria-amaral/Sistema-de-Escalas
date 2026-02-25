from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Optional, List, Dict
from datetime import date, datetime
import hashlib
import os
import uuid

from app.database import get_db
from app.models import (
    ReportUpload, UploadStatus, ReportType,
    ReportExtractLog, OccupancySnapshot, OccupancyLatest,
    FrontdeskEvent, FrontdeskEventsHourlyAgg, EventType,
    WeekdayBiasStats, HourlyDistributionStats
)
from app.datalayer import ReportDetector, HPParser, HP_PARSER_VERSION, FrontdeskParser, CheckInOutParser, CHECKINOUT_PARSER_VERSION
from app.services.stats_calculator import StatsCalculator

router = APIRouter(prefix="/api/data-lake", tags=["Data Lake"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/uploads")
async def upload_report(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome")
    
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    existing = db.query(ReportUpload).filter(
        ReportUpload.file_hash == file_hash
    ).first()
    if existing:
        return {
            "status": "duplicate",
            "message": "Arquivo já foi enviado anteriormente",
            "existing_upload_id": existing.id
        }
    
    file_ext = file.filename.split(".")[-1].lower()
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    detected_code, detection_confidence, detection_message = ReportDetector.detect(file_path, file.filename)
    
    report_type = None
    if detected_code:
        report_type = db.query(ReportType).filter(
            ReportType.code == detected_code
        ).first()
        
        if not report_type:
            report_type = ReportType(
                code=detected_code,
                name=detected_code.replace("_", " ").title(),
                category="OCCUPANCY" if "HP" in detected_code else "FRONTDESK_EVENTS",
                is_active=True
            )
            db.add(report_type)
            db.flush()
    
    upload = ReportUpload(
        filename=unique_name,
        original_filename=file.filename,
        file_path=file_path,
        file_type=file_ext,
        file_size=len(content),
        file_hash=file_hash,
        report_type_id=report_type.id if report_type else None,
        auto_detected=detected_code is not None,
        detection_confidence=detection_confidence,
        status=UploadStatus.PENDING,
        processing_notes=detection_message
    )
    db.add(upload)
    db.commit()
    db.refresh(upload)
    
    parse_result = None
    if detected_code and file_ext in ["pdf", "csv", "xlsx", "xls"]:
        parse_result = await process_upload(upload.id, db)
    
    return {
        "upload_id": upload.id,
        "filename": file.filename,
        "detected_type": detected_code,
        "confidence": detection_confidence,
        "message": detection_message,
        "parse_result": parse_result
    }


async def process_upload(upload_id: int, db: Session) -> Dict:
    upload = db.query(ReportUpload).filter(ReportUpload.id == upload_id).first()
    if not upload:
        return {"error": "Upload não encontrado"}
    
    upload.status = UploadStatus.PROCESSING
    db.commit()
    
    result = {}
    report_type = upload.report_type
    
    try:
        if report_type and report_type.code == "HP_DAILY":
            parser = HPParser(db)
            result = parser.parse(upload)
            
            db.refresh(upload)
            
            if result["success"]:
                upload.generated_at = result.get("generated_at")
                upload.date_start = result.get("period_start")
                upload.date_end = result.get("period_end")
                upload.rows_inserted = result.get("snapshots_created", 0)
                upload.rows_skipped = result.get("skipped", 0)
                
                stats_calc = StatsCalculator(db)
                stats_calc.update_weekday_bias()
        
        elif report_type and report_type.code == "CHECKIN_DAILY":
            file_ext = upload.file_path.split(".")[-1].lower() if upload.file_path else ""
            
            if file_ext in ["csv", "xlsx", "xls"]:
                parser = CheckInOutParser(db)
                result = parser.parse(upload, force_event_type=EventType.CHECKIN)
            else:
                parser = FrontdeskParser(db)
                result = parser.parse_checkin(upload)
            
            db.refresh(upload)
            
            if result.get("success"):
                upload.rows_inserted = result.get("events_created", 0)
                if result.get("date_range"):
                    upload.date_start = result["date_range"].get("start")
                    upload.date_end = result["date_range"].get("end")
                stats_calc = StatsCalculator(db)
                stats_calc.update_hourly_distribution(EventType.CHECKIN)
        
        elif report_type and report_type.code == "CHECKOUT_DAILY":
            file_ext = upload.file_path.split(".")[-1].lower() if upload.file_path else ""
            
            if file_ext in ["csv", "xlsx", "xls"]:
                parser = CheckInOutParser(db)
                result = parser.parse(upload, force_event_type=EventType.CHECKOUT)
            else:
                parser = FrontdeskParser(db)
                result = parser.parse_checkout(upload)
            
            db.refresh(upload)
            
            if result.get("success"):
                upload.rows_inserted = result.get("events_created", 0)
                if result.get("date_range"):
                    upload.date_start = result["date_range"].get("start")
                    upload.date_end = result["date_range"].get("end")
                stats_calc = StatsCalculator(db)
                stats_calc.update_hourly_distribution(EventType.CHECKOUT)
        
        else:
            result = {"error": "Tipo de relatório não suportado para parsing automático"}
        
        snapshots_created = result.get("snapshots_created", 0)
        events_created = result.get("events_created", 0)
        has_data = snapshots_created > 0 or events_created > 0
        
        if result.get("success") or has_data:
            upload.status = UploadStatus.COMPLETED
            if report_type and report_type.code == "HP_DAILY":
                upload.parser_version = HP_PARSER_VERSION
            elif report_type and report_type.code in ["CHECKIN_DAILY", "CHECKOUT_DAILY"]:
                file_ext = upload.file_path.split(".")[-1].lower() if upload.file_path else ""
                upload.parser_version = CHECKINOUT_PARSER_VERSION if file_ext in ["csv", "xlsx", "xls"] else "1.0.0"
            else:
                upload.parser_version = "1.0.0"
            upload.error_message = None
        else:
            upload.status = UploadStatus.FAILED
            errors = result.get("errors", [])
            upload.error_message = "; ".join(errors) if errors else result.get("error", "Nenhum dado extraído")
        
        upload.processed_at = datetime.utcnow()
        db.commit()
        db.refresh(upload)
        
    except Exception as e:
        db.rollback()
        upload = db.query(ReportUpload).filter(ReportUpload.id == upload_id).first()
        if upload:
            upload.status = UploadStatus.FAILED
            upload.error_message = str(e)
            upload.processed_at = datetime.utcnow()
            db.commit()
        result = {"error": str(e), "success": False}
    
    return result


@router.post("/uploads/{upload_id}/reprocess")
async def reprocess_upload(upload_id: int, db: Session = Depends(get_db)):
    from app.models import AuditLog, AuditAction
    
    upload = db.query(ReportUpload).filter(ReportUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload não encontrado")
    
    old_status = upload.status.value if upload.status else None
    
    result = await process_upload(upload_id, db)
    
    db.refresh(upload)
    new_status = upload.status.value if upload.status else None
    success = result.get("success", False)
    
    records_count = (
        result.get("records_extracted") or 
        result.get("events_created") or 
        result.get("snapshots_created") or 
        0
    )
    
    audit_action = AuditAction.REPORT_REPROCESSED if success else AuditAction.REPORT_FAILED
    
    log = AuditLog(
        action=audit_action,
        entity_type="report_upload",
        entity_id=upload_id,
        description=f"Reprocessamento: {old_status} -> {new_status}",
        extra_data={
            "old_status": old_status,
            "new_status": new_status,
            "records_extracted": records_count,
            "success": success
        }
    )
    db.add(log)
    db.commit()
    
    return {
        "success": success,
        "old_status": old_status,
        "new_status": new_status,
        "records_extracted": records_count,
        "errors": result.get("errors", []),
        "message": "Relatório reprocessado com sucesso" if success else "Falha no reprocessamento"
    }


@router.post("/uploads/reprocess-failed")
async def reprocess_failed_uploads(db: Session = Depends(get_db)):
    """
    HOTFIX: Reprocessa todos os uploads HP com status FAILED.
    Usa o parser corrigido com normalização UTC.
    """
    from app.models import AuditLog, AuditAction
    
    failed_uploads = db.query(ReportUpload).filter(
        ReportUpload.status == UploadStatus.FAILED
    ).all()
    
    results = []
    for upload in failed_uploads:
        old_status = upload.status.value
        
        try:
            result = await process_upload(upload.id, db)
            db.refresh(upload)
            new_status = upload.status.value if upload.status else None
            success = result.get("success", False)
            
            records_count = (
                result.get("snapshots_created") or 
                result.get("events_created") or 0
            )
            
            audit_action = AuditAction.REPORT_REPROCESSED if success else AuditAction.REPORT_FAILED
            log = AuditLog(
                action=audit_action,
                entity_type="report_upload",
                entity_id=upload.id,
                description=f"Bulk reprocess: {old_status} -> {new_status}",
                extra_data={
                    "old_status": old_status,
                    "new_status": new_status,
                    "records_extracted": records_count,
                    "success": success
                }
            )
            db.add(log)
            db.commit()
            
            results.append({
                "id": upload.id,
                "filename": upload.original_filename,
                "old_status": old_status,
                "new_status": new_status,
                "success": success,
                "records": records_count
            })
        except Exception as e:
            results.append({
                "id": upload.id,
                "filename": upload.original_filename,
                "old_status": old_status,
                "new_status": "FAILED",
                "success": False,
                "error": str(e)
            })
    
    success_count = sum(1 for r in results if r.get("success"))
    return {
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "results": results
    }


@router.get("/uploads")
def list_uploads(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    uploads = db.query(ReportUpload).order_by(
        desc(ReportUpload.created_at)
    ).offset(skip).limit(limit).all()
    
    return [
        {
            "id": u.id,
            "filename": u.original_filename,
            "type": u.report_type.code if u.report_type else None,
            "status": u.status.value if u.status else None,
            "generated_at": u.generated_at.isoformat() if u.generated_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "confidence": u.detection_confidence,
            "rows_inserted": u.rows_inserted or 0,
            "rows_skipped": u.rows_skipped or 0,
            "error_message": u.error_message
        }
        for u in uploads
    ]


@router.get("/uploads/{upload_id}")
def get_upload_detail(upload_id: int, db: Session = Depends(get_db)):
    upload = db.query(ReportUpload).filter(ReportUpload.id == upload_id).first()
    if not upload:
        raise HTTPException(status_code=404, detail="Upload não encontrado")
    
    logs = db.query(ReportExtractLog).filter(
        ReportExtractLog.report_upload_id == upload_id
    ).order_by(ReportExtractLog.created_at).all()
    
    return {
        "id": upload.id,
        "filename": upload.original_filename,
        "file_type": upload.file_type,
        "file_size": upload.file_size,
        "file_hash": upload.file_hash,
        "type": upload.report_type.code if upload.report_type else None,
        "status": upload.status.value if upload.status else None,
        "generated_at": upload.generated_at.isoformat() if upload.generated_at else None,
        "date_start": upload.date_start.isoformat() if upload.date_start else None,
        "date_end": upload.date_end.isoformat() if upload.date_end else None,
        "parser_version": upload.parser_version,
        "processing_notes": upload.processing_notes,
        "error_message": upload.error_message,
        "rows_inserted": upload.rows_inserted or 0,
        "rows_skipped": upload.rows_skipped or 0,
        "created_at": upload.created_at.isoformat() if upload.created_at else None,
        "logs": [
            {
                "step": log.step.value,
                "severity": log.severity.value,
                "message": log.message,
                "payload": log.payload_json,
                "created_at": log.created_at.isoformat() if log.created_at else None
            }
            for log in logs
        ]
    }


@router.get("/occupancy/latest")
def get_occupancy_latest(
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(OccupancyLatest)
    
    if start:
        query = query.filter(OccupancyLatest.target_date >= start)
    if end:
        query = query.filter(OccupancyLatest.target_date <= end)
    
    latests = query.order_by(OccupancyLatest.target_date).all()
    
    return [
        {
            "target_date": l.target_date.isoformat(),
            "real_pct": l.latest_real_occupancy_pct,
            "real_as_of": l.latest_real_generated_at.isoformat() if l.latest_real_generated_at else None,
            "forecast_pct": l.latest_forecast_occupancy_pct,
            "forecast_as_of": l.latest_forecast_generated_at.isoformat() if l.latest_forecast_generated_at else None
        }
        for l in latests
    ]


@router.get("/events/hourly")
def get_events_hourly(
    event_type: str = Query(..., description="CHECKIN ou CHECKOUT"),
    start: Optional[date] = Query(None),
    end: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    try:
        evt_type = EventType(event_type.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail="Tipo de evento inválido")
    
    query = db.query(FrontdeskEventsHourlyAgg).filter(
        FrontdeskEventsHourlyAgg.event_type == evt_type
    )
    
    if start:
        query = query.filter(FrontdeskEventsHourlyAgg.op_date >= start)
    if end:
        query = query.filter(FrontdeskEventsHourlyAgg.op_date <= end)
    
    aggs = query.order_by(
        FrontdeskEventsHourlyAgg.op_date,
        FrontdeskEventsHourlyAgg.hour_timeline
    ).all()
    
    return [
        {
            "op_date": a.op_date.isoformat(),
            "weekday": a.weekday_pt,
            "hour_timeline": a.hour_timeline,
            "count": a.count_events
        }
        for a in aggs
    ]


@router.get("/stats/weekday-bias")
def get_weekday_bias(db: Session = Depends(get_db)):
    stats = db.query(WeekdayBiasStats).filter(
        WeekdayBiasStats.metric_name == "OCCUPANCY_BIAS_PP"
    ).all()
    
    return [
        {
            "weekday": s.weekday_pt,
            "bias_pp": round(s.bias_pp, 2) if s.bias_pp else 0,
            "n": s.n,
            "std_pp": round(s.std_pp, 2) if s.std_pp else None,
            "mae_pp": round(s.mae_pp, 2) if s.mae_pp else None,
            "method": s.method
        }
        for s in stats
    ]


@router.get("/stats/hourly-distribution")
def get_hourly_distribution(
    metric: str = Query(..., description="CHECKIN_PCT ou CHECKOUT_PCT"),
    db: Session = Depends(get_db)
):
    stats = db.query(HourlyDistributionStats).filter(
        HourlyDistributionStats.metric_name == metric.upper()
    ).order_by(
        HourlyDistributionStats.weekday_pt,
        HourlyDistributionStats.hour_timeline
    ).all()
    
    result = {}
    for s in stats:
        if s.weekday_pt not in result:
            result[s.weekday_pt] = []
        result[s.weekday_pt].append({
            "hour": s.hour_timeline,
            "pct": round(s.pct, 2)
        })
    
    return result


@router.post("/stats/bootstrap-bias")
def bootstrap_bias(
    data: Dict[str, float],
    db: Session = Depends(get_db)
):
    calculator = StatsCalculator(db)
    results = calculator.bootstrap_bias(data)
    return {"results": results}


@router.post("/stats/recalculate")
def recalculate_all_stats(db: Session = Depends(get_db)):
    calculator = StatsCalculator(db)
    
    bias_results = calculator.update_weekday_bias()
    checkin_results = calculator.update_hourly_distribution(EventType.CHECKIN)
    checkout_results = calculator.update_hourly_distribution(EventType.CHECKOUT)
    
    return {
        "weekday_bias": bias_results,
        "checkin_distribution": checkin_results,
        "checkout_distribution": checkout_results
    }


@router.get("/forecast/adjusted")
def get_adjusted_forecast(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db)
):
    import logging
    from datetime import timedelta
    
    try:
        calculator = StatsCalculator(db)
        
        results = []
        current = start
        has_any_data = False
        
        while current <= end:
            result = calculator.get_adjusted_forecast(current)
            results.append(result)
            if result.get("forecast_pct") is not None or result.get("real_pct") is not None:
                has_any_data = True
            current = current + timedelta(days=1)
        
        return {
            "status": "success" if has_any_data else "no_data",
            "message": None if has_any_data else "Ainda não há dados suficientes para gerar previsão para este período.",
            "error_code": None if has_any_data else "DATA_NOT_AVAILABLE",
            "data": results
        }
    except Exception as e:
        logging.exception(f"Erro técnico ao carregar previsão: {e}")
        raise HTTPException(
            status_code=500, 
            detail={
                "status": "error",
                "message": "Erro técnico ao carregar previsão — ver logs para detalhes.",
                "error_code": "INTERNAL_ERROR",
                "data": None
            }
        )
