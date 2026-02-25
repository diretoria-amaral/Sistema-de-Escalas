from datetime import time, datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models import ShiftTemplate, LaborRules, AuditLog, AuditAction


class ShiftTemplateService:
    """
    PROMPT 16: Serviço para gerenciamento de templates de turno.
    
    Templates definem padrões reutilizáveis de jornada por setor,
    servindo como ponte entre Programação de Atividades e Geração de Escalas.
    """
    
    MIN_BREAK_MINUTES = 60
    MAX_SHIFT_HOURS = 12
    
    @staticmethod
    def _calculate_work_hours(start: time, end: time, break_minutes: int) -> float:
        start_dt = datetime.combine(datetime.today(), start)
        end_dt = datetime.combine(datetime.today(), end)
        
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)
        
        total_minutes = (end_dt - start_dt).total_seconds() / 60
        work_minutes = total_minutes - break_minutes
        return work_minutes / 60
    
    @staticmethod
    def _is_overnight_shift(start: time, end: time) -> bool:
        return end <= start
    
    @staticmethod
    def validate_template(
        db: Session,
        start_time: time,
        end_time: time,
        break_minutes: int,
        min_hours: int,
        max_hours: int
    ) -> Dict[str, Any]:
        errors = []
        warnings = []
        
        if start_time >= end_time:
            start_dt = datetime.combine(datetime.today(), start_time)
            end_dt = datetime.combine(datetime.today(), end_time)
            end_dt += timedelta(days=1)
        
        work_hours = ShiftTemplateService._calculate_work_hours(start_time, end_time, break_minutes)
        
        labor_rules = db.query(LaborRules).filter(LaborRules.is_active == True).first()
        
        is_overnight = ShiftTemplateService._is_overnight_shift(start_time, end_time)
        if is_overnight:
            warnings.append("Turno noturno detectado (atravessa meia-noite)")
        
        if work_hours > ShiftTemplateService.MAX_SHIFT_HOURS:
            errors.append(f"Carga horária ({work_hours:.1f}h) excede limite máximo de {ShiftTemplateService.MAX_SHIFT_HOURS}h")
        
        if work_hours <= 0:
            errors.append("Carga horária deve ser positiva")
        
        if labor_rules:
            if work_hours > labor_rules.max_daily_hours:
                errors.append(f"Carga horária ({work_hours:.1f}h) excede limite legal diário ({labor_rules.max_daily_hours}h)")
            
            min_break_minutes = int(labor_rules.min_break_hours * 60) if labor_rules.min_break_hours else 60
            no_break_threshold = labor_rules.no_break_threshold_hours or 4.0
            
            if work_hours > no_break_threshold and break_minutes < min_break_minutes:
                errors.append(f"Intervalo ({break_minutes}min) abaixo do mínimo legal ({min_break_minutes}min) para jornadas > {no_break_threshold}h")
            
            if work_hours <= no_break_threshold and break_minutes > 0:
                pass
        
        if min_hours > max_hours:
            errors.append("Mínimo de horas não pode ser maior que máximo")
        
        if work_hours < float(min_hours):
            warnings.append(f"Carga horária calculada ({work_hours:.1f}h) é menor que mínimo configurado ({min_hours}h)")
        
        if work_hours > float(max_hours):
            warnings.append(f"Carga horária calculada ({work_hours:.1f}h) é maior que máximo configurado ({max_hours}h)")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "calculated_hours": round(work_hours, 2)
        }
    
    @staticmethod
    def create_template(
        db: Session,
        sector_id: int,
        name: str,
        start_time: time,
        end_time: time,
        break_minutes: int = 60,
        min_hours: int = 4,
        max_hours: int = 8,
        valid_weekdays: List[int] = None
    ) -> Dict[str, Any]:
        if valid_weekdays is None:
            valid_weekdays = [0, 1, 2, 3, 4, 5, 6]
        
        validation = ShiftTemplateService.validate_template(
            db, start_time, end_time, break_minutes, min_hours, max_hours
        )
        
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "template": None
            }
        
        template = ShiftTemplate(
            sector_id=sector_id,
            name=name,
            start_time=start_time,
            end_time=end_time,
            break_minutes=break_minutes,
            min_hours=min_hours,
            max_hours=max_hours,
            valid_weekdays=valid_weekdays,
            is_active=True
        )
        
        db.add(template)
        db.commit()
        db.refresh(template)
        
        audit = AuditLog(
            action=AuditAction.TEMPLATE_CREATED,
            entity_type="ShiftTemplate",
            entity_id=template.id,
            description=f"Template '{name}' criado para setor {sector_id}",
            new_values={
                "name": name,
                "sector_id": sector_id,
                "start_time": str(start_time),
                "end_time": str(end_time),
                "break_minutes": break_minutes,
                "calculated_hours": validation["calculated_hours"]
            }
        )
        db.add(audit)
        db.commit()
        
        return {
            "success": True,
            "template": template,
            "calculated_hours": validation["calculated_hours"],
            "warnings": validation.get("warnings", [])
        }
    
    @staticmethod
    def update_template(
        db: Session,
        template_id: int,
        **kwargs
    ) -> Dict[str, Any]:
        template = db.query(ShiftTemplate).filter(ShiftTemplate.id == template_id).first()
        
        if not template:
            return {"success": False, "error": "Template não encontrado"}
        
        old_values = {
            "name": template.name,
            "start_time": str(template.start_time),
            "end_time": str(template.end_time),
            "break_minutes": template.break_minutes,
            "min_hours": template.min_hours,
            "max_hours": template.max_hours,
            "valid_weekdays": template.valid_weekdays,
            "is_active": template.is_active
        }
        
        start_time = kwargs.get("start_time", template.start_time)
        end_time = kwargs.get("end_time", template.end_time)
        break_minutes = kwargs.get("break_minutes", template.break_minutes)
        min_hours = kwargs.get("min_hours", template.min_hours)
        max_hours = kwargs.get("max_hours", template.max_hours)
        
        validation = ShiftTemplateService.validate_template(
            db, start_time, end_time, break_minutes, min_hours, max_hours
        )
        
        if not validation["valid"]:
            return {
                "success": False,
                "errors": validation["errors"],
                "template": None
            }
        
        for key, value in kwargs.items():
            if hasattr(template, key):
                setattr(template, key, value)
        
        db.commit()
        db.refresh(template)
        
        new_values = {
            "name": template.name,
            "start_time": str(template.start_time),
            "end_time": str(template.end_time),
            "break_minutes": template.break_minutes,
            "min_hours": template.min_hours,
            "max_hours": template.max_hours,
            "valid_weekdays": template.valid_weekdays,
            "is_active": template.is_active
        }
        
        audit = AuditLog(
            action=AuditAction.TEMPLATE_UPDATED,
            entity_type="ShiftTemplate",
            entity_id=template.id,
            description=f"Template '{template.name}' atualizado",
            old_values=old_values,
            new_values=new_values
        )
        db.add(audit)
        db.commit()
        
        return {
            "success": True,
            "template": template,
            "calculated_hours": validation["calculated_hours"],
            "warnings": validation.get("warnings", [])
        }
    
    @staticmethod
    def disable_template(db: Session, template_id: int) -> Dict[str, Any]:
        template = db.query(ShiftTemplate).filter(ShiftTemplate.id == template_id).first()
        
        if not template:
            return {"success": False, "error": "Template não encontrado"}
        
        template.is_active = False
        db.commit()
        
        audit = AuditLog(
            action=AuditAction.TEMPLATE_DISABLED,
            entity_type="ShiftTemplate",
            entity_id=template.id,
            description=f"Template '{template.name}' desativado"
        )
        db.add(audit)
        db.commit()
        
        return {"success": True, "template": template}
    
    @staticmethod
    def enable_template(db: Session, template_id: int) -> Dict[str, Any]:
        template = db.query(ShiftTemplate).filter(ShiftTemplate.id == template_id).first()
        
        if not template:
            return {"success": False, "error": "Template não encontrado"}
        
        template.is_active = True
        db.commit()
        db.refresh(template)
        
        return {"success": True, "template": template}
    
    @staticmethod
    def get_templates_by_sector(
        db: Session,
        sector_id: int,
        active_only: bool = True
    ) -> List[ShiftTemplate]:
        query = db.query(ShiftTemplate).filter(ShiftTemplate.sector_id == sector_id)
        
        if active_only:
            query = query.filter(ShiftTemplate.is_active == True)
        
        return query.order_by(ShiftTemplate.name).all()
    
    @staticmethod
    def get_all_templates(db: Session, active_only: bool = True) -> List[ShiftTemplate]:
        query = db.query(ShiftTemplate)
        
        if active_only:
            query = query.filter(ShiftTemplate.is_active == True)
        
        return query.order_by(ShiftTemplate.sector_id, ShiftTemplate.name).all()
    
    @staticmethod
    def get_template_by_id(db: Session, template_id: int) -> Optional[ShiftTemplate]:
        return db.query(ShiftTemplate).filter(ShiftTemplate.id == template_id).first()
    
    @staticmethod
    def match_programming_to_templates(
        db: Session,
        sector_id: int,
        daily_workload_minutes: Dict[str, int]
    ) -> Dict[str, Any]:
        """
        Sugere templates compatíveis para a carga de trabalho diária.
        
        Args:
            sector_id: ID do setor
            daily_workload_minutes: Dict com data (YYYY-MM-DD) -> minutos de trabalho
        
        Returns:
            Dict com sugestões de alocação de templates por dia
        """
        templates = ShiftTemplateService.get_templates_by_sector(db, sector_id, active_only=True)
        
        if not templates:
            return {
                "success": False,
                "error": "Nenhum template ativo encontrado para o setor",
                "suggestions": {}
            }
        
        template_info = []
        for t in templates:
            work_hours = ShiftTemplateService._calculate_work_hours(
                t.start_time, t.end_time, t.break_minutes
            )
            template_info.append({
                "id": t.id,
                "name": t.name,
                "work_minutes": int(work_hours * 60),
                "valid_weekdays": t.valid_weekdays,
                "start_time": str(t.start_time),
                "end_time": str(t.end_time)
            })
        
        suggestions = {}
        total_shifts_needed = 0
        
        for date_str, workload_minutes in daily_workload_minutes.items():
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                weekday = date_obj.weekday()
            except ValueError:
                continue
            
            valid_templates = [
                t for t in template_info
                if weekday in t["valid_weekdays"]
            ]
            
            if not valid_templates:
                suggestions[date_str] = {
                    "workload_minutes": workload_minutes,
                    "templates": [],
                    "warning": "Nenhum template válido para este dia da semana"
                }
                continue
            
            day_suggestions = []
            remaining = workload_minutes
            
            for tmpl in sorted(valid_templates, key=lambda x: -x["work_minutes"]):
                if remaining <= 0:
                    break
                
                shifts_needed = remaining // tmpl["work_minutes"]
                if shifts_needed > 0:
                    day_suggestions.append({
                        "template_id": tmpl["id"],
                        "template_name": tmpl["name"],
                        "shifts": shifts_needed,
                        "hours_per_shift": tmpl["work_minutes"] / 60,
                        "total_hours": (shifts_needed * tmpl["work_minutes"]) / 60,
                        "time_window": f"{tmpl['start_time'][:5]} - {tmpl['end_time'][:5]}"
                    })
                    remaining -= shifts_needed * tmpl["work_minutes"]
                    total_shifts_needed += shifts_needed
            
            if remaining > 0 and valid_templates:
                smallest_template = min(valid_templates, key=lambda x: x["work_minutes"])
                day_suggestions.append({
                    "template_id": smallest_template["id"],
                    "template_name": smallest_template["name"],
                    "shifts": 1,
                    "hours_per_shift": smallest_template["work_minutes"] / 60,
                    "total_hours": smallest_template["work_minutes"] / 60,
                    "time_window": f"{smallest_template['start_time'][:5]} - {smallest_template['end_time'][:5]}",
                    "note": f"Cobre {remaining}min restantes"
                })
                total_shifts_needed += 1
            
            suggestions[date_str] = {
                "workload_minutes": workload_minutes,
                "templates": day_suggestions
            }
        
        return {
            "success": True,
            "suggestions": suggestions,
            "total_shifts_suggested": total_shifts_needed,
            "available_templates": len(templates)
        }
