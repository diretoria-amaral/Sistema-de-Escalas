from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional
from datetime import date, datetime, timedelta
import math

from app.models.data_lake import (
    OccupancySnapshot, OccupancyLatest,
    FrontdeskEventsHourlyAgg, EventType,
    WeekdayBiasStats, HourlyDistributionStats
)

WEEKDAYS_PT = ["SEGUNDA-FEIRA", "TERÇA-FEIRA", "QUARTA-FEIRA", "QUINTA-FEIRA",
               "SEXTA-FEIRA", "SÁBADO", "DOMINGO"]


class StatsCalculator:
    
    def __init__(self, db: Session, ewma_alpha: float = 0.2):
        self.db = db
        self.ewma_alpha = ewma_alpha
    
    def update_weekday_bias(self) -> Dict[str, Dict]:
        results = {}
        
        for weekday_idx, weekday_pt in enumerate(WEEKDAYS_PT):
            latests = self.db.query(OccupancyLatest).filter(
                func.extract('dow', OccupancyLatest.target_date) == (weekday_idx + 1) % 7
            ).all()
            
            errors = []
            for latest in latests:
                if latest.latest_real_occupancy_pct is not None and latest.latest_forecast_occupancy_pct is not None:
                    error_pp = latest.latest_real_occupancy_pct - latest.latest_forecast_occupancy_pct
                    errors.append(error_pp)
            
            if not errors:
                continue
            
            mean_bias = sum(errors) / len(errors)
            n = len(errors)
            
            if n > 1:
                variance = sum((e - mean_bias) ** 2 for e in errors) / (n - 1)
                std_pp = math.sqrt(variance)
            else:
                std_pp = 0
            
            mae_pp = sum(abs(e) for e in errors) / n
            
            existing = self.db.query(WeekdayBiasStats).filter(
                WeekdayBiasStats.metric_name == "OCCUPANCY_BIAS_PP",
                WeekdayBiasStats.weekday_pt == weekday_pt
            ).first()
            
            if existing:
                new_bias = (1 - self.ewma_alpha) * existing.bias_pp + self.ewma_alpha * mean_bias
                existing.bias_pp = new_bias
                existing.n = n
                existing.std_pp = std_pp
                existing.mae_pp = mae_pp
                existing.method = "EWMA"
                existing.method_params_json = {"alpha": self.ewma_alpha}
            else:
                stat = WeekdayBiasStats(
                    metric_name="OCCUPANCY_BIAS_PP",
                    weekday_pt=weekday_pt,
                    bias_pp=mean_bias,
                    n=n,
                    std_pp=std_pp,
                    mae_pp=mae_pp,
                    method="EWMA",
                    method_params_json={"alpha": self.ewma_alpha}
                )
                self.db.add(stat)
            
            results[weekday_pt] = {
                "bias_pp": round(mean_bias, 2),
                "n": n,
                "std_pp": round(std_pp, 2),
                "mae_pp": round(mae_pp, 2)
            }
        
        self.db.commit()
        return results
    
    def update_hourly_distribution(self, event_type: EventType) -> Dict[str, Dict]:
        results = {}
        metric_name = f"{event_type.value}_PCT"
        
        for weekday_pt in WEEKDAYS_PT:
            aggs = self.db.query(FrontdeskEventsHourlyAgg).filter(
                FrontdeskEventsHourlyAgg.weekday_pt == weekday_pt,
                FrontdeskEventsHourlyAgg.event_type == event_type
            ).all()
            
            if not aggs:
                continue
            
            total_events = sum(a.count_events for a in aggs)
            if total_events == 0:
                continue
            
            unique_dates = len(set(a.op_date for a in aggs))
            
            hourly_totals = {}
            for agg in aggs:
                if agg.hour_timeline not in hourly_totals:
                    hourly_totals[agg.hour_timeline] = 0
                hourly_totals[agg.hour_timeline] += agg.count_events
            
            for hour_timeline, count in hourly_totals.items():
                pct = (count / total_events) * 100
                
                existing = self.db.query(HourlyDistributionStats).filter(
                    HourlyDistributionStats.metric_name == metric_name,
                    HourlyDistributionStats.weekday_pt == weekday_pt,
                    HourlyDistributionStats.hour_timeline == hour_timeline
                ).first()
                
                if existing:
                    existing.pct = pct
                    existing.n = unique_dates
                else:
                    stat = HourlyDistributionStats(
                        metric_name=metric_name,
                        weekday_pt=weekday_pt,
                        hour_timeline=hour_timeline,
                        pct=pct,
                        n=unique_dates,
                        method="INCREMENTAL"
                    )
                    self.db.add(stat)
            
            results[weekday_pt] = {
                "total_events": total_events,
                "unique_dates": unique_dates,
                "hours_count": len(hourly_totals)
            }
        
        self.db.commit()
        return results
    
    def bootstrap_bias(self, data: Dict[str, float]) -> Dict[str, str]:
        results = {}
        
        for weekday_pt, bias_pp in data.items():
            weekday_pt_upper = weekday_pt.upper()
            if weekday_pt_upper not in [w.upper() for w in WEEKDAYS_PT]:
                results[weekday_pt] = "Invalid weekday"
                continue
            
            normalized_weekday = next(w for w in WEEKDAYS_PT if w.upper() == weekday_pt_upper)
            
            existing = self.db.query(WeekdayBiasStats).filter(
                WeekdayBiasStats.metric_name == "OCCUPANCY_BIAS_PP",
                WeekdayBiasStats.weekday_pt == normalized_weekday
            ).first()
            
            if existing:
                existing.bias_pp = bias_pp
                existing.method = "BOOTSTRAP_MANUAL"
                existing.n = 0
            else:
                stat = WeekdayBiasStats(
                    metric_name="OCCUPANCY_BIAS_PP",
                    weekday_pt=normalized_weekday,
                    bias_pp=bias_pp,
                    n=0,
                    method="BOOTSTRAP_MANUAL"
                )
                self.db.add(stat)
            
            results[weekday_pt] = "OK"
        
        self.db.commit()
        return results
    
    def get_adjusted_forecast(self, target_date: date) -> Dict:
        weekday_idx = target_date.weekday()
        weekday_pt = WEEKDAYS_PT[weekday_idx]
        
        latest = self.db.query(OccupancyLatest).filter(
            OccupancyLatest.target_date == target_date
        ).first()
        
        bias_stat = self.db.query(WeekdayBiasStats).filter(
            WeekdayBiasStats.metric_name == "OCCUPANCY_BIAS_PP",
            WeekdayBiasStats.weekday_pt == weekday_pt
        ).first()
        
        result = {
            "target_date": target_date.isoformat(),
            "weekday_pt": weekday_pt,
            "forecast_pct": None,
            "bias_pp": 0,
            "adjusted_forecast_pct": None,
            "real_pct": None,
            "has_bias_data": False
        }
        
        if latest:
            result["forecast_pct"] = latest.latest_forecast_occupancy_pct
            result["real_pct"] = latest.latest_real_occupancy_pct
        
        if bias_stat:
            result["bias_pp"] = bias_stat.bias_pp
            result["has_bias_data"] = True
            
            if result["forecast_pct"] is not None:
                adjusted = result["forecast_pct"] + bias_stat.bias_pp
                result["adjusted_forecast_pct"] = max(0, min(100, adjusted))
        
        return result
