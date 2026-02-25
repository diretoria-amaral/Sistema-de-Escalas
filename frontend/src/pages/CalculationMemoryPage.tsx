import { useState, useEffect } from 'react';

interface Sector {
  id: number;
  name: string;
}

interface AgentRun {
  id: number;
  setor_id: number;
  week_start: string;
  run_type: string;
  status: string;
  created_at: string;
  finished_at: string | null;
}

interface TimelineStep {
  order: number;
  key: string;
  description: string;
  summary: string;
  has_violations: boolean;
  timestamp: string | null;
}

interface MathItem {
  label: string;
  items: { key: string; value: number | string }[];
}

interface RuleApplied {
  codigo: string;
  tipo: string;
  nivel: string;
  step: string;
  order: number;
}

interface RuleViolated {
  regra: string;
  motivo: string;
  step: string;
  dados: Record<string, unknown>;
}

interface Explanation {
  text: string;
  math: MathItem[];
  rules_applied: RuleApplied[];
  rules_violated: RuleViolated[];
  timeline: TimelineStep[];
}

const RUN_TYPE_LABELS: Record<string, string> = {
  FORECAST: 'Previsão de Ocupação',
  DEMAND: 'Cálculo de Demanda',
  SCHEDULE: 'Geração de Escala',
  CONVOCATIONS: 'Geração de Convocações',
  FULL_PIPELINE: 'Pipeline Completo'
};

const STATUS_LABELS: Record<string, { label: string; color: string }> = {
  RUNNING: { label: 'Em execução', color: 'bg-blue-100 text-blue-800' },
  SUCCESS: { label: 'Sucesso', color: 'bg-green-100 text-green-800' },
  FAILED: { label: 'Falhou', color: 'bg-red-100 text-red-800' }
};

