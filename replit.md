# Hotel Workforce Scheduling System

## Overview
This project is an AI-powered workforce scheduling system designed for hotels. Its primary purpose is to optimize hotel operations and ensure compliance with Brazilian labor laws, particularly for intermittent workers. The system aims to achieve this through comprehensive employee management, AI-driven analytics, and automated, compliant scheduling, ultimately enhancing operational efficiency and legal adherence in the hospitality sector.

## User Preferences
I want iterative development.
Ask before making major changes.
I prefer detailed explanations.
Do not make changes to the folder `Z`.
Do not make changes to the file `Y`.

## System Architecture
The system employs a microservices-oriented architecture. The backend is built with Python FastAPI, the frontend uses React with TypeScript, and PostgreSQL serves as the primary database for data persistence.

**UI/UX Decisions:**
The frontend, developed with React 18 and Vite, provides a modern and responsive user experience. Key functionalities are accessible through dedicated pages for Employee Management, Governance Activities, Schedule Generation, Report Uploads, Intelligence Dashboards, and a Data Lake. Navigation is structured with a sidebar categorizing features into 'Cadastros', 'Operação', 'Inteligência', 'Consultas/Históricos', and 'Configuração'. The Governance page includes tabs for operational parameters, forecast, demand, schedule, and replanning, while the Planning page features panels for Baseline, Daily Update, and Planned vs. Actual comparisons.

**Technical Implementations:**
- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic.
- **Frontend**: React 18, TypeScript, Vite, React Router.
- **Database**: PostgreSQL.

**Feature Specifications:**
- **Employee Management**: Comprehensive CRUD for employees, sectors, and roles.
- **Legal Compliance**: Enforces Brazilian intermittent worker regulations (e.g., 72-hour notice, shift rotation, weekly hour limits).
- **Intelligence Module**: Provides AI analytics, automated report upload with content detection, multi-sector support, statistical deviation tracking, and audit logging.
- **Data Lake Module**: Manages data ingestion, statistics, occupancy tracking, and calculates weekday bias and hourly distribution.
- **Governance Module**: Automates housekeeping scheduling, defines sector operational parameters, generates weekly forecasts and demand, creates schedules, and suggests daily replanning, including legal validations.
- **Planning Module**: Manages `ForecastRun` entities (BASELINE, DAILY_UPDATE, MANUAL) with services for creation, locking, and comparison.
- **Multi-Sector Architecture**: Activities are linked to specific sectors; rules are categorized into global Labor Rules and sector-specific Operational Rules with a cascade mechanism.
- **Operational Calendar Module**: Manages holidays and special events, applying calendar factors (demand_factor, productivity_factor, block_convocations) to adjust demand.
- **Activity Programming Module**: Allows defining weekly operational programming (demand and execution schedule) per sector, supporting AUTO and MANUAL modes with an approval workflow.
- **Activity Classification & Periodicities Module**: Classifies activities as CALCULADA_PELO_AGENTE (agent-calculated), RECORRENTE (recurring), or EVENTUAL (manual). Periodicities define execution intervals.
- **Turnos/Templates Module**: Defines reusable shift patterns per sector without allocating specific people, includes CRUD, validation against labor rules, and a template matching service.
- **Confirmation & Alterations Module**: Manages schedules, convocations, accepts/refusals, and substitutions. All changes generate Adjustment Runs with recorded reasons.
- **Daily Suggestions (Copiloto) Module**: Offers AI-powered recommendations based on new data (e.g., occupancy changes, convocation refusals). Suggestions require human approval and include impact estimation, justification, and actions.
- **Decision Agent Module**: Orchestrates four intelligence cores (Demand, Capacity, Scheduling, Governance) to generate suggestive weekly schedules. Includes calculation memory for audit, rule hierarchy tracking, and an approval workflow, blocking convocations until schedules are approved. This module provides a complete refactor of the rule form with a card-based layout, and an auto-generated `codigo_regra` and `metadados_json`. The Governance and Convocations pages have been rebuilt to unify workflows, requiring sector and week selection and prerequisite validation. New features include an Activity Classification System with three types, a Periodicities Module, and a Recurrence Expansion Service. Calculation rules are now defined per sector for Demand, Programming, and Adjustments, evaluated by priority via a safe rule execution service. The `AUTO` mode is validated, and recurrence control fields are added.
- **Hierarchical Rules Infrastructure**: A comprehensive system for hierarchical rules with four types: LABOR (global), SYSTEM (global), OPERATIONAL (sector-specific), and CALCULATION (sector-specific). Precedence order: LABOR > SYSTEM > OPERATIONAL > CALCULATION. Each type supports three rigidity levels (MANDATORY, DESIRABLE, FLEXIBLE) with CRUD, drag-and-drop reordering, cloning, and activation/deactivation. Global rules (LABOR, SYSTEM) apply across all sectors while sector-specific rules (OPERATIONAL, CALCULATION) can be customized per sector.
- **Calculation Memory & Traceability**: Infrastructure for tracking agent executions (`AgentRun`) and steps (`AgentTraceStep`), including applied rules, calculations, and violated constraints, accessible via a memory endpoint and UI.
- **Rule Engine Central**: A central engine to load, order, and apply hierarchical rules, resolving conflicts and integrating with DemandService and ScheduleGenerator.
- **Explanation Service & Memory UI**: Transforms `AgentTraceStep` into human-readable explanations (text, math, rules_applied, rules_violated, timeline) via an `ExplainService` and a frontend `CalculationMemoryPage`.

**System Design Choices:**
- **API Endpoints**: Comprehensive RESTful APIs for all functionalities.
- **Modularity**: Separation of concerns into distinct backend modules.
- **Data Models**: SQLAlchemy models define the database schema, including audit logs and statistical aggregates.
- **Operational Planning**: Supports a weekly planning cycle with schedule generation, daily monitoring, and 72-hour advance notice for convocations.
- **ISO-8601 Week Standard**: All calendar operations adhere to ISO-8601 for week numbering and fixed weekday order.

## External Dependencies
- **PostgreSQL**: Primary relational database.
- **FastAPI**: Python web framework for building APIs.
- **SQLAlchemy**: Python SQL toolkit and Object-Relational Mapper.
- **React**: JavaScript library for building user interfaces.
- **TypeScript**: Statically typed superset of JavaScript.
- **Vite**: Next-generation frontend tooling.
- **React Router**: Declarative routing for React.