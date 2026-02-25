from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.models.room import RoomStatus, RoomType


class RoomBase(BaseModel):
    room_number: str
    floor: Optional[int] = None
    room_type: RoomType = RoomType.DOUBLE
    status: RoomStatus = RoomStatus.VACANT_CLEAN
    description: Optional[str] = None
    is_active: bool = True


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    room_number: Optional[str] = None
    floor: Optional[int] = None
    room_type: Optional[RoomType] = None
    status: Optional[RoomStatus] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class RoomResponse(RoomBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
