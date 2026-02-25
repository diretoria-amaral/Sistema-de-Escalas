import { useState, useEffect } from 'react';
import axios from 'axios';

interface ApiStats {
  total_calls: number;
  total_tokens: number;
  by_provider: Record<string, { calls: number; tokens: number }>;
}

interface ApiHistory {
  id: number;
  provider: string;
  endpoint: string;
  model: string;
  tokens_prompt: number;
  tokens_completion: number;
  tokens_total: number;
  created_at: string;
}

export default function ApiIntegrationPage() {
  const [stats, setStats] = useState<ApiStats | null>(null);
  const [history, setHistory] = useState<ApiHistory[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [statsRes, historyRes] = await Promise.all([
        axios.get('/api/api-usage/stats'),
        axios.get('/api/api-usage/history')
      ]);
      setStats(statsRes.data);
      setHistory(historyRes.data);
    } catch (error) {
      console.error('Erro ao carregar dados de integracao:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div className="p-8 text-center">Carregando dados de integração...</div>;

  return (
    <div className="p-6 bg-[#f8f9fa] min-h-screen space-y-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-black text-gray-900 tracking-tight">Consumo de API</h1>
            <p className="text-gray-500">Monitore o uso de tokens e chamadas de inteligência artificial</p>
          </div>
          <button 
            onClick={fetchData}
            className="px-4 py-2 bg-white border border-gray-200 rounded-xl font-bold text-sm shadow-sm hover:bg-gray-50 transition-all"
          >
            Atualizar Dados
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-1">Total de Chamadas</p>
            <p className="text-4xl font-black text-indigo-600">{stats?.total_calls.toLocaleString()}</p>
          </div>
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-1">Total de Tokens</p>
            <p className="text-4xl font-black text-emerald-600">{stats?.total_tokens.toLocaleString()}</p>
          </div>
          <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
            <p className="text-xs font-black text-gray-400 uppercase tracking-widest mb-1">Provedores Ativos</p>
            <p className="text-4xl font-black text-amber-500">{Object.keys(stats?.by_provider || {}).length}</p>
          </div>
        </div>

        {/* Providers Breakdown */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden mb-8">
          <div className="px-6 py-4 border-b border-gray-50 bg-gray-50/50">
            <h2 className="font-bold text-gray-800">Uso por Provedor</h2>
          </div>
          <div className="p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(stats?.by_provider || {}).map(([provider, data]) => (
                <div key={provider} className="p-4 bg-gray-50 rounded-xl border border-gray-100">
                  <div className="flex justify-between items-center mb-3">
                    <span className="font-black text-gray-700 uppercase text-xs tracking-wider">{provider}</span>
                    <span className="px-2 py-0.5 bg-white rounded-full text-[10px] font-bold text-gray-400 border border-gray-100">Ativo</span>
                  </div>
                  <div className="space-y-1">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Chamadas:</span>
                      <span className="font-bold text-gray-800">{data.calls}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-500">Tokens:</span>
                      <span className="font-bold text-gray-800">{data.tokens.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* History Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-50 bg-gray-50/50">
            <h2 className="font-bold text-gray-800">Histórico Recente</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50/30 border-b border-gray-100">
                  <th className="p-4 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">Data/Hora</th>
                  <th className="p-4 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">Provedor</th>
                  <th className="p-4 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">Modelo</th>
                  <th className="p-4 text-right text-[10px] font-black text-gray-400 uppercase tracking-widest">Prompt</th>
                  <th className="p-4 text-right text-[10px] font-black text-gray-400 uppercase tracking-widest">Compl.</th>
                  <th className="p-4 text-right text-[10px] font-black text-gray-400 uppercase tracking-widest">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {history.map(row => (
                  <tr key={row.id} className="hover:bg-gray-50/50 transition-all">
                    <td className="p-4 text-sm text-gray-500 font-mono">
                      {new Date(row.created_at).toLocaleString('pt-BR')}
                    </td>
                    <td className="p-4">
                      <span className="px-2 py-1 bg-indigo-50 text-indigo-700 rounded-lg text-[10px] font-black uppercase tracking-wider">
                        {row.provider}
                      </span>
                    </td>
                    <td className="p-4 text-sm font-bold text-gray-700">{row.model || 'N/A'}</td>
                    <td className="p-4 text-right text-sm text-gray-500 font-mono">{row.tokens_prompt}</td>
                    <td className="p-4 text-right text-sm text-gray-500 font-mono">{row.tokens_completion}</td>
                    <td className="p-4 text-right text-sm font-black text-gray-800 font-mono">{row.tokens_total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
