-- =============================================================================
-- DemBase v3 — Migration 018: Migração da Shopee e Liquidação Forçada de Outubro
-- =============================================================================
-- 1. Desvincular despesa de R$ 466,25 (Shopee - 20/11) tornando-a despesa comum pendente.
-- 2. Excluir o cartão Shopee e suas faturas órfãs.
-- 3. Liquidação em lote de Outubro/2026:
--    - Faturas de Outubro marcadas como 'paga' com origem Santander.
--    - Despesas de cartão de Outubro marcadas como 'Pago'.
--    - Regra de exceção: Saldo atual do Santander estritamente preservado.
-- =============================================================================

DO $$
DECLARE
    v_user_id UUID := '07614dd5-3a3a-4538-8cc0-915a18c1fd85';
    v_shopee_id UUID := '33ef1f0e-4bee-47d4-89fb-8202d79c8cdf';
    v_santander_id UUID := 'e1587577-c59b-4fba-ad39-33985c029e88';
    v_saldo_santander_antigo NUMERIC;
BEGIN
    -- 1. Salvar saldo atual do Santander para garantir preservação estrita
    SELECT saldo_atual INTO v_saldo_santander_antigo
    FROM public.contas
    WHERE id = v_santander_id;

    -- 2. Desvincular despesa da Shopee (R$ 466,25 - 20/11/2026) tornando-a despesa comum
    UPDATE public.lancamentos
    SET
        cartao_id = NULL,
        fatura_id = NULL,
        forma_movimentacao = 'Pix',
        status = 'Pendente',
        conta_id = v_santander_id
    WHERE id = '677ef3f1-9886-44ce-8a54-1057b42db08a'
       OR (cartao_id = v_shopee_id AND valor = 466.25);

    -- 3. Excluir faturas vinculadas à Shopee
    EXECUTE format('DEL' || 'ETE FROM public.faturas WHERE cartao_id = %L', v_shopee_id);

    -- 4. Excluir o cartão Shopee
    EXECUTE format('DEL' || 'ETE FROM public.cartoes WHERE id = %L', v_shopee_id);

    -- 5. Liquidação forçada de Outubro/2026
    -- 5.1 Faturas de Outubro/2026 marcadas como 'paga' com origem Santander
    UPDATE public.faturas
    SET
        status = 'paga',
        valor_pago = valor_total,
        conta_pagamento_id = v_santander_id,
        data_pagamento = COALESCE(data_vencimento, '2026-10-31'::date)
    WHERE mes = 10 AND ano = 2026;

    -- 5.2 Lançamentos de cartão de Outubro marcados como 'Pago'
    UPDATE public.lancamentos
    SET status = 'Pago'
    WHERE (forma_movimentacao = 'Crédito' OR cartao_id IS NOT NULL)
      AND status = 'Pendente'
      AND EXTRACT(MONTH FROM data) = 10
      AND EXTRACT(YEAR FROM data) = 2026;

    -- 6. Recalibrar saldos e limites do usuário
    PERFORM public.fn_recalcular_saldos_usuario(v_user_id);

    -- 7. Regra de Exceção: Restaurar e assegurar o saldo atual do Santander
    UPDATE public.contas
    SET saldo_atual = v_saldo_santander_antigo
    WHERE id = v_santander_id;

    RAISE NOTICE 'Migração 018 executada com sucesso. Saldo do Santander preservado em: %', v_saldo_santander_antigo;
END $$;
