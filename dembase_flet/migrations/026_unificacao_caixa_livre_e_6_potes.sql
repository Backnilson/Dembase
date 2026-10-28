-- =============================================================================
-- DemBase v3 — Migração 026: Unificação Matemática entre Caixa Livre e 6 Potes
-- =============================================================================
-- 1. Garante que os nomes padrão de fábrica sejam:
--    1: Custos Fixos, 2: Custos Semi Fixos, 3: Metas, 4: Prazeres,
--    5: Conhecimento, 6: Liberdade Financeira
-- 2. Atualiza a RPC `get_potes_resumo` para calcular dinamicamente:
--    - Custos Fixos: limite = max(gasto real, piso de R$ 1.150,00) e calcula a % da receita.
--    - Custos Semi Fixos, Metas e Conhecimento: orçamentos retidos / intocáveis.
--    - Liberdade Financeira e Prazeres: fatias restantes do Caixa Livre orquestradas
--      pelo slider de investimento (config_caixa_livre_mensal), cravando sempre 100,00%.
-- =============================================================================

-- 1. Atualização dos nomes padrão de fábrica na posição 2
UPDATE public.potes
   SET nome = 'Custos Semi Fixos'
 WHERE posicao = 2 AND lower(nome) IN ('conforto', 'custo semi fixo');

UPDATE public.potes_mensais
   SET nome = 'Custos Semi Fixos'
 WHERE posicao = 2 AND lower(nome) IN ('conforto', 'custo semi fixo');

-- 2. RPC unificada: get_potes_resumo
CREATE OR REPLACE FUNCTION public.get_potes_resumo(
    p_data_inicio  DATE,
    p_data_fim     DATE,
    p_piso_fixos   NUMERIC DEFAULT 1150.00
) RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid          UUID := COALESCE(auth.uid(), (SELECT id FROM public.perfis LIMIT 1));
    v_renda        NUMERIC := 0;
    v_gasto_total  NUMERIC := 0;
    v_mes_ref      SMALLINT := EXTRACT(MONTH FROM COALESCE(p_data_inicio, CURRENT_DATE))::SMALLINT;
    v_ano_ref      SMALLINT := EXTRACT(YEAR  FROM COALESCE(p_data_inicio, CURRENT_DATE))::SMALLINT;
    v_potes_mes    JSONB;
    v_personaliz   BOOLEAN := FALSE;
    v_cfg_caixa    JSONB;
    v_slider_inv   NUMERIC := 50.0;
    v_piso_fix     NUMERIC := GREATEST(0, COALESCE(p_piso_fixos, 1150.00));

    -- Variáveis dos 6 potes
    v_p1_id UUID; v_p1_nome TEXT; v_p1_cor TEXT; v_p1_gasto NUMERIC := 0; v_p1_qtd INT := 0; v_p1_prev NUMERIC := 0; v_p1_pct NUMERIC := 0;
    v_p2_id UUID; v_p2_nome TEXT; v_p2_cor TEXT; v_p2_gasto NUMERIC := 0; v_p2_qtd INT := 0; v_p2_prev NUMERIC := 0; v_p2_pct NUMERIC := 0;
    v_p3_id UUID; v_p3_nome TEXT; v_p3_cor TEXT; v_p3_gasto NUMERIC := 0; v_p3_qtd INT := 0; v_p3_prev NUMERIC := 0; v_p3_pct NUMERIC := 0;
    v_p4_id UUID; v_p4_nome TEXT; v_p4_cor TEXT; v_p4_gasto NUMERIC := 0; v_p4_qtd INT := 0; v_p4_prev NUMERIC := 0; v_p4_pct NUMERIC := 0;
    v_p5_id UUID; v_p5_nome TEXT; v_p5_cor TEXT; v_p5_gasto NUMERIC := 0; v_p5_qtd INT := 0; v_p5_prev NUMERIC := 0; v_p5_pct NUMERIC := 0;
    v_p6_id UUID; v_p6_nome TEXT; v_p6_cor TEXT; v_p6_gasto NUMERIC := 0; v_p6_qtd INT := 0; v_p6_prev NUMERIC := 0; v_p6_pct NUMERIC := 0;

    v_pct_caixa_livre NUMERIC := 0;
    v_teto_caixa_livre NUMERIC := 0;
    v_sobra_livre_real NUMERIC := 0;
    v_retido_total     NUMERIC := 0;
    v_excessos_outros  NUMERIC := 0;
    v_potes            JSONB;
    v_sem              JSONB;
