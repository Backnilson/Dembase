-- =============================================================================
-- DemBase v3 — Migração 002
-- Novas tabelas: cartoes, faturas, transacoes_recorrentes, objetivos
-- Execute DEPOIS da 001 (depende de subcategorias já existir)
-- Execute no SQL Editor do Supabase (schema: public)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. CARTÕES DE CRÉDITO
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.cartoes (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  nome                TEXT NOT NULL,
  bandeira            TEXT NOT NULL DEFAULT 'outro'
      CHECK (bandeira IN ('visa','mastercard','amex','elo','hipercard','outro')),
  cor                 TEXT NOT NULL DEFAULT '#6366F1',
  icone               TEXT NOT NULL DEFAULT 'credit_card',
  limite_total        NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  limite_disponivel   NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  dia_vencimento      SMALLINT NOT NULL DEFAULT 10
      CHECK (dia_vencimento BETWEEN 1 AND 31),
  dia_fechamento      SMALLINT NOT NULL DEFAULT 3
      CHECK (dia_fechamento BETWEEN 1 AND 31),
  -- campo para uso futuro (ligar cartão a uma conta para débito automático)
  conta_debito_id     UUID REFERENCES public.contas(id) ON DELETE SET NULL,
  ativo               BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cartoes_user_id ON public.cartoes(user_id);
CREATE INDEX IF NOT EXISTS idx_cartoes_ativo   ON public.cartoes(user_id, ativo);

-- Trigger: atualiza 'atualizado_em' automaticamente
CREATE OR REPLACE FUNCTION public.fn_update_timestamp()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.atualizado_em = NOW();
  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_cartoes_updated
  BEFORE UPDATE ON public.cartoes
  FOR EACH ROW EXECUTE FUNCTION public.fn_update_timestamp();


-- -----------------------------------------------------------------------------
-- 2. FATURAS DE CARTÃO
-- Status lifecycle: aberta → fechada → paga | vencida
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.faturas (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cartao_id        UUID NOT NULL REFERENCES public.cartoes(id) ON DELETE CASCADE,
  user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  mes              SMALLINT NOT NULL CHECK (mes BETWEEN 1 AND 12),
  ano              SMALLINT NOT NULL CHECK (ano >= 2000),
  valor_total      NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  valor_pago       NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  data_fechamento  DATE NOT NULL,
  data_vencimento  DATE NOT NULL,
  status           TEXT NOT NULL DEFAULT 'aberta'
      CHECK (status IN ('aberta','fechada','paga','vencida')),
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  -- Unicidade: só uma fatura por cartão por mês/ano
  UNIQUE (cartao_id, mes, ano)
);

CREATE INDEX IF NOT EXISTS idx_faturas_cartao    ON public.faturas(cartao_id);
CREATE INDEX IF NOT EXISTS idx_faturas_user      ON public.faturas(user_id);
CREATE INDEX IF NOT EXISTS idx_faturas_status    ON public.faturas(status);
CREATE INDEX IF NOT EXISTS idx_faturas_vencimento ON public.faturas(data_vencimento DESC);

CREATE TRIGGER trg_faturas_updated
  BEFORE UPDATE ON public.faturas
  FOR EACH ROW EXECUTE FUNCTION public.fn_update_timestamp();

-- Adicionar as FKs que foram preparadas na migração 001 (usando DO block para idempotência)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_lancamentos_cartao'
  ) THEN
    ALTER TABLE public.lancamentos
      ADD CONSTRAINT fk_lancamentos_cartao
        FOREIGN KEY (cartao_id) REFERENCES public.cartoes(id) ON DELETE SET NULL;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'fk_lancamentos_fatura'
  ) THEN
    ALTER TABLE public.lancamentos
      ADD CONSTRAINT fk_lancamentos_fatura
        FOREIGN KEY (fatura_id) REFERENCES public.faturas(id) ON DELETE SET NULL;
  END IF;
END $$;


