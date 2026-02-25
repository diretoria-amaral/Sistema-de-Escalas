from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import Optional, List
from datetime import date, datetime, timedelta
import io
import json

from app.database import get_db
from app.models.system_settings import SystemSettings, RuleVersion, ParserVersion, WorkRegimeMode
from app.models.employee import Employee
from app.models.convocation import Convocation, ConvocationStatus
from app.models.sector import Sector
from app.models.governance_activity import GovernanceActivity
from app.models.rules import LaborRules, SectorOperationalRules
from app.models.governance_module import ForecastRun
from app.models.weekly_schedule import WeeklySchedule
from app.models.report_upload import ReportUpload
from app.models.audit_log import AuditLog, AuditAction
from app.models.operational_calendar import OperationalCalendar

router = APIRouter(prefix="/compliance", tags=["Compliance & Governance"])


@router.get("/system-settings")
def get_system_settings(db: Session = Depends(get_db)):
    settings = db.query(SystemSettings).filter(SystemSettings.is_active == True).first()
    
    if not settings:
        settings = SystemSettings(
            work_regime_mode=WorkRegimeMode.INTERMITENTE.value,
            intermittent_mode_active=True,
            is_active=True
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)
    
    return {
        "id": settings.id,
        "work_regime_mode": settings.work_regime_mode,
        "intermittent_mode_active": settings.intermittent_mode_active,
        "min_advance_notice_hours": settings.min_advance_notice_hours,
        "block_fixed_schedules": settings.block_fixed_schedules,
        "block_continuous_patterns": settings.block_continuous_patterns,
        "require_formal_convocations": settings.require_formal_convocations,
        "allow_schedule_generation": settings.allow_schedule_generation,
        "allow_convocation_generation": settings.allow_convocation_generation,
        "production_ready": settings.production_ready,
        "system_version": settings.system_version,
        "last_readiness_check": settings.last_readiness_check,
        "readiness_issues": settings.readiness_issues
    }


