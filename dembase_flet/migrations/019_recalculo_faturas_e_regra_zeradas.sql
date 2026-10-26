-- =============================================================================
-- Migration 019: Recálculo Estrito de Faturas e Regra de Negócio de Faturas Zeradas
-- 1. Recalcula o valor_total de cada fatura de Outubro/2026 refletindo estritamente
--    a soma das despesas vinculadas, sem valores fantasmas.
-- 2. Mantém o status das faturas de Outubro/2026 como 'paga' com valor_pago = valor_total.
-- 3. Regra de Negócio: Faturas com valor zerado (R$ 0,00) são automaticamente classificadas
--    como 'paga' (ou concluída), saindo da lista de pendências.
-- 4. Cria trigger BEFORE INSERT OR UPDATE na tabela public.faturas para que faturas com
--    valor_total <= 0.01 assumam automaticamente status = 'paga'.
-- 5. NENHUMA alteração é feita no saldo atual de contas bancárias.
-- =============================================================================

-- 1. Recalcula o valor_total exato das faturas de Outubro/2026
UPDATE public.faturas f
SET valor_total = COALESCE((
    SELECT SUM(l.valor)
    FROM public.lancamentos l
    WHERE l.fatura_id = f.id
      AND l.tipo = 'Despesa'
), 0)
WHERE f.mes = 10 AND f.ano = 2026;

-- 2. Garante status 'paga' e valor_pago igual ao valor_total exato em Outubro/2026
UPDATE public.faturas
SET status = 'paga',
    valor_pago = valor_total,
    data_pagamento = COALESCE(data_pagamento, '2026-10-31')
WHERE mes = 10 AND ano = 2026;

-- 3. Regra de Negócio: Faturas com valor zerado são automaticamente 'paga'
UPDATE public.faturas
SET status = 'paga',
    valor_pago = 0.00
WHERE valor_total <= 0.01
  AND status <> 'paga';

-- 4. Função e Trigger para automatizar a classificação de faturas zeradas
CREATE OR REPLACE FUNCTION public.fn_trg_fatura_zerada_paga()
RETURNS TRIGGER AS $$
BEGIN
    IF COALESCE(NEW.valor_total, 0) <= 0.01 THEN
        NEW.status := 'paga';
        NEW.valor_pago := 0.00;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_fatura_zerada_paga ON public.faturas;
CREATE TRIGGER trg_fatura_zerada_paga
BEFORE INSERT OR UPDATE OF valor_total, status ON public.faturas
FOR EACH ROW
EXECUTE FUNCTION public.fn_trg_fatura_zerada_paga();
