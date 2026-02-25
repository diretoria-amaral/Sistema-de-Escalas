import { useState, useEffect } from 'react';
import axios from 'axios';

interface DailyForecast {
  target_date: string;
  weekday_pt: string;
  occ_raw: number | null;
  bias_pp: number;
  safety_pp: number;
  occ_adj: number | null;
  source?: string;
}

interface ForecastRun {
  id: number;
  run_type: string;
  run_date: string;
  run_datetime: string | null;
  horizon_start: string;
  horizon_end: string;
  status: string;
  is_locked: boolean;
  locked_at: string | null;
  method_version: string;
  daily_forecasts?: DailyForecast[];
}

interface Sector {
  id: number;
  name: string;
}

interface ErrorDay {
  target_date: string;
  weekday_pt: string;
  is_past: boolean;
  has_real: boolean;
  occ_raw_forecast: number | null;
  occ_adj_forecast: number | null;
  occ_real: number | null;
  error_raw_pp: number | null;
  error_adj_pp: number | null;
}

interface ComparisonDay {
  target_date: string;
  weekday_pt: string;
  occ_raw_a: number | null;
  occ_raw_b: number | null;
  delta_raw_pp: number | null;
  occ_adj_a: number | null;
  occ_adj_b: number | null;
  delta_adj_pp: number | null;
}

interface Prerequisite {
  valid: boolean;
  message: string;
  details: any;
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

function PlanejamentoPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<'baseline' | 'update' | 'comparison'>('baseline');
  
  const [runs, setRuns] = useState<ForecastRun[]>([]);
  const [selectedBaseline, setSelectedBaseline] = useState<ForecastRun | null>(null);
  const [latestUpdate, setLatestUpdate] = useState<ForecastRun | null>(null);
  
  const [comparison, setComparison] = useState<ComparisonDay[]>([]);
  const [errors, setErrors] = useState<ErrorDay[]>([]);
  const [errorsSummary, setErrorsSummary] = useState<any>(null);
  
  const [prerequisites, setPrerequisites] = useState<Prerequisites | null>(null);
  const [loadingPrerequisites, setLoadingPrerequisites] = useState(false);
  
  const [safetyPP, setSafetyPP] = useState<Record<string, number>>({
    "SEGUNDA-FEIRA": 0,
    "TERÇA-FEIRA": 0,
    "QUARTA-FEIRA": 0,
    "QUINTA-FEIRA": 0,
    "SEXTA-FEIRA": 2,
    "SÁBADO": 3,
    "DOMINGO": 2
  });
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [scheduleResult, setScheduleResult] = useState<any>(null);

  useEffect(() => {
    fetchSectors();
  }, []);

  useEffect(() => {
    if (selectedSector) {
      fetchRuns();
      fetchPrerequisites();
    }
  }, [selectedSector]);

  const fetchPrerequisites = async () => {
    if (!selectedSector) return;
    setLoadingPrerequisites(true);
    try {
      const response = await axios.get(`/api/forecast-runs/prerequisites?sector_id=${selectedSector}`);
      setPrerequisites(response.data);
    } catch (error) {
      console.error('Error fetching prerequisites:', error);
      setPrerequisites(null);
    } finally {
      setLoadingPrerequisites(false);
    }
  };

  const fetchSectors = async () => {
    try {
      const response = await axios.get('/api/sectors/');
      setSectors(response.data);
      const govSector = response.data.find((s: Sector) => 
        s.name.toLowerCase().includes('governan')
      );
      if (govSector) {
        setSelectedSector(govSector.id);
      } else if (response.data.length > 0) {
        setSelectedSector(response.data[0].id);
      }
    } catch (error) {
      console.error('Error fetching sectors:', error);
    }
  };

