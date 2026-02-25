"""
ExplainService - Serviço de Explicação de Cálculos
===================================================
Transforma AgentTraceStep em explicações legíveis para humanos.

Versão: 1.0.0
"""

from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from datetime import date

from app.models.agent_run import AgentRun, AgentTraceStep, RunType

METHOD_VERSION = "1.0.0"

STEP_DESCRIPTIONS = {
    "LOAD_SLOTS": "Carregamento de turnos atribuídos",
    "LOAD_RULES": "Carregamento de regras do setor",
    "LOAD_ACTIVITIES": "Carregamento de atividades programadas",
    "LOAD_CONSTRAINTS": "Carregamento de restrições legais",
    "FILTER_ELIGIBLE": "Filtragem de colaboradores elegíveis",
    "ASSIGNMENT": "Alocação de colaboradores",
    "ASSIGN_ACTIVITY": "Atribuição de atividade",
    "ASSIGN_PENDING": "Atribuição de atividade pendente",
    "GENERATE_DAY": "Geração de agenda diária",
    "CALCULATE_DEMAND": "Cálculo de demanda",
    "APPLY_RULES": "Aplicação de regras",
    "VALIDATE_LEGAL": "Validação legal",
    "GENERATE_SCHEDULE": "Geração de escala"
}

RUN_TYPE_LABELS = {
    "FORECAST": "Previsão de Ocupação",
    "DEMAND": "Cálculo de Demanda",
    "SCHEDULE": "Geração de Escala",
    "CONVOCATIONS": "Geração de Convocações",
    "FULL_PIPELINE": "Pipeline Completo"
}


