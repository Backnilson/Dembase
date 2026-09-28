-- =============================================================================
-- DemBase v3 — Migração 003
-- RPCs (Stored Functions) para o Dashboard e módulos
-- Todas retornam JSON diretamente para o cliente Flet via supabase.rpc()
-- Execute DEPOIS das migrações 001 e 002
-- =============================================================================

-- -----------------------------------------------------------------------------
-- RPC 1: get_dashboard_overview
-- Retorna KPIs principais do Dashboard para um mês/ano específico
-- Uso: db.obter_overview_dashboard(mes=9, ano=2026)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_dashboard_overview(
  p_mes  SMALLINT DEFAULT NULL,
  p_ano  SMALLINT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER   -- executa com privilégios do owner, respeita RLS via auth.uid()
AS $$
DECLARE
  v_user_id   UUID := auth.uid();
  v_inicio    DATE;
  v_fim       DATE;
  v_receitas  NUMERIC;
  v_despesas  NUMERIC;
  v_saldo_contas  NUMERIC;
  v_total_faturas NUMERIC;
BEGIN
  -- Define período
  IF p_mes IS NOT NULL AND p_ano IS NOT NULL THEN
    v_inicio := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
    v_fim    := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  ELSE
    v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_fim    := CURRENT_DATE;
  END IF;

  -- Receitas do período
  SELECT COALESCE(SUM(valor), 0) INTO v_receitas
  FROM public.lancamentos
  WHERE user_id = v_user_id
    AND tipo = 'Receita'
    AND data BETWEEN v_inicio AND v_fim
    AND status = 'Pago';

  -- Despesas do período (conta bancária — exclui cartão)
  SELECT COALESCE(SUM(valor), 0) INTO v_despesas
  FROM public.lancamentos
  WHERE user_id = v_user_id
    AND tipo = 'Despesa'
    AND data BETWEEN v_inicio AND v_fim
    AND status = 'Pago'
    AND cartao_id IS NULL;  -- despesas de conta, não de cartão

  -- Saldo atual de todas as contas
  SELECT COALESCE(SUM(saldo_atual), 0) INTO v_saldo_contas
  FROM public.contas
  WHERE user_id = v_user_id AND ativo = TRUE;

  -- Total de faturas abertas em cartões
  SELECT COALESCE(SUM(valor_total - valor_pago), 0) INTO v_total_faturas
  FROM public.faturas f
  JOIN public.cartoes c ON c.id = f.cartao_id
  WHERE c.user_id = v_user_id
    AND f.status IN ('aberta','fechada','vencida')
    AND f.mes = COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE))
    AND f.ano = COALESCE(p_ano, EXTRACT(YEAR FROM CURRENT_DATE));

  RETURN JSON_BUILD_OBJECT(
    'receitas',       v_receitas,
    'despesas',       v_despesas,
    'saldo',          v_receitas - v_despesas,
    'saldo_contas',   v_saldo_contas,
    'total_faturas',  v_total_faturas,
    'periodo_inicio', v_inicio,
    'periodo_fim',    v_fim
  );
END;
$$;


