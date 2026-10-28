-- =============================================================================
-- DemBase v3 — migrations/025_create_cofres_investimentos.sql
-- Módulo de Investimentos & Patrimônio ("Meu Cofre")
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.cofres_investimento (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    nome                TEXT NOT NULL,
    tipo                TEXT NOT NULL DEFAULT 'renda_fixa' CHECK (tipo IN ('reserva_emergencia', 'renda_fixa', 'outros')),
    cor                 TEXT NOT NULL DEFAULT '#00E676',
    icone               TEXT NOT NULL DEFAULT 'savings',
    meta_valor          NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    percentual_cdi      NUMERIC(6,2) NOT NULL DEFAULT 102.00,
    saldo_atual         NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_aportado      NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_rendimentos   NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    total_resgatado     NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    ativo               BOOLEAN NOT NULL DEFAULT TRUE,
    ordem               INT NOT NULL DEFAULT 0,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cofres_investimento_user_ativo ON public.cofres_investimento(user_id, ativo);
CREATE INDEX IF NOT EXISTS idx_cofres_investimento_tipo       ON public.cofres_investimento(tipo);

CREATE TABLE IF NOT EXISTS public.cofres_movimentacoes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cofre_id            UUID NOT NULL REFERENCES public.cofres_investimento(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tipo                TEXT NOT NULL CHECK (tipo IN ('aporte', 'rendimento', 'resgate')),
    valor               NUMERIC(14,2) NOT NULL CHECK (valor > 0),
    saldo_anterior      NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    saldo_posterior     NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    descricao           TEXT,
    data                DATE NOT NULL DEFAULT CURRENT_DATE,
    conta_origem_id     UUID REFERENCES public.contas(id) ON DELETE SET NULL,
    lancamento_id       UUID REFERENCES public.lancamentos(id) ON DELETE SET NULL,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cofres_mov_cofre_id   ON public.cofres_movimentacoes(cofre_id);
CREATE INDEX IF NOT EXISTS idx_cofres_mov_user_data  ON public.cofres_movimentacoes(user_id, data DESC);
CREATE INDEX IF NOT EXISTS idx_cofres_mov_tipo       ON public.cofres_movimentacoes(tipo);

CREATE TABLE IF NOT EXISTS public.cofres_config (
    user_id             UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    taxa_cdi_anual      NUMERIC(6,2) NOT NULL DEFAULT 10.75,
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.cofres_investimento ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cofres_movimentacoes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cofres_config ENABLE ROW LEVEL SECURITY;

CREATE POLICY "cofres_investimento_user_policy"
    ON public.cofres_investimento
    FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "cofres_movimentacoes_user_policy"
    ON public.cofres_movimentacoes
    FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "cofres_config_user_policy"
    ON public.cofres_config
    FOR ALL
    TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE OR REPLACE FUNCTION public.fn_garantir_cofres_padrao(p_user_id UUID)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM public.cofres_investimento 
        WHERE user_id = p_user_id AND tipo = 'reserva_emergencia' AND ativo = TRUE
    ) THEN
        INSERT INTO public.cofres_investimento (
            user_id, nome, tipo, cor, icone, meta_valor, percentual_cdi, ordem
        ) VALUES (
            p_user_id, 'Porquinho (Reserva de Emergência)', 'reserva_emergencia', '#10B981', 'savings', 10000.00, 100.00, 1
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.cofres_investimento 
        WHERE user_id = p_user_id AND tipo = 'renda_fixa' AND ativo = TRUE
    ) THEN
        INSERT INTO public.cofres_investimento (
            user_id, nome, tipo, cor, icone, meta_valor, percentual_cdi, ordem
        ) VALUES (
            p_user_id, 'Renda Fixa (102% CDI)', 'renda_fixa', '#00E676', 'trending_up', 50000.00, 102.00, 2
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM public.cofres_config WHERE user_id = p_user_id
    ) THEN
        INSERT INTO public.cofres_config (user_id, taxa_cdi_anual)
        VALUES (p_user_id, 10.75);
    END IF;
END;
$$;