@router.put("/system-settings")
def update_system_settings(
    intermittent_mode_active: Optional[bool] = None,
    min_advance_notice_hours: Optional[int] = None,
    block_fixed_schedules: Optional[bool] = None,
    require_formal_convocations: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    settings = db.query(SystemSettings).filter(SystemSettings.is_active == True).first()
    
    if not settings:
        settings = SystemSettings(is_active=True)
        db.add(settings)
    
    if intermittent_mode_active is not None:
        settings.intermittent_mode_active = intermittent_mode_active
        settings.work_regime_mode = WorkRegimeMode.INTERMITENTE.value if intermittent_mode_active else WorkRegimeMode.CLT_PADRAO.value
    if min_advance_notice_hours is not None:
        settings.min_advance_notice_hours = min_advance_notice_hours
    if block_fixed_schedules is not None:
        settings.block_fixed_schedules = block_fixed_schedules
    if require_formal_convocations is not None:
        settings.require_formal_convocations = require_formal_convocations
    
    db.commit()
    db.refresh(settings)
    
    audit = AuditLog(
        action=AuditAction.SETTINGS_CHANGE,
        entity_type="system_settings",
        entity_id=settings.id,
        description="Configuracoes do sistema atualizadas"
    )
    db.add(audit)
    db.commit()
    
    return {"message": "Configuracoes atualizadas", "settings": get_system_settings(db)}


@router.get("/intermittent-mode-status")
def get_intermittent_mode_status(db: Session = Depends(get_db)):
    settings = db.query(SystemSettings).filter(SystemSettings.is_active == True).first()
    
    is_active = settings.intermittent_mode_active if settings else True
    
    return {
        "intermittent_mode_active": is_active,
        "work_regime_mode": settings.work_regime_mode if settings else WorkRegimeMode.INTERMITENTE.value,
        "restrictions": {
            "block_fixed_schedules": settings.block_fixed_schedules if settings else True,
            "block_continuous_patterns": settings.block_continuous_patterns if settings else True,
            "require_formal_convocations": settings.require_formal_convocations if settings else True,
            "min_advance_notice_hours": settings.min_advance_notice_hours if settings else 72
        },
        "alert_message": "Sistema operando em modo de trabalho intermitente - convocacoes devem respeitar a legislacao vigente." if is_active else None
    }


@router.get("/employee-dossier/{employee_id}")
def get_employee_legal_dossier(
    employee_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador nao encontrado")
    
    query = db.query(Convocation).filter(Convocation.employee_id == employee_id)
    if date_from:
        query = query.filter(Convocation.date >= date_from)
    if date_to:
        query = query.filter(Convocation.date <= date_to)
    
    convocations = query.order_by(Convocation.date.desc(), Convocation.created_at.desc()).all()
    
    sector = db.query(Sector).filter(Sector.id == employee.sector_id).first() if employee.sector_id else None
    
    convocation_records = []
    total_hours_worked = 0
    legal_violations = 0
    
    for conv in convocations:
        advance_hours = None
        if conv.sent_at and conv.start_time and conv.date:
            shift_start = datetime.combine(conv.date, conv.start_time)
            advance_hours = (shift_start - conv.sent_at).total_seconds() / 3600
        
        met_72h = advance_hours >= 72 if advance_hours else None
        
        if conv.status == ConvocationStatus.ACCEPTED:
            total_hours_worked += conv.total_hours or 0
        
        if not conv.legal_validation_passed:
            legal_violations += 1
        
        labor_rules = db.query(LaborRules).filter(LaborRules.is_active == True).first()
        
        convocation_records.append({
            "id": conv.id,
            "date": conv.date.isoformat() if conv.date else None,
            "start_time": conv.start_time.isoformat() if conv.start_time else None,
            "end_time": conv.end_time.isoformat() if conv.end_time else None,
            "total_hours": conv.total_hours,
            "status": conv.status.value if conv.status else None,
            "sent_at": conv.sent_at.isoformat() if conv.sent_at else None,
            "response_deadline": conv.response_deadline.isoformat() if conv.response_deadline else None,
            "responded_at": conv.responded_at.isoformat() if conv.responded_at else None,
            "advance_notice_hours": round(advance_hours, 1) if advance_hours else None,
            "met_72h_requirement": met_72h,
            "legal_validation_passed": conv.legal_validation_passed,
            "legal_validation_errors": conv.legal_validation_errors,
            "legal_validation_warnings": conv.legal_validation_warnings,
            "decline_reason": conv.decline_reason,
            "generated_from": conv.generated_from.value if conv.generated_from else None,
            "rules_applied": {
                "min_notice_hours": labor_rules.min_notice_hours if labor_rules else 72,
                "max_week_hours": labor_rules.max_week_hours if labor_rules else 44.0,
                "max_daily_hours": labor_rules.max_daily_hours if labor_rules else 8.0
            }
        })
    
    accepted_count = sum(1 for c in convocations if c.status == ConvocationStatus.ACCEPTED)
    declined_count = sum(1 for c in convocations if c.status == ConvocationStatus.DECLINED)
    expired_count = sum(1 for c in convocations if c.status == ConvocationStatus.EXPIRED)
    
    audit_logs = db.query(AuditLog).filter(
        AuditLog.entity_type == "convocation",
        AuditLog.entity_id.in_([c.id for c in convocations])
    ).order_by(AuditLog.created_at.desc()).all()
    
    audit_timeline = []
    for log in audit_logs:
        audit_timeline.append({
            "timestamp": log.created_at.isoformat() if log.created_at else None,
            "action": log.action.value if log.action else None,
            "description": log.description,
            "entity_id": log.entity_id
        })
    
    return {
        "dossier_generated_at": datetime.now().isoformat(),
        "employee": {
            "id": employee.id,
            "name": employee.name,
            "cpf": employee.cpf,
            "email": employee.email,
            "phone": employee.phone,
            "contract_type": employee.contract_type.value if employee.contract_type else None,
            "sector_name": sector.name if sector else None,
            "role_name": employee.role.name if employee.role else None,
            "hire_date": employee.hire_date.isoformat() if employee.hire_date else None,
            "is_active": employee.is_active
        },
        "period": {
            "date_from": date_from.isoformat() if date_from else "inicio",
            "date_to": date_to.isoformat() if date_to else "atual"
        },
        "summary": {
            "total_convocations": len(convocations),
            "accepted": accepted_count,
            "declined": declined_count,
            "expired": expired_count,
            "acceptance_rate": round(accepted_count / len(convocations) * 100, 1) if convocations else 0,
            "total_hours_worked": round(total_hours_worked, 1),
            "legal_violations": legal_violations,
            "compliance_rate": round((len(convocations) - legal_violations) / len(convocations) * 100, 1) if convocations else 100
        },
        "convocations": convocation_records,
        "audit_trail": audit_timeline,
        "legal_notes": {
            "work_regime": "INTERMITENTE",
            "applicable_legislation": "CLT Art. 452-A - Contrato de Trabalho Intermitente",
            "min_advance_notice": "72 horas",
            "response_deadline": "24 horas apos recebimento"
        }
    }


@router.get("/system-status")
def get_system_status(db: Session = Depends(get_db)):
    from datetime import timezone
    now = datetime.now(timezone.utc)
    today = date.today()
    
    last_hp_upload = db.query(ReportUpload).filter(
        ReportUpload.report_type_id != None
    ).order_by(ReportUpload.created_at.desc()).first()
    
    last_checkin_upload = db.query(ReportUpload).filter(
        ReportUpload.report_type_id != None
    ).order_by(ReportUpload.created_at.desc()).first()
    
    last_checkout_upload = db.query(ReportUpload).filter(
        ReportUpload.report_type_id != None
    ).order_by(ReportUpload.created_at.desc()).first()
    
    last_forecast = db.query(ForecastRun).order_by(ForecastRun.created_at.desc()).first()
    
    last_schedule = db.query(WeeklySchedule).order_by(WeeklySchedule.created_at.desc()).first()
    
    last_convocation = db.query(Convocation).order_by(Convocation.created_at.desc()).first()
    
    alerts = []
    
    sectors = db.query(Sector).filter(Sector.is_active == True).all()
    for sector in sectors:
        op_rules = db.query(SectorOperationalRules).filter(
            SectorOperationalRules.sector_id == sector.id,
            SectorOperationalRules.is_active == True
        ).first()
        if not op_rules:
            alerts.append({
                "type": "warning",
                "category": "configuration",
                "message": f"Setor '{sector.name}' sem regras operacionais configuradas"
            })
        
        activities = db.query(GovernanceActivity).filter(
            GovernanceActivity.sector_id == sector.id,
            GovernanceActivity.is_active == True
        ).count()
        if activities == 0:
            alerts.append({
                "type": "warning",
                "category": "configuration",
                "message": f"Setor '{sector.name}' sem atividades cadastradas"
            })
    
    labor_rules = db.query(LaborRules).filter(LaborRules.is_active == True).first()
    if not labor_rules:
        alerts.append({
            "type": "error",
            "category": "rules",
            "message": "Regras trabalhistas globais nao configuradas"
        })
    
    if not last_hp_upload or (now - last_hp_upload.created_at).days > 7:
        alerts.append({
            "type": "warning",
            "category": "data",
            "message": "Dados HP desatualizados (mais de 7 dias)"
        })
    
    week_start = today - timedelta(days=today.weekday())
    next_week_start = week_start + timedelta(days=7)
    
    calendar_events = db.query(OperationalCalendar).filter(
        OperationalCalendar.date >= today,
        OperationalCalendar.date <= today + timedelta(days=30)
    ).count()
    
    try:
        pending_convocations = db.query(Convocation).filter(
            Convocation.status == ConvocationStatus.PENDING
        ).count()
    except Exception:
        pending_convocations = 0
    
    system_healthy = len([a for a in alerts if a["type"] == "error"]) == 0
    
    return {
        "timestamp": now.isoformat(),
        "system_healthy": system_healthy,
        "ready_to_generate_schedules": system_healthy and last_hp_upload is not None,
        "data_status": {
            "last_hp_upload": {
                "date": last_hp_upload.created_at.isoformat() if last_hp_upload else None,
                "days_ago": (now - last_hp_upload.created_at).days if last_hp_upload else None
            },
            "last_checkin_upload": {
                "date": last_checkin_upload.created_at.isoformat() if last_checkin_upload else None,
                "days_ago": (now - last_checkin_upload.created_at).days if last_checkin_upload else None
            },
            "last_checkout_upload": {
                "date": last_checkout_upload.created_at.isoformat() if last_checkout_upload else None,
                "days_ago": (now - last_checkout_upload.created_at).days if last_checkout_upload else None
            }
        },
        "operations_status": {
            "last_forecast_run": {
                "id": last_forecast.id if last_forecast else None,
                "date": last_forecast.created_at.isoformat() if last_forecast else None,
                "type": last_forecast.run_type.value if last_forecast and last_forecast.run_type else None
            },
            "last_schedule_generated": {
                "id": last_schedule.id if last_schedule else None,
                "date": last_schedule.created_at.isoformat() if last_schedule else None,
                "week_start": last_schedule.week_start.isoformat() if last_schedule else None
            },
            "last_convocation": {
                "id": last_convocation.id if last_convocation else None,
                "date": last_convocation.created_at.isoformat() if last_convocation else None
            },
            "pending_convocations": pending_convocations
        },
        "configuration_status": {
            "sectors_configured": len(sectors),
            "calendar_events_next_30_days": calendar_events,
            "labor_rules_active": labor_rules is not None
        },
        "alerts": alerts,
        "alerts_summary": {
            "errors": len([a for a in alerts if a["type"] == "error"]),
            "warnings": len([a for a in alerts if a["type"] == "warning"]),
            "info": len([a for a in alerts if a["type"] == "info"])
        }
    }


@router.get("/readiness-checklist")
def get_readiness_checklist(db: Session = Depends(get_db)):
    checks = []
    all_passed = True
    
    sectors = db.query(Sector).filter(Sector.is_active == True).count()
    checks.append({
        "id": "sectors",
        "name": "Setores cadastrados",
        "passed": sectors > 0,
        "value": sectors,
        "required": "Pelo menos 1 setor"
    })
    if sectors == 0:
        all_passed = False
    
    employees = db.query(Employee).filter(Employee.is_active == True).count()
    checks.append({
        "id": "employees",
        "name": "Colaboradores ativos",
        "passed": employees > 0,
        "value": employees,
        "required": "Pelo menos 1 colaborador"
    })
    if employees == 0:
        all_passed = False
    
    activities = db.query(GovernanceActivity).filter(GovernanceActivity.is_active == True).count()
    checks.append({
        "id": "activities",
        "name": "Atividades cadastradas",
        "passed": activities > 0,
        "value": activities,
        "required": "Pelo menos 1 atividade"
    })
    if activities == 0:
        all_passed = False
    
    labor_rules = db.query(LaborRules).filter(LaborRules.is_active == True).first()
    checks.append({
        "id": "labor_rules",
        "name": "Regras trabalhistas configuradas",
        "passed": labor_rules is not None,
        "value": "Configurado" if labor_rules else "Nao configurado",
        "required": "Obrigatorio"
    })
    if not labor_rules:
        all_passed = False
    
    hp_data = db.query(ReportUpload).filter(ReportUpload.report_type_id != None).count()
    checks.append({
        "id": "hp_data",
        "name": "Dados HP carregados",
        "passed": hp_data > 0,
        "value": hp_data,
        "required": "Pelo menos 1 upload"
    })
    if hp_data == 0:
        all_passed = False
    
    settings = db.query(SystemSettings).filter(SystemSettings.is_active == True).first()
    intermittent_active = settings.intermittent_mode_active if settings else True
    checks.append({
        "id": "intermittent_mode",
        "name": "Modo intermitente ativo",
        "passed": intermittent_active,
        "value": "Ativo" if intermittent_active else "Inativo",
        "required": "Obrigatorio para compliance"
    })
    if not intermittent_active:
        all_passed = False
    
    calendar_events = db.query(OperationalCalendar).filter(
        OperationalCalendar.date >= date.today()
    ).count()
    checks.append({
        "id": "calendar",
        "name": "Calendario configurado",
        "passed": True,
        "value": f"{calendar_events} eventos futuros",
        "required": "Recomendado"
    })
    
    op_rules_count = db.query(SectorOperationalRules).filter(SectorOperationalRules.is_active == True).count()
    sectors_with_rules = op_rules_count >= sectors if sectors > 0 else False
    checks.append({
        "id": "operational_rules",
        "name": "Regras operacionais por setor",
        "passed": sectors_with_rules,
        "value": f"{op_rules_count} de {sectors} setores",
        "required": "Todos os setores"
    })
    
    if settings:
        settings.production_ready = all_passed
        settings.last_readiness_check = datetime.now()
        settings.readiness_issues = [c for c in checks if not c["passed"]]
        db.commit()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "all_passed": all_passed,
        "production_ready": all_passed,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": len([c for c in checks if c["passed"]]),
            "failed": len([c for c in checks if not c["passed"]])
        },
        "blocking_actions": [] if all_passed else [
            "Geracao de escalas bloqueada ate resolver pendencias",
            "Emissao de convocacoes bloqueada ate resolver pendencias"
        ]
    }


