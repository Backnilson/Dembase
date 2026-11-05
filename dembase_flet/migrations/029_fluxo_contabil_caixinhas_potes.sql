-- =============================================================================
-- DemBase v3 — Migration 029: Arquitetura de Fluxo Contábil de Caixinhas,
-- Contas Bancárias e Metas Financeiras (6 Potes) sem Dupla Contagem
-- =============================================================================
-- Regras de Negócio:
--   Etapa A (Encher Caixinha / Aporte / Provisão):
--     - Lançamento com caixinha_id IS NOT NULL, subtipo = 'Provisionamento', status = 'Pago',
--       conta_id = <banco_origem>, pote_id = <pote_escolhido>.
--     - Desconta imediatamente do saldo_atual da Conta Bancária.
--     - Aumenta imediatamente o saldo_atual da Caixinha (via caixinhas_teto_movimentacoes).
--     - Contabiliza imediatamente como Gasto Real no Pote correspondente (6 Potes).
--   Etapa B (Gastar usando saldo da Caixinha / Consumo de Provisão):
--     - Lançamento com caixinha_id IS NOT NULL, subtipo = 'Consumo Caixinha',
--       forma_movimentacao = 'Caixinha', conta_id = NULL, status = 'Pago'.
--     - Desconta exclusivamente do saldo_atual da Caixinha.
--     - NEUTRO para Contas Bancárias (conta_id = NULL) e NEUTRO para o "Gasto Real"
--       dos 6 Potes e totais do Dashboard/Calendário (evitando dupla contagem).
--     - Mantém pote_id, categoria_id, subcategoria_id e caixinha_id para histórico visual no extrato.
-- =============================================================================

-- 1. Funções auxiliares imutáveis para classificar lançamentos de Caixinha
CREATE OR REPLACE FUNCTION public.fn_eh_consumo_caixinha_neutro(p_caixinha_id UUID, p_subtipo TEXT)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT p_caixinha_id IS NOT NULL
       AND LOWER(COALESCE(TRIM(p_subtipo), '')) <> 'provisionamento';
$$;

CREATE OR REPLACE FUNCTION public.fn_eh_despesa_orcamento_ativa(p_caixinha_id UUID, p_subtipo TEXT, p_status TEXT)
RETURNS BOOLEAN
LANGUAGE sql
IMMUTABLE
AS $$
    SELECT CASE
        WHEN p_caixinha_id IS NULL THEN TRUE
        WHEN LOWER(COALESCE(TRIM(p_subtipo), '')) = 'provisionamento' THEN (COALESCE(p_status, '') = 'Pago')
        ELSE FALSE
    END;
$$;

-- 2. Atualiza fn_trg_membro_padrao (BEFORE INSERT OR UPDATE em public.lancamentos)
--    para garantir integridade contábil absoluta em lançamentos vinculados a Caixinhas
CREATE OR REPLACE FUNCTION public.fn_trg_membro_padrao()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_uid UUID;
    v_m   UUID;
    v_cx  RECORD;
BEGIN
    IF TG_TABLE_NAME = 'lancamentos' AND NEW.caixinha_id IS NOT NULL THEN
        SELECT id, pote_id, conta_id, categoria_id, subcategoria_id, membro_id
        INTO v_cx
        FROM public.caixinhas_teto
        WHERE id = NEW.caixinha_id;

        IF LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' THEN
            -- Etapa A: Aporte / Provisionamento na Caixinha
            NEW.subtipo := 'Provisionamento';
            IF NEW.pote_id IS NULL AND v_cx.id IS NOT NULL THEN
                NEW.pote_id := v_cx.pote_id;
            END IF;
            IF NEW.conta_id IS NULL AND v_cx.id IS NOT NULL THEN
                NEW.conta_id := v_cx.conta_id;
            END IF;
            IF NEW.categoria_id IS NULL AND v_cx.id IS NOT NULL THEN
                NEW.categoria_id := v_cx.categoria_id;
            END IF;
            IF NEW.subcategoria_id IS NULL AND v_cx.id IS NOT NULL THEN
                NEW.subcategoria_id := v_cx.subcategoria_id;
            END IF;
        ELSE
            -- Etapa B: Consumo usando saldo da Caixinha (Neutro no Banco e no Pote)
            NEW.conta_id := NULL;
            NEW.cartao_id := NULL;
            NEW.fatura_id := NULL;
            NEW.subtipo := 'Consumo Caixinha';
            NEW.forma_movimentacao := 'Caixinha';
            NEW.status := 'Pago';
            IF NEW.pote_id IS NULL AND v_cx.id IS NOT NULL THEN
                NEW.pote_id := v_cx.pote_id;
            END IF;
            IF NEW.categoria_id IS NULL AND v_cx.id IS NOT NULL THEN
                NEW.categoria_id := v_cx.categoria_id;
            END IF;
            IF NEW.subcategoria_id IS NULL AND v_cx.id IS NOT NULL THEN
                NEW.subcategoria_id := v_cx.subcategoria_id;
            END IF;
        END IF;
    END IF;

    IF NEW.membro_id IS NOT NULL THEN
        RETURN NEW;
    END IF;
    v_uid := COALESCE(NEW.user_id, auth.uid());
    IF TG_TABLE_NAME = 'lancamentos' THEN
        IF NEW.caixinha_id IS NOT NULL AND v_cx.id IS NOT NULL THEN
            v_m := v_cx.membro_id;
        END IF;
        IF v_m IS NULL AND NEW.cartao_id IS NOT NULL THEN
            SELECT membro_id INTO v_m FROM public.cartoes WHERE id = NEW.cartao_id;
        END IF;
        IF v_m IS NULL AND NEW.conta_id IS NOT NULL THEN
            SELECT membro_id INTO v_m FROM public.contas WHERE id = NEW.conta_id;
        END IF;
    END IF;
    IF v_m IS NULL THEN
        v_m := public.fn_garantir_membro_principal(v_uid);
    END IF;
    NEW.membro_id := v_m;
    RETURN NEW;
END;
$$;

-- 3. Atualiza fn_recalcular_saldo_caixinha para considerar injeções e despesas de consumo sem duplicidade
CREATE OR REPLACE FUNCTION public.fn_recalcular_saldo_caixinha(p_caixinha_id UUID)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_meta              NUMERIC := 0;
    v_total_injecoes    NUMERIC := 0;
    v_total_despesas    NUMERIC := 0;
    v_deducoes_avulsas  NUMERIC := 0;
    v_base_provisionada NUMERIC := 0;
    v_novo_saldo        NUMERIC := 0;
    v_tem_provisao_lanc BOOLEAN := FALSE;
BEGIN
    IF p_caixinha_id IS NULL THEN
        RETURN jsonb_build_object('sucesso', false, 'motivo', 'id_nulo');
    END IF;

    SELECT COALESCE(valor_meta, 0)
    INTO v_meta
    FROM public.caixinhas_teto
    WHERE id = p_caixinha_id;

    IF NOT FOUND THEN
        RETURN jsonb_build_object('sucesso', false, 'motivo', 'nao_encontrada');
    END IF;

    -- Soma todas as despesas de consumo vinculadas a esta caixinha (exclui Provisionamento)
    SELECT COALESCE(SUM(valor), 0)
    INTO v_total_despesas
    FROM public.lancamentos
    WHERE caixinha_id = p_caixinha_id
      AND lower(tipo) LIKE 'despesa%'
      AND LOWER(COALESCE(TRIM(subtipo), '')) <> 'provisionamento';

    -- Soma eventuais deduções avulsas antigas que não tenham lancamento_id vinculado
    SELECT COALESCE(SUM(valor), 0)
    INTO v_deducoes_avulsas
    FROM public.caixinhas_teto_movimentacoes
    WHERE caixinha_id = p_caixinha_id
      AND tipo = 'deducao'
      AND lancamento_id IS NULL;

    v_total_despesas := v_total_despesas + v_deducoes_avulsas;

    -- Soma todas as injeções/aportes registrados na caixinha
    SELECT COALESCE(SUM(valor), 0)
    INTO v_total_injecoes
    FROM public.caixinhas_teto_movimentacoes
    WHERE caixinha_id = p_caixinha_id
      AND tipo = 'injecao';

    IF v_total_injecoes > 0 THEN
        v_base_provisionada := v_total_injecoes;
    ELSE
        SELECT EXISTS(
            SELECT 1 FROM public.lancamentos
            WHERE caixinha_id = p_caixinha_id
              AND LOWER(COALESCE(TRIM(subtipo), '')) = 'provisionamento'
        ) INTO v_tem_provisao_lanc;

        IF v_tem_provisao_lanc THEN
            SELECT COALESCE(SUM(valor), 0)
            INTO v_base_provisionada
            FROM public.lancamentos
            WHERE caixinha_id = p_caixinha_id
              AND LOWER(COALESCE(TRIM(subtipo), '')) = 'provisionamento'
              AND status = 'Pago';
        ELSE
            v_base_provisionada := 0;
        END IF;
    END IF;

    v_novo_saldo := GREATEST(0, v_base_provisionada - v_total_despesas);

    UPDATE public.caixinhas_teto
    SET saldo_atual = v_novo_saldo,
        atualizado_em = NOW()
    WHERE id = p_caixinha_id;

    RETURN jsonb_build_object(
        'sucesso', true,
        'caixinha_id', p_caixinha_id,
        'valor_meta', v_meta,
        'base_provisionada', v_base_provisionada,
        'total_gasto', v_total_despesas,
        'saldo_atual', v_novo_saldo
    );
END;
$$;

