# Projeto: DemBase v2.0 - Controle Financeiro Pessoal Premium

## 1. Visão Geral
O objetivo é criar um aplicativo de controle financeiro pessoal multiplataforma (Android, Web, Desktop) com frontend em **Python (Flet 1.0.1)** e banco de dados em nuvem usando **Supabase**. O design deve ser premium, minimalista e intuitivo, focado em usabilidade máxima e experiência de alto nível.

### Diferenciais do Sistema:
1. **Sistema de Filtros Flexíveis de Data** — Períodos personalizados (ex: do dia 01 ao dia 23), abandonando a limitação de meses fechados.
2. **Regra 50/30/20** — Cada despesa é classificada em uma das três categorias orçamentárias, com acompanhamento visual em tempo real no Dashboard.
3. **Performance Ultra-leve** — Toda lógica de cálculo e agregação ocorre no Supabase (PostgreSQL), o Flet apenas consome e exibe.

*Nota de Referência:* O projeto ativo e oficial está na pasta `dembase_flet/`. As pastas `Codigos_antigos/` e `Codigos_antigos1/` contêm protótipos e versões anteriores arquivadas apenas para consulta de regras de negócio.

## 2. Escopo do MVP (Minimum Viable Product)
- **Dashboard (Tela Inicial):** Visão geral de receitas, despesas e saldo, com KPIs, gráficos dinâmicos, barras de progresso da Regra 50/30/20 e espaço para frase motivacional diária.
- **Gestão de Lançamentos:** Formulário limpo, rápido e direto com campos dinâmicos.
- **Cadastros Base (CRUDs Simples):** Telas para gerenciar:
    - **Perfil:** Controle do nome do usuário.
    - **Contas:** (Santander, Itaú, Inter, Dinheiro).
- **Categorias Universais & Subcategorias (Menu Lateral):**
    - Não há mais divisão ou restrição entre "Receita" e "Despesa". A mesma categoria pode ser usada para ambas (ex: "Investimento" ou "DJ" pode receber entradas e saídas).
    - As categorias padrão são: Alimentação, Transporte, Moradia, Lazer, Saúde, Educação, DJ, Investimento, Outros.
    - **Subcategorias:** Detalham o item (ex: Tipo = Despesa | Categoria = Investimento | Subcategoria = Notebook). Criadas e vinculadas obrigatoriamente a uma Categoria pai.
    - Possui tela própria de gestão no Menu Lateral principal (Sidebar).
    - No formulário de lançamentos, possui botões de criação inline (+) para criar categorias e subcategorias sem sair da tela.
- **Destinos:** Campo descontinuado e eliminado do formulário de lançamentos para simplificar a jornada do usuário.
- **Histórico:** Lista de lançamentos ordenados por data com filtros flexíveis.

## 3. Lógica de Negócio

### 3.1 Cartão de Crédito e Parcelamento Inteligente
Quando a forma de movimentação for "Crédito":
1. O formulário exibe opções de compra parcelada com cálculo dinâmico e bidirecional de parcelas (Total = Parcelas × Valor da Parcela).
2. Campos para `parcela_atual`, `total_parcelas` e `fatura`.
3. **Status Automático (Trigger no Supabase):**
   - Data **futura** → Status = "Pendente"
   - Data **hoje ou no passado** → Status = "Pago"
   - O campo `status` permanece visível e editável para controle manual.

### 3.2 Regra 50/30/20
Ao registrar uma **despesa**, o usuário DEVE classificá-la em uma das categorias:
- **Essencial (50%)** — Moradia, alimentação, transporte, contas fixas
- **Estilo de Vida (30%)** — Lazer, restaurantes, compras, entretenimento
- **Investimento (20%)** — Poupança, investimentos, cursos, DJ (equipamentos)

O Dashboard exibe barras de progresso comparando o gasto real vs. o orçamento ideal (calculado com base na receita total do período). Para Receitas, o campo `regra` fica NULL e não é exibido.

## 4. Estrutura de Dados (Supabase - PostgreSQL)
A tabela principal `lancamentos` possui:
- `id`, `perfil_id`, `user_id`
- `tipo` (Receita, Despesa), `subtipo`, `forma_movimentacao`
- `conta_id`, `categoria_id`, `subcategoria_id` (foreign keys)
- `valor`, `data`, `hora`, `descricao`, `status`
- **`regra`** (Essencial, Estilo de Vida, Investimento) — obrigatório para despesas
- Exclusivos para crédito: `parcela_atual`, `total_parcelas`, `fatura`
- Auditoria: `criado_em`, `atualizado_em`

### RPCs (Funções no PostgreSQL):
- `get_financial_totals(p_data_inicio, p_data_fim)` — Retorna receitas, despesas e saldo
- `get_regra_50_30_20_summary(p_data_inicio, p_data_fim)` — Retorna o resumo da regra por categoria
- `get_dashboard_periodo(p_data_inicio, p_data_fim)` — Pacote consolidado do Dashboard com categorias (`categoria_id`), frequência diária e modalidades
- `get_relatorio_lancamentos(...)` — Relatório geral parametrizado com KPIs, evolução diária, ranking de categorias e paginação
- `get_lista_contas_resumo(p_data_inicio, p_data_fim)` — Lista de contas com saldo atual, previsto e movimentação no período
- `get_relatorio_conta(...)` — Extrato analítico individual de conta com saldo inicial/final do período, transferências enviadas/recebidas e evolução diária do saldo
- `get_relatorio_cartao(...)` — Fatura e extrato analítico individual de cartão de crédito

