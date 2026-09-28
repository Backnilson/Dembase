-- ====================================================================
-- DemBase v2.0 - Schema Completo (Supabase / PostgreSQL)
-- Autor: Arquiteto DemBase
-- Inclui: Regra 50/30/20, Triggers Inteligentes, RPCs de Dashboard
-- ====================================================================

-- ====================================================================
-- 1. TIPOS ENUM
-- ====================================================================
DO $$ BEGIN
  CREATE TYPE tipo_lancamento AS ENUM ('Receita', 'Despesa');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE subtipo_lancamento AS ENUM ('Receita', 'Entrada', 'Despesa', 'Saída', 'Dívida', 'Empréstimo');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE forma_movimentacao AS ENUM ('Credito', 'Debito', 'Pix', 'Dinheiro');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
  CREATE TYPE status_lancamento AS ENUM ('Pago', 'Pendente');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

-- ====================================================================
-- NOVO: Enum para a Regra 50/30/20
-- Classifica cada despesa em uma das três categorias orçamentárias.
-- ====================================================================
DO $$ BEGIN
  CREATE TYPE regra_financeira AS ENUM ('Essencial', 'Estilo de Vida', 'Investimento');
EXCEPTION WHEN duplicate_object THEN null;
END $$;


-- ====================================================================
-- 2. TABELA DE PERFIS (Vinculada ao auth.users do Supabase)
-- ====================================================================
CREATE TABLE IF NOT EXISTS perfis (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE perfis ENABLE ROW LEVEL SECURITY;


-- ====================================================================
-- 3. TABELA DE CONTAS (Santander, Itaú, Inter, Dinheiro...)
-- ====================================================================
CREATE TABLE IF NOT EXISTS contas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id UUID NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE contas ENABLE ROW LEVEL SECURITY;


-- ====================================================================
-- 4. TABELA DE CATEGORIAS (Alimentação, Transporte, Moradia...)
-- ====================================================================
CREATE TABLE IF NOT EXISTS categorias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id UUID NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    icone TEXT, -- Nome do ícone para o Flutter (ex: 'restaurant', 'directions_car')
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE categorias ENABLE ROW LEVEL SECURITY;


-- ====================================================================
-- 5. TABELA DE DESTINOS (Eu, Casa, Moto, Carro, DJ, Família...)
-- ====================================================================
CREATE TABLE IF NOT EXISTS destinos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id UUID NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE destinos ENABLE ROW LEVEL SECURITY;


-- ====================================================================
-- 6. TABELA PRINCIPAL DE LANÇAMENTOS (com regra 50/30/20)
-- ====================================================================
CREATE TABLE IF NOT EXISTS lancamentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id UUID NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    
    -- Classificação
    tipo tipo_lancamento NOT NULL,
    subtipo subtipo_lancamento NOT NULL,
    forma_movimentacao forma_movimentacao NOT NULL,
    
    -- Relacionamentos
    conta_id UUID REFERENCES contas(id) ON DELETE SET NULL,
    categoria_id UUID REFERENCES categorias(id) ON DELETE SET NULL,
    destino_id UUID REFERENCES destinos(id) ON DELETE SET NULL,
    
    -- Detalhes Financeiros
    valor DECIMAL(12, 2) NOT NULL CHECK (valor > 0),
    data DATE NOT NULL,
    hora INT CHECK (hora >= 0 AND hora <= 23),
    descricao TEXT NOT NULL,
    status status_lancamento NOT NULL DEFAULT 'Pago',
    
    -- ============================================================
    -- NOVO: Regra 50/30/20
    -- Este campo classifica DESPESAS em uma das três categorias:
    --   'Essencial'       → 50% da renda (moradia, alimentação, contas)
    --   'Estilo de Vida'  → 30% da renda (lazer, restaurantes, compras)
    --   'Investimento'    → 20% da renda (poupança, investimentos, cursos)
    -- Para RECEITAS, este campo fica NULL.
    -- ============================================================
    regra regra_financeira,
    
    -- Exclusivos para Crédito
    parcela_atual INT,
    total_parcelas INT,
    fatura TEXT,
    
    -- Auditoria
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    
    -- Constraint: regra é obrigatória para despesas
    CONSTRAINT chk_regra_despesa CHECK (
        (tipo = 'Receita' AND regra IS NULL)
        OR (tipo = 'Despesa' AND regra IS NOT NULL)
    ),
    
    -- Constraint: campos de crédito obrigatórios quando forma é Credito
    CONSTRAINT chk_credito_campos CHECK (
        (forma_movimentacao != 'Credito')
        OR (forma_movimentacao = 'Credito' AND parcela_atual IS NOT NULL AND total_parcelas IS NOT NULL)
    )
);
ALTER TABLE lancamentos ENABLE ROW LEVEL SECURITY;


