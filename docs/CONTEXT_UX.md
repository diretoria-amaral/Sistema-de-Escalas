# UI/UX & NAVIGATION STANDARDS

Este documento define a taxonomia dos menus e padrões visuais.

## 1. TAXONOMIA DE MENUS (ORGANIZAÇÃO)
Nenhum item deve ficar solto na raiz do menu (exceto Dashboard). Todo módulo deve ser classificado em:

### A. 📂 CADASTROS (Entities)
Para criação e edição de dados estáticos.
*Exemplos:* Clientes, Quartos, Produtos, Fornecedores.

### B. 📂 PROCESSOS (Operations)
Para ações do dia a dia, fluxos de trabalho e cálculos.
*Exemplos:* Check-in, Convocação de Equipe, Importação de CSV, Fechamento.

### C. 📂 RELATÓRIOS (Analytics)
Para visualização de dados históricos e leitura.
*Exemplos:* Ocupação Mensal, Performance, Logs.

## 2. DECISÃO DE UI (Para a IA)
- Se o usuário pedir "Quero lançar notas", crie a rota em **PROCESSOS**.
- Se o usuário pedir "Quero ver o histórico", crie a rota em **RELATÓRIOS**.

## 3. PADRÕES VISUAIS
- **MainLayout:** Todas as telas devem herdar o layout padrão com Sidebar.
- **Breadcrumbs:** Obrigatório em todas as telas internas (Ex: `Home > Cadastros > Usuários`).
- **Feedback:** Use Toasts/Snackbars para sucesso/erro, nunca `alert()`.