  const fetchRuns = async () => {
    if (!selectedSector) return;
    try {
      const response = await axios.get(`/api/forecast-runs?sector_id=${selectedSector}&limit=20`);
      setRuns(response.data);
      
      const lockedBaseline = response.data.find((r: ForecastRun) => 
        r.run_type === 'baseline' && r.is_locked
      );
      if (lockedBaseline) {
        await fetchRunDetail(lockedBaseline.id, 'baseline');
      }
      
      const latestDailyUpdate = response.data.find((r: ForecastRun) => 
        r.run_type === 'daily_update'
      );
      if (latestDailyUpdate) {
        await fetchRunDetail(latestDailyUpdate.id, 'update');
      }
    } catch (error) {
      console.error('Error fetching runs:', error);
    }
  };

  const fetchRunDetail = async (runId: number, type: 'baseline' | 'update') => {
    try {
      const response = await axios.get(`/api/forecast-runs/${runId}`);
      if (type === 'baseline') {
        setSelectedBaseline(response.data);
      } else {
        setLatestUpdate(response.data);
      }
    } catch (error) {
      console.error('Error fetching run detail:', error);
    }
  };

  const createBaseline = async () => {
    if (!selectedSector) return;
    setLoading(true);
    setMessage('');
    try {
      const response = await axios.post('/api/forecast-runs/baseline', {
        sector_id: selectedSector,
        safety_pp_by_weekday: safetyPP,
        alpha: 0.2
      });
      setMessage(`Baseline criado com sucesso! ID: ${response.data.run_id}`);
      await fetchRuns();
      if (response.data.run_id) {
        await fetchRunDetail(response.data.run_id, 'baseline');
      }
    } catch (error: any) {
      setMessage(`Erro: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const lockBaseline = async () => {
    if (!selectedBaseline) return;
    setLoading(true);
    setMessage('');
    try {
      await axios.post(`/api/forecast-runs/${selectedBaseline.id}/lock`);
      setMessage('Baseline travado com sucesso!');
      await fetchRuns();
      await fetchRunDetail(selectedBaseline.id, 'baseline');
    } catch (error: any) {
      setMessage(`Erro: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const createDailyUpdate = async () => {
    if (!selectedSector) return;
    setLoading(true);
    setMessage('');
    try {
      const response = await axios.post('/api/forecast-runs/daily-update', {
        sector_id: selectedSector
      });
      setMessage(`Atualização criada com sucesso! ID: ${response.data.run_id}`);
      await fetchRuns();
      if (response.data.run_id) {
        await fetchRunDetail(response.data.run_id, 'update');
      }
    } catch (error: any) {
      setMessage(`Erro: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const fetchComparison = async () => {
    if (!selectedBaseline) return;
    setLoading(true);
    try {
      const response = await axios.get(`/api/forecast-runs/${selectedBaseline.id}/comparison/latest`);
      if (response.data.comparison) {
        setComparison(response.data.comparison);
      }
    } catch (error) {
      console.error('Error fetching comparison:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchErrors = async () => {
    if (!selectedBaseline) return;
    setLoading(true);
    try {
      const response = await axios.get(`/api/forecast-runs/${selectedBaseline.id}/errors`);
      setErrors(response.data.errors_by_day || []);
      setErrorsSummary(response.data.summary || null);
    } catch (error) {
      console.error('Error fetching errors:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'comparison' && selectedBaseline) {
      fetchComparison();
      fetchErrors();
    }
  }, [activeTab, selectedBaseline]);

  const generateGovernanceSchedule = async (forecastRunId: number) => {
    setLoading(true);
    setMessage('');
    setScheduleResult(null);
    try {
      const response = await axios.post(`/api/forecast-runs/${forecastRunId}/generate-governance-schedule`);
      setScheduleResult(response.data);
      setMessage(`Escala de Governança gerada com sucesso! Plan ID: ${response.data.schedule_plan_id}`);
    } catch (error: any) {
      setMessage(`Erro: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  const exportConvocations = async (forecastRunId: number) => {
    try {
      const response = await axios.get(
        `/api/forecast-runs/${forecastRunId}/convocations/export?format=csv`,
        { responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `convocacoes_fr${forecastRunId}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      setMessage('Convocações exportadas com sucesso!');
    } catch (error: any) {
      setMessage(`Erro ao exportar: ${error.response?.data?.detail || error.message}`);
    }
  };

  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr + 'T00:00:00');
    return d.toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit' });
  };

  const getDeltaColor = (delta: number | null) => {
    if (delta === null) return '';
    if (Math.abs(delta) > 5) return 'text-red-600 font-bold';
    if (Math.abs(delta) > 2) return 'text-yellow-600';
    return 'text-green-600';
  };

  return (
    <div className="card">
      <h2>Planejamento Semanal</h2>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        Baseline de sexta-feira, atualizações diárias e comparativo planejado x real.
      </p>

      <div style={{ marginBottom: '1rem' }}>
        <label style={{ marginRight: '0.5rem' }}>Setor:</label>
        <select 
          value={selectedSector || ''} 
          onChange={(e) => setSelectedSector(Number(e.target.value))}
          style={{ padding: '0.5rem', minWidth: '150px' }}
        >
          {sectors.map(s => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      </div>

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <button 
          onClick={() => setActiveTab('baseline')}
          className={activeTab === 'baseline' ? 'btn-primary' : 'btn-secondary'}
        >
          Baseline (Sexta)
        </button>
        <button 
          onClick={() => setActiveTab('update')}
          className={activeTab === 'update' ? 'btn-primary' : 'btn-secondary'}
        >
          Atualização Diária
        </button>
        <button 
          onClick={() => setActiveTab('comparison')}
          className={activeTab === 'comparison' ? 'btn-primary' : 'btn-secondary'}
        >
          Planejado x Real
        </button>
      </div>

      {message && (
        <div style={{ 
          padding: '0.75rem', 
          marginBottom: '1rem', 
          backgroundColor: message.includes('Erro') ? '#fee2e2' : '#d1fae5',
          borderRadius: '4px',
          color: message.includes('Erro') ? '#991b1b' : '#065f46'
        }}>
          {message}
        </div>
      )}

      {activeTab === 'baseline' && (
        <div>
          <h3 style={{ marginBottom: '1rem' }}>Baseline da Semana</h3>
          
          {/* Prerequisites Status Panel */}
          {loadingPrerequisites ? (
            <div style={{ padding: '1rem', marginBottom: '1rem', backgroundColor: '#f1f5f9', borderRadius: '8px' }}>
              Verificando pré-requisitos...
            </div>
          ) : prerequisites && (
            <div style={{ 
              padding: '1rem', 
              marginBottom: '1.5rem', 
              backgroundColor: prerequisites.can_generate ? '#f0fdf4' : '#fef2f2',
              border: `1px solid ${prerequisites.can_generate ? '#86efac' : '#fca5a5'}`,
              borderRadius: '8px' 
            }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: '0.75rem' }}>
                <span style={{ 
                  fontSize: '1.25rem', 
                  marginRight: '0.5rem' 
                }}>
                  {prerequisites.can_generate ? '✓' : '✗'}
                </span>
                <h4 style={{ margin: 0 }}>
                  {prerequisites.can_generate 
                    ? 'Pré-requisitos atendidos - Pronto para gerar' 
                    : 'Pré-requisitos pendentes - Geração bloqueada'}
                </h4>
              </div>
              
              <div style={{ fontSize: '0.875rem', marginBottom: '0.5rem', color: '#666' }}>
                Semana: {prerequisites.week_start} a {prerequisites.week_end}
              </div>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.5rem', marginBottom: '0.75rem' }}>
                {Object.entries(prerequisites.prerequisites).map(([key, prereq]) => (
                  <div 
                    key={key} 
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center',
                      padding: '0.5rem',
                      backgroundColor: prereq.valid ? '#dcfce7' : '#fee2e2',
                      borderRadius: '4px',
                      fontSize: '0.875rem'
                    }}
                  >
                    <span style={{ marginRight: '0.5rem', fontSize: '1rem' }}>
                      {prereq.valid ? '✓' : '✗'}
                    </span>
                    <div>
                      <strong style={{ textTransform: 'capitalize' }}>
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
                  padding: '0.75rem', 
                  backgroundColor: '#fee2e2', 
                  borderRadius: '4px',
                  marginBottom: '0.5rem'
                }}>
                  <strong style={{ color: '#991b1b' }}>Erros bloqueantes:</strong>
                  <ul style={{ margin: '0.5rem 0 0 1rem', padding: 0, color: '#991b1b' }}>
                    {prerequisites.blocking_errors.map((err, i) => (
                      <li key={i} style={{ marginBottom: '0.25rem' }}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
              
              {prerequisites.warnings.length > 0 && (
                <div style={{ 
                  padding: '0.75rem', 
                  backgroundColor: '#fef3c7', 
                  borderRadius: '4px' 
                }}>
                  <strong style={{ color: '#92400e' }}>Avisos:</strong>
                  <ul style={{ margin: '0.5rem 0 0 1rem', padding: 0, color: '#92400e' }}>
                    {prerequisites.warnings.map((warn, i) => (
                      <li key={i} style={{ marginBottom: '0.25rem' }}>{warn}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          
          <div style={{ marginBottom: '1.5rem', padding: '1rem', backgroundColor: '#f8fafc', borderRadius: '8px' }}>
            <h4 style={{ marginBottom: '0.75rem' }}>Margem de Segurança por Dia (pp)</h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '0.5rem' }}>
              {Object.entries(safetyPP).map(([day, value]) => (
                <div key={day} style={{ textAlign: 'center' }}>
                  <label style={{ fontSize: '0.75rem', display: 'block' }}>
                    {day.substring(0, 3)}
                  </label>
                  <input
                    type="number"
                    value={value}
                    onChange={(e) => setSafetyPP({...safetyPP, [day]: Number(e.target.value)})}
                    style={{ width: '50px', padding: '0.25rem', textAlign: 'center' }}
                    step="0.5"
                    min="0"
                    max="10"
                  />
                </div>
              ))}
            </div>
          </div>

          <button 
            onClick={createBaseline} 
            disabled={loading || (prerequisites && !prerequisites.can_generate)}
            className="btn-primary"
            style={{ marginRight: '0.5rem' }}
            title={prerequisites && !prerequisites.can_generate ? 'Pré-requisitos não atendidos' : ''}
          >
            {loading ? 'Gerando...' : 'Gerar Baseline da Próxima Semana'}
          </button>
          
          <button
            onClick={fetchPrerequisites}
            disabled={loadingPrerequisites}
            className="btn-secondary"
            style={{ marginLeft: '0.5rem' }}
          >
            {loadingPrerequisites ? 'Verificando...' : 'Atualizar Status'}
          </button>

          {selectedBaseline && (
            <div style={{ marginTop: '1.5rem' }}>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'space-between',
                marginBottom: '1rem',
                padding: '0.75rem',
                backgroundColor: selectedBaseline.is_locked ? '#d1fae5' : '#fef3c7',
                borderRadius: '4px'
              }}>
                <div>
                  <strong>
                    {selectedBaseline.is_locked ? 'Baseline Oficial' : 'Baseline (não travado)'}
                  </strong>
                  <span style={{ marginLeft: '1rem', fontSize: '0.875rem', color: '#666' }}>
                    {selectedBaseline.horizon_start} a {selectedBaseline.horizon_end}
                  </span>
                  {selectedBaseline.locked_at && (
                    <span style={{ marginLeft: '1rem', fontSize: '0.75rem', color: '#666' }}>
                      Travado em: {new Date(selectedBaseline.locked_at).toLocaleString('pt-BR')}
                    </span>
                  )}
                </div>
                {!selectedBaseline.is_locked && (
                  <button onClick={lockBaseline} disabled={loading} className="btn-secondary">
                    Travar Baseline
                  </button>
                )}
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f1f5f9' }}>
                    <th style={{ padding: '0.5rem', textAlign: 'left', border: '1px solid #e2e8f0' }}>Dia</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Data</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Occ Raw (%)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Bias (pp)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Safety (pp)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Occ Adj (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedBaseline.daily_forecasts?.map((d, i) => (
                    <tr key={i}>
                      <td style={{ padding: '0.5rem', border: '1px solid #e2e8f0' }}>{d.weekday_pt}</td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {formatDate(d.target_date)}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {d.occ_raw !== null ? d.occ_raw.toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {d.bias_pp.toFixed(1)}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {d.safety_pp.toFixed(1)}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold' }}>
                        {d.occ_adj !== null ? d.occ_adj.toFixed(1) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: '#666' }}>
                Método: {selectedBaseline.method_version} | EWMA alpha: 0.2
              </div>

              <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button 
                  onClick={() => generateGovernanceSchedule(selectedBaseline.id)}
                  disabled={loading}
                  className="btn-primary"
                >
                  {loading ? 'Gerando...' : 'Gerar Escala Governança'}
                </button>
                {scheduleResult && scheduleResult.schedule_plan_id && (
                  <button
                    onClick={() => exportConvocations(selectedBaseline.id)}
                    className="btn-secondary"
                  >
                    Exportar Convocações (CSV)
                  </button>
                )}
              </div>

              {scheduleResult && (
                <div style={{ marginTop: '1rem', padding: '1rem', backgroundColor: '#f0f9ff', borderRadius: '8px' }}>
                  <h4 style={{ marginBottom: '0.5rem' }}>Escala Gerada - Plan #{scheduleResult.schedule_plan_id}</h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                    <div style={{ textAlign: 'center', padding: '0.5rem', backgroundColor: '#dbeafe', borderRadius: '4px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>Total Headcount</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{scheduleResult.schedule_summary?.total_headcount}</div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '0.5rem', backgroundColor: '#dbeafe', borderRadius: '4px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>Total Horas</div>
                      <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>{scheduleResult.schedule_summary?.total_hours?.toFixed(1)}</div>
                    </div>
                    <div style={{ textAlign: 'center', padding: '0.5rem', backgroundColor: '#dbeafe', borderRadius: '4px' }}>
                      <div style={{ fontSize: '0.75rem', color: '#666' }}>Status</div>
                      <div style={{ fontSize: '1rem', fontWeight: 'bold' }}>{scheduleResult.schedule_summary?.status?.toUpperCase()}</div>
                    </div>
                  </div>
                  
                  <h5>Demanda por Dia</h5>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#e0f2fe' }}>
                        <th style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>Dia</th>
                        <th style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>Occ%</th>
                        <th style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>Quartos</th>
                        <th style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>Saídas</th>
                        <th style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>Estadias</th>
                        <th style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>Horas</th>
                        <th style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>Headcount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scheduleResult.daily_demands?.map((d: any, i: number) => (
                        <tr key={i}>
                          <td style={{ padding: '0.4rem', border: '1px solid #bae6fd' }}>{d.weekday_pt?.substring(0, 3)}</td>
                          <td style={{ padding: '0.4rem', textAlign: 'center', border: '1px solid #bae6fd' }}>{d.occ_adj?.toFixed(0)}</td>
                          <td style={{ padding: '0.4rem', textAlign: 'center', border: '1px solid #bae6fd' }}>{d.occupied_rooms}</td>
                          <td style={{ padding: '0.4rem', textAlign: 'center', border: '1px solid #bae6fd' }}>{d.departures_count}</td>
                          <td style={{ padding: '0.4rem', textAlign: 'center', border: '1px solid #bae6fd' }}>{d.stayovers_estimated}</td>
                          <td style={{ padding: '0.4rem', textAlign: 'center', border: '1px solid #bae6fd' }}>{d.hours_total_required?.toFixed(1)}</td>
                          <td style={{ padding: '0.4rem', textAlign: 'center', border: '1px solid #bae6fd', fontWeight: 'bold' }}>{d.headcount_rounded}</td>
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

      {activeTab === 'update' && (
        <div>
          <h3 style={{ marginBottom: '1rem' }}>Atualização Diária</h3>
          
          <button 
            onClick={createDailyUpdate} 
            disabled={loading}
            className="btn-primary"
          >
            {loading ? 'Gerando...' : 'Gerar Atualização de Hoje'}
          </button>

          {latestUpdate && (
            <div style={{ marginTop: '1.5rem' }}>
              <div style={{ 
                marginBottom: '1rem',
                padding: '0.75rem',
                backgroundColor: '#e0f2fe',
                borderRadius: '4px'
              }}>
                <strong>Última Atualização</strong>
                <span style={{ marginLeft: '1rem', fontSize: '0.875rem' }}>
                  {latestUpdate.run_datetime ? new Date(latestUpdate.run_datetime).toLocaleString('pt-BR') : latestUpdate.run_date}
                </span>
                <span style={{ marginLeft: '1rem', fontSize: '0.875rem', color: '#666' }}>
                  Semana: {latestUpdate.horizon_start} a {latestUpdate.horizon_end}
                </span>
              </div>

              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f1f5f9' }}>
                    <th style={{ padding: '0.5rem', textAlign: 'left', border: '1px solid #e2e8f0' }}>Dia</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Data</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Occ Raw (%)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Occ Adj (%)</th>
                  </tr>
                </thead>
                <tbody>
                  {latestUpdate.daily_forecasts?.map((d, i) => (
                    <tr key={i}>
                      <td style={{ padding: '0.5rem', border: '1px solid #e2e8f0' }}>{d.weekday_pt}</td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {formatDate(d.target_date)}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {d.occ_raw !== null ? d.occ_raw.toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0', fontWeight: 'bold' }}>
                        {d.occ_adj !== null ? d.occ_adj.toFixed(1) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ marginTop: '1rem' }}>
                <button 
                  onClick={() => generateGovernanceSchedule(latestUpdate.id)}
                  disabled={loading}
                  className="btn-primary"
                >
                  {loading ? 'Gerando...' : 'Gerar Escala Governança (Update)'}
                </button>
              </div>
            </div>
          )}

          {comparison.length > 0 && selectedBaseline && (
            <div style={{ marginTop: '1.5rem' }}>
              <h4>Comparativo: Baseline vs Atualização</h4>
              <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '0.5rem' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f1f5f9' }}>
                    <th style={{ padding: '0.5rem', textAlign: 'left', border: '1px solid #e2e8f0' }}>Dia</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Baseline (%)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Update (%)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Delta (pp)</th>
                  </tr>
                </thead>
                <tbody>
                  {comparison.map((c, i) => (
                    <tr key={i}>
                      <td style={{ padding: '0.5rem', border: '1px solid #e2e8f0' }}>{c.weekday_pt}</td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {c.occ_adj_a !== null ? c.occ_adj_a.toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {c.occ_adj_b !== null ? c.occ_adj_b.toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}
                          className={getDeltaColor(c.delta_adj_pp)}>
                        {c.delta_adj_pp !== null ? (c.delta_adj_pp > 0 ? '+' : '') + c.delta_adj_pp.toFixed(1) : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {activeTab === 'comparison' && (
        <div>
          <h3 style={{ marginBottom: '1rem' }}>Planejado x Real</h3>
          
          {!selectedBaseline && (
            <p style={{ color: '#666' }}>Selecione ou crie um baseline primeiro.</p>
          )}

          {selectedBaseline && errors.length > 0 && (
            <>
              {errorsSummary && (
                <div style={{ 
                  display: 'grid', 
                  gridTemplateColumns: 'repeat(3, 1fr)', 
                  gap: '1rem', 
                  marginBottom: '1.5rem' 
                }}>
                  <div style={{ padding: '1rem', backgroundColor: '#f8fafc', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: '#666' }}>Dias com Real</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                      {errorsSummary.days_with_real} / {errorsSummary.days_total}
                    </div>
                  </div>
                  <div style={{ padding: '1rem', backgroundColor: '#f8fafc', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: '#666' }}>Erro Médio Raw (pp)</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                      {errorsSummary.avg_error_raw_pp !== null ? errorsSummary.avg_error_raw_pp.toFixed(1) : '-'}
                    </div>
                  </div>
                  <div style={{ padding: '1rem', backgroundColor: '#f8fafc', borderRadius: '8px', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.75rem', color: '#666' }}>Erro Médio Adj (pp)</div>
                    <div style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>
                      {errorsSummary.avg_error_adj_pp !== null ? errorsSummary.avg_error_adj_pp.toFixed(1) : '-'}
                    </div>
                  </div>
                </div>
              )}

              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f1f5f9' }}>
                    <th style={{ padding: '0.5rem', textAlign: 'left', border: '1px solid #e2e8f0' }}>Dia</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Data</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Forecast (%)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Real (%)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Erro (pp)</th>
                    <th style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {errors.map((e, i) => (
                    <tr key={i} style={{ opacity: e.is_past ? 1 : 0.5 }}>
                      <td style={{ padding: '0.5rem', border: '1px solid #e2e8f0' }}>{e.weekday_pt}</td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {formatDate(e.target_date)}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {e.occ_adj_forecast !== null ? e.occ_adj_forecast.toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {e.occ_real !== null ? e.occ_real.toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}
                          className={getDeltaColor(e.error_adj_pp)}>
                        {e.error_adj_pp !== null ? (e.error_adj_pp > 0 ? '+' : '') + e.error_adj_pp.toFixed(1) : '-'}
                      </td>
                      <td style={{ padding: '0.5rem', textAlign: 'center', border: '1px solid #e2e8f0' }}>
                        {!e.is_past ? (
                          <span style={{ color: '#666', fontSize: '0.75rem' }}>Futuro</span>
                        ) : e.has_real ? (
                          <span style={{ color: '#059669', fontSize: '0.75rem' }}>Consolidado</span>
                        ) : (
                          <span style={{ color: '#d97706', fontSize: '0.75rem' }}>Sem real</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {selectedBaseline && errors.length === 0 && (
            <p style={{ color: '#666' }}>Nenhum dado de erro disponível ainda.</p>
          )}
        </div>
      )}

      <div style={{ marginTop: '2rem', padding: '1rem', backgroundColor: '#f1f5f9', borderRadius: '8px' }}>
        <h4>Histórico de Runs</h4>
        {runs.length === 0 ? (
          <p style={{ color: '#666', marginTop: '0.5rem' }}>Nenhum forecast run encontrado.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '0.5rem' }}>
            <thead>
              <tr>
                <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>ID</th>
                <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>Tipo</th>
                <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>Data</th>
                <th style={{ padding: '0.5rem', textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>Semana</th>
                <th style={{ padding: '0.5rem', textAlign: 'center', borderBottom: '1px solid #e2e8f0' }}>Locked</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 10).map(r => (
                <tr key={r.id} style={{ cursor: 'pointer' }} 
                    onClick={() => fetchRunDetail(r.id, r.run_type === 'baseline' ? 'baseline' : 'update')}>
                  <td style={{ padding: '0.5rem', borderBottom: '1px solid #e2e8f0' }}>{r.id}</td>
                  <td style={{ padding: '0.5rem', borderBottom: '1px solid #e2e8f0' }}>
                    <span style={{ 
                      padding: '0.125rem 0.5rem', 
                      borderRadius: '4px',
                      fontSize: '0.75rem',
                      backgroundColor: r.run_type === 'baseline' ? '#dbeafe' : '#fef3c7'
                    }}>
                      {r.run_type.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '0.5rem', borderBottom: '1px solid #e2e8f0' }}>{r.run_date}</td>
                  <td style={{ padding: '0.5rem', borderBottom: '1px solid #e2e8f0' }}>
                    {r.horizon_start} a {r.horizon_end}
                  </td>
                  <td style={{ padding: '0.5rem', textAlign: 'center', borderBottom: '1px solid #e2e8f0' }}>
                    {r.is_locked ? 'Sim' : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default PlanejamentoPage;
