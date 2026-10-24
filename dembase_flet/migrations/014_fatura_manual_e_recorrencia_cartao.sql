-- =============================================================================
-- DemBase v3 — migrations/014_fatura_manual_e_recorrencia_cartao.sql
-- Suporte à seleção manual de fatura (sobrescrevendo dedução automática de fechamento)
-- e persistência em compras à vista, parceladas e recorrências contínuas no cartão.
-- =============================================================================

CREATE OR REPLACE FUNCTION public.criar_lancamento_com_recorrencia(
    p_dados JSONB,
    p_modo TEXT DEFAULT 'unica',
    p_frequencia TEXT DEFAULT 'mensal',
    p_quantidade INTEGER DEFAULT 1,
    p_valor_modo TEXT DEFAULT 'parcelado'
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id UUID;
    v_perfil_id UUID;
    v_tipo TEXT;
    v_subtipo TEXT;
    v_forma TEXT;
    v_conta_id UUID;
    v_cartao_id UUID;
    v_categoria_id UUID;
    v_subcategoria_id UUID;
    v_destino_id UUID;
    v_pote_id UUID;
    v_descricao TEXT;
    v_regra TEXT;
    v_hora INT;
    v_status_inicial TEXT;
    v_data_inicio DATE;
    v_valor_total NUMERIC(14,2);
    v_freq TEXT := lower(COALESCE(NULLIF(trim(p_frequencia), ''), 'mensal'));
    v_serie_id UUID := gen_random_uuid();
    v_recorrente_id UUID;
    v_qtd INT := GREATEST(COALESCE(p_quantidade, 1), 1);
    v_centavos_total BIGINT;
    v_centavos_parcela BIGINT;
    v_resto BIGINT;
    v_valor_item NUMERIC(14,2);
    v_dt DATE;
    v_status_item TEXT;
    v_fatura_id UUID;
    v_fatura_manual_id UUID;
    v_fatura_base_mes INT;
    v_fatura_base_ano INT;
    v_criados INT := 0;
    v_limite_horizonte DATE;
    i INT;
BEGIN
    v_user_id := COALESCE(auth.uid(), NULLIF(trim(p_dados->>'user_id'), '')::uuid);
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Usuário não autenticado';
    END IF;

    v_perfil_id := COALESCE(NULLIF(trim(p_dados->>'perfil_id'), '')::uuid, v_user_id);
    v_tipo := COALESCE(NULLIF(trim(p_dados->>'tipo'), ''), 'Despesa');
    v_subtipo := COALESCE(NULLIF(trim(p_dados->>'subtipo'), ''), v_tipo, 'Geral');
    v_forma := COALESCE(NULLIF(trim(p_dados->>'forma_movimentacao'), ''), 'Pix');
    v_conta_id := NULLIF(trim(p_dados->>'conta_id'), '')::uuid;
    v_cartao_id := NULLIF(trim(p_dados->>'cartao_id'), '')::uuid;
    v_categoria_id := NULLIF(trim(p_dados->>'categoria_id'), '')::uuid;
    v_subcategoria_id := NULLIF(trim(p_dados->>'subcategoria_id'), '')::uuid;
    v_destino_id := NULLIF(trim(p_dados->>'destino_id'), '')::uuid;
    v_pote_id := NULLIF(trim(p_dados->>'pote_id'), '')::uuid;
    v_descricao := COALESCE(NULLIF(trim(p_dados->>'descricao'), ''), v_subtipo, v_tipo, 'Lançamento');
    v_regra := NULLIF(trim(COALESCE(p_dados->>'regra', '')), '');
    IF v_regra NOT IN ('Essencial', 'Estilo de Vida', 'Investimento') THEN
        v_regra := NULL;
    END IF;
    v_hora := COALESCE(NULLIF(trim(p_dados->>'hora'), '')::int, 12);
    v_status_inicial := COALESCE(NULLIF(trim(p_dados->>'status'), ''), 'Pago');
    v_data_inicio := COALESCE(NULLIF(trim(p_dados->>'data'), '')::date, CURRENT_DATE);
    v_valor_total := (p_dados->>'valor')::numeric;

    -- Extrai eventual fatura manual informada no payload
    v_fatura_manual_id := NULLIF(trim(p_dados->>'fatura_id'), '')::uuid;
    IF v_fatura_manual_id IS NOT NULL THEN
        SELECT mes, ano INTO v_fatura_base_mes, v_fatura_base_ano
        FROM public.faturas
        WHERE id = v_fatura_manual_id;
    END IF;

    IF v_freq NOT IN ('diaria', 'semanal', 'quinzenal', 'mensal', 'bimestral', 'trimestral', 'semestral', 'anual') THEN
        v_freq := 'mensal';
    END IF;

    IF v_destino_id IS NOT NULL THEN
        INSERT INTO public.destinos (id, perfil_id, user_id, nome, ativo)
        SELECT c.id, COALESCE(c.perfil_id, v_perfil_id), COALESCE(c.user_id, v_user_id), c.nome, TRUE
        FROM public.contas c
        WHERE c.id = v_destino_id
        ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome;
    END IF;

    IF p_modo = 'unica' OR (v_qtd <= 1 AND p_modo != 'fixa') THEN
        IF v_forma IN ('Credito', 'Crédito') AND v_cartao_id IS NOT NULL THEN
            IF v_fatura_manual_id IS NOT NULL THEN
                v_fatura_id := v_fatura_manual_id;
            ELSE
                v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_data_inicio);
            END IF;
        END IF;

        INSERT INTO public.lancamentos (
            user_id, perfil_id, tipo, subtipo, forma_movimentacao,
            conta_id, cartao_id, categoria_id, subcategoria_id, destino_id, pote_id,
            valor, data, hora, descricao, status, regra,
            fatura_id, parcela_atual, total_parcelas, serie_id, tipo_recorrencia
        ) VALUES (
            v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
            v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id, v_pote_id,
            v_valor_total, v_data_inicio, v_hora, v_descricao, v_status_inicial::status_lancamento,
            CASE WHEN v_regra IS NOT NULL THEN v_regra::regra_financeira ELSE NULL END,
            v_fatura_id, 1, 1, v_serie_id, 'unica'
        );

        RETURN jsonb_build_object('sucesso', true, 'serie_id', v_serie_id, 'total_criados', 1);

    ELSIF p_modo = 'parcelada' THEN
        v_centavos_total := round(v_valor_total * 100)::bigint;
        v_centavos_parcela := v_centavos_total / v_qtd;
        v_resto := v_centavos_total - (v_centavos_parcela * v_qtd);

        FOR i IN 1..v_qtd LOOP
            IF i = v_qtd THEN
                v_valor_item := (v_centavos_parcela + v_resto) / 100.0;
            ELSE
                v_valor_item := v_centavos_parcela / 100.0;
            END IF;

            v_dt := fn_calcular_proxima_data(v_data_inicio, v_freq, i - 1);
            v_status_item := CASE WHEN i = 1 THEN v_status_inicial ELSE 'Pendente' END;

            v_fatura_id := NULL;
            IF v_cartao_id IS NOT NULL THEN
                IF i = 1 AND v_fatura_manual_id IS NOT NULL THEN
                    v_fatura_id := v_fatura_manual_id;
                ELSIF v_fatura_base_mes IS NOT NULL AND v_fatura_base_ano IS NOT NULL THEN
                    -- Se a 1ª parcela usou fatura manual, as seguintes calculam sequencialmente
                    DECLARE
                        v_target_date DATE := (v_fatura_base_ano || '-' || LPAD(v_fatura_base_mes::text, 2, '0') || '-01')::DATE + ((i - 1) || ' months')::INTERVAL;
                    BEGIN
                        v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_target_date);
                    END;
                ELSE
                    v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_dt);
                END IF;
            END IF;

            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id, pote_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, parcela_atual, total_parcelas, serie_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id, v_pote_id,
                v_valor_item, v_dt, v_hora, v_descricao, v_status_item::status_lancamento,
                CASE WHEN v_regra IS NOT NULL THEN v_regra::regra_financeira ELSE NULL END,
                v_fatura_id, i, v_qtd, v_serie_id, 'parcelada'
            );
            v_criados := v_criados + 1;
        END LOOP;

        RETURN jsonb_build_object('sucesso', true, 'serie_id', v_serie_id, 'total_criados', v_criados);

    ELSIF p_modo = 'repetida' THEN
        v_valor_item := v_valor_total;

        FOR i IN 1..v_qtd LOOP
            v_dt := fn_calcular_proxima_data(v_data_inicio, v_freq, i - 1);
            v_status_item := CASE WHEN i = 1 THEN v_status_inicial ELSE 'Pendente' END;

            v_fatura_id := NULL;
            IF v_cartao_id IS NOT NULL THEN
                IF i = 1 AND v_fatura_manual_id IS NOT NULL THEN
                    v_fatura_id := v_fatura_manual_id;
                ELSE
                    v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_dt);
                END IF;
            END IF;

            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id, pote_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, parcela_atual, total_parcelas, serie_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id, v_pote_id,
                v_valor_item, v_dt, v_hora, v_descricao, v_status_item::status_lancamento,
                CASE WHEN v_regra IS NOT NULL THEN v_regra::regra_financeira ELSE NULL END,
                v_fatura_id, i, v_qtd, v_serie_id, 'repetida'
            );
            v_criados := v_criados + 1;
        END LOOP;

        RETURN jsonb_build_object('sucesso', true, 'serie_id', v_serie_id, 'total_criados', v_criados);

    ELSIF p_modo = 'fixa' THEN
        INSERT INTO public.transacoes_recorrentes (
            user_id, conta_id, cartao_id, categoria_id, subcategoria_id, pote_id,
            tipo, subtipo, forma_movimentacao, valor, descricao, regra,
            frequencia, dia_vencimento, data_inicio, data_fim, ultimo_lancamento,
            ativo, modo, status_padrao, hora, quantidade
        ) VALUES (
            v_user_id, v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_pote_id,
            v_tipo, v_subtipo, v_forma, v_valor_total, v_descricao, v_regra,
            v_freq, extract(day from v_data_inicio)::int, v_data_inicio, NULL, NULL,
            TRUE, 'fixa', v_status_inicial, v_hora, 1
        ) RETURNING id INTO v_recorrente_id;

        v_limite_horizonte := (CURRENT_DATE + INTERVAL '12 months')::DATE;
        i := 0;

        LOOP
            v_dt := fn_calcular_proxima_data(v_data_inicio, v_freq, i);
            EXIT WHEN v_dt > v_limite_horizonte;

            v_status_item := CASE WHEN i = 0 THEN v_status_inicial ELSE 'Pendente' END;

            v_fatura_id := NULL;
            IF v_cartao_id IS NOT NULL THEN
                IF i = 0 AND v_fatura_manual_id IS NOT NULL THEN
                    v_fatura_id := v_fatura_manual_id;
                ELSE
                    v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_dt);
                END IF;
            END IF;

            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id, pote_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, serie_id, recorrente_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id, v_pote_id,
                v_valor_total, v_dt, v_hora, v_descricao, v_status_item::status_lancamento,
                CASE WHEN v_regra IS NOT NULL THEN v_regra::regra_financeira ELSE NULL END,
                v_fatura_id, v_serie_id, v_recorrente_id, 'fixa'
            )
            ON CONFLICT (recorrente_id, data) WHERE (recorrente_id IS NOT NULL) DO NOTHING;

            v_criados := v_criados + 1;
            i := i + 1;
        END LOOP;

        UPDATE public.transacoes_recorrentes
        SET ultimo_lancamento = fn_calcular_proxima_data(v_data_inicio, v_freq, GREATEST(i - 1, 0))
        WHERE id = v_recorrente_id;

        RETURN jsonb_build_object(
            'sucesso', true,
            'recorrente_id', v_recorrente_id,
            'serie_id', v_serie_id,
            'total_criados', v_criados
        );

    ELSE
        RAISE EXCEPTION 'Modo de recorrência inválido: %', p_modo;
    END IF;
END;
$$;
