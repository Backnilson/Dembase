-- =============================================================================
-- DemBase v3 — Migration 035: DemBox Fatura (100% ADITIVA)
-- =============================================================================
-- Principios:
--  * Nao altera nenhuma funcao existente (get_potes_resumo, calendario, etc.).
--  * Movimentos do box de fatura vivem em tabela propria (dembox_fatura_movs) e
--    NAO criam linhas em public.lancamentos como Despesa => zero impacto nos 6 Potes.
--  * Saldo guardado = soma dos movimentos EFETIVADOS (pendente nunca conta).
--  * Pagamento da fatura = Transferencia 'Pagamento de Fatura' (neutra nos Potes),
--    ja ligada a fatura via fatura_id. Pagamento parcial e derivado dessas
--    transferencias (faturas.valor_pago e recalculado por fn_recalcular_saldos_usuario).
-- =============================================================================

ALTER TABLE public.caixinhas_teto ADD COLUMN IF NOT EXISTS tipo_box TEXT NOT NULL DEFAULT 'padrao';
ALTER TABLE public.caixinhas_teto ADD COLUMN IF NOT EXISTS cartao_id UUID REFERENCES public.cartoes(id) ON DELETE SET NULL;
ALTER TABLE public.caixinhas_teto ADD COLUMN IF NOT EXISTS auto_efetivar BOOLEAN NOT NULL DEFAULT FALSE;

