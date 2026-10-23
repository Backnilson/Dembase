-- =============================================================================
-- DemBase v3 — Migração 009: Sistema dinâmico de 6 POTES financeiros
-- Substitui a regra fixa 50/30/20 (lancamentos.regra permanece apenas como legado).
--
-- MODELO
--   perfis.renda_referencia ........ base de planejamento (não é receita real)
--   potes .......................... EXATAMENTE 6 por usuário (posicao 1..6).
--                                    Usuário edita nome/percentual; não cria nem apaga.
--   lancamentos.pote_id ............ DESPESA -> 1 pote (FK direta, índice p/ relatórios)
--   distribuicoes_receita .......... RECEITA -> N potes (1 linha por pote, com snapshot
--                                    do % aplicado). "Previsto" = SUM(distribuicoes).
--   "Gasto vs Previsto" = despesas.pote_id  x  distribuicoes_receita.pote_id
--
-- GARANTIAS
--   * soma dos percentuais = 100 e exatamente 6 potes: constraint trigger DEFERRED
--     (valida no COMMIT) + RPC salvar_potes() atômica.
--   * cliente (authenticated) só tem SELECT em potes: sem INSERT/UPDATE/DELETE direto.
-- Execute no SQL Editor do Supabase (schema: public). Script idempotente.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. PERFIS — renda de referência mensal
-- -----------------------------------------------------------------------------
ALTER TABLE public.perfis
  ADD COLUMN IF NOT EXISTS renda_referencia NUMERIC(14,2) NOT NULL DEFAULT 0
      CHECK (renda_referencia >= 0);

-- -----------------------------------------------------------------------------
-- 2. POTES
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.potes (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  posicao     SMALLINT NOT NULL CHECK (posicao BETWEEN 1 AND 6),
  nome        TEXT NOT NULL CHECK (char_length(btrim(nome)) BETWEEN 1 AND 40),
  percentual  NUMERIC(5,2) NOT NULL CHECK (percentual BETWEEN 0 AND 100),
  cor         TEXT NOT NULL DEFAULT '#94A3B8',
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_potes_user_posicao UNIQUE (user_id, posicao),
  -- DEFERRABLE permite trocar nomes entre potes dentro da mesma transação
  CONSTRAINT uq_potes_user_nome UNIQUE (user_id, nome) DEFERRABLE INITIALLY DEFERRED
);

CREATE INDEX IF NOT EXISTS idx_potes_user ON public.potes(user_id);

-- Atualiza timestamp
CREATE OR REPLACE FUNCTION public.fn_potes_touch()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.atualizado_em := NOW();
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_potes_touch ON public.potes;
CREATE TRIGGER trg_potes_touch BEFORE UPDATE ON public.potes
  FOR EACH ROW EXECUTE FUNCTION public.fn_potes_touch();

-- Invariante: 6 potes e soma = 100 (avaliada no COMMIT)
CREATE OR REPLACE FUNCTION public.fn_potes_valida_invariantes()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
  v_qtd   INT;
  v_soma  NUMERIC;
BEGIN
  SELECT COUNT(*), COALESCE(SUM(percentual), 0)
    INTO v_qtd, v_soma
    FROM public.potes WHERE user_id = NEW.user_id;

  IF v_qtd <> 6 THEN
    RAISE EXCEPTION 'POTES_INVALIDOS: o usuário deve possuir exatamente 6 potes (encontrados: %).', v_qtd
      USING ERRCODE = 'check_violation';
  END IF;
  IF v_soma <> 100 THEN
    RAISE EXCEPTION 'POTES_INVALIDOS: a soma dos percentuais deve ser 100%% (atual: %).', v_soma
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_potes_invariantes ON public.potes;
CREATE CONSTRAINT TRIGGER trg_potes_invariantes
  AFTER INSERT OR UPDATE ON public.potes
  DEFERRABLE INITIALLY DEFERRED
  FOR EACH ROW EXECUTE FUNCTION public.fn_potes_valida_invariantes();

