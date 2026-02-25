import { useState, useEffect } from 'react';
import { calendarApi, sectorsApi, CalendarEvent, CalendarEventCreate, Sector, HolidayType, CalendarScope } from '../services/client';

const HOLIDAY_TYPES: { value: HolidayType; label: string }[] = [
  { value: 'NATIONAL', label: 'Nacional' },
  { value: 'STATE', label: 'Estadual' },
  { value: 'MUNICIPAL', label: 'Municipal' },
  { value: 'INTERNAL', label: 'Interno' },
];

const WEEKDAYS_ISO = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sab', 'Dom'];
const WEEKDAYS_FULL = ['Segunda-feira', 'Terca-feira', 'Quarta-feira', 'Quinta-feira', 'Sexta-feira', 'Sabado', 'Domingo'];

function getISOWeekNumber(date: Date): number {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
}

function getWeeksInYear(year: number): number {
  const dec31 = new Date(year, 11, 31);
  const week = getISOWeekNumber(dec31);
  return week === 1 ? 52 : week;
}

function getDateFromISOWeek(year: number, week: number, dayOfWeek: number): Date {
  const jan4 = new Date(year, 0, 4);
  const jan4DayOfWeek = jan4.getDay() || 7;
  const mondayOfWeek1 = new Date(jan4);
  mondayOfWeek1.setDate(jan4.getDate() - jan4DayOfWeek + 1);
  const targetDate = new Date(mondayOfWeek1);
  targetDate.setDate(mondayOfWeek1.getDate() + (week - 1) * 7 + (dayOfWeek - 1));
  return targetDate;
}

