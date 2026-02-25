import { useState, useEffect } from 'react';
import { sectorsApi, rolesApi, Sector, Role } from '../services/client';

function SetupPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  
  const [sectorForm, setSectorForm] = useState({ name: '', code: '', description: '' });
  const [roleForm, setRoleForm] = useState({ name: '', sector_id: '', cbo_code: '', description: '' });
  const [showSectorModal, setShowSectorModal] = useState(false);
  const [showRoleModal, setShowRoleModal] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [secRes, roleRes] = await Promise.all([
        sectorsApi.list(),
        rolesApi.list(),
      ]);
      setSectors(secRes.data);
      setRoles(roleRes.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar dados' });
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSector = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await sectorsApi.create(sectorForm);
      setMessage({ type: 'success', text: 'Setor criado!' });
      setShowSectorModal(false);
      setSectorForm({ name: '', code: '', description: '' });
      loadData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao criar setor' });
    }
  };

  const handleCreateRole = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await rolesApi.create({
        ...roleForm,
        sector_id: Number(roleForm.sector_id),
      });
      setMessage({ type: 'success', text: 'Cargo criado!' });
      setShowRoleModal(false);
      setRoleForm({ name: '', sector_id: '', cbo_code: '', description: '' });
      loadData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao criar cargo' });
    }
  };

  const handleDeleteSector = async (id: number) => {
    if (!confirm('Excluir este setor?')) return;
    try {
      await sectorsApi.delete(id);
      setMessage({ type: 'success', text: 'Setor excluido!' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao excluir. Verifique se nao ha colaboradores neste setor.' });
    }
  };

  const handleDeleteRole = async (id: number) => {
    if (!confirm('Excluir este cargo?')) return;
    try {
      await rolesApi.delete(id);
      setMessage({ type: 'success', text: 'Cargo excluido!' });
      loadData();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao excluir. Verifique se nao ha colaboradores com este cargo.' });
    }
  };

  const seedGovernance = async () => {
    try {
      const govSector = await sectorsApi.create({
        name: 'Governanca',
        code: 'GOV',
        description: 'Setor de governanca hoteleira - limpeza e arrumacao de quartos',
      });

      await Promise.all([
        rolesApi.create({ name: 'Camareira', sector_id: govSector.data.id, cbo_code: '5133-05' }),
        rolesApi.create({ name: 'Lider de Governanca', sector_id: govSector.data.id, cbo_code: '5133-10' }),
        rolesApi.create({ name: 'Auxiliar de Governanca', sector_id: govSector.data.id, cbo_code: '5133-15' }),
        rolesApi.create({ name: 'Supervisora de Andares', sector_id: govSector.data.id, cbo_code: '5133-20' }),
      ]);

      setMessage({ type: 'success', text: 'Setor de Governanca e cargos criados!' });
      loadData();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao criar dados iniciais' });
    }
  };

  const hasGovernance = sectors.some(s => s.code === 'GOV');

  return (
    <div>
      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
          <button onClick={() => setMessage(null)} style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer' }}>x</button>
        </div>
      )}

      {!hasGovernance && !loading && (
        <div className="card" style={{ background: '#fff3cd', border: '1px solid #ffc107' }}>
          <h2 style={{ color: '#856404' }}>Configuracao Inicial</h2>
          <p style={{ marginTop: 10 }}>O setor de Governanca ainda nao foi configurado. Clique abaixo para criar automaticamente.</p>
          <button className="btn btn-success" onClick={seedGovernance} style={{ marginTop: 15 }}>
            Criar Setor de Governanca + Cargos
          </button>
        </div>
      )}

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
          <h2>Setores</h2>
          <button className="btn btn-primary" onClick={() => setShowSectorModal(true)}>+ Novo Setor</button>
        </div>

        {loading ? (
          <div className="loading">Carregando...</div>
        ) : sectors.length === 0 ? (
          <div className="empty-state">Nenhum setor cadastrado</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Codigo</th>
                <th>Nome</th>
                <th>Descricao</th>
                <th>Acoes</th>
              </tr>
            </thead>
            <tbody>
              {sectors.map(s => (
                <tr key={s.id}>
                  <td><code>{s.code}</code></td>
                  <td>{s.name}</td>
                  <td>{s.description || '-'}</td>
                  <td>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeleteSector(s.id)}>Excluir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 15 }}>
          <h2>Cargos/Funcoes</h2>
          <button className="btn btn-primary" onClick={() => setShowRoleModal(true)} disabled={sectors.length === 0}>
            + Novo Cargo
          </button>
        </div>

        {roles.length === 0 ? (
          <div className="empty-state">Nenhum cargo cadastrado</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>CBO</th>
                <th>Setor</th>
                <th>Acoes</th>
              </tr>
            </thead>
            <tbody>
              {roles.map(r => (
                <tr key={r.id}>
                  <td>{r.name}</td>
                  <td>{r.cbo_code || '-'}</td>
                  <td>{sectors.find(s => s.id === r.sector_id)?.name || '-'}</td>
                  <td>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDeleteRole(r.id)}>Excluir</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showSectorModal && (
        <div className="modal-overlay" onClick={() => setShowSectorModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Novo Setor</h3>
            <form onSubmit={handleCreateSector}>
              <div className="form-row">
                <div className="form-group">
                  <label>Nome *</label>
                  <input 
                    type="text" 
                    value={sectorForm.name} 
                    onChange={e => setSectorForm({...sectorForm, name: e.target.value})}
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Codigo *</label>
                  <input 
                    type="text" 
                    value={sectorForm.code} 
                    onChange={e => setSectorForm({...sectorForm, code: e.target.value.toUpperCase()})}
                    placeholder="Ex: GOV, AEB, REC"
                    required 
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Descricao</label>
                <textarea 
                  value={sectorForm.description} 
                  onChange={e => setSectorForm({...sectorForm, description: e.target.value})}
                  rows={2}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowSectorModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary">Salvar</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showRoleModal && (
        <div className="modal-overlay" onClick={() => setShowRoleModal(false)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Novo Cargo</h3>
            <form onSubmit={handleCreateRole}>
              <div className="form-group">
                <label>Setor *</label>
                <select 
                  value={roleForm.sector_id} 
                  onChange={e => setRoleForm({...roleForm, sector_id: e.target.value})}
                  required
                >
                  <option value="">Selecione...</option>
                  {sectors.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Nome do Cargo *</label>
                  <input 
                    type="text" 
                    value={roleForm.name} 
                    onChange={e => setRoleForm({...roleForm, name: e.target.value})}
                    required 
                  />
                </div>
                <div className="form-group">
                  <label>Codigo CBO</label>
                  <input 
                    type="text" 
                    value={roleForm.cbo_code} 
                    onChange={e => setRoleForm({...roleForm, cbo_code: e.target.value})}
                    placeholder="Ex: 5133-05"
                  />
                </div>
              </div>
              <div className="form-group">
                <label>Descricao</label>
                <textarea 
                  value={roleForm.description} 
                  onChange={e => setRoleForm({...roleForm, description: e.target.value})}
                  rows={2}
                />
              </div>
              <div className="modal-actions">
                <button type="button" className="btn btn-secondary" onClick={() => setShowRoleModal(false)}>Cancelar</button>
                <button type="submit" className="btn btn-primary">Salvar</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

export default SetupPage;
