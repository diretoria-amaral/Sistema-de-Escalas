from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, Date, JSON, String, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class OccupancyForecast(Base):
    __tablename__ = "occupancy_forecasts"

    id = Column(Integer, primary_key=True, index=True)
    
    date = Column(Date, nullable=False, index=True)
    day_of_week = Column(Integer, nullable=False)
    
    rooms_available = Column(Integer, nullable=True)
    rooms_occupied_forecast = Column(Integer, nullable=True)
    occupancy_rate_forecast = Column(Float, nullable=True)
    
    arrivals_forecast = Column(Integer, default=0)
    departures_forecast = Column(Integer, default=0)
    stayovers_forecast = Column(Integer, default=0)
    
    vip_guests = Column(Integer, default=0)
    group_rooms = Column(Integer, default=0)
    
    events_scheduled = Column(JSON, default=list)
    special_notes = Column(String(500), nullable=True)
    
    planning_week_date = Column(Date, nullable=True)
    
    source_report_id = Column(Integer, ForeignKey("report_uploads.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    source_report = relationship("ReportUpload", back_populates="occupancy_forecasts")


class OccupancyActual(Base):
    __tablename__ = "occupancy_actuals"

    id = Column(Integer, primary_key=True, index=True)
    
    date = Column(Date, nullable=False, index=True, unique=True)
    day_of_week = Column(Integer, nullable=False)
    
    rooms_available = Column(Integer, nullable=True)
    rooms_occupied = Column(Integer, nullable=True)
    occupancy_rate = Column(Float, nullable=True)
    
    arrivals = Column(Integer, default=0)
    departures = Column(Integer, default=0)
    stayovers = Column(Integer, default=0)
    
    no_shows = Column(Integer, default=0)
    walk_ins = Column(Integer, default=0)
    early_departures = Column(Integer, default=0)
    
    vip_guests = Column(Integer, default=0)
    
    rooms_cleaned = Column(Integer, default=0)
    cleaning_hours_used = Column(Float, default=0)
    employees_worked = Column(Integer, default=0)
    
    source_report_id = Column(Integer, ForeignKey("report_uploads.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    source_report = relationship("ReportUpload", back_populates="occupancy_actuals")


class DeviationHistory(Base):
    __tablename__ = "deviation_history"

    id = Column(Integer, primary_key=True, index=True)
    
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=True, index=True)
    day_of_week = Column(Integer, nullable=False, index=True)
    
    sample_count = Column(Integer, default=0)
    
    avg_occupancy_forecast = Column(Float, default=0)
    avg_occupancy_actual = Column(Float, default=0)
    avg_deviation = Column(Float, default=0)
    std_deviation = Column(Float, default=0)
    
    correction_factor = Column(Float, default=1.0)
    
    avg_arrivals_forecast = Column(Float, default=0)
    avg_arrivals_actual = Column(Float, default=0)
    arrivals_deviation = Column(Float, default=0)
    
    avg_departures_forecast = Column(Float, default=0)
    avg_departures_actual = Column(Float, default=0)
    departures_deviation = Column(Float, default=0)
    
    avg_employees_needed = Column(Float, default=0)
    avg_employees_used = Column(Float, default=0)
    employees_deviation = Column(Float, default=0)
    
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    version = Column(Integer, default=1)
    history_snapshots = Column(JSON, default=list)
