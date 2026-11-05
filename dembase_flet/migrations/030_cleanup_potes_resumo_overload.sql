-- =============================================================================
-- Migration 030: Eliminação de Sobrecarga Ambiguidade da RPC get_potes_resumo
-- Remove a sobrecarga legada get_potes_resumo(date, date) que causava erro
-- PGRST203 (HTTP 300 Multiple Choices) no PostgREST do Supabase, mantendo
-- exclusivamente a assinatura canônica de 3 argumentos com default.
-- =============================================================================

DROP FUNCTION IF EXISTS public.get_potes_resumo(date, date);

-- Notifica o PostgREST para recarregar o schema cache imediatamente
NOTIFY pgrst, 'reload schema';
