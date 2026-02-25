from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import math

from app.models.occupancy_data import OccupancyForecast, OccupancyActual, DeviationHistory
from app.models.audit_log import AuditLog, AuditAction


DAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


class DeviationCalculator:
    
    def __init__(self, db: Session):
        self.db = db
    
    def calculate_deviation(self, forecast: float, actual: float) -> float:
        if forecast == 0:
            return 0 if actual == 0 else 100
        return ((actual - forecast) / forecast) * 100
    
    def update_deviation_history(self) -> Dict[int, Dict]:
        results = {}
        
        for day_of_week in range(7):
            forecasts = self.db.query(OccupancyForecast).filter(
                OccupancyForecast.day_of_week == day_of_week
            ).all()
            
            actuals = self.db.query(OccupancyActual).filter(
                OccupancyActual.day_of_week == day_of_week
            ).all()
            
            actuals_by_date = {a.date: a for a in actuals}
            
            matched_data = []
            for forecast in forecasts:
                if forecast.date in actuals_by_date:
                    actual = actuals_by_date[forecast.date]
                    matched_data.append({
                        "date": forecast.date,
                        "forecast_occupancy": forecast.occupancy_rate_forecast or 0,
                        "actual_occupancy": actual.occupancy_rate or 0,
                        "forecast_arrivals": forecast.arrivals_forecast or 0,
                        "actual_arrivals": actual.arrivals or 0,
                        "forecast_departures": forecast.departures_forecast or 0,
                        "actual_departures": actual.departures or 0,
                        "employees_worked": actual.employees_worked or 0
                    })
            
            if not matched_data:
                continue
            
            sample_count = len(matched_data)
            
            avg_occ_forecast = sum(d["forecast_occupancy"] for d in matched_data) / sample_count
            avg_occ_actual = sum(d["actual_occupancy"] for d in matched_data) / sample_count
            avg_deviation = self.calculate_deviation(avg_occ_forecast, avg_occ_actual)
            
            deviations = [self.calculate_deviation(d["forecast_occupancy"], d["actual_occupancy"]) 
                         for d in matched_data if d["forecast_occupancy"] > 0]
            std_deviation = 0
            if len(deviations) > 1:
                mean_dev = sum(deviations) / len(deviations)
                variance = sum((d - mean_dev) ** 2 for d in deviations) / len(deviations)
                std_deviation = math.sqrt(variance)
            
            if avg_occ_forecast > 0:
                correction_factor = avg_occ_actual / avg_occ_forecast
            else:
                correction_factor = 1.0
            
            avg_arr_forecast = sum(d["forecast_arrivals"] for d in matched_data) / sample_count
            avg_arr_actual = sum(d["actual_arrivals"] for d in matched_data) / sample_count
            arr_deviation = self.calculate_deviation(avg_arr_forecast, avg_arr_actual)
            
            avg_dep_forecast = sum(d["forecast_departures"] for d in matched_data) / sample_count
            avg_dep_actual = sum(d["actual_departures"] for d in matched_data) / sample_count
            dep_deviation = self.calculate_deviation(avg_dep_forecast, avg_dep_actual)
            
            avg_employees = sum(d["employees_worked"] for d in matched_data) / sample_count
            
            history = self.db.query(DeviationHistory).filter(
                DeviationHistory.day_of_week == day_of_week
            ).first()
            
            old_values = None
            if history:
                old_values = {
                    "correction_factor": history.correction_factor,
                    "avg_deviation": history.avg_deviation,
                    "version": history.version
                }
                
                snapshot = {
                    "version": history.version,
                    "timestamp": datetime.now().isoformat(),
                    "correction_factor": history.correction_factor,
                    "avg_deviation": history.avg_deviation,
                    "sample_count": history.sample_count
                }
                
                if history.history_snapshots is None:
                    history.history_snapshots = []
                
                snapshots = list(history.history_snapshots)
                snapshots.append(snapshot)
                if len(snapshots) > 52:
                    snapshots = snapshots[-52:]
                history.history_snapshots = snapshots
                
                history.sample_count = sample_count
                history.avg_occupancy_forecast = avg_occ_forecast
                history.avg_occupancy_actual = avg_occ_actual
                history.avg_deviation = avg_deviation
                history.std_deviation = std_deviation
                history.correction_factor = correction_factor
                history.avg_arrivals_forecast = avg_arr_forecast
                history.avg_arrivals_actual = avg_arr_actual
                history.arrivals_deviation = arr_deviation
                history.avg_departures_forecast = avg_dep_forecast
                history.avg_departures_actual = avg_dep_actual
                history.departures_deviation = dep_deviation
                history.avg_employees_used = avg_employees
                history.version += 1
            else:
                history = DeviationHistory(
                    day_of_week=day_of_week,
                    sample_count=sample_count,
                    avg_occupancy_forecast=avg_occ_forecast,
                    avg_occupancy_actual=avg_occ_actual,
                    avg_deviation=avg_deviation,
                    std_deviation=std_deviation,
                    correction_factor=correction_factor,
                    avg_arrivals_forecast=avg_arr_forecast,
                    avg_arrivals_actual=avg_arr_actual,
                    arrivals_deviation=arr_deviation,
                    avg_departures_forecast=avg_dep_forecast,
                    avg_departures_actual=avg_dep_actual,
                    departures_deviation=dep_deviation,
                    avg_employees_used=avg_employees,
                    version=1,
                    history_snapshots=[]
                )
                self.db.add(history)
            
            audit = AuditLog(
                action=AuditAction.DEVIATION_UPDATE,
                entity_type="deviation_history",
                entity_id=day_of_week,
                description=f"Updated deviation history for {DAY_NAMES[day_of_week]}",
                old_values=old_values,
                new_values={
                    "correction_factor": correction_factor,
                    "avg_deviation": avg_deviation,
                    "sample_count": sample_count
                }
            )
            self.db.add(audit)
            
            results[day_of_week] = {
                "day_name": DAY_NAMES[day_of_week],
                "sample_count": sample_count,
                "avg_deviation": round(avg_deviation, 2),
                "correction_factor": round(correction_factor, 3),
                "std_deviation": round(std_deviation, 2)
            }
        
        self.db.commit()
        return results
    
    def get_corrected_forecast(self, target_date: date) -> Dict:
        day_of_week = target_date.weekday()
        
        forecast = self.db.query(OccupancyForecast).filter(
            OccupancyForecast.date == target_date
        ).first()
        
        history = self.db.query(DeviationHistory).filter(
            DeviationHistory.day_of_week == day_of_week
        ).first()
        
        if not forecast:
            return {
                "date": target_date,
                "day_name": DAY_NAMES[day_of_week],
                "has_forecast": False,
                "message": "No forecast available for this date"
            }
        
        result = {
            "date": target_date,
            "day_name": DAY_NAMES[day_of_week],
            "has_forecast": True,
            "original_occupancy": forecast.occupancy_rate_forecast,
            "original_arrivals": forecast.arrivals_forecast,
            "original_departures": forecast.departures_forecast
        }
        
        if history and history.sample_count >= 4:
            correction_factor = history.correction_factor
            result["correction_factor"] = correction_factor
            result["corrected_occupancy"] = round(
                (forecast.occupancy_rate_forecast or 0) * correction_factor, 1
            )
            result["confidence"] = "high" if history.sample_count >= 12 else "medium"
            result["based_on_samples"] = history.sample_count
        else:
            result["correction_factor"] = 1.0
            result["corrected_occupancy"] = forecast.occupancy_rate_forecast
            result["confidence"] = "low"
            result["based_on_samples"] = history.sample_count if history else 0
        
        return result
    
    def get_schedule_adjustment_recommendations(
        self, 
        start_date: date, 
        end_date: date,
        employees_per_occupancy_point: float = 0.1
    ) -> List[Dict]:
        recommendations = []
        
        current_date = start_date
        while current_date <= end_date:
            corrected = self.get_corrected_forecast(current_date)
            
            if corrected.get("has_forecast"):
                original_occ = corrected.get("original_occupancy", 0) or 0
                corrected_occ = corrected.get("corrected_occupancy", 0) or 0
                correction_factor = corrected.get("correction_factor", 1.0)
                
                original_employees = int(original_occ * employees_per_occupancy_point)
                recommended_employees = int(corrected_occ * employees_per_occupancy_point)
                
                adjustment = recommended_employees - original_employees
                
                if abs(adjustment) > 0:
                    if adjustment > 0:
                        reason = f"Historical data suggests occupancy will be {round((correction_factor - 1) * 100, 1)}% higher than forecast"
                        priority = "high" if adjustment >= 2 else "medium"
                    else:
                        reason = f"Historical data suggests occupancy will be {round((1 - correction_factor) * 100, 1)}% lower than forecast"
                        priority = "low"
                    
                    recommendations.append({
                        "date": current_date,
                        "day_name": DAY_NAMES[current_date.weekday()],
                        "forecasted_occupancy": original_occ,
                        "corrected_occupancy": corrected_occ,
                        "correction_factor": correction_factor,
                        "current_employees": original_employees,
                        "recommended_employees": recommended_employees,
                        "adjustment": adjustment,
                        "adjustment_reason": reason,
                        "confidence_level": corrected.get("confidence", "low"),
                        "priority": priority
                    })
            
            current_date += timedelta(days=1)
        
        return sorted(recommendations, key=lambda x: (
            0 if x["priority"] == "high" else (1 if x["priority"] == "medium" else 2),
            x["date"]
        ))
    
    def compare_forecast_vs_actual(
        self,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        comparisons = []
        
        forecasts = self.db.query(OccupancyForecast).filter(
            OccupancyForecast.date >= start_date,
            OccupancyForecast.date <= end_date
        ).all()
        
        actuals = self.db.query(OccupancyActual).filter(
            OccupancyActual.date >= start_date,
            OccupancyActual.date <= end_date
        ).all()
        
        actuals_by_date = {a.date: a for a in actuals}
        
        current_date = start_date
        while current_date <= end_date:
            forecast = next((f for f in forecasts if f.date == current_date), None)
            actual = actuals_by_date.get(current_date)
            
            comparison = {
                "date": current_date,
                "day_name": DAY_NAMES[current_date.weekday()],
                "forecast_occupancy": None,
                "actual_occupancy": None,
                "deviation": None,
                "forecast_arrivals": 0,
                "actual_arrivals": 0,
                "forecast_departures": 0,
                "actual_departures": 0,
                "employees_scheduled": 0,
                "employees_worked": 0
            }
            
            if forecast:
                comparison["forecast_occupancy"] = forecast.occupancy_rate_forecast
                comparison["forecast_arrivals"] = forecast.arrivals_forecast or 0
                comparison["forecast_departures"] = forecast.departures_forecast or 0
            
            if actual:
                comparison["actual_occupancy"] = actual.occupancy_rate
                comparison["actual_arrivals"] = actual.arrivals or 0
                comparison["actual_departures"] = actual.departures or 0
                comparison["employees_worked"] = actual.employees_worked or 0
            
            if forecast and actual and forecast.occupancy_rate_forecast and actual.occupancy_rate:
                comparison["deviation"] = self.calculate_deviation(
                    forecast.occupancy_rate_forecast,
                    actual.occupancy_rate
                )
            
            comparisons.append(comparison)
            current_date += timedelta(days=1)
        
        return comparisons
