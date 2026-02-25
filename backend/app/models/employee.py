from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Date, JSON, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ContractType(str, enum.Enum):
    INTERMITTENT = "intermitente"
    PERMANENT = "efetivo"


class WorkRegime(str, enum.Enum):
    FIVE_BY_TWO = "5x2"
    SIX_BY_ONE = "6x1"
    TWELVE_BY_THIRTYSIX = "12x36"
    FLEXIBLE = "flexivel"


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    cpf = Column(String(14), unique=True, nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    cbo_code = Column(String(20), nullable=True)
    
    contract_type = Column(SQLEnum(ContractType), nullable=False, default=ContractType.INTERMITTENT)
    work_regime = Column(SQLEnum(WorkRegime), nullable=True)
    monthly_hours_target = Column(Float, default=176.0)
    
    # Campos específicos de Governança
    velocidade_limpeza_vago_sujo = Column(Float, default=25.0)  # Minutos por quarto vago sujo
    velocidade_limpeza_estada = Column(Float, default=10.0)     # Minutos por quarto estada
    carga_horaria_max_semana = Column(Float, default=44.0)      # Máximo de horas semanais
    
    unavailable_days = Column(JSON, default=list)
    time_off_preferences = Column(JSON, default=list)
    restrictions = Column(JSON, default=list)
    
    last_full_week_off = Column(Date, nullable=True)
    vacation_period_start = Column(Date, nullable=True)
    vacation_period_end = Column(Date, nullable=True)
    
    hours_history = Column(JSON, default=list)
    shifts_history = Column(JSON, default=list)
    convocation_history = Column(JSON, default=list)
    
    hire_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector", back_populates="employees")
    role = relationship("Role", back_populates="employees")
    daily_shifts = relationship("DailyShift", back_populates="employee")
    convocations = relationship("Convocation", back_populates="employee")
