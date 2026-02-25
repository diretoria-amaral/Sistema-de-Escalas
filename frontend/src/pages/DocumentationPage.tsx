import { useState, useEffect } from 'react';
import { apiClient } from '../services/client';

interface DecisionStep {
  step: number;
  name: string;
  description: string;
  details: string[];
}

interface Documentation {
  title: string;
  version: string;
  generated_at: string;
  work_regime: { mode: string; description: string };
  decision_flow: DecisionStep[];
  current_parameters: {
    labor_rules: Record<string, number | boolean>;
    intermittent_guardrails: Record<string, number | boolean>;
  };
  audit_trail: string;
}

interface ParserVersion {
  parser_name: string;
  version: string;
  method_version: string | null;
  description?: string;
}

export default function DocumentationPage() {
  const [loading, setLoading] = useState(true);
  const [docs, setDocs] = useState<Documentation | null>(null);
  const [parsers, setParsers] = useState<ParserVersion[]>([]);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [docsRes, parsersRes] = await Promise.all([
        apiClient.get('/compliance/how-system-decides'),
        apiClient.get('/compliance/parser-versions')
      ]);
      setDocs(docsRes.data);
      setParsers(parsersRes.data.parsers || []);
    } catch (error) {
      console.error('Error loading documentation:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '20px' }}>Carregando documentacao...</div>;
  }

  if (!docs) {
    return <div style={{ padding: '20px' }}>Erro ao carregar documentacao.</div>;
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1000px' }}>
      <h1>{docs.title}</h1>
      <p style={{ color: '#6b7280' }}>
        Versao {docs.version} | Gerado em: {new Date(docs.generated_at).toLocaleString('pt-BR')}
      </p>

      <div style={{ 
        padding: '15px', 
        backgroundColor: '#fef3c7', 
        borderRadius: '8px', 
        marginBottom: '30px',
        border: '1px solid #f59e0b'
      }}>
        <strong>Regime de Trabalho: {docs.work_regime.mode}</strong>
        <p style={{ margin: '10px 0 0 0', fontSize: '14px' }}>{docs.work_regime.description}</p>
      </div>

      <h2>Fluxo de Decisao</h2>
      <p style={{ color: '#6b7280', marginBottom: '20px' }}>
        Passo a passo de como o sistema processa dados e toma decisoes:
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginBottom: '40px' }}>
        {docs.decision_flow.map((step, idx) => (
          <div key={idx} style={{ 
            display: 'flex', 
            gap: '20px',
            padding: '20px',
            backgroundColor: '#f8fafc',
            borderRadius: '8px',
            borderLeft: '4px solid #3b82f6'
          }}>
            <div style={{ 
              width: '40px', 
              height: '40px', 
              borderRadius: '50%', 
              backgroundColor: '#3b82f6',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 'bold',
              flexShrink: 0
            }}>
              {step.step}
            </div>
            <div>
              <h4 style={{ margin: '0 0 8px 0' }}>{step.name}</h4>
              <p style={{ margin: '0 0 10px 0', color: '#374151' }}>{step.description}</p>
              <ul style={{ margin: 0, paddingLeft: '20px', fontSize: '14px', color: '#6b7280' }}>
                {step.details.map((detail, dIdx) => (
                  <li key={dIdx} style={{ marginBottom: '4px' }}>{detail}</li>
                ))}
              </ul>
            </div>
          </div>
        ))}
      </div>

      <h2>Parametros Atuais</h2>
      
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '20px', marginBottom: '40px' }}>
        <div style={{ backgroundColor: '#f8fafc', padding: '20px', borderRadius: '8px' }}>
          <h4 style={{ marginTop: 0, color: '#0369a1' }}>Regras Trabalhistas</h4>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              {Object.entries(docs.current_parameters.labor_rules).map(([key, value]) => (
                <tr key={key}>
                  <td style={{ padding: '6px 0' }}>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</td>
                  <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 'bold' }}>
                    {typeof value === 'boolean' ? (value ? 'Sim' : 'Nao') : value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ backgroundColor: '#f8fafc', padding: '20px', borderRadius: '8px' }}>
          <h4 style={{ marginTop: 0, color: '#0369a1' }}>Guardrails Intermitente</h4>
          <table style={{ width: '100%', fontSize: '14px' }}>
            <tbody>
              {Object.entries(docs.current_parameters.intermittent_guardrails).map(([key, value]) => (
                <tr key={key}>
                  <td style={{ padding: '6px 0' }}>{key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:</td>
                  <td style={{ padding: '6px 0', textAlign: 'right', fontWeight: 'bold' }}>
                    {typeof value === 'boolean' ? (value ? 'Sim' : 'Nao') : value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <h2>Versoes dos Parsers</h2>
      <p style={{ color: '#6b7280', marginBottom: '15px' }}>
        Versoes dos processadores de dados do Data Lake:
      </p>
      
      <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '40px' }}>
        <thead>
          <tr style={{ backgroundColor: '#f3f4f6' }}>
            <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Parser</th>
            <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Versao</th>
            <th style={{ padding: '12px', textAlign: 'left', borderBottom: '1px solid #e5e7eb' }}>Metodo</th>
          </tr>
        </thead>
        <tbody>
          {parsers.map((parser, idx) => (
            <tr key={idx} style={{ borderBottom: '1px solid #e5e7eb' }}>
              <td style={{ padding: '12px' }}>{parser.parser_name}</td>
              <td style={{ padding: '12px' }}>
                <span style={{ 
                  padding: '2px 8px', 
                  backgroundColor: '#e0f2fe', 
                  borderRadius: '4px',
                  fontSize: '13px'
                }}>
                  v{parser.version}
                </span>
              </td>
              <td style={{ padding: '12px', color: '#6b7280' }}>{parser.method_version || '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ 
        padding: '15px', 
        backgroundColor: '#ecfdf5', 
        borderRadius: '8px',
        border: '1px solid #10b981'
      }}>
        <strong style={{ color: '#10b981' }}>Rastreabilidade</strong>
        <p style={{ margin: '10px 0 0 0', fontSize: '14px' }}>{docs.audit_trail}</p>
      </div>

      <div style={{ marginTop: '40px', padding: '20px', backgroundColor: '#f3f4f6', borderRadius: '8px' }}>
        <h3 style={{ marginTop: 0 }}>Legislacao Aplicavel</h3>
        <ul style={{ marginBottom: 0 }}>
          <li><strong>CLT Art. 452-A</strong> - Contrato de Trabalho Intermitente</li>
          <li><strong>Antecedencia minima:</strong> 72 horas para convocacao</li>
          <li><strong>Prazo de resposta:</strong> 24 horas apos recebimento</li>
          <li><strong>Limite semanal:</strong> 44 horas (sem hora extra)</li>
          <li><strong>Descanso entre turnos:</strong> 11 horas minimas</li>
        </ul>
      </div>
    </div>
  );
}