-- 4. Atualiza fn_trg_sincronizar_provisionamento_caixinha para cobrir INSERT, UPDATE (status e valor) e DELETE
CREATE OR REPLACE FUNCTION public.fn_trg_sincronizar_provisionamento_caixinha()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_anterior NUMERIC;
BEGIN
    -- CASO 1: Lançamento de provisionamento foi pago (Pendente -> Pago, ou criado direto como Pago)
    IF (TG_OP = 'INSERT' AND NEW.status = 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL)
       OR (TG_OP = 'UPDATE' AND (OLD.status IS NULL OR OLD.status <> 'Pago') AND NEW.status = 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL) THEN

        IF NOT EXISTS (
            SELECT 1 FROM public.caixinhas_teto_movimentacoes
            WHERE lancamento_id = NEW.id AND tipo = 'injecao'
        ) THEN
            SELECT COALESCE(saldo_atual, 0) INTO v_anterior
            FROM public.caixinhas_teto WHERE id = NEW.caixinha_id;

            INSERT INTO public.caixinhas_teto_movimentacoes (
                caixinha_id, user_id, tipo, valor, saldo_anterior, saldo_posterior, descricao, data, lancamento_id
            ) VALUES (
                NEW.caixinha_id, NEW.user_id, 'injecao', NEW.valor, v_anterior, v_anterior + NEW.valor,
                COALESCE(NEW.descricao, 'Aporte / Provisão na Caixinha'), NEW.data, NEW.id
            );
        ELSE
            UPDATE public.caixinhas_teto_movimentacoes
            SET valor = NEW.valor,
                data = NEW.data,
                descricao = COALESCE(NEW.descricao, descricao)
            WHERE lancamento_id = NEW.id AND tipo = 'injecao';
        END IF;

        PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);

    -- CASO 2: Lançamento de provisionamento já estava Pago e teve valor/data alterado
    ELSIF TG_OP = 'UPDATE' AND OLD.status = 'Pago' AND NEW.status = 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM public.caixinhas_teto_movimentacoes
            WHERE lancamento_id = NEW.id AND tipo = 'injecao'
        ) THEN
            UPDATE public.caixinhas_teto_movimentacoes
            SET valor = NEW.valor,
                data = NEW.data,
                descricao = COALESCE(NEW.descricao, descricao)
            WHERE lancamento_id = NEW.id AND tipo = 'injecao';
        ELSE
            SELECT COALESCE(saldo_atual, 0) INTO v_anterior
            FROM public.caixinhas_teto WHERE id = NEW.caixinha_id;

            INSERT INTO public.caixinhas_teto_movimentacoes (
                caixinha_id, user_id, tipo, valor, saldo_anterior, saldo_posterior, descricao, data, lancamento_id
            ) VALUES (
                NEW.caixinha_id, NEW.user_id, 'injecao', NEW.valor, v_anterior, v_anterior + NEW.valor,
                COALESCE(NEW.descricao, 'Aporte / Provisão na Caixinha'), NEW.data, NEW.id
            );
        END IF;

        PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);

    -- CASO 3: Lançamento de provisionamento voltou para Pendente (estornado)
    ELSIF TG_OP = 'UPDATE' AND OLD.status = 'Pago' AND NEW.status <> 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL THEN
        DELETE FROM public.caixinhas_teto_movimentacoes
        WHERE lancamento_id = NEW.id;

        PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);

    -- CASO 4: Lançamento de provisionamento foi excluído
    ELSIF TG_OP = 'DELETE' AND OLD.caixinha_id IS NOT NULL AND LOWER(COALESCE(TRIM(OLD.subtipo), '')) = 'provisionamento' THEN
        DELETE FROM public.caixinhas_teto_movimentacoes
        WHERE lancamento_id = OLD.id;

        PERFORM public.fn_recalcular_saldo_caixinha(OLD.caixinha_id);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

-- 5. Atualiza criar_lancamento_com_recorrencia para suportar caixinha_id e membro_id nativamente
CREATE OR REPLACE FUNCTION public.criar_lancamento_com_recorrencia(p_dados jsonb, p_recorrencia jsonb DEFAULT NULL::jsonb)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id            UUID := auth.uid();
  v_tipo               TEXT := p_dados->>'tipo';
  v_subtipo            TEXT := p_dados->>'subtipo';
  v_forma_movimentacao TEXT := p_dados->>'forma_movimentacao';
  v_valor              NUMERIC := (p_dados->>'valor')::NUMERIC;
  v_data_base          DATE := COALESCE((p_dados->>'data')::DATE, CURRENT_DATE);
  v_hora               SMALLINT := COALESCE((p_dados->>'hora')::SMALLINT, EXTRACT(HOUR FROM NOW())::SMALLINT);
  v_descricao          TEXT := p_dados->>'descricao';
  v_regra              regra_5030 := NULLIF(p_dados->>'regra', '')::regra_5030;
  v_conta_id           UUID := NULLIF(trim(COALESCE(p_dados->>'conta_id', '')), '')::UUID;
  v_cartao_id          UUID := NULLIF(trim(COALESCE(p_dados->>'cartao_id', '')), '')::UUID;
  v_categoria_id       UUID := NULLIF(trim(COALESCE(p_dados->>'categoria_id', '')), '')::UUID;
  v_subcategoria_id    UUID := NULLIF(trim(COALESCE(p_dados->>'subcategoria_id', '')), '')::UUID;
  v_destino_id         UUID := NULLIF(trim(COALESCE(p_dados->>'destino_id', '')), '')::UUID;
  v_pote_id            UUID := NULLIF(trim(COALESCE(p_dados->>'pote_id', '')), '')::UUID;
  v_caixinha_id        UUID := NULLIF(trim(COALESCE(p_dados->>'caixinha_id', '')), '')::UUID;
  v_membro_id          UUID := NULLIF(trim(COALESCE(p_dados->>'membro_id', '')), '')::UUID;
  v_status_explicito   status_lanc := NULLIF(p_dados->>'status', '')::status_lanc;

  v_tipo_rec           TEXT := COALESCE(p_recorrencia->>'tipo_recorrencia', 'unica');
  v_total_parcelas     SMALLINT := COALESCE((p_recorrencia->>'total_parcelas')::SMALLINT, 1);
  v_frequencia         TEXT := COALESCE(p_recorrencia->>'frequencia', 'mensal');

  v_serie_id           UUID := gen_random_uuid();
  v_recorrente_id      UUID := NULL;
  v_lancamento_id      UUID := NULL;
  v_fatura_id          UUID := NULL;
  v_data_parcela       DATE;
  v_valor_parcela      NUMERIC;
  v_status_inicial     status_lanc;
  v_criados            INT := 0;
  i                    INT;
BEGIN
  -- Se for Consumo de Caixinha (Etapa B), garante neutralidade bancária imediata
  IF v_caixinha_id IS NOT NULL AND LOWER(COALESCE(TRIM(v_subtipo), '')) <> 'provisionamento' THEN
    v_conta_id := NULL;
    v_cartao_id := NULL;
    v_subtipo := 'Consumo Caixinha';
    v_forma_movimentacao := 'Caixinha';
    v_status_explicito := 'Pago'::status_lanc;
  END IF;

  IF v_status_explicito IS NOT NULL THEN
    v_status_inicial := v_status_explicito;
  ELSIF v_forma_movimentacao = 'Crédito' OR v_data_base > CURRENT_DATE THEN
    v_status_inicial := 'Pendente';
  ELSE
    v_status_inicial := 'Pago';
  END IF;

  -- CASO 1: Transação ÚNICA
  IF v_tipo_rec = 'unica' THEN
    IF v_forma_movimentacao = 'Crédito' AND v_cartao_id IS NOT NULL THEN
      v_fatura_id := obter_ou_criar_fatura(v_cartao_id, v_data_base, v_user_id);
    END IF;

    INSERT INTO public.lancamentos (
      user_id, perfil_id, tipo, subtipo, forma_movimentacao,
      conta_id, cartao_id, fatura_id, categoria_id, subcategoria_id,
      destino_id, pote_id, caixinha_id, membro_id, valor, data, hora, descricao,
      regra, status, tipo_recorrencia, fonte_importacao
    ) VALUES (
      v_user_id, v_user_id, v_tipo, v_subtipo, v_forma_movimentacao,
      v_conta_id, v_cartao_id, v_fatura_id, v_categoria_id, v_subcategoria_id,
      v_destino_id, v_pote_id, v_caixinha_id, v_membro_id, v_valor, v_data_base, v_hora, v_descricao,
      v_regra, v_status_inicial, 'unica', 'manual'
    )
    RETURNING id INTO v_lancamento_id;

    v_criados := 1;

  -- CASO 2: PARCELADA
  ELSIF v_tipo_rec = 'parcelada' THEN
    v_valor_parcela := ROUND(v_valor / v_total_parcelas, 2);

    FOR i IN 1..v_total_parcelas LOOP
      v_data_parcela := CASE v_frequencia
        WHEN 'semanal'    THEN v_data_base + ((i - 1) * 7 || ' days')::INTERVAL
        WHEN 'quinzenal'  THEN v_data_base + ((i - 1) * 15 || ' days')::INTERVAL
        WHEN 'bimestral'  THEN v_data_base + ((i - 1) * 2 || ' months')::INTERVAL
        WHEN 'trimestral' THEN v_data_base + ((i - 1) * 3 || ' months')::INTERVAL
        WHEN 'semestral'  THEN v_data_base + ((i - 1) * 6 || ' months')::INTERVAL
        WHEN 'anual'      THEN v_data_base + ((i - 1) || ' years')::INTERVAL
        ELSE                   v_data_base + ((i - 1) || ' months')::INTERVAL
      END;

      v_fatura_id := NULL;
      IF v_forma_movimentacao = 'Crédito' AND v_cartao_id IS NOT NULL THEN
        v_fatura_id := obter_ou_criar_fatura(v_cartao_id, v_data_parcela, v_user_id);
      END IF;

      INSERT INTO public.lancamentos (
        user_id, perfil_id, tipo, subtipo, forma_movimentacao,
        conta_id, cartao_id, fatura_id, categoria_id, subcategoria_id,
        destino_id, pote_id, caixinha_id, membro_id, valor, data, hora,
        descricao, regra, status,
        tipo_recorrencia, serie_id, parcela_atual, total_parcelas, fonte_importacao
      ) VALUES (
        v_user_id, v_user_id, v_tipo, v_subtipo, v_forma_movimentacao,
        v_conta_id, v_cartao_id, v_fatura_id, v_categoria_id, v_subcategoria_id,
        v_destino_id, v_pote_id, v_caixinha_id, v_membro_id,
        CASE WHEN i = v_total_parcelas
          THEN v_valor - (v_valor_parcela * (v_total_parcelas - 1))
          ELSE v_valor_parcela
        END,
        v_data_parcela, v_hora,
        v_descricao || ' (' || i || '/' || v_total_parcelas || ')',
        v_regra,
        CASE WHEN i = 1 THEN v_status_inicial ELSE 'Pendente'::status_lanc END,
        'parcelada', v_serie_id, i, v_total_parcelas, 'manual'
      )
      RETURNING id INTO v_lancamento_id;

      v_criados := v_criados + 1;
    END LOOP;

  -- CASO 3: REPETIDA
  ELSIF v_tipo_rec = 'repetida' THEN
    FOR i IN 1..v_total_parcelas LOOP
      v_data_parcela := CASE v_frequencia
        WHEN 'semanal'    THEN v_data_base + ((i - 1) * 7 || ' days')::INTERVAL
        WHEN 'quinzenal'  THEN v_data_base + ((i - 1) * 15 || ' days')::INTERVAL
        WHEN 'bimestral'  THEN v_data_base + ((i - 1) * 2 || ' months')::INTERVAL
        WHEN 'trimestral' THEN v_data_base + ((i - 1) * 3 || ' months')::INTERVAL
        WHEN 'semestral'  THEN v_data_base + ((i - 1) * 6 || ' months')::INTERVAL
        WHEN 'anual'      THEN v_data_base + ((i - 1) || ' years')::INTERVAL
        ELSE                   v_data_base + ((i - 1) || ' months')::INTERVAL
      END;

      v_fatura_id := NULL;
      IF v_forma_movimentacao = 'Crédito' AND v_cartao_id IS NOT NULL THEN
        v_fatura_id := obter_ou_criar_fatura(v_cartao_id, v_data_parcela, v_user_id);
      END IF;

      INSERT INTO public.lancamentos (
        user_id, perfil_id, tipo, subtipo, forma_movimentacao,
        conta_id, cartao_id, fatura_id, categoria_id, subcategoria_id,
        destino_id, pote_id, caixinha_id, membro_id, valor, data, hora, descricao, regra,
        status, tipo_recorrencia, serie_id, parcela_atual, total_parcelas, fonte_importacao
      ) VALUES (
        v_user_id, v_user_id, v_tipo, v_subtipo, v_forma_movimentacao,
        v_conta_id, v_cartao_id, v_fatura_id, v_categoria_id, v_subcategoria_id,
        v_destino_id, v_pote_id, v_caixinha_id, v_membro_id, v_valor, v_data_parcela, v_hora, v_descricao, v_regra,
        CASE WHEN i = 1 THEN v_status_inicial ELSE 'Pendente'::status_lanc END,
        'repetida', v_serie_id, i, v_total_parcelas, 'manual'
      )
      RETURNING id INTO v_lancamento_id;

      v_criados := v_criados + 1;
    END LOOP;

  -- CASO 4: FIXA
  ELSIF v_tipo_rec = 'fixa' THEN
    INSERT INTO public.transacoes_recorrentes (
      user_id, tipo, subtipo, forma_movimentacao,
      conta_id, cartao_id, categoria_id, subcategoria_id, destino_id,
      valor, descricao, regra, frequencia,
      dia_vencimento, data_inicio, proxima_ocorrencia, ativo
    ) VALUES (
      v_user_id, v_tipo, v_subtipo, v_forma_movimentacao,
      v_conta_id, v_cartao_id, v_categoria_id, v_subcategoria_id, v_destino_id,
      v_valor, v_descricao, v_regra, v_frequencia,
      EXTRACT(DAY FROM v_data_base)::SMALLINT,
      v_data_base,
      v_data_base + INTERVAL '1 year',
      TRUE
    )
    RETURNING id INTO v_recorrente_id;

    FOR i IN 1..12 LOOP
      v_data_parcela := CASE v_frequencia
        WHEN 'semanal'    THEN v_data_base + ((i - 1) * 7 || ' days')::INTERVAL
        WHEN 'quinzenal'  THEN v_data_base + ((i - 1) * 15 || ' days')::INTERVAL
        WHEN 'bimestral'  THEN v_data_base + ((i - 1) * 2 || ' months')::INTERVAL
        WHEN 'trimestral' THEN v_data_base + ((i - 1) * 3 || ' months')::INTERVAL
        WHEN 'semestral'  THEN v_data_base + ((i - 1) * 6 || ' months')::INTERVAL
        WHEN 'anual'      THEN v_data_base + ((i - 1) || ' years')::INTERVAL
        ELSE                   v_data_base + ((i - 1) || ' months')::INTERVAL
      END;

      v_fatura_id := NULL;
      IF v_forma_movimentacao = 'Crédito' AND v_cartao_id IS NOT NULL THEN
        v_fatura_id := obter_ou_criar_fatura(v_cartao_id, v_data_parcela, v_user_id);
      END IF;

      INSERT INTO public.lancamentos (
        user_id, perfil_id, tipo, subtipo, forma_movimentacao,
        conta_id, cartao_id, fatura_id, categoria_id, subcategoria_id,
        destino_id, pote_id, caixinha_id, membro_id, valor, data, hora, descricao, regra,
        status, tipo_recorrencia, serie_id, recorrente_id,
        parcela_atual, total_parcelas, fonte_importacao
      ) VALUES (
        v_user_id, v_user_id, v_tipo, v_subtipo, v_forma_movimentacao,
        v_conta_id, v_cartao_id, v_fatura_id, v_categoria_id, v_subcategoria_id,
        v_destino_id, v_pote_id, v_caixinha_id, v_membro_id, v_valor, v_data_parcela, v_hora, v_descricao, v_regra,
        CASE WHEN i = 1 THEN v_status_inicial ELSE 'Pendente'::status_lanc END,
        'fixa', v_serie_id, v_recorrente_id,
        i, 12, 'manual'
      )
      RETURNING id INTO v_lancamento_id;

      v_criados := v_criados + 1;
    END LOOP;
  END IF;

  RETURN JSON_BUILD_OBJECT(
    'sucesso',        TRUE,
    'id',             v_lancamento_id,
    'criados',        v_criados,
    'serie_id',       v_serie_id,
    'recorrente_id',  v_recorrente_id,
    'caixinha_id',    v_caixinha_id
  );
