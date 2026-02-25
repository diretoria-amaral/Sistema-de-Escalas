import { useState, useEffect } from 'react';
import { sectorsApi, dailySuggestionsApi, Sector, DailySuggestion } from '../services/client';

const SUGGESTION_TYPE_LABELS: Record<string, string> = {
  team_reinforcement: 'Reforco de Equipe',
  hours_reduction: 'Reducao de Horas',
  shift_anticipation: 'Antecipacao de Turno',
  shift_postponement: 'Adiamento de Turno',
  preventive_substitution: 'Substituicao Preventiva',
  schedule_adjustment: 'Ajuste de Escala',
};

const IMPACT_BADGES: Record<string, { color: string; label: string }> = {
  financial: { color: '#22c55e', label: 'Financeiro' },
  operational: { color: '#3b82f6', label: 'Operacional' },
  legal: { color: '#ef4444', label: 'Legal' },
};

export default function DailySuggestionsPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<DailySuggestion[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('open');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [generateDate, setGenerateDate] = useState<string>(new Date().toISOString().split('T')[0]);

  useEffect(() => {
    loadSectors();
  }, []);

  useEffect(() => {
    loadSuggestions();
  }, [selectedSector, statusFilter]);

  const loadSectors = async () => {
    try {
      const response = await sectorsApi.list();
      setSectors(response.data);
      if (response.data.length > 0 && !selectedSector) {
        setSelectedSector(response.data[0].id);
      }
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar setores' });
    }
  };

  const loadSuggestions = async () => {
    setLoading(true);
    try {
      const params: any = { limit: 100 };
      if (selectedSector) params.sector_id = selectedSector;
      if (statusFilter) params.status = statusFilter;
      
      const response = await dailySuggestionsApi.list(params);
      setSuggestions(response.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar sugestoes' });
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    if (!selectedSector) {
      setMessage({ type: 'error', text: 'Selecione um setor' });
      return;
    }
    
    setLoading(true);
    try {
      const response = await dailySuggestionsApi.generate(selectedSector, generateDate);
      setMessage({ 
        type: 'success', 
        text: response.data.length > 0 
          ? `${response.data.length} sugestao(oes) gerada(s)` 
          : 'Nenhuma nova sugestao identificada'
      });
      loadSuggestions();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao gerar sugestoes' });
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async (suggestion: DailySuggestion) => {
    const notes = prompt('Observacoes (opcional):');
    if (notes === null) return;
    
    try {
      await dailySuggestionsApi.apply(suggestion.id, undefined, notes || undefined);
      setMessage({ type: 'success', text: 'Sugestao aplicada. Adjustment Run criado.' });
      loadSuggestions();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao aplicar sugestao' });
    }
  };

  const handleIgnore = async (suggestion: DailySuggestion) => {
    const notes = prompt('Motivo para ignorar:');
    if (notes === null) return;
    
    try {
      await dailySuggestionsApi.ignore(suggestion.id, undefined, notes || undefined);
      setMessage({ type: 'success', text: 'Sugestao ignorada e registrada.' });
      loadSuggestions();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao ignorar sugestao' });
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('pt-BR');
  };

  return (
    <div style={{ padding: '24px' }}>
      <h1 style={{ fontSize: '28px', marginBottom: '24px' }}>Sugestoes Diarias (Copiloto)</h1>
      
      {message && (
        <div style={{
          padding: '12px 16px',
          borderRadius: '8px',
          marginBottom: '16px',
          backgroundColor: message.type === 'success' ? '#dcfce7' : '#fee2e2',
          color: message.type === 'success' ? '#166534' : '#dc2626'
        }}>
          {message.text}
        </div>
      )}

      <div style={{ 
        display: 'flex', 
        gap: '16px', 
        marginBottom: '24px',
        flexWrap: 'wrap',
        alignItems: 'flex-end'
      }}>
        <div>
          <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>Setor:</label>
          <select
            value={selectedSector || ''}
            onChange={(e) => setSelectedSector(Number(e.target.value))}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          >
            {sectors.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          >
            <option value="">Todos</option>
            <option value="open">Abertas</option>
            <option value="applied">Aplicadas</option>
            <option value="ignored">Ignoradas</option>
          </select>
        </div>

        <div>
          <label style={{ display: 'block', marginBottom: '4px', fontWeight: 500 }}>Data para Gerar:</label>
          <input
            type="date"
            value={generateDate}
            onChange={(e) => setGenerateDate(e.target.value)}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          />
        </div>

        <button
          onClick={handleGenerate}
          disabled={loading}
          style={{
            padding: '10px 20px',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
            fontWeight: 500
          }}
        >
          Gerar Sugestoes
        </button>
      </div>

      {loading ? (
        <p>Carregando...</p>
      ) : suggestions.length === 0 ? (
        <div style={{
          padding: '48px',
          textAlign: 'center',
          backgroundColor: '#f9fafb',
          borderRadius: '8px',
          color: '#6b7280'
        }}>
          <p>Nenhuma sugestao encontrada para os filtros selecionados.</p>
          <p style={{ marginTop: '8px', fontSize: '14px' }}>
            Clique em "Gerar Sugestoes" para analisar dados e criar recomendacoes.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {suggestions.map(suggestion => (
            <div
              key={suggestion.id}
              style={{
                backgroundColor: 'white',
                borderRadius: '8px',
                padding: '20px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                border: '1px solid #e5e7eb',
                opacity: suggestion.status !== 'open' ? 0.7 : 1
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 600,
                      backgroundColor: IMPACT_BADGES[suggestion.impact_category]?.color || '#6b7280',
                      color: 'white'
                    }}>
                      {IMPACT_BADGES[suggestion.impact_category]?.label || suggestion.impact_category}
                    </span>
                    <span style={{
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '12px',
                      backgroundColor: '#f3f4f6',
                      color: '#374151'
                    }}>
                      {SUGGESTION_TYPE_LABELS[suggestion.suggestion_type] || suggestion.suggestion_type}
                    </span>
                    <span style={{ fontSize: '12px', color: '#6b7280' }}>
                      Prioridade: {suggestion.priority}
                    </span>
                  </div>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>
                    {suggestion.sector_name} - {formatDate(suggestion.date)}
                  </h3>
                </div>
                <span style={{
                  padding: '4px 12px',
                  borderRadius: '20px',
                  fontSize: '12px',
                  fontWeight: 500,
                  backgroundColor: suggestion.status === 'open' ? '#fef3c7' : 
                    suggestion.status === 'applied' ? '#dcfce7' : '#f3f4f6',
                  color: suggestion.status === 'open' ? '#92400e' : 
                    suggestion.status === 'applied' ? '#166534' : '#6b7280'
                }}>
                  {suggestion.status === 'open' ? 'Aberta' : 
                   suggestion.status === 'applied' ? 'Aplicada' : 'Ignorada'}
                </span>
              </div>

              <p style={{ color: '#4b5563', marginBottom: '12px', lineHeight: 1.5 }}>
                {suggestion.description}
              </p>

              {suggestion.impact_json && Object.keys(suggestion.impact_json).length > 0 && (
                <div style={{ 
                  backgroundColor: '#f9fafb', 
                  padding: '12px', 
                  borderRadius: '6px',
                  marginBottom: '12px',
                  fontSize: '14px'
                }}>
                  <strong>Impacto estimado:</strong>
                  <div style={{ display: 'flex', gap: '16px', marginTop: '8px', flexWrap: 'wrap' }}>
                    {Object.entries(suggestion.impact_json).map(([key, value]) => (
                      <span key={key} style={{ color: '#6b7280' }}>
                        {key.replace(/_/g, ' ')}: <strong>{String(value)}</strong>
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {suggestion.status === 'open' && (
                <div style={{ display: 'flex', gap: '8px', marginTop: '16px' }}>
                  <button
                    onClick={() => handleApply(suggestion)}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: '#22c55e',
                      color: 'white',
                      border: 'none',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: 500
                    }}
                  >
                    Aplicar
                  </button>
                  <button
                    onClick={() => handleIgnore(suggestion)}
                    style={{
                      padding: '8px 16px',
                      backgroundColor: '#f3f4f6',
                      color: '#374151',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontWeight: 500
                    }}
                  >
                    Ignorar
                  </button>
                </div>
              )}

              {suggestion.resolved_at && (
                <div style={{ 
                  marginTop: '12px', 
                  fontSize: '13px', 
                  color: '#6b7280',
                  borderTop: '1px solid #e5e7eb',
                  paddingTop: '12px'
                }}>
                  Resolvido em: {new Date(suggestion.resolved_at).toLocaleString('pt-BR')}
                  {suggestion.resolved_by && ` por ${suggestion.resolved_by}`}
                  {suggestion.resolution_notes && ` - "${suggestion.resolution_notes}"`}
                  {suggestion.adjustment_run_id && (
                    <span style={{ marginLeft: '8px', color: '#3b82f6' }}>
                      (Adjustment Run #{suggestion.adjustment_run_id})
                    </span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