function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingEvent, setEditingEvent] = useState<CalendarEvent | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [viewMode, setViewMode] = useState<'calendar' | 'list'>('calendar');
  
  const today = new Date();
  const [selectedYear, setSelectedYear] = useState(today.getFullYear());
  const [selectedWeekStart, setSelectedWeekStart] = useState(1);
  const [selectedWeekEnd, setSelectedWeekEnd] = useState(Math.min(12, getWeeksInYear(today.getFullYear())));
  const [filterSector, setFilterSector] = useState<number | null>(null);
  const [filterType, setFilterType] = useState<HolidayType | null>(null);

  const [form, setForm] = useState<CalendarEventCreate>({
    date: '',
    name: '',
    holiday_type: 'NATIONAL',
    scope: 'GLOBAL',
    sector_id: null,
    productivity_factor: 1.0,
    demand_factor: 1.0,
    block_convocations: false,
    notes: '',
  });

  useEffect(() => {
    loadSectors();
  }, []);

  useEffect(() => {
    loadEvents();
  }, [selectedYear, selectedWeekStart, selectedWeekEnd, filterSector, filterType]);

  const loadSectors = async () => {
    try {
      const res = await sectorsApi.list();
      setSectors(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar setores' });
    }
  };

  const loadEvents = async () => {
    try {
      setLoading(true);
      const startDate = getDateFromISOWeek(selectedYear, selectedWeekStart, 1);
      const endDate = getDateFromISOWeek(selectedYear, selectedWeekEnd, 7);
      
      const params: Record<string, number | string | undefined> = {
        year: selectedYear,
        start_date: startDate.toISOString().split('T')[0],
        end_date: endDate.toISOString().split('T')[0],
      };
      if (filterSector) params.sector_id = filterSector;
      if (filterType) params.holiday_type = filterType;
      
      const res = await calendarApi.list(params);
      setEvents(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar eventos do calendario' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (form.scope === 'SECTOR' && !form.sector_id) {
      setMessage({ type: 'error', text: 'Setor e obrigatorio quando escopo e por setor' });
      return;
    }

    try {
      const submitData = {
        ...form,
        sector_id: form.scope === 'GLOBAL' ? null : form.sector_id,
      };

      if (editingEvent) {
        await calendarApi.update(editingEvent.id, submitData);
        setMessage({ type: 'success', text: 'Evento atualizado!' });
      } else {
        await calendarApi.create(submitData);
        setMessage({ type: 'success', text: 'Evento cadastrado!' });
      }
      setShowModal(false);
      resetForm();
      loadEvents();
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      setMessage({ type: 'error', text: err.response?.data?.detail || 'Erro ao salvar evento' });
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir este evento?')) return;
    
    try {
      await calendarApi.delete(id);
      setMessage({ type: 'success', text: 'Evento excluido!' });
      loadEvents();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao excluir evento' });
    }
  };

  const resetForm = () => {
    setForm({
      date: '',
      name: '',
      holiday_type: 'NATIONAL',
      scope: 'GLOBAL',
      sector_id: null,
      productivity_factor: 1.0,
      demand_factor: 1.0,
      block_convocations: false,
      notes: '',
    });
    setEditingEvent(null);
  };

  const openEditModal = (event: CalendarEvent) => {
    setEditingEvent(event);
    setForm({
      date: event.date,
      name: event.name,
      holiday_type: event.holiday_type,
      scope: event.scope,
      sector_id: event.sector_id,
      productivity_factor: event.productivity_factor,
      demand_factor: event.demand_factor,
      block_convocations: event.block_convocations,
      notes: event.notes || '',
    });
    setShowModal(true);
  };

  const openNewModal = (date?: string) => {
    resetForm();
    if (date) {
      setForm(prev => ({ ...prev, date }));
    }
    setShowModal(true);
  };

  const getEventsForDate = (dateStr: string) => {
    return events.filter(e => e.date === dateStr);
  };

  const getTypeColor = (type: HolidayType) => {
    switch (type) {
      case 'NATIONAL': return '#dc3545';
      case 'STATE': return '#fd7e14';
      case 'MUNICIPAL': return '#198754';
      case 'INTERNAL': return '#0d6efd';
      default: return '#6c757d';
    }
  };

  const getTypeLabel = (type: HolidayType) => {
    return HOLIDAY_TYPES.find(t => t.value === type)?.label || type;
  };

  const formatDateBR = (dateStr: string) => {
    const [, m, d] = dateStr.split('-');
    return `${d}/${m}`;
  };

  const renderWeeklyCalendarView = () => {
    const weeks: { weekNum: number; days: { date: Date; dateStr: string }[] }[] = [];
    const totalWeeks = getWeeksInYear(selectedYear);
    
    for (let week = selectedWeekStart; week <= Math.min(selectedWeekEnd, totalWeeks); week++) {
      const weekDays: { date: Date; dateStr: string }[] = [];
      for (let dayOfWeek = 1; dayOfWeek <= 7; dayOfWeek++) {
        const date = getDateFromISOWeek(selectedYear, week, dayOfWeek);
        const dateStr = date.toISOString().split('T')[0];
        weekDays.push({ date, dateStr });
      }
      weeks.push({ weekNum: week, days: weekDays });
    }

    const todayStr = new Date().toISOString().split('T')[0];

    return (
      <div className="calendar-grid-weekly">
        <table className="weekly-calendar-table">
          <thead>
            <tr>
              <th className="week-num-header">Semana</th>
              {WEEKDAYS_ISO.map((day, idx) => (
                <th key={day} className="weekday-header">
                  <div className="weekday-name">{day}</div>
                  <div className="weekday-full">{WEEKDAYS_FULL[idx]}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map(week => (
              <tr key={week.weekNum} className="week-row">
                <td className="week-num-cell">
                  <span className="week-number">{week.weekNum}</span>
                </td>
                {week.days.map((day, idx) => {
                  const dayEvents = getEventsForDate(day.dateStr);
                  const isToday = day.dateStr === todayStr;
                  const isWeekend = idx >= 5;
                  const isSunday = idx === 6;
                  
                  return (
                    <td 
                      key={day.dateStr} 
                      className={`day-cell ${isToday ? 'today' : ''} ${isWeekend ? 'weekend' : ''} ${isSunday ? 'sunday' : ''} ${dayEvents.length > 0 ? 'has-events' : ''}`}
                      onClick={() => openNewModal(day.dateStr)}
                    >
                      <div className="day-header">
                        <span className={`day-number ${isToday ? 'today-number' : ''}`}>
                          {formatDateBR(day.dateStr)}
                        </span>
                      </div>
                      <div className="day-events">
                        {dayEvents.slice(0, 2).map(event => (
                          <div 
                            key={event.id} 
                            className="day-event"
                            style={{ backgroundColor: getTypeColor(event.holiday_type) }}
                            onClick={(e) => {
                              e.stopPropagation();
                              openEditModal(event);
                            }}
                            title={`${event.name}${event.scope === 'SECTOR' ? ` (${event.sector_name})` : ''}`}
                          >
                            {event.name.substring(0, 10)}{event.name.length > 10 ? '..' : ''}
                          </div>
                        ))}
                        {dayEvents.length > 2 && (
                          <div className="day-event more">+{dayEvents.length - 2}</div>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const renderListView = () => {
    const sortedEvents = [...events].sort((a, b) => a.date.localeCompare(b.date));

    const eventsWithWeek = sortedEvents.map(event => {
      const eventDate = new Date(event.date + 'T12:00:00');
      return {
        ...event,
        weekNum: getISOWeekNumber(eventDate),
        weekDay: WEEKDAYS_FULL[(eventDate.getDay() + 6) % 7],
      };
    });

    return (
      <table className="data-table">
        <thead>
          <tr>
            <th>Semana</th>
            <th>Dia</th>
            <th>Data</th>
            <th>Nome</th>
            <th>Tipo</th>
            <th>Escopo</th>
            <th>Fator Prod.</th>
            <th>Fator Dem.</th>
            <th>Bloqueia</th>
            <th>Acoes</th>
          </tr>
        </thead>
        <tbody>
          {eventsWithWeek.length === 0 ? (
            <tr>
              <td colSpan={10} style={{ textAlign: 'center', padding: '2rem' }}>
                Nenhum evento encontrado para este periodo
              </td>
            </tr>
          ) : (
            eventsWithWeek.map(event => (
              <tr key={event.id}>
                <td className="week-num-col">{event.weekNum}</td>
                <td>{event.weekDay}</td>
                <td>{new Date(event.date + 'T12:00:00').toLocaleDateString('pt-BR')}</td>
                <td>{event.name}</td>
                <td>
                  <span className="badge" style={{ backgroundColor: getTypeColor(event.holiday_type) }}>
                    {getTypeLabel(event.holiday_type)}
                  </span>
                </td>
                <td>
                  {event.scope === 'GLOBAL' ? 'Global' : event.sector_name || 'Setor'}
                </td>
                <td>{(event.productivity_factor * 100).toFixed(0)}%</td>
                <td>{(event.demand_factor * 100).toFixed(0)}%</td>
                <td>{event.block_convocations ? 'Sim' : 'Nao'}</td>
                <td>
                  <button className="btn btn-sm btn-secondary" onClick={() => openEditModal(event)}>
                    Editar
                  </button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(event.id)} style={{ marginLeft: '0.5rem' }}>
                    Excluir
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    );
  };

  const totalWeeks = getWeeksInYear(selectedYear);
  const weekOptions = Array.from({ length: totalWeeks }, (_, i) => i + 1);

  return (
    <div className="page-container">
      <div className="page-header">
        <h1>Calendario Operacional (ISO-8601)</h1>
        <button className="btn btn-primary" onClick={() => openNewModal()}>
          + Novo Evento
        </button>
      </div>

      <div className="iso-info-banner">
        <strong>Padrao ISO-8601:</strong> Semanas 1-52 | Ordem: Segunda → Domingo
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)}>&times;</button>
        </div>
      )}

      <div className="card">
        <div className="calendar-controls">
          <div className="control-group">
            <label>Ano:</label>
            <select value={selectedYear} onChange={e => setSelectedYear(Number(e.target.value))}>
              {[2024, 2025, 2026, 2027].map(y => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label>Semana Inicio:</label>
            <select value={selectedWeekStart} onChange={e => setSelectedWeekStart(Number(e.target.value))}>
              {weekOptions.map(w => (
                <option key={w} value={w}>Semana {w}</option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label>Semana Fim:</label>
            <select value={selectedWeekEnd} onChange={e => setSelectedWeekEnd(Number(e.target.value))}>
              {weekOptions.filter(w => w >= selectedWeekStart).map(w => (
                <option key={w} value={w}>Semana {w}</option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label>Setor:</label>
            <select value={filterSector || ''} onChange={e => setFilterSector(e.target.value ? Number(e.target.value) : null)}>
              <option value="">Todos</option>
              {sectors.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div className="control-group">
            <label>Tipo:</label>
            <select value={filterType || ''} onChange={e => setFilterType(e.target.value as HolidayType || null)}>
              <option value="">Todos</option>
              {HOLIDAY_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="control-group view-toggle">
            <button 
              className={`btn ${viewMode === 'calendar' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setViewMode('calendar')}
            >
              Semanal
            </button>
            <button 
              className={`btn ${viewMode === 'list' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setViewMode('list')}
            >
              Lista
            </button>
          </div>
        </div>

        <div className="calendar-legend">
          {HOLIDAY_TYPES.map(t => (
            <span key={t.value} className="legend-item">
              <span className="legend-color" style={{ backgroundColor: getTypeColor(t.value) }}></span>
              {t.label}
            </span>
          ))}
        </div>

        {loading ? (
          <div className="loading">Carregando...</div>
        ) : viewMode === 'calendar' ? (
          renderWeeklyCalendarView()
        ) : (
          renderListView()
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{editingEvent ? 'Editar Evento' : 'Novo Evento'}</h2>
              <button className="close-btn" onClick={() => setShowModal(false)}>&times;</button>
            </div>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label>Data *</label>
                  <input
                    type="date"
                    value={form.date}
                    onChange={e => setForm({ ...form, date: e.target.value })}
                    required
                  />
                  {form.date && (
                    <span className="week-hint">
                      Semana {getISOWeekNumber(new Date(form.date + 'T12:00:00'))} - {WEEKDAYS_FULL[(new Date(form.date + 'T12:00:00').getDay() + 6) % 7]}
                    </span>
                  )}
                </div>
                <div className="form-group">
                  <label>Nome *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={e => setForm({ ...form, name: e.target.value })}
                    placeholder="Ex: Natal, Dia da Consciencia Negra"
                    required
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Tipo de Feriado *</label>
                  <select
                    value={form.holiday_type}
                    onChange={e => setForm({ ...form, holiday_type: e.target.value as HolidayType })}
                  >
                    {HOLIDAY_TYPES.map(t => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Escopo *</label>
                  <select
                    value={form.scope}
                    onChange={e => setForm({ ...form, scope: e.target.value as CalendarScope, sector_id: e.target.value === 'GLOBAL' ? null : form.sector_id })}
                  >
                    <option value="GLOBAL">Global (todos setores)</option>
                    <option value="SECTOR">Especifico por Setor</option>
                  </select>
                </div>
              </div>

              {form.scope === 'SECTOR' && (
                <div className="form-group">
                  <label>Setor *</label>
                  <select
                    value={form.sector_id || ''}
                    onChange={e => setForm({ ...form, sector_id: Number(e.target.value) || null })}
                    required
                  >
                    <option value="">Selecione...</option>
                    {sectors.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
              )}

              <div className="form-row">
                <div className="form-group">
                  <label>Fator de Produtividade</label>
                  <div className="input-with-hint">
                    <input
                      type="number"
                      step="0.05"
                      min="0.1"
                      max="2"
                      value={form.productivity_factor}
                      onChange={e => setForm({ ...form, productivity_factor: parseFloat(e.target.value) })}
                    />
                    <span className="hint">
                      {(form.productivity_factor ?? 1) < 1 ? `${((1 - (form.productivity_factor ?? 1)) * 100).toFixed(0)}% menos produtivo` : 
                       (form.productivity_factor ?? 1) > 1 ? `${(((form.productivity_factor ?? 1) - 1) * 100).toFixed(0)}% mais produtivo` : 'Normal'}
                    </span>
                  </div>
                </div>
                <div className="form-group">
                  <label>Fator de Demanda</label>
                  <div className="input-with-hint">
                    <input
                      type="number"
                      step="0.05"
                      min="0.1"
                      max="2"
                      value={form.demand_factor}
                      onChange={e => setForm({ ...form, demand_factor: parseFloat(e.target.value) })}
                    />
                    <span className="hint">
                      {(form.demand_factor ?? 1) > 1 ? `+${(((form.demand_factor ?? 1) - 1) * 100).toFixed(0)}% demanda` :
                       (form.demand_factor ?? 1) < 1 ? `${((1 - (form.demand_factor ?? 1)) * 100).toFixed(0)}% menos demanda` : 'Normal'}
                    </span>
                  </div>
                </div>
              </div>

              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={form.block_convocations}
                    onChange={e => setForm({ ...form, block_convocations: e.target.checked })}
                  />
                  Bloquear convocacoes neste dia
                </label>
              </div>

              <div className="form-group">
                <label>Observacoes</label>
                <textarea
                  value={form.notes || ''}
                  onChange={e => setForm({ ...form, notes: e.target.value })}
                  placeholder="Anotacoes adicionais..."
                  rows={3}
                />
              </div>

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary">
                  {editingEvent ? 'Salvar' : 'Cadastrar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <style>{`
        .iso-info-banner {
          background: #e7f5ff;
          border: 1px solid #74c0fc;
          border-radius: 6px;
          padding: 0.75rem 1rem;
          margin-bottom: 1rem;
          color: #1864ab;
          font-size: 0.875rem;
        }
        .calendar-controls {
          display: flex;
          gap: 1rem;
          flex-wrap: wrap;
          margin-bottom: 1rem;
          padding: 1rem;
          background: #f8f9fa;
          border-radius: 8px;
        }
        .control-group {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }
        .control-group label {
          font-weight: 500;
          white-space: nowrap;
        }
        .control-group select {
          padding: 0.5rem;
          border: 1px solid #ddd;
          border-radius: 4px;
        }
        .view-toggle {
          margin-left: auto;
        }
        .view-toggle .btn {
          padding: 0.5rem 1rem;
        }
        .calendar-legend {
          display: flex;
          gap: 1.5rem;
          margin-bottom: 1rem;
          padding: 0.5rem 1rem;
        }
        .legend-item {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          font-size: 0.875rem;
        }
        .legend-color {
          width: 12px;
          height: 12px;
          border-radius: 2px;
        }
        .calendar-grid-weekly {
          overflow-x: auto;
        }
        .weekly-calendar-table {
          width: 100%;
          border-collapse: collapse;
          table-layout: fixed;
        }
        .weekly-calendar-table th,
        .weekly-calendar-table td {
          border: 1px solid #ddd;
          padding: 0.5rem;
          vertical-align: top;
        }
        .week-num-header {
          width: 80px;
          background: #1a365d;
          color: white;
          text-align: center;
          font-weight: 600;
        }
        .weekday-header {
          background: #1e3a5f;
          color: white;
          text-align: center;
          padding: 0.5rem;
        }
        .weekday-name {
          font-weight: 600;
          font-size: 0.9rem;
        }
        .weekday-full {
          font-size: 0.7rem;
          opacity: 0.8;
        }
        .week-num-cell {
          background: #f1f3f4;
          text-align: center;
          vertical-align: middle;
        }
        .week-number {
          font-weight: 700;
          font-size: 1.1rem;
          color: #1a365d;
        }
        .day-cell {
          min-height: 80px;
          cursor: pointer;
          transition: background-color 0.2s;
        }
        .day-cell:hover {
          background-color: #f0f7ff;
        }
        .day-cell.weekend {
          background-color: #f8f9fa;
        }
        .day-cell.sunday {
          background-color: #fff5f5;
        }
        .day-cell.today {
          background-color: #e7f5ff;
        }
        .day-cell.has-events {
          background-color: #fff3cd;
        }
        .day-cell.sunday.has-events {
          background-color: #ffe8cc;
        }
        .day-header {
          margin-bottom: 0.25rem;
        }
        .day-number {
          font-size: 0.8rem;
          color: #666;
        }
        .day-number.today-number {
          background: #1e3a5f;
          color: white;
          padding: 2px 6px;
          border-radius: 4px;
          font-weight: 600;
        }
        .day-events {
          display: flex;
          flex-direction: column;
          gap: 2px;
        }
        .day-event {
          font-size: 0.7rem;
          padding: 2px 4px;
          border-radius: 3px;
          color: white;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          cursor: pointer;
        }
        .day-event:hover {
          opacity: 0.9;
        }
        .day-event.more {
          background: #6c757d;
          text-align: center;
        }
        .week-num-col {
          font-weight: 600;
          text-align: center;
          color: #1a365d;
        }
        .week-hint {
          font-size: 0.75rem;
          color: #1864ab;
          margin-top: 0.25rem;
          display: block;
        }
        .input-with-hint {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }
        .input-with-hint input {
          width: 100%;
        }
        .hint {
          font-size: 0.75rem;
          color: #666;
        }
        .checkbox-label {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          cursor: pointer;
        }
        .checkbox-label input[type="checkbox"] {
          width: auto;
        }
        .badge {
          display: inline-block;
          padding: 0.25rem 0.5rem;
          border-radius: 4px;
          color: white;
          font-size: 0.75rem;
        }
      `}</style>
    </div>
  );
}

export default CalendarPage;
