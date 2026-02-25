from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.governance_rules import GovernanceRules
from app.schemas.governance_rules import (
    GovernanceRulesCreate,
    GovernanceRulesUpdate,
    GovernanceRulesResponse
)

router = APIRouter(prefix="/governance-rules", tags=["Regras de Governança"])


@router.get("/", response_model=GovernanceRulesResponse)
def obter_regras_ativas(db: Session = Depends(get_db)):
    """
    Obtém as regras de governança ativas.
    Cria regras padrão se não existirem.
    """
    regras = db.query(GovernanceRules).filter(GovernanceRules.is_active == True).first()
    if not regras:
        regras = GovernanceRules()
        db.add(regras)
        db.commit()
        db.refresh(regras)
    return regras


@router.get("/all", response_model=List[GovernanceRulesResponse])
def listar_todas_regras(db: Session = Depends(get_db)):
    """Lista todas as configurações de regras (histórico)."""
    return db.query(GovernanceRules).order_by(GovernanceRules.created_at.desc()).all()


@router.post("/", response_model=GovernanceRulesResponse)
def criar_regras(
    regras: GovernanceRulesCreate,
    db: Session = Depends(get_db)
):
    """
    Cria novas regras de governança.
    Desativa regras anteriores automaticamente.
    """
    db.query(GovernanceRules).filter(GovernanceRules.is_active == True).update(
        {"is_active": False}
    )
    
    db_regras = GovernanceRules(**regras.model_dump(), is_active=True)
    db.add(db_regras)
    db.commit()
    db.refresh(db_regras)
    return db_regras


@router.put("/", response_model=GovernanceRulesResponse)
def atualizar_regras_ativas(
    regras: GovernanceRulesUpdate,
    db: Session = Depends(get_db)
):
    """Atualiza as regras de governança ativas."""
    db_regras = db.query(GovernanceRules).filter(GovernanceRules.is_active == True).first()
    if not db_regras:
        db_regras = GovernanceRules()
        db.add(db_regras)
        db.commit()
        db.refresh(db_regras)
    
    update_data = regras.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_regras, key, value)
    
    db.commit()
    db.refresh(db_regras)
    return db_regras


@router.delete("/{id}")
def excluir_regras(id: int, db: Session = Depends(get_db)):
    """Exclui um conjunto de regras (exceto as ativas)."""
    db_regras = db.query(GovernanceRules).filter(GovernanceRules.id == id).first()
    if not db_regras:
        raise HTTPException(status_code=404, detail="Regras não encontradas")
    if db_regras.is_active:
        raise HTTPException(status_code=400, detail="Não é possível excluir regras ativas")
    
    db.delete(db_regras)
    db.commit()
    return {"message": "Regras excluídas com sucesso"}
