import { useState, useEffect, useRef } from 'react';
import { dataLakeApi, DataLakeUpload, WeekdayBias, AdjustedForecast } from '../services/client';

export default function DataLakePage() {
  const [uploads, setUploads] = useState<DataLakeUpload[]>([]);
  const [biasStats, setBiasStats] = useState<WeekdayBias[]>([]);
  const [forecast, setForecast] = useState<AdjustedForecast[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);
  const [activeTab, setActiveTab] = useState<'upload' | 'stats' | 'forecast'>('upload');
  
  const getDefaultDates = () => {
    const today = new Date();
    const start = new Date(today);
    start.setDate(today.getDate() - (today.getDay() === 0 ? 6 : today.getDay() - 1));
    const end = new Date(start);
    end.setDate(start.getDate() + 6);
    return {
      start: start.toISOString().split('T')[0],
      end: end.toISOString().split('T')[0]
    };
  };
  
  const defaults = getDefaultDates();
  const [forecastStart, setForecastStart] = useState(defaults.start);
  const [forecastEnd, setForecastEnd] = useState(defaults.end);
  const [selectedUpload, setSelectedUpload] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [uploadsRes, biasRes] = await Promise.all([
        dataLakeApi.listUploads(),
        dataLakeApi.getWeekdayBias()
      ]);
      setUploads(uploadsRes.data || []);
      setBiasStats(biasRes.data || []);
    } catch (error: any) {
      console.error('Erro ao carregar dados:', error);
      setMessage({ type: 'error', text: 'Erro ao carregar dados do Data Lake' });
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setMessage({ type: 'error', text: 'Selecione um arquivo' });
      return;
    }

    setUploading(true);
    setMessage(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await dataLakeApi.upload(formData);
      
      if (response.data.status === 'duplicate') {
        setMessage({ type: 'info', text: 'Este arquivo já foi enviado anteriormente.' });
      } else {
        setMessage({ 
          type: 'success', 
          text: `Arquivo processado! Tipo: ${response.data.detected_type || 'Não detectado'}. Confiança: ${response.data.confidence}%` 
        });
      }

      if (fileInputRef.current) fileInputRef.current.value = '';
      loadData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao fazer upload' });
    } finally {
      setUploading(false);
    }
  };

  const handleViewDetails = async (id: number) => {
    try {
      const response = await dataLakeApi.getUpload(id);
      setSelectedUpload(response.data);
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao carregar detalhes' });
    }
  };

  const handleReprocess = async (id: number) => {
    try {
      setMessage({ type: 'info', text: 'Reprocessando relatório...' });
      const response = await dataLakeApi.reprocessUpload(id);
      const result = response.data;
      
      if (result.success) {
        setMessage({ 
          type: 'success', 
          text: `Relatório reprocessado com sucesso! Registros extraídos: ${result.records_extracted || 0}` 
        });
      } else {
        setMessage({ 
          type: 'error', 
          text: `Falha no reprocessamento: ${result.errors?.join(', ') || 'Erro desconhecido'}` 
        });
      }
      loadData();
      if (selectedUpload?.id === id) {
        handleViewDetails(id);
      }
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao reprocessar' });
    }
  };

  const handleLoadForecast = async () => {
    if (!forecastStart || !forecastEnd) {
      setMessage({ type: 'error', text: 'Selecione as datas inicial e final' });
      return;
    }

    try {
      const response = await dataLakeApi.getAdjustedForecast(forecastStart, forecastEnd);
      const result = response.data;
      
      if (result.status === 'no_data') {
        setMessage({ type: 'info', text: result.message || 'Ainda não há dados suficientes para gerar previsão para este período.' });
        setForecast([]);
      } else if (result.status === 'error') {
        setMessage({ type: 'error', text: result.message || 'Erro técnico ao carregar previsão.' });
        setForecast([]);
      } else {
        setForecast(result.data || []);
        setMessage(null);
      }
    } catch (error: any) {
      const detail = error.response?.data?.detail;
      if (detail?.error_code === 'INTERNAL_ERROR') {
        setMessage({ type: 'error', text: detail.message || 'Erro técnico ao carregar previsão — ver logs.' });
      } else {
        setMessage({ type: 'error', text: 'Erro ao carregar previsão. Verifique se há dados disponíveis.' });
      }
      setForecast([]);
    }
  };

  const handleRecalculateStats = async () => {
    try {
      setMessage({ type: 'info', text: 'Recalculando estatísticas...' });
      await dataLakeApi.recalculateStats();
      setMessage({ type: 'success', text: 'Estatísticas recalculadas com sucesso' });
      loadData();
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao recalcular estatísticas' });
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      completed: '#28a745',
      processing: '#ffc107',
      failed: '#dc3545',
      pending: '#6c757d'
    };
    return (
      <span style={{ 
        padding: '2px 8px', 
        borderRadius: '4px', 
        backgroundColor: colors[status] || '#6c757d',
        color: 'white',
        fontSize: '12px'
      }}>
        {status}
      </span>
    );
  };

  const getTypeBadge = (type: string | null) => {
    if (!type) return '-';
    const colors: Record<string, string> = {
      'HP_DAILY': '#007bff',
      'CHECKIN_DAILY': '#17a2b8',
      'CHECKOUT_DAILY': '#6f42c1'
    };
    return (
      <span style={{ 
        padding: '2px 8px', 
        borderRadius: '4px', 
        backgroundColor: colors[type] || '#6c757d',
        color: 'white',
        fontSize: '12px'
      }}>
        {type}
      </span>
    );
  };

  if (loading) return <div className="card"><p>Carregando...</p></div>;

  return (
    <div>
      <div className="card">
        <h2>Data Lake - Ingestão de Relatórios</h2>
        <p style={{ marginBottom: '20px', color: '#666' }}>
          Faça upload dos relatórios diários do PMS (HP, Check-in, Check-out). 
          O sistema detectará automaticamente o tipo e extrairá os dados.
        </p>

        <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
          <button 
            className={`btn ${activeTab === 'upload' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('upload')}
          >
            Upload de Relatórios
          </button>
          <button 
            className={`btn ${activeTab === 'stats' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('stats')}
          >
            Estatísticas por Dia
          </button>
          <button 
            className={`btn ${activeTab === 'forecast' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('forecast')}
          >
            Projeção Ajustada
          </button>
        </div>

        {message && (
          <div style={{ 
            padding: '10px', 
            marginBottom: '15px', 
            borderRadius: '4px',
            backgroundColor: message.type === 'success' ? '#d4edda' : message.type === 'error' ? '#f8d7da' : '#d1ecf1',
            color: message.type === 'success' ? '#155724' : message.type === 'error' ? '#721c24' : '#0c5460'
          }}>
            {message.text}
          </div>
        )}
      </div>

      {activeTab === 'upload' && (
        <>
          <div className="card">
            <h3>Upload de Arquivo</h3>
            <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
              <div className="form-group">
                <label>Arquivo PDF do relatório diário</label>
                <input 
                  type="file" 
                  ref={fileInputRef}
                  accept=".pdf,.xlsx,.xls,.csv"
                  style={{ padding: '8px' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '10px' }}>
                <button type="submit" className="btn btn-primary" disabled={uploading}>
                  {uploading ? 'Processando...' : 'Enviar e Processar'}
                </button>
              </div>
            </form>
          </div>

          <div className="card">
            <h3>Histórico de Uploads ({uploads.length})</h3>
            <table>
              <thead>
                <tr>
                  <th>Arquivo</th>
                  <th>Tipo Detectado</th>
                  <th>Confiança</th>
                  <th>Gerado em</th>
                  <th>Status</th>
                  <th>Registros</th>
                  <th>Upload</th>
                  <th>Ações</th>
                </tr>
              </thead>
              <tbody>
                {uploads.length === 0 ? (
                  <tr><td colSpan={8} style={{ textAlign: 'center' }}>Nenhum relatório enviado</td></tr>
                ) : (
                  uploads.map(upload => (
                    <tr key={upload.id}>
                      <td>
                        <strong>{upload.filename}</strong>
                        {upload.status === 'failed' && upload.error_message && (
                          <div style={{ fontSize: '11px', color: '#dc3545', marginTop: '4px' }}>
                            {upload.error_message.substring(0, 60)}{upload.error_message.length > 60 ? '...' : ''}
                          </div>
                        )}
                      </td>
                      <td>{getTypeBadge(upload.type)}</td>
                      <td>{upload.confidence}%</td>
                      <td>{upload.generated_at ? new Date(upload.generated_at).toLocaleString('pt-BR') : '-'}</td>
                      <td>{getStatusBadge(upload.status)}</td>
                      <td>
                        {upload.rows_inserted > 0 ? (
                          <span style={{ color: '#28a745', fontWeight: 'bold' }}>{upload.rows_inserted}</span>
                        ) : '-'}
                        {upload.rows_skipped > 0 && (
                          <span style={{ color: '#6c757d', fontSize: '11px' }}> ({upload.rows_skipped} dup)</span>
                        )}
                      </td>
                      <td>{new Date(upload.created_at).toLocaleString('pt-BR')}</td>
                      <td>
                        <button 
                          className="btn btn-secondary" 
                          onClick={() => handleViewDetails(upload.id)}
                          style={{ padding: '4px 8px', fontSize: '12px', marginRight: '5px' }}
                        >
                          Detalhes
                        </button>
                        {upload.status === 'failed' && (
                          <button 
                            className="btn btn-primary" 
                            onClick={() => handleReprocess(upload.id)}
                            style={{ padding: '4px 8px', fontSize: '12px' }}
                          >
                            Reprocessar
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {activeTab === 'stats' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3>Viés (Bias) por Dia da Semana</h3>
            <button className="btn btn-secondary" onClick={handleRecalculateStats}>
              Recalcular Estatísticas
            </button>
          </div>
          <p style={{ marginBottom: '15px', color: '#666' }}>
            O bias indica a diferença média (em pontos percentuais) entre o real e a previsão. 
            Valores positivos indicam que a previsão subestima a ocupação.
          </p>
          <table>
            <thead>
              <tr>
                <th>Dia da Semana</th>
                <th>Bias (pp)</th>
                <th>Desvio Padrão</th>
                <th>MAE (pp)</th>
                <th>Amostras</th>
                <th>Método</th>
              </tr>
            </thead>
            <tbody>
              {biasStats.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: 'center' }}>Nenhuma estatística calculada ainda</td></tr>
              ) : (
                biasStats.map(stat => (
                  <tr key={stat.weekday}>
                    <td><strong>{stat.weekday}</strong></td>
                    <td style={{ 
                      color: stat.bias_pp > 0 ? '#28a745' : stat.bias_pp < 0 ? '#dc3545' : 'inherit',
                      fontWeight: 'bold'
                    }}>
                      {stat.bias_pp > 0 ? '+' : ''}{stat.bias_pp.toFixed(2)}
                    </td>
                    <td>{stat.std_pp?.toFixed(2) || '-'}</td>
                    <td>{stat.mae_pp?.toFixed(2) || '-'}</td>
                    <td>{stat.n}</td>
                    <td>{stat.method}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {activeTab === 'forecast' && (
        <div className="card">
          <h3>Projeção Ajustada de Ocupação</h3>
          <p style={{ marginBottom: '15px', color: '#666' }}>
            A previsão ajustada aplica o viés estatístico para corrigir a projeção do PMS.
          </p>
          
          <div style={{ display: 'flex', gap: '15px', marginBottom: '20px', alignItems: 'flex-end' }}>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Data Início</label>
              <input 
                type="date" 
                value={forecastStart}
                onChange={(e) => setForecastStart(e.target.value)}
              />
            </div>
            <div className="form-group" style={{ margin: 0 }}>
              <label>Data Fim</label>
              <input 
                type="date" 
                value={forecastEnd}
                onChange={(e) => setForecastEnd(e.target.value)}
              />
            </div>
            <button className="btn btn-primary" onClick={handleLoadForecast}>
              Carregar Projeção
            </button>
          </div>

          <table>
            <thead>
              <tr>
                <th>Data</th>
                <th>Dia da Semana</th>
                <th>Previsão PMS (%)</th>
                <th>Bias (pp)</th>
                <th>Previsão Ajustada (%)</th>
                <th>Real (%)</th>
              </tr>
            </thead>
            <tbody>
              {forecast.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: 'center' }}>Selecione um período para ver a projeção</td></tr>
              ) : (
                forecast.map(f => (
                  <tr key={f.target_date}>
                    <td><strong>{new Date(f.target_date + 'T00:00:00').toLocaleDateString('pt-BR')}</strong></td>
                    <td>{f.weekday_pt}</td>
                    <td>{f.forecast_pct?.toFixed(1) || '-'}</td>
                    <td style={{ 
                      color: f.bias_pp > 0 ? '#28a745' : f.bias_pp < 0 ? '#dc3545' : 'inherit'
                    }}>
                      {f.has_bias_data ? `${f.bias_pp > 0 ? '+' : ''}${f.bias_pp.toFixed(2)}` : '-'}
                    </td>
                    <td style={{ fontWeight: 'bold', color: '#007bff' }}>
                      {f.adjusted_forecast_pct?.toFixed(1) || '-'}
                    </td>
                    <td style={{ color: '#28a745', fontWeight: f.real_pct ? 'bold' : 'normal' }}>
                      {f.real_pct?.toFixed(1) || '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {selectedUpload && (
        <div className="card" style={{ marginTop: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3>Detalhes do Upload</h3>
            <button className="btn btn-secondary" onClick={() => setSelectedUpload(null)}>
              Fechar
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginTop: '15px' }}>
            <div><strong>Arquivo:</strong> {selectedUpload.filename}</div>
            <div><strong>Tipo:</strong> {selectedUpload.type || 'Não detectado'}</div>
            <div><strong>Status:</strong> {selectedUpload.status}</div>
            <div><strong>Hash:</strong> <code style={{ fontSize: '10px' }}>{selectedUpload.file_hash?.substring(0, 16)}...</code></div>
            <div><strong>Período:</strong> {selectedUpload.date_start} - {selectedUpload.date_end}</div>
            <div><strong>Parser:</strong> v{selectedUpload.parser_version || '-'}</div>
          </div>
          
          {selectedUpload.logs && selectedUpload.logs.length > 0 && (
            <div style={{ marginTop: '15px' }}>
              <h4>Logs de Extração</h4>
              <table>
                <thead>
                  <tr>
                    <th>Etapa</th>
                    <th>Nível</th>
                    <th>Mensagem</th>
                    <th>Data/Hora</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedUpload.logs.map((log: any, idx: number) => (
                    <tr key={idx}>
                      <td>{log.step}</td>
                      <td>
                        <span style={{ 
                          color: log.severity === 'ERROR' ? '#dc3545' : 
                                 log.severity === 'WARN' ? '#ffc107' : '#28a745'
                        }}>
                          {log.severity}
                        </span>
                      </td>
                      <td>{log.message}</td>
                      <td>{new Date(log.created_at).toLocaleString('pt-BR')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          
          {selectedUpload.error_message && (
            <div style={{ marginTop: '15px', padding: '10px', backgroundColor: '#f8d7da', borderRadius: '4px', color: '#721c24' }}>
              <strong>Erro:</strong> {selectedUpload.error_message}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
