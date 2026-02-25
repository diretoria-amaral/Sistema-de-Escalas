"""
Serviço para construir metadados automaticamente a partir de pergunta e resposta.
Usa heurísticas simples (sem IA externa) para extrair informações estruturadas.
"""
import re
from typing import Dict, Any, List


def build_metadata(question: str, answer: str) -> Dict[str, Any]:
    """
    Constrói metadados estruturados a partir da pergunta e resposta.
    
    Returns:
        Dict com extracted_keys, inferred_params, tags, notes
    """
    q_lower = question.lower()
    a_lower = answer.lower()
    combined = f"{q_lower} {a_lower}"
    
    extracted_keys: List[str] = []
    inferred_params: Dict[str, Any] = {}
    tags: List[str] = []
    notes: str = ""
    
    # Detectar dias da semana
    weekdays_map = {
        "segunda-feira": "MON",
        "segunda": "MON",
        "terça-feira": "TUE",
        "terça": "TUE",
        "quarta-feira": "WED",
        "quarta": "WED",
        "quinta-feira": "THU",
        "quinta": "THU",
        "sexta-feira": "FRI",
        "sexta": "FRI",
        "sábado": "SAT",
        "sabado": "SAT",
        "domingo": "SUN",
    }
    
    detected_days = []
    for day_pt, day_code in weekdays_map.items():
        if day_pt in combined:
            detected_days.append(day_code)
            extracted_keys.append(f"weekday_{day_code.lower()}")
    
    if detected_days:
        inferred_params["weekdays"] = list(set(detected_days))
        if len(detected_days) == 7 or "segunda-feira a domingo" in combined or "todos os dias" in combined:
            inferred_params["week_period"] = "MON_SUN"
            tags.append("full_week")
        elif "FRI" in detected_days:
            inferred_params["planning_day"] = "FRIDAY"
            tags.append("friday_planning")
    
    # Detectar horas
    hours_patterns = [
        (r"(\d+)\s*horas?\s*semanais?", "weekly_hours"),
        (r"(\d+)\s*horas?\s*diárias?", "daily_hours"),
        (r"(\d+)\s*horas?\s*de\s*descanso", "rest_hours"),
        (r"máximo\s*de\s*(\d+)\s*horas?", "max_hours"),
        (r"mínimo\s*de\s*(\d+)\s*horas?", "min_hours"),
        (r"(\d+)h", "hours_mentioned"),
    ]
    
    for pattern, key in hours_patterns:
        match = re.search(pattern, combined)
        if match:
            inferred_params[key] = int(match.group(1))
            extracted_keys.append(key)
    
    # Detectar percentuais
    pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", combined)
    if pct_match:
        inferred_params["percentage"] = float(pct_match.group(1))
        extracted_keys.append("percentage")
    
    # Detectar limites numéricos
    limit_patterns = [
        (r"limite\s*(?:máximo\s*)?(?:de\s*)?(\d+)", "limit_value"),
        (r"até\s*(\d+)", "max_value"),
        (r"no\s*máximo\s*(\d+)", "max_value"),
        (r"pelo\s*menos\s*(\d+)", "min_value"),
        (r"mínimo\s*(?:de\s*)?(\d+)", "min_value"),
    ]
    
    for pattern, key in limit_patterns:
        match = re.search(pattern, combined)
        if match:
            inferred_params[key] = int(match.group(1))
            extracted_keys.append(key)
    
    # Detectar keywords de domínio
    domain_keywords = {
        "alternância": ("rotation_required", True, "rotation"),
        "rodízio": ("rotation_required", True, "rotation"),
        "rotação": ("rotation_required", True, "rotation"),
        "folga": ("rest_related", True, "rest"),
        "descanso": ("rest_related", True, "rest"),
        "intervalo": ("break_related", True, "break"),
        "almoço": ("lunch_break", True, "lunch"),
        "turno": ("shift_related", True, "shift"),
        "jornada": ("workday_related", True, "workday"),
        "hora extra": ("overtime_related", True, "overtime"),
        "extra": ("overtime_related", True, "overtime"),
        "clt": ("clt_compliance", True, "labor_law"),
        "trabalhista": ("labor_law", True, "labor_law"),
        "limpeza": ("cleaning_related", True, "cleaning"),
        "governança": ("housekeeping", True, "housekeeping"),
        "ocupação": ("occupancy_related", True, "occupancy"),
        "convocação": ("convocation_related", True, "convocation"),
        "antecedência": ("advance_notice", True, "notice"),
        "72 horas": ("notice_72h", True, "notice"),
        "intermitente": ("intermittent_worker", True, "worker_type"),
    }
    
    for keyword, (param_key, param_value, tag) in domain_keywords.items():
        if keyword in combined:
            inferred_params[param_key] = param_value
            if tag not in tags:
                tags.append(tag)
            extracted_keys.append(param_key)
    
    # Detectar escopo
    if "global" in combined or "todos os setores" in combined:
        inferred_params["scope"] = "global"
        tags.append("global_scope")
    elif "setor" in combined:
        inferred_params["scope"] = "sector"
        tags.append("sector_scope")
    
    # Detectar prioridade/criticidade
    if any(w in combined for w in ["obrigatório", "obrigatória", "deve", "sempre", "nunca"]):
        inferred_params["is_mandatory"] = True
        tags.append("mandatory")
    if any(w in combined for w in ["preferencialmente", "idealmente", "recomendado"]):
        inferred_params["is_preference"] = True
        tags.append("preference")
    
    # Remover duplicatas
    extracted_keys = list(set(extracted_keys))
    tags = list(set(tags))
    
    # Gerar nota resumida
    if tags:
        notes = f"Regra relacionada a: {', '.join(tags[:5])}"
    
    return {
        "extracted_keys": extracted_keys,
        "inferred_params": inferred_params,
        "tags": tags,
        "notes": notes,
        "auto_generated": True,
        "version": "1.0.0"
    }


def generate_codigo_from_title(title: str, tipo_regra: str, existing_codes: List[str] = None) -> str:
    """
    Gera um codigo_regra a partir do título.
    Formato: {PREFIXO}-{NUMERO}
    """
    prefix_map = {
        "LABOR": "LAB",
        "OPERATIONAL": "OPE",
        "CALCULATION": "CAL"
    }
    prefix = prefix_map.get(tipo_regra, "RUL")
    
    if existing_codes:
        existing_nums = []
        for code in existing_codes:
            if code.startswith(prefix + "-"):
                try:
                    num = int(code.split("-")[1])
                    existing_nums.append(num)
                except (ValueError, IndexError):
                    pass
        next_num = max(existing_nums, default=0) + 1
    else:
        next_num = 1
    
    return f"{prefix}-{next_num:03d}"
