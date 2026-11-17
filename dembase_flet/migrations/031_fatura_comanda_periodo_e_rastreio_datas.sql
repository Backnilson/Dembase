-- =============================================================================
-- DemBase v3 - Migration 031
-- FATURA COMANDA O PERIODO + RASTREABILIDADE DE DATAS (Vencimento x Pagamento)
--
-- Regras de negocio implementadas:
--   1. Compra no cartao pertence ao mes de VENCIMENTO da fatura em que caiu
--      (comprou em Outubro p/ fatura de Novembro -> 6 Potes e Relatorios de Novembro).
--   2. Compras de fatura em aberto NUNCA ficam "Pago" soltas; so viram "Pago"
--      quando a fatura e liquidada (liquidar_pagamento_fatura) e voltam a
--      "Pendente" no estorno (estornar_pagamento_fatura).
--   3. Tres marcos de tempo por lancamento:
--        data            -> data da compra / lancamento (nao muda)
--        data_vencimento -> previsao original (vencimento da fatura p/ cartao;
--                           igual a `data` para os demais) - chave de PERIODO
--        data_pagamento  -> dia em que o dinheiro realmente saiu/entrou
--   4. Relatorio do cartao passa a devolver pote_id / pote_nome / pote_cor.
--
-- Estrategia: aditiva e idempotente. Funcoes existentes sao reescritas a partir
-- da propria definicao viva (pg_get_functiondef) por substituicoes com
-- asserção: se o padrao nao casar, a migration ABORTA (nada silencioso).
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. COLUNAS NOVAS + INDICES
-- -----------------------------------------------------------------------------
ALTER TABLE public.lancamentos ADD COLUMN IF NOT EXISTS data_vencimento DATE;
ALTER TABLE public.lancamentos ADD COLUMN IF NOT EXISTS data_pagamento  DATE;

COMMENT ON COLUMN public.lancamentos.data IS
    'Data da compra / lancamento (Credito: dia da compra). Para despesas fora do cartao e a propria data de vencimento.';
COMMENT ON COLUMN public.lancamentos.data_vencimento IS
    'Previsao original. Credito: vencimento da fatura onde a compra caiu. Demais: igual a data. E a CHAVE DE PERIODO dos 6 Potes e Relatorios. Mantida por trigger.';
COMMENT ON COLUMN public.lancamentos.data_pagamento IS
    'Dia em que o pagamento foi efetivado (NULL enquanto Pendente). Pagar adiantado preserva data_vencimento. Credito: dia do pagamento da fatura.';

CREATE INDEX IF NOT EXISTS idx_lancamentos_user_venc   ON public.lancamentos (user_id, data_vencimento);
CREATE INDEX IF NOT EXISTS idx_lancamentos_perfil_venc ON public.lancamentos (perfil_id, data_vencimento);

-- -----------------------------------------------------------------------------
-- 2. FUNCAO AUXILIAR: DATA DE CAIXA (quando o dinheiro de fato se moveu)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_data_caixa(p_status TEXT, p_data_pagamento DATE, p_data DATE)
RETURNS DATE
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE WHEN p_status = 'Pago' THEN COALESCE(p_data_pagamento, p_data) ELSE p_data END;
$$;

-- -----------------------------------------------------------------------------
-- 3. TRIGGER BEFORE INSERT/UPDATE: vencimento, pagamento e trava de status
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_trg_lancamento_datas_e_status()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public'
AS $function$
DECLARE
    v_fat               RECORD;
    v_em_fluxo_fatura   BOOLEAN := COALESCE(current_setting('dembase.fluxo_fatura', true), '') = 'on';
