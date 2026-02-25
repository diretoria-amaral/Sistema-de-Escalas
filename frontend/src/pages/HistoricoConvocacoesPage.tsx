import { useState, useEffect } from 'react';
import { apiClient } from '../services/client';

interface ConvocationSummary {
  total: number;
  accepted: number;
  declined: number;
  expired: number;
  acceptance_rate: number;
  decline_rate: number;
}

interface ConvocationRecord {
  id: number;
  date: string;
  employee_id: number;
  employee_name: string | null;
  sector_id: number;
  sector_name: string | null;
  activity_name: string | null;
  start_time: string | null;
  end_time: string | null;
  total_hours: number;
  status: string;
  generated_from: string | null;
  decline_reason: string | null;
}

interface Sector {
  id: number;
  name: string;
}

interface Employee {
  id: number;
  name: string;
}

export default function HistoricoConvocacoesPage() {
  const [loading, setLoading] = useState(false);
  const [summary, setSummary] = useState<ConvocationSummary | null>(null);
  const [convocations, setConvocations] = useState<ConvocationRecord[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [selectedEmployee, setSelectedEmployee] = useState<number | null>(null);
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');
  const [viewMode, setViewMode] = useState<'employee' | 'sector'>('employee');

  useEffect(() => {
    loadFilters();
  }, []);

  useEffect(() => {
    loadData();
  }, [selectedSector, selectedEmployee, selectedStatus, dateFrom, dateTo, viewMode]);

  const loadFilters = async () => {
    try {
      const [sectorsRes, employeesRes] = await Promise.all([
        apiClient.get('/sectors/'),
        apiClient.get('/employees/')
      ]);
      setSectors(sectorsRes.data);
      setEmployees(employeesRes.data);
    } catch (error) {
      console.error('Error loading filters:', error);
    }
  };

  const loadData = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedEmployee) params.append('employee_id', selectedEmployee.toString());
      if (selectedSector) params.append('sector_id', selectedSector.toString());
      if (selectedStatus) params.append('status', selectedStatus);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);

      const endpoint = viewMode === 'employee' 
        ? `/reports/convocations/by-employee?${params.toString()}`
        : `/reports/convocations/by-sector?${params.toString()}`;
      
      const response = await apiClient.get(endpoint);
      
      if (viewMode === 'employee') {
        setSummary(response.data.summary);
        setConvocations(response.data.convocations);
      } else {
        setSummary({
          total: response.data.summary.total_convocations,
          accepted: 0,
          declined: 0,
          expired: 0,
          acceptance_rate: 0,
          decline_rate: 0
        });
        setConvocations([]);
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportExcel = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedEmployee) params.append('employee_id', selectedEmployee.toString());
      if (selectedSector) params.append('sector_id', selectedSector.toString());
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);

      const response = await apiClient.get(`/reports/export/convocations-excel?${params.toString()}`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `convocacoes_${new Date().toISOString().split('T')[0]}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error exporting:', error);
    }
  };

  const statusLabel = (status: string) => {
    const labels: Record<string, string> = {
      'pending': 'Pendente',
      'accepted': 'Aceita',
      'declined': 'Recusada',
      'expired': 'Expirada',
      'cancelled': 'Cancelada'
    };
    return labels[status] || status;
  };

  const statusColor = (status: string) => {
    const colors: Record<string, string> = {
      'pending': '#f59e0b',
      'accepted': '#10b981',
      'declined': '#ef4444',
      'expired': '#6b7280',
      'cancelled': '#9ca3af'
    };
    return colors[status] || '#6b7280';
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1>Historico de Convocacoes</h1>
        <button 
          onClick={exportExcel}
          style={{ 
            padding: '10px 20px', 
            backgroundColor: '#10b981', 
            color: 'white', 
            border: 'none', 
            borderRadius: '4px', 
            cursor: 'pointer' 
          }}
        >
          Exportar Excel
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
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Visualizar por</label>
          <select 
            value={viewMode} 
            onChange={(e) => setViewMode(e.target.value as 'employee' | 'sector')}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          >
            <option value="employee">Colaborador</option>
            <option value="sector">Setor</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Setor</label>
          <select 
            value={selectedSector || ''} 
            onChange={(e) => setSelectedSector(e.target.value ? parseInt(e.target.value) : null)}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          >
            <option value="">Todos os Setores</option>
            {sectors.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        {viewMode === 'employee' && (
          <div>
            <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Colaborador</label>
            <select 
              value={selectedEmployee || ''} 
              onChange={(e) => setSelectedEmployee(e.target.value ? parseInt(e.target.value) : null)}
              style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
            >
              <option value="">Todos</option>
              {employees.map(e => (
                <option key={e.id} value={e.id}>{e.name}</option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Status</label>
          <select 
            value={selectedStatus} 
            onChange={(e) => setSelectedStatus(e.target.value)}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          >
            <option value="">Todos</option>
            <option value="pending">Pendente</option>
            <option value="accepted">Aceita</option>
            <option value="declined">Recusada</option>
            <option value="expired">Expirada</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Data Inicial</label>
          <input 
            type="date" 
            value={dateFrom} 
            onChange={(e) => setDateFrom(e.target.value)}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          />
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Data Final</label>
          <input 
            type="date" 
            value={dateTo} 
            onChange={(e) => setDateTo(e.target.value)}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          />
        </div>
      </div>

      {summary && (
        <div style={{ 
          display: 'grid', 
          gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
          gap: '15px', 
          marginBottom: '20px' 
        }}>
          <div style={{ padding: '15px', backgroundColor: '#f8fafc', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{summary.total}</div>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>Total</div>
          </div>
          <div style={{ padding: '15px', backgroundColor: '#ecfdf5', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>{summary.accepted}</div>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>Aceitas</div>
          </div>
          <div style={{ padding: '15px', backgroundColor: '#fef2f2', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>{summary.declined}</div>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>Recusadas</div>
          </div>
          <div style={{ padding: '15px', backgroundColor: '#f3f4f6', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#6b7280' }}>{summary.expired}</div>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>Expiradas</div>
          </div>
          <div style={{ padding: '15px', backgroundColor: '#ecfdf5', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>{summary.acceptance_rate}%</div>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>Taxa Aceite</div>
          </div>
          <div style={{ padding: '15px', backgroundColor: '#fef2f2', borderRadius: '8px', textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>{summary.decline_rate}%</div>
            <div style={{ fontSize: '12px', color: '#6b7280' }}>Taxa Recusa</div>
          </div>
        </div>
      )}

      {loading ? (
        <p>Carregando...</p>
      ) : convocations.length === 0 ? (
        <p style={{ color: '#6b7280' }}>Nenhuma convocacao encontrada para os filtros selecionados.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f3f4f6' }}>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Data</th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Colaborador</th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Setor</th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Horario</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Horas</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Status</th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Origem</th>
            </tr>
          </thead>
          <tbody>
            {convocations.map(conv => (
              <tr key={conv.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: '12px' }}>{new Date(conv.date).toLocaleDateString('pt-BR')}</td>
                <td style={{ padding: '12px' }}>{conv.employee_name || '-'}</td>
                <td style={{ padding: '12px' }}>{conv.sector_name || '-'}</td>
                <td style={{ padding: '12px' }}>{conv.start_time?.slice(0, 5)} - {conv.end_time?.slice(0, 5)}</td>
                <td style={{ padding: '12px', textAlign: 'center' }}>{conv.total_hours}h</td>
                <td style={{ padding: '12px', textAlign: 'center' }}>
                  <span style={{ 
                    padding: '4px 8px', 
                    borderRadius: '4px', 
                    fontSize: '12px',
                    backgroundColor: statusColor(conv.status) + '20',
                    color: statusColor(conv.status)
                  }}>
                    {statusLabel(conv.status)}
                  </span>
                </td>
                <td style={{ padding: '12px' }}>{conv.generated_from || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
