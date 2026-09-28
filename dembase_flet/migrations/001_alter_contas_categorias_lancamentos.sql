-- =============================================================================
-- DemBase v3 — Migração 001
-- Altera tabelas EXISTENTES: contas, categorias, lancamentos
-- Adiciona colunas necessárias para o sistema completo e importação CSV.
-- Execute no SQL Editor do Supabase (schema: public)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. CONTAS — enriquecer com metadados visuais e financeiros
-- -----------------------------------------------------------------------------
ALTER TABLE public.contas
  ADD COLUMN IF NOT EXISTS tipo_conta    TEXT    NOT NULL DEFAULT 'corrente'
      CHECK (tipo_conta IN ('corrente','poupanca','investimento','dinheiro','outro')),
  ADD COLUMN IF NOT EXISTS banco         TEXT,
  ADD COLUMN IF NOT EXISTS cor           TEXT    NOT NULL DEFAULT '#10B981',
  ADD COLUMN IF NOT EXISTS icone         TEXT    NOT NULL DEFAULT 'account_balance',
  ADD COLUMN IF NOT EXISTS saldo_inicial NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  ADD COLUMN IF NOT EXISTS saldo_atual   NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  ADD COLUMN IF NOT EXISTS saldo_previsto NUMERIC(14,2) NOT NULL DEFAULT 0.00,
  -- auditoria / multi-user (caso já não exista)
  ADD COLUMN IF NOT EXISTS user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Índice para listagem por usuário
CREATE INDEX IF NOT EXISTS idx_contas_user_id ON public.contas(user_id);


-- -----------------------------------------------------------------------------
-- 2. CATEGORIAS — enriquecer com tipo, cor, ícone e hierarquia
-- -----------------------------------------------------------------------------
ALTER TABLE public.categorias
  ADD COLUMN IF NOT EXISTS tipo         TEXT NOT NULL DEFAULT 'despesa'
      CHECK (tipo IN ('receita','despesa','ambos')),
  ADD COLUMN IF NOT EXISTS cor          TEXT NOT NULL DEFAULT '#6366F1',
  ADD COLUMN IF NOT EXISTS icone        TEXT NOT NULL DEFAULT 'category',
  ADD COLUMN IF NOT EXISTS user_id      UUID REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_categorias_user_id ON public.categorias(user_id);


-- -----------------------------------------------------------------------------
-- 3. SUBCATEGORIAS — nova tabela filha de categorias
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.subcategorias (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  categoria_id  UUID NOT NULL REFERENCES public.categorias(id) ON DELETE CASCADE,
  user_id       UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  nome          TEXT NOT NULL,
  cor           TEXT NOT NULL DEFAULT '#94A3B8',
  ativo         BOOLEAN NOT NULL DEFAULT TRUE,
  criado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_subcategorias_categoria ON public.subcategorias(categoria_id);


-- -----------------------------------------------------------------------------
-- 4. LANCAMENTOS — adicionar colunas para cartão, fatura, parcelas e importação
-- -----------------------------------------------------------------------------
ALTER TABLE public.lancamentos
  -- ligação a cartão de crédito (NULL se for conta bancária)
  ADD COLUMN IF NOT EXISTS cartao_id         UUID,  -- FK adicionada depois de criar a tabela
  ADD COLUMN IF NOT EXISTS fatura_id         UUID,  -- FK adicionada depois de criar a tabela
  -- subcategoria
  ADD COLUMN IF NOT EXISTS subcategoria_id   UUID REFERENCES public.subcategorias(id) ON DELETE SET NULL,
  -- parcelas: este lançamento pode ser filho de um pai
  ADD COLUMN IF NOT EXISTS lancamento_pai_id UUID REFERENCES public.lancamentos(id) ON DELETE SET NULL,
  -- importação CSV / Mobills (deduplicação)
  ADD COLUMN IF NOT EXISTS external_id       TEXT,   -- ex: "mobills_1234567"
  ADD COLUMN IF NOT EXISTS fonte_importacao  TEXT NOT NULL DEFAULT 'manual'
      CHECK (fonte_importacao IN ('manual','csv_mobills','csv_generic','api')),
  -- multi-user guard
  ADD COLUMN IF NOT EXISTS user_id           UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- Índice de deduplicação na importação
CREATE UNIQUE INDEX IF NOT EXISTS idx_lancamentos_external_id
  ON public.lancamentos(user_id, external_id)
  WHERE external_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_lancamentos_user_id    ON public.lancamentos(user_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_data        ON public.lancamentos(data DESC);
CREATE INDEX IF NOT EXISTS idx_lancamentos_cartao      ON public.lancamentos(cartao_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_fatura      ON public.lancamentos(fatura_id);


-- -----------------------------------------------------------------------------
-- 5. DESTINOS — garantir user_id (se ainda não tiver)
-- -----------------------------------------------------------------------------
ALTER TABLE public.destinos
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_destinos_user_id ON public.destinos(user_id);


-- =============================================================================
-- COMENTÁRIOS DE SEGURANÇA (RLS — Row Level Security)
-- Se o seu projeto usa RLS, aplique políticas nestes novos campos também.
-- Exemplo para subcategorias:
-- ALTER TABLE public.subcategorias ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "user_own_subcategorias" ON public.subcategorias
--   USING (user_id = auth.uid());
-- =============================================================================
