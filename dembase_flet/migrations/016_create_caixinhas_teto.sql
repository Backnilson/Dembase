-- =============================================================================
-- DemBase v3 — migrations/016_create_caixinhas_teto.sql
-- Módulo de Caixinhas de Teto (Provisionamento Mensal e Ritmo de Gastos)
-- 
-- Regras de Negócio e Arquitetura:
-- 1. Provisionamento: O usuário aloca valores específicos para contas/gastos variáveis
--    (ex: gasolina da moto, feira, lazer semanal) que devem durar até uma data alvo.
-- 2. Registro Automático de Despesa Pendente: O provisionamento na caixinha é uma
--    reserva de capital (dinheiro carimbado para o futuro). O aporte gera um
--    lançamento do tipo "Despesa" (subtipo "Provisionamento", status "Pendente")
--    na data de provisão definida, compondo a previsão de gastos sem debitar o saldo real imediatamente.
-- 3. Vínculo Obrigatório aos 6 Potes & Subcategoria: Cada caixinha é um sub-nível de controle
--    vinculado a um Pote Financeiro, com Categoria e Subcategoria específicas.
-- 4. Sistema de Consumo (Esvaziando a Caixinha): Despesas diárias lançadas no app podem
--    ser vinculadas a uma Caixinha ("Vincular a uma Caixinha?"). O valor da despesa
--    abate do saldo da caixinha em tempo real (Saldo = Provisionado - Despesas Vinculadas).
-- =============================================================================

