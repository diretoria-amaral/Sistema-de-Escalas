import { useState, useEffect } from 'react';
import axios from 'axios';

interface Sector {
  id: number;
  name: string;
}

interface ForecastRun {
  id: number;
  sector_id: number;
  run_type: string;
  run_date: string;
  horizon_start: string;
  horizon_end: string;
  status: string;
  is_locked: boolean;
}

interface Activity {
  id: number;
  name: string;
  code: string;
  average_time_minutes: number;
}

interface ProgramItem {
  id: number;
  activity_id: number;
  activity_name: string;
  activity_code: string;
  op_date: string;
  window_start: string | null;
  window_end: string | null;
  quantity: number;
  workload_minutes: number;
  priority: number;
  source: string;
  drivers_json: Record<string, any>;
  notes: string | null;
}

interface ProgramWeek {
  id: number;
  sector_id: number;
  sector_name: string;
  forecast_run_id: number;
  week_start: string;
  status: string;
  created_at: string;
  created_by: string;
  updated_at: string | null;
  updated_by: string | null;
  items_by_day: Record<string, ProgramItem[]>;
  total_items: number;
}

const WEEKDAYS = ['SEG', 'TER', 'QUA', 'QUI', 'SEX', 'SAB', 'DOM'];
const PRIORITY_COLORS: Record<number, string> = {
  1: '#ef4444',
  2: '#f97316',
  3: '#eab308',
  4: '#22c55e',
  5: '#3b82f6'
};

