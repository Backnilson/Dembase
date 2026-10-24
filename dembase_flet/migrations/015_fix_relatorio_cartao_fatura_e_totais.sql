-- =============================================================================
-- DemBase v3 — migrations/015_fix_relatorio_cartao_fatura_e_totais.sql
-- Correção crítica do Relatório de Cartão de Crédito (get_relatorio_cartao):
-- 1. Precedência absoluta da "Fatura Vinculada/Destino" (mês/ano da fatura)
--    sobre a data de compra real (data da compra é apenas para exibição).
-- 2. Compatibilidade total de chaves nos totais e kpis (gasto_periodo,
--    total_gasto_periodo, total_parcelado, total_avista, total_a_vista).
-- 3. Retorno explícito de status_parcelamento ('Parcela X de Y', 'Recorrência', 'À vista').
-- =============================================================================

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
    v_mes          INT := COALESCE(NULLIF(trim(p_filtros->>'mes'), '')::INT, EXTRACT(MONTH FROM v_inicio)::INT);
    v_ano          INT := COALESCE(NULLIF(trim(p_filtros->>'ano'), '')::INT, EXTRACT(YEAR FROM v_inicio)::INT);
    v_categoria_id UUID := NULLIF(trim(COALESCE(p_filtros->>'categoria_id', '')), '')::uuid;
    v_busca        TEXT := NULLIF(trim(COALESCE(p_filtros->>'busca', '')), '');
    v_cartao       RECORD;
    v_gasto_per    NUMERIC := 0;
    v_qtd_compras  INT := 0;
    v_tot_parc     NUMERIC := 0;
    v_tot_avista   NUMERIC := 0;
    v_faturas      JSONB;
    v_por_cat      JSONB;
    v_evolucao     JSONB;
    v_lancamentos  JSONB;
