-- =============================================================================
-- DemBase v3 — Migração 028: Multi-Perfis Familiares ("Eu, Ela & Nós")
-- =============================================================================
-- Conceito: dentro de UMA conta de usuário (auth.users) existem N "membros"
-- (Denilson = principal, Erika, ...). Contas, cartões, caixinhas e lançamentos
-- passam a pertencer a um membro (coluna membro_id).
--
-- NOTA: a coluna legada `perfil_id` (FK -> auth.users) NÃO é tocada; ela
-- representa o dono da conta de login, não o membro familiar.
--
-- Visão ativa: tabela `visao_ativa` guarda quais membros estão selecionados
-- (NULL = Casa / todos). As RPCs de leitura consultam fn_membro_visivel()
-- e, portanto, recalculam tudo (KPIs, potes, calendário...) no PostgreSQL.
--
-- ZERO PERDA DE DADOS: somente colunas NULLable novas + backfill para o
-- membro principal. Nenhum registro é removido ou alterado em valor.
-- =============================================================================

-- 1. Tabela de membros ---------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.membros (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    nome          TEXT NOT NULL CHECK (char_length(btrim(nome)) BETWEEN 1 AND 40),
    cor           TEXT NOT NULL DEFAULT '#6366F1',
    icone         TEXT NOT NULL DEFAULT 'person',
    principal     BOOLEAN NOT NULL DEFAULT FALSE,
    ativo         BOOLEAN NOT NULL DEFAULT TRUE,
    ordem         INTEGER NOT NULL DEFAULT 0,
    criado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_membros_principal_por_usuario
    ON public.membros (user_id) WHERE principal;
CREATE INDEX IF NOT EXISTS ix_membros_user ON public.membros (user_id);

ALTER TABLE public.membros ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS membros_dono ON public.membros;
CREATE POLICY membros_dono ON public.membros
    FOR ALL
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

CREATE OR REPLACE FUNCTION public.fn_trg_membros_guarda()
RETURNS trigger LANGUAGE plpgsql SET search_path = public AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        IF OLD.principal THEN
            RAISE EXCEPTION 'O perfil principal não pode ser excluído.';
        END IF;
        RETURN OLD;
    END IF;
    NEW.atualizado_em := now();
    IF TG_OP = 'UPDATE' AND OLD.principal AND NOT NEW.principal THEN
        RAISE EXCEPTION 'O perfil principal não pode deixar de ser principal.';
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.principal AND NOT NEW.ativo THEN
        RAISE EXCEPTION 'O perfil principal não pode ser desativado.';
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_membros_guarda ON public.membros;
CREATE TRIGGER trg_membros_guarda
    BEFORE UPDATE OR DELETE ON public.membros
    FOR EACH ROW EXECUTE FUNCTION public.fn_trg_membros_guarda();

-- 2. Visão ativa -----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.visao_ativa (
    user_id       UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    membro_ids    UUID[],               -- NULL = Casa (todos os membros)
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
ALTER TABLE public.visao_ativa ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS visao_ativa_dono ON public.visao_ativa;
CREATE POLICY visao_ativa_dono ON public.visao_ativa
    FOR ALL
    USING (user_id = (SELECT auth.uid()))
    WITH CHECK (user_id = (SELECT auth.uid()));

-- 3. Membro principal (idempotente) ------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_garantir_membro_principal(p_user UUID)
RETURNS UUID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_id   UUID;
    v_nome TEXT;
BEGIN
    IF p_user IS NULL THEN
        RETURN NULL;
    END IF;
    SELECT id INTO v_id FROM public.membros WHERE user_id = p_user AND principal;
    IF v_id IS NOT NULL THEN
        RETURN v_id;
    END IF;
    SELECT NULLIF(btrim(split_part(nome, ' ', 1)), '') INTO v_nome
      FROM public.perfis WHERE id = p_user;
    INSERT INTO public.membros (user_id, nome, cor, icone, principal, ordem)
    VALUES (p_user, COALESCE(v_nome, 'Eu'), '#6366F1', 'person', TRUE, 0)
    ON CONFLICT DO NOTHING;
    SELECT id INTO v_id FROM public.membros WHERE user_id = p_user AND principal;
    RETURN v_id;
END $$;

-- 4. Colunas membro_id -----------------------------------------------------------------
ALTER TABLE public.lancamentos    ADD COLUMN IF NOT EXISTS membro_id UUID REFERENCES public.membros(id) ON DELETE RESTRICT;
ALTER TABLE public.contas         ADD COLUMN IF NOT EXISTS membro_id UUID REFERENCES public.membros(id) ON DELETE RESTRICT;
ALTER TABLE public.cartoes        ADD COLUMN IF NOT EXISTS membro_id UUID REFERENCES public.membros(id) ON DELETE RESTRICT;
ALTER TABLE public.caixinhas_teto ADD COLUMN IF NOT EXISTS membro_id UUID REFERENCES public.membros(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS ix_lancamentos_membro    ON public.lancamentos (membro_id);
CREATE INDEX IF NOT EXISTS ix_contas_membro         ON public.contas (membro_id);
CREATE INDEX IF NOT EXISTS ix_cartoes_membro        ON public.cartoes (membro_id);
CREATE INDEX IF NOT EXISTS ix_caixinhas_teto_membro ON public.caixinhas_teto (membro_id);

-- 5. Trigger: todo INSERT sem membro_id herda o dono lógico ----------------------------
--    Ordem de inferência (lançamentos): caixinha -> cartão -> conta -> principal.
CREATE OR REPLACE FUNCTION public.fn_trg_membro_padrao()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid UUID;
    v_m   UUID;
BEGIN
    IF NEW.membro_id IS NOT NULL THEN
        RETURN NEW;
    END IF;
    v_uid := COALESCE(NEW.user_id, auth.uid());
    IF TG_TABLE_NAME = 'lancamentos' THEN
        IF NEW.caixinha_id IS NOT NULL THEN
            SELECT membro_id INTO v_m FROM public.caixinhas_teto WHERE id = NEW.caixinha_id;
        END IF;
        IF v_m IS NULL AND NEW.cartao_id IS NOT NULL THEN
            SELECT membro_id INTO v_m FROM public.cartoes WHERE id = NEW.cartao_id;
        END IF;
        IF v_m IS NULL AND NEW.conta_id IS NOT NULL THEN
            SELECT membro_id INTO v_m FROM public.contas WHERE id = NEW.conta_id;
        END IF;
    END IF;
    IF v_m IS NULL THEN
        v_m := public.fn_garantir_membro_principal(v_uid);
    END IF;
    NEW.membro_id := v_m;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_a_membro_padrao ON public.lancamentos;
CREATE TRIGGER trg_a_membro_padrao BEFORE INSERT ON public.lancamentos
    FOR EACH ROW EXECUTE FUNCTION public.fn_trg_membro_padrao();
DROP TRIGGER IF EXISTS trg_a_membro_padrao ON public.contas;
CREATE TRIGGER trg_a_membro_padrao BEFORE INSERT ON public.contas
    FOR EACH ROW EXECUTE FUNCTION public.fn_trg_membro_padrao();
DROP TRIGGER IF EXISTS trg_a_membro_padrao ON public.cartoes;
CREATE TRIGGER trg_a_membro_padrao BEFORE INSERT ON public.cartoes
    FOR EACH ROW EXECUTE FUNCTION public.fn_trg_membro_padrao();
DROP TRIGGER IF EXISTS trg_a_membro_padrao ON public.caixinhas_teto;
CREATE TRIGGER trg_a_membro_padrao BEFORE INSERT ON public.caixinhas_teto
    FOR EACH ROW EXECUTE FUNCTION public.fn_trg_membro_padrao();

-- 6. BACKFILL: 100% dos registros atuais -> membro principal -----------------------------
--    Triggers de usuário são suspensos para não recalcular saldos nem alterar
--    `atualizado_em` (apenas a nova coluna é preenchida).
ALTER TABLE public.lancamentos    DISABLE TRIGGER USER;
ALTER TABLE public.contas         DISABLE TRIGGER USER;
ALTER TABLE public.cartoes        DISABLE TRIGGER USER;
ALTER TABLE public.caixinhas_teto DISABLE TRIGGER USER;

DO $bf$
DECLARE
    r        RECORD;
    v_m      UUID;
BEGIN
    FOR r IN
        SELECT uid FROM (
            SELECT id AS uid FROM public.perfis
            UNION SELECT user_id FROM public.lancamentos    WHERE user_id IS NOT NULL
            UNION SELECT perfil_id FROM public.lancamentos  WHERE perfil_id IS NOT NULL
            UNION SELECT user_id FROM public.contas         WHERE user_id IS NOT NULL
            UNION SELECT user_id FROM public.cartoes        WHERE user_id IS NOT NULL
            UNION SELECT user_id FROM public.caixinhas_teto WHERE user_id IS NOT NULL
        ) u WHERE uid IN (SELECT id FROM auth.users)
    LOOP
        v_m := public.fn_garantir_membro_principal(r.uid);
        UPDATE public.contas         SET membro_id = v_m WHERE membro_id IS NULL AND COALESCE(user_id, perfil_id) = r.uid;
        UPDATE public.cartoes        SET membro_id = v_m WHERE membro_id IS NULL AND user_id = r.uid;
        UPDATE public.caixinhas_teto SET membro_id = v_m WHERE membro_id IS NULL AND user_id = r.uid;
        UPDATE public.lancamentos    SET membro_id = v_m WHERE membro_id IS NULL AND COALESCE(user_id, perfil_id) = r.uid;
    END LOOP;

    -- Auditoria interna: nenhum registro pode ficar órfão de membro.
    IF EXISTS (SELECT 1 FROM public.lancamentos WHERE membro_id IS NULL)
       OR EXISTS (SELECT 1 FROM public.contas WHERE membro_id IS NULL)
       OR EXISTS (SELECT 1 FROM public.cartoes WHERE membro_id IS NULL)
       OR EXISTS (SELECT 1 FROM public.caixinhas_teto WHERE membro_id IS NULL) THEN
        RAISE EXCEPTION 'Backfill incompleto: existem registros sem membro_id (migração revertida).';
    END IF;
END $bf$;

ALTER TABLE public.lancamentos    ENABLE TRIGGER USER;
ALTER TABLE public.contas         ENABLE TRIGGER USER;
ALTER TABLE public.cartoes        ENABLE TRIGGER USER;
ALTER TABLE public.caixinhas_teto ENABLE TRIGGER USER;

-- 7. Filtro de visão usado pelas RPCs --------------------------------------------------------
CREATE OR REPLACE FUNCTION public.fn_membro_visivel(p_membro UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT COALESCE(
        (SELECT va.membro_ids IS NULL
                OR cardinality(va.membro_ids) = 0
                OR p_membro IS NULL
                OR p_membro = ANY (va.membro_ids)
           FROM public.visao_ativa va
          WHERE va.user_id = auth.uid()),
        TRUE);
$$;

CREATE OR REPLACE FUNCTION public.definir_visao_membros(p_membro_ids UUID[] DEFAULT NULL)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid   UUID := auth.uid();
    v_ids   UUID[];
    v_total INT;
BEGIN
    IF v_uid IS NULL THEN
        RAISE EXCEPTION 'Sessão inválida.';
    END IF;
    PERFORM public.fn_garantir_membro_principal(v_uid);

    IF p_membro_ids IS NOT NULL AND cardinality(p_membro_ids) > 0 THEN
        SELECT array_agg(id ORDER BY ordem, criado_em) INTO v_ids
          FROM public.membros
         WHERE user_id = v_uid AND ativo AND id = ANY (p_membro_ids);
        IF v_ids IS NULL THEN
            RAISE EXCEPTION 'Perfil inválido ou inativo.';
        END IF;
        SELECT count(*) INTO v_total FROM public.membros WHERE user_id = v_uid AND ativo;
        IF cardinality(v_ids) >= v_total THEN
            v_ids := NULL;   -- todos selecionados == Casa
        END IF;
    ELSE
        v_ids := NULL;
    END IF;

    INSERT INTO public.visao_ativa (user_id, membro_ids, atualizado_em)
    VALUES (v_uid, v_ids, now())
    ON CONFLICT (user_id) DO UPDATE SET membro_ids = EXCLUDED.membro_ids, atualizado_em = now();

    RETURN jsonb_build_object('membro_ids', to_jsonb(v_ids), 'casa', v_ids IS NULL);
END $$;

-- 8. Reescrita CIRÚRGICA das RPCs de leitura ---------------------------------------------------
--    Parte das definições VIVAS (pg_get_functiondef) e acrescenta o predicado
--    de visão ao lado de cada filtro de dono sobre lancamentos/contas/cartoes.
--    get_relatorio_conta / get_relatorio_cartao NÃO entram: são escopadas por
--    id de conta/cartão (drill-down explícito).
DO $rw$
DECLARE
    r     RECORD;
    v_def TEXT;
    v_new TEXT;
BEGIN
    FOR r IN
        SELECT p.oid, p.proname, p.pronargs
          FROM pg_proc p
         WHERE p.pronamespace = 'public'::regnamespace
           AND p.prokind = 'f'
           AND (   p.proname IN (
                       'get_balanco_ultimos_6_meses','get_dashboard_overview','get_dashboard_periodo',
                       'get_despesas_por_categoria','get_receitas_por_categoria','get_frequencia_gastos_mes',
                       'get_lancamentos_calendario','get_lista_contas_resumo','get_resumo_contas',
                       'get_resumo_cartoes','get_potes_resumo','get_regra_50_30_20_summary',
                       'get_relatorio_lancamentos')
                OR (p.proname = 'get_calendario_financeiro_mes' AND p.pronargs = 4)
                OR (p.proname = 'get_financial_totals'          AND p.pronargs = 2))
    LOOP
        v_def := pg_get_functiondef(r.oid);
        CONTINUE WHEN v_def LIKE '%fn_membro_visivel%';   -- idempotência

        -- (a) "(x.user_id = V OR x.perfil_id = V)"  ->  acrescenta AND visão
        v_new := regexp_replace(
                    v_def,
                    '\((\w+\.)?user_id = (\w+) OR (\w+\.)?perfil_id = \2\)',
                    '\& AND public.fn_membro_visivel(\1membro_id)', 'g');

        -- (b) "x.user_id = v_user_id|v_uid" simples (sem OR perfil_id)
        --     get_potes_resumo só usa a forma (a); evita tocar a tabela potes.
        IF r.proname <> 'get_potes_resumo' THEN
            v_new := regexp_replace(
                        v_new,
                        '(\w+\.)?user_id = (v_user_id|v_uid)(?! OR)',
                        '\& AND public.fn_membro_visivel(\1membro_id)', 'g');
        END IF;

        -- (c) get_financial_totals(date,date): "WHERE perfil_id = v_uid"
        IF r.proname = 'get_financial_totals' THEN
            v_new := regexp_replace(
                        v_new,
                        'WHERE perfil_id = v_uid',
                        'WHERE perfil_id = v_uid AND public.fn_membro_visivel(membro_id)', 'g');
        END IF;

        IF v_new = v_def OR v_new NOT LIKE '%fn_membro_visivel%' THEN
            RAISE EXCEPTION 'Nenhum filtro de visão aplicado em %(%) — migração revertida.',
                r.proname, r.pronargs;
        END IF;
        EXECUTE v_new;
    END LOOP;
END $rw$;

-- 9. Cobertura Real de Sobrevivência (Meu Cofre) --------------------------------------------------
--    Meses que a Reserva de Emergência cobre: (a) só o custo do membro principal;
--    (b) custo total da casa. Custo de Vida = despesas dos potes 1 (Custos Fixos)
--    e 2 (Custos Semi Fixos) no período, por membro. NÃO depende da visão ativa.
CREATE OR REPLACE FUNCTION public.get_cobertura_reserva(
    p_data_inicio DATE,
    p_data_fim    DATE
) RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
DECLARE
    v_uid        UUID := auth.uid();
    v_reserva    NUMERIC := 0;
    v_principal  UUID;
    v_custo_prin NUMERIC := 0;
    v_custo_casa NUMERIC := 0;
    v_membros    JSONB;
BEGIN
    IF v_uid IS NULL THEN
        RETURN jsonb_build_object('erro', 'sessao_invalida');
    END IF;
    v_principal := public.fn_garantir_membro_principal(v_uid);

    SELECT COALESCE(SUM(saldo_atual), 0) INTO v_reserva
      FROM public.cofres_investimento
     WHERE user_id = v_uid AND ativo AND tipo = 'reserva_emergencia';

    SELECT COALESCE(jsonb_agg(jsonb_build_object(
               'membro_id', m.id, 'nome', m.nome, 'cor', m.cor, 'principal', m.principal,
               'custo_fixos', COALESCE(c.fixos, 0), 'custo_semi', COALESCE(c.semi, 0),
               'custo_total', COALESCE(c.fixos, 0) + COALESCE(c.semi, 0)
           ) ORDER BY m.ordem, m.criado_em), '[]'::jsonb)
      INTO v_membros
      FROM public.membros m
      LEFT JOIN (
            SELECT l.membro_id,
                   SUM(l.valor) FILTER (WHERE pt.posicao = 1) AS fixos,
                   SUM(l.valor) FILTER (WHERE pt.posicao = 2) AS semi
              FROM public.lancamentos l
              JOIN public.potes pt ON pt.id = l.pote_id
             WHERE l.user_id = v_uid
               AND lower(l.tipo) LIKE 'despesa%'
               AND pt.posicao IN (1, 2)
               AND l.data BETWEEN p_data_inicio AND p_data_fim
             GROUP BY l.membro_id
      ) c ON c.membro_id = m.id
     WHERE m.user_id = v_uid AND m.ativo;

    SELECT COALESCE(SUM((e->>'custo_total')::numeric), 0),
           COALESCE(SUM((e->>'custo_total')::numeric) FILTER (WHERE (e->>'principal')::boolean), 0)
      INTO v_custo_casa, v_custo_prin
      FROM jsonb_array_elements(v_membros) e;

    RETURN jsonb_build_object(
        'reserva_atual',     v_reserva,
        'custo_individual',  v_custo_prin,
        'custo_casa',        v_custo_casa,
        'meses_individual',  CASE WHEN v_custo_prin > 0 THEN ROUND(v_reserva / v_custo_prin, 1) END,
        'meses_casa',        CASE WHEN v_custo_casa > 0 THEN ROUND(v_reserva / v_custo_casa, 1) END,
        'membros',           v_membros
    );
END $$;

GRANT EXECUTE ON FUNCTION public.definir_visao_membros(UUID[])        TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_cobertura_reserva(DATE, DATE)    TO authenticated;
GRANT EXECUTE ON FUNCTION public.fn_membro_visivel(UUID)              TO authenticated;
