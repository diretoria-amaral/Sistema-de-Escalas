import { useState, useEffect } from 'react';
import { rulesApi, sectorsApi, LaborRules, SectorOperationalRules, Sector } from '../services/client';

interface RulesPageProps {
  defaultTab?: 'labor' | 'operational';
}

function RulesPage({ defaultTab = 'labor' }: RulesPageProps) {
  const [activeTab, setActiveTab] = useState<'labor' | 'operational'>(defaultTab);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);

  const [laborRules, setLaborRules] = useState<LaborRules | null>(null);
  const [operationalRules, setOperationalRules] = useState<SectorOperationalRules | null>(null);

  useEffect(() => {
    setActiveTab(defaultTab);
  }, [defaultTab]);

  useEffect(() => {
    loadSectors();
    loadLaborRules();
  }, []);

  useEffect(() => {
    if (selectedSector && activeTab === 'operational') {
      loadOperationalRules();
    }
  }, [selectedSector, activeTab]);

  const loadSectors = async () => {
    try {
      const res = await sectorsApi.list();
      setSectors(res.data);
      if (res.data.length > 0) {
        setSelectedSector(res.data[0].id);
      }
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar setores' });
    }
  };

  const loadLaborRules = async () => {
    try {
      setLoading(true);
      const res = await rulesApi.getLaborRules();
      setLaborRules(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar regras trabalhistas' });
    } finally {
      setLoading(false);
    }
  };

  const loadOperationalRules = async () => {
    if (!selectedSector) return;
    try {
      setLoading(true);
      const res = await rulesApi.getOperationalRules(selectedSector);
      setOperationalRules(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar regras operacionais' });
    } finally {
      setLoading(false);
    }
  };

  const saveLaborRules = async () => {
    if (!laborRules) return;
    try {
      setSaving(true);
      await rulesApi.updateLaborRules(laborRules);
      setMessage({ type: 'success', text: 'Regras trabalhistas salvas!' });
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao salvar' });
    } finally {
      setSaving(false);
    }
  };

  const saveOperationalRules = async () => {
    if (!operationalRules || !selectedSector) return;
    try {
      setSaving(true);
      await rulesApi.updateOperationalRules(selectedSector, operationalRules);
      setMessage({ type: 'success', text: 'Regras operacionais salvas!' });
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao salvar' });
    } finally {
      setSaving(false);
    }
  };

  const getSectorName = (id: number) => {
    return sectors.find(s => s.id === id)?.name || '';
  };

  return (
    <div className="card">
      <h2>Regras do Sistema</h2>
      <p style={{ color: '#666', marginBottom: '1rem' }}>
        Configure as regras trabalhistas globais e operacionais por setor.
      </p>

      {message && (
        <div className={`alert alert-${message.type}`} style={{ marginBottom: '1rem' }}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
        </div>
      )}

      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <button 
          onClick={() => setActiveTab('labor')}
          className={activeTab === 'labor' ? 'btn-primary' : 'btn-secondary'}
        >
          Regras Trabalhistas (Global)
        </button>
        <button 
          onClick={() => setActiveTab('operational')}
          className={activeTab === 'operational' ? 'btn-primary' : 'btn-secondary'}
        >
          Regras Operacionais (por Setor)
        </button>
      </div>

      {activeTab === 'labor' && (
        <div>
          <h3 style={{ marginBottom: '1rem' }}>Regras Trabalhistas Globais</h3>
          <p style={{ color: '#666', marginBottom: '1rem', fontSize: '0.875rem' }}>
            Estas regras se aplicam a todos os setores e colaboradores.
          </p>

          {loading ? (
            <div>Carregando...</div>
          ) : laborRules && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group">
                  <label>Antecedencia Minima Convocacao (horas)</label>
                  <input 
                    type="number" 
                    value={laborRules.min_notice_hours}
                    onChange={e => setLaborRules({...laborRules, min_notice_hours: Number(e.target.value)})}
                  />
                </div>
                <div className="form-group">
                  <label>Limite Horas Semanais</label>
                  <input 
                    type="number" 
                    value={laborRules.max_week_hours}
                    onChange={e => setLaborRules({...laborRules, max_week_hours: Number(e.target.value)})}
                  />
                </div>
                <div className="form-group">
                  <label>Limite Horas Semanais c/ Extra</label>
                  <input 
                    type="number" 
                    value={laborRules.max_week_hours_with_overtime}
                    onChange={e => setLaborRules({...laborRules, max_week_hours_with_overtime: Number(e.target.value)})}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group">
                  <label>Limite Horas Diarias</label>
                  <input 
                    type="number" 
                    value={laborRules.max_daily_hours}
                    onChange={e => setLaborRules({...laborRules, max_daily_hours: Number(e.target.value)})}
                  />
                </div>
                <div className="form-group">
                  <label>Descanso Minimo Entre Turnos (h)</label>
                  <input 
                    type="number" 
                    value={laborRules.min_rest_hours_between_shifts}
                    onChange={e => setLaborRules({...laborRules, min_rest_hours_between_shifts: Number(e.target.value)})}
                  />
                </div>
                <div className="form-group">
                  <label>Dias Consecutivos Max Trabalho</label>
                  <input 
                    type="number" 
                    value={laborRules.max_consecutive_work_days}
                    onChange={e => setLaborRules({...laborRules, max_consecutive_work_days: Number(e.target.value)})}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group">
                  <label>Intervalo Min Intrajornada (h)</label>
                  <input 
                    type="number" 
                    value={laborRules.min_break_hours}
                    onChange={e => setLaborRules({...laborRules, min_break_hours: Number(e.target.value)})}
                    step="0.5"
                  />
                </div>
                <div className="form-group">
                  <label>Intervalo Max Intrajornada (h)</label>
                  <input 
                    type="number" 
                    value={laborRules.max_break_hours}
                    onChange={e => setLaborRules({...laborRules, max_break_hours: Number(e.target.value)})}
                    step="0.5"
                  />
                </div>
                <div className="form-group">
                  <label>Jornada Dispensa Intervalo (h)</label>
                  <input 
                    type="number" 
                    value={laborRules.no_break_threshold_hours}
                    onChange={e => setLaborRules({...laborRules, no_break_threshold_hours: Number(e.target.value)})}
                    step="0.5"
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group">
                  <label>Domingos Folga por Mes</label>
                  <input 
                    type="number" 
                    value={laborRules.sundays_off_per_month}
                    onChange={e => setLaborRules({...laborRules, sundays_off_per_month: Number(e.target.value)})}
                  />
                </div>
                <div className="form-group">
                  <label>Dias Ferias Anuais</label>
                  <input 
                    type="number" 
                    value={laborRules.vacation_days_annual}
                    onChange={e => setLaborRules({...laborRules, vacation_days_annual: Number(e.target.value)})}
                  />
                </div>
                <div className="form-group" style={{ display: 'flex', alignItems: 'center', paddingTop: '1.5rem' }}>
                  <label>
                    <input 
                      type="checkbox" 
                      checked={laborRules.allow_vacation_split}
                      onChange={e => setLaborRules({...laborRules, allow_vacation_split: e.target.checked})}
                      style={{ marginRight: '0.5rem' }}
                    />
                    Permite Fracionamento Ferias
                  </label>
                </div>
              </div>

              <div className="form-group" style={{ marginBottom: '1.5rem' }}>
                <label>
                  <input 
                    type="checkbox" 
                    checked={laborRules.respect_cbo_activities}
                    onChange={e => setLaborRules({...laborRules, respect_cbo_activities: e.target.checked})}
                    style={{ marginRight: '0.5rem' }}
                  />
                  Respeitar CBO nas Atividades
                </label>
              </div>

              <button 
                onClick={saveLaborRules} 
                disabled={saving}
                className="btn-primary"
              >
                {saving ? 'Salvando...' : 'Salvar Regras Trabalhistas'}
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'operational' && (
        <div>
          <h3 style={{ marginBottom: '1rem' }}>Regras Operacionais por Setor</h3>
          
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
            {sectors.map(sector => (
              <button
                key={sector.id}
                onClick={() => setSelectedSector(sector.id)}
                className={selectedSector === sector.id ? 'btn-primary' : 'btn-secondary'}
                style={{ minWidth: '120px' }}
              >
                {sector.name}
              </button>
            ))}
          </div>

          {selectedSector && (
            <div style={{ 
              padding: '1rem', 
              backgroundColor: '#f8fafc', 
              borderRadius: '8px',
              marginBottom: '1rem'
            }}>
              <strong>Configurando: {getSectorName(selectedSector)}</strong>
            </div>
          )}

          {loading ? (
            <div>Carregando...</div>
          ) : operationalRules && (
            <div>
              <h4 style={{ marginBottom: '1rem' }}>Metas e Buffers</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group">
                  <label>Meta Aproveitamento (%)</label>
                  <input 
                    type="number" 
                    value={operationalRules.utilization_target_pct}
                    onChange={e => setOperationalRules({...operationalRules, utilization_target_pct: Number(e.target.value)})}
                    step="1"
                    min="0"
                    max="100"
                  />
                </div>
                <div className="form-group">
                  <label>Buffer de Seguranca (%)</label>
                  <input 
                    type="number" 
                    value={operationalRules.buffer_pct}
                    onChange={e => setOperationalRules({...operationalRules, buffer_pct: Number(e.target.value)})}
                    step="1"
                    min="0"
                    max="50"
                  />
                </div>
              </div>

              <h4 style={{ marginBottom: '1rem' }}>Regime de Trabalho</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group">
                  <label>Regime Preferencial</label>
                  <select 
                    value={operationalRules.regime_preferencial}
                    onChange={e => setOperationalRules({...operationalRules, regime_preferencial: e.target.value})}
                  >
                    <option value="5x2">5x2 (5 dias, 2 folgas)</option>
                    <option value="6x1">6x1 (6 dias, 1 folga)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Dias Folga por Semana</label>
                  <input 
                    type="number" 
                    value={operationalRules.dias_folga_semana}
                    onChange={e => setOperationalRules({...operationalRules, dias_folga_semana: Number(e.target.value)})}
                    min="1"
                    max="3"
                  />
                </div>
                <div className="form-group">
                  <label>Intervalo Semanas Folga</label>
                  <input 
                    type="number" 
                    value={operationalRules.intervalo_semanas_folga}
                    onChange={e => setOperationalRules({...operationalRules, intervalo_semanas_folga: Number(e.target.value)})}
                    min="1"
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group" style={{ display: 'flex', alignItems: 'center' }}>
                  <label>
                    <input 
                      type="checkbox" 
                      checked={operationalRules.permitir_alternar_regime}
                      onChange={e => setOperationalRules({...operationalRules, permitir_alternar_regime: e.target.checked})}
                      style={{ marginRight: '0.5rem' }}
                    />
                    Permitir Alternar Regime
                  </label>
                </div>
                <div className="form-group" style={{ display: 'flex', alignItems: 'center' }}>
                  <label>
                    <input 
                      type="checkbox" 
                      checked={operationalRules.folgas_consecutivas}
                      onChange={e => setOperationalRules({...operationalRules, folgas_consecutivas: e.target.checked})}
                      style={{ marginRight: '0.5rem' }}
                    />
                    Folgas Consecutivas
                  </label>
                </div>
                <div className="form-group" style={{ display: 'flex', alignItems: 'center' }}>
                  <label>
                    <input 
                      type="checkbox" 
                      checked={operationalRules.modo_conservador}
                      onChange={e => setOperationalRules({...operationalRules, modo_conservador: e.target.checked})}
                      style={{ marginRight: '0.5rem' }}
                    />
                    Modo Conservador
                  </label>
                </div>
              </div>

              <h4 style={{ marginBottom: '1rem' }}>Alternancia e Repeticao</h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group" style={{ display: 'flex', alignItems: 'center' }}>
                  <label>
                    <input 
                      type="checkbox" 
                      checked={operationalRules.alternancia_horarios}
                      onChange={e => setOperationalRules({...operationalRules, alternancia_horarios: e.target.checked})}
                      style={{ marginRight: '0.5rem' }}
                    />
                    Alternancia de Horarios
                  </label>
                </div>
                <div className="form-group" style={{ display: 'flex', alignItems: 'center' }}>
                  <label>
                    <input 
                      type="checkbox" 
                      checked={operationalRules.alternancia_atividades}
                      onChange={e => setOperationalRules({...operationalRules, alternancia_atividades: e.target.checked})}
                      style={{ marginRight: '0.5rem' }}
                    />
                    Alternancia de Atividades
                  </label>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
                <div className="form-group">
                  <label>% Max Repeticao Turno</label>
                  <input 
                    type="number" 
                    value={operationalRules.percentual_max_repeticao_turno}
                    onChange={e => setOperationalRules({...operationalRules, percentual_max_repeticao_turno: Number(e.target.value)})}
                    min="0"
                    max="100"
                  />
                </div>
                <div className="form-group">
                  <label>% Max Repeticao Dia/Turno</label>
                  <input 
                    type="number" 
                    value={operationalRules.percentual_max_repeticao_dia_turno}
                    onChange={e => setOperationalRules({...operationalRules, percentual_max_repeticao_dia_turno: Number(e.target.value)})}
                    min="0"
                    max="100"
                  />
                </div>
              </div>

              <button 
                onClick={saveOperationalRules} 
                disabled={saving}
                className="btn-primary"
              >
                {saving ? 'Salvando...' : `Salvar Regras de ${selectedSector ? getSectorName(selectedSector) : ''}`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default RulesPage;
