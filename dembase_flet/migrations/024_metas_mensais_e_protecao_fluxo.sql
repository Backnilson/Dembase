-- =============================================================================
-- DemBase v3 — Migração 024: Metas Mensais Independentes (6 Potes e Caixa Livre)
-- =============================================================================
-- 1. Cria `public.potes_mensais` para armazenar as porcentagens e nomes dos 6 Potes
--    isoladamente por (user_id, ano, mes), mantendo `public.potes` como cadastro base
--    de IDs e cores para preservar todas as Foreign Keys existentes.
-- 2. Cria `public.config_caixa_livre_mensal` para armazenar o percentual de retenção
--    (Investimento/Poupança vs Livre para Gastar) da Sobra do Período por (user_id, ano, mes).
-- 3. Atualiza `get_potes_resumo(p_data_inicio, p_data_fim)` e cria `listar_potes_mes`,
--    `salvar_potes_mes`, `obter_config_caixa_livre_mes` e `salvar_config_caixa_livre_mes`.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. TABELA: potes_mensais (Metas dos 6 Potes por Mês/Ano)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.potes_mensais (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    pote_id       UUID NOT NULL REFERENCES public.potes(id) ON DELETE CASCADE,
    ano           SMALLINT NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    mes           SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    posicao       SMALLINT NOT NULL CHECK (posicao BETWEEN 1 AND 6),
    nome          TEXT NOT NULL CHECK (char_length(btrim(nome)) BETWEEN 1 AND 40),
    percentual    NUMERIC(5,2) NOT NULL CHECK (percentual BETWEEN 0 AND 100),
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_potes_mensais_user_periodo_pos  UNIQUE (user_id, ano, mes, posicao),
    CONSTRAINT uq_potes_mensais_user_periodo_pote UNIQUE (user_id, ano, mes, pote_id)
);

CREATE INDEX IF NOT EXISTS idx_potes_mensais_lookup
    ON public.potes_mensais(user_id, ano DESC, mes DESC, posicao);

ALTER TABLE public.potes_mensais ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'potes_mensais'
          AND policyname = 'potes_mensais_select_own'
    ) THEN
        CREATE POLICY "potes_mensais_select_own"
            ON public.potes_mensais
            FOR SELECT TO authenticated
            USING (user_id = auth.uid());
    END IF;
END $$;

GRANT SELECT ON public.potes_mensais TO authenticated;

-- Backfill inicial: garante snapshot dos potes atuais para o mês corrente e meses com lançamentos
INSERT INTO public.potes_mensais (user_id, pote_id, ano, mes, posicao, nome, percentual)
SELECT
    p.user_id,
    p.id AS pote_id,
    periodos.ano,
    periodos.mes,
    p.posicao,
    p.nome,
    p.percentual
FROM public.potes p
JOIN (
    SELECT DISTINCT
        COALESCE(l.user_id, l.perfil_id) AS uid,
        EXTRACT(YEAR FROM l.data)::SMALLINT AS ano,
        EXTRACT(MONTH FROM l.data)::SMALLINT AS mes
    FROM public.lancamentos l
    WHERE l.data IS NOT NULL
      AND COALESCE(l.user_id, l.perfil_id) IS NOT NULL
    UNION
    SELECT
        u.id AS uid,
        EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT AS ano,
        EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT AS mes
    FROM auth.users u
) periodos ON periodos.uid = p.user_id
ON CONFLICT (user_id, ano, mes, pote_id) DO NOTHING;


-- -----------------------------------------------------------------------------
-- 2. TABELA: config_caixa_livre_mensal (Retenção da Sobra por Mês/Ano)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.config_caixa_livre_mensal (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    ano               SMALLINT NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    mes               SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
    pct_investimento  NUMERIC(5,2) NOT NULL DEFAULT 50.00 CHECK (pct_investimento BETWEEN 0 AND 100),
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_caixa_livre_user_periodo UNIQUE (user_id, ano, mes)
);

