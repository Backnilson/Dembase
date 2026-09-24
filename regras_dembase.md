# Projeto: DemBase - MVP de Controle Financeiro

## 1. Visão Geral
O objetivo é criar um aplicativo de controle financeiro pessoal com frontend em Flet e banco de dados em nuvem usando Supabase. O design deve ser limpo e intuitivo, focado em usabilidade máxima. O diferencial principal é o **sistema de filtros flexíveis de data** (ex: do dia 01 ao dia 23) nos dashboards, abandonando a limitação de meses fechados.

*Nota de Referência:* Existe uma pasta chamada `codigo antigos/` no projeto que contém os protótipos originais. O agente pode consultar esses arquivos para entender a estrutura de opções e campos desejada, **porém**, o novo código deve ser escrito absolutamente do zero, com uma UI/UX superior, sem reutilizar a estrutura do código antigo.

## 2. Escopo do MVP (Minimum Viable Product)
- **Dashboard (Tela Inicial):** Visão geral de receitas, despesas e saldo, com gráficos dinâmicos e espaço para uma frase motivacional.
- **Gestão de Lançamentos:** Formulário limpo, rápido e direto.
- **Cadastros Base (CRUDs Simples):** Telas para gerenciar:
    - **Perfil:** Controle do nome do usuário.
    - **Contas:** (Santander, Itaú, Inter, Dinheiro).
    - **Categorias:** (Alimentação, Transporte, Moradia, Lazer, Saúde, Educação, DJ, Investimento, Outros).
    - **Destinos:** (Eu, Casa, Moto, Carro, DJ, Família, Outros).
- **Histórico:** Lista de lançamentos ordenados por data.

## 3. Lógica de Negócio: Cartão de Crédito
Para otimizar o uso diário, quando a forma de movimentação for "Credito":
1. O sistema exibirá campos perguntando a `parcela_atual` e o `total_parcelas`.
2. **Status Automático:**
   - Se a data do lançamento for no **futuro** (maior que a data atual), o `status` muda para "Pendente".
   - Se a data for **hoje ou no passado**, o `status` muda para "Pago".
   - O campo `status` deve permanecer visível e editável para controle manual do usuário.

## 4. Estrutura de Dados (Supabase - PostgreSQL)
A tabela principal `lancamentos` terá as colunas:
- `id`
- `tipo` (Receita ou Despesa) e `subtipo`
- `forma_movimentacao` (Credito, Debito, Pix, Dinheiro)
- `valor`, `data` (formato AAAA-MM-DD), `hora`
- `conta`, `descricao`, `categoria`, `destino`, `status`
- Exclusivos para crédito: `parcela_atual`, `total_parcelas`, `fatura`

## 5. Diretrizes de Execução (Modo Manual Orquestrado)
O desenvolvimento deste projeto é **orquestrado manualmente pelo usuário**. O agente de IA não deve tentar criar o aplicativo inteiro de uma vez, nem invocar equipes autônomas. 

*   O usuário fornecerá instruções cirúrgicas indicando qual arquivo deve ser criado ou editado (ex: `backend.py` para banco, `main.py` para telas).
*   A lógica de interface (Flet) **nunca** deve se misturar com a lógica de banco de dados (Supabase) no mesmo arquivo, lembrando que a logica deve ocorrer toda no supabase e o flet deve apenas interagir com o supabase deixando o aplicativo leve e rapido.
*   O agente deve aguardar as ordens do usuário para prosseguir entre as etapas de Banco de Dados, Backend, e Frontend.
me retorne sempre em portugues do brasil.