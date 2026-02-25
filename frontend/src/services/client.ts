import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface Sector {
  id: number;
  name: string;
  code: string;
  description?: string;
  is_active: boolean;
  created_at: string;
}

export interface Role {
  id: number;
  name: string;
  cbo_code?: string;
  sector_id: number;
  description?: string;
  is_active: boolean;
  created_at: string;
}

export interface Employee {
  id: number;
  name: string;
  cpf?: string;
  email?: string;
  phone?: string;
  sector_id: number;
  sector_name?: string;
  role_id: number;
  role_name?: string;
  cbo_code?: string;
  contract_type: 'intermitente' | 'efetivo';
  work_regime?: string;
  monthly_hours_target: number;
  velocidade_limpeza_vago_sujo: number;
  velocidade_limpeza_estada: number;
  carga_horaria_max_semana: number;
  unavailable_days: string[];
  time_off_preferences: string[];
  restrictions: string[];
  last_full_week_off?: string;
  hire_date?: string;
  is_active: boolean;
  created_at: string;
}

export type DayType = 'normal' | 'feriado' | 'vespera_feriado';

export interface WeeklyParameters {
  id: number;
  sector_id?: number;
  semana_inicio: string;
  seg_ocupacao_prevista: number;
  seg_quartos_vagos_sujos: number;
  seg_quartos_estada: number;
  seg_tipo_dia: DayType;
  ter_ocupacao_prevista: number;
  ter_quartos_vagos_sujos: number;
  ter_quartos_estada: number;
  ter_tipo_dia: DayType;
  qua_ocupacao_prevista: number;
  qua_quartos_vagos_sujos: number;
  qua_quartos_estada: number;
  qua_tipo_dia: DayType;
  qui_ocupacao_prevista: number;
  qui_quartos_vagos_sujos: number;
  qui_quartos_estada: number;
  qui_tipo_dia: DayType;
  sex_ocupacao_prevista: number;
  sex_quartos_vagos_sujos: number;
  sex_quartos_estada: number;
  sex_tipo_dia: DayType;
  sab_ocupacao_prevista: number;
  sab_quartos_vagos_sujos: number;
  sab_quartos_estada: number;
  sab_tipo_dia: DayType;
  dom_ocupacao_prevista: number;
  dom_quartos_vagos_sujos: number;
  dom_quartos_estada: number;
  dom_tipo_dia: DayType;
  created_at: string;
  updated_at?: string;
}

