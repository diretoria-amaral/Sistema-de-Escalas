import { useState, useEffect } from 'react';
import { shiftTemplatesApi, sectorsApi, ShiftTemplate, Sector } from '../services/client';

const WEEKDAY_LABELS = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'];

function ShiftTemplatesPage() {
  const [templates, setTemplates] = useState<ShiftTemplate[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<ShiftTemplate | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);

  const [form, setForm] = useState({
    name: '',
    start_time: '07:00',
    end_time: '15:00',
    break_minutes: 60,
    min_hours: 4,
    max_hours: 8,
    valid_weekdays: [0, 1, 2, 3, 4, 5, 6] as number[],
  });

  useEffect(() => {
    loadSectors();
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [selectedSector, showInactive]);

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

  const loadTemplates = async () => {
    try {
      setLoading(true);
      const res = await shiftTemplatesApi.list(selectedSector || undefined, !showInactive);
      setTemplates(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar templates' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!selectedSector) {
      setMessage({ type: 'error', text: 'Selecione um setor' });
      return;
    }

    try {
      const submitData = {
        ...form,
        sector_id: selectedSector,
      };

      if (editingTemplate) {
        await shiftTemplatesApi.update(editingTemplate.id, form);
        setMessage({ type: 'success', text: 'Template atualizado!' });
      } else {
        await shiftTemplatesApi.create(submitData);
        setMessage({ type: 'success', text: 'Template criado!' });
      }
      setShowModal(false);
      resetForm();
      loadTemplates();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail?.errors?.join('; ') ||
        error.response?.data?.detail || 'Erro ao salvar template';
      setMessage({ type: 'error', text: errorMsg });
    }
  };

  const handleEdit = (template: ShiftTemplate) => {
    setEditingTemplate(template);
    setForm({
      name: template.name,
      start_time: template.start_time,
      end_time: template.end_time,
      break_minutes: template.break_minutes,
      min_hours: template.min_hours,
      max_hours: template.max_hours,
      valid_weekdays: template.valid_weekdays,
    });
    setShowModal(true);
  };

  const handleToggleActive = async (template: ShiftTemplate) => {
    const action = template.is_active ? 'desativar' : 'ativar';
    if (!confirm(`Deseja ${action} o template "${template.name}"?`)) return;
    
    try {
      if (template.is_active) {
        await shiftTemplatesApi.disable(template.id);
        setMessage({ type: 'success', text: `Template "${template.name}" desativado` });
      } else {
        await shiftTemplatesApi.enable(template.id);
        setMessage({ type: 'success', text: `Template "${template.name}" ativado` });
      }
      loadTemplates();
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || 'Erro ao alterar status';
      setMessage({ type: 'error', text: errorMsg });
    }
  };

  const resetForm = () => {
    setEditingTemplate(null);
    setForm({
      name: '',
      start_time: '07:00',
      end_time: '15:00',
      break_minutes: 60,
      min_hours: 4,
      max_hours: 8,
      valid_weekdays: [0, 1, 2, 3, 4, 5, 6],
    });
  };

  const toggleWeekday = (day: number) => {
    setForm(prev => ({
      ...prev,
      valid_weekdays: prev.valid_weekdays.includes(day)
        ? prev.valid_weekdays.filter(d => d !== day)
        : [...prev.valid_weekdays, day].sort(),
    }));
  };

  return (
    <div style={{ padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1 style={{ margin: 0 }}>Turnos / Templates</h1>
        <button
          onClick={() => { resetForm(); setShowModal(true); }}
          style={{
            padding: '10px 20px',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontWeight: 'bold',
          }}
        >
          + Novo Template
        </button>
      </div>

      {message && (
        <div
          style={{
            padding: '12px 16px',
            marginBottom: '16px',
            borderRadius: '8px',
            backgroundColor: message.type === 'error' ? '#fee2e2' : '#dcfce7',
            color: message.type === 'error' ? '#991b1b' : '#166534',
          }}
        >
          {message.text}
          <button
            onClick={() => setMessage(null)}
            style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}
          >
            X
          </button>
        </div>
      )}

      <div style={{ display: 'flex', gap: '16px', marginBottom: '20px', alignItems: 'center' }}>
        <div>
          <label style={{ marginRight: '8px' }}>Setor:</label>
          <select
            value={selectedSector || ''}
            onChange={(e) => setSelectedSector(Number(e.target.value))}
            style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid #d1d5db' }}
          >
            <option value="">Todos</option>
            {sectors.map(s => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
          />
          Mostrar inativos
        </label>
      </div>

      {loading ? (
        <p>Carregando...</p>
      ) : templates.length === 0 ? (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: '#f3f4f6',
          borderRadius: '8px',
          color: '#6b7280'
        }}>
          <p>Nenhum template encontrado para este setor.</p>
          <p>Clique em "Novo Template" para criar o primeiro.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gap: '16px', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {templates.map(template => (
            <div
              key={template.id}
              style={{
                padding: '20px',
                backgroundColor: template.is_active ? '#fff' : '#f3f4f6',
                border: '1px solid #e5e7eb',
                borderRadius: '12px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                opacity: template.is_active ? 1 : 0.7,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                <div>
                  <h3 style={{ margin: '0 0 4px 0' }}>{template.name}</h3>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>{template.sector_name}</span>
                </div>
                <span
                  style={{
                    padding: '4px 8px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    backgroundColor: template.is_active ? '#dcfce7' : '#fee2e2',
                    color: template.is_active ? '#166534' : '#991b1b',
                  }}
                >
                  {template.is_active ? 'Ativo' : 'Inativo'}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '12px' }}>
                <div>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>Horario</span>
                  <div style={{ fontWeight: 'bold' }}>{template.start_time} - {template.end_time}</div>
                </div>
                <div>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>Carga Horaria</span>
                  <div style={{ fontWeight: 'bold' }}>{template.calculated_hours}h</div>
                </div>
                <div>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>Intervalo</span>
                  <div style={{ fontWeight: 'bold' }}>{template.break_minutes} min</div>
                </div>
                <div>
                  <span style={{ fontSize: '12px', color: '#6b7280' }}>Limites</span>
                  <div style={{ fontWeight: 'bold' }}>{template.min_hours}h - {template.max_hours}h</div>
                </div>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <span style={{ fontSize: '12px', color: '#6b7280' }}>Dias validos</span>
                <div style={{ display: 'flex', gap: '4px', marginTop: '4px' }}>
                  {[0, 1, 2, 3, 4, 5, 6].map(day => (
                    <span
                      key={day}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 'bold',
                        backgroundColor: template.valid_weekdays.includes(day) ? '#3b82f6' : '#e5e7eb',
                        color: template.valid_weekdays.includes(day) ? '#fff' : '#9ca3af',
                      }}
                    >
                      {WEEKDAY_LABELS[day]}
                    </span>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => handleEdit(template)}
                  style={{
                    flex: 1,
                    padding: '8px',
                    backgroundColor: '#f3f4f6',
                    border: '1px solid #d1d5db',
                    borderRadius: '6px',
                    cursor: 'pointer',
                  }}
                >
                  Editar
                </button>
                <button
                  onClick={() => handleToggleActive(template)}
                  style={{
                    flex: 1,
                    padding: '8px',
                    backgroundColor: template.is_active ? '#fee2e2' : '#dcfce7',
                    color: template.is_active ? '#991b1b' : '#166534',
                    border: 'none',
                    borderRadius: '6px',
                    cursor: 'pointer',
                  }}
                >
                  {template.is_active ? 'Desativar' : 'Ativar'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
        }}>
          <div style={{
            backgroundColor: '#fff',
            padding: '24px',
            borderRadius: '12px',
            width: '100%',
            maxWidth: '500px',
            maxHeight: '90vh',
            overflow: 'auto',
          }}>
            <h2 style={{ marginTop: 0 }}>{editingTemplate ? 'Editar Template' : 'Novo Template'}</h2>

            <form onSubmit={handleSubmit}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Nome</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  required
                  placeholder="Ex: Camareira Manha"
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Inicio</label>
                  <input
                    type="time"
                    value={form.start_time}
                    onChange={(e) => setForm({ ...form, start_time: e.target.value })}
                    required
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Fim</label>
                  <input
                    type="time"
                    value={form.end_time}
                    onChange={(e) => setForm({ ...form, end_time: e.target.value })}
                    required
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Intervalo (minutos)</label>
                <input
                  type="number"
                  value={form.break_minutes}
                  onChange={(e) => setForm({ ...form, break_minutes: parseInt(e.target.value) || 0 })}
                  min={0}
                  max={120}
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                <div>
                  <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Min. Horas</label>
                  <input
                    type="number"
                    value={form.min_hours}
                    onChange={(e) => setForm({ ...form, min_hours: parseInt(e.target.value) || 0 })}
                    min={1}
                    max={12}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', marginBottom: '4px', fontWeight: 'bold' }}>Max. Horas</label>
                  <input
                    type="number"
                    value={form.max_hours}
                    onChange={(e) => setForm({ ...form, max_hours: parseInt(e.target.value) || 0 })}
                    min={1}
                    max={12}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #d1d5db' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold' }}>Dias Validos</label>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  {[0, 1, 2, 3, 4, 5, 6].map(day => (
                    <button
                      type="button"
                      key={day}
                      onClick={() => toggleWeekday(day)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: 'none',
                        cursor: 'pointer',
                        backgroundColor: form.valid_weekdays.includes(day) ? '#3b82f6' : '#e5e7eb',
                        color: form.valid_weekdays.includes(day) ? '#fff' : '#374151',
                        fontWeight: 'bold',
                      }}
                    >
                      {WEEKDAY_LABELS[day]}
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  type="button"
                  onClick={() => { setShowModal(false); resetForm(); }}
                  style={{
                    flex: 1,
                    padding: '12px',
                    backgroundColor: '#f3f4f6',
                    border: '1px solid #d1d5db',
                    borderRadius: '8px',
                    cursor: 'pointer',
                  }}
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  style={{
                    flex: 1,
                    padding: '12px',
                    backgroundColor: '#3b82f6',
                    color: 'white',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 'bold',
                  }}
                >
                  {editingTemplate ? 'Salvar' : 'Criar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default ShiftTemplatesPage;