END;
$$;

-- 6. Atualiza fn_recalcular_saldos_usuario para garantir que Consumo de Caixinha nunca desconte do Banco
CREATE OR REPLACE FUNCTION public.fn_recalcular_saldos_usuario(p_user_id UUID DEFAULT NULL::UUID)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_uid UUID := COALESCE(p_user_id, auth.uid());
BEGIN
    IF v_uid IS NULL THEN
        RETURN;
    END IF;

    -- 1. CONTAS BANCÁRIAS
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
            ), 0),
        atualizado_em = NOW()
    WHERE c.user_id = v_uid;

    -- 2. FATURAS DE CARTÃO
    UPDATE public.faturas f
    SET
        valor_total = COALESCE((
            SELECT SUM(l.valor) FROM public.lancamentos l
            WHERE l.fatura_id = f.id AND l.tipo = 'Despesa'
        ), 0),
        valor_pago = COALESCE((
            SELECT SUM(l.valor) FROM public.lancamentos l
            WHERE l.fatura_id = f.id AND l.tipo = 'Despesa' AND l.status = 'Pago'
        ), 0),
        status = CASE
            WHEN COALESCE((SELECT SUM(l.valor) FROM public.lancamentos l WHERE l.fatura_id = f.id AND l.tipo = 'Despesa'), 0) > 0
             AND COALESCE((SELECT SUM(l.valor) FROM public.lancamentos l WHERE l.fatura_id = f.id AND l.tipo = 'Despesa' AND l.status <> 'Pago'), 0) = 0
            THEN 'paga'::status_fatura
            WHEN f.status = 'paga'::status_fatura
             AND COALESCE((SELECT SUM(l.valor) FROM public.lancamentos l WHERE l.fatura_id = f.id AND l.tipo = 'Despesa' AND l.status <> 'Pago'), 0) > 0
            THEN 'aberta'::status_fatura
            ELSE f.status
        END,
        atualizado_em = NOW()
    FROM public.cartoes ct
    WHERE f.cartao_id = ct.id AND ct.user_id = v_uid;

    -- 3. CARTÕES DE CRÉDITO
    UPDATE public.cartoes ct
    SET
        limite_disponivel = COALESCE(ct.limite_total, 0) - COALESCE((
            SELECT SUM(l.valor) FROM public.lancamentos l
            WHERE l.cartao_id = ct.id AND l.tipo = 'Despesa' AND l.status = 'Pendente'
        ), 0),
        atualizado_em = NOW()
    WHERE ct.user_id = v_uid;
END;
$$;

-- 7. Atualiza get_potes_resumo (remove sobrecarga ambígua de 2 parâmetros e aplica regra sem dupla contagem)
DROP FUNCTION IF EXISTS public.get_potes_resumo(DATE, DATE);

