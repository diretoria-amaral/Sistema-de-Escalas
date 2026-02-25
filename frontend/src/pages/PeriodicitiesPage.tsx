import { useState, useEffect } from 'react';

type IntervalUnit = 'DAYS' | 'MONTHS' | 'YEARS';
type AnchorPolicy = 'SAME_DAY' | 'LAST_DAY_IF_MISSING';

interface Periodicity {
  id: number;
  name: string;
  tipo: string;
  interval_unit: IntervalUnit;
  interval_value: number;
  anchor_policy: AnchorPolicy;
  intervalo_dias: number;
  description: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string | null;
}

interface PeriodicityForm {
  name: string;
  interval_unit: IntervalUnit;
  interval_value: number;
  anchor_policy: AnchorPolicy;
  description: string;
  is_active: boolean;
}

const initialForm: PeriodicityForm = {
  name: '',
  interval_unit: 'DAYS',
  interval_value: 7,
  anchor_policy: 'SAME_DAY',
  description: '',
  is_active: true
};

const presetOptions = [
  { label: 'Diaria', unit: 'DAYS' as IntervalUnit, value: 1, icon: '📅' },
  { label: 'Semanal', unit: 'DAYS' as IntervalUnit, value: 7, icon: '📆' },
  { label: 'Quinzenal', unit: 'DAYS' as IntervalUnit, value: 14, icon: '🗓️' },
  { label: 'Mensal', unit: 'MONTHS' as IntervalUnit, value: 1, icon: '📋' },
  { label: 'Trimestral', unit: 'MONTHS' as IntervalUnit, value: 3, icon: '📊' },
  { label: 'Anual', unit: 'YEARS' as IntervalUnit, value: 1, icon: '🗓️' },
];

function getExpansionText(unit: IntervalUnit, value: number): string {
  if (unit === 'DAYS') {
    if (value === 1) return 'Executa todos os dias';
    if (value === 7) return 'Executa 1x por semana';
    if (value === 14) return 'Executa a cada 2 semanas';
    return `Executa a cada ${value} dias`;
  }
  if (unit === 'MONTHS') {
    if (value === 1) return 'Executa 1x por mes';
    if (value === 3) return 'Executa 1x por trimestre';
    if (value === 6) return 'Executa 1x por semestre';
    return `Executa a cada ${value} meses`;
  }
  if (unit === 'YEARS') {
    if (value === 1) return 'Executa 1x por ano';
    return `Executa a cada ${value} anos`;
  }
  return `Executa a cada ${value}`;
}

function getIntervalBadgeColor(unit: IntervalUnit, value: number): string {
  if (unit === 'DAYS') {
    if (value === 1) return '#10b981';
    if (value === 7) return '#3b82f6';
    if (value === 14) return '#8b5cf6';
    return '#6b7280';
  }
  if (unit === 'MONTHS') return '#f59e0b';
  if (unit === 'YEARS') return '#ef4444';
  return '#6b7280';
}

function getIntervalDisplayText(unit: IntervalUnit, value: number): string {
  const unitLabels: Record<IntervalUnit, string> = {
    'DAYS': value === 1 ? 'dia' : 'dias',
    'MONTHS': value === 1 ? 'mes' : 'meses',
    'YEARS': value === 1 ? 'ano' : 'anos'
  };
  return `${value} ${unitLabels[unit]}`;
}

