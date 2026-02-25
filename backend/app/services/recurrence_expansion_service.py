"""
Serviço de Expansão de Recorrência para Atividades Recorrentes.

Este serviço calcula quais atividades RECORRENTES devem ser executadas
em uma determinada semana, baseado em sua periodicidade e data de
última execução.
"""
from datetime import date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.governance_activity import GovernanceActivity, ActivityClassification
from app.models.activity_periodicity import ActivityPeriodicity
from app.models.activity_program import ActivityProgramWeek, ActivityProgramItem


def get_week_dates(year: int, week: int) -> tuple[date, date]:
    """
    Retorna a data de início (segunda) e fim (domingo) de uma semana ISO.
    """
    jan4 = date(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    week_start = start_of_week1 + timedelta(weeks=week - 1)
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def find_last_execution_date(
    db: Session,
    activity_id: int,
    before_date: date
) -> Optional[date]:
    """
    Encontra a última data em que a atividade foi programada.
    Busca nos itens de programação anteriores à data especificada.
    """
    last_item = db.query(ActivityProgramItem).join(
        ActivityProgramWeek,
        ActivityProgramItem.program_week_id == ActivityProgramWeek.id
    ).filter(
        ActivityProgramItem.activity_id == activity_id,
        ActivityProgramWeek.week_start_date < before_date
    ).order_by(ActivityProgramWeek.week_start_date.desc()).first()
    
    if last_item:
        program_week = db.query(ActivityProgramWeek).filter(
            ActivityProgramWeek.id == last_item.program_week_id
        ).first()
        if program_week:
            return program_week.week_start_date + timedelta(days=last_item.weekday)
    
    return None


def should_execute_this_week(
    periodicity: ActivityPeriodicity,
    week_start: date,
    last_execution: Optional[date],
    anchor_weekday: int = 0
) -> List[int]:
    """
    Determina em quais dias da semana (0=Seg, 6=Dom) a atividade deve ser executada.
    
    Lógica baseada no tipo de periodicidade:
    - DAILY: Todos os dias
    - WEEKLY: Uma vez por semana no dia âncora
    - FORTNIGHTLY: A cada duas semanas no dia âncora
    - MONTHLY: Uma vez por mês (aproximado na semana)
    - CUSTOM: Baseado em intervalo_dias
    
    Retorna lista de dias da semana quando a atividade deve ser agendada.
    """
    days_to_schedule = []
    tipo = periodicity.tipo
    intervalo = periodicity.intervalo_dias
    
    if last_execution is None:
        if tipo.value == 'DAILY':
            return list(range(7))
        else:
            return [anchor_weekday]
    
    if tipo.value == 'DAILY':
        return list(range(7))
    
    if tipo.value == 'WEEKLY':
        original_weekday = last_execution.weekday()
        return [original_weekday]
    
    if tipo.value == 'FORTNIGHTLY':
        days_since = (week_start - last_execution).days
        if days_since >= 14:
            original_weekday = last_execution.weekday()
            return [original_weekday]
        return []
    
    if tipo.value == 'MONTHLY':
        days_since = (week_start - last_execution).days
        if days_since >= 28:
            original_weekday = last_execution.weekday()
            return [original_weekday]
        return []
    
    for day_offset in range(7):
        current_date = week_start + timedelta(days=day_offset)
        days_since_last = (current_date - last_execution).days
        
        if days_since_last >= intervalo:
            if days_since_last % intervalo == 0:
                days_to_schedule.append(day_offset)
            elif not days_to_schedule and day_offset == 6:
                first_valid = days_since_last // intervalo * intervalo
                if days_since_last >= first_valid:
                    days_to_schedule.append(day_offset)
    
    if not days_to_schedule and last_execution:
        days_since = (week_start - last_execution).days
        if days_since >= intervalo:
            days_to_schedule.append(0)
    
    return days_to_schedule


def expand_recurring_activities(
    db: Session,
    sector_id: int,
    year: int,
    week: int
) -> List[Dict[str, Any]]:
    """
    Expande todas as atividades recorrentes de um setor para uma semana específica.
    
    Retorna uma lista de dicionários com as atividades expandidas:
    [
        {
            "activity_id": int,
            "activity_name": str,
            "activity_code": str,
            "weekday": int,  # 0-6 (Seg-Dom)
            "date": date,
            "periodicity_name": str,
            "average_time_minutes": float
        },
        ...
    ]
    """
    week_start, week_end = get_week_dates(year, week)
    
    recurring_activities = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == sector_id,
        GovernanceActivity.classificacao_atividade == ActivityClassification.RECORRENTE,
        GovernanceActivity.is_active == True,
        GovernanceActivity.periodicidade_id.isnot(None)
    ).all()
    
    expanded_items = []
    
    for activity in recurring_activities:
        periodicity = db.query(ActivityPeriodicity).filter(
            ActivityPeriodicity.id == activity.periodicidade_id,
            ActivityPeriodicity.is_active == True
        ).first()
        
        if not periodicity:
            continue
        
        last_execution = find_last_execution_date(db, activity.id, week_start)
        
        days_to_execute = should_execute_this_week(periodicity, week_start, last_execution)
        
        for weekday in days_to_execute:
            execution_date = week_start + timedelta(days=weekday)
            expanded_items.append({
                "activity_id": activity.id,
                "activity_name": activity.name,
                "activity_code": activity.code,
                "weekday": weekday,
                "date": execution_date,
                "periodicity_name": periodicity.name,
                "periodicity_interval_days": periodicity.intervalo_dias,
                "average_time_minutes": activity.average_time_minutes,
                "last_execution": last_execution
            })
    
    return expanded_items


def get_recurring_activities_summary(
    db: Session,
    sector_id: int
) -> Dict[str, Any]:
    """
    Retorna resumo das atividades recorrentes de um setor.
    """
    recurring = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == sector_id,
        GovernanceActivity.classificacao_atividade == ActivityClassification.RECORRENTE,
        GovernanceActivity.is_active == True
    ).all()
    
    activities_summary = []
    for act in recurring:
        periodicity = None
        if act.periodicidade_id:
            periodicity = db.query(ActivityPeriodicity).filter(
                ActivityPeriodicity.id == act.periodicidade_id
            ).first()
        
        activities_summary.append({
            "id": act.id,
            "name": act.name,
            "code": act.code,
            "average_time_minutes": act.average_time_minutes,
            "periodicity": {
                "id": periodicity.id if periodicity else None,
                "name": periodicity.name if periodicity else None,
                "interval_days": periodicity.intervalo_dias if periodicity else None
            } if periodicity else None
        })
    
    return {
        "sector_id": sector_id,
        "total_recurring_activities": len(recurring),
        "activities": activities_summary
    }