-- -----------------------------------------------------------------------------
-- RPC 2: get_despesas_por_categoria
-- Para os gráficos de Donut — Despesas por Categoria
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_despesas_por_categoria(
  p_mes SMALLINT DEFAULT NULL,
  p_ano SMALLINT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_inicio  DATE;
  v_fim     DATE;
  v_total   NUMERIC;
  v_result  JSON;
BEGIN
  IF p_mes IS NOT NULL AND p_ano IS NOT NULL THEN
    v_inicio := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
    v_fim    := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  ELSE
    v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_fim    := CURRENT_DATE;
  END IF;

  SELECT COALESCE(SUM(valor), 0) INTO v_total
  FROM public.lancamentos
  WHERE user_id = v_user_id AND tipo = 'Despesa'
    AND data BETWEEN v_inicio AND v_fim AND status = 'Pago';

  SELECT JSON_AGG(row ORDER BY row.valor DESC)
  INTO v_result
  FROM (
    SELECT
      COALESCE(c.nome, 'Sem Categoria') AS categoria,
      COALESCE(c.cor, '#94A3B8')        AS cor,
      COALESCE(c.icone, 'category')     AS icone,
      SUM(l.valor)                       AS valor,
      ROUND(SUM(l.valor) / NULLIF(v_total, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE l.user_id = v_user_id AND l.tipo = 'Despesa'
      AND l.data BETWEEN v_inicio AND v_fim AND l.status = 'Pago'
    GROUP BY c.nome, c.cor, c.icone
  ) row;

  RETURN JSON_BUILD_OBJECT('total', v_total, 'categorias', COALESCE(v_result, '[]'::JSON));
END;
$$;


-- -----------------------------------------------------------------------------
-- RPC 3: get_receitas_por_categoria
-- Para os gráficos de Donut — Receitas por Categoria
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_receitas_por_categoria(
  p_mes SMALLINT DEFAULT NULL,
  p_ano SMALLINT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_inicio  DATE;
  v_fim     DATE;
  v_total   NUMERIC;
  v_result  JSON;
BEGIN
  IF p_mes IS NOT NULL AND p_ano IS NOT NULL THEN
    v_inicio := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
    v_fim    := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  ELSE
    v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_fim    := CURRENT_DATE;
  END IF;

  SELECT COALESCE(SUM(valor), 0) INTO v_total
  FROM public.lancamentos
  WHERE user_id = v_user_id AND tipo = 'Receita'
    AND data BETWEEN v_inicio AND v_fim AND status = 'Pago';

  SELECT JSON_AGG(row ORDER BY row.valor DESC)
  INTO v_result
  FROM (
    SELECT
      COALESCE(c.nome, 'Sem Categoria') AS categoria,
      COALESCE(c.cor, '#10B981')        AS cor,
      COALESCE(c.icone, 'category')     AS icone,
      SUM(l.valor)                       AS valor,
      ROUND(SUM(l.valor) / NULLIF(v_total, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE l.user_id = v_user_id AND l.tipo = 'Receita'
      AND l.data BETWEEN v_inicio AND v_fim AND l.status = 'Pago'
    GROUP BY c.nome, c.cor, c.icone
  ) row;

  RETURN JSON_BUILD_OBJECT('total', v_total, 'categorias', COALESCE(v_result, '[]'::JSON));
END;
$$;


-- -----------------------------------------------------------------------------
-- RPC 4: get_balanco_ultimos_6_meses
-- Para o gráfico de linha — Balanço mensal dos últimos 6 meses
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_balanco_ultimos_6_meses()
RETURNS JSON
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_result  JSON;
BEGIN
  SELECT JSON_AGG(row ORDER BY row.ano, row.mes)
  INTO v_result
  FROM (
    SELECT
      EXTRACT(YEAR  FROM data)::INT AS ano,
      EXTRACT(MONTH FROM data)::INT AS mes,
      TO_CHAR(data, 'Mon/YY')       AS label,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) AS receitas,
      SUM(CASE WHEN tipo = 'Despesa' AND cartao_id IS NULL THEN valor ELSE 0 END) AS despesas,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END)
        - SUM(CASE WHEN tipo = 'Despesa' AND cartao_id IS NULL THEN valor ELSE 0 END) AS saldo
    FROM public.lancamentos
    WHERE user_id = v_user_id
      AND status = 'Pago'
      AND data >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
    GROUP BY EXTRACT(YEAR FROM data), EXTRACT(MONTH FROM data), TO_CHAR(data, 'Mon/YY')
  ) row;

  RETURN COALESCE(v_result, '[]'::JSON);
END;
$$;


-- -----------------------------------------------------------------------------
-- RPC 5: get_frequencia_gastos_mes
-- Para o gráfico de linha — Gastos diários do mês
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_frequencia_gastos_mes(
  p_mes SMALLINT DEFAULT NULL,
  p_ano SMALLINT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_inicio  DATE;
  v_fim     DATE;
  v_result  JSON;
BEGIN
  IF p_mes IS NOT NULL AND p_ano IS NOT NULL THEN
    v_inicio := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
    v_fim    := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  ELSE
    v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_fim    := CURRENT_DATE;
  END IF;

  SELECT JSON_AGG(row ORDER BY row.data)
  INTO v_result
  FROM (
    SELECT
      data,
      EXTRACT(DAY FROM data)::INT AS dia,
      SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) AS despesas,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) AS receitas
    FROM public.lancamentos
    WHERE user_id = v_user_id
      AND data BETWEEN v_inicio AND v_fim
      AND status = 'Pago'
    GROUP BY data
  ) row;

  RETURN COALESCE(v_result, '[]'::JSON);
END;
$$;


-- -----------------------------------------------------------------------------
-- RPC 6: get_resumo_contas
-- Para o módulo de Contas — saldos consolidados
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_resumo_contas()
RETURNS JSON
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_result  JSON;
BEGIN
  SELECT JSON_BUILD_OBJECT(
    'saldo_total_atual',    COALESCE(SUM(saldo_atual), 0),
    'saldo_total_previsto', COALESCE(SUM(saldo_previsto), 0),
    'contas', (
      SELECT JSON_AGG(c ORDER BY c.nome)
      FROM (
        SELECT id, nome, tipo_conta, banco, cor, icone, saldo_atual, saldo_previsto, ativo
        FROM public.contas
        WHERE user_id = v_user_id AND ativo = TRUE
      ) c
    )
  ) INTO v_result
  FROM public.contas
  WHERE user_id = v_user_id AND ativo = TRUE;

  RETURN v_result;
END;
$$;


-- -----------------------------------------------------------------------------
-- RPC 7: get_resumo_cartoes
-- Para o módulo de Cartões — faturas e limites consolidados
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_resumo_cartoes(
  p_mes SMALLINT DEFAULT NULL,
  p_ano SMALLINT DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_mes     SMALLINT := COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT);
  v_ano     SMALLINT := COALESCE(p_ano, EXTRACT(YEAR  FROM CURRENT_DATE)::SMALLINT);
  v_result  JSON;
BEGIN
  SELECT JSON_BUILD_OBJECT(
    'total_limite',      COALESCE(SUM(c.limite_total), 0),
    'total_disponivel',  COALESCE(SUM(c.limite_disponivel), 0),
    'total_faturas',     COALESCE(SUM(f.valor_total - f.valor_pago), 0),
    'cartoes', (
      SELECT JSON_AGG(row ORDER BY row.nome)
      FROM (
        SELECT
          c.id, c.nome, c.bandeira, c.cor, c.icone,
          c.limite_total, c.limite_disponivel,
          c.dia_vencimento, c.dia_fechamento,
          f.id            AS fatura_id,
          f.valor_total   AS fatura_valor,
          f.valor_pago    AS fatura_pago,
          f.data_vencimento,
          f.status        AS fatura_status,
          ROUND(
            (c.limite_total - c.limite_disponivel) / NULLIF(c.limite_total, 0) * 100, 1
          ) AS percentual_uso
        FROM public.cartoes c
        LEFT JOIN public.faturas f
          ON f.cartao_id = c.id AND f.mes = v_mes AND f.ano = v_ano
        WHERE c.user_id = v_user_id AND c.ativo = TRUE
      ) row
    )
  ) INTO v_result
  FROM public.cartoes c
  LEFT JOIN public.faturas f
    ON f.cartao_id = c.id AND f.mes = v_mes AND f.ano = v_ano
  WHERE c.user_id = v_user_id AND c.ativo = TRUE;

  RETURN v_result;
END;
$$;


-- -----------------------------------------------------------------------------
-- RPC 8: get_lancamentos_calendario
-- Para o calendário — lançamentos agrupados por dia
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_lancamentos_calendario(
  p_mes SMALLINT,
  p_ano SMALLINT
)
RETURNS JSON
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_inicio  DATE := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
  v_fim     DATE := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  v_result  JSON;
BEGIN
  SELECT JSON_AGG(row ORDER BY row.data)
  INTO v_result
  FROM (
    SELECT
      data,
      EXTRACT(DAY FROM data)::INT AS dia,
      JSON_AGG(
        JSON_BUILD_OBJECT(
          'id', id, 'tipo', tipo, 'valor', valor,
          'descricao', descricao, 'status', status,
          'categoria_id', categoria_id
        ) ORDER BY hora
      ) AS lancamentos,
      SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END) AS total_despesas,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) AS total_receitas
    FROM public.lancamentos
    WHERE user_id = v_user_id AND data BETWEEN v_inicio AND v_fim
    GROUP BY data
  ) row;

  RETURN COALESCE(v_result, '[]'::JSON);
END;
$$;
