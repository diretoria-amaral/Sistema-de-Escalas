from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum


class EmploymentTypeEnum(str, Enum):
    INTERMITTENT = "intermitente"
    PERMANENT = "efetivo"


class RoleBase(BaseModel):
    name: str
    cbo_code: Optional[str] = None
    sector_id: int
    employment_type: EmploymentTypeEnum = EmploymentTypeEnum.PERMANENT
    description: Optional[str] = None
    is_active: bool = True
    
    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError('Nome da função é obrigatório')
        return v.strip()


class RoleCreate(RoleBase):
    pass


class RoleUpdate(BaseModel):
    name: Optional[str] = None
    cbo_code: Optional[str] = None
    sector_id: Optional[int] = None
    employment_type: Optional[EmploymentTypeEnum] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    
    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not v.strip():
            raise ValueError('Nome da função não pode estar vazio')
        return v.strip() if v else v


class SectorInfo(BaseModel):
    id: int
    name: str
    
    class Config:
        from_attributes = True


class RoleResponse(RoleBase):
    id: int
    sector: Optional[SectorInfo] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