BEGIN
    -- ---------------------------------------------------------------------
    -- A) DESPESA NO CARTAO (pertence a uma fatura)
    -- ---------------------------------------------------------------------
    IF NEW.tipo = 'Despesa' AND NEW.cartao_id IS NOT NULL THEN
        IF NEW.fatura_id IS NULL THEN
            NEW.fatura_id := public.fn_obter_ou_criar_fatura_para_compra(
                NEW.cartao_id,
                COALESCE(NEW.user_id, NEW.perfil_id, auth.uid()),
                NEW.data
            );
        END IF;

        SELECT f.status, f.data_vencimento, f.data_pagamento, f.valor_pago
          INTO v_fat
          FROM public.faturas f
         WHERE f.id = NEW.fatura_id;

        -- O mes de vencimento da fatura comanda o periodo da compra
        NEW.data_vencimento := COALESCE(v_fat.data_vencimento, NEW.data);

        -- TRAVA: status da compra e ditado pela fatura, nunca solto.
        -- Uma fatura recem-criada (zerada) pode ter status='paga' pelo trigger de fatura zerada,
        -- por isso verificamos tambem se houve pagamento efetivo (valor_pago > 0 ou data_pagamento IS NOT NULL).
        IF NOT v_em_fluxo_fatura THEN
            IF TG_OP = 'INSERT' THEN
                NEW.status := 'Pendente';
            ELSIF NEW.fatura_id IS DISTINCT FROM OLD.fatura_id THEN
                NEW.status := 'Pendente';
            ELSIF COALESCE(v_fat.status, 'aberta') = 'paga'
              AND (COALESCE(v_fat.valor_pago, 0) > 0 OR v_fat.data_pagamento IS NOT NULL) THEN
                NEW.status := 'Pago';
            ELSE
                NEW.status := 'Pendente';
            END IF;
        END IF;

        IF NEW.status = 'Pago' THEN
            NEW.data_pagamento := COALESCE(NEW.data_pagamento, v_fat.data_pagamento, NEW.data_vencimento);
        ELSE
            NEW.data_pagamento := NULL;
        END IF;

        RETURN NEW;
    END IF;

    -- ---------------------------------------------------------------------
    -- B) DEMAIS LANCAMENTOS (conta, caixinha, receita, transferencia)
    -- ---------------------------------------------------------------------
    NEW.data_vencimento := NEW.data;

    IF NEW.status = 'Pago' THEN
        IF TG_OP = 'INSERT' THEN
            -- Lancado ja como pago: passado = pago no proprio dia; futuro = pago adiantado hoje
            NEW.data_pagamento := COALESCE(NEW.data_pagamento, LEAST(NEW.data, CURRENT_DATE));
        ELSIF OLD.status IS DISTINCT FROM 'Pago' THEN
            -- Baixa (Pendente -> Pago): dia real do pagamento (hoje), preservando o vencimento
            NEW.data_pagamento := COALESCE(NEW.data_pagamento, CURRENT_DATE);
        ELSE
            NEW.data_pagamento := COALESCE(NEW.data_pagamento, NEW.data_vencimento);
        END IF;
    ELSE
        NEW.data_pagamento := NULL;
    END IF;

    RETURN NEW;
END;
$function$;

CREATE OR REPLACE TRIGGER trg_zz_lancamento_datas_e_status
    BEFORE INSERT OR UPDATE ON public.lancamentos
    FOR EACH ROW EXECUTE FUNCTION public.fn_trg_lancamento_datas_e_status();

-- -----------------------------------------------------------------------------
-- 4. TRIGGER AFTER UPDATE em faturas: propaga novo vencimento aos lancamentos
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_trg_fatura_propaga_vencimento()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
    IF NEW.data_vencimento IS DISTINCT FROM OLD.data_vencimento THEN
        UPDATE public.lancamentos
           SET data_vencimento = NEW.data_vencimento
         WHERE fatura_id = NEW.id
           AND tipo = 'Despesa'
           AND cartao_id IS NOT NULL;
    END IF;
    RETURN NULL;
END;
$function$;

CREATE OR REPLACE TRIGGER trg_fatura_propaga_vencimento
    AFTER UPDATE OF data_vencimento ON public.faturas
    FOR EACH ROW EXECUTE FUNCTION public.fn_trg_fatura_propaga_vencimento();

-- -----------------------------------------------------------------------------
-- 5. HELPER DE REESCRITA SEGURA (descartado ao fim da sessao)
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION pg_temp.fn_reescrever(
    p_nome      TEXT,
    p_nargs     INT,
    p_marcador  TEXT,
    p_pares     TEXT[]
) RETURNS TEXT
LANGUAGE plpgsql
AS $helper$
DECLARE
    v_oid    OID;
    v_def    TEXT;
    v_novo   TEXT;
    v_antes  TEXT;
    i        INT;
