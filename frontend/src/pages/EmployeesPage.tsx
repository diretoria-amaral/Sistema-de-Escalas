import { useState, useEffect } from 'react';
import { employeesApi, sectorsApi, rolesApi, Employee, Sector, Role } from '../services/client';

function EmployeesPage() {
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [filterSector, setFilterSector] = useState<number | ''>('');

  const [form, setForm] = useState({
    name: '',
    cpf: '',
    email: '',
    phone: '',
    sector_id: '',
    role_id: '',
    cbo_code: '',
    contract_type: 'intermitente' as 'intermitente' | 'efetivo',
    work_regime: '',
    monthly_hours_target: 176,
    restrictions: '',
    unavailable_days: '',
  });

  useEffect(() => {
    loadData();
  }, [filterSector]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [empRes, secRes, roleRes] = await Promise.all([
        employeesApi.list(filterSector ? { sector_id: filterSector } : undefined),
        sectorsApi.list(),
        rolesApi.list(),
      ]);
      setEmployees(empRes.data);
      setSectors(secRes.data);
      setRoles(roleRes.data);
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao carregar dados' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const payload = {
        ...form,
        sector_id: Number(form.sector_id),
        role_id: Number(form.role_id),
        restrictions: form.restrictions ? form.restrictions.split(',').map(s => s.trim()) : [],
        unavailable_days: form.unavailable_days ? form.unavailable_days.split(',').map(s => s.trim()) : [],
        work_regime: form.work_regime || undefined,
      };

      if (editingEmployee) {
        await employeesApi.update(editingEmployee.id, payload);
        setMessage({ type: 'success', text: 'Colaborador atualizado com sucesso!' });
      } else {
        await employeesApi.create(payload);
        setMessage({ type: 'success', text: 'Colaborador cadastrado com sucesso!' });
      }
      setShowModal(false);
      resetForm();
      loadData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao salvar colaborador' });
    }
  };

  const handleEdit = (employee: Employee) => {
    setEditingEmployee(employee);
    setForm({
      name: employee.name,
      cpf: employee.cpf || '',
      email: employee.email || '',
      phone: employee.phone || '',
      sector_id: String(employee.sector_id),
      role_id: String(employee.role_id),
      cbo_code: employee.cbo_code || '',
      contract_type: employee.contract_type,
      work_regime: employee.work_regime || '',
      monthly_hours_target: employee.monthly_hours_target,
      restrictions: employee.restrictions?.join(', ') || '',
      unavailable_days: employee.unavailable_days?.join(', ') || '',
    });
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Tem certeza que deseja excluir este colaborador?')) return;
    try {
      await employeesApi.delete(id);
      setMessage({ type: 'success', text: 'Colaborador excluido!' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao excluir colaborador' });
    }
  };

  const resetForm = () => {
    setEditingEmployee(null);
    setForm({
      name: '',
      cpf: '',
      email: '',
      phone: '',
      sector_id: '',
      role_id: '',
      cbo_code: '',
      contract_type: 'intermitente',
      work_regime: '',
      monthly_hours_target: 176,
      restrictions: '',
      unavailable_days: '',
    });
  };

  const filteredRoles = form.sector_id 
    ? roles.filter(r => r.sector_id === Number(form.sector_id))
    : roles;

  return (
    <div>
      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
          <h2>Colaboradores</h2>
          <div style={{ display: 'flex', gap: 10 }}>
            <select 
              value={filterSector} 
              onChange={e => setFilterSector(e.target.value ? Number(e.target.value) : '')}
              style={{ padding: '8px 12px', borderRadius: 6, border: '1px solid #ddd' }}
            >
              <option value="">Todos os setores</option>
              {sectors.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }}>
              + Novo Colaborador
            </button>
          </div>
        </div>

        {loading ? (
          <div className="loading">Carregando...</div>
        ) : employees.length === 0 ? (
          <div className="empty-state">Nenhum colaborador cadastrado</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Setor</th>
                <th>Cargo</th>
                <th>Vinculo</th>
                <th>Acoes</th>
              </tr>
            </thead>
            <tbody>
              {employees.map(emp => (
                <tr key={emp.id}>
                  <td>{emp.name}</td>
                  <td>{emp.sector_name}</td>
                  <td>{emp.role_name}</td>
                  <td>
                    <span className={`badge ${emp.contract_type === 'intermitente' ? 'badge-warning' : 'badge-success'}`}>
                      {emp.contract_type === 'intermitente' ? 'Intermitente' : 'Efetivo'}
                    </span>
                  </td>
                  <td className="actions">
                    <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(emp)}>Editar</button>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(emp.id)}>Excluir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>{editingEmployee ? 'Editar Colaborador' : 'Novo Colaborador'}</h3>
            <form onSubmit={handleSubmit}>
              <div className="form-row">
                <div className="form-group">
                  <label>Nome *</label>
                  <input 
                    type="text" 
                    value={form.name} 
                    onChange={e => setForm({...form, name: e.target.value})}
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>CPF</label>
                  <input 
                    type="text" 
                    value={form.cpf} 
                    onChange={e => setForm({...form, cpf: e.target.value})}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Email</label>
                  <input 
                    type="email" 
                    value={form.email} 
                    onChange={e => setForm({...form, email: e.target.value})}
                  />
                </div>
                <div className="form-group">
                  <label>Telefone</label>
                  <input 
                    type="text" 
                    value={form.phone} 
                    onChange={e => setForm({...form, phone: e.target.value})}
                  />
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Setor *</label>
                  <select 
                    value={form.sector_id} 
                    onChange={e => setForm({...form, sector_id: e.target.value, role_id: ''})}
                    required
                  >
                    <option value="">Selecione...</option>
                    {sectors.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div className="form-group">
                  <label>Cargo *</label>
                  <select 
                    value={form.role_id} 
                    onChange={e => setForm({...form, role_id: e.target.value})}
                    required
                    disabled={!form.sector_id}
                  >
                    <option value="">Selecione...</option>
                    {filteredRoles.map(r => (
                      <option key={r.id} value={r.id}>{r.name}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Tipo de Vinculo *</label>
                  <select 
                    value={form.contract_type} 
                    onChange={e => setForm({...form, contract_type: e.target.value as 'intermitente' | 'efetivo'})}
                  >
                    <option value="intermitente">Intermitente</option>
                    <option value="efetivo">Efetivo</option>
                  </select>
                </div>
                <div className="form-group">
                  <label>Regime de Trabalho</label>
                  <select 
                    value={form.work_regime} 
                    onChange={e => setForm({...form, work_regime: e.target.value})}
                  >
                    <option value="">Selecione...</option>
                    <option value="5x2">5x2</option>
                    <option value="6x1">6x1</option>
                    <option value="12x36">12x36</option>
                    <option value="flexivel">Flexivel</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>CBO</label>
                  <input 
                    type="text" 
                    value={form.cbo_code} 
                    onChange={e => setForm({...form, cbo_code: e.target.value})}
                  />
                </div>
                <div className="form-group">
                  <label>Horas Mensais Alvo</label>
                  <input 
                    type="number" 
                    value={form.monthly_hours_target} 
                    onChange={e => setForm({...form, monthly_hours_target: Number(e.target.value)})}
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Restricoes (separadas por virgula)</label>
                <textarea 
                  value={form.restrictions} 
                  onChange={e => setForm({...form, restrictions: e.target.value})}
                  placeholder="Ex: nao trabalha a noite, nao pode carga pesada"
                  rows={2}
                />
              </div>

              <div className="form-group">
                <label>Dias Indisponiveis (separados por virgula)</label>
                <input 
                  type="text" 
                  value={form.unavailable_days} 
                  onChange={e => setForm({...form, unavailable_days: e.target.value})}
                  placeholder="Ex: sabado, domingo"
                />
              </div>

              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary">Salvar</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default EmployeesPage;