BEGIN
    IF p_data_inicio IS NOT NULL AND p_data_fim IS NOT NULL THEN
        v_mes_ref := EXTRACT(MONTH FROM (p_data_inicio + ((p_data_fim - p_data_inicio) / 2)))::SMALLINT;
        v_ano_ref := EXTRACT(YEAR  FROM (p_data_inicio + ((p_data_fim - p_data_inicio) / 2)))::SMALLINT;
    END IF;

    -- Carrega potes do mês
    v_potes_mes := public.listar_potes_mes(v_mes_ref, v_ano_ref);
    SELECT COALESCE(bool_or((elem->>'personalizado_no_mes')::BOOLEAN), FALSE)
      INTO v_personaliz
      FROM jsonb_array_elements(v_potes_mes) elem;

    -- Carrega slider do Caixa Livre do mês (Investimento vs Livre)
    v_cfg_caixa := public.obter_config_caixa_livre_mes(v_mes_ref, v_ano_ref);
    IF v_cfg_caixa IS NOT NULL AND v_cfg_caixa ? 'pct_investimento' THEN
        v_slider_inv := GREATEST(0, LEAST(100, (v_cfg_caixa->>'pct_investimento')::NUMERIC));
    END IF;

    -- 1. Receitas REAIS do período
    SELECT COALESCE(SUM(valor), 0) INTO v_renda
      FROM public.lancamentos
     WHERE (user_id = v_uid OR perfil_id = v_uid)
       AND lower(tipo) LIKE 'receita%'
       AND data BETWEEN p_data_inicio AND p_data_fim;

    -- 2. Despesas REAIS do período
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_total
      FROM public.lancamentos
     WHERE (user_id = v_uid OR perfil_id = v_uid)
       AND lower(tipo) LIKE 'despesa%'
       AND data BETWEEN p_data_inicio AND p_data_fim;

    -- Descompacta os 6 potes do mês
    FOR r IN SELECT * FROM jsonb_to_recordset(v_potes_mes) AS pm(
        id UUID, posicao SMALLINT, nome TEXT, percentual NUMERIC, cor TEXT
    ) LOOP
        IF r.posicao = 1 THEN
            v_p1_id := r.id; v_p1_nome := r.nome; v_p1_cor := r.cor; v_p1_pct := r.percentual;
        ELSIF r.posicao = 2 THEN
            v_p2_id := r.id; v_p2_nome := r.nome; v_p2_cor := r.cor; v_p2_pct := r.percentual;
        ELSIF r.posicao = 3 THEN
            v_p3_id := r.id; v_p3_nome := r.nome; v_p3_cor := r.cor; v_p3_pct := r.percentual;
        ELSIF r.posicao = 4 THEN
            v_p4_id := r.id; v_p4_nome := r.nome; v_p4_cor := r.cor; v_p4_pct := r.percentual;
        ELSIF r.posicao = 5 THEN
            v_p5_id := r.id; v_p5_nome := r.nome; v_p5_cor := r.cor; v_p5_pct := r.percentual;
        ELSIF r.posicao = 6 THEN
            v_p6_id := r.id; v_p6_nome := r.nome; v_p6_cor := r.cor; v_p6_pct := r.percentual;
        END IF;
    END LOOP;

    -- Agrega gastos reais por pote
    SELECT COALESCE(SUM(valor), 0), COUNT(*) INTO v_p1_gasto, v_p1_qtd FROM public.lancamentos WHERE (user_id = v_uid OR perfil_id = v_uid) AND lower(tipo) LIKE 'despesa%' AND pote_id = v_p1_id AND data BETWEEN p_data_inicio AND p_data_fim;
    SELECT COALESCE(SUM(valor), 0), COUNT(*) INTO v_p2_gasto, v_p2_qtd FROM public.lancamentos WHERE (user_id = v_uid OR perfil_id = v_uid) AND lower(tipo) LIKE 'despesa%' AND pote_id = v_p2_id AND data BETWEEN p_data_inicio AND p_data_fim;
    SELECT COALESCE(SUM(valor), 0), COUNT(*) INTO v_p3_gasto, v_p3_qtd FROM public.lancamentos WHERE (user_id = v_uid OR perfil_id = v_uid) AND lower(tipo) LIKE 'despesa%' AND pote_id = v_p3_id AND data BETWEEN p_data_inicio AND p_data_fim;
    SELECT COALESCE(SUM(valor), 0), COUNT(*) INTO v_p4_gasto, v_p4_qtd FROM public.lancamentos WHERE (user_id = v_uid OR perfil_id = v_uid) AND lower(tipo) LIKE 'despesa%' AND pote_id = v_p4_id AND data BETWEEN p_data_inicio AND p_data_fim;
    SELECT COALESCE(SUM(valor), 0), COUNT(*) INTO v_p5_gasto, v_p5_qtd FROM public.lancamentos WHERE (user_id = v_uid OR perfil_id = v_uid) AND lower(tipo) LIKE 'despesa%' AND pote_id = v_p5_id AND data BETWEEN p_data_inicio AND p_data_fim;
    SELECT COALESCE(SUM(valor), 0), COUNT(*) INTO v_p6_gasto, v_p6_qtd FROM public.lancamentos WHERE (user_id = v_uid OR perfil_id = v_uid) AND lower(tipo) LIKE 'despesa%' AND pote_id = v_p6_id AND data BETWEEN p_data_inicio AND p_data_fim;

    -- Despesas sem pote
    SELECT jsonb_build_object('qtd', COUNT(*), 'total', COALESCE(SUM(valor), 0)) INTO v_sem
      FROM public.lancamentos
     WHERE (user_id = v_uid OR perfil_id = v_uid)
       AND lower(tipo) LIKE 'despesa%'
       AND pote_id IS NULL
       AND data BETWEEN p_data_inicio AND p_data_fim;

    -- ─────────────────────────────────────────────────────────────────────────
    -- A NOVA MATEMÁTICA UNIFICADA
    -- ─────────────────────────────────────────────────────────────────────────
    IF v_renda > 0 THEN
        -- 1. Pote 1: Custos Fixos (Automático / Ajustado à Despesa)
        v_p1_prev := GREATEST(v_p1_gasto, v_piso_fix);
        v_p1_pct  := LEAST(100.0, ROUND((v_p1_prev / v_renda) * 100.0, 2));

        -- 2. Potes 2, 3 e 5: Orçamentos Retidos / Intocáveis
        v_p2_prev := ROUND(v_renda * v_p2_pct / 100.0, 2);
        v_p3_prev := ROUND(v_renda * v_p3_pct / 100.0, 2);
        v_p5_prev := ROUND(v_renda * v_p5_pct / 100.0, 2);

        -- Comprometimento e retenção
        v_retido_total := GREATEST(0, v_p2_prev - v_p2_gasto)
                        + GREATEST(0, v_p3_prev - v_p3_gasto)
                        + GREATEST(0, v_p5_prev - v_p5_gasto);

        v_excessos_outros := GREATEST(0, v_p2_gasto - v_p2_prev)
                           + GREATEST(0, v_p3_gasto - v_p3_prev)
                           + GREATEST(0, v_p5_gasto - v_p5_prev)
                           + GREATEST(0, v_p1_gasto - v_p1_prev);

        -- 3. Fatia Restante do Caixa Livre (Liberdade Financeira + Prazeres)
        v_pct_caixa_livre  := GREATEST(0, ROUND(100.0 - v_p1_pct - v_p2_pct - v_p3_pct - v_p5_pct, 2));
        v_teto_caixa_livre := ROUND(v_renda * v_pct_caixa_livre / 100.0, 2);

        -- 4. Divisão do Slider entre Prazeres (Pote 4) e Liberdade Financeira (Pote 6)
        v_p4_pct  := ROUND(v_pct_caixa_livre * ((100.0 - v_slider_inv) / 100.0), 2);
        v_p4_prev := ROUND(v_teto_caixa_livre * ((100.0 - v_slider_inv) / 100.0), 2);

        -- Liberdade Financeira absorve o complemento exato para fechar rigorosamente 100,00%
        v_p6_pct  := ROUND(100.0 - (v_p1_pct + v_p2_pct + v_p3_pct + v_p4_pct + v_p5_pct), 2);
        v_p6_prev := GREATEST(0, v_teto_caixa_livre - v_p4_prev);

        -- Sobra Livre Real (após gastos de prazeres, aportes e descontar excessos)
        v_sobra_livre_real := GREATEST(0, v_teto_caixa_livre - v_p4_gasto - v_p6_gasto - v_excessos_outros);
    ELSE
        v_p1_prev := 0; v_p1_pct := 0;
        v_p2_prev := 0; v_p2_pct := 0;
        v_p3_prev := 0; v_p3_pct := 0;
        v_p4_prev := 0; v_p4_pct := 0;
        v_p5_prev := 0; v_p5_pct := 0;
        v_p6_prev := 0; v_p6_pct := 0;
        v_pct_caixa_livre := 0;
        v_teto_caixa_livre := 0;
        v_sobra_livre_real := 0;
    END IF;

    -- Montagem do JSON dos 6 potes
    v_potes := jsonb_build_array(
        jsonb_build_object(
            'id', v_p1_id, 'posicao', 1, 'nome', v_p1_nome, 'cor', v_p1_cor,
            'percentual', v_p1_pct, 'previsto', v_p1_prev, 'gasto', v_p1_gasto,
            'qtd_transacoes', v_p1_qtd, 'restante', v_p1_prev - v_p1_gasto,
            'percentual_usado', CASE WHEN v_p1_prev > 0 THEN ROUND(v_p1_gasto / v_p1_prev * 100, 2) ELSE 0 END,
            'tipo_comportamento', 'automatico_fixo',
            'piso_configurado', v_piso_fix
        ),
        jsonb_build_object(
            'id', v_p2_id, 'posicao', 2, 'nome', v_p2_nome, 'cor', v_p2_cor,
            'percentual', v_p2_pct, 'previsto', v_p2_prev, 'gasto', v_p2_gasto,
            'qtd_transacoes', v_p2_qtd, 'restante', v_p2_prev - v_p2_gasto,
            'percentual_usado', CASE WHEN v_p2_prev > 0 THEN ROUND(v_p2_gasto / v_p2_prev * 100, 2) ELSE 0 END,
            'tipo_comportamento', 'retido_intocavel'
        ),
        jsonb_build_object(
            'id', v_p3_id, 'posicao', 3, 'nome', v_p3_nome, 'cor', v_p3_cor,
            'percentual', v_p3_pct, 'previsto', v_p3_prev, 'gasto', v_p3_gasto,
            'qtd_transacoes', v_p3_qtd, 'restante', v_p3_prev - v_p3_gasto,
            'percentual_usado', CASE WHEN v_p3_prev > 0 THEN ROUND(v_p3_gasto / v_p3_prev * 100, 2) ELSE 0 END,
            'tipo_comportamento', 'retido_intocavel'
        ),
        jsonb_build_object(
            'id', v_p4_id, 'posicao', 4, 'nome', v_p4_nome, 'cor', v_p4_cor,
            'percentual', v_p4_pct, 'previsto', v_p4_prev, 'gasto', v_p4_gasto,
            'qtd_transacoes', v_p4_qtd, 'restante', v_p4_prev - v_p4_gasto,
            'percentual_usado', CASE WHEN v_p4_prev > 0 THEN ROUND(v_p4_gasto / v_p4_prev * 100, 2) ELSE 0 END,
            'tipo_comportamento', 'caixa_livre_prazeres'
        ),
        jsonb_build_object(
            'id', v_p5_id, 'posicao', 5, 'nome', v_p5_nome, 'cor', v_p5_cor,
            'percentual', v_p5_pct, 'previsto', v_p5_prev, 'gasto', v_p5_gasto,
            'qtd_transacoes', v_p5_qtd, 'restante', v_p5_prev - v_p5_gasto,
            'percentual_usado', CASE WHEN v_p5_prev > 0 THEN ROUND(v_p5_gasto / v_p5_prev * 100, 2) ELSE 0 END,
            'tipo_comportamento', 'retido_intocavel'
        ),
        jsonb_build_object(
            'id', v_p6_id, 'posicao', 6, 'nome', v_p6_nome, 'cor', v_p6_cor,
            'percentual', v_p6_pct, 'previsto', v_p6_prev, 'gasto', v_p6_gasto,
            'qtd_transacoes', v_p6_qtd, 'restante', v_p6_prev - v_p6_gasto,
            'percentual_usado', CASE WHEN v_p6_prev > 0 THEN ROUND(v_p6_gasto / v_p6_prev * 100, 2) ELSE 0 END,
            'tipo_comportamento', 'caixa_livre_investimento'
        )
    );

    RETURN jsonb_build_object(
        'renda',                  v_renda,
        'base_utilizada',         v_renda,
        'total_gasto',            v_gasto_total,
        'saldo',                  v_renda - v_gasto_total,
        'percentual_renda_usado', CASE WHEN v_renda > 0 THEN ROUND(v_gasto_total / v_renda * 100, 2) ELSE 0 END,
        'mes_ref',                v_mes_ref,
        'ano_ref',                v_ano_ref,
        'personalizado_no_mes',   v_personaliz,
        'potes',                  v_potes,
        'sem_pote',               v_sem,
        'caixa_livre',            jsonb_build_object(
            'teto_orcamento',           v_teto_caixa_livre,
            'pct_orcamento',            v_pct_caixa_livre,
            'pct_slider_investimento',  v_slider_inv,
            'pct_slider_livre',         100.0 - v_slider_inv,
            'retido_outros_potes',      v_retido_total,
            'sobra_livre_disponivel',   v_sobra_livre_real,
            'prazeres_teto',            v_p4_prev,
            'prazeres_gasto',           v_p4_gasto,
            'prazeres_restante',        v_p4_prev - v_p4_gasto,
            'liberdade_teto',           v_p6_prev,
            'liberdade_gasto',          v_p6_gasto,
            'liberdade_restante',       v_p6_prev - v_p6_gasto
        )
    );
END $$;

GRANT EXECUTE ON FUNCTION public.get_potes_resumo(DATE, DATE, NUMERIC) TO authenticated;
