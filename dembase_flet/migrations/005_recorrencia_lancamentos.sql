-- =============================================================================
-- DemBase v3 — Migration 005: Recorrência, Séries de Lançamentos e Status Switch
-- =============================================================================

-- 1. Atualizar o trigger de status automático
-- REGRA DE NEGÓCIO: A escolha manual do usuário (Switch) tem prioridade absoluta.
-- O trigger só deve atribuir status automático se NEW.status for NULL.
CREATE OR REPLACE FUNCTION public.definir_status_credito_automatico()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public'
AS $function$
BEGIN
    IF NEW.status IS NULL THEN
        IF NEW.data > CURRENT_DATE THEN
            NEW.status := 'Pendente';
        ELSE
            NEW.status := 'Pago';
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;

-- 2. Estender tabela 'lancamentos' com identificadores de série e recorrência
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'lancamentos' AND column_name = 'serie_id'
    ) THEN
        ALTER TABLE public.lancamentos ADD COLUMN serie_id UUID NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'lancamentos' AND column_name = 'recorrente_id'
    ) THEN
        ALTER TABLE public.lancamentos ADD COLUMN recorrente_id UUID NULL
            REFERENCES public.transacoes_recorrentes(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'lancamentos' AND column_name = 'tipo_recorrencia'
    ) THEN
        ALTER TABLE public.lancamentos ADD COLUMN tipo_recorrencia TEXT NOT NULL DEFAULT 'unica'
            CHECK (tipo_recorrencia IN ('unica', 'parcelada', 'repetida', 'fixa'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_lancamentos_serie_id ON public.lancamentos(serie_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_recorrente_id ON public.lancamentos(recorrente_id);
-- Índice único parcial para garantir que fixas nunca gerem lançamentos duplicados na mesma data
CREATE UNIQUE INDEX IF NOT EXISTS idx_lancamentos_rec_data ON public.lancamentos(recorrente_id, data)
    WHERE recorrente_id IS NOT NULL;

-- 3. Estender tabela 'transacoes_recorrentes'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'transacoes_recorrentes' AND column_name = 'subtipo'
    ) THEN
        ALTER TABLE public.transacoes_recorrentes ADD COLUMN subtipo TEXT NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'transacoes_recorrentes' AND column_name = 'status_padrao'
    ) THEN
        ALTER TABLE public.transacoes_recorrentes ADD COLUMN status_padrao TEXT DEFAULT 'Pendente';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'transacoes_recorrentes' AND column_name = 'hora'
    ) THEN
        ALTER TABLE public.transacoes_recorrentes ADD COLUMN hora INTEGER NULL;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'transacoes_recorrentes' AND column_name = 'modo'
    ) THEN
        ALTER TABLE public.transacoes_recorrentes ADD COLUMN modo TEXT DEFAULT 'fixa'
            CHECK (modo IN ('fixa', 'repetida'));
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'transacoes_recorrentes' AND column_name = 'quantidade'
    ) THEN
        ALTER TABLE public.transacoes_recorrentes ADD COLUMN quantidade INTEGER NULL;
    END IF;
END $$;

-- 4. Função auxiliar: calcular próxima data com ancoragem e clamping no fim do mês
CREATE OR REPLACE FUNCTION public.fn_calcular_proxima_data(
    p_data_base DATE,
    p_frequencia TEXT,
    p_passo INTEGER
)
RETURNS DATE
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    v_freq TEXT := lower(COALESCE(p_frequencia, 'mensal'));
    v_orig_day INT;
    v_target_month_first DATE;
    v_last_day_target DATE;
    v_days_in_month INT;
    v_interval_months INT := 1;
BEGIN
    IF p_passo = 0 THEN
        RETURN p_data_base;
    END IF;

    IF v_freq = 'diaria' THEN
        RETURN (p_data_base + (p_passo || ' days')::interval)::DATE;
    ELSIF v_freq = 'semanal' THEN
        RETURN (p_data_base + ((p_passo * 7) || ' days')::interval)::DATE;
    ELSIF v_freq = 'quinzenal' THEN
        RETURN (p_data_base + ((p_passo * 15) || ' days')::interval)::DATE;
    ELSIF v_freq IN ('mensal', 'bimestral', 'trimestral', 'semestral', 'anual') THEN
        IF v_freq = 'bimestral' THEN v_interval_months := 2;
        ELSIF v_freq = 'trimestral' THEN v_interval_months := 3;
        ELSIF v_freq = 'semestral' THEN v_interval_months := 6;
        ELSIF v_freq = 'anual' THEN v_interval_months := 12;
        ELSE v_interval_months := 1;
        END IF;

        v_orig_day := extract(day FROM p_data_base)::int;
        v_target_month_first := (date_trunc('month', p_data_base) + ((p_passo * v_interval_months) || ' months')::interval)::DATE;
        v_last_day_target := (date_trunc('month', v_target_month_first) + interval '1 month' - interval '1 day')::DATE;
        v_days_in_month := extract(day FROM v_last_day_target)::int;

        RETURN (date_trunc('month', v_target_month_first) + ((LEAST(v_orig_day, v_days_in_month) - 1) || ' days')::interval)::DATE;
    ELSE
        RETURN (p_data_base + ((p_passo * 30) || ' days')::interval)::DATE;
    END IF;
