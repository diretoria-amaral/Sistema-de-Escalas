from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class RegraEscopoEnum(str, Enum):
    DEMANDA = "DEMANDA"
    PROGRAMACAO = "PROGRAMACAO"
    AJUSTES = "AJUSTES"


DRIVERS_VALIDOS = ["ocupacao", "quartos_ocupados", "checkout", "checkin", "stayover", "fixo"]
DIAS_VALIDOS = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"]
ACOES_VALIDAS = ["inserir_atividade", "multiplicar_demanda", "adicionar_minutos", "aplicar_fator"]
OPERADORES_VALIDOS = ["+", "-", "*", "/", "min", "max"]


def validar_condicao_json(condicao: Optional[Dict[str, Any]]) -> None:
    """Valida estrutura do JSON de condição."""
    if condicao is None:
        return
    
    if "driver" in condicao:
        if condicao["driver"] not in DRIVERS_VALIDOS:
            raise ValueError(f"Driver inválido: {condicao['driver']}. Valores válidos: {DRIVERS_VALIDOS}")
    
    if "min" in condicao:
        if not isinstance(condicao["min"], (int, float)):
            raise ValueError("Campo 'min' deve ser numérico.")
        if condicao["min"] < 0:
            raise ValueError("Campo 'min' não pode ser negativo.")
    
    if "max" in condicao:
        if not isinstance(condicao["max"], (int, float)):
            raise ValueError("Campo 'max' deve ser numérico.")
    
    if "min" in condicao and "max" in condicao:
        if condicao["min"] > condicao["max"]:
            raise ValueError("Campo 'min' não pode ser maior que 'max'.")
    
    if "dias" in condicao:
        if not isinstance(condicao["dias"], list):
            raise ValueError("Campo 'dias' deve ser uma lista.")
        for dia in condicao["dias"]:
            if dia not in DIAS_VALIDOS:
                raise ValueError(f"Dia inválido: {dia}. Valores válidos: {DIAS_VALIDOS}")


def validar_acao_json(acao: Dict[str, Any], escopo: str) -> None:
    """Valida estrutura do JSON de ação baseado no escopo."""
    if not acao:
        raise ValueError("Campo 'acao_json' é obrigatório e não pode estar vazio.")
    
    if "tipo" not in acao:
        raise ValueError("Campo 'tipo' é obrigatório em acao_json.")
    
    tipo = acao["tipo"]
    if tipo not in ACOES_VALIDAS:
        raise ValueError(f"Tipo de ação inválido: {tipo}. Valores válidos: {ACOES_VALIDAS}")
    
    if tipo == "inserir_atividade":
        if "atividade_id" not in acao:
            raise ValueError("Ação 'inserir_atividade' requer campo 'atividade_id'.")
        if not isinstance(acao["atividade_id"], int):
            raise ValueError("Campo 'atividade_id' deve ser um inteiro.")
    
    if tipo == "multiplicar_demanda":
        if "fator" not in acao:
            raise ValueError("Ação 'multiplicar_demanda' requer campo 'fator'.")
        if not isinstance(acao["fator"], (int, float)):
            raise ValueError("Campo 'fator' deve ser numérico.")
        if acao["fator"] < 0:
            raise ValueError("Campo 'fator' não pode ser negativo.")
    
    if tipo == "adicionar_minutos":
        if "minutos" not in acao:
            raise ValueError("Ação 'adicionar_minutos' requer campo 'minutos'.")
        if not isinstance(acao["minutos"], (int, float)):
            raise ValueError("Campo 'minutos' deve ser numérico.")
    
    if tipo == "aplicar_fator":
        if "fator" not in acao:
            raise ValueError("Ação 'aplicar_fator' requer campo 'fator'.")
        if "parametro" not in acao:
            raise ValueError("Ação 'aplicar_fator' requer campo 'parametro'.")


class RegraCalculoSetorBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=200, description="Nome da regra")
    descricao: Optional[str] = Field(None, max_length=1000, description="Descrição detalhada da regra")
    prioridade: int = Field(default=100, ge=1, le=9999, description="Prioridade de execução (menor = primeiro)")
    escopo: RegraEscopoEnum = Field(..., description="Escopo de aplicação da regra")
    condicao_json: Optional[Dict[str, Any]] = Field(None, description="Condições para aplicação da regra")
    acao_json: Dict[str, Any] = Field(..., description="Ação a ser executada quando condições forem atendidas")
    ativo: bool = Field(default=True, description="Se a regra está ativa")


class RegraCalculoSetorCreate(RegraCalculoSetorBase):
    setor_id: int = Field(..., description="ID do setor")
    
    @field_validator('condicao_json')
    @classmethod
    def validate_condicao(cls, v):
        validar_condicao_json(v)
        return v
    
    @model_validator(mode='after')
    def validate_acao(self):
        validar_acao_json(self.acao_json, self.escopo.value)
        return self


class RegraCalculoSetorUpdate(BaseModel):
    nome: Optional[str] = Field(None, min_length=1, max_length=200)
    descricao: Optional[str] = Field(None, max_length=1000)
    prioridade: Optional[int] = Field(None, ge=1, le=9999)
    escopo: Optional[RegraEscopoEnum] = None
    condicao_json: Optional[Dict[str, Any]] = None
    acao_json: Optional[Dict[str, Any]] = None
    ativo: Optional[bool] = None
    
    @field_validator('condicao_json')
    @classmethod
    def validate_condicao(cls, v):
        if v is not None:
            validar_condicao_json(v)
        return v


class RegraCalculoSetorResponse(RegraCalculoSetorBase):
    id: int
    setor_id: int
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class RegraCalculoSetorListResponse(BaseModel):
    regras: List[RegraCalculoSetorResponse]
    total: int