@router.get("/rule-versions")
def get_rule_versions(
    rule_type: Optional[str] = Query(None),
    sector_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(RuleVersion)
    
    if rule_type:
        query = query.filter(RuleVersion.rule_type == rule_type)
    if sector_id:
        query = query.filter(RuleVersion.sector_id == sector_id)
    
    versions = query.order_by(RuleVersion.created_at.desc()).all()
    
    return {
        "total": len(versions),
        "versions": [
            {
                "id": v.id,
                "rule_type": v.rule_type,
                "sector_id": v.sector_id,
                "version_number": v.version_number,
                "effective_from": v.effective_from.isoformat() if v.effective_from else None,
                "effective_until": v.effective_until.isoformat() if v.effective_until else None,
                "change_reason": v.change_reason,
                "created_at": v.created_at.isoformat() if v.created_at else None
            }
            for v in versions
        ]
    }


@router.get("/parser-versions")
def get_parser_versions(db: Session = Depends(get_db)):
    versions = db.query(ParserVersion).filter(ParserVersion.is_active == True).all()
    
    default_parsers = [
        {"parser_name": "HP_Parser", "version": "1.0.0", "method_version": "EWMA_v1"},
        {"parser_name": "Checkin_Parser", "version": "1.0.0", "method_version": "hourly_distribution_v1"},
        {"parser_name": "Checkout_Parser", "version": "1.0.0", "method_version": "hourly_distribution_v1"},
        {"parser_name": "PDF_Extractor", "version": "1.0.0", "method_version": "pdfplumber_v1"},
        {"parser_name": "Excel_Processor", "version": "1.0.0", "method_version": "openpyxl_v1"}
    ]
    
    if not versions:
        return {
            "parsers": default_parsers,
            "last_updated": None
        }
    
    return {
        "parsers": [
            {
                "id": v.id,
                "parser_name": v.parser_name,
                "version": v.version,
                "method_version": v.method_version,
                "description": v.description,
                "is_active": v.is_active,
                "created_at": v.created_at.isoformat() if v.created_at else None
            }
            for v in versions
        ],
        "last_updated": max([v.created_at for v in versions]).isoformat() if versions else None
    }


@router.get("/how-system-decides")
def get_system_documentation(db: Session = Depends(get_db)):
    labor_rules = db.query(LaborRules).filter(LaborRules.is_active == True).first()
    settings = db.query(SystemSettings).filter(SystemSettings.is_active == True).first()
    
    return {
        "title": "Como o Sistema Decide",
        "version": "1.3.0",
        "generated_at": datetime.now().isoformat(),
        "work_regime": {
            "mode": settings.work_regime_mode if settings else "INTERMITENTE",
            "description": "Sistema configurado para regime de trabalho intermitente conforme CLT Art. 452-A"
        },
        "decision_flow": [
            {
                "step": 1,
                "name": "Ingestao de Dados",
                "description": "Upload de relatorios HP (ocupacao), Checkin e Checkout via Data Lake",
                "details": [
                    "Processamento automatico de PDF, Excel e CSV",
                    "Extracao de indicadores por tipo de relatorio",
                    "Classificacao REAL vs FORECAST baseada em as_of_date"
                ]
            },
            {
                "step": 2,
                "name": "Definicao REAL vs FORECAST",
                "description": "Dados com target_date <= as_of_date sao REAL, demais sao FORECAST",
                "details": [
                    "REAL: dados confirmados do passado",
                    "FORECAST: projecoes para datas futuras"
                ]
            },
            {
                "step": 3,
                "name": "Baseline e Ajustes",
                "description": "Forecast Run BASELINE define projecao base, ajustes posteriores sao ADJUSTMENT",
                "details": [
                    "BASELINE: projecao inicial congelada",
                    "DAILY_UPDATE: atualizacoes diarias",
                    "ADJUSTMENT: correcoes manuais"
                ]
            },
            {
                "step": 4,
                "name": "Calculo de Demanda",
                "description": "Demanda de headcount calculada por setor usando turnover rate e produtividade",
                "details": [
                    "Turnover rate por tipo de quarto (checkout vs estada)",
                    "Produtividade configurada por setor",
                    "Fatores de calendario (feriados, eventos especiais)"
                ]
            },
            {
                "step": 5,
                "name": "Geracao de Escalas",
                "description": "Escala sugestiva gerada respeitando regras trabalhistas e operacionais",
                "details": [
                    "Limite semanal: " + (f"{labor_rules.max_week_hours}h" if labor_rules else "44h"),
                    "Limite diario: " + (f"{labor_rules.max_daily_hours}h" if labor_rules else "8h"),
                    "Descanso entre turnos: " + (f"{labor_rules.min_rest_hours_between_shifts}h" if labor_rules else "11h")
                ]
            },
            {
                "step": 6,
                "name": "Emissao de Convocacoes",
                "description": "Convocacoes formais enviadas aos colaboradores intermitentes",
                "details": [
                    "Antecedencia minima: " + (f"{labor_rules.min_notice_hours}h" if labor_rules else "72h"),
                    "Prazo de resposta: 24h",
                    "Validacao legal automatica em cada convocacao"
                ]
            },
            {
                "step": 7,
                "name": "Gerenciamento de Respostas",
                "description": "Aceites, recusas e substituicoes automaticas",
                "details": [
                    "Aceite: confirma o turno",
                    "Recusa: dispara busca de substituto",
                    "Expiracao: convocacao sem resposta apos prazo"
                ]
            }
        ],
        "current_parameters": {
            "labor_rules": {
                "min_notice_hours": labor_rules.min_notice_hours if labor_rules else 72,
                "max_week_hours": labor_rules.max_week_hours if labor_rules else 44.0,
                "max_daily_hours": labor_rules.max_daily_hours if labor_rules else 8.0,
                "min_rest_between_shifts": labor_rules.min_rest_hours_between_shifts if labor_rules else 11.0,
                "max_consecutive_days": labor_rules.max_consecutive_work_days if labor_rules else 6
            },
            "intermittent_guardrails": {
                "require_formal_convocations": settings.require_formal_convocations if settings else True,
                "block_fixed_schedules": settings.block_fixed_schedules if settings else True,
                "min_advance_notice": settings.min_advance_notice_hours if settings else 72
            }
        },
        "audit_trail": "Todas as decisoes sao registradas no log de auditoria para rastreabilidade"
    }
