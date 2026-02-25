from sqlalchemy import Column, Integer, String, Time, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class ShiftTemplate(Base):
    """
    Template de turno reutilizável por setor.
    
    PROMPT 16: Ponte entre Programação de Atividades e Geração de Escalas.
    Templates definem "como" o trabalho será distribuído em jornadas padrão,
    mas NÃO alocam pessoas - isso é feito na geração de escalas.
    """
    __tablename__ = "shift_templates"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    
    name = Column(String(100), nullable=False)
    
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    break_minutes = Column(Integer, default=60)
    
    max_hours = Column(Integer, default=8)
    min_hours = Column(Integer, default=4)
    
    valid_weekdays = Column(JSON, default=[0, 1, 2, 3, 4, 5, 6])
    
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    sector = relationship("Sector", backref="shift_templates")
