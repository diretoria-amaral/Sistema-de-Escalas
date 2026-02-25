from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from app.database import Base
import enum


class AuditAction(str, enum.Enum):
    REPORT_UPLOAD = "REPORT_UPLOAD"
    REPORT_PROCESS = "REPORT_PROCESS"
    REPORT_REPROCESSED = "report_reprocessed"
    REPORT_FAILED = "report_failed"
    SCHEDULE_GENERATE = "SCHEDULE_GENERATE"
    SCHEDULE_ADJUST = "SCHEDULE_ADJUST"
    DEVIATION_UPDATE = "DEVIATION_UPDATE"
    CORRECTION_APPLY = "CORRECTION_APPLY"
    SETTINGS_CHANGE = "SETTINGS_CHANGE"
    DATA_IMPORT = "DATA_IMPORT"
    DATA_EXPORT = "DATA_EXPORT"
    RULE_SAVED = "rule_saved"
    FORECAST_RUN_CREATED = "forecast_run_created"
    MANUAL_OVERRIDE = "manual_override"
    CALENDAR_EVENT_CREATED = "calendar_event_created"
    CALENDAR_EVENT_UPDATED = "calendar_event_updated"
    CALENDAR_EVENT_DELETED = "calendar_event_deleted"
    CALENDAR_APPLIED_TO_FORECAST = "calendar_applied_to_forecast"
    CALENDAR_APPLIED_TO_SCHEDULE = "calendar_applied_to_schedule"
    CONVOCATION_CREATED = "convocation_created"
    CONVOCATION_ACCEPTED = "convocation_accepted"
    CONVOCATION_DECLINED = "convocation_declined"
    CONVOCATION_EXPIRED = "convocation_expired"
    CONVOCATION_CANCELLED = "convocation_cancelled"
    RESCHEDULE_TRIGGERED = "reschedule_triggered"
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_UPDATED = "template_updated"
    TEMPLATE_DISABLED = "template_disabled"
    TEMPLATE_USED_IN_SCHEDULE = "template_used_in_schedule"
    SUGGESTION_CREATED = "suggestion_created"
    SUGGESTION_APPLIED = "suggestion_applied"
    SUGGESTION_IGNORED = "suggestion_ignored"
    ADJUSTMENT_CREATED_FROM_SUGGESTION = "adjustment_created_from_suggestion"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    action = Column(SQLEnum(AuditAction, values_callable=lambda e: [member.value for member in e]), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=True)
    
    user_id = Column(String(100), nullable=True)
    user_name = Column(String(200), nullable=True)
    
    description = Column(Text, nullable=True)
    
    old_values = Column(JSON, nullable=True)
    new_values = Column(JSON, nullable=True)
    
    extra_data = Column(JSON, default=dict)
    
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