export default function CalculationMemoryPage() {
  const [sectors, setSectors] = useState<Sector[]>([]);
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [selectedSector, setSelectedSector] = useState<number | ''>('');
  const [weekStart, setWeekStart] = useState('');
  const [selectedRunType, setSelectedRunType] = useState<string>('');
  const [selectedRun, setSelectedRun] = useState<AgentRun | null>(null);
  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingExplanation, setLoadingExplanation] = useState(false);

  useEffect(() => {
    loadSectors();
  }, []);

  useEffect(() => {
    if (selectedSector && weekStart) {
      loadRuns();
    }
  }, [selectedSector, weekStart, selectedRunType]);

  const loadSectors = async () => {
    try {
      const res = await fetch('/api/sectors');
      const data = await res.json();
      setSectors(data);
    } catch (error) {
      console.error('Erro ao carregar setores:', error);
    }
  };

  const loadRuns = async () => {
    if (!selectedSector || !weekStart) return;
    
    setLoading(true);
    try {
      let url = `/api/agent-runs?setor_id=${selectedSector}&week_start=${weekStart}&limit=50`;
      if (selectedRunType) {
        url += `&run_type=${selectedRunType}`;
      }
      const res = await fetch(url);
      const data = await res.json();
      setRuns(data.items || []);
    } catch (error) {
      console.error('Erro ao carregar execuções:', error);
      setRuns([]);
    } finally {
      setLoading(false);
    }
  };

  const loadExplanation = async (run: AgentRun) => {
    setSelectedRun(run);
    setLoadingExplanation(true);
    try {
      const res = await fetch(`/api/agent-runs/${run.id}/explain`);
      const data = await res.json();
      setExplanation(data.explanation);
    } catch (error) {
      console.error('Erro ao carregar explicação:', error);
      setExplanation(null);
    } finally {
      setLoadingExplanation(false);
    }
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleString('pt-BR');
  };

  return (
    <div className="p-6">
      <div className="mb-6">
        <nav className="text-sm text-gray-500 mb-2">
          Relatórios &gt; Memória de Cálculo
        </nav>
        <h1 className="text-2xl font-bold text-gray-900">Memória de Cálculo</h1>
        <p className="text-gray-600 mt-1">
          Visualize o histórico de execuções do agente com explicações detalhadas.
        </p>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Setor</label>
            <select
              value={selectedSector}
              onChange={(e) => setSelectedSector(e.target.value ? Number(e.target.value) : '')}
              className="w-full border rounded-md px-3 py-2"
            >
              <option value="">Selecione...</option>
              {sectors.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Semana</label>
            <input
              type="date"
              value={weekStart}
              onChange={(e) => setWeekStart(e.target.value)}
              className="w-full border rounded-md px-3 py-2"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Tipo de Execução</label>
            <select
              value={selectedRunType}
              onChange={(e) => setSelectedRunType(e.target.value)}
              className="w-full border rounded-md px-3 py-2"
            >
              <option value="">Todos</option>
              <option value="FORECAST">Previsão</option>
              <option value="DEMAND">Demanda</option>
              <option value="SCHEDULE">Escala</option>
              <option value="CONVOCATIONS">Convocações</option>
              <option value="FULL_PIPELINE">Pipeline Completo</option>
            </select>
          </div>
          <div className="flex items-end">
            <button
              onClick={loadRuns}
              disabled={!selectedSector || !weekStart}
              className="w-full bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              Buscar
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow">
            <div className="px-4 py-3 border-b">
              <h2 className="font-semibold">Execuções</h2>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              {loading ? (
                <div className="p-4 text-center text-gray-500">Carregando...</div>
              ) : runs.length === 0 ? (
                <div className="p-4 text-center text-gray-500">
                  {selectedSector && weekStart 
                    ? 'Nenhuma execução encontrada' 
                    : 'Selecione setor e semana'}
                </div>
              ) : (
                <ul className="divide-y">
                  {runs.map(run => (
                    <li
                      key={run.id}
                      onClick={() => loadExplanation(run)}
                      className={`p-4 cursor-pointer hover:bg-gray-50 ${
                        selectedRun?.id === run.id ? 'bg-blue-50' : ''
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <span className="font-medium text-gray-900">
                            {RUN_TYPE_LABELS[run.run_type] || run.run_type}
                          </span>
                          <p className="text-sm text-gray-500">
                            {formatDate(run.created_at)}
                          </p>
                        </div>
                        <span className={`px-2 py-1 text-xs rounded-full ${STATUS_LABELS[run.status]?.color || 'bg-gray-100'}`}>
                          {STATUS_LABELS[run.status]?.label || run.status}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>

        <div className="lg:col-span-2">
          {loadingExplanation ? (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-2 text-gray-500">Carregando explicação...</p>
            </div>
          ) : !selectedRun || !explanation ? (
            <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
              Selecione uma execução para ver os detalhes
            </div>
          ) : (
            <div className="space-y-6">
              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="font-semibold text-lg mb-4">Resumo</h3>
                <div className="prose prose-sm max-w-none whitespace-pre-wrap">
                  {explanation.text.split('\n').map((line, i) => (
                    <p key={i} className={line.startsWith('**') ? 'font-semibold' : ''}>
                      {line.replace(/\*\*/g, '')}
                    </p>
                  ))}
                </div>
              </div>

              {explanation.math.length > 0 && (
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="font-semibold text-lg mb-4">Cálculos Numéricos</h3>
                  <div className="space-y-4">
                    {explanation.math.map((section, idx) => (
                      <div key={idx} className="border rounded-lg p-4">
                        <h4 className="font-medium text-gray-900 mb-2">{section.label}</h4>
                        <table className="w-full text-sm">
                          <tbody>
                            {section.items.map((item, i) => (
                              <tr key={i} className="border-b last:border-0">
                                <td className="py-2 text-gray-600">{item.key}</td>
                                <td className="py-2 text-right font-mono">{item.value}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="bg-white rounded-lg shadow p-6">
                <h3 className="font-semibold text-lg mb-4">Timeline</h3>
                {explanation.timeline.length === 0 ? (
                  <p className="text-gray-500">Nenhum passo registrado</p>
                ) : (
                  <div className="relative">
                    <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200"></div>
                    <ul className="space-y-4">
                      {explanation.timeline.map((step, idx) => (
                        <li key={idx} className="relative pl-10">
                          <div className={`absolute left-2 w-5 h-5 rounded-full ${
                            step.has_violations ? 'bg-red-500' : 'bg-blue-500'
                          } flex items-center justify-center`}>
                            <span className="text-white text-xs">{step.order}</span>
                          </div>
                          <div className="bg-gray-50 rounded-lg p-3">
                            <div className="flex justify-between">
                              <span className="font-medium">{step.description}</span>
                              {step.timestamp && (
                                <span className="text-xs text-gray-500">
                                  {new Date(step.timestamp).toLocaleTimeString('pt-BR')}
                                </span>
                              )}
                            </div>
                            {step.summary && (
                              <p className="text-sm text-gray-600 mt-1">{step.summary}</p>
                            )}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="font-semibold text-lg mb-4 flex items-center">
                    <span className="w-3 h-3 bg-green-500 rounded-full mr-2"></span>
                    Regras Aplicadas ({explanation.rules_applied.length})
                  </h3>
                  {explanation.rules_applied.length === 0 ? (
                    <p className="text-gray-500">Nenhuma regra registrada</p>
                  ) : (
                    <ul className="space-y-2">
                      {explanation.rules_applied.map((rule, idx) => (
                        <li key={idx} className="flex justify-between items-center py-2 border-b last:border-0">
                          <div>
                            <span className="font-mono text-sm text-gray-900">{rule.codigo}</span>
                            <span className="text-xs text-gray-500 ml-2">({rule.step})</span>
                          </div>
                          <span className="text-xs bg-gray-100 px-2 py-1 rounded">
                            {rule.tipo !== 'N/A' ? rule.tipo : ''} {rule.nivel !== 'N/A' ? rule.nivel : ''}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="bg-white rounded-lg shadow p-6">
                  <h3 className="font-semibold text-lg mb-4 flex items-center">
                    <span className="w-3 h-3 bg-red-500 rounded-full mr-2"></span>
                    Regras Violadas ({explanation.rules_violated.length})
                  </h3>
                  {explanation.rules_violated.length === 0 ? (
                    <p className="text-gray-500">Nenhuma violação detectada</p>
                  ) : (
                    <ul className="space-y-3">
                      {explanation.rules_violated.map((violation, idx) => (
                        <li key={idx} className="bg-red-50 p-3 rounded-lg">
                          <div className="font-medium text-red-800">{violation.regra}</div>
                          <p className="text-sm text-red-600 mt-1">{violation.motivo}</p>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