END;
$$;

-- 5. Função auxiliar: obter ou criar fatura para cartão de crédito
CREATE OR REPLACE FUNCTION public.fn_obter_ou_criar_fatura_para_compra(
    p_cartao_id UUID,
    p_user_id UUID,
    p_data_compra DATE
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_dia_fechamento SMALLINT;
    v_dia_vencimento SMALLINT;
    v_mes_target INT;
    v_ano_target INT;
    v_base_target DATE;
    v_fatura_id UUID;
    v_dt_fechamento DATE;
    v_dt_vencimento DATE;
    v_last_day INT;
BEGIN
    IF p_cartao_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT dia_fechamento, dia_vencimento
    INTO v_dia_fechamento, v_dia_vencimento
    FROM public.cartoes
    WHERE id = p_cartao_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    v_dia_fechamento := COALESCE(v_dia_fechamento, 1);
    v_dia_vencimento := COALESCE(v_dia_vencimento, 10);

    -- Se a compra ocorreu no dia de fechamento ou depois, entra na fatura do mês seguinte
    IF extract(day FROM p_data_compra) >= v_dia_fechamento THEN
        v_base_target := (date_trunc('month', p_data_compra) + interval '1 month')::DATE;
    ELSE
        v_base_target := p_data_compra;
    END IF;

    v_mes_target := extract(month FROM v_base_target)::int;
    v_ano_target := extract(year FROM v_base_target)::int;

    -- Tentar encontrar fatura existente
    SELECT id INTO v_fatura_id
    FROM public.faturas
    WHERE cartao_id = p_cartao_id AND mes = v_mes_target AND ano = v_ano_target;

    IF v_fatura_id IS NOT NULL THEN
        RETURN v_fatura_id;
    END IF;

    -- Calcular data_fechamento e data_vencimento seguras (clamp no fim do mês)
    v_last_day := extract(day FROM (date_trunc('month', v_base_target) + interval '1 month' - interval '1 day'))::int;
    v_dt_fechamento := (date_trunc('month', v_base_target) + ((LEAST(v_dia_fechamento, v_last_day) - 1) || ' days')::interval)::DATE;

    -- Se dia vencimento < dia fechamento, vencimento cai no mês seguinte
    IF v_dia_vencimento < v_dia_fechamento THEN
        v_last_day := extract(day FROM (date_trunc('month', v_base_target + interval '1 month') + interval '1 month' - interval '1 day'))::int;
        v_dt_vencimento := (date_trunc('month', v_base_target + interval '1 month') + ((LEAST(v_dia_vencimento, v_last_day) - 1) || ' days')::interval)::DATE;
    ELSE
        v_dt_vencimento := (date_trunc('month', v_base_target) + ((LEAST(v_dia_vencimento, v_last_day) - 1) || ' days')::interval)::DATE;
    END IF;

    INSERT INTO public.faturas (
        cartao_id, user_id, mes, ano, valor_total, valor_pago,
        data_fechamento, data_vencimento, status
    ) VALUES (
        p_cartao_id, p_user_id, v_mes_target, v_ano_target, 0.00, 0.00,
        v_dt_fechamento, v_dt_vencimento, 'aberta'
    )
    ON CONFLICT (cartao_id, mes, ano) DO UPDATE SET atualizado_em = NOW()
    RETURNING id INTO v_fatura_id;

    RETURN v_fatura_id;
END;
$$;

-- 6. RPC: Criar lançamento com recorrência (atômico)
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
    v_user_id := COALESCE(auth.uid(), (p_dados->>'user_id')::uuid);
    IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Usuário não autenticado';
    END IF;

    v_perfil_id := COALESCE((p_dados->>'perfil_id')::uuid, v_user_id);
    v_tipo := p_dados->>'tipo';
    v_subtipo := p_dados->>'subtipo';
    v_forma := p_dados->>'forma_movimentacao';
    v_conta_id := (p_dados->>'conta_id')::uuid;
    v_cartao_id := (p_dados->>'cartao_id')::uuid;
    v_categoria_id := (p_dados->>'categoria_id')::uuid;
    v_subcategoria_id := (p_dados->>'subcategoria_id')::uuid;
    v_destino_id := (p_dados->>'destino_id')::uuid;
    v_descricao := p_dados->>'descricao';
    v_regra := p_dados->>'regra';
    v_hora := (p_dados->>'hora')::int;
    v_status_inicial := COALESCE(p_dados->>'status', 'Pago');
    v_data_inicio := (p_dados->>'data')::date;
    v_valor_total := (p_dados->>'valor')::numeric;

    -- Se houver destino_id (Transferência entre contas), garante espelhamento na tabela destinos
    IF v_destino_id IS NOT NULL THEN
        INSERT INTO public.destinos (id, perfil_id, user_id, nome, ativo)
        SELECT c.id, COALESCE(c.perfil_id, v_perfil_id), COALESCE(c.user_id, v_user_id), c.nome, TRUE
        FROM public.contas c
        WHERE c.id = v_destino_id
        ON CONFLICT (id) DO UPDATE SET nome = EXCLUDED.nome;
    END IF;

    -- =========================================================================
    -- MODO ÚNICA
    -- =========================================================================
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
            CASE WHEN v_regra IS NOT NULL AND v_regra <> '' THEN v_regra::regra_financeira ELSE NULL END,
            v_fatura_id, 1, 1, v_serie_id, 'unica'
        );

        RETURN jsonb_build_object('sucesso', true, 'serie_id', v_serie_id, 'total_criados', 1);

    -- =========================================================================
    -- MODO PARCELADA (Crédito: valor total dividido em N parcelas sem perda de centavos)
    -- =========================================================================
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

            v_dt := fn_calcular_proxima_data(v_data_inicio, COALESCE(p_frequencia, 'mensal'), i - 1);
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
                CASE WHEN v_regra IS NOT NULL AND v_regra <> '' THEN v_regra::regra_financeira ELSE NULL END,
                v_fatura_id, i, v_qtd, v_serie_id, 'parcelada'
            );
            v_criados := v_criados + 1;
        END LOOP;

        RETURN jsonb_build_object('sucesso', true, 'serie_id', v_serie_id, 'total_criados', v_criados);

    -- =========================================================================
    -- MODO REPETIDA (Outras formas: mesmo valor repetido N vezes)
    -- =========================================================================
    ELSIF p_modo = 'repetida' THEN
        v_valor_item := v_valor_total;

        FOR i IN 1..v_qtd LOOP
            v_dt := fn_calcular_proxima_data(v_data_inicio, COALESCE(p_frequencia, 'mensal'), i - 1);
            v_status_item := CASE WHEN i = 1 THEN v_status_inicial ELSE 'Pendente' END;

            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id,
                valor, data, hora, descricao, status, regra,
                parcela_atual, total_parcelas, serie_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id,
                v_valor_item, v_dt, v_hora, v_descricao, v_status_item::status_lancamento,
                CASE WHEN v_regra IS NOT NULL AND v_regra <> '' THEN v_regra::regra_financeira ELSE NULL END,
                i, v_qtd, v_serie_id, 'repetida'
            );
            v_criados := v_criados + 1;
        END LOOP;

        RETURN jsonb_build_object('sucesso', true, 'serie_id', v_serie_id, 'total_criados', v_criados);

    -- =========================================================================
    -- MODO FIXA (Assinatura / Conta Fixa: cabeçalho + materializa 12 meses à frente)
    -- =========================================================================
    ELSIF p_modo = 'fixa' THEN
        INSERT INTO public.transacoes_recorrentes (
            user_id, conta_id, cartao_id, categoria_id, subcategoria_id,
            tipo, subtipo, forma_movimentacao, valor, descricao, regra,
            frequencia, dia_vencimento, data_inicio, data_fim, ultimo_lancamento,
            ativo, modo, status_padrao, hora, quantidade
        ) VALUES (
            v_user_id, v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id,
            v_tipo, v_subtipo, v_forma, v_valor_total, v_descricao, v_regra,
            COALESCE(p_frequencia, 'mensal'), extract(day FROM v_data_inicio)::smallint,
            v_data_inicio, NULL, v_data_inicio,
            TRUE, 'fixa', 'Pendente', v_hora, NULL
        ) RETURNING id INTO v_recorrente_id;

        v_limite_horizonte := (v_data_inicio + interval '12 months')::DATE;
        i := 0;
        LOOP
            v_dt := fn_calcular_proxima_data(v_data_inicio, COALESCE(p_frequencia, 'mensal'), i);
            EXIT WHEN v_dt > v_limite_horizonte;

            v_status_item := CASE WHEN i = 0 THEN v_status_inicial ELSE 'Pendente' END;

            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id, destino_id,
                valor, data, hora, descricao, status, regra,
                serie_id, recorrente_id, tipo_recorrencia
            ) VALUES (
                v_user_id, v_perfil_id, v_tipo, v_subtipo, v_forma,
                v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id,
                v_valor_total, v_dt, v_hora, v_descricao, v_status_item::status_lancamento,
                CASE WHEN v_regra IS NOT NULL AND v_regra <> '' THEN v_regra::regra_financeira ELSE NULL END,
                v_serie_id, v_recorrente_id, 'fixa'
            )
            ON CONFLICT (recorrente_id, data) DO NOTHING;

            v_criados := v_criados + 1;
            i := i + 1;
        END LOOP;

        UPDATE public.transacoes_recorrentes
        SET ultimo_lancamento = fn_calcular_proxima_data(v_data_inicio, COALESCE(p_frequencia, 'mensal'), i - 1)
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

