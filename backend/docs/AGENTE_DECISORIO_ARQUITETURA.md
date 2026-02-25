# Agente Decisorio de Escalas - Arquitetura

## Visao Geral

O sistema de escalas da governanca opera como um **Agente Decisorio** com quatro nucleos de inteligencia independentes e encadeados. O agente nunca gera escalas automaticamente - sempre produz **sugestoes** que requerem aprovacao humana.

## Arquitetura de Nucleos

```
┌─────────────────────────────────────────────────────────────────┐
│                    AGENTE DECISORIO                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐    ┌─────────────────┐                    │
│  │  1. DEMANDA     │───>│  2. CAPACIDADE  │                    │
│  │  Intelligence   │    │  Intelligence   │                    │
│  └────────┬────────┘    └────────┬────────┘                    │
│           │                      │                              │
│           v                      v                              │
│  ┌─────────────────────────────────────────┐                   │
│  │         3. ESCALONAMENTO                │                   │
│  │         Intelligence                    │                   │
│  └────────────────────┬────────────────────┘                   │
│                       │                                         │
│                       v                                         │
│  ┌─────────────────────────────────────────┐                   │
│  │         4. GOVERNANCA                   │                   │
│  │         Intelligence                    │                   │
│  │  - Memoria de Calculo                   │                   │
│  │  - Aprovacao/Contestacao                │                   │
│  └─────────────────────────────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Fluxo Obrigatorio

```
Forecast Run (simulacao apenas)
         │
         v
Planejamento Semanal (consolida dados)
         │
         v
Governanca (orquestrador central)
         │
         v
Escala Sugestiva + Memoria de Calculo
         │
         v
Aprovacao/Contestacao pelo Usuario
         │
         v
