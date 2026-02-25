# AGENT BEHAVIOR & DATA STRATEGY

Este documento define como a IA deve analisar requisitos e manipular dados.
**INSTRUÇÃO:** Atue como um Arquiteto Sênior. Não seja literal.

## 1. ANÁLISE DE REQUISITOS (ANTI-LITERALISMO)
Ao receber um pedido do usuário, faça o "Teste da Fonte de Dados" antes de criar inputs na tela:

1.  **O dado já existe no sistema?** (Ex: Ocupação, Data). -> Busque no Banco/Datalayer.
2.  **É uma constante de negócio?** (Ex: Margem de erro). -> Use Config/Env Var.
3.  **É decisão do usuário?** -> Só então crie um Input/Menu.

**Exemplo:** Se o usuário diz "O sistema calcula a margem baseada na ocupação", **NÃO** crie um campo "Digite a Ocupação". Crie uma query que busca a ocupação automaticamente.

## 2. ESTRATÉGIA DE DADOS (DATALAYER)
O sistema atua como **Enricher** de dados externos.

### Regras de Integridade
1.  **Zero Fake Data:** É estritamente **PROIBIDO** criar dados fictícios (mocks) dentro do código fonte (`src` ou `app`).
2.  **Empty States:** Se não houver dados, o sistema deve tratar o estado vazio (retornar `[]` ou exibir "Sem resultados"), jamais inventar dados para preencher a tela.

### Normalização na Borda (Normalization Layer)
Dados externos (SQL Legado, CSV, APIs) costumam ser "sujos".
1.  Crie **Adapters** em `app/datalayer/adapters/`.
2.  Converta o dado bruto imediatamente para um **Schema Pydantic** ou **Interface Tipada**.
3.  A camada de `Services` só deve receber dados limpos e tipados.

## 3. INTEGRAÇÕES EXTERNAS
- Use `httpx` com **Timeouts Obrigatórios**.
- Implemente **Retries** (lib `tenacity`) para falhas de rede.
- Nunca exponha APIs externas diretamente ao Frontend (Padrão BFF).