DO $$ BEGIN
    ALTER TABLE public.caixinhas_teto
        ADD CONSTRAINT caixinhas_teto_tipo_box_chk CHECK (tipo_box IN ('padrao', 'fatura'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_caixinhas_fatura_por_cartao
    ON public.caixinhas_teto (cartao_id) WHERE tipo_box = 'fatura' AND ativo;

CREATE TABLE IF NOT EXISTS public.dembox_fatura_movs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID NOT NULL DEFAULT auth.uid() REFERENCES auth.users(id) ON DELETE CASCADE,
    caixinha_id    UUID NOT NULL REFERENCES public.caixinhas_teto(id) ON DELETE CASCADE,
    membro_id      UUID REFERENCES public.membros(id) ON DELETE SET NULL,
    tipo           TEXT NOT NULL CHECK (tipo IN ('aporte', 'retirada', 'transf_entrada', 'transf_saida', 'pagamento')),
    valor          NUMERIC(14,2) NOT NULL CHECK (valor > 0),
    data_prevista  DATE NOT NULL DEFAULT CURRENT_DATE,
    status         TEXT NOT NULL DEFAULT 'efetivado' CHECK (status IN ('pendente', 'efetivado', 'cancelado')),
    efetivado_em   TIMESTAMPTZ,
    fatura_id      UUID REFERENCES public.faturas(id) ON DELETE SET NULL,
    grupo_id       UUID,
    descricao      TEXT,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dfm_caixinha ON public.dembox_fatura_movs (caixinha_id, status);
CREATE INDEX IF NOT EXISTS idx_dfm_user_data ON public.dembox_fatura_movs (user_id, data_prevista);

ALTER TABLE public.dembox_fatura_movs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dfm_dono ON public.dembox_fatura_movs;
CREATE POLICY dfm_dono ON public.dembox_fatura_movs
    FOR ALL TO authenticated
    USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- Saldo guardado (somente efetivado)
CREATE OR REPLACE FUNCTION public.fn_dembox_fatura_saldo(p_caixinha_id UUID)
RETURNS NUMERIC LANGUAGE sql STABLE SET search_path = public AS $$
    SELECT COALESCE(SUM(CASE WHEN tipo IN ('aporte', 'transf_entrada') THEN valor ELSE -valor END), 0)::NUMERIC(14,2)
      FROM public.dembox_fatura_movs
     WHERE caixinha_id = p_caixinha_id AND status = 'efetivado';
$$;

-- Aporte / retirada. Aporte pode nascer pendente (agendado) via p_status.
CREATE OR REPLACE FUNCTION public.dembox_fatura_registrar(
    p_caixinha_id UUID, p_tipo TEXT, p_valor NUMERIC,
    p_data DATE DEFAULT CURRENT_DATE, p_status TEXT DEFAULT 'efetivado', p_descricao TEXT DEFAULT NULL
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid UUID := auth.uid();
    v_cx  RECORD;
    v_saldo NUMERIC;
    v_id UUID;
BEGIN
    IF v_uid IS NULL THEN RAISE EXCEPTION 'Sessao invalida'; END IF;
    IF p_tipo NOT IN ('aporte', 'retirada') THEN RAISE EXCEPTION 'Tipo invalido'; END IF;
    IF p_status NOT IN ('pendente', 'efetivado') THEN RAISE EXCEPTION 'Status invalido'; END IF;
    IF COALESCE(p_valor, 0) <= 0 THEN RAISE EXCEPTION 'Valor deve ser maior que zero'; END IF;
    IF p_tipo = 'retirada' AND p_status <> 'efetivado' THEN RAISE EXCEPTION 'Retirada nao pode ser agendada'; END IF;

    SELECT * INTO v_cx FROM public.caixinhas_teto
     WHERE id = p_caixinha_id AND user_id = v_uid AND tipo_box = 'fatura' FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Box de fatura nao encontrado'; END IF;

    v_saldo := public.fn_dembox_fatura_saldo(p_caixinha_id);
    IF p_tipo = 'retirada' AND p_valor > v_saldo + 0.004 THEN
        RAISE EXCEPTION 'Saldo insuficiente no box (disponivel: %)', v_saldo;
    END IF;

    INSERT INTO public.dembox_fatura_movs (user_id, caixinha_id, membro_id, tipo, valor, data_prevista, status, efetivado_em, descricao)
    VALUES (v_uid, p_caixinha_id, v_cx.membro_id, p_tipo, ROUND(p_valor, 2), COALESCE(p_data, CURRENT_DATE), p_status,
            CASE WHEN p_status = 'efetivado' THEN NOW() END, p_descricao)
    RETURNING id INTO v_id;

    RETURN jsonb_build_object('sucesso', TRUE, 'mov_id', v_id,
        'saldo', public.fn_dembox_fatura_saldo(p_caixinha_id));
END $$;

-- Transferencia entre boxes de fatura (atomica, valida saldo)
CREATE OR REPLACE FUNCTION public.dembox_fatura_transferir(
    p_origem UUID, p_destino UUID, p_valor NUMERIC
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid UUID := auth.uid();
    v_o RECORD; v_d RECORD; v_saldo NUMERIC; v_grp UUID := gen_random_uuid();
BEGIN
    IF v_uid IS NULL THEN RAISE EXCEPTION 'Sessao invalida'; END IF;
    IF p_origem = p_destino THEN RAISE EXCEPTION 'Origem e destino devem ser diferentes'; END IF;
    IF COALESCE(p_valor, 0) <= 0 THEN RAISE EXCEPTION 'Valor deve ser maior que zero'; END IF;

    -- Ordem fixa de lock evita deadlock
    PERFORM 1 FROM public.caixinhas_teto WHERE id IN (p_origem, p_destino) ORDER BY id FOR UPDATE;
    SELECT * INTO v_o FROM public.caixinhas_teto WHERE id = p_origem  AND user_id = v_uid AND tipo_box = 'fatura';
    IF NOT FOUND THEN RAISE EXCEPTION 'Box de origem nao encontrado'; END IF;
    SELECT * INTO v_d FROM public.caixinhas_teto WHERE id = p_destino AND user_id = v_uid AND tipo_box = 'fatura';
    IF NOT FOUND THEN RAISE EXCEPTION 'Box de destino nao encontrado'; END IF;

    v_saldo := public.fn_dembox_fatura_saldo(p_origem);
    IF p_valor > v_saldo + 0.004 THEN
        RAISE EXCEPTION 'Saldo insuficiente no box de origem (disponivel: %)', v_saldo;
    END IF;

    INSERT INTO public.dembox_fatura_movs (user_id, caixinha_id, membro_id, tipo, valor, status, efetivado_em, grupo_id, descricao)
    VALUES (v_uid, p_origem,  v_o.membro_id, 'transf_saida',   ROUND(p_valor, 2), 'efetivado', NOW(), v_grp, 'Movido para ' || v_d.nome),
           (v_uid, p_destino, v_d.membro_id, 'transf_entrada', ROUND(p_valor, 2), 'efetivado', NOW(), v_grp, 'Recebido de ' || v_o.nome);

    RETURN jsonb_build_object('sucesso', TRUE, 'grupo_id', v_grp,
        'saldo_origem', public.fn_dembox_fatura_saldo(p_origem),
        'saldo_destino', public.fn_dembox_fatura_saldo(p_destino));
END $$;

-- Pagamento (parcial ou total) da fatura debitando o box.
-- Cria Transferencia 'Pagamento de Fatura' (neutra nos Potes). So quita a fatura
-- (baixa das despesas e status 'paga') quando a soma dos pagamentos cobre o total.
CREATE OR REPLACE FUNCTION public.dembox_fatura_pagar(
    p_caixinha_id UUID, p_fatura_id UUID, p_conta_id UUID,
    p_valor NUMERIC, p_data DATE DEFAULT CURRENT_DATE
) RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid UUID := auth.uid();
    v_cx RECORD; v_f RECORD; v_ct RECORD; v_conta RECORD;
    v_total NUMERIC; v_pago_antes NUMERIC; v_restante NUMERIC; v_saldo NUMERIC;
    v_debito_box NUMERIC; v_lanc UUID; v_quitada BOOLEAN := FALSE; v_dt DATE := COALESCE(p_data, CURRENT_DATE);
BEGIN
    IF v_uid IS NULL THEN RAISE EXCEPTION 'Sessao invalida'; END IF;
    IF COALESCE(p_valor, 0) <= 0 THEN RAISE EXCEPTION 'Valor deve ser maior que zero'; END IF;

    SELECT * INTO v_cx FROM public.caixinhas_teto
     WHERE id = p_caixinha_id AND user_id = v_uid AND tipo_box = 'fatura' FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Box de fatura nao encontrado'; END IF;

    SELECT * INTO v_f FROM public.faturas WHERE id = p_fatura_id AND user_id = v_uid FOR UPDATE;
    IF NOT FOUND THEN RAISE EXCEPTION 'Fatura nao encontrada'; END IF;
    IF v_f.cartao_id IS DISTINCT FROM v_cx.cartao_id THEN RAISE EXCEPTION 'Fatura nao pertence ao cartao do box'; END IF;
    IF v_f.status = 'paga' THEN RAISE EXCEPTION 'Fatura ja esta paga'; END IF;

    SELECT * INTO v_ct FROM public.cartoes WHERE id = v_f.cartao_id;
    SELECT * INTO v_conta FROM public.contas WHERE id = p_conta_id AND (user_id = v_uid OR perfil_id = v_uid);
    IF NOT FOUND THEN RAISE EXCEPTION 'Conta de origem nao encontrada'; END IF;

    SELECT COALESCE(SUM(valor), 0) INTO v_total FROM public.lancamentos
     WHERE fatura_id = p_fatura_id AND tipo = 'Despesa';
    SELECT COALESCE(SUM(valor), 0) INTO v_pago_antes FROM public.lancamentos
     WHERE fatura_id = p_fatura_id AND tipo = 'Transferência' AND subtipo = 'Pagamento de Fatura' AND status = 'Pago';
    v_restante := GREATEST(0, v_total - v_pago_antes);

    IF v_restante <= 0.004 THEN RAISE EXCEPTION 'Fatura sem valor a pagar'; END IF;
    IF p_valor > v_restante + 0.004 THEN
        RAISE EXCEPTION 'Valor maior que o restante da fatura (restante: %)', v_restante;
    END IF;

    PERFORM set_config('dembase.fluxo_fatura', 'on', true);

    INSERT INTO public.lancamentos (user_id, perfil_id, tipo, subtipo, forma_movimentacao, conta_id, fatura_id,
                                    valor, data, hora, descricao, status, fonte_importacao)
    VALUES (v_uid, v_uid, 'Transferência', 'Pagamento de Fatura', 'Pix', p_conta_id, p_fatura_id,
            ROUND(p_valor, 2), v_dt, COALESCE(EXTRACT(HOUR FROM NOW())::INT, 12),
            'Pagamento Fatura ' || v_ct.nome || ' (' || LPAD(v_f.mes::TEXT, 2, '0') || '/' || v_f.ano::TEXT || ')'
              || CASE WHEN p_valor + 0.004 < v_restante THEN ' - parcial' ELSE '' END,
            'Pago'::public.status_lancamento, 'manual')
    RETURNING id INTO v_lanc;

    IF p_valor + 0.004 >= v_restante THEN
        v_quitada := TRUE;
        UPDATE public.lancamentos SET status = 'Pago'::public.status_lancamento, data_pagamento = v_dt, atualizado_em = NOW()
         WHERE fatura_id = p_fatura_id AND tipo = 'Despesa' AND status <> 'Pago';
        UPDATE public.faturas
           SET status = 'paga', valor_pago = v_total, data_pagamento = v_dt,
               conta_pagamento_id = p_conta_id, pagamento_lancamento_id = v_lanc, atualizado_em = NOW()
         WHERE id = p_fatura_id;
    END IF;

    -- Debita o box (no maximo o que ha guardado; o restante sai direto da conta)
    v_saldo := public.fn_dembox_fatura_saldo(p_caixinha_id);
    v_debito_box := LEAST(ROUND(p_valor, 2), v_saldo);
    IF v_debito_box > 0 THEN
        INSERT INTO public.dembox_fatura_movs (user_id, caixinha_id, membro_id, tipo, valor, status, efetivado_em, fatura_id, descricao)
        VALUES (v_uid, p_caixinha_id, v_cx.membro_id, 'pagamento', v_debito_box, 'efetivado', NOW(), p_fatura_id,
                'Pagamento fatura ' || v_ct.nome);
    END IF;

    PERFORM public.fn_recalcular_saldos_usuario(v_uid);
    PERFORM set_config('dembase.fluxo_fatura', 'off', true);

    RETURN jsonb_build_object('sucesso', TRUE, 'lancamento_id', v_lanc, 'valor_pago', ROUND(p_valor, 2),
        'data_pagamento', v_dt, 'quitada', v_quitada, 'restante', GREATEST(0, v_restante - p_valor),
        'debitado_do_box', v_debito_box, 'saldo_box', public.fn_dembox_fatura_saldo(p_caixinha_id),
        'conta_nome', v_conta.nome, 'cartao_nome', v_ct.nome);
END $$;

GRANT EXECUTE ON FUNCTION public.fn_dembox_fatura_saldo(UUID) TO authenticated;
GRANT EXECUTE ON FUNCTION public.dembox_fatura_registrar(UUID, TEXT, NUMERIC, DATE, TEXT, TEXT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.dembox_fatura_transferir(UUID, UUID, NUMERIC) TO authenticated;
GRANT EXECUTE ON FUNCTION public.dembox_fatura_pagar(UUID, UUID, UUID, NUMERIC, DATE) TO authenticated;

