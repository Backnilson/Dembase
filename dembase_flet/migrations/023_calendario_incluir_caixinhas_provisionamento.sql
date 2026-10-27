-- =============================================================================
-- MIGRAÇÃO 023: Inclusão de Caixinhas de Teto (Provisionamento) no Calendário Financeiro
-- =============================================================================
-- Permite que lançamentos de provisionamento das caixinhas (subtipo = 'Provisionamento',
-- status = 'Pendente' ou 'Pago') entrem no fluxo de caixa diário e projetado do calendário,
-- garantindo que compromissos reais futuros (como Aluguel, Moto, etc.) sejam visualizados
-- e computados no saldo acumulado do período.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_calendario_financeiro_mes(
  p_mes         SMALLINT,
  p_ano         SMALLINT,
  p_data_inicio DATE DEFAULT NULL,
  p_data_fim    DATE DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_user_id     UUID := COALESCE(auth.uid(), (SELECT user_id FROM public.lancamentos LIMIT 1));
  v_inicio_mes  DATE := make_date(p_ano::INT, p_mes::INT, 1);
  v_fim_mes     DATE := (v_inicio_mes + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  v_d_ini       DATE := COALESCE(p_data_inicio, v_inicio_mes);
  v_d_fim       DATE := COALESCE(p_data_fim, v_fim_mes);
  v_base_ini    DATE := LEAST(v_inicio_mes, v_d_ini);
  v_base_fim    DATE := GREATEST(v_fim_mes, v_d_fim);
  v_grid_inicio DATE := v_base_ini - (EXTRACT(DOW FROM v_base_ini)::INT);
  v_grid_fim    DATE := GREATEST(
                          v_grid_inicio + 41,
                          v_base_fim + (6 - EXTRACT(DOW FROM v_base_fim)::INT)
                        );
  v_kpis        JSON;
  v_dias        JSON;
  v_faturas     JSON;
  v_desp_cat    JSON;
  v_rec_cat     JSON;
  v_tot_desp    NUMERIC := 0;
  v_tot_rec     NUMERIC := 0;
BEGIN
  IF v_d_fim < v_d_ini THEN
    v_d_fim := v_d_ini;
  END IF;

  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva,
      cat.nome  AS cat_nome,
      cat.cor   AS cat_cor,
      cat.icone AS cat_icone,
      sub.nome  AS sub_nome,
      cta.nome  AS cta_nome,
      crt.nome  AS crt_nome,
      crt.cor   AS crt_cor,
      cx.nome   AS caixinha_nome,
      cx.cor    AS caixinha_cor,
      cx.icone  AS caixinha_icone
    FROM public.lancamentos l
    LEFT JOIN public.faturas f          ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c          ON c.id = l.cartao_id
    LEFT JOIN public.categorias cat     ON cat.id = l.categoria_id
    LEFT JOIN public.subcategorias sub  ON sub.id = l.subcategoria_id
    LEFT JOIN public.contas cta         ON cta.id = l.conta_id
    LEFT JOIN public.cartoes crt        ON crt.id = l.cartao_id
    LEFT JOIN public.caixinhas_teto cx  ON cx.id = l.caixinha_id
    WHERE l.user_id = v_user_id
  )
  SELECT
    COALESCE(SUM(CASE WHEN le.tipo = 'Receita' THEN le.valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' THEN le.valor ELSE 0 END), 0)
  INTO v_tot_rec, v_tot_desp
  FROM lancs_efetivos le
  WHERE le.data_efetiva BETWEEN v_d_ini AND v_d_fim;

  -- 1. KPIs consolidados do período [v_d_ini .. v_d_fim] usando data_efetiva (incluindo provisões de caixinhas)
  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva
    FROM public.lancamentos l
    LEFT JOIN public.faturas f ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c ON c.id = l.cartao_id
    WHERE l.user_id = v_user_id
  )
  SELECT JSON_BUILD_OBJECT(
    'receitas_mes',        v_tot_rec,
    'despesas_mes',        v_tot_desp,
    'resultado_mes',       (v_tot_rec - v_tot_desp),
    'despesas_conta_mes',  COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NULL THEN le.valor ELSE 0 END), 0),
    'despesas_cartao_mes', COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NOT NULL THEN le.valor ELSE 0 END), 0),
    'dias_com_saida',      COUNT(DISTINCT CASE WHEN le.tipo = 'Despesa' AND le.valor > 0 THEN le.data_efetiva END),
    'dias_com_entrada',    COUNT(DISTINCT CASE WHEN le.tipo = 'Receita' AND le.valor > 0 THEN le.data_efetiva END),
    'qtd_lancamentos_mes', COUNT(le.id),
    'maior_saida_dia',     COALESCE((
      SELECT MAX(soma_d) FROM (
        SELECT SUM(le2.valor) AS soma_d
        FROM lancs_efetivos le2
        WHERE le2.data_efetiva BETWEEN v_d_ini AND v_d_fim
          AND le2.tipo = 'Despesa'
        GROUP BY le2.data_efetiva
      ) s
    ), 0)
  )
  INTO v_kpis
  FROM lancs_efetivos le
  WHERE le.data_efetiva BETWEEN v_d_ini AND v_d_fim;

  -- 2. Agregação por Dia cobrindo toda a grade (v_grid_inicio .. v_grid_fim) usando data_efetiva
  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva,
      cat.nome  AS cat_nome,
      cat.cor   AS cat_cor,
      cat.icone AS cat_icone,
      sub.nome  AS sub_nome,
      cta.nome  AS cta_nome,
      crt.nome  AS crt_nome,
      crt.cor   AS crt_cor,
      cx.nome   AS caixinha_nome,
      cx.cor    AS caixinha_cor,
      cx.icone  AS caixinha_icone
    FROM public.lancamentos l
    LEFT JOIN public.faturas f          ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c          ON c.id = l.cartao_id
    LEFT JOIN public.categorias cat     ON cat.id = l.categoria_id
    LEFT JOIN public.subcategorias sub  ON sub.id = l.subcategoria_id
    LEFT JOIN public.contas cta         ON cta.id = l.conta_id
    LEFT JOIN public.cartoes crt        ON crt.id = l.cartao_id
    LEFT JOIN public.caixinhas_teto cx  ON cx.id = l.caixinha_id
    WHERE l.user_id = v_user_id
  )
  SELECT COALESCE(JSON_AGG(row_dia ORDER BY row_dia.data), '[]'::JSON)
  INTO v_dias
  FROM (
    SELECT
      le.data_efetiva::TEXT AS data,
      EXTRACT(DAY FROM le.data_efetiva)::INT AS dia,
      EXTRACT(MONTH FROM le.data_efetiva)::INT AS mes,
      EXTRACT(YEAR FROM le.data_efetiva)::INT AS ano,
      (le.data_efetiva BETWEEN v_inicio_mes AND v_fim_mes) AS no_mes_atual,
      (le.data_efetiva BETWEEN v_d_ini AND v_d_fim) AS no_periodo_filtro,
      COALESCE(SUM(CASE WHEN le.tipo = 'Receita' THEN le.valor ELSE 0 END), 0) AS total_receitas,
      COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' THEN le.valor ELSE 0 END), 0) AS total_despesas,
      COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NULL THEN le.valor ELSE 0 END), 0) AS despesas_conta,
      COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NOT NULL THEN le.valor ELSE 0 END), 0) AS despesas_cartao,
      COUNT(le.id)::INT AS qtd_lancamentos,
      JSON_AGG(
        JSON_BUILD_OBJECT(
          'id', le.id,
          'data', le.data_efetiva::TEXT,
          'data_compra', le.data::TEXT,
          'hora', le.hora,
          'tipo', le.tipo,
          'subtipo', le.subtipo,
          'valor', le.valor,
          'descricao', le.descricao,
          'status', le.status,
          'regra', le.regra,
          'forma_movimentacao', le.forma_movimentacao,
          'parcela_atual', le.parcela_atual,
          'total_parcelas', le.total_parcelas,
          'fatura', le.fatura,
          'fatura_id', le.fatura_id,
          'conta_id', le.conta_id,
          'cartao_id', le.cartao_id,
          'caixinha_id', le.caixinha_id,
          'caixinha_nome', le.caixinha_nome,
          'caixinha_cor', le.caixinha_cor,
          'caixinha_icone', le.caixinha_icone,
          'categoria_id', le.categoria_id,
          'subcategoria_id', le.subcategoria_id,
          'categoria_nome', COALESCE(le.cat_nome, 'Sem Categoria'),
          'categoria_cor', COALESCE(le.cat_cor, '#64748B'),
          'categoria_icone', COALESCE(le.cat_icone, 'category'),
          'subcategoria_nome', le.sub_nome,
          'conta_nome', le.cta_nome,
          'cartao_nome', le.crt_nome,
          'cartao_cor', le.crt_cor
        ) ORDER BY le.hora DESC NULLS LAST, le.criado_em DESC
      ) AS lancamentos
    FROM lancs_efetivos le
    WHERE le.data_efetiva BETWEEN v_grid_inicio AND v_grid_fim
    GROUP BY le.data_efetiva
  ) row_dia;

  -- 3. Faturas e Cartões cujos vencimentos caem na grade ou pertencem ao mês de referência
  SELECT COALESCE(JSON_AGG(row_cart ORDER BY row_cart.data_vencimento, row_cart.cartao_nome), '[]'::JSON)
  INTO v_faturas
  FROM (
    SELECT
      c.id AS cartao_id,
      c.nome AS cartao_nome,
      c.bandeira,
      c.cor AS cartao_cor,
      c.icone AS cartao_icone,
      c.limite_total,
      c.limite_disponivel,
      c.dia_fechamento,
      c.dia_vencimento,
      f.id AS fatura_id,
      f.mes AS fatura_mes,
      f.ano AS fatura_ano,
      COALESCE(
        f.data_vencimento,
        make_date(
          p_ano::INT,
          p_mes::INT,
          LEAST(COALESCE(c.dia_vencimento, 10)::INT, EXTRACT(DAY FROM v_fim_mes)::INT)
        )
      )::TEXT AS data_vencimento,
      EXTRACT(DAY FROM COALESCE(
        f.data_vencimento,
        make_date(
          p_ano::INT,
          p_mes::INT,
          LEAST(COALESCE(c.dia_vencimento, 10)::INT, EXTRACT(DAY FROM v_fim_mes)::INT)
        )
      ))::INT AS dia_vencimento_efetivo,
      COALESCE(f.valor_total, 0) AS valor_total,
      COALESCE(f.valor_pago, 0) AS valor_pago,
      CASE
        WHEN COALESCE(f.valor_total, 0) <= 0.01 THEN 'paga'
        ELSE COALESCE(f.status, 'aberta')
      END AS status
    FROM public.cartoes c
    LEFT JOIN public.faturas f
      ON f.cartao_id = c.id
     AND (
       (f.data_vencimento BETWEEN v_grid_inicio AND v_grid_fim)
       OR (f.data_vencimento IS NULL AND f.mes = p_mes AND f.ano = p_ano)
     )
    WHERE c.user_id = v_user_id
      AND c.ativo = TRUE
  ) row_cart;

  -- 4. Ranking de Despesas por Categoria/Tag no Período [v_d_ini .. v_d_fim] (incluindo caixinhas)
  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva
    FROM public.lancamentos l
    LEFT JOIN public.faturas f ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c ON c.id = l.cartao_id
    WHERE l.user_id = v_user_id
  )
  SELECT COALESCE(JSON_AGG(row_dc ORDER BY row_dc.total DESC), '[]'::JSON)
  INTO v_desp_cat
  FROM (
    SELECT
      cat.id AS categoria_id,
      COALESCE(cat.nome, 'Sem Categoria') AS categoria,
      COALESCE(cat.cor, '#94A3B8') AS cor,
      COALESCE(cat.icone, 'label') AS icone,
      SUM(le.valor) AS total,
      COUNT(le.id)::INT AS qtd,
      ROUND((SUM(le.valor) / NULLIF(v_tot_desp, 0)) * 100, 1) AS percentual
    FROM lancs_efetivos le
    LEFT JOIN public.categorias cat ON cat.id = le.categoria_id
    WHERE le.data_efetiva BETWEEN v_d_ini AND v_d_fim
      AND le.tipo = 'Despesa'
    GROUP BY cat.id, cat.nome, cat.cor, cat.icone
  ) row_dc;

  -- 5. Ranking de Receitas por Categoria/Tag no Período [v_d_ini .. v_d_fim]
  SELECT COALESCE(JSON_AGG(row_rc ORDER BY row_rc.total DESC), '[]'::JSON)
  INTO v_rec_cat
  FROM (
    SELECT
      cat.id AS categoria_id,
      COALESCE(cat.nome, 'Sem Categoria') AS categoria,
      COALESCE(cat.cor, '#10B981') AS cor,
      COALESCE(cat.icone, 'label') AS icone,
      SUM(l.valor) AS total,
      COUNT(l.id)::INT AS qtd,
      ROUND((SUM(l.valor) / NULLIF(v_tot_rec, 0)) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE l.user_id = v_user_id
      AND l.data BETWEEN v_d_ini AND v_d_fim
      AND l.tipo = 'Receita'
    GROUP BY cat.id, cat.nome, cat.cor, cat.icone
  ) row_rc;

  RETURN JSON_BUILD_OBJECT(
    'mes', p_mes,
    'ano', p_ano,
    'inicio_mes', v_inicio_mes::TEXT,
    'fim_mes', v_fim_mes::TEXT,
    'filtro_inicio', v_d_ini::TEXT,
    'filtro_fim', v_d_fim::TEXT,
    'eh_periodo_parcial', (v_d_ini <> v_inicio_mes OR v_d_fim <> v_fim_mes),
    'grid_inicio', v_grid_inicio::TEXT,
    'grid_fim', v_grid_fim::TEXT,
    'kpis', v_kpis,
    'dias', v_dias,
    'cartoes_faturas', v_faturas,
    'despesas_por_categoria', v_desp_cat,
    'receitas_por_categoria', v_rec_cat
  );
END;
$$;
