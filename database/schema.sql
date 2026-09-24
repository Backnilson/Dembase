-- ====================================================================
-- DemBase - Schema Inicial do Banco de Dados (Supabase / PostgreSQL)
-- ====================================================================

-- 1. Tipos ENUM para consistência de dados
CREATE TYPE tipo_lancamento AS ENUM ('Receita', 'Despesa');
CREATE TYPE subtipo_lancamento AS ENUM ('Receita', 'Entrada', 'Despesa', 'Saída', 'Dívida', 'Empréstimo');
CREATE TYPE forma_movimentacao AS ENUM ('Credito', 'Debito', 'Pix', 'Dinheiro');
CREATE TYPE status_lancamento AS ENUM ('Pago', 'Pendente');

-- 2. Tabela de Perfis (Vinculada à auth.users do Supabase)
CREATE TABLE perfis (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE perfis ENABLE ROW LEVEL SECURITY;

-- 3. Tabela de Contas (Santander, Itaú, Inter, Dinheiro...)
CREATE TABLE contas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id UUID NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE contas ENABLE ROW LEVEL SECURITY;

-- 4. Tabela de Categorias (Alimentação, Transporte, Moradia...)
CREATE TABLE categorias (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id UUID NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE categorias ENABLE ROW LEVEL SECURITY;

-- 5. Tabela de Destinos (Eu, Casa, Moto, Carro...)
CREATE TABLE destinos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    perfil_id UUID NOT NULL REFERENCES perfis(id) ON DELETE CASCADE,
    nome TEXT NOT NULL,
    criado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE destinos ENABLE ROW LEVEL SECURITY;

-- 6. Tabela Principal de Lançamentos
CREATE TABLE lancamentos (
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
    
    -- Detalhes Financeiros e Textuais
    valor DECIMAL(12, 2) NOT NULL CHECK (valor > 0),
    data DATE NOT NULL,
    hora INT CHECK (hora >= 0 AND hora <= 23),
    descricao TEXT NOT NULL,
    status status_lancamento NOT NULL DEFAULT 'Pago',
    
    -- Exclusivos para Crédito
    parcela_atual INT,
    total_parcelas INT,
    fatura TEXT,
    
    -- Auditoria
    criado_em TIMESTAMPTZ DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ DEFAULT NOW()
);
ALTER TABLE lancamentos ENABLE ROW LEVEL SECURITY;

-- 7. Lógica de Negócio: Trigger de Status Automático para Cartão de Crédito
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

CREATE TRIGGER trg_status_credito
BEFORE INSERT ON lancamentos
FOR EACH ROW
EXECUTE FUNCTION definir_status_credito_automatico();

-- 8. Índices de Performance
CREATE INDEX idx_categorias_perfil_id ON public.categorias(perfil_id);
CREATE INDEX idx_contas_perfil_id ON public.contas(perfil_id);
CREATE INDEX idx_destinos_perfil_id ON public.destinos(perfil_id);
CREATE INDEX idx_lancamentos_perfil_id ON public.lancamentos(perfil_id);
CREATE INDEX idx_lancamentos_conta_id ON public.lancamentos(conta_id);
CREATE INDEX idx_lancamentos_categoria_id ON public.lancamentos(categoria_id);
CREATE INDEX idx_lancamentos_destino_id ON public.lancamentos(destino_id);
CREATE INDEX idx_lancamentos_data ON public.lancamentos(data);

-- 9. Políticas de Segurança RLS Otimizadas
CREATE POLICY "Users can view own profile" ON perfis FOR SELECT USING ((select auth.uid()) = id);
CREATE POLICY "Users can update own profile" ON perfis FOR UPDATE USING ((select auth.uid()) = id);
CREATE POLICY "Users can insert own profile" ON perfis FOR INSERT WITH CHECK ((select auth.uid()) = id);

CREATE POLICY "Users can manage own accounts" ON contas FOR ALL USING ((select auth.uid()) = perfil_id) WITH CHECK ((select auth.uid()) = perfil_id);
CREATE POLICY "Users can manage own categories" ON categorias FOR ALL USING ((select auth.uid()) = perfil_id) WITH CHECK ((select auth.uid()) = perfil_id);
CREATE POLICY "Users can manage own destinations" ON destinos FOR ALL USING ((select auth.uid()) = perfil_id) WITH CHECK ((select auth.uid()) = perfil_id);
CREATE POLICY "Users can manage own transactions" ON lancamentos FOR ALL USING ((select auth.uid()) = perfil_id) WITH CHECK ((select auth.uid()) = perfil_id);
