from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class EmploymentType(str, enum.Enum):
    INTERMITTENT = "intermitente"
    PERMANENT = "efetivo"


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    cbo_code = Column(String(20), nullable=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False)
    employment_type = Column(
        SQLEnum(EmploymentType, values_callable=lambda x: [e.value for e in x]),
        nullable=False, 
        default=EmploymentType.PERMANENT
    )
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector", back_populates="roles")
    employees = relationship("Employee", back_populates="role")
    role_activities = relationship("RoleActivity", back_populates="role")