class ExplainService:
    """
    Serviço para gerar explicações legíveis dos cálculos do agente.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def explain_trace(self, agent_run: AgentRun) -> Dict[str, Any]:
        """
        Gera explicação completa a partir de um AgentRun.
        
        Returns:
            {
                "text": str,
                "math": List[Dict],
                "rules_applied": List[Dict],
                "rules_violated": List[Dict],
                "timeline": List[Dict]
            }
        """
        if not agent_run or not agent_run.trace_steps:
            return self._empty_explanation()
        
        text = self._generate_text_explanation(agent_run)
        math = self._extract_math_calculations(agent_run.trace_steps)
        rules_applied = self._extract_applied_rules(agent_run.trace_steps)
        rules_violated = self._extract_violated_rules(agent_run.trace_steps)
        timeline = self._build_timeline(agent_run.trace_steps)
        
        return {
            "text": text,
            "math": math,
            "rules_applied": rules_applied,
            "rules_violated": rules_violated,
            "timeline": timeline
        }
    
    def explain_from_run_id(self, run_id: int) -> Dict[str, Any]:
        """Gera explicação a partir do ID da execução."""
        agent_run = self.db.query(AgentRun).filter(AgentRun.id == run_id).first()
        if not agent_run:
            return self._empty_explanation()
        return self.explain_trace(agent_run)
    
    def explain_latest(
        self,
        sector_id: int,
        week_start: date,
        run_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Busca e explica a execução mais recente."""
        query = self.db.query(AgentRun).filter(
            AgentRun.setor_id == sector_id,
            AgentRun.week_start == week_start
        )
        
        if run_type:
            query = query.filter(AgentRun.run_type == run_type)
        
        agent_run = query.order_by(AgentRun.created_at.desc()).first()
        
        if not agent_run:
            return self._empty_explanation()
        
        return self.explain_trace(agent_run)
    
    def _empty_explanation(self) -> Dict[str, Any]:
        """Retorna explicação vazia quando não há dados."""
        return {
            "text": "Nenhuma memória de cálculo disponível para esta execução.",
            "math": [],
            "rules_applied": [],
            "rules_violated": [],
            "timeline": []
        }
    
    def _generate_text_explanation(self, agent_run: AgentRun) -> str:
        """Gera texto explicativo em português."""
        run_type_label = RUN_TYPE_LABELS.get(
            agent_run.run_type.value if agent_run.run_type else "",
            "Execução"
        )
        
        lines = [
            f"**{run_type_label}**",
            f"Semana: {agent_run.week_start.strftime('%d/%m/%Y') if agent_run.week_start else 'N/A'}",
            ""
        ]
        
        if agent_run.inputs_snapshot:
            inputs = agent_run.inputs_snapshot
            if "method_version" in inputs:
                lines.append(f"Versão do método: {inputs['method_version']}")
            if "schedule_plan_id" in inputs:
                lines.append(f"Plano de escala: #{inputs['schedule_plan_id']}")
        
        lines.append("")
        
        steps_count = len(agent_run.trace_steps)
        lines.append(f"**Passos executados:** {steps_count}")
        
        if agent_run.outputs_summary:
            outputs = agent_run.outputs_summary
            if "agendas_geradas" in outputs:
                lines.append(f"Agendas geradas: {outputs['agendas_geradas']}")
            if "conflitos" in outputs:
                lines.append(f"Conflitos identificados: {outputs['conflitos']}")
            if "pendencias" in outputs:
                lines.append(f"Pendências: {outputs['pendencias']}")
        
        all_violated = []
        for step in agent_run.trace_steps:
            if step.constraints_violated:
                all_violated.extend(step.constraints_violated)
        
        if all_violated:
            lines.append("")
            lines.append(f"**Restrições violadas:** {len(all_violated)}")
        
        return "\n".join(lines)
    
    def _extract_math_calculations(self, trace_steps: List[AgentTraceStep]) -> List[Dict]:
        """Extrai cálculos numéricos dos passos."""
        math_items = []
        
        for step in trace_steps:
            if not step.calculations:
                continue
            
            calc = step.calculations
            step_key = step.step_key
            
            if step_key == "GENERATE_DAY":
                math_items.append({
                    "label": f"Dia {calc.get('date', 'N/A')}",
                    "items": [
                        {"key": "Colaboradores", "value": calc.get("employees", 0)},
                        {"key": "Demanda total (min)", "value": calc.get("total_demand", 0)},
                        {"key": "Capacidade total (min)", "value": calc.get("total_capacity", 0)},
                        {"key": "Atividades distribuídas", "value": calc.get("activities_distributed", 0)},
                        {"key": "Eventuais pendentes", "value": calc.get("eventual_pending", 0)}
                    ]
                })
            
            elif step_key == "LOAD_SLOTS":
                math_items.append({
                    "label": "Slots Carregados",
                    "items": [
                        {"key": "Total de slots", "value": calc.get("total_slots", 0)},
                        {"key": "Dias cobertos", "value": calc.get("days_covered", 0)}
                    ]
                })
            
            elif step_key == "LOAD_ACTIVITIES":
                math_items.append({
                    "label": "Atividades por Tipo",
                    "items": [
                        {"key": "Calculadas pelo agente", "value": calc.get("calculadas", 0)},
                        {"key": "Recorrentes", "value": calc.get("recorrentes", 0)},
                        {"key": "Eventuais", "value": calc.get("eventuais", 0)}
                    ]
                })
            
            elif step_key == "LOAD_RULES":
                math_items.append({
                    "label": "Regras Carregadas",
                    "items": [
                        {"key": "Regras de cálculo", "value": calc.get("calculation_rules", 0)},
                        {"key": "Regras operacionais", "value": calc.get("operational_rules", 0)}
                    ]
                })
            
            elif step_key == "ASSIGN_ACTIVITY":
                pass
        
        return math_items
    
    def _extract_applied_rules(self, trace_steps: List[AgentTraceStep]) -> List[Dict]:
        """Extrai regras aplicadas em ordem."""
        all_rules = []
        seen_codes = set()
        
        for step in trace_steps:
            if not step.applied_rules:
                continue
            
            for rule in step.applied_rules:
                if isinstance(rule, dict):
                    code = rule.get("codigo", "")
                    if code and code not in seen_codes:
                        seen_codes.add(code)
                        all_rules.append({
                            "codigo": code,
                            "tipo": rule.get("tipo", "N/A"),
                            "nivel": rule.get("nivel", "N/A"),
                            "step": step.step_key,
                            "order": len(all_rules) + 1
                        })
                elif isinstance(rule, str):
                    if rule not in seen_codes:
                        seen_codes.add(rule)
                        all_rules.append({
                            "codigo": rule,
                            "tipo": "N/A",
                            "nivel": "N/A",
                            "step": step.step_key,
                            "order": len(all_rules) + 1
                        })
        
        return all_rules
    
    def _extract_violated_rules(self, trace_steps: List[AgentTraceStep]) -> List[Dict]:
        """Extrai regras violadas com justificativas."""
        violations = []
        
        for step in trace_steps:
            if not step.constraints_violated:
                continue
            
            for violation in step.constraints_violated:
                if isinstance(violation, dict):
                    violations.append({
                        "regra": violation.get("rule", violation.get("regra", "Desconhecida")),
                        "motivo": violation.get("reason", violation.get("motivo", "Não especificado")),
                        "step": step.step_key,
                        "dados": violation.get("data", {})
                    })
                elif isinstance(violation, str):
                    violations.append({
                        "regra": violation,
                        "motivo": "Restrição violada",
                        "step": step.step_key,
                        "dados": {}
                    })
        
        return violations
    
    def _build_timeline(self, trace_steps: List[AgentTraceStep]) -> List[Dict]:
        """Constrói timeline dos passos."""
        timeline = []
        
        for step in trace_steps:
            step_desc = STEP_DESCRIPTIONS.get(step.step_key, step.step_key)
            
            calc = step.calculations or {}
            summary = ""
            
            if step.step_key == "ASSIGN_ACTIVITY":
                summary = f"Atividade: {calc.get('activity', 'N/A')}, {calc.get('minutes', 0)} min"
            elif step.step_key == "GENERATE_DAY":
                summary = f"{calc.get('employees', 0)} colaboradores, {calc.get('total_demand', 0)} min demanda"
            elif step.step_key == "LOAD_SLOTS":
                summary = f"{calc.get('total_slots', 0)} slots em {calc.get('days_covered', 0)} dias"
            elif step.step_key == "LOAD_RULES":
                summary = f"{calc.get('calculation_rules', 0) + calc.get('operational_rules', 0)} regras"
            elif step.step_key == "LOAD_ACTIVITIES":
                total = calc.get("calculadas", 0) + calc.get("recorrentes", 0) + calc.get("eventuais", 0)
                summary = f"{total} atividades"
            
            timeline.append({
                "order": step.step_order,
                "key": step.step_key,
                "description": step_desc,
                "summary": summary,
                "has_violations": bool(step.constraints_violated),
                "timestamp": step.created_at.isoformat() if step.created_at else None
            })
        
        return timeline
    
    def create_explanation_response(
        self,
        data: Any,
        agent_run_id: Optional[int] = None,
        trace_steps: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Cria resposta com dados + explicação.
        Usado pelos endpoints para incluir explanation.
        """
        explanation = self._empty_explanation()
        
        if agent_run_id:
            explanation = self.explain_from_run_id(agent_run_id)
        elif trace_steps:
            explanation = self._explain_from_raw_trace(trace_steps)
        
        return {
            "data": data,
            "explanation": explanation
        }
    
    def _explain_from_raw_trace(self, trace_steps: List[Dict]) -> Dict[str, Any]:
        """Gera explicação a partir de trace bruto (sem AgentRun)."""
        if not trace_steps:
            return self._empty_explanation()
        
        text_lines = [
            "**Resumo da Execução**",
            f"Passos executados: {len(trace_steps)}",
            ""
        ]
        
        math = []
        rules_applied = []
        rules_violated = []
        timeline = []
        
        seen_rules = set()
        
        for i, step in enumerate(trace_steps):
            step_key = step.get("step", "UNKNOWN")
            step_desc = STEP_DESCRIPTIONS.get(step_key, step_key)
            
            summary = ""
            if step_key == "ASSIGN_ACTIVITY":
                summary = f"Atividade: {step.get('activity', 'N/A')}, {step.get('minutes', 0)} min"
            elif step_key == "GENERATE_DAY":
                summary = f"{step.get('employees', 0)} colaboradores"
                math.append({
                    "label": f"Dia {step.get('date', 'N/A')}",
                    "items": [
                        {"key": "Demanda (min)", "value": step.get("total_demand", 0)},
                        {"key": "Capacidade (min)", "value": step.get("total_capacity", 0)}
                    ]
                })
            elif step_key == "LOAD_SLOTS":
                summary = f"{step.get('total_slots', 0)} slots"
            
            timeline.append({
                "order": i + 1,
                "key": step_key,
                "description": step_desc,
                "summary": summary,
                "has_violations": False,
                "timestamp": None
            })
        
        return {
            "text": "\n".join(text_lines),
            "math": math,
            "rules_applied": rules_applied,
            "rules_violated": rules_violated,
            "timeline": timeline
        }
