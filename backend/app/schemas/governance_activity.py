from pydantic import BaseModel, field_validator, model_validator
from typing import Optional
from datetime import datetime, date
from enum import Enum


class WorkloadDriverEnum(str, Enum):
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"


class ActivityClassificationEnum(str, Enum):
    CALCULADA_PELO_AGENTE = "CALCULADA_PELO_AGENTE"
    RECORRENTE = "RECORRENTE"
    EVENTUAL = "EVENTUAL"


class GovernanceActivityBase(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    average_time_minutes: float
    unit_type: Optional[str] = None
    workload_driver: WorkloadDriverEnum = WorkloadDriverEnum.VARIABLE
    classificacao_atividade: ActivityClassificationEnum = ActivityClassificationEnum.CALCULADA_PELO_AGENTE
    periodicidade_id: Optional[int] = None
    tolerancia_dias: Optional[int] = None
    data_primeira_execucao: Optional[date] = None
    difficulty_level: int = 1
    requires_training: bool = False
    is_active: bool = True


class GovernanceActivityCreate(GovernanceActivityBase):
    sector_id: int
    
    @model_validator(mode='after')
    def validate_classification_fields(self):
        classificacao = self.classificacao_atividade
        
        if classificacao == ActivityClassificationEnum.RECORRENTE:
            if not self.periodicidade_id:
                raise ValueError('Atividades RECORRENTES devem ter uma periodicidade definida.')
            if not self.data_primeira_execucao:
                raise ValueError('Atividades RECORRENTES devem ter uma data de primeira execucao.')
        
        if classificacao == ActivityClassificationEnum.EVENTUAL:
            if self.periodicidade_id is not None:
                raise ValueError('Atividades EVENTUAIS nao podem ter periodicidade.')
            if self.tolerancia_dias is not None:
                raise ValueError('Atividades EVENTUAIS nao podem ter tolerancia de dias.')
            if self.data_primeira_execucao is not None:
                raise ValueError('Atividades EVENTUAIS nao podem ter data de primeira execucao.')
        
        if classificacao == ActivityClassificationEnum.CALCULADA_PELO_AGENTE:
            if self.periodicidade_id is not None:
                raise ValueError('Atividades CALCULADAS_PELO_AGENTE nao podem ter periodicidade.')
            if self.tolerancia_dias is not None:
                raise ValueError('Atividades CALCULADAS_PELO_AGENTE nao podem ter tolerancia de dias.')
            if self.data_primeira_execucao is not None:
                raise ValueError('Atividades CALCULADAS_PELO_AGENTE nao podem ter data de primeira execucao.')
        
        return self


class GovernanceActivityUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    description: Optional[str] = None
    average_time_minutes: Optional[float] = None
    unit_type: Optional[str] = None
    workload_driver: Optional[WorkloadDriverEnum] = None
    classificacao_atividade: Optional[ActivityClassificationEnum] = None
    periodicidade_id: Optional[int] = None
    tolerancia_dias: Optional[int] = None
    data_primeira_execucao: Optional[date] = None
    difficulty_level: Optional[int] = None
    requires_training: Optional[bool] = None
    is_active: Optional[bool] = None
    
    def validate_classification_fields(
        self,
        current_classificacao: str,
        current_periodicidade_id: Optional[int],
        current_tolerancia_dias: Optional[int],
        current_data_primeira_execucao: Optional[date],
        periodicidade_tipo: Optional[str] = None
    ) -> None:
        """
        Valida consistencia entre classificacao e campos relacionados ao atualizar.
        Deve ser chamado no router passando os valores atuais da entidade.
        """
        new_classificacao = self.classificacao_atividade.value if self.classificacao_atividade else current_classificacao
        
        new_periodicidade = self.periodicidade_id if 'periodicidade_id' in self.model_fields_set else current_periodicidade_id
        new_tolerancia = self.tolerancia_dias if 'tolerancia_dias' in self.model_fields_set else current_tolerancia_dias
        new_data_exec = self.data_primeira_execucao if 'data_primeira_execucao' in self.model_fields_set else current_data_primeira_execucao
        
        if new_classificacao == 'RECORRENTE':
            if not new_periodicidade:
                raise ValueError('Atividades RECORRENTES devem ter uma periodicidade definida.')
            if not new_data_exec:
                raise ValueError('Atividades RECORRENTES devem ter uma data de primeira execucao.')
            if periodicidade_tipo and periodicidade_tipo != 'DAILY' and not new_tolerancia:
                raise ValueError('Atividades RECORRENTES com periodicidade diferente de DIARIA devem ter tolerancia de dias.')
        
        if new_classificacao == 'EVENTUAL':
            if new_periodicidade:
                raise ValueError('Atividades EVENTUAIS nao podem ter periodicidade.')
            if new_tolerancia:
                raise ValueError('Atividades EVENTUAIS nao podem ter tolerancia de dias.')
            if new_data_exec:
                raise ValueError('Atividades EVENTUAIS nao podem ter data de primeira execucao.')
        
        if new_classificacao == 'CALCULADA_PELO_AGENTE':
            if new_periodicidade:
                raise ValueError('Atividades CALCULADAS_PELO_AGENTE nao podem ter periodicidade.')
            if new_tolerancia:
                raise ValueError('Atividades CALCULADAS_PELO_AGENTE nao podem ter tolerancia de dias.')
            if new_data_exec:
                raise ValueError('Atividades CALCULADAS_PELO_AGENTE nao podem ter data de primeira execucao.')


class GovernanceActivityResponse(GovernanceActivityBase):
    id: int
    sector_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
