import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import './index.css';
import { MainLayout } from './components/common';
import EmployeesPage from './pages/EmployeesPage';
import ActivitiesPage from './pages/ActivitiesPage';
import SchedulePage from './pages/SchedulePage';
import SetupPage from './pages/SetupPage';
import WeeklyParametersPage from './pages/WeeklyParametersPage';
import RulesPage from './pages/RulesPage';
import ReportsPage from './pages/ReportsPage';
import IntelligencePage from './pages/IntelligencePage';
import DataLakePage from './pages/DataLakePage';
import GovernancePage from './pages/GovernancePage';
import PlanejamentoPage from './pages/PlanejamentoPage';
import RolesPage from './pages/RolesPage';
import SectorsPage from './pages/SectorsPage';
import PlaceholderPage from './pages/PlaceholderPage';
import CalendarPage from './pages/CalendarPage';
import ConvocationsPage from './pages/ConvocationsPage';
import HistoricoConvocacoesPage from './pages/HistoricoConvocacoesPage';
import PlanejadoExecutadoPage from './pages/PlanejadoExecutadoPage';
import AuditLogPage from './pages/AuditLogPage';
import SystemStatusPage from './pages/SystemStatusPage';
import DocumentationPage from './pages/DocumentationPage';
import ActivityProgrammingPage from './pages/ActivityProgrammingPage';
import ShiftTemplatesPage from './pages/ShiftTemplatesPage';
import DailySuggestionsPage from './pages/DailySuggestionsPage';
import ConfirmacaoAlteracoesPage from './pages/ConfirmacaoAlteracoesPage';
import PeriodicitiesPage from './pages/PeriodicitiesPage';
import RegrasCalculoPage from './pages/RegrasCalculoPage';
import RulesBySectorPage from './pages/RulesBySectorPage';
import CalculationMemoryPage from './pages/CalculationMemoryPage';
import GlobalRulesPage from './pages/GlobalRulesPage';
import WorkShiftManagement from './pages/WorkShiftManagement';
import ApiIntegrationPage from './pages/ApiIntegrationPage';

