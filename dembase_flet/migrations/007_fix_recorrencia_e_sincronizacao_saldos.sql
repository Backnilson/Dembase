-- =============================================================================
-- DemBase v3 — Migração 007: Correção do ON CONFLICT em Recorrências Fixas (42P10)
-- e Trigger Automático de Sincronização de Saldos (Contas, Cartões e Faturas)
-- =============================================================================

-- 1. Criar índice único completo (não-parcial) para permitir inferência tanto com quanto sem WHERE
CREATE UNIQUE INDEX IF NOT EXISTS idx_lancamentos_rec_data_unq ON public.lancamentos (recorrente_id, data);

-- 2. Função de recálculo atômico de saldos de contas, faturas e limites de cartões
CREATE OR REPLACE FUNCTION public.fn_recalcular_saldos_usuario(p_user_id UUID)
RETURNS VOID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_fim_mes DATE := (date_trunc('month', CURRENT_DATE) + interval '1 month' - interval '1 day')::DATE;
BEGIN
    IF p_user_id IS NULL THEN
        RETURN;
    END IF;

    UPDATE public.contas c
    SET
        saldo_atual = COALESCE(c.saldo_inicial, 0)
            + COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.conta_id = c.id
                  AND l.tipo = 'Receita'
                  AND l.status = 'Pago'
            ), 0)
            + COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.destino_id = c.id
                  AND l.tipo = 'Transferência'
                  AND l.status = 'Pago'
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.conta_id = c.id
                  AND l.tipo = 'Despesa'
                  AND l.cartao_id IS NULL
                  AND l.status = 'Pago'
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.conta_id = c.id
                  AND l.tipo = 'Transferência'
                  AND l.status = 'Pago'
            ), 0),
        saldo_previsto = COALESCE(c.saldo_inicial, 0)
            + COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.conta_id = c.id
                  AND l.tipo = 'Receita'
                  AND (l.status = 'Pago' OR l.data <= v_fim_mes)
            ), 0)
            + COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.destino_id = c.id
                  AND l.tipo = 'Transferência'
                  AND (l.status = 'Pago' OR l.data <= v_fim_mes)
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.conta_id = c.id
                  AND l.tipo = 'Despesa'
                  AND l.cartao_id IS NULL
                  AND (l.status = 'Pago' OR l.data <= v_fim_mes)
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE l.conta_id = c.id
                  AND l.tipo = 'Transferência'
                  AND (l.status = 'Pago' OR l.data <= v_fim_mes)
            ), 0)
    WHERE c.user_id = p_user_id OR c.perfil_id = p_user_id;

    UPDATE public.faturas f
    SET valor_total = COALESCE((
        SELECT SUM(l.valor)
        FROM public.lancamentos l
        WHERE l.fatura_id = f.id
          AND l.tipo = 'Despesa'
    ), 0)
    WHERE f.user_id = p_user_id;

    UPDATE public.cartoes ct
    SET limite_disponivel = GREATEST(
        0,
        COALESCE(ct.limite_total, 0) - COALESCE((
            SELECT SUM(l.valor)
            FROM public.lancamentos l
            LEFT JOIN public.faturas f ON f.id = l.fatura_id
            WHERE l.cartao_id = ct.id
              AND l.tipo = 'Despesa'
              AND COALESCE(f.status, 'aberta') <> 'paga'
        ), 0)
    )
    WHERE ct.user_id = p_user_id;
END;
$$;

-- 3. Trigger automático em public.lancamentos
CREATE OR REPLACE FUNCTION public.fn_trg_sincronizar_saldos_lancamento()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_uid UUID;
BEGIN
    IF TG_OP = 'DELETE' THEN
        v_uid := COALESCE(OLD.user_id, OLD.perfil_id);
    ELSE
        v_uid := COALESCE(NEW.user_id, NEW.perfil_id);
    END IF;
    PERFORM public.fn_recalcular_saldos_usuario(v_uid);
    RETURN NULL;
