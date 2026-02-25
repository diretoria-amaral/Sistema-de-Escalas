from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class GovernanceRulesBase(BaseModel):
    # REGRAS TRABALHISTAS
    limite_horas_diarias: float = 8.0
    limite_horas_semanais_sem_extra: float = 44.0
    limite_horas_semanais_com_extra: float = 48.0
    intervalo_minimo_entre_turnos: float = 11.0
    intervalo_intrajornada_minimo: float = 1.0
    intervalo_intrajornada_maximo: float = 2.0
    jornada_dispensa_intervalo: float = 4.0
    domingos_folga_por_mes: int = 1
    dias_ferias_anuais: int = 30
    permite_fracionamento_ferias: bool = True
    respeitar_cbo_atividade: bool = True
    
    # REGRAS OPERACIONAIS
    alternancia_horarios: bool = True
    alternancia_atividades: bool = True
    variacao_minima_semanal: float = 36.0
    variacao_maxima_semanal: float = 44.0
    regime_preferencial: str = "5x2"
    permitir_alternar_regime: bool = True
    dias_folga_semana: int = 2
    folgas_consecutivas: bool = True
    maximo_dias_consecutivos: int = 6
    
    # TEMPOS DE LIMPEZA
    tempo_padrao_vago_sujo: float = 25.0
    tempo_padrao_estada: float = 10.0
    fator_feriado: float = 1.1
    fator_vespera_feriado: float = 1.05
    
    # CONFIGURAÇÕES DE TURNO
    turno_manha_inicio: str = "07:00"
    turno_manha_fim: str = "15:00"
    turno_tarde_inicio: str = "14:00"
    turno_tarde_fim: str = "22:00"
    jornada_media_horas: float = 8.0
    
    # REGRAS PARA FERIADOS
    permitir_intermitentes_feriado: bool = True
    preferir_efetivos_feriado: bool = True
    
    # CAMPO LÓGICA
    logica_customizada: Optional[str] = None
    
    # CONTROLE DE ALTERNÂNCIA
    percentual_max_repeticao_turno: float = 60.0
    percentual_max_repeticao_dia_turno: float = 50.0
    modo_conservador: bool = True
    intervalo_semanas_folga: int = 4


class GovernanceRulesCreate(GovernanceRulesBase):
    pass


class GovernanceRulesUpdate(BaseModel):
    # REGRAS TRABALHISTAS
    limite_horas_diarias: Optional[float] = None
    limite_horas_semanais_sem_extra: Optional[float] = None
    limite_horas_semanais_com_extra: Optional[float] = None
    intervalo_minimo_entre_turnos: Optional[float] = None
    intervalo_intrajornada_minimo: Optional[float] = None
    intervalo_intrajornada_maximo: Optional[float] = None
    jornada_dispensa_intervalo: Optional[float] = None
    domingos_folga_por_mes: Optional[int] = None
    dias_ferias_anuais: Optional[int] = None
    permite_fracionamento_ferias: Optional[bool] = None
    respeitar_cbo_atividade: Optional[bool] = None
    
    # REGRAS OPERACIONAIS
    alternancia_horarios: Optional[bool] = None
    alternancia_atividades: Optional[bool] = None
    variacao_minima_semanal: Optional[float] = None
    variacao_maxima_semanal: Optional[float] = None
    regime_preferencial: Optional[str] = None
    permitir_alternar_regime: Optional[bool] = None
    dias_folga_semana: Optional[int] = None
    folgas_consecutivas: Optional[bool] = None
    maximo_dias_consecutivos: Optional[int] = None
    
    # TEMPOS DE LIMPEZA
    tempo_padrao_vago_sujo: Optional[float] = None
    tempo_padrao_estada: Optional[float] = None
    fator_feriado: Optional[float] = None
    fator_vespera_feriado: Optional[float] = None
    
    # CONFIGURAÇÕES DE TURNO
    turno_manha_inicio: Optional[str] = None
    turno_manha_fim: Optional[str] = None
    turno_tarde_inicio: Optional[str] = None
    turno_tarde_fim: Optional[str] = None
    jornada_media_horas: Optional[float] = None
    
    # REGRAS PARA FERIADOS
    permitir_intermitentes_feriado: Optional[bool] = None
    preferir_efetivos_feriado: Optional[bool] = None
    
    # CAMPO LÓGICA
    logica_customizada: Optional[str] = None
    
    # CONTROLE DE ALTERNÂNCIA
    percentual_max_repeticao_turno: Optional[float] = None
    percentual_max_repeticao_dia_turno: Optional[float] = None
    modo_conservador: Optional[bool] = None
    intervalo_semanas_folga: Optional[int] = None


class GovernanceRulesResponse(GovernanceRulesBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
