from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import GovernanceActivity, RoleActivity, Sector, Role
from app.schemas.rules import (
    ActivityCreate, ActivityUpdate, ActivityResponse,
    RoleActivityCreate, RoleActivityResponse
)

router = APIRouter(prefix="/api/activities", tags=["Activities"])


@router.get("/", response_model=List[ActivityResponse])
def list_activities(
    sector_id: Optional[int] = Query(None, description="Filtrar por setor"),
    include_inactive: bool = Query(False, description="Incluir inativos"),
    db: Session = Depends(get_db)
):
    """Lista atividades, opcionalmente filtradas por setor."""
    query = db.query(GovernanceActivity)
    
    if sector_id:
        query = query.filter(GovernanceActivity.sector_id == sector_id)
    
    if not include_inactive:
        query = query.filter(GovernanceActivity.is_active == True)
    
    activities = query.order_by(GovernanceActivity.name).all()
    
    result = []
    for a in activities:
        sector_name = None
        if a.sector_id:
            sector = db.query(Sector).filter(Sector.id == a.sector_id).first()
            if sector:
                sector_name = sector.name
        
        result.append(ActivityResponse(
            id=a.id,
            sector_id=a.sector_id,
            name=a.name,
            code=a.code,
            description=a.description,
            average_time_minutes=a.average_time_minutes,
            unit_type=a.unit_type,
            difficulty_level=a.difficulty_level,
            requires_training=a.requires_training,
            is_active=a.is_active,
            created_at=a.created_at,
            updated_at=a.updated_at,
            sector_name=sector_name
        ))
    
    return result


@router.get("/{activity_id}", response_model=ActivityResponse)
def get_activity(activity_id: int, db: Session = Depends(get_db)):
    """Obtém uma atividade por ID."""
    activity = db.query(GovernanceActivity).filter(
        GovernanceActivity.id == activity_id
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")
    
    sector_name = None
    if activity.sector_id:
        sector = db.query(Sector).filter(Sector.id == activity.sector_id).first()
        if sector:
            sector_name = sector.name
    
    return ActivityResponse(
        id=activity.id,
        sector_id=activity.sector_id,
        name=activity.name,
        code=activity.code,
        description=activity.description,
        average_time_minutes=activity.average_time_minutes,
        unit_type=activity.unit_type,
        difficulty_level=activity.difficulty_level,
        requires_training=activity.requires_training,
        is_active=activity.is_active,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
        sector_name=sector_name
    )


@router.post("/", response_model=ActivityResponse)
def create_activity(data: ActivityCreate, db: Session = Depends(get_db)):
    """Cria uma nova atividade. Requer sector_id."""
    sector = db.query(Sector).filter(Sector.id == data.sector_id).first()
    if not sector:
        raise HTTPException(
            status_code=400, 
            detail=f"Setor {data.sector_id} não encontrado"
        )
    
    existing = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == data.sector_id,
        GovernanceActivity.code == data.code
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Já existe atividade com código {data.code} neste setor"
        )
    
    activity = GovernanceActivity(
        sector_id=data.sector_id,
        name=data.name,
        code=data.code,
        description=data.description,
        average_time_minutes=data.average_time_minutes,
        unit_type=data.unit_type,
        difficulty_level=data.difficulty_level,
        requires_training=data.requires_training
    )
    
    db.add(activity)
    db.commit()
    db.refresh(activity)
    
    return ActivityResponse(
        id=activity.id,
        sector_id=activity.sector_id,
        name=activity.name,
        code=activity.code,
        description=activity.description,
        average_time_minutes=activity.average_time_minutes,
        unit_type=activity.unit_type,
        difficulty_level=activity.difficulty_level,
        requires_training=activity.requires_training,
        is_active=activity.is_active,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
        sector_name=sector.name
    )