-- -----------------------------------------------------------------------------
-- 3. SEED dos 6 potes padrão (idempotente)
--    Ordem: Custos Fixos, Conforto, Metas, Prazeres, Conhecimento, Liberdade Financeira
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.seed_potes_usuario(p_user UUID)
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM public.potes WHERE user_id = p_user) THEN
    RETURN;
  END IF;

  INSERT INTO public.potes (user_id, posicao, nome, percentual, cor) VALUES
    (p_user, 1, 'Custos Fixos',          30, '#007AFF'),
    (p_user, 2, 'Conforto',              15, '#FF69B4'),
    (p_user, 3, 'Metas',                 15, '#800080'),
    (p_user, 4, 'Prazeres',              10, '#FF7A00'),
    (p_user, 5, 'Conhecimento',           5, '#FFD60A'),
    (p_user, 6, 'Liberdade Financeira',  25, '#6C5CE7');
END $$;

REVOKE ALL ON FUNCTION public.seed_potes_usuario(UUID) FROM PUBLIC, anon, authenticated;

-- Novos usuários: seed automático ao criar o perfil
CREATE OR REPLACE FUNCTION public.fn_perfis_seed_potes()
RETURNS TRIGGER LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  PERFORM public.seed_potes_usuario(NEW.id);
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_perfis_seed_potes ON public.perfis;
CREATE TRIGGER trg_perfis_seed_potes AFTER INSERT ON public.perfis
  FOR EACH ROW EXECUTE FUNCTION public.fn_perfis_seed_potes();

-- Usuários existentes (backfill)
SELECT public.seed_potes_usuario(id) FROM public.perfis;

-- Auto-cura chamada pelo app (usuário logado sem potes)
CREATE OR REPLACE FUNCTION public.garantir_potes()
RETURNS VOID LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'Não autenticado.' USING ERRCODE = '28000';
  END IF;
  PERFORM public.seed_potes_usuario(auth.uid());
END $$;

-- -----------------------------------------------------------------------------
-- 4. RLS + PRIVILÉGIOS: cliente apenas LÊ potes (edição só via salvar_potes)
-- -----------------------------------------------------------------------------
ALTER TABLE public.potes ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "potes_select_own" ON public.potes;
CREATE POLICY "potes_select_own" ON public.potes
  FOR SELECT TO authenticated USING (user_id = auth.uid());

REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.potes FROM anon, authenticated;
GRANT SELECT ON public.potes TO authenticated;