CREATE OR REPLACE FUNCTION public.get_potes_resumo(
    p_data_inicio DATE,
    p_data_fim DATE,
    p_piso_fixos NUMERIC DEFAULT 1150.00
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_uid          UUID := auth.uid();
    v_renda        NUMERIC(12,2) := 0;
    v_gasto_total  NUMERIC(12,2) := 0;
    v_potes        JSON;
    v_sem          JSON;
    v_mes_ref      SMALLINT := EXTRACT(MONTH FROM COALESCE(p_data_fim, CURRENT_DATE))::SMALLINT;
    v_ano_ref      SMALLINT := EXTRACT(YEAR  FROM COALESCE(p_data_fim, CURRENT_DATE))::SMALLINT;
    v_pct_inv      NUMERIC := 50.0;
    v_piso         NUMERIC(12,2) := COALESCE(p_piso_fixos, 1150.00);

    v_p1_id UUID; v_p1_gasto NUMERIC(12,2) := 0; v_p1_prev NUMERIC(12,2) := 0;
    v_p2_id UUID; v_p2_gasto NUMERIC(12,2) := 0; v_p2_prev NUMERIC(12,2) := 0; v_p2_pct_cfg NUMERIC := 15; v_p2_lib BOOLEAN := FALSE; v_p2_lib_val NUMERIC(12,2) := 0;
    v_p3_id UUID; v_p3_gasto NUMERIC(12,2) := 0; v_p3_prev NUMERIC(12,2) := 0; v_p3_pct_cfg NUMERIC := 15; v_p3_lib BOOLEAN := FALSE; v_p3_lib_val NUMERIC(12,2) := 0;
    v_p4_id UUID; v_p4_gasto NUMERIC(12,2) := 0; v_p4_prev NUMERIC(12,2) := 0;
    v_p5_id UUID; v_p5_gasto NUMERIC(12,2) := 0; v_p5_prev NUMERIC(12,2) := 0; v_p5_pct_cfg NUMERIC := 5;  v_p5_lib BOOLEAN := FALSE; v_p5_lib_val NUMERIC(12,2) := 0;
    v_p6_id UUID; v_p6_gasto NUMERIC(12,2) := 0; v_p6_prev NUMERIC(12,2) := 0;

    v_sobra_caixa_livre NUMERIC(12,2) := 0;
    v_sobra_liberada_total NUMERIC(12,2) := 0;
BEGIN
    PERFORM public.garantir_potes_padrao(v_uid);

    SELECT COALESCE(cl.pct_investimento, 50.0),
           COALESCE(cl.piso_custos_fixos, COALESCE(p_piso_fixos, 1150.00)),
           COALESCE(cl.liberar_pote_2, FALSE),
           COALESCE(cl.liberar_pote_3, FALSE),
           COALESCE(cl.liberar_pote_5, FALSE)
    INTO v_pct_inv, v_piso, v_p2_lib, v_p3_lib, v_p5_lib
    FROM public.caixa_livre_config cl
    WHERE cl.user_id = v_uid AND cl.mes = v_mes_ref AND cl.ano = v_ano_ref
    LIMIT 1;

    v_pct_inv := LEAST(100.0, GREATEST(0.0, COALESCE(v_pct_inv, 50.0)));
    v_piso    := GREATEST(0.0, COALESCE(v_piso, 1150.00));

    -- Receita do período (inclui Receitas Pagas e Pendentes para previsão de orçamento do ciclo)
    SELECT COALESCE(SUM(valor), 0) INTO v_renda
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Receita'
      AND data BETWEEN p_data_inicio AND p_data_fim;

    -- Gasto Real Total do período (inclui Provisionamento Pago de Caixinha; exclui Consumo de Caixinha)
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_total
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Despesa'
      AND data BETWEEN p_data_inicio AND p_data_fim
      AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    SELECT id INTO v_p1_id FROM public.potes WHERE user_id = v_uid AND posicao = 1 LIMIT 1;
    SELECT id, COALESCE((SELECT pm.percentual FROM public.potes_mensais pm WHERE pm.pote_id = potes.id AND pm.mes = v_mes_ref AND pm.ano = v_ano_ref LIMIT 1), percentual)
      INTO v_p2_id, v_p2_pct_cfg FROM public.potes WHERE user_id = v_uid AND posicao = 2 LIMIT 1;
    SELECT id, COALESCE((SELECT pm.percentual FROM public.potes_mensais pm WHERE pm.pote_id = potes.id AND pm.mes = v_mes_ref AND pm.ano = v_ano_ref LIMIT 1), percentual)
      INTO v_p3_id, v_p3_pct_cfg FROM public.potes WHERE user_id = v_uid AND posicao = 3 LIMIT 1;
    SELECT id INTO v_p4_id FROM public.potes WHERE user_id = v_uid AND posicao = 4 LIMIT 1;
    SELECT id, COALESCE((SELECT pm.percentual FROM public.potes_mensais pm WHERE pm.pote_id = potes.id AND pm.mes = v_mes_ref AND pm.ano = v_ano_ref LIMIT 1), percentual)
      INTO v_p5_id, v_p5_pct_cfg FROM public.potes WHERE user_id = v_uid AND posicao = 5 LIMIT 1;
    SELECT id INTO v_p6_id FROM public.potes WHERE user_id = v_uid AND posicao = 6 LIMIT 1;

    -- Gastos reais de cada pote (Etapa A conta no pote; Etapa B é neutra)
    SELECT COALESCE(SUM(valor), 0) INTO v_p1_gasto FROM public.lancamentos
      WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
        AND tipo = 'Despesa' AND pote_id = v_p1_id AND data BETWEEN p_data_inicio AND p_data_fim
        AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    SELECT COALESCE(SUM(valor), 0) INTO v_p2_gasto FROM public.lancamentos
      WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
        AND tipo = 'Despesa' AND pote_id = v_p2_id AND data BETWEEN p_data_inicio AND p_data_fim
        AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    SELECT COALESCE(SUM(valor), 0) INTO v_p3_gasto FROM public.lancamentos
      WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
        AND tipo = 'Despesa' AND pote_id = v_p3_id AND data BETWEEN p_data_inicio AND p_data_fim
        AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    SELECT COALESCE(SUM(valor), 0) INTO v_p4_gasto FROM public.lancamentos
      WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
        AND tipo = 'Despesa' AND pote_id = v_p4_id AND data BETWEEN p_data_inicio AND p_data_fim
        AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    SELECT COALESCE(SUM(valor), 0) INTO v_p5_gasto FROM public.lancamentos
      WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
        AND tipo = 'Despesa' AND pote_id = v_p5_id AND data BETWEEN p_data_inicio AND p_data_fim
        AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    SELECT COALESCE(SUM(valor), 0) INTO v_p6_gasto FROM public.lancamentos
      WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
        AND tipo = 'Despesa' AND pote_id = v_p6_id AND data BETWEEN p_data_inicio AND p_data_fim
        AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    IF v_renda > 0 THEN
        v_p1_prev := LEAST(v_renda, GREATEST(v_p1_gasto, v_piso));
        v_p2_prev := ROUND(v_renda * (COALESCE(v_p2_pct_cfg, 15) / 100.0), 2);
        v_p3_prev := ROUND(v_renda * (COALESCE(v_p3_pct_cfg, 15) / 100.0), 2);
        v_p5_prev := ROUND(v_renda * (COALESCE(v_p5_pct_cfg, 5)  / 100.0), 2);

        IF v_p2_lib AND v_p2_prev > v_p2_gasto THEN
            v_p2_lib_val := ROUND(v_p2_prev - v_p2_gasto, 2);
            v_p2_prev    := v_p2_gasto;
        END IF;

        IF v_p3_lib AND v_p3_prev > v_p3_gasto THEN
            v_p3_lib_val := ROUND(v_p3_prev - v_p3_gasto, 2);
            v_p3_prev    := v_p3_gasto;
        END IF;

        IF v_p5_lib AND v_p5_prev > v_p5_gasto THEN
            v_p5_lib_val := ROUND(v_p5_prev - v_p5_gasto, 2);
            v_p5_prev    := v_p5_gasto;
        END IF;

        v_sobra_liberada_total := v_p2_lib_val + v_p3_lib_val + v_p5_lib_val;
        v_sobra_caixa_livre    := GREATEST(0, v_renda - v_p1_prev - v_p2_prev - v_p3_prev - v_p5_prev);
        v_p6_prev := ROUND(v_sobra_caixa_livre * (v_pct_inv / 100.0), 2);
        v_p4_prev := GREATEST(0, v_sobra_caixa_livre - v_p6_prev);
    END IF;

    SELECT json_agg(row_data ORDER BY row_data.posicao) INTO v_potes
    FROM (
        SELECT
            p.id,
            p.posicao,
            p.nome,
            p.cor,
            p.icone,
            CASE p.posicao
                WHEN 1 THEN CASE WHEN v_renda > 0 THEN ROUND((v_p1_prev / v_renda) * 100, 2) ELSE p.percentual END
                WHEN 2 THEN CASE WHEN v_p2_lib AND v_renda > 0 THEN ROUND((v_p2_prev / v_renda) * 100, 2) ELSE COALESCE(v_p2_pct_cfg, p.percentual) END
                WHEN 3 THEN CASE WHEN v_p3_lib AND v_renda > 0 THEN ROUND((v_p3_prev / v_renda) * 100, 2) ELSE COALESCE(v_p3_pct_cfg, p.percentual) END
                WHEN 4 THEN CASE WHEN v_renda > 0 THEN ROUND((v_p4_prev / v_renda) * 100, 2) ELSE p.percentual END
                WHEN 5 THEN CASE WHEN v_p5_lib AND v_renda > 0 THEN ROUND((v_p5_prev / v_renda) * 100, 2) ELSE COALESCE(v_p5_pct_cfg, p.percentual) END
                WHEN 6 THEN CASE WHEN v_renda > 0 THEN ROUND((v_p6_prev / v_renda) * 100, 2) ELSE p.percentual END
                ELSE p.percentual
            END AS percentual,
            CASE p.posicao
                WHEN 1 THEN v_p1_prev
                WHEN 2 THEN v_p2_prev
                WHEN 3 THEN v_p3_prev
                WHEN 4 THEN v_p4_prev
                WHEN 5 THEN v_p5_prev
                WHEN 6 THEN v_p6_prev
                ELSE 0
            END AS previsto,
            CASE p.posicao
                WHEN 1 THEN v_p1_gasto
                WHEN 2 THEN v_p2_gasto
                WHEN 3 THEN v_p3_gasto
                WHEN 4 THEN v_p4_gasto
                WHEN 5 THEN v_p5_gasto
                WHEN 6 THEN v_p6_gasto
                ELSE 0
            END AS gasto,
            (
                SELECT COUNT(*)::int
                FROM public.lancamentos l
                WHERE (l.user_id = v_uid OR l.perfil_id = v_uid) AND public.fn_membro_visivel(l.membro_id)
                  AND l.pote_id = p.id
                  AND l.tipo = 'Despesa'
                  AND l.data BETWEEN p_data_inicio AND p_data_fim
                  AND public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text)
            ) AS qtd_transacoes,
            CASE p.posicao
                WHEN 1 THEN 'automatico_fixo'
                WHEN 2 THEN 'retido_intocavel'
                WHEN 3 THEN 'retido_intocavel'
                WHEN 4 THEN 'caixa_livre_prazeres'
                WHEN 5 THEN 'retido_intocavel'
                WHEN 6 THEN 'caixa_livre_investimento'
            END AS tipo_comportamento,
            CASE p.posicao
                WHEN 1 THEN v_piso
                ELSE 0
            END AS piso_configurado,
            CASE p.posicao
                WHEN 2 THEN v_p2_lib
                WHEN 3 THEN v_p3_lib
                WHEN 5 THEN v_p5_lib
                ELSE FALSE
            END AS liberado,
            CASE p.posicao
                WHEN 2 THEN v_p2_lib_val
                WHEN 3 THEN v_p3_lib_val
                WHEN 5 THEN v_p5_lib_val
                ELSE 0
            END AS liberado_valor,
            CASE p.posicao
                WHEN 2 THEN COALESCE(v_p2_pct_cfg, p.percentual)
                WHEN 3 THEN COALESCE(v_p3_pct_cfg, p.percentual)
                WHEN 5 THEN COALESCE(v_p5_pct_cfg, p.percentual)
                ELSE p.percentual
            END AS percentual_original
        FROM public.potes p
        WHERE p.user_id = v_uid
    ) row_data;

    SELECT json_build_object(
        'qtd',   COUNT(*)::int,
        'total', COALESCE(SUM(valor), 0)::numeric(12,2)
    ) INTO v_sem
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Despesa'
      AND pote_id IS NULL
      AND data BETWEEN p_data_inicio AND p_data_fim
      AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text);

    RETURN json_build_object(
        'renda',                  v_renda,
        'total_gasto',            v_gasto_total,
        'saldo',                  v_renda - v_gasto_total,
        'percentual_renda_usado', CASE WHEN v_renda > 0
                                       THEN ROUND((v_gasto_total / v_renda) * 100, 1)
                                       ELSE 0 END,
        'mes_referencia',         v_mes_ref,
        'ano_referencia',         v_ano_ref,
        'pct_investimento',       v_pct_inv,
        'piso_custos_fixos',      v_piso,
        'sobra_caixa_livre',      v_sobra_caixa_livre,
        'sobra_liberada_total',   v_sobra_liberada_total,
        'liberar_pote_2',         v_p2_lib,
        'liberar_pote_3',         v_p3_lib,
        'liberar_pote_5',         v_p5_lib,
        'potes',                  COALESCE(v_potes, '[]'::json),
        'sem_pote',               v_sem
    );
END;
$$;

-- 8. Atualiza get_lista_contas_resumo e get_relatorio_conta para neutralidade bancária
CREATE OR REPLACE FUNCTION public.get_lista_contas_resumo(p_data_inicio date DEFAULT NULL::date, p_data_fim date DEFAULT NULL::date)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id    UUID := auth.uid();
    v_inicio     DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
    v_fim        DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
    v_contas     JSONB;
    v_tot_atual  NUMERIC := 0;
    v_tot_prev   NUMERIC := 0;
    v_tot_ent    NUMERIC := 0;
    v_tot_sai    NUMERIC := 0;
