from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.sql import func
from app.database import Base
import enum


class RoomStatus(str, enum.Enum):
    VACANT_DIRTY = "vago_sujo"
    VACANT_CLEAN = "vago_limpo"
    OCCUPIED = "ocupado"
    BLOCKED = "bloqueado"
    MAINTENANCE = "manutencao"


class RoomType(str, enum.Enum):
    SINGLE = "single"
    DOUBLE = "double"
    TWIN = "twin"
    SUITE = "suite"
    FAMILY = "family"


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    room_number = Column(String(20), unique=True, nullable=False, index=True)
    floor = Column(Integer, nullable=True)
    room_type = Column(SQLEnum(RoomType), nullable=False, default=RoomType.DOUBLE)
    status = Column(SQLEnum(RoomStatus), nullable=False, default=RoomStatus.VACANT_CLEAN)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
