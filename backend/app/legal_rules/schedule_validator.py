from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from .intermittent_rules import IntermittentWorkerRules, LegalConfig


class ScheduleValidator:
    
    def __init__(self, config: Optional[LegalConfig] = None):
        self.rules = IntermittentWorkerRules(config)
    
    def validate_schedule_for_employee(
        self,
        employee_data: Dict,
        proposed_shifts: List[Dict],
        week_start: date
    ) -> Dict:
        
        validation_result = {
            "employee_id": employee_data.get("id"),
            "employee_name": employee_data.get("name"),
            "is_valid": True,
            "warnings": [],
            "errors": [],
            "shift_validations": []
        }
        
        if employee_data.get("contract_type") != "intermitente":
            validation_result["message"] = "Colaborador efetivo - regras de intermitente não aplicáveis"
            return validation_result
        
        week_off_check = self.rules.check_full_week_off_needed(
            employee_data.get("last_full_week_off"),
            week_start
        )
        if week_off_check["week_off_needed"]:
            validation_result["errors"].append(week_off_check["message"])
            validation_result["is_valid"] = False
        elif week_off_check.get("approaching_limit"):
            validation_result["warnings"].append(week_off_check["message"])
        
        recent_shifts = employee_data.get("shifts_history", [])
        shift_rotation_check = self.rules.check_shift_rotation_needed(recent_shifts)
        if shift_rotation_check["rotation_needed"]:
            validation_result["warnings"].append(shift_rotation_check["message"])
        
        hours_history = employee_data.get("hours_history", [])
        pattern_check = self.rules.check_pattern_variation(hours_history)
        if not pattern_check["variation_ok"]:
            validation_result["warnings"].append(pattern_check["message"])
        
        total_weekly_hours = 0
        
        for shift in proposed_shifts:
            shift_hours = shift.get("planned_hours", 0)
            total_weekly_hours += shift_hours
            
            daily_check = self.rules.validate_daily_hours(shift_hours)
            validation_result["shift_validations"].append({
                "date": shift.get("date"),
                "hours": shift_hours,
                **daily_check
            })
            
            if not daily_check["is_valid"]:
                validation_result["errors"].append(
                    f"Dia {shift.get('date')}: {daily_check['message']}"
                )
                validation_result["is_valid"] = False
        
        weekly_check = self.rules.validate_weekly_hours(total_weekly_hours)
        if not weekly_check["is_valid"]:
            validation_result["errors"].append(weekly_check["message"])
            validation_result["is_valid"] = False
        
        validation_result["total_weekly_hours"] = total_weekly_hours
        
        return validation_result
    
    def validate_convocation_timing(
        self,
        convocation_datetime: datetime,
        shift_date: date,
        shift_start_time: str
    ) -> Dict:
        
        shift_datetime = datetime.combine(
            shift_date, 
            datetime.strptime(shift_start_time, "%H:%M").time()
        )
        
        return self.rules.validate_convocation_advance_time(
            convocation_datetime, 
            shift_datetime
        )
    
    def get_recommended_shift_for_rotation(
        self,
        recent_shifts: List[str]
    ) -> str:
        if not recent_shifts:
            return "manha"
        
        shift_options = ["manha", "tarde", "noite"]
        last_shift = recent_shifts[-1] if recent_shifts else None
        
        shift_rotation = self.rules.check_shift_rotation_needed(recent_shifts)
        
        if shift_rotation["rotation_needed"] and last_shift:
            current_idx = shift_options.index(last_shift) if last_shift in shift_options else 0
            next_idx = (current_idx + 1) % len(shift_options)
            return shift_options[next_idx]
        
        shift_counts = {s: recent_shifts.count(s) for s in shift_options}
        return min(shift_counts, key=shift_counts.get)