export interface GovernanceRules {
  id: number;
  // Regras Trabalhistas
  limite_horas_diarias: number;
  limite_horas_semanais_sem_extra: number;
  limite_horas_semanais_com_extra: number;
  intervalo_minimo_entre_turnos: number;
  intervalo_intrajornada_minimo: number;
  intervalo_intrajornada_maximo: number;
  jornada_dispensa_intervalo: number;
  domingos_folga_por_mes: number;
  dias_ferias_anuais: number;
  permite_fracionamento_ferias: boolean;
  respeitar_cbo_atividade: boolean;
  // Regras Operacionais
  alternancia_horarios: boolean;
  alternancia_atividades: boolean;
  variacao_minima_semanal: number;
  variacao_maxima_semanal: number;
  regime_preferencial: string;
  permitir_alternar_regime: boolean;
  dias_folga_semana: number;
  folgas_consecutivas: boolean;
  maximo_dias_consecutivos: number;
  // Tempos de Limpeza
  tempo_padrao_vago_sujo: number;
  tempo_padrao_estada: number;
  meta_aproveitamento_horas: number;
  fator_feriado: number;
  fator_vespera_feriado: number;
  fator_pico: number;
  fator_baixa_ocupacao: number;
  // Configurações de Turno
  turno_manha_inicio: string;
  turno_manha_fim: string;
  turno_tarde_inicio: string;
  turno_tarde_fim: string;
  jornada_media_horas: number;
  // Regras para Feriados
  permitir_intermitentes_feriado: boolean;
  preferir_efetivos_feriado: boolean;
  // Campo Lógica
  logica_customizada?: string;
  // Controle de Alternância
  percentual_max_repeticao_turno: number;
  percentual_max_repeticao_dia_turno: number;
  modo_conservador: boolean;
  intervalo_semanas_folga: number;
  // Metadados
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface GovernanceActivity {
  id: number;
  sector_id?: number;
  sector_name?: string;
  name: string;
  code: string;
  description?: string;
  average_time_minutes: number;
  unit_type?: string;
  difficulty_level: number;
  requires_training: boolean;
  is_active: boolean;
  created_at: string;
}

export interface LaborRules {
  id: number;
  min_notice_hours: number;
  max_week_hours: number;
  max_week_hours_with_overtime: number;
  max_daily_hours: number;
  min_rest_hours_between_shifts: number;
  min_break_hours: number;
  max_break_hours: number;
  no_break_threshold_hours: number;
  sundays_off_per_month: number;
  vacation_days_annual: number;
  allow_vacation_split: boolean;
  max_consecutive_work_days: number;
  respect_cbo_activities: boolean;
  overtime_policy_json?: Record<string, any>;
  intermittent_guardrails_json?: Record<string, any>;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface SectorOperationalRules {
  id: number;
  sector_id: number;
  utilization_target_pct: number;
  buffer_pct: number;
  shift_templates_json?: Record<string, any>;
  productivity_params_json?: Record<string, any>;
  indicators_json?: Record<string, any>;
  alternancia_horarios: boolean;
  alternancia_atividades: boolean;
  regime_preferencial: string;
  permitir_alternar_regime: boolean;
  dias_folga_semana: number;
  folgas_consecutivas: boolean;
  percentual_max_repeticao_turno: number;
  percentual_max_repeticao_dia_turno: number;
  modo_conservador: boolean;
  intervalo_semanas_folga: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string;
}

export interface Room {
  id: number;
  room_number: string;
  floor?: number;
  room_type: string;
  status: string;
  description?: string;
  is_active: boolean;
}

export const sectorsApi = {
  list: () => api.get<Sector[]>('/sectors/'),
  get: (id: number) => api.get<Sector>(`/sectors/${id}`),
  create: (data: Partial<Sector>) => api.post<Sector>('/sectors/', data),
  update: (id: number, data: Partial<Sector>) => api.put<Sector>(`/sectors/${id}`, data),
  delete: (id: number) => api.delete(`/sectors/${id}`),
};

export const rolesApi = {
  list: (sectorId?: number) => api.get<Role[]>('/roles/', { params: { sector_id: sectorId } }),
  get: (id: number) => api.get<Role>(`/roles/${id}`),
  create: (data: Partial<Role>) => api.post<Role>('/roles/', data),
  update: (id: number, data: Partial<Role>) => api.put<Role>(`/roles/${id}`, data),
  delete: (id: number) => api.delete(`/roles/${id}`),
};

export const employeesApi = {
  list: (params?: { sector_id?: number; contract_type?: string }) => 
    api.get<Employee[]>('/employees/', { params }),
  get: (id: number) => api.get<Employee>(`/employees/${id}`),
  create: (data: Partial<Employee>) => api.post<Employee>('/employees/', data),
  update: (id: number, data: Partial<Employee>) => api.put<Employee>(`/employees/${id}`, data),
  delete: (id: number) => api.delete(`/employees/${id}`),
};

export const activitiesApi = {
  list: (sectorId?: number) => api.get<GovernanceActivity[]>('/activities/', { params: { sector_id: sectorId } }),
  get: (id: number) => api.get<GovernanceActivity>(`/activities/${id}`),
  create: (data: Partial<GovernanceActivity> & { sector_id: number }) => api.post<GovernanceActivity>('/activities/', data),
  update: (id: number, data: Partial<GovernanceActivity>) => api.put<GovernanceActivity>(`/activities/${id}`, data),
  delete: (id: number) => api.delete(`/activities/${id}`),
};

export const rulesApi = {
  getLaborRules: () => api.get<LaborRules>('/rules/labor'),
  updateLaborRules: (data: Partial<LaborRules>) => api.put<LaborRules>('/rules/labor', data),
  getOperationalRules: (sectorId: number) => api.get<SectorOperationalRules>('/rules/operational', { params: { sector_id: sectorId } }),
  updateOperationalRules: (sectorId: number, data: Partial<SectorOperationalRules>) => 
    api.put<SectorOperationalRules>('/rules/operational', data, { params: { sector_id: sectorId } }),
  getAllOperationalRules: () => api.get<SectorOperationalRules[]>('/rules/operational/all'),
};

export const roomsApi = {
  list: () => api.get<Room[]>('/rooms/'),
  statusSummary: () => api.get('/rooms/status-summary'),
  create: (data: Partial<Room>) => api.post<Room>('/rooms/', data),
  update: (id: number, data: Partial<Room>) => api.put<Room>(`/rooms/${id}`, data),
  delete: (id: number) => api.delete(`/rooms/${id}`),
};

export const schedulesApi = {
  list: (sectorId?: number) => api.get('/schedules/', { params: { sector_id: sectorId } }),
  generate: (data: { sector_id: number; week_start: string; expected_occupancy?: number; expected_rooms_to_clean?: number }) =>
    api.post('/schedules/generate-governance', data),
  gerarEscalaSugestiva: (semana_inicio: string, sector_id?: number) =>
    api.post('/schedules/gerar-escala-sugestiva', { semana_inicio, sector_id }),
  calcularNecessidade: (semana_inicio: string, sector_id?: number) =>
    api.get(`/schedules/calcular-necessidade/${semana_inicio}`, { params: { sector_id } }),
};

export const weeklyParametersApi = {
  list: (sectorId?: number) => api.get<WeeklyParameters[]>('/weekly-parameters/', { params: { sector_id: sectorId } }),
  get: (id: number) => api.get<WeeklyParameters>(`/weekly-parameters/${id}`),
  getByWeek: (semana_inicio: string, sectorId?: number) => api.get<WeeklyParameters>(`/weekly-parameters/semana/${semana_inicio}`, { params: { sector_id: sectorId } }),
  getBySectorAndWeek: (sectorId: number, semana_inicio: string) => api.get<WeeklyParameters>(`/weekly-parameters/sectors/${sectorId}/week/${semana_inicio}`),
  create: (data: Partial<WeeklyParameters>) => api.post<WeeklyParameters>('/weekly-parameters/', data),
  update: (id: number, data: Partial<WeeklyParameters>) => api.put<WeeklyParameters>(`/weekly-parameters/${id}`, data),
  updateBySector: (sectorId: number, semana_inicio: string, data: Partial<WeeklyParameters>) => api.put<WeeklyParameters>(`/weekly-parameters/sectors/${sectorId}/week/${semana_inicio}`, data),
  delete: (id: number) => api.delete(`/weekly-parameters/${id}`),
};

export const governanceRulesApi = {
  get: () => api.get<GovernanceRules>('/governance-rules/'),
  update: (data: Partial<GovernanceRules>) => api.put<GovernanceRules>('/governance-rules/', data),
  create: (data: Partial<GovernanceRules>) => api.post<GovernanceRules>('/governance-rules/', data),
};

export interface ReportType {
  id: number;
  name: string;
  description?: string;
  indicators: string[];
  sectors: string[];
  is_active: boolean;
}

export interface ReportUpload {
  id: number;
  original_filename: string;
  file_type: string;
  report_type_name?: string;
  date_start?: string;
  date_end?: string;
  status: string;
  sectors_affected: string[];
  created_at: string;
  auto_detected?: boolean;
  detection_confidence?: number;
  indicators_found?: string[];
}

export interface DeviationHistory {
  id: number;
  day_of_week: number;
  day_name: string;
  sample_count: number;
  avg_occupancy_forecast: number;
  avg_occupancy_actual: number;
  avg_deviation: number;
  correction_factor: number;
  version: number;
  last_updated: string;
}

export interface ScheduleRecommendation {
  date: string;
  day_name: string;
  forecasted_occupancy: number;
  corrected_occupancy: number;
  correction_factor: number;
  current_employees: number;
  recommended_employees: number;
  adjustment: number;
  adjustment_reason: string;
  confidence_level: string;
  priority: string;
}

export const reportsApi = {
  listTypes: () => api.get<ReportType[]>('/reports/types'),
  createType: (data: Partial<ReportType>) => api.post<ReportType>('/reports/types', data),
  listUploads: (params?: { status?: string; date_from?: string; date_to?: string }) =>
    api.get<ReportUpload[]>('/reports/uploads', { params }),
  getUpload: (id: number) => api.get<ReportUpload>(`/reports/uploads/${id}`),
  upload: (formData: FormData) => api.post('/reports/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  assignType: (uploadId: number, reportTypeId: number) =>
    api.put(`/reports/uploads/${uploadId}/type`, null, { params: { report_type_id: reportTypeId } }),
  deleteUpload: (id: number) => api.delete(`/reports/uploads/${id}`),
};

export const intelligenceApi = {
  getDeviations: () => api.get<DeviationHistory[]>('/intelligence/deviations'),
  recalculateDeviations: () => api.post('/intelligence/deviations/recalculate'),
  getForecast: (date: string) => api.get(`/intelligence/forecast/${date}`),
  getRecommendations: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/intelligence/recommendations', { params }),
  getComparison: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/intelligence/comparison', { params }),
  getDashboard: () => api.get('/intelligence/dashboard'),
  getAuditLogs: (params?: { action?: string; entity_type?: string; limit?: number }) =>
    api.get('/intelligence/audit-logs', { params }),
};

export interface DataLakeUpload {
  id: number;
  filename: string;
  type: string | null;
  status: string;
  generated_at: string | null;
  created_at: string;
  confidence: number;
  rows_inserted: number;
  rows_skipped: number;
  error_message: string | null;
}

export interface OccupancyLatest {
  target_date: string;
  real_pct: number | null;
  real_as_of: string | null;
  forecast_pct: number | null;
  forecast_as_of: string | null;
}

export interface WeekdayBias {
  weekday: string;
  bias_pp: number;
  n: number;
  std_pp: number | null;
  mae_pp: number | null;
  method: string;
}

export interface AdjustedForecast {
  target_date: string;
  weekday_pt: string;
  forecast_pct: number | null;
  bias_pp: number;
  adjusted_forecast_pct: number | null;
  real_pct: number | null;
  has_bias_data: boolean;
}

export type HolidayType = 'NATIONAL' | 'STATE' | 'MUNICIPAL' | 'INTERNAL';
export type CalendarScope = 'GLOBAL' | 'SECTOR';

export interface CalendarEvent {
  id: number;
  date: string;
  name: string;
  holiday_type: HolidayType;
  scope: CalendarScope;
  sector_id: number | null;
  sector_name: string | null;
  productivity_factor: number;
  demand_factor: number;
  block_convocations: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CalendarEventCreate {
  date: string;
  name: string;
  holiday_type: HolidayType;
  scope: CalendarScope;
  sector_id?: number | null;
  productivity_factor?: number;
  demand_factor?: number;
  block_convocations?: boolean;
  notes?: string | null;
}

export interface CalendarFactors {
  productivity_factor: number;
  demand_factor: number;
  block_convocations: boolean;
  applied_events: string[];
}

export const calendarApi = {
  list: (params?: { year?: number; month?: number; sector_id?: number; holiday_type?: HolidayType; start_date?: string; end_date?: string }) =>
    api.get<CalendarEvent[]>('/calendar/', { params }),
  get: (id: number) => api.get<CalendarEvent>(`/calendar/${id}`),
  create: (data: CalendarEventCreate) => api.post<CalendarEvent>('/calendar/', data),
  update: (id: number, data: Partial<CalendarEventCreate>) => api.put<CalendarEvent>(`/calendar/${id}`, data),
  delete: (id: number) => api.delete(`/calendar/${id}`),
  getFactors: (targetDate: string, sectorId?: number) =>
    api.get<CalendarFactors>(`/calendar/factors/${targetDate}`, { params: { sector_id: sectorId } }),
};

export interface ShiftTemplate {
  id: number;
  sector_id: number;
  sector_name: string | null;
  name: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
  min_hours: number;
  max_hours: number;
  valid_weekdays: number[];
  is_active: boolean;
  calculated_hours: number | null;
}

export interface ShiftTemplateCreate {
  sector_id: number;
  name: string;
  start_time: string;
  end_time: string;
  break_minutes?: number;
  min_hours?: number;
  max_hours?: number;
  valid_weekdays?: number[];
}

export interface ShiftTemplateUpdate {
  name?: string;
  start_time?: string;
  end_time?: string;
  break_minutes?: number;
  min_hours?: number;
  max_hours?: number;
  valid_weekdays?: number[];
}

export const shiftTemplatesApi = {
  list: (sectorId?: number, activeOnly?: boolean) =>
    api.get<ShiftTemplate[]>('/shift-templates', { params: { sector_id: sectorId, active_only: activeOnly } }),
  get: (id: number) => api.get<ShiftTemplate>(`/shift-templates/${id}`),
  create: (data: ShiftTemplateCreate) => api.post<ShiftTemplate>('/shift-templates', data),
  update: (id: number, data: ShiftTemplateUpdate) => api.put<ShiftTemplate>(`/shift-templates/${id}`, data),
  disable: (id: number) => api.post(`/shift-templates/${id}/disable`),
  enable: (id: number) => api.post(`/shift-templates/${id}/enable`),
  matchProgramming: (sectorId: number, dailyWorkloadMinutes: Record<string, number>) =>
    api.post('/shift-templates/match-programming', { sector_id: sectorId, daily_workload_minutes: dailyWorkloadMinutes }),
};

export const dataLakeApi = {
  upload: (formData: FormData) => 
    api.post('/data-lake/uploads', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),
  listUploads: (skip?: number, limit?: number) =>
    api.get<DataLakeUpload[]>('/data-lake/uploads', { params: { skip, limit } }),
  getUpload: (id: number) => api.get(`/data-lake/uploads/${id}`),
  reprocessUpload: (id: number) => api.post(`/data-lake/uploads/${id}/reprocess`),
  getOccupancyLatest: (start?: string, end?: string) =>
    api.get<OccupancyLatest[]>('/data-lake/occupancy/latest', { params: { start, end } }),
  getEventsHourly: (eventType: string, start?: string, end?: string) =>
    api.get('/data-lake/events/hourly', { params: { event_type: eventType, start, end } }),
  getWeekdayBias: () => api.get<WeekdayBias[]>('/data-lake/stats/weekday-bias'),
  getHourlyDistribution: (metric: string) =>
    api.get('/data-lake/stats/hourly-distribution', { params: { metric } }),
  bootstrapBias: (data: Record<string, number>) =>
    api.post('/data-lake/stats/bootstrap-bias', data),
  recalculateStats: () => api.post('/data-lake/stats/recalculate'),
  getAdjustedForecast: (start: string, end: string) =>
    api.get<AdjustedForecast[]>('/data-lake/forecast/adjusted', { params: { start, end } }),
};

export interface DailySuggestion {
  id: number;
  sector_id: number;
  sector_name: string | null;
  date: string;
  suggestion_type: string;
  description: string;
  impact_category: string;
  impact_json: Record<string, any> | null;
  source_data: Record<string, any> | null;
  status: 'open' | 'applied' | 'ignored';
  priority: number;
  adjustment_run_id: number | null;
  created_at: string;
  resolved_at: string | null;
  resolved_by: string | null;
  resolution_notes: string | null;
}

export const dailySuggestionsApi = {
  list: (params?: { sector_id?: number; date?: string; status?: string; limit?: number }) =>
    api.get<DailySuggestion[]>('/daily-suggestions', { params }),
  listOpen: (sectorId?: number) =>
    api.get<DailySuggestion[]>('/daily-suggestions/open', { params: { sector_id: sectorId } }),
  get: (id: number) => api.get<DailySuggestion>(`/daily-suggestions/${id}`),
  generate: (sectorId: number, date: string) =>
    api.post<DailySuggestion[]>('/daily-suggestions/generate', { sector_id: sectorId, date }),
  apply: (id: number, userId?: string, notes?: string) =>
    api.post(`/daily-suggestions/${id}/apply`, { user_id: userId, notes }),
  ignore: (id: number, userId?: string, notes?: string) =>
    api.post(`/daily-suggestions/${id}/ignore`, { user_id: userId, notes }),
};

export const apiClient = api;
export default api;
