import { useState, useEffect } from 'react';
import { sectorsApi, Sector } from '../services/client';

function SectorsPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingSector, setEditingSector] = useState<Sector | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [form, setForm] = useState({ name: '', code: '', description: '' });

  useEffect(() => {
    loadSectors();
  }, []);

  const loadSectors = async () => {
    try {
      setLoading(true);
      const res = await sectorsApi.list();
      setSectors(res.data);
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar setores' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingSector) {
        await sectorsApi.update(editingSector.id, form);
        setMessage({ type: 'success', text: 'Setor atualizado!' });
      } else {
        await sectorsApi.create(form);
        setMessage({ type: 'success', text: 'Setor criado!' });
      }
      setShowModal(false);
      resetForm();
      loadSectors();
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao salvar setor' });
    }
  };

  const handleEdit = (sector: Sector) => {
    setEditingSector(sector);
    setForm({
      name: sector.name,
      code: sector.code || '',
      description: sector.description || ''
    });
    setShowModal(true);
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Excluir este setor?')) return;
    try {
      await sectorsApi.delete(id);
      setMessage({ type: 'success', text: 'Setor excluido!' });
      loadSectors();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao excluir' });
    }
  };

  const resetForm = () => {
    setEditingSector(null);
    setForm({ name: '', code: '', description: '' });
  };

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
          <h2>Setores</h2>
          <button className="btn btn-primary" onClick={() => { resetForm(); setShowModal(true); }}>
            + Novo Setor
          </button>
        </div>

        <p style={{ color: '#666', marginBottom: '1rem' }}>
          Cadastre os setores do hotel. Cada setor pode ter suas proprias atividades e regras operacionais.
        </p>

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
              {sectors.map(sector => (
                <tr key={sector.id}>
                  <td><code>{sector.code || '-'}</code></td>
                  <td>{sector.name}</td>
                  <td>{sector.description || '-'}</td>
                  <td className="actions">
                    <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(sector)}>Editar</button>
                    <button className="btn btn-danger btn-sm" onClick={() => handleDelete(sector.id)}>Excluir</button>
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
            <h3>{editingSector ? 'Editar Setor' : 'Novo Setor'}</h3>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label>Nome *</label>
                <input 
                  type="text" 
                  value={form.name} 
                  onChange={e => setForm({...form, name: e.target.value})}
                  placeholder="Ex: Governanca"
                  required 
                />
              </div>
              <div className="form-group">
                <label>Codigo</label>
                <input 
                  type="text" 
                  value={form.code} 
                  onChange={e => setForm({...form, code: e.target.value.toUpperCase()})}
                  placeholder="Ex: GOV"
                />
              </div>
              <div className="form-group">
                <label>Descricao</label>
                <textarea 
                  value={form.description} 
                  onChange={e => setForm({...form, description: e.target.value})}
                  rows={2}
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

export default SectorsPage;
