from datetime import date, timedelta
from dateutil.relativedelta import relativedelta
from typing import Union
from app.models.activity_periodicity import IntervalUnit, AnchorPolicy


def add_interval(
    base_date: date,
    unit: Union[IntervalUnit, str],
    value: int,
    anchor_policy: Union[AnchorPolicy, str] = AnchorPolicy.SAME_DAY
) -> date:
    """
    Adiciona um intervalo a uma data base, respeitando a politica de ancoragem.
    
    Args:
        base_date: Data base para o calculo
        unit: Unidade do intervalo (DAYS, MONTHS, YEARS)
        value: Valor do intervalo (ex: 3 para trimestral)
        anchor_policy: Politica para tratar datas invalidas
            - SAME_DAY: Mantém o mesmo dia do mês (padrão do relativedelta)
            - LAST_DAY_IF_MISSING: Se o dia não existir, usa último dia do mês
    
    Returns:
        Data calculada após adicionar o intervalo
    
    Examples:
        >>> add_interval(date(2026, 1, 31), IntervalUnit.MONTHS, 1)
        date(2026, 2, 28)  # Fev não tem 31, usa 28
        
        >>> add_interval(date(2024, 2, 29), IntervalUnit.YEARS, 1)
        date(2025, 2, 28)  # 2025 não é bissexto
    """
    if isinstance(unit, str):
        unit = IntervalUnit(unit)
    if isinstance(anchor_policy, str):
        anchor_policy = AnchorPolicy(anchor_policy)
    
    if unit == IntervalUnit.DAYS:
        return base_date + timedelta(days=value)
    
    elif unit == IntervalUnit.MONTHS:
        result = base_date + relativedelta(months=value)
        if anchor_policy == AnchorPolicy.LAST_DAY_IF_MISSING:
            target_day = base_date.day
            if result.day < target_day:
                import calendar
                _, last_day = calendar.monthrange(result.year, result.month)
                result = result.replace(day=last_day)
        return result
    
    elif unit == IntervalUnit.YEARS:
        result = base_date + relativedelta(years=value)
        if anchor_policy == AnchorPolicy.LAST_DAY_IF_MISSING:
            target_day = base_date.day
            if result.day < target_day:
                import calendar
                _, last_day = calendar.monthrange(result.year, result.month)
                result = result.replace(day=last_day)
        return result
    
    raise ValueError(f"Unidade de intervalo desconhecida: {unit}")


def calculate_approximate_days(unit: Union[IntervalUnit, str], value: int) -> int:
    """
    Calcula o numero aproximado de dias para um intervalo.
    Usado para retrocompatibilidade com o campo intervalo_dias.
    
    Args:
        unit: Unidade do intervalo
        value: Valor do intervalo
    
    Returns:
        Numero aproximado de dias
    """
    if isinstance(unit, str):
        unit = IntervalUnit(unit)
    
    if unit == IntervalUnit.DAYS:
        return value
    elif unit == IntervalUnit.MONTHS:
        return value * 30
    elif unit == IntervalUnit.YEARS:
        return value * 365
    
    return value


def get_interval_display_text(unit: Union[IntervalUnit, str], value: int) -> str:
    """
    Retorna texto de exibição para o intervalo.
    
    Examples:
        >>> get_interval_display_text(IntervalUnit.DAYS, 7)
        "A cada 7 dias"
        >>> get_interval_display_text(IntervalUnit.MONTHS, 3)
        "A cada 3 meses (trimestral)"
    """
    if isinstance(unit, str):
        unit = IntervalUnit(unit)
    
    if unit == IntervalUnit.DAYS:
        if value == 1:
            return "Diariamente"
        elif value == 7:
            return "Semanalmente"
        elif value == 14:
            return "Quinzenalmente"
        return f"A cada {value} dias"
    
    elif unit == IntervalUnit.MONTHS:
        if value == 1:
            return "Mensalmente"
        elif value == 3:
            return "Trimestralmente"
        elif value == 6:
            return "Semestralmente"
        return f"A cada {value} meses"
    
    elif unit == IntervalUnit.YEARS:
        if value == 1:
            return "Anualmente"
        return f"A cada {value} anos"
    
    return f"A cada {value}"
