from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Time, ForeignKey, JSON, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class ExtractStep(str, enum.Enum):
    DETECT = "DETECT"
    EXTRACT = "EXTRACT"
    NORMALIZE = "NORMALIZE"
    PERSIST = "PERSIST"
    DERIVE = "DERIVE"


class LogSeverity(str, enum.Enum):
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"


class EventType(str, enum.Enum):
    CHECKIN = "CHECKIN"
    CHECKOUT = "CHECKOUT"


class ReportExtractLog(Base):
    __tablename__ = "report_extract_logs"

    id = Column(Integer, primary_key=True, index=True)
    report_upload_id = Column(Integer, ForeignKey("report_uploads.id"), nullable=False, index=True)
    step = Column(SQLEnum(ExtractStep), nullable=False)
    severity = Column(SQLEnum(LogSeverity), default=LogSeverity.INFO)
    message = Column(Text, nullable=True)
    payload_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    report_upload = relationship("ReportUpload", back_populates="extract_logs")


class OccupancySnapshot(Base):
    __tablename__ = "occupancy_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    target_date = Column(Date, nullable=False, index=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    occupancy_pct = Column(Float, nullable=True)
    occupancy_total = Column(Integer, nullable=True)
    is_real = Column(Boolean, default=False)
    is_forecast = Column(Boolean, default=True)
    source_upload_id = Column(Integer, ForeignKey("report_uploads.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source_upload = relationship("ReportUpload", back_populates="occupancy_snapshots")


class OccupancyLatest(Base):
    """
    Tabela que mantém a melhor versão mais recente de ocupação por target_date.
    
    Regras:
    - REAL tem precedência sobre FORECAST (quando ambos existem, occupancy_pct = REAL)
    - Dentro do mesmo tipo, maior generated_at vence
    """
    __tablename__ = "occupancy_latest"

    target_date = Column(Date, primary_key=True)
    occupancy_pct = Column(Float, nullable=True)
    is_real = Column(Boolean, default=False)
    source_upload_id = Column(Integer, ForeignKey("report_uploads.id"), nullable=True)
    latest_real_generated_at = Column(DateTime(timezone=True), nullable=True)
    latest_real_occupancy_pct = Column(Float, nullable=True)
    latest_forecast_generated_at = Column(DateTime(timezone=True), nullable=True)
    latest_forecast_occupancy_pct = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FrontdeskEvent(Base):
    __tablename__ = "frontdesk_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    anchor_date = Column(Date, nullable=False, index=True)
    event_time = Column(Time, nullable=True)
    uh = Column(String(10), nullable=True)
    room_type = Column(String(50), nullable=True)
    other_date = Column(Date, nullable=True)
    time_a = Column(Time, nullable=True)
    time_b = Column(Time, nullable=True)
    source_upload_id = Column(Integer, ForeignKey("report_uploads.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    source_upload = relationship("ReportUpload", back_populates="frontdesk_events")


class FrontdeskEventsHourlyAgg(Base):
    __tablename__ = "frontdesk_events_hourly_agg"

    id = Column(Integer, primary_key=True, index=True)
    op_date = Column(Date, nullable=False, index=True)
    weekday_pt = Column(String(20), nullable=False)
    hour_timeline = Column(Integer, nullable=False)
    event_type = Column(SQLEnum(EventType), nullable=False, index=True)
    count_events = Column(Integer, default=0)
    source_window = Column(String(50), default="auto_agg")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class WeekdayBiasStats(Base):
    __tablename__ = "weekday_bias_stats"

    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(50), nullable=False, index=True)
    weekday_pt = Column(String(20), nullable=False, index=True)
    bias_pp = Column(Float, default=0.0)
    n = Column(Integer, default=0)
    std_pp = Column(Float, nullable=True)
    mae_pp = Column(Float, nullable=True)
    method = Column(String(30), default="MEAN_INCREMENTAL")
    method_params_json = Column(JSON, default=dict)
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class HourlyDistributionStats(Base):
    __tablename__ = "hourly_distribution_stats"

    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(30), nullable=False, index=True)
    weekday_pt = Column(String(20), nullable=False, index=True)
    hour_timeline = Column(Integer, nullable=False)
    pct = Column(Float, default=0.0)
    n = Column(Integer, default=0)
    method = Column(String(30), default="INCREMENTAL")
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
