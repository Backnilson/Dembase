-- =============================================================================
-- MIGRAÇÃO 020: Calendário Financeiro Interativo (Mapa de Calor + Rosca + Faturas)
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_calendario_financeiro_mes(
  p_mes SMALLINT,
  p_ano SMALLINT
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_user_id     UUID := auth.uid();
  v_inicio_mes  DATE := make_date(p_ano::INT, p_mes::INT, 1);
  v_fim_mes     DATE := (v_inicio_mes + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  -- Grade de 6 semanas começando no Domingo (DOW = 0 no PostgreSQL)
  v_grid_inicio DATE := v_inicio_mes - (EXTRACT(DOW FROM v_inicio_mes)::INT);
  v_grid_fim    DATE := v_grid_inicio + 41;
  v_kpis        JSON;
  v_dias        JSON;
  v_faturas     JSON;
  v_desp_cat    JSON;
  v_rec_cat     JSON;
  v_tot_desp    NUMERIC := 0;
  v_tot_rec     NUMERIC := 0;
BEGIN
  -- 1. KPIs consolidados estritamente do mês selecionado
  SELECT
    COALESCE(SUM(CASE WHEN l.tipo = 'Receita' THEN l.valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' AND COALESCE(l.subtipo, '') <> 'Provisionamento' THEN l.valor ELSE 0 END), 0)
  INTO v_tot_rec, v_tot_desp
  FROM public.lancamentos l
  WHERE l.user_id = v_user_id
    AND l.data BETWEEN v_inicio_mes AND v_fim_mes;

  SELECT JSON_BUILD_OBJECT(
    'receitas_mes',        v_tot_rec,
    'despesas_mes',        v_tot_desp,
    'resultado_mes',       (v_tot_rec - v_tot_desp),
    'despesas_conta_mes',  COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' AND l.cartao_id IS NULL AND COALESCE(l.subtipo, '') <> 'Provisionamento' THEN l.valor ELSE 0 END), 0),
    'despesas_cartao_mes', COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' AND l.cartao_id IS NOT NULL THEN l.valor ELSE 0 END), 0),
    'dias_com_saida',      COUNT(DISTINCT CASE WHEN l.tipo = 'Despesa' AND COALESCE(l.subtipo, '') <> 'Provisionamento' AND l.valor > 0 THEN l.data END),
    'dias_com_entrada',    COUNT(DISTINCT CASE WHEN l.tipo = 'Receita' AND l.valor > 0 THEN l.data END),
    'qtd_lancamentos_mes', COUNT(CASE WHEN COALESCE(l.subtipo, '') <> 'Provisionamento' THEN 1 END),
    'maior_saida_dia',     COALESCE((
      SELECT MAX(soma_d) FROM (
        SELECT SUM(l2.valor) AS soma_d
        FROM public.lancamentos l2
        WHERE l2.user_id = v_user_id
          AND l2.data BETWEEN v_inicio_mes AND v_fim_mes
          AND l2.tipo = 'Despesa'
          AND COALESCE(l2.subtipo, '') <> 'Provisionamento'
        GROUP BY l2.data
      ) s
    ), 0)
  )
  INTO v_kpis
  FROM public.lancamentos l
  WHERE l.user_id = v_user_id
    AND l.data BETWEEN v_inicio_mes AND v_fim_mes;

  -- 2. Agregação por Dia cobrindo a grade completa (v_grid_inicio .. v_grid_fim)
  SELECT COALESCE(JSON_AGG(row_dia ORDER BY row_dia.data), '[]'::JSON)
  INTO v_dias
  FROM (
    SELECT
      l.data::TEXT AS data,
      EXTRACT(DAY FROM l.data)::INT AS dia,
      EXTRACT(MONTH FROM l.data)::INT AS mes,
      EXTRACT(YEAR FROM l.data)::INT AS ano,
      (l.data BETWEEN v_inicio_mes AND v_fim_mes) AS no_mes_atual,
      COALESCE(SUM(CASE WHEN l.tipo = 'Receita' THEN l.valor ELSE 0 END), 0) AS total_receitas,
      COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' AND COALESCE(l.subtipo, '') <> 'Provisionamento' THEN l.valor ELSE 0 END), 0) AS total_despesas,
      COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' AND l.cartao_id IS NULL AND COALESCE(l.subtipo, '') <> 'Provisionamento' THEN l.valor ELSE 0 END), 0) AS despesas_conta,
      COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' AND l.cartao_id IS NOT NULL THEN l.valor ELSE 0 END), 0) AS despesas_cartao,
      COUNT(l.id)::INT AS qtd_lancamentos,
      JSON_AGG(
        JSON_BUILD_OBJECT(
          'id', l.id,
          'data', l.data::TEXT,
          'hora', l.hora,
          'tipo', l.tipo,
          'subtipo', l.subtipo,
          'valor', l.valor,
          'descricao', l.descricao,
          'status', l.status,
          'regra', l.regra,
          'forma_movimentacao', l.forma_movimentacao,
          'parcela_atual', l.parcela_atual,
          'total_parcelas', l.total_parcelas,
          'fatura', l.fatura,
          'conta_id', l.conta_id,
          'cartao_id', l.cartao_id,
          'categoria_id', l.categoria_id,
          'subcategoria_id', l.subcategoria_id,
          'categoria_nome', COALESCE(cat.nome, 'Sem Categoria'),
          'categoria_cor', COALESCE(cat.cor, '#64748B'),
          'categoria_icone', COALESCE(cat.icone, 'category'),
          'subcategoria_nome', sub.nome,
          'conta_nome', cta.nome,
          'cartao_nome', crt.nome,
          'cartao_cor', crt.cor
        ) ORDER BY l.hora DESC NULLS LAST, l.criado_em DESC
      ) AS lancamentos
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
    LEFT JOIN public.contas cta ON cta.id = l.conta_id
    LEFT JOIN public.cartoes crt ON crt.id = l.cartao_id
    WHERE l.user_id = v_user_id
      AND l.data BETWEEN v_grid_inicio AND v_grid_fim
      AND COALESCE(l.subtipo, '') <> 'Provisionamento'
    GROUP BY l.data
  ) row_dia;

  -- 3. Faturas e Cartões do Mês (para marcadores de vencimento e barra lateral de cartões)
  SELECT COALESCE(JSON_AGG(row_cart ORDER BY row_cart.dia_vencimento, row_cart.cartao_nome), '[]'::JSON)
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
      COALESCE(
        f.data_vencimento,
        make_date(
          p_ano::INT,
          p_mes::INT,
          LEAST(COALESCE(c.dia_vencimento, 10)::INT, EXTRACT(DAY FROM v_fim_mes)::INT)
        )
      )::TEXT AS data_vencimento,
      LEAST(COALESCE(c.dia_vencimento, 10)::INT, EXTRACT(DAY FROM v_fim_mes)::INT) AS dia_vencimento_efetivo,
      COALESCE(f.valor_total, 0) AS valor_total,
      COALESCE(f.valor_pago, 0) AS valor_pago,
      CASE
        WHEN COALESCE(f.valor_total, 0) <= 0.01 THEN 'paga'
        ELSE COALESCE(f.status, 'aberta')
      END AS status
    FROM public.cartoes c
    LEFT JOIN public.faturas f
      ON f.cartao_id = c.id AND f.mes = p_mes AND f.ano = p_ano
    WHERE c.user_id = v_user_id
      AND c.ativo = TRUE
  ) row_cart;

  -- 4. Ranking de Despesas por Categoria/Tag no Mês (Gráfico de Rosca)
  SELECT COALESCE(JSON_AGG(row_dc ORDER BY row_dc.total DESC), '[]'::JSON)
  INTO v_desp_cat
  FROM (
    SELECT
      cat.id AS categoria_id,
      COALESCE(cat.nome, 'Sem Categoria') AS categoria,
      COALESCE(cat.cor, '#94A3B8') AS cor,
      COALESCE(cat.icone, 'label') AS icone,
      SUM(l.valor) AS total,
      COUNT(l.id)::INT AS qtd,
      ROUND((SUM(l.valor) / NULLIF(v_tot_desp, 0)) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE l.user_id = v_user_id
      AND l.data BETWEEN v_inicio_mes AND v_fim_mes
      AND l.tipo = 'Despesa'
      AND COALESCE(l.subtipo, '') <> 'Provisionamento'
    GROUP BY cat.id, cat.nome, cat.cor, cat.icone
  ) row_dc;

  -- 5. Ranking de Receitas por Categoria/Tag no Mês (Gráfico de Rosca)
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
      AND l.data BETWEEN v_inicio_mes AND v_fim_mes
      AND l.tipo = 'Receita'
    GROUP BY cat.id, cat.nome, cat.cor, cat.icone
  ) row_rc;

  RETURN JSON_BUILD_OBJECT(
    'mes', p_mes,
    'ano', p_ano,
    'inicio_mes', v_inicio_mes::TEXT,
    'fim_mes', v_fim_mes::TEXT,
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
