import { Link, useLocation } from 'react-router-dom';

interface BreadcrumbItem {
  label: string;
  path?: string;
}

interface BreadcrumbProps {
  items?: BreadcrumbItem[];
}

const pathLabels: Record<string, string> = {
  'cadastros': 'Cadastros',
  'funcoes': 'Funções',
  'setores': 'Setores',
  'colaboradores': 'Colaboradores',
  'atividades': 'Atividades',
  'operacao': 'Operação',
  'calendario': 'Calendário Anual',
  'programacao': 'Programação de Atividades',
  'turnos': 'Turnos/Templates',
  'confirmacao': 'Confirmação e Alterações',
  'convocacoes': 'Convocações',
  'sugestoes': 'Sugestões Diárias',
  'inteligencia': 'Inteligência',
  'relatorios': 'Relatórios',
  'data-lake': 'Data Lake',
  'consultas': 'Consultas/Históricos',
  'historico-convocacoes': 'Histórico de Convocações',
  'planejado-executado': 'Planejado x Executado',
  'audit-log': 'Log de Auditoria',
  'configuracao': 'Configuração',
  'status': 'Status do Sistema',
  'documentacao': 'Documentação',
  'regras': 'Regras',
  'trabalhistas': 'Trabalhistas (Global)',
  'operacionais': 'Operacionais (por Setor)',
  'parametros': 'Parâmetros Semanais',
  'planejamento': 'Planejamento Semanal',
  'escalas': 'Gerar Escala Sugestiva',
  'governanca': 'Governança',
};

export default function Breadcrumb({ items }: BreadcrumbProps) {
  const location = useLocation();
  
  const generateBreadcrumbs = (): BreadcrumbItem[] => {
    if (items) return items;
    
    const pathParts = location.pathname.split('/').filter(Boolean);
    const breadcrumbs: BreadcrumbItem[] = [{ label: 'Home', path: '/' }];
    
    let currentPath = '';
    pathParts.forEach((part, index) => {
      currentPath += `/${part}`;
      const label = pathLabels[part] || part.charAt(0).toUpperCase() + part.slice(1);
      
      if (index === pathParts.length - 1) {
        breadcrumbs.push({ label });
      } else {
        breadcrumbs.push({ label, path: currentPath });
      }
    });
    
    return breadcrumbs;
  };

  const breadcrumbs = generateBreadcrumbs();

  if (breadcrumbs.length <= 1) return null;

  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      <ol className="breadcrumb-list">
        {breadcrumbs.map((item, index) => (
          <li key={index} className="breadcrumb-item">
            {item.path ? (
              <Link to={item.path} className="breadcrumb-link">
                {item.label}
              </Link>
            ) : (
              <span className="breadcrumb-current">{item.label}</span>
            )}
            {index < breadcrumbs.length - 1 && (
              <span className="breadcrumb-separator">/</span>
            )}
          </li>
        ))}
      </ol>
    </nav>
  );
}
