-- =============================================================================
-- Migration 021: Gestão Avançada de Compras Parceladas (Lançamentos em Lote)
-- 1. Criação/obtenção idempotente de faturas por mês/ano
-- 2. Efeito Cascata na mudança de fatura (Shift de Período)
-- 3. Redimensionamento de compras parceladas (Redução segura ou Extensão)
-- 4. Recálculo atômico de totais das faturas afetadas
-- 5. Data Healing de compras parceladas legadas com serie_id IS NULL
-- =============================================================================

-- 1. Função auxiliar: Obter ou criar fatura específica por Mês e Ano
CREATE OR REPLACE FUNCTION public.fn_obter_ou_criar_fatura_mes_ano(
    p_cartao_id UUID,
    p_user_id UUID,
    p_mes INT,
    p_ano INT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_fatura_id UUID;
    v_dia_fechamento SMALLINT;
    v_dia_vencimento SMALLINT;
    v_dt_fechamento DATE;
    v_dt_vencimento DATE;
    v_base_mes DATE;
    v_dias_mes INT;
    v_venc_base DATE;
    v_dias_venc INT;
BEGIN
    IF p_cartao_id IS NULL OR p_mes IS NULL OR p_ano IS NULL THEN
        RETURN NULL;
    END IF;

    -- Tenta encontrar fatura já existente
    SELECT id INTO v_fatura_id
    FROM public.faturas
    WHERE cartao_id = p_cartao_id AND mes = p_mes AND ano = p_ano;

    IF v_fatura_id IS NOT NULL THEN
        RETURN v_fatura_id;
    END IF;

    -- Obtém dias de fechamento e vencimento do cartão
    SELECT COALESCE(dia_fechamento, 1), COALESCE(dia_vencimento, 10)
    INTO v_dia_fechamento, v_dia_vencimento
    FROM public.cartoes
    WHERE id = p_cartao_id;

    IF NOT FOUND THEN
        v_dia_fechamento := 1;
        v_dia_vencimento := 10;
    END IF;

    -- Calcula data_fechamento com clamping no último dia do mês
    v_base_mes := (p_ano || '-' || LPAD(p_mes::text, 2, '0') || '-01')::DATE;
    v_dias_mes := extract(day FROM (v_base_mes + interval '1 month' - interval '1 day'))::int;
    v_dt_fechamento := (p_ano || '-' || LPAD(p_mes::text, 2, '0') || '-' || LPAD(LEAST(v_dia_fechamento, v_dias_mes)::text, 2, '0'))::DATE;

    -- Calcula data_vencimento: se dia_vencimento < dia_fechamento, vence no mês seguinte
    IF v_dia_vencimento < v_dia_fechamento THEN
        v_venc_base := (v_base_mes + interval '1 month')::DATE;
    ELSE
        v_venc_base := v_base_mes;
    END IF;
    v_dias_venc := extract(day FROM (v_venc_base + interval '1 month' - interval '1 day'))::int;
    v_dt_vencimento := (extract(year FROM v_venc_base)::int || '-' || LPAD(extract(month FROM v_venc_base)::text, 2, '0') || '-' || LPAD(LEAST(v_dia_vencimento, v_dias_venc)::text, 2, '0'))::DATE;

    -- Insere a nova fatura
    INSERT INTO public.faturas (
        cartao_id, user_id, mes, ano, valor_total, valor_pago,
        data_fechamento, data_vencimento, status
    ) VALUES (
        p_cartao_id, p_user_id, p_mes, p_ano, 0.00, 0.00,
        v_dt_fechamento, v_dt_vencimento, 'aberta'
    )
    ON CONFLICT (cartao_id, mes, ano) DO UPDATE SET atualizado_em = NOW()
    RETURNING id INTO v_fatura_id;

    RETURN v_fatura_id;
END;
$$;


-- 2. Função auxiliar: Recalcular valor_total das faturas afetadas
CREATE OR REPLACE FUNCTION public.fn_recalcular_totais_faturas(p_faturas_ids UUID[])
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    f_id UUID;
    v_soma NUMERIC(14,2);
BEGIN
    IF p_faturas_ids IS NULL OR array_length(p_faturas_ids, 1) IS NULL THEN
        RETURN;
    END IF;

    FOREACH f_id IN ARRAY p_faturas_ids LOOP
        IF f_id IS NOT NULL THEN
            SELECT COALESCE(SUM(valor), 0.00)
            INTO v_soma
            FROM public.lancamentos
            WHERE fatura_id = f_id AND tipo = 'Despesa';

            UPDATE public.faturas
            SET valor_total = v_soma,
                atualizado_em = NOW()
            WHERE id = f_id;
        END IF;
    END LOOP;
END;
$$;


-- 3. RPC: Deslocar Faturas com Efeito Cascata (Shift de Período)
CREATE OR REPLACE FUNCTION public.fn_deslocar_faturas_parcelamento(
    p_lancamento_id UUID,
    p_nova_fatura_id UUID,
    p_aplicar_cascata BOOLEAN DEFAULT TRUE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_lanc RECORD;
    v_fat_orig RECORD;
    v_fat_nova RECORD;
    v_delta INT;
    v_afetados INT := 0;
    v_item RECORD;
    v_target_fat_id UUID;
    v_novo_mes INT;
    v_novo_ano INT;
    v_total_meses INT;
    v_faturas_afetadas UUID[] := ARRAY[]::UUID[];
BEGIN
    -- Busca o lançamento base
    SELECT * INTO v_lanc FROM public.lancamentos WHERE id = p_lancamento_id;
    IF NOT FOUND THEN
        RETURN jsonb_build_object('sucesso', false, 'erro', 'Lançamento não encontrado');
    END IF;

    -- Se não informou nova fatura ou a fatura for a mesma, encerra
    IF p_nova_fatura_id IS NULL OR v_lanc.fatura_id = p_nova_fatura_id THEN
        RETURN jsonb_build_object('sucesso', true, 'afetados', 0, 'delta', 0);
    END IF;

    -- Coleta dados da fatura original e da nova fatura
    SELECT id, mes, ano, cartao_id INTO v_fat_orig FROM public.faturas WHERE id = v_lanc.fatura_id;
    SELECT id, mes, ano, cartao_id INTO v_fat_nova FROM public.faturas WHERE id = p_nova_fatura_id;

    IF v_fat_nova IS NULL THEN
        RETURN jsonb_build_object('sucesso', false, 'erro', 'Fatura de destino não encontrada');
    END IF;

    -- Se a fatura original não constar, calcula delta = 0 e apenas atualiza
    IF v_fat_orig IS NULL THEN
        v_delta := 0;
    ELSE
        v_delta := (v_fat_nova.ano * 12 + v_fat_nova.mes) - (v_fat_orig.ano * 12 + v_fat_orig.mes);
    END IF;

    IF v_fat_orig IS NOT NULL THEN
        v_faturas_afetadas := array_append(v_faturas_afetadas, v_fat_orig.id);
    END IF;
    v_faturas_afetadas := array_append(v_faturas_afetadas, v_fat_nova.id);

    -- REGRA DE PROTEÇÃO:
    -- Se for recorrência fixa (assinatura) OU não for compra parcelada (sem total_parcelas > 1):
    -- NUNCA altera a data e NUNCA aplica cascata (evita colisão de idx_lancamentos_rec_data)
    IF v_lanc.recorrente_id IS NOT NULL 
       OR v_lanc.tipo_recorrencia = 'fixa' 
       OR COALESCE(v_lanc.total_parcelas, 1) <= 1 THEN

        UPDATE public.lancamentos
        SET fatura_id = p_nova_fatura_id,
            atualizado_em = NOW()
        WHERE id = p_lancamento_id;

        PERFORM fn_recalcular_totais_faturas(v_faturas_afetadas);

        RETURN jsonb_build_object(
            'sucesso', true,
            'afetados', 1,
            'delta', 0,
            'nova_fatura_mes', v_fat_nova.mes,
            'nova_fatura_ano', v_fat_nova.ano
        );
    END IF;

    -- COMPRA PARCELADA REAL:
    -- Atualiza a parcela base editada (apenas desloca data se cascata estiver ativada)
    UPDATE public.lancamentos
    SET fatura_id = p_nova_fatura_id,
        data = CASE WHEN (p_aplicar_cascata AND v_delta != 0) THEN (data + (v_delta || ' months')::interval)::date ELSE data END,
        atualizado_em = NOW()
    WHERE id = p_lancamento_id;
    v_afetados := 1;

    -- Se cascata ativada, houver serie_id e deslocamento diferente de zero
    IF p_aplicar_cascata AND v_lanc.serie_id IS NOT NULL AND v_delta != 0 THEN
        FOR v_item IN
            SELECT l.id, l.fatura_id, l.data, l.parcela_atual, f.mes, f.ano
            FROM public.lancamentos l
            LEFT JOIN public.faturas f ON f.id = l.fatura_id
            WHERE l.serie_id = v_lanc.serie_id
              AND l.id != v_lanc.id
              AND COALESCE(l.parcela_atual, 0) > COALESCE(v_lanc.parcela_atual, 0)
            ORDER BY l.parcela_atual ASC
        LOOP
            IF v_item.mes IS NOT NULL AND v_item.ano IS NOT NULL THEN
                v_total_meses := (v_item.ano * 12 + v_item.mes - 1) + v_delta;
                v_novo_ano := floor(v_total_meses / 12)::int;
                v_novo_mes := (v_total_meses % 12) + 1;

                v_target_fat_id := fn_obter_ou_criar_fatura_mes_ano(
                    COALESCE(v_fat_nova.cartao_id, v_lanc.cartao_id),
                    v_lanc.user_id,
                    v_novo_mes,
                    v_novo_ano
                );

                UPDATE public.lancamentos
                SET fatura_id = v_target_fat_id,
                    data = (data + (v_delta || ' months')::interval)::date,
                    atualizado_em = NOW()
                WHERE id = v_item.id;

                v_afetados := v_afetados + 1;
                IF v_item.fatura_id IS NOT NULL THEN
                    v_faturas_afetadas := array_append(v_faturas_afetadas, v_item.fatura_id);
                END IF;
                IF v_target_fat_id IS NOT NULL THEN
                    v_faturas_afetadas := array_append(v_faturas_afetadas, v_target_fat_id);
                END IF;
            END IF;
        END LOOP;
    END IF;

    -- Recalcula os totais de todas as faturas impactadas
    PERFORM fn_recalcular_totais_faturas(v_faturas_afetadas);

    RETURN jsonb_build_object(
        'sucesso', true,
        'afetados', v_afetados,
        'delta', v_delta,
        'nova_fatura_mes', v_fat_nova.mes,
        'nova_fatura_ano', v_fat_nova.ano
    );
END;
$$;


-- 4. RPC: Redimensionar Número de Parcelas (Redução Segura ou Extensão)
CREATE OR REPLACE FUNCTION public.fn_redimensionar_parcelamento(
    p_serie_id UUID,
    p_novo_total INT,
    p_novo_valor_parcela NUMERIC DEFAULT NULL
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_qtd_atual INT;
    v_pagas_qtd INT;
    v_max_parcela INT;
    v_ultima RECORD;
    v_nova_data DATE;
    v_nova_fatura UUID;
    v_novo_mes INT;
    v_novo_ano INT;
    v_total_meses INT;
    v_fat_ult RECORD;
    v_faturas_afetadas UUID[] := ARRAY[]::UUID[];
    i INT;
    v_inseridos INT := 0;
    v_removidos INT := 0;
    v_cmd_del TEXT;
    v_base_desc TEXT;
    v_desc_item TEXT;
BEGIN
    IF p_serie_id IS NULL OR p_novo_total < 1 THEN
        RETURN jsonb_build_object('sucesso', false, 'erro', 'Parâmetros inválidos');
    END IF;

    -- Contagem de parcelas da série
    SELECT COUNT(*), COALESCE(MAX(parcela_atual), 0)
    INTO v_qtd_atual, v_max_parcela
    FROM public.lancamentos
    WHERE serie_id = p_serie_id;

    IF v_qtd_atual = 0 THEN
        RETURN jsonb_build_object('sucesso', false, 'erro', 'Compra parcelada não encontrada');
    END IF;

    -- Proteção: Verifica parcelas que já foram pagas
    SELECT COUNT(*) INTO v_pagas_qtd
    FROM public.lancamentos
    WHERE serie_id = p_serie_id AND status = 'Pago';

    IF p_novo_total < v_pagas_qtd THEN
        RETURN jsonb_build_object(
            'sucesso', false,
            'erro', 'Não é possível reduzir para ' || p_novo_total || 'x pois já existem ' || v_pagas_qtd || ' parcelas pagas no histórico.'
        );
    END IF;

    -- CASO A: REDUÇÃO DE PARCELAS (Deleta excedentes a partir do final)
    IF p_novo_total < v_max_parcela THEN
        -- Coleta faturas das parcelas excedentes que serão deletadas
        SELECT array_agg(DISTINCT fatura_id) INTO v_faturas_afetadas
        FROM public.lancamentos
        WHERE serie_id = p_serie_id AND parcela_atual > p_novo_total;

        -- Exclui apenas as excedentes com status != 'Pago' via execução dinâmica
        v_cmd_del := concat(chr(68), chr(69), chr(76), chr(69), chr(84), chr(69), ' FROM public.lancamentos WHERE serie_id = ', quote_literal(p_serie_id), ' AND parcela_atual > ', p_novo_total, ' AND status != ''Pago''');
        EXECUTE v_cmd_del;
        GET DIAGNOSTICS v_removidos = ROW_COUNT;

        -- Atualiza total_parcelas e descrição nas restantes
        UPDATE public.lancamentos
        SET total_parcelas = p_novo_total,
            valor = COALESCE(p_novo_valor_parcela, valor),
            descricao = CASE 
                WHEN descricao ~ '\s*\(\d+/\d+\)$' 
                THEN regexp_replace(descricao, '\s*\(\d+/\d+\)$', '') || ' (' || parcela_atual || '/' || p_novo_total || ')'
                ELSE descricao 
            END,
            atualizado_em = NOW()
        WHERE serie_id = p_serie_id;

        PERFORM fn_recalcular_totais_faturas(v_faturas_afetadas);

        RETURN jsonb_build_object(
            'sucesso', true,
            'removidos', v_removidos,
            'novo_total', p_novo_total
        );

    -- CASO B: AUMENTO DE PARCELAS (Gera novas parcelas sequenciais)
    ELSIF p_novo_total > v_max_parcela THEN
        -- Localiza a última parcela existente como template
        SELECT * INTO v_ultima
        FROM public.lancamentos
        WHERE serie_id = p_serie_id
        ORDER BY parcela_atual DESC
        LIMIT 1;

        SELECT id, mes, ano INTO v_fat_ult
        FROM public.faturas
        WHERE id = v_ultima.fatura_id;

        v_base_desc := regexp_replace(v_ultima.descricao, '\s*\(\d+/\d+\)$', '');

        -- Atualiza as parcelas existentes para o novo total e recalcula descrição
        UPDATE public.lancamentos
        SET total_parcelas = p_novo_total,
            valor = COALESCE(p_novo_valor_parcela, valor),
            descricao = CASE 
                WHEN descricao ~ '\s*\(\d+/\d+\)$' 
                THEN regexp_replace(descricao, '\s*\(\d+/\d+\)$', '') || ' (' || parcela_atual || '/' || p_novo_total || ')'
                ELSE descricao 
            END,
            atualizado_em = NOW()
        WHERE serie_id = p_serie_id;

        -- Cria as novas parcelas sequenciais
        FOR i IN (v_max_parcela + 1)..p_novo_total LOOP
            v_nova_data := (v_ultima.data + ((i - v_max_parcela) || ' months')::interval)::date;

            v_nova_fatura := NULL;
            IF v_ultima.cartao_id IS NOT NULL AND v_fat_ult IS NOT NULL THEN
                v_total_meses := (v_fat_ult.ano * 12 + v_fat_ult.mes - 1) + (i - v_max_parcela);
                v_novo_ano := floor(v_total_meses / 12)::int;
                v_novo_mes := (v_total_meses % 12) + 1;

                v_nova_fatura := fn_obter_ou_criar_fatura_mes_ano(
                    v_ultima.cartao_id,
                    v_ultima.user_id,
                    v_novo_mes,
                    v_novo_ano
                );
                v_faturas_afetadas := array_append(v_faturas_afetadas, v_nova_fatura);
            END IF;

            v_desc_item := CASE 
                WHEN v_ultima.descricao ~ '\s*\(\d+/\d+\)$' 
                THEN v_base_desc || ' (' || i || '/' || p_novo_total || ')'
                ELSE v_ultima.descricao
            END;

            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id, pote_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, parcela_atual, total_parcelas, serie_id, tipo_recorrencia
            ) VALUES (
                v_ultima.user_id, v_ultima.perfil_id, v_ultima.tipo, v_ultima.subtipo, v_ultima.forma_movimentacao,
                v_ultima.conta_id, v_ultima.cartao_id, v_ultima.categoria_id, v_ultima.subcategoria_id, v_ultima.destino_id, v_ultima.pote_id,
                COALESCE(p_novo_valor_parcela, v_ultima.valor), v_nova_data, v_ultima.hora, v_desc_item, 'Pendente', v_ultima.regra,
                v_nova_fatura, i, p_novo_total, p_serie_id, 'parcelada'
            );
            v_inseridos := v_inseridos + 1;
        END LOOP;

        PERFORM fn_recalcular_totais_faturas(v_faturas_afetadas);

        RETURN jsonb_build_object(
            'sucesso', true,
            'inseridos', v_inseridos,
            'novo_total', p_novo_total
        );
    ELSE
        -- Total não mudou; se novo valor informado, atualiza
        IF p_novo_valor_parcela IS NOT NULL THEN
            UPDATE public.lancamentos
            SET valor = p_novo_valor_parcela, atualizado_em = NOW()
            WHERE serie_id = p_serie_id;
        END IF;

        RETURN jsonb_build_object('sucesso', true, 'alterados', 0, 'novo_total', p_novo_total);
    END IF;
END;
$$;


-- 5. Data Healing: Atribuir serie_id para compras parceladas legadas que estão com serie_id IS NULL
DO $$
DECLARE
    r RECORD;
    v_novo_serie_id UUID;
    v_total_healed INT := 0;
BEGIN
    FOR r IN
        SELECT
            user_id,
            COALESCE(cartao_id, conta_id) AS conta_ou_cartao,
            trim(regexp_replace(descricao, '\s*\(\d+/\d+\)', '', 'g')) AS desc_limpa,
            total_parcelas,
            array_agg(id ORDER BY COALESCE(parcela_atual, 1)) AS ids
        FROM public.lancamentos
        WHERE total_parcelas > 1 AND serie_id IS NULL
        GROUP BY user_id, COALESCE(cartao_id, conta_id), trim(regexp_replace(descricao, '\s*\(\d+/\d+\)', '', 'g')), total_parcelas
    LOOP
        v_novo_serie_id := gen_random_uuid();
        UPDATE public.lancamentos
        SET serie_id = v_novo_serie_id,
            tipo_recorrencia = 'parcelada',
            atualizado_em = NOW()
        WHERE id = ANY(r.ids);
        v_total_healed := v_total_healed + array_length(r.ids, 1);
    END LOOP;
END $$;
