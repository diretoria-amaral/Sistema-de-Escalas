import { useState, useEffect } from 'react';
import { intelligenceApi } from '../services/client';

interface DashboardData {
  deviation_patterns: Array<{
    day: string;
    correction_factor: number;
    avg_deviation: number;
    samples: number;
    confidence: string;
  }>;
  next_7_days_forecast: Array<{
    date: string;
    day_name: string;
    has_forecast: boolean;
    original_occupancy?: number;
    corrected_occupancy?: number;
    correction_factor?: number;
    confidence?: string;
  }>;
  pending_adjustments: {
    high_priority: number;
    total: number;
    items: Array<{
      date: string;
      day_name: string;
      adjustment: number;
      adjustment_reason: string;
      priority: string;
    }>;
  };
  recent_accuracy: {
    score: number;
    based_on_days: number;
    avg_deviation: number;
  };
}

export default function IntelligencePage() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [recalculating, setRecalculating] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      const response = await intelligenceApi.getDashboard();
      setDashboard(response.data);
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao carregar dashboard' });
    } finally {
      setLoading(false);
    }
  };

  const handleRecalculate = async () => {
    setRecalculating(true);
    try {
      await intelligenceApi.recalculateDeviations();
      setMessage({ type: 'success', text: 'Desvios recalculados com sucesso!' });
      loadDashboard();
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao recalcular desvios' });
    } finally {
      setRecalculating(false);
    }
  };

  const getConfidenceColor = (confidence: string) => {
    switch (confidence) {
      case 'high': return '#28a745';
      case 'medium': return '#ffc107';
      default: return '#dc3545';
    }
  };

  const getPriorityStyle = (priority: string) => {
    switch (priority) {
      case 'high': return { backgroundColor: '#dc3545', color: 'white' };
      case 'medium': return { backgroundColor: '#ffc107', color: 'black' };
      default: return { backgroundColor: '#6c757d', color: 'white' };
    }
  };

  if (loading) return <div className="card"><p>Carregando dashboard...</p></div>;

  return (
    <div>
      {message && (
        <div style={{ 
          padding: '10px', 
          marginBottom: '15px', 
          borderRadius: '4px',
          backgroundColor: message.type === 'success' ? '#d4edda' : '#f8d7da',
          color: message.type === 'success' ? '#155724' : '#721c24'
        }}>
          {message.text}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '15px', marginBottom: '20px' }}>
        <div className="card" style={{ textAlign: 'center', padding: '20px' }}>
          <h3 style={{ margin: 0, color: '#666' }}>Precisão Recente</h3>
          <p style={{ fontSize: '36px', fontWeight: 'bold', margin: '10px 0', color: dashboard?.recent_accuracy.score && dashboard.recent_accuracy.score >= 80 ? '#28a745' : '#ffc107' }}>
            {dashboard?.recent_accuracy.score?.toFixed(1) || 0}%
          </p>
          <small>Baseado em {dashboard?.recent_accuracy.based_on_days || 0} dias</small>
        </div>

        <div className="card" style={{ textAlign: 'center', padding: '20px' }}>
          <h3 style={{ margin: 0, color: '#666' }}>Desvio Médio</h3>
          <p style={{ fontSize: '36px', fontWeight: 'bold', margin: '10px 0' }}>
            {dashboard?.recent_accuracy.avg_deviation?.toFixed(1) || 0}%
          </p>
          <small>Últimos 7 dias</small>
        </div>

        <div className="card" style={{ textAlign: 'center', padding: '20px' }}>
          <h3 style={{ margin: 0, color: '#666' }}>Ajustes Pendentes</h3>
          <p style={{ fontSize: '36px', fontWeight: 'bold', margin: '10px 0', color: dashboard?.pending_adjustments.high_priority ? '#dc3545' : '#28a745' }}>
            {dashboard?.pending_adjustments.total || 0}
          </p>
          <small>{dashboard?.pending_adjustments.high_priority || 0} alta prioridade</small>
        </div>

        <div className="card" style={{ textAlign: 'center', padding: '20px' }}>
          <button 
            className="btn btn-primary" 
            onClick={handleRecalculate}
            disabled={recalculating}
            style={{ width: '100%', height: '100%' }}
          >
            {recalculating ? 'Recalculando...' : 'Recalcular Desvios'}
          </button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        <div className="card">
          <h2>Padrões de Desvio por Dia da Semana</h2>
          <p style={{ color: '#666', marginBottom: '15px' }}>
            Fator de correção baseado no histórico de previsões vs realizados
          </p>
          <table>
            <thead>
              <tr>
                <th>Dia</th>
                <th>Fator Correção</th>
                <th>Desvio Médio</th>
                <th>Amostras</th>
                <th>Confiança</th>
              </tr>
            </thead>
            <tbody>
              {dashboard?.deviation_patterns?.length === 0 ? (
                <tr><td colSpan={5} style={{ textAlign: 'center' }}>Nenhum dado disponível. Faça upload de relatórios.</td></tr>
              ) : (
                dashboard?.deviation_patterns?.map((pattern, idx) => (
                  <tr key={idx}>
                    <td><strong>{pattern.day}</strong></td>
                    <td style={{ fontWeight: 'bold', color: pattern.correction_factor > 1 ? '#28a745' : pattern.correction_factor < 1 ? '#dc3545' : 'inherit' }}>
                      {pattern.correction_factor != null ? Number(pattern.correction_factor).toFixed(3) : '1.000'}x
                    </td>
                    <td>{pattern.avg_deviation != null ? Number(pattern.avg_deviation).toFixed(1) : '0.0'}%</td>
                    <td>{pattern.samples ?? 0}</td>
                    <td>
                      <span style={{ 
                        padding: '2px 8px', 
                        borderRadius: '4px', 
                        backgroundColor: getConfidenceColor(pattern.confidence),
                        color: 'white',
                        fontSize: '12px'
                      }}>
                        {pattern.confidence}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="card">
          <h2>Previsão Próximos 7 Dias</h2>
          <p style={{ color: '#666', marginBottom: '15px' }}>
            Ocupação prevista com correção baseada no histórico
          </p>
          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Dia</th>
                <th>Previsão Original</th>
                <th>Previsão Corrigida</th>
                <th>Confiança</th>
              </tr>
            </thead>
            <tbody>
              {dashboard?.next_7_days_forecast?.map((day, idx) => (
                <tr key={idx}>
                  <td>{day.date}</td>
                  <td><strong>{day.day_name}</strong></td>
                  <td>{day.has_forecast && day.original_occupancy != null ? `${Number(day.original_occupancy).toFixed(1)}%` : '-'}</td>
                  <td style={{ fontWeight: 'bold' }}>
                    {day.has_forecast && day.corrected_occupancy != null ? `${Number(day.corrected_occupancy).toFixed(1)}%` : '-'}
                  </td>
                  <td>
                    {day.confidence && (
                      <span style={{ 
                        padding: '2px 8px', 
                        borderRadius: '4px', 
                        backgroundColor: getConfidenceColor(day.confidence),
                        color: 'white',
                        fontSize: '12px'
                      }}>
                        {day.confidence}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Recomendações de Ajuste de Escala</h2>
        <p style={{ color: '#666', marginBottom: '15px' }}>
          Baseado nas correções de previsão, o sistema recomenda os seguintes ajustes
        </p>
        <table>
          <thead>
            <tr>
              <th>Data</th>
              <th>Dia</th>
              <th>Ajuste</th>
              <th>Motivo</th>
              <th>Prioridade</th>
            </tr>
          </thead>
          <tbody>
            {dashboard?.pending_adjustments?.items?.length === 0 ? (
              <tr><td colSpan={5} style={{ textAlign: 'center' }}>Nenhum ajuste recomendado no momento</td></tr>
            ) : (
              dashboard?.pending_adjustments?.items?.map((item, idx) => (
                <tr key={idx}>
                  <td>{item.date}</td>
                  <td><strong>{item.day_name}</strong></td>
                  <td style={{ fontWeight: 'bold', color: item.adjustment > 0 ? '#28a745' : '#dc3545' }}>
                    {item.adjustment > 0 ? '+' : ''}{item.adjustment} colaboradores
                  </td>
                  <td>{item.adjustment_reason}</td>
                  <td>
                    <span style={{ 
                      padding: '2px 8px', 
                      borderRadius: '4px', 
                      ...getPriorityStyle(item.priority),
                      fontSize: '12px'
                    }}>
                      {item.priority}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
