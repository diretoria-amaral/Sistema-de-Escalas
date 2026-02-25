import { useState, useEffect } from 'react';
import { schedulesApi, weeklyParametersApi, sectorsApi, WeeklyParameters, Sector } from '../services/client';

interface Alocacao {
  colaborador_id: number;
  colaborador_nome: string;
  tipo_contrato: string;
  turno: string;
  dia: string;
  data: string;
  horas: number;
  entrada: string;
  inicio_intervalo: string;
  fim_intervalo: string;
  saida: string;
  atividade: string;
  editavel: boolean;
}

interface ColaboradorEscala {
  colaborador_id: number;
  colaborador_nome: string;
  tipo_contrato: string;
  total_horas_semana: number;
  dias_trabalhados: number;
  dias_folga: number;
  detalhes: Alocacao[];
}

function getNextMonday(): string {
  const today = new Date();
  const day = today.getDay();
  const diff = day === 0 ? 1 : 8 - day;
  const nextMonday = new Date(today);
  nextMonday.setDate(today.getDate() + diff);
  return nextMonday.toISOString().split('T')[0];
}

export default function SchedulePage() {
  const [weeksList, setWeeksList] = useState<WeeklyParameters[]>([]);
  const [selectedWeek, setSelectedWeek] = useState<string>(getNextMonday());
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingCalc, setLoadingCalc] = useState(false);
  const [escala, setEscala] = useState<any>(null);
  const [necessidade, setNecessidade] = useState<any>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [viewMode, setViewMode] = useState<'diaria' | 'colaborador'>('colaborador');
  const [editingCell, setEditingCell] = useState<string | null>(null);

  useEffect(() => {
    loadSectors();
    loadWeeks();
  }, []);

  const loadSectors = async () => {
    try {
      const res = await sectorsApi.list();
      setSectors(res.data);
      if (res.data.length > 0) {
        setSelectedSector(res.data[0].id);
      }
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar setores' });
    }
  };

  const getSectorName = () => {
    const sector = sectors.find(s => s.id === selectedSector);
    return sector?.name || 'Setor';
  };

  const loadWeeks = async () => {
    try {
      const res = await weeklyParametersApi.list();
      setWeeksList(res.data);
      if (res.data.length > 0) {
        setSelectedWeek(res.data[0].semana_inicio);
      }
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar semanas' });
    }
  };

  const calcularNecessidade = async () => {
    if (!selectedWeek) {
      setMessage({ type: 'error', text: 'Selecione uma semana' });
      return;
    }

    try {
      setLoadingCalc(true);
      setNecessidade(null);
      const res = await schedulesApi.calcularNecessidade(selectedWeek, selectedSector || undefined);
      setNecessidade(res.data);
      setMessage({ type: 'success', text: 'Calculo de necessidade concluido!' });
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao calcular necessidade' });
    } finally {
      setLoadingCalc(false);
    }
  };

  const gerarEscala = async () => {
    if (!selectedWeek) {
      setMessage({ type: 'error', text: 'Selecione uma semana' });
      return;
    }

    try {
      setLoading(true);
      setEscala(null);
      const res = await schedulesApi.gerarEscalaSugestiva(selectedWeek, selectedSector || undefined);
      setEscala(res.data);
      setMessage({ type: 'success', text: 'Escala sugestiva gerada! Voce pode editar manualmente.' });
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao gerar escala' });
    } finally {
      setLoading(false);
    }
  };

  const handleCellEdit = (colabId: number, diaIdx: number, field: keyof Alocacao, value: string) => {
    if (!escala || !escala.escala_colaboradores) return;
    
    const newEscala = { ...escala };
    const colab = newEscala.escala_colaboradores.find((c: ColaboradorEscala) => c.colaborador_id === colabId);
    if (colab && colab.detalhes[diaIdx]) {
      (colab.detalhes[diaIdx] as any)[field] = value;
      setEscala(newEscala);
    }
    setEditingCell(null);
  };

  const exportarCSV = () => {
    if (!escala || !escala.escala_colaboradores) return;

    let csv = 'Colaborador,Tipo Contrato,Dia,Data,Horas,Entrada,Início Intervalo,Fim Intervalo,Saída,Atividade\n';
    
    escala.escala_colaboradores.forEach((colab: ColaboradorEscala) => {
      colab.detalhes.forEach((det: Alocacao) => {
        csv += `${det.colaborador_nome},${det.tipo_contrato},${det.dia},${det.data},${det.horas},${det.entrada},${det.inicio_intervalo},${det.fim_intervalo},${det.saida},${det.atividade}\n`;
      });
    });

    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `escala_${getSectorName().toLowerCase()}_${selectedWeek}.csv`;
    link.click();
  };

  return (
    <div>
      {message && (
        <div className={message.type === 'error' ? 'error' : 'success'}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
        </div>
      )}

      <div className="card">
        <h2>Geracao de Escala Sugestiva - {getSectorName()}</h2>
        <p style={{ color: '#666', marginBottom: '1.5rem' }}>
          A escala e gerada de forma sugestiva. Voce pode editar manualmente clicando nas celulas.
        </p>

        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', marginBottom: '1.5rem' }}>
          <div className="form-group">
            <label>Setor</label>
            <select
              value={selectedSector || ''}
              onChange={e => {
                setSelectedSector(Number(e.target.value));
                setEscala(null);
                setNecessidade(null);
              }}
              style={{ minWidth: '180px' }}
            >
              {sectors.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ flex: 1 }}>
            <label>Semana (Segunda-feira)</label>
            <select
              value={selectedWeek}
              onChange={e => setSelectedWeek(e.target.value)}
            >
              {weeksList.length === 0 ? (
                <option value="">Nenhuma semana cadastrada</option>
              ) : (
                weeksList.map(w => (
                  <option key={w.id} value={w.semana_inicio}>
                    {new Date(w.semana_inicio + 'T12:00:00').toLocaleDateString('pt-BR')}
                  </option>
                ))
              )}
            </select>
          </div>
          <button
            onClick={calcularNecessidade}
            className="btn"
            disabled={loadingCalc || weeksList.length === 0}
            style={{ background: '#17a2b8' }}
          >
            {loadingCalc ? 'Calculando...' : 'Calcular Necessidade'}
          </button>
          <button
            onClick={gerarEscala}
            className="btn"
            disabled={loading || weeksList.length === 0}
          >
            {loading ? 'Gerando...' : 'Gerar Escala'}
          </button>
        </div>

        {weeksList.length === 0 && (
          <div style={{ padding: '1rem', background: '#fff3cd', borderRadius: '6px' }}>
            Nenhuma semana com parâmetros cadastrados. Acesse a aba "Parâmetros Semanais" para cadastrar.
          </div>
        )}
      </div>

      {necessidade && (
        <div className="card">
          <h3>Cálculo de Necessidade de Horas</h3>
          <p><strong>Total Semanal:</strong> {necessidade.total_horas_semana} horas</p>
          
          <table className="table">
            <thead>
              <tr>
                <th>Dia</th>
                <th>Tipo</th>
                <th>Min. Vago Sujo</th>
                <th>Min. Estada</th>
                <th>Min. Total</th>
                <th>Horas Necessárias</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(necessidade.necessidade_por_dia).map(([dia, info]: [string, any]) => (
                <tr key={dia}>
                  <td><strong>{info.nome_dia}</strong></td>
                  <td>
                    <span style={{
                      padding: '2px 8px',
                      borderRadius: '4px',
                      background: info.tipo_dia === 'feriado' ? '#dc3545' : 
                                  info.tipo_dia === 'vespera_feriado' ? '#ffc107' : '#28a745',
                      color: info.tipo_dia === 'vespera_feriado' ? '#000' : '#fff',
                      fontSize: '12px'
                    }}>
                      {info.tipo_dia === 'feriado' ? 'Feriado' : 
                       info.tipo_dia === 'vespera_feriado' ? 'Véspera' : 'Normal'}
                    </span>
                  </td>
                  <td>{Math.round(info.minutos_vago_sujo)} min</td>
                  <td>{Math.round(info.minutos_estada)} min</td>
                  <td>{Math.round(info.minutos_totais)} min</td>
                  <td><strong>{info.horas_necessarias}h</strong></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {escala && escala.escala_colaboradores && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3>Escala Sugestiva - Semana de {new Date(escala.semana_inicio + 'T12:00:00').toLocaleDateString('pt-BR')}</h3>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              <button 
                onClick={() => setViewMode('colaborador')}
                className="btn"
                style={{ background: viewMode === 'colaborador' ? '#007bff' : '#6c757d' }}
              >
                Por Colaborador
              </button>
              <button 
                onClick={() => setViewMode('diaria')}
                className="btn"
                style={{ background: viewMode === 'diaria' ? '#007bff' : '#6c757d' }}
              >
                Por Dia
              </button>
              <button onClick={exportarCSV} className="btn" style={{ background: '#28a745' }}>
                Exportar CSV
              </button>
            </div>
          </div>

          {escala.erro && (
            <div className="error">{escala.erro}</div>
          )}

          {escala.resumo && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
              <div style={{ padding: '1rem', background: '#e3f2fd', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{escala.resumo.total_horas_necessarias}h</div>
                <div style={{ fontSize: '12px', color: '#666' }}>Horas Necessárias</div>
              </div>
              <div style={{ padding: '1rem', background: '#e8f5e9', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{escala.resumo.total_horas_alocadas}h</div>
                <div style={{ fontSize: '12px', color: '#666' }}>Horas Alocadas</div>
              </div>
              <div style={{ padding: '1rem', background: escala.resumo.diferenca_total >= 0 ? '#e8f5e9' : '#ffebee', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{escala.resumo.cobertura_percentual}%</div>
                <div style={{ fontSize: '12px', color: '#666' }}>Cobertura</div>
              </div>
              <div style={{ padding: '1rem', background: '#fff3e0', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{escala.resumo.colaboradores_alocados}</div>
                <div style={{ fontSize: '12px', color: '#666' }}>Colaboradores</div>
              </div>
              <div style={{ padding: '1rem', background: '#f3e5f5', borderRadius: '6px', textAlign: 'center' }}>
                <div style={{ fontSize: '24px', fontWeight: 'bold' }}>{escala.regras_aplicadas?.regime_preferencial || '5x2'}</div>
                <div style={{ fontSize: '12px', color: '#666' }}>Regime</div>
              </div>
            </div>
          )}

          {viewMode === 'colaborador' && (
            <>
              <h4 style={{ marginTop: '1.5rem', marginBottom: '1rem' }}>
                Escala Detalhada por Colaborador
                <span style={{ fontSize: '0.8rem', color: '#666', marginLeft: '1rem' }}>
                  (Clique em uma célula para editar)
                </span>
              </h4>
              
              {escala.escala_colaboradores.map((colab: ColaboradorEscala) => (
                <div key={colab.colaborador_id} style={{ marginBottom: '2rem' }}>
                  <div style={{ 
                    background: '#f8f9fa', 
                    padding: '0.75rem 1rem', 
                    borderRadius: '6px 6px 0 0',
                    borderBottom: '2px solid #007bff',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                  }}>
                    <div>
                      <strong style={{ fontSize: '1.1rem' }}>{colab.colaborador_nome}</strong>
                      <span style={{ 
                        marginLeft: '1rem',
                        padding: '2px 8px', 
                        background: colab.tipo_contrato === 'intermitente' ? '#6c757d' : '#007bff',
                        color: '#fff',
                        borderRadius: '4px',
                        fontSize: '12px'
                      }}>
                        {colab.tipo_contrato}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.9rem', color: '#666' }}>
                      <span style={{ marginRight: '1rem' }}>Total: <strong>{colab.total_horas_semana}h</strong></span>
                      <span style={{ marginRight: '1rem' }}>Dias: <strong>{colab.dias_trabalhados}</strong></span>
                      <span>Folgas: <strong>{colab.dias_folga}</strong></span>
                    </div>
                  </div>
                  
                  <table className="table" style={{ borderRadius: '0 0 6px 6px', marginTop: 0 }}>
                    <thead>
                      <tr style={{ background: '#e9ecef' }}>
                        <th>Dia</th>
                        <th>Data</th>
                        <th>Horas</th>
                        <th>Entrada</th>
                        <th>Início Intervalo</th>
                        <th>Fim Intervalo</th>
                        <th>Saída</th>
                        <th>Atividade</th>
                      </tr>
                    </thead>
                    <tbody>
                      {colab.detalhes.map((det: Alocacao, idx: number) => (
                        <tr key={idx}>
                          <td><strong>{det.dia}</strong></td>
                          <td>{new Date(det.data + 'T12:00:00').toLocaleDateString('pt-BR')}</td>
                          <td>
                            {editingCell === `${colab.colaborador_id}-${idx}-horas` ? (
                              <input 
                                type="number" 
                                defaultValue={det.horas}
                                style={{ width: '60px' }}
                                onBlur={e => handleCellEdit(colab.colaborador_id, idx, 'horas', e.target.value)}
                                autoFocus
                              />
                            ) : (
                              <span 
                                onClick={() => setEditingCell(`${colab.colaborador_id}-${idx}-horas`)}
                                style={{ cursor: 'pointer', borderBottom: '1px dashed #007bff' }}
                              >
                                {det.horas}h
                              </span>
                            )}
                          </td>
                          <td>
                            {editingCell === `${colab.colaborador_id}-${idx}-entrada` ? (
                              <input 
                                type="time" 
                                defaultValue={det.entrada}
                                onBlur={e => handleCellEdit(colab.colaborador_id, idx, 'entrada', e.target.value)}
                                autoFocus
                              />
                            ) : (
                              <span 
                                onClick={() => setEditingCell(`${colab.colaborador_id}-${idx}-entrada`)}
                                style={{ cursor: 'pointer', borderBottom: '1px dashed #007bff' }}
                              >
                                {det.entrada}
                              </span>
                            )}
                          </td>
                          <td style={{ color: det.inicio_intervalo === '-' ? '#999' : 'inherit' }}>
                            {det.inicio_intervalo}
                          </td>
                          <td style={{ color: det.fim_intervalo === '-' ? '#999' : 'inherit' }}>
                            {det.fim_intervalo}
                          </td>
                          <td>
                            {editingCell === `${colab.colaborador_id}-${idx}-saida` ? (
                              <input 
                                type="time" 
                                defaultValue={det.saida}
                                onBlur={e => handleCellEdit(colab.colaborador_id, idx, 'saida', e.target.value)}
                                autoFocus
                              />
                            ) : (
                              <span 
                                onClick={() => setEditingCell(`${colab.colaborador_id}-${idx}-saida`)}
                                style={{ cursor: 'pointer', borderBottom: '1px dashed #007bff' }}
                              >
                                {det.saida}
                              </span>
                            )}
                          </td>
                          <td>
                            {editingCell === `${colab.colaborador_id}-${idx}-atividade` ? (
                              <input 
                                type="text" 
                                defaultValue={det.atividade}
                                style={{ width: '150px' }}
                                onBlur={e => handleCellEdit(colab.colaborador_id, idx, 'atividade', e.target.value)}
                                autoFocus
                              />
                            ) : (
                              <span 
                                onClick={() => setEditingCell(`${colab.colaborador_id}-${idx}-atividade`)}
                                style={{ cursor: 'pointer', borderBottom: '1px dashed #007bff' }}
                              >
                                {det.atividade}
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ))}
            </>
          )}

          {viewMode === 'diaria' && escala.escala_diaria && (
            <>
              <h4>Distribuição Diária</h4>
              <table className="table">
                <thead>
                  <tr>
                    <th>Dia</th>
                    <th>Data</th>
                    <th>Tipo</th>
                    <th>Necessário</th>
                    <th>Alocado</th>
                    <th>Diferença</th>
                    <th>Colaboradores</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(escala.escala_diaria).map(([dia, info]: [string, any]) => (
                    <tr key={dia}>
                      <td><strong>{info.nome_dia}</strong></td>
                      <td>{new Date(info.data + 'T12:00:00').toLocaleDateString('pt-BR')}</td>
                      <td>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          background: info.tipo_dia === 'feriado' ? '#dc3545' : 
                                      info.tipo_dia === 'vespera_feriado' ? '#ffc107' : '#28a745',
                          color: info.tipo_dia === 'vespera_feriado' ? '#000' : '#fff',
                          fontSize: '12px'
                        }}>
                          {info.tipo_dia === 'feriado' ? 'Feriado' : 
                           info.tipo_dia === 'vespera_feriado' ? 'Véspera' : 'Normal'}
                        </span>
                      </td>
                      <td>{info.horas_necessarias}h</td>
                      <td>{info.horas_alocadas}h</td>
                      <td style={{ color: info.diferenca >= 0 ? '#28a745' : '#dc3545' }}>
                        {info.diferenca >= 0 ? '+' : ''}{info.diferenca}h
                      </td>
                      <td>
                        {info.alocacoes && info.alocacoes.length > 0 ? (
                          <div style={{ fontSize: '13px' }}>
                            {info.alocacoes.map((a: Alocacao, i: number) => (
                              <div key={i} style={{ marginBottom: '4px' }}>
                                <strong>{a.colaborador_nome}</strong>
                                <span style={{ marginLeft: '0.5rem', color: '#666' }}>
                                  {a.entrada}-{a.saida} ({a.horas}h)
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: '#999' }}>Sem alocações</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {escala.regras_aplicadas && escala.regras_aplicadas.logica_customizada && (
            <div style={{ marginTop: '1.5rem', padding: '1rem', background: '#fff3cd', borderRadius: '6px' }}>
              <h5 style={{ margin: '0 0 0.5rem 0' }}>Lógica Customizada Aplicada:</h5>
              <pre style={{ margin: 0, whiteSpace: 'pre-wrap', fontFamily: 'inherit' }}>
                {escala.regras_aplicadas.logica_customizada}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