export default function ActivityProgrammingPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [forecastRuns, setForecastRuns] = useState<ForecastRun[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [programWeeks, setProgramWeeks] = useState<any[]>([]);
  const [currentProgram, setCurrentProgram] = useState<ProgramWeek | null>(null);
  
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [selectedForecastRunId, setSelectedForecastRunId] = useState<number | null>(null);
  const [selectedWeekStart, setSelectedWeekStart] = useState<string>(getMonday(new Date()).toISOString().split('T')[0]);
  
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{type: 'success' | 'error'; text: string} | null>(null);
  
  const [showAddModal, setShowAddModal] = useState(false);
  const [showDriversModal, setShowDriversModal] = useState<ProgramItem | null>(null);
  const [showAdjustmentModal, setShowAdjustmentModal] = useState(false);
  const [adjustmentReason, setAdjustmentReason] = useState('');
  
  const [newItem, setNewItem] = useState({
    activity_id: 0,
    op_date: '',
    quantity: 1,
    workload_minutes: 0,
    priority: 3,
    window_start: '08:00',
    window_end: '17:00',
    notes: ''
  });

  function getMonday(d: Date): Date {
    const date = new Date(d);
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1);
    return new Date(date.setDate(diff));
  }

  function getWeekDates(weekStart: string): string[] {
    const start = new Date(weekStart);
    const dates: string[] = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      dates.push(d.toISOString().split('T')[0]);
    }
    return dates;
  }

  useEffect(() => {
    loadSectors();
  }, []);

  useEffect(() => {
    if (selectedSectorId) {
      loadForecastRuns();
      loadActivities();
      loadProgramWeeks();
    }
  }, [selectedSectorId]);

  useEffect(() => {
    if (selectedSectorId && selectedForecastRunId && selectedWeekStart) {
      loadCurrentProgram();
    }
  }, [selectedSectorId, selectedForecastRunId, selectedWeekStart]);

  const loadSectors = async () => {
    try {
      const response = await axios.get('/api/activity-program/sectors');
      setSectors(response.data);
      if (response.data.length > 0) {
        setSelectedSectorId(response.data[0].id);
      }
    } catch (error) {
      console.error('Error loading sectors:', error);
    }
  };

  const loadForecastRuns = async () => {
    if (!selectedSectorId) return;
    try {
      const response = await axios.get(`/api/activity-program/forecast-runs?sector_id=${selectedSectorId}`);
      setForecastRuns(response.data);
      if (response.data.length > 0) {
        setSelectedForecastRunId(response.data[0].id);
      }
    } catch (error) {
      console.error('Error loading forecast runs:', error);
    }
  };

  const loadActivities = async () => {
    if (!selectedSectorId) return;
    try {
      const response = await axios.get(`/api/activity-program/activities?sector_id=${selectedSectorId}`);
      setActivities(response.data);
    } catch (error) {
      console.error('Error loading activities:', error);
    }
  };

  const loadProgramWeeks = async () => {
    if (!selectedSectorId) return;
    try {
      const response = await axios.get(`/api/activity-program/weeks?sector_id=${selectedSectorId}`);
      setProgramWeeks(response.data);
    } catch (error) {
      console.error('Error loading program weeks:', error);
    }
  };

  const loadCurrentProgram = async () => {
    if (!selectedSectorId || !selectedForecastRunId) return;
    setLoading(true);
    try {
      const existing = programWeeks.find(
        (p) => p.sector_id === selectedSectorId && 
               p.forecast_run_id === selectedForecastRunId &&
               p.week_start === selectedWeekStart
      );
      
      if (existing) {
        const response = await axios.get(`/api/activity-program/week/${existing.id}`);
        setCurrentProgram(response.data);
      } else {
        setCurrentProgram(null);
      }
    } catch (error) {
      console.error('Error loading current program:', error);
      setCurrentProgram(null);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateProgram = async (mode: 'AUTO' | 'MANUAL') => {
    if (!selectedSectorId || !selectedForecastRunId) {
      setMessage({ type: 'error', text: 'Selecione setor e forecast run' });
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post('/api/activity-program/week', {
        sector_id: selectedSectorId,
        forecast_run_id: selectedForecastRunId,
        week_start: selectedWeekStart,
        mode
      });
      setMessage({ type: 'success', text: `Programacao criada (${mode})` });
      loadProgramWeeks();
      const detailResponse = await axios.get(`/api/activity-program/week/${response.data.id}`);
      setCurrentProgram(detailResponse.data);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao criar programacao' });
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async () => {
    if (!currentProgram) return;
    setLoading(true);
    try {
      await axios.post(`/api/activity-program/week/${currentProgram.id}/approve`);
      setMessage({ type: 'success', text: 'Programacao aprovada' });
      loadCurrentProgram();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao aprovar' });
    } finally {
      setLoading(false);
    }
  };

  const handleLock = async () => {
    if (!currentProgram) return;
    setLoading(true);
    try {
      await axios.post(`/api/activity-program/week/${currentProgram.id}/lock`);
      setMessage({ type: 'success', text: 'Programacao bloqueada' });
      loadCurrentProgram();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao bloquear' });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateAdjustment = async () => {
    if (!selectedForecastRunId || !selectedSectorId || !adjustmentReason) return;
    setLoading(true);
    try {
      await axios.post(
        `/api/activity-program/baseline/${selectedForecastRunId}/adjustment?sector_id=${selectedSectorId}`,
        { reason: adjustmentReason }
      );
      setMessage({ type: 'success', text: 'Ajuste criado com sucesso' });
      setShowAdjustmentModal(false);
      setAdjustmentReason('');
      loadForecastRuns();
      loadProgramWeeks();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao criar ajuste' });
    } finally {
      setLoading(false);
    }
  };

  const handleAddItem = async () => {
    if (!currentProgram || !newItem.activity_id || !newItem.op_date) return;
    setLoading(true);
    try {
      await axios.post(`/api/activity-program/week/${currentProgram.id}/items`, newItem);
      setMessage({ type: 'success', text: 'Item adicionado' });
      setShowAddModal(false);
      loadCurrentProgram();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao adicionar item' });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteItem = async (itemId: number) => {
    if (!confirm('Confirma exclusao do item?')) return;
    setLoading(true);
    try {
      await axios.delete(`/api/activity-program/items/${itemId}`);
      setMessage({ type: 'success', text: 'Item removido' });
      loadCurrentProgram();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao remover item' });
    } finally {
      setLoading(false);
    }
  };

  const weekDates = getWeekDates(selectedWeekStart);

  return (
    <div style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px' }}>
        Programacao de Atividades
      </h1>
      
      {message && (
        <div style={{
          padding: '12px',
          marginBottom: '16px',
          borderRadius: '8px',
          backgroundColor: message.type === 'success' ? '#dcfce7' : '#fee2e2',
          color: message.type === 'success' ? '#166534' : '#991b1b'
        }}>
          {message.text}
          <button 
            onClick={() => setMessage(null)}
            style={{ marginLeft: '12px', cursor: 'pointer' }}
          >
            X
          </button>
        </div>
      )}

      <div style={{ 
        display: 'flex', 
        gap: '16px', 
        marginBottom: '20px',
        flexWrap: 'wrap',
        alignItems: 'flex-end'
      }}>
        <div>
          <label style={{ display: 'block', fontSize: '14px', marginBottom: '4px' }}>Setor</label>
          <select
            value={selectedSectorId || ''}
            onChange={(e) => setSelectedSectorId(Number(e.target.value))}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', minWidth: '150px' }}
          >
            {sectors.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
        
        <div>
          <label style={{ display: 'block', fontSize: '14px', marginBottom: '4px' }}>Semana (inicio)</label>
          <input
            type="date"
            value={selectedWeekStart}
            onChange={(e) => setSelectedWeekStart(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          />
        </div>
        
        <div>
          <label style={{ display: 'block', fontSize: '14px', marginBottom: '4px' }}>Forecast Run</label>
          <select
            value={selectedForecastRunId || ''}
            onChange={(e) => setSelectedForecastRunId(Number(e.target.value))}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db', minWidth: '200px' }}
          >
            <option value="">Selecione...</option>
            {forecastRuns.map((r) => (
              <option key={r.id} value={r.id}>
                #{r.id} - {r.run_type} ({r.run_date})
              </option>
            ))}
          </select>
        </div>

        {currentProgram && (
          <div style={{ 
            padding: '8px 16px', 
            borderRadius: '6px',
            backgroundColor: currentProgram.status === 'locked' ? '#fee2e2' : 
                           currentProgram.status === 'approved' ? '#dcfce7' : '#fef3c7',
            fontWeight: 'bold',
            textTransform: 'uppercase'
          }}>
            {currentProgram.status}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {!currentProgram && (
          <>
            <button
              onClick={() => handleCreateProgram('AUTO')}
              disabled={loading || !selectedForecastRunId}
              style={{
                padding: '10px 20px',
                backgroundColor: '#2563eb',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                opacity: loading || !selectedForecastRunId ? 0.5 : 1
              }}
            >
              Gerar Automatico
            </button>
            <button
              onClick={() => handleCreateProgram('MANUAL')}
              disabled={loading || !selectedForecastRunId}
              style={{
                padding: '10px 20px',
                backgroundColor: '#6b7280',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                opacity: loading || !selectedForecastRunId ? 0.5 : 1
              }}
            >
              Criar Manual
            </button>
          </>
        )}
        
        {currentProgram && currentProgram.status !== 'locked' && (
          <>
            <button
              onClick={() => setShowAddModal(true)}
              style={{
                padding: '10px 20px',
                backgroundColor: '#059669',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              + Adicionar Item
            </button>
            
            {currentProgram.status === 'draft' && (
              <button
                onClick={handleApprove}
                disabled={loading}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#16a34a',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer'
                }}
              >
                Aprovar
              </button>
            )}
            
            {currentProgram.status === 'approved' && (
              <button
                onClick={handleLock}
                disabled={loading}
                style={{
                  padding: '10px 20px',
                  backgroundColor: '#dc2626',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer'
                }}
              >
                Bloquear
              </button>
            )}
          </>
        )}
        
        <button
          onClick={() => setShowAdjustmentModal(true)}
          disabled={loading || !selectedForecastRunId}
          style={{
            padding: '10px 20px',
            backgroundColor: '#7c3aed',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            opacity: loading || !selectedForecastRunId ? 0.5 : 1
          }}
        >
          Criar Ajuste Diario
        </button>
      </div>

      {loading && <div style={{ textAlign: 'center', padding: '40px' }}>Carregando...</div>}

      {!loading && currentProgram && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f3f4f6' }}>
                {weekDates.map((date, idx) => (
                  <th key={date} style={{ padding: '12px', border: '1px solid #e5e7eb', textAlign: 'center', minWidth: '150px' }}>
                    <div style={{ fontWeight: 'bold' }}>{WEEKDAYS[idx]}</div>
                    <div style={{ fontSize: '12px', color: '#6b7280' }}>{date}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                {weekDates.map((date) => {
                  const items = currentProgram.items_by_day[date] || [];
                  const totalWorkload = items.reduce((sum, i) => sum + (i.workload_minutes || 0), 0);
                  
                  return (
                    <td key={date} style={{ padding: '8px', border: '1px solid #e5e7eb', verticalAlign: 'top' }}>
                      <div style={{ marginBottom: '8px', fontSize: '12px', color: '#6b7280' }}>
                        {items.length} itens | {Math.round(totalWorkload / 60)}h
                      </div>
                      
                      {items.map((item) => (
                        <div 
                          key={item.id}
                          style={{
                            padding: '8px',
                            marginBottom: '8px',
                            borderRadius: '6px',
                            backgroundColor: '#fff',
                            border: `2px solid ${PRIORITY_COLORS[item.priority] || '#d1d5db'}`,
                            boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                          }}
                        >
                          <div style={{ fontWeight: 'bold', marginBottom: '4px' }}>
                            {item.activity_name}
                          </div>
                          <div style={{ fontSize: '12px', color: '#6b7280' }}>
                            {item.window_start && item.window_end && (
                              <div>{item.window_start} - {item.window_end}</div>
                            )}
                            <div>Qtd: {item.quantity} | {item.workload_minutes}min</div>
                            <div style={{ display: 'flex', gap: '4px', alignItems: 'center', marginTop: '4px' }}>
                              <span style={{ 
                                padding: '2px 6px', 
                                backgroundColor: item.source === 'auto' ? '#dbeafe' : '#fef3c7',
                                borderRadius: '4px',
                                fontSize: '10px'
                              }}>
                                {item.source.toUpperCase()}
                              </span>
                              <span style={{
                                padding: '2px 6px',
                                backgroundColor: PRIORITY_COLORS[item.priority],
                                color: 'white',
                                borderRadius: '4px',
                                fontSize: '10px'
                              }}>
                                P{item.priority}
                              </span>
                            </div>
                          </div>
                          <div style={{ display: 'flex', gap: '4px', marginTop: '8px' }}>
                            <button
                              onClick={() => setShowDriversModal(item)}
                              style={{
                                padding: '4px 8px',
                                fontSize: '11px',
                                backgroundColor: '#e5e7eb',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer'
                              }}
                            >
                              Drivers
                            </button>
                            {currentProgram.status !== 'locked' && (
                              <button
                                onClick={() => handleDeleteItem(item.id)}
                                style={{
                                  padding: '4px 8px',
                                  fontSize: '11px',
                                  backgroundColor: '#fee2e2',
                                  color: '#991b1b',
                                  border: 'none',
                                  borderRadius: '4px',
                                  cursor: 'pointer'
                                }}
                              >
                                Excluir
                              </button>
                            )}
                          </div>
                        </div>
                      ))}
                    </td>
                  );
                })}
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {!loading && !currentProgram && selectedForecastRunId && (
        <div style={{ 
          textAlign: 'center', 
          padding: '60px', 
          backgroundColor: '#f9fafb',
          borderRadius: '8px',
          color: '#6b7280'
        }}>
          <div style={{ fontSize: '18px', marginBottom: '12px' }}>Nenhuma programacao encontrada</div>
          <div>Clique em "Gerar Automatico" ou "Criar Manual" para comecar</div>
        </div>
      )}

      {currentProgram && (
        <div style={{ marginTop: '20px', padding: '16px', backgroundColor: '#f9fafb', borderRadius: '8px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 'bold', marginBottom: '8px' }}>Auditoria</h3>
          <div style={{ fontSize: '14px', color: '#6b7280' }}>
            <div>Criado por: {currentProgram.created_by || 'N/A'}</div>
            <div>Criado em: {currentProgram.created_at || 'N/A'}</div>
            {currentProgram.updated_at && (
              <>
                <div>Atualizado por: {currentProgram.updated_by || 'N/A'}</div>
                <div>Atualizado em: {currentProgram.updated_at}</div>
              </>
            )}
          </div>
        </div>
      )}

      {showAddModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '24px',
            borderRadius: '12px',
            width: '400px',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <h2 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 'bold' }}>Adicionar Item</h2>
            
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Atividade</label>
              <select
                value={newItem.activity_id}
                onChange={(e) => setNewItem({ ...newItem, activity_id: Number(e.target.value) })}
                style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
              >
                <option value={0}>Selecione...</option>
                {activities.map((a) => (
                  <option key={a.id} value={a.id}>{a.name} ({a.average_time_minutes}min)</option>
                ))}
              </select>
            </div>
            
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Data</label>
              <select
                value={newItem.op_date}
                onChange={(e) => setNewItem({ ...newItem, op_date: e.target.value })}
                style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
              >
                <option value="">Selecione...</option>
                {weekDates.map((date, idx) => (
                  <option key={date} value={date}>{WEEKDAYS[idx]} - {date}</option>
                ))}
              </select>
            </div>
            
            <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '4px' }}>Quantidade</label>
                <input
                  type="number"
                  min={1}
                  value={newItem.quantity}
                  onChange={(e) => setNewItem({ ...newItem, quantity: Number(e.target.value) })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '4px' }}>Carga (min)</label>
                <input
                  type="number"
                  min={0}
                  value={newItem.workload_minutes}
                  onChange={(e) => setNewItem({ ...newItem, workload_minutes: Number(e.target.value) })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                />
              </div>
            </div>
            
            <div style={{ display: 'flex', gap: '12px', marginBottom: '12px' }}>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '4px' }}>Inicio</label>
                <input
                  type="time"
                  value={newItem.window_start}
                  onChange={(e) => setNewItem({ ...newItem, window_start: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                />
              </div>
              <div style={{ flex: 1 }}>
                <label style={{ display: 'block', marginBottom: '4px' }}>Fim</label>
                <input
                  type="time"
                  value={newItem.window_end}
                  onChange={(e) => setNewItem({ ...newItem, window_end: e.target.value })}
                  style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                />
              </div>
            </div>
            
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Prioridade (1-5)</label>
              <select
                value={newItem.priority}
                onChange={(e) => setNewItem({ ...newItem, priority: Number(e.target.value) })}
                style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db' }}
              >
                {[1, 2, 3, 4, 5].map((p) => (
                  <option key={p} value={p}>P{p} - {p === 1 ? 'Urgente' : p === 2 ? 'Alta' : p === 3 ? 'Media' : p === 4 ? 'Baixa' : 'Minima'}</option>
                ))}
              </select>
            </div>
            
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Notas</label>
              <textarea
                value={newItem.notes}
                onChange={(e) => setNewItem({ ...newItem, notes: e.target.value })}
                style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #d1d5db', minHeight: '60px' }}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowAddModal(false)}
                style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #d1d5db', cursor: 'pointer' }}
              >
                Cancelar
              </button>
              <button
                onClick={handleAddItem}
                disabled={!newItem.activity_id || !newItem.op_date}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#2563eb',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  opacity: !newItem.activity_id || !newItem.op_date ? 0.5 : 1
                }}
              >
                Adicionar
              </button>
            </div>
          </div>
        </div>
      )}

      {showDriversModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '24px',
            borderRadius: '12px',
            width: '500px',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <h2 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 'bold' }}>
              Drivers - {showDriversModal.activity_name}
            </h2>
            
            <div style={{ marginBottom: '12px' }}>
              <strong>Data:</strong> {showDriversModal.op_date}
            </div>
            <div style={{ marginBottom: '12px' }}>
              <strong>Quantidade:</strong> {showDriversModal.quantity}
            </div>
            <div style={{ marginBottom: '12px' }}>
              <strong>Carga:</strong> {showDriversModal.workload_minutes} minutos
            </div>
            
            <div style={{ marginBottom: '12px' }}>
              <strong>Drivers JSON:</strong>
              <pre style={{ 
                backgroundColor: '#f3f4f6', 
                padding: '12px', 
                borderRadius: '6px',
                fontSize: '12px',
                overflow: 'auto',
                maxHeight: '300px'
              }}>
                {JSON.stringify(showDriversModal.drivers_json, null, 2)}
              </pre>
            </div>
            
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowDriversModal(null)}
                style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #d1d5db', cursor: 'pointer' }}
              >
                Fechar
              </button>
            </div>
          </div>
        </div>
      )}

      {showAdjustmentModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            padding: '24px',
            borderRadius: '12px',
            width: '400px'
          }}>
            <h2 style={{ marginBottom: '16px', fontSize: '18px', fontWeight: 'bold' }}>
              Criar Ajuste Diario
            </h2>
            
            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '4px' }}>Motivo do Ajuste</label>
              <textarea
                value={adjustmentReason}
                onChange={(e) => setAdjustmentReason(e.target.value)}
                placeholder="Ex: Demanda maior que o previsto..."
                style={{ 
                  width: '100%', 
                  padding: '8px', 
                  borderRadius: '6px', 
                  border: '1px solid #d1d5db',
                  minHeight: '100px'
                }}
              />
            </div>
            
            <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowAdjustmentModal(false)}
                style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #d1d5db', cursor: 'pointer' }}
              >
                Cancelar
              </button>
              <button
                onClick={handleCreateAdjustment}
                disabled={!adjustmentReason}
                style={{
                  padding: '8px 16px',
                  backgroundColor: '#7c3aed',
                  color: 'white',
                  border: 'none',
                  borderRadius: '6px',
                  cursor: 'pointer',
                  opacity: !adjustmentReason ? 0.5 : 1
                }}
              >
                Criar Ajuste
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