CREATE INDEX IF NOT EXISTS idx_config_caixa_livre_lookup
    ON public.config_caixa_livre_mensal(user_id, ano DESC, mes DESC);

ALTER TABLE public.config_caixa_livre_mensal ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'public'
          AND tablename = 'config_caixa_livre_mensal'
          AND policyname = 'config_caixa_livre_own'
    ) THEN
        CREATE POLICY "config_caixa_livre_own"
            ON public.config_caixa_livre_mensal
            FOR ALL TO authenticated
            USING (user_id = auth.uid())
            WITH CHECK (user_id = auth.uid());
    END IF;
END $$;

GRANT SELECT, INSERT, UPDATE ON public.config_caixa_livre_mensal TO authenticated;


-- -----------------------------------------------------------------------------
-- 3. RPC: listar_potes_mes(p_mes, p_ano)
--    Retorna os 6 potes efetivos para o mês/ano solicitado.
--    Se o mês ainda não possuir configuração própria, herda do mês anterior
--    mais próximo ou do cadastro base `public.potes`.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.listar_potes_mes(
    p_mes SMALLINT DEFAULT NULL,
    p_ano SMALLINT DEFAULT NULL
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid       UUID := COALESCE(auth.uid(), (SELECT id FROM public.perfis LIMIT 1));
    v_mes       SMALLINT := COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT);
    v_ano       SMALLINT := COALESCE(p_ano, EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT);
    v_ref_ano   SMALLINT;
    v_ref_mes   SMALLINT;
    v_proprio   BOOLEAN := FALSE;
BEGIN
    IF v_uid IS NULL THEN
        RETURN '[]'::JSONB;
    END IF;

    PERFORM public.seed_potes_usuario(v_uid);

    -- 1. Verifica se já existe configuração salva exatamente para (v_ano, v_mes)
    IF (SELECT COUNT(*) FROM public.potes_mensais WHERE user_id = v_uid AND ano = v_ano AND mes = v_mes) = 6 THEN
        v_ref_ano := v_ano;
        v_ref_mes := v_mes;
        v_proprio := TRUE;
    ELSE
        -- 2. Busca o mês anterior mais recente configurado
        SELECT pm.ano, pm.mes
          INTO v_ref_ano, v_ref_mes
          FROM public.potes_mensais pm
         WHERE pm.user_id = v_uid
           AND (pm.ano < v_ano OR (pm.ano = v_ano AND pm.mes < v_mes))
         GROUP BY pm.ano, pm.mes
        HAVING COUNT(*) = 6
         ORDER BY pm.ano DESC, pm.mes DESC
         LIMIT 1;
    END IF;

    IF v_ref_ano IS NOT NULL AND v_ref_mes IS NOT NULL THEN
        RETURN (
            SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY t.posicao), '[]'::jsonb)
              FROM (
                  SELECT
                      p.id,
                      p.posicao,
                      pm.nome,
                      pm.percentual,
                      p.cor,
                      v_mes AS mes,
                      v_ano AS ano,
                      v_proprio AS personalizado_no_mes,
                      v_ref_mes AS mes_origem,
                      v_ref_ano AS ano_origem
                  FROM public.potes p
                  JOIN public.potes_mensais pm
                    ON pm.pote_id = p.id
                   AND pm.user_id = v_uid
                   AND pm.ano = v_ref_ano
                   AND pm.mes = v_ref_mes
                  WHERE p.user_id = v_uid
              ) t
        );
    END IF;

    -- 3. Fallback: lê da tabela base `public.potes`
    RETURN (
        SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY t.posicao), '[]'::jsonb)
          FROM (
              SELECT
                  p.id,
                  p.posicao,
                  p.nome,
                  p.percentual,
                  p.cor,
                  v_mes AS mes,
                  v_ano AS ano,
                  FALSE AS personalizado_no_mes,
                  v_mes AS mes_origem,
                  v_ano AS ano_origem
              FROM public.potes p
              WHERE p.user_id = v_uid
          ) t
    );