-- -----------------------------------------------------------------------------
-- 3. TRANSAÇÕES RECORRENTES
-- Motor de agendamento para receitas/despesas fixas
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.transacoes_recorrentes (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  conta_id         UUID REFERENCES public.contas(id) ON DELETE SET NULL,
  cartao_id        UUID REFERENCES public.cartoes(id) ON DELETE SET NULL,
  categoria_id     UUID REFERENCES public.categorias(id) ON DELETE SET NULL,
  subcategoria_id  UUID REFERENCES public.subcategorias(id) ON DELETE SET NULL,
  tipo             TEXT NOT NULL CHECK (tipo IN ('Receita','Despesa')),
  forma_movimentacao TEXT NOT NULL DEFAULT 'Pix',
  valor            NUMERIC(14,2) NOT NULL,
  descricao        TEXT NOT NULL,
  regra            TEXT CHECK (regra IN ('Essencial','Estilo de Vida','Investimento')),
  frequencia       TEXT NOT NULL DEFAULT 'mensal'
      CHECK (frequencia IN ('diaria','semanal','quinzenal','mensal','bimestral','trimestral','semestral','anual')),
  dia_vencimento   SMALLINT CHECK (dia_vencimento BETWEEN 1 AND 31),
  data_inicio      DATE NOT NULL,
  data_fim         DATE,             -- NULL = sem prazo de término
  ultimo_lancamento DATE,            -- controle interno do motor
  ativo            BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recorrentes_user   ON public.transacoes_recorrentes(user_id);
CREATE INDEX IF NOT EXISTS idx_recorrentes_ativo  ON public.transacoes_recorrentes(user_id, ativo);


-- -----------------------------------------------------------------------------
-- 4. OBJETIVOS / METAS FINANCEIRAS
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.objetivos (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  nome           TEXT NOT NULL,
  descricao      TEXT,
  valor_meta     NUMERIC(14,2) NOT NULL,
  valor_atual    NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  data_inicio    DATE NOT NULL DEFAULT CURRENT_DATE,
  data_limite    DATE,
  cor            TEXT NOT NULL DEFAULT '#10B981',
  icone          TEXT NOT NULL DEFAULT 'flag',
  categoria      TEXT,               -- ex: "Viagem", "Emergência", "Casa"
  conta_id       UUID REFERENCES public.contas(id) ON DELETE SET NULL,
  ativo          BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_objetivos_user ON public.objetivos(user_id);

CREATE TRIGGER trg_objetivos_updated
  BEFORE UPDATE ON public.objetivos
  FOR EACH ROW EXECUTE FUNCTION public.fn_update_timestamp();


-- =============================================================================
-- SEGURANÇA — Habilitar RLS nas novas tabelas
-- =============================================================================
ALTER TABLE public.cartoes              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.faturas              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transacoes_recorrentes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.objetivos            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subcategorias        ENABLE ROW LEVEL SECURITY;

-- Políticas: cada usuário só vê seus próprios dados
-- (DROP IF EXISTS + CREATE para idempotência — Supabase não suporta CREATE POLICY IF NOT EXISTS)
DROP POLICY IF EXISTS "cartoes_user_policy"    ON public.cartoes;
DROP POLICY IF EXISTS "faturas_user_policy"    ON public.faturas;
DROP POLICY IF EXISTS "recorrentes_user_policy" ON public.transacoes_recorrentes;
DROP POLICY IF EXISTS "objetivos_user_policy"  ON public.objetivos;
DROP POLICY IF EXISTS "subcategorias_user_policy" ON public.subcategorias;

CREATE POLICY "cartoes_user_policy"
  ON public.cartoes FOR ALL USING (user_id = auth.uid());

CREATE POLICY "faturas_user_policy"
  ON public.faturas FOR ALL USING (user_id = auth.uid());

CREATE POLICY "recorrentes_user_policy"
  ON public.transacoes_recorrentes FOR ALL USING (user_id = auth.uid());

CREATE POLICY "objetivos_user_policy"
  ON public.objetivos FOR ALL USING (user_id = auth.uid());

CREATE POLICY "subcategorias_user_policy"
  ON public.subcategorias FOR ALL USING (user_id = auth.uid());

