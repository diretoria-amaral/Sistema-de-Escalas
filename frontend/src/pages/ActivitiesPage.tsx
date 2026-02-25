import { useState, useEffect } from 'react';
import { activitiesApi, sectorsApi, GovernanceActivity, Sector } from '../services/client';

type ActivityClassification = 'CALCULADA_PELO_AGENTE' | 'RECORRENTE' | 'EVENTUAL';
type WorkloadDriver = 'VARIABLE' | 'CONSTANT';

interface Periodicity {
  id: number;
  name: string;
  tipo: string;
  intervalo_dias: number;
  is_active: boolean;
}

const classificationLabels: Record<ActivityClassification, string> = {
  CALCULADA_PELO_AGENTE: 'Calculada pelo Agente',
  RECORRENTE: 'Recorrente',
  EVENTUAL: 'Eventual'
};

const workloadLabels: Record<WorkloadDriver, string> = {
  VARIABLE: 'Variavel (ocupacao)',
  CONSTANT: 'Constante (fixa)'
};

function ActivitiesPage() {
  const [activities, setActivities] = useState<GovernanceActivity[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [periodicities, setPeriodicities] = useState<Periodicity[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingActivity, setEditingActivity] = useState<GovernanceActivity | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);

  const [form, setForm] = useState({
    name: '',
    code: '',
    description: '',
    average_time_minutes: 15,
    unit_type: '',
    workload_driver: 'VARIABLE' as WorkloadDriver,
    classificacao_atividade: 'CALCULADA_PELO_AGENTE' as ActivityClassification,
    periodicidade_id: null as number | null,
    tolerancia_dias: null as number | null,
    data_primeira_execucao: null as string | null,
    difficulty_level: 1,
    requires_training: false,
    sector_id: 0,
  });

  useEffect(() => {
    loadSectors();
    loadPeriodicities();
  }, []);

  useEffect(() => {
    if (selectedSector) {
      loadActivities();
    }
  }, [selectedSector]);

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

  const loadPeriodicities = async () => {
    try {
      const res = await fetch('/api/periodicities/?active_only=true');
      if (res.ok) {
        const data = await res.json();
        setPeriodicities(data);
      }
    } catch {
      console.error('Erro ao carregar periodicidades');
    }
  };

  const loadActivities = async () => {
    try {
      setLoading(true);
      const res = await activitiesApi.list(selectedSector || undefined);
      setActivities(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar atividades' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!form.sector_id) {
      setMessage({ type: 'error', text: 'Setor e obrigatorio para criar atividade' });
      return;
    }
    
    try {
      const submitData = {
        ...form,
        sector_id: form.sector_id,
      };

      if (editingActivity) {
        await activitiesApi.update(editingActivity.id, submitData);
        setMessage({ type: 'success', text: 'Atividade atualizada!' });
      } else {
        await activitiesApi.create(submitData);
        setMessage({ type: 'success', text: 'Atividade cadastrada!' });
      }
      setShowModal(false);
      resetForm();
      loadActivities();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao salvar atividade' });
    }
  };

  const handleEdit = (activity: GovernanceActivity) => {
    setEditingActivity(activity);
    setForm({
      name: activity.name,
      code: activity.code,
      description: activity.description || '',
      average_time_minutes: activity.average_time_minutes,
      unit_type: activity.unit_type || '',
      workload_driver: (activity as any).workload_driver || 'VARIABLE',
      classificacao_atividade: (activity as any).classificacao_atividade || 'CALCULADA_PELO_AGENTE',
      periodicidade_id: (activity as any).periodicidade_id || null,
      tolerancia_dias: (activity as any).tolerancia_dias || null,
      data_primeira_execucao: (activity as any).data_primeira_execucao || null,
      difficulty_level: activity.difficulty_level,
      requires_training: activity.requires_training,
      sector_id: activity.sector_id || selectedSector || 0,
    });
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Excluir esta atividade?')) return;
    try {
      await activitiesApi.delete(id);
      setMessage({ type: 'success', text: 'Atividade excluida!' });
      loadActivities();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao excluir' });
    }
  };

  const resetForm = () => {
    setEditingActivity(null);
    setForm({
      name: '',
      code: '',
      description: '',
      average_time_minutes: 15,
      unit_type: '',
      workload_driver: 'VARIABLE',
      classificacao_atividade: 'CALCULADA_PELO_AGENTE',
      periodicidade_id: null,
      tolerancia_dias: null,
      data_primeira_execucao: null,
      difficulty_level: 1,
      requires_training: false,
      sector_id: selectedSector || 0,
    });
  };

  const handleClassificationChange = (value: ActivityClassification) => {
    if (value === 'RECORRENTE') {
      setForm({
        ...form,
        classificacao_atividade: value,
      });
    } else {
      setForm({
        ...form,
        classificacao_atividade: value,
        periodicidade_id: null,
        tolerancia_dias: null,
        data_primeira_execucao: null,
      });
    }
  };

  const getSelectedPeriodicityTipo = () => {
    if (!form.periodicidade_id) return null;
    const periodicity = periodicities.find(p => p.id === form.periodicidade_id);
    return periodicity?.tipo || null;
  };

  const openNewModal = () => {
    resetForm();
    setShowModal(true);
  };

  return (
    <div>
      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
          <h2>Atividades por Setor</h2>
          <button className="btn btn-primary" onClick={openNewModal}>
            + Nova Atividade
          </button>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ marginRight: '0.5rem' }}>Setor:</label>
          <select 
            value={selectedSector || ''} 
            onChange={(e) => setSelectedSector(Number(e.target.value))}
            style={{ padding: '0.5rem', minWidth: '200px' }}
          >
            {sectors.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <div className="loading">Carregando...</div>
        ) : activities.length === 0 ? (
          <div className="empty-state">Nenhuma atividade cadastrada para este setor</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Codigo</th>
                <th>Nome</th>
                <th>Setor</th>
                <th>Classificacao</th>
                <th>Driver</th>
                <th>Tempo Medio</th>
                <th>Acoes</th>
              </tr>
            </thead>
            <tbody>
              {activities.map(act => {
                const classificacao = (act as any).classificacao_atividade || 'CALCULADA_PELO_AGENTE';
                const driver = (act as any).workload_driver || 'VARIABLE';
                const periodicity = periodicities.find(p => p.id === (act as any).periodicidade_id);
                return (
                  <tr key={act.id}>
                    <td><code>{act.code}</code></td>
                    <td>{act.name}</td>
                    <td>{act.sector_name || '-'}</td>
                    <td>
                      <span className={`badge ${classificacao === 'CALCULADA_PELO_AGENTE' ? 'badge-primary' : classificacao === 'RECORRENTE' ? 'badge-info' : 'badge-secondary'}`}>
                        {classificationLabels[classificacao as ActivityClassification]}
                      </span>
                      {periodicity && <div className="text-xs text-gray-500">{periodicity.name}</div>}
                    </td>
                    <td>
                      <span className={`badge ${driver === 'VARIABLE' ? 'badge-warning' : 'badge-success'}`}>
                        {workloadLabels[driver as WorkloadDriver]}
                      </span>
                    </td>
                    <td>{act.average_time_minutes} min</td>
                    <td className="actions">
                      <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(act)}>Editar</button>
                      <button className="btn btn-danger btn-sm" onClick={() => handleDelete(act.id)}>Excluir</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>{editingActivity ? 'Editar Atividade' : 'Nova Atividade'}</h3>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Setor * (obrigatorio)</label>
                <select 
                  value={form.sector_id || ''} 
                  onChange={e => setForm({...form, sector_id: Number(e.target.value)})}
                  required
                  style={{ borderColor: !form.sector_id ? '#dc3545' : undefined }}
                >
                  <option value="">Selecione o setor</option>
                  {sectors.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
                {!form.sector_id && (
                  <small style={{ color: '#dc3545' }}>Setor e obrigatorio para criar atividade</small>
                )}
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Nome *</label>
                  <input 
                    type="text" 
                    value={form.name} 
                    onChange={e => setForm({...form, name: e.target.value})}
                    placeholder="Ex: Limpeza Vago Sujo"
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Codigo *</label>
                  <input 
                    type="text" 
                    value={form.code} 
                    onChange={e => setForm({...form, code: e.target.value.toUpperCase()})}
                    placeholder="Ex: LVS"
                    required 
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Descricao</label>
                <textarea 
                  value={form.description} 
                  onChange={e => setForm({...form, description: e.target.value})}
                  rows={2}
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Tempo Medio (minutos) *</label>
                  <input 
                    type="number" 
                    value={form.average_time_minutes} 
                    onChange={e => setForm({...form, average_time_minutes: Number(e.target.value)})}
                    min={1}
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Tipo de Unidade</label>
                  <select 
                    value={form.unit_type} 
                    onChange={e => setForm({...form, unit_type: e.target.value})}
                  >
                    <option value="">Selecione</option>
                    <option value="room">Quarto</option>
                    <option value="task">Tarefa</option>
                    <option value="event">Evento</option>
                    <option value="area">Area</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Classificacao *</label>
                  <select 
                    value={form.classificacao_atividade} 
                    onChange={e => handleClassificationChange(e.target.value as ActivityClassification)}
                  >
                    <option value="CALCULADA_PELO_AGENTE">Calculada pelo Agente (LVS, LET)</option>
                    <option value="RECORRENTE">Recorrente (com periodicidade)</option>
                    <option value="EVENTUAL">Eventual (agendamento manual)</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Driver de Demanda *</label>
                  <select 
                    value={form.workload_driver} 
                    onChange={e => setForm({...form, workload_driver: e.target.value as WorkloadDriver})}
                  >
                    <option value="VARIABLE">Variavel (baseada em ocupacao)</option>
                    <option value="CONSTANT">Constante (fixa)</option>
                  </select>
                </div>
              </div>

              {form.classificacao_atividade === 'RECORRENTE' && (
                <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', marginBottom: '15px' }}>
                  <h4 style={{ margin: '0 0 15px 0', fontSize: '14px', color: '#666' }}>Configuracao da Recorrencia</h4>
                  
                  <div className="form-row">
                    <div className="form-group">
                      <label>Periodicidade *</label>
                      <select 
                        value={form.periodicidade_id || ''} 
                        onChange={e => setForm({...form, periodicidade_id: e.target.value ? Number(e.target.value) : null})}
                        required
                        style={{ borderColor: !form.periodicidade_id ? '#dc3545' : undefined }}
                      >
                        <option value="">Selecione a periodicidade</option>
                        {periodicities.map(p => (
                          <option key={p.id} value={p.id}>{p.name} ({p.intervalo_dias} dias)</option>
                        ))}
                      </select>
                      {!form.periodicidade_id && (
                        <small style={{ color: '#dc3545' }}>Obrigatoria para atividades recorrentes</small>
                      )}
                    </div>
                    
                    <div className="form-group">
                      <label>Data Primeira Execucao *</label>
                      <input 
                        type="date" 
                        value={form.data_primeira_execucao || ''} 
                        onChange={e => setForm({...form, data_primeira_execucao: e.target.value || null})}
                        required
                        style={{ borderColor: !form.data_primeira_execucao ? '#dc3545' : undefined }}
                      />
                      {!form.data_primeira_execucao && (
                        <small style={{ color: '#dc3545' }}>Obrigatoria para atividades recorrentes</small>
                      )}
                    </div>
                  </div>
                  
                  {getSelectedPeriodicityTipo() && getSelectedPeriodicityTipo() !== 'DAILY' && (
                    <div className="form-group">
                      <label>Tolerancia (dias) *</label>
                      <input 
                        type="number" 
                        value={form.tolerancia_dias || ''} 
                        onChange={e => setForm({...form, tolerancia_dias: e.target.value ? Number(e.target.value) : null})}
                        min={1}
                        max={30}
                        placeholder="Dias de tolerancia antes/depois da data programada"
                        style={{ borderColor: !form.tolerancia_dias ? '#dc3545' : undefined }}
                      />
                      {!form.tolerancia_dias && (
                        <small style={{ color: '#dc3545' }}>Obrigatoria para periodicidades nao-diarias</small>
                      )}
                      <small style={{ display: 'block', color: '#666', marginTop: '5px' }}>
                        Define quantos dias de atraso sao permitidos antes de marcar como PENDENTE
                      </small>
                    </div>
                  )}
                </div>
              )}

              <div className="form-row">
                <div className="form-group">
                  <label>Nivel de Dificuldade (1-5)</label>
                  <select 
                    value={form.difficulty_level} 
                    onChange={e => setForm({...form, difficulty_level: Number(e.target.value)})}
                  >
                    <option value={1}>1 - Muito Facil</option>
                    <option value={2}>2 - Facil</option>
                    <option value={3}>3 - Medio</option>
                    <option value={4}>4 - Dificil</option>
                    <option value={5}>5 - Muito Dificil</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>
                  <input 
                    type="checkbox" 
                    checked={form.requires_training}
                    onChange={e => setForm({...form, requires_training: e.target.checked})}
                    style={{ marginRight: 8 }}
                  />
                  Requer treinamento especifico
                </label>
              </div>

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary">Salvar</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default ActivitiesPage;