function App() {
  return (
    <Router>
      <MainLayout>
        <Routes>
          {/* Cadastros */}
          <Route path="/cadastros/funcoes" element={<RolesPage />} />
          <Route path="/cadastros/regimes" element={
            <PlaceholderPage 
              title="Regimes de Trabalho" 
              description="Cadastro de regimes de trabalho (CLT, Intermitente, etc.)"
              section="Cadastros"
            />
          } />
          <Route path="/cadastros/tipos-relatorio" element={
            <PlaceholderPage 
              title="Tipos de Relatorios" 
              description="Configuracao dos tipos de relatorios aceitos pelo sistema (HP, Checkin, Checkout, etc.)"
              section="Cadastros"
            />
          } />
          <Route path="/colaboradores" element={<EmployeesPage />} />
          <Route path="/cadastros/setores" element={<SectorsPage />} />
          <Route path="/atividades" element={<ActivitiesPage />} />
          <Route path="/cadastros/periodicidades" element={<PeriodicitiesPage />} />
          <Route path="/cadastros/regras-setor" element={<RulesBySectorPage />} />
          <Route path="/cadastros/turnos" element={<WorkShiftManagement />} />
          
          {/* Regras Hierarquicas */}
          <Route path="/regras/trabalhistas-global" element={<GlobalRulesPage ruleType="LABOR" />} />
          <Route path="/regras/sistema-global" element={<GlobalRulesPage ruleType="SYSTEM" />} />
          <Route path="/regras/operacao-setor" element={<RulesBySectorPage ruleType="OPERATIONAL" />} />
          <Route path="/regras/calculo-setor" element={<RulesBySectorPage ruleType="CALCULATION" />} />
          
          {/* Operacao (Processos) */}
          <Route path="/operacao/calendario" element={<CalendarPage />} />
          <Route path="/regras" element={<RulesPage />} />
          <Route path="/operacao/regras-calculo" element={<RegrasCalculoPage />} />
          <Route path="/parametros" element={<WeeklyParametersPage />} />
          <Route path="/operacao/programacao" element={<ActivityProgrammingPage />} />
          <Route path="/operacao/turnos" element={<ShiftTemplatesPage />} />
          <Route path="/planejamento" element={<PlanejamentoPage />} />
          <Route path="/escalas" element={<SchedulePage />} />
          <Route path="/operacao/confirmacao" element={<ConfirmacaoAlteracoesPage />} />
          <Route path="/operacao/convocacoes" element={<ConvocationsPage />} />
          <Route path="/operacao/sugestoes" element={<DailySuggestionsPage />} />
          <Route path="/governanca" element={<GovernancePage />} />
          
          {/* Inteligencia (Relatorios) */}
          <Route path="/data-lake" element={<DataLakePage />} />
          <Route path="/relatorios" element={<ReportsPage />} />
          <Route path="/relatorios/memoria-calculo" element={<CalculationMemoryPage />} />
          <Route path="/inteligencia" element={<IntelligencePage />} />
          <Route path="/inteligencia/estatisticas" element={
            <PlaceholderPage 
              title="Estatisticas por Setor" 
              description="Visualizacao de estatisticas consolidadas por setor: EWMA de bias, distribuicao horaria, tendencias."
              section="Inteligencia"
            />
          } />
          
          {/* Consultas/Historicos */}
          <Route path="/consultas/historico-convocacoes" element={<HistoricoConvocacoesPage />} />
          <Route path="/consultas/planejado-executado" element={<PlanejadoExecutadoPage />} />
          <Route path="/consultas/projecao-real" element={
            <PlaceholderPage 
              title="Projecao x Real" 
              description="Comparativo entre valores projetados (forecast) e realizados para analise de desvios."
              section="Consultas"
            />
          } />
          <Route path="/consultas/audit-log" element={<AuditLogPage />} />
          <Route path="/consultas/governanca-quartos" element={
            <PlaceholderPage 
              title="Vagos Sujos x Estadias" 
              description="Analise diaria de quartos vagos sujos e estadias para dimensionamento de equipe."
              section="Consultas"
            />
          } />
          <Route path="/consultas/checkins-checkouts" element={
            <PlaceholderPage 
              title="Checkins/Checkouts por Hora" 
              description="Distribuicao horaria de checkins e checkouts para otimizacao de turnos."
              section="Consultas"
            />
          } />
          <Route path="/consultas/intervalo-arrumacao" element={
            <PlaceholderPage 
              title="Intervalo para Arrumacao" 
              description="Analise do intervalo disponivel entre checkout e checkin para arrumacao de quartos."
              section="Consultas"
            />
          } />
          <Route path="/consultas/manutencao" element={
            <PlaceholderPage 
              title="Manutencao Corretiva" 
              description="Historico de manutencoes corretivas por dia para planejamento de equipe de manutencao."
              section="Consultas"
            />
          } />
          <Route path="/consultas/produtividade" element={
            <PlaceholderPage 
              title="Produtividade por Camareira" 
              description="Indicadores de produtividade individual: quartos/hora, tempo medio, qualidade."
              section="Consultas"
            />
          } />
          
          {/* Configuracao */}
          <Route path="/configuracao" element={<SetupPage />} />
          <Route path="/configuracao/status" element={<SystemStatusPage />} />
          <Route path="/configuracao/integracao" element={<ApiIntegrationPage />} />
          <Route path="/configuracao/documentacao" element={<DocumentationPage />} />
          
          {/* Default route */}
          <Route path="/" element={<EmployeesPage />} />
          <Route path="*" element={<EmployeesPage />} />
        </Routes>
      </MainLayout>
    </Router>
  );
}

export default App;
