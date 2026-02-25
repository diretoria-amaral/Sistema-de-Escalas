"""
Serviço para execução segura de regras de cálculo por setor.

Este serviço:
- Avalia condições das regras sem usar eval() ou exec()
- Executa ações definidas nas regras
- Integra com cálculo de demanda e programação semanal
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import date
from sqlalchemy.orm import Session

from app.models.regra_calculo_setor import RegraCalculoSetor, RegraEscopo
from app.models.governance_activity import GovernanceActivity, ActivityClassification


def avaliar_condicao(
    condicao: Optional[Dict[str, Any]],
    contexto: Dict[str, Any]
) -> bool:
    """
    Avalia se a condição da regra é satisfeita pelo contexto atual.
    
    Contexto esperado:
    - ocupacao: float (0.0 a 1.0)
    - quartos_ocupados: int
    - checkout: int
    - checkin: int
    - stayover: int
    - dia_semana: str (SEG, TER, QUA, QUI, SEX, SAB, DOM)
    
    Retorna True se a condição é satisfeita.
    """
    if not condicao:
        return True
    
    if "driver" in condicao:
        driver = condicao["driver"]
        valor = contexto.get(driver)
        
        if valor is None:
            if driver != "fixo":
                return False
        else:
            if "min" in condicao and valor < condicao["min"]:
                return False
            if "max" in condicao and valor > condicao["max"]:
                return False
    
    if "dias" in condicao:
        dia_atual = contexto.get("dia_semana")
        if dia_atual and dia_atual not in condicao["dias"]:
            return False
    
    return True


def executar_acao_demanda(
    acao: Dict[str, Any],
    demanda_atual: float,
    contexto: Dict[str, Any]
) -> float:
    """
    Executa uma ação de demanda e retorna a nova demanda.
    
    Tipos de ação suportados:
    - multiplicar_demanda: multiplica demanda pelo fator
    - adicionar_minutos: adiciona minutos fixos
    - aplicar_fator: aplica fator baseado em parâmetro do contexto
    """
    tipo = acao.get("tipo")
    
    if tipo == "multiplicar_demanda":
        fator = acao.get("fator", 1.0)
        return demanda_atual * fator
    
    if tipo == "adicionar_minutos":
        minutos = acao.get("minutos", 0)
        return demanda_atual + minutos
    
    if tipo == "aplicar_fator":
        fator = acao.get("fator", 1.0)
        parametro = acao.get("parametro")
        if parametro and parametro in contexto:
            valor_param = contexto[parametro]
            return demanda_atual * fator * valor_param
        return demanda_atual * fator
    
    return demanda_atual


def executar_acao_programacao(
    acao: Dict[str, Any],
    db: Session
) -> Optional[int]:
    """
    Executa uma ação de programação e retorna o ID da atividade a inserir.
    
    Tipos de ação suportados:
    - inserir_atividade: retorna o ID da atividade a ser inserida
    """
    tipo = acao.get("tipo")
    
    if tipo == "inserir_atividade":
        return acao.get("atividade_id")
    
    return None


def obter_regras_setor(
    db: Session,
    setor_id: int,
    escopo: Optional[RegraEscopo] = None
) -> List[RegraCalculoSetor]:
    """
    Obtém regras ativas de um setor, ordenadas por prioridade.
    """
    query = db.query(RegraCalculoSetor).filter(
        RegraCalculoSetor.setor_id == setor_id,
        RegraCalculoSetor.ativo == True
    )
    
    if escopo:
        query = query.filter(RegraCalculoSetor.escopo == escopo)
    
    return query.order_by(RegraCalculoSetor.prioridade.asc()).all()


def calcular_demanda_com_regras(
    db: Session,
    setor_id: int,
    demanda_base: float,
    contexto: Dict[str, Any]
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Aplica regras de DEMANDA sobre a demanda base.
    
    Retorna:
    - demanda_final: float
    - log_aplicacoes: lista de regras aplicadas com detalhes
    """
    regras = obter_regras_setor(db, setor_id, RegraEscopo.DEMANDA)
    
    demanda = demanda_base
    log = []
    
    for regra in regras:
        if avaliar_condicao(regra.condicao_json, contexto):
            demanda_anterior = demanda
            demanda = executar_acao_demanda(regra.acao_json, demanda, contexto)
            
            log.append({
                "regra_id": regra.id,
                "regra_nome": regra.nome,
                "prioridade": regra.prioridade,
                "demanda_antes": demanda_anterior,
                "demanda_depois": demanda,
                "acao": regra.acao_json
            })
    
    return demanda, log


