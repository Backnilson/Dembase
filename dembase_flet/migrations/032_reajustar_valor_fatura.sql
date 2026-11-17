-- =============================================================================
-- Migration 032: Reajustar Valor Total da Fatura (Ajustes Positivos e Negativos)
-- Permite lançamentos de ajuste de fatura com valor positivo (acréscimo/IOF/juros)
-- ou negativo (desconto/estorno parcial/arredondamento) em public.lancamentos.
-- =============================================================================

ALTER TABLE public.lancamentos
    DROP CONSTRAINT IF EXISTS lancamentos_valor_check;

ALTER TABLE public.lancamentos
    ADD CONSTRAINT lancamentos_valor_check CHECK (valor <> (0)::numeric);
