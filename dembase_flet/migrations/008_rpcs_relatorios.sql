-- =============================================================================
-- DemBase v3 — Migração 008: RPCs de Relatórios Modulares e Drill-down
-- - Índices compostos para consultas analíticas por período/conta/categoria
-- - Atualização de get_dashboard_periodo (inclui categoria_id e consistência de totais)
-- - get_relatorio_lancamentos (relatório geral com filtros completos e paginação)
-- - get_lista_contas_resumo (lista de contas enriquecida com entradas/saídas do período)
-- - get_relatorio_conta (drill-down de conta com saldo inicial/final e evolução diária)
-- - get_relatorio_cartao (drill-down de cartão com faturas, categorias e lançamentos)
-- =============================================================================

-- 0. Remove FK legada de destino_id para destinos (evita erro em Transferências e ambiguidade PostgREST)
ALTER TABLE public.lancamentos DROP CONSTRAINT IF EXISTS lancamentos_destino_id_fkey;

-- 1. Índices analíticos
CREATE INDEX IF NOT EXISTS idx_lancamentos_user_data
    ON public.lancamentos (user_id, data DESC);

CREATE INDEX IF NOT EXISTS idx_lancamentos_user_conta_data
    ON public.lancamentos (user_id, conta_id, data DESC);

CREATE INDEX IF NOT EXISTS idx_lancamentos_user_destino_data
    ON public.lancamentos (user_id, destino_id, data DESC)
    WHERE (destino_id IS NOT NULL);

CREATE INDEX IF NOT EXISTS idx_lancamentos_user_cat_data
    ON public.lancamentos (user_id, categoria_id, data DESC);

CREATE INDEX IF NOT EXISTS idx_lancamentos_user_cartao_data
    ON public.lancamentos (user_id, cartao_id, data DESC)
    WHERE (cartao_id IS NOT NULL);


-- 2. Atualizar get_dashboard_periodo para incluir categoria_id nos rankings e manter consistência
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
  v_user_id        UUID := auth.uid();
  v_inicio         DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
  v_fim            DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
  v_receitas       NUMERIC;
  v_despesas       NUMERIC;
  v_receitas_pagas NUMERIC;
  v_despesas_pagas NUMERIC;
  v_saldo_contas   NUMERIC;
  v_total_faturas  NUMERIC;
  v_desp_cat       JSON;
  v_rec_cat        JSON;
  v_freq           JSON;
  v_formas         JSON;
  v_mes_ref        SMALLINT := EXTRACT(MONTH FROM v_fim)::SMALLINT;
  v_ano_ref        SMALLINT := EXTRACT(YEAR  FROM v_fim)::SMALLINT;
