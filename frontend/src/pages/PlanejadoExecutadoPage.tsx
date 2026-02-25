import { useState, useEffect } from 'react';
import { apiClient } from '../services/client';

interface DailyData {
  date: string;
  weekday: string;
  planned_hours: number;
  convoked_hours: number;
  accepted_hours: number;
  declined_hours: number;
  deficit: number;
  surplus: number;
  deviation_reasons: string[];
}

interface Summary {
  total_planned_hours: number;
  total_convoked_hours: number;
  total_accepted_hours: number;
  total_declined_hours: number;
  execution_rate: number;
}

interface Sector {
  id: number;
  name: string;
}

export default function PlanejadoExecutadoPage() {
  const [loading, setLoading] = useState(false);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [weekStart, setWeekStart] = useState<string>('');
  const [summary, setSummary] = useState<Summary | null>(null);
  const [dailyData, setDailyData] = useState<DailyData[]>([]);
  const [sectorName, setSectorName] = useState<string>('');

  useEffect(() => {
    loadSectors();
    const today = new Date();
    const monday = new Date(today);
    monday.setDate(today.getDate() - today.getDay() + 1);
    setWeekStart(monday.toISOString().split('T')[0]);
  }, []);

  useEffect(() => {
    if (selectedSector && weekStart) {
      loadData();
    }
  }, [selectedSector, weekStart]);

  const loadSectors = async () => {
    try {
      const response = await apiClient.get('/sectors/');
      setSectors(response.data);
      if (response.data.length > 0) {
        setSelectedSector(response.data[0].id);
      }
    } catch (error) {
      console.error('Error loading sectors:', error);
    }
  };

  const loadData = async () => {
    if (!selectedSector || !weekStart) return;
    
    setLoading(true);
    try {
      const response = await apiClient.get('/reports/planned-vs-executed', {
        params: { sector_id: selectedSector, week_start: weekStart }
      });
      
      setSectorName(response.data.sector_name);
      setSummary(response.data.summary);
      setDailyData(response.data.daily_breakdown);
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportExcel = async () => {
    if (!selectedSector || !weekStart) return;
    
    try {
      const response = await apiClient.get('/reports/export/planned-vs-executed-excel', {
        params: { sector_id: selectedSector, week_start: weekStart },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `planejado_executado_${weekStart}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Error exporting:', error);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1>Planejado x Executado</h1>
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
        padding: '15px',
        backgroundColor: '#f3f4f6',
        borderRadius: '8px'
      }}>
        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Setor</label>
          <select 
            value={selectedSector || ''} 
            onChange={(e) => setSelectedSector(parseInt(e.target.value))}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db', minWidth: '200px' }}
          >
            {sectors.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px' }}>Semana (Segunda-feira)</label>
          <input 
            type="date" 
            value={weekStart} 
            onChange={(e) => setWeekStart(e.target.value)}
            style={{ padding: '8px', borderRadius: '4px', border: '1px solid #d1d5db' }}
          />
        </div>
      </div>

      {summary && (
        <div style={{ marginBottom: '20px' }}>
          <h3 style={{ marginBottom: '10px' }}>{sectorName} - Semana de {new Date(weekStart).toLocaleDateString('pt-BR')}</h3>
          
          <div style={{ 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', 
            gap: '15px', 
            marginBottom: '20px' 
          }}>
            <div style={{ padding: '15px', backgroundColor: '#e0f2fe', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#0369a1' }}>{summary.total_planned_hours}h</div>
              <div style={{ fontSize: '12px', color: '#6b7280' }}>Horas Planejadas</div>
            </div>
            <div style={{ padding: '15px', backgroundColor: '#fef3c7', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#d97706' }}>{summary.total_convoked_hours}h</div>
              <div style={{ fontSize: '12px', color: '#6b7280' }}>Horas Convocadas</div>
            </div>
            <div style={{ padding: '15px', backgroundColor: '#ecfdf5', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#10b981' }}>{summary.total_accepted_hours}h</div>
              <div style={{ fontSize: '12px', color: '#6b7280' }}>Horas Aceitas</div>
            </div>
            <div style={{ padding: '15px', backgroundColor: '#fef2f2', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ef4444' }}>{summary.total_declined_hours}h</div>
              <div style={{ fontSize: '12px', color: '#6b7280' }}>Horas Recusadas</div>
            </div>
            <div style={{ padding: '15px', backgroundColor: summary.execution_rate >= 80 ? '#ecfdf5' : '#fef2f2', borderRadius: '8px', textAlign: 'center' }}>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: summary.execution_rate >= 80 ? '#10b981' : '#ef4444' }}>
                {summary.execution_rate}%
              </div>
              <div style={{ fontSize: '12px', color: '#6b7280' }}>Taxa Execucao</div>
            </div>
          </div>
        </div>
      )}

      {loading ? (
        <p>Carregando...</p>
      ) : dailyData.length === 0 ? (
        <p style={{ color: '#6b7280' }}>Selecione um setor e semana para visualizar os dados.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ backgroundColor: '#f3f4f6' }}>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Dia</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Planejado</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Convocado</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Aceito</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Recusado</th>
              <th style={{ padding: '12px', textAlign: 'center', borderBottom: '1px solid #e5e7eb' }}>Deficit</th>
              <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Motivos Desvio</th>
            </tr>
          </thead>
          <tbody>
            {dailyData.map(day => (
              <tr key={day.date} style={{ borderBottom: '1px solid #e5e7eb' }}>
                <td style={{ padding: '12px' }}>
                  <strong>{day.weekday}</strong>
                  <br />
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>
                    {new Date(day.date).toLocaleDateString('pt-BR')}
                  </span>
                </td>
                <td style={{ padding: '12px', textAlign: 'center' }}>{day.planned_hours}h</td>
                <td style={{ padding: '12px', textAlign: 'center' }}>{day.convoked_hours}h</td>
                <td style={{ padding: '12px', textAlign: 'center', color: '#10b981' }}>{day.accepted_hours}h</td>
                <td style={{ padding: '12px', textAlign: 'center', color: '#ef4444' }}>{day.declined_hours}h</td>
                <td style={{ padding: '12px', textAlign: 'center' }}>
                  {day.deficit > 0 ? (
                    <span style={{ color: '#ef4444', fontWeight: 'bold' }}>-{day.deficit}h</span>
                  ) : day.surplus > 0 ? (
                    <span style={{ color: '#10b981', fontWeight: 'bold' }}>+{day.surplus}h</span>
                  ) : (
                    <span style={{ color: '#10b981' }}>OK</span>
                  )}
                </td>
                <td style={{ padding: '12px', fontSize: '12px', color: '#6b7280' }}>
                  {day.deviation_reasons.join(', ') || '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
