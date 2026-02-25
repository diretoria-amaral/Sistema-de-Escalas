from sqlalchemy import Column, Integer, Float, Boolean, String, Text
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from app.database import Base


class GovernanceRules(Base):
    """
    Painel de Regras e Parâmetros da Governança.
    Armazena configurações ajustáveis pelo usuário para geração de escalas.
    Apenas uma entrada ativa por vez (singleton).
    """
    __tablename__ = "governance_rules"

    id = Column(Integer, primary_key=True, index=True)
    
    # ============================================
    # REGRAS TRABALHISTAS (Editáveis pelo usuário)
    # ============================================
    
    # Limite de horas
    limite_horas_diarias = Column(Float, default=8.0)
    limite_horas_semanais_sem_extra = Column(Float, default=44.0)
    limite_horas_semanais_com_extra = Column(Float, default=48.0)
    
    # Intervalo entre turnos
    intervalo_minimo_entre_turnos = Column(Float, default=11.0)  # Horas
    
    # Intervalo intrajornada (descanso/almoço)
    intervalo_intrajornada_minimo = Column(Float, default=1.0)  # Horas
    intervalo_intrajornada_maximo = Column(Float, default=2.0)  # Horas
    jornada_dispensa_intervalo = Column(Float, default=4.0)  # Jornadas até X horas dispensam intervalo
    
    # Domingo de folga
    domingos_folga_por_mes = Column(Integer, default=1)  # Mínimo de domingos de folga por mês
    
    # Férias
    dias_ferias_anuais = Column(Integer, default=30)
    permite_fracionamento_ferias = Column(Boolean, default=True)
    
    # CBO e atividades
    respeitar_cbo_atividade = Column(Boolean, default=True)  # Convocações respeitam CBO
    
    # ============================================
    # REGRAS OPERACIONAIS (Editáveis)
    # ============================================
    
    # Alternância obrigatória
    alternancia_horarios = Column(Boolean, default=True)
    alternancia_atividades = Column(Boolean, default=True)
    
    # Variação semanal de horas
    variacao_minima_semanal = Column(Float, default=36.0)
    variacao_maxima_semanal = Column(Float, default=44.0)
    
    # Regime de trabalho preferencial
    regime_preferencial = Column(String(10), default="5x2")  # 5x2 ou 6x1
    permitir_alternar_regime = Column(Boolean, default=True)
    
    # Folgas semanais
    dias_folga_semana = Column(Integer, default=2)
    folgas_consecutivas = Column(Boolean, default=True)  # Idealmente consecutivas
    
    # Dias máximos consecutivos de trabalho
    maximo_dias_consecutivos = Column(Integer, default=6)
    
    # ============================================
    # TEMPOS MÉDIOS DE LIMPEZA (Governança)
    # ============================================
    
    tempo_padrao_vago_sujo = Column(Float, default=25.0)  # Minutos
    tempo_padrao_estada = Column(Float, default=10.0)     # Minutos
    
    # Meta de aproveitamento das horas (% da jornada efetiva)
    meta_aproveitamento_horas = Column(Float, default=85.0)  # Percentual (ex: 85%)
    
    # Fatores de ajuste
    fator_feriado = Column(Float, default=1.1)
    fator_vespera_feriado = Column(Float, default=1.05)
    fator_pico = Column(Float, default=1.2)  # Alta demanda
    fator_baixa_ocupacao = Column(Float, default=0.9)  # Baixa demanda
    
    # ============================================
    # CONFIGURAÇÕES DE TURNO
    # ============================================
    
    turno_manha_inicio = Column(String(5), default="07:00")
    turno_manha_fim = Column(String(5), default="15:00")
    turno_tarde_inicio = Column(String(5), default="14:00")
    turno_tarde_fim = Column(String(5), default="22:00")
    
    # Jornada média para cálculo
    jornada_media_horas = Column(Float, default=8.0)
    
    # ============================================
    # REGRAS PARA FERIADOS
    # ============================================
    
    permitir_intermitentes_feriado = Column(Boolean, default=True)
    preferir_efetivos_feriado = Column(Boolean, default=True)
    
    # ============================================
    # CAMPO LÓGICA (Editável pelo administrador)
    # ============================================
    
    logica_customizada = Column(Text, nullable=True)  # Regras em linguagem natural
    
    # ============================================
    # CONTROLE DE ALTERNÂNCIA E HISTÓRICO
    # ============================================
    
    percentual_max_repeticao_turno = Column(Float, default=60.0)
    percentual_max_repeticao_dia_turno = Column(Float, default=50.0)
    modo_conservador = Column(Boolean, default=True)
    
    # Intervalo entre convocações
    intervalo_semanas_folga = Column(Integer, default=4)
    
    # ============================================
    # METADADOS
    # ============================================
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
