from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SectorBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    is_active: bool = True


class SectorCreate(SectorBase):
    pass


class SectorUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SectorResponse(SectorBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
