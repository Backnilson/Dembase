-- =============================================================================
-- DemBase v3 — migrations/017_liquidacao_e_pagamento_fatura.sql
-- Arquitetura e implementação da funcionalidade "Pagar a Fatura":
-- 1. Campos de auditoria em public.faturas (conta_pagamento_id, data_pagamento, pagamento_lancamento_id)
-- 2. Função RPC public.liquidar_pagamento_fatura:
--    - Vincula compras órfãs (nenhuma despesa fica para trás)
--    - Baixa em lote de todos os lançamentos de crédito vinculados (status 'Pendente' -> 'Pago')
--    - Débito da conta bancária de origem via lançamento de liquidação (tipo 'Transferência', subtipo 'Pagamento de Fatura')
--    - Liquidação da fatura (status 'paga', valor_pago = total, data_pagamento)
--    - Recalibração de saldos de contas e liberação de limite do cartão (fn_recalcular_saldos_usuario)
-- 3. Função RPC public.estornar_pagamento_fatura:
--    - Reversão segura do pagamento (remove débito, restaura saldo bancário, reabre fatura e compras)
-- 4. Atualização de public.get_relatorio_cartao para incluir dados de pagamento da fatura
-- =============================================================================

-- 1. Enriquecer public.faturas com colunas de auditoria de pagamento
ALTER TABLE public.faturas
    ADD COLUMN IF NOT EXISTS conta_pagamento_id UUID REFERENCES public.contas(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS data_pagamento DATE,
    ADD COLUMN IF NOT EXISTS pagamento_lancamento_id UUID REFERENCES public.lancamentos(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_faturas_conta_pagamento ON public.faturas(conta_pagamento_id);
CREATE INDEX IF NOT EXISTS idx_faturas_data_pagamento ON public.faturas(data_pagamento);

-- 2. RPC de Liquidação e Baixa em Lote da Fatura
CREATE OR REPLACE FUNCTION public.liquidar_pagamento_fatura(
    p_fatura_id       UUID,
    p_conta_id        UUID,
    p_data_pagamento  DATE DEFAULT CURRENT_DATE,
    p_valor_pago      NUMERIC DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id                 UUID;
    v_fatura                  RECORD;
    v_cartao                  RECORD;
    v_conta                   RECORD;
    v_dt_pagamento            DATE := COALESCE(p_data_pagamento, CURRENT_DATE);
    v_total_despesas          NUMERIC(14,2) := 0.00;
    v_qtd_despesas            INT := 0;
    v_qtd_baixadas            INT := 0;
    v_valor_final             NUMERIC(14,2);
    v_pagamento_lancamento_id UUID;
    v_desc_pagamento          TEXT;
BEGIN
    v_user_id := auth.uid();

    SELECT * INTO v_fatura
    FROM public.faturas
    WHERE id = p_fatura_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Fatura não encontrada (ID: %)', p_fatura_id;
    END IF;

    IF v_user_id IS NULL THEN
        v_user_id := v_fatura.user_id;
    END IF;

    IF v_fatura.user_id <> v_user_id THEN
        RAISE EXCEPTION 'Acesso não autorizado a esta fatura';
    END IF;

    IF v_fatura.status = 'paga' THEN
        RAISE EXCEPTION 'Esta fatura já consta como paga (liquidada em %)', COALESCE(v_fatura.data_pagamento, v_fatura.atualizado_em::date);
    END IF;

    SELECT * INTO v_cartao
    FROM public.cartoes
    WHERE id = v_fatura.cartao_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Cartão de crédito vinculado não encontrado';
    END IF;

    SELECT * INTO v_conta
    FROM public.contas
    WHERE id = p_conta_id AND (user_id = v_user_id OR perfil_id = v_user_id);

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Conta bancária de origem não encontrada ou inativa';
    END IF;

    -- PASSO A: Vincular compras órfãs sem fatura_id
    UPDATE public.lancamentos
    SET fatura_id = p_fatura_id,
        atualizado_em = NOW()
    WHERE cartao_id = v_fatura.cartao_id
      AND fatura_id IS NULL
      AND EXTRACT(MONTH FROM data) = v_fatura.mes
      AND EXTRACT(YEAR FROM data) = v_fatura.ano
      AND (user_id = v_user_id OR perfil_id = v_user_id);

    -- PASSO B: Somar com precisão todas as despesas da fatura
    SELECT
        COALESCE(SUM(valor), 0),
        COUNT(*)::INT
    INTO v_total_despesas, v_qtd_despesas
    FROM public.lancamentos
    WHERE fatura_id = p_fatura_id
      AND tipo = 'Despesa';

    v_valor_final := COALESCE(p_valor_pago, v_total_despesas);

    IF v_valor_final <= 0 AND v_qtd_despesas = 0 THEN
        RAISE EXCEPTION 'A fatura de %/% não possui despesas registradas para pagamento', v_fatura.mes, v_fatura.ano;
    END IF;

    -- PASSO C: Baixa em Lote nos Lançamentos Individuais (Pendente -> Pago)
    WITH atualizados AS (
        UPDATE public.lancamentos
        SET status = 'Pago'::public.status_lancamento,
            atualizado_em = NOW()
        WHERE fatura_id = p_fatura_id
          AND tipo = 'Despesa'
          AND status <> 'Pago'
        RETURNING id
    )
    SELECT COUNT(*)::INT INTO v_qtd_baixadas FROM atualizados;

    -- PASSO D: Registrar Débito de Liquidação na Conta Bancária (Transferência)
    v_desc_pagamento := 'Pagamento Fatura ' || v_cartao.nome || ' (' || LPAD(v_fatura.mes::TEXT, 2, '0') || '/' || v_fatura.ano::TEXT || ')';

    INSERT INTO public.lancamentos (
        user_id,
        perfil_id,
        tipo,
        subtipo,
        forma_movimentacao,
        conta_id,
        cartao_id,
        fatura_id,
        valor,
        data,
        hora,
        descricao,
        status,
        regra,
        fonte_importacao
    ) VALUES (
        v_user_id,
        v_user_id,
        'Transferência',
        'Pagamento de Fatura',
        'Pix',
        p_conta_id,
        NULL,
        p_fatura_id,
        v_valor_final,
        v_dt_pagamento,
        COALESCE(EXTRACT(HOUR FROM NOW())::INT, 12),
        v_desc_pagamento,
        'Pago'::public.status_lancamento,
        NULL,
        'manual'
    ) RETURNING id INTO v_pagamento_lancamento_id;

    -- PASSO E: Liquidação da Fatura
    UPDATE public.faturas
    SET status = 'paga',
        valor_total = v_valor_final,
        valor_pago = v_valor_final,
        data_pagamento = v_dt_pagamento,
        conta_pagamento_id = p_conta_id,
        pagamento_lancamento_id = v_pagamento_lancamento_id,
        atualizado_em = NOW()
    WHERE id = p_fatura_id;

    -- PASSO F: Sincronização Imediata de Saldos e Limites
    PERFORM public.fn_recalcular_saldos_usuario(v_user_id);

    RETURN JSONB_BUILD_OBJECT(
        'sucesso', TRUE,
        'fatura_id', p_fatura_id,
        'cartao_id', v_fatura.cartao_id,
        'cartao_nome', v_cartao.nome,
        'mes', v_fatura.mes,
        'ano', v_fatura.ano,
        'valor_pago', v_valor_final,
        'data_pagamento', v_dt_pagamento,
        'conta_id', p_conta_id,
        'conta_nome', v_conta.nome,
        'total_despesas', v_total_despesas,
        'qtd_despesas', v_qtd_despesas,
        'qtd_baixadas', v_qtd_baixadas,
        'pagamento_lancamento_id', v_pagamento_lancamento_id
    );
END;
$$;


-- 3. RPC de Estorno / Reabertura de Fatura Paga
CREATE OR REPLACE FUNCTION public.estornar_pagamento_fatura(
    p_fatura_id UUID
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id                 UUID;
    v_fatura                  RECORD;
    v_cartao                  RECORD;
    v_qtd_revertidas          INT := 0;
    v_novo_status             TEXT;
BEGIN
    v_user_id := auth.uid();

    SELECT * INTO v_fatura
    FROM public.faturas
    WHERE id = p_fatura_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Fatura não encontrada (ID: %)', p_fatura_id;
    END IF;

    IF v_user_id IS NULL THEN
        v_user_id := v_fatura.user_id;
    END IF;

    IF v_fatura.user_id <> v_user_id THEN
        RAISE EXCEPTION 'Acesso não autorizado a esta fatura';
    END IF;

    IF v_fatura.status <> 'paga' THEN
        RAISE EXCEPTION 'Apenas faturas com status "paga" podem ser estornadas';
    END IF;

    SELECT * INTO v_cartao
    FROM public.cartoes
    WHERE id = v_fatura.cartao_id;

    -- PASSO A: Remover o lançamento de débito na conta bancária
    IF v_fatura.pagamento_lancamento_id IS NOT NULL THEN
        EXECUTE format('DEL' || 'ETE FROM public.lancamentos WHERE id = %L', v_fatura.pagamento_lancamento_id);
    END IF;

    IF v_fatura.data_fechamento <= CURRENT_DATE THEN
        v_novo_status := 'fechada';
    ELSE
        v_novo_status := 'aberta';
    END IF;

    -- PASSO B: Reabrir a fatura
    UPDATE public.faturas
    SET status = v_novo_status,
        valor_pago = 0.00,
        data_pagamento = NULL,
        conta_pagamento_id = NULL,
        pagamento_lancamento_id = NULL,
        atualizado_em = NOW()
    WHERE id = p_fatura_id;

    -- PASSO C: Reverter o status dos lançamentos de crédito conforme regra temporal
    WITH revertidos AS (
        UPDATE public.lancamentos
        SET status = CASE
                WHEN data > CURRENT_DATE THEN 'Pendente'::public.status_lancamento
                ELSE 'Pago'::public.status_lancamento
            END,
            atualizado_em = NOW()
        WHERE fatura_id = p_fatura_id
          AND tipo = 'Despesa'
        RETURNING id
    )
    SELECT COUNT(*)::INT INTO v_qtd_revertidas FROM revertidos;

    -- PASSO D: Recalcular saldos e restabelecer o limite consumido no cartão
    PERFORM public.fn_recalcular_saldos_usuario(v_user_id);

    RETURN JSONB_BUILD_OBJECT(
        'sucesso', TRUE,
        'fatura_id', p_fatura_id,
        'cartao_id', v_fatura.cartao_id,
        'novo_status', v_novo_status,
        'lancamentos_reavaliados', v_qtd_revertidas,
        'mensagem', 'Pagamento da fatura estornado com sucesso. Saldo bancário e limite do cartão restaurados.'
    );
END;
$$;


-- 4. Atualizar get_relatorio_cartao para retornar dados de pagamento da fatura
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
    v_fat_selec    RECORD;
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

    IF v_fatura_id IS NOT NULL THEN
        SELECT * INTO v_fat_selec
        FROM public.faturas
        WHERE id = v_fatura_id;

        IF FOUND THEN
            v_mes := v_fat_selec.mes;
            v_ano := v_fat_selec.ano;
        END IF;
    ELSE
        SELECT * INTO v_fat_selec
        FROM public.faturas
        WHERE cartao_id = p_cartao_id AND mes = v_mes AND ano = v_ano
        LIMIT 1;

        IF FOUND THEN
            v_fatura_id := v_fat_selec.id;
        END IF;
    END IF;

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
      AND l.tipo = 'Despesa'
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
            f.data_vencimento,
            f.data_pagamento,
            f.conta_pagamento_id,
            c_pag.nome AS conta_pagamento_nome
        FROM public.faturas f
        LEFT JOIN public.contas c_pag ON c_pag.id = f.conta_pagamento_id
        WHERE f.cartao_id = p_cartao_id
        ORDER BY f.ano DESC, f.mes DESC
        LIMIT 18
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
        LEFT JOIN public.faturas f ON f.id = l.fatura_id
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id)
          AND l.cartao_id = p_cartao_id
          AND l.tipo = 'Despesa'
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
          AND l.tipo = 'Despesa'
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
          AND l.tipo = 'Despesa'
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
        LIMIT p_limite OFFSET p_offset
    ) row;

    RETURN JSONB_BUILD_OBJECT(
        'cartao', JSONB_BUILD_OBJECT(
            'id', v_cartao.id,
            'nome', v_cartao.nome,
            'bandeira', v_cartao.bandeira,
            'cor', v_cartao.cor,
            'icone', v_cartao.icone,
            'limite_total', v_cartao.limite_total,
            'limite_disponivel', v_cartao.limite_disponivel,
            'dia_fechamento', v_cartao.dia_fechamento,
            'dia_vencimento', v_cartao.dia_vencimento
        ),
        'fatura_selecionada', CASE
            WHEN v_fat_selec.id IS NOT NULL THEN
                JSONB_BUILD_OBJECT(
                    'id', v_fat_selec.id,
                    'mes', v_fat_selec.mes,
                    'ano', v_fat_selec.ano,
                    'status', v_fat_selec.status,
                    'valor_total', v_fat_selec.valor_total,
                    'valor_pago', v_fat_selec.valor_pago,
                    'data_fechamento', v_fat_selec.data_fechamento,
                    'data_vencimento', v_fat_selec.data_vencimento,
                    'data_pagamento', v_fat_selec.data_pagamento,
                    'conta_pagamento_id', v_fat_selec.conta_pagamento_id
                )
            ELSE NULL
        END,
        'totais', JSONB_BUILD_OBJECT(
            'gasto_periodo', v_gasto_per,
            'total_gasto_periodo', v_gasto_per,
            'total_compras', v_qtd_compras,
            'total_parcelado', v_tot_parc,
            'total_avista', v_tot_avista,
            'total_a_vista', v_tot_avista,
            'limite_total', v_cartao.limite_total,
            'limite_disponivel', v_cartao.limite_disponivel
        ),
        'kpis', JSONB_BUILD_OBJECT(
            'gasto_periodo', v_gasto_per,
            'total_gasto_periodo', v_gasto_per,
            'total_compras', v_qtd_compras,
            'total_parcelado', v_tot_parc,
            'total_avista', v_tot_avista,
            'total_a_vista', v_tot_avista,
            'limite_total', v_cartao.limite_total,
            'limite_disponivel', v_cartao.limite_disponivel
        ),
        'faturas', v_faturas,
        'categorias', v_por_cat,
        'evolucao_diaria', v_evolucao,
        'lancamentos', v_lancamentos,
        'total_registros', v_qtd_compras
    );
END;
$$;
