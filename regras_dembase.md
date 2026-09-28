# Projeto: DemBase v2.0 - Controle Financeiro Pessoal Premium

## 1. Visão Geral
O objetivo é criar um aplicativo de controle financeiro pessoal multiplataforma (Android, Web, Desktop) com frontend em **flet** e banco de dados em nuvem usando **Supabase**. O design deve ser premium, minimalista e intuitivo, focado em usabilidade máxima e experiência de alto nível.

### Diferenciais do Sistema:
1. **Sistema de Filtros Flexíveis de Data** — Períodos personalizados (ex: do dia 01 ao dia 23), abandonando a limitação de meses fechados.
2. **Regra 50/30/20** — Cada despesa é classificada em uma das três categorias orçamentárias, com acompanhamento visual em tempo real no Dashboard.
3. **Performance Ultra-leve** — Toda lógica de cálculo ocorre no Supabase (PostgreSQL), o flet apenas consome e exibe.

*Nota de Referência:* As pastas `Codigos_antigos/` e `Codigos_antigos1/` contêm protótipos originais em Python/Flet. Servem apenas como referência para lógica de negócio. O novo código é escrito do zero em Dart.

## 2. Escopo do MVP (Minimum Viable Product)
- **Dashboard (Tela Inicial):** Visão geral de receitas, despesas e saldo, com KPIs, gráficos dinâmicos, barras de progresso da Regra 50/30/20 e espaço para frase motivacional diária.
- **Gestão de Lançamentos:** Formulário limpo, rápido e direto com campos dinâmicos.
- **Cadastros Base (CRUDs Simples):** Telas para gerenciar:
    - **Perfil:** Controle do nome do usuário.
    - **Contas:** (Santander, Itaú, Inter, Dinheiro).
    - **Categorias:** (Alimentação, Transporte, Moradia, Lazer, Saúde, Educação, DJ, Investimento, Outros).
    - **Destinos:** (Eu, Casa, Moto, Carro, DJ, Família, Outros).
- **Histórico:** Lista de lançamentos ordenados por data com filtros flexíveis.

## 3. Lógica de Negócio

### 3.1 Cartão de Crédito (Status Automático)
Quando a forma de movimentação for "Credito":
1. O sistema exibirá campos para `parcela_atual` e `total_parcelas`.
2. **Status Automático (Trigger no Supabase):**
   - Data **futura** → Status = "Pendente"
   - Data **hoje ou no passado** → Status = "Pago"
   - O campo `status` permanece visível e editável para controle manual.

### 3.2 Regra 50/30/20 (NOVO)
Ao registrar uma **despesa**, o usuário DEVE classificá-la em uma das categorias:
- **Essencial (50%)** — Moradia, alimentação, transporte, contas fixas
- **Estilo de Vida (30%)** — Lazer, restaurantes, compras, entretenimento
- **Investimento (20%)** — Poupança, investimentos, cursos, DJ (equipamentos)

O Dashboard exibe barras de progresso comparando o gasto real vs. o orçamento ideal (calculado com base na receita total do período). Para Receitas, o campo `regra` fica NULL.

## 4. Estrutura de Dados (Supabase - PostgreSQL)
A tabela principal `lancamentos` possui:
- `id`, `perfil_id`
- `tipo` (Receita, Despesa), `subtipo`, `forma_movimentacao`
- `conta_id`, `categoria_id`, `destino_id` (foreign keys)
- `valor`, `data`, `hora`, `descricao`, `status`
- **`regra`** (Essencial, Estilo de Vida, Investimento) — NOVO, obrigatório para despesas
- Exclusivos para crédito: `parcela_atual`, `total_parcelas`, `fatura`
- Auditoria: `criado_em`, `atualizado_em`

### RPCs (Funções no PostgreSQL):
- `get_financial_totals(p_data_inicio, p_data_fim)` — Retorna receitas, despesas e saldo
- `get_regra_50_30_20_summary(p_data_inicio, p_data_fim)` — Retorna o resumo da regra por categoria

## 5. Arquitetura Flutter
```
dembase_app/
├── lib/
│   ├── main.dart              → Inicialização (Supabase, dotenv, Riverpod)
│   ├── app.dart               → MaterialApp.router com GoRouter
│   ├── core/
│   │   ├── theme/app_theme.dart    → Design tokens premium
│   │   ├── constants/app_constants.dart → Constantes de negócio
│   │   └── routes/app_router.dart  → Roteamento com guards de auth
│   ├── data/
│   │   ├── services/supabase_service.dart → Wrapper do Supabase
│   │   └── repositories/auth_repository.dart
│   ├── models/
│   │   └── lancamento_model.dart
│   └── presentation/
│       ├── screens/
│       │   ├── auth/login_screen.dart
│       │   └── dashboard/dashboard_screen.dart
│       └── widgets/
│           ├── kpi_card.dart
│           └── date_filter_bar.dart
├── database/
│   └── schema_v2.sql          → Schema completo com regra 50/30/20
└── pubspec.yaml
```

## 6. Diretrizes de Execução
- Desenvolvimento **orquestrado manualmente pelo usuário**.
- A lógica de interface (flet) **nunca** se mistura com a lógica de banco (Supabase) no mesmo arquivo.
- O Flutter deve ser leve: apenas consome dados do Supabase. Cálculos pesados ficam no PostgreSQL via RPCs.
- Retorne sempre em **português do Brasil**.