import { useState, useEffect } from 'react';
import { weeklyParametersApi, WeeklyParameters, DayType, sectorsApi, Sector } from '../services/client';

const DIAS = [
  { key: 'seg', nome: 'Segunda-feira' },
  { key: 'ter', nome: 'Terça-feira' },
  { key: 'qua', nome: 'Quarta-feira' },
  { key: 'qui', nome: 'Quinta-feira' },
  { key: 'sex', nome: 'Sexta-feira' },
  { key: 'sab', nome: 'Sábado' },
  { key: 'dom', nome: 'Domingo' },
];

const TIPOS_DIA: { value: DayType; label: string }[] = [
  { value: 'normal', label: 'Normal' },
  { value: 'feriado', label: 'Feriado' },
  { value: 'vespera_feriado', label: 'Véspera de Feriado' },
];

function getNextMonday(): string {
  const today = new Date();
  const day = today.getDay();
  const diff = day === 0 ? 1 : 8 - day;
  const nextMonday = new Date(today);
  nextMonday.setDate(today.getDate() + diff);
  return nextMonday.toISOString().split('T')[0];
}

export default function WeeklyParametersPage() {
  const [parametrosList, setParametrosList] = useState<WeeklyParameters[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  
  const [formData, setFormData] = useState<Partial<WeeklyParameters>>({
    sector_id: undefined,
    semana_inicio: getNextMonday(),
    seg_ocupacao_prevista: 0, seg_quartos_vagos_sujos: 0, seg_quartos_estada: 0, seg_tipo_dia: 'normal',
    ter_ocupacao_prevista: 0, ter_quartos_vagos_sujos: 0, ter_quartos_estada: 0, ter_tipo_dia: 'normal',
    qua_ocupacao_prevista: 0, qua_quartos_vagos_sujos: 0, qua_quartos_estada: 0, qua_tipo_dia: 'normal',
    qui_ocupacao_prevista: 0, qui_quartos_vagos_sujos: 0, qui_quartos_estada: 0, qui_tipo_dia: 'normal',
    sex_ocupacao_prevista: 0, sex_quartos_vagos_sujos: 0, sex_quartos_estada: 0, sex_tipo_dia: 'normal',
    sab_ocupacao_prevista: 0, sab_quartos_vagos_sujos: 0, sab_quartos_estada: 0, sab_tipo_dia: 'normal',
    dom_ocupacao_prevista: 0, dom_quartos_vagos_sujos: 0, dom_quartos_estada: 0, dom_tipo_dia: 'normal',
  });

  useEffect(() => {
    loadSectors();
  }, []);

  useEffect(() => {
    loadParametros();
  }, [selectedSectorId]);

  const loadSectors = async () => {
    try {
      const response = await sectorsApi.list();
      setSectors(response.data);
      if (response.data.length > 0) {
        setSelectedSectorId(response.data[0].id);
      }
    } catch (err) {
      setError('Erro ao carregar setores');
    }
  };

  const loadParametros = async () => {
    try {
      setLoading(true);
      const response = await weeklyParametersApi.list(selectedSectorId || undefined);
      setParametrosList(response.data);
    } catch (err) {
      setError('Erro ao carregar parâmetros');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    
    try {
      const dataToSend = {
        ...formData,
        sector_id: selectedSectorId || formData.sector_id
      };
      
      if (editingId) {
        await weeklyParametersApi.update(editingId, dataToSend);
        setSuccess('Parametros atualizados com sucesso!');
      } else {
        await weeklyParametersApi.create(dataToSend);
        setSuccess('Parametros criados com sucesso!');
      }
      loadParametros();
      resetForm();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao salvar parametros');
    }
  };

  const handleEdit = (params: WeeklyParameters) => {
    setFormData(params);
    setEditingId(params.id);
    setShowForm(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir estes parâmetros?')) return;
    try {
      await weeklyParametersApi.delete(id);
      setSuccess('Parâmetros excluídos com sucesso!');
      loadParametros();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Erro ao excluir');
    }
  };

  const resetForm = () => {
    setFormData({
      sector_id: selectedSectorId || undefined,
      semana_inicio: getNextMonday(),
      seg_ocupacao_prevista: 0, seg_quartos_vagos_sujos: 0, seg_quartos_estada: 0, seg_tipo_dia: 'normal',
      ter_ocupacao_prevista: 0, ter_quartos_vagos_sujos: 0, ter_quartos_estada: 0, ter_tipo_dia: 'normal',
      qua_ocupacao_prevista: 0, qua_quartos_vagos_sujos: 0, qua_quartos_estada: 0, qua_tipo_dia: 'normal',
      qui_ocupacao_prevista: 0, qui_quartos_vagos_sujos: 0, qui_quartos_estada: 0, qui_tipo_dia: 'normal',
      sex_ocupacao_prevista: 0, sex_quartos_vagos_sujos: 0, sex_quartos_estada: 0, sex_tipo_dia: 'normal',
      sab_ocupacao_prevista: 0, sab_quartos_vagos_sujos: 0, sab_quartos_estada: 0, sab_tipo_dia: 'normal',
      dom_ocupacao_prevista: 0, dom_quartos_vagos_sujos: 0, dom_quartos_estada: 0, dom_tipo_dia: 'normal',
    });
    setEditingId(null);
    setShowForm(false);
  };

  const getSectorName = (sectorId?: number) => {
    if (!sectorId) return 'Global';
    const sector = sectors.find(s => s.id === sectorId);
    return sector ? sector.nome : 'Desconhecido';
  };

  const updateDayField = (dia: string, campo: string, valor: any) => {
    setFormData(prev => ({
      ...prev,
      [`${dia}_${campo}`]: valor
    }));
  };

  if (loading) return <div className="card">Carregando...</div>;

  const selectedSectorName = sectors.find(s => s.id === selectedSectorId)?.nome || '';

  return (
    <div>
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
          <h2>Parametros Operacionais da Semana{selectedSectorName ? ` - ${selectedSectorName}` : ''}</h2>
          <button onClick={() => setShowForm(!showForm)} className="btn">
            {showForm ? 'Fechar' : 'Nova Semana'}
          </button>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label style={{ marginRight: '0.5rem', fontWeight: 'bold' }}>Setor:</label>
          <select
            value={selectedSectorId || ''}
            onChange={(e) => setSelectedSectorId(e.target.value ? Number(e.target.value) : null)}
            style={{ padding: '0.5rem', minWidth: '200px' }}
          >
            <option value="">Todos os setores</option>
            {sectors.map((sector) => (
              <option key={sector.id} value={sector.id}>
                {sector.nome}
              </option>
            ))}
          </select>
        </div>

        {error && <div className="error">{error}</div>}
        {success && <div className="success">{success}</div>}

        {showForm && (
          <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
            <div className="form-group">
              <label>Semana Início (Segunda-feira)</label>
              <input
                type="date"
                value={formData.semana_inicio}
                onChange={e => setFormData({ ...formData, semana_inicio: e.target.value })}
                required
                disabled={!!editingId}
              />
            </div>

            <table className="table">
              <thead>
                <tr>
                  <th>Dia</th>
                  <th>Ocupação (%)</th>
                  <th>Quartos Vagos Sujos</th>
                  <th>Quartos Estada</th>
                  <th>Tipo do Dia</th>
                </tr>
              </thead>
              <tbody>
                {DIAS.map(dia => (
                  <tr key={dia.key}>
                    <td><strong>{dia.nome}</strong></td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        max="100"
                        step="0.1"
                        value={(formData as any)[`${dia.key}_ocupacao_prevista`] || 0}
                        onChange={e => updateDayField(dia.key, 'ocupacao_prevista', parseFloat(e.target.value) || 0)}
                        style={{ width: '80px' }}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        value={(formData as any)[`${dia.key}_quartos_vagos_sujos`] || 0}
                        onChange={e => updateDayField(dia.key, 'quartos_vagos_sujos', parseInt(e.target.value) || 0)}
                        style={{ width: '80px' }}
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min="0"
                        value={(formData as any)[`${dia.key}_quartos_estada`] || 0}
                        onChange={e => updateDayField(dia.key, 'quartos_estada', parseInt(e.target.value) || 0)}
                        style={{ width: '80px' }}
                      />
                    </td>
                    <td>
                      <select
                        value={(formData as any)[`${dia.key}_tipo_dia`] || 'normal'}
                        onChange={e => updateDayField(dia.key, 'tipo_dia', e.target.value)}
                      >
                        {TIPOS_DIA.map(tipo => (
                          <option key={tipo.value} value={tipo.value}>{tipo.label}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
              <button type="submit" className="btn">
                {editingId ? 'Atualizar' : 'Salvar'}
              </button>
              <button type="button" onClick={resetForm} className="btn" style={{ background: '#6c757d' }}>
                Cancelar
              </button>
            </div>
          </form>
        )}

        <h3>Semanas Cadastradas</h3>
        {parametrosList.length === 0 ? (
          <p>Nenhum parametro cadastrado ainda{selectedSectorId ? ' para este setor' : ''}.</p>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Semana</th>
                {!selectedSectorId && <th>Setor</th>}
                <th>Total Quartos V.S.</th>
                <th>Total Quartos Estada</th>
                <th>Feriados</th>
                <th>Acoes</th>
              </tr>
            </thead>
            <tbody>
              {parametrosList.map(params => {
                const totalVS = DIAS.reduce((sum, d) => sum + ((params as any)[`${d.key}_quartos_vagos_sujos`] || 0), 0);
                const totalEstada = DIAS.reduce((sum, d) => sum + ((params as any)[`${d.key}_quartos_estada`] || 0), 0);
                const feriados = DIAS.filter(d => (params as any)[`${d.key}_tipo_dia`] !== 'normal').length;
                
                return (
                  <tr key={params.id}>
                    <td>{new Date(params.semana_inicio + 'T12:00:00').toLocaleDateString('pt-BR')}</td>
                    {!selectedSectorId && <td>{getSectorName(params.sector_id)}</td>}
                    <td>{totalVS}</td>
                    <td>{totalEstada}</td>
                    <td>{feriados > 0 ? `${feriados} dia(s)` : '-'}</td>
                    <td>
                      <button onClick={() => handleEdit(params)} className="btn" style={{ marginRight: '0.5rem', padding: '0.25rem 0.5rem' }}>
                        Editar
                      </button>
                      <button onClick={() => handleDelete(params.id)} className="btn" style={{ background: '#dc3545', padding: '0.25rem 0.5rem' }}>
                        Excluir
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
