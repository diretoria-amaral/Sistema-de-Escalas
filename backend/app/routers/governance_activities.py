from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models.governance_activity import GovernanceActivity, ActivityClassification
from app.models.activity_periodicity import ActivityPeriodicity
from app.schemas.governance_activity import (
    GovernanceActivityCreate,
    GovernanceActivityUpdate,
    GovernanceActivityResponse,
    ActivityClassificationEnum
)

router = APIRouter(prefix="/governance-activities", tags=["Governance Activities"])


@router.get("/", response_model=List[GovernanceActivityResponse])
def list_activities(
    skip: int = 0, 
    limit: int = 100,
    sector_id: Optional[int] = None,
    classificacao: Optional[ActivityClassificationEnum] = None,
    db: Session = Depends(get_db)
):
    """Lista atividades com filtros opcionais por setor e classificacao."""
    query = db.query(GovernanceActivity)
    
    if sector_id:
        query = query.filter(GovernanceActivity.sector_id == sector_id)
    if classificacao:
        query = query.filter(GovernanceActivity.classificacao_atividade == classificacao.value)
    
    activities = query.offset(skip).limit(limit).all()
    return activities


@router.get("/{activity_id}", response_model=GovernanceActivityResponse)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    activity = db.query(GovernanceActivity).filter(GovernanceActivity.id == activity_id).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Atividade nao encontrada.")
    return activity


@router.post("/", response_model=GovernanceActivityResponse, status_code=status.HTTP_201_CREATED)
def create_activity(activity: GovernanceActivityCreate, db: Session = Depends(get_db)):
    existing = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == activity.sector_id,
        (GovernanceActivity.name == activity.name) | (GovernanceActivity.code == activity.code)
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Ja existe uma atividade com este nome ou codigo neste setor."
        )
    
    periodicidade_tipo = None
    if activity.periodicidade_id:
        periodicity = db.query(ActivityPeriodicity).filter(
            ActivityPeriodicity.id == activity.periodicidade_id,
            ActivityPeriodicity.is_active == True
        ).first()
        if not periodicity:
            raise HTTPException(
                status_code=400,
                detail="Periodicidade nao encontrada ou inativa."
            )
        periodicidade_tipo = periodicity.tipo
    
    if activity.classificacao_atividade == ActivityClassificationEnum.RECORRENTE:
        if periodicidade_tipo and periodicidade_tipo != 'DAILY' and not activity.tolerancia_dias:
            raise HTTPException(
                status_code=400,
                detail="Atividades RECORRENTES com periodicidade diferente de DIARIA devem ter tolerancia de dias."
            )
    
    db_activity = GovernanceActivity(**activity.model_dump())
    db.add(db_activity)
    db.commit()
    db.refresh(db_activity)
    return db_activity


@router.put("/{activity_id}", response_model=GovernanceActivityResponse)
def update_activity(activity_id: int, activity: GovernanceActivityUpdate, db: Session = Depends(get_db)):
    db_activity = db.query(GovernanceActivity).filter(GovernanceActivity.id == activity_id).first()
    if not db_activity:
        raise HTTPException(status_code=404, detail="Atividade nao encontrada.")
    
    current_classificacao = db_activity.classificacao_atividade.value if hasattr(db_activity.classificacao_atividade, 'value') else str(db_activity.classificacao_atividade)
    current_periodicidade = db_activity.periodicidade_id
    current_tolerancia = db_activity.tolerancia_dias
    current_data_exec = db_activity.data_primeira_execucao
    
    new_periodicidade = activity.periodicidade_id if 'periodicidade_id' in activity.model_fields_set else current_periodicidade
    periodicidade_tipo = None
    if new_periodicidade:
        periodicity = db.query(ActivityPeriodicity).filter(
            ActivityPeriodicity.id == new_periodicidade,
            ActivityPeriodicity.is_active == True
        ).first()
        if not periodicity:
            raise HTTPException(
                status_code=400,
                detail="Periodicidade nao encontrada ou inativa."
            )
        periodicidade_tipo = periodicity.tipo
    
    try:
        activity.validate_classification_fields(
            current_classificacao=current_classificacao,
            current_periodicidade_id=current_periodicidade,
            current_tolerancia_dias=current_tolerancia,
            current_data_primeira_execucao=current_data_exec,
            periodicidade_tipo=periodicidade_tipo
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    update_data = activity.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(db_activity, key, value)
    
    db.commit()
    db.refresh(db_activity)
    return db_activity


@router.delete("/{activity_id}")
def delete_activity(activity_id: int, db: Session = Depends(get_db)):
    db_activity = db.query(GovernanceActivity).filter(GovernanceActivity.id == activity_id).first()
    if not db_activity:
        raise HTTPException(status_code=404, detail="Atividade nao encontrada.")
    
    db.delete(db_activity)
    db.commit()
    return {"message": "Atividade excluida com sucesso."}