BEGIN
    SELECT p.oid INTO v_oid
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public' AND p.proname = p_nome AND p.pronargs = p_nargs;

    IF v_oid IS NULL THEN
        RAISE EXCEPTION 'Funcao % (% args) nao encontrada', p_nome, p_nargs;
    END IF;

    v_def := pg_get_functiondef(v_oid);

    IF position(p_marcador IN v_def) > 0 THEN
        RETURN p_nome || ': ja migrada';
    END IF;

    v_novo := v_def;
    i := 1;
    WHILE i < array_length(p_pares, 1) LOOP
        v_antes := v_novo;
        v_novo := regexp_replace(v_novo, p_pares[i], p_pares[i + 1], 'g');
        IF v_novo = v_antes THEN
            RAISE EXCEPTION 'Padrao nao casou em %: %', p_nome, p_pares[i];
        END IF;
        i := i + 2;
    END LOOP;

    EXECUTE v_novo;
    RETURN p_nome || ': reescrita';
END;
$helper$;

-- Padrao generico: "[l.]data BETWEEN" -> "[l.]data_vencimento BETWEEN"
-- (grupo 2 = prefixo "l." opcional; grupo 3 = resto da comparacao)

-- ---- 6 POTES -----------------------------------------------------------------
SELECT pg_temp.fn_reescrever('get_potes_resumo', 3, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+p_data_inicio)$p$,
    $p$\1\2data_vencimento\3$p$
]);

SELECT pg_temp.fn_reescrever('fn_diagnostico_potes_detalhe', 3, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+v_di)$p$,
    $p$\1\2data_vencimento\3$p$
]);

SELECT pg_temp.fn_reescrever('fn_diagnostico_potes_funil', 1, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s)$p$,
    $p$\1\2data_vencimento\3$p$
]);

SELECT pg_temp.fn_reescrever('get_cobertura_reserva', 2, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+p_data_inicio)$p$,
    $p$\1\2data_vencimento\3$p$
]);

-- ---- DASHBOARD / TOTAIS / REGRA 50-30-20 -------------------------------------
SELECT pg_temp.fn_reescrever('get_dashboard_periodo', 2, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+v_inicio)$p$,
    $p$\1\2data_vencimento\3$p$,
    $p$SELECT(\s+)data,(\s+)EXTRACT\(DAY FROM data\)::INT AS dia,(\s+)TO_CHAR\(data, 'DD/MM'\)$p$,
    $p$SELECT\1data_vencimento AS data,\2EXTRACT(DAY FROM data_vencimento)::INT AS dia,\3TO_CHAR(data_vencimento, 'DD/MM')$p$,
    $p$GROUP BY data(\s+\) row)$p$,
    $p$GROUP BY data_vencimento\1$p$
]);

SELECT pg_temp.fn_reescrever('get_regra_50_30_20_summary', 2, 'data_vencimento >= p_data_inicio', ARRAY[
    $p$(p_data_inicio IS NULL OR )data( >= p_data_inicio)$p$,
    $p$\1data_vencimento\2$p$,
    $p$(p_data_fim IS NULL OR )data( <= p_data_fim)$p$,
    $p$\1data_vencimento\2$p$
]);

SELECT pg_temp.fn_reescrever('get_financial_totals', 2, 'data_vencimento >= p_data_inicio', ARRAY[
    $p$(p_data_inicio IS NULL OR )data( >= p_data_inicio)$p$,
    $p$\1data_vencimento\2$p$,
    $p$(p_data_fim IS NULL OR )data( <= p_data_fim)$p$,
    $p$\1data_vencimento\2$p$
]);

SELECT pg_temp.fn_reescrever('get_dashboard_overview', 2, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+v_inicio)$p$,
    $p$\1\2data_vencimento\3$p$
]);

SELECT pg_temp.fn_reescrever('get_despesas_por_categoria', 2, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+v_inicio)$p$,
    $p$\1\2data_vencimento\3$p$
]);

SELECT pg_temp.fn_reescrever('get_receitas_por_categoria', 2, 'data_vencimento BETWEEN', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+v_inicio)$p$,
    $p$\1\2data_vencimento\3$p$
]);