BEGIN
    SELECT
        COALESCE(SUM(c.saldo_atual), 0),
        COALESCE(SUM(c.saldo_previsto), 0)
    INTO v_tot_atual, v_tot_prev
    FROM public.contas c
    WHERE c.user_id = v_user_id AND public.fn_membro_visivel(c.membro_id) AND c.ativo = TRUE;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.nome), '[]'::jsonb) INTO v_contas
    FROM (
        SELECT
            c.id,
            c.nome,
            c.tipo_conta,
            c.banco,
            c.cor,
            c.icone,
            COALESCE(c.saldo_inicial, 0) AS saldo_inicial,
            COALESCE(c.saldo_atual, COALESCE(c.saldo_inicial, 0)) AS saldo_atual,
            COALESCE(c.saldo_previsto, COALESCE(c.saldo_inicial, 0)) AS saldo_previsto,
            COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
                  AND l.data BETWEEN v_inicio AND v_fim
                  AND (
                      (l.conta_id = c.id AND l.tipo = 'Receita')
                      OR (l.destino_id = c.id AND l.tipo = 'Transferência')
                  )
            ), 0) AS entradas_periodo,
            COALESCE((
                SELECT SUM(l.valor)
                FROM public.lancamentos l
                WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
                  AND l.data BETWEEN v_inicio AND v_fim
                  AND l.conta_id = c.id
                  AND l.tipo IN ('Despesa', 'Transferência')
                  AND NOT public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo)
            ), 0) AS saidas_periodo,
            COALESCE((
                SELECT COUNT(*)::INT
                FROM public.lancamentos l
                WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
                  AND l.data BETWEEN v_inicio AND v_fim
                  AND (l.conta_id = c.id OR l.destino_id = c.id)
                  AND NOT public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo)
            ), 0) AS qtd_lancamentos_periodo
        FROM public.contas c
        WHERE c.user_id = v_user_id AND public.fn_membro_visivel(c.membro_id) AND c.ativo = TRUE
    ) row;

    SELECT
        COALESCE(SUM((elem->>'entradas_periodo')::numeric), 0),
        COALESCE(SUM((elem->>'saidas_periodo')::numeric), 0)
    INTO v_tot_ent, v_tot_sai
    FROM JSONB_ARRAY_ELEMENTS(v_contas) elem;

    RETURN JSONB_BUILD_OBJECT(
        'saldo_total_atual', v_tot_atual,
        'saldo_total_previsto', v_tot_prev,
        'entradas_periodo_total', v_tot_ent,
        'saidas_periodo_total', v_tot_sai,
        'contas', v_contas
    );
END;
$$;

-- 9. Atualiza get_dashboard_periodo, get_dashboard_overview, get_financial_totals,
--    get_regra_50_30_20_summary, get_despesas_por_categoria, get_balanco_ultimos_6_meses
CREATE OR REPLACE FUNCTION public.get_dashboard_periodo(p_data_inicio date, p_data_fim date)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  v_user_id        UUID := auth.uid();
  v_inicio         DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
  v_fim            DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
  v_receitas       NUMERIC;
  v_despesas       NUMERIC;
  v_receitas_pagas NUMERIC;
  v_despesas_pagas NUMERIC;
  v_saldo_contas   NUMERIC;
  v_total_faturas  NUMERIC;
  v_desp_cat       JSON;
  v_rec_cat        JSON;
  v_freq           JSON;
  v_formas         JSON;
  v_mes_ref        SMALLINT := EXTRACT(MONTH FROM v_fim)::SMALLINT;
  v_ano_ref        SMALLINT := EXTRACT(YEAR  FROM v_fim)::SMALLINT;
BEGIN
  SELECT
    COALESCE(SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN tipo = 'Despesa' AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text) THEN valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN tipo = 'Receita' AND status = 'Pago' THEN valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN tipo = 'Despesa' AND status = 'Pago' AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text) THEN valor ELSE 0 END), 0)
  INTO v_receitas, v_despesas, v_receitas_pagas, v_despesas_pagas
  FROM public.lancamentos
  WHERE (user_id = v_user_id OR perfil_id = v_user_id) AND public.fn_membro_visivel(membro_id)
    AND data BETWEEN v_inicio AND v_fim;

  SELECT COALESCE(SUM(saldo_atual), 0) INTO v_saldo_contas
  FROM public.contas
  WHERE user_id = v_user_id AND public.fn_membro_visivel(membro_id) AND ativo = TRUE;

  SELECT COALESCE(SUM(valor_total - valor_pago), 0) INTO v_total_faturas
  FROM public.faturas f
  JOIN public.cartoes c ON c.id = f.cartao_id
  WHERE c.user_id = v_user_id AND public.fn_membro_visivel(c.membro_id)
    AND f.status IN ('aberta','fechada','vencida')
    AND f.mes = v_mes_ref
    AND f.ano = v_ano_ref;

  SELECT JSON_AGG(row ORDER BY row.valor DESC) INTO v_desp_cat
  FROM (
    SELECT
      c.id                               AS categoria_id,
      COALESCE(c.nome, 'Sem Categoria')  AS categoria,
      COALESCE(c.nome, 'Sem Categoria')  AS nome,
      COALESCE(c.cor, '#94A3B8')         AS cor,
      COALESCE(c.icone, 'category')      AS icone,
      SUM(l.valor)                       AS valor,
      SUM(l.valor)                       AS total,
      COUNT(*)::INT                      AS qtd,
      ROUND(SUM(l.valor) / NULLIF(v_despesas, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
      AND l.tipo = 'Despesa'
      AND l.data BETWEEN v_inicio AND v_fim
      AND public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text)
    GROUP BY c.id, c.nome, c.cor, c.icone
  ) row;

  SELECT JSON_AGG(row ORDER BY row.valor DESC) INTO v_rec_cat
  FROM (
    SELECT
      c.id                               AS categoria_id,
      COALESCE(c.nome, 'Sem Categoria')  AS categoria,
      COALESCE(c.nome, 'Sem Categoria')  AS nome,
      COALESCE(c.cor, '#10B981')         AS cor,
      COALESCE(c.icone, 'category')      AS icone,
      SUM(l.valor)                       AS valor,
      SUM(l.valor)                       AS total,
      COUNT(*)::INT                      AS qtd,
      ROUND(SUM(l.valor) / NULLIF(v_receitas, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
      AND l.tipo = 'Receita'
      AND l.data BETWEEN v_inicio AND v_fim
    GROUP BY c.id, c.nome, c.cor, c.icone
  ) row;

  SELECT JSON_AGG(row ORDER BY row.data) INTO v_freq
  FROM (
    SELECT
      data,
      EXTRACT(DAY FROM data)::INT AS dia,
      TO_CHAR(data, 'DD/MM')      AS label,
      SUM(CASE WHEN tipo = 'Despesa' AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text) THEN valor ELSE 0 END) AS despesas,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) AS receitas
    FROM public.lancamentos
    WHERE (user_id = v_user_id OR perfil_id = v_user_id) AND public.fn_membro_visivel(membro_id)
      AND data BETWEEN v_inicio AND v_fim
    GROUP BY data
  ) row;

  SELECT JSON_AGG(row ORDER BY row.valor DESC) INTO v_formas
  FROM (
    SELECT
      COALESCE(forma_movimentacao, 'Outros') AS forma,
      SUM(valor) AS valor,
      COUNT(*)::INT AS qtd,
      ROUND(SUM(valor) / NULLIF(v_despesas, 0) * 100, 1) AS percentual
    FROM public.lancamentos
    WHERE (user_id = v_user_id OR perfil_id = v_user_id) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Despesa'
      AND data BETWEEN v_inicio AND v_fim
      AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text)
    GROUP BY forma_movimentacao
  ) row;

  RETURN JSON_BUILD_OBJECT(
    'overview', JSON_BUILD_OBJECT(
      'receitas',        v_receitas,
      'despesas',        v_despesas,
      'receitas_pagas',  v_receitas_pagas,
      'despesas_pagas',  v_despesas_pagas,
      'saldo',           v_receitas - v_despesas,
      'saldo_contas',    v_saldo_contas,
      'total_faturas',   v_total_faturas,
      'periodo_inicio',  v_inicio,
      'periodo_fim',     v_fim
    ),
    'despesas_por_categoria', JSON_BUILD_OBJECT('total', v_despesas, 'categorias', COALESCE(v_desp_cat, '[]'::JSON)),
    'receitas_por_categoria', JSON_BUILD_OBJECT('total', v_receitas, 'categorias', COALESCE(v_rec_cat, '[]'::JSON)),
    'frequencia_diaria',      COALESCE(v_freq, '[]'::JSON),
    'despesas_por_forma',     COALESCE(v_formas, '[]'::JSON)
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_dashboard_overview(p_mes smallint DEFAULT NULL::smallint, p_ano smallint DEFAULT NULL::smallint)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_user_id       UUID := auth.uid();
  v_inicio        DATE;
  v_fim           DATE;
  v_receitas      NUMERIC;
  v_despesas      NUMERIC;
  v_saldo_contas  NUMERIC;
  v_total_faturas NUMERIC;
BEGIN
  IF p_mes IS NOT NULL AND p_ano IS NOT NULL THEN
    v_inicio := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
    v_fim    := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  ELSE
    v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_fim    := CURRENT_DATE;
  END IF;

  SELECT COALESCE(SUM(valor), 0) INTO v_receitas
  FROM public.lancamentos
  WHERE user_id = v_user_id AND public.fn_membro_visivel(membro_id)
    AND tipo = 'Receita'
    AND data BETWEEN v_inicio AND v_fim
    AND status = 'Pago';

  SELECT COALESCE(SUM(valor), 0) INTO v_despesas
  FROM public.lancamentos
  WHERE user_id = v_user_id AND public.fn_membro_visivel(membro_id)
    AND tipo = 'Despesa'
    AND data BETWEEN v_inicio AND v_fim
    AND status = 'Pago'
    AND cartao_id IS NULL
    AND NOT public.fn_eh_consumo_caixinha_neutro(caixinha_id, subtipo);

  SELECT COALESCE(SUM(saldo_atual), 0) INTO v_saldo_contas
  FROM public.contas
  WHERE user_id = v_user_id AND public.fn_membro_visivel(membro_id) AND ativo = TRUE;

  SELECT COALESCE(SUM(valor_total - valor_pago), 0) INTO v_total_faturas
  FROM public.faturas f
  JOIN public.cartoes c ON c.id = f.cartao_id
  WHERE c.user_id = v_user_id AND public.fn_membro_visivel(c.membro_id)
    AND f.status IN ('aberta','fechada','vencida')
    AND f.mes = COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE))
    AND f.ano = COALESCE(p_ano, EXTRACT(YEAR FROM CURRENT_DATE));

  RETURN JSON_BUILD_OBJECT(
    'receitas',       v_receitas,
    'despesas',       v_despesas,
    'saldo',          v_receitas - v_despesas,
    'saldo_contas',   v_saldo_contas,
    'total_faturas',  v_total_faturas,
    'periodo_inicio', v_inicio,
    'periodo_fim',    v_fim
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_financial_totals(p_data_inicio date DEFAULT NULL::date, p_data_fim date DEFAULT NULL::date)
RETURNS json
LANGUAGE plpgsql
SET search_path TO 'public'
AS $$
DECLARE
    v_receitas DECIMAL(12,2);
    v_despesas DECIMAL(12,2);
    v_uid UUID;
BEGIN
    v_uid := auth.uid();

    SELECT COALESCE(SUM(valor), 0) INTO v_receitas
    FROM public.lancamentos
    WHERE (perfil_id = v_uid OR user_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Receita'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    SELECT COALESCE(SUM(valor), 0) INTO v_despesas
    FROM public.lancamentos
    WHERE (perfil_id = v_uid OR user_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Despesa'
      AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text)
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    RETURN json_build_object(
        'receitas', v_receitas,
        'despesas', v_despesas,
        'saldo', v_receitas - v_despesas
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_regra_50_30_20_summary(p_data_inicio date DEFAULT NULL::date, p_data_fim date DEFAULT NULL::date)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_receita_total      DECIMAL(12,2);
    v_gasto_essencial    DECIMAL(12,2);
    v_gasto_estilo       DECIMAL(12,2);
    v_gasto_investimento DECIMAL(12,2);
    v_uid                UUID := auth.uid();
BEGIN
    SELECT COALESCE(SUM(valor), 0) INTO v_receita_total
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id) AND tipo = 'Receita'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_essencial
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Despesa' AND regra = 'Essencial'
      AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text)
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_estilo
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Despesa' AND regra = 'Estilo de Vida'
      AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text)
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_investimento
    FROM public.lancamentos
    WHERE (user_id = v_uid OR perfil_id = v_uid) AND public.fn_membro_visivel(membro_id)
      AND tipo = 'Despesa' AND regra = 'Investimento'
      AND public.fn_eh_despesa_orcamento_ativa(caixinha_id, subtipo, status::text)
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);

    RETURN json_build_object(
        'receita_total', v_receita_total,
        'essencial', json_build_object(
            'gasto', v_gasto_essencial,
            'orcamento', v_receita_total * 0.50,
            'percentual_usado', CASE WHEN v_receita_total > 0
                THEN ROUND((v_gasto_essencial / v_receita_total) * 100, 1) ELSE 0 END
        ),
        'estilo_vida', json_build_object(
            'gasto', v_gasto_estilo,
            'orcamento', v_receita_total * 0.30,
            'percentual_usado', CASE WHEN v_receita_total > 0
                THEN ROUND((v_gasto_estilo / v_receita_total) * 100, 1) ELSE 0 END
        ),
        'investimento', json_build_object(
            'gasto', v_gasto_investimento,
            'orcamento', v_receita_total * 0.20,
            'percentual_usado', CASE WHEN v_receita_total > 0
                THEN ROUND((v_gasto_investimento / v_receita_total) * 100, 1) ELSE 0 END
        )
    );
