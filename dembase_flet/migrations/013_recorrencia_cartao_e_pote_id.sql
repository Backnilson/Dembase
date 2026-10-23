-- =============================================================================
-- DemBase v3 — Migration 013: Recorrência Contínua em Cartão de Crédito e pote_id
-- Atualiza as RPCs criar_lancamento_com_recorrencia e gerar_lancamentos_recorrentes
-- para persistir pote_id em transações recorrentes e lançamentos gerados, além de
-- garantir compatibilidade total com despesas fixas contínuas em Cartão de Crédito.
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
            v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_data_inicio);
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
                v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_dt);
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
                v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_dt);
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
            CASE WHEN v_tipo IN ('Receita', 'Despesa') THEN v_tipo ELSE 'Despesa' END,
            v_subtipo, v_forma, v_valor_total, v_descricao, v_regra,
            v_freq, extract(day FROM v_data_inicio)::smallint,
            v_data_inicio, NULL, v_data_inicio,
            TRUE, 'fixa', 'Pendente', v_hora, NULL
        ) RETURNING id INTO v_recorrente_id;

        v_limite_horizonte := (v_data_inicio + interval '12 months')::DATE;
        i := 0;
        LOOP
            v_dt := fn_calcular_proxima_data(v_data_inicio, v_freq, i);
            EXIT WHEN v_dt > v_limite_horizonte;

            v_status_item := CASE WHEN i = 0 THEN v_status_inicial ELSE 'Pendente' END;

            v_fatura_id := NULL;
            IF v_cartao_id IS NOT NULL THEN
                v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_dt);
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
            'serie_id', v_serie_id,
            'recorrente_id', v_recorrente_id,
            'total_criados', v_criados
        );
    END IF;

    RETURN jsonb_build_object('sucesso', false, 'erro', 'Modo não reconhecido');
END;
$$;

CREATE OR REPLACE FUNCTION public.gerar_lancamentos_recorrentes(
    p_ate DATE DEFAULT (CURRENT_DATE + interval '12 months')::DATE
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id UUID := auth.uid();
    rec RECORD;
    v_dt DATE;
    v_max_dt DATE;
    v_fatura_id UUID;
    v_inseridos INT := 0;
    v_passo INT;
BEGIN
    FOR rec IN
        SELECT *
        FROM public.transacoes_recorrentes
        WHERE ativo = TRUE
          AND modo = 'fixa'
          AND (v_user_id IS NULL OR user_id = v_user_id)
    LOOP
        v_dt := COALESCE(rec.ultimo_lancamento, rec.data_inicio);
        v_max_dt := v_dt;
        v_passo := 1;

        LOOP
            v_dt := fn_calcular_proxima_data(COALESCE(rec.ultimo_lancamento, rec.data_inicio), rec.frequencia, v_passo);
            EXIT WHEN v_dt > p_ate OR (rec.data_fim IS NOT NULL AND v_dt > rec.data_fim);

            v_fatura_id := NULL;
            IF rec.cartao_id IS NOT NULL THEN
                v_fatura_id := fn_obter_ou_criar_fatura_para_compra(rec.cartao_id, rec.user_id, v_dt);
            END IF;

            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id, pote_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, recorrente_id, tipo_recorrencia
            ) VALUES (
                rec.user_id, rec.user_id, rec.tipo, COALESCE(rec.subtipo, rec.tipo, 'Geral'), rec.forma_movimentacao,
                rec.conta_id, rec.cartao_id, rec.categoria_id, rec.subcategoria_id, rec.pote_id,
                rec.valor, v_dt, rec.hora, COALESCE(rec.descricao, rec.tipo, 'Lançamento'),
                COALESCE(rec.status_padrao, 'Pendente')::status_lancamento,
                CASE WHEN rec.regra IS NOT NULL AND rec.regra <> '' THEN rec.regra::regra_financeira ELSE NULL END,
                v_fatura_id, rec.id, 'fixa'
            )
            ON CONFLICT (recorrente_id, data) WHERE (recorrente_id IS NOT NULL) DO NOTHING;

            IF FOUND THEN
                v_inseridos := v_inseridos + 1;
            END IF;

            v_max_dt := v_dt;
            v_passo := v_passo + 1;
        END LOOP;

        IF v_max_dt > COALESCE(rec.ultimo_lancamento, rec.data_inicio) THEN
            UPDATE public.transacoes_recorrentes
            SET ultimo_lancamento = v_max_dt
            WHERE id = rec.id;
        END IF;
    END LOOP;

    RETURN jsonb_build_object('sucesso', true, 'total_gerados', v_inseridos);
END;
$$;
