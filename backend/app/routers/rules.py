from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import LaborRules, SectorOperationalRules, Sector, AuditLog, AuditAction
from app.schemas.rules import (
    LaborRulesUpdate, LaborRulesResponse,
    SectorOperationalRulesUpdate, SectorOperationalRulesResponse
)

router = APIRouter(prefix="/api/rules", tags=["Rules"])


def create_audit_log(db: Session, action: str, entity_type: str, entity_id: int, details: str = None):
    """Cria registro de auditoria para mudanças de regras."""
    log = AuditLog(
        action=AuditAction.RULE_SAVED,
        entity_type=entity_type,
        entity_id=entity_id,
        description=details
    )
    db.add(log)


@router.get("/labor", response_model=LaborRulesResponse)
def get_labor_rules(db: Session = Depends(get_db)):
    """
    Obtém as regras trabalhistas globais.
    Cria registro default se não existir.
    """
    rules = db.query(LaborRules).filter(LaborRules.is_active == True).first()
    
    if not rules:
        rules = LaborRules()
        db.add(rules)
        db.commit()
        db.refresh(rules)
    
    return rules


@router.put("/labor", response_model=LaborRulesResponse)
def update_labor_rules(data: LaborRulesUpdate, db: Session = Depends(get_db)):
    """Atualiza as regras trabalhistas globais."""
    rules = db.query(LaborRules).filter(LaborRules.is_active == True).first()
    
    if not rules:
        rules = LaborRules()
        db.add(rules)
        db.flush()
    
    rules.min_notice_hours = data.min_notice_hours
    rules.max_week_hours = data.max_week_hours
    rules.max_week_hours_with_overtime = data.max_week_hours_with_overtime
    rules.max_daily_hours = data.max_daily_hours
    rules.min_rest_hours_between_shifts = data.min_rest_hours_between_shifts
    rules.min_break_hours = data.min_break_hours
    rules.max_break_hours = data.max_break_hours
    rules.no_break_threshold_hours = data.no_break_threshold_hours
    rules.sundays_off_per_month = data.sundays_off_per_month
    rules.vacation_days_annual = data.vacation_days_annual
    rules.allow_vacation_split = data.allow_vacation_split
    rules.max_consecutive_work_days = data.max_consecutive_work_days
    rules.respect_cbo_activities = data.respect_cbo_activities
    rules.overtime_policy_json = data.overtime_policy_json
    rules.intermittent_guardrails_json = data.intermittent_guardrails_json
    
    create_audit_log(
        db, 
        action="UPDATE_LABOR_RULES",
        entity_type="labor_rules",
        entity_id=rules.id,
        details=f"Regras trabalhistas atualizadas"
    )
    
    db.commit()
    db.refresh(rules)
    
    return rules


@router.get("/operational", response_model=SectorOperationalRulesResponse)
def get_operational_rules(
    sector_id: int = Query(..., description="ID do setor"),
    db: Session = Depends(get_db)
):
    """
    Obtém as regras operacionais de um setor específico.
    Cria registro default se não existir (lazy-create).
    """
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail=f"Setor {sector_id} não encontrado")
    
    rules = db.query(SectorOperationalRules).filter(
        SectorOperationalRules.sector_id == sector_id,
        SectorOperationalRules.is_active == True
    ).first()
    
    if not rules:
        rules = SectorOperationalRules(
            sector_id=sector_id,
            shift_templates_json={
                "morning": {"start": "07:00", "end": "15:00"},
                "afternoon": {"start": "14:00", "end": "22:00"}
            },
            productivity_params_json={
                "tempo_checkout": 25.0,
                "tempo_estada": 10.0,
                "jornada_media_horas": 8.0
            },
            indicators_json={
                "fator_feriado": 1.1,
                "fator_vespera_feriado": 1.05,
                "fator_pico": 1.2,
                "fator_baixa_ocupacao": 0.9
            }
        )
        db.add(rules)
        db.commit()
        db.refresh(rules)
    
    return rules


@router.put("/operational", response_model=SectorOperationalRulesResponse)
def update_operational_rules(
    sector_id: int = Query(..., description="ID do setor"),
    data: SectorOperationalRulesUpdate = None,
    db: Session = Depends(get_db)
):
    """Atualiza as regras operacionais de um setor específico."""
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail=f"Setor {sector_id} não encontrado")
    
    rules = db.query(SectorOperationalRules).filter(
        SectorOperationalRules.sector_id == sector_id
    ).first()
    
    if not rules:
        rules = SectorOperationalRules(sector_id=sector_id)
        db.add(rules)
        db.flush()
    
    if data:
        rules.utilization_target_pct = data.utilization_target_pct
        rules.buffer_pct = data.buffer_pct
        if data.shift_templates_json is not None:
            rules.shift_templates_json = data.shift_templates_json
        if data.productivity_params_json is not None:
            rules.productivity_params_json = data.productivity_params_json
        if data.indicators_json is not None:
            rules.indicators_json = data.indicators_json
        rules.alternancia_horarios = data.alternancia_horarios
        rules.alternancia_atividades = data.alternancia_atividades
        rules.regime_preferencial = data.regime_preferencial
        rules.permitir_alternar_regime = data.permitir_alternar_regime
        rules.dias_folga_semana = data.dias_folga_semana
        rules.folgas_consecutivas = data.folgas_consecutivas
        rules.percentual_max_repeticao_turno = data.percentual_max_repeticao_turno
        rules.percentual_max_repeticao_dia_turno = data.percentual_max_repeticao_dia_turno
        rules.modo_conservador = data.modo_conservador
        rules.intervalo_semanas_folga = data.intervalo_semanas_folga
    
    create_audit_log(
        db,
        action="UPDATE_OPERATIONAL_RULES",
        entity_type="sector_operational_rules",
        entity_id=rules.id,
        details=f"Regras operacionais do setor {sector.name} atualizadas"
    )
    
    db.commit()
    db.refresh(rules)
    
    return rules


@router.get("/operational/all", response_model=List[SectorOperationalRulesResponse])
def get_all_operational_rules(db: Session = Depends(get_db)):
    """Obtém todas as regras operacionais de todos os setores."""
    rules = db.query(SectorOperationalRules).filter(
        SectorOperationalRules.is_active == True
    ).all()
    return rules