END;
$$;

CREATE OR REPLACE FUNCTION public.get_despesas_por_categoria(p_mes smallint DEFAULT NULL::smallint, p_ano smallint DEFAULT NULL::smallint)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_inicio  DATE;
  v_fim     DATE;
  v_total   NUMERIC;
  v_result  JSON;
BEGIN
  IF p_mes IS NOT NULL AND p_ano IS NOT NULL THEN
    v_inicio := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
    v_fim    := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  ELSE
    v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_fim    := CURRENT_DATE;
  END IF;

  SELECT COALESCE(SUM(valor), 0) INTO v_total
  FROM public.lancamentos
  WHERE user_id = v_user_id AND public.fn_membro_visivel(membro_id) AND tipo = 'Despesa'
    AND data BETWEEN v_inicio AND v_fim AND status = 'Pago'
    AND NOT public.fn_eh_consumo_caixinha_neutro(caixinha_id, subtipo);

  SELECT JSON_AGG(row ORDER BY row.valor DESC)
  INTO v_result
  FROM (
    SELECT
      COALESCE(c.nome, 'Sem Categoria') AS categoria,
      COALESCE(c.cor, '#94A3B8')        AS cor,
      COALESCE(c.icone, 'category')     AS icone,
      SUM(l.valor)                       AS valor,
      ROUND(SUM(l.valor) / NULLIF(v_total, 0) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias c ON c.id = l.categoria_id
    WHERE l.user_id = v_user_id AND public.fn_membro_visivel(l.membro_id) AND l.tipo = 'Despesa'
      AND l.data BETWEEN v_inicio AND v_fim AND l.status = 'Pago'
      AND NOT public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo)
    GROUP BY c.nome, c.cor, c.icone
  ) row;

  RETURN JSON_BUILD_OBJECT('total', v_total, 'categorias', COALESCE(v_result, '[]'::JSON));
END;
$$;

CREATE OR REPLACE FUNCTION public.get_balanco_ultimos_6_meses()
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_user_id UUID := auth.uid();
  v_result  JSON;
BEGIN
  SELECT JSON_AGG(row ORDER BY row.ano, row.mes)
  INTO v_result
  FROM (
    SELECT
      EXTRACT(YEAR  FROM data)::INT AS ano,
      EXTRACT(MONTH FROM data)::INT AS mes,
      TO_CHAR(data, 'Mon/YY')       AS label,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) AS receitas,
      SUM(CASE WHEN tipo = 'Despesa' AND cartao_id IS NULL AND NOT public.fn_eh_consumo_caixinha_neutro(caixinha_id, subtipo) THEN valor ELSE 0 END) AS despesas,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END)
        - SUM(CASE WHEN tipo = 'Despesa' AND cartao_id IS NULL AND NOT public.fn_eh_consumo_caixinha_neutro(caixinha_id, subtipo) THEN valor ELSE 0 END) AS saldo
    FROM public.lancamentos
    WHERE user_id = v_user_id AND public.fn_membro_visivel(membro_id)
      AND status = 'Pago'
      AND data >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '5 months'
    GROUP BY EXTRACT(YEAR FROM data), EXTRACT(MONTH FROM data), TO_CHAR(data, 'Mon/YY')
  ) row;

  RETURN COALESCE(v_result, '[]'::JSON);
END;
$$;