Convocacoes (somente apos aprovacao)
```

---

## Nucleo 1: Inteligencia de Demanda

### Responsabilidades
- Consumir HP diario (mes corrente + proximo)
- Diferenciar dados historicos (realizados) vs futuros (previsoes)
- Aplicar estatistica historica de variacao
- Incorporar margem de seguranca definida nas regras do setor
- Calcular demanda total semanal em minutos

### Componentes da Demanda
1. **Limpeza Variavel** - baseada em ocupacao (LVS, LET)
2. **Atividades Unitarias Programadas** - tempo fixo por unidade
3. **Atividades Recorrentes** - diarias, semanais, quinzenais, mensais
4. **Atividades Eventuais** - input obrigatorio do usuario

### Servico Principal
`DemandIntelligenceService`

### Saida (DemandIntelligenceOutput)
```python
{
    "sector_id": int,
    "week_start": date,
    "week_end": date,
    "daily_demands": [
        {
            "date": date,
            "weekday": str,
            "hp_source": "HISTORICO" | "PREVISAO",
            "occupancy_pct": float,
            "occupancy_rooms": int,
            "departures": int,
            "arrivals": int,
            "stayovers": int,
            "minutes_variable": float,
            "minutes_constant": float,
            "minutes_recurrent": float,
            "minutes_eventual": float,
            "minutes_raw": float,
            "minutes_with_variance": float,
            "minutes_with_safety": float,
            "variance_applied": float,
            "safety_margin_applied": float
        }
    ],
    "weekly_totals": {
        "minutes_variable": float,
        "minutes_constant": float,
        "minutes_recurrent": float,
        "minutes_eventual": float,
        "minutes_total": float,
        "hours_total": float
    },
    "rules_applied": [...],
    "data_sources": [...]
}
```

---

## Nucleo 2: Inteligencia de Capacidade

### Responsabilidades
- Considerar quadro de colaboradores fixos e intermitentes
- Aplicar regras trabalhistas e operacionais
- Calcular horas disponiveis por colaborador
- Aplicar percentual maximo de utilizacao definido pelo setor

### Classificacao de Colaboradores
- **Fixos**: contrato CLT padrao, horas definidas
- **Intermitentes**: convocacao sob demanda, regras especificas

### Servico Principal
`CapacityIntelligenceService`

### Saida (CapacityIntelligenceOutput)
```python
{
    "sector_id": int,
    "week_start": date,
    "week_end": date,
    "employees": [
        {
            "employee_id": int,
            "name": str,
            "type": "FIXO" | "INTERMITENTE",
            "weekly_hours_max": float,
            "weekly_hours_available": float,
            "daily_availability": {
                "SEG": {"available": bool, "hours": float},
                ...
            },
            "restrictions": [...]
        }
    ],
    "capacity_summary": {
        "total_employees": int,
        "fixed_count": int,
        "intermittent_count": int,
        "total_hours_available": float,
        "max_utilization_pct": float,
        "effective_hours": float
    },
    "labor_rules_applied": [...]
}
```

---

## Nucleo 3: Inteligencia de Escalonamento

### Responsabilidades
- Utilizar estatistica horaria de check-ins e check-outs
- Aplicar regras de tolerancia operacional
- Projetar liberacao de UHs por hora
- Definir turnos ideais (entrada, intervalo, saida)
- Alternar horarios e folgas entre colaboradores
- Garantir equilibrio de horas trabalhadas
- Respeitar minimos e maximos semanais

### Regras de Tolerancia
- Check-ins entre 12h e 6h → atribuir a data do primeiro dia
- Check-outs entre 18h e 14h → atribuir a data do primeiro dia

### Servico Principal
`SchedulingIntelligenceService`

### Saida (SchedulingIntelligenceOutput)
```python
{
    "sector_id": int,
    "week_start": date,
    "schedule_entries": [
        {
            "date": date,
            "weekday": str,
            "employee_id": int,
            "employee_name": str,
            "shift_start": time,
            "break_start": time,
            "break_end": time,
            "shift_end": time,
            "hours_worked": float,
            "activities": [...],
            "is_off_day": bool
        }
    ],
    "hourly_coverage": {
        "date": {
            "06:00": {"employees": int, "capacity_minutes": float},
            ...
        }
    },
    "balance_metrics": {
        "employee_hours": {...},
        "standard_deviation": float,
        "balance_score": float
    }
}
```

---

## Nucleo 4: Inteligencia de Governanca

### Responsabilidades
- Gerar escala semanal SUGESTIVA (nunca automatica)
- Exibir memoria de calculo completa
- Indicar hierarquia de regras aplicadas
- Indicar regras nao atendidas (com motivo)
- Permitir ciclo de analise e contestacao
- Recalcular escala apos alteracoes
- Bloquear aprovacao se regras criticas violadas

### Workflow de Aprovacao
1. **DRAFT** - Escala gerada, aguardando revisao
2. **UNDER_REVIEW** - Usuario analisando
3. **CONTESTED** - Usuario solicitou alteracoes
4. **RECALCULATING** - Sistema processando alteracoes
5. **APPROVED** - Aprovada, pode gerar convocacoes
6. **BLOCKED** - Regras criticas violadas

### Servico Principal
`GovernanceIntelligenceService`

### Saida (GovernanceIntelligenceOutput)
```python
{
    "schedule_id": int,
    "sector_id": int,
    "week_start": date,
    "status": "DRAFT" | "UNDER_REVIEW" | "CONTESTED" | "APPROVED" | "BLOCKED",
    "calculation_memory": {
        "demand_intelligence": {...},
        "capacity_intelligence": {...},
        "scheduling_intelligence": {...},
        "execution_timestamp": datetime,
        "version": int
    },
    "rules_hierarchy": [
        {
            "priority": int,
            "rule_name": str,
            "rule_type": "LABOR" | "OPERATIONAL" | "SECTOR",
            "status": "APPLIED" | "VIOLATED" | "SKIPPED",
            "impact": str,
            "is_critical": bool
        }
    ],
    "unmet_rules": [...],
    "can_approve": bool,
    "blocking_reasons": [...],
    "contestation_history": [...],
    "approved_by": str,
    "approved_at": datetime
}
```

---

## Integracao com Servicos Existentes

### Servicos Reutilizados
| Servico Existente | Nucleo | Uso |
|-------------------|--------|-----|
| `GovernanceDemandService` | Demanda | Base do calculo de demanda |
| `GovernanceForecastService` | Demanda | Geracao de forecast |
| `StatsCalculator` | Demanda/Escalonamento | Estatisticas de vies e horarias |
| `ScheduleGenerator` | Escalonamento | Geracao de escalas |
| `regra_calculo_service` | Todos | Execucao segura de regras |
| `activity_program_service` | Demanda | Programacao de atividades |

### Novos Servicos
| Servico | Nucleo | Responsabilidade |
|---------|--------|------------------|
| `DemandIntelligenceService` | 1 | Orquestrador de demanda |
| `CapacityIntelligenceService` | 2 | Calculo de capacidade |
| `SchedulingIntelligenceService` | 3 | Otimizacao de escalas |
| `GovernanceIntelligenceService` | 4 | Orquestrador central |
| `DecisionAgentOrchestrator` | Central | Pipeline completo |

---

## Modelos de Dados Novos

### ScheduleApproval
- Armazena estado de aprovacao de escalas
- Historico de contestacoes
- Memoria de calculo

### CalculationMemory
- Snapshot de todos os inputs e outputs
- Regras aplicadas com hierarquia
- Versao do calculo

### CapacitySnapshot
- Foto da capacidade por semana/setor
- Horas disponiveis por colaborador

---

## Regras de Negocio Criticas

### Bloqueio de Aprovacao
A escala NAO pode ser aprovada se:
1. Colaborador excede maximo semanal de horas
2. Intervalo minimo entre turnos violado
3. Folga semanal obrigatoria nao respeitada
4. Convocacao de intermitente sem 72h de antecedencia

### Bloqueio de Convocacoes
Convocacoes NAO podem ser geradas se:
1. Escala nao esta com status APPROVED
2. Existem regras criticas violadas

---

## Versionamento

| Versao | Data | Descricao |
|--------|------|-----------|
| 1.0.0 | 2026-01-14 | Arquitetura inicial do Agente Decisorio |
