from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import date
from sqlalchemy.orm import Session
from sqlalchemy import case, and_, or_

from app.models import SectorRule, TipoRegra, NivelRigidez


@dataclass
class RuleApplication:
    codigo_regra: str
    tipo_regra: TipoRegra
    nivel_rigidez: NivelRigidez
    applied: bool
    reason: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RuleExecutionResult:
    applied_rules: List[RuleApplication] = field(default_factory=list)
    violated_rules: List[RuleApplication] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def add_applied(self, rule: SectorRule, params: Dict[str, Any] = None):
        self.applied_rules.append(RuleApplication(
            codigo_regra=rule.codigo_regra,
            tipo_regra=rule.tipo_regra,
            nivel_rigidez=rule.nivel_rigidez,
            applied=True,
            params=params or {}
        ))

    def add_violated(self, rule: SectorRule, reason: str):
        self.violated_rules.append(RuleApplication(
            codigo_regra=rule.codigo_regra,
            tipo_regra=rule.tipo_regra,
            nivel_rigidez=rule.nivel_rigidez,
            applied=False,
            reason=reason
        ))

    def has_mandatory_violations(self) -> bool:
        return any(r.nivel_rigidez == NivelRigidez.MANDATORY for r in self.violated_rules)

    def to_trace_dict(self) -> Dict[str, Any]:
        return {
            "applied_rules": [r.codigo_regra for r in self.applied_rules],
            "violated_rules": [{"codigo": r.codigo_regra, "motivo": r.reason} for r in self.violated_rules],
            "warnings": self.warnings
        }


@dataclass
class GroupedRules:
    labor: Dict[str, List[SectorRule]] = field(default_factory=dict)
    operational: Dict[str, List[SectorRule]] = field(default_factory=dict)
    calculation: Dict[str, List[SectorRule]] = field(default_factory=dict)

    def all_ordered(self) -> List[SectorRule]:
        result = []
        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            result.extend(self.labor.get(nivel, []))
        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            result.extend(self.operational.get(nivel, []))
        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            result.extend(self.calculation.get(nivel, []))
        return result


