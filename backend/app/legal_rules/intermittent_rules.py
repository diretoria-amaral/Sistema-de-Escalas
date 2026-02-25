from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class LegalConfig:
    min_convocation_hours: int = 72
    max_consecutive_weeks_same_shift: int = 3
    max_consecutive_weeks_same_days: int = 4
    min_weeks_between_full_time_off: int = 4
    max_weeks_between_full_time_off: int = 6
    vacation_period_days: int = 10
    min_daily_hours: float = 4.0
    max_daily_hours: float = 10.0
    max_weekly_hours: float = 44.0


class IntermittentWorkerRules:
    
    def __init__(self, config: Optional[LegalConfig] = None):
        self.config = config or LegalConfig()
    
    def validate_convocation_advance_time(self, convocation_datetime: datetime, shift_datetime: datetime) -> Dict:
        hours_advance = (shift_datetime - convocation_datetime).total_seconds() / 3600
        is_valid = hours_advance >= self.config.min_convocation_hours
        return {
            "is_valid": is_valid,
            "hours_advance": hours_advance,
            "min_required": self.config.min_convocation_hours,
            "message": f"Convocação com {hours_advance:.1f}h de antecedência" if is_valid 
                      else f"Antecedência mínima de {self.config.min_convocation_hours}h não atendida"
        }
    
    def check_shift_rotation_needed(self, recent_shifts: List[str]) -> Dict:
        if len(recent_shifts) < self.config.max_consecutive_weeks_same_shift:
            return {"rotation_needed": False, "message": "Histórico insuficiente para análise"}
        
        recent = recent_shifts[-self.config.max_consecutive_weeks_same_shift:]
        same_shift = all(s == recent[0] for s in recent) if recent else False
        
        return {
            "rotation_needed": same_shift,
            "consecutive_weeks": len(recent) if same_shift else 0,
            "last_shift": recent[-1] if recent else None,
            "message": "Recomenda-se alternar turno" if same_shift 
                      else "Rotação de turnos adequada"
        }
    
    def check_full_week_off_needed(self, last_full_week_off: Optional[date], current_date: Optional[date] = None) -> Dict:
        if not last_full_week_off:
            return {
                "week_off_needed": True,
                "weeks_since_last": None,
                "message": "Sem registro de semana de folga completa"
            }
        
        current = current_date or date.today()
        weeks_since = (current - last_full_week_off).days // 7
        
        needs_week_off = weeks_since >= self.config.max_weeks_between_full_time_off
        approaching = weeks_since >= self.config.min_weeks_between_full_time_off
        
        return {
            "week_off_needed": needs_week_off,
            "approaching_limit": approaching,
            "weeks_since_last": weeks_since,
            "max_weeks_allowed": self.config.max_weeks_between_full_time_off,
            "message": "Semana de folga completa obrigatória" if needs_week_off 
                      else ("Semana de folga recomendada" if approaching 
                            else "Dentro do período regular")
        }
    
    def check_pattern_variation(self, hours_history: List[Dict]) -> Dict:
        if len(hours_history) < 4:
            return {"variation_ok": True, "message": "Histórico insuficiente para análise de padrões"}
        
        recent = hours_history[-4:]
        hours = [h.get("total_hours", 0) for h in recent]
        days = [h.get("days_worked", 0) for h in recent]
        
        hours_same = len(set(hours)) == 1
        days_same = len(set(days)) == 1
        
        return {
            "variation_ok": not (hours_same and days_same),
            "hours_pattern_detected": hours_same,
            "days_pattern_detected": days_same,
            "recent_hours": hours,
            "recent_days": days,
            "message": "Padrão repetitivo detectado - recomenda-se variação" 
                      if (hours_same and days_same) else "Variação adequada"
        }
    
    def validate_daily_hours(self, hours: float) -> Dict:
        is_valid = self.config.min_daily_hours <= hours <= self.config.max_daily_hours
        return {
            "is_valid": is_valid,
            "hours": hours,
            "min_hours": self.config.min_daily_hours,
            "max_hours": self.config.max_daily_hours,
            "message": "Jornada dentro dos limites" if is_valid 
                      else f"Jornada deve estar entre {self.config.min_daily_hours}h e {self.config.max_daily_hours}h"
        }
    
    def validate_weekly_hours(self, hours: float) -> Dict:
        is_valid = hours <= self.config.max_weekly_hours
        return {
            "is_valid": is_valid,
            "hours": hours,
            "max_hours": self.config.max_weekly_hours,
            "message": "Carga semanal dentro do limite" if is_valid 
                      else f"Carga semanal excede o máximo de {self.config.max_weekly_hours}h"
        }
    
    def get_full_compliance_report(
        self,
        convocation_datetime: Optional[datetime] = None,
        shift_datetime: Optional[datetime] = None,
        recent_shifts: Optional[List[str]] = None,
        last_full_week_off: Optional[date] = None,
        hours_history: Optional[List[Dict]] = None,
        daily_hours: Optional[float] = None,
        weekly_hours: Optional[float] = None
    ) -> Dict:
        report = {"checks": [], "all_valid": True, "warnings": [], "errors": []}
        
        if convocation_datetime and shift_datetime:
            check = self.validate_convocation_advance_time(convocation_datetime, shift_datetime)
            report["checks"].append({"name": "convocation_advance", **check})
            if not check["is_valid"]:
                report["errors"].append(check["message"])
                report["all_valid"] = False
        
        if recent_shifts:
            check = self.check_shift_rotation_needed(recent_shifts)
            report["checks"].append({"name": "shift_rotation", **check})
            if check["rotation_needed"]:
                report["warnings"].append(check["message"])
        
        if last_full_week_off is not None:
            check = self.check_full_week_off_needed(last_full_week_off)
            report["checks"].append({"name": "week_off", **check})
            if check["week_off_needed"]:
                report["errors"].append(check["message"])
                report["all_valid"] = False
            elif check.get("approaching_limit"):
                report["warnings"].append(check["message"])
        
        if hours_history:
            check = self.check_pattern_variation(hours_history)
            report["checks"].append({"name": "pattern_variation", **check})
            if not check["variation_ok"]:
                report["warnings"].append(check["message"])
        
        if daily_hours is not None:
            check = self.validate_daily_hours(daily_hours)
            report["checks"].append({"name": "daily_hours", **check})
            if not check["is_valid"]:
                report["errors"].append(check["message"])
                report["all_valid"] = False
        
        if weekly_hours is not None:
            check = self.validate_weekly_hours(weekly_hours)
            report["checks"].append({"name": "weekly_hours", **check})
            if not check["is_valid"]:
                report["errors"].append(check["message"])
                report["all_valid"] = False
        
        return report