END $$;


-- -----------------------------------------------------------------------------
-- 4. RPC: salvar_potes_mes(p_potes, p_mes, p_ano)
--    Salva a configuração dos 6 potes EXCLUSIVAMENTE para o mês/ano informado,
--    garantindo que os demais meses mantenham suas próprias porcentagens intactas.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.salvar_potes_mes(
    p_potes JSONB,
    p_mes   SMALLINT DEFAULT NULL,
    p_ano   SMALLINT DEFAULT NULL
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid    UUID := COALESCE(auth.uid(), (SELECT id FROM public.perfis LIMIT 1));
    v_mes    SMALLINT := COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT);
    v_ano    SMALLINT := COALESCE(p_ano, EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT);
    v_item   JSONB;
    v_soma   NUMERIC := 0;
    v_nomes  TEXT[] := '{}';
    v_nome   TEXT;
    v_perc   NUMERIC;
    v_id     UUID;
    v_ids    UUID[] := '{}';
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Não autenticado.' USING ERRCODE = '28000';
    END IF;
    IF jsonb_typeof(p_potes) <> 'array' OR jsonb_array_length(p_potes) <> 6 THEN
        RAISE EXCEPTION 'POTES_INVALIDOS: envie exatamente 6 potes.' USING ERRCODE = 'check_violation';
    END IF;

    FOR v_item IN SELECT * FROM jsonb_array_elements(p_potes) LOOP
        v_id   := (v_item->>'id')::UUID;
        v_nome := btrim(COALESCE(v_item->>'nome', ''));
        v_perc := (v_item->>'percentual')::NUMERIC;

        IF v_nome = '' OR char_length(v_nome) > 40 THEN
            RAISE EXCEPTION 'POTES_INVALIDOS: nome do pote deve ter de 1 a 40 caracteres.' USING ERRCODE = 'check_violation';
        END IF;
        IF v_perc IS NULL OR v_perc < 0 OR v_perc > 100 THEN
            RAISE EXCEPTION 'POTES_INVALIDOS: percentual deve estar entre 0 e 100.' USING ERRCODE = 'check_violation';
        END IF;
        IF lower(v_nome) = ANY (v_nomes) THEN
            RAISE EXCEPTION 'POTES_INVALIDOS: nomes de potes devem ser únicos ("%").', v_nome USING ERRCODE = 'check_violation';
        END IF;
        IF v_id = ANY (v_ids) THEN
            RAISE EXCEPTION 'POTES_INVALIDOS: pote repetido no payload.' USING ERRCODE = 'check_violation';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM public.potes WHERE id = v_id AND user_id = v_uid) THEN
            RAISE EXCEPTION 'POTES_INVALIDOS: pote inexistente ou de outro usuário.' USING ERRCODE = 'check_violation';
        END IF;

        v_nomes := v_nomes || lower(v_nome);
        v_ids   := v_ids   || v_id;
        v_soma  := v_soma  + v_perc;
    END LOOP;

    IF v_soma <> 100 THEN
        RAISE EXCEPTION 'POTES_INVALIDOS: a soma dos percentuais deve ser exatamente 100%% (atual: %).', v_soma
            USING ERRCODE = 'check_violation';
    END IF;

    -- Antes de gravar o mês alvo, garante que outros meses que já possuam lançamentos
    -- tenham seu snapshot preservado com a configuração anterior, evitando efeito cascata indesejado.
    INSERT INTO public.potes_mensais (user_id, pote_id, ano, mes, posicao, nome, percentual)
    SELECT
        p.user_id,
        p.id,
        per.ano,
        per.mes,
        p.posicao,
        p.nome,
        p.percentual
    FROM public.potes p
    JOIN (
        SELECT DISTINCT
            EXTRACT(YEAR FROM l.data)::SMALLINT AS ano,
            EXTRACT(MONTH FROM l.data)::SMALLINT AS mes
        FROM public.lancamentos l
        WHERE (l.user_id = v_uid OR l.perfil_id = v_uid)
          AND l.data IS NOT NULL
        UNION
        SELECT
            EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT AS ano,
            EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT AS mes
    ) per ON NOT (per.ano = v_ano AND per.mes = v_mes)
    WHERE p.user_id = v_uid
    ON CONFLICT (user_id, ano, mes, pote_id) DO NOTHING;

    -- Grava/Atualiza exclusivamente o (v_ano, v_mes) solicitado em `potes_mensais`
    INSERT INTO public.potes_mensais (user_id, pote_id, ano, mes, posicao, nome, percentual, atualizado_em)
    SELECT
        v_uid,
        p.id,
        v_ano,
        v_mes,
        p.posicao,
        btrim(x.nome),
        x.percentual,
        NOW()
    FROM jsonb_to_recordset(p_potes) AS x(id UUID, nome TEXT, percentual NUMERIC)
    JOIN public.potes p ON p.id = x.id AND p.user_id = v_uid
    ON CONFLICT (user_id, ano, mes, pote_id)
    DO UPDATE SET
        nome          = EXCLUDED.nome,
        percentual    = EXCLUDED.percentual,
        atualizado_em = NOW();

    -- Mantém os nomes base sincronizados em `public.potes` se for o mês corrente ou único,
    -- sem afetar os snapshots já salvos em `public.potes_mensais` dos outros meses!
    IF v_ano = EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT
       AND v_mes = EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT THEN
        UPDATE public.potes p
           SET nome       = btrim(x.nome),
               percentual = x.percentual
          FROM jsonb_to_recordset(p_potes) AS x(id UUID, nome TEXT, percentual NUMERIC)
         WHERE p.id = x.id AND p.user_id = v_uid;
    END IF;

    RETURN public.listar_potes_mes(v_mes, v_ano);
