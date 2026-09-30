-- =============================================================================
-- DemBase v3 — Migração 004
-- Ajuste e Unificação de Políticas de Segurança RLS para Categorias e Subcategorias
-- Execute no SQL Editor do Supabase (schema: public)
-- =============================================================================

-- 1. Garante que as colunas user_id e perfil_id existam com os tipos corretos
ALTER TABLE public.categorias
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
  ADD COLUMN IF NOT EXISTS perfil_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

ALTER TABLE public.subcategorias
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE;

-- 2. Habilita RLS
ALTER TABLE public.categorias ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subcategorias ENABLE ROW LEVEL SECURITY;

-- 3. Limpa políticas antigas ou conflituosas em categorias
DROP POLICY IF EXISTS "Users can manage own categories" ON public.categorias;
DROP POLICY IF EXISTS "Gerenciar categorias" ON public.categorias;
DROP POLICY IF EXISTS "Categorias do usuario" ON public.categorias;

-- Cria política permissiva e segura validando tanto auth.uid() = user_id quanto perfil_id
CREATE POLICY "Gerenciar categorias" ON public.categorias
FOR ALL
USING (auth.uid() = user_id OR auth.uid() = perfil_id)
WITH CHECK (auth.uid() = user_id OR auth.uid() = perfil_id);

-- 4. Limpa políticas antigas em subcategorias
DROP POLICY IF EXISTS "user_own_subcategorias" ON public.subcategorias;
DROP POLICY IF EXISTS "Gerenciar subcategorias" ON public.subcategorias;
DROP POLICY IF EXISTS "Subcategorias do usuario" ON public.subcategorias;

-- Cria política para subcategorias
CREATE POLICY "Gerenciar subcategorias" ON public.subcategorias
FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);
