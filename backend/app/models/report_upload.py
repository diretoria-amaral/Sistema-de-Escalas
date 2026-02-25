from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Date, JSON, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class UploadStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class ReportUpload(Base):
    __tablename__ = "report_uploads"

    id = Column(Integer, primary_key=True, index=True)
    
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)
    
    report_type_id = Column(Integer, ForeignKey("report_types.id"), nullable=True)
    auto_detected = Column(Boolean, default=False)
    detection_confidence = Column(Integer, default=0)
    
    generated_at = Column(DateTime(timezone=True), nullable=True)
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    
    status = Column(SQLEnum(UploadStatus), default=UploadStatus.PENDING)
    parser_version = Column(String(20), nullable=True)
    processing_notes = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    
    rows_inserted = Column(Integer, default=0)
    rows_skipped = Column(Integer, default=0)
    
    extracted_data = Column(JSON, default=dict)
    indicators_found = Column(JSON, default=list)
    sectors_affected = Column(JSON, default=list)
    
    uploaded_by = Column(String(100), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    report_type = relationship("ReportType", back_populates="uploads")
    occupancy_forecasts = relationship("OccupancyForecast", back_populates="source_report")
    occupancy_actuals = relationship("OccupancyActual", back_populates="source_report")
    extract_logs = relationship("ReportExtractLog", back_populates="report_upload")
    occupancy_snapshots = relationship("OccupancySnapshot", back_populates="source_upload")
    frontdesk_events = relationship("FrontdeskEvent", back_populates="source_upload")
