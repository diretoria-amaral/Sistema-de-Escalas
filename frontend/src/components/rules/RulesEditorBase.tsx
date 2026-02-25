import { useState, useEffect, Component, ReactNode } from 'react';
import { sectorsApi, Sector } from '../../services/client';
import { sectorRulesApi, SectorRule, RuleType, RigidityLevel, SectorRuleCreate, SectorRuleUpdate, GroupedRulesResponse } from '../../services/rules';
import { ExpandableText } from '../common/ExpandableText';

interface ErrorBoundaryProps {
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[RulesEditorBase] Erro capturado:', error, errorInfo);
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '40px',
          textAlign: 'center',
          backgroundColor: '#fff3cd',
          border: '1px solid #ffc107',
          borderRadius: '8px',
          margin: '20px',
        }}>
          <h3 style={{ color: '#856404', marginBottom: '16px' }}>
            Ocorreu um erro na tela
          </h3>
          <p style={{ color: '#856404', marginBottom: '16px' }}>
            {this.state.error?.message || 'Erro desconhecido'}
          </p>
          <button 
            onClick={this.handleReload}
            className="btn btn-primary"
          >
            Clique para recarregar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

const RIGIDITY_LEVELS: { key: RigidityLevel; label: string; color: string; bgColor: string }[] = [
  { key: 'MANDATORY', label: 'Mandatorias', color: '#dc3545', bgColor: '#f8d7da' },
  { key: 'DESIRABLE', label: 'Desejaveis', color: '#fd7e14', bgColor: '#fff3cd' },
  { key: 'FLEXIBLE', label: 'Flexiveis', color: '#28a745', bgColor: '#d4edda' },
];

const emptyGrouped: GroupedRulesResponse = {
  labor: { MANDATORY: [], DESIRABLE: [], FLEXIBLE: [] },
  system: { MANDATORY: [], DESIRABLE: [], FLEXIBLE: [] },
  operational: { MANDATORY: [], DESIRABLE: [], FLEXIBLE: [] },
  calculation: { MANDATORY: [], DESIRABLE: [], FLEXIBLE: [] },
};

const typeKeyMap: Record<RuleType, keyof GroupedRulesResponse> = {
  'LABOR': 'labor',
  'SYSTEM': 'system',
  'OPERATIONAL': 'operational',
  'CALCULATION': 'calculation',
};

export interface RulesEditorBaseProps {
  ruleType: RuleType;
  showSectorSelector?: boolean;
  title: string;
  description: string;
}