-- Balanco 6 meses: mes de competencia (vencimento) e inclui compras do cartao
SELECT pg_temp.fn_reescrever('get_balanco_ultimos_6_meses', 0, 'FROM data_vencimento)', ARRAY[
    $p$FROM data\)$p$,
    $p$FROM data_vencimento)$p$,
    $p$TO_CHAR\(data, 'Mon/YY'\)$p$,
    $p$TO_CHAR(data_vencimento, 'Mon/YY')$p$,
    $p$AND data >= DATE_TRUNC$p$,
    $p$AND data_vencimento >= DATE_TRUNC$p$,
    $p$tipo = 'Despesa' AND cartao_id IS NULL AND NOT$p$,
    $p$tipo = 'Despesa' AND NOT$p$
]);

-- ---- RELATORIO GERAL DE LANCAMENTOS -------------------------------------------
SELECT pg_temp.fn_reescrever('get_relatorio_lancamentos', 5, 'l.data_pagamento', ARRAY[
    $p$(^|[^A-Za-z0-9_.])(l\.)?data(\s+BETWEEN\s+v_inicio)$p$,
    $p$\1\2data_vencimento\3$p$,
    $p$l\.data,(\s+)TO_CHAR\(l\.data, 'DD/MM'\) AS label,$p$,
    $p$l.data_vencimento AS data,\1TO_CHAR(l.data_vencimento, 'DD/MM') AS label,$p$,
    $p$GROUP BY l\.data(\s+\) row)$p$,
    $p$GROUP BY l.data_vencimento\1$p$,
    $p$ORDER BY l\.data DESC,$p$,
    $p$ORDER BY l.data_vencimento DESC, l.data DESC,$p$,
    $p$(l\.regra::text AS regra,)$p$,
    $p$\1 l.data_vencimento, l.data_pagamento, l.fatura_id, f.mes AS fatura_mes, f.ano AS fatura_ano, f.status AS fatura_status,$p$,
    $p$(LEFT JOIN public\.contas co ON co\.id = l\.conta_id)$p$,
    $p$\1 LEFT JOIN public.faturas f ON f.id = l.fatura_id$p$,
    $p$(SELECT COALESCE\(JSONB_AGG\(row ORDER BY row\.posicao\), '\[\]'::jsonb\) INTO v_por_pote[\s\S]*?)ROUND\(SUM\(l\.valor\) / NULLIF\(v_base_total, 0\) \* 100, 1\)([\s\S]*?)AND \(\s*\(v_tipo IS NULL AND l\.tipo IN \('Receita', 'Despesa'\)\)\s*OR \(v_tipo IS NOT NULL AND l\.tipo = v_tipo\)\s*\)$p$,
    $p$\1ROUND(SUM(l.valor) / NULLIF(v_despesas, 0) * 100, 1)\2AND l.tipo = 'Despesa' AND (v_tipo IS NULL OR v_tipo = 'Despesa')$p$
]);

