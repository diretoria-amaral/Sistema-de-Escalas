import { useState, useEffect, useCallback } from 'react';

type EscopoType = 'DEMANDA' | 'PROGRAMACAO' | 'AJUSTES';

interface Sector {
  id: number;
  name: string;
}

interface Regra {
  id: number;
  setor_id: number;
  nome: string;
  descricao: string | null;
  prioridade: number;
  escopo: EscopoType;
  condicao_json: Record<string, unknown> | null;
  acao_json: Record<string, unknown>;
  ativo: boolean;
  criado_em: string;
  atualizado_em: string | null;
}

interface Activity {
  id: number;
  name: string;
  code: string;
  classificacao_atividade: string;
}

const escopoOptions: { value: EscopoType; label: string; description: string }[] = [
  { value: 'DEMANDA', label: 'Demanda', description: 'Define como calcular horas/minutos de trabalho' },
  { value: 'PROGRAMACAO', label: 'Programacao', description: 'Define como inserir/ordenar atividades na semana' },
  { value: 'AJUSTES', label: 'Ajustes', description: 'Define ajustes por estatistica/HP/vies por dia' }
];

const driverOptions = [
  { value: 'ocupacao', label: 'Taxa de Ocupacao' },
  { value: 'quartos_ocupados', label: 'Quartos Ocupados' },
  { value: 'checkout', label: 'Checkouts' },
  { value: 'checkin', label: 'Checkins' },
  { value: 'stayover', label: 'Stayovers' },
  { value: 'fixo', label: 'Valor Fixo' }
];

const acaoTipoOptions = [
  { value: 'inserir_atividade', label: 'Inserir Atividade', description: 'Insere uma atividade na programacao' },
  { value: 'multiplicar_demanda', label: 'Multiplicar Demanda', description: 'Multiplica a demanda por um fator' },
  { value: 'adicionar_minutos', label: 'Adicionar Minutos', description: 'Adiciona minutos fixos a demanda' },
  { value: 'aplicar_fator', label: 'Aplicar Fator', description: 'Aplica fator baseado em parametro' }
];

const diasSemana = [
  { value: 'SEG', label: 'Seg' },
  { value: 'TER', label: 'Ter' },
  { value: 'QUA', label: 'Qua' },
  { value: 'QUI', label: 'Qui' },
  { value: 'SEX', label: 'Sex' },
  { value: 'SAB', label: 'Sab' },
  { value: 'DOM', label: 'Dom' }
];

interface RegraForm {
  nome: string;
  descricao: string;
  prioridade: number;
  escopo: EscopoType;
  condicao_driver: string;
  condicao_min: number;
  condicao_max: number;
  condicao_dias: string[];
  acao_tipo: string;
  acao_atividade_id: number | null;
  acao_fator: number;
  acao_minutos: number;
  acao_parametro: string;
  ativo: boolean;
}

const initialForm: RegraForm = {
  nome: '',
  descricao: '',
  prioridade: 100,
  escopo: 'DEMANDA',
  condicao_driver: 'ocupacao',
  condicao_min: 0,
  condicao_max: 1,
  condicao_dias: [],
  acao_tipo: 'multiplicar_demanda',
  acao_atividade_id: null,
  acao_fator: 1,
  acao_minutos: 0,
  acao_parametro: '',
  ativo: true
};

function RegrasCalculoPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [regras, setRegras] = useState<Regra[]>([]);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Regra | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [form, setForm] = useState<RegraForm>(initialForm);
  const [validation, setValidation] = useState<{ pode_usar_modo_auto: boolean; erros: unknown[] } | null>(null);
  const [filterEscopo, setFilterEscopo] = useState<string>('');
  const [showInactive, setShowInactive] = useState(false);

  useEffect(() => {
    loadSectors();
  }, []);

  const loadSectors = async () => {
    try {
      const res = await fetch('/api/sectors');
      if (res.ok) {
        const data = await res.json();
        setSectors(data);
      }
    } catch (err) {
      console.error('Erro ao carregar setores:', err);
    }
  };

  const loadRegras = useCallback(async () => {
    if (!selectedSectorId) return;
    
    try {
      setLoading(true);
      let url = `/api/regras-calculo-setor?setor_id=${selectedSectorId}`;
      if (filterEscopo) url += `&escopo=${filterEscopo}`;
      if (!showInactive) url += '&apenas_ativas=true';
      
      const res = await fetch(url);
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Erro ao carregar regras');
      }
      const data = await res.json();
      setRegras(data.regras || []);
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Erro ao carregar regras' });
    } finally {
      setLoading(false);
    }
  }, [selectedSectorId, filterEscopo, showInactive]);

  const loadActivities = useCallback(async () => {
    if (!selectedSectorId) return;
    
    try {
      const res = await fetch(`/api/governance-activities?sector_id=${selectedSectorId}`);
      if (res.ok) {
        const data = await res.json();
        setActivities(data);
      }
    } catch (err) {
      console.error('Erro ao carregar atividades:', err);
    }
  }, [selectedSectorId]);

  const loadValidation = useCallback(async () => {
    if (!selectedSectorId) return;
    
    try {
      const res = await fetch(`/api/regras-calculo-setor/validar/setor/${selectedSectorId}`);
      if (res.ok) {
        const data = await res.json();
        setValidation(data);
      }
    } catch (err) {
      console.error('Erro ao validar regras:', err);
    }
  }, [selectedSectorId]);

  useEffect(() => {
    if (selectedSectorId) {
      loadRegras();
      loadActivities();
      loadValidation();
    } else {
      setRegras([]);
      setActivities([]);
      setValidation(null);
    }
  }, [selectedSectorId, loadRegras, loadActivities, loadValidation]);

  const parseRegraToForm = (regra: Regra): RegraForm => {
    const condicao = regra.condicao_json || {};
    const acao = regra.acao_json || {};
    
    return {
      nome: regra.nome,
      descricao: regra.descricao || '',
      prioridade: regra.prioridade,
      escopo: regra.escopo,
      condicao_driver: (condicao as Record<string, unknown>).driver as string || 'ocupacao',
      condicao_min: (condicao as Record<string, unknown>).min as number || 0,
      condicao_max: (condicao as Record<string, unknown>).max as number || 1,
      condicao_dias: ((condicao as Record<string, unknown>).dias as string[]) || [],
      acao_tipo: (acao as Record<string, unknown>).tipo as string || 'multiplicar_demanda',
      acao_atividade_id: (acao as Record<string, unknown>).atividade_id as number || null,
      acao_fator: (acao as Record<string, unknown>).fator as number || 1,
      acao_minutos: (acao as Record<string, unknown>).minutos as number || 0,
      acao_parametro: (acao as Record<string, unknown>).parametro as string || '',
      ativo: regra.ativo
    };
  };

  const formToPayload = () => {
    const condicao: Record<string, unknown> = {};
    if (form.condicao_driver) condicao.driver = form.condicao_driver;
    if (form.condicao_min !== undefined) condicao.min = form.condicao_min;
    if (form.condicao_max !== undefined) condicao.max = form.condicao_max;
    if (form.condicao_dias.length > 0) condicao.dias = form.condicao_dias;

    const acao: Record<string, unknown> = { tipo: form.acao_tipo };
    if (form.acao_tipo === 'inserir_atividade' && form.acao_atividade_id) {
      acao.atividade_id = form.acao_atividade_id;
    }
    if (form.acao_tipo === 'multiplicar_demanda' || form.acao_tipo === 'aplicar_fator') {
      acao.fator = form.acao_fator;
    }
    if (form.acao_tipo === 'adicionar_minutos') {
      acao.minutos = form.acao_minutos;
    }
    if (form.acao_tipo === 'aplicar_fator') {
      acao.parametro = form.acao_parametro;
    }

    return {
      setor_id: selectedSectorId,
      nome: form.nome.trim(),
      descricao: form.descricao.trim() || null,
      prioridade: form.prioridade,
      escopo: form.escopo,
      condicao_json: Object.keys(condicao).length > 0 ? condicao : null,
      acao_json: acao,
      ativo: form.ativo
    };
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!form.nome.trim()) {
      setMessage({ type: 'error', text: 'Nome da regra e obrigatorio' });
      return;
    }
    
    if (form.acao_tipo === 'inserir_atividade' && !form.acao_atividade_id) {
      setMessage({ type: 'error', text: 'Selecione uma atividade para inserir' });
      return;
    }
    
    try {
      const url = editing ? `/api/regras-calculo-setor/${editing.id}` : '/api/regras-calculo-setor';
      const method = editing ? 'PUT' : 'POST';
      
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(formToPayload())
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        setMessage({ type: 'error', text: data.detail || 'Erro ao salvar regra' });
        return;
      }
      
      setMessage({ type: 'success', text: editing ? 'Regra atualizada!' : 'Regra criada!' });
      setShowModal(false);
      resetForm();
      loadRegras();
      loadValidation();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao salvar regra' });
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir esta regra?')) return;
    
    try {
      const res = await fetch(`/api/regras-calculo-setor/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Erro ao excluir');
      }
      setMessage({ type: 'success', text: 'Regra excluida!' });
      loadRegras();
      loadValidation();
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Erro ao excluir' });
    }
  };

  const handleDuplicate = async (id: number) => {
    try {
      const res = await fetch(`/api/regras-calculo-setor/${id}/duplicar`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Erro ao duplicar');
      }
      setMessage({ type: 'success', text: 'Regra duplicada!' });
      loadRegras();
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Erro ao duplicar' });
    }
  };

  const openEdit = (regra: Regra) => {
    setEditing(regra);
    setForm(parseRegraToForm(regra));
    setShowModal(true);
  };

  const openCreate = () => {
    setEditing(null);
    resetForm();
    setShowModal(true);
  };

  const resetForm = () => {
    setForm(initialForm);
    setEditing(null);
  };

  const toggleDia = (dia: string) => {
    setForm(prev => ({
      ...prev,
      condicao_dias: prev.condicao_dias.includes(dia)
        ? prev.condicao_dias.filter(d => d !== dia)
        : [...prev.condicao_dias, dia]
    }));
  };

  const getEscopoColor = (escopo: string) => {
    switch (escopo) {
      case 'DEMANDA': return '#2196F3';
      case 'PROGRAMACAO': return '#4CAF50';
      case 'AJUSTES': return '#FF9800';
      default: return '#666';
    }
  };

  return (
    <div className="page-container">
      <div className="page-header">
        <div className="header-content">
          <h1>Regras de Calculos por Setor</h1>
          <p>Defina como o sistema calcula demanda e aloca atividades automaticamente</p>
        </div>
      </div>

      <div className="selector-panel" style={{ marginBottom: '20px', padding: '20px', backgroundColor: '#f5f5f5', borderRadius: '8px' }}>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Setor *</label>
            <select
              value={selectedSectorId || ''}
              onChange={e => setSelectedSectorId(e.target.value ? Number(e.target.value) : null)}
              style={{ padding: '10px', minWidth: '250px', fontSize: '14px' }}
            >
              <option value="">Selecione um setor...</option>
              {sectors.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          
          {selectedSectorId && (
            <>
              <div>
                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>Filtrar por Escopo</label>
                <select
                  value={filterEscopo}
                  onChange={e => setFilterEscopo(e.target.value)}
                  style={{ padding: '10px', minWidth: '180px' }}
                >
                  <option value="">Todos</option>
                  {escopoOptions.map(e => (
                    <option key={e.value} value={e.value}>{e.label}</option>
                  ))}
                </select>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '20px' }}>
                <input
                  type="checkbox"
                  id="showInactive"
                  checked={showInactive}
                  onChange={e => setShowInactive(e.target.checked)}
                />
                <label htmlFor="showInactive">Mostrar inativas</label>
              </div>
              
              <button 
                className="btn-primary"
                onClick={openCreate}
                style={{ marginTop: '20px' }}
              >
                + Nova Regra
              </button>
            </>
          )}
        </div>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`} style={{ marginBottom: '20px' }}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {selectedSectorId && validation && (
        <div style={{ 
          marginBottom: '20px', 
          padding: '15px', 
          borderRadius: '8px',
          backgroundColor: validation.pode_usar_modo_auto ? '#e8f5e9' : '#fff3e0',
          border: `1px solid ${validation.pode_usar_modo_auto ? '#4CAF50' : '#FF9800'}`
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '24px' }}>{validation.pode_usar_modo_auto ? '✓' : '⚠'}</span>
            <div>
              <strong>{validation.pode_usar_modo_auto ? 'Pronto para Modo AUTO' : 'Configuracao Incompleta'}</strong>
              {validation.erros && (validation.erros as Array<{ mensagem: string }>).length > 0 && (
                <ul style={{ margin: '10px 0 0 0', paddingLeft: '20px' }}>
                  {(validation.erros as Array<{ mensagem: string }>).map((erro, i) => (
                    <li key={i}>{erro.mensagem}</li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {!selectedSectorId && (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: '#666' }}>
          <p style={{ fontSize: '18px' }}>Selecione um setor para gerenciar suas regras de calculo</p>
        </div>
      )}

      {selectedSectorId && loading && (
        <div style={{ textAlign: 'center', padding: '40px' }}>Carregando regras...</div>
      )}

      {selectedSectorId && !loading && regras.length === 0 && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
          <p>Nenhuma regra cadastrada para este setor.</p>
          <button className="btn-primary" onClick={openCreate}>Criar Primeira Regra</button>
        </div>
      )}

      {selectedSectorId && !loading && regras.length > 0 && (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '60px' }}>Prio</th>
                <th>Nome</th>
                <th style={{ width: '120px' }}>Escopo</th>
                <th>Condicao</th>
                <th>Acao</th>
                <th style={{ width: '80px' }}>Status</th>
                <th style={{ width: '150px' }}>Acoes</th>
              </tr>
            </thead>
            <tbody>
              {regras.map(regra => (
                <tr key={regra.id} style={{ opacity: regra.ativo ? 1 : 0.6 }}>
                  <td style={{ textAlign: 'center', fontWeight: 'bold' }}>{regra.prioridade}</td>
                  <td>
                    <div style={{ fontWeight: '500' }}>{regra.nome}</div>
                    {regra.descricao && <div style={{ fontSize: '12px', color: '#666' }}>{regra.descricao}</div>}
                  </td>
                  <td>
                    <span style={{ 
                      padding: '4px 8px', 
                      borderRadius: '4px', 
                      backgroundColor: getEscopoColor(regra.escopo),
                      color: 'white',
                      fontSize: '12px'
                    }}>
                      {regra.escopo}
                    </span>
                  </td>
                  <td style={{ fontSize: '12px' }}>
                    {regra.condicao_json ? JSON.stringify(regra.condicao_json) : '-'}
                  </td>
                  <td style={{ fontSize: '12px' }}>
                    {JSON.stringify(regra.acao_json)}
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <span style={{ color: regra.ativo ? '#4CAF50' : '#999' }}>
                      {regra.ativo ? 'Ativa' : 'Inativa'}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '5px' }}>
                      <button className="btn-small" onClick={() => openEdit(regra)}>Editar</button>
                      <button className="btn-small" onClick={() => handleDuplicate(regra.id)}>Copiar</button>
                      <button className="btn-small btn-danger" onClick={() => handleDelete(regra.id)}>X</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()} style={{ maxWidth: '700px' }}>
            <h2>{editing ? 'Editar Regra' : 'Nova Regra'}</h2>
            
            <form onSubmit={handleSubmit}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                  <label>Nome da Regra *</label>
                  <input
                    type="text"
                    value={form.nome}
                    onChange={e => setForm({ ...form, nome: e.target.value })}
                    placeholder="Ex: Calculo base por ocupacao"
                  />
                </div>
                
                <div className="form-group">
                  <label>Prioridade (menor = primeiro)</label>
                  <input
                    type="number"
                    value={form.prioridade}
                    onChange={e => setForm({ ...form, prioridade: Number(e.target.value) })}
                    min={1}
                    max={9999}
                  />
                </div>
                
                <div className="form-group">
                  <label>Escopo *</label>
                  <select
                    value={form.escopo}
                    onChange={e => setForm({ ...form, escopo: e.target.value as EscopoType })}
                  >
                    {escopoOptions.map(e => (
                      <option key={e.value} value={e.value}>{e.label} - {e.description}</option>
                    ))}
                  </select>
                </div>
                
                <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                  <label>Descricao</label>
                  <textarea
                    value={form.descricao}
                    onChange={e => setForm({ ...form, descricao: e.target.value })}
                    placeholder="Descreva o proposito desta regra..."
                    rows={2}
                  />
                </div>
              </div>

              <fieldset style={{ marginTop: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '8px' }}>
                <legend style={{ fontWeight: 'bold', padding: '0 10px' }}>Condicao (quando aplicar)</legend>
                
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
                  <div className="form-group">
                    <label>Driver</label>
                    <select
                      value={form.condicao_driver}
                      onChange={e => setForm({ ...form, condicao_driver: e.target.value })}
                    >
                      {driverOptions.map(d => (
                        <option key={d.value} value={d.value}>{d.label}</option>
                      ))}
                    </select>
                  </div>
                  
                  <div className="form-group">
                    <label>Minimo</label>
                    <input
                      type="number"
                      value={form.condicao_min}
                      onChange={e => setForm({ ...form, condicao_min: Number(e.target.value) })}
                      step="0.01"
                    />
                  </div>
                  
                  <div className="form-group">
                    <label>Maximo</label>
                    <input
                      type="number"
                      value={form.condicao_max}
                      onChange={e => setForm({ ...form, condicao_max: Number(e.target.value) })}
                      step="0.01"
                    />
                  </div>
                </div>
                
                <div className="form-group" style={{ marginTop: '10px' }}>
                  <label>Dias da Semana (opcional)</label>
                  <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                    {diasSemana.map(dia => (
                      <label key={dia.value} style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={form.condicao_dias.includes(dia.value)}
                          onChange={() => toggleDia(dia.value)}
                        />
                        {dia.label}
                      </label>
                    ))}
                  </div>
                </div>
              </fieldset>

              <fieldset style={{ marginTop: '20px', padding: '15px', border: '1px solid #ddd', borderRadius: '8px' }}>
                <legend style={{ fontWeight: 'bold', padding: '0 10px' }}>Acao (o que fazer)</legend>
                
                <div className="form-group">
                  <label>Tipo de Acao *</label>
                  <select
                    value={form.acao_tipo}
                    onChange={e => setForm({ ...form, acao_tipo: e.target.value })}
                  >
                    {acaoTipoOptions.map(a => (
                      <option key={a.value} value={a.value}>{a.label}</option>
                    ))}
                  </select>
                </div>
                
                {form.acao_tipo === 'inserir_atividade' && (
                  <div className="form-group">
                    <label>Atividade a Inserir *</label>
                    <select
                      value={form.acao_atividade_id || ''}
                      onChange={e => setForm({ ...form, acao_atividade_id: e.target.value ? Number(e.target.value) : null })}
                    >
                      <option value="">Selecione...</option>
                      {activities.filter(a => a.classificacao_atividade === 'CALCULADA_PELO_AGENTE').map(a => (
                        <option key={a.id} value={a.id}>{a.code} - {a.name}</option>
                      ))}
                    </select>
                  </div>
                )}
                
                {(form.acao_tipo === 'multiplicar_demanda' || form.acao_tipo === 'aplicar_fator') && (
                  <div className="form-group">
                    <label>Fator</label>
                    <input
                      type="number"
                      value={form.acao_fator}
                      onChange={e => setForm({ ...form, acao_fator: Number(e.target.value) })}
                      step="0.01"
                    />
                  </div>
                )}
                
                {form.acao_tipo === 'adicionar_minutos' && (
                  <div className="form-group">
                    <label>Minutos</label>
                    <input
                      type="number"
                      value={form.acao_minutos}
                      onChange={e => setForm({ ...form, acao_minutos: Number(e.target.value) })}
                    />
                  </div>
                )}
                
                {form.acao_tipo === 'aplicar_fator' && (
                  <div className="form-group">
                    <label>Parametro</label>
                    <input
                      type="text"
                      value={form.acao_parametro}
                      onChange={e => setForm({ ...form, acao_parametro: e.target.value })}
                      placeholder="Nome do parametro"
                    />
                  </div>
                )}
              </fieldset>

              <div className="form-group" style={{ marginTop: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.ativo}
                    onChange={e => setForm({ ...form, ativo: e.target.checked })}
                  />
                  Regra Ativa
                </label>
              </div>

              <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', marginTop: '20px' }}>
                <button type="button" className="btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn-primary">
                  {editing ? 'Salvar Alteracoes' : 'Criar Regra'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default RegrasCalculoPage;