END;
$$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_sincronizar_saldos_lancamento'
    ) THEN
        CREATE TRIGGER trg_sincronizar_saldos_lancamento
            AFTER INSERT OR UPDATE OR DELETE ON public.lancamentos
            FOR EACH ROW EXECUTE FUNCTION public.fn_trg_sincronizar_saldos_lancamento();
    END IF;
END $$;

-- 4. Atualizar RPC criar_lancamento_com_recorrencia
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
            conta_id, cartao_id, categoria_id, subcategoria_id, destino_id,
            valor, data, hora, descricao, status, regra,
            fatura_id, parcela_atual, total_parcelas, serie_id, tipo_recorrencia
        ) VALUES (
            v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
            v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id,
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
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, parcela_atual, total_parcelas, serie_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id,
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
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, parcela_atual, total_parcelas, serie_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id,
                v_valor_item, v_dt, v_hora, v_descricao, v_status_item::status_lancamento,
                CASE WHEN v_regra IS NOT NULL THEN v_regra::regra_financeira ELSE NULL END,
                v_fatura_id, i, v_qtd, v_serie_id, 'repetida'
            );
            v_criados := v_criados + 1;
        END LOOP;

        RETURN jsonb_build_object('sucesso', true, 'serie_id', v_serie_id, 'total_criados', v_criados);

    ELSIF p_modo = 'fixa' THEN
        INSERT INTO public.transacoes_recorrentes (
            user_id, conta_id, cartao_id, categoria_id, subcategoria_id,
            tipo, subtipo, forma_movimentacao, valor, descricao, regra,
            frequencia, dia_vencimento, data_inicio, data_fim, ultimo_lancamento,
            ativo, modo, status_padrao, hora, quantidade
        ) VALUES (
            v_user_id, v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id,
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
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, serie_id, recorrente_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id,
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

-- 5. Atualizar RPC gerar_lancamentos_recorrentes
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
                conta_id, cartao_id, categoria_id, subcategoria_id,
                valor, data, hora, descricao, status, regra,
                fatura_id, recorrente_id, tipo_recorrencia
            ) VALUES (
                rec.user_id, rec.user_id, rec.tipo, COALESCE(rec.subtipo, rec.tipo, 'Geral'), rec.forma_movimentacao,
                rec.conta_id, rec.cartao_id, rec.categoria_id, rec.subcategoria_id,
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

-- 6. Atualizar RPCs atualizar_serie e excluir_serie para aceitar serie_id ou recorrente_id
CREATE OR REPLACE FUNCTION public.atualizar_serie(
    p_serie_id UUID,
    p_a_partir_de DATE DEFAULT NULL,
    p_dados JSONB DEFAULT '{}'::jsonb
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

CREATE OR REPLACE FUNCTION public.excluir_serie(
    p_serie_id UUID,
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
    SELECT DISTINCT recorrente_id INTO v_rec_id
    FROM public.lancamentos
    WHERE (serie_id = p_serie_id OR recorrente_id = p_serie_id)
      AND recorrente_id IS NOT NULL
    LIMIT 1;

    IF p_a_partir_de IS NULL THEN
        DELETE FROM public.lancamentos
        WHERE (serie_id = p_serie_id OR recorrente_id = p_serie_id);
    ELSE
        DELETE FROM public.lancamentos
        WHERE (serie_id = p_serie_id OR recorrente_id = p_serie_id)
          AND data >= p_a_partir_de;
    END IF;

    GET DIAGNOSTICS v_afetados = ROW_COUNT;

    IF v_rec_id IS NOT NULL AND (p_a_partir_de IS NULL OR p_a_partir_de <= CURRENT_DATE) THEN
        UPDATE public.transacoes_recorrentes
        SET ativo = FALSE
        WHERE id = v_rec_id;
    END IF;

    RETURN jsonb_build_object('sucesso', true, 'afetados', v_afetados);
END;
$$;

-- 7. Recalcular saldos iniciais de todos os usuários existentes
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT DISTINCT id FROM auth.users LOOP
        PERFORM public.fn_recalcular_saldos_usuario(r.id);
    END LOOP;
END $$;
