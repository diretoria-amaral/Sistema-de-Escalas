import { useState, useEffect } from 'react';
import { sectorsApi, Sector, apiClient } from '../services/client';

interface Convocation {
  id: number;
  employee_id: number;
  employee_name: string;
  sector_id: number;
  shift_date: string;
  start_time: string;
  end_time: string;
  status: string;
  origin: string;
  created_at: string;
  response_deadline: string;
  responded_at: string | null;
  decline_reason: string | null;
}

interface SchedulePlan {
  id: number;
  sector_id: number;
  week_start: string;
  status: string;
  kind: string;
  slots: ShiftSlot[];
}

interface ShiftSlot {
  id: number;
  schedule_id: number;
  employee_id: number;
  employee_name: string;
  date: string;
  start_time: string;
  end_time: string;
  role: string;
  notes: string | null;
}

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  pending: { label: 'Pendente', color: '#f59e0b' },
  accepted: { label: 'Aceito', color: '#22c55e' },
  declined: { label: 'Recusado', color: '#ef4444' },
  expired: { label: 'Expirado', color: '#6b7280' },
  cancelled: { label: 'Cancelado', color: '#9ca3af' },
};

export default function ConfirmacaoAlteracoesPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [weekStart, setWeekStart] = useState<string>('');
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [convocations, setConvocations] = useState<Convocation[]>([]);
  const [schedule, setSchedule] = useState<SchedulePlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadSectors();
    const today = new Date();
    const monday = new Date(today);
    monday.setDate(today.getDate() - today.getDay() + 1);
    setWeekStart(monday.toISOString().split('T')[0]);
    setSelectedDate(today.toISOString().split('T')[0]);
  }, []);

  useEffect(() => {
    if (selectedSector && weekStart) {
      loadData();
    }
  }, [selectedSector, weekStart, selectedDate]);

  const loadSectors = async () => {
    try {
      const response = await sectorsApi.list();
      setSectors(response.data);
      if (response.data.length > 0) {
        setSelectedSector(response.data[0].id);
      }
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar setores' });
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const convResponse = await apiClient.get<Convocation[]>('/convocations/by-sector', {
        params: { sector_id: selectedSector }
      });
      
      const allConvocations = convResponse.data || [];
      setConvocations(allConvocations);
      setSchedule(null);
    } catch (err) {
      console.error('Load error:', err);
      setConvocations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleCancelConvocation = async (convocation: Convocation) => {
    const reason = prompt('Motivo do cancelamento:');
    if (!reason) return;

    try {
      await apiClient.post(`/convocations/${convocation.id}/cancel`, { reason });
      setMessage({ type: 'success', text: 'Convocacao cancelada. Adjustment Run gerado.' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao cancelar convocacao' });
    }
  };

  const handleRequestSubstitution = async (convocation: Convocation) => {
    if (!confirm('Deseja solicitar substituicao para esta convocacao recusada?')) return;

    try {
      await apiClient.post(`/convocations/${convocation.id}/substitute`);
      setMessage({ type: 'success', text: 'Solicitacao de substituicao enviada.' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao solicitar substituicao' });
    }
  };

  const formatTime = (time: string) => time?.slice(0, 5) || '--:--';
  const formatDate = (dateStr: string) => new Date(dateStr).toLocaleDateString('pt-BR');

  const getWeekDays = () => {
    if (!weekStart) return [];
    const days = [];
    const start = new Date(weekStart);
    for (let i = 0; i < 7; i++) {
      const day = new Date(start);
      day.setDate(start.getDate() + i);
      days.push(day.toISOString().split('T')[0]);
    }
    return days;
  };

  const filteredSlots = schedule?.slots?.filter(
    s => !selectedDate || s.date === selectedDate
  ) || [];

  const filteredConvocations = convocations.filter(
    c => !selectedDate || c.shift_date.split('T')[0] === selectedDate
  );

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '28px', marginBottom: '24px' }}>Confirmacao e Alteracoes</h1>
      
      {message && (
        <div style={{
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '16px',
          backgroundColor: message.type === 'success' ? '#dcfce7' : '#fee2e2',
          color: message.type === 'success' ? '#166534' : '#dc2626'
        }}>
          {message.text}
        </div>
      )}

      <div style={{ 
        display: 'flex', 
        gap: '16px', 
        marginBottom: '24px',
        flexWrap: 'wrap',
        alignItems: 'flex-end'
      }}>
        <div>
          <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>Setor:</label>
          <select
            value={selectedSector || ''}
            onChange={(e) => setSelectedSector(Number(e.target.value))}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          >
            {sectors.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>Semana:</label>
          <input
            type="date"
            value={weekStart}
            onChange={(e) => setWeekStart(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>Dia Especifico:</label>
          <select
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          >
            <option value="">Todos os dias</option>
            {getWeekDays().map(day => (
              <option key={day} value={day}>{formatDate(day)}</option>
            ))}
          </select>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          style={{
            padding: '10px 20px',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: 500
          }}
        >
          Atualizar
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        <div>
          <h2 style={{ fontSize: '20px', marginBottom: '16px', color: '#374151' }}>
            Escala Planejada
          </h2>
          
          {loading ? (
            <p>Carregando...</p>
          ) : !schedule ? (
            <div style={{
              padding: '24px',
              backgroundColor: '#f9fafb',
              borderRadius: '8px',
              textAlign: 'center',
              color: '#6b7280'
            }}>
              Nenhuma escala encontrada para esta semana.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filteredSlots.length === 0 ? (
                <p style={{ color: '#6b7280' }}>Nenhum turno para o dia selecionado.</p>
              ) : (
                filteredSlots.map(slot => (
                  <div
                    key={slot.id}
                    style={{
                      backgroundColor: 'white',
                      padding: '12px 16px',
                      borderRadius: '8px',
                      border: '1px solid #e5e7eb',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center'
                    }}
                  >
                    <div>
                      <strong>{slot.employee_name}</strong>
                      <div style={{ fontSize: '14px', color: '#6b7280' }}>
                        {formatDate(slot.date)} | {formatTime(slot.start_time)} - {formatTime(slot.end_time)}
                      </div>
                    </div>
                    <span style={{
                      padding: '4px 8px',
                      backgroundColor: '#dbeafe',
                      color: '#1d4ed8',
                      borderRadius: '4px',
                      fontSize: '12px'
                    }}>
                      {slot.role}
                    </span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div>
          <h2 style={{ fontSize: '20px', marginBottom: '16px', color: '#374151' }}>
            Convocacoes
          </h2>
          
          {loading ? (
            <p>Carregando...</p>
          ) : filteredConvocations.length === 0 ? (
            <div style={{
              padding: '24px',
              backgroundColor: '#f9fafb',
              borderRadius: '8px',
              textAlign: 'center',
              color: '#6b7280'
            }}>
              Nenhuma convocacao para o periodo selecionado.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {filteredConvocations.map(conv => (
                <div
                  key={conv.id}
                  style={{
                    backgroundColor: 'white',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    border: '1px solid #e5e7eb'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <strong>{conv.employee_name}</strong>
                      <div style={{ fontSize: '14px', color: '#6b7280' }}>
                        {formatDate(conv.shift_date)} | {formatTime(conv.start_time)} - {formatTime(conv.end_time)}
                      </div>
                    </div>
                    <span style={{
                      padding: '4px 12px',
                      backgroundColor: STATUS_LABELS[conv.status]?.color || '#6b7280',
                      color: 'white',
                      borderRadius: '20px',
                      fontSize: '12px',
                      fontWeight: 500
                    }}>
                      {STATUS_LABELS[conv.status]?.label || conv.status}
                    </span>
                  </div>

                  {conv.decline_reason && (
                    <div style={{
                      marginTop: '8px',
                      padding: '8px',
                      backgroundColor: '#fef2f2',
                      borderRadius: '4px',
                      fontSize: '13px',
                      color: '#dc2626'
                    }}>
                      Motivo da recusa: {conv.decline_reason}
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
                    {conv.status === 'pending' && (
                      <button
                        onClick={() => handleCancelConvocation(conv)}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#fee2e2',
                          color: '#dc2626',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '13px'
                        }}
                      >
                        Cancelar
                      </button>
                    )}
                    {conv.status === 'declined' && (
                      <button
                        onClick={() => handleRequestSubstitution(conv)}
                        style={{
                          padding: '6px 12px',
                          backgroundColor: '#dbeafe',
                          color: '#1d4ed8',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '13px'
                        }}
                      >
                        Gerar Substituicao
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div style={{
        marginTop: '32px',
        padding: '16px',
        backgroundColor: '#fffbeb',
        borderRadius: '8px',
        border: '1px solid #fcd34d'
      }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#92400e', marginBottom: '8px' }}>
          Regras de Alteracao
        </h3>
        <ul style={{ margin: 0, paddingLeft: '20px', color: '#78350f', fontSize: '14px', lineHeight: 1.6 }}>
          <li>Baseline nunca e alterado diretamente</li>
          <li>Todas as alteracoes geram um Adjustment Run com motivo registrado</li>
          <li>Ajustes de horario somente via Adjustment Run</li>
          <li>Cancelamentos e substituicoes sao auditados</li>
        </ul>
      </div>
    </div>
  );
}