BEGIN
  SELECT
    COALESCE(SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN tipo = 'Despesa' THEN valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN tipo = 'Receita' AND status = 'Pago' THEN valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN tipo = 'Despesa' AND status = 'Pago' THEN valor ELSE 0 END), 0)
  INTO v_receitas, v_despesas, v_receitas_pagas, v_despesas_pagas
  FROM public.lancamentos
  WHERE (user_id = v_user_id OR perfil_id = v_user_id)
    AND data BETWEEN v_inicio AND v_fim;

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
      c.id                               AS categoria_id,
      COALESCE(c.nome, 'Sem Categoria')  AS categoria,
      COALESCE(c.nome, 'Sem Categoria')  AS nome,
      COALESCE(c.cor, '#94A3B8')         AS cor,
      COALESCE(c.icone, 'category')      AS icone,
      SUM(l.valor)                       AS valor,
      SUM(l.valor)                       AS total,
      COUNT(*)::INT                      AS qtd,
      ROUND(SUM(l.valor) / NULLIF(v_despesas, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
      AND l.tipo = 'Despesa'
      AND l.data BETWEEN v_inicio AND v_fim
    GROUP BY c.id, c.nome, c.cor, c.icone
  ) row;

  SELECT JSON_AGG(row ORDER BY row.valor DESC) INTO v_rec_cat
  FROM (
    SELECT
      c.id                               AS categoria_id,
      COALESCE(c.nome, 'Sem Categoria')  AS categoria,
      COALESCE(c.nome, 'Sem Categoria')  AS nome,
      COALESCE(c.cor, '#10B981')         AS cor,
      COALESCE(c.icone, 'category')      AS icone,
      SUM(l.valor)                       AS valor,
      SUM(l.valor)                       AS total,
      COUNT(*)::INT                      AS qtd,
      ROUND(SUM(l.valor) / NULLIF(v_receitas, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
      AND l.tipo = 'Receita'
      AND l.data BETWEEN v_inicio AND v_fim
    GROUP BY c.id, c.nome, c.cor, c.icone
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
      ROUND(SUM(valor) / NULLIF(v_despesas, 0) * 100, 1) AS percentual
    FROM public.lancamentos
    WHERE (user_id = v_user_id OR perfil_id = v_user_id)
      AND tipo = 'Despesa'
      AND data BETWEEN v_inicio AND v_fim
    GROUP BY forma_movimentacao
  ) row;

  RETURN JSON_BUILD_OBJECT(
    'overview', JSON_BUILD_OBJECT(
      'receitas',        v_receitas,
      'despesas',        v_despesas,
      'receitas_pagas',  v_receitas_pagas,
      'despesas_pagas',  v_despesas_pagas,
      'saldo',           v_receitas - v_despesas,
      'saldo_contas',    v_saldo_contas,
      'total_faturas',   v_total_faturas,
      'periodo_inicio',  v_inicio,
      'periodo_fim',     v_fim
    ),
    'despesas_por_categoria', JSON_BUILD_OBJECT('total', v_despesas, 'categorias', COALESCE(v_desp_cat, '[]'::JSON)),
    'receitas_por_categoria', JSON_BUILD_OBJECT('total', v_receitas, 'categorias', COALESCE(v_rec_cat, '[]'::JSON)),
    'frequencia_diaria',      COALESCE(v_freq, '[]'::JSON),
    'despesas_por_forma',     COALESCE(v_formas, '[]'::JSON)
  );
END;
$$;


-- 3. RPC: Relatório Geral de Lançamentos (Receitas, Despesas, Categoria, Regra, etc.)
CREATE OR REPLACE FUNCTION public.get_relatorio_lancamentos(
    p_data_inicio DATE,
    p_data_fim    DATE,
    p_filtros     JSONB DEFAULT '{}'::jsonb,
    p_limite      INT DEFAULT 50,
    p_offset      INT DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id      UUID := COALESCE(NULLIF(p_filtros->>'user_id', '')::uuid, auth.uid());
    v_inicio       DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
    v_fim          DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
    v_tipo         TEXT := NULLIF(trim(COALESCE(p_filtros->>'tipo', '')), '');
    v_conta_id     UUID := NULLIF(trim(COALESCE(p_filtros->>'conta_id', '')), '')::uuid;
    v_cartao_id    UUID := NULLIF(trim(COALESCE(p_filtros->>'cartao_id', '')), '')::uuid;
    v_categoria_id UUID := NULLIF(trim(COALESCE(p_filtros->>'categoria_id', '')), '')::uuid;
    v_subcat_id    UUID := NULLIF(trim(COALESCE(p_filtros->>'subcategoria_id', '')), '')::uuid;
    v_regra        TEXT := NULLIF(trim(COALESCE(p_filtros->>'regra', '')), '');
    v_status       TEXT := NULLIF(trim(COALESCE(p_filtros->>'status', '')), '');
    v_forma        TEXT := NULLIF(trim(COALESCE(p_filtros->>'forma', '')), '');
    v_busca        TEXT := NULLIF(trim(COALESCE(p_filtros->>'busca', '')), '');
    v_dias_periodo INT;
    v_receitas     NUMERIC := 0;
    v_despesas     NUMERIC := 0;
    v_transf       NUMERIC := 0;
    v_pago         NUMERIC := 0;
    v_pendente     NUMERIC := 0;
    v_qtd          INT := 0;
    v_base_total   NUMERIC := 0;
    v_por_cat      JSONB;
    v_por_subcat   JSONB;
    v_por_dia      JSONB;
    v_por_forma    JSONB;
    v_lancamentos  JSONB;
BEGIN
    IF v_fim < v_inicio THEN
        v_fim := v_inicio;
    END IF;
    v_dias_periodo := GREATEST(1, (v_fim - v_inicio) + 1);

    -- Normaliza filtro de tipo ('Transferencia' -> 'Transferência', 'Todos' -> NULL)
    IF v_tipo IS NOT NULL THEN
        IF lower(v_tipo) IN ('todos', 'all') THEN
            v_tipo := NULL;
        ELSIF lower(v_tipo) LIKE 'trans%' THEN
            v_tipo := 'Transferência';
        ELSIF lower(v_tipo) LIKE 'rec%' THEN
            v_tipo := 'Receita';
        ELSIF lower(v_tipo) LIKE 'desp%' THEN
            v_tipo := 'Despesa';
        END IF;
    END IF;

    -- Totais agregados sobre o conjunto filtrado
    -- Decisão aprovada: se v_tipo IS NULL, Transferências ficam ocultas por padrão
    SELECT
        COALESCE(SUM(CASE WHEN l.tipo = 'Receita' THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.tipo = 'Transferência' THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.status = 'Pago' THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.status = 'Pendente' THEN l.valor ELSE 0 END), 0),
        COUNT(*)::INT
    INTO v_receitas, v_despesas, v_transf, v_pago, v_pendente, v_qtd
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
      AND l.data BETWEEN v_inicio AND v_fim
      AND (
          (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
          OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
      )
      AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
      AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
      AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
      AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
      AND (v_regra IS NULL OR l.regra::text = v_regra)
      AND (v_status IS NULL OR l.status::text = v_status)
      AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
      AND (
          v_busca IS NULL
          OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
      );

    v_base_total := CASE
        WHEN v_tipo = 'Receita' THEN v_receitas
        WHEN v_tipo = 'Despesa' THEN v_despesas
        WHEN v_tipo = 'Transferência' THEN v_transf
        ELSE (v_receitas + v_despesas)
    END;

    -- Ranking por Categoria
    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_cat
    FROM (
        SELECT
            cat.id AS categoria_id,
            COALESCE(cat.nome, 'Sem Categoria') AS nome,
            COALESCE(cat.cor, '#94A3B8') AS cor,
            COALESCE(cat.icone, 'category') AS icone,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY cat.id, cat.nome, cat.cor, cat.icone
    ) row;

    -- Ranking por Subcategoria (útil para drill-down de Categoria)
    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_subcat
    FROM (
        SELECT
            sub.id AS subcategoria_id,
            COALESCE(sub.nome, 'Geral (Sem subcategoria)') AS nome,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY sub.id, sub.nome
    ) row;

    -- Evolução por Dia
    SELECT COALESCE(JSONB_AGG(row ORDER BY row.data), '[]'::jsonb) INTO v_por_dia
    FROM (
        SELECT
            l.data,
            TO_CHAR(l.data, 'DD/MM') AS label,
            SUM(CASE WHEN l.tipo = 'Receita' THEN l.valor ELSE 0 END) AS receitas,
            SUM(CASE WHEN l.tipo = 'Despesa' THEN l.valor ELSE 0 END) AS despesas,
            SUM(l.valor) AS total
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY l.data
    ) row;

    -- Distribuição por Forma de Movimentação
    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_forma
    FROM (
        SELECT
            COALESCE(l.forma_movimentacao, 'Outros') AS forma,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY l.forma_movimentacao
    ) row;

    -- Lista paginada de lançamentos enriquecidos
    SELECT COALESCE(JSONB_AGG(row), '[]'::jsonb) INTO v_lancamentos
    FROM (
        SELECT
            l.id,
            l.tipo,
            l.subtipo,
            l.forma_movimentacao,
            l.valor,
            l.data,
            l.hora,
            l.descricao,
            l.status::text AS status,
            l.regra::text AS regra,
            l.conta_id,
            co.nome AS conta_nome,
            co.cor AS conta_cor,
            l.destino_id,
            cd.nome AS destino_nome,
            l.cartao_id,
            ca.nome AS cartao_nome,
            ca.cor AS cartao_cor,
            l.categoria_id,
            COALESCE(cat.nome, 'Sem Categoria') AS categoria_nome,
            COALESCE(cat.cor, '#94A3B8') AS categoria_cor,
            COALESCE(cat.icone, 'category') AS categoria_icone,
            l.subcategoria_id,
            sub.nome AS subcategoria_nome,
            l.parcela_atual,
            l.total_parcelas,
            l.serie_id,
            l.recorrente_id
        FROM public.lancamentos l
        LEFT JOIN public.contas co ON co.id = l.conta_id
        LEFT JOIN public.contas cd ON cd.id = l.destino_id
        LEFT JOIN public.cartoes ca ON ca.id = l.cartao_id
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        ORDER BY l.data DESC, l.hora DESC, l.criado_em DESC
        LIMIT GREATEST(1, COALESCE(p_limite, 50))
        OFFSET GREATEST(0, COALESCE(p_offset, 0))
    ) row;

    RETURN JSONB_BUILD_OBJECT(
        'totais', JSONB_BUILD_OBJECT(
            'receitas', v_receitas,
            'despesas', v_despesas,
            'transferencias', v_transf,
            'saldo', v_receitas - v_despesas,
            'total_filtrado', v_base_total,
            'pago', v_pago,
            'pendente', v_pendente,
            'qtd', v_qtd,
            'media_diaria', ROUND(v_base_total / v_dias_periodo, 2)
        ),
        'por_categoria', v_por_cat,
        'por_subcategoria', v_por_subcat,
        'por_dia', v_por_dia,
        'por_forma', v_por_forma,
        'lancamentos', v_lancamentos,
        'total_registros', v_qtd
    );
END;
$$;


-- 4. RPC: Lista de Contas com Resumo do Período (para /contas)
CREATE OR REPLACE FUNCTION public.get_lista_contas_resumo(
    p_data_inicio DATE DEFAULT NULL,
    p_data_fim    DATE DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id    UUID := auth.uid();
    v_inicio     DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
    v_fim        DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
    v_contas     JSONB;
    v_tot_atual  NUMERIC := 0;
    v_tot_prev   NUMERIC := 0;
    v_tot_ent    NUMERIC := 0;
    v_tot_sai    NUMERIC := 0;
BEGIN
    SELECT
        COALESCE(SUM(c.saldo_atual), 0),
        COALESCE(SUM(c.saldo_previsto), 0)
    INTO v_tot_atual, v_tot_prev
    FROM public.contas c
    WHERE c.user_id = v_user_id AND c.ativo = TRUE;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.nome), '[]'::jsonb) INTO v_contas
    FROM (
        SELECT
            c.id,
            c.nome,
            c.tipo_conta,
            c.banco,
            c.cor,
            c.icone,
            COALESCE(c.saldo_inicial, 0) AS saldo_inicial,
            COALESCE(c.saldo_atual, COALESCE(c.saldo_inicial, 0)) AS saldo_atual,
            COALESCE(c.saldo_previsto, COALESCE(c.saldo_inicial, 0)) AS saldo_previsto,
            COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
                  AND l.data BETWEEN v_inicio AND v_fim
                  AND (
                      (l.conta_id = c.id AND l.tipo = 'Receita')
                      OR (l.destino_id = c.id AND l.tipo = 'Transferência')
                  )
            ), 0) AS entradas_periodo,
            COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
                  AND l.data BETWEEN v_inicio AND v_fim
                  AND l.conta_id = c.id
                  AND l.tipo IN ('Despesa', 'Transferência')
            ), 0) AS saidas_periodo,
            COALESCE((
                SELECT COUNT(*)::INT
                FROM public.lancamentos l
                WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
                  AND l.data BETWEEN v_inicio AND v_fim
                  AND (l.conta_id = c.id OR l.destino_id = c.id)
            ), 0) AS qtd_lancamentos_periodo
        FROM public.contas c
        WHERE c.user_id = v_user_id AND c.ativo = TRUE
    ) row;

    SELECT
        COALESCE(SUM((elem->>'entradas_periodo')::numeric), 0),
        COALESCE(SUM((elem->>'saidas_periodo')::numeric), 0)
    INTO v_tot_ent, v_tot_sai
    FROM JSONB_ARRAY_ELEMENTS(v_contas) elem;

    RETURN JSONB_BUILD_OBJECT(
        'saldo_total_atual', v_tot_atual,
        'saldo_total_previsto', v_tot_prev,
        'entradas_periodo_total', v_tot_ent,
        'saidas_periodo_total', v_tot_sai,
        'contas', v_contas
    );
