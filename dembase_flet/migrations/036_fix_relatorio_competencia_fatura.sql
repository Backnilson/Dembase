-- =============================================================================
-- DemBase v3 - Migration 036
-- CORRECAO DE COMPETENCIA NO RELATORIO DE LANCAMENTOS (ZERO VAZAMENTO ENTRE MESES)
--
-- Problema:
--   A RPC get_relatorio_lancamentos voltou a filtrar por l.data (data da compra)
--   em vez de l.data_vencimento (vencimento da fatura / competencia), causando
--   vazamento de compras, parcelas e recorrencias da fatura de Dezembro/2026
--   para o relatorio de Novembro/2026, alem de omitir metadados da fatura.
--
-- Correcao:
--   1. Filtra exclusivamente por l.data_vencimento BETWEEN v_inicio AND v_fim.
--   2. Agrupa por_dia por b.data_vencimento e ordena lancamentos por
--      b.data_vencimento DESC, b.data DESC.
--   3. Expoe data_vencimento, data_pagamento, fatura_id, fatura_mes, fatura_ano,
--      fatura_status, fatura_data_vencimento, fatura_data_pagamento,
--      fatura_valor_total, tipo_recorrencia e membro_id/nome/cor no JSON.
--   4. Preserva integralmente todas as regras de DemBox, 6 Potes e Perfis.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.get_relatorio_lancamentos(
    p_data_inicio DATE,
    p_data_fim DATE,
    p_filtros JSONB DEFAULT '{}'::jsonb,
    p_limite INTEGER DEFAULT 50,
    p_offset INTEGER DEFAULT 0
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
    v_user_id        UUID := COALESCE(NULLIF(p_filtros->>'user_id', '')::uuid, auth.uid());
    v_inicio         DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
    v_fim            DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
    v_tipo           TEXT := NULLIF(trim(COALESCE(p_filtros->>'tipo', '')), '');
    v_conta_id       UUID := NULLIF(trim(COALESCE(p_filtros->>'conta_id', '')), '')::uuid;
    v_cartao_id      UUID := NULLIF(trim(COALESCE(p_filtros->>'cartao_id', '')), '')::uuid;
    v_fatura_id      UUID := NULLIF(trim(COALESCE(p_filtros->>'fatura_id', '')), '')::uuid;
    v_categoria_id   UUID := NULLIF(trim(COALESCE(p_filtros->>'categoria_id', '')), '')::uuid;
    v_subcat_id      UUID := NULLIF(trim(COALESCE(p_filtros->>'subcategoria_id', '')), '')::uuid;
    v_pote_id        UUID := NULLIF(trim(COALESCE(p_filtros->>'pote_id', '')), '')::uuid;
    v_caixinha_id    UUID := NULLIF(trim(COALESCE(p_filtros->>'caixinha_id', '')), '')::uuid;
    v_modalidade_box TEXT := NULLIF(lower(trim(COALESCE(p_filtros->>'modalidade_box', ''))), '');
    v_tratamento_box TEXT := NULLIF(lower(trim(COALESCE(p_filtros->>'tratamento_box', ''))), '');
    v_membro_id      UUID := NULLIF(trim(COALESCE(p_filtros->>'membro_id', '')), '')::uuid;
    v_regra          TEXT := NULLIF(trim(COALESCE(p_filtros->>'regra', '')), '');
    v_status         TEXT := NULLIF(trim(COALESCE(p_filtros->>'status', '')), '');
    v_forma          TEXT := NULLIF(trim(COALESCE(p_filtros->>'forma', '')), '');
    v_busca          TEXT := NULLIF(trim(COALESCE(p_filtros->>'busca', '')), '');
    v_dias_periodo   INT;
    v_receitas       NUMERIC := 0;
    v_despesas       NUMERIC := 0;
    v_transf         NUMERIC := 0;
    v_pago           NUMERIC := 0;
    v_pendente       NUMERIC := 0;
    v_qtd            INT := 0;
    v_base_total     NUMERIC := 0;
    v_por_cat        JSONB;
    v_por_subcat     JSONB;
    v_por_pote       JSONB;
    v_por_dia        JSONB;
    v_por_forma      JSONB;
    v_lancamentos    JSONB;
BEGIN
    IF v_fim < v_inicio THEN
        v_fim := v_inicio;
    END IF;
    v_dias_periodo := GREATEST(1, (v_fim - v_inicio) + 1);

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

    WITH base AS (
        SELECT l.*, cat.nome AS _cat_nome, cx.modalidade AS _cx_mod, cx.tipo_box AS _cx_tipo
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.caixinhas_teto cx ON cx.id = l.caixinha_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
          AND public.fn_membro_visivel(l.membro_id)
          AND l.data_vencimento BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_fatura_id IS NULL OR l.fatura_id = v_fatura_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
          AND (v_caixinha_id IS NULL OR l.caixinha_id = v_caixinha_id)
          AND (v_membro_id IS NULL OR l.membro_id = v_membro_id)
          AND (
              v_modalidade_box IS NULL
              OR (v_modalidade_box = 'fatura' AND cx.tipo_box = 'fatura')
              OR (v_modalidade_box = 'divida' AND l.caixinha_id IS NOT NULL AND COALESCE(cx.tipo_box, 'padrao') <> 'fatura' AND lower(COALESCE(cx.modalidade, 'provisao_mensal')) IN ('divida', 'quitacao'))
              OR (v_modalidade_box = 'provisao_mensal' AND l.caixinha_id IS NOT NULL AND COALESCE(cx.tipo_box, 'padrao') <> 'fatura' AND lower(COALESCE(cx.modalidade, 'provisao_mensal')) NOT IN ('divida', 'quitacao'))
          )
          AND (
              v_tratamento_box IS NULL
              OR (v_tratamento_box = 'apenas_box' AND l.caixinha_id IS NOT NULL)
              OR (v_tratamento_box = 'ocultar_neutros' AND NOT public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo))
          )
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (
              v_status IS NULL
              OR (v_status = 'Agendado' AND l.status::text = 'Pendente' AND l.data_vencimento > CURRENT_DATE)
              OR (v_status <> 'Agendado' AND l.status::text = v_status)
          )
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
    )
    SELECT
        COALESCE(SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN tipo = 'Despesa' AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text) THEN valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN tipo = 'Transferência' THEN valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN status = 'Pago' AND (tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text)) THEN valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN status = 'Pendente' AND (tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text)) THEN valor ELSE 0 END), 0),
        COUNT(*)::INT
    INTO v_receitas, v_despesas, v_transf, v_pago, v_pendente, v_qtd
    FROM base;

    v_base_total := CASE
        WHEN v_tipo = 'Receita' THEN v_receitas
        WHEN v_tipo = 'Despesa' THEN v_despesas
        WHEN v_tipo = 'Transferência' THEN v_transf
        ELSE (v_receitas + v_despesas)
    END;

    WITH base AS (
        SELECT l.*
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.caixinhas_teto cx ON cx.id = l.caixinha_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id)
          AND public.fn_membro_visivel(l.membro_id)
          AND l.data_vencimento BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_fatura_id IS NULL OR l.fatura_id = v_fatura_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
          AND (v_caixinha_id IS NULL OR l.caixinha_id = v_caixinha_id)
          AND (v_membro_id IS NULL OR l.membro_id = v_membro_id)
          AND (
              v_modalidade_box IS NULL
              OR (v_modalidade_box = 'fatura' AND cx.tipo_box = 'fatura')
              OR (v_modalidade_box = 'divida' AND l.caixinha_id IS NOT NULL AND COALESCE(cx.tipo_box, 'padrao') <> 'fatura' AND lower(COALESCE(cx.modalidade, 'provisao_mensal')) IN ('divida', 'quitacao'))
              OR (v_modalidade_box = 'provisao_mensal' AND l.caixinha_id IS NOT NULL AND COALESCE(cx.tipo_box, 'padrao') <> 'fatura' AND lower(COALESCE(cx.modalidade, 'provisao_mensal')) NOT IN ('divida', 'quitacao'))
          )
          AND (
              v_tratamento_box IS NULL
              OR (v_tratamento_box = 'apenas_box' AND l.caixinha_id IS NOT NULL)
              OR (v_tratamento_box = 'ocultar_neutros' AND NOT public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo))
          )
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (
              v_status IS NULL
              OR (v_status = 'Agendado' AND l.status::text = 'Pendente' AND l.data_vencimento > CURRENT_DATE)
              OR (v_status <> 'Agendado' AND l.status::text = v_status)
          )
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
    )
    SELECT
        (SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) FROM (
            SELECT cat.id AS categoria_id, COALESCE(cat.nome, 'Sem Categoria') AS nome, COALESCE(cat.cor, '#94A3B8') AS cor, COALESCE(cat.icone, 'category') AS icone,
                   SUM(b.valor) AS total, COUNT(*)::INT AS qtd, COALESCE(ROUND(SUM(b.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
            FROM base b LEFT JOIN public.categorias cat ON cat.id = b.categoria_id
            WHERE (b.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(b.caixinha_id, b.subtipo, b.status::text))
            GROUP BY cat.id, cat.nome, cat.cor, cat.icone
        ) row),
        (SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) FROM (
            SELECT sub.id AS subcategoria_id, COALESCE(sub.nome, 'Geral (Sem subcategoria)') AS nome,
                   SUM(b.valor) AS total, COUNT(*)::INT AS qtd, COALESCE(ROUND(SUM(b.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
            FROM base b LEFT JOIN public.subcategorias sub ON sub.id = b.subcategoria_id
            WHERE (b.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(b.caixinha_id, b.subtipo, b.status::text))
            GROUP BY sub.id, sub.nome
        ) row),
        (SELECT COALESCE(JSONB_AGG(row ORDER BY row.posicao), '[]'::jsonb) FROM (
            SELECT pot.id AS pote_id, COALESCE(pot.posicao, 99) AS posicao, COALESCE(pot.nome, 'Sem Pote') AS nome, COALESCE(pot.cor, '#94A3B8') AS cor,
                   SUM(b.valor) AS total, COUNT(*)::INT AS qtd, COALESCE(ROUND(SUM(b.valor) / NULLIF(v_despesas, 0) * 100, 1), 0) AS percentual
            FROM base b LEFT JOIN public.potes pot ON pot.id = b.pote_id
            WHERE b.tipo = 'Despesa'
              AND (v_tipo IS NULL OR v_tipo = 'Despesa')
              AND public.fn_eh_despesa_orcamento_ativa(b.caixinha_id, b.subtipo, b.status::text)
            GROUP BY pot.id, pot.posicao, pot.nome, pot.cor
        ) row),
        (SELECT COALESCE(JSONB_AGG(row ORDER BY row.data), '[]'::jsonb) FROM (
            SELECT b.data_vencimento AS data, TO_CHAR(b.data_vencimento, 'DD/MM') AS label,
                   SUM(CASE WHEN b.tipo = 'Receita' THEN b.valor ELSE 0 END) AS receitas,
                   SUM(CASE WHEN b.tipo = 'Despesa' AND public.fn_eh_despesa_orcamento_ativa(b.caixinha_id, b.subtipo, b.status::text) THEN b.valor ELSE 0 END) AS despesas,
                   SUM(CASE WHEN b.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(b.caixinha_id, b.subtipo, b.status::text) THEN b.valor ELSE 0 END) AS total
            FROM base b GROUP BY b.data_vencimento
        ) row),
        (SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) FROM (
            SELECT COALESCE(b.forma_movimentacao, 'Outros') AS forma, SUM(b.valor) AS total, COUNT(*)::INT AS qtd,
                   COALESCE(ROUND(SUM(b.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
            FROM base b
            WHERE (b.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(b.caixinha_id, b.subtipo, b.status::text))
            GROUP BY b.forma_movimentacao
        ) row),
        (SELECT COALESCE(JSONB_AGG(row), '[]'::jsonb) FROM (
            SELECT
                b.id, b.tipo, b.subtipo, b.forma_movimentacao, b.valor,
                b.data, b.data_vencimento, b.data_pagamento, b.hora, b.descricao,
                b.status::text AS status, b.regra::text AS regra,
                b.fatura_id, f.mes AS fatura_mes, f.ano AS fatura_ano, f.status AS fatura_status,
                f.data_vencimento AS fatura_data_vencimento, f.data_pagamento AS fatura_data_pagamento,
                f.valor_total AS fatura_valor_total,
                b.pote_id, pot.nome AS pote_nome, pot.cor AS pote_cor,
                b.conta_id, co.nome AS conta_nome, co.cor AS conta_cor,
                b.destino_id, cd.nome AS destino_nome,
                b.cartao_id, ca.nome AS cartao_nome, ca.cor AS cartao_cor,
                b.caixinha_id, cx.nome AS caixinha_nome, cx.cor AS caixinha_cor,
                b.membro_id, mb.nome AS membro_nome, mb.cor AS membro_cor,
                public.fn_eh_consumo_caixinha_neutro(b.caixinha_id, b.subtipo) AS neutro_caixinha,
                b.categoria_id, COALESCE(cat.nome, 'Sem Categoria') AS categoria_nome, COALESCE(cat.cor, '#94A3B8') AS categoria_cor, COALESCE(cat.icone, 'category') AS categoria_icone,
                b.subcategoria_id, sub.nome AS subcategoria_nome,
                b.parcela_atual, b.total_parcelas, b.serie_id, b.recorrente_id, b.tipo_recorrencia
            FROM base b
            LEFT JOIN public.faturas f ON f.id = b.fatura_id
            LEFT JOIN public.potes pot ON pot.id = b.pote_id
            LEFT JOIN public.contas co ON co.id = b.conta_id
            LEFT JOIN public.contas cd ON cd.id = b.destino_id
            LEFT JOIN public.cartoes ca ON ca.id = b.cartao_id
            LEFT JOIN public.caixinhas_teto cx ON cx.id = b.caixinha_id
            LEFT JOIN public.membros mb ON mb.id = b.membro_id
            LEFT JOIN public.categorias cat ON cat.id = b.categoria_id
            LEFT JOIN public.subcategorias sub ON sub.id = b.subcategoria_id
            ORDER BY b.data_vencimento DESC, b.data DESC, b.hora DESC, b.criado_em DESC
            LIMIT GREATEST(1, COALESCE(p_limite, 50))
            OFFSET GREATEST(0, COALESCE(p_offset, 0))
        ) row)
    INTO v_por_cat, v_por_subcat, v_por_pote, v_por_dia, v_por_forma, v_lancamentos;

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
        'por_pote', v_por_pote,
        'por_dia', v_por_dia,
        'por_forma', v_por_forma,
        'lancamentos', v_lancamentos,
        'total_registros', v_qtd
    );
END;
$function$;

NOTIFY pgrst, 'reload schema';
