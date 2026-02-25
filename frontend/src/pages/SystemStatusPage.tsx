import { useState, useEffect } from 'react';
import { apiClient } from '../services/client';

interface SystemStatus {
  timestamp: string;
  system_healthy: boolean;
  ready_to_generate_schedules: boolean;
  data_status: {
    last_hp_upload: { date: string | null; days_ago: number | null };
    last_checkin_upload: { date: string | null; days_ago: number | null };
    last_checkout_upload: { date: string | null; days_ago: number | null };
  };
  operations_status: {
    last_forecast_run: { id: number | null; date: string | null; type: string | null };
    last_schedule_generated: { id: number | null; date: string | null; week_start: string | null };
    last_convocation: { id: number | null; date: string | null };
    pending_convocations: number;
  };
  configuration_status: {
    sectors_configured: number;
    calendar_events_next_30_days: number;
    labor_rules_active: boolean;
  };
  alerts: Array<{ type: string; category: string; message: string }>;
  alerts_summary: { errors: number; warnings: number; info: number };
}

interface ReadinessCheck {
  all_passed: boolean;
  production_ready: boolean;
  checks: Array<{
    id: string;
    name: string;
    passed: boolean;
    value: string | number;
    required: string;
  }>;
  summary: { total: number; passed: number; failed: number };
  blocking_actions: string[];
}

