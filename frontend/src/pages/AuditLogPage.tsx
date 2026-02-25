import { useState, useEffect } from 'react';
import { apiClient } from '../services/client';

interface AuditLogEntry {
  id: number;
  timestamp: string;
  action: string;
  entity_type: string;
  entity_id: number;
  description: string;
  user_id: number | null;
  old_values: string | null;
  new_values: string | null;
}

export default function AuditLogPage() {
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 50;

  const [actionFilter, setActionFilter] = useState<string>('');
  const [entityTypeFilter, setEntityTypeFilter] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  const actions = [
    'schedule_generated',
    'schedule_published',
    'schedule_modified',
    'report_upload',
    'report_process',
    'settings_change',
    'deviation_calculated',
    'forecast_run_created',
    'forecast_run_locked',
    'demand_calculated',
    'employee_created',
    'employee_updated',
    'convocation_created',
    'convocation_accepted',
    'convocation_declined',
    'convocation_expired',
    'convocation_cancelled',
    'reschedule_triggered'
  ];

  const entityTypes = [
    'convocation',
    'schedule',
    'employee',
    'sector',
    'forecast_run',
    'report_upload'
  ];

  useEffect(() => {
    loadLogs();
  }, [offset, actionFilter, entityTypeFilter, dateFrom, dateTo]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { limit, offset };
      if (actionFilter) params.action = actionFilter;
      if (entityTypeFilter) params.entity_type = entityTypeFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const response = await apiClient.get('/reports/audit-log', { params });
      setLogs(response.data.logs);
      setTotal(response.data.total);
    } catch (error) {
      console.error('Error loading logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportCSV = async () => {
    try {
      const params: Record<string, string> = {};
      if (actionFilter) params.action = actionFilter;
      if (entityTypeFilter) params.entity_type = entityTypeFilter;
      if (dateFrom) params.date_from = dateFrom;
      if (dateTo) params.date_to = dateTo;

      const response = await apiClient.get('/reports/export/audit-log-csv', {
        params,
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `audit_log_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error exporting:', error);
    }
  };

  const formatAction = (action: string) => {
    const labels: Record<string, string> = {
      'schedule_generated': 'Escala Gerada',
      'schedule_published': 'Escala Publicada',
      'schedule_modified': 'Escala Modificada',
      'report_upload': 'Upload Relatorio',
      'report_process': 'Processamento Relatorio',
      'settings_change': 'Alteracao Configuracao',
      'deviation_calculated': 'Desvio Calculado',
      'forecast_run_created': 'Forecast Criado',
      'forecast_run_locked': 'Forecast Bloqueado',
      'demand_calculated': 'Demanda Calculada',
      'employee_created': 'Colaborador Criado',
      'employee_updated': 'Colaborador Atualizado',
      'convocation_created': 'Convocacao Criada',
      'convocation_accepted': 'Convocacao Aceita',
      'convocation_declined': 'Convocacao Recusada',
      'convocation_expired': 'Convocacao Expirada',
      'convocation_cancelled': 'Convocacao Cancelada',
      'reschedule_triggered': 'Reescala Disparada'
    };
    return labels[action] || action;
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1>Log de Auditoria</h1>
        <button 
          onClick={exportCSV}
          style={{ 
            padding: '10px 20px', 
            backgroundColor: '#10b981', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px', 
            cursor: 'pointer' 
          }}
        >
          Exportar CSV
        </button>
      </div>

      <div style={{ 
        display: 'flex', 
        gap: '15px', 
        marginBottom: '20px',
        flexWrap: 'wrap',
        padding: '15px',
        backgroundColor: '#f3f4f6',
        borderRadius: '8px'
      }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Acao</label>
          <select 
            value={actionFilter} 
            onChange={(e) => { setActionFilter(e.target.value); setOffset(0); }}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db', minWidth: '180px' }}
          >
            <option value="">Todas as Acoes</option>
            {actions.map(a => (
              <option key={a} value={a}>{formatAction(a)}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Tipo Entidade</label>
          <select 
            value={entityTypeFilter} 
            onChange={(e) => { setEntityTypeFilter(e.target.value); setOffset(0); }}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db', minWidth: '150px' }}
          >
            <option value="">Todos</option>
            {entityTypes.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Data Inicial</label>
          <input 
            type="date" 
            value={dateFrom} 
            onChange={(e) => { setDateFrom(e.target.value); setOffset(0); }}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Data Final</label>
          <input 
            type="date" 
            value={dateTo} 
            onChange={(e) => { setDateTo(e.target.value); setOffset(0); }}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          />
        </div>
      </div>

      <div style={{ marginBottom: '15px', color: '#6b7280' }}>
        Total: {total} registros
      </div>

      {loading ? (
        <p>Carregando...</p>
      ) : logs.length === 0 ? (
        <p style={{ color: '#6b7280' }}>Nenhum registro encontrado.</p>
      ) : (
        <>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f3f4f6' }}>
                <th style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Data/Hora</th>
                <th style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Acao</th>
                <th style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Entidade</th>
                <th style={{ padding: '10px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Descricao</th>
              </tr>
            </thead>
            <tbody>
              {logs.map(log => (
                <tr key={log.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '10px', whiteSpace: 'nowrap' }}>
                    {log.timestamp ? new Date(log.timestamp).toLocaleString('pt-BR') : '-'}
                  </td>
                  <td style={{ padding: '10px' }}>
                    <span style={{ 
                      padding: '2px 6px', 
                      borderRadius: '4px', 
                      fontSize: '12px',
                      backgroundColor: '#e0f2fe',
                      color: '#0369a1'
                    }}>
                      {formatAction(log.action)}
                    </span>
                  </td>
                  <td style={{ padding: '10px' }}>
                    {log.entity_type} #{log.entity_id}
                  </td>
                  <td style={{ padding: '10px', color: '#6b7280' }}>{log.description}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginTop: '20px' }}>
            <button 
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              style={{ 
                padding: '8px 16px', 
                border: '1px solid #d1d5db', 
                borderRadius: '4px',
                cursor: offset === 0 ? 'not-allowed' : 'pointer',
                opacity: offset === 0 ? 0.5 : 1
              }}
            >
              Anterior
            </button>
            <span style={{ padding: '8px', color: '#6b7280' }}>
              Pagina {Math.floor(offset / limit) + 1} de {Math.ceil(total / limit)}
            </span>
            <button 
              onClick={() => setOffset(offset + limit)}
              disabled={offset + limit >= total}
              style={{ 
                padding: '8px 16px', 
                border: '1px solid #d1d5db', 
                borderRadius: '4px',
                cursor: offset + limit >= total ? 'not-allowed' : 'pointer',
                opacity: offset + limit >= total ? 0.5 : 1
              }}
            >
              Proximo
            </button>
          </div>
        </>
      )}
    </div>
  );
}
