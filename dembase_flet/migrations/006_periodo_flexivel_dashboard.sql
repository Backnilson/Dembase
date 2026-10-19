-- =============================================================================
-- DemBase v3 — Migração 006: Suporte a Período Flexível (p_data_inicio / p_data_fim)
-- Cria a RPC consolidada get_dashboard_periodo e atualiza get_regra_50_30_20_summary
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_regra_50_30_20_summary(
  p_data_inicio DATE DEFAULT NULL::DATE,
  p_data_fim    DATE DEFAULT NULL::DATE
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
    v_receita_total      DECIMAL(12,2);
    v_gasto_essencial    DECIMAL(12,2);
    v_gasto_estilo       DECIMAL(12,2);
    v_gasto_investimento DECIMAL(12,2);
    v_uid                UUID := auth.uid();
BEGIN
    SELECT COALESCE(SUM(valor), 0) INTO v_receita_total
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND tipo = 'Receita'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_essencial
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND tipo = 'Despesa' AND regra = 'Essencial'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_estilo
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND tipo = 'Despesa' AND regra = 'Estilo de Vida'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_investimento
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND tipo = 'Despesa' AND regra = 'Investimento'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    RETURN json_build_object(
        'receita_total', v_receita_total,
        'essencial', json_build_object(
            'gasto', v_gasto_essencial,
            'orcamento', v_receita_total * 0.50,
            'percentual_usado', CASE WHEN v_receita_total > 0
                THEN ROUND((v_gasto_essencial / v_receita_total) * 100, 1) ELSE 0 END
        ),
        'estilo_vida', json_build_object(
            'gasto', v_gasto_estilo,
            'orcamento', v_receita_total * 0.30,
            'percentual_usado', CASE WHEN v_receita_total > 0
                THEN ROUND((v_gasto_estilo / v_receita_total) * 100, 1) ELSE 0 END
        ),
        'investimento', json_build_object(
            'gasto', v_gasto_investimento,
            'orcamento', v_receita_total * 0.20,
            'percentual_usado', CASE WHEN v_receita_total > 0
                THEN ROUND((v_gasto_investimento / v_receita_total) * 100, 1) ELSE 0 END
        )
    );
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_dashboard_periodo(
  p_data_inicio DATE,
  p_data_fim    DATE
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id       UUID := auth.uid();
  v_inicio        DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
  v_fim           DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
  v_receitas      NUMERIC;
  v_despesas      NUMERIC;
  v_saldo_contas  NUMERIC;
  v_total_faturas NUMERIC;
  v_desp_cat      JSON;
  v_rec_cat       JSON;
  v_freq          JSON;
  v_formas        JSON;
  v_mes_ref       SMALLINT := EXTRACT(MONTH FROM v_fim)::SMALLINT;
  v_ano_ref       SMALLINT := EXTRACT(YEAR  FROM v_fim)::SMALLINT;
BEGIN
  SELECT COALESCE(SUM(valor), 0) INTO v_receitas
  FROM public.lancamentos
  WHERE (user_id = v_user_id OR perfil_id = v_user_id)
    AND tipo = 'Receita'
    AND data BETWEEN v_inicio AND v_fim
    AND status = 'Pago';

  SELECT COALESCE(SUM(valor), 0) INTO v_despesas
  FROM public.lancamentos
  WHERE (user_id = v_user_id OR perfil_id = v_user_id)
    AND tipo = 'Despesa'
    AND data BETWEEN v_inicio AND v_fim
    AND status = 'Pago';

  SELECT COALESCE(SUM(saldo_atual), 0) INTO v_saldo_contas
  FROM public.contas
  WHERE user_id = v_user_id AND ativo = TRUE;

  SELECT COALESCE(SUM(valor_total - valor_pago), 0) INTO v_total_faturas
  FROM public.faturas f
  JOIN public.cartoes c ON c.id = f.cartao_id
  WHERE c.user_id = v_user_id
    AND f.status IN ('aberta','fechada','vencida')
    AND f.mes = v_mes_ref
    AND f.ano = v_ano_ref;

  SELECT JSON_AGG(row ORDER BY row.valor DESC) INTO v_desp_cat
  FROM (
    SELECT
      COALESCE(c.nome, 'Sem Categoria') AS categoria,
      COALESCE(c.cor, '#94A3B8')        AS cor,
      COALESCE(c.icone, 'category')     AS icone,
      SUM(l.valor)                       AS valor,
      SUM(l.valor)                       AS total,
      ROUND(SUM(l.valor) / NULLIF(v_despesas, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
      AND l.tipo = 'Despesa'
      AND l.data BETWEEN v_inicio AND v_fim
    GROUP BY c.nome, c.cor, c.icone
  ) row;

  SELECT JSON_AGG(row ORDER BY row.valor DESC) INTO v_rec_cat
  FROM (
    SELECT
      COALESCE(c.nome, 'Sem Categoria') AS categoria,
      COALESCE(c.cor, '#10B981')        AS cor,
      COALESCE(c.icone, 'category')     AS icone,
      SUM(l.valor)                       AS valor,
      SUM(l.valor)                       AS total,
      ROUND(SUM(l.valor) / NULLIF(v_receitas, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
      AND l.tipo = 'Receita'
      AND l.data BETWEEN v_inicio AND v_fim
    GROUP BY c.nome, c.cor, c.icone
  ) row;

  SELECT JSON_AGG(row ORDER BY row.data) INTO v_freq
  FROM (
    SELECT
      data,
      EXTRACT(DAY FROM data)::INT AS dia,
      TO_CHAR(data, 'DD/MM')      AS label,
      SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) AS despesas,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) AS receitas
    FROM public.lancamentos
    WHERE (user_id = v_user_id OR perfil_id = v_user_id)
      AND data BETWEEN v_inicio AND v_fim
    GROUP BY data
  ) row;

  SELECT JSON_AGG(row ORDER BY row.valor DESC) INTO v_formas
  FROM (
    SELECT
      COALESCE(forma_movimentacao, 'Outros') AS forma,
      SUM(valor) AS valor,
      COUNT(*)::INT AS qtd,
      ROUND(SUM(valor) / NULLIF(
        (SELECT SUM(valor) FROM public.lancamentos WHERE (user_id = v_user_id OR perfil_id = v_user_id) AND tipo = 'Despesa' AND data BETWEEN v_inicio AND v_fim),
        0
      ) * 100, 1) AS percentual
    FROM public.lancamentos
    WHERE (user_id = v_user_id OR perfil_id = v_user_id)
      AND tipo = 'Despesa'
      AND data BETWEEN v_inicio AND v_fim
    GROUP BY forma_movimentacao
  ) row;

  RETURN JSON_BUILD_OBJECT(
    'overview', JSON_BUILD_OBJECT(
      'receitas',       v_receitas,
      'despesas',       v_despesas,
      'saldo',          v_receitas - v_despesas,
      'saldo_contas',   v_saldo_contas,
      'total_faturas',  v_total_faturas,
      'periodo_inicio', v_inicio,
      'periodo_fim',    v_fim
    ),
    'despesas_por_categoria', JSON_BUILD_OBJECT('total', v_despesas, 'categorias', COALESCE(v_desp_cat, '[]'::JSON)),
    'receitas_por_categoria', JSON_BUILD_OBJECT('total', v_receitas, 'categorias', COALESCE(v_rec_cat, '[]'::JSON)),
    'frequencia_diaria',      COALESCE(v_freq, '[]'::JSON),
    'despesas_por_forma',     COALESCE(v_formas, '[]'::JSON)
  );
END;
$$;
