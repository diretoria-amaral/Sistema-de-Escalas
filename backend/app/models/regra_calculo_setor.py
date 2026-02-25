from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class RegraEscopo(str, enum.Enum):
    """
    Escopo de aplicação da regra de cálculo:
    - DEMANDA: Define como calcular horas/minutos de trabalho
    - PROGRAMACAO: Define como inserir/ordenar atividades na semana
    - AJUSTES: Define ajustes por estatística/HP/viés por dia
    """
    DEMANDA = "DEMANDA"
    PROGRAMACAO = "PROGRAMACAO"
    AJUSTES = "AJUSTES"


class RegraCalculoSetor(Base):
    """
    Regras de cálculo por setor que definem:
    - Como calcular demanda de trabalho
    - Como alocar atividades na programação semanal
    - Como determinar atividades CALCULADA_PELO_AGENTE automáticas
    
    Regras são versionáveis por data/estado e ordenadas por prioridade.
    """
    __tablename__ = "regras_calculo_setor"

    id = Column(Integer, primary_key=True, index=True)
    setor_id = Column(Integer, ForeignKey("sectors.id"), nullable=False, index=True)
    nome = Column(String(200), nullable=False)
    descricao = Column(String(1000), nullable=True)
    prioridade = Column(Integer, nullable=False, default=100, index=True)
    escopo = Column(
        String(20),
        nullable=False,
        index=True
    )
    condicao_json = Column(JSON, nullable=True)
    acao_json = Column(JSON, nullable=False)
    ativo = Column(Boolean, default=True, nullable=False, index=True)
    criado_em = Column(DateTime(timezone=True), server_default=func.now())
    atualizado_em = Column(DateTime(timezone=True), onupdate=func.now())

    setor = relationship("Sector", back_populates="regras_calculo")
