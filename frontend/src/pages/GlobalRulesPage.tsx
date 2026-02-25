import { RulesEditorBase } from '../components/rules/RulesEditorBase';

interface GlobalRulesPageProps {
  ruleType: 'LABOR' | 'SYSTEM';
}

function GlobalRulesPage({ ruleType }: GlobalRulesPageProps) {
  const title = ruleType === 'LABOR' 
    ? 'Regras Trabalhistas (Global)' 
    : 'Regras do Sistema (Global)';
  
  const description = ruleType === 'LABOR'
    ? 'Regras de conformidade com a legislacao trabalhista brasileira (CLT). Aplicam-se a todos os setores e tem a maior precedencia.'
    : 'Regras de sistema que definem comportamentos padrao do agente. Aplicam-se a todos os setores.';

  return (
    <RulesEditorBase 
      ruleType={ruleType}
      showSectorSelector={false}
      title={title}
      description={description}
    />
  );
}

export default GlobalRulesPage;