function PeriodicitiesPage() {
  const [periodicities, setPeriodicities] = useState<Periodicity[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editing, setEditing] = useState<Periodicity | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [form, setForm] = useState<PeriodicityForm>(initialForm);
  const [showInactive, setShowInactive] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, [showInactive]);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`/api/periodicities/?active_only=${!showInactive}`);
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Erro ao carregar periodicidades');
      }
      const data = await res.json();
      setPeriodicities(data);
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Erro ao carregar dados' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!form.name.trim()) {
      setMessage({ type: 'error', text: 'Nome da periodicidade e obrigatorio' });
      return;
    }
    
    if (form.interval_value < 1) {
      setMessage({ type: 'error', text: 'Valor do intervalo deve ser maior que zero' });
      return;
    }
    
    setSubmitting(true);
    try {
      const url = editing ? `/api/periodicities/${editing.id}` : '/api/periodicities/';
      const method = editing ? 'PUT' : 'POST';
      
      const payload = {
        name: form.name.trim(),
        interval_unit: form.interval_unit,
        interval_value: form.interval_value,
        anchor_policy: form.anchor_policy,
        description: form.description.trim() || null,
        is_active: form.is_active
      };
      
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        setMessage({ type: 'error', text: data.detail || 'Erro ao salvar periodicidade' });
        return;
      }
      
      setMessage({ type: 'success', text: editing ? 'Periodicidade atualizada!' : 'Periodicidade criada!' });
      setShowModal(false);
      resetForm();
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao salvar periodicidade' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Deseja desativar esta periodicidade?')) return;
    
    try {
      const res = await fetch(`/api/periodicities/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json();
        setMessage({ type: 'error', text: data.detail || 'Erro ao desativar periodicidade' });
        return;
      }
      setMessage({ type: 'success', text: 'Periodicidade desativada!' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao desativar periodicidade' });
    }
  };

  const resetForm = () => {
    setForm(initialForm);
    setEditing(null);
  };

  const openEdit = (p: Periodicity) => {
    setEditing(p);
    setForm({
      name: p.name,
      interval_unit: p.interval_unit || 'DAYS',
      interval_value: p.interval_value || p.intervalo_dias || 1,
      anchor_policy: p.anchor_policy || 'SAME_DAY',
      description: p.description || '',
      is_active: p.is_active
    });
    setShowModal(true);
  };

  const selectPreset = (unit: IntervalUnit, value: number) => {
    const preset = presetOptions.find(p => p.unit === unit && p.value === value);
    if (preset && !editing) {
      setForm({ ...form, interval_unit: unit, interval_value: value, name: form.name || preset.label });
    } else {
      setForm({ ...form, interval_unit: unit, interval_value: value });
    }
  };

  return (
    <div style={{ padding: '24px', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 'bold', color: '#1f2937', margin: 0 }}>
            Periodicidades
          </h1>
          <p style={{ color: '#6b7280', marginTop: '4px', fontSize: '0.9rem' }}>
            Configure a frequência de execução das atividades recorrentes
          </p>
        </div>
        <button
          onClick={() => { resetForm(); setShowModal(true); }}
          style={{
            backgroundColor: '#2563eb',
            color: 'white',
            padding: '10px 20px',
            borderRadius: '8px',
            border: 'none',
            fontWeight: '600',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <span style={{ fontSize: '1.2rem' }}>+</span>
          Nova Periodicidade
        </button>
      </div>

      {message && (
        <div style={{
          marginBottom: '16px',
          padding: '12px 16px',
          borderRadius: '8px',
          backgroundColor: message.type === 'error' ? '#fef2f2' : '#f0fdf4',
          color: message.type === 'error' ? '#dc2626' : '#16a34a',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          {message.text}
          <button 
            onClick={() => setMessage(null)} 
            style={{ background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold', fontSize: '1.1rem' }}
          >
            ×
          </button>
        </div>
      )}

      <div style={{ marginBottom: '20px' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.875rem', color: '#6b7280', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            style={{ accentColor: '#2563eb' }}
          />
          Mostrar inativas
        </label>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '48px', color: '#6b7280' }}>
          Carregando...
        </div>
      ) : periodicities.length === 0 ? (
        <div style={{
          textAlign: 'center',
          padding: '64px 24px',
          backgroundColor: '#f9fafb',
          borderRadius: '12px',
          border: '2px dashed #e5e7eb'
        }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>📅</div>
          <h3 style={{ color: '#374151', marginBottom: '8px' }}>Nenhuma periodicidade cadastrada</h3>
          <p style={{ color: '#6b7280', marginBottom: '16px' }}>
            Crie periodicidades para definir a frequência das atividades recorrentes.
          </p>
          <button
            onClick={() => { resetForm(); setShowModal(true); }}
            style={{
              backgroundColor: '#2563eb',
              color: 'white',
              padding: '10px 20px',
              borderRadius: '8px',
              border: 'none',
              fontWeight: '500',
              cursor: 'pointer'
            }}
          >
            Criar primeira periodicidade
          </button>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '16px'
        }}>
          {periodicities.map((p) => (
            <div
              key={p.id}
              style={{
                backgroundColor: p.is_active ? '#ffffff' : '#f9fafb',
                borderRadius: '12px',
                border: '1px solid #e5e7eb',
                padding: '20px',
                opacity: p.is_active ? 1 : 0.7,
                transition: 'box-shadow 0.2s',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ 
                    fontSize: '1.1rem', 
                    fontWeight: '600', 
                    color: '#1f2937', 
                    margin: 0,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px'
                  }}>
                    {p.name}
                  </h3>
                  {p.description && (
                    <p style={{ color: '#6b7280', fontSize: '0.875rem', marginTop: '4px', margin: '4px 0 0 0' }}>
                      {p.description}
                    </p>
                  )}
                </div>
                <span style={{
                  padding: '4px 10px',
                  borderRadius: '9999px',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  backgroundColor: p.is_active ? '#dcfce7' : '#f3f4f6',
                  color: p.is_active ? '#166534' : '#6b7280'
                }}>
                  {p.is_active ? 'Ativa' : 'Inativa'}
                </span>
              </div>

              <div style={{
                backgroundColor: '#f8fafc',
                borderRadius: '8px',
                padding: '12px',
                marginBottom: '16px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{
                    width: '48px',
                    height: '40px',
                    borderRadius: '8px',
                    backgroundColor: getIntervalBadgeColor(p.interval_unit || 'DAYS', p.interval_value || p.intervalo_dias),
                    color: 'white',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 'bold',
                    fontSize: '0.75rem',
                    textAlign: 'center',
                    padding: '2px'
                  }}>
                    {getIntervalDisplayText(p.interval_unit || 'DAYS', p.interval_value || p.intervalo_dias)}
                  </div>
                  <div>
                    <div style={{ fontWeight: '500', color: '#374151' }}>
                      Regra de Expansao
                    </div>
                    <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                      {getExpansionText(p.interval_unit || 'DAYS', p.interval_value || p.intervalo_dias)}
                    </div>
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => openEdit(p)}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb',
                    backgroundColor: 'white',
                    color: '#374151',
                    cursor: 'pointer',
                    fontSize: '0.875rem',
                    fontWeight: '500'
                  }}
                >
                  Editar
                </button>
                {p.is_active && (
                  <button
                    onClick={() => handleDelete(p.id)}
                    style={{
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid #fecaca',
                      backgroundColor: '#fef2f2',
                      color: '#dc2626',
                      cursor: 'pointer',
                      fontSize: '0.875rem',
                      fontWeight: '500'
                    }}
                  >
                    Desativar
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'white',
            borderRadius: '16px',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
            width: '100%',
            maxWidth: '480px',
            padding: '24px',
            maxHeight: '90vh',
            overflowY: 'auto'
          }}>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '20px', color: '#1f2937' }}>
              {editing ? 'Editar Periodicidade' : 'Nova Periodicidade'}
            </h2>
            
            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>
                  Nome *
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: '1px solid #d1d5db',
                    borderRadius: '8px',
                    fontSize: '0.95rem',
                    boxSizing: 'border-box'
                  }}
                  placeholder="Ex: Semanal, Quinzenal, etc."
                  disabled={submitting}
                />
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#374151', marginBottom: '8px' }}>
                  Intervalo de Execucao
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginBottom: '12px' }}>
                  {presetOptions.map((preset) => (
                    <button
                      key={`${preset.unit}-${preset.value}`}
                      type="button"
                      onClick={() => selectPreset(preset.unit, preset.value)}
                      disabled={submitting}
                      style={{
                        padding: '10px 8px',
                        borderRadius: '8px',
                        border: form.interval_unit === preset.unit && form.interval_value === preset.value ? '2px solid #2563eb' : '1px solid #e5e7eb',
                        backgroundColor: form.interval_unit === preset.unit && form.interval_value === preset.value ? '#eff6ff' : 'white',
                        cursor: 'pointer',
                        textAlign: 'center'
                      }}
                    >
                      <div style={{ fontSize: '1.2rem', marginBottom: '2px' }}>{preset.icon}</div>
                      <div style={{ fontSize: '0.75rem', fontWeight: '500', color: '#374151' }}>{preset.label}</div>
                    </button>
                  ))}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <span style={{ fontSize: '0.875rem', color: '#6b7280' }}>Repetir a cada:</span>
                  <input
                    type="number"
                    min="1"
                    value={form.interval_value}
                    onChange={(e) => setForm({ ...form, interval_value: parseInt(e.target.value) || 1 })}
                    style={{
                      width: '70px',
                      padding: '8px 10px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      textAlign: 'center'
                    }}
                    disabled={submitting}
                  />
                  <select
                    value={form.interval_unit}
                    onChange={(e) => setForm({ ...form, interval_unit: e.target.value as IntervalUnit })}
                    style={{
                      padding: '8px 12px',
                      border: '1px solid #d1d5db',
                      borderRadius: '6px',
                      backgroundColor: 'white'
                    }}
                    disabled={submitting}
                  >
                    <option value="DAYS">dias</option>
                    <option value="MONTHS">meses</option>
                    <option value="YEARS">anos</option>
                  </select>
                </div>
                <div style={{
                  padding: '10px 12px',
                  backgroundColor: '#fef3c7',
                  borderRadius: '6px',
                  fontSize: '0.8rem',
                  color: '#92400e',
                  marginBottom: '8px'
                }}>
                  Dica: Use meses para trimestral (3 meses), semestral (6 meses). Evite usar dias para periodos mensais (meses tem comprimentos diferentes).
                </div>
                <div style={{
                  padding: '8px 12px',
                  backgroundColor: '#f0fdf4',
                  borderRadius: '6px',
                  fontSize: '0.875rem',
                  color: '#166534'
                }}>
                  {getExpansionText(form.interval_unit, form.interval_value)}
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: '500', color: '#374151', marginBottom: '6px' }}>
                  Descrição (opcional)
                </label>
                <textarea
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    border: '1px solid #d1d5db',
                    borderRadius: '8px',
                    fontSize: '0.95rem',
                    resize: 'vertical',
                    minHeight: '60px',
                    boxSizing: 'border-box'
                  }}
                  rows={2}
                  placeholder="Descreva quando esta periodicidade deve ser usada..."
                  disabled={submitting}
                />
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
                    style={{ accentColor: '#2563eb', width: '16px', height: '16px' }}
                    disabled={submitting}
                  />
                  <span style={{ fontSize: '0.875rem', color: '#374151' }}>Ativa</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => { setShowModal(false); resetForm(); }}
                  disabled={submitting}
                  style={{
                    padding: '10px 20px',
                    borderRadius: '8px',
                    border: '1px solid #d1d5db',
                    backgroundColor: 'white',
                    color: '#374151',
                    cursor: 'pointer',
                    fontWeight: '500'
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  style={{
                    padding: '10px 20px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: '#2563eb',
                    color: 'white',
                    cursor: submitting ? 'not-allowed' : 'pointer',
                    fontWeight: '500',
                    opacity: submitting ? 0.7 : 1
                  }}
                >
                  {submitting ? 'Salvando...' : (editing ? 'Salvar' : 'Criar')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default PeriodicitiesPage;