-- -----------------------------------------------------------------------------
-- 5. LANÇAMENTOS — vínculo direto da despesa com o pote
-- -----------------------------------------------------------------------------
ALTER TABLE public.lancamentos
  ADD COLUMN IF NOT EXISTS pote_id UUID REFERENCES public.potes(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_lancamentos_pote_data
  ON public.lancamentos(user_id, pote_id, data DESC) WHERE pote_id IS NOT NULL;

-- Backfill das despesas legadas (regra 50/30/20 -> potes equivalentes)
UPDATE public.lancamentos l
   SET pote_id = p.id
  FROM public.potes p
 WHERE l.pote_id IS NULL
   AND l.user_id = p.user_id
   AND l.regra IS NOT NULL
   AND p.posicao = CASE l.regra
                     WHEN 'Essencial'      THEN 1  -- Custos Fixos
                     WHEN 'Estilo de Vida' THEN 2  -- Conforto
                     WHEN 'Investimento'   THEN 6  -- Liberdade Financeira
                   END;

-- -----------------------------------------------------------------------------
-- 6. DISTRIBUIÇÃO DE RECEITAS (receita -> N potes, com snapshot do %)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.distribuicoes_receita (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id              UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  lancamento_id        UUID NOT NULL REFERENCES public.lancamentos(id) ON DELETE CASCADE,
  pote_id              UUID NOT NULL REFERENCES public.potes(id) ON DELETE RESTRICT,
  percentual_aplicado  NUMERIC(5,2) NOT NULL CHECK (percentual_aplicado BETWEEN 0 AND 100),
  valor                NUMERIC(14,2) NOT NULL CHECK (valor >= 0),
  data                 DATE NOT NULL,   -- desnormalizada p/ relatórios sem JOIN
  criado_em            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_distribuicao_lanc_pote UNIQUE (lancamento_id, pote_id)
);

CREATE INDEX IF NOT EXISTS idx_distrib_user_pote_data
  ON public.distribuicoes_receita(user_id, pote_id, data DESC);

ALTER TABLE public.distribuicoes_receita ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "distrib_select_own" ON public.distribuicoes_receita;
CREATE POLICY "distrib_select_own" ON public.distribuicoes_receita
  FOR SELECT TO authenticated USING (user_id = auth.uid());

-- Escrita somente via RPC registrar_distribuicao_receita (SECURITY DEFINER)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON public.distribuicoes_receita FROM anon, authenticated;
GRANT SELECT ON public.distribuicoes_receita TO authenticated;

-- -----------------------------------------------------------------------------
-- 7. RPC: salvar_potes — atualização ATÔMICA com validação rigorosa
--    p_potes: [{"id": "...", "nome": "...", "percentual": 30}, ... x6]
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.salvar_potes(p_potes JSONB)
RETURNS JSONB LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_uid    UUID := auth.uid();
  v_item   JSONB;
  v_soma   NUMERIC := 0;
  v_nomes  TEXT[] := '{}';
  v_nome   TEXT;
  v_perc   NUMERIC;
  v_id     UUID;
  v_ids    UUID[] := '{}';
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Não autenticado.' USING ERRCODE = '28000';
  END IF;
  IF jsonb_typeof(p_potes) <> 'array' OR jsonb_array_length(p_potes) <> 6 THEN
    RAISE EXCEPTION 'POTES_INVALIDOS: envie exatamente 6 potes.' USING ERRCODE = 'check_violation';
  END IF;

  FOR v_item IN SELECT * FROM jsonb_array_elements(p_potes) LOOP
    v_id   := (v_item->>'id')::UUID;
    v_nome := btrim(COALESCE(v_item->>'nome', ''));
    v_perc := (v_item->>'percentual')::NUMERIC;

    IF v_nome = '' OR char_length(v_nome) > 40 THEN
      RAISE EXCEPTION 'POTES_INVALIDOS: nome do pote deve ter de 1 a 40 caracteres.' USING ERRCODE = 'check_violation';
    END IF;
    IF v_perc IS NULL OR v_perc < 0 OR v_perc > 100 THEN
      RAISE EXCEPTION 'POTES_INVALIDOS: percentual deve estar entre 0 e 100.' USING ERRCODE = 'check_violation';
    END IF;
    IF lower(v_nome) = ANY (v_nomes) THEN
      RAISE EXCEPTION 'POTES_INVALIDOS: nomes de potes devem ser únicos ("%").', v_nome USING ERRCODE = 'check_violation';
    END IF;
    IF v_id = ANY (v_ids) THEN
      RAISE EXCEPTION 'POTES_INVALIDOS: pote repetido no payload.' USING ERRCODE = 'check_violation';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.potes WHERE id = v_id AND user_id = v_uid) THEN
      RAISE EXCEPTION 'POTES_INVALIDOS: pote inexistente ou de outro usuário.' USING ERRCODE = 'check_violation';
    END IF;

    v_nomes := v_nomes || lower(v_nome);
    v_ids   := v_ids   || v_id;
    v_soma  := v_soma  + v_perc;
  END LOOP;

  IF v_soma <> 100 THEN
    RAISE EXCEPTION 'POTES_INVALIDOS: a soma dos percentuais deve ser exatamente 100%% (atual: %).', v_soma
      USING ERRCODE = 'check_violation';
  END IF;

  UPDATE public.potes p
     SET nome       = btrim(x.nome),
         percentual = x.percentual
    FROM jsonb_to_recordset(p_potes) AS x(id UUID, nome TEXT, percentual NUMERIC)
   WHERE p.id = x.id AND p.user_id = v_uid;

  RETURN (
    SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY t.posicao), '[]'::jsonb)
      FROM (SELECT id, posicao, nome, percentual, cor
              FROM public.potes WHERE user_id = v_uid) t
  );
