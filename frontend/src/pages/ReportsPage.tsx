import { useState, useEffect, useRef } from 'react';
import { reportsApi, ReportUpload, ReportType } from '../services/client';

export default function ReportsPage() {
  const [uploads, setUploads] = useState<ReportUpload[]>([]);
  const [reportTypes, setReportTypes] = useState<ReportType[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [dateStart, setDateStart] = useState('');
  const [dateEnd, setDateEnd] = useState('');
  const [selectedType, setSelectedType] = useState<number | ''>('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [uploadsRes, typesRes] = await Promise.all([
        reportsApi.listUploads(),
        reportsApi.listTypes()
      ]);
      setUploads(uploadsRes.data);
      setReportTypes(typesRes.data);
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao carregar dados' });
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
      if (dateStart) formData.append('date_start', dateStart);
      if (dateEnd) formData.append('date_end', dateEnd);
      if (selectedType) formData.append('report_type_id', selectedType.toString());

      const response = await reportsApi.upload(formData);
      
      if (response.data.status === 'completed') {
        setMessage({ 
          type: 'success', 
          text: `Relatório processado! Tipo detectado: ${response.data.detected_type || 'Manual'}. Confiança: ${response.data.confidence}%` 
        });
      } else {
        setMessage({ type: 'error', text: response.data.message || 'Erro no processamento' });
      }

      if (fileInputRef.current) fileInputRef.current.value = '';
      setDateStart('');
      setDateEnd('');
      setSelectedType('');
      loadData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao fazer upload' });
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Deseja excluir este relatório?')) return;
    try {
      await reportsApi.deleteUpload(id);
      setMessage({ type: 'success', text: 'Relatório excluído' });
      loadData();
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao excluir' });
    }
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      completed: '#28a745',
      processing: '#ffc107',
      failed: '#dc3545',
      pending: '#6c757d',
      needs_review: '#17a2b8'
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

  if (loading) return <div className="card"><p>Carregando...</p></div>;

  return (
    <div>
      <div className="card">
        <h2>Upload de Relatórios</h2>
        <p style={{ marginBottom: '20px', color: '#666' }}>
          Faça upload de relatórios em PDF, Excel ou CSV. O sistema tentará identificar automaticamente o tipo.
        </p>

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

        <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
          <div className="form-group">
            <label>Arquivo (PDF, Excel, CSV)</label>
            <input 
              type="file" 
              ref={fileInputRef}
              accept=".pdf,.xlsx,.xls,.csv"
              style={{ padding: '8px' }}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
            <div className="form-group">
              <label>Data Início (opcional)</label>
              <input 
                type="date" 
                value={dateStart}
                onChange={(e) => setDateStart(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Data Fim (opcional)</label>
              <input 
                type="date" 
                value={dateEnd}
                onChange={(e) => setDateEnd(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Tipo de Relatório (opcional)</label>
              <select value={selectedType} onChange={(e) => setSelectedType(e.target.value ? Number(e.target.value) : '')}>
                <option value="">Detectar automaticamente</option>
                {reportTypes.map(type => (
                  <option key={type.id} value={type.id}>{type.name}</option>
                ))}
              </select>
            </div>
          </div>

          <button type="submit" className="btn btn-primary" disabled={uploading}>
            {uploading ? 'Processando...' : 'Fazer Upload'}
          </button>
        </form>
      </div>

      <div className="card">
        <h2>Histórico de Uploads</h2>
        <table>
          <thead>
            <tr>
              <th>Arquivo</th>
              <th>Tipo</th>
              <th>Período</th>
              <th>Setores</th>
              <th>Status</th>
              <th>Data Upload</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {uploads.length === 0 ? (
              <tr><td colSpan={7} style={{ textAlign: 'center' }}>Nenhum relatório enviado</td></tr>
            ) : (
              uploads.map(upload => (
                <tr key={upload.id}>
                  <td>
                    <strong>{upload.original_filename}</strong>
                    <br />
                    <small style={{ color: '#666' }}>{upload.file_type.toUpperCase()}</small>
                  </td>
                  <td>{upload.report_type_name || '-'}</td>
                  <td>
                    {upload.date_start && upload.date_end 
                      ? `${upload.date_start} a ${upload.date_end}`
                      : upload.date_start || '-'}
                  </td>
                  <td>
                    {upload.sectors_affected?.length > 0 
                      ? upload.sectors_affected.join(', ') 
                      : '-'}
                  </td>
                  <td>{getStatusBadge(upload.status)}</td>
                  <td>{new Date(upload.created_at).toLocaleString('pt-BR')}</td>
                  <td>
                    <button 
                      className="btn btn-secondary" 
                      onClick={() => handleDelete(upload.id)}
                      style={{ padding: '4px 8px', fontSize: '12px' }}
                    >
                      Excluir
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>Tipos de Relatório Cadastrados</h2>
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Indicadores</th>
              <th>Setores</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {reportTypes.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: 'center' }}>Nenhum tipo cadastrado</td></tr>
            ) : (
              reportTypes.map(type => (
                <tr key={type.id}>
                  <td><strong>{type.name}</strong></td>
                  <td>{type.indicators?.join(', ') || '-'}</td>
                  <td>{type.sectors?.join(', ') || '-'}</td>
                  <td>{type.is_active ? 'Ativo' : 'Inativo'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
