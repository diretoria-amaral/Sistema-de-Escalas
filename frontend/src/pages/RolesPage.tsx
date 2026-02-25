import { useState, useEffect } from 'react';

interface Sector {
  id: number;
  name: string;
}

interface Role {
  id: number;
  name: string;
  cbo_code: string | null;
  sector_id: number;
  sector: Sector | null;
  employment_type: 'intermitente' | 'efetivo';
  description: string | null;
  is_active: boolean;
  created_at: string;
}

interface RoleForm {
  name: string;
  cbo_code: string;
  sector_id: number | '';
  employment_type: 'intermitente' | 'efetivo';
  description: string;
  is_active: boolean;
}

const initialForm: RoleForm = {
  name: '',
  cbo_code: '',
  sector_id: '',
  employment_type: 'efetivo',
  description: '',
  is_active: true
};

function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingRole, setEditingRole] = useState<Role | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [form, setForm] = useState<RoleForm>(initialForm);
  const [filterSector, setFilterSector] = useState<number | ''>('');
  const [filterActive, setFilterActive] = useState<boolean | ''>('');

  useEffect(() => {
    loadData();
  }, [filterSector, filterActive]);

  const loadData = async () => {
    try {
      setLoading(true);
      
      const [rolesRes, sectorsRes] = await Promise.all([
        fetch(`/api/roles/${filterSector ? `?sector_id=${filterSector}` : ''}${filterActive !== '' ? `${filterSector ? '&' : '?'}is_active=${filterActive}` : ''}`),
        fetch('/api/sectors/')
      ]);
      
      if (!rolesRes.ok) {
        const error = await rolesRes.json();
        throw new Error(error.detail || 'Erro ao carregar funcoes');
      }
      
      if (!sectorsRes.ok) {
        throw new Error('Erro ao carregar setores');
      }
      
      const rolesData = await rolesRes.json();
      const sectorsData = await sectorsRes.json();
      
      setRoles(rolesData);
      setSectors(sectorsData);
    } catch (err) {
      setMessage({ type: 'error', text: err instanceof Error ? err.message : 'Erro ao carregar dados' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!form.name.trim()) {
      setMessage({ type: 'error', text: 'Nome da funcao e obrigatorio' });
      return;
    }
    
    if (!form.sector_id) {
      setMessage({ type: 'error', text: 'Selecione um setor' });
      return;
    }
    
    try {
      const url = editingRole ? `/api/roles/${editingRole.id}` : '/api/roles/';
      const method = editingRole ? 'PUT' : 'POST';
      
      const payload = {
        name: form.name.trim(),
        cbo_code: form.cbo_code.trim() || null,
        sector_id: form.sector_id,
        employment_type: form.employment_type,
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
        setMessage({ type: 'error', text: data.detail || 'Erro ao salvar funcao' });
        return;
      }
      
      setMessage({ type: 'success', text: editingRole ? 'Funcao atualizada com sucesso!' : 'Funcao criada com sucesso!' });
      setShowModal(false);
      resetForm();
      loadData();
    } catch (err) {
      setMessage({ type: 'error', text: 'Erro de conexao ao salvar funcao' });
    }
  };

  const handleEdit = (role: Role) => {
    setEditingRole(role);
    setForm({
      name: role.name,
      cbo_code: role.cbo_code || '',
      sector_id: role.sector_id,
      employment_type: role.employment_type,
      description: role.description || '',
      is_active: role.is_active
    });
    setShowModal(true);
  };

  const handleDelete = async (role: Role) => {
    if (!confirm(`Excluir a funcao "${role.name}"?`)) return;
    
    try {
      const res = await fetch(`/api/roles/${role.id}`, { method: 'DELETE' });
      const data = await res.json();
      
      if (!res.ok) {
        setMessage({ type: 'error', text: data.detail || 'Erro ao excluir' });
        return;
      }
      
      setMessage({ type: 'success', text: 'Funcao excluida com sucesso!' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro de conexao ao excluir' });
    }
  };

  const handleToggleActive = async (role: Role) => {
    try {
      const res = await fetch(`/api/roles/${role.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !role.is_active })
      });
      
      if (!res.ok) {
        const data = await res.json();
        setMessage({ type: 'error', text: data.detail || 'Erro ao atualizar status' });
        return;
      }
      
      setMessage({ type: 'success', text: `Funcao ${role.is_active ? 'desativada' : 'ativada'} com sucesso!` });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao atualizar status' });
    }
  };

  const resetForm = () => {
    setEditingRole(null);
    setForm(initialForm);
  };

  const getSectorName = (role: Role) => {
    if (role.sector) return role.sector.name;
    const sector = sectors.find(s => s.id === role.sector_id);
    return sector ? sector.name : '-';
  };

  return (
    <div>
      {message && (
        <div className={`alert alert-${message.type}`} style={{ marginBottom: 15 }}>
          {message.text}
          <button 
            onClick={() => setMessage(null)} 
            style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontWeight: 'bold' }}
          >
            x
          </button>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15, flexWrap: 'wrap', gap: 10 }}>
          <h2 style={{ margin: 0 }}>Cadastro de Funcoes</h2>
          <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }}>
            + Nova Funcao
          </button>
        </div>

        <div style={{ display: 'flex', gap: 15, marginBottom: 15, flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>Filtrar por Setor:</label>
            <select 
              value={filterSector} 
              onChange={e => setFilterSector(e.target.value ? Number(e.target.value) : '')}
              style={{ padding: '6px 10px', minWidth: 150 }}
            >
              <option value="">Todos os setores</option>
              {sectors.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: 12, marginBottom: 4 }}>Status:</label>
            <select 
              value={filterActive === '' ? '' : filterActive.toString()} 
              onChange={e => setFilterActive(e.target.value === '' ? '' : e.target.value === 'true')}
              style={{ padding: '6px 10px', minWidth: 120 }}
            >
              <option value="">Todos</option>
              <option value="true">Ativos</option>
              <option value="false">Inativos</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="loading" style={{ padding: 40, textAlign: 'center' }}>Carregando...</div>
        ) : roles.length === 0 ? (
          <div className="empty-state" style={{ padding: 40, textAlign: 'center', color: '#666' }}>
            Nenhuma funcao cadastrada
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'left', padding: 10, borderBottom: '2px solid #ddd' }}>Nome</th>
                  <th style={{ textAlign: 'left', padding: 10, borderBottom: '2px solid #ddd' }}>CBO</th>
                  <th style={{ textAlign: 'left', padding: 10, borderBottom: '2px solid #ddd' }}>Setor</th>
                  <th style={{ textAlign: 'left', padding: 10, borderBottom: '2px solid #ddd' }}>Vinculo</th>
                  <th style={{ textAlign: 'center', padding: 10, borderBottom: '2px solid #ddd' }}>Status</th>
                  <th style={{ textAlign: 'center', padding: 10, borderBottom: '2px solid #ddd' }}>Acoes</th>
                </tr>
              </thead>
              <tbody>
                {roles.map(role => (
                  <tr key={role.id} style={{ opacity: role.is_active ? 1 : 0.6 }}>
                    <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>
                      <strong>{role.name}</strong>
                      {role.description && (
                        <div style={{ fontSize: 12, color: '#666', marginTop: 2 }}>{role.description}</div>
                      )}
                    </td>
                    <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>
                      {role.cbo_code ? <code>{role.cbo_code}</code> : '-'}
                    </td>
                    <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>{getSectorName(role)}</td>
                    <td style={{ padding: 10, borderBottom: '1px solid #eee' }}>
                      <span style={{ 
                        padding: '2px 8px', 
                        borderRadius: 4, 
                        fontSize: 12,
                        backgroundColor: role.employment_type === 'intermitente' ? '#fff3cd' : '#d4edda',
                        color: role.employment_type === 'intermitente' ? '#856404' : '#155724'
                      }}>
                        {role.employment_type === 'intermitente' ? 'Intermitente' : 'Efetivo'}
                      </span>
                    </td>
                    <td style={{ padding: 10, borderBottom: '1px solid #eee', textAlign: 'center' }}>
                      <button 
                        onClick={() => handleToggleActive(role)}
                        style={{ 
                          padding: '4px 12px', 
                          border: 'none', 
                          borderRadius: 4,
                          cursor: 'pointer',
                          backgroundColor: role.is_active ? '#28a745' : '#6c757d',
                          color: 'white',
                          fontSize: 12
                        }}
                      >
                        {role.is_active ? 'Ativo' : 'Inativo'}
                      </button>
                    </td>
                    <td style={{ padding: 10, borderBottom: '1px solid #eee', textAlign: 'center' }}>
                      <div style={{ display: 'flex', gap: 5, justifyContent: 'center' }}>
                        <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(role)}>
                          Editar
                        </button>
                        <button className="btn btn-danger btn-sm" onClick={() => handleDelete(role)}>
                          Excluir
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showModal && (
        <div 
          className="modal-overlay" 
          onClick={() => setShowModal(false)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000
          }}
        >
          <div 
            className="modal" 
            onClick={e => e.stopPropagation()}
            style={{
              backgroundColor: 'white',
              padding: 24,
              borderRadius: 8,
              width: '100%',
              maxWidth: 500,
              maxHeight: '90vh',
              overflowY: 'auto'
            }}
          >
            <h3 style={{ marginTop: 0 }}>{editingRole ? 'Editar Funcao' : 'Nova Funcao'}</h3>
            
            <form onSubmit={handleSubmit}>
              <div className="form-group" style={{ marginBottom: 15 }}>
                <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Nome *</label>
                <input 
                  type="text" 
                  value={form.name} 
                  onChange={e => setForm({...form, name: e.target.value})}
                  placeholder="Ex: Camareira"
                  required 
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 4 }}
                />
              </div>
              
              <div className="form-group" style={{ marginBottom: 15 }}>
                <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Setor *</label>
                <select 
                  value={form.sector_id} 
                  onChange={e => setForm({...form, sector_id: e.target.value ? Number(e.target.value) : ''})}
                  required
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 4 }}
                >
                  <option value="">Selecione um setor</option>
                  {sectors.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              
              <div className="form-group" style={{ marginBottom: 15 }}>
                <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Tipo de Vinculo *</label>
                <select 
                  value={form.employment_type} 
                  onChange={e => setForm({...form, employment_type: e.target.value as 'intermitente' | 'efetivo'})}
                  required
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 4 }}
                >
                  <option value="efetivo">Efetivo / Fixo</option>
                  <option value="intermitente">Intermitente</option>
                </select>
              </div>
              
              <div className="form-group" style={{ marginBottom: 15 }}>
                <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Codigo CBO</label>
                <input 
                  type="text" 
                  value={form.cbo_code} 
                  onChange={e => setForm({...form, cbo_code: e.target.value.toUpperCase()})}
                  placeholder="Ex: 5133-15"
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 4 }}
                />
                <small style={{ color: '#666', fontSize: 11 }}>Classificacao Brasileira de Ocupacoes</small>
              </div>
              
              <div className="form-group" style={{ marginBottom: 15 }}>
                <label style={{ display: 'block', marginBottom: 5, fontWeight: 500 }}>Descricao</label>
                <textarea 
                  value={form.description} 
                  onChange={e => setForm({...form, description: e.target.value})}
                  placeholder="Descricao das responsabilidades da funcao"
                  rows={2}
                  style={{ width: '100%', padding: '8px 12px', border: '1px solid #ddd', borderRadius: 4, resize: 'vertical' }}
                />
              </div>
              
              <div className="form-group" style={{ marginBottom: 20 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
                  <input 
                    type="checkbox" 
                    checked={form.is_active} 
                    onChange={e => setForm({...form, is_active: e.target.checked})}
                    style={{ width: 18, height: 18 }}
                  />
                  <span style={{ fontWeight: 500 }}>Funcao ativa</span>
                </label>
              </div>
              
              <div className="modal-actions" style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={() => setShowModal(false)}
                  style={{ padding: '8px 16px' }}
                >
                  Cancelar
                </button>
                <button 
                  type="submit" 
                  className="btn btn-primary"
                  style={{ padding: '8px 16px' }}
                >
                  Salvar
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default RolesPage;