END $$;

-- -----------------------------------------------------------------------------
-- 8. RPC: registrar_distribuicao_receita
--    Grava a distribuição de uma receita já inserida. Valida que:
--      * o lançamento pertence ao usuário e é Receita
--      * SUM(valor) == valor da receita (centavo a centavo)
--      * há exatamente 1 linha por pote, todos do usuário
--    p_itens: [{"pote_id": "...", "percentual": 30, "valor": 1722.10}, ... x6]
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.registrar_distribuicao_receita(
  p_lancamento_id UUID,
  p_itens         JSONB
) RETURNS INT LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_uid   UUID := auth.uid();
  v_lanc  RECORD;
  v_soma  NUMERIC;
BEGIN
  IF v_uid IS NULL THEN
    RAISE EXCEPTION 'Não autenticado.' USING ERRCODE = '28000';
  END IF;

  SELECT id, tipo, valor, data INTO v_lanc
    FROM public.lancamentos WHERE id = p_lancamento_id AND user_id = v_uid;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Lançamento não encontrado.' USING ERRCODE = 'no_data_found';
  END IF;
  IF lower(v_lanc.tipo) NOT LIKE 'receita%' THEN
    RAISE EXCEPTION 'Somente receitas podem ser distribuídas entre potes.' USING ERRCODE = 'check_violation';
  END IF;
  IF jsonb_typeof(p_itens) <> 'array' OR jsonb_array_length(p_itens) <> 6 THEN
    RAISE EXCEPTION 'A distribuição deve conter exatamente 6 potes.' USING ERRCODE = 'check_violation';
  END IF;

  SELECT COALESCE(SUM(valor), 0) INTO v_soma
    FROM jsonb_to_recordset(p_itens) AS x(pote_id UUID, percentual NUMERIC, valor NUMERIC);

  IF v_soma <> v_lanc.valor THEN
    RAISE EXCEPTION 'A soma da distribuição (%) difere do valor da receita (%).', v_soma, v_lanc.valor
      USING ERRCODE = 'check_violation';
  END IF;

  IF (SELECT COUNT(DISTINCT x.pote_id)
        FROM jsonb_to_recordset(p_itens) AS x(pote_id UUID, percentual NUMERIC, valor NUMERIC)
        JOIN public.potes p ON p.id = x.pote_id AND p.user_id = v_uid) <> 6 THEN
    RAISE EXCEPTION 'Distribuição referencia potes inválidos.' USING ERRCODE = 'check_violation';
  END IF;

  DELETE FROM public.distribuicoes_receita WHERE lancamento_id = p_lancamento_id;

  INSERT INTO public.distribuicoes_receita
         (user_id, lancamento_id, pote_id, percentual_aplicado, valor, data)
  SELECT v_uid, p_lancamento_id, x.pote_id, x.percentual, x.valor, v_lanc.data
    FROM jsonb_to_recordset(p_itens) AS x(pote_id UUID, percentual NUMERIC, valor NUMERIC);

  RETURN 6;
END $$;

-- -----------------------------------------------------------------------------
-- 9. RPC: get_potes_resumo — "Gasto vs Previsto" por pote em um período
--    Previsto = receitas distribuídas no período | Gasto = despesas com pote_id
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.get_potes_resumo(
  p_data_inicio DATE,
  p_data_fim    DATE
) RETURNS JSONB LANGUAGE plpgsql STABLE SECURITY INVOKER SET search_path = public AS $$
DECLARE
  v_uid     UUID := auth.uid();
  v_renda   NUMERIC;
  v_gasto   NUMERIC;
  v_potes   JSONB;
  v_sem     JSONB;
