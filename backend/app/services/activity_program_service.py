from datetime import date, time, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.activity_program import (
    ActivityProgramWeek, ActivityProgramItem, 
    ProgramWeekStatus, ProgramItemSource
)
from app.models.sector import Sector
from app.models.governance_activity import GovernanceActivity
from app.models.governance_module import ForecastRun, ForecastRunType, ForecastRunStatus
from app.models.data_lake import OccupancyLatest
from app.models.audit_log import AuditLog, AuditAction
from app.models.governance_activity import ActivityClassification
from app.services import regra_calculo_service


class ActivityProgramService:
    
    @staticmethod
    def get_week_bounds(week_start: date) -> tuple:
        week_end = week_start + timedelta(days=6)
        return week_start, week_end
    
    @staticmethod
    def create_program_week(
        db: Session,
        sector_id: int,
        forecast_run_id: int,
        week_start: date,
        mode: str = "MANUAL",
        created_by: str = "system"
    ) -> ActivityProgramWeek:
        existing = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.sector_id == sector_id,
            ActivityProgramWeek.forecast_run_id == forecast_run_id,
            ActivityProgramWeek.week_start == week_start
        ).first()
        
        if existing:
            return existing
        
        program_week = ActivityProgramWeek(
            sector_id=sector_id,
            forecast_run_id=forecast_run_id,
            week_start=week_start,
            status=ProgramWeekStatus.DRAFT,
            created_by=created_by
        )
        db.add(program_week)
        db.flush()
        
        if mode == "AUTO":
            validation = regra_calculo_service.validar_regras_para_modo_auto(db, sector_id)
            if not validation["pode_usar_auto"]:
                erros = validation.get("erros", [])
                msgs = [e.get("mensagem", str(e)) for e in erros]
                raise ValueError(f"Modo AUTO bloqueado: {'; '.join(msgs)}")
            
            ActivityProgramService._generate_auto_items_com_regras(db, program_week, created_by)
        
        db.commit()
        db.refresh(program_week)
        
        AuditLog.log(db, "activity_program_weeks", program_week.id, 
                     AuditAction.CREATE, created_by, 
                     {"mode": mode, "sector_id": sector_id})
        
        return program_week
    
    @staticmethod
    def _generate_auto_items(
        db: Session,
        program_week: ActivityProgramWeek,
        created_by: str
    ):
        sector = db.query(Sector).filter(Sector.id == program_week.sector_id).first()
        activities = db.query(GovernanceActivity).filter(
            GovernanceActivity.sector_id == program_week.sector_id,
            GovernanceActivity.is_active == True
        ).all()
        
        if not activities:
            return
        
        week_start, week_end = ActivityProgramService.get_week_bounds(program_week.week_start)
        
        forecast_run = db.query(ForecastRun).filter(
            ForecastRun.id == program_week.forecast_run_id
        ).first()
        
        from app.models.governance_module import ForecastDaily, SectorOperationalParameters
        forecast_data = {}
        if forecast_run:
            daily_forecasts = db.query(ForecastDaily).filter(
                ForecastDaily.forecast_run_id == forecast_run.id
            ).all()
            for df in daily_forecasts:
                forecast_data[df.target_date] = {
                    "occ_adj": df.occ_adj,
                    "occ_raw": df.occ_raw,
                    "bias_pp": df.bias_pp
                }
        
        sector_params = db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == program_week.sector_id
        ).first()
        total_rooms = sector_params.total_rooms if sector_params else 100
        
        is_governance = sector and sector.name.lower() in ["governança", "governanca", "housekeeping"]
        
        for day_offset in range(7):
            op_date = week_start + timedelta(days=day_offset)
            
            if op_date in forecast_data and forecast_data[op_date].get("occ_adj") is not None:
                occ_pct = forecast_data[op_date]["occ_adj"]
            else:
                occupancy = db.query(OccupancyLatest).filter(
                    OccupancyLatest.target_date == op_date
                ).first()
                occ_pct = occupancy.occupancy_pct if occupancy else 70.0
            
            if is_governance:
                ActivityProgramService._generate_governance_items(
                    db, program_week, op_date, activities, occ_pct, created_by, total_rooms
                )
            else:
                ActivityProgramService._generate_generic_items(
                    db, program_week, op_date, activities, occ_pct, created_by
                )
    
    @staticmethod
    def _generate_auto_items_com_regras(
        db: Session,
        program_week: ActivityProgramWeek,
        created_by: str
    ):
        """Gera itens usando regras de cálculo definidas para o setor."""
        from app.models.governance_module import ForecastDaily, SectorOperationalParameters
        
        sector = db.query(Sector).filter(Sector.id == program_week.sector_id).first()
        
        week_start, week_end = ActivityProgramService.get_week_bounds(program_week.week_start)
        
        forecast_run = db.query(ForecastRun).filter(
            ForecastRun.id == program_week.forecast_run_id
        ).first()
        
        forecast_data = {}
        if forecast_run:
            daily_forecasts = db.query(ForecastDaily).filter(
                ForecastDaily.forecast_run_id == forecast_run.id
            ).all()
            for df in daily_forecasts:
                forecast_data[df.target_date] = {
                    "occ_adj": df.occ_adj,
                    "occ_raw": df.occ_raw,
                    "bias_pp": df.bias_pp
                }
        
        sector_params = db.query(SectorOperationalParameters).filter(
            SectorOperationalParameters.sector_id == program_week.sector_id
        ).first()
        total_rooms = sector_params.total_rooms if sector_params else 100
        checkout_rate = 0.25
        
        dias_semana_map = {0: "SEG", 1: "TER", 2: "QUA", 3: "QUI", 4: "SEX", 5: "SAB", 6: "DOM"}
        
        for day_offset in range(7):
            op_date = week_start + timedelta(days=day_offset)
            dia_semana = dias_semana_map.get(op_date.weekday(), "SEG")
            
            if op_date in forecast_data and forecast_data[op_date].get("occ_adj") is not None:
                occ_pct = forecast_data[op_date]["occ_adj"]
            else:
                occupancy = db.query(OccupancyLatest).filter(
                    OccupancyLatest.target_date == op_date
                ).first()
                occ_pct = occupancy.occupancy_pct if occupancy else 70.0
            
            quartos_ocupados = int(total_rooms * (occ_pct / 100))
            checkouts = int(quartos_ocupados * checkout_rate)
            stayovers = quartos_ocupados - checkouts
            
            contexto = {
                "ocupacao": occ_pct / 100,
                "quartos_ocupados": quartos_ocupados,
                "checkout": checkouts,
                "checkin": checkouts,
                "stayover": stayovers,
                "dia_semana": dia_semana,
                "total_rooms": total_rooms
            }
            
            atividades_programadas = regra_calculo_service.obter_atividades_programacao(
                db, program_week.sector_id, contexto
            )
            
            for ativ_info in atividades_programadas:
                atividade = db.query(GovernanceActivity).filter(
                    GovernanceActivity.id == ativ_info["atividade_id"]
                ).first()
                
                if not atividade:
                    continue
                
                if atividade.workload_driver and atividade.workload_driver.value == "VARIABLE":
                    if "vago" in atividade.name.lower() or "checkout" in atividade.name.lower():
                        quantity = max(1, checkouts)
                    elif "estadia" in atividade.name.lower() or "stayover" in atividade.name.lower():
                        quantity = max(1, stayovers)
                    else:
                        quantity = max(1, quartos_ocupados)
                else:
                    quantity = 1
                
                workload = int(quantity * atividade.average_time_minutes)
                
                item = ActivityProgramItem(
                    program_week_id=program_week.id,
                    sector_id=program_week.sector_id,
                    activity_id=atividade.id,
                    op_date=op_date,
                    window_start=time(8, 0),
                    window_end=time(17, 0),
                    quantity=quantity,
                    workload_minutes=workload,
                    priority=1,
                    source=ProgramItemSource.AUTO,
                    drivers_json={
                        "ocupacao": occ_pct,
                        "dia_semana": dia_semana,
                        "quartos_ocupados": quartos_ocupados,
                        "regra_id": ativ_info.get("regra_id"),
                        "regra_nome": ativ_info.get("regra_nome"),
                        "calculation": f"{quantity} unidades x {atividade.average_time_minutes} min"
                    },
                    created_by=created_by
                )
                db.add(item)
    
    @staticmethod
    def _generate_governance_items(
        db: Session,
        program_week: ActivityProgramWeek,
        op_date: date,
        activities: List[GovernanceActivity],
        occ_pct: float,
        created_by: str,
        total_rooms: int = 100
    ):
        checkout_rate = 0.25
        stayover_rate = occ_pct / 100 * (1 - checkout_rate)
        departure_rate = occ_pct / 100 * checkout_rate
        
        room_count = total_rooms
        departures = int(room_count * departure_rate)
        stayovers = int(room_count * stayover_rate)
        
        checkout_activity = next(
            (a for a in activities if "vago" in a.name.lower() or "checkout" in a.name.lower() or "saída" in a.name.lower()),
            activities[0] if activities else None
        )
        
        stayover_activity = next(
            (a for a in activities if "estadia" in a.name.lower() or "ocupado" in a.name.lower()),
            activities[1] if len(activities) > 1 else (activities[0] if activities else None)
        )
        
        if checkout_activity:
            workload = int(departures * checkout_activity.average_time_minutes)
            item = ActivityProgramItem(
                program_week_id=program_week.id,
                sector_id=program_week.sector_id,
                activity_id=checkout_activity.id,
                op_date=op_date,
                window_start=time(10, 0),
                window_end=time(15, 0),
                quantity=max(1, departures),
                workload_minutes=workload,
                priority=1,
                source=ProgramItemSource.AUTO,
                drivers_json={
                    "occupancy_pct": occ_pct,
                    "departure_rate": departure_rate,
                    "estimated_departures": departures,
                    "avg_time_min": checkout_activity.average_time_minutes,
                    "calculation": f"{departures} quartos x {checkout_activity.average_time_minutes} min"
                },
                created_by=created_by
            )
            db.add(item)
        
        if stayover_activity and stayover_activity != checkout_activity:
            workload = int(stayovers * stayover_activity.average_time_minutes)
            item = ActivityProgramItem(
                program_week_id=program_week.id,
                sector_id=program_week.sector_id,
                activity_id=stayover_activity.id,
                op_date=op_date,
                window_start=time(9, 0),
                window_end=time(14, 0),
                quantity=max(1, stayovers),
                workload_minutes=workload,
                priority=2,
                source=ProgramItemSource.AUTO,
                drivers_json={
                    "occupancy_pct": occ_pct,
                    "stayover_rate": stayover_rate,
                    "estimated_stayovers": stayovers,
                    "avg_time_min": stayover_activity.average_time_minutes,
                    "calculation": f"{stayovers} quartos x {stayover_activity.average_time_minutes} min"
                },
                created_by=created_by
            )
            db.add(item)
    
    @staticmethod
    def _generate_generic_items(
        db: Session,
        program_week: ActivityProgramWeek,
        op_date: date,
        activities: List[GovernanceActivity],
        occ_pct: float,
        created_by: str
    ):
        for activity in activities[:3]:
            quantity = max(1, int(occ_pct / 20))
            workload = int(quantity * activity.average_time_minutes)
            
            item = ActivityProgramItem(
                program_week_id=program_week.id,
                sector_id=program_week.sector_id,
                activity_id=activity.id,
                op_date=op_date,
                window_start=time(8, 0),
                window_end=time(17, 0),
                quantity=quantity,
                workload_minutes=workload,
                priority=3,
                source=ProgramItemSource.AUTO,
                drivers_json={
                    "occupancy_pct": occ_pct,
                    "base_calculation": "generic",
                    "avg_time_min": activity.average_time_minutes
                },
                created_by=created_by
            )
            db.add(item)
    
    @staticmethod
    def add_item(
        db: Session,
        program_week_id: int,
        activity_id: int,
        op_date: date,
        quantity: int = 1,
        workload_minutes: Optional[int] = None,
        priority: int = 3,
        window_start: Optional[time] = None,
        window_end: Optional[time] = None,
        notes: Optional[str] = None,
        created_by: str = "user"
    ) -> ActivityProgramItem:
        program_week = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.id == program_week_id
        ).first()
        
        if not program_week:
            raise ValueError("Program week not found")
        
        if program_week.status == ProgramWeekStatus.LOCKED:
            raise ValueError("Cannot modify locked program")
        
        activity = db.query(GovernanceActivity).filter(
            GovernanceActivity.id == activity_id
        ).first()
        
        if not activity:
            raise ValueError("Activity not found")
        
        if activity.sector_id != program_week.sector_id:
            raise ValueError("Activity does not belong to the program's sector")
        
        week_start, week_end = ActivityProgramService.get_week_bounds(program_week.week_start)
        if not (week_start <= op_date <= week_end):
            raise ValueError("Date is outside the program week")
        
        if window_start and window_end and window_start >= window_end:
            raise ValueError("Window start must be before window end")
        
        if quantity < 1:
            raise ValueError("Quantity must be at least 1")
        
        if workload_minutes is not None and workload_minutes < 0:
            raise ValueError("Workload cannot be negative")
        
        if workload_minutes is None:
            workload_minutes = int(quantity * activity.average_time_minutes)
        
        item = ActivityProgramItem(
            program_week_id=program_week_id,
            sector_id=program_week.sector_id,
            activity_id=activity_id,
            op_date=op_date,
            window_start=window_start,
            window_end=window_end,
            quantity=quantity,
            workload_minutes=workload_minutes,
            priority=priority,
            source=ProgramItemSource.MANUAL,
            notes=notes,
            created_by=created_by
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        
        return item
    
    @staticmethod
    def update_item(
        db: Session,
        item_id: int,
        updates: Dict[str, Any],
        updated_by: str = "user"
    ) -> ActivityProgramItem:
        item = db.query(ActivityProgramItem).filter(
            ActivityProgramItem.id == item_id
        ).first()
        
        if not item:
            raise ValueError("Item not found")
        
        program_week = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.id == item.program_week_id
        ).first()
        
        if program_week and program_week.status == ProgramWeekStatus.LOCKED:
            raise ValueError("Cannot modify locked program")
        
        allowed_fields = ["quantity", "workload_minutes", "priority", 
                          "window_start", "window_end", "notes", "op_date"]
        
        for field, value in updates.items():
            if field in allowed_fields:
                if field == "quantity" and value < 1:
                    raise ValueError("Quantity must be at least 1")
                if field == "workload_minutes" and value is not None and value < 0:
                    raise ValueError("Workload cannot be negative")
                setattr(item, field, value)
        
        item.updated_by = updated_by
        db.commit()
        db.refresh(item)
        
        return item
    
    @staticmethod
    def delete_item(db: Session, item_id: int, deleted_by: str = "user") -> bool:
        item = db.query(ActivityProgramItem).filter(
            ActivityProgramItem.id == item_id
        ).first()
        
        if not item:
            return False
        
        program_week = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.id == item.program_week_id
        ).first()
        
        if program_week and program_week.status == ProgramWeekStatus.LOCKED:
            raise ValueError("Cannot modify locked program")
        
        db.delete(item)
        db.commit()
        
        return True
    
    @staticmethod
    def approve_program(
        db: Session, 
        program_week_id: int, 
        approved_by: str = "user"
    ) -> ActivityProgramWeek:
        program_week = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.id == program_week_id
        ).first()
        
        if not program_week:
            raise ValueError("Program week not found")
        
        if program_week.status == ProgramWeekStatus.LOCKED:
            raise ValueError("Program is already locked")
        
        if program_week.status == ProgramWeekStatus.APPROVED:
            raise ValueError("Program is already approved")
        
        if program_week.status != ProgramWeekStatus.DRAFT:
            raise ValueError("Only DRAFT programs can be approved")
        
        program_week.status = ProgramWeekStatus.APPROVED
        program_week.updated_by = approved_by
        db.commit()
        db.refresh(program_week)
        
        AuditLog.log(db, "activity_program_weeks", program_week.id,
                     AuditAction.UPDATE, approved_by,
                     {"action": "approve", "new_status": "APPROVED"})
        
        return program_week
    
    @staticmethod
    def lock_program(
        db: Session, 
        program_week_id: int, 
        locked_by: str = "admin"
    ) -> ActivityProgramWeek:
        program_week = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.id == program_week_id
        ).first()
        
        if not program_week:
            raise ValueError("Program week not found")
        
        if program_week.status == ProgramWeekStatus.LOCKED:
            raise ValueError("Program is already locked")
        
        if program_week.status != ProgramWeekStatus.APPROVED:
            raise ValueError("Only APPROVED programs can be locked")
        
        program_week.status = ProgramWeekStatus.LOCKED
        program_week.updated_by = locked_by
        db.commit()
        db.refresh(program_week)
        
        AuditLog.log(db, "activity_program_weeks", program_week.id,
                     AuditAction.UPDATE, locked_by,
                     {"action": "lock", "new_status": "LOCKED"})
        
        return program_week
    
    @staticmethod
    def create_adjustment(
        db: Session,
        baseline_forecast_run_id: int,
        sector_id: int,
        reason: str,
        created_by: str = "user"
    ) -> Dict[str, Any]:
        baseline_run = db.query(ForecastRun).filter(
            ForecastRun.id == baseline_forecast_run_id
        ).first()
        
        if not baseline_run:
            raise ValueError("Baseline forecast run not found")
        
        adjustment_run = ForecastRun(
            sector_id=sector_id,
            run_type=ForecastRunType.MANUAL,
            run_date=date.today(),
            horizon_start=baseline_run.horizon_start,
            horizon_end=baseline_run.horizon_end,
            status=ForecastRunStatus.COMPLETED,
            superseded_by_run_id=None,
            notes=f"Adjustment: {reason}",
            created_by=created_by
        )
        db.add(adjustment_run)
        db.flush()
        
        original_program = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.forecast_run_id == baseline_forecast_run_id,
            ActivityProgramWeek.sector_id == sector_id
        ).first()
        
        if original_program:
            new_program = ActivityProgramWeek(
                sector_id=sector_id,
                forecast_run_id=adjustment_run.id,
                week_start=original_program.week_start,
                status=ProgramWeekStatus.DRAFT,
                created_by=created_by
            )
            db.add(new_program)
            db.flush()
            
            for item in original_program.items:
                new_item = ActivityProgramItem(
                    program_week_id=new_program.id,
                    sector_id=item.sector_id,
                    activity_id=item.activity_id,
                    op_date=item.op_date,
                    window_start=item.window_start,
                    window_end=item.window_end,
                    quantity=item.quantity,
                    workload_minutes=item.workload_minutes,
                    priority=item.priority,
                    source=item.source,
                    drivers_json=item.drivers_json,
                    notes=item.notes,
                    created_by=created_by
                )
                db.add(new_item)
        
        db.commit()
        
        return {
            "adjustment_run_id": adjustment_run.id,
            "reason": reason,
            "based_on_baseline_id": baseline_forecast_run_id
        }
    
    @staticmethod
    def get_programming_inputs(
        db: Session,
        sector_id: int,
        week_start: date,
        forecast_run_id: int
    ) -> Dict[str, Any]:
        program_week = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.sector_id == sector_id,
            ActivityProgramWeek.forecast_run_id == forecast_run_id,
            ActivityProgramWeek.week_start == week_start
        ).first()
        
        if not program_week:
            return {"error": "Program not found", "items_by_day": {}}
        
        items_by_day = {}
        total_workload = 0
        
        for item in program_week.items:
            day_key = item.op_date.isoformat()
            if day_key not in items_by_day:
                items_by_day[day_key] = []
            
            items_by_day[day_key].append({
                "activity_id": item.activity_id,
                "activity_name": item.activity.name if item.activity else None,
                "quantity": item.quantity,
                "workload_minutes": item.workload_minutes,
                "window_start": item.window_start.isoformat() if item.window_start else None,
                "window_end": item.window_end.isoformat() if item.window_end else None,
                "priority": item.priority
            })
            total_workload += item.workload_minutes or 0
        
        return {
            "program_week_id": program_week.id,
            "status": program_week.status.value,
            "items_by_day": items_by_day,
            "total_workload_minutes": total_workload
        }
