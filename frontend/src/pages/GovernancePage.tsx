import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

interface Sector {
  id: number;
  name: string;
  code: string;
}

interface SectorParams {
  id?: number;
  sector_id: number;
  exists: boolean;
  target_utilization_pct: number;
  buffer_pct: number;
  cleaning_time_vago_sujo_min: number;
  cleaning_time_estadia_min: number;
  safety_pp_by_weekday: Record<string, number>;
  shift_templates: Array<{name: string; start_time: string; end_time: string; hours: number}>;
  lunch_rules: Record<string, any>;
  total_rooms: number;
  replan_threshold_pp: number;
}

interface OccupancyData {
  target_date: string;
  occ_pct: number;
  source: string;
}

interface DailyForecast {
  target_date: string;
  weekday_pt: string;
  occ_raw: number | null;
  bias_pp: number;
  safety_pp: number;
  occ_adj: number | null;
}

interface ForecastRun {
  id: number;
  run_date: string;
  horizon_start: string;
  horizon_end: string;
  status: string;
  iso_week?: number;
  daily_forecasts?: DailyForecast[];
}

interface DemandDaily {
  target_date: string;
  weekday_pt: string;
  occ_adj?: number;
  occupied_rooms: number;
  departures_count: number;
  arrivals_count: number;
  stayovers_estimated: number;
  minutes_variable: number;
  minutes_constant: number;
  minutes_required_raw: number;
  minutes_required_buffered: number;
  hours_productive_required: number;
  hours_total_required: number;
  headcount_required: number;
  headcount_rounded: number;
  constant_activities_count: number;
  breakdown?: any;
}

interface DemandSummary {
  total_rooms: number;
  total_minutes_week: number;
  total_minutes_variable_week: number;
  total_minutes_constant_week: number;
  total_hours_week: number;
  total_headcount_week: number;
  avg_headcount_daily: number;
}

interface SchedulePlan {
  id: number;
  week_start: string;
  status: string;
  daily_slots?: any[];
  summary?: any;
}

interface Prerequisite {
  valid: boolean;
  message: string;
  details?: any;
}

interface Prerequisites {
  can_generate: boolean;
  sector_id: number;
  week_start: string;
  week_end: string;
  prerequisites: {
    sector: Prerequisite;
    parameters: Prerequisite;
    activities: Prerequisite;
    historical_data: Prerequisite;
  };
  blocking_errors: string[];
  warnings: string[];
}

interface GovernanceActivity {
  id: number;
  name: string;
  code: string;
  average_time_minutes: number;
  is_programmed: boolean;
  sector_id: number;
}

type TabType = 'overview' | 'params' | 'forecast' | 'demand' | 'schedule' | 'replan';