END $$;


-- Mantém compatibilidade com a assinatura original salvar_potes(p_potes)
CREATE OR REPLACE FUNCTION public.salvar_potes(p_potes JSONB)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
    RETURN public.salvar_potes_mes(
        p_potes,
        EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT,
        EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT
    );
END $$;


-- -----------------------------------------------------------------------------
-- 5. RPC: get_potes_resumo(p_data_inicio, p_data_fim)
--    Usa as porcentagens exclusivas do mês/ano do período filtrado!
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_potes_resumo(
    p_data_inicio DATE,
    p_data_fim    DATE
) RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid         UUID := COALESCE(auth.uid(), (SELECT id FROM public.perfis LIMIT 1));
    v_renda       NUMERIC;
    v_gasto       NUMERIC;
    v_potes       JSONB;
    v_sem         JSONB;
    v_mes_ref     SMALLINT := EXTRACT(MONTH FROM COALESCE(p_data_inicio, CURRENT_DATE))::SMALLINT;
    v_ano_ref     SMALLINT := EXTRACT(YEAR  FROM COALESCE(p_data_inicio, CURRENT_DATE))::SMALLINT;
    v_potes_mes   JSONB;
    v_personaliz  BOOLEAN := FALSE;
BEGIN
    -- Se o filtro cruza meses mas termina no mês principal (ex: ciclo 25/Out a 24/Nov),
    -- se o ponto médio do intervalo cair no mês seguinte, usa o mês do ponto médio
    IF p_data_inicio IS NOT NULL AND p_data_fim IS NOT NULL THEN
        v_mes_ref := EXTRACT(MONTH FROM (p_data_inicio + ((p_data_fim - p_data_inicio) / 2)))::SMALLINT;
        v_ano_ref := EXTRACT(YEAR  FROM (p_data_inicio + ((p_data_fim - p_data_inicio) / 2)))::SMALLINT;
    END IF;

    v_potes_mes := public.listar_potes_mes(v_mes_ref, v_ano_ref);

    SELECT COALESCE(bool_or((elem->>'personalizado_no_mes')::BOOLEAN), FALSE)
      INTO v_personaliz
      FROM jsonb_array_elements(v_potes_mes) elem;

    -- 1. Receitas REAIS do período filtrado
    SELECT COALESCE(SUM(valor), 0) INTO v_renda
      FROM public.lancamentos
     WHERE (user_id = v_uid OR perfil_id = v_uid)
       AND lower(tipo) LIKE 'receita%'
       AND data BETWEEN p_data_inicio AND p_data_fim;

    -- 2. Despesas REAIS do período filtrado
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto
      FROM public.lancamentos
     WHERE (user_id = v_uid OR perfil_id = v_uid)
       AND lower(tipo) LIKE 'despesa%'
       AND data BETWEEN p_data_inicio AND p_data_fim;

    -- 3. Limite de cada pote = percentual configurado DAQUELE MÊS x Receita Real do período
    SELECT COALESCE(jsonb_agg(r ORDER BY r.posicao), '[]'::jsonb) INTO v_potes
    FROM (
        SELECT
            pm.id,
            pm.posicao,
            pm.nome,
            pm.cor,
            pm.percentual,
            ROUND(v_renda * pm.percentual / 100.0, 2) AS previsto,
            COALESCE(g.gasto, 0)                      AS gasto,
            COALESCE(g.qtd, 0)                        AS qtd_transacoes,
            ROUND(v_renda * pm.percentual / 100.0, 2) - COALESCE(g.gasto, 0) AS restante,
            CASE WHEN ROUND(v_renda * pm.percentual / 100.0, 2) > 0
                 THEN ROUND(COALESCE(g.gasto, 0) / (v_renda * pm.percentual / 100.0) * 100, 2)
                 ELSE 0 END                           AS percentual_usado
        FROM jsonb_to_recordset(v_potes_mes) AS pm(
            id UUID, posicao SMALLINT, nome TEXT, percentual NUMERIC, cor TEXT
        )
        LEFT JOIN (
            SELECT pote_id, SUM(valor) AS gasto, COUNT(*) AS qtd
              FROM public.lancamentos
             WHERE (user_id = v_uid OR perfil_id = v_uid)
               AND lower(tipo) LIKE 'despesa%'
               AND pote_id IS NOT NULL
               AND data BETWEEN p_data_inicio AND p_data_fim
             GROUP BY pote_id
        ) g ON g.pote_id = pm.id
    ) r;

    SELECT jsonb_build_object('qtd', COUNT(*), 'total', COALESCE(SUM(valor), 0)) INTO v_sem
      FROM public.lancamentos
     WHERE (user_id = v_uid OR perfil_id = v_uid)
       AND lower(tipo) LIKE 'despesa%'
       AND pote_id IS NULL
       AND data BETWEEN p_data_inicio AND p_data_fim;

    RETURN jsonb_build_object(
        'renda',                  v_renda,
        'base_utilizada',         v_renda,
        'total_gasto',            v_gasto,
        'saldo',                  v_renda - v_gasto,
        'percentual_renda_usado', CASE WHEN v_renda > 0 THEN ROUND(v_gasto / v_renda * 100, 2) ELSE 0 END,
        'mes_ref',                v_mes_ref,
        'ano_ref',                v_ano_ref,
        'personalizado_no_mes',   v_personaliz,
        'potes',                  v_potes,
        'sem_pote',               v_sem
    );