-- ====================================================================
-- 7. TRIGGER: Status Automático para Cartão de Crédito
-- Funciona em INSERT e UPDATE para manter consistência.
-- Regra: data futura → Pendente | data hoje ou passada → Pago
-- ====================================================================
CREATE OR REPLACE FUNCTION public.definir_status_credito_automatico()
RETURNS TRIGGER 
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    IF NEW.forma_movimentacao = 'Credito' THEN
        IF NEW.data > CURRENT_DATE THEN
            NEW.status := 'Pendente';
        ELSE
            NEW.status := 'Pago';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_status_credito ON lancamentos;
CREATE TRIGGER trg_status_credito
BEFORE INSERT OR UPDATE ON lancamentos
FOR EACH ROW
EXECUTE FUNCTION definir_status_credito_automatico();


-- ====================================================================
-- 8. TRIGGER: Atualizar timestamp 'atualizado_em' em UPDATE
-- ====================================================================
CREATE OR REPLACE FUNCTION public.atualizar_timestamp()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.atualizado_em := NOW();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_atualizar_timestamp ON lancamentos;
CREATE TRIGGER trg_atualizar_timestamp
BEFORE UPDATE ON lancamentos
FOR EACH ROW
EXECUTE FUNCTION atualizar_timestamp();


-- ====================================================================
-- 9. TRIGGER: Criar perfil automático ao cadastrar usuário
-- Utiliza metadata.full_name enviado no signUp do Supabase.
-- ====================================================================
CREATE OR REPLACE FUNCTION public.criar_perfil_novo_usuario()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO public.perfis (id, nome)
    VALUES (
        NEW.id,
        COALESCE(NEW.raw_user_meta_data->>'full_name', 'Usuário')
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_criar_perfil ON auth.users;
CREATE TRIGGER trg_criar_perfil
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION criar_perfil_novo_usuario();


-- ====================================================================
-- 10. ÍNDICES DE PERFORMANCE
-- ====================================================================
CREATE INDEX IF NOT EXISTS idx_categorias_perfil_id ON public.categorias(perfil_id);
CREATE INDEX IF NOT EXISTS idx_contas_perfil_id ON public.contas(perfil_id);
CREATE INDEX IF NOT EXISTS idx_destinos_perfil_id ON public.destinos(perfil_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_perfil_id ON public.lancamentos(perfil_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_conta_id ON public.lancamentos(conta_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_categoria_id ON public.lancamentos(categoria_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_destino_id ON public.lancamentos(destino_id);
CREATE INDEX IF NOT EXISTS idx_lancamentos_data ON public.lancamentos(data);
CREATE INDEX IF NOT EXISTS idx_lancamentos_tipo ON public.lancamentos(tipo);
CREATE INDEX IF NOT EXISTS idx_lancamentos_regra ON public.lancamentos(regra);
-- Índice composto para filtros de dashboard (tipo + data + perfil)
CREATE INDEX IF NOT EXISTS idx_lancamentos_dashboard ON public.lancamentos(perfil_id, tipo, data);


-- ====================================================================
-- 11. POLÍTICAS DE SEGURANÇA RLS
-- ====================================================================
-- Perfis
DROP POLICY IF EXISTS "perfis_select" ON perfis;
DROP POLICY IF EXISTS "perfis_update" ON perfis;
DROP POLICY IF EXISTS "perfis_insert" ON perfis;
CREATE POLICY "perfis_select" ON perfis FOR SELECT USING ((SELECT auth.uid()) = id);
CREATE POLICY "perfis_update" ON perfis FOR UPDATE USING ((SELECT auth.uid()) = id);
CREATE POLICY "perfis_insert" ON perfis FOR INSERT WITH CHECK ((SELECT auth.uid()) = id);

-- Contas
DROP POLICY IF EXISTS "contas_all" ON contas;
CREATE POLICY "contas_all" ON contas FOR ALL 
  USING ((SELECT auth.uid()) = perfil_id) 
  WITH CHECK ((SELECT auth.uid()) = perfil_id);

-- Categorias
DROP POLICY IF EXISTS "categorias_all" ON categorias;
CREATE POLICY "categorias_all" ON categorias FOR ALL 
  USING ((SELECT auth.uid()) = perfil_id) 
  WITH CHECK ((SELECT auth.uid()) = perfil_id);

-- Destinos
DROP POLICY IF EXISTS "destinos_all" ON destinos;
CREATE POLICY "destinos_all" ON destinos FOR ALL 
  USING ((SELECT auth.uid()) = perfil_id) 
  WITH CHECK ((SELECT auth.uid()) = perfil_id);

-- Lançamentos
DROP POLICY IF EXISTS "lancamentos_all" ON lancamentos;
CREATE POLICY "lancamentos_all" ON lancamentos FOR ALL 
  USING ((SELECT auth.uid()) = perfil_id) 
  WITH CHECK ((SELECT auth.uid()) = perfil_id);


-- ====================================================================
-- 12. RPC: Totais Financeiros para Dashboard
-- Retorna receitas, despesas e saldo para o período selecionado.
-- Aceita filtros de data flexíveis (o diferencial DemBase).
-- ====================================================================
CREATE OR REPLACE FUNCTION public.get_financial_totals(
    p_data_inicio DATE DEFAULT NULL,
    p_data_fim DATE DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_receitas DECIMAL(12,2);
    v_despesas DECIMAL(12,2);
    v_uid UUID;
BEGIN
    v_uid := auth.uid();
    
    SELECT COALESCE(SUM(valor), 0) INTO v_receitas
    FROM lancamentos
    WHERE perfil_id = v_uid
      AND tipo = 'Receita'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    SELECT COALESCE(SUM(valor), 0) INTO v_despesas
    FROM lancamentos
    WHERE perfil_id = v_uid
      AND tipo = 'Despesa'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    RETURN json_build_object(
        'receitas', v_receitas,
        'despesas', v_despesas,
        'saldo', v_receitas - v_despesas
    );
END;
$$;


-- ====================================================================
-- 13. RPC: Resumo da Regra 50/30/20 para Dashboard
-- Retorna o total gasto em cada categoria vs o orçamento ideal.
-- O orçamento ideal é calculado com base na receita total do período.
-- ====================================================================
CREATE OR REPLACE FUNCTION public.get_regra_50_30_20_summary(
    p_data_inicio DATE DEFAULT NULL,
    p_data_fim DATE DEFAULT NULL
)
RETURNS JSON
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_receita_total DECIMAL(12,2);
    v_gasto_essencial DECIMAL(12,2);
    v_gasto_estilo DECIMAL(12,2);
    v_gasto_investimento DECIMAL(12,2);
    v_uid UUID;
BEGIN
    v_uid := auth.uid();
    
    -- Total de receitas no período (base do orçamento)
    SELECT COALESCE(SUM(valor), 0) INTO v_receita_total
    FROM lancamentos
    WHERE perfil_id = v_uid
      AND tipo = 'Receita'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    -- Gastos por categoria da regra
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_essencial
    FROM lancamentos
    WHERE perfil_id = v_uid
      AND tipo = 'Despesa'
      AND regra = 'Essencial'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_estilo
    FROM lancamentos
    WHERE perfil_id = v_uid
      AND tipo = 'Despesa'
      AND regra = 'Estilo de Vida'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_investimento
    FROM lancamentos
    WHERE perfil_id = v_uid
      AND tipo = 'Despesa'
      AND regra = 'Investimento'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    RETURN json_build_object(
        'receita_total', v_receita_total,
        'essencial', json_build_object(
            'gasto', v_gasto_essencial,
            'orcamento', v_receita_total * 0.50,
            'percentual_usado', CASE WHEN v_receita_total > 0 
                THEN ROUND((v_gasto_essencial / v_receita_total) * 100, 1) 
                ELSE 0 END
        ),
        'estilo_vida', json_build_object(
            'gasto', v_gasto_estilo,
            'orcamento', v_receita_total * 0.30,
            'percentual_usado', CASE WHEN v_receita_total > 0 
                THEN ROUND((v_gasto_estilo / v_receita_total) * 100, 1) 
                ELSE 0 END
        ),
        'investimento', json_build_object(
            'gasto', v_gasto_investimento,
            'orcamento', v_receita_total * 0.20,
            'percentual_usado', CASE WHEN v_receita_total > 0 
                THEN ROUND((v_gasto_investimento / v_receita_total) * 100, 1) 
                ELSE 0 END
        )
    );
END;
$$;


-- ====================================================================
-- 14. SEED: Dados iniciais padrão (executar após primeiro cadastro)
-- Inserir dados padrão para o usuário recém-criado via trigger.
-- ====================================================================
CREATE OR REPLACE FUNCTION public.seed_dados_padrao_usuario()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Contas padrão
    INSERT INTO contas (perfil_id, nome) VALUES
        (NEW.id, 'Santander'),
        (NEW.id, 'Itaú'),
        (NEW.id, 'Inter'),
        (NEW.id, 'Dinheiro');
    
    -- Categorias padrão
    INSERT INTO categorias (perfil_id, nome, icone) VALUES
        (NEW.id, 'Alimentação', 'restaurant'),
        (NEW.id, 'Transporte', 'directions_car'),
        (NEW.id, 'Moradia', 'home'),
        (NEW.id, 'Lazer', 'sports_esports'),
        (NEW.id, 'Saúde', 'local_hospital'),
        (NEW.id, 'Educação', 'school'),
        (NEW.id, 'DJ', 'headphones'),
        (NEW.id, 'Investimento', 'trending_up'),
        (NEW.id, 'Outros', 'more_horiz');
    
    -- Destinos padrão
    INSERT INTO destinos (perfil_id, nome) VALUES
        (NEW.id, 'Eu'),
        (NEW.id, 'Casa'),
        (NEW.id, 'Moto'),
        (NEW.id, 'Carro'),
        (NEW.id, 'DJ'),
        (NEW.id, 'Família'),
        (NEW.id, 'Outros');
    
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_seed_dados ON perfis;
CREATE TRIGGER trg_seed_dados
AFTER INSERT ON perfis
FOR EACH ROW
EXECUTE FUNCTION seed_dados_padrao_usuario();