def aplicar_ajustes_com_regras(
    db: Session,
    setor_id: int,
    demanda: float,
    contexto: Dict[str, Any]
) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Aplica regras de AJUSTES sobre a demanda.
    
    Retorna:
    - demanda_ajustada: float
    - log_aplicacoes: lista de regras aplicadas
    """
    regras = obter_regras_setor(db, setor_id, RegraEscopo.AJUSTES)
    
    demanda_ajustada = demanda
    log = []
    
    for regra in regras:
        if avaliar_condicao(regra.condicao_json, contexto):
            demanda_anterior = demanda_ajustada
            demanda_ajustada = executar_acao_demanda(regra.acao_json, demanda_ajustada, contexto)
            
            log.append({
                "regra_id": regra.id,
                "regra_nome": regra.nome,
                "prioridade": regra.prioridade,
                "demanda_antes": demanda_anterior,
                "demanda_depois": demanda_ajustada,
                "acao": regra.acao_json
            })
    
    return demanda_ajustada, log


def obter_atividades_programacao(
    db: Session,
    setor_id: int,
    contexto: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Determina quais atividades CALCULADAS_PELO_AGENTE devem ser inseridas
    na programação semanal baseado nas regras de PROGRAMACAO.
    
    Retorna lista de atividades com seus dados e origem (regra que determinou).
    """
    regras = obter_regras_setor(db, setor_id, RegraEscopo.PROGRAMACAO)
    
    atividades_programadas = []
    atividades_ids_inseridos = set()
    
    for regra in regras:
        if avaliar_condicao(regra.condicao_json, contexto):
            atividade_id = executar_acao_programacao(regra.acao_json, db)
            
            if atividade_id and atividade_id not in atividades_ids_inseridos:
                atividade = db.query(GovernanceActivity).filter(
                    GovernanceActivity.id == atividade_id,
                    GovernanceActivity.is_active == True
                ).first()
                
                if atividade:
                    atividades_programadas.append({
                        "atividade_id": atividade.id,
                        "atividade_nome": atividade.name,
                        "atividade_codigo": atividade.code,
                        "tempo_medio_minutos": atividade.average_time_minutes,
                        "driver": atividade.workload_driver.value if atividade.workload_driver else "VARIABLE",
                        "origem": "AUTO",
                        "regra_id": regra.id,
                        "regra_nome": regra.nome,
                        "condicao": regra.condicao_json
                    })
                    atividades_ids_inseridos.add(atividade_id)
    
    return atividades_programadas


def validar_regras_para_modo_auto(
    db: Session,
    setor_id: int
) -> Dict[str, Any]:
    """
    Valida se o setor possui regras configuradas para todas as atividades
    CALCULADAS_PELO_AGENTE, requisito para usar modo AUTO.
    
    Retorna:
    - pode_usar_auto: bool
    - erros: lista de problemas encontrados
    """
    atividades_calculadas = db.query(GovernanceActivity).filter(
        GovernanceActivity.sector_id == setor_id,
        GovernanceActivity.classificacao_atividade == ActivityClassification.CALCULADA_PELO_AGENTE,
        GovernanceActivity.is_active == True
    ).all()
    
    regras_programacao = obter_regras_setor(db, setor_id, RegraEscopo.PROGRAMACAO)
    regras_demanda = obter_regras_setor(db, setor_id, RegraEscopo.DEMANDA)
    
    atividades_cobertas = set()
    for regra in regras_programacao:
        if regra.acao_json and regra.acao_json.get("tipo") == "inserir_atividade":
            atividades_cobertas.add(regra.acao_json.get("atividade_id"))
    
    erros = []
    atividades_sem_regra = []
    
    for ativ in atividades_calculadas:
        if ativ.id not in atividades_cobertas:
            atividades_sem_regra.append({
                "id": ativ.id,
                "nome": ativ.name,
                "codigo": ativ.code
            })
    
    if atividades_sem_regra:
        erros.append({
            "tipo": "ATIVIDADES_SEM_REGRA",
            "mensagem": f"Existem {len(atividades_sem_regra)} atividades CALCULADAS_PELO_AGENTE sem regras de programação.",
            "detalhes": atividades_sem_regra
        })
    
    if atividades_calculadas and not regras_demanda:
        erros.append({
            "tipo": "SEM_REGRAS_DEMANDA",
            "mensagem": "Nenhuma regra de DEMANDA configurada para o setor."
        })
    
    return {
        "pode_usar_auto": len(erros) == 0,
        "total_atividades_calculadas": len(atividades_calculadas),
        "total_regras_programacao": len(regras_programacao),
        "total_regras_demanda": len(regras_demanda),
        "erros": erros
    }
