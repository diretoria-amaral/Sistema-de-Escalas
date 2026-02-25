from .sectors import router as sectors_router
from .roles import router as roles_router
from .employees import router as employees_router
from .rooms import router as rooms_router
from .governance_activities import router as governance_activities_router
from .schedules import router as schedules_router
from .weekly_parameters import router as weekly_parameters_router
from .governance_rules import router as governance_rules_router
from .reports import router as reports_router
from .intelligence import router as intelligence_router
from .data_lake import router as data_lake_router
from .governance import router as governance_router
from .forecast_runs import router as forecast_runs_router
from .activities import router as activities_router
from .rules import router as rules_router
from .calendar import router as calendar_router
from .convocations import router as convocations_router
from .compliance import router as compliance_router
from .activity_program import router as activity_program_router
from .work_shift import router as work_shifts_router
from .shift_template import router as shift_template_router
from .daily_suggestion import router as daily_suggestion_router
from .periodicities import router as periodicities_router
from .regras_calculo_setor import router as regras_calculo_setor_router
from .decision_agent import router as decision_agent_router
from .sector_rules import router as sector_rules_router
from .agent_runs import router as agent_runs_router
from .rule_engine import router as rule_engine_router
from .admin_rules import router as admin_rules_router
from .api_usage import router as api_usage_router

__all__ = [
    "sectors_router",
    "roles_router", 
    "employees_router",
    "rooms_router",
    "governance_activities_router",
    "schedules_router",
    "weekly_parameters_router",
    "governance_rules_router",
    "reports_router",
    "intelligence_router",
    "data_lake_router",
    "governance_router",
    "forecast_runs_router",
    "activities_router",
    "rules_router",
    "calendar_router",
    "convocations_router",
    "compliance_router",
    "activity_program_router",
    "work_shifts_router",
    "shift_template_router",
    "daily_suggestion_router",
    "periodicities_router",
    "regras_calculo_setor_router",
    "decision_agent_router",
    "sector_rules_router",
    "agent_runs_router",
    "rule_engine_router",
    "admin_rules_router",
    "api_usage_router"
]
