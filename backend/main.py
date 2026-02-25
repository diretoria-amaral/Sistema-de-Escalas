import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import (
    sectors_router,
    roles_router,
    employees_router,
    rooms_router,
    governance_activities_router,
    schedules_router,
    weekly_parameters_router,
    governance_rules_router,
    reports_router,
    intelligence_router,
    data_lake_router,
    governance_router,
    forecast_runs_router,
    activities_router,
    rules_router,
    calendar_router,
    convocations_router,
    compliance_router,
    activity_program_router,
    shift_template_router,
    daily_suggestion_router,
    periodicities_router,
    regras_calculo_setor_router,
    decision_agent_router,
    sector_rules_router,
    agent_runs_router,
    rule_engine_router,
    admin_rules_router,
    work_shifts_router,
    api_usage_router
)

app = FastAPI(
    title="Hotel Workforce Scheduling System",
    description="AI-powered workforce scheduling for hotel governance and operations",
    version="1.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sectors_router, prefix="/api")
app.include_router(roles_router, prefix="/api")
app.include_router(employees_router, prefix="/api")
app.include_router(rooms_router, prefix="/api")
app.include_router(governance_activities_router, prefix="/api")
app.include_router(schedules_router, prefix="/api")
app.include_router(weekly_parameters_router, prefix="/api")
app.include_router(governance_rules_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(intelligence_router, prefix="/api")
app.include_router(data_lake_router)
app.include_router(governance_router)
app.include_router(forecast_runs_router)
app.include_router(activities_router)
app.include_router(rules_router)
app.include_router(calendar_router, prefix="/api")
app.include_router(convocations_router)
app.include_router(compliance_router, prefix="/api")
app.include_router(activity_program_router, prefix="/api")
app.include_router(shift_template_router)
app.include_router(daily_suggestion_router)
app.include_router(periodicities_router)
app.include_router(regras_calculo_setor_router)
app.include_router(decision_agent_router)
app.include_router(sector_rules_router)
app.include_router(agent_runs_router)
app.include_router(rule_engine_router)
app.include_router(admin_rules_router)
app.include_router(work_shifts_router)
app.include_router(api_usage_router, prefix="/api")


@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {
        "message": "Hotel Workforce Scheduling System API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
