from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.models.employee import Employee, ContractType
from app.models.sector import Sector
from app.models.role import Role
from app.schemas.employee import EmployeeCreate, EmployeeUpdate, EmployeeResponse, EmployeeListResponse

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("/", response_model=List[EmployeeListResponse])
def list_employees(
    sector_id: Optional[int] = None,
    role_id: Optional[int] = None,
    contract_type: Optional[ContractType] = None,
    is_active: Optional[bool] = True,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    query = db.query(Employee).options(
        joinedload(Employee.sector),
        joinedload(Employee.role)
    )
    
    if sector_id:
        query = query.filter(Employee.sector_id == sector_id)
    if role_id:
        query = query.filter(Employee.role_id == role_id)
    if contract_type:
        query = query.filter(Employee.contract_type == contract_type)
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)
    
    employees = query.offset(skip).limit(limit).all()
    
    result = []
    for emp in employees:
        result.append(EmployeeListResponse(
            id=emp.id,
            name=emp.name,
            sector_id=emp.sector_id,
            sector_name=emp.sector.name if emp.sector else None,
            role_id=emp.role_id,
            role_name=emp.role.name if emp.role else None,
            contract_type=emp.contract_type,
            is_active=emp.is_active
        ))
    return result


@router.get("/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.post("/", response_model=EmployeeResponse)
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db)):
    sector = db.query(Sector).filter(Sector.id == employee.sector_id).first()
    if not sector:
        raise HTTPException(status_code=404, detail="Sector not found")
    
    role = db.query(Role).filter(Role.id == employee.role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.sector_id != employee.sector_id:
        raise HTTPException(status_code=400, detail="Role does not belong to the specified sector")
    
    employee_data = employee.model_dump()
    
    if employee_data.get('cpf') == '':
        employee_data['cpf'] = None
    if employee_data.get('email') == '':
        employee_data['email'] = None
    if employee_data.get('phone') == '':
        employee_data['phone'] = None
    if employee_data.get('cbo_code') == '':
        employee_data['cbo_code'] = None
    
    if employee_data.get('cpf'):
        existing = db.query(Employee).filter(Employee.cpf == employee_data['cpf']).first()
        if existing:
            raise HTTPException(status_code=400, detail="Employee with this CPF already exists")
    
    db_employee = Employee(**employee_data)
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee


@router.put("/{employee_id}", response_model=EmployeeResponse)
def update_employee(employee_id: int, employee: EmployeeUpdate, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if employee.sector_id:
        sector = db.query(Sector).filter(Sector.id == employee.sector_id).first()
        if not sector:
            raise HTTPException(status_code=404, detail="Sector not found")
    
    if employee.role_id:
        role = db.query(Role).filter(Role.id == employee.role_id).first()
        if not role:
            raise HTTPException(status_code=404, detail="Role not found")
    
    update_data = employee.model_dump(exclude_unset=True)
    
    for field in ['cpf', 'email', 'phone', 'cbo_code']:
        if field in update_data and update_data[field] == '':
            update_data[field] = None
    
    for key, value in update_data.items():
        setattr(db_employee, key, value)
    
    db.commit()
    db.refresh(db_employee)
    return db_employee


@router.delete("/{employee_id}")
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    db_employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    db.delete(db_employee)
    db.commit()
    return {"message": "Employee deleted successfully"}
