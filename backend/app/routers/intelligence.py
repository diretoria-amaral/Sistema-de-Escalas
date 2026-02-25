from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta

from app.database import get_db
from app.models.occupancy_data import DeviationHistory
from app.models.audit_log import AuditLog
from app.schemas.report import (
    DeviationHistoryResponse,
    ScheduleAdjustmentRecommendation,
    DailyComparisonResponse
)
from app.services.deviation_calculator import DeviationCalculator, DAY_NAMES

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


@router.get("/deviations", response_model=List[DeviationHistoryResponse])
def get_deviation_history(db: Session = Depends(get_db)):
    deviations = db.query(DeviationHistory).order_by(DeviationHistory.day_of_week).all()
    
    result = []
    for dev in deviations:
        result.append(DeviationHistoryResponse(
            id=dev.id,
            day_of_week=dev.day_of_week,
            day_name=DAY_NAMES[dev.day_of_week],
            sample_count=dev.sample_count,
            avg_occupancy_forecast=dev.avg_occupancy_forecast,
            avg_occupancy_actual=dev.avg_occupancy_actual,
            avg_deviation=dev.avg_deviation,
            std_deviation=dev.std_deviation,
            correction_factor=dev.correction_factor,
            avg_arrivals_forecast=dev.avg_arrivals_forecast,
            avg_arrivals_actual=dev.avg_arrivals_actual,
            arrivals_deviation=dev.arrivals_deviation,
            avg_departures_forecast=dev.avg_departures_forecast,
            avg_departures_actual=dev.avg_departures_actual,
            departures_deviation=dev.departures_deviation,
            avg_employees_needed=dev.avg_employees_needed,
            avg_employees_used=dev.avg_employees_used,
            employees_deviation=dev.employees_deviation,
            version=dev.version,
            last_updated=dev.last_updated
        ))
    
    return result


@router.post("/deviations/recalculate")
def recalculate_deviations(db: Session = Depends(get_db)):
    calculator = DeviationCalculator(db)
    results = calculator.update_deviation_history()
    
    return {
        "message": "Deviation history recalculated successfully",
        "days_updated": len(results),
        "results": results
    }


@router.get("/forecast/{target_date}")
def get_corrected_forecast(target_date: date, db: Session = Depends(get_db)):
    calculator = DeviationCalculator(db)
    return calculator.get_corrected_forecast(target_date)


@router.get("/recommendations")
def get_schedule_recommendations(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    employees_per_point: float = 0.1,
    db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today()
    if not end_date:
        end_date = start_date + timedelta(days=7)
    
    calculator = DeviationCalculator(db)
    recommendations = calculator.get_schedule_adjustment_recommendations(
        start_date, end_date, employees_per_point
    )
    
    return {
        "period": {
            "start": start_date,
            "end": end_date
        },
        "total_recommendations": len(recommendations),
        "high_priority": len([r for r in recommendations if r["priority"] == "high"]),
        "recommendations": recommendations
    }


@router.get("/comparison")
def get_forecast_comparison(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    if not start_date:
        start_date = date.today() - timedelta(days=7)
    if not end_date:
        end_date = date.today()
    
    calculator = DeviationCalculator(db)
    comparisons = calculator.compare_forecast_vs_actual(start_date, end_date)
    
    total_deviation = 0
    deviation_count = 0
    for comp in comparisons:
        if comp["deviation"] is not None:
            total_deviation += abs(comp["deviation"])
            deviation_count += 1
    
    avg_absolute_deviation = total_deviation / deviation_count if deviation_count > 0 else 0
    
    return {
        "period": {
            "start": start_date,
            "end": end_date
        },
        "summary": {
            "total_days": len(comparisons),
            "days_with_data": deviation_count,
            "avg_absolute_deviation": round(avg_absolute_deviation, 2)
        },
        "daily_comparison": comparisons
    }


@router.get("/dashboard")
def get_intelligence_dashboard(db: Session = Depends(get_db)):
    deviations = db.query(DeviationHistory).all()
    
    deviation_summary = []
    for dev in deviations:
        deviation_summary.append({
            "day": DAY_NAMES[dev.day_of_week],
            "correction_factor": round(dev.correction_factor, 3),
            "avg_deviation": round(dev.avg_deviation, 1),
            "samples": dev.sample_count,
            "confidence": "high" if dev.sample_count >= 12 else ("medium" if dev.sample_count >= 4 else "low")
        })
    
    today = date.today()
    calculator = DeviationCalculator(db)
    
    next_7_days = []
    for i in range(7):
        target_date = today + timedelta(days=i)
        forecast = calculator.get_corrected_forecast(target_date)
        next_7_days.append(forecast)
    
    recommendations = calculator.get_schedule_adjustment_recommendations(
        today, today + timedelta(days=7)
    )
    
    high_priority = [r for r in recommendations if r["priority"] == "high"]
    
    last_7_days = calculator.compare_forecast_vs_actual(
        today - timedelta(days=7), today - timedelta(days=1)
    )
    
    accuracy_score = 100
    deviation_count = 0
    total_deviation = 0
    for day in last_7_days:
        if day["deviation"] is not None:
            total_deviation += abs(day["deviation"])
            deviation_count += 1
    
    if deviation_count > 0:
        accuracy_score = max(0, 100 - (total_deviation / deviation_count))
    
    return {
        "last_updated": datetime.now(),
        "deviation_patterns": deviation_summary,
        "next_7_days_forecast": next_7_days,
        "pending_adjustments": {
            "high_priority": len(high_priority),
            "total": len(recommendations),
            "items": high_priority[:5]
        },
        "recent_accuracy": {
            "score": round(accuracy_score, 1),
            "based_on_days": deviation_count,
            "avg_deviation": round(total_deviation / deviation_count, 1) if deviation_count > 0 else 0
        }
    }


@router.get("/audit-logs")
def get_audit_logs(
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    
    logs = query.limit(limit).all()
    
    return [{
        "id": log.id,
        "action": log.action.value,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "description": log.description,
        "user_name": log.user_name,
        "created_at": log.created_at
    } for log in logs]