END $$;


-- -----------------------------------------------------------------------------
-- 6. RPCs de Configuração Mensal do Caixa Livre (Sobra do Período)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.obter_config_caixa_livre_mes(
    p_mes SMALLINT DEFAULT NULL,
    p_ano SMALLINT DEFAULT NULL
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid       UUID := COALESCE(auth.uid(), (SELECT id FROM public.perfis LIMIT 1));
    v_mes       SMALLINT := COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT);
    v_ano       SMALLINT := COALESCE(p_ano, EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT);
    v_pct       NUMERIC;
    v_proprio   BOOLEAN := FALSE;
    v_orig_mes  SMALLINT := v_mes;
    v_orig_ano  SMALLINT := v_ano;
BEGIN
    IF v_uid IS NULL THEN
        RETURN jsonb_build_object(
            'mes', v_mes, 'ano', v_ano,
            'pct_investimento', 50.0,
            'personalizado_no_mes', FALSE
        );
    END IF;

    -- 1. Busca configuração exata do mês/ano
    SELECT c.pct_investimento
      INTO v_pct
      FROM public.config_caixa_livre_mensal c
     WHERE c.user_id = v_uid AND c.ano = v_ano AND c.mes = v_mes
     LIMIT 1;

    IF FOUND THEN
        v_proprio := TRUE;
    ELSE
        -- 2. Herda do mês anterior mais recente configurado
        SELECT c.pct_investimento, c.mes, c.ano
          INTO v_pct, v_orig_mes, v_orig_ano
          FROM public.config_caixa_livre_mensal c
         WHERE c.user_id = v_uid
           AND (c.ano < v_ano OR (c.ano = v_ano AND c.mes < v_mes))
         ORDER BY c.ano DESC, c.mes DESC
         LIMIT 1;

        IF NOT FOUND THEN
            v_pct := 50.0;
        END IF;
    END IF;

    RETURN jsonb_build_object(
        'mes',                  v_mes,
        'ano',                  v_ano,
        'pct_investimento',     ROUND(COALESCE(v_pct, 50.0), 1),
        'personalizado_no_mes', v_proprio,
        'mes_origem',           v_orig_mes,
        'ano_origem',           v_orig_ano
    );
