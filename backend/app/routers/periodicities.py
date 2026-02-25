from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from app.database import get_db
from app.models.activity_periodicity import ActivityPeriodicity, PeriodicityType, IntervalUnit, AnchorPolicy
from app.schemas.periodicity import (
    PeriodicityCreate,
    PeriodicityUpdate,
    PeriodicityResponse,
    IntervalUnit as SchemaIntervalUnit,
    AnchorPolicy as SchemaAnchorPolicy
)
from app.services.interval_service import calculate_approximate_days

router = APIRouter(prefix="/api/periodicities", tags=["Periodicities"])


@router.get("/", response_model=List[PeriodicityResponse])
def list_periodicities(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Lista todas as periodicidades cadastradas."""
    query = db.query(ActivityPeriodicity)
    if active_only:
        query = query.filter(ActivityPeriodicity.is_active == True)
    return query.order_by(ActivityPeriodicity.intervalo_dias).all()


@router.get("/{periodicity_id}", response_model=PeriodicityResponse)
def get_periodicity(periodicity_id: int, db: Session = Depends(get_db)):
    """Retorna uma periodicidade específica."""
    periodicity = db.query(ActivityPeriodicity).filter(
        ActivityPeriodicity.id == periodicity_id
    ).first()
    
    if not periodicity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Periodicidade não encontrada."
        )
    return periodicity


def infer_periodicity_type(unit: IntervalUnit, value: int) -> PeriodicityType:
    """Infere o tipo da periodicidade baseado na unidade e valor."""
    if unit == IntervalUnit.DAYS:
        if value == 1:
            return PeriodicityType.DAILY
        elif value == 7:
            return PeriodicityType.WEEKLY
        elif value == 14:
            return PeriodicityType.FORTNIGHTLY
        else:
            return PeriodicityType.CUSTOM
    elif unit == IntervalUnit.MONTHS:
        if value == 1:
            return PeriodicityType.MONTHLY
        elif value == 3:
            return PeriodicityType.QUARTERLY
        else:
            return PeriodicityType.CUSTOM
    elif unit == IntervalUnit.YEARS:
        if value == 1:
            return PeriodicityType.YEARLY
        else:
            return PeriodicityType.CUSTOM
    return PeriodicityType.CUSTOM


@router.post("/", response_model=PeriodicityResponse, status_code=status.HTTP_201_CREATED)
def create_periodicity(
    data: PeriodicityCreate,
    db: Session = Depends(get_db)
):
    """Cria uma nova periodicidade."""
    existing = db.query(ActivityPeriodicity).filter(
        func.lower(ActivityPeriodicity.name) == data.name.lower()
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Já existe uma periodicidade com o nome '{data.name}'."
        )
    
    interval_unit = IntervalUnit(data.interval_unit.value)
    anchor_policy = AnchorPolicy(data.anchor_policy.value)
    
    inferred_tipo = data.tipo
    if not inferred_tipo:
        inferred_tipo = infer_periodicity_type(interval_unit, data.interval_value)
    
    intervalo_dias = calculate_approximate_days(interval_unit, data.interval_value)
    
    periodicity = ActivityPeriodicity(
        name=data.name,
        tipo=inferred_tipo if isinstance(inferred_tipo, PeriodicityType) else PeriodicityType(inferred_tipo.value),
        interval_unit=interval_unit,
        interval_value=data.interval_value,
        anchor_policy=anchor_policy,
        intervalo_dias=intervalo_dias,
        description=data.description,
        is_active=data.is_active
    )
    
    db.add(periodicity)
    db.commit()
    db.refresh(periodicity)
    return periodicity


@router.put("/{periodicity_id}", response_model=PeriodicityResponse)
def update_periodicity(
    periodicity_id: int,
    data: PeriodicityUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza uma periodicidade existente."""
    periodicity = db.query(ActivityPeriodicity).filter(
        ActivityPeriodicity.id == periodicity_id
    ).first()
    
    if not periodicity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Periodicidade não encontrada."
        )
    
    if data.name and data.name.lower() != periodicity.name.lower():
        existing = db.query(ActivityPeriodicity).filter(
            func.lower(ActivityPeriodicity.name) == data.name.lower(),
            ActivityPeriodicity.id != periodicity_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Já existe outra periodicidade com o nome '{data.name}'."
            )
    
    update_data = data.model_dump(exclude_unset=True)
    
    if 'intervalo_dias' in update_data and 'interval_unit' not in update_data and 'interval_value' not in update_data:
        update_data['interval_unit'] = SchemaIntervalUnit.DAYS
        update_data['interval_value'] = update_data['intervalo_dias']
    
    if 'intervalo_dias' in update_data:
        del update_data['intervalo_dias']
    
    for field, value in update_data.items():
        if field == "tipo" and value is not None:
            setattr(periodicity, field, PeriodicityType(value.value))
        elif field == "interval_unit" and value is not None:
            if hasattr(value, 'value'):
                setattr(periodicity, field, IntervalUnit(value.value))
            else:
                setattr(periodicity, field, IntervalUnit(value))
        elif field == "anchor_policy" and value is not None:
            setattr(periodicity, field, AnchorPolicy(value.value))
        else:
            setattr(periodicity, field, value)
    
    new_unit = periodicity.interval_unit
    new_value = periodicity.interval_value
    periodicity.intervalo_dias = calculate_approximate_days(new_unit, new_value)
    
    if not data.tipo:
        periodicity.tipo = infer_periodicity_type(new_unit, new_value)
    
    db.commit()
    db.refresh(periodicity)
    return periodicity


@router.delete("/{periodicity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_periodicity(periodicity_id: int, db: Session = Depends(get_db)):
    """Remove uma periodicidade (soft delete definindo is_active=False)."""
    periodicity = db.query(ActivityPeriodicity).filter(
        ActivityPeriodicity.id == periodicity_id
    ).first()
    
    if not periodicity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Periodicidade não encontrada."
        )
    
    from app.models.governance_activity import GovernanceActivity
    activities_using = db.query(GovernanceActivity).filter(
        GovernanceActivity.periodicidade_id == periodicity_id,
        GovernanceActivity.is_active == True
    ).count()
    
    if activities_using > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível excluir: {activities_using} atividade(s) ativa(s) usam esta periodicidade."
        )
    
    periodicity.is_active = False
    db.commit()
    return None
