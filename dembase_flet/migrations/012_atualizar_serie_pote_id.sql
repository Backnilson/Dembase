-- =============================================================================
-- DemBase v3 — Migration 012: Suporte a Pote Financeiro em Séries e Recorrências
-- Adiciona a coluna pote_id na tabela transacoes_recorrentes e atualiza a RPC
-- atualizar_serie para replicar pote_id em lançamentos futuros e no agendamento recorrente.
-- =============================================================================

-- 1. Coluna pote_id na tabela transacoes_recorrentes
ALTER TABLE public.transacoes_recorrentes
ADD COLUMN IF NOT EXISTS pote_id UUID REFERENCES public.potes(id) ON DELETE SET NULL;

-- 2. Atualizar RPC atualizar_serie com suporte a pote_id
CREATE OR REPLACE FUNCTION public.atualizar_serie(
    p_serie_id UUID,
    p_dados JSONB,
    p_a_partir_de DATE DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_afetados INT := 0;
    v_rec_id UUID;
BEGIN
    UPDATE public.lancamentos
    SET
        descricao = COALESCE(NULLIF(trim(p_dados->>'descricao'), ''), descricao),
        categoria_id = CASE WHEN p_dados ? 'categoria_id' THEN NULLIF(p_dados->>'categoria_id', '')::uuid ELSE categoria_id END,
        subcategoria_id = CASE WHEN p_dados ? 'subcategoria_id' THEN NULLIF(p_dados->>'subcategoria_id', '')::uuid ELSE subcategoria_id END,
        conta_id = CASE WHEN p_dados ? 'conta_id' THEN NULLIF(p_dados->>'conta_id', '')::uuid ELSE conta_id END,
        cartao_id = CASE WHEN p_dados ? 'cartao_id' THEN NULLIF(p_dados->>'cartao_id', '')::uuid ELSE cartao_id END,
        pote_id = CASE WHEN p_dados ? 'pote_id' THEN NULLIF(p_dados->>'pote_id', '')::uuid ELSE pote_id END,
        forma_movimentacao = COALESCE(NULLIF(trim(p_dados->>'forma_movimentacao'), ''), forma_movimentacao),
        subtipo = COALESCE(NULLIF(trim(p_dados->>'subtipo'), ''), subtipo),
        regra = CASE
            WHEN p_dados ? 'regra' AND p_dados->>'regra' IN ('Essencial', 'Estilo de Vida', 'Investimento')
            THEN (p_dados->>'regra')::regra_financeira
            ELSE regra
        END,
        valor = CASE WHEN p_dados ? 'valor' AND NULLIF(p_dados->>'valor', '') IS NOT NULL THEN (p_dados->>'valor')::numeric ELSE valor END,
        atualizado_em = NOW()
    WHERE (serie_id = p_serie_id OR recorrente_id = p_serie_id)
      AND (p_a_partir_de IS NULL OR data >= p_a_partir_de);

    GET DIAGNOSTICS v_afetados = ROW_COUNT;

    SELECT DISTINCT recorrente_id INTO v_rec_id
    FROM public.lancamentos
    WHERE (serie_id = p_serie_id OR recorrente_id = p_serie_id)
      AND recorrente_id IS NOT NULL
    LIMIT 1;

    IF v_rec_id IS NOT NULL THEN
        UPDATE public.transacoes_recorrentes
        SET
            descricao = COALESCE(NULLIF(trim(p_dados->>'descricao'), ''), descricao),
            categoria_id = CASE WHEN p_dados ? 'categoria_id' THEN NULLIF(p_dados->>'categoria_id', '')::uuid ELSE categoria_id END,
            subcategoria_id = CASE WHEN p_dados ? 'subcategoria_id' THEN NULLIF(p_dados->>'subcategoria_id', '')::uuid ELSE subcategoria_id END,
            conta_id = CASE WHEN p_dados ? 'conta_id' THEN NULLIF(p_dados->>'conta_id', '')::uuid ELSE conta_id END,
            cartao_id = CASE WHEN p_dados ? 'cartao_id' THEN NULLIF(p_dados->>'cartao_id', '')::uuid ELSE cartao_id END,
            pote_id = CASE WHEN p_dados ? 'pote_id' THEN NULLIF(p_dados->>'pote_id', '')::uuid ELSE pote_id END,
            forma_movimentacao = COALESCE(NULLIF(trim(p_dados->>'forma_movimentacao'), ''), forma_movimentacao),
            subtipo = COALESCE(NULLIF(trim(p_dados->>'subtipo'), ''), subtipo),
            regra = CASE
                WHEN p_dados ? 'regra' AND p_dados->>'regra' IN ('Essencial', 'Estilo de Vida', 'Investimento')
                THEN p_dados->>'regra'
                ELSE regra
            END,
            valor = CASE WHEN p_dados ? 'valor' AND NULLIF(p_dados->>'valor', '') IS NOT NULL THEN (p_dados->>'valor')::numeric ELSE valor END
        WHERE id = v_rec_id;
    END IF;

    RETURN jsonb_build_object('sucesso', true, 'afetados', v_afetados);
END;
$$;