END $$;


CREATE OR REPLACE FUNCTION public.salvar_config_caixa_livre_mes(
    p_mes              SMALLINT,
    p_ano              SMALLINT,
    p_pct_investimento NUMERIC
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid UUID := COALESCE(auth.uid(), (SELECT id FROM public.perfis LIMIT 1));
    v_mes SMALLINT := COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT);
    v_ano SMALLINT := COALESCE(p_ano, EXTRACT(YEAR FROM CURRENT_DATE)::SMALLINT);
    v_pct NUMERIC  := GREATEST(0, LEAST(100, ROUND(COALESCE(p_pct_investimento, 50.0), 1)));
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Não autenticado.' USING ERRCODE = '28000';
    END IF;

    INSERT INTO public.config_caixa_livre_mensal (user_id, ano, mes, pct_investimento, atualizado_em)
    VALUES (v_uid, v_ano, v_mes, v_pct, NOW())
    ON CONFLICT (user_id, ano, mes)
    DO UPDATE SET
        pct_investimento = EXCLUDED.pct_investimento,
        atualizado_em    = NOW();

    RETURN jsonb_build_object(
        'mes',                  v_mes,
        'ano',                  v_ano,
        'pct_investimento',     v_pct,
        'personalizado_no_mes', TRUE
    );
END $$;


GRANT EXECUTE ON FUNCTION public.listar_potes_mes(SMALLINT, SMALLINT)                    TO authenticated;
GRANT EXECUTE ON FUNCTION public.salvar_potes_mes(JSONB, SMALLINT, SMALLINT)             TO authenticated;
GRANT EXECUTE ON FUNCTION public.salvar_potes(JSONB)                                     TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_potes_resumo(DATE, DATE)                            TO authenticated;
GRANT EXECUTE ON FUNCTION public.obter_config_caixa_livre_mes(SMALLINT, SMALLINT)        TO authenticated;
GRANT EXECUTE ON FUNCTION public.salvar_config_caixa_livre_mes(SMALLINT, SMALLINT, NUMERIC) TO authenticated;
