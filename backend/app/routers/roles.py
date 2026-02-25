from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.models.role import Role, EmploymentType
from app.models.sector import Sector
from app.schemas.role import RoleCreate, RoleUpdate, RoleResponse, EmploymentTypeEnum

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("/employment-types")
def list_employment_types():
    """Retorna os tipos de vínculo disponíveis."""
    return [
        {"value": "intermitente", "label": "Intermitente"},
        {"value": "efetivo", "label": "Efetivo/Fixo"}
    ]


@router.get("/", response_model=List[RoleResponse])
def list_roles(
    sector_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """Lista todas as funções cadastradas com seus setores."""
    query = db.query(Role).options(joinedload(Role.sector))
    
    if sector_id:
        query = query.filter(Role.sector_id == sector_id)
    if is_active is not None:
        query = query.filter(Role.is_active == is_active)
    
    roles = query.order_by(Role.name).offset(skip).limit(limit).all()
    return roles


@router.get("/{role_id}", response_model=RoleResponse)
def get_role(role_id: int, db: Session = Depends(get_db)):
    """Obtém uma função específica pelo ID."""
    role = db.query(Role).options(joinedload(Role.sector)).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Função não encontrada")
    return role


@router.post("/", response_model=RoleResponse)
def create_role(role: RoleCreate, db: Session = Depends(get_db)):
    """Cria uma nova função."""
    # Validar setor
    sector = db.query(Sector).filter(Sector.id == role.sector_id).first()
    if not sector:
        raise HTTPException(status_code=400, detail="Setor não encontrado. Selecione um setor válido.")
    
    # Verificar duplicidade de nome no mesmo setor
    existing = db.query(Role).filter(
        Role.name == role.name,
        Role.sector_id == role.sector_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=400, 
            detail=f"Já existe uma função '{role.name}' cadastrada no setor '{sector.name}'"
        )
    
    try:
        db_role = Role(**role.model_dump())
        db.add(db_role)
        db.commit()
        db.refresh(db_role)
        
        # Reload with sector info
        db_role = db.query(Role).options(joinedload(Role.sector)).filter(Role.id == db_role.id).first()
        return db_role
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao salvar função: {str(e)}")


@router.put("/{role_id}", response_model=RoleResponse)
def update_role(role_id: int, role: RoleUpdate, db: Session = Depends(get_db)):
    """Atualiza uma função existente."""
    db_role = db.query(Role).options(joinedload(Role.sector)).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Função não encontrada")
    
    # Validar setor se fornecido
    if role.sector_id:
        sector = db.query(Sector).filter(Sector.id == role.sector_id).first()
        if not sector:
            raise HTTPException(status_code=400, detail="Setor não encontrado. Selecione um setor válido.")
    
    # Verificar duplicidade se nome ou setor mudarem
    if role.name or role.sector_id:
        new_name = role.name if role.name else db_role.name
        new_sector_id = role.sector_id if role.sector_id else db_role.sector_id
        
        existing = db.query(Role).filter(
            Role.name == new_name,
            Role.sector_id == new_sector_id,
            Role.id != role_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=400, 
                detail=f"Já existe outra função com este nome neste setor"
            )
    
    try:
        update_data = role.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_role, key, value)
        
        db.commit()
        db.refresh(db_role)
        return db_role
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar função: {str(e)}")


@router.delete("/{role_id}")
def delete_role(role_id: int, db: Session = Depends(get_db)):
    """Remove uma função (verificando dependências)."""
    db_role = db.query(Role).filter(Role.id == role_id).first()
    if not db_role:
        raise HTTPException(status_code=404, detail="Função não encontrada")
    
    # Verificar se há funcionários vinculados
    from app.models.employee import Employee
    employee_count = db.query(Employee).filter(Employee.role_id == role_id).count()
    if employee_count > 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Não é possível excluir: existem {employee_count} funcionário(s) vinculado(s) a esta função. Desative a função ou remova os vínculos primeiro."
        )
    
    try:
        db.delete(db_role)
        db.commit()
        return {"message": "Função excluída com sucesso", "success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao excluir função: {str(e)}")
