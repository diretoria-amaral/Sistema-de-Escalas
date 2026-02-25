from sqlalchemy import Column, Integer, Float, Boolean, String, Text, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class LaborRules(Base):
    """
    PROMPT 5: Regras Trabalhistas GLOBAIS.
    Singleton - apenas um registro ativo por vez.
    Válido para todos os setores.
    """
    __tablename__ = "labor_rules"

    id = Column(Integer, primary_key=True, index=True)
    
    min_notice_hours = Column(Integer, default=72)
    max_week_hours = Column(Float, default=44.0)
    max_week_hours_with_overtime = Column(Float, default=48.0)
    max_daily_hours = Column(Float, default=8.0)
    min_rest_hours_between_shifts = Column(Float, default=11.0)
    
    min_break_hours = Column(Float, default=1.0)
    max_break_hours = Column(Float, default=2.0)
    no_break_threshold_hours = Column(Float, default=4.0)
    
    sundays_off_per_month = Column(Integer, default=1)
    
    vacation_days_annual = Column(Integer, default=30)
    allow_vacation_split = Column(Boolean, default=True)
    
    max_consecutive_work_days = Column(Integer, default=6)
    
    respect_cbo_activities = Column(Boolean, default=True)
    
    overtime_policy_json = Column(JSON, nullable=True)
    intermittent_guardrails_json = Column(JSON, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SectorOperationalRules(Base):
    """
    PROMPT 5: Regras Operacionais e Indicadores POR SETOR.
    Um registro por setor.
    """
    __tablename__ = "sector_operational_rules"

    id = Column(Integer, primary_key=True, index=True)
    sector_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, unique=True, index=True)
    
    utilization_target_pct = Column(Float, default=85.0)
    buffer_pct = Column(Float, default=10.0)
    
    shift_templates_json = Column(JSON, nullable=True, default=lambda: {
        "morning": {"start": "07:00", "end": "15:00"},
        "afternoon": {"start": "14:00", "end": "22:00"}
    })
    
    productivity_params_json = Column(JSON, nullable=True, default=lambda: {
        "tempo_checkout": 25.0,
        "tempo_estada": 10.0,
        "jornada_media_horas": 8.0
    })
    
    indicators_json = Column(JSON, nullable=True, default=lambda: {
        "fator_feriado": 1.1,
        "fator_vespera_feriado": 1.05,
        "fator_pico": 1.2,
        "fator_baixa_ocupacao": 0.9
    })
    
    alternancia_horarios = Column(Boolean, default=True)
    alternancia_atividades = Column(Boolean, default=True)
    
    regime_preferencial = Column(String(10), default="5x2")
    permitir_alternar_regime = Column(Boolean, default=True)
    dias_folga_semana = Column(Integer, default=2)
    folgas_consecutivas = Column(Boolean, default=True)
    
    percentual_max_repeticao_turno = Column(Float, default=60.0)
    percentual_max_repeticao_dia_turno = Column(Float, default=50.0)
    modo_conservador = Column(Boolean, default=True)
    intervalo_semanas_folga = Column(Integer, default=4)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    sector = relationship("Sector", backref="operational_rules")
