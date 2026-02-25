"""
Serviço de Geração de Escalas de Governança
Módulo responsável pelo cálculo de necessidade de mão de obra e geração de escalas sugestivas.
Formato de saída: Dia | Data | Horas | Entrada | Início Intervalo | Fim Intervalo | Saída | Atividade
"""

from typing import List, Dict, Any, Optional
from datetime import date, timedelta, datetime, time
from sqlalchemy.orm import Session

from app.models.employee import Employee, ContractType
from app.models.weekly_parameters import WeeklyParameters, DayType
from app.models.governance_rules import GovernanceRules


DIAS_SEMANA = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]
NOMES_DIAS = {
    "seg": "Segunda-feira",
    "ter": "Terça-feira",
    "qua": "Quarta-feira",
    "qui": "Quinta-feira",
    "sex": "Sexta-feira",
    "sab": "Sábado",
    "dom": "Domingo"
}
DIAS_OFFSET = {"seg": 0, "ter": 1, "qua": 2, "qui": 3, "sex": 4, "sab": 5, "dom": 6}


def parse_time(time_str: str) -> time:
    """Converte string HH:MM para objeto time."""
    parts = time_str.split(":")
    return time(int(parts[0]), int(parts[1]))


def add_hours(t: time, hours: float) -> time:
    """Adiciona horas a um objeto time."""
    total_minutes = t.hour * 60 + t.minute + int(hours * 60)
    new_hour = (total_minutes // 60) % 24
    new_minute = total_minutes % 60
    return time(new_hour, new_minute)


def format_time(t: time) -> str:
    """Formata time para string HH:MM."""
    return t.strftime("%H:%M")


def calcular_horas_necessarias_dia(
    quartos_vagos_sujos: int,
    quartos_estada: int,
    tempo_vago_sujo: float,
    tempo_estada: float,
    tipo_dia: DayType,
    fator_feriado: float,
    fator_vespera_feriado: float
) -> Dict[str, float]:
    """
    Calcula as horas necessárias de governança para um dia específico.
    
    Args:
        quartos_vagos_sujos: Número de quartos vagos sujos previstos
        quartos_estada: Número de quartos com estada previstos
        tempo_vago_sujo: Tempo em minutos para limpar quarto vago sujo
        tempo_estada: Tempo em minutos para limpar quarto estada
        tipo_dia: Tipo do dia (normal, feriado, véspera de feriado)
        fator_feriado: Multiplicador para dias de feriado
        fator_vespera_feriado: Multiplicador para vésperas de feriado
    
    Returns:
        Dicionário com minutos e horas necessárias detalhadas
    """
    minutos_vago_sujo = quartos_vagos_sujos * tempo_vago_sujo
    minutos_estada = quartos_estada * tempo_estada
    minutos_totais = minutos_vago_sujo + minutos_estada
    
    if tipo_dia == DayType.FERIADO:
        minutos_totais *= fator_feriado
    elif tipo_dia == DayType.VESPERA_FERIADO:
        minutos_totais *= fator_vespera_feriado
    
    horas_necessarias = minutos_totais / 60
    
    return {
        "minutos_vago_sujo": minutos_vago_sujo,
        "minutos_estada": minutos_estada,
        "minutos_totais": minutos_totais,
        "horas_necessarias": round(horas_necessarias, 2),
        "tipo_dia": tipo_dia.value
    }


def calcular_horarios_jornada(
    hora_entrada: str,
    horas_trabalho: float,
    regras: GovernanceRules
) -> Dict[str, str]:
    """
    Calcula os horários completos da jornada incluindo intervalo.
    
    Regras de intervalo intrajornada:
    - Jornadas até 4h: dispensadas de intervalo
    - Jornadas maiores: intervalo de 1h a 2h
    
    Returns:
        Dict com entrada, inicio_intervalo, fim_intervalo, saida
    """
    entrada = parse_time(hora_entrada)
    
    if horas_trabalho <= regras.jornada_dispensa_intervalo:
        saida = add_hours(entrada, horas_trabalho)
        return {
            "entrada": format_time(entrada),
            "inicio_intervalo": "-",
            "fim_intervalo": "-",
            "saida": format_time(saida)
        }
    
    horas_ate_intervalo = 4.0
    inicio_intervalo = add_hours(entrada, horas_ate_intervalo)
    
    duracao_intervalo = regras.intervalo_intrajornada_minimo
    fim_intervalo = add_hours(inicio_intervalo, duracao_intervalo)
    
    horas_apos_intervalo = horas_trabalho - horas_ate_intervalo
    saida = add_hours(fim_intervalo, horas_apos_intervalo)
    
    return {
        "entrada": format_time(entrada),
        "inicio_intervalo": format_time(inicio_intervalo),
        "fim_intervalo": format_time(fim_intervalo),
        "saida": format_time(saida)
    }


class ScheduleGenerator:
    """
    Gerador de escalas sugestivas para setores do hotel.
    Implementa lógica de distribuição equilibrada entre colaboradores.
    Produz formato: Dia | Data | Horas | Entrada | Início Intervalo | Fim Intervalo | Saída | Atividade
    Usa sector_id para filtrar colaboradores e aplicar regras operacionais específicas.
    """
    
    def __init__(self, db: Session, sector_id: int = None):
        self.db = db
        self.sector_id = sector_id
    
    def obter_regras_ativas(self) -> GovernanceRules:
        """Obtém as regras de governança ativas ou cria padrão."""
        regras = self.db.query(GovernanceRules).filter(
            GovernanceRules.is_active == True
        ).first()
        if not regras:
            regras = GovernanceRules()
            self.db.add(regras)
            self.db.commit()
            self.db.refresh(regras)
        return regras
    
    def obter_colaboradores_governanca(self, setor_nome: str = "Governança") -> List[Employee]:
        """
        Obtém todos os colaboradores ativos do setor selecionado.
        Usa self.sector_id se definido, senão busca por nome do setor.
        Retorna lista ordenada por tipo de contrato (intermitentes primeiro para distribuição).
        """
        from app.models.sector import Sector
        
        if self.sector_id:
            setor = self.db.query(Sector).filter(Sector.id == self.sector_id).first()
        else:
            setor = self.db.query(Sector).filter(Sector.name == setor_nome).first()
        
        if not setor:
            return []
        
        colaboradores = self.db.query(Employee).filter(
            Employee.sector_id == setor.id,
            Employee.is_active == True
        ).all()
        
        colaboradores.sort(key=lambda e: (
            0 if e.contract_type == ContractType.INTERMITTENT else 1
        ))
        
        return colaboradores
    
    def calcular_necessidade_semanal(
        self,
        parametros: WeeklyParameters,
        regras: GovernanceRules
    ) -> Dict[str, Dict[str, float]]:
        """
        Calcula a necessidade de horas para cada dia da semana.
        
        Returns:
            Dicionário com cálculo detalhado por dia
        """
        resultado = {}
        
        for dia in DIAS_SEMANA:
            quartos_vagos = getattr(parametros, f"{dia}_quartos_vagos_sujos", 0)
            quartos_estada = getattr(parametros, f"{dia}_quartos_estada", 0)
            tipo_dia = getattr(parametros, f"{dia}_tipo_dia", DayType.NORMAL)
            
            calculo = calcular_horas_necessarias_dia(
                quartos_vagos_sujos=quartos_vagos,
                quartos_estada=quartos_estada,
                tempo_vago_sujo=regras.tempo_padrao_vago_sujo,
                tempo_estada=regras.tempo_padrao_estada,
                tipo_dia=tipo_dia,
                fator_feriado=regras.fator_feriado,
                fator_vespera_feriado=regras.fator_vespera_feriado
            )
            
            resultado[dia] = {
                "nome_dia": NOMES_DIAS[dia],
                **calculo
            }
        
        return resultado
    
    def gerar_escala_sugestiva(
        self,
        parametros: WeeklyParameters,
        regras: Optional[GovernanceRules] = None
    ) -> Dict[str, Any]:
        """
        Gera uma escala semanal sugestiva para governança.
        
        Formato de saída por colaborador:
        Dia | Data | Horas | Entrada | Início Intervalo | Fim Intervalo | Saída | Atividade
        
        Lógica de distribuição:
        1. Calcula horas necessárias por dia
        2. Prioriza distribuição equilibrada entre colaboradores
        3. Respeita limites de carga horária e dias consecutivos
        4. Calcula horários com intervalos conforme regras trabalhistas
        5. Alterna turnos conforme modo (conservador/flexível)
        
        Returns:
            Dicionário com escala completa, detalhada por colaborador, e resumo
        """
        if regras is None:
            regras = self.obter_regras_ativas()
        
        colaboradores = self.obter_colaboradores_governanca()
        if not colaboradores:
            return {
                "erro": "Nenhum colaborador encontrado no setor de Governança",
                "escala_diaria": {},
                "escala_colaboradores": [],
                "resumo": {}
            }
        
        necessidade_diaria = self.calcular_necessidade_semanal(parametros, regras)
        
        horas_alocadas_semana = {c.id: 0.0 for c in colaboradores}
        dias_trabalhados_semana = {c.id: 0 for c in colaboradores}
        dias_consecutivos = {c.id: 0 for c in colaboradores}
        ultimo_turno = {c.id: None for c in colaboradores}
        escala_diaria = {}
        escala_por_colaborador = {c.id: [] for c in colaboradores}
        
        turnos_disponiveis = ["manha", "tarde"]
        semana_inicio = parametros.semana_inicio
        
        for idx, dia in enumerate(DIAS_SEMANA):
            data_dia = semana_inicio + timedelta(days=DIAS_OFFSET[dia])
            info_dia = necessidade_diaria[dia]
            horas_necessarias = info_dia["horas_necessarias"]
            tipo_dia = info_dia["tipo_dia"]
            
            alocacoes_dia = []
            horas_restantes = horas_necessarias
            
            for turno_idx, turno in enumerate(turnos_disponiveis):
                if horas_restantes <= 0:
                    break
                
                horas_turno = min(regras.limite_horas_diarias, horas_restantes)
                horas_restantes -= horas_turno
                
                hora_inicio = regras.turno_manha_inicio if turno == "manha" else regras.turno_tarde_inicio
                
                candidatos = self._ordenar_candidatos(
                    colaboradores,
                    horas_alocadas_semana,
                    dias_consecutivos,
                    ultimo_turno,
                    turno,
                    tipo_dia,
                    regras
                )
                
                for colaborador in candidatos:
                    if horas_turno <= 0:
                        break
                    
                    if not self._verificar_folga_semanal(
                        colaborador, dias_trabalhados_semana, regras
                    ):
                        continue
                    
                    horas_disponiveis = self._calcular_horas_disponiveis(
                        colaborador,
                        horas_alocadas_semana[colaborador.id],
                        regras
                    )
                    
                    if horas_disponiveis <= 0:
                        continue
                    
                    if dias_consecutivos[colaborador.id] >= regras.maximo_dias_consecutivos:
                        continue
                    
                    if tipo_dia == "feriado":
                        if not regras.permitir_intermitentes_feriado:
                            if colaborador.contract_type == ContractType.INTERMITTENT:
                                continue
                        if regras.preferir_efetivos_feriado:
                            if colaborador.contract_type == ContractType.INTERMITTENT:
                                tem_efetivo = any(
                                    c.contract_type == ContractType.PERMANENT and
                                    self._calcular_horas_disponiveis(c, horas_alocadas_semana[c.id], regras) > 0
                                    for c in candidatos
                                )
                                if tem_efetivo:
                                    continue
                    
                    horas_alocar = min(horas_turno, horas_disponiveis, regras.limite_horas_diarias)
                    
                    horarios = calcular_horarios_jornada(hora_inicio, horas_alocar, regras)
                    
                    atividade = self._determinar_atividade(colaborador, tipo_dia)
                    
                    alocacao = {
                        "colaborador_id": colaborador.id,
                        "colaborador_nome": colaborador.name,
                        "tipo_contrato": colaborador.contract_type.value,
                        "turno": turno,
                        "dia": NOMES_DIAS[dia],
                        "data": data_dia.isoformat(),
                        "horas": round(horas_alocar, 2),
                        "entrada": horarios["entrada"],
                        "inicio_intervalo": horarios["inicio_intervalo"],
                        "fim_intervalo": horarios["fim_intervalo"],
                        "saida": horarios["saida"],
                        "atividade": atividade,
                        "editavel": True
                    }
                    
                    alocacoes_dia.append(alocacao)
                    escala_por_colaborador[colaborador.id].append(alocacao)
                    
                    horas_alocadas_semana[colaborador.id] += horas_alocar
                    dias_trabalhados_semana[colaborador.id] += 1
                    horas_turno -= horas_alocar
                    ultimo_turno[colaborador.id] = turno
            
            for col_id in dias_consecutivos:
                if any(a["colaborador_id"] == col_id for a in alocacoes_dia):
                    dias_consecutivos[col_id] += 1
                else:
                    dias_consecutivos[col_id] = 0
            
            total_alocado = sum(a["horas"] for a in alocacoes_dia)
            escala_diaria[dia] = {
                "nome_dia": NOMES_DIAS[dia],
                "data": data_dia.isoformat(),
                "tipo_dia": tipo_dia,
                "horas_necessarias": horas_necessarias,
                "horas_alocadas": round(total_alocado, 2),
                "diferenca": round(total_alocado - horas_necessarias, 2),
                "alocacoes": alocacoes_dia
            }
        
        escala_colaboradores = []
        for colaborador in colaboradores:
            if escala_por_colaborador[colaborador.id]:
                escala_colaboradores.append({
                    "colaborador_id": colaborador.id,
                    "colaborador_nome": colaborador.name,
                    "tipo_contrato": colaborador.contract_type.value,
                    "total_horas_semana": round(horas_alocadas_semana[colaborador.id], 2),
                    "dias_trabalhados": dias_trabalhados_semana[colaborador.id],
                    "dias_folga": 7 - dias_trabalhados_semana[colaborador.id],
                    "detalhes": escala_por_colaborador[colaborador.id]
                })
        
        resumo = self._gerar_resumo(colaboradores, horas_alocadas_semana, escala_diaria, regras)
        
        return {
            "semana_inicio": parametros.semana_inicio.isoformat(),
            "escala_diaria": escala_diaria,
            "escala_colaboradores": escala_colaboradores,
            "resumo": resumo,
            "regras_aplicadas": {
                "limite_horas_diarias": regras.limite_horas_diarias,
                "limite_horas_semanais": regras.limite_horas_semanais_sem_extra,
                "intervalo_minimo_entre_turnos": regras.intervalo_minimo_entre_turnos,
                "intervalo_intrajornada": f"{regras.intervalo_intrajornada_minimo}h a {regras.intervalo_intrajornada_maximo}h",
                "regime_preferencial": regras.regime_preferencial,
                "dias_folga_semana": regras.dias_folga_semana,
                "logica_customizada": regras.logica_customizada
            }
        }
    
    def _verificar_folga_semanal(
        self,
        colaborador: Employee,
        dias_trabalhados: Dict[int, int],
        regras: GovernanceRules
    ) -> bool:
        """
        Verifica se o colaborador ainda pode trabalhar respeitando folgas semanais.
        """
        dias_trabalho_permitidos = 7 - regras.dias_folga_semana
        return dias_trabalhados[colaborador.id] < dias_trabalho_permitidos
    
    def _determinar_atividade(self, colaborador: Employee, tipo_dia: str) -> str:
        """
        Determina a atividade do colaborador.
        Futuramente integrar com CBO e atividades cadastradas.
        """
        return "Limpeza de Quartos"
    
    def _ordenar_candidatos(
        self,
        colaboradores: List[Employee],
        horas_alocadas: Dict[int, float],
        dias_consecutivos: Dict[int, int],
        ultimo_turno: Dict[int, Optional[str]],
        turno_atual: str,
        tipo_dia: str,
        regras: GovernanceRules
    ) -> List[Employee]:
        """
        Ordena colaboradores por prioridade para alocação.
        Prioriza quem trabalhou menos e varia turnos conforme configuração.
        """
        def score_colaborador(c):
            score = 0
            
            score += horas_alocadas[c.id] * 10
            
            if tipo_dia == "feriado" and regras.preferir_efetivos_feriado:
                if c.contract_type == ContractType.PERMANENT:
                    score -= 50
            
            if regras.modo_conservador:
                if ultimo_turno[c.id] == turno_atual:
                    score += 20
            
            if regras.alternancia_horarios:
                if ultimo_turno[c.id] == turno_atual:
                    score += 15
            
            score += dias_consecutivos[c.id] * 5
            
            return score
        
        return sorted(colaboradores, key=score_colaborador)
    
    def _calcular_horas_disponiveis(
        self,
        colaborador: Employee,
        horas_ja_alocadas: float,
        regras: GovernanceRules
    ) -> float:
        """Calcula quantas horas ainda podem ser alocadas para um colaborador."""
        max_semanal = min(
            colaborador.carga_horaria_max_semana,
            regras.limite_horas_semanais_sem_extra
        )
        return max(0, max_semanal - horas_ja_alocadas)
    
    def _gerar_resumo(
        self,
        colaboradores: List[Employee],
        horas_alocadas: Dict[int, float],
        escala_diaria: Dict[str, Dict],
        regras: GovernanceRules
    ) -> Dict[str, Any]:
        """Gera resumo da escala para análise."""
        total_necessario = sum(d["horas_necessarias"] for d in escala_diaria.values())
        total_alocado = sum(d["horas_alocadas"] for d in escala_diaria.values())
        
        colaboradores_alocados = [
            {
                "id": c.id,
                "nome": c.name,
                "tipo_contrato": c.contract_type.value,
                "horas_semana": round(horas_alocadas[c.id], 2),
                "max_permitido": c.carga_horaria_max_semana,
                "percentual_utilizado": round(
                    (horas_alocadas[c.id] / c.carga_horaria_max_semana) * 100, 1
                ) if c.carga_horaria_max_semana > 0 else 0
            }
            for c in colaboradores
            if horas_alocadas[c.id] > 0
        ]
        
        intermitentes = [
            c for c in colaboradores_alocados 
            if c["tipo_contrato"] == "intermitente"
        ]
        efetivos = [
            c for c in colaboradores_alocados 
            if c["tipo_contrato"] == "efetivo"
        ]
        
        return {
            "total_horas_necessarias": round(total_necessario, 2),
            "total_horas_alocadas": round(total_alocado, 2),
            "diferenca_total": round(total_alocado - total_necessario, 2),
            "cobertura_percentual": round(
                (total_alocado / total_necessario) * 100, 1
            ) if total_necessario > 0 else 100,
            "colaboradores_alocados": len(colaboradores_alocados),
            "intermitentes_utilizados": len(intermitentes),
            "efetivos_utilizados": len(efetivos),
            "detalhamento_colaboradores": colaboradores_alocados
        }