## 5. Arquitetura do Projeto Ativo (`dembase_flet/`)
```
dembase_flet/
├── main.py                        → Ponto de entrada (Flet 1.0.1 async com ft.run(main))
├── core/
│   ├── constants.py               → Constantes de negócio, paleta e rotas
│   ├── lancamento_state.py        → Máquina de estado, cascatas e validação de lançamentos
│   ├── nav.py                     → Helpers tipados de navegação e drill-down (push_route)
│   ├── periodo.py                 → Estado global do período flexível na sessão
│   ├── recorrencia.py             → Lógica pura de datas (clamping) e parcelas (centavos exatos)
│   ├── report_context.py          → Dataclass imutável ReportContext (serialização URL/query)
│   ├── responsive.py              → Detecção de breakpoints (Mobile vs Desktop)
│   ├── router.py                  → Roteador declarativo com TemplateRoute e pilha page.views
│   ├── storage.py                 → Persistência local e em memória de preferências
│   ├── theme.py                   → Design tokens premium (cores, estilos, bordas)
│   └── window_manager.py          → Responsividade e dimensionamento adaptativo de janelas
├── services/
│   └── supabase_client.py         → ÚNICO ponto de contato com o banco (Auth, CRUD, RPCs)
├── views/
│   ├── auth_view.py               → Autenticação (Login e Cadastro com validação)
│   ├── calendario_view.py         → Calendário financeiro interativo
│   ├── cartoes_view.py            → Gestão de cartões com drill-down para /cartoes/:cartao_id
│   ├── categorias_view.py         → Gestão de categorias e subcategorias
│   ├── config_view.py             → Configurações de perfil, ciclo e gráficos do Dashboard
│   ├── contas_view.py             → Gestão de contas com drill-down para /contas/:conta_id
│   ├── dashboard_view.py          → Dashboard 100% clicável com KPIs, gráficos e regra 50/30/20
│   ├── lancamento_view.py         → Adaptador de rota /lancamento delegando ao modal
│   ├── relatorios_view.py         → Shim delegando para views/relatorios/hub_view.py
│   ├── shell_view.py              → Layout shell persistente com sidebar, botão voltar e período global
│   ├── relatorios/
│   │   ├── registry.py            → Catálogo declarativo de relatórios (RELATORIOS_CATALOGO)
│   │   ├── hub_view.py            → Central de Relatórios (/relatorios)
│   │   ├── lancamentos_report.py  → Relatório Geral de Lançamentos (/relatorios/lancamentos)
│   │   ├── conta_report.py        → Extrato Analítico de Conta (/contas/:conta_id)
│   │   ├── cartao_report.py       → Fatura e Extrato de Cartão (/cartoes/:cartao_id)
│   │   ├── categoria_report.py    → Diagnóstico por Categoria (/relatorios/categoria/:cat_id)
│   │   ├── regra5030_report.py    → Análise por Pilar 50/30/20 (/relatorios/regra/:regra)
│   │   └── fluxo_mensal_report.py → Fluxo de Caixa e Comparativo 6 Meses (/relatorios/fluxo-mensal)
│   └── widgets/
│       ├── clickable_card.py      → Componente reutilizável de card/KPI clicável com hover e ink
│       ├── dashboard_charts.py    → Catálogo modular de 6 gráficos clicáveis do Dashboard
│       ├── lancamento_form.py     → Formulário moderno de lançamentos
│       ├── lancamento_sheet.py    → Hospedeiro modal com pré-seleção contextual (conta/cartão/categoria)
│       ├── regra_5030.py          → Componentes da Regra 50/30/20
│       └── report/                → Componentes modulares de relatórios (header, kpi_strip, filter_bar, transaction_list, scaffold, empty_state)
├── migrations/                    → Scripts SQL de schema, tabelas e RPCs (001 a 008)
└── requirements.txt               → Dependências (flet>=1.0.0, supabase, python-dotenv)
```

## 6. Diretrizes de Execução & Regras Obrigatórias

1. **Atenção à Versão Flet 1.0.1 (Python):**
   - O projeto utiliza a versão **Flet 1.0.1**.
   - Esta versão trouxe **mudanças profundas de sintaxe e de nomenclatura** em relação às versões legadas (0.x), incluindo:
     - Execução assíncrona nativa (`async def main(page: ft.Page)`, `ft.run(main)`).
     - Novas APIs de eventos e animações (`animate=ft.Animation(...)`).
     - Novo tratamento de rotas e navegação.
     - Novos controles e nomes de atributos atualizados.
   - **Sempre consultar e verificar a sintaxe oficial do Flet 1.0.1** antes de implementar ou modificar código. NUNCA utilizar sintaxe obsoleta das versões legadas.

2. **Testar SEMPRE antes de Entregar (Regra Crítica):**
   - **É estritamente obrigatório testar todo o código no terminal antes de entregar qualquer resultado ao usuário.**
   - O agente deve rodar validações de imports, sintaxe, dependências e funcionamento real para assegurar que nada foi quebrado e que a aplicação está pronta para uso.

3. **Separação Rigorosa de Responsabilidades:**
   - A lógica de interface (Flet) **NUNCA** deve se misturar com a lógica de banco de dados (Supabase) no mesmo arquivo.
   - Toda comunicação com o banco ocorre exclusivamente via [`services/supabase_client.py`](file:///c:/Users/Denilson/Documents/GitHub/Dembase/dembase_flet/services/supabase_client.py).
   - Cálculos e agregações pesadas devem ser feitos no PostgreSQL através de RPCs, mantendo o front leve e rápido.

4. **Desenvolvimento Orquestrado:**
   - O desenvolvimento é conduzido de forma modular e orquestrado cirurgicamente pelo usuário.

5. **Idioma:**
   - Toda comunicação, explicações e comentários devem ser em **Português do Brasil**.