-- 1. TABELA PRINCIPAL: caixinhas_teto
CREATE TABLE IF NOT EXISTS public.caixinhas_teto (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    nome            TEXT NOT NULL,
    valor_meta      NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    saldo_atual     NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    data_provisao   DATE NOT NULL DEFAULT CURRENT_DATE,
    data_alvo       DATE,
    cor             TEXT NOT NULL DEFAULT '#10B981',
    icone           TEXT NOT NULL DEFAULT 'inventory_2',
    categoria_id    UUID REFERENCES public.categorias(id) ON DELETE SET NULL,
    subcategoria_id UUID REFERENCES public.subcategorias(id) ON DELETE SET NULL,
    pote_id         UUID REFERENCES public.potes(id) ON DELETE SET NULL,
    conta_id        UUID REFERENCES public.contas(id) ON DELETE SET NULL,
    ativo           BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Garantir colunas se a tabela já existir previamente
ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS data_provisao DATE NOT NULL DEFAULT CURRENT_DATE;

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS subcategoria_id UUID REFERENCES public.subcategorias(id) ON DELETE SET NULL;

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS pote_id UUID REFERENCES public.potes(id) ON DELETE SET NULL;

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS conta_id UUID REFERENCES public.contas(id) ON DELETE SET NULL;

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS conta_destino_id UUID REFERENCES public.contas(id) ON DELETE SET NULL;

ALTER TABLE public.caixinhas_teto
ADD COLUMN IF NOT EXISTS tipo_provisao TEXT DEFAULT 'despesa';

-- Índices de alta performance
CREATE INDEX IF NOT EXISTS idx_caixinhas_teto_user_ativo    ON public.caixinhas_teto(user_id, ativo);
CREATE INDEX IF NOT EXISTS idx_caixinhas_teto_categoria     ON public.caixinhas_teto(categoria_id);
CREATE INDEX IF NOT EXISTS idx_caixinhas_teto_subcategoria  ON public.caixinhas_teto(subcategoria_id);
CREATE INDEX IF NOT EXISTS idx_caixinhas_teto_pote          ON public.caixinhas_teto(pote_id);
CREATE INDEX IF NOT EXISTS idx_caixinhas_teto_conta         ON public.caixinhas_teto(conta_id);
CREATE INDEX IF NOT EXISTS idx_caixinhas_teto_conta_destino ON public.caixinhas_teto(conta_destino_id);
CREATE INDEX IF NOT EXISTS idx_caixinhas_teto_data_provisao ON public.caixinhas_teto(data_provisao);

-- 2. TABELA DE MOVIMENTAÇÕES / HISTÓRICO: caixinhas_teto_movimentacoes
CREATE TABLE IF NOT EXISTS public.caixinhas_teto_movimentacoes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caixinha_id     UUID NOT NULL REFERENCES public.caixinhas_teto(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tipo            TEXT NOT NULL CHECK (tipo IN ('injecao', 'deducao', 'ajuste')),
    valor           NUMERIC(14,2) NOT NULL,
    saldo_anterior  NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    saldo_posterior NUMERIC(14,2) NOT NULL DEFAULT 0.00,
    descricao       TEXT,
    data            DATE NOT NULL DEFAULT CURRENT_DATE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.caixinhas_teto_movimentacoes
ADD COLUMN IF NOT EXISTS lancamento_id UUID REFERENCES public.lancamentos(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_caixinhas_mov_lancamento_id ON public.caixinhas_teto_movimentacoes(lancamento_id);

CREATE INDEX IF NOT EXISTS idx_caixinhas_mov_caixinha_id ON public.caixinhas_teto_movimentacoes(caixinha_id);
CREATE INDEX IF NOT EXISTS idx_caixinhas_mov_user_data   ON public.caixinhas_teto_movimentacoes(user_id, data DESC);

-- 3. VINCULAÇÃO EM LANÇAMENTOS
ALTER TABLE public.lancamentos 
ADD COLUMN IF NOT EXISTS caixinha_id UUID REFERENCES public.caixinhas_teto(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_lancamentos_caixinha_id ON public.lancamentos(caixinha_id);

-- 4. TRIGGER: Atualização automática de atualizado_em
CREATE OR REPLACE FUNCTION public.fn_caixinhas_teto_atualizado_em()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.atualizado_em = NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_caixinhas_teto_atualizado_em ON public.caixinhas_teto;
CREATE TRIGGER trg_caixinhas_teto_atualizado_em
BEFORE UPDATE ON public.caixinhas_teto
FOR EACH ROW EXECUTE FUNCTION public.fn_caixinhas_teto_atualizado_em();

-- 5. SEGURANÇA: Row Level Security (RLS)
ALTER TABLE public.caixinhas_teto ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.caixinhas_teto_movimentacoes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Usuários gerenciam suas próprias caixinhas" ON public.caixinhas_teto;
CREATE POLICY "Usuários gerenciam suas próprias caixinhas"
ON public.caixinhas_teto
FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "Usuários gerenciam suas próprias movimentações de caixinhas" ON public.caixinhas_teto_movimentacoes;
CREATE POLICY "Usuários gerenciam suas próprias movimentações de caixinhas"
ON public.caixinhas_teto_movimentacoes
FOR ALL
USING (auth.uid() = user_id)
WITH CHECK (auth.uid() = user_id);

-- 6. RPC: Injetar Saldo na Caixinha (Provisionar)
CREATE OR REPLACE FUNCTION public.injetar_saldo_caixinha(
    p_caixinha_id UUID,
    p_valor NUMERIC,
    p_descricao TEXT DEFAULT ''
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id   UUID := auth.uid();
    v_anterior  NUMERIC;
    v_posterior NUMERIC;
    v_caixinha  RECORD;
BEGIN
    IF p_valor <= 0 THEN
        RAISE EXCEPTION 'O valor a injetar deve ser maior que zero.';
    END IF;

    SELECT * INTO v_caixinha
    FROM public.caixinhas_teto
    WHERE id = p_caixinha_id AND (v_user_id IS NULL OR user_id = v_user_id)
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN JSONB_BUILD_OBJECT('erro', 'Caixinha não encontrada');
    END IF;

    v_anterior := COALESCE(v_caixinha.saldo_atual, 0);
    v_posterior := v_anterior + p_valor;

    UPDATE public.caixinhas_teto
    SET saldo_atual = v_posterior
    WHERE id = p_caixinha_id;

    INSERT INTO public.caixinhas_teto_movimentacoes (
        caixinha_id, user_id, tipo, valor, saldo_anterior, saldo_posterior, descricao
    ) VALUES (
        p_caixinha_id, v_caixinha.user_id, 'injecao', p_valor, v_anterior, v_posterior, COALESCE(p_descricao, 'Aporte de saldo')
    );

    RETURN JSONB_BUILD_OBJECT(
        'sucesso', true,
        'caixinha_id', p_caixinha_id,
        'saldo_anterior', v_anterior,
        'saldo_atual', v_posterior,
        'valor_injetado', p_valor
    );
END;
$$;

-- 7. RPC: Deduzir / Gastar da Caixinha
CREATE OR REPLACE FUNCTION public.deduzir_saldo_caixinha(
    p_caixinha_id UUID,
    p_valor NUMERIC,
    p_descricao TEXT DEFAULT ''
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_user_id   UUID := auth.uid();
    v_anterior  NUMERIC;
    v_posterior NUMERIC;
    v_caixinha  RECORD;
BEGIN
    IF p_valor <= 0 THEN
        RAISE EXCEPTION 'O valor a deduzir deve ser maior que zero.';
    END IF;

    SELECT * INTO v_caixinha
    FROM public.caixinhas_teto
    WHERE id = p_caixinha_id AND (v_user_id IS NULL OR user_id = v_user_id)
    FOR UPDATE;

    IF NOT FOUND THEN
        RETURN JSONB_BUILD_OBJECT('erro', 'Caixinha não encontrada');
    END IF;

    v_anterior := COALESCE(v_caixinha.saldo_atual, 0);
    v_posterior := GREATEST(0.00, v_anterior - p_valor);

    UPDATE public.caixinhas_teto
    SET saldo_atual = v_posterior
    WHERE id = p_caixinha_id;

    INSERT INTO public.caixinhas_teto_movimentacoes (
        caixinha_id, user_id, tipo, valor, saldo_anterior, saldo_posterior, descricao
    ) VALUES (
        p_caixinha_id, v_caixinha.user_id, 'deducao', p_valor, v_anterior, v_posterior, COALESCE(p_descricao, 'Gasto registrado')
    );

    RETURN JSONB_BUILD_OBJECT(
        'sucesso', true,
        'caixinha_id', p_caixinha_id,
        'saldo_anterior', v_anterior,
        'saldo_atual', v_posterior,
        'valor_deduzido', p_valor
    );
END;
$$;

-- 8. RPC: Recalcular Saldo da Caixinha em Tempo Real (Provisionado - Despesas Vinculadas)
CREATE OR REPLACE FUNCTION public.fn_recalcular_saldo_caixinha(p_caixinha_id UUID)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_caixinha        RECORD;
    v_total_injecoes  NUMERIC := 0;
    v_total_despesas  NUMERIC := 0;
    v_saldo_calculado NUMERIC := 0;
BEGIN
    SELECT * INTO v_caixinha
    FROM public.caixinhas_teto
    WHERE id = p_caixinha_id;

    IF NOT FOUND THEN
        RETURN JSONB_BUILD_OBJECT('erro', 'Caixinha não encontrada');
    END IF;

    -- Soma de todas as injeções de saldo registradas na caixinha
    SELECT COALESCE(SUM(valor), 0) INTO v_total_injecoes
    FROM public.caixinhas_teto_movimentacoes
    WHERE caixinha_id = p_caixinha_id AND tipo = 'injecao';

    -- Soma de todas as deduções manuais registradas na caixinha
    SELECT COALESCE(SUM(valor), 0) INTO v_total_deducoes
    FROM public.caixinhas_teto_movimentacoes
    WHERE caixinha_id = p_caixinha_id AND tipo = 'deducao';

    -- Soma de todas as despesas diárias vinculadas a essa caixinha
    -- Exclui lançamentos com subtipo 'Provisionamento' para não computar o próprio aporte como despesa de consumo
    SELECT COALESCE(SUM(valor), 0) INTO v_total_despesas
    FROM public.lancamentos
    WHERE caixinha_id = p_caixinha_id
      AND tipo = 'Despesa'
      AND (subtipo IS NULL OR LOWER(subtipo) <> 'provisionamento');

    -- Saldo atual = Total Injetado - Total Deduzido - Despesas Vinculadas
    -- Se não houve injeção (caixinha recém criada vazia), saldo_calculado é 0.00
    v_saldo_calculado := GREATEST(0.00, v_total_injecoes - v_total_deducoes - v_total_despesas);

    UPDATE public.caixinhas_teto
    SET saldo_atual = v_saldo_calculado
    WHERE id = p_caixinha_id;

    RETURN JSONB_BUILD_OBJECT(
        'sucesso', true,
        'caixinha_id', p_caixinha_id,
        'valor_provisionado', v_total_injecoes,
        'total_despesas_vinculadas', v_total_despesas,
        'saldo_atual', v_saldo_calculado
    );
END;
$$;

-- Trigger para recalcular automaticamente o saldo da caixinha ao inserir, alterar ou deletar despesas ou movimentações
CREATE OR REPLACE FUNCTION public.fn_trg_recalcular_caixinha()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.caixinha_id IS NOT NULL THEN
            PERFORM public.fn_recalcular_saldo_caixinha(OLD.caixinha_id);
        END IF;
        RETURN OLD;
    ELSE
        IF NEW.caixinha_id IS NOT NULL THEN
            PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);
        END IF;
        IF TG_OP = 'UPDATE' AND OLD.caixinha_id IS NOT NULL AND OLD.caixinha_id <> NEW.caixinha_id THEN
            PERFORM public.fn_recalcular_saldo_caixinha(OLD.caixinha_id);
        END IF;
        RETURN NEW;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_lancamentos_recalcular_caixinha ON public.lancamentos;
CREATE TRIGGER trg_lancamentos_recalcular_caixinha
AFTER INSERT OR UPDATE OR DELETE ON public.lancamentos
FOR EACH ROW
EXECUTE FUNCTION public.fn_trg_recalcular_caixinha();

DROP TRIGGER IF EXISTS trg_movimentacoes_recalcular_caixinha ON public.caixinhas_teto_movimentacoes;
CREATE TRIGGER trg_movimentacoes_recalcular_caixinha
AFTER INSERT OR UPDATE OR DELETE ON public.caixinhas_teto_movimentacoes
FOR EACH ROW
EXECUTE FUNCTION public.fn_trg_recalcular_caixinha();

-- Trigger para sincronizar pagamento de provisionamento (Pendente -> Pago enche a caixinha)
CREATE OR REPLACE FUNCTION public.fn_trg_sincronizar_provisionamento_caixinha()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_anterior NUMERIC;
BEGIN
    -- CASO 1: Lançamento de provisionamento foi pago (Pendente -> Pago, ou criado direto como Pago)
    IF (TG_OP = 'INSERT' AND NEW.status = 'Pago' AND LOWER(COALESCE(NEW.subtipo, '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL)
       OR (TG_OP = 'UPDATE' AND (OLD.status IS NULL OR OLD.status <> 'Pago') AND NEW.status = 'Pago' AND LOWER(COALESCE(NEW.subtipo, '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL) THEN
        
        -- Garante que não duplica se já houver injeção vinculada a este lançamento
        IF NOT EXISTS (
            SELECT 1 FROM public.caixinhas_teto_movimentacoes
            WHERE lancamento_id = NEW.id
        ) THEN
            SELECT COALESCE(saldo_atual, 0) INTO v_anterior
            FROM public.caixinhas_teto WHERE id = NEW.caixinha_id;

            INSERT INTO public.caixinhas_teto_movimentacoes (
                caixinha_id, user_id, tipo, valor, saldo_anterior, saldo_posterior, descricao, data, lancamento_id
            ) VALUES (
                NEW.caixinha_id, NEW.user_id, 'injecao', NEW.valor, v_anterior, v_anterior + NEW.valor,
                COALESCE(NEW.descricao, 'Efetivação de Provisão'), NEW.data, NEW.id
            );

            PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);
        END IF;

    -- CASO 2: Lançamento de provisionamento voltou para Pendente (ou estornado)
    ELSIF TG_OP = 'UPDATE' AND OLD.status = 'Pago' AND NEW.status <> 'Pago' AND LOWER(COALESCE(NEW.subtipo, '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL THEN
        DELETE FROM public.caixinhas_teto_movimentacoes
        WHERE lancamento_id = NEW.id;

        PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);

    -- CASO 3: Lançamento de provisionamento foi excluído
    ELSIF TG_OP = 'DELETE' AND OLD.caixinha_id IS NOT NULL AND LOWER(COALESCE(OLD.subtipo, '')) = 'provisionamento' THEN
        DELETE FROM public.caixinhas_teto_movimentacoes
        WHERE lancamento_id = OLD.id;

        PERFORM public.fn_recalcular_saldo_caixinha(OLD.caixinha_id);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$$;

DROP TRIGGER IF EXISTS trg_provisionamento_sincronizar_caixinha ON public.lancamentos;
CREATE TRIGGER trg_provisionamento_sincronizar_caixinha
AFTER INSERT OR UPDATE OR DELETE ON public.lancamentos
FOR EACH ROW
EXECUTE FUNCTION public.fn_trg_sincronizar_provisionamento_caixinha();

-- 10. RECORRÊNCIA MENSAL DE CAIXINHAS E SINCRONIZAÇÃO AUTOMÁTICA DE PROVISÕES
ALTER TABLE public.caixinhas_teto ADD COLUMN IF NOT EXISTS recorrente BOOLEAN DEFAULT FALSE;
ALTER TABLE public.caixinhas_teto ADD COLUMN IF NOT EXISTS dia_recorrencia SMALLINT DEFAULT 5;

CREATE OR REPLACE FUNCTION public.fn_sincronizar_provisoes_caixinha(
    p_caixinha_id UUID,
    p_meses INT DEFAULT 12
)
RETURNS INT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
    v_cx RECORD;
    v_inicio DATE;
    v_dt DATE;
    v_ano INT;
    v_mes INT;
    v_dia INT;
    v_ult_dia INT;
    v_criados INT := 0;
    v_max_iter INT;
    i INT;
BEGIN
    SELECT * INTO v_cx FROM public.caixinhas_teto WHERE id = p_caixinha_id;
    IF NOT FOUND OR v_cx.ativo = FALSE OR v_cx.conta_id IS NULL THEN
        DELETE FROM public.lancamentos
        WHERE caixinha_id = p_caixinha_id
          AND status = 'Pendente'
          AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
        RETURN 0;
    END IF;

    v_dia := COALESCE(v_cx.dia_recorrencia, EXTRACT(DAY FROM COALESCE(v_cx.data_provisao, CURRENT_DATE))::INT, 5);
    v_inicio := COALESCE(v_cx.data_provisao, CURRENT_DATE);

    IF v_cx.recorrente = TRUE THEN
        v_max_iter := GREATEST(1, p_meses);
    ELSE
        v_max_iter := 1;
        DELETE FROM public.lancamentos
        WHERE caixinha_id = p_caixinha_id
          AND status = 'Pendente'
          AND data > v_inicio
          AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
    END IF;

    FOR i IN 0..(v_max_iter - 1) LOOP
        v_ano := EXTRACT(YEAR FROM (v_inicio + (i || ' month')::interval))::INT;
        v_mes := EXTRACT(MONTH FROM (v_inicio + (i || ' month')::interval))::INT;
        v_ult_dia := EXTRACT(DAY FROM (DATE(v_ano || '-' || LPAD(v_mes::TEXT, 2, '0') || '-01') + INTERVAL '1 month' - INTERVAL '1 day'))::INT;
        v_dt := DATE(v_ano || '-' || LPAD(v_mes::TEXT, 2, '0') || '-' || LPAD(LEAST(v_dia, v_ult_dia)::TEXT, 2, '0'));

        IF NOT EXISTS (
            SELECT 1 FROM public.lancamentos
            WHERE caixinha_id = p_caixinha_id
              AND EXTRACT(YEAR FROM data) = v_ano
              AND EXTRACT(MONTH FROM data) = v_mes
              AND LOWER(COALESCE(subtipo, '')) = 'provisionamento'
        ) THEN
            INSERT INTO public.lancamentos (
                user_id, perfil_id, tipo, subtipo, forma_movimentacao,
                conta_id, categoria_id, subcategoria_id, pote_id,
                valor, data, descricao, status, caixinha_id, tipo_recorrencia
            ) VALUES (
                v_cx.user_id, v_cx.user_id, 'Despesa', 'Provisionamento', 'Débito',
                v_cx.conta_id, v_cx.categoria_id, v_cx.subcategoria_id, v_cx.pote_id,
                v_cx.valor_meta, v_dt, 'Provisão Caixinha · ' || v_cx.nome, 'Pendente',
                p_caixinha_id, CASE WHEN v_cx.recorrente THEN 'fixa' ELSE 'unica' END
            );
            v_criados := v_criados + 1;
        ELSE
            UPDATE public.lancamentos
            SET valor = v_cx.valor_meta,
                conta_id = v_cx.conta_id,
                categoria_id = v_cx.categoria_id,
                subcategoria_id = v_cx.subcategoria_id,
                pote_id = v_cx.pote_id,
                descricao = 'Provisão Caixinha · ' || v_cx.nome,
                data = v_dt,
                tipo_recorrencia = CASE WHEN v_cx.recorrente THEN 'fixa' ELSE 'unica' END
            WHERE caixinha_id = p_caixinha_id
              AND EXTRACT(YEAR FROM data) = v_ano
              AND EXTRACT(MONTH FROM data) = v_mes
              AND status = 'Pendente'
              AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
        END IF;
    END LOOP;

    RETURN v_criados;
END;
$$;

CREATE OR REPLACE FUNCTION public.fn_trg_caixinhas_teto_sincronizar_provisoes()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        DELETE FROM public.lancamentos
        WHERE caixinha_id = OLD.id
          AND status = 'Pendente'
          AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
        RETURN OLD;
    ELSE
        PERFORM public.fn_sincronizar_provisoes_caixinha(NEW.id, 12);
        RETURN NEW;
    END IF;
END;
$$;

DROP TRIGGER IF EXISTS trg_caixinhas_teto_sincronizar_provisoes ON public.caixinhas_teto;
CREATE TRIGGER trg_caixinhas_teto_sincronizar_provisoes
AFTER INSERT OR UPDATE OF valor_meta, data_provisao, conta_id, categoria_id, subcategoria_id, pote_id, ativo, recorrente, dia_recorrencia
ON public.caixinhas_teto
FOR EACH ROW
EXECUTE FUNCTION public.fn_trg_caixinhas_teto_sincronizar_provisoes();

-- Notificar o PostgREST para recarregar o schema cache imediatamente
NOTIFY pgrst, 'reload schema';
