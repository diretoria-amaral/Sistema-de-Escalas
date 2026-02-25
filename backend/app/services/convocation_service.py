from datetime import datetime, date, time, timedelta
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.convocation import Convocation, ConvocationStatus, ConvocationOrigin
from app.models.employee import Employee, ContractType
from app.models.sector import Sector
from app.models.daily_shift import DailyShift
from app.models.weekly_schedule import WeeklySchedule, ScheduleStatus
from app.models.governance_activity import GovernanceActivity, RoleActivity
from app.models.audit_log import AuditLog, AuditAction
from app.models.governance_rules import GovernanceRules
from app.legal_rules.intermittent_rules import IntermittentWorkerRules, LegalConfig


class ConvocationService:
    
    def __init__(self, db: Session):
        self.db = db
        self.legal_rules = IntermittentWorkerRules()
    
    def _get_governance_rules(self) -> Optional[GovernanceRules]:
        return self.db.query(GovernanceRules).filter(
            GovernanceRules.is_active == True
        ).first()
    
    def _get_legal_config(self) -> LegalConfig:
        rules = self._get_governance_rules()
        if rules:
            return LegalConfig(
                min_convocation_hours=72,
                max_daily_hours=rules.limite_horas_diarias or 10.0,
                max_weekly_hours=rules.limite_horas_semanais_sem_extra or 44.0
            )
        return LegalConfig()
    
    def validate_convocation(
        self,
        employee_id: int,
        sector_id: int,
        conv_date: date,
        start_time: time,
        end_time: time,
        total_hours: float,
        convocation_datetime: Optional[datetime] = None
    ) -> Dict:
        result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "checks": []
        }
        
        employee = self.db.query(Employee).filter(Employee.id == employee_id).first()
        if not employee:
            result["is_valid"] = False
            result["errors"].append(f"Colaborador {employee_id} não encontrado")
            return result
        
        if not employee.is_active:
            result["is_valid"] = False
            result["errors"].append(f"Colaborador {employee.name} está inativo")
            return result
        
        if employee.contract_type != ContractType.INTERMITTENT:
            result["is_valid"] = False
            result["errors"].append(f"Colaborador {employee.name} não é trabalhador intermitente (contrato: {employee.contract_type.value})")
            return result
        
        if employee.sector_id != sector_id:
            result["warnings"].append(f"Colaborador pertence a outro setor (ID: {employee.sector_id})")
        
        conv_datetime = convocation_datetime or datetime.now()
        shift_datetime = datetime.combine(conv_date, start_time)
        
        advance_check = self.legal_rules.validate_convocation_advance_time(
            conv_datetime, shift_datetime
        )
        result["checks"].append({"name": "advance_time", **advance_check})
        if not advance_check["is_valid"]:
            result["is_valid"] = False
            result["errors"].append(advance_check["message"])
        
        hours_check = self.legal_rules.validate_daily_hours(total_hours)
        result["checks"].append({"name": "daily_hours", **hours_check})
        if not hours_check["is_valid"]:
            result["is_valid"] = False
            result["errors"].append(hours_check["message"])
        
        week_start = conv_date - timedelta(days=conv_date.weekday())
        week_end = week_start + timedelta(days=6)
        
        existing_convocations = self.db.query(Convocation).filter(
            Convocation.employee_id == employee_id,
            Convocation.date >= week_start,
            Convocation.date <= week_end,
            Convocation.status.in_([ConvocationStatus.PENDING, ConvocationStatus.ACCEPTED])
        ).all()
        
        weekly_hours = sum(c.total_hours for c in existing_convocations) + total_hours
        weekly_check = self.legal_rules.validate_weekly_hours(weekly_hours)
        result["checks"].append({"name": "weekly_hours", "projected_hours": weekly_hours, **weekly_check})
        if not weekly_check["is_valid"]:
            result["is_valid"] = False
            result["errors"].append(weekly_check["message"])
        
        if employee.last_full_week_off:
            week_off_check = self.legal_rules.check_full_week_off_needed(
                employee.last_full_week_off, conv_date
            )
            result["checks"].append({"name": "week_off", **week_off_check})
            if week_off_check["week_off_needed"]:
                result["is_valid"] = False
                result["errors"].append(week_off_check["message"])
            elif week_off_check.get("approaching_limit"):
                result["warnings"].append(week_off_check["message"])
        
        same_day_convocations = self.db.query(Convocation).filter(
            Convocation.employee_id == employee_id,
            Convocation.date == conv_date,
            Convocation.status.in_([ConvocationStatus.PENDING, ConvocationStatus.ACCEPTED])
        ).all()
        
        if same_day_convocations:
            result["is_valid"] = False
            result["errors"].append(f"Colaborador já possui convocação para {conv_date}")
        
        return result
    
    def create_convocation(
        self,
        employee_id: int,
        sector_id: int,
        conv_date: date,
        start_time: time,
        end_time: time,
        total_hours: float,
        response_deadline: datetime,
        activity_id: Optional[int] = None,
        daily_shift_id: Optional[int] = None,
        weekly_schedule_id: Optional[int] = None,
        forecast_run_id: Optional[int] = None,
        generated_from: ConvocationOrigin = ConvocationOrigin.MANUAL,
        break_minutes: int = 60,
        operational_justification: Optional[str] = None,
        replaced_convocation_id: Optional[int] = None,
        skip_validation: bool = False
    ) -> Tuple[Optional[Convocation], Dict]:
        
        validation = {"is_valid": True, "errors": [], "warnings": []}
        
        if not skip_validation:
            validation = self.validate_convocation(
                employee_id=employee_id,
                sector_id=sector_id,
                conv_date=conv_date,
                start_time=start_time,
                end_time=end_time,
                total_hours=total_hours
            )
        
        convocation = Convocation(
            employee_id=employee_id,
            sector_id=sector_id,
            activity_id=activity_id,
            daily_shift_id=daily_shift_id,
            weekly_schedule_id=weekly_schedule_id,
            forecast_run_id=forecast_run_id,
            date=conv_date,
            start_time=start_time,
            end_time=end_time,
            break_minutes=break_minutes,
            total_hours=total_hours,
            status=ConvocationStatus.PENDING,
            generated_from=generated_from,
            response_deadline=response_deadline,
            sent_at=datetime.now(),
            operational_justification=operational_justification,
            replaced_convocation_id=replaced_convocation_id,
            legal_validation_passed=validation["is_valid"],
            legal_validation_errors="; ".join(validation["errors"]) if validation["errors"] else None,
            legal_validation_warnings="; ".join(validation["warnings"]) if validation["warnings"] else None
        )
        
        if not validation["is_valid"]:
            return None, validation
        
        self.db.add(convocation)
        self.db.flush()
        
        self._log_audit(
            action=AuditAction.CONVOCATION_CREATED,
            entity_type="convocation",
            entity_id=convocation.id,
            description=f"Convocação criada para colaborador {employee_id} em {conv_date}",
            new_values={
                "employee_id": employee_id,
                "sector_id": sector_id,
                "date": conv_date.isoformat(),
                "total_hours": total_hours,
                "generated_from": generated_from.value,
                "response_deadline": response_deadline.isoformat()
            }
        )
        
        return convocation, validation
    
    def accept_convocation(self, convocation_id: int, response_notes: Optional[str] = None) -> Dict:
        convocation = self.db.query(Convocation).filter(Convocation.id == convocation_id).first()
        
        if not convocation:
            return {"success": False, "error": "Convocação não encontrada"}
        
        if convocation.status != ConvocationStatus.PENDING:
            return {"success": False, "error": f"Convocação não está pendente (status: {convocation.status.value})"}
        
        if datetime.now() > convocation.response_deadline:
            convocation.status = ConvocationStatus.EXPIRED
            self.db.commit()
            return {"success": False, "error": "Prazo de resposta expirado"}
        
        convocation.status = ConvocationStatus.ACCEPTED
        convocation.responded_at = datetime.now()
        convocation.response_notes = response_notes
        
        self.db.commit()
        
        self._log_audit(
            action=AuditAction.CONVOCATION_ACCEPTED,
            entity_type="convocation",
            entity_id=convocation_id,
            description=f"Convocação aceita pelo colaborador {convocation.employee_id}",
            new_values={"status": "aceita", "responded_at": convocation.responded_at.isoformat()}
        )
        
        return {"success": True, "convocation": convocation}
    
    def decline_convocation(
        self,
        convocation_id: int,
        decline_reason: Optional[str] = None,
        response_notes: Optional[str] = None,
        auto_reschedule: bool = True
    ) -> Dict:
        convocation = self.db.query(Convocation).filter(Convocation.id == convocation_id).first()
        
        if not convocation:
            return {"success": False, "error": "Convocação não encontrada"}
        
        if convocation.status != ConvocationStatus.PENDING:
            return {"success": False, "error": f"Convocação não está pendente (status: {convocation.status.value})"}
        
        convocation.status = ConvocationStatus.DECLINED
        convocation.responded_at = datetime.now()
        convocation.decline_reason = decline_reason
        convocation.response_notes = response_notes
        
        self.db.commit()
        
        self._log_audit(
            action=AuditAction.CONVOCATION_DECLINED,
            entity_type="convocation",
            entity_id=convocation_id,
            description=f"Convocação recusada pelo colaborador {convocation.employee_id}",
            new_values={
                "status": "recusada",
                "decline_reason": decline_reason,
                "responded_at": convocation.responded_at.isoformat()
            }
        )
        
        result = {"success": True, "convocation": convocation, "reschedule_result": None}
        
        if auto_reschedule:
            reschedule_result = self.trigger_reschedule(convocation)
            result["reschedule_result"] = reschedule_result
        
        return result
    
    def cancel_convocation(self, convocation_id: int, cancellation_reason: str) -> Dict:
        convocation = self.db.query(Convocation).filter(Convocation.id == convocation_id).first()
        
        if not convocation:
            return {"success": False, "error": "Convocação não encontrada"}
        
        if convocation.status not in [ConvocationStatus.PENDING, ConvocationStatus.ACCEPTED]:
            return {"success": False, "error": f"Não é possível cancelar convocação com status {convocation.status.value}"}
        
        old_status = convocation.status.value
        convocation.status = ConvocationStatus.CANCELLED
        convocation.response_notes = cancellation_reason
        
        self.db.commit()
        
        self._log_audit(
            action=AuditAction.CONVOCATION_CANCELLED,
            entity_type="convocation",
            entity_id=convocation_id,
            description=f"Convocação cancelada: {cancellation_reason}",
            old_values={"status": old_status},
            new_values={"status": "cancelada", "reason": cancellation_reason}
        )
        
        return {"success": True, "convocation": convocation}
    
    def expire_pending_convocations(self) -> Dict:
        now = datetime.now()
        
        expired = self.db.query(Convocation).filter(
            Convocation.status == ConvocationStatus.PENDING,
            Convocation.response_deadline < now
        ).all()
        
        expired_count = 0
        reschedule_results = []
        
        for convocation in expired:
            convocation.status = ConvocationStatus.EXPIRED
            expired_count += 1
            
            self._log_audit(
                action=AuditAction.CONVOCATION_EXPIRED,
                entity_type="convocation",
                entity_id=convocation.id,
                description=f"Convocação expirada automaticamente (prazo: {convocation.response_deadline})",
                new_values={"status": "expirada"}
            )
            
            reschedule_result = self.trigger_reschedule(convocation)
            reschedule_results.append(reschedule_result)
        
        self.db.commit()
        
        return {
            "expired_count": expired_count,
            "reschedule_results": reschedule_results
        }
    
    def trigger_reschedule(self, original_convocation: Convocation) -> Dict:
        result = {
            "success": False,
            "original_convocation_id": original_convocation.id,
            "replacement_convocation_id": None,
            "eligible_employees_found": 0,
            "message": "",
            "errors": []
        }
        
        self._log_audit(
            action=AuditAction.RESCHEDULE_TRIGGERED,
            entity_type="convocation",
            entity_id=original_convocation.id,
            description=f"Reescala automática disparada para {original_convocation.date}",
            extra_data={
                "sector_id": original_convocation.sector_id,
                "date": original_convocation.date.isoformat(),
                "hours_needed": original_convocation.total_hours
            }
        )
        
        eligible_employees = self._find_eligible_employees(
            sector_id=original_convocation.sector_id,
            activity_id=original_convocation.activity_id,
            conv_date=original_convocation.date,
            start_time=original_convocation.start_time,
            end_time=original_convocation.end_time,
            total_hours=original_convocation.total_hours,
            exclude_employee_id=original_convocation.employee_id
        )
        
        result["eligible_employees_found"] = len(eligible_employees)
        
        if not eligible_employees:
            result["message"] = "Nenhum colaborador elegível encontrado para reescala"
            return result
        
        for employee in eligible_employees:
            new_deadline = datetime.now() + timedelta(hours=72)
            
            new_convocation, validation = self.create_convocation(
                employee_id=employee.id,
                sector_id=original_convocation.sector_id,
                conv_date=original_convocation.date,
                start_time=original_convocation.start_time,
                end_time=original_convocation.end_time,
                total_hours=original_convocation.total_hours,
                response_deadline=new_deadline,
                activity_id=original_convocation.activity_id,
                daily_shift_id=original_convocation.daily_shift_id,
                weekly_schedule_id=original_convocation.weekly_schedule_id,
                forecast_run_id=original_convocation.forecast_run_id,
                generated_from=ConvocationOrigin.RESCHEDULE,
                break_minutes=original_convocation.break_minutes,
                operational_justification=f"Reescala automática (convocação original: {original_convocation.id})",
                replaced_convocation_id=original_convocation.id
            )
            
            if new_convocation:
                original_convocation.replacement_convocation_id = new_convocation.id
                self.db.commit()
                
                result["success"] = True
                result["replacement_convocation_id"] = new_convocation.id
                result["message"] = f"Reescala bem-sucedida: nova convocação para {employee.name}"
                return result
            else:
                result["errors"].append(f"Colaborador {employee.name}: {'; '.join(validation['errors'])}")
        
        result["message"] = "Não foi possível criar convocação de reescala para nenhum colaborador elegível"
        return result
    
    def _find_eligible_employees(
        self,
        sector_id: int,
        activity_id: Optional[int],
        conv_date: date,
        start_time: time,
        end_time: time,
        total_hours: float,
        exclude_employee_id: int
    ) -> List[Employee]:
        query = self.db.query(Employee).filter(
            Employee.sector_id == sector_id,
            Employee.is_active == True,
            Employee.id != exclude_employee_id,
            Employee.contract_type == ContractType.INTERMITTENT
        )
        
        employees = query.all()
        eligible = []
        
        for employee in employees:
            validation = self.validate_convocation(
                employee_id=employee.id,
                sector_id=sector_id,
                conv_date=conv_date,
                start_time=start_time,
                end_time=end_time,
                total_hours=total_hours
            )
            
            if validation["is_valid"]:
                if activity_id:
                    can_do_activity = self.db.query(RoleActivity).filter(
                        RoleActivity.role_id == employee.role_id,
                        RoleActivity.activity_id == activity_id,
                        RoleActivity.is_active == True
                    ).first()
                    
                    if can_do_activity:
                        eligible.append(employee)
                else:
                    eligible.append(employee)
        
        return eligible
    
    def generate_convocations_from_schedule(
        self,
        weekly_schedule_id: int,
        response_deadline_hours: int = 72
    ) -> Dict:
        result = {
            "success": False,
            "convocations_created": 0,
            "convocations_blocked": 0,
            "errors": [],
            "warnings": [],
            "created_convocation_ids": []
        }
        
        schedule = self.db.query(WeeklySchedule).filter(
            WeeklySchedule.id == weekly_schedule_id
        ).first()
        
        if not schedule:
            result["errors"].append(f"Escala semanal {weekly_schedule_id} não encontrada")
            return result
        
        if schedule.status != ScheduleStatus.PUBLISHED:
            result["errors"].append(f"Escala deve estar publicada para gerar convocações (status: {schedule.status.value})")
            return result
        
        shifts = self.db.query(DailyShift).filter(
            DailyShift.weekly_schedule_id == weekly_schedule_id
        ).all()
        
        if not shifts:
            result["errors"].append("Escala não possui turnos definidos. Configure os turnos antes de gerar convocações.")
            return result
        
        response_deadline = datetime.now() + timedelta(hours=response_deadline_hours)
        
        for shift in shifts:
            existing = self.db.query(Convocation).filter(
                Convocation.daily_shift_id == shift.id
            ).first()
            
            if existing:
                result["warnings"].append(f"Turno {shift.id} já possui convocação")
                continue
            
            convocation, validation = self.create_convocation(
                employee_id=shift.employee_id,
                sector_id=schedule.sector_id,
                conv_date=shift.date,
                start_time=shift.start_time,
                end_time=shift.end_time,
                total_hours=shift.planned_hours,
                response_deadline=response_deadline,
                activity_id=None,
                daily_shift_id=shift.id,
                weekly_schedule_id=weekly_schedule_id,
                generated_from=ConvocationOrigin.BASELINE
            )
            
            if convocation:
                result["convocations_created"] += 1
                result["created_convocation_ids"].append(convocation.id)
            else:
                result["convocations_blocked"] += 1
                result["errors"].append(
                    f"Turno {shift.id} ({shift.date}): {'; '.join(validation['errors'])}"
                )
        
        self.db.commit()
        result["success"] = True
        
        return result
    
    def get_convocation_stats(
        self,
        sector_id: Optional[int] = None,
        week_start: Optional[date] = None
    ) -> Dict:
        query = self.db.query(Convocation)
        
        if sector_id:
            query = query.filter(Convocation.sector_id == sector_id)
        
        if week_start:
            week_end = week_start + timedelta(days=6)
            query = query.filter(
                Convocation.date >= week_start,
                Convocation.date <= week_end
            )
        
        convocations = query.all()
        
        total = len(convocations)
        pending = sum(1 for c in convocations if c.status == ConvocationStatus.PENDING)
        accepted = sum(1 for c in convocations if c.status == ConvocationStatus.ACCEPTED)
        declined = sum(1 for c in convocations if c.status == ConvocationStatus.DECLINED)
        expired = sum(1 for c in convocations if c.status == ConvocationStatus.EXPIRED)
        cancelled = sum(1 for c in convocations if c.status == ConvocationStatus.CANCELLED)
        
        responded = accepted + declined
        acceptance_rate = (accepted / responded * 100) if responded > 0 else 0.0
        
        return {
            "total": total,
            "pending": pending,
            "accepted": accepted,
            "declined": declined,
            "expired": expired,
            "cancelled": cancelled,
            "acceptance_rate": round(acceptance_rate, 1)
        }
    
    def _log_audit(
        self,
        action: AuditAction,
        entity_type: str,
        entity_id: int,
        description: str,
        old_values: Optional[Dict] = None,
        new_values: Optional[Dict] = None,
        extra_data: Optional[Dict] = None
    ):
        import json
        audit = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            old_values=json.dumps(old_values) if old_values else None,
            new_values=json.dumps(new_values) if new_values else None,
            extra_data=extra_data or {}
        )
        self.db.add(audit)
