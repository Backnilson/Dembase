-- ====================================================================
-- DemBase v2.0 - Migração do Schema v1 para v2
-- Aplica sobre o banco existente sem destruir dados
-- ====================================================================

-- 1. Criar novos ENUMs (se não existirem)
DO $$ BEGIN
  CREATE TYPE regra_financeira AS ENUM ('Essencial', 'Estilo de Vida', 'Investimento');
EXCEPTION WHEN duplicate_object THEN null;
END $$;

-- 2. Adicionar campo 'regra' na tabela lancamentos
DO $$ BEGIN
  ALTER TABLE lancamentos ADD COLUMN regra regra_financeira;
EXCEPTION WHEN duplicate_column THEN null;
END $$;

-- 3. Adicionar campo 'ativo' nas tabelas auxiliares
DO $$ BEGIN
  ALTER TABLE contas ADD COLUMN ativo BOOLEAN DEFAULT TRUE;
EXCEPTION WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
  ALTER TABLE categorias ADD COLUMN ativo BOOLEAN DEFAULT TRUE;
EXCEPTION WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
  ALTER TABLE categorias ADD COLUMN icone TEXT;
EXCEPTION WHEN duplicate_column THEN null;
END $$;

DO $$ BEGIN
  ALTER TABLE destinos ADD COLUMN ativo BOOLEAN DEFAULT TRUE;
EXCEPTION WHEN duplicate_column THEN null;
END $$;

-- 4. Atualizar trigger de status para funcionar em UPDATE também
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

-- 5. Trigger de atualizado_em
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

-- 6. Trigger de criação automática de perfil
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
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_criar_perfil ON auth.users;
CREATE TRIGGER trg_criar_perfil
AFTER INSERT ON auth.users
FOR EACH ROW
EXECUTE FUNCTION criar_perfil_novo_usuario();

-- 7. Novos índices
CREATE INDEX IF NOT EXISTS idx_lancamentos_tipo ON public.lancamentos(tipo);
CREATE INDEX IF NOT EXISTS idx_lancamentos_regra ON public.lancamentos(regra);
CREATE INDEX IF NOT EXISTS idx_lancamentos_dashboard ON public.lancamentos(perfil_id, tipo, data);

-- 8. RPC: Totais financeiros com filtros de data
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

-- 9. RPC: Resumo 50/30/20
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
    
    SELECT COALESCE(SUM(valor), 0) INTO v_receita_total
    FROM lancamentos
    WHERE perfil_id = v_uid AND tipo = 'Receita'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_essencial
    FROM lancamentos
    WHERE perfil_id = v_uid AND tipo = 'Despesa' AND regra = 'Essencial'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_estilo
    FROM lancamentos
    WHERE perfil_id = v_uid AND tipo = 'Despesa' AND regra = 'Estilo de Vida'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    SELECT COALESCE(SUM(valor), 0) INTO v_gasto_investimento
    FROM lancamentos
    WHERE perfil_id = v_uid AND tipo = 'Despesa' AND regra = 'Investimento'
      AND (p_data_inicio IS NULL OR data >= p_data_inicio)
      AND (p_data_fim IS NULL OR data <= p_data_fim);
    
    RETURN json_build_object(
        'receita_total', v_receita_total,
        'essencial', json_build_object(
            'gasto', v_gasto_essencial,
            'orcamento', v_receita_total * 0.50,
            'percentual_usado', CASE WHEN v_receita_total > 0 
                THEN ROUND((v_gasto_essencial / v_receita_total) * 100, 1) ELSE 0 END
        ),
        'estilo_vida', json_build_object(
            'gasto', v_gasto_estilo,
            'orcamento', v_receita_total * 0.30,
            'percentual_usado', CASE WHEN v_receita_total > 0 
                THEN ROUND((v_gasto_estilo / v_receita_total) * 100, 1) ELSE 0 END
        ),
        'investimento', json_build_object(
            'gasto', v_gasto_investimento,
            'orcamento', v_receita_total * 0.20,
            'percentual_usado', CASE WHEN v_receita_total > 0 
                THEN ROUND((v_gasto_investimento / v_receita_total) * 100, 1) ELSE 0 END
        )
    );
END;
$$;

-- 10. Seed de dados padrão para novos usuários
CREATE OR REPLACE FUNCTION public.seed_dados_padrao_usuario()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO contas (perfil_id, nome) VALUES
        (NEW.id, 'Santander'), (NEW.id, 'Itaú'), (NEW.id, 'Inter'), (NEW.id, 'Dinheiro');
    
    INSERT INTO categorias (perfil_id, nome, icone) VALUES
        (NEW.id, 'Alimentação', 'restaurant'), (NEW.id, 'Transporte', 'directions_car'),
        (NEW.id, 'Moradia', 'home'), (NEW.id, 'Lazer', 'sports_esports'),
        (NEW.id, 'Saúde', 'local_hospital'), (NEW.id, 'Educação', 'school'),
        (NEW.id, 'DJ', 'headphones'), (NEW.id, 'Investimento', 'trending_up'),
        (NEW.id, 'Outros', 'more_horiz');
    
    INSERT INTO destinos (perfil_id, nome) VALUES
        (NEW.id, 'Eu'), (NEW.id, 'Casa'), (NEW.id, 'Moto'), (NEW.id, 'Carro'),
        (NEW.id, 'DJ'), (NEW.id, 'Família'), (NEW.id, 'Outros');
    
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_seed_dados ON perfis;
CREATE TRIGGER trg_seed_dados
AFTER INSERT ON perfis
FOR EACH ROW
EXECUTE FUNCTION seed_dados_padrao_usuario();
