import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';

interface MenuItem {
  path: string;
  label: string;
  placeholder?: boolean;
}

interface MenuSection {
  title: string;
  icon: string;
  items: MenuItem[];
}

const menuStructure: MenuSection[] = [
  {
    title: 'Cadastros',
    icon: '📋',
    items: [
      { path: '/cadastros/funcoes', label: 'Funcoes (Roles)' },
      { path: '/cadastros/regimes', label: 'Regimes de Trabalho', placeholder: true },
      { path: '/cadastros/tipos-relatorio', label: 'Tipos de Relatorios', placeholder: true },
      { path: '/colaboradores', label: 'Colaboradores' },
      { path: '/cadastros/setores', label: 'Setores' },
      { path: '/atividades', label: 'Atividades' },
      { path: '/cadastros/periodicidades', label: 'Periodicidades' },
      { path: '/cadastros/turnos', label: 'Turnos de Trabalho' },
      { path: '/regras/trabalhistas-global', label: 'Regras Trabalhistas (Global)' },
      { path: '/regras/sistema-global', label: 'Regras do Sistema (Global)' },
      { path: '/regras/operacao-setor', label: 'Regras de Operacao (por Setor)' },
      { path: '/regras/calculo-setor', label: 'Regras de Calculo (por Setor)' },
    ]
  },
  {
    title: 'Operacao',
    icon: '⚙️',
    items: [
      { path: '/operacao/calendario', label: 'Calendario Anual' },
      { path: '/parametros', label: 'Parametros Semanais' },
      { path: '/operacao/programacao', label: 'Programacao Atividades' },
      { path: '/operacao/turnos', label: 'Turnos/Templates', placeholder: true },
      { path: '/planejamento', label: 'Planejamento Semanal' },
      { path: '/escalas', label: 'Gerar Escala Sugestiva' },
      { path: '/governanca', label: 'Governanca (Demanda/Escala)' },
      { path: '/operacao/confirmacao', label: 'Confirmacao/Alteracoes', placeholder: true },
      { path: '/operacao/convocacoes', label: 'Convocacoes' },
      { path: '/operacao/sugestoes', label: 'Sugestoes Diarias', placeholder: true },
    ]
  },
  {
    title: 'Inteligencia',
    icon: '🧠',
    items: [
      { path: '/data-lake', label: 'Upload de Relatorios' },
      { path: '/relatorios', label: 'Relatorios Processados' },
      { path: '/relatorios/memoria-calculo', label: 'Memoria de Calculo' },
      { path: '/inteligencia', label: 'Painel Inteligencia' },
      { path: '/inteligencia/estatisticas', label: 'Estatisticas por Setor', placeholder: true },
    ]
  },
  {
    title: 'Consultas/Historicos',
    icon: '📊',
    items: [
      { path: '/consultas/historico-convocacoes', label: 'Historico Convocacoes' },
      { path: '/consultas/planejado-executado', label: 'Planejado x Executado' },
      { path: '/consultas/projecao-real', label: 'Projecao x Real', placeholder: true },
      { path: '/consultas/audit-log', label: 'Log de Auditoria' },
      { path: '/consultas/governanca-quartos', label: 'Vagos/Sujos x Estadias', placeholder: true },
      { path: '/consultas/checkins-checkouts', label: 'Checkins/Checkouts por Hora', placeholder: true },
      { path: '/consultas/intervalo-arrumacao', label: 'Intervalo Arrumacao', placeholder: true },
      { path: '/consultas/manutencao', label: 'Manutencao Corretiva', placeholder: true },
      { path: '/consultas/produtividade', label: 'Produtividade Camareira', placeholder: true },
    ]
  },
  {
    title: 'Configuracao',
    icon: '🔧',
    items: [
      { path: '/configuracao', label: 'Configuracao Geral' },
      { path: '/configuracao/status', label: 'Status do Sistema' },
      { path: '/configuracao/integracao', label: 'Integracao' },
      { path: '/configuracao/documentacao', label: 'Como o Sistema Decide' },
    ]
  }
];

function Sidebar() {
  const location = useLocation();
  const [expandedSections, setExpandedSections] = useState<string[]>(['Cadastros', 'Operacao', 'Inteligencia', 'Consultas/Historicos', 'Configuracao']);

  const toggleSection = (title: string) => {
    setExpandedSections(prev => 
      prev.includes(title) 
        ? prev.filter(s => s !== title)
        : [...prev, title]
    );
  };

  const isActive = (path: string) => {
    return location.pathname === path || location.pathname.startsWith(path + '/');
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2>Sistema de Escalas</h2>
        <p>Housekeeping</p>
      </div>
      
      <nav className="sidebar-nav">
        {menuStructure.map(section => (
          <div key={section.title} className="sidebar-section">
            <div 
              className="sidebar-section-header"
              onClick={() => toggleSection(section.title)}
            >
              <span className="sidebar-section-icon">{section.icon}</span>
              <span className="sidebar-section-title">{section.title}</span>
              <span className="sidebar-section-arrow">
                {expandedSections.includes(section.title) ? '▼' : '▶'}
              </span>
            </div>
            
            {expandedSections.includes(section.title) && (
              <div className="sidebar-section-items">
                {section.items.map(item => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive: navIsActive }) => 
                      `sidebar-item ${navIsActive || isActive(item.path) ? 'active' : ''} ${item.placeholder ? 'placeholder' : ''}`
                    }
                  >
                    {item.label}
                    {item.placeholder && <span className="badge-soon">Em breve</span>}
                  </NavLink>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>
    </div>
  );
}

export default Sidebar;
