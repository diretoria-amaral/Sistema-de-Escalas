from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ReportType(Base):
    __tablename__ = "report_types"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), nullable=True, unique=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    
    detector_rules_json = Column(JSON, default=dict)
    mapping_json = Column(JSON, default=dict)
    
    file_patterns = Column(JSON, default=list)
    header_patterns = Column(JSON, default=list)
    keyword_patterns = Column(JSON, default=list)
    
    indicators = Column(JSON, default=list)
    sectors = Column(JSON, default=list)
    parser_config = Column(JSON, default=dict)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    uploads = relationship("ReportUpload", back_populates="report_type")
