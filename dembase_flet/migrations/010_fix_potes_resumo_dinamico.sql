-- =============================================================================
-- DemBase v3 — Migration 010: Fix Potes Resumo Dinâmico
-- Corrige a RPC get_potes_resumo para calcular 'previsto' dinamicamente a partir
-- da renda de referência do perfil (valor base) e dos percentuais configurados
-- nos potes, eliminando a dependência de snapshots congelados em distribuicoes_receita.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_potes_resumo(
  p_data_inicio DATE,
  p_data_fim    DATE
) RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = public AS $$
DECLARE
  v_uid       UUID := auth.uid();
  v_renda     NUMERIC;
  v_gasto     NUMERIC;
  v_potes     JSONB;
  v_sem       JSONB;
BEGIN
  -- 1. Receitas REAIS do período filtrado
  SELECT COALESCE(SUM(valor), 0) INTO v_renda
    FROM public.lancamentos
   WHERE user_id = v_uid AND lower(tipo) LIKE 'receita%'
     AND data BETWEEN p_data_inicio AND p_data_fim;

  -- 2. Despesas REAIS do período filtrado
  SELECT COALESCE(SUM(valor), 0) INTO v_gasto
    FROM public.lancamentos
   WHERE user_id = v_uid AND lower(tipo) LIKE 'despesa%'
     AND data BETWEEN p_data_inicio AND p_data_fim;

  -- 3. Limite de cada pote = percentual configurado x Receita Real do período
  SELECT COALESCE(jsonb_agg(r ORDER BY r.posicao), '[]'::jsonb) INTO v_potes
  FROM (
    SELECT p.id, p.posicao, p.nome, p.cor, p.percentual,
           ROUND(v_renda * p.percentual / 100.0, 2) AS previsto,
           COALESCE(g.gasto, 0)                     AS gasto,
           COALESCE(g.qtd, 0)                       AS qtd_transacoes,
           ROUND(v_renda * p.percentual / 100.0, 2) - COALESCE(g.gasto, 0) AS restante,
           CASE WHEN ROUND(v_renda * p.percentual / 100.0, 2) > 0
                THEN ROUND(COALESCE(g.gasto, 0) / (v_renda * p.percentual / 100.0) * 100, 2)
                ELSE 0 END                          AS percentual_usado
      FROM public.potes p
      LEFT JOIN (
        SELECT pote_id, SUM(valor) AS gasto, COUNT(*) AS qtd
          FROM public.lancamentos
         WHERE user_id = v_uid AND lower(tipo) LIKE 'despesa%'
           AND pote_id IS NOT NULL
           AND data BETWEEN p_data_inicio AND p_data_fim
         GROUP BY pote_id
      ) g ON g.pote_id = p.id
     WHERE p.user_id = v_uid
  ) r;

  SELECT jsonb_build_object('qtd', COUNT(*), 'total', COALESCE(SUM(valor), 0)) INTO v_sem
    FROM public.lancamentos
   WHERE user_id = v_uid AND lower(tipo) LIKE 'despesa%'
     AND pote_id IS NULL
     AND data BETWEEN p_data_inicio AND p_data_fim;

  RETURN jsonb_build_object(
    'renda',                  v_renda,
    'base_utilizada',         v_renda,
    'total_gasto',            v_gasto,
    'saldo',                  v_renda - v_gasto,
    'percentual_renda_usado', CASE WHEN v_renda > 0 THEN ROUND(v_gasto / v_renda * 100, 2) ELSE 0 END,
    'potes',                  v_potes,
    'sem_pote',               v_sem
  );
END $$;

REVOKE ALL ON FUNCTION public.get_potes_resumo(DATE, DATE) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_potes_resumo(DATE, DATE) TO authenticated, anon, service_role;
