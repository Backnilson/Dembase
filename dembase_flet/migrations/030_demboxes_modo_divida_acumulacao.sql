-- =============================================================================
-- DemBase v3 — Migration 030: Evolução para DemBoxes (Provisão Mensal + Quitação de Dívidas)
-- =============================================================================
-- Adiciona suporte nativo ao modo acumulativo de Quitação de Dívidas ('divida')
-- além do modo tradicional de Provisão de Consumo Mensal ('provisao_mensal').
-- =============================================================================

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS modalidade TEXT NOT NULL DEFAULT 'provisao_mensal';

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS credor TEXT;

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS valor_abatido NUMERIC(14,2) NOT NULL DEFAULT 0.00;

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

    -- Soma eventuais deduções avulsas que não tenham lancamento_id vinculado
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
        valor_abatido = v_total_despesas,
        atualizado_em = NOW()
    WHERE id = p_caixinha_id;

    RETURN jsonb_build_object(
        'sucesso', true,
        'caixinha_id', p_caixinha_id,
        'valor_meta', v_meta,
        'base_provisionada', v_base_provisionada,
        'total_gasto', v_total_despesas,
        'valor_abatido', v_total_despesas,
        'saldo_atual', v_novo_saldo
    );
END;
$$;

NOTIFY pgrst, 'reload schema';

CREATE OR REPLACE FUNCTION public.fn_trg_caixinhas_teto_sincronizar_provisoes()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM public.lancamentos
        WHERE caixinha_id = OLD.id
          AND status = 'Pendente'
          AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
        RETURN OLD;
    ELSE
        IF LOWER(COALESCE(NEW.modalidade, 'provisao_mensal')) IN ('divida', 'quitacao') THEN
            DELETE FROM public.lancamentos
            WHERE caixinha_id = NEW.id
              AND status = 'Pendente'
              AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
            RETURN NEW;
        END IF;
        PERFORM public.fn_sincronizar_provisoes_caixinha(NEW.id, 12);
        RETURN NEW;
    END IF;
END;
$function$;