-- ---- RELATORIO DO CARTAO: POTE + DATAS + QUEBRA POR POTE -----------------------
SELECT pg_temp.fn_reescrever('get_relatorio_cartao', 6, 'v_por_pote', ARRAY[
    $p$(v_categoria_id UUID := NULLIF\(trim\(COALESCE\(p_filtros->>'categoria_id', ''\)\),\s*''\)::uuid;)$p$,
    $p$\1 v_pote_id UUID := NULLIF(trim(COALESCE(p_filtros->>'pote_id', '')), '')::uuid; v_regra TEXT := NULLIF(trim(COALESCE(p_filtros->>'regra', '')), ''); v_status TEXT := NULLIF(trim(COALESCE(p_filtros->>'status', '')), '');$p$,
    $p$(l\.regra::text AS regra,)$p$,
    $p$\1 l.pote_id, pot.nome AS pote_nome, pot.cor AS pote_cor, pot.posicao AS pote_posicao, l.data_vencimento, l.data_pagamento, f.data_vencimento AS fatura_data_vencimento, f.data_pagamento AS fatura_data_pagamento,$p$,
    $p$(LEFT JOIN public\.subcategorias sub ON sub\.id = l\.subcategoria_id)$p$,
    $p$\1 LEFT JOIN public.potes pot ON pot.id = l.pote_id$p$,
    $p$(v_evolucao\s+JSONB;)$p$,
    $p$\1 v_por_pote JSONB;$p$,
    $p$(SELECT COALESCE\(JSONB_AGG\(row ORDER BY row\.data ASC\), '\[\]'::jsonb\) INTO v_evolucao)$p$,
    $p$SELECT COALESCE(JSONB_AGG(row ORDER BY row.posicao), '[]'::jsonb) INTO v_por_pote FROM (SELECT pot.id AS pote_id, COALESCE(pot.posicao, 99) AS posicao, COALESCE(pot.nome, 'Sem Pote') AS nome, COALESCE(pot.cor, '#94A3B8') AS cor, SUM(l.valor) AS total, COUNT(*)::INT AS qtd, COALESCE(ROUND(SUM(l.valor) / NULLIF(v_gasto_per, 0) * 100, 1), 0) AS percentual FROM public.lancamentos l LEFT JOIN public.faturas f ON f.id = l.fatura_id LEFT JOIN public.potes pot ON pot.id = l.pote_id LEFT JOIN public.categorias cat ON cat.id = l.categoria_id WHERE (l.user_id = v_cartao.user_id OR l.perfil_id = v_cartao.user_id) AND l.cartao_id = p_cartao_id AND l.tipo = 'Despesa' AND ((l.fatura_id IS NOT NULL AND ((v_fatura_id IS NOT NULL AND l.fatura_id = v_fatura_id) OR (f.mes = v_mes AND f.ano = v_ano))) OR (l.fatura_id IS NULL AND EXTRACT(MONTH FROM l.data) = v_mes AND EXTRACT(YEAR FROM l.data) = v_ano)) AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id) AND (v_busca IS NULL OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%' OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%') GROUP BY pot.id, pot.posicao, pot.nome, pot.cor) row; \1$p$,
    $p$AND \(v_categoria_id IS NULL OR l\.categoria_id = v_categoria_id\)$p$,
    $p$AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id) AND (v_pote_id IS NULL OR l.pote_id = v_pote_id) AND (v_regra IS NULL OR l.regra::text = v_regra) AND (v_status IS NULL OR l.status::text = v_status)$p$,
    $p$('categorias', v_por_cat,)$p$,
    $p$\1 'por_pote', v_por_pote,$p$
]);

-- ---- CALENDARIO: expoe vencimento original e pagamento efetivo -----------------
SELECT pg_temp.fn_reescrever('get_calendario_financeiro_mes', 4, 'data_pagamento', ARRAY[
    $p$('data_compra', le\.data::TEXT,)$p$,
    $p$\1 'data_vencimento', le.data_efetiva::TEXT, 'data_pagamento', le.data_pagamento::TEXT, 'pote_id', le.pote_id,$p$
]);