export default function GovernancePage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [weekStart, setWeekStart] = useState<string>('');
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{type: 'success' | 'error' | 'warning'; text: string} | null>(null);
  
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  
  const [params, setParams] = useState<SectorParams | null>(null);
  const [prerequisites, setPrerequisites] = useState<Prerequisites | null>(null);
  const [occupancyData, setOccupancyData] = useState<OccupancyData[]>([]);
  
  const [activities, setActivities] = useState<GovernanceActivity[]>([]);
  const [selectedActivityIds, setSelectedActivityIds] = useState<number[]>([]);
  
  const [forecastRun, setForecastRun] = useState<ForecastRun | null>(null);
  const [demands, setDemands] = useState<DemandDaily[]>([]);
  const [demandSummary, setDemandSummary] = useState<DemandSummary | null>(null);
  
  const [schedulePlan, setSchedulePlan] = useState<SchedulePlan | null>(null);
  const [suggestions, setSuggestions] = useState<any[]>([]);

  useEffect(() => {
    loadSectors();
    const today = new Date();
    const dayOfWeek = today.getDay();
    const daysToNextMonday = dayOfWeek === 0 ? 1 : (8 - dayOfWeek);
    const nextMonday = new Date(today);
    nextMonday.setDate(today.getDate() + daysToNextMonday);
    setWeekStart(nextMonday.toISOString().split('T')[0]);
  }, []);

  useEffect(() => {
    if (selectedSectorId && weekStart) {
      resetWorkflowState();
      loadAllData();
    }
  }, [selectedSectorId, weekStart]);

  const resetWorkflowState = () => {
    setForecastRun(null);
    setDemands([]);
    setDemandSummary(null);
    setSchedulePlan(null);
    setSuggestions([]);
  };

  const loadSectors = async () => {
    try {
      const response = await axios.get('/api/sectors');
      setSectors(response.data);
      const govSector = response.data.find((s: Sector) => 
        s.code?.toLowerCase().includes('gov') || s.name?.toLowerCase().includes('governança')
      );
      if (govSector) {
        setSelectedSectorId(govSector.id);
      } else if (response.data.length > 0) {
        setSelectedSectorId(response.data[0].id);
      }
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao carregar setores. Verifique se há setores cadastrados.' });
    }
  };

  const loadAllData = async () => {
    if (!selectedSectorId || !weekStart) return;
    
    setLoading(true);
    setMessage(null);
    
    try {
      await Promise.all([
        loadParameters(),
        loadPrerequisites(),
        loadOccupancyLatest(),
        loadActivities()
      ]);
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    }
    
    setLoading(false);
  };

  const loadParameters = async () => {
    try {
      const response = await axios.get(`/api/governance/parameters?sector_id=${selectedSectorId}`);
      setParams(response.data);
    } catch (error) {
      setParams(null);
    }
  };

  const loadPrerequisites = async () => {
    try {
      const response = await axios.get(
        `/api/forecast-runs/prerequisites?sector_id=${selectedSectorId}&week_start=${weekStart}`
      );
      setPrerequisites(response.data);
    } catch (error: any) {
      setPrerequisites(null);
      const detail = error.response?.data?.detail;
      if (detail) {
        const errorText = typeof detail === 'string' ? detail : JSON.stringify(detail);
        setMessage({ type: 'error', text: `Erro ao verificar pré-requisitos: ${errorText}` });
      }
    }
  };

  const loadOccupancyLatest = async () => {
    try {
      const response = await axios.get('/api/data-lake/occupancy/latest?limit=7');
      setOccupancyData(response.data || []);
    } catch (error) {
      setOccupancyData([]);
    }
  };

  const loadActivities = async () => {
    if (!weekStart || !selectedSectorId) return;
    try {
      const response = await axios.get(
        `/api/governance/forecast/available-activities?sector_id=${selectedSectorId}&week_start=${weekStart}`
      );
      setActivities(response.data.activities || []);
      const programmedIds = response.data.activities
        .filter((a: GovernanceActivity) => a.is_programmed)
        .map((a: GovernanceActivity) => a.id);
      if (programmedIds.length > 0) {
        setSelectedActivityIds(programmedIds);
      } else {
        setSelectedActivityIds(response.data.activities.map((a: GovernanceActivity) => a.id));
      }
    } catch (error: any) {
      setActivities([]);
      setSelectedActivityIds([]);
      const detail = error.response?.data?.detail;
      if (detail) {
        const errorText = typeof detail === 'string' ? detail : JSON.stringify(detail);
        setMessage({ type: 'warning', text: `Atividades: ${errorText}` });
      }
    }
  };

  const canExecuteWorkflow = (): boolean => {
    return prerequisites?.can_generate === true;
  };

  const runForecast = async () => {
    if (!canExecuteWorkflow()) {
      setMessage({ type: 'error', text: 'Pré-requisitos não atendidos. Verifique o painel de validação.' });
      return;
    }
    if (!selectedSectorId || !weekStart) {
      setMessage({ type: 'error', text: 'Selecione o setor e a semana antes de gerar a projeção.' });
      return;
    }
    if (selectedActivityIds.length === 0) {
      setMessage({ type: 'error', text: 'Selecione pelo menos uma atividade.' });
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post('/api/governance/forecast/run', {
        sector_id: selectedSectorId,
        week_start: weekStart,
        activity_ids: selectedActivityIds
      });
      
      setMessage({ type: 'success', text: `Projeção gerada! Semana ISO ${response.data.iso_week}` });
      
      if (response.data.forecast_run_id) {
        await loadForecastDetails(response.data.forecast_run_id);
      }
      
      setActiveTab('forecast');
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      const errorText = Array.isArray(detail) ? detail.join(' | ') : (typeof detail === 'string' ? detail : JSON.stringify(detail));
      setMessage({ type: 'error', text: errorText || 'Erro ao gerar projeção.' });
    }
    setLoading(false);
  };

  const loadForecastDetails = async (runId: number) => {
    try {
      const response = await axios.get(`/api/governance/forecast/${runId}`);
      setForecastRun(response.data);
    } catch (error) {
      console.error('Erro ao carregar forecast:', error);
    }
  };

  const computeDemand = async () => {
    if (!canExecuteWorkflow()) {
      setMessage({ type: 'error', text: 'Pré-requisitos não atendidos. Verifique o painel de validação.' });
      return;
    }
    if (!forecastRun) {
      setMessage({ type: 'error', text: 'Gere a projeção de ocupação primeiro.' });
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post(`/api/governance/demand/compute?forecast_run_id=${forecastRun.id}`);
      
      setDemands(response.data.daily_demands || []);
      setDemandSummary(response.data.summary || null);
      setMessage({ type: 'success', text: 'Demanda de limpeza calculada!' });
      setActiveTab('demand');
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao calcular demanda.' });
    }
    setLoading(false);
  };

  const generateSchedule = async () => {
    if (!canExecuteWorkflow()) {
      setMessage({ type: 'error', text: 'Pré-requisitos não atendidos. Verifique o painel de validação.' });
      return;
    }
    if (!forecastRun || !selectedSectorId) {
      setMessage({ type: 'error', text: 'Gere a projeção e a demanda primeiro.' });
      return;
    }
    if (demands.length === 0) {
      setMessage({ type: 'error', text: 'Calcule a demanda de limpeza antes de gerar a escala.' });
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post(
        `/api/governance/schedule/generate?week_start=${forecastRun.horizon_start}&sector_id=${selectedSectorId}&forecast_run_id=${forecastRun.id}`
      );
      
      if (response.data.schedule_plan_id) {
        await loadScheduleDetails(response.data.schedule_plan_id);
      }
      
      setMessage({ type: 'success', text: 'Escala sugerida gerada!' });
      setActiveTab('schedule');
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao gerar escala.' });
    }
    setLoading(false);
  };

  const loadScheduleDetails = async (planId: number) => {
    try {
      const response = await axios.get(`/api/governance/schedule/${planId}`);
      setSchedulePlan(response.data);
    } catch (error) {
      console.error('Erro ao carregar escala:', error);
    }
  };

  const loadSuggestions = async () => {
    if (!selectedSectorId) return;
    try {
      const response = await axios.get(`/api/governance/replan/suggestions?sector_id=${selectedSectorId}`);
      setSuggestions(response.data || []);
    } catch (error) {
      setSuggestions([]);
    }
  };

  const saveParams = async () => {
    if (!params || !selectedSectorId) return;
    setLoading(true);
    try {
      if (params.id) {
        await axios.put(`/api/governance/parameters/${params.id}`, params);
      } else {
        await axios.post('/api/governance/parameters', { ...params, sector_id: selectedSectorId });
      }
      setMessage({ type: 'success', text: 'Parâmetros salvos com sucesso!' });
      loadAllData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao salvar parâmetros.' });
    }
    setLoading(false);
  };

  const initializeParams = () => {
    setParams({
      sector_id: selectedSectorId || 1,
      exists: false,
      target_utilization_pct: 85,
      buffer_pct: 10,
      cleaning_time_vago_sujo_min: 25,
      cleaning_time_estadia_min: 10,
      safety_pp_by_weekday: {
        "SEGUNDA-FEIRA": 0,
        "TERÇA-FEIRA": 0,
        "QUARTA-FEIRA": 0,
        "QUINTA-FEIRA": 0,
        "SEXTA-FEIRA": 2,
        "SÁBADO": 3,
        "DOMINGO": 2
      },
      shift_templates: [
        { name: "Manhã", start_time: "07:00", end_time: "15:00", hours: 8 },
        { name: "Tarde", start_time: "14:00", end_time: "22:00", hours: 8 }
      ],
      lunch_rules: {
        duration_min: 60,
        window_start: "11:00",
        window_end: "14:00"
      },
      total_rooms: 100,
      replan_threshold_pp: 5
    });
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  };

  const getPrerequisiteIcon = (valid: boolean) => valid ? '✓' : '✗';
  const getPrerequisiteColor = (valid: boolean) => valid ? '#16a34a' : '#dc2626';

  const selectedSector = sectors.find(s => s.id === selectedSectorId);

  return (
    <div className="card">
      <h2>Módulo de Governança (Demanda / Escala)</h2>
      <p style={{ color: '#666', marginBottom: '1.5rem' }}>
        Projeção de ocupação, cálculo de demanda de limpeza e geração de escalas para camareiras.
      </p>

      {message && (
        <div style={{
          padding: '12px 16px',
          marginBottom: '1rem',
          borderRadius: '6px',
          backgroundColor: message.type === 'success' ? '#d1fae5' : message.type === 'warning' ? '#fef3c7' : '#fee2e2',
          color: message.type === 'success' ? '#065f46' : message.type === 'warning' ? '#92400e' : '#991b1b',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>{message.text}</span>
          <button onClick={() => setMessage(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem' }}>×</button>
        </div>
      )}

      <div style={{ 
        background: '#f1f5f9', 
        padding: '20px', 
        borderRadius: '8px', 
        marginBottom: '1.5rem',
        border: '1px solid #e2e8f0'
      }}>
        <h4 style={{ marginTop: 0, marginBottom: '15px' }}>Seleção Obrigatória</h4>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Setor</label>
            <select 
              value={selectedSectorId || ''} 
              onChange={(e) => setSelectedSectorId(Number(e.target.value))}
              style={{ padding: '10px 12px', borderRadius: '4px', border: '1px solid #cbd5e1', minWidth: '200px' }}
            >
              <option value="">Selecione um setor...</option>
              {sectors.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Semana (Segunda-feira)</label>
            <input 
              type="date" 
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              style={{ padding: '10px 12px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
            />
          </div>
          <button 
            onClick={loadAllData}
            disabled={loading || !selectedSectorId || !weekStart}
            className="btn-secondary"
            style={{ height: '42px' }}
          >
            {loading ? 'Carregando...' : 'Atualizar Dados'}
          </button>
        </div>
      </div>

      {!selectedSectorId && (
        <div style={{ 
          padding: '40px', 
          textAlign: 'center', 
          backgroundColor: '#fef3c7', 
          borderRadius: '8px',
          border: '1px solid #fcd34d'
        }}>
          <h3 style={{ color: '#92400e', marginBottom: '10px' }}>Selecione um Setor</h3>
          <p style={{ color: '#a16207' }}>
            É necessário selecionar um setor para visualizar os dados de governança.
          </p>
        </div>
      )}

      {selectedSectorId && (
        <>
          {prerequisites && (
            <div style={{ 
              padding: '16px', 
              marginBottom: '1.5rem', 
              backgroundColor: prerequisites.can_generate ? '#f0fdf4' : '#fef2f2',
              border: `1px solid ${prerequisites.can_generate ? '#86efac' : '#fca5a5'}`,
              borderRadius: '8px' 
            }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '12px' }}>
                <span style={{ 
                  fontSize: '1.5rem', 
                  marginRight: '10px',
                  color: prerequisites.can_generate ? '#16a34a' : '#dc2626'
                }}>
                  {prerequisites.can_generate ? '✓' : '✗'}
                </span>
                <div>
                  <h4 style={{ margin: 0 }}>
                    {prerequisites.can_generate 
                      ? 'Pré-requisitos Atendidos - Sistema Pronto' 
                      : 'Pré-requisitos Pendentes - Ação Necessária'}
                  </h4>
                  <span style={{ fontSize: '0.875rem', color: '#666' }}>
                    Setor: {selectedSector?.name} | Semana: {prerequisites.week_start} a {prerequisites.week_end}
                  </span>
                </div>
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px' }}>
                {Object.entries(prerequisites.prerequisites).map(([key, prereq]) => (
                  <div 
                    key={key} 
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center',
                      padding: '10px 12px',
                      backgroundColor: prereq.valid ? '#dcfce7' : '#fee2e2',
                      borderRadius: '6px',
                      border: `1px solid ${prereq.valid ? '#86efac' : '#fca5a5'}`
                    }}
                  >
                    <span style={{ 
                      marginRight: '10px', 
                      fontSize: '1.2rem',
                      color: getPrerequisiteColor(prereq.valid)
                    }}>
                      {getPrerequisiteIcon(prereq.valid)}
                    </span>
                    <div>
                      <strong>
                        {key === 'historical_data' ? 'Dados HP' : 
                         key === 'parameters' ? 'Parâmetros' :
                         key === 'activities' ? 'Atividades' :
                         key === 'sector' ? 'Setor' : key}
                      </strong>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>{prereq.message}</div>
                    </div>
                  </div>
                ))}
              </div>
              
              {prerequisites.blocking_errors.length > 0 && (
                <div style={{ 
                  marginTop: '12px',
                  padding: '12px', 
                  backgroundColor: '#fee2e2', 
                  borderRadius: '6px',
                  border: '1px solid #fca5a5'
                }}>
                  <strong style={{ color: '#991b1b' }}>Erros Bloqueantes:</strong>
                  <ul style={{ margin: '8px 0 0 20px', padding: 0, color: '#991b1b' }}>
                    {prerequisites.blocking_errors.map((err, i) => (
                      <li key={i}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}

          <div className="tabs" style={{ marginBottom: '20px', display: 'flex', flexWrap: 'wrap', gap: '5px' }}>
            {[
              { key: 'overview', label: 'Visão Geral' },
              { key: 'params', label: 'Parâmetros' },
              { key: 'forecast', label: 'Projeção Ocupação' },
              { key: 'demand', label: 'Demanda de Limpeza' },
              { key: 'schedule', label: 'Escala Sugerida' },
              { key: 'replan', label: 'Ajustes Diários' }
            ].map(tab => (
              <button 
                key={tab.key}
                className={activeTab === tab.key ? 'active' : ''} 
                onClick={() => {
                  setActiveTab(tab.key as TabType);
                  if (tab.key === 'replan') loadSuggestions();
                }}
                style={{
                  padding: '10px 16px',
                  borderRadius: '6px',
                  border: activeTab === tab.key ? '2px solid #3b82f6' : '1px solid #cbd5e1',
                  backgroundColor: activeTab === tab.key ? '#eff6ff' : '#fff',
                  fontWeight: activeTab === tab.key ? '600' : '400',
                  cursor: 'pointer'
                }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {loading && (
            <div style={{ textAlign: 'center', padding: '20px', color: '#666' }}>
              Carregando...
            </div>
          )}

          {activeTab === 'overview' && !loading && (
            <div>
              <h3>Fluxo de Trabalho</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px', marginBottom: '20px' }}>
                <div style={{ 
                  padding: '16px', 
                  backgroundColor: prerequisites?.can_generate ? '#f0fdf4' : '#f8fafc', 
                  borderRadius: '8px',
                  border: '1px solid #e2e8f0'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontSize: '1.5rem', marginRight: '10px' }}>1️⃣</span>
                    <strong>Validar Pré-requisitos</strong>
                  </div>
                  <p style={{ fontSize: '0.875rem', color: '#666', margin: 0 }}>
                    Setor, parâmetros, atividades e dados HP devem estar configurados.
                  </p>
                  <div style={{ marginTop: '10px', fontSize: '0.875rem', fontWeight: '500', color: prerequisites?.can_generate ? '#16a34a' : '#dc2626' }}>
                    Status: {prerequisites?.can_generate ? 'Pronto' : 'Pendente'}
                  </div>
                </div>

                <div style={{ 
                  padding: '16px', 
                  backgroundColor: forecastRun ? '#f0fdf4' : '#f8fafc', 
                  borderRadius: '8px',
                  border: '1px solid #e2e8f0'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontSize: '1.5rem', marginRight: '10px' }}>2️⃣</span>
                    <strong>Gerar Projeção</strong>
                  </div>
                  <p style={{ fontSize: '0.875rem', color: '#666', margin: 0 }}>
                    Ocupação ajustada com bias estatístico e margem de segurança.
                  </p>
                  <button 
                    onClick={runForecast}
                    disabled={loading || !prerequisites?.can_generate}
                    className="btn-primary"
                    style={{ marginTop: '10px', width: '100%' }}
                  >
                    Gerar Projeção
                  </button>
                </div>

                <div style={{ 
                  padding: '16px', 
                  backgroundColor: demands.length > 0 ? '#f0fdf4' : '#f8fafc', 
                  borderRadius: '8px',
                  border: '1px solid #e2e8f0'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontSize: '1.5rem', marginRight: '10px' }}>3️⃣</span>
                    <strong>Calcular Demanda</strong>
                  </div>
                  <p style={{ fontSize: '0.875rem', color: '#666', margin: 0 }}>
                    Minutos de limpeza (variável + constante) e headcount.
                  </p>
                  <button 
                    onClick={computeDemand}
                    disabled={loading || !canExecuteWorkflow() || !forecastRun}
                    className="btn-primary"
                    style={{ marginTop: '10px', width: '100%' }}
                  >
                    Calcular Demanda
                  </button>
                </div>

                <div style={{ 
                  padding: '16px', 
                  backgroundColor: schedulePlan ? '#f0fdf4' : '#f8fafc', 
                  borderRadius: '8px',
                  border: '1px solid #e2e8f0'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', marginBottom: '10px' }}>
                    <span style={{ fontSize: '1.5rem', marginRight: '10px' }}>4️⃣</span>
                    <strong>Gerar Escala</strong>
                  </div>
                  <p style={{ fontSize: '0.875rem', color: '#666', margin: 0 }}>
                    Distribuição de colaboradores por turno e dia.
                  </p>
                  <button 
                    onClick={generateSchedule}
                    disabled={loading || !canExecuteWorkflow() || demands.length === 0}
                    className="btn-primary"
                    style={{ marginTop: '10px', width: '100%' }}
                  >
                    Gerar Escala
                  </button>
                </div>
              </div>

              {params?.exists && (
                <div style={{ marginTop: '20px' }}>
                  <h4>Parâmetros do Setor Carregados</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px' }}>
                    <div style={{ padding: '10px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>Total Quartos</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{params.total_rooms}</div>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>Tempo Vago/Sujo</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{params.cleaning_time_vago_sujo_min} min</div>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>Tempo Estadia</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{params.cleaning_time_estadia_min} min</div>
                    </div>
                    <div style={{ padding: '10px', backgroundColor: '#f8fafc', borderRadius: '6px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>Buffer</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 'bold' }}>{params.buffer_pct}%</div>
                    </div>
                  </div>
                </div>
              )}

              {occupancyData.length > 0 && (
                <div style={{ marginTop: '20px' }}>
                  <h4>Últimos Dados de Ocupação (HP)</h4>
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#f1f5f9' }}>
                          <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Data</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Ocupação (%)</th>
                          <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Fonte</th>
                        </tr>
                      </thead>
                      <tbody>
                        {occupancyData.slice(0, 7).map((occ, i) => (
                          <tr key={i}>
                            <td style={{ padding: '10px', border: '1px solid #e2e8f0' }}>{formatDate(occ.target_date)}</td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold' }}>
                              {occ.occ_pct?.toFixed(1) || '-'}%
                            </td>
                            <td style={{ padding: '10px', border: '1px solid #e2e8f0' }}>{occ.source}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'params' && !loading && (
            <div>
              <h3>Parâmetros Operacionais</h3>
              {!params?.exists && !params?.id ? (
                <div style={{ padding: '20px', backgroundColor: '#fef3c7', borderRadius: '8px', marginBottom: '20px' }}>
                  <p style={{ margin: 0, marginBottom: '10px' }}>Nenhum parâmetro configurado para este setor.</p>
                  <button className="btn-primary" onClick={initializeParams}>
                    Criar Parâmetros Padrão
                  </button>
                </div>
              ) : params && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginBottom: '20px' }}>
                    <div>
                      <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Total de Quartos</label>
                      <input 
                        type="number" 
                        value={params.total_rooms} 
                        onChange={(e) => setParams({...params, total_rooms: Number(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Meta Aproveitamento (%)</label>
                      <input 
                        type="number" 
                        value={params.target_utilization_pct} 
                        onChange={(e) => setParams({...params, target_utilization_pct: Number(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Buffer/Margem (%)</label>
                      <input 
                        type="number" 
                        value={params.buffer_pct} 
                        onChange={(e) => setParams({...params, buffer_pct: Number(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Tempo Vago Sujo (min)</label>
                      <input 
                        type="number" 
                        value={params.cleaning_time_vago_sujo_min} 
                        onChange={(e) => setParams({...params, cleaning_time_vago_sujo_min: Number(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Tempo Estadia (min)</label>
                      <input 
                        type="number" 
                        value={params.cleaning_time_estadia_min} 
                        onChange={(e) => setParams({...params, cleaning_time_estadia_min: Number(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ display: 'block', marginBottom: '5px', fontWeight: '500' }}>Threshold Replan (pp)</label>
                      <input 
                        type="number" 
                        value={params.replan_threshold_pp} 
                        onChange={(e) => setParams({...params, replan_threshold_pp: Number(e.target.value)})}
                        style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                  </div>

                  <div style={{ marginBottom: '20px' }}>
                    <label style={{ display: 'block', marginBottom: '10px', fontWeight: '500' }}>Safety PP por Dia da Semana</label>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '10px' }}>
                      {Object.entries(params.safety_pp_by_weekday || {}).map(([day, value]) => (
                        <div key={day} style={{ textAlign: 'center' }}>
                          <label style={{ fontSize: '0.75rem', display: 'block', marginBottom: '5px' }}>{day.substring(0, 3)}</label>
                          <input 
                            type="number" 
                            step="0.5"
                            value={value} 
                            onChange={(e) => setParams({
                              ...params, 
                              safety_pp_by_weekday: {...params.safety_pp_by_weekday, [day]: Number(e.target.value)}
                            })}
                            style={{ width: '100%', padding: '8px', textAlign: 'center', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                          />
                        </div>
                      ))}
                    </div>
                  </div>

                  <button className="btn-primary" onClick={saveParams} disabled={loading}>
                    {loading ? 'Salvando...' : 'Salvar Parâmetros'}
                  </button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'forecast' && !loading && (
            <div>
              <h3>Projeção de Ocupação Ajustada</h3>
              
              {activities.length > 0 && (
                <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
                  <h4 style={{ marginTop: 0, marginBottom: '10px' }}>Atividades para Inclusão</h4>
                  <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                    <button 
                      className="btn-secondary" 
                      onClick={() => setSelectedActivityIds(activities.map(a => a.id))}
                      style={{ fontSize: '0.875rem' }}
                    >
                      Selecionar Todas
                    </button>
                    <button 
                      className="btn-secondary" 
                      onClick={() => setSelectedActivityIds([])}
                      style={{ fontSize: '0.875rem' }}
                    >
                      Limpar Seleção
                    </button>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px' }}>
                    {activities.map(activity => (
                      <label 
                        key={activity.id} 
                        style={{ 
                          display: 'flex', 
                          alignItems: 'center', 
                          padding: '8px 12px',
                          backgroundColor: selectedActivityIds.includes(activity.id) ? '#dbeafe' : '#fff',
                          borderRadius: '4px',
                          border: '1px solid #e2e8f0',
                          cursor: 'pointer'
                        }}
                      >
                        <input 
                          type="checkbox"
                          checked={selectedActivityIds.includes(activity.id)}
                          onChange={() => {
                            setSelectedActivityIds(prev => 
                              prev.includes(activity.id) 
                                ? prev.filter(id => id !== activity.id)
                                : [...prev, activity.id]
                            );
                          }}
                          style={{ marginRight: '10px' }}
                        />
                        <span>{activity.name} ({activity.code})</span>
                        {activity.is_programmed && (
                          <span style={{ marginLeft: 'auto', fontSize: '0.75rem', color: '#16a34a' }}>Programada</span>
                        )}
                      </label>
                    ))}
                  </div>
                </div>
              )}

              <button 
                onClick={runForecast}
                disabled={loading || !prerequisites?.can_generate || selectedActivityIds.length === 0}
                className="btn-primary"
                style={{ marginBottom: '20px' }}
              >
                {loading ? 'Gerando...' : 'Gerar Projeção da Semana'}
              </button>

              {forecastRun && (
                <div>
                  <div style={{ 
                    padding: '12px', 
                    backgroundColor: '#e0f2fe', 
                    borderRadius: '6px', 
                    marginBottom: '15px' 
                  }}>
                    <strong>Forecast #{forecastRun.id}</strong> | 
                    Semana: {forecastRun.horizon_start} a {forecastRun.horizon_end} |
                    Status: {forecastRun.status}
                  </div>

                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f1f5f9' }}>
                        <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Dia</th>
                        <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Data</th>
                        <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Occ Raw (%)</th>
                        <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Bias (pp)</th>
                        <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Safety (pp)</th>
                        <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold' }}>Occ Adj (%)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {forecastRun.daily_forecasts?.map((d, i) => (
                        <tr key={i}>
                          <td style={{ padding: '10px', border: '1px solid #e2e8f0' }}>{d.weekday_pt}</td>
                          <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{formatDate(d.target_date)}</td>
                          <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                            {d.occ_raw !== null ? d.occ_raw.toFixed(1) : '-'}
                          </td>
                          <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{d.bias_pp.toFixed(1)}</td>
                          <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{d.safety_pp.toFixed(1)}</td>
                          <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold', backgroundColor: '#f0fdf4' }}>
                            {d.occ_adj !== null ? d.occ_adj.toFixed(1) : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>

                  <div style={{ marginTop: '15px' }}>
                    <button 
                      onClick={computeDemand} 
                      disabled={loading || !canExecuteWorkflow()} 
                      className="btn-primary"
                    >
                      Calcular Demanda de Limpeza
                    </button>
                  </div>
                </div>
              )}

              {!forecastRun && activities.length === 0 && (
                <div style={{ padding: '20px', backgroundColor: '#fef3c7', borderRadius: '8px' }}>
                  <strong>Nenhuma atividade cadastrada para este setor.</strong>
                  <p>Cadastre atividades em Cadastros &gt; Atividades antes de gerar a projeção.</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'demand' && !loading && (
            <div>
              <h3>Demanda de Limpeza</h3>
              
              {demands.length === 0 ? (
                <div style={{ padding: '20px', backgroundColor: '#fef3c7', borderRadius: '8px' }}>
                  <strong>Nenhuma demanda calculada.</strong>
                  <p>Gere a projeção de ocupação primeiro e depois calcule a demanda.</p>
                  <button onClick={() => setActiveTab('forecast')} className="btn-secondary" style={{ marginTop: '10px' }}>
                    Ir para Projeção
                  </button>
                </div>
              ) : (
                <>
                  {demandSummary && (
                    <div style={{ 
                      display: 'grid', 
                      gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
                      gap: '15px', 
                      marginBottom: '20px',
                      padding: '15px',
                      backgroundColor: '#e0f2fe',
                      borderRadius: '8px'
                    }}>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>Total Minutos (Semana)</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{demandSummary.total_minutes_week?.toLocaleString()}</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>Min. Variáveis</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#0369a1' }}>
                          {demandSummary.total_minutes_variable_week?.toLocaleString()}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>Min. Constantes</div>
                        <div style={{ fontSize: '1.25rem', fontWeight: 'bold', color: '#7c3aed' }}>
                          {demandSummary.total_minutes_constant_week?.toLocaleString()}
                        </div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>Total Horas</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{demandSummary.total_hours_week?.toFixed(1)}</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>Headcount Total</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{demandSummary.total_headcount_week}</div>
                      </div>
                      <div style={{ textAlign: 'center' }}>
                        <div style={{ fontSize: '0.75rem', color: '#666' }}>Média Diária</div>
                        <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{demandSummary.avg_headcount_daily?.toFixed(1)}</div>
                      </div>
                    </div>
                  )}

                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                      <thead>
                        <tr style={{ backgroundColor: '#f1f5f9' }}>
                          <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Dia</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Data</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Occ (%)</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>UHs Ocup.</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Saídas</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Estadias</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', backgroundColor: '#dbeafe' }}>Min. Var.</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', backgroundColor: '#ede9fe' }}>Min. Const.</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Min. Buffer</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Horas</th>
                          <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold', backgroundColor: '#dcfce7' }}>Headcount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {demands.map((d, i) => (
                          <tr key={i}>
                            <td style={{ padding: '10px', border: '1px solid #e2e8f0' }}>{d.weekday_pt}</td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{formatDate(d.target_date)}</td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                              {d.occ_adj?.toFixed(1) || '-'}
                            </td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{d.occupied_rooms}</td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{d.departures_count}</td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{d.stayovers_estimated}</td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', backgroundColor: '#eff6ff' }}>
                              {d.minutes_variable?.toFixed(0)}
                            </td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', backgroundColor: '#f5f3ff' }}>
                              {d.minutes_constant?.toFixed(0)}
                              {d.constant_activities_count > 0 && (
                                <span style={{ fontSize: '0.7rem', color: '#7c3aed' }}> ({d.constant_activities_count})</span>
                              )}
                            </td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                              {d.minutes_required_buffered?.toFixed(0)}
                            </td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                              {d.hours_total_required?.toFixed(1)}
                            </td>
                            <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold', backgroundColor: '#f0fdf4' }}>
                              {d.headcount_rounded}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <div style={{ marginTop: '15px' }}>
                    <button 
                      onClick={generateSchedule} 
                      disabled={loading || !canExecuteWorkflow()} 
                      className="btn-primary"
                    >
                      Gerar Escala Sugerida
                    </button>
                  </div>
                </>
              )}
            </div>
          )}

          {activeTab === 'schedule' && !loading && (
            <div>
              <h3>Escala Sugerida</h3>
              
              {!schedulePlan ? (
                <div style={{ padding: '20px', backgroundColor: '#fef3c7', borderRadius: '8px' }}>
                  <strong>Nenhuma escala gerada.</strong>
                  <p>Calcule a demanda primeiro e depois gere a escala.</p>
                  <button onClick={() => setActiveTab('demand')} className="btn-secondary" style={{ marginTop: '10px' }}>
                    Ir para Demanda
                  </button>
                </div>
              ) : (
                <div>
                  <div style={{ 
                    padding: '15px', 
                    backgroundColor: '#e0f2fe', 
                    borderRadius: '8px', 
                    marginBottom: '20px' 
                  }}>
                    <strong>Plano #{schedulePlan.id}</strong> | 
                    Semana: {schedulePlan.week_start} | 
                    Status: {schedulePlan.status}
                    {schedulePlan.summary && (
                      <span> | Total Headcount: {schedulePlan.summary.total_headcount}</span>
                    )}
                  </div>

                  {schedulePlan.daily_slots && schedulePlan.daily_slots.length > 0 && (
                    <div style={{ overflowX: 'auto' }}>
                      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                          <tr style={{ backgroundColor: '#f1f5f9' }}>
                            <th style={{ padding: '10px', textAlign: 'left', border: '1px solid #e2e8f0' }}>Dia</th>
                            <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Turno</th>
                            <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Colaboradores</th>
                            <th style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>Horas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {schedulePlan.daily_slots.map((slot: any, i: number) => (
                            <tr key={i}>
                              <td style={{ padding: '10px', border: '1px solid #e2e8f0' }}>{slot.weekday_pt}</td>
                              <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{slot.shift_name}</td>
                              <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold' }}>
                                {slot.headcount}
                              </td>
                              <td style={{ padding: '10px', textAlign: 'center', border: '1px solid #e2e8f0' }}>{slot.hours}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {activeTab === 'replan' && !loading && (
            <div>
              <h3>Ajustes Diários (Replanejamento)</h3>
              
              <button onClick={loadSuggestions} className="btn-secondary" style={{ marginBottom: '15px' }}>
                Atualizar Sugestões
              </button>

              {suggestions.length === 0 ? (
                <div style={{ padding: '20px', backgroundColor: '#f0fdf4', borderRadius: '8px' }}>
                  <strong>Nenhuma sugestão de ajuste pendente.</strong>
                  <p>O sistema monitora automaticamente variações de ocupação e sugere ajustes quando necessário.</p>
                </div>
              ) : (
                <div>
                  {suggestions.map((sug, i) => (
                    <div 
                      key={i} 
                      style={{ 
                        padding: '15px', 
                        marginBottom: '10px', 
                        backgroundColor: '#fff', 
                        borderRadius: '8px',
                        border: '1px solid #e2e8f0'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div>
                          <strong>{sug.type}</strong>
                          <p style={{ margin: '5px 0', color: '#666' }}>{sug.description}</p>
                        </div>
                        <div style={{ display: 'flex', gap: '10px' }}>
                          <button className="btn-primary">Aceitar</button>
                          <button className="btn-secondary">Ignorar</button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      <style>{`
        .tabs button { transition: all 0.2s ease; }
        .tabs button:hover { background-color: #f1f5f9; }
        .btn-primary { 
          background-color: #3b82f6; 
          color: white; 
          padding: 10px 20px; 
          border: none; 
          border-radius: 6px; 
          cursor: pointer;
          font-weight: 500;
        }
        .btn-primary:hover { background-color: #2563eb; }
        .btn-primary:disabled { background-color: #94a3b8; cursor: not-allowed; }
        .btn-secondary { 
          background-color: #f1f5f9; 
          color: #334155; 
          padding: 10px 20px; 
          border: 1px solid #cbd5e1; 
          border-radius: 6px; 
          cursor: pointer;
        }
        .btn-secondary:hover { background-color: #e2e8f0; }
      `}</style>
    </div>
  );
}