BEGIN
  SELECT COALESCE(SUM(valor), 0) INTO v_renda
    FROM public.lancamentos
   WHERE user_id = v_uid AND lower(tipo) LIKE 'receita%'
     AND data BETWEEN p_data_inicio AND p_data_fim;

  SELECT COALESCE(SUM(valor), 0) INTO v_gasto
    FROM public.lancamentos
   WHERE user_id = v_uid AND lower(tipo) LIKE 'despesa%'
     AND data BETWEEN p_data_inicio AND p_data_fim;

  SELECT COALESCE(jsonb_agg(r ORDER BY r.posicao), '[]'::jsonb) INTO v_potes
  FROM (
    SELECT p.id, p.posicao, p.nome, p.cor, p.percentual,
           COALESCE(prev.previsto, 0)             AS previsto,
           COALESCE(g.gasto, 0)                   AS gasto,
           COALESCE(g.qtd, 0)                     AS qtd_transacoes,
           COALESCE(prev.previsto, 0) - COALESCE(g.gasto, 0) AS restante,
           CASE WHEN COALESCE(prev.previsto, 0) > 0
                THEN ROUND(COALESCE(g.gasto, 0) / prev.previsto * 100, 2)
                ELSE 0 END                         AS percentual_usado
      FROM public.potes p
      LEFT JOIN (
        SELECT pote_id, SUM(valor) AS previsto
          FROM public.distribuicoes_receita
         WHERE user_id = v_uid AND data BETWEEN p_data_inicio AND p_data_fim
         GROUP BY pote_id
      ) prev ON prev.pote_id = p.id
      LEFT JOIN (
        SELECT pote_id, SUM(valor) AS gasto, COUNT(*) AS qtd
          FROM public.lancamentos
         WHERE user_id = v_uid AND lower(tipo) LIKE 'despesa%'
           AND pote_id IS NOT NULL
           AND data BETWEEN p_data_inicio AND p_data_fim
         GROUP BY pote_id
      ) g ON g.pote_id = p.id
     WHERE p.user_id = v_uid
  ) r;

  SELECT jsonb_build_object('qtd', COUNT(*), 'total', COALESCE(SUM(valor), 0)) INTO v_sem
    FROM public.lancamentos
   WHERE user_id = v_uid AND lower(tipo) LIKE 'despesa%'
     AND pote_id IS NULL
     AND data BETWEEN p_data_inicio AND p_data_fim;

  RETURN jsonb_build_object(
    'renda',        v_renda,
    'total_gasto',  v_gasto,
    'saldo',        v_renda - v_gasto,
    'percentual_renda_usado', CASE WHEN v_renda > 0 THEN ROUND(v_gasto / v_renda * 100, 2) ELSE 0 END,
    'potes',        v_potes,
    'sem_pote',     v_sem
  );
END $$;

-- -----------------------------------------------------------------------------
-- 10. EXECUTE nas RPCs somente para usuários autenticados
-- -----------------------------------------------------------------------------
REVOKE ALL ON FUNCTION public.garantir_potes()                              FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.salvar_potes(JSONB)                           FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.registrar_distribuicao_receita(UUID, JSONB)   FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.get_potes_resumo(DATE, DATE)                  FROM PUBLIC, anon;

GRANT EXECUTE ON FUNCTION public.garantir_potes()                            TO authenticated;
GRANT EXECUTE ON FUNCTION public.salvar_potes(JSONB)                         TO authenticated;
GRANT EXECUTE ON FUNCTION public.registrar_distribuicao_receita(UUID, JSONB) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_potes_resumo(DATE, DATE)                TO authenticated;