-- ---- CONTAS (visao de CAIXA: quando o dinheiro realmente saiu) -----------------
SELECT pg_temp.fn_reescrever('get_relatorio_conta', 6, 'fn_data_caixa', ARRAY[
    $p$l\.data < v_inicio$p$,
    $p$public.fn_data_caixa(l.status::text, l.data_pagamento, l.data) < v_inicio$p$,
    $p$l\.data BETWEEN v_inicio AND v_fim$p$,
    $p$public.fn_data_caixa(l.status::text, l.data_pagamento, l.data) BETWEEN v_inicio AND v_fim$p$,
    $p$SELECT(\s+)l\.data,(\s+)SUM\(CASE$p$,
    $p$SELECT\1public.fn_data_caixa(l.status::text, l.data_pagamento, l.data) AS data,\2SUM(CASE$p$,
    $p$GROUP BY l\.data(\s+\) d)$p$,
    $p$GROUP BY public.fn_data_caixa(l.status::text, l.data_pagamento, l.data)\1$p$,
    $p$ORDER BY l\.data DESC,$p$,
    $p$ORDER BY public.fn_data_caixa(l.status::text, l.data_pagamento, l.data) DESC,$p$,
    $p$(l\.regra::text AS regra,)$p$,
    $p$\1 l.data_vencimento, l.data_pagamento, public.fn_data_caixa(l.status::text, l.data_pagamento, l.data) AS data_caixa,$p$
]);

SELECT pg_temp.fn_reescrever('get_lista_contas_resumo', 2, 'fn_data_caixa', ARRAY[
    $p$l\.data BETWEEN v_inicio AND v_fim$p$,
    $p$public.fn_data_caixa(l.status::text, l.data_pagamento, l.data) BETWEEN v_inicio AND v_fim$p$
]);

-- -----------------------------------------------------------------------------
-- 6. LIQUIDACAO / ESTORNO DA FATURA: unicos caminhos que mexem no status Pago
-- -----------------------------------------------------------------------------
SELECT pg_temp.fn_reescrever('liquidar_pagamento_fatura', 4, 'dembase.fluxo_fatura', ARRAY[
    $p$(v_user_id := auth\.uid\(\);)$p$,
    $p$PERFORM set_config('dembase.fluxo_fatura', 'on', true); \1$p$,
    $p$SET status = 'Pago'::public\.status_lancamento,(\s+)atualizado_em = NOW\(\)$p$,
    $p$SET status = 'Pago'::public.status_lancamento,\1data_pagamento = v_dt_pagamento,\1atualizado_em = NOW()$p$,
    $p$(RETURN JSONB_BUILD_OBJECT\()$p$,
    $p$PERFORM set_config('dembase.fluxo_fatura', 'off', true); \1$p$
]);

SELECT pg_temp.fn_reescrever('estornar_pagamento_fatura', 1, 'dembase.fluxo_fatura', ARRAY[
    $p$(v_user_id := auth\.uid\(\);)$p$,
    $p$PERFORM set_config('dembase.fluxo_fatura', 'on', true); \1$p$,
    $p$SET status = CASE\s+WHEN data > CURRENT_DATE THEN 'Pendente'::public\.status_lancamento\s+ELSE 'Pago'::public\.status_lancamento\s+END,$p$,
    $p$SET status = 'Pendente'::public.status_lancamento, data_pagamento = NULL,$p$,
    $p$(RETURN JSONB_BUILD_OBJECT\()$p$,
    $p$PERFORM set_config('dembase.fluxo_fatura', 'off', true); \1$p$
]);

-- Permite pular o recalculo de saldos em operacoes em lote (backfill)
SELECT pg_temp.fn_reescrever('fn_trg_sincronizar_saldos_lancamento', 0, 'dembase.pular_recalculo', ARRAY[
    $p$(BEGIN\s+)(IF TG_OP = 'DELETE')$p$,
    $p$\1IF COALESCE(current_setting('dembase.pular_recalculo', true), '') = 'on' THEN RETURN NULL; END IF; \2$p$
]);

-- Respeita fatura_id manual enviada em p_dados ao criar compra no cartao (unica ou parcelada)
SELECT pg_temp.fn_reescrever('criar_lancamento_com_recorrencia', 5, 'p_dados->>''fatura_id''', ARRAY[
    $p$v_fatura_id := fn_obter_ou_criar_fatura_para_compra\(v_cartao_id, v_user_id, v_data_inicio\);$p$,
    $p$v_fatura_id := COALESCE(NULLIF(trim(COALESCE(p_dados->>'fatura_id', '')), '')::uuid, fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_data_inicio));$p$,
    $p$(ELSIF p_modo = 'parcelada' THEN[\s\S]*?)v_fatura_id := fn_obter_ou_criar_fatura_para_compra\(v_cartao_id, v_user_id, v_dt\);$p$,
    $p$\1IF NULLIF(trim(COALESCE(p_dados->>'fatura_id', '')), '') IS NOT NULL THEN IF i = 1 THEN v_fatura_id := NULLIF(trim(p_dados->>'fatura_id'), '')::uuid; ELSE SELECT fn_obter_ou_criar_fatura_mes_ano(v_cartao_id, v_user_id, (((f.ano * 12 + f.mes - 1) + (i - 1)) % 12) + 1, (((f.ano * 12 + f.mes - 1) + (i - 1)) / 12)::int) INTO v_fatura_id FROM public.faturas f WHERE f.id = NULLIF(trim(p_dados->>'fatura_id'), '')::uuid; END IF; END IF; IF v_fatura_id IS NULL THEN v_fatura_id := fn_obter_ou_criar_fatura_para_compra(v_cartao_id, v_user_id, v_dt); END IF;$p$
]);

-- -----------------------------------------------------------------------------
-- 7. RECALCULO DE SALDOS (Fatura comanda o status) + BACKFILL
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_recalcular_saldos_usuario(p_user_id uuid DEFAULT NULL::uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    v_uid UUID := COALESCE(p_user_id, auth.uid());
BEGIN
    IF v_uid IS NULL THEN
        RETURN;
    END IF;

    UPDATE public.contas c
    SET
        saldo_atual = COALESCE(c.saldo_inicial, 0)
            + COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.conta_id = c.id AND l.tipo = 'Receita' AND l.status = 'Pago'
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.conta_id = c.id AND l.tipo = 'Despesa' AND l.cartao_id IS NULL AND l.status = 'Pago'
                  AND NOT public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo)
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.conta_id = c.id AND l.tipo = 'Transferência' AND l.status = 'Pago'
            ), 0)
            + COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.destino_id = c.id AND l.tipo = 'Transferência' AND l.status = 'Pago'
            ), 0),

        saldo_previsto = COALESCE(c.saldo_inicial, 0)
            + COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.conta_id = c.id AND l.tipo = 'Receita'
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.conta_id = c.id AND l.tipo = 'Despesa' AND l.cartao_id IS NULL
                  AND NOT public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo)
            ), 0)
            - COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.conta_id = c.id AND l.tipo = 'Transferência'
            ), 0)
            + COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.destino_id = c.id AND l.tipo = 'Transferência'
            ), 0)
    WHERE c.user_id = v_uid;

    -- Fatura comanda o status: nunca promove fatura aberta para 'paga' sem liquidacao formal
    UPDATE public.faturas f
    SET
        valor_total = COALESCE((
            SELECT SUM(l.valor) FROM public.lancamentos l
            WHERE l.fatura_id = f.id AND l.tipo = 'Despesa'
        ), 0),
        valor_pago = CASE
            WHEN f.status = 'paga' AND (
                f.pagamento_lancamento_id IS NOT NULL
                OR f.data_pagamento IS NOT NULL
                OR f.conta_pagamento_id IS NOT NULL
                OR f.ano < 2026
                OR (f.ano = 2026 AND f.mes <= 10)
            )
            THEN COALESCE((
                SELECT SUM(l.valor) FROM public.lancamentos l
                WHERE l.fatura_id = f.id AND l.tipo = 'Despesa'
            ), 0)
            ELSE 0.00
        END,
        status = CASE
            WHEN COALESCE((SELECT SUM(l.valor) FROM public.lancamentos l WHERE l.fatura_id = f.id AND l.tipo = 'Despesa'), 0) <= 0.01
            THEN 'paga'
            WHEN f.status = 'paga' AND (
                f.pagamento_lancamento_id IS NOT NULL
                OR f.data_pagamento IS NOT NULL
                OR f.conta_pagamento_id IS NOT NULL
                OR f.ano < 2026
                OR (f.ano = 2026 AND f.mes <= 10)
            )
            THEN 'paga'
            WHEN f.status = 'paga'
            THEN 'aberta'
            ELSE f.status
        END
    FROM public.cartoes ct
    WHERE f.cartao_id = ct.id AND ct.user_id = v_uid;

    UPDATE public.cartoes ct
    SET
        limite_disponivel = COALESCE(ct.limite_total, 0) - COALESCE((
            SELECT SUM(l.valor) FROM public.lancamentos l
            WHERE l.cartao_id = ct.id AND l.tipo = 'Despesa' AND l.status = 'Pendente'
        ), 0)
    WHERE ct.user_id = v_uid;