export default function SystemStatusPage() {
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [readiness, setReadiness] = useState<ReadinessCheck | null>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [statusRes, readinessRes] = await Promise.all([
        apiClient.get('/compliance/system-status'),
        apiClient.get('/compliance/readiness-checklist')
      ]);
      setStatus(statusRes.data);
      setReadiness(readinessRes.data);
    } catch (error) {
      console.error('Error loading system status:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('pt-BR');
  };

  if (loading) {
    return <div style={{ padding: '20px' }}>Carregando status do sistema...</div>;
  }

  return (
    <div style={{ padding: '20px' }}>
      <h1>Status do Sistema</h1>
      <p style={{ color: '#6b7280', marginBottom: '20px' }}>
        Ultima verificacao: {status ? formatDate(status.timestamp) : '-'}
      </p>

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
        gap: '20px',
        marginBottom: '30px'
      }}>
        <div style={{ 
          padding: '20px', 
          borderRadius: '8px', 
          backgroundColor: status?.system_healthy ? '#ecfdf5' : '#fef2f2',
          border: `2px solid ${status?.system_healthy ? '#10b981' : '#ef4444'}`
        }}>
          <h3 style={{ margin: '0 0 10px 0', color: status?.system_healthy ? '#10b981' : '#ef4444' }}>
            {status?.system_healthy ? 'Sistema Saudavel' : 'Atencao Necessaria'}
          </h3>
          <p style={{ margin: 0, fontSize: '14px' }}>
            {status?.ready_to_generate_schedules 
              ? 'Pronto para gerar escalas' 
              : 'Nao esta pronto para gerar escalas'}
          </p>
        </div>

        <div style={{ 
          padding: '20px', 
          borderRadius: '8px', 
          backgroundColor: readiness?.production_ready ? '#ecfdf5' : '#fef3c7',
          border: `2px solid ${readiness?.production_ready ? '#10b981' : '#f59e0b'}`
        }}>
          <h3 style={{ margin: '0 0 10px 0', color: readiness?.production_ready ? '#10b981' : '#f59e0b' }}>
            {readiness?.production_ready ? 'Pronto para Producao' : 'Pendencias para Producao'}
          </h3>
          <p style={{ margin: 0, fontSize: '14px' }}>
            {readiness?.summary.passed} de {readiness?.summary.total} verificacoes passaram
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px' }}>
        <div style={{ backgroundColor: '#f8fafc', padding: '20px', borderRadius: '8px' }}>
          <h3 style={{ marginTop: 0 }}>Status dos Dados</h3>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              <tr>
                <td style={{ padding: '8px 0' }}>Ultimo Upload HP:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>
                  {status?.data_status.last_hp_upload.date 
                    ? `${formatDate(status.data_status.last_hp_upload.date)} (${status.data_status.last_hp_upload.days_ago} dias)`
                    : 'Nenhum'}
                </td>
              </tr>
              <tr>
                <td style={{ padding: '8px 0' }}>Ultimo Checkin:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>
                  {status?.data_status.last_checkin_upload.date 
                    ? formatDate(status.data_status.last_checkin_upload.date)
                    : 'Nenhum'}
                </td>
              </tr>
              <tr>
                <td style={{ padding: '8px 0' }}>Ultimo Checkout:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>
                  {status?.data_status.last_checkout_upload.date 
                    ? formatDate(status.data_status.last_checkout_upload.date)
                    : 'Nenhum'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div style={{ backgroundColor: '#f8fafc', padding: '20px', borderRadius: '8px' }}>
          <h3 style={{ marginTop: 0 }}>Status das Operacoes</h3>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              <tr>
                <td style={{ padding: '8px 0' }}>Ultimo Forecast Run:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>
                  {status?.operations_status.last_forecast_run.date 
                    ? `${formatDate(status.operations_status.last_forecast_run.date)} (${status.operations_status.last_forecast_run.type})`
                    : 'Nenhum'}
                </td>
              </tr>
              <tr>
                <td style={{ padding: '8px 0' }}>Ultima Escala Gerada:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>
                  {status?.operations_status.last_schedule_generated.week_start 
                    ? `Semana de ${status.operations_status.last_schedule_generated.week_start}`
                    : 'Nenhuma'}
                </td>
              </tr>
              <tr>
                <td style={{ padding: '8px 0' }}>Ultima Convocacao:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>
                  {status?.operations_status.last_convocation.date 
                    ? formatDate(status.operations_status.last_convocation.date)
                    : 'Nenhuma'}
                </td>
              </tr>
              <tr>
                <td style={{ padding: '8px 0' }}>Convocacoes Pendentes:</td>
                <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 'bold' }}>
                  {status?.operations_status.pending_convocations}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div style={{ backgroundColor: '#f8fafc', padding: '20px', borderRadius: '8px' }}>
          <h3 style={{ marginTop: 0 }}>Configuracao</h3>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              <tr>
                <td style={{ padding: '8px 0' }}>Setores Configurados:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>{status?.configuration_status.sectors_configured}</td>
              </tr>
              <tr>
                <td style={{ padding: '8px 0' }}>Eventos Calendario (30 dias):</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>{status?.configuration_status.calendar_events_next_30_days}</td>
              </tr>
              <tr>
                <td style={{ padding: '8px 0' }}>Regras Trabalhistas:</td>
                <td style={{ padding: '8px 0', textAlign: 'right' }}>
                  {status?.configuration_status.labor_rules_active ? 'Ativas' : 'Nao configuradas'}
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        {status && status.alerts.length > 0 && (
          <div style={{ backgroundColor: '#fef2f2', padding: '20px', borderRadius: '8px' }}>
            <h3 style={{ marginTop: 0, color: '#ef4444' }}>
              Alertas ({status.alerts_summary.errors} erros, {status.alerts_summary.warnings} avisos)
            </h3>
            <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '14px' }}>
              {status.alerts.map((alert, idx) => (
                <li key={idx} style={{ 
                  marginBottom: '8px',
                  color: alert.type === 'error' ? '#ef4444' : alert.type === 'warning' ? '#f59e0b' : '#6b7280'
                }}>
                  [{alert.category}] {alert.message}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <h2 style={{ marginTop: '40px' }}>Checklist de Prontidao</h2>
      
      {readiness && (
        <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
          <thead>
            <tr style={{ backgroundColor: '#f3f4f6' }}>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Verificacao</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Status</th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Valor Atual</th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Requisito</th>
            </tr>
          </thead>
          <tbody>
            {readiness.checks.map(check => (
              <tr key={check.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: '12px' }}>{check.name}</td>
                <td style={{ padding: '12px', textAlign: 'center' }}>
                  <span style={{ 
                    padding: '4px 12px', 
                    borderRadius: '12px',
                    backgroundColor: check.passed ? '#ecfdf5' : '#fef2f2',
                    color: check.passed ? '#10b981' : '#ef4444',
                    fontSize: '12px',
                    fontWeight: 'bold'
                  }}>
                    {check.passed ? 'OK' : 'PENDENTE'}
                  </span>
                </td>
                <td style={{ padding: '12px' }}>{check.value}</td>
                <td style={{ padding: '12px', color: '#6b7280' }}>{check.required}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {readiness && readiness.blocking_actions.length > 0 && (
        <div style={{ 
          marginTop: '20px', 
          padding: '15px', 
          backgroundColor: '#fef2f2', 
          borderRadius: '8px',
          border: '1px solid #ef4444'
        }}>
          <strong style={{ color: '#ef4444' }}>Acoes Bloqueadas:</strong>
          <ul style={{ margin: '10px 0 0 0', paddingLeft: '20px' }}>
            {readiness.blocking_actions.map((action, idx) => (
              <li key={idx}>{action}</li>
            ))}
          </ul>
        </div>
      )}

      <button 
        onClick={loadData}
        style={{ 
          marginTop: '30px',
          padding: '10px 20px', 
          backgroundColor: '#3b82f6', 
          color: 'white', 
          border: 'none', 
          borderRadius: '4px', 
          cursor: 'pointer' 
        }}
      >
        Atualizar Status
      </button>
    </div>
  );
}
