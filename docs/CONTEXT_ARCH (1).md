# MASTER ARCHITECTURE & STANDARDS

Este documento define a infraestrutura e os padrões de código do projeto.
**INSTRUÇÃO:** A IA deve seguir estritamente a estrutura de pastas e as regras de nomenclatura abaixo.

## 1. INFRAESTRUTURA (DOCKER COMPOSE)
O projeto roda em 3 containers orquestrados.
1.  **db:** PostgreSQL 16 (Dados persistentes).
2.  **api:** Backend FastAPI. **ISOLADO** (Sem portas expostas ao host).
3.  **frontend:** React + Nginx. Atua como **Reverse Proxy**.

### Regra de Proxy Reverso (Nginx)
A API nunca é acessada diretamente. O Frontend chama `/api/...` e o Nginx redireciona internamente.
- **Frontend URL:** Relativa (`/api/users`) ou vazia. Nunca `http://localhost:8000`.

## 2. BACKEND (PYTHON / FASTAPI)
**Padrão:** MVC com separação de Services.

### Estrutura de Pastas
- `app/models/`: ORM (SQLAlchemy/SQLModel).
- `app/schemas/`: Pydantic Models (DTOs de Input/Output).
- `app/routers/`: Controllers (Recebem HTTP -> Chamam Service -> Retornam Response).
- `app/services/`: Regra de Negócio Pura (Sem dependência de HTTP).
- `app/clients/`: Integração com APIs externas (Com Timeouts e Retries).
- `app/datalayer/`: Adapters para leitura de dados (Ver CONTEXT_BEHAVIOR.md).
- `alembic/`: Configurações e versões de migração.

### Banco de Dados (PostgreSQL 16)

#### A. Regra de Tradução (Banco vs Código)
- **Banco de Dados:** Tabelas e Colunas em **PORTUGUÊS** (snake_case).
- **Código Python:** Classes e Atributos em **INGLÊS** (PascalCase/snake_case).
- *Ex:* Tabela `pedido_compra` -> Classe `PurchaseOrder`.

#### B. Gestão de Schema (Migrations - CRÍTICO)
Todo controle de versão do banco é feito via **Alembic**.
1.  **Imutabilidade:** NUNCA edite um arquivo de migration (`versions/*.py`) que já foi criado ou aplicado anteriormente em outro ambiente.
2.  **Fluxo de Alteração:** Se precisar adicionar, remover ou editar um campo em uma tabela já existente:
    - Modifique o Model Python (`models/`).
    - Gere uma **NOVA migration** de alteração (`alembic revision --autogenerate -m "add_column_x"`).
    - **Proibido:** Jamais tente "corrigir" a migration antiga (exceto se for o dev inicial local). Em produção, a evolução deve ser linear via novas migrations.

## 3. FRONTEND (REACT)
**Padrão:** Functional Components + Hooks.

### Estrutura de Pastas
- `src/components/common/`: UI Reutilizável (Botões, Inputs).
- `src/pages/`: Telas vinculadas a rotas.
- `src/hooks/`: Lógica de estado e regras de tela.
- `src/services/`: Chamadas API (Axios).

## 4. GOVERNANÇA (PROIBIÇÕES)
1.  **Não crie arquivos lixo:** Nada de `teste.py`, `temp.json` ou scripts na raiz.
2.  **Testes:** Apenas nas pastas `tests/` (Backend) ou `__tests__/` (Frontend).
3.  **Secrets:** Nunca hardcoded. Use variáveis de ambiente.