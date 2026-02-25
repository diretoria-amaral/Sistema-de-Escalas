import { RulesEditorBase } from '../components/rules/RulesEditorBase';

interface RulesBySectorPageProps {
  ruleType?: 'OPERATIONAL' | 'CALCULATION';
}

function RulesBySectorPage({ ruleType = 'OPERATIONAL' }: RulesBySectorPageProps) {
  const title = ruleType === 'OPERATIONAL' 
    ? 'Regras de Operacao (por Setor)' 
    : 'Regras de Calculo (por Setor)';
  
  const description = ruleType === 'OPERATIONAL'
    ? 'Gerencie as regras operacionais especificas para cada setor. Estas regras definem como as operacoes devem ser executadas.'
    : 'Gerencie as regras de calculo especificas para cada setor. Estas regras definem como os calculos de demanda e programacao sao realizados.';

  return (
    <RulesEditorBase 
      ruleType={ruleType}
      showSectorSelector={true}
      title={title}
      description={description}
    />
  );
}

export default RulesBySectorPage;