-- 10. Atualiza get_relatorio_lancamentos: preserva caixinha_id, caixinha_nome e flag neutro_caixinha
--     na lista de histórico, mas exclui o consumo neutro dos somatórios de despesas/potes
CREATE OR REPLACE FUNCTION public.get_relatorio_lancamentos(
    p_data_inicio date,
    p_data_fim date,
    p_filtros jsonb DEFAULT '{}'::jsonb,
    p_limite integer DEFAULT 50,
    p_offset integer DEFAULT 0
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id      UUID := COALESCE(NULLIF(p_filtros->>'user_id', '')::uuid, auth.uid());
    v_inicio       DATE := COALESCE(p_data_inicio, DATE_TRUNC('month', CURRENT_DATE)::DATE);
    v_fim          DATE := COALESCE(p_data_fim, (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month' - INTERVAL '1 day')::DATE);
    v_tipo         TEXT := NULLIF(trim(COALESCE(p_filtros->>'tipo', '')), '');
    v_conta_id     UUID := NULLIF(trim(COALESCE(p_filtros->>'conta_id', '')), '')::uuid;
    v_cartao_id    UUID := NULLIF(trim(COALESCE(p_filtros->>'cartao_id', '')), '')::uuid;
    v_categoria_id UUID := NULLIF(trim(COALESCE(p_filtros->>'categoria_id', '')), '')::uuid;
    v_subcat_id    UUID := NULLIF(trim(COALESCE(p_filtros->>'subcategoria_id', '')), '')::uuid;
    v_pote_id      UUID := NULLIF(trim(COALESCE(p_filtros->>'pote_id', '')), '')::uuid;
    v_regra        TEXT := NULLIF(trim(COALESCE(p_filtros->>'regra', '')), '');
    v_status       TEXT := NULLIF(trim(COALESCE(p_filtros->>'status', '')), '');
    v_forma        TEXT := NULLIF(trim(COALESCE(p_filtros->>'forma', '')), '');
    v_busca        TEXT := NULLIF(trim(COALESCE(p_filtros->>'busca', '')), '');
    v_dias_periodo INT;
    v_receitas     NUMERIC := 0;
    v_despesas     NUMERIC := 0;
    v_transf       NUMERIC := 0;
    v_pago         NUMERIC := 0;
    v_pendente     NUMERIC := 0;
    v_qtd          INT := 0;
    v_base_total   NUMERIC := 0;
    v_por_cat      JSONB;
    v_por_subcat   JSONB;
    v_por_pote     JSONB;
    v_por_dia      JSONB;
    v_por_forma    JSONB;
    v_lancamentos  JSONB;
BEGIN
    IF v_fim < v_inicio THEN
        v_fim := v_inicio;
    END IF;
    v_dias_periodo := GREATEST(1, (v_fim - v_inicio) + 1);

    IF v_tipo IS NOT NULL THEN
        IF lower(v_tipo) IN ('todos', 'all') THEN
            v_tipo := NULL;
        ELSIF lower(v_tipo) LIKE 'trans%' THEN
            v_tipo := 'Transferência';
        ELSIF lower(v_tipo) LIKE 'rec%' THEN
            v_tipo := 'Receita';
        ELSIF lower(v_tipo) LIKE 'desp%' THEN
            v_tipo := 'Despesa';
        END IF;
    END IF;

    SELECT
        COALESCE(SUM(CASE WHEN l.tipo = 'Receita' THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.tipo = 'Despesa' AND public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text) THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.tipo = 'Transferência' THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.status = 'Pago' AND (l.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text)) THEN l.valor ELSE 0 END), 0),
        COALESCE(SUM(CASE WHEN l.status = 'Pendente' AND (l.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text)) THEN l.valor ELSE 0 END), 0),
        COUNT(*)::INT
    INTO v_receitas, v_despesas, v_transf, v_pago, v_pendente, v_qtd
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
      AND l.data BETWEEN v_inicio AND v_fim
      AND (
          (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
          OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
      )
      AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
      AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
      AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
      AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
      AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
      AND (v_regra IS NULL OR l.regra::text = v_regra)
      AND (v_status IS NULL OR l.status::text = v_status)
      AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
      AND (
          v_busca IS NULL
          OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
          OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
      );

    v_base_total := CASE
        WHEN v_tipo = 'Receita' THEN v_receitas
        WHEN v_tipo = 'Despesa' THEN v_despesas
        WHEN v_tipo = 'Transferência' THEN v_transf
        ELSE (v_receitas + v_despesas)
    END;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_cat
    FROM (
        SELECT
            cat.id AS categoria_id,
            COALESCE(cat.nome, 'Sem Categoria') AS nome,
            COALESCE(cat.cor, '#94A3B8') AS cor,
            COALESCE(cat.icone, 'category') AS icone,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (l.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text))
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY cat.id, cat.nome, cat.cor, cat.icone
    ) row;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_subcat
    FROM (
        SELECT
            sub.id AS subcategoria_id,
            COALESCE(sub.nome, 'Geral (Sem subcategoria)') AS nome,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (l.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text))
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY sub.id, sub.nome
    ) row;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.posicao), '[]'::jsonb) INTO v_por_pote
    FROM (
        SELECT
            pot.id AS pote_id,
            COALESCE(pot.posicao, 99) AS posicao,
            COALESCE(pot.nome, 'Sem Pote') AS nome,
            COALESCE(pot.cor, '#94A3B8') AS cor,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.potes pot ON pot.id = l.pote_id
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (l.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text))
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY pot.id, pot.posicao, pot.nome, pot.cor
    ) row;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.data), '[]'::jsonb) INTO v_por_dia
    FROM (
        SELECT
            l.data,
            TO_CHAR(l.data, 'DD/MM') AS label,
            SUM(CASE WHEN l.tipo = 'Receita' THEN l.valor ELSE 0 END) AS receitas,
            SUM(CASE WHEN l.tipo = 'Despesa' AND public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text) THEN l.valor ELSE 0 END) AS despesas,
            SUM(CASE WHEN l.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text) THEN l.valor ELSE 0 END) AS total
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY l.data
    ) row;

    SELECT COALESCE(JSONB_AGG(row ORDER BY row.total DESC), '[]'::jsonb) INTO v_por_forma
    FROM (
        SELECT
            COALESCE(l.forma_movimentacao, 'Outros') AS forma,
            SUM(l.valor) AS total,
            COUNT(*)::INT AS qtd,
            COALESCE(ROUND(SUM(l.valor) / NULLIF(v_base_total, 0) * 100, 1), 0) AS percentual
        FROM public.lancamentos l
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (l.tipo <> 'Despesa' OR public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text))
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        GROUP BY l.forma_movimentacao
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
            l.pote_id,
            pot.nome AS pote_nome,
            pot.cor AS pote_cor,
            l.conta_id,
            co.nome AS conta_nome,
            co.cor AS conta_cor,
            l.destino_id,
            cd.nome AS destino_nome,
            l.cartao_id,
            ca.nome AS cartao_nome,
            ca.cor AS cartao_cor,
            l.caixinha_id,
            cx.nome AS caixinha_nome,
            cx.cor AS caixinha_cor,
            public.fn_eh_consumo_caixinha_neutro(l.caixinha_id, l.subtipo) AS neutro_caixinha,
            l.categoria_id,
            COALESCE(cat.nome, 'Sem Categoria') AS categoria_nome,
            COALESCE(cat.cor, '#94A3B8') AS categoria_cor,
            COALESCE(cat.icone, 'category') AS categoria_icone,
            l.subcategoria_id,
            sub.nome AS subcategoria_nome,
            l.parcela_atual,
            l.total_parcelas,
            l.serie_id,
            l.recorrente_id
        FROM public.lancamentos l
        LEFT JOIN public.potes pot ON pot.id = l.pote_id
        LEFT JOIN public.contas co ON co.id = l.conta_id
        LEFT JOIN public.contas cd ON cd.id = l.destino_id
        LEFT JOIN public.cartoes ca ON ca.id = l.cartao_id
        LEFT JOIN public.caixinhas_teto cx ON cx.id = l.caixinha_id
        LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
        LEFT JOIN public.subcategorias sub ON sub.id = l.subcategoria_id
        WHERE (l.user_id = v_user_id OR l.perfil_id = v_user_id) AND public.fn_membro_visivel(l.membro_id)
          AND l.data BETWEEN v_inicio AND v_fim
          AND (
              (v_tipo IS NULL AND l.tipo IN ('Receita', 'Despesa'))
              OR (v_tipo IS NOT NULL AND l.tipo = v_tipo)
          )
          AND (v_conta_id IS NULL OR l.conta_id = v_conta_id OR l.destino_id = v_conta_id)
          AND (v_cartao_id IS NULL OR l.cartao_id = v_cartao_id)
          AND (v_categoria_id IS NULL OR l.categoria_id = v_categoria_id)
          AND (v_subcat_id IS NULL OR l.subcategoria_id = v_subcat_id)
          AND (v_pote_id IS NULL OR l.pote_id = v_pote_id)
          AND (v_regra IS NULL OR l.regra::text = v_regra)
          AND (v_status IS NULL OR l.status::text = v_status)
          AND (v_forma IS NULL OR lower(l.forma_movimentacao) = lower(v_forma))
          AND (
              v_busca IS NULL
              OR COALESCE(l.descricao, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(l.subtipo, '') ILIKE '%' || v_busca || '%'
              OR COALESCE(cat.nome, '') ILIKE '%' || v_busca || '%'
          )
        ORDER BY l.data DESC, l.hora DESC, l.criado_em DESC
        LIMIT GREATEST(1, COALESCE(p_limite, 50))
        OFFSET GREATEST(0, COALESCE(p_offset, 0))
    ) row;

    RETURN JSONB_BUILD_OBJECT(
        'totais', JSONB_BUILD_OBJECT(
            'receitas', v_receitas,
            'despesas', v_despesas,
            'transferencias', v_transf,
            'saldo', v_receitas - v_despesas,
            'total_filtrado', v_base_total,
            'pago', v_pago,
            'pendente', v_pendente,
            'qtd', v_qtd,
            'media_diaria', ROUND(v_base_total / v_dias_periodo, 2)
        ),
        'por_categoria', v_por_cat,
        'por_subcategoria', v_por_subcat,
        'por_pote', v_por_pote,
        'por_dia', v_por_dia,
        'por_forma', v_por_forma,
        'lancamentos', v_lancamentos,
        'total_registros', v_qtd
    );
END;
$$;

