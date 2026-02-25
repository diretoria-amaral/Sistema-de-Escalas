from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta
from pydantic import BaseModel
from app.database import get_db
from app.models.sector import Sector
from app.models.employee import Employee, ContractType
from app.models.weekly_schedule import WeeklySchedule, ScheduleStatus
from app.models.weekly_parameters import WeeklyParameters
from app.schemas.weekly_schedule import WeeklyScheduleCreate, WeeklyScheduleResponse, ScheduleGenerationRequest
from app.legal_rules import ScheduleValidator
from app.services.schedule_generator import ScheduleGenerator

router = APIRouter(prefix="/schedules", tags=["Schedules"])


class GenerarEscalaRequest(BaseModel):
    """Request para gerar escala sugestiva de governança."""
    semana_inicio: date
    sector_id: Optional[int] = None


@router.get("/", response_model=List[WeeklyScheduleResponse])
def list_schedules(
    sector_id: int = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    query = db.query(WeeklySchedule)
    if sector_id:
        query = query.filter(WeeklySchedule.sector_id == sector_id)
    schedules = query.order_by(WeeklySchedule.week_start.desc()).offset(skip).limit(limit).all()
    return schedules


@router.get("/check", response_model=dict)
def check_schedule_status(
    sector_id: int,
    week_start: date,
    db: Session = Depends(get_db)
):
    from app.models.daily_shift import DailyShift
    
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        return {
            "has_schedule": False,
            "schedule": None,
            "can_generate_convocations": False,
            "blocking_errors": ["Setor não encontrado"],
            "shifts_count": 0
        }
    
    schedule = db.query(WeeklySchedule).filter(
        WeeklySchedule.sector_id == sector_id,
        WeeklySchedule.week_start == week_start
    ).first()
    
    if not schedule:
        return {
            "has_schedule": False,
            "schedule": None,
            "can_generate_convocations": False,
            "blocking_errors": [f"Nenhuma escala encontrada para o setor '{sector.name}' na semana de {week_start.isoformat()}. Gere a escala primeiro no módulo de Governança."],
            "shifts_count": 0
        }
    
    shifts = db.query(DailyShift).filter(
        DailyShift.weekly_schedule_id == schedule.id
    ).all()
    
    blocking_errors = []
    if schedule.status == ScheduleStatus.DRAFT:
        blocking_errors.append(f"Escala está em rascunho. Publique a escala antes de gerar convocações.")
    elif schedule.status == ScheduleStatus.CANCELLED:
        blocking_errors.append(f"Escala foi cancelada. Gere uma nova escala.")
    
    if len(shifts) == 0:
        blocking_errors.append("Escala não possui turnos definidos. Configure os turnos primeiro.")
    
    can_generate = schedule.status == ScheduleStatus.PUBLISHED and len(shifts) > 0
    
    schedule_data = {
        "id": schedule.id,
        "sector_id": schedule.sector_id,
        "week_start": schedule.week_start.isoformat(),
        "week_end": schedule.week_end.isoformat(),
        "status": schedule.status.value,
        "notes": schedule.notes,
        "expected_occupancy": schedule.expected_occupancy,
        "expected_rooms_to_clean": schedule.expected_rooms_to_clean,
        "created_at": schedule.created_at.isoformat() if schedule.created_at else None
    }
    
    shifts_data = []
    for shift in shifts:
        emp = db.query(Employee).filter(Employee.id == shift.employee_id).first()
        shifts_data.append({
            "id": shift.id,
            "employee_id": shift.employee_id,
            "employee_name": emp.name if emp else None,
            "date": shift.date.isoformat(),
            "start_time": str(shift.start_time) if shift.start_time else None,
            "end_time": str(shift.end_time) if shift.end_time else None,
            "planned_hours": shift.planned_hours
        })
    
    return {
        "has_schedule": True,
        "schedule": schedule_data,
        "shifts": shifts_data,
        "can_generate_convocations": can_generate,
        "blocking_errors": blocking_errors,
        "shifts_count": len(shifts)
    }


@router.get("/{schedule_id}", response_model=WeeklyScheduleResponse)
def get_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(WeeklySchedule).filter(WeeklySchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.post("/generate-governance", response_model=dict)
def generate_governance_schedule(request: ScheduleGenerationRequest, db: Session = Depends(get_db)):
    
    sector = db.query(Sector).filter(Sector.id == request.sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    
    if sector.code.upper() != "GOV":
        raise HTTPException(status_code=400, detail="This endpoint is for Governance sector only")
    
    week_end = request.week_start + timedelta(days=6)
    
    existing = db.query(WeeklySchedule).filter(
        WeeklySchedule.sector_id == request.sector_id,
        WeeklySchedule.week_start == request.week_start
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Schedule for this week already exists")
    
    employees = db.query(Employee).filter(
        Employee.sector_id == request.sector_id,
        Employee.is_active == True
    ).all()
    
    if not employees:
        raise HTTPException(status_code=400, detail="No active employees found in Governance sector")
    
    validator = ScheduleValidator()
    employee_validations = []
    
    for emp in employees:
        emp_data = {
            "id": emp.id,
            "name": emp.name,
            "contract_type": emp.contract_type.value,
            "last_full_week_off": emp.last_full_week_off,
            "shifts_history": emp.shifts_history or [],
            "hours_history": emp.hours_history or []
        }
        
        sample_shifts = [
            {"date": str(request.week_start + timedelta(days=i)), "planned_hours": 8.0}
            for i in range(5)
        ]
        
        validation = validator.validate_schedule_for_employee(
            emp_data, 
            sample_shifts, 
            request.week_start
        )
        employee_validations.append(validation)
    
    schedule = WeeklySchedule(
        sector_id=request.sector_id,
        week_start=request.week_start,
        week_end=week_end,
        status=ScheduleStatus.DRAFT,
        notes=request.notes,
        expected_occupancy=request.expected_occupancy,
        expected_rooms_to_clean=request.expected_rooms_to_clean
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    
    return {
        "message": "Schedule generation initiated (stub - full implementation pending)",
        "schedule_id": schedule.id,
        "week_start": str(request.week_start),
        "week_end": str(week_end),
        "sector": sector.name,
        "employees_available": len(employees),
        "employee_validations": employee_validations,
        "next_steps": [
            "Full algorithm implementation will assign specific shifts",
            "Convocations will be generated with 72h+ advance notice",
            "Shift rotation and pattern variation will be enforced"
        ]
    }


@router.post("/gerar-escala-sugestiva", response_model=dict)
def gerar_escala_sugestiva(request: GenerarEscalaRequest, db: Session = Depends(get_db)):
    """
    Gera uma escala semanal sugestiva para o setor selecionado.
    
    Utiliza os parâmetros operacionais da semana (quartos, ocupação) e as regras
    configuradas no painel para calcular horas necessárias e distribuir colaboradores.
    
    Args:
        request: Contém a data de início da semana (segunda-feira) e sector_id opcional
    
    Returns:
        Escala sugestiva com alocações por dia, resumo e estatísticas
    """
    parametros = db.query(WeeklyParameters).filter(
        WeeklyParameters.semana_inicio == request.semana_inicio
    ).first()
    
    if not parametros:
        raise HTTPException(
            status_code=404,
            detail=f"Parâmetros operacionais não encontrados para a semana de {request.semana_inicio}. Cadastre os parâmetros primeiro."
        )
    
    generator = ScheduleGenerator(db, sector_id=request.sector_id)
    escala = generator.gerar_escala_sugestiva(parametros)
    
    return escala


@router.get("/calcular-necessidade/{semana_inicio}", response_model=dict)
def calcular_necessidade_semanal(
    semana_inicio: date, 
    sector_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Calcula a necessidade de horas de governança para cada dia da semana.
    
    Args:
        semana_inicio: Data de início da semana (segunda-feira)
        sector_id: ID do setor (opcional)
    
    Returns:
        Cálculo detalhado de horas necessárias por dia
    """
    parametros = db.query(WeeklyParameters).filter(
        WeeklyParameters.semana_inicio == semana_inicio
    ).first()
    
    if not parametros:
        raise HTTPException(
            status_code=404,
            detail=f"Parâmetros operacionais não encontrados para a semana de {semana_inicio}"
        )
    
    generator = ScheduleGenerator(db, sector_id=sector_id)
    regras = generator.obter_regras_ativas()
    necessidade = generator.calcular_necessidade_semanal(parametros, regras)
    
    total_horas = sum(d["horas_necessarias"] for d in necessidade.values())
    
    return {
        "semana_inicio": semana_inicio.isoformat(),
        "sector_id": sector_id,
        "necessidade_por_dia": necessidade,
        "total_horas_semana": round(total_horas, 2)
    }


@router.post("/", response_model=WeeklyScheduleResponse)
def create_schedule(schedule: WeeklyScheduleCreate, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == schedule.sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    
    db_schedule = WeeklySchedule(**schedule.model_dump())
    db.add(db_schedule)
    db.commit()
    db.refresh(db_schedule)
    return db_schedule


@router.delete("/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    db_schedule = db.query(WeeklySchedule).filter(WeeklySchedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    if db_schedule.status not in [ScheduleStatus.DRAFT, ScheduleStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Cannot delete published or completed schedules")
    
    db.delete(db_schedule)
    db.commit()
    return {"message": "Schedule deleted successfully"}