BEGIN
    SELECT * INTO v_cartao
    FROM public.cartoes c
    WHERE c.id = p_cartao_id AND (v_user_id IS NULL OR c.user_id = v_user_id)
    LIMIT 1;

    IF NOT FOUND THEN
        RETURN JSONB_BUILD_OBJECT('erro', 'Cartão não encontrado', 'cartao', NULL);
    END IF;

    -- Se passou v_fatura_id explícito, sincroniza o mês e o ano da fatura selecionada
    IF v_fatura_id IS NOT NULL THEN
        SELECT mes, ano INTO v_mes, v_ano
        FROM public.faturas
        WHERE id = v_fatura_id;
    ELSE
        -- Tenta localizar se já existe uma fatura criada para este cartão no mês/ano alvo
        SELECT id INTO v_fatura_id
        FROM public.faturas
        WHERE cartao_id = p_cartao_id AND mes = v_mes AND ano = v_ano
        LIMIT 1;
    END IF;

    -- 1. Totais da Fatura Específica (varre lançamentos vinculados à fatura de destino)
    SELECT
        COALESCE(SUM(l.valor), 0),
        COUNT(*)::INT,
        COALESCE(SUM(CASE WHEN COALESCE(l.total_parcelas, 1) > 1 OR l.recorrente_id IS NOT NULL THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN COALESCE(l.total_parcelas, 1) <= 1 AND l.recorrente_id IS NULL THEN l.valor ELSE 0 END), 0)
    INTO v_gasto_per, v_qtd_compras, v_tot_parc, v_tot_avista
    FROM public.lancamentos l
    LEFT JOIN public.faturas f ON f.id = l.fatura_id
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
      AND l.cartao_id = p_cartao_id
      AND (
          -- Regra Principal: Fatura Vinculada/Destino
          (
              l.fatura_id IS NOT NULL 
              AND (
                  (v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id)
                  OR (f.mes = v_mes AND f.ano = v_ano)
              )
          )
          -- Fallback: compras antigas órfãs sem fatura vinculada
          OR (
              l.fatura_id IS NULL
              AND EXTRACT(MONTH FROM l.data) = v_mes
              AND EXTRACT(YEAR FROM l.data) = v_ano
          )
      )
      AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
      AND (
          v_busca IS NULL
          OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
      );

    -- 2. Lista de Faturas do Cartão
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
        LIMIT 18
    ) row;

    -- 3. Agrupamento por Categoria dentro da Fatura
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
        LEFT JOIN public.faturas f ON f.id = l.fatura_id
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
          AND l.cartao_id = p_cartao_id
          AND (
              (
                  l.fatura_id IS NOT NULL 
                  AND (
                      (v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id)
                      OR (f.mes = v_mes AND f.ano = v_ano)
                  )
              )
              OR (
                  l.fatura_id IS NULL
                  AND EXTRACT(MONTH FROM l.data) = v_mes
                  AND EXTRACT(YEAR FROM l.data) = v_ano
              )
          )
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY cat.id, cat.nome, cat.cor, cat.icone
    ) row;

    -- 4. Ritmo Diário de Compras pertencentes à Fatura
    SELECT COALESCE(JSONB_AGG(row ORDER BY row.data ASC), '[]'::jsonb) INTO v_evolucao
    FROM (
        SELECT
            l.data,
            SUM(l.valor) AS valor,
            COUNT(*)::INT AS qtd
        FROM public.lancamentos l
        LEFT JOIN public.faturas f ON f.id = l.fatura_id
        WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
          AND l.cartao_id = p_cartao_id
          AND (
              (
                  l.fatura_id IS NOT NULL 
                  AND (
                      (v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id)
                      OR (f.mes = v_mes AND f.ano = v_ano)
                  )
              )
              OR (
                  l.fatura_id IS NULL
                  AND EXTRACT(MONTH FROM l.data) = v_mes
                  AND EXTRACT(YEAR FROM l.data) = v_ano
              )
          )
        GROUP BY l.data
    ) row;

    -- 5. Lançamentos Detalhados da Fatura com status de parcelamento explícito
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
            f.mes AS fatura_mes,
            f.ano AS fatura_ano,
            f.status AS fatura_status,
            CASE
                WHEN COALESCE(l.total_parcelas, 1) > 1 THEN
                    'Parcela ' || COALESCE(l.parcela_atual, 1) || ' de ' || l.total_parcelas
                WHEN l.recorrente_id IS NOT NULL THEN
                    'Recorrência'
                ELSE
                    'À vista'
            END AS status_parcelamento,
            l.serie_id,
            l.recorrente_id
        FROM public.lancamentos l
        LEFT JOIN public.faturas f ON f.id = l.fatura_id
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
        WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
          AND l.cartao_id = p_cartao_id
          AND (
              (
                  l.fatura_id IS NOT NULL 
                  AND (
                      (v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id)
                      OR (f.mes = v_mes AND f.ano = v_ano)
                  )
              )
              OR (
                  l.fatura_id IS NULL
                  AND EXTRACT(MONTH FROM l.data) = v_mes
                  AND EXTRACT(YEAR FROM l.data) = v_ano
              )
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

    -- 6. Retorno enriquecido compatível com kpis e totais
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
            'total_gasto_periodo', v_gasto_per,
            'qtd_compras', v_qtd_compras,
            'ticket_medio', CASE WHEN v_qtd_compras > 0 THEN ROUND(v_gasto_per / v_qtd_compras, 2) ELSE 0 END,
            'total_parcelado', v_tot_parc,
            'total_avista', v_tot_avista,
            'total_a_vista', v_tot_avista
        ),
        'kpis', JSONB_BUILD_OBJECT(
            'total_gasto_periodo', v_gasto_per,
            'gasto_periodo', v_gasto_per,
            'qtd_compras', v_qtd_compras,
            'ticket_medio', CASE WHEN v_qtd_compras > 0 THEN ROUND(v_gasto_per / v_qtd_compras, 2) ELSE 0 END,
            'total_parcelado', v_tot_parc,
            'total_avista', v_tot_avista,
            'total_a_vista', v_tot_avista,
            'limite_total', COALESCE(v_cartao.limite_total, 0),
            'limite_disponivel', COALESCE(v_cartao.limite_disponivel, COALESCE(v_cartao.limite_total, 0))
        ),
        'faturas', v_faturas,
        'fatura_selecionada', JSONB_BUILD_OBJECT(
            'id', v_fatura_id,
            'mes', v_mes,
            'ano', v_ano
        ),
        'evolucao_diaria', COALESCE(v_evolucao, '[]'::jsonb),
        'por_categoria', COALESCE(v_por_cat, '[]'::jsonb),
        'lancamentos', COALESCE(v_lancamentos, '[]'::jsonb),
        'total_registros', v_qtd_compras
    );
END;
$$;