export function RulesEditorBase({ 
  ruleType,
  showSectorSelector = true,
  title,
  description 
}: RulesEditorBaseProps) {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [selectedSectorId, setSelectedSectorId] = useState<number | null>(null);
  const [groupedRules, setGroupedRules] = useState<GroupedRulesResponse>(emptyGrouped);
  const [loading, setLoading] = useState(false);
  const [showInactive, setShowInactive] = useState(false);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingRule, setEditingRule] = useState<SectorRule | null>(null);
  const [draggedItem, setDraggedItem] = useState<SectorRule | null>(null);
  const [dragOverItem, setDragOverItem] = useState<number | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const isGlobal = ruleType === 'LABOR' || ruleType === 'SYSTEM';

  const [form, setForm] = useState<{
    title: string;
    pergunta: string;
    resposta: string;
    nivel_rigidez: RigidityLevel;
    prioridade: number;
    validade_inicio: string;
    validade_fim: string;
  }>({
    title: '',
    pergunta: '',
    resposta: '',
    nivel_rigidez: 'MANDATORY',
    prioridade: 1,
    validade_inicio: '',
    validade_fim: '',
  });

  useEffect(() => {
    if (showSectorSelector) {
      loadSectors();
    } else {
      loadGlobalRules();
    }
  }, [showSectorSelector, ruleType]);

  useEffect(() => {
    if (selectedSectorId && showSectorSelector) {
      loadRules();
    }
  }, [selectedSectorId, showInactive]);

  const loadSectors = async () => {
    try {
      const res = await sectorsApi.list();
      setSectors(res.data);
      if (res.data.length > 0 && !selectedSectorId) {
        setSelectedSectorId(res.data[0].id);
      }
    } catch {
      setMessage({ type: 'error', text: 'Erro ao carregar setores' });
    }
  };

  const loadRules = async () => {
    if (!selectedSectorId) return;
    setLoading(true);
    try {
      const res = await sectorRulesApi.getGrouped(selectedSectorId, !showInactive);
      setGroupedRules(res.data);
    } catch {
      setGroupedRules(emptyGrouped);
    } finally {
      setLoading(false);
    }
  };

  const loadGlobalRules = async () => {
    setLoading(true);
    try {
      const res = await sectorRulesApi.listGlobal(ruleType);
      const rules = res.data;
      const grouped: GroupedRulesResponse = { ...emptyGrouped };
      const typeKey = typeKeyMap[ruleType];
      grouped[typeKey] = {
        MANDATORY: rules.filter((r: SectorRule) => r.nivel_rigidez === 'MANDATORY'),
        DESIRABLE: rules.filter((r: SectorRule) => r.nivel_rigidez === 'DESIRABLE'),
        FLEXIBLE: rules.filter((r: SectorRule) => r.nivel_rigidez === 'FLEXIBLE'),
      };
      setGroupedRules(grouped);
    } catch {
      setGroupedRules(emptyGrouped);
    } finally {
      setLoading(false);
    }
  };

  const reloadRules = async () => {
    if (isGlobal) {
      await loadGlobalRules();
    } else {
      await loadRules();
    }
  };

  const resetForm = () => {
    setEditingRule(null);
    setShowAdvanced(false);
    setForm({
      title: '',
      pergunta: '',
      resposta: '',
      nivel_rigidez: 'MANDATORY',
      prioridade: 1,
      validade_inicio: '',
      validade_fim: '',
    });
  };

  const openCreateModal = (rigidity: RigidityLevel) => {
    resetForm();
    const typeKey = typeKeyMap[ruleType];
    const rulesInBlock = groupedRules[typeKey][rigidity] || [];
    const nextPriority = rulesInBlock.length > 0 
      ? Math.max(...rulesInBlock.map(r => r.prioridade)) + 1 
      : 1;
    setForm(prev => ({ ...prev, nivel_rigidez: rigidity, prioridade: nextPriority }));
    setShowModal(true);
  };

  const openEditModal = (rule: SectorRule) => {
    setEditingRule(rule);
    setForm({
      title: rule.title || rule.codigo_regra,
      pergunta: rule.pergunta,
      resposta: rule.resposta,
      nivel_rigidez: rule.nivel_rigidez,
      prioridade: rule.prioridade,
      validade_inicio: rule.validade_inicio || '',
      validade_fim: rule.validade_fim || '',
    });
    setShowModal(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!isGlobal && !selectedSectorId) {
      setMessage({ type: 'error', text: 'Selecione um setor antes de criar a regra.' });
      return;
    }

    if (!form.title.trim()) {
      setMessage({ type: 'error', text: 'Titulo da regra e obrigatorio.' });
      return;
    }

    if (!form.pergunta.trim()) {
      setMessage({ type: 'error', text: 'Pergunta e obrigatoria.' });
      return;
    }

    if (!form.resposta.trim()) {
      setMessage({ type: 'error', text: 'Resposta e obrigatoria.' });
      return;
    }

    setSubmitting(true);

    try {
      if (editingRule) {
        const updateData: SectorRuleUpdate = {
          title: form.title.trim(),
          pergunta: form.pergunta.trim(),
          resposta: form.resposta.trim(),
          nivel_rigidez: form.nivel_rigidez,
          prioridade: form.prioridade,
          validade_inicio: form.validade_inicio || undefined,
          validade_fim: form.validade_fim || undefined,
        };
        await sectorRulesApi.update(editingRule.id, updateData);
        setMessage({ type: 'success', text: 'Regra atualizada com sucesso!' });
        await reloadRules();
      } else {
        const createData: SectorRuleCreate = {
          setor_id: isGlobal ? undefined : selectedSectorId!,
          tipo_regra: ruleType,
          nivel_rigidez: form.nivel_rigidez,
          title: form.title.trim(),
          pergunta: form.pergunta.trim(),
          resposta: form.resposta.trim(),
          prioridade: form.prioridade,
          validade_inicio: form.validade_inicio || undefined,
          validade_fim: form.validade_fim || undefined,
          is_global: isGlobal,
        };
        await sectorRulesApi.create(createData);
        setMessage({ type: 'success', text: 'Regra criada com sucesso!' });
      }
      
      setShowModal(false);
      resetForm();
      reloadRules();
    } catch (error: any) {
      console.error('[RulesEditorBase] Erro ao salvar regra:', error);
      let errorMessage = 'Erro ao salvar regra. Tente novamente.';
      if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      }
      setMessage({ type: 'error', text: errorMessage });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (rule: SectorRule) => {
    if (!confirm(`Excluir regra "${rule.title || rule.codigo_regra}"?`)) return;
    try {
      await sectorRulesApi.delete(rule.id);
      setMessage({ type: 'success', text: 'Regra excluida!' });
      reloadRules();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao excluir regra' });
    }
  };

  const handleToggle = async (rule: SectorRule) => {
    try {
      await sectorRulesApi.toggle(rule.id);
      setMessage({ type: 'success', text: rule.regra_ativa ? 'Regra desativada!' : 'Regra ativada!' });
      reloadRules();
    } catch {
      setMessage({ type: 'error', text: 'Erro ao alterar status' });
    }
  };

  const handleDuplicate = async (rule: SectorRule) => {
    const originalTitle = rule.title || rule.codigo_regra;
    const newTitle = `COPIA - ${originalTitle}`;
    try {
      const response = await sectorRulesApi.clone(rule.id, newTitle);
      const clonedRule = response.data;
      setMessage({ type: 'success', text: 'Regra duplicada! Abrindo para edicao...' });
      await reloadRules();
      openEditModal(clonedRule);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'Erro ao duplicar regra' });
    }
  };

  const handleDragStart = (rule: SectorRule) => {
    setDraggedItem(rule);
  };

  const handleDragOver = (e: React.DragEvent, ruleId: number) => {
    e.preventDefault();
    setDragOverItem(ruleId);
  };

  const handleDragEnd = () => {
    setDraggedItem(null);
    setDragOverItem(null);
  };

  const handleDrop = async (targetRule: SectorRule) => {
    if (!draggedItem) return;
    if (draggedItem.id === targetRule.id) return;
    if (draggedItem.nivel_rigidez !== targetRule.nivel_rigidez) {
      setMessage({ type: 'error', text: 'Nao e possivel reordenar entre niveis de rigidez diferentes' });
      return;
    }

    const rigidity = draggedItem.nivel_rigidez;
    const typeKey = typeKeyMap[ruleType];
    const rules = [...(groupedRules[typeKey][rigidity] || [])];
    const dragIndex = rules.findIndex(r => r.id === draggedItem.id);
    const dropIndex = rules.findIndex(r => r.id === targetRule.id);

    if (dragIndex === -1 || dropIndex === -1) return;

    rules.splice(dragIndex, 1);
    rules.splice(dropIndex, 0, draggedItem);

    const reorderedRules = rules.map((rule, index) => ({
      ...rule,
      prioridade: index + 1
    }));

    const newGrouped = { ...groupedRules };
    newGrouped[typeKey] = { ...newGrouped[typeKey], [rigidity]: reorderedRules };
    setGroupedRules(newGrouped);

    try {
      if (isGlobal) {
        await sectorRulesApi.reorderGlobal(ruleType, rules.map(r => r.id));
      } else if (selectedSectorId) {
        await sectorRulesApi.reorder(selectedSectorId, ruleType, rules.map(r => r.id));
      }
      setMessage({ type: 'success', text: 'Ordem atualizada!' });
    } catch {
      setMessage({ type: 'error', text: 'Erro ao reordenar' });
      reloadRules();
    }

    handleDragEnd();
  };

  const renderRuleCard = (rule: SectorRule) => {
    const isDragging = draggedItem?.id === rule.id;
    const isDragOver = dragOverItem === rule.id;

    return (
      <div
        key={rule.id}
        className={`rule-card ${isDragging ? 'dragging' : ''} ${isDragOver ? 'drag-over' : ''} ${!rule.regra_ativa ? 'inactive' : ''}`}
        draggable
        onDragStart={() => handleDragStart(rule)}
        onDragOver={(e) => handleDragOver(e, rule.id)}
        onDragEnd={handleDragEnd}
        onDrop={() => handleDrop(rule)}
        style={{
          padding: '16px',
          marginBottom: '10px',
          border: '1px solid #e0e0e0',
          borderRadius: '8px',
          backgroundColor: isDragOver ? '#e3f2fd' : (isDragging ? '#f5f5f5' : (rule.regra_ativa ? '#fff' : '#f9f9f9')),
          cursor: 'grab',
          opacity: rule.regra_ativa ? 1 : 0.6,
          transition: 'all 0.2s ease',
          boxShadow: isDragging ? '0 4px 12px rgba(0,0,0,0.15)' : '0 1px 3px rgba(0,0,0,0.08)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ flex: 1, marginRight: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <span style={{ 
                fontWeight: 'bold', 
                color: '#1a1a2e',
                fontSize: '1rem'
              }}>
                {rule.title || rule.codigo_regra}
              </span>
              <span style={{
                fontSize: '0.75rem',
                backgroundColor: '#3b82f6',
                color: 'white',
                padding: '3px 10px',
                borderRadius: '12px',
                fontWeight: '600',
              }}>
                #{String(rule.prioridade).padStart(2, '0')}
              </span>
              {!rule.regra_ativa && (
                <span style={{
                  fontSize: '0.75rem',
                  backgroundColor: '#ffcdd2',
                  color: '#c62828',
                  padding: '3px 8px',
                  borderRadius: '12px',
                }}>
                  Inativo
                </span>
              )}
            </div>
            <div style={{ fontSize: '0.9rem', color: '#444', marginBottom: '8px' }}>
              <strong style={{ color: '#666' }}>P:</strong>{' '}
              <ExpandableText text={rule.pergunta} maxLines={2} />
            </div>
            <div style={{ fontSize: '0.9rem', color: '#555' }}>
              <strong style={{ color: '#666' }}>R:</strong>{' '}
              <ExpandableText text={rule.resposta} maxLines={3} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <button
              onClick={() => openEditModal(rule)}
              className="btn btn-sm"
              style={{ padding: '6px 12px', fontSize: '0.8rem', backgroundColor: '#e3f2fd', border: '1px solid #90caf9', color: '#1976d2' }}
              title="Editar"
            >
              Editar
            </button>
            <button
              onClick={() => handleDuplicate(rule)}
              className="btn btn-sm"
              style={{ padding: '6px 12px', fontSize: '0.8rem', backgroundColor: '#f3e5f5', border: '1px solid #ce93d8', color: '#7b1fa2' }}
              title="Duplicar"
            >
              Duplicar
            </button>
            <button
              onClick={() => handleToggle(rule)}
              className="btn btn-sm"
              style={{ 
                padding: '6px 12px', 
                fontSize: '0.8rem',
                backgroundColor: rule.regra_ativa ? '#fff3cd' : '#d4edda',
                border: rule.regra_ativa ? '1px solid #ffc107' : '1px solid #28a745',
                color: rule.regra_ativa ? '#856404' : '#155724',
              }}
              title={rule.regra_ativa ? 'Desativar' : 'Ativar'}
            >
              {rule.regra_ativa ? 'Desativar' : 'Ativar'}
            </button>
            <button
              onClick={() => handleDelete(rule)}
              className="btn btn-sm"
              style={{ padding: '6px 12px', fontSize: '0.8rem', backgroundColor: '#ffebee', border: '1px solid #ef9a9a', color: '#c62828' }}
              title="Excluir"
            >
              Excluir
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderRigiditySection = (rigidity: RigidityLevel) => {
    const levelInfo = RIGIDITY_LEVELS.find(r => r.key === rigidity)!;
    const typeKey = typeKeyMap[ruleType];
    const rules = groupedRules[typeKey][rigidity] || [];

    return (
      <div key={rigidity} style={{ marginBottom: '28px' }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center',
          marginBottom: '14px',
          paddingBottom: '10px',
          borderBottom: `3px solid ${levelInfo.color}`,
        }}>
          <h4 style={{ margin: 0, color: levelInfo.color, fontSize: '1.1rem', fontWeight: '600' }}>
            {levelInfo.label} ({rules.length})
          </h4>
          <button 
            className="btn btn-sm btn-primary"
            onClick={() => openCreateModal(rigidity)}
            style={{ padding: '6px 14px' }}
          >
            + Nova Regra
          </button>
        </div>

        {rules.length === 0 ? (
          <div style={{ 
            padding: '32px', 
            textAlign: 'center', 
            backgroundColor: levelInfo.bgColor,
            borderRadius: '8px',
            color: levelInfo.color,
            border: `1px dashed ${levelInfo.color}`,
          }}>
            <p style={{ marginBottom: '12px' }}>
              Nenhuma regra {levelInfo.label.toLowerCase()} cadastrada.
            </p>
            <button 
              className="btn btn-primary"
              onClick={() => openCreateModal(rigidity)}
            >
              Criar Primeira Regra
            </button>
          </div>
        ) : (
          <div>
            {rules.map(rule => renderRuleCard(rule))}
          </div>
        )}
      </div>
    );
  };

  const canShowContent = isGlobal || selectedSectorId;

  return (
    <ErrorBoundary>
      <div>
        {message && (
          <div 
            className={`alert alert-${message.type}`}
            style={{
              padding: '12px 16px',
              marginBottom: '16px',
              borderRadius: '6px',
              backgroundColor: message.type === 'error' ? '#ffebee' : '#e8f5e9',
              color: message.type === 'error' ? '#c62828' : '#2e7d32',
              border: `1px solid ${message.type === 'error' ? '#ef9a9a' : '#a5d6a7'}`,
            }}
          >
            {message.text}
            <button 
              onClick={() => setMessage(null)} 
              style={{ float: 'right', background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.1rem' }}
            >
              &times;
            </button>
          </div>
        )}

        <div className="card" style={{ padding: '24px', backgroundColor: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.08)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
            <h2 style={{ margin: 0, color: '#1a1a2e' }}>{title}</h2>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.9rem', color: '#666' }}>
              <input 
                type="checkbox" 
                id="showInactive" 
                checked={showInactive} 
                onChange={(e) => setShowInactive(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <label htmlFor="showInactive" style={{ cursor: 'pointer' }}>Mostrar inativas</label>
            </div>
          </div>
          <p style={{ color: '#666', marginBottom: '24px', lineHeight: '1.5' }}>
            {description}
            {' '}Dentro de cada tipo, a ordem de precedencia e: Mandatorias {'>'} Desejaveis {'>'} Flexiveis.
          </p>

          {showSectorSelector && (
            <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #e9ecef' }}>
              <label style={{ display: 'block', marginBottom: '8px', fontWeight: 'bold', color: '#495057' }}>
                Selecione o Setor:
              </label>
              <select
                value={selectedSectorId || ''}
                onChange={(e) => setSelectedSectorId(Number(e.target.value))}
                className="form-control"
                style={{ maxWidth: '350px', padding: '10px 12px', fontSize: '1rem' }}
              >
                <option value="">-- Selecione um setor --</option>
                {sectors.map(sector => (
                  <option key={sector.id} value={sector.id}>{sector.name}</option>
                ))}
              </select>
            </div>
          )}

          {canShowContent ? (
            loading ? (
              <div style={{ padding: '40px', textAlign: 'center', color: '#666' }}>
                <div style={{ marginBottom: '12px' }}>Carregando regras...</div>
              </div>
            ) : (
              <div>
                {RIGIDITY_LEVELS.map(level => renderRigiditySection(level.key))}
              </div>
            )
          ) : (
            <div style={{ 
              padding: '40px', 
              textAlign: 'center', 
              backgroundColor: '#f5f5f5', 
              borderRadius: '8px',
              color: '#666',
            }}>
              Selecione um setor para visualizar as regras.
            </div>
          )}
        </div>

        {showModal && (
          <div className="modal-overlay" style={{
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
            <div className="modal-content" style={{
              backgroundColor: '#fff',
              padding: '28px',
              borderRadius: '12px',
              width: '650px',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 8px 32px rgba(0,0,0,0.2)',
            }}>
              <h3 style={{ marginBottom: '20px', color: '#1a1a2e' }}>
                {editingRule ? 'Editar Regra' : 'Nova Regra'}
              </h3>

              <form onSubmit={handleSubmit}>
                <div style={{ 
                  border: '1px solid #e0e0e0', 
                  borderRadius: '8px', 
                  padding: '20px', 
                  marginBottom: '20px',
                  backgroundColor: '#fafafa'
                }}>
                  <h4 style={{ margin: '0 0 16px 0', color: '#333', fontSize: '1rem' }}>
                    Identificacao
                  </h4>
                  
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', marginBottom: '6px', fontWeight: 'bold' }}>
                      Titulo da Regra *
                    </label>
                    <input
                      type="text"
                      className="form-control"
                      value={form.title}
                      onChange={(e) => setForm({ ...form, title: e.target.value })}
                      required
                      placeholder="Ex: Limite de horas semanais"
                      disabled={submitting}
                      style={{ fontSize: '1rem', padding: '10px 12px' }}
                    />
                  </div>

                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', marginBottom: '6px', fontWeight: 'bold' }}>
                      Nivel de Rigidez *
                    </label>
                    <select
                      className="form-control"
                      value={form.nivel_rigidez}
                      onChange={(e) => setForm({ ...form, nivel_rigidez: e.target.value as RigidityLevel })}
                      disabled={submitting}
                      style={{ fontSize: '1rem', padding: '10px 12px' }}
                    >
                      <option value="MANDATORY">Mandatoria</option>
                      <option value="DESIRABLE">Desejavel</option>
                      <option value="FLEXIBLE">Flexivel</option>
                    </select>
                  </div>
                </div>

                <div style={{ 
                  border: '1px solid #bbdefb', 
                  borderRadius: '8px', 
                  padding: '20px', 
                  marginBottom: '20px',
                  backgroundColor: '#e3f2fd'
                }}>
                  <h4 style={{ margin: '0 0 16px 0', color: '#1565c0', fontSize: '1rem' }}>
                    Conteudo (Pergunta/Resposta)
                  </h4>
                  
                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', marginBottom: '6px', fontWeight: 'bold' }}>
                      Pergunta *
                    </label>
                    <textarea
                      className="form-control"
                      value={form.pergunta}
                      onChange={(e) => setForm({ ...form, pergunta: e.target.value })}
                      required
                      placeholder="A pergunta que esta regra responde..."
                      disabled={submitting}
                      rows={5}
                      style={{ fontSize: '1rem', padding: '10px 12px', resize: 'vertical' }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', marginBottom: '6px', fontWeight: 'bold' }}>
                      Resposta *
                    </label>
                    <textarea
                      className="form-control"
                      value={form.resposta}
                      onChange={(e) => setForm({ ...form, resposta: e.target.value })}
                      required
                      placeholder="A resposta/definicao da regra..."
                      disabled={submitting}
                      rows={7}
                      style={{ fontSize: '1rem', padding: '10px 12px', resize: 'vertical' }}
                    />
                  </div>
                </div>

                <div style={{ marginBottom: '20px' }}>
                  <button
                    type="button"
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    style={{ 
                      background: 'none', 
                      border: 'none', 
                      color: '#1976d2', 
                      cursor: 'pointer',
                      fontSize: '0.95rem',
                      padding: '4px 0',
                    }}
                  >
                    {showAdvanced ? '▼ Ocultar opcoes avancadas' : '▶ Mostrar opcoes avancadas'}
                  </button>
                </div>

                {showAdvanced && (
                  <div style={{ 
                    border: '1px solid #e0e0e0', 
                    borderRadius: '8px', 
                    padding: '20px', 
                    marginBottom: '20px',
                    backgroundColor: '#f5f5f5'
                  }}>
                    <h4 style={{ margin: '0 0 16px 0', color: '#666', fontSize: '1rem' }}>
                      Opcoes Avancadas
                    </h4>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px' }}>
                          Validade Inicio (opcional)
                        </label>
                        <input
                          type="date"
                          className="form-control"
                          value={form.validade_inicio}
                          onChange={(e) => setForm({ ...form, validade_inicio: e.target.value })}
                          disabled={submitting}
                        />
                      </div>
                      <div>
                        <label style={{ display: 'block', marginBottom: '6px' }}>
                          Validade Fim (opcional)
                        </label>
                        <input
                          type="date"
                          className="form-control"
                          value={form.validade_fim}
                          onChange={(e) => setForm({ ...form, validade_fim: e.target.value })}
                          disabled={submitting}
                        />
                      </div>
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid #e0e0e0' }}>
                  <button
                    type="button"
                    onClick={() => { setShowModal(false); resetForm(); }}
                    className="btn"
                    style={{ padding: '10px 20px', backgroundColor: '#f5f5f5', border: '1px solid #ddd' }}
                    disabled={submitting}
                  >
                    Cancelar
                  </button>
                  <button
                    type="submit"
                    className="btn btn-primary"
                    style={{ padding: '10px 24px' }}
                    disabled={submitting}
                  >
                    {submitting ? 'Salvando...' : (editingRule ? 'Salvar Alteracoes' : 'Criar Regra')}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </ErrorBoundary>
  );
}

export default RulesEditorBase;