END;
$function$;

DO $recalc_init$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT DISTINCT COALESCE(user_id, perfil_id) AS uid FROM public.lancamentos LOOP
        PERFORM public.fn_recalcular_saldos_usuario(r.uid);
    END LOOP;
END;
$recalc_init$;

SELECT set_config('dembase.pular_recalculo', 'on', true);

UPDATE public.lancamentos l
   SET fatura_id = public.fn_obter_ou_criar_fatura_para_compra(
           l.cartao_id, COALESCE(l.user_id, l.perfil_id), l.data)
 WHERE l.tipo = 'Despesa' AND l.cartao_id IS NOT NULL AND l.fatura_id IS NULL;

-- Forca o trigger a recalcular data_vencimento/data_pagamento em todas as linhas
UPDATE public.lancamentos SET data_vencimento = NULL WHERE id IS NOT NULL;

SELECT set_config('dembase.pular_recalculo', 'off', true);

DO $recalc$
DECLARE
    r RECORD;
BEGIN
    FOR r IN SELECT DISTINCT COALESCE(user_id, perfil_id) AS uid FROM public.lancamentos LOOP
        PERFORM public.fn_recalcular_saldos_usuario(r.uid);
    END LOOP;
END;
$recalc$;

NOTIFY pgrst, 'reload schema';
