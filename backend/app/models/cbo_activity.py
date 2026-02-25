from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class CboActivityMapping(Base):
    """
    Mapeamento de atividades compatíveis por CBO.
    Define quais atividades cada código CBO pode executar.
    """
    __tablename__ = "cbo_activity_mappings"

    id = Column(Integer, primary_key=True, index=True)
    cbo_code = Column(String(20), nullable=False, index=True)
    cbo_description = Column(String(200), nullable=True)
    activity_id = Column(Integer, ForeignKey("governance_activities.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    activity = relationship("GovernanceActivity")
