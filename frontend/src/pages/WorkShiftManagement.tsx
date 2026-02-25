import { useState, useEffect } from 'react';
import { sectorsApi, Sector } from '../services/client';
import { workShiftsApi, WorkShift, WorkShiftDayRule, ShiftTimeConstraint } from '../services/workShifts';

const WEEKDAYS = [
  { value: 1, label: 'Segunda' },
  { value: 2, label: 'Terça' },
  { value: 3, label: 'Quarta' },
  { value: 4, label: 'Quinta' },
  { value: 5, label: 'Sexta' },
  { value: 6, label: 'Sábado' },
  { value: 7, label: 'Domingo' },
];

export default function WorkShiftManagement() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [shifts, setShifts] = useState<WorkShift[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [editingShift, setEditingShift] = useState<WorkShift | null>(null);
  const [name, setName] = useState('');
  const [showInactive, setShowInactive] = useState(false);
  const [dayRules, setDayRules] = useState<Partial<WorkShiftDayRule>[]>(
    WEEKDAYS.map(w => ({
      weekday: w.value,
      start_time: '',
      break_out_time: '',
      break_in_time: '',
      end_time: '',
      start_constraint: 'FLEXIBLE' as ShiftTimeConstraint,
      end_constraint: 'FLEXIBLE' as ShiftTimeConstraint
    }))
  );

  const copyFirstDayToAll = () => {
    const firstDay = dayRules[0];
    setDayRules(WEEKDAYS.map(w => ({
      ...firstDay,
      weekday: w.value
    })));
  };

  const clearDay = (index: number) => {
    const newRules = [...dayRules];
    newRules[index] = {
      weekday: WEEKDAYS[index].value,
      start_time: '',
      break_out_time: '',
      break_in_time: '',
      end_time: '',
      start_constraint: 'FLEXIBLE',
      end_constraint: 'FLEXIBLE'
    };
    setDayRules(newRules);
  };

  const clearAllDays = () => {
    setDayRules(WEEKDAYS.map(w => ({
      weekday: w.value,
      start_time: '',
      break_out_time: '',
      break_in_time: '',
      end_time: '',
      start_constraint: 'FLEXIBLE',
      end_constraint: 'FLEXIBLE'
    })));
  };

  useEffect(() => {
    sectorsApi.list().then(res => {
      setSectors(res.data);
      if (res.data.length > 0) setSelectedSectorId(res.data[0].id);
    });
  }, []);

  useEffect(() => {
    if (selectedSectorId) loadShifts();
  }, [selectedSectorId]);

  const loadShifts = async () => {
    if (!selectedSectorId) return;
    const res = await workShiftsApi.list(selectedSectorId);
    setShifts(res.data);
  };

  const handleOpenCreate = () => {
    setEditingShift(null);
    setName('');
    setDayRules(WEEKDAYS.map(w => ({
      weekday: w.value,
      start_time: '',
      break_out_time: '',
      break_in_time: '',
      end_time: '',
      start_constraint: 'FLEXIBLE',
      end_constraint: 'FLEXIBLE'
    })));
    setShowModal(true);
  };

  const handleEdit = (shift: WorkShift) => {
    setEditingShift(shift);
    setName(shift.name);
    const rules = WEEKDAYS.map(w => {
      const existing = shift.day_rules.find(r => r.weekday === w.value);
      return (existing ? { ...existing } : {
        weekday: w.value,
        start_time: '',
        break_out_time: '',
        break_in_time: '',
        end_time: '',
        start_constraint: 'FLEXIBLE' as ShiftTimeConstraint,
        end_constraint: 'FLEXIBLE' as ShiftTimeConstraint
      }) as Partial<WorkShiftDayRule>;
    });
    setDayRules(rules);
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!selectedSectorId || !name) return;
    const payload = {
      sector_id: selectedSectorId,
      name,
      days: dayRules.map(d => ({
        ...d,
        weekday: d.weekday as number,
        start_time: d.start_time || null,
        break_out_time: d.break_out_time || null,
        break_in_time: d.break_in_time || null,
        end_time: d.end_time || null,
      })) as WorkShiftDayRule[]
    };

    try {
      if (editingShift) {
        await workShiftsApi.update(editingShift.id, payload);
      } else {
        await workShiftsApi.create(payload as any);
      }
      setShowModal(false);
      loadShifts();
    } catch (err: any) {
      alert(err.response?.data?.detail?.[0]?.msg || err.response?.data?.detail || 'Erro ao salvar');
    }
  };

  const handleToggleActive = async (shift: WorkShift) => {
    const confirmMsg = shift.is_active ? 'Deseja realmente desativar este turno?' : 'Deseja reativar este turno?';
    if (!window.confirm(confirmMsg)) return;
    try {
      await workShiftsApi.update(shift.id, { is_active: !shift.is_active });
      loadShifts();
    } catch (err) {
      console.error(err);
      alert('Erro ao alterar status do turno');
    }
  };

  const filteredShifts = shifts.filter(s => showInactive || s.is_active);

  return (
    <div className="p-6 bg-[#f8f9fa] min-h-screen">
      <div className="max-w-[1600px] mx-auto space-y-6">
        {/* Header Section */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 tracking-tight">Turnos de Trabalho</h1>
            <p className="text-gray-500 text-sm mt-1">Gerencie os horários operacionais e restrições por setor</p>
          </div>
          
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 bg-gray-50 px-3 py-2 rounded-xl border border-gray-200">
              <label className="text-xs font-bold text-gray-500 uppercase tracking-wider">Setor:</label>
              <select 
                className="bg-transparent text-sm font-semibold text-gray-700 outline-none min-w-[150px]"
                value={selectedSectorId || ''} 
                onChange={e => setSelectedSectorId(Number(e.target.value))}
              >
                {sectors.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </div>

            <label className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-xl cursor-pointer hover:bg-gray-50 transition-colors shadow-sm">
              <input 
                type="checkbox" 
                checked={showInactive} 
                onChange={e => setShowInactive(e.target.checked)}
                className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 border-gray-300"
              />
              <span className="text-sm font-medium text-gray-600">Mostrar inativos</span>
            </label>

            <button 
              onClick={handleOpenCreate}
              className="flex items-center gap-2 px-5 py-2.5 bg-indigo-600 text-white rounded-xl font-bold text-sm shadow-lg shadow-indigo-100 hover:bg-indigo-700 transition-all active:scale-95"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" /></svg>
              Novo Turno
            </button>
          </div>
        </div>

        {/* Main Grid Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50/50 border-b border-gray-100">
                  <th className="p-4 text-left text-[11px] font-bold text-gray-400 uppercase tracking-widest w-[220px] min-w-[220px]">Turno</th>
                  {WEEKDAYS.map(w => (
                    <th key={w.value} className="p-4 text-center text-[11px] font-bold text-gray-400 uppercase tracking-widest w-[120px] min-w-[120px]">{w.label}</th>
                  ))}
                  <th className="p-4 text-right text-[11px] font-bold text-gray-400 uppercase tracking-widest w-[140px] min-w-[140px]">Ações</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredShifts.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="p-20 text-center">
                      <div className="flex flex-col items-center gap-3">
                        <div className="p-4 bg-gray-50 rounded-full">
                          <svg className="w-8 h-8 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                        </div>
                        <p className="text-gray-400 italic text-sm font-medium">Nenhum turno configurado para este setor</p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  filteredShifts.map(shift => (
                    <tr key={shift.id} className={`group hover:bg-gray-50/80 transition-all ${!shift.is_active ? 'opacity-60 grayscale-[0.5]' : ''}`}>
                      <td className="p-4 align-middle">
                        <div className="flex flex-col gap-1">
                          <span className="font-bold text-gray-800 leading-tight truncate" title={shift.name}>{shift.name}</span>
                          <div className="flex items-center gap-1.5">
                            <span className={`w-2 h-2 rounded-full ${shift.is_active ? 'bg-green-500' : 'bg-gray-300'}`}></span>
                            <span className="text-[10px] font-bold text-gray-400 uppercase tracking-tighter">
                              {shift.is_active ? 'Operacional' : 'Inativo'}
                            </span>
                          </div>
                        </div>
                      </td>
                      {WEEKDAYS.map(w => {
                        const rule = shift.day_rules.find(r => r.weekday === w.value);
                        if (!rule || !rule.start_time) return (
                          <td key={w.value} className="p-4 text-center align-middle">
                            <span className="text-gray-200 font-light opacity-50">—</span>
                          </td>
                        );
                        
                        return (
                          <td key={w.value} className="p-4 text-center align-middle">
                            <div className="inline-flex flex-col items-center justify-center py-1.5 px-2.5 rounded-lg border border-transparent group-hover:border-gray-200 group-hover:bg-white transition-all cursor-default relative" 
                                 title={rule.break_out_time ? `Intervalo: ${rule.break_out_time.slice(0,5)} - ${rule.break_in_time?.slice(0,5)}` : 'Sem intervalo'}>
                              <div className="flex items-center gap-1 font-mono text-[13px] tracking-tight">
                                <span className={rule.start_constraint === 'MANDATORY' ? 'text-indigo-600 font-black' : 'text-gray-600 font-medium'}>
                                  {rule.start_time.slice(0, 5)}
                                </span>
                                <span className="text-gray-300 px-0.5 opacity-60">→</span>
                                <span className={rule.end_constraint === 'MANDATORY' ? 'text-indigo-600 font-black' : 'text-gray-600 font-medium'}>
                                  {rule.end_time?.slice(0, 5)}
                                </span>
                              </div>
                            </div>
                          </td>
                        );
                      })}
                      <td className="p-4 align-middle text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button 
                            onClick={() => handleEdit(shift)} 
                            className="p-2 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all"
                            title="Editar Turno"
                          >
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                          </button>
                          <button 
                            onClick={() => handleToggleActive(shift)} 
                            className={`p-2 rounded-xl transition-all ${shift.is_active ? 'text-gray-400 hover:text-amber-600 hover:bg-amber-50' : 'text-gray-400 hover:text-green-600 hover:bg-green-50'}`}
                            title={shift.is_active ? 'Desativar' : 'Reativar'}
                          >
                            {shift.is_active ? (
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" /></svg>
                            ) : (
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" /></svg>
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 bg-gray-900/60 backdrop-blur-md flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-[2rem] shadow-2xl w-full max-w-6xl max-h-[95vh] flex flex-col overflow-hidden animate-in fade-in zoom-in duration-300">
            {/* Modal Header */}
            <div className="px-10 py-8 border-b border-gray-100 flex justify-between items-start bg-white sticky top-0 z-10">
              <div className="space-y-1">
                <h2 className="text-3xl font-black text-gray-900 tracking-tight">
                  {editingShift ? 'Editar Turno' : 'Novo Turno'}
                </h2>
                <p className="text-gray-500 font-medium">
                  Defina os horários por dia (Seg–Dom) e marque o início/fim como <span className="text-indigo-600 font-bold">Mandatório</span> ou Flexível.
                </p>
              </div>
              <button 
                onClick={() => setShowModal(false)} 
                className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-400"
              >
                <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M6 18L18 6M6 6l12 12" /></svg>
              </button>
            </div>
            
            {/* Modal Content */}
            <div className="px-10 py-8 overflow-y-auto flex-1 bg-gray-50/30">
              <div className="flex flex-col md:flex-row justify-between items-end gap-6 mb-10">
                <div className="flex-1 max-w-md w-full">
                  <label className="block text-xs font-black text-gray-400 uppercase tracking-[0.2em] mb-2 px-1">Nome Identificador</label>
                  <input 
                    className="w-full px-5 py-4 bg-white border border-gray-200 rounded-2xl shadow-sm focus:ring-4 focus:ring-indigo-100 focus:border-indigo-500 outline-none transition-all text-lg font-bold text-gray-800 placeholder:text-gray-300" 
                    value={name} 
                    onChange={e => setName(e.target.value)} 
                    placeholder="Ex: Manhã (08h - 17h)"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <button 
                    onClick={copyFirstDayToAll}
                    className="px-6 py-4 bg-white border border-gray-200 text-gray-700 rounded-2xl hover:border-indigo-200 hover:text-indigo-600 transition-all font-bold text-sm shadow-sm flex items-center gap-2 group"
                  >
                    <svg className="w-5 h-5 group-hover:scale-110 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2h-2M8 7H6a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2v-2" /></svg>
                    Replicar Segunda
                  </button>
                  <button 
                    onClick={clearAllDays}
                    className="px-6 py-4 bg-red-50 text-red-600 rounded-2xl hover:bg-red-100 transition-all font-bold text-sm"
                  >
                    Limpar Todos
                  </button>
                </div>
              </div>

              <div className="bg-white rounded-[2rem] border border-gray-100 shadow-xl shadow-gray-200/50 overflow-hidden">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="bg-gray-900 text-white">
                      <th className="p-5 text-left font-black uppercase tracking-widest text-[10px] opacity-70">Dia</th>
                      <th className="p-5 text-left font-black uppercase tracking-widest text-[10px] opacity-70">Entrada</th>
                      <th className="p-5 text-left font-black uppercase tracking-widest text-[10px] opacity-70">Intervalo (Saída)</th>
                      <th className="p-5 text-left font-black uppercase tracking-widest text-[10px] opacity-70">Intervalo (Retorno)</th>
                      <th className="p-5 text-left font-black uppercase tracking-widest text-[10px] opacity-70">Saída Final</th>
                      <th className="p-5 text-center font-black uppercase tracking-widest text-[10px] opacity-70">Ações</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {dayRules.map((rule, idx) => (
                      <tr key={rule.weekday} className="hover:bg-indigo-50/30 transition-colors">
                        <td className="p-5">
                          <span className="font-black text-gray-900">{WEEKDAYS.find(w => w.value === rule.weekday)?.label}</span>
                        </td>
                        <td className="p-5">
                          <div className="flex flex-col gap-2">
                            <input 
                              type="time" 
                              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-100 rounded-xl font-mono font-bold text-gray-700 focus:bg-white focus:ring-4 focus:ring-indigo-50 transition-all outline-none"
                              value={rule.start_time || ''} 
                              onChange={e => {
                                const newRules = [...dayRules];
                                newRules[idx].start_time = e.target.value;
                                setDayRules(newRules);
                              }}
                            />
                            <div className="flex bg-gray-100 p-1 rounded-lg">
                              {(['FLEXIBLE', 'MANDATORY'] as ShiftTimeConstraint[]).map(type => (
                                <button
                                  key={type}
                                  onClick={() => {
                                    const newRules = [...dayRules];
                                    newRules[idx].start_constraint = type;
                                    setDayRules(newRules);
                                  }}
                                  className={`flex-1 text-[9px] font-black uppercase py-1 rounded-md transition-all ${rule.start_constraint === type ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
                                >
                                  {type === 'MANDATORY' ? 'Mandatório' : 'Flexível'}
                                </button>
                              ))}
                            </div>
                          </div>
                        </td>
                        <td className="p-5">
                          <input 
                            type="time" 
                            className="w-full px-4 py-2.5 bg-gray-50 border border-gray-100 rounded-xl font-mono font-bold text-gray-700 focus:bg-white transition-all outline-none"
                            value={rule.break_out_time || ''} 
                            onChange={e => {
                              const newRules = [...dayRules];
                              newRules[idx].break_out_time = e.target.value;
                              setDayRules(newRules);
                            }}
                          />
                        </td>
                        <td className="p-5">
                          <input 
                            type="time" 
                            className="w-full px-4 py-2.5 bg-gray-50 border border-gray-100 rounded-xl font-mono font-bold text-gray-700 focus:bg-white transition-all outline-none"
                            value={rule.break_in_time || ''} 
                            onChange={e => {
                              const newRules = [...dayRules];
                              newRules[idx].break_in_time = e.target.value;
                              setDayRules(newRules);
                            }}
                          />
                        </td>
                        <td className="p-5">
                          <div className="flex flex-col gap-2">
                            <input 
                              type="time" 
                              className="w-full px-4 py-2.5 bg-gray-50 border border-gray-100 rounded-xl font-mono font-bold text-gray-700 focus:bg-white focus:ring-4 focus:ring-indigo-50 transition-all outline-none"
                              value={rule.end_time || ''} 
                              onChange={e => {
                                const newRules = [...dayRules];
                                newRules[idx].end_time = e.target.value;
                                setDayRules(newRules);
                              }}
                            />
                            <div className="flex bg-gray-100 p-1 rounded-lg">
                              {(['FLEXIBLE', 'MANDATORY'] as ShiftTimeConstraint[]).map(type => (
                                <button
                                  key={type}
                                  onClick={() => {
                                    const newRules = [...dayRules];
                                    newRules[idx].end_constraint = type;
                                    setDayRules(newRules);
                                  }}
                                  className={`flex-1 text-[9px] font-black uppercase py-1 rounded-md transition-all ${rule.end_constraint === type ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-400 hover:text-gray-600'}`}
                                >
                                  {type === 'MANDATORY' ? 'Mandatório' : 'Flexível'}
                                </button>
                              ))}
                            </div>
                          </div>
                        </td>
                        <td className="p-5 text-center">
                          <button 
                            onClick={() => clearDay(idx)}
                            className="p-3 text-gray-300 hover:text-red-500 hover:bg-red-50 rounded-2xl transition-all"
                            title="Limpar Dia"
                          >
                            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-10 py-8 border-t border-gray-100 bg-white flex justify-end gap-4 sticky bottom-0">
              <button 
                onClick={() => setShowModal(false)}
                className="px-10 py-4 border border-gray-200 bg-white rounded-2xl font-bold text-gray-600 hover:bg-gray-50 transition-all active:scale-95"
              >
                Cancelar
              </button>
              <button 
                onClick={handleSave}
                className="px-14 py-4 bg-indigo-600 text-white rounded-2xl font-black shadow-2xl shadow-indigo-200 hover:bg-indigo-700 hover:-translate-y-1 transition-all active:translate-y-0 active:scale-95"
              >
                Salvar Configuração
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
