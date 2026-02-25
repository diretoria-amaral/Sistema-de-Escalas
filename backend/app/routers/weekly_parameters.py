from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.database import get_db
from app.models.weekly_parameters import WeeklyParameters
from app.models.sector import Sector
from app.schemas.weekly_parameters import (
    WeeklyParametersCreate,
    WeeklyParametersUpdate,
    WeeklyParametersResponse
)

router = APIRouter(prefix="/weekly-parameters", tags=["Parâmetros Semanais"])


@router.get("/", response_model=List[WeeklyParametersResponse])
def listar_parametros_semanais(
    skip: int = 0,
    limit: int = 100,
    sector_id: Optional[int] = Query(None, description="Filtrar por setor"),
    db: Session = Depends(get_db)
):
    """Lista todos os parâmetros semanais cadastrados, opcionalmente filtrados por setor."""
    query = db.query(WeeklyParameters)
    if sector_id is not None:
        query = query.filter(WeeklyParameters.sector_id == sector_id)
    parametros = query.order_by(
        WeeklyParameters.semana_inicio.desc()
    ).offset(skip).limit(limit).all()
    return parametros


@router.get("/semana/{semana_inicio}", response_model=WeeklyParametersResponse)
def obter_parametros_por_semana(
    semana_inicio: date,
    sector_id: Optional[int] = Query(None, description="Filtrar por setor"),
    db: Session = Depends(get_db)
):
    """Obtém parâmetros de uma semana específica pela data de início e setor."""
    query = db.query(WeeklyParameters).filter(
        WeeklyParameters.semana_inicio == semana_inicio
    )
    if sector_id is not None:
        query = query.filter(WeeklyParameters.sector_id == sector_id)
    parametros = query.first()
    if not parametros:
        raise HTTPException(status_code=404, detail="Parâmetros não encontrados para esta semana/setor")
    return parametros


@router.get("/sectors/{sector_id}/week/{semana_inicio}", response_model=WeeklyParametersResponse)
def obter_parametros_por_setor_e_semana(
    sector_id: int,
    semana_inicio: date,
    db: Session = Depends(get_db)
):
    """
    PROMPT 8: Obtém parâmetros de um setor específico para uma semana.
    Endpoint RESTful: GET /api/sectors/{sector_id}/weekly-parameters?week_start=YYYY-MM-DD
    """
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    
    parametros = db.query(WeeklyParameters).filter(
        WeeklyParameters.sector_id == sector_id,
        WeeklyParameters.semana_inicio == semana_inicio
    ).first()
    if not parametros:
        raise HTTPException(status_code=404, detail="Parâmetros não encontrados para este setor/semana")
    return parametros


@router.get("/{id}", response_model=WeeklyParametersResponse)
def obter_parametros(id: int, db: Session = Depends(get_db)):
    """Obtém parâmetros semanais por ID."""
    parametros = db.query(WeeklyParameters).filter(WeeklyParameters.id == id).first()
    if not parametros:
        raise HTTPException(status_code=404, detail="Parâmetros não encontrados")
    return parametros


@router.post("/", response_model=WeeklyParametersResponse)
def criar_parametros_semanais(
    parametros: WeeklyParametersCreate,
    db: Session = Depends(get_db)
):
    """Cria parâmetros operacionais para uma nova semana/setor."""
    query = db.query(WeeklyParameters).filter(
        WeeklyParameters.semana_inicio == parametros.semana_inicio
    )
    if parametros.sector_id is not None:
        query = query.filter(WeeklyParameters.sector_id == parametros.sector_id)
    else:
        query = query.filter(WeeklyParameters.sector_id.is_(None))
    
    existente = query.first()
    if existente:
        raise HTTPException(
            status_code=400,
            detail="Já existem parâmetros cadastrados para esta semana/setor"
        )
    
    db_parametros = WeeklyParameters(**parametros.model_dump())
    db.add(db_parametros)
    db.commit()
    db.refresh(db_parametros)
    return db_parametros


@router.put("/sectors/{sector_id}/week/{semana_inicio}", response_model=WeeklyParametersResponse)
def atualizar_ou_criar_parametros_por_setor(
    sector_id: int,
    semana_inicio: date,
    parametros: WeeklyParametersUpdate,
    db: Session = Depends(get_db)
):
    """
    PROMPT 8: Atualiza ou cria parâmetros de um setor para uma semana.
    Endpoint RESTful: PUT /api/sectors/{sector_id}/weekly-parameters?week_start=YYYY-MM-DD
    """
    sector = db.query(Sector).filter(Sector.id == sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Setor não encontrado")
    
    db_parametros = db.query(WeeklyParameters).filter(
        WeeklyParameters.sector_id == sector_id,
        WeeklyParameters.semana_inicio == semana_inicio
    ).first()
    
    if not db_parametros:
        db_parametros = WeeklyParameters(
            sector_id=sector_id,
            semana_inicio=semana_inicio
        )
        db.add(db_parametros)
    
    update_data = parametros.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_parametros, key, value)
    
    db.commit()
    db.refresh(db_parametros)
    return db_parametros


@router.put("/{id}", response_model=WeeklyParametersResponse)
def atualizar_parametros_semanais(
    id: int,
    parametros: WeeklyParametersUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza parâmetros semanais existentes."""
    db_parametros = db.query(WeeklyParameters).filter(WeeklyParameters.id == id).first()
    if not db_parametros:
        raise HTTPException(status_code=404, detail="Parâmetros não encontrados")
    
    update_data = parametros.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_parametros, key, value)
    
    db.commit()
    db.refresh(db_parametros)
    return db_parametros


@router.delete("/{id}")
def excluir_parametros_semanais(id: int, db: Session = Depends(get_db)):
    """Exclui parâmetros semanais."""
    db_parametros = db.query(WeeklyParameters).filter(WeeklyParameters.id == id).first()
    if not db_parametros:
        raise HTTPException(status_code=404, detail="Parâmetros não encontrados")
    
    db.delete(db_parametros)
    db.commit()
    return {"message": "Parâmetros excluídos com sucesso"}
