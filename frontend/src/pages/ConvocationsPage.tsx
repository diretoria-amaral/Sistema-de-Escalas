import { useState, useEffect } from 'react';
import axios from 'axios';

interface Sector {
  id: number;
  name: string;
  code: string;
}

interface ScheduleCheck {
  has_schedule: boolean;
  schedule: {
    id: number;
    sector_id: number;
    week_start: string;
    week_end: string;
    status: string;
    notes: string | null;
    expected_occupancy: number | null;
    expected_rooms_to_clean: number | null;
    created_at: string | null;
  } | null;
  shifts: ShiftData[];
  can_generate_convocations: boolean;
  blocking_errors: string[];
  shifts_count: number;
}

interface ShiftData {
  id: number;
  employee_id: number;
  employee_name: string | null;
  date: string;
  start_time: string | null;
  end_time: string | null;
  planned_hours: number;
}

interface Convocation {
  id: number;
  employee_id: number;
  sector_id: number;
  activity_id: number | null;
  date: string;
  start_time: string;
  end_time: string;
  total_hours: number;
  status: string;
  generated_from: string;
  response_deadline: string;
  responded_at: string | null;
  decline_reason: string | null;
  employee_name: string | null;
  sector_name: string | null;
  legal_validation_passed: boolean;
  replaced_convocation_id: number | null;
  replacement_convocation_id: number | null;
}

interface ConvocationStats {
  total: number;
  pending: number;
  accepted: number;
  declined: number;
  expired: number;
  cancelled: number;
  acceptance_rate: number;
}

interface GenerateResult {
  success: boolean;
  convocations_created: number;
  convocations_blocked: number;
  errors: string[];
  warnings: string[];
  created_convocation_ids: number[];
}

type TabType = 'overview' | 'schedule' | 'convocations' | 'history';