END;
$$;


-- 5. RPC: Relatório Detalhado de Uma Conta (/contas/:conta_id)
CREATE OR REPLACE FUNCTION public.get_relatorio_conta(
    p_conta_id    UUID,
    p_data_inicio DATE,
    p_data_fim    DATE,
    p_filtros     JSONB DEFAULT '{}'::jsonb,
    p_limite      INT DEFAULT 50,
    p_offset      INT DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id      UUID := COALESCE(NULLIF(p_filtros->>'user_id', '')::uuid, auth.uid());
    v_inicio       DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
    v_fim          DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
    v_tipo         TEXT := NULLIF(trim(COALESCE(p_filtros->>'tipo', '')), '');
    v_categoria_id UUID := NULLIF(trim(COALESCE(p_filtros->>'categoria_id', '')), '')::uuid;
    v_status       TEXT := NULLIF(trim(COALESCE(p_filtros->>'status', '')), '');
    v_busca        TEXT := NULLIF(trim(COALESCE(p_filtros->>'busca', '')), '');
    v_conta        RECORD;
    v_saldo_cad    NUMERIC := 0;
    v_mov_ant      NUMERIC := 0;
    v_saldo_ini    NUMERIC := 0;
    v_entradas     NUMERIC := 0;
    v_saidas       NUMERIC := 0;
    v_ent_pend     NUMERIC := 0;
    v_sai_pend     NUMERIC := 0;
    v_saldo_fim    NUMERIC := 0;
    v_saldo_prev   NUMERIC := 0;
    v_qtd          INT := 0;
    v_evolucao     JSONB;
    v_por_cat      JSONB;
    v_lancamentos  JSONB;
BEGIN
    IF v_fim < v_inicio THEN
        v_fim := v_inicio;
    END IF;

    SELECT * INTO v_conta
    FROM public.contas c
    WHERE c.id = p_conta_id AND (v_user_id IS NULL OR c.user_id = v_user_id)
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN JSONB_BUILD_OBJECT('erro', 'Conta não encontrada', 'conta', NULL);
    END IF;

    v_saldo_cad := COALESCE(v_conta.saldo_inicial, 0);

    -- Saldo realizado acumulado estritamente ANTES de v_inicio
    SELECT COALESCE(SUM(
        CASE
            WHEN l.conta_id = p_conta_id AND l.tipo = 'Receita' THEN l.valor
            WHEN l.destino_id = p_conta_id AND l.tipo = 'Transferência' THEN l.valor
            WHEN l.conta_id = p_conta_id AND l.tipo IN ('Despesa', 'Transferência') THEN -l.valor
            ELSE 0
        END
    ), 0)
    INTO v_mov_ant
    FROM public.lancamentos l
    WHERE (l.user_id = v_conta.user_id OR l.perfil_id = v_conta.user_id)
      AND (l.conta_id = p_conta_id OR l.destino_id = p_conta_id)
      AND l.status = 'Pago'
      AND l.data < v_inicio;

    v_saldo_ini := v_saldo_cad + v_mov_ant;

    -- Entradas e saídas do período na conta (independente de filtro secundário de tipo para os KPIs da conta)
    SELECT
        COALESCE(SUM(CASE
            WHEN l.status = 'Pago' AND ((l.conta_id = p_conta_id AND l.tipo = 'Receita') OR (l.destino_id = p_conta_id AND l.tipo = 'Transferência'))
            THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE
            WHEN l.status = 'Pago' AND (l.conta_id = p_conta_id AND l.tipo IN ('Despesa', 'Transferência'))
            THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE
            WHEN l.status = 'Pendente' AND ((l.conta_id = p_conta_id AND l.tipo = 'Receita') OR (l.destino_id = p_conta_id AND l.tipo = 'Transferência'))
            THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE
            WHEN l.status = 'Pendente' AND (l.conta_id = p_conta_id AND l.tipo IN ('Despesa', 'Transferência'))
            THEN l.valor ELSE 0 END), 0)
    INTO v_entradas, v_saidas, v_ent_pend, v_sai_pend
    FROM public.lancamentos l
    WHERE (l.user_id = v_conta.user_id OR l.perfil_id = v_conta.user_id)
      AND (l.conta_id = p_conta_id OR l.destino_id = p_conta_id)
      AND l.data BETWEEN v_inicio AND v_fim;

    v_saldo_fim  := v_saldo_ini + v_entradas - v_saidas;
    v_saldo_prev := v_saldo_fim + v_ent_pend - v_sai_pend;

    -- Evolução do saldo acumulado dia a dia nos dias com movimento no período
    SELECT COALESCE(JSONB_AGG(row ORDER BY row.data), '[]'::jsonb) INTO v_evolucao
    FROM (
        SELECT
            d.data,
            TO_CHAR(d.data, 'DD/MM') AS label,
            d.entradas,
            d.saidas,
            v_saldo_ini + SUM(d.entradas - d.saidas) OVER (ORDER BY d.data ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS saldo
        FROM (
            SELECT
                l.data,
                SUM(CASE
                    WHEN (l.conta_id = p_conta_id AND l.tipo = 'Receita') OR (l.destino_id = p_conta_id AND l.tipo = 'Transferência')
                    THEN l.valor ELSE 0 END) AS entradas,
                SUM(CASE
                    WHEN l.conta_id = p_conta_id AND l.tipo IN ('Despesa', 'Transferência')
                    THEN l.valor ELSE 0 END) AS saidas
            FROM public.lancamentos l
            WHERE (l.user_id = v_conta.user_id OR l.perfil_id = v_conta.user_id)
              AND (l.conta_id = p_conta_id OR l.destino_id = p_conta_id)
              AND l.data BETWEEN v_inicio AND v_fim
            GROUP BY l.data
        ) d
    ) row;

    -- Normaliza filtro de tipo na conta ('Receita' inclui entradas na conta, 'Despesa' inclui saídas da conta)
    IF v_tipo IS NOT NULL AND lower(v_tipo) IN ('todos', 'all') THEN
        v_tipo := NULL;
    END IF;

    -- Ranking por Categoria na conta
    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_cat
    FROM (
        SELECT
            cat.id AS categoria_id,
            COALESCE(cat.nome, CASE WHEN l.tipo = 'Transferência' THEN 'Transferências' ELSE 'Sem Categoria' END) AS nome,
            COALESCE(cat.cor, CASE WHEN l.tipo = 'Transferência' THEN '#3B82F6' ELSE '#94A3B8' END) AS cor,
            COALESCE(cat.icone, 'category') AS icone,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(GREATEST(v_entradas + v_saidas + v_ent_pend + v_sai_pend, 1), 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_conta.user_id OR l.perfil_id = v_conta.user_id)
          AND (l.conta_id = p_conta_id OR l.destino_id = p_conta_id)
          AND l.data BETWEEN v_inicio AND v_fim
        GROUP BY cat.id, cat.nome, cat.cor, cat.icone, l.tipo
    ) row;

    -- Contagem total com os filtros ativos
    SELECT COUNT(*)::INT INTO v_qtd
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE (l.user_id = v_conta.user_id OR l.perfil_id = v_conta.user_id)
      AND (l.conta_id = p_conta_id OR l.destino_id = p_conta_id)
      AND l.data BETWEEN v_inicio AND v_fim
      AND (
          v_tipo IS NULL
          OR (lower(v_tipo) LIKE 'rec%' AND ((l.conta_id = p_conta_id AND l.tipo = 'Receita') OR (l.destino_id = p_conta_id AND l.tipo = 'Transferência')))
          OR (lower(v_tipo) LIKE 'desp%' AND (l.conta_id = p_conta_id AND l.tipo = 'Despesa'))
          OR (lower(v_tipo) LIKE 'trans%' AND l.tipo = 'Transferência')
      )
      AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
      AND (v_status IS NULL OR l.status::text = v_status)
      AND (
          v_busca IS NULL
          OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
      );

    -- Lançamentos paginados da conta (inclui transferências de entrada/saída)
    SELECT COALESCE(JSONB_AGG(row), '[]'::jsonb) INTO v_lancamentos
    FROM (
        SELECT
            l.id,
            l.tipo,
            l.subtipo,
            l.forma_movimentacao,
            l.valor,
            l.data,
            l.hora,
            l.descricao,
            l.status::text AS status,
            l.regra::text AS regra,
            l.conta_id,
            co.nome AS conta_nome,
            co.cor AS conta_cor,
            l.destino_id,
            cd.nome AS destino_nome,
            l.cartao_id,
            l.categoria_id,
            COALESCE(cat.nome, CASE WHEN l.tipo = 'Transferência' THEN 'Transferência' ELSE 'Sem Categoria' END) AS categoria_nome,
            COALESCE(cat.cor, '#94A3B8') AS categoria_cor,
            COALESCE(cat.icone, 'category') AS categoria_icone,
            l.subcategoria_id,
            sub.nome AS subcategoria_nome,
            l.serie_id,
            l.recorrente_id,
            CASE
                WHEN (l.conta_id = p_conta_id AND l.tipo = 'Receita') OR (l.destino_id = p_conta_id AND l.tipo = 'Transferência')
                THEN 'Entrada'
                ELSE 'Saida'
            END AS direcao_conta
        FROM public.lancamentos l
        LEFT JOIN public.contas co ON co.id = l.conta_id
        LEFT JOIN public.contas cd ON cd.id = l.destino_id
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
        WHERE (l.user_id = v_conta.user_id OR l.perfil_id = v_conta.user_id)
          AND (l.conta_id = p_conta_id OR l.destino_id = p_conta_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              v_tipo IS NULL
              OR (lower(v_tipo) LIKE 'rec%' AND ((l.conta_id = p_conta_id AND l.tipo = 'Receita') OR (l.destino_id = p_conta_id AND l.tipo = 'Transferência')))
              OR (lower(v_tipo) LIKE 'desp%' AND (l.conta_id = p_conta_id AND l.tipo = 'Despesa'))
              OR (lower(v_tipo) LIKE 'trans%' AND l.tipo = 'Transferência')
          )
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        ORDER BY l.data DESC, l.hora DESC, l.criado_em DESC
        LIMIT GREATEST(1, COALESCE(p_limite, 50))
        OFFSET GREATEST(0, COALESCE(p_offset, 0))
    ) row;

    RETURN JSONB_BUILD_OBJECT(
        'conta', JSONB_BUILD_OBJECT(
            'id', v_conta.id,
            'nome', v_conta.nome,
            'tipo_conta', v_conta.tipo_conta,
            'banco', v_conta.banco,
            'cor', COALESCE(v_conta.cor, '#10B981'),
            'icone', COALESCE(v_conta.icone, 'account_balance'),
            'saldo_inicial_cadastro', v_saldo_cad,
            'saldo_atual', COALESCE(v_conta.saldo_atual, v_saldo_cad),
            'saldo_previsto', COALESCE(v_conta.saldo_previsto, v_saldo_cad)
        ),
        'saldo_inicial', v_saldo_ini,
        'entradas', v_entradas,
        'saidas', v_saidas,
        'entradas_pendentes', v_ent_pend,
        'saidas_pendentes', v_sai_pend,
        'saldo_final', v_saldo_fim,
        'saldo_previsto_fim', v_saldo_prev,
        'evolucao_saldo', v_evolucao,
        'por_categoria', v_por_cat,
        'lancamentos', v_lancamentos,
        'total_registros', v_qtd
    );
END;
$$;


-- 6. RPC: Relatório Detalhado de Um Cartão de Crédito (/cartoes/:cartao_id)
CREATE OR REPLACE FUNCTION public.get_relatorio_cartao(
    p_cartao_id   UUID,
    p_data_inicio DATE,
    p_data_fim    DATE,
    p_filtros     JSONB DEFAULT '{}'::jsonb,
    p_limite      INT DEFAULT 50,
    p_offset      INT DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id      UUID := COALESCE(NULLIF(p_filtros->>'user_id', '')::uuid, auth.uid());
    v_inicio       DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
    v_fim          DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
    v_fatura_id    UUID := NULLIF(trim(COALESCE(p_filtros->>'fatura_id', '')), '')::uuid;
    v_categoria_id UUID := NULLIF(trim(COALESCE(p_filtros->>'categoria_id', '')), '')::uuid;
    v_busca        TEXT := NULLIF(trim(COALESCE(p_filtros->>'busca', '')), '');
    v_cartao       RECORD;
    v_gasto_per    NUMERIC := 0;
    v_qtd_compras  INT := 0;
    v_tot_parc     NUMERIC := 0;
    v_tot_avista   NUMERIC := 0;
    v_faturas      JSONB;
    v_por_cat      JSONB;
    v_lancamentos  JSONB;
BEGIN
    SELECT * INTO v_cartao
    FROM public.cartoes c
    WHERE c.id = p_cartao_id AND (v_user_id IS NULL OR c.user_id = v_user_id)
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN JSONB_BUILD_OBJECT('erro', 'Cartão não encontrado', 'cartao', NULL);
    END IF;

    SELECT
        COALESCE(SUM(l.valor), 0),
        COUNT(*)::INT,
        COALESCE(SUM(CASE WHEN COALESCE(l.total_parcelas, 1) > 1 THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN COALESCE(l.total_parcelas, 1) <= 1 THEN l.valor ELSE 0 END), 0)
    INTO v_gasto_per, v_qtd_compras, v_tot_parc, v_tot_avista
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
      AND l.cartao_id = p_cartao_id
      AND (
          (v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id)
          OR (v_fatura_id IS NULL AND l.data BETWEEN v_inicio AND v_fim)
      )
      AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
      AND (
          v_busca IS NULL
          OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
      );

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.ano DESC, row.mes DESC), '[]'::jsonb) INTO v_faturas
    FROM (
        SELECT
            f.id,
            f.mes,
            f.ano,
            COALESCE(f.valor_total, 0) AS valor_total,
            COALESCE(f.valor_pago, 0) AS valor_pago,
            f.status,
            f.data_fechamento,
            f.data_vencimento
        FROM public.faturas f
        WHERE f.cartao_id = p_cartao_id
        ORDER BY f.ano DESC, f.mes DESC
        LIMIT 12
    ) row;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_cat
    FROM (
        SELECT
            cat.id AS categoria_id,
            COALESCE(cat.nome, 'Sem Categoria') AS nome,
            COALESCE(cat.cor, '#F59E0B') AS cor,
            COALESCE(cat.icone, 'category') AS icone,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_gasto_per, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
          AND l.cartao_id = p_cartao_id
          AND (
              (v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id)
              OR (v_fatura_id IS NULL AND l.data BETWEEN v_inicio AND v_fim)
          )
        GROUP BY cat.id, cat.nome, cat.cor, cat.icone
    ) row;

    SELECT COALESCE(JSONB_AGG(row), '[]'::jsonb) INTO v_lancamentos
    FROM (
        SELECT
            l.id,
            l.tipo,
            l.subtipo,
            l.forma_movimentacao,
            l.valor,
            l.data,
            l.hora,
            l.descricao,
            l.status::text AS status,
            l.regra::text AS regra,
            l.cartao_id,
            v_cartao.nome AS cartao_nome,
            v_cartao.cor AS cartao_cor,
            l.categoria_id,
            COALESCE(cat.nome, 'Sem Categoria') AS categoria_nome,
            COALESCE(cat.cor, '#94A3B8') AS categoria_cor,
            COALESCE(cat.icone, 'category') AS categoria_icone,
            l.subcategoria_id,
            sub.nome AS subcategoria_nome,
            l.parcela_atual,
            l.total_parcelas,
            l.fatura_id,
            l.serie_id,
            l.recorrente_id
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
        WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
          AND l.cartao_id = p_cartao_id
          AND (
              (v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id)
              OR (v_fatura_id IS NULL AND l.data BETWEEN v_inicio AND v_fim)
          )
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        ORDER BY l.data DESC, l.hora DESC
        LIMIT GREATEST(1, COALESCE(p_limite, 50))
        OFFSET GREATEST(0, COALESCE(p_offset, 0))
    ) row;

    RETURN JSONB_BUILD_OBJECT(
        'cartao', JSONB_BUILD_OBJECT(
            'id', v_cartao.id,
            'nome', v_cartao.nome,
            'bandeira', v_cartao.bandeira,
            'cor', COALESCE(v_cartao.cor, '#820AD1'),
            'limite_total', COALESCE(v_cartao.limite_total, 0),
            'limite_disponivel', COALESCE(v_cartao.limite_disponivel, COALESCE(v_cartao.limite_total, 0)),
            'limite_usado', GREATEST(0, COALESCE(v_cartao.limite_total, 0) - COALESCE(v_cartao.limite_disponivel, COALESCE(v_cartao.limite_total, 0))),
            'dia_fechamento', v_cartao.dia_fechamento,
            'dia_vencimento', v_cartao.dia_vencimento
        ),
        'totais', JSONB_BUILD_OBJECT(
            'gasto_periodo', v_gasto_per,
            'qtd_compras', v_qtd_compras,
            'ticket_medio', CASE WHEN v_qtd_compras > 0 THEN ROUND(v_gasto_per / v_qtd_compras, 2) ELSE 0 END,
            'total_parcelado', v_tot_parc,
            'total_avista', v_tot_avista
        ),
        'faturas', v_faturas,
        'por_categoria', v_por_cat,
        'lancamentos', v_lancamentos,
        'total_registros', v_qtd_compras
    );
END;
$$;