-- 11. Atualiza get_calendario_financeiro_mes para não somar consumo neutro de caixinha nas saídas do banco
CREATE OR REPLACE FUNCTION public.get_calendario_financeiro_mes(
    p_mes smallint,
    p_ano smallint,
    p_data_inicio date DEFAULT NULL::date,
    p_data_fim date DEFAULT NULL::date
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_user_id     UUID := COALESCE(auth.uid(), (SELECT user_id FROM public.lancamentos LIMIT 1));
  v_inicio_mes  DATE := make_date(p_ano::INT, p_mes::INT, 1);
  v_fim_mes     DATE := (v_inicio_mes + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  v_d_ini       DATE := COALESCE(p_data_inicio, v_inicio_mes);
  v_d_fim       DATE := COALESCE(p_data_fim, v_fim_mes);
  v_base_ini    DATE := LEAST(v_inicio_mes, v_d_ini);
  v_base_fim    DATE := GREATEST(v_fim_mes, v_d_fim);
  v_grid_inicio DATE := v_base_ini - (EXTRACT(DOW FROM v_base_ini)::INT);
  v_grid_fim    DATE := GREATEST(
                          v_grid_inicio + 41,
                          v_base_fim + (6 - EXTRACT(DOW FROM v_base_fim)::INT)
                        );
  v_kpis        JSON;
  v_dias        JSON;
  v_faturas     JSON;
  v_desp_cat    JSON;
  v_rec_cat     JSON;
  v_tot_desp    NUMERIC := 0;
  v_tot_rec     NUMERIC := 0;
BEGIN
  IF v_d_fim < v_d_ini THEN
    v_d_fim := v_d_ini;
  END IF;

  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva
    FROM public.lancamentos l
    LEFT JOIN public.faturas f ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c ON c.id = l.cartao_id
    WHERE l.user_id = v_user_id AND public.fn_membro_visivel(l.membro_id)
  )
  SELECT
    COALESCE(SUM(CASE WHEN le.tipo = 'Receita' THEN le.valor ELSE 0 END), 0),
    COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND NOT public.fn_eh_consumo_caixinha_neutro(le.caixinha_id, le.subtipo) THEN le.valor ELSE 0 END), 0)
  INTO v_tot_rec, v_tot_desp
  FROM lancs_efetivos le
  WHERE le.data_efetiva BETWEEN v_d_ini AND v_d_fim;

  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva
    FROM public.lancamentos l
    LEFT JOIN public.faturas f ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c ON c.id = l.cartao_id
    WHERE l.user_id = v_user_id AND public.fn_membro_visivel(l.membro_id)
  )
  SELECT JSON_BUILD_OBJECT(
    'receitas_mes',        v_tot_rec,
    'despesas_mes',        v_tot_desp,
    'resultado_mes',       (v_tot_rec - v_tot_desp),
    'despesas_conta_mes',  COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NULL AND NOT public.fn_eh_consumo_caixinha_neutro(le.caixinha_id, le.subtipo) THEN le.valor ELSE 0 END), 0),
    'despesas_cartao_mes', COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NOT NULL THEN le.valor ELSE 0 END), 0),
    'dias_com_saida',      COUNT(DISTINCT CASE WHEN le.tipo = 'Despesa' AND NOT public.fn_eh_consumo_caixinha_neutro(le.caixinha_id, le.subtipo) AND le.valor > 0 THEN le.data_efetiva END),
    'dias_com_entrada',    COUNT(DISTINCT CASE WHEN le.tipo = 'Receita' AND le.valor > 0 THEN le.data_efetiva END),
    'qtd_lancamentos_mes', COUNT(le.id),
    'maior_saida_dia',     COALESCE((
      SELECT MAX(soma_d) FROM (
        SELECT SUM(le2.valor) AS soma_d
        FROM lancs_efetivos le2
        WHERE le2.data_efetiva BETWEEN v_d_ini AND v_d_fim
          AND le2.tipo = 'Despesa'
          AND NOT public.fn_eh_consumo_caixinha_neutro(le2.caixinha_id, le2.subtipo)
        GROUP BY le2.data_efetiva
      ) s
    ), 0)
  )
  INTO v_kpis
  FROM lancs_efetivos le
  WHERE le.data_efetiva BETWEEN v_d_ini AND v_d_fim;

  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva,
      cat.nome  AS cat_nome,
      cat.cor   AS cat_cor,
      cat.icone AS cat_icone,
      sub.nome  AS sub_nome,
      cta.nome  AS cta_nome,
      crt.nome  AS crt_nome,
      crt.cor   AS crt_cor,
      cx.nome   AS caixinha_nome,
      cx.cor    AS caixinha_cor,
      cx.icone  AS caixinha_icone
    FROM public.lancamentos l
    LEFT JOIN public.faturas f          ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c          ON c.id = l.cartao_id
    LEFT JOIN public.categorias cat     ON cat.id = l.categoria_id
    LEFT JOIN public.subcategorias sub  ON sub.id = l.subcategoria_id
    LEFT JOIN public.contas cta         ON cta.id = l.conta_id
    LEFT JOIN public.cartoes crt        ON crt.id = l.cartao_id
    LEFT JOIN public.caixinhas_teto cx  ON cx.id = l.caixinha_id
    WHERE l.user_id = v_user_id AND public.fn_membro_visivel(l.membro_id)
  )
  SELECT COALESCE(JSON_AGG(row_dia ORDER BY row_dia.data), '[]'::JSON)
  INTO v_dias
  FROM (
    SELECT
      le.data_efetiva::TEXT AS data,
      EXTRACT(DAY FROM le.data_efetiva)::INT AS dia,
      EXTRACT(MONTH FROM le.data_efetiva)::INT AS mes,
      EXTRACT(YEAR FROM le.data_efetiva)::INT AS ano,
      (le.data_efetiva BETWEEN v_inicio_mes AND v_fim_mes) AS no_mes_atual,
      (le.data_efetiva BETWEEN v_d_ini AND v_d_fim) AS no_periodo_filtro,
      COALESCE(SUM(CASE WHEN le.tipo = 'Receita' THEN le.valor ELSE 0 END), 0) AS total_receitas,
      COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND NOT public.fn_eh_consumo_caixinha_neutro(le.caixinha_id, le.subtipo) THEN le.valor ELSE 0 END), 0) AS total_despesas,
      COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NULL AND NOT public.fn_eh_consumo_caixinha_neutro(le.caixinha_id, le.subtipo) THEN le.valor ELSE 0 END), 0) AS despesas_conta,
      COALESCE(SUM(CASE WHEN le.tipo = 'Despesa' AND le.cartao_id IS NOT NULL THEN le.valor ELSE 0 END), 0) AS despesas_cartao,
      COUNT(le.id)::INT AS qtd_lancamentos,
      JSON_AGG(
        JSON_BUILD_OBJECT(
          'id', le.id,
          'data', le.data_efetiva::TEXT,
          'data_compra', le.data::TEXT,
          'hora', le.hora,
          'tipo', le.tipo,
          'subtipo', le.subtipo,
          'valor', le.valor,
          'descricao', le.descricao,
          'status', le.status,
          'regra', le.regra,
          'forma_movimentacao', le.forma_movimentacao,
          'parcela_atual', le.parcela_atual,
          'total_parcelas', le.total_parcelas,
          'fatura', le.fatura,
          'fatura_id', le.fatura_id,
          'conta_id', le.conta_id,
          'cartao_id', le.cartao_id,
          'caixinha_id', le.caixinha_id,
          'caixinha_nome', le.caixinha_nome,
          'caixinha_cor', le.caixinha_cor,
          'caixinha_icone', le.caixinha_icone,
          'neutro_caixinha', public.fn_eh_consumo_caixinha_neutro(le.caixinha_id, le.subtipo),
          'categoria_id', le.categoria_id,
          'subcategoria_id', le.subcategoria_id,
          'categoria_nome', COALESCE(le.cat_nome, 'Sem Categoria'),
          'categoria_cor', COALESCE(le.cat_cor, '#64748B'),
          'categoria_icone', COALESCE(le.cat_icone, 'category'),
          'subcategoria_nome', le.sub_nome,
          'conta_nome', le.cta_nome,
          'cartao_nome', le.crt_nome,
          'cartao_cor', le.crt_cor
        ) ORDER BY le.hora DESC NULLS LAST, le.criado_em DESC
      ) AS lancamentos
    FROM lancs_efetivos le
    WHERE le.data_efetiva BETWEEN v_grid_inicio AND v_grid_fim
    GROUP BY le.data_efetiva
  ) row_dia;

  SELECT COALESCE(JSON_AGG(row_cart ORDER BY row_cart.data_vencimento, row_cart.cartao_nome), '[]'::JSON)
  INTO v_faturas
  FROM (
    SELECT
      c.id AS cartao_id,
      c.nome AS cartao_nome,
      c.bandeira,
      c.cor AS cartao_cor,
      c.icone AS cartao_icone,
      c.limite_total,
      c.limite_disponivel,
      c.dia_fechamento,
      c.dia_vencimento,
      f.id AS fatura_id,
      f.mes AS fatura_mes,
      f.ano AS fatura_ano,
      COALESCE(
        f.data_vencimento,
        make_date(
          p_ano::INT,
          p_mes::INT,
          LEAST(COALESCE(c.dia_vencimento, 10)::INT, EXTRACT(DAY FROM v_fim_mes)::INT)
        )
      )::TEXT AS data_vencimento,
      EXTRACT(DAY FROM COALESCE(
        f.data_vencimento,
        make_date(
          p_ano::INT,
          p_mes::INT,
          LEAST(COALESCE(c.dia_vencimento, 10)::INT, EXTRACT(DAY FROM v_fim_mes)::INT)
        )
      ))::INT AS dia_vencimento_efetivo,
      COALESCE(f.valor_total, 0) AS valor_total,
      COALESCE(f.valor_pago, 0) AS valor_pago,
      CASE
        WHEN COALESCE(f.valor_total, 0) <= 0.01 THEN 'paga'
        ELSE COALESCE(f.status, 'aberta')
      END AS status
    FROM public.cartoes c
    LEFT JOIN public.faturas f
      ON f.cartao_id = c.id
     AND (
       (f.data_vencimento BETWEEN v_grid_inicio AND v_grid_fim)
       OR (f.data_vencimento IS NULL AND f.mes = p_mes AND f.ano = p_ano)
     )
    WHERE c.user_id = v_user_id AND public.fn_membro_visivel(c.membro_id)
      AND c.ativo = TRUE
  ) row_cart;

  WITH lancs_efetivos AS (
    SELECT
      l.*,
      CASE
        WHEN l.cartao_id IS NOT NULL THEN
          COALESCE(
            f.data_vencimento,
            CASE
              WHEN COALESCE(c.dia_vencimento, 10) < COALESCE(c.dia_fechamento, 1) THEN
                (date_trunc('month', l.data)::DATE + INTERVAL '1 month'
                 + (LEAST(
                      COALESCE(c.dia_vencimento, 10)::INT,
                      EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '2 months - 1 day'))::INT
                    ) - 1) * INTERVAL '1 day')::DATE
              ELSE
                make_date(
                  EXTRACT(YEAR FROM l.data)::INT,
                  EXTRACT(MONTH FROM l.data)::INT,
                  LEAST(
                    COALESCE(c.dia_vencimento, 10)::INT,
                    EXTRACT(DAY FROM (date_trunc('month', l.data) + INTERVAL '1 month - 1 day'))::INT
                  )
                )
            END
          )
        ELSE l.data
      END AS data_efetiva
    FROM public.lancamentos l
    LEFT JOIN public.faturas f ON f.id = l.fatura_id
    LEFT JOIN public.cartoes c ON c.id = l.cartao_id
    WHERE l.user_id = v_user_id AND public.fn_membro_visivel(l.membro_id)
  )
  SELECT COALESCE(JSON_AGG(row_dc ORDER BY row_dc.total DESC), '[]'::JSON)
  INTO v_desp_cat
  FROM (
    SELECT
      cat.id AS categoria_id,
      COALESCE(cat.nome, 'Sem Categoria') AS categoria,
      COALESCE(cat.cor, '#94A3B8') AS cor,
      COALESCE(cat.icone, 'label') AS icone,
      SUM(le.valor) AS total,
      COUNT(le.id)::INT AS qtd,
      ROUND((SUM(le.valor) / NULLIF(v_tot_desp, 0)) * 100, 1) AS percentual
    FROM lancs_efetivos le
    LEFT JOIN public.categorias cat ON cat.id = le.categoria_id
    WHERE le.data_efetiva BETWEEN v_d_ini AND v_d_fim
      AND le.tipo = 'Despesa'
      AND NOT public.fn_eh_consumo_caixinha_neutro(le.caixinha_id, le.subtipo)
    GROUP BY cat.id, cat.nome, cat.cor, cat.icone
  ) row_dc;

  SELECT COALESCE(JSON_AGG(row_rc ORDER BY row_rc.total DESC), '[]'::JSON)
  INTO v_rec_cat
  FROM (
    SELECT
      cat.id AS categoria_id,
      COALESCE(cat.nome, 'Sem Categoria') AS categoria,
      COALESCE(cat.cor, '#10B981') AS cor,
      COALESCE(cat.icone, 'label') AS icone,
      SUM(l.valor) AS total,
      COUNT(l.id)::INT AS qtd,
      ROUND((SUM(l.valor) / NULLIF(v_tot_rec, 0)) * 100, 1) AS percentual
    FROM public.lancamentos l
    LEFT JOIN public.categorias cat ON cat.id = l.categoria_id
    WHERE l.user_id = v_user_id AND public.fn_membro_visivel(l.membro_id)
      AND l.data BETWEEN v_d_ini AND v_d_fim
      AND l.tipo = 'Receita'
    GROUP BY cat.id, cat.nome, cat.cor, cat.icone
  ) row_rc;

  RETURN JSON_BUILD_OBJECT(
    'mes', p_mes,
    'ano', p_ano,
    'inicio_mes', v_inicio_mes::TEXT,
    'fim_mes', v_fim_mes::TEXT,
    'filtro_inicio', v_d_ini::TEXT,
    'filtro_fim', v_d_fim::TEXT,
    'eh_periodo_parcial', (v_d_ini <> v_inicio_mes OR v_d_fim <> v_fim_mes),
    'grid_inicio', v_grid_inicio::TEXT,
    'grid_fim', v_grid_fim::TEXT,
    'kpis', v_kpis,
    'dias', v_dias,
    'cartoes_faturas', v_faturas,
    'despesas_por_categoria', v_desp_cat,
    'receitas_por_categoria', v_rec_cat
  );
END;
$$;

-- 12. Saneamento retroativo dos lançamentos de consumo de caixinha existentes
UPDATE public.lancamentos
SET conta_id = NULL,
    cartao_id = NULL,
    fatura_id = NULL,
    subtipo = 'Consumo Caixinha',
    forma_movimentacao = 'Caixinha',
    status = 'Pago'
WHERE caixinha_id IS NOT NULL
  AND LOWER(COALESCE(TRIM(subtipo), '')) <> 'provisionamento';

-- Recalcula saldos de todas as caixinhas e contas de todos os usuários
DO $$
DECLARE
    r_cx RECORD;
    r_u  RECORD;
BEGIN
    FOR r_cx IN SELECT id FROM public.caixinhas_teto LOOP
        PERFORM public.fn_recalcular_saldo_caixinha(r_cx.id);
    END LOOP;

    FOR r_u IN SELECT DISTINCT user_id FROM public.contas WHERE user_id IS NOT NULL LOOP
        PERFORM public.fn_recalcular_saldos_usuario(r_u.user_id);
    END LOOP;
END;
$$;
