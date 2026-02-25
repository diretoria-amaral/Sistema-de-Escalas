from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date, datetime
from app.models.report_upload import UploadStatus


class ReportTypeBase(BaseModel):
    name: str
    description: Optional[str] = None
    file_patterns: List[str] = []
    header_patterns: List[str] = []
    keyword_patterns: List[str] = []
    indicators: List[str] = []
    sectors: List[str] = []
    parser_config: dict = {}
    is_active: bool = True


class ReportTypeCreate(ReportTypeBase):
    pass


class ReportTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    file_patterns: Optional[List[str]] = None
    header_patterns: Optional[List[str]] = None
    keyword_patterns: Optional[List[str]] = None
    indicators: Optional[List[str]] = None
    sectors: Optional[List[str]] = None
    parser_config: Optional[dict] = None
    is_active: Optional[bool] = None


class ReportTypeResponse(ReportTypeBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReportUploadResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_type: str
    file_size: Optional[int] = None
    report_type_id: Optional[int] = None
    report_type_name: Optional[str] = None
    auto_detected: bool
    detection_confidence: int
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    status: UploadStatus
    processing_notes: Optional[str] = None
    error_message: Optional[str] = None
    indicators_found: List[str] = []
    sectors_affected: List[str] = []
    uploaded_by: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportUploadListResponse(BaseModel):
    id: int
    original_filename: str
    file_type: str
    report_type_name: Optional[str] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    status: UploadStatus
    sectors_affected: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


class OccupancyForecastBase(BaseModel):
    date: date
    rooms_available: Optional[int] = None
    rooms_occupied_forecast: Optional[int] = None
    occupancy_rate_forecast: Optional[float] = None
    arrivals_forecast: int = 0
    departures_forecast: int = 0
    stayovers_forecast: int = 0
    vip_guests: int = 0
    group_rooms: int = 0
    events_scheduled: List[str] = []
    special_notes: Optional[str] = None


class OccupancyForecastCreate(OccupancyForecastBase):
    planning_week_date: Optional[date] = None


class OccupancyForecastResponse(OccupancyForecastBase):
    id: int
    day_of_week: int
    planning_week_date: Optional[date] = None
    source_report_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OccupancyActualBase(BaseModel):
    date: date
    rooms_available: Optional[int] = None
    rooms_occupied: Optional[int] = None
    occupancy_rate: Optional[float] = None
    arrivals: int = 0
    departures: int = 0
    stayovers: int = 0
    no_shows: int = 0
    walk_ins: int = 0
    early_departures: int = 0
    vip_guests: int = 0
    rooms_cleaned: int = 0
    cleaning_hours_used: float = 0
    employees_worked: int = 0


class OccupancyActualCreate(OccupancyActualBase):
    pass


class OccupancyActualResponse(OccupancyActualBase):
    id: int
    day_of_week: int
    source_report_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DeviationHistoryResponse(BaseModel):
    id: int
    day_of_week: int
    day_name: str
    sample_count: int
    avg_occupancy_forecast: float
    avg_occupancy_actual: float
    avg_deviation: float
    std_deviation: float
    correction_factor: float
    avg_arrivals_forecast: float
    avg_arrivals_actual: float
    arrivals_deviation: float
    avg_departures_forecast: float
    avg_departures_actual: float
    departures_deviation: float
    avg_employees_needed: float
    avg_employees_used: float
    employees_deviation: float
    version: int
    last_updated: datetime

    class Config:
        from_attributes = True


class ScheduleAdjustmentRecommendation(BaseModel):
    date: date
    day_name: str
    forecasted_occupancy: float
    corrected_occupancy: float
    correction_factor: float
    current_employees: int
    recommended_employees: int
    adjustment_reason: str
    confidence_level: str
    priority: str


class DailyComparisonResponse(BaseModel):
    date: date
    day_name: str
    forecast_occupancy: Optional[float] = None
    actual_occupancy: Optional[float] = None
    deviation: Optional[float] = None
    forecast_arrivals: int = 0
    actual_arrivals: int = 0
    forecast_departures: int = 0
    actual_departures: int = 0
    employees_scheduled: int = 0
    employees_worked: int = 0