export default function ConvocationsPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [weekStart, setWeekStart] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'warning' | 'info'; text: string } | null>(null);
  
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [scheduleCheck, setScheduleCheck] = useState<ScheduleCheck | null>(null);
  const [convocations, setConvocations] = useState<Convocation[]>([]);
  const [stats, setStats] = useState<ConvocationStats | null>(null);
  const [generateResult, setGenerateResult] = useState<GenerateResult | null>(null);
  
  const [showResponseModal, setShowResponseModal] = useState(false);
  const [selectedConvocation, setSelectedConvocation] = useState<Convocation | null>(null);
  const [modalAction, setModalAction] = useState<'accept' | 'decline' | 'cancel' | null>(null);
  const [declineReason, setDeclineReason] = useState('');
  const [responseNotes, setResponseNotes] = useState('');

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
    setScheduleCheck(null);
    setConvocations([]);
    setStats(null);
    setGenerateResult(null);
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
        checkScheduleStatus(),
        loadConvocations(),
        loadStats()
      ]);
    } catch (error) {
      console.error('Erro ao carregar dados:', error);
    }
    
    setLoading(false);
  };

  const checkScheduleStatus = async () => {
    try {
      const response = await axios.get(`/api/schedules/check?sector_id=${selectedSectorId}&week_start=${weekStart}`);
      setScheduleCheck(response.data);
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 'Erro ao verificar status da escala';
      setScheduleCheck({
        has_schedule: false,
        schedule: null,
        shifts: [],
        can_generate_convocations: false,
        blocking_errors: [errorMsg],
        shifts_count: 0
      });
    }
  };

  const loadConvocations = async () => {
    try {
      const response = await axios.get(`/api/convocations/?sector_id=${selectedSectorId}&week_start=${weekStart}`);
      setConvocations(response.data);
    } catch (error) {
      console.error('Erro ao carregar convocações:', error);
    }
  };

  const loadStats = async () => {
    try {
      const response = await axios.get(`/api/convocations/stats?sector_id=${selectedSectorId}&week_start=${weekStart}`);
      setStats(response.data);
    } catch (error) {
      console.error('Erro ao carregar estatísticas:', error);
    }
  };

  const canGenerateConvocations = (): boolean => {
    return scheduleCheck?.can_generate_convocations === true;
  };

  const generateConvocations = async () => {
    if (!canGenerateConvocations() || !scheduleCheck?.schedule?.id) {
      setMessage({ type: 'error', text: 'Não é possível gerar convocações. Verifique os pré-requisitos.' });
      return;
    }

    setLoading(true);
    setMessage(null);

    try {
      const response = await axios.post('/api/convocations/generate-from-schedule', {
        weekly_schedule_id: scheduleCheck.schedule.id,
        response_deadline_hours: 72
      });
      
      setGenerateResult(response.data);
      
      if (response.data.success) {
        if (response.data.convocations_created > 0) {
          setMessage({ 
            type: 'success', 
            text: `${response.data.convocations_created} convocação(ões) gerada(s) com sucesso!` 
          });
        } else if (response.data.convocations_blocked > 0) {
          setMessage({ 
            type: 'warning', 
            text: `Nenhuma nova convocação gerada. ${response.data.convocations_blocked} bloqueada(s).` 
          });
        } else {
          setMessage({ 
            type: 'info', 
            text: 'Todas as convocações já foram geradas para esta escala.' 
          });
        }
        await loadConvocations();
        await loadStats();
      } else {
        setMessage({ type: 'error', text: 'Erro ao gerar convocações.' });
      }
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 'Erro ao gerar convocações';
      setMessage({ type: 'error', text: errorMsg });
    }

    setLoading(false);
  };

  const openResponseModal = (convocation: Convocation, action: 'accept' | 'decline' | 'cancel') => {
    setSelectedConvocation(convocation);
    setModalAction(action);
    setDeclineReason('');
    setResponseNotes('');
    setShowResponseModal(true);
  };

  const handleConvocationResponse = async () => {
    if (!selectedConvocation || !modalAction) return;

    try {
      if (modalAction === 'accept') {
        await axios.post(`/api/convocations/${selectedConvocation.id}/respond`, {
          action: 'accept',
          response_notes: responseNotes || null
        });
      } else if (modalAction === 'decline') {
        await axios.post(`/api/convocations/${selectedConvocation.id}/respond`, {
          action: 'decline',
          decline_reason: declineReason || null,
          response_notes: responseNotes || null
        });
      } else if (modalAction === 'cancel') {
        await axios.post(`/api/convocations/${selectedConvocation.id}/cancel`, {
          cancellation_reason: declineReason
        });
      }
      
      setShowResponseModal(false);
      setSelectedConvocation(null);
      setModalAction(null);
      setMessage({ type: 'success', text: 'Ação processada com sucesso!' });
      await loadConvocations();
      await loadStats();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 'Erro ao processar ação';
      setMessage({ type: 'error', text: errorMsg });
    }
  };

  const getWeekEnd = (start: string): string => {
    const d = new Date(start);
    d.setDate(d.getDate() + 6);
    return d.toISOString().split('T')[0];
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr + 'T00:00:00').toLocaleDateString('pt-BR');
  };

  const formatTime = (timeStr: string | null) => {
    return timeStr ? timeStr.substring(0, 5) : '';
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
      'pendente': { bg: '#fef3c7', text: '#92400e' },
      'aceita': { bg: '#d1fae5', text: '#065f46' },
      'recusada': { bg: '#fee2e2', text: '#991b1b' },
      'expirada': { bg: '#f3f4f6', text: '#4b5563' },
      'cancelada': { bg: '#ede9fe', text: '#6b21a8' }
    };
    const style = colors[status] || { bg: '#f3f4f6', text: '#4b5563' };
    return { backgroundColor: style.bg, color: style.text, padding: '2px 8px', borderRadius: '4px', fontSize: '12px' };
  };

  const getScheduleStatusBadge = (status: string) => {
    const colors: Record<string, { bg: string; text: string }> = {
      'rascunho': { bg: '#fef3c7', text: '#92400e' },
      'gerada': { bg: '#dbeafe', text: '#1e40af' },
      'publicada': { bg: '#d1fae5', text: '#065f46' },
      'concluida': { bg: '#f3f4f6', text: '#4b5563' },
      'cancelada': { bg: '#fee2e2', text: '#991b1b' }
    };
    const style = colors[status] || { bg: '#f3f4f6', text: '#4b5563' };
    return { backgroundColor: style.bg, color: style.text, padding: '4px 12px', borderRadius: '4px', fontWeight: 'bold' };
  };

  const selectedSector = sectors.find(s => s.id === selectedSectorId);

  return (
    <div style={{ padding: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      <h1 style={{ marginBottom: '10px' }}>Convocações</h1>
      <p style={{ color: '#666', marginBottom: '20px' }}>
        Geração e gestão de convocações baseadas na escala publicada
      </p>

      <div style={{ 
        backgroundColor: '#f8f9fa', 
        border: '1px solid #dee2e6', 
        borderRadius: '8px', 
        padding: '20px', 
        marginBottom: '20px' 
      }}>
        <h3 style={{ marginTop: 0, marginBottom: '15px' }}>Seleção Obrigatória</h3>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Setor</label>
            <select
              value={selectedSectorId || ''}
              onChange={(e) => setSelectedSectorId(Number(e.target.value))}
              style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid #ccc', minWidth: '200px' }}
            >
              <option value="">Selecione um setor</option>
              {sectors.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Semana (Segunda-feira)</label>
            <input
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              style={{ padding: '8px 12px', borderRadius: '4px', border: '1px solid #ccc' }}
            />
          </div>

          <button 
            onClick={loadAllData} 
            disabled={loading || !selectedSectorId || !weekStart}
            className="btn-primary"
          >
            Atualizar Dados
          </button>
        </div>
      </div>

      {scheduleCheck && (
        <div style={{ 
          backgroundColor: scheduleCheck.can_generate_convocations ? '#d4edda' : '#f8d7da',
          border: `1px solid ${scheduleCheck.can_generate_convocations ? '#c3e6cb' : '#f5c6cb'}`,
          borderRadius: '8px', 
          padding: '20px', 
          marginBottom: '20px' 
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
            <span style={{ fontSize: '24px' }}>
              {scheduleCheck.can_generate_convocations ? '✓' : '✗'}
            </span>
            <h3 style={{ margin: 0 }}>
              {scheduleCheck.can_generate_convocations 
                ? 'Pré-requisitos Atendidos - Pronto para Gerar Convocações' 
                : 'Pré-requisitos Não Atendidos'}
            </h3>
          </div>
          
          <p style={{ color: '#666', marginBottom: '15px' }}>
            Setor: {selectedSector?.name || '-'} | Semana: {weekStart} a {getWeekEnd(weekStart)}
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px' }}>
            <div style={{ 
              backgroundColor: 'white', 
              padding: '15px', 
              borderRadius: '6px',
              borderLeft: `4px solid ${scheduleCheck.has_schedule ? '#28a745' : '#dc3545'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: scheduleCheck.has_schedule ? '#28a745' : '#dc3545' }}>
                  {scheduleCheck.has_schedule ? '✓' : '✗'}
                </span>
                <strong>Escala</strong>
              </div>
              <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#666' }}>
                {scheduleCheck.has_schedule 
                  ? `Escala encontrada (${scheduleCheck.schedule?.status})` 
                  : 'Nenhuma escala para esta semana'}
              </p>
            </div>

            <div style={{ 
              backgroundColor: 'white', 
              padding: '15px', 
              borderRadius: '6px',
              borderLeft: `4px solid ${scheduleCheck.schedule?.status === 'publicada' ? '#28a745' : '#dc3545'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: scheduleCheck.schedule?.status === 'publicada' ? '#28a745' : '#dc3545' }}>
                  {scheduleCheck.schedule?.status === 'publicada' ? '✓' : '✗'}
                </span>
                <strong>Status Publicada</strong>
              </div>
              <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#666' }}>
                {scheduleCheck.schedule?.status === 'publicada' 
                  ? 'Escala publicada' 
                  : scheduleCheck.has_schedule 
                    ? `Status: ${scheduleCheck.schedule?.status || '-'}`
                    : 'N/A'}
              </p>
            </div>

            <div style={{ 
              backgroundColor: 'white', 
              padding: '15px', 
              borderRadius: '6px',
              borderLeft: `4px solid ${scheduleCheck.shifts_count > 0 ? '#28a745' : '#dc3545'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: scheduleCheck.shifts_count > 0 ? '#28a745' : '#dc3545' }}>
                  {scheduleCheck.shifts_count > 0 ? '✓' : '✗'}
                </span>
                <strong>Turnos</strong>
              </div>
              <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#666' }}>
                {scheduleCheck.shifts_count > 0 
                  ? `${scheduleCheck.shifts_count} turno(s) definido(s)` 
                  : 'Nenhum turno cadastrado'}
              </p>
            </div>

            <div style={{ 
              backgroundColor: 'white', 
              padding: '15px', 
              borderRadius: '6px',
              borderLeft: `4px solid ${convocations.length > 0 ? '#17a2b8' : '#6c757d'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ color: convocations.length > 0 ? '#17a2b8' : '#6c757d' }}>
                  {convocations.length > 0 ? '✓' : '○'}
                </span>
                <strong>Convocações</strong>
              </div>
              <p style={{ margin: '5px 0 0 0', fontSize: '14px', color: '#666' }}>
                {convocations.length > 0 
                  ? `${convocations.length} convocação(ões) existente(s)` 
                  : 'Nenhuma convocação gerada ainda'}
              </p>
            </div>
          </div>

          {scheduleCheck.blocking_errors.length > 0 && (
            <div style={{ marginTop: '15px', backgroundColor: '#fff3cd', padding: '10px', borderRadius: '4px' }}>
              <strong style={{ color: '#856404' }}>Erros Bloqueadores:</strong>
              <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px', color: '#856404' }}>
                {scheduleCheck.blocking_errors.map((error, idx) => (
                  <li key={idx}>{error}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {message && (
        <div style={{ 
          padding: '12px', 
          marginBottom: '20px', 
          borderRadius: '4px',
          backgroundColor: message.type === 'success' ? '#d4edda' : 
                          message.type === 'error' ? '#f8d7da' : 
                          message.type === 'warning' ? '#fff3cd' : '#cce5ff',
          color: message.type === 'success' ? '#155724' : 
                 message.type === 'error' ? '#721c24' : 
                 message.type === 'warning' ? '#856404' : '#004085',
          border: `1px solid ${message.type === 'success' ? '#c3e6cb' : 
                                message.type === 'error' ? '#f5c6cb' : 
                                message.type === 'warning' ? '#ffeeba' : '#b8daff'}`
        }}>
          {message.text}
        </div>
      )}

      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px', flexWrap: 'wrap' }}>
        {['overview', 'schedule', 'convocations', 'history'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab as TabType)}
            style={{
              padding: '10px 20px',
              borderRadius: '4px',
              border: activeTab === tab ? '2px solid #0056b3' : '1px solid #ccc',
              backgroundColor: activeTab === tab ? '#e7f1ff' : 'white',
              cursor: 'pointer',
              fontWeight: activeTab === tab ? 'bold' : 'normal'
            }}
          >
            {tab === 'overview' && 'Visão Geral'}
            {tab === 'schedule' && 'Escala da Semana'}
            {tab === 'convocations' && 'Convocações'}
            {tab === 'history' && 'Histórico'}
          </button>
        ))}
      </div>

      {loading && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
          Carregando...
        </div>
      )}

      {activeTab === 'overview' && !loading && (
        <div>
          <h3>Fluxo de Trabalho</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '15px', marginBottom: '30px' }}>
            <div style={{ 
              backgroundColor: 'white', 
              border: '1px solid #dee2e6', 
              borderRadius: '8px', 
              padding: '20px',
              borderLeft: `4px solid ${scheduleCheck?.has_schedule ? '#28a745' : '#6c757d'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <span style={{ 
                  backgroundColor: scheduleCheck?.has_schedule ? '#28a745' : '#6c757d', 
                  color: 'white', 
                  borderRadius: '50%', 
                  width: '30px', 
                  height: '30px', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center' 
                }}>1</span>
                <strong>Verificar Escala</strong>
              </div>
              <p style={{ color: '#666', fontSize: '14px', margin: 0 }}>
                {scheduleCheck?.has_schedule 
                  ? `Escala encontrada: ${scheduleCheck.schedule?.status}` 
                  : 'Gere a escala no módulo de Governança'}
              </p>
            </div>

            <div style={{ 
              backgroundColor: 'white', 
              border: '1px solid #dee2e6', 
              borderRadius: '8px', 
              padding: '20px',
              borderLeft: `4px solid ${scheduleCheck?.schedule?.status === 'publicada' ? '#28a745' : '#6c757d'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <span style={{ 
                  backgroundColor: scheduleCheck?.schedule?.status === 'publicada' ? '#28a745' : '#6c757d', 
                  color: 'white', 
                  borderRadius: '50%', 
                  width: '30px', 
                  height: '30px', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center' 
                }}>2</span>
                <strong>Publicar Escala</strong>
              </div>
              <p style={{ color: '#666', fontSize: '14px', margin: 0 }}>
                {scheduleCheck?.schedule?.status === 'publicada' 
                  ? 'Escala publicada e pronta' 
                  : 'Publique a escala antes de gerar convocações'}
              </p>
            </div>

            <div style={{ 
              backgroundColor: 'white', 
              border: '1px solid #dee2e6', 
              borderRadius: '8px', 
              padding: '20px',
              borderLeft: `4px solid ${canGenerateConvocations() ? '#28a745' : '#6c757d'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <span style={{ 
                  backgroundColor: canGenerateConvocations() ? '#28a745' : '#6c757d', 
                  color: 'white', 
                  borderRadius: '50%', 
                  width: '30px', 
                  height: '30px', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center' 
                }}>3</span>
                <strong>Gerar Convocações</strong>
              </div>
              <p style={{ color: '#666', fontSize: '14px', margin: 0 }}>
                {convocations.length > 0 
                  ? `${convocations.length} convocação(ões) gerada(s)` 
                  : 'Clique para gerar convocações'}
              </p>
            </div>

            <div style={{ 
              backgroundColor: 'white', 
              border: '1px solid #dee2e6', 
              borderRadius: '8px', 
              padding: '20px',
              borderLeft: `4px solid ${(stats?.accepted || 0) > 0 ? '#28a745' : '#6c757d'}`
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '10px' }}>
                <span style={{ 
                  backgroundColor: (stats?.accepted || 0) > 0 ? '#28a745' : '#6c757d', 
                  color: 'white', 
                  borderRadius: '50%', 
                  width: '30px', 
                  height: '30px', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center' 
                }}>4</span>
                <strong>Acompanhar Respostas</strong>
              </div>
              <p style={{ color: '#666', fontSize: '14px', margin: 0 }}>
                {stats ? `${stats.accepted} aceitas, ${stats.pending} pendentes` : 'Aguardando convocações'}
              </p>
            </div>
          </div>

          {stats && (
            <div>
              <h3>Estatísticas da Semana</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: '15px', marginBottom: '20px' }}>
                <div style={{ backgroundColor: 'white', padding: '15px', borderRadius: '8px', border: '1px solid #dee2e6', textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#333' }}>{stats.total}</div>
                  <div style={{ fontSize: '14px', color: '#666' }}>Total</div>
                </div>
                <div style={{ backgroundColor: '#fef3c7', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#92400e' }}>{stats.pending}</div>
                  <div style={{ fontSize: '14px', color: '#92400e' }}>Pendentes</div>
                </div>
                <div style={{ backgroundColor: '#d1fae5', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#065f46' }}>{stats.accepted}</div>
                  <div style={{ fontSize: '14px', color: '#065f46' }}>Aceitas</div>
                </div>
                <div style={{ backgroundColor: '#fee2e2', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#991b1b' }}>{stats.declined}</div>
                  <div style={{ fontSize: '14px', color: '#991b1b' }}>Recusadas</div>
                </div>
                <div style={{ backgroundColor: '#f3f4f6', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#4b5563' }}>{stats.expired}</div>
                  <div style={{ fontSize: '14px', color: '#4b5563' }}>Expiradas</div>
                </div>
                <div style={{ backgroundColor: '#dbeafe', padding: '15px', borderRadius: '8px', textAlign: 'center' }}>
                  <div style={{ fontSize: '28px', fontWeight: 'bold', color: '#1e40af' }}>{stats.acceptance_rate.toFixed(1)}%</div>
                  <div style={{ fontSize: '14px', color: '#1e40af' }}>Taxa Aceite</div>
                </div>
              </div>
            </div>
          )}

          <div style={{ marginTop: '20px' }}>
            <button 
              onClick={generateConvocations}
              disabled={loading || !canGenerateConvocations()}
              className="btn-primary"
              style={{ 
                opacity: canGenerateConvocations() ? 1 : 0.5,
                cursor: canGenerateConvocations() ? 'pointer' : 'not-allowed'
              }}
            >
              Gerar Convocações da Escala
            </button>
            {!canGenerateConvocations() && (
              <p style={{ color: '#dc3545', fontSize: '14px', marginTop: '10px' }}>
                Não é possível gerar convocações. Verifique se a escala está publicada e possui turnos definidos.
              </p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'schedule' && !loading && (
        <div>
          <h3>Escala da Semana</h3>
          
          {!scheduleCheck?.has_schedule ? (
            <div style={{ 
              backgroundColor: '#fff3cd', 
              padding: '20px', 
              borderRadius: '8px',
              border: '1px solid #ffeeba'
            }}>
              <h4 style={{ color: '#856404', margin: '0 0 10px 0' }}>Nenhuma Escala Encontrada</h4>
              <p style={{ color: '#856404', margin: 0 }}>
                Não há escala cadastrada para o setor {selectedSector?.name || '-'} na semana de {weekStart}.
                <br />
                Acesse o módulo de <strong>Governança</strong> para gerar a escala primeiro.
              </p>
            </div>
          ) : (
            <>
              <div style={{ 
                backgroundColor: 'white', 
                border: '1px solid #dee2e6', 
                borderRadius: '8px', 
                padding: '20px', 
                marginBottom: '20px' 
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                  <div>
                    <strong>Escala #{scheduleCheck.schedule?.id}</strong>
                    <span style={{ marginLeft: '10px', ...getScheduleStatusBadge(scheduleCheck.schedule?.status || '') }}>
                      {scheduleCheck.schedule?.status}
                    </span>
                  </div>
                  <div style={{ color: '#666' }}>
                    Período: {formatDate(scheduleCheck.schedule?.week_start || '')} a {formatDate(scheduleCheck.schedule?.week_end || '')}
                  </div>
                </div>
                {scheduleCheck.schedule?.notes && (
                  <p style={{ color: '#666', marginTop: '10px', marginBottom: 0 }}>
                    Observações: {scheduleCheck.schedule.notes}
                  </p>
                )}
              </div>

              {scheduleCheck.shifts && scheduleCheck.shifts.length > 0 ? (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white' }}>
                    <thead>
                      <tr style={{ backgroundColor: '#f8f9fa' }}>
                        <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Data</th>
                        <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Colaborador</th>
                        <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Horário</th>
                        <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Horas</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scheduleCheck.shifts.map((shift) => (
                        <tr key={shift.id} style={{ borderBottom: '1px solid #dee2e6' }}>
                          <td style={{ padding: '12px' }}>{formatDate(shift.date)}</td>
                          <td style={{ padding: '12px' }}>{shift.employee_name || `ID: ${shift.employee_id}`}</td>
                          <td style={{ padding: '12px' }}>
                            {formatTime(shift.start_time)} - {formatTime(shift.end_time)}
                          </td>
                          <td style={{ padding: '12px' }}>{shift.planned_hours?.toFixed(1)}h</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ 
                  backgroundColor: '#fff3cd', 
                  padding: '20px', 
                  borderRadius: '8px',
                  border: '1px solid #ffeeba'
                }}>
                  <p style={{ color: '#856404', margin: 0 }}>
                    A escala existe mas não possui turnos definidos. Configure os turnos no módulo de Governança.
                  </p>
                </div>
              )}

              <div style={{ marginTop: '20px' }}>
                <button 
                  onClick={generateConvocations}
                  disabled={loading || !canGenerateConvocations()}
                  className="btn-primary"
                  style={{ 
                    opacity: canGenerateConvocations() ? 1 : 0.5,
                    cursor: canGenerateConvocations() ? 'pointer' : 'not-allowed'
                  }}
                >
                  Gerar Convocações desta Escala
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {activeTab === 'convocations' && !loading && (
        <div>
          <h3>Convocações da Semana</h3>
          
          {convocations.length === 0 ? (
            <div style={{ 
              backgroundColor: '#f8f9fa', 
              padding: '40px', 
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <p style={{ color: '#666', margin: 0 }}>
                Nenhuma convocação encontrada para esta semana.
              </p>
              {canGenerateConvocations() && (
                <button 
                  onClick={generateConvocations}
                  disabled={loading}
                  className="btn-primary"
                  style={{ marginTop: '15px' }}
                >
                  Gerar Convocações
                </button>
              )}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa' }}>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Colaborador</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Data</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Horário</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Horas</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Status</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Prazo Resposta</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Ações</th>
                  </tr>
                </thead>
                <tbody>
                  {convocations.map((conv) => (
                    <tr key={conv.id} style={{ borderBottom: '1px solid #dee2e6' }}>
                      <td style={{ padding: '12px' }}>
                        <div>{conv.employee_name || `ID: ${conv.employee_id}`}</div>
                        {!conv.legal_validation_passed && (
                          <span style={{ fontSize: '12px', color: '#dc3545' }}>Validação pendente</span>
                        )}
                      </td>
                      <td style={{ padding: '12px' }}>{formatDate(conv.date)}</td>
                      <td style={{ padding: '12px' }}>
                        {formatTime(conv.start_time)} - {formatTime(conv.end_time)}
                      </td>
                      <td style={{ padding: '12px' }}>{conv.total_hours?.toFixed(1)}h</td>
                      <td style={{ padding: '12px' }}>
                        <span style={getStatusBadge(conv.status)}>{conv.status}</span>
                      </td>
                      <td style={{ padding: '12px', fontSize: '14px', color: '#666' }}>
                        {conv.response_deadline ? new Date(conv.response_deadline).toLocaleString('pt-BR') : '-'}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {conv.status === 'pendente' && (
                          <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                            <button
                              onClick={() => openResponseModal(conv, 'accept')}
                              style={{ 
                                padding: '4px 8px', 
                                fontSize: '12px', 
                                backgroundColor: '#28a745', 
                                color: 'white', 
                                border: 'none', 
                                borderRadius: '4px', 
                                cursor: 'pointer' 
                              }}
                            >
                              Aceitar
                            </button>
                            <button
                              onClick={() => openResponseModal(conv, 'decline')}
                              style={{ 
                                padding: '4px 8px', 
                                fontSize: '12px', 
                                backgroundColor: '#dc3545', 
                                color: 'white', 
                                border: 'none', 
                                borderRadius: '4px', 
                                cursor: 'pointer' 
                              }}
                            >
                              Recusar
                            </button>
                          </div>
                        )}
                        {(conv.status === 'pendente' || conv.status === 'aceita') && (
                          <button
                            onClick={() => openResponseModal(conv, 'cancel')}
                            style={{ 
                              padding: '4px 8px', 
                              fontSize: '12px', 
                              backgroundColor: '#6c757d', 
                              color: 'white', 
                              border: 'none', 
                              borderRadius: '4px', 
                              cursor: 'pointer',
                              marginTop: '5px'
                            }}
                          >
                            Cancelar
                          </button>
                        )}
                        {conv.decline_reason && (
                          <div style={{ fontSize: '12px', color: '#dc3545', marginTop: '5px' }}>
                            Motivo: {conv.decline_reason.substring(0, 30)}...
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {generateResult && (
            <div style={{ 
              marginTop: '20px', 
              backgroundColor: generateResult.errors.length > 0 ? '#fff3cd' : '#d4edda', 
              padding: '15px', 
              borderRadius: '8px',
              border: `1px solid ${generateResult.errors.length > 0 ? '#ffeeba' : '#c3e6cb'}`
            }}>
              <h4 style={{ margin: '0 0 10px 0' }}>Resultado da Geração</h4>
              <p style={{ margin: '5px 0' }}>Convocações criadas: {generateResult.convocations_created}</p>
              <p style={{ margin: '5px 0' }}>Convocações bloqueadas: {generateResult.convocations_blocked}</p>
              {generateResult.errors.length > 0 && (
                <div style={{ marginTop: '10px' }}>
                  <strong>Erros:</strong>
                  <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px' }}>
                    {generateResult.errors.map((err, idx) => (
                      <li key={idx} style={{ color: '#856404' }}>{err}</li>
                    ))}
                  </ul>
                </div>
              )}
              {generateResult.warnings.length > 0 && (
                <div style={{ marginTop: '10px' }}>
                  <strong>Avisos:</strong>
                  <ul style={{ margin: '5px 0 0 0', paddingLeft: '20px' }}>
                    {generateResult.warnings.map((warn, idx) => (
                      <li key={idx} style={{ color: '#856404' }}>{warn}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'history' && !loading && (
        <div>
          <h3>Histórico de Convocações</h3>
          <p style={{ color: '#666' }}>
            Visualize todas as convocações do setor, incluindo semanas anteriores.
          </p>
          
          {convocations.filter(c => c.responded_at || c.status !== 'pendente').length === 0 ? (
            <div style={{ 
              backgroundColor: '#f8f9fa', 
              padding: '40px', 
              borderRadius: '8px',
              textAlign: 'center'
            }}>
              <p style={{ color: '#666', margin: 0 }}>
                Nenhum histórico de respostas para esta semana.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', backgroundColor: 'white' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f8f9fa' }}>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Colaborador</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Data Turno</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Status Final</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Respondido Em</th>
                    <th style={{ padding: '12px', textAlign: 'left', borderBottom: '2px solid #dee2e6' }}>Motivo/Observações</th>
                  </tr>
                </thead>
                <tbody>
                  {convocations
                    .filter(c => c.responded_at || c.status !== 'pendente')
                    .map((conv) => (
                      <tr key={conv.id} style={{ borderBottom: '1px solid #dee2e6' }}>
                        <td style={{ padding: '12px' }}>{conv.employee_name || `ID: ${conv.employee_id}`}</td>
                        <td style={{ padding: '12px' }}>{formatDate(conv.date)}</td>
                        <td style={{ padding: '12px' }}>
                          <span style={getStatusBadge(conv.status)}>{conv.status}</span>
                        </td>
                        <td style={{ padding: '12px', fontSize: '14px', color: '#666' }}>
                          {conv.responded_at ? new Date(conv.responded_at).toLocaleString('pt-BR') : '-'}
                        </td>
                        <td style={{ padding: '12px', fontSize: '14px', color: '#666' }}>
                          {conv.decline_reason || '-'}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {showResponseModal && selectedConvocation && (
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
            borderRadius: '8px', 
            padding: '24px', 
            maxWidth: '500px', 
            width: '90%',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <h2 style={{ marginTop: 0 }}>
              {modalAction === 'accept' && 'Aceitar Convocação'}
              {modalAction === 'decline' && 'Recusar Convocação'}
              {modalAction === 'cancel' && 'Cancelar Convocação'}
            </h2>

            <div style={{ backgroundColor: '#f8f9fa', padding: '15px', borderRadius: '4px', marginBottom: '20px' }}>
              <p style={{ margin: '5px 0' }}><strong>Colaborador:</strong> {selectedConvocation.employee_name}</p>
              <p style={{ margin: '5px 0' }}><strong>Data:</strong> {formatDate(selectedConvocation.date)}</p>
              <p style={{ margin: '5px 0' }}><strong>Horário:</strong> {formatTime(selectedConvocation.start_time)} - {formatTime(selectedConvocation.end_time)}</p>
              <p style={{ margin: '5px 0' }}><strong>Horas:</strong> {selectedConvocation.total_hours?.toFixed(1)}h</p>
            </div>

            {(modalAction === 'decline' || modalAction === 'cancel') && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  {modalAction === 'decline' ? 'Motivo da Recusa' : 'Motivo do Cancelamento'}
                </label>
                <textarea
                  value={declineReason}
                  onChange={(e) => setDeclineReason(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ccc', minHeight: '80px' }}
                  placeholder="Informe o motivo..."
                />
              </div>
            )}

            {modalAction !== 'cancel' && (
              <div style={{ marginBottom: '15px' }}>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
                  Observações (opcional)
                </label>
                <textarea
                  value={responseNotes}
                  onChange={(e) => setResponseNotes(e.target.value)}
                  style={{ width: '100%', padding: '10px', borderRadius: '4px', border: '1px solid #ccc', minHeight: '60px' }}
                  placeholder="Observações adicionais..."
                />
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                onClick={() => {
                  setShowResponseModal(false);
                  setSelectedConvocation(null);
                  setModalAction(null);
                  setDeclineReason('');
                  setResponseNotes('');
                }}
                style={{ 
                  padding: '10px 20px', 
                  backgroundColor: '#f8f9fa', 
                  border: '1px solid #ccc', 
                  borderRadius: '4px', 
                  cursor: 'pointer' 
                }}
              >
                Cancelar
              </button>
              <button
                onClick={handleConvocationResponse}
                style={{ 
                  padding: '10px 20px', 
                  backgroundColor: modalAction === 'accept' ? '#28a745' : modalAction === 'decline' ? '#dc3545' : '#6c757d',
                  color: 'white', 
                  border: 'none', 
                  borderRadius: '4px', 
                  cursor: 'pointer' 
                }}
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