@router.put("/{activity_id}", response_model=ActivityResponse)
def update_activity(activity_id: int, data: ActivityUpdate, db: Session = Depends(get_db)):
    """Atualiza uma atividade existente."""
    activity = db.query(GovernanceActivity).filter(
        GovernanceActivity.id == activity_id
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")
    
    if data.sector_id is not None:
        sector = db.query(Sector).filter(Sector.id == data.sector_id).first()
        if not sector:
            raise HTTPException(
                status_code=400,
                detail=f"Setor {data.sector_id} não encontrado"
            )
        activity.sector_id = data.sector_id
    
    if data.name is not None:
        activity.name = data.name
    if data.code is not None:
        activity.code = data.code
    if data.description is not None:
        activity.description = data.description
    if data.average_time_minutes is not None:
        activity.average_time_minutes = data.average_time_minutes
    if data.unit_type is not None:
        activity.unit_type = data.unit_type
    if data.difficulty_level is not None:
        activity.difficulty_level = data.difficulty_level
    if data.requires_training is not None:
        activity.requires_training = data.requires_training
    
    db.commit()
    db.refresh(activity)
    
    sector_name = None
    if activity.sector_id:
        sector = db.query(Sector).filter(Sector.id == activity.sector_id).first()
        if sector:
            sector_name = sector.name
    
    return ActivityResponse(
        id=activity.id,
        sector_id=activity.sector_id,
        name=activity.name,
        code=activity.code,
        description=activity.description,
        average_time_minutes=activity.average_time_minutes,
        unit_type=activity.unit_type,
        difficulty_level=activity.difficulty_level,
        requires_training=activity.requires_training,
        is_active=activity.is_active,
        created_at=activity.created_at,
        updated_at=activity.updated_at,
        sector_name=sector_name
    )


@router.delete("/{activity_id}")
def delete_activity(activity_id: int, hard: bool = False, db: Session = Depends(get_db)):
    """
    Desativa (soft delete) ou remove (hard delete) uma atividade.
    Por padrão faz soft delete (is_active=False).
    """
    activity = db.query(GovernanceActivity).filter(
        GovernanceActivity.id == activity_id
    ).first()
    
    if not activity:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")
    
    if hard:
        db.query(RoleActivity).filter(RoleActivity.activity_id == activity_id).delete()
        db.delete(activity)
        db.commit()
        return {"message": "Atividade removida permanentemente"}
    else:
        activity.is_active = False
        db.commit()
        return {"message": "Atividade desativada"}


@router.get("/role/{role_id}/activities", response_model=List[RoleActivityResponse])
def list_role_activities(role_id: int, db: Session = Depends(get_db)):
    """Lista atividades associadas a uma função."""
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Função não encontrada")
    
    role_activities = db.query(RoleActivity).filter(
        RoleActivity.role_id == role_id,
        RoleActivity.is_active == True
    ).all()
    
    result = []
    for ra in role_activities:
        activity = db.query(GovernanceActivity).filter(
            GovernanceActivity.id == ra.activity_id
        ).first()
        
        result.append(RoleActivityResponse(
            id=ra.id,
            role_id=ra.role_id,
            activity_id=ra.activity_id,
            is_active=ra.is_active,
            created_at=ra.created_at,
            activity_name=activity.name if activity else None,
            role_name=role.name
        ))
    
    return result


@router.post("/role/{role_id}/activities", response_model=RoleActivityResponse)
def add_role_activity(
    role_id: int, 
    data: RoleActivityCreate, 
    db: Session = Depends(get_db)
):
    """
    Associa uma atividade a uma função.
    Valida que o setor da função é igual ao setor da atividade.
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Função não encontrada")
    
    activity = db.query(GovernanceActivity).filter(
        GovernanceActivity.id == data.activity_id
    ).first()
    if not activity:
        raise HTTPException(status_code=404, detail="Atividade não encontrada")
    
    if activity.sector_id and activity.sector_id != role.sector_id:
        raise HTTPException(
            status_code=400,
            detail=f"Setor da atividade ({activity.sector_id}) diferente do setor da função ({role.sector_id})"
        )
    
    existing = db.query(RoleActivity).filter(
        RoleActivity.role_id == role_id,
        RoleActivity.activity_id == data.activity_id
    ).first()
    
    if existing:
        if not existing.is_active:
            existing.is_active = True
            db.commit()
            db.refresh(existing)
            return RoleActivityResponse(
                id=existing.id,
                role_id=existing.role_id,
                activity_id=existing.activity_id,
                is_active=existing.is_active,
                created_at=existing.created_at,
                activity_name=activity.name,
                role_name=role.name
            )
        raise HTTPException(
            status_code=400,
            detail="Esta atividade já está associada à função"
        )
    
    role_activity = RoleActivity(
        role_id=role_id,
        activity_id=data.activity_id
    )
    
    db.add(role_activity)
    db.commit()
    db.refresh(role_activity)
    
    return RoleActivityResponse(
        id=role_activity.id,
        role_id=role_activity.role_id,
        activity_id=role_activity.activity_id,
        is_active=role_activity.is_active,
        created_at=role_activity.created_at,
        activity_name=activity.name,
        role_name=role.name
    )


@router.delete("/role/{role_id}/activities/{activity_id}")
def remove_role_activity(role_id: int, activity_id: int, db: Session = Depends(get_db)):
    """Remove a associação entre função e atividade."""
    role_activity = db.query(RoleActivity).filter(
        RoleActivity.role_id == role_id,
        RoleActivity.activity_id == activity_id
    ).first()
    
    if not role_activity:
        raise HTTPException(
            status_code=404,
            detail="Associação não encontrada"
        )
    
    role_activity.is_active = False
    db.commit()
    
    return {"message": "Associação removida"}