-- 7. RPC: Gerar lançamentos de fixas pendentes (chamada ao iniciar o app, idempotente)
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

            INSERT INTO public.lancamentos (
                user_id, tipo, subtipo, forma_movimentacao,
                conta_id, cartao_id, categoria_id, subcategoria_id,
                valor, data, hora, descricao, status, regra,
                recorrente_id, tipo_recorrencia
            ) VALUES (
                rec.user_id, rec.tipo, rec.subtipo, rec.forma_movimentacao,
                rec.conta_id, rec.cartao_id, rec.categoria_id, rec.subcategoria_id,
                rec.valor, v_dt, rec.hora, rec.descricao,
                COALESCE(rec.status_padrao, 'Pendente')::status_lancamento,
                CASE WHEN rec.regra IS NOT NULL AND rec.regra <> '' THEN rec.regra::regra_financeira ELSE NULL END,
                rec.id, 'fixa'
            )
            ON CONFLICT (recorrente_id, data) DO NOTHING;

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

-- 8. RPC: Atualizar série
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
BEGIN
    UPDATE public.lancamentos
    SET
        descricao = COALESCE(p_dados->>'descricao', descricao),
        categoria_id = CASE WHEN p_dados ? 'categoria_id' AND p_dados->>'categoria_id' IS NOT NULL THEN (p_dados->>'categoria_id')::uuid ELSE categoria_id END,
        subcategoria_id = CASE WHEN p_dados ? 'subcategoria_id' THEN (p_dados->>'subcategoria_id')::uuid ELSE subcategoria_id END,
        conta_id = CASE WHEN p_dados ? 'conta_id' THEN (p_dados->>'conta_id')::uuid ELSE conta_id END,
        cartao_id = CASE WHEN p_dados ? 'cartao_id' THEN (p_dados->>'cartao_id')::uuid ELSE cartao_id END,
        forma_movimentacao = COALESCE(p_dados->>'forma_movimentacao', forma_movimentacao),
        subtipo = COALESCE(p_dados->>'subtipo', subtipo),
        regra = CASE WHEN p_dados ? 'regra' AND p_dados->>'regra' IS NOT NULL AND p_dados->>'regra' <> '' THEN (p_dados->>'regra')::regra_financeira ELSE regra END,
        valor = CASE WHEN p_dados ? 'valor' AND p_dados->>'valor' IS NOT NULL THEN (p_dados->>'valor')::numeric ELSE valor END,
        atualizado_em = NOW()
    WHERE serie_id = p_serie_id
      AND (p_a_partir_de IS NULL OR data >= p_a_partir_de);

    GET DIAGNOSTICS v_afetados = ROW_COUNT;

    RETURN jsonb_build_object('sucesso', true, 'afetados', v_afetados);
END;
$$;

-- 9. RPC: Excluir série
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
    v_sql TEXT;
BEGIN
    SELECT DISTINCT recorrente_id INTO v_rec_id
    FROM public.lancamentos
    WHERE serie_id = p_serie_id AND recorrente_id IS NOT NULL
    LIMIT 1;

    IF p_a_partir_de IS NULL THEN
        v_sql := 'DELETE FROM public.lancamentos WHERE serie_id = ' || quote_literal(p_serie_id);
    ELSE
        v_sql := 'DELETE FROM public.lancamentos WHERE serie_id = ' || quote_literal(p_serie_id) || ' AND data >= ' || quote_literal(p_a_partir_de);
    END IF;

    EXECUTE v_sql;
    GET DIAGNOSTICS v_afetados = ROW_COUNT;

    IF v_rec_id IS NOT NULL AND (p_a_partir_de IS NULL OR p_a_partir_de <= CURRENT_DATE) THEN
        UPDATE public.transacoes_recorrentes
        SET ativo = FALSE
        WHERE id = v_rec_id;
    END IF;

    RETURN jsonb_build_object('sucesso', true, 'afetados', v_afetados);
END;
$$;