class RuleEngine:

    def __init__(self, db: Session):
        self.db = db

    def _get_tipo_order_expr(self):
        return case(
            (SectorRule.tipo_regra == TipoRegra.LABOR, 1),
            (SectorRule.tipo_regra == TipoRegra.OPERATIONAL, 2),
            (SectorRule.tipo_regra == TipoRegra.CALCULATION, 3),
            else_=99
        )

    def _get_rigidez_order_expr(self):
        return case(
            (SectorRule.nivel_rigidez == NivelRigidez.MANDATORY, 1),
            (SectorRule.nivel_rigidez == NivelRigidez.DESIRABLE, 2),
            (SectorRule.nivel_rigidez == NivelRigidez.FLEXIBLE, 3),
            else_=99
        )

    def fetch_rules(
        self,
        sector_id: int,
        reference_date: Optional[date] = None,
        active_only: bool = True
    ) -> GroupedRules:
        if reference_date is None:
            reference_date = date.today()

        query = self.db.query(SectorRule).filter(
            SectorRule.setor_id == sector_id,
            SectorRule.deleted_at.is_(None)
        )

        if active_only:
            query = query.filter(SectorRule.regra_ativa == True)
            query = query.filter(
                or_(
                    SectorRule.validade_inicio.is_(None),
                    SectorRule.validade_inicio <= reference_date
                )
            )
            query = query.filter(
                or_(
                    SectorRule.validade_fim.is_(None),
                    SectorRule.validade_fim >= reference_date
                )
            )

        query = query.order_by(
            self._get_tipo_order_expr(),
            self._get_rigidez_order_expr(),
            SectorRule.prioridade
        )

        rules = query.all()
        grouped = GroupedRules()

        for rule in rules:
            nivel = rule.nivel_rigidez.value
            if rule.tipo_regra == TipoRegra.LABOR:
                if nivel not in grouped.labor:
                    grouped.labor[nivel] = []
                grouped.labor[nivel].append(rule)
            elif rule.tipo_regra == TipoRegra.OPERATIONAL:
                if nivel not in grouped.operational:
                    grouped.operational[nivel] = []
                grouped.operational[nivel].append(rule)
            else:
                if nivel not in grouped.calculation:
                    grouped.calculation[nivel] = []
                grouped.calculation[nivel].append(rule)

        return grouped

    def get_rules_by(
        self,
        sector_id: int,
        tipo_regra: Optional[TipoRegra] = None,
        nivel_rigidez: Optional[NivelRigidez] = None,
        reference_date: Optional[date] = None,
        active_only: bool = True
    ) -> List[SectorRule]:
        if reference_date is None:
            reference_date = date.today()

        query = self.db.query(SectorRule).filter(
            SectorRule.setor_id == sector_id,
            SectorRule.deleted_at.is_(None)
        )

        if tipo_regra:
            query = query.filter(SectorRule.tipo_regra == tipo_regra)
        if nivel_rigidez:
            query = query.filter(SectorRule.nivel_rigidez == nivel_rigidez)

        if active_only:
            query = query.filter(SectorRule.regra_ativa == True)
            query = query.filter(
                or_(
                    SectorRule.validade_inicio.is_(None),
                    SectorRule.validade_inicio <= reference_date
                )
            )
            query = query.filter(
                or_(
                    SectorRule.validade_fim.is_(None),
                    SectorRule.validade_fim >= reference_date
                )
            )

        query = query.order_by(
            self._get_tipo_order_expr(),
            self._get_rigidez_order_expr(),
            SectorRule.prioridade
        )

        return query.all()

    def resolve_param(
        self,
        rule: SectorRule,
        key: str,
        default: Any = None
    ) -> Any:
        if rule.metadados_json and key in rule.metadados_json:
            return rule.metadados_json[key]

        response_lower = rule.resposta.lower().strip()

        if key == "max_hours_weekly":
            if "44" in response_lower:
                return 44
            if "40" in response_lower:
                return 40

        if key == "max_hours_daily":
            if "10" in response_lower:
                return 10
            if "8" in response_lower:
                return 8

        if key == "min_rest_between_shifts":
            if "11" in response_lower:
                return 11
            if "12" in response_lower:
                return 12

        if key == "buffer_pct":
            import re
            match = re.search(r'(\d+)%', rule.resposta)
            if match:
                return int(match.group(1))

        return default

    def resolve_all_params(self, rule: SectorRule) -> Dict[str, Any]:
        params = {}
        if rule.metadados_json:
            params.update(rule.metadados_json)

        known_keys = ["max_hours_weekly", "max_hours_daily", "min_rest_between_shifts", "buffer_pct"]
        for key in known_keys:
            value = self.resolve_param(rule, key, None)
            if value is not None and key not in params:
                params[key] = value

        return params

    def validate_rule_consistency(self, sector_id: int, tipo_regra: TipoRegra) -> Tuple[bool, List[str]]:
        rules = self.get_rules_by(sector_id, tipo_regra=tipo_regra, active_only=True)

        errors = []
        seen_priorities = {}

        for rule in rules:
            nivel = rule.nivel_rigidez.value
            if nivel not in seen_priorities:
                seen_priorities[nivel] = {}

            if rule.prioridade in seen_priorities[nivel]:
                errors.append(
                    f"Prioridade {rule.prioridade} duplicada no nivel {nivel}: "
                    f"{seen_priorities[nivel][rule.prioridade]} e {rule.codigo_regra}"
                )
            else:
                seen_priorities[nivel][rule.prioridade] = rule.codigo_regra

        return len(errors) == 0, errors

    def apply_rules_with_conflict_resolution(
        self,
        sector_id: int,
        context: Dict[str, Any],
        apply_fn: callable,
        reference_date: Optional[date] = None
    ) -> Tuple[Dict[str, Any], RuleExecutionResult]:
        grouped = self.fetch_rules(sector_id, reference_date)
        result = RuleExecutionResult()

        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            labor_rules = grouped.labor.get(nivel, [])
            for rule in labor_rules:
                try:
                    context = apply_fn(rule, context)
                    params = self.resolve_all_params(rule)
                    result.add_applied(rule, params)
                except Exception as e:
                    if nivel == "MANDATORY":
                        result.add_violated(rule, str(e))
                    else:
                        result.warnings.append(f"Regra {rule.codigo_regra} nao aplicada: {str(e)}")

        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            op_rules = grouped.operational.get(nivel, [])
            for rule in op_rules:
                try:
                    context = apply_fn(rule, context)
                    params = self.resolve_all_params(rule)
                    result.add_applied(rule, params)
                except Exception as e:
                    if nivel == "MANDATORY":
                        result.add_violated(rule, str(e))
                    else:
                        result.warnings.append(f"Regra {rule.codigo_regra} nao aplicada: {str(e)}")

        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            calc_rules = grouped.calculation.get(nivel, [])
            for rule in calc_rules:
                try:
                    context = apply_fn(rule, context)
                    params = self.resolve_all_params(rule)
                    result.add_applied(rule, params)
                except Exception as e:
                    if nivel == "MANDATORY":
                        result.add_violated(rule, str(e))
                    else:
                        result.warnings.append(f"Regra {rule.codigo_regra} nao aplicada: {str(e)}")

        return context, result

    def get_labor_constraints(self, sector_id: int) -> Dict[str, Any]:
        labor_rules = self.get_rules_by(sector_id, tipo_regra=TipoRegra.LABOR)

        constraints = {
            "max_hours_weekly": 44,
            "max_hours_daily": 10,
            "min_rest_between_shifts": 11,
            "advance_notice_hours": 72
        }

        for rule in labor_rules:
            params = self.resolve_all_params(rule)
            for key, value in params.items():
                if key in constraints and value is not None:
                    constraints[key] = value

        return constraints

    def get_all_constraints(self, sector_id: int) -> Tuple[Dict[str, Any], List[str]]:
        grouped = self.fetch_rules(sector_id)
        applied_rules = []

        constraints = {
            "max_hours_weekly": 44,
            "max_hours_daily": 10,
            "min_rest_between_shifts": 11,
            "advance_notice_hours": 72,
            "utilization_target_pct": 85.0,
            "buffer_pct": 10.0,
            "fator_feriado": 1.1,
            "fator_vespera_feriado": 1.05,
            "fator_pico": 1.2,
            "fator_baixa_ocupacao": 0.9
        }

        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            for rule in grouped.labor.get(nivel, []):
                params = self.resolve_all_params(rule)
                for key, value in params.items():
                    if key in constraints and value is not None:
                        constraints[key] = value
                        applied_rules.append(rule.codigo_regra)

        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            for rule in grouped.operational.get(nivel, []):
                params = self.resolve_all_params(rule)
                for key, value in params.items():
                    if value is not None:
                        constraints[key] = value
                        applied_rules.append(rule.codigo_regra)

        for nivel in ["MANDATORY", "DESIRABLE", "FLEXIBLE"]:
            for rule in grouped.calculation.get(nivel, []):
                params = self.resolve_all_params(rule)
                for key, value in params.items():
                    if value is not None:
                        constraints[key] = value
                        applied_rules.append(rule.codigo_regra)

        return constraints, list(set(applied_rules))

    def create_trace_for_service(
        self,
        sector_id: int,
        step_key: str,
        calculations: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        constraints, applied_rules = self.get_all_constraints(sector_id)

        return {
            "step_key": step_key,
            "applied_rules": applied_rules,
            "calculations": calculations or {},
            "constraints_snapshot": constraints,
            "constraints_violated": []
        }

    def validate_against_constraints(
        self,
        sector_id: int,
        values: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        constraints, _ = self.get_all_constraints(sector_id)
        violations = []

        if "hours_weekly" in values and values["hours_weekly"] > constraints.get("max_hours_weekly", 44):
            violations.append({
                "constraint": "max_hours_weekly",
                "limit": constraints.get("max_hours_weekly", 44),
                "actual": values["hours_weekly"],
                "message": f"Limite semanal de {constraints.get('max_hours_weekly', 44)}h excedido"
            })

        if "hours_daily" in values and values["hours_daily"] > constraints.get("max_hours_daily", 10):
            violations.append({
                "constraint": "max_hours_daily",
                "limit": constraints.get("max_hours_daily", 10),
                "actual": values["hours_daily"],
                "message": f"Limite diario de {constraints.get('max_hours_daily', 10)}h excedido"
            })

        if "rest_hours" in values and values["rest_hours"] < constraints.get("min_rest_between_shifts", 11):
            violations.append({
                "constraint": "min_rest_between_shifts",
                "limit": constraints.get("min_rest_between_shifts", 11),
                "actual": values["rest_hours"],
                "message": f"Descanso minimo de {constraints.get('min_rest_between_shifts', 11)}h nao respeitado"
            })

        return violations
