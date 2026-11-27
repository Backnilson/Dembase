-- 009_faxina_categorias.sql
-- Faxina de categorias/subcategorias do usuario 07614dd5 (9 categorias macro).
-- Atomica: repontar TUDO -> provar 0 referencias -> apagar antigas -> conferir fingerprints.
-- Backup local: backup_categorias_pre_faxina.json | backup no banco: schema bkp_faxina.
-- Otimizacao: usa dembase.pular_recalculo='on' e dembase.fluxo_fatura='on' (escopo local a transacao)
-- para evitar 1.650 recalculos de saldo/caixinha no UPDATE exclusivo de categoria_id/subcategoria_id.

-- Guarda aditiva (CREATE OR REPLACE) nos triggers de caixinha para respeitar dembase.pular_recalculo='on'
-- (mesmo padrao ja existente em fn_trg_sincronizar_saldos_lancamento).
CREATE OR REPLACE FUNCTION public.fn_trg_caixinhas_teto_sincronizar_provisoes()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
    IF COALESCE(current_setting('dembase.pular_recalculo', true), '') = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
    IF TG_OP = 'DELETE' THEN
        DELETE FROM public.lancamentos
        WHERE caixinha_id = OLD.id
          AND status = 'Pendente'
          AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
        RETURN OLD;
    ELSE
        IF LOWER(COALESCE(NEW.modalidade, 'provisao_mensal')) IN ('divida', 'quitacao') THEN
            DELETE FROM public.lancamentos
            WHERE caixinha_id = NEW.id
              AND status = 'Pendente'
              AND LOWER(COALESCE(subtipo, '')) = 'provisionamento';
            RETURN NEW;
        END IF;
        PERFORM public.fn_sincronizar_provisoes_caixinha(NEW.id, 12);
        RETURN NEW;
    END IF;
END;
$function$;

CREATE OR REPLACE FUNCTION public.fn_trg_recalcular_caixinha()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
    IF COALESCE(current_setting('dembase.pular_recalculo', true), '') = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;
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
$function$;

CREATE OR REPLACE FUNCTION public.fn_trg_sincronizar_provisionamento_caixinha()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    v_anterior NUMERIC;
BEGIN
    IF COALESCE(current_setting('dembase.pular_recalculo', true), '') = 'on' THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF (TG_OP = 'INSERT' AND NEW.status = 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL)
       OR (TG_OP = 'UPDATE' AND (OLD.status IS NULL OR OLD.status <> 'Pago') AND NEW.status = 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL) THEN

        IF NOT EXISTS (
            SELECT 1 FROM public.caixinhas_teto_movimentacoes
            WHERE lancamento_id = NEW.id AND tipo = 'injecao'
        ) THEN
            SELECT COALESCE(saldo_atual, 0) INTO v_anterior
            FROM public.caixinhas_teto WHERE id = NEW.caixinha_id;

            INSERT INTO public.caixinhas_teto_movimentacoes (
                caixinha_id, user_id, tipo, valor, saldo_anterior, saldo_posterior, descricao, data, lancamento_id
            ) VALUES (
                NEW.caixinha_id, NEW.user_id, 'injecao', NEW.valor, v_anterior, v_anterior + NEW.valor,
                COALESCE(NEW.descricao, 'Aporte / Provisão na Caixinha'), NEW.data, NEW.id
            );
        ELSE
            UPDATE public.caixinhas_teto_movimentacoes
            SET valor = NEW.valor,
                data = NEW.data,
                descricao = COALESCE(NEW.descricao, descricao)
            WHERE lancamento_id = NEW.id AND tipo = 'injecao';
        END IF;

        PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);

    ELSIF TG_OP = 'UPDATE' AND OLD.status = 'Pago' AND NEW.status = 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL THEN
        IF EXISTS (
            SELECT 1 FROM public.caixinhas_teto_movimentacoes
            WHERE lancamento_id = NEW.id AND tipo = 'injecao'
        ) THEN
            UPDATE public.caixinhas_teto_movimentacoes
            SET valor = NEW.valor,
                data = NEW.data,
                descricao = COALESCE(NEW.descricao, descricao)
            WHERE lancamento_id = NEW.id AND tipo = 'injecao';
        ELSE
            SELECT COALESCE(saldo_atual, 0) INTO v_anterior
            FROM public.caixinhas_teto WHERE id = NEW.caixinha_id;

            INSERT INTO public.caixinhas_teto_movimentacoes (
                caixinha_id, user_id, tipo, valor, saldo_anterior, saldo_posterior, descricao, data, lancamento_id
            ) VALUES (
                NEW.caixinha_id, NEW.user_id, 'injecao', NEW.valor, v_anterior, v_anterior + NEW.valor,
                COALESCE(NEW.descricao, 'Aporte / Provisão na Caixinha'), NEW.data, NEW.id
            );
        END IF;

        PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);

    ELSIF TG_OP = 'UPDATE' AND OLD.status = 'Pago' AND NEW.status <> 'Pago' AND LOWER(COALESCE(TRIM(NEW.subtipo), '')) = 'provisionamento' AND NEW.caixinha_id IS NOT NULL THEN
        DELETE FROM public.caixinhas_teto_movimentacoes
        WHERE lancamento_id = NEW.id;

        PERFORM public.fn_recalcular_saldo_caixinha(NEW.caixinha_id);

    ELSIF TG_OP = 'DELETE' AND OLD.caixinha_id IS NOT NULL AND LOWER(COALESCE(TRIM(OLD.subtipo), '')) = 'provisionamento' THEN
        DELETE FROM public.caixinhas_teto_movimentacoes
        WHERE lancamento_id = OLD.id;

        PERFORM public.fn_recalcular_saldo_caixinha(OLD.caixinha_id);
    END IF;

    RETURN COALESCE(NEW, OLD);
END;
$function$;

DO $mig$
DECLARE
  uid uuid := '07614dd5-3a3a-4538-8cc0-915a18c1fd85';
  b_cnt bigint; b_sum numeric; b_fl text; b_fc text; b_ft text;
  a_cnt bigint; a_sum numeric; a_fl text; a_fc text; a_ft text;
  n_null bigint; n_ref bigint; n_sem bigint;
BEGIN
  -- Flags locais a transacao (resetam automaticamente no COMMIT/ROLLBACK)
  PERFORM set_config('dembase.pular_recalculo', 'on', true);
  PERFORM set_config('dembase.fluxo_fatura', 'on', true);
  -- ===== 0. BASELINE =====
  SELECT count(*), sum(valor), md5(string_agg((to_jsonb(l)-'categoria_id'-'subcategoria_id'-'atualizado_em')::text,'|' ORDER BY id))
    INTO b_cnt, b_sum, b_fl FROM lancamentos l;
  SELECT md5(string_agg((to_jsonb(c)-'atualizado_em')::text,'|' ORDER BY id)) INTO b_fc FROM contas c;
  SELECT md5(string_agg((to_jsonb(t)-'categoria_id'-'subcategoria_id'-'atualizado_em')::text,'|' ORDER BY id)) INTO b_ft FROM caixinhas_teto t;

  -- ===== 1. BACKUP NO BANCO (schema nao exposto na API) =====
  CREATE SCHEMA bkp_faxina;
  CREATE TABLE bkp_faxina.categorias AS SELECT * FROM categorias WHERE user_id = uid;
  CREATE TABLE bkp_faxina.subcategorias AS SELECT * FROM subcategorias WHERE user_id = uid;
  CREATE TABLE bkp_faxina.lancamentos_map AS SELECT id, categoria_id, subcategoria_id FROM lancamentos;
  CREATE TABLE bkp_faxina.caixinhas_map AS SELECT id, categoria_id, subcategoria_id FROM caixinhas_teto;
  CREATE TABLE bkp_faxina.recorrentes_map AS SELECT id, categoria_id, subcategoria_id FROM transacoes_recorrentes;
  CREATE TABLE bkp_faxina.auditoria (chave text, valor jsonb);
  ALTER TABLE bkp_faxina.categorias ENABLE ROW LEVEL SECURITY;
  ALTER TABLE bkp_faxina.subcategorias ENABLE ROW LEVEL SECURITY;
  ALTER TABLE bkp_faxina.lancamentos_map ENABLE ROW LEVEL SECURITY;
  ALTER TABLE bkp_faxina.caixinhas_map ENABLE ROW LEVEL SECURITY;
  ALTER TABLE bkp_faxina.recorrentes_map ENABLE ROW LEVEL SECURITY;
  ALTER TABLE bkp_faxina.auditoria ENABLE ROW LEVEL SECURITY;

  CREATE TEMP TABLE old_cat ON COMMIT DROP AS SELECT id FROM categorias WHERE user_id = uid;
  CREATE TEMP TABLE old_sub ON COMMIT DROP AS SELECT id FROM subcategorias WHERE user_id = uid;

  -- ===== 2. NOVA TAXONOMIA =====
  CREATE TEMP TABLE nc ON COMMIT DROP AS
  SELECT gen_random_uuid() id, nome, icone, cor FROM (VALUES
    ('Renda','💰','#34D399'),('Moradia','🏡','#38BDF8'),('Alimentação','🍔','#FBBF24'),
    ('Transporte','🚗','#FB7185'),('Saúde & Bem-estar','💊','#2DD4BF'),('Lazer & Viagens','🍻','#FB923C'),
    ('Educação & Carreira','🎓','#818CF8'),('Pessoal & Família','👨‍👩‍👦','#A78BFA'),
    ('Finanças & Investimentos','📈','#60A5FA')) v(nome,icone,cor);
  INSERT INTO categorias (id, perfil_id, user_id, nome, icone, cor, tipo, ativo)
    SELECT id, uid, uid, nome, icone, cor, 'ambos', true FROM nc;

  CREATE TEMP TABLE ns ON COMMIT DROP AS
  SELECT gen_random_uuid() id, nc.id cat_id, v.cat, v.sub, nc.cor FROM (VALUES
    ('Renda','Salário'),('Renda','Adiantamento & Vale Transporte'),('Renda','Renda Extra'),
    ('Moradia','Aluguel'),('Moradia','Contas'),('Moradia','Internet & Telefonia'),('Moradia','Casa & Manutenção'),
    ('Alimentação','Supermercado'),('Alimentação','Restaurantes & Delivery'),('Alimentação','Café & Lanches'),
    ('Transporte','Moto'),('Transporte','Carro'),('Transporte','Apps & Ônibus'),
    ('Saúde & Bem-estar','Farmácia'),('Saúde & Bem-estar','Academia'),('Saúde & Bem-estar','Consultas'),('Saúde & Bem-estar','Beleza & Barbearia'),
    ('Lazer & Viagens','Bares & Bebidas'),('Lazer & Viagens','Passeios & Eventos'),('Lazer & Viagens','Viagens'),('Lazer & Viagens','Assinaturas & Streaming'),
    ('Educação & Carreira','Cursos & Estudo'),('Educação & Carreira','DJ'),('Educação & Carreira','IA & Software'),
    ('Pessoal & Família','Vestuário'),('Pessoal & Família','Presentes'),('Pessoal & Família','Pets & Filhos'),('Pessoal & Família','Eletrônicos & Tecnologia'),('Pessoal & Família','Diversos'),
    ('Finanças & Investimentos','Investimentos & Reservas'),('Finanças & Investimentos','Empréstimos & Dívidas'),('Finanças & Investimentos','Juros & Tarifas'),('Finanças & Investimentos','Ajustes de Saldo'),('Finanças & Investimentos','Transferências & Faturas')
  ) v(cat,sub) JOIN nc ON nc.nome = v.cat;
  INSERT INTO subcategorias (id, categoria_id, user_id, nome, cor, ativo)
    SELECT id, cat_id, uid, sub, cor, true FROM ns;

  -- ===== 3. REGRAS ESTRUTURAIS (cat antiga, sub antiga -> nova) =====
  CREATE TEMP TABLE sr ON COMMIT DROP AS SELECT * FROM (VALUES
    ('Salário','Denilson','Renda','Salário'),('Salário','Erika','Renda','Salário'),
    ('Salário','*','Renda','Adiantamento & Vale Transporte'),
    ('Renda extra','*','Renda','Renda Extra'),('Pix','*','Renda','Renda Extra'),
    ('Denílson','Saque Aniversario','Renda','Renda Extra'),('Evento','*','Renda','Renda Extra'),
    ('Casa','Aluguel','Moradia','Aluguel'),('Casa','Conta de água','Moradia','Contas'),('Casa','Conta de luz','Moradia','Contas'),
    ('Casa','Internet','Moradia','Internet & Telefonia'),('Casa','*','Moradia','Casa & Manutenção'),
    ('Internet','*','Moradia','Internet & Telefonia'),('Denílson','Internet Móvel','Moradia','Internet & Telefonia'),
    ('Erika','Internet Móvel','Moradia','Internet & Telefonia'),('Eletrônicos','Internet Móvel','Moradia','Internet & Telefonia'),
    ('Denílson','Celular','Pessoal & Família','Eletrônicos & Tecnologia'),('Denílson','Computador','Pessoal & Família','Eletrônicos & Tecnologia'),
    ('Eletrônicos','*','Pessoal & Família','Eletrônicos & Tecnologia'),('Investimento','Notebook','Pessoal & Família','Eletrônicos & Tecnologia'),
    ('Supermercado','*','Alimentação','Supermercado'),('Alimentação','Mercado','Alimentação','Supermercado'),
    ('Alimentação','Ifood etc','Alimentação','Restaurantes & Delivery'),('Alimentação','Almoço Trabalho','Alimentação','Restaurantes & Delivery'),
    ('Alimentação','Espetinho','Alimentação','Restaurantes & Delivery'),('Erika','Comida','Alimentação','Restaurantes & Delivery'),
    ('Alimentação','Café','Alimentação','Café & Lanches'),('Alimentação','Cafe da Tarde','Alimentação','Café & Lanches'),
    ('Alimentação','Bolo','Alimentação','Café & Lanches'),('Erika','Doceria','Alimentação','Café & Lanches'),
    ('Alimentação','*','Alimentação','Restaurantes & Delivery'),
    ('Troca crédito pra débito','*','Alimentação','Supermercado'),
    ('Transporte','Moto','Transporte','Moto'),('Automoveis','Moto','Transporte','Moto'),
    ('Transporte','Carro','Transporte','Carro'),('Automoveis','Carro','Transporte','Carro'),
    ('Transporte','Uber','Transporte','Apps & Ônibus'),('Transporte','Ônibus','Transporte','Apps & Ônibus'),
    ('Transporte','*','Transporte','Carro'),('Automoveis','*','Transporte','Carro'),('Auto Movel','*','Transporte','Carro'),
    ('Drogaria','Perfumaria','Saúde & Bem-estar','Beleza & Barbearia'),('Drogaria','*','Saúde & Bem-estar','Farmácia'),
    ('Erika','Dentista','Saúde & Bem-estar','Consultas'),('Denílson','Barbearia','Saúde & Bem-estar','Beleza & Barbearia'),
    ('Erika','Cabeleleiro','Saúde & Bem-estar','Beleza & Barbearia'),
    ('Assinatura','Academia','Saúde & Bem-estar','Academia'),('Denílson','Academia','Saúde & Bem-estar','Academia'),
    ('Lazer','Adega/Bebida/Narguilé','Lazer & Viagens','Bares & Bebidas'),('Lazer','Adega','Lazer & Viagens','Bares & Bebidas'),
    ('Lazer','Bar','Lazer & Viagens','Bares & Bebidas'),('Lazer','Caipirinha','Lazer & Viagens','Bares & Bebidas'),
    ('Lazer','Cerveja','Lazer & Viagens','Bares & Bebidas'),('Bebida','*','Lazer & Viagens','Bares & Bebidas'),
    ('Denílson','Bebida Alcoolica','Lazer & Viagens','Bares & Bebidas'),
    ('Lazer','Compras','Pessoal & Família','Diversos'),
    ('Lazer','Viagem','Lazer & Viagens','Viagens'),('Viagem','*','Lazer & Viagens','Viagens'),
    ('Lazer','*','Lazer & Viagens','Passeios & Eventos'),
    ('Assinatura','*','Lazer & Viagens','Assinaturas & Streaming'),
    ('Investimento','Dj','Educação & Carreira','DJ'),('Investimento','Estudo','Educação & Carreira','Cursos & Estudo'),
    ('Educação','*','Educação & Carreira','Cursos & Estudo'),('Lais','Livro','Educação & Carreira','Cursos & Estudo'),
    ('Investimento','IA','Educação & Carreira','IA & Software'),
    ('Investimento','*','Finanças & Investimentos','Investimentos & Reservas'),
    ('Vestuário','*','Pessoal & Família','Vestuário'),('Denílson','Vestimenta','Pessoal & Família','Vestuário'),
    ('Presente','*','Pessoal & Família','Presentes'),('Denílson','Presente','Pessoal & Família','Presentes'),
    ('Erika','Prensente','Pessoal & Família','Presentes'),
    ('Cachorro Pipoca','*','Pessoal & Família','Pets & Filhos'),('Brayan','*','Pessoal & Família','Pets & Filhos'),
    ('Lais','*','Pessoal & Família','Pets & Filhos'),
    ('Denílson','*','Pessoal & Família','Diversos'),('Erika','*','Pessoal & Família','Diversos'),
    ('Outros','*','Pessoal & Família','Diversos'),
    ('Empréstimo','*','Finanças & Investimentos','Empréstimos & Dívidas'),('Divida','*','Finanças & Investimentos','Empréstimos & Dívidas'),
    ('Cartão de Crédito','*','Finanças & Investimentos','Juros & Tarifas'),('Juros por Atraso','*','Finanças & Investimentos','Juros & Tarifas'),
    ('Operação bancária','*','Finanças & Investimentos','Juros & Tarifas'),
    ('Reajuste','*','Finanças & Investimentos','Ajustes de Saldo'),('Reajuste de fatura','*','Finanças & Investimentos','Ajustes de Saldo'),
    ('Transferência bancária','*','Finanças & Investimentos','Transferências & Faturas')
  ) v(ocat,osub,ncat,nsub);

  -- ===== 4. REGRAS POR DESCRICAO (menor prio vence). also=true vale tambem p/ itens com sub =====
  CREATE TEMP TABLE dr ON COMMIT DROP AS SELECT row_number() OVER () prio, * FROM (VALUES
    ('∅','fatura',NULL,'Finanças & Investimentos','Transferências & Faturas',true),
    ('∅','d[ií]vida',NULL,'Finanças & Investimentos','Empréstimos & Dívidas',true),
    ('∅','mercado livre',NULL,'Finanças & Investimentos','Investimentos & Reservas',true),
    ('∅','.*','Transferência','Finanças & Investimentos','Transferências & Faturas',true),
    ('Erika','lais|brayan|cuidadora|fralda',NULL,'Pessoal & Família','Pets & Filhos',false),
    ('Erika','emprest',NULL,'Finanças & Investimentos','Empréstimos & Dívidas',false),
    ('Erika','dentista|aparelho',NULL,'Saúde & Bem-estar','Consultas',false),
    ('Erika','aluguel',NULL,'Moradia','Aluguel',false),
    ('Erika','agua|água|luz',NULL,'Moradia','Contas',false),
    ('Erika','internet|celular',NULL,'Moradia','Internet & Telefonia',false),
    ('Erika','academia',NULL,'Saúde & Bem-estar','Academia',false),
    ('Erika','cabele|maquiagem|desodorante',NULL,'Saúde & Bem-estar','Beleza & Barbearia',false),
    ('Erika','cart[aã]o|picpay',NULL,'Finanças & Investimentos','Transferências & Faturas',false),
    ('Erika','carregador',NULL,'Pessoal & Família','Eletrônicos & Tecnologia',false),
    ('Erika','mercado',NULL,'Alimentação','Supermercado',false),
    ('Erika','pizza',NULL,'Alimentação','Restaurantes & Delivery',false),
    ('Erika','caf[eé]',NULL,'Alimentação','Café & Lanches',false),
    ('Erika','narguil|adega',NULL,'Lazer & Viagens','Bares & Bebidas',false),
    ('Erika','niver',NULL,'Lazer & Viagens','Passeios & Eventos',false),
    ('Denílson','refrigerante|bala',NULL,'Alimentação','Café & Lanches',false),
    ('Denílson','jbl',NULL,'Pessoal & Família','Eletrônicos & Tecnologia',false),
    ('Denílson','[oó]culos',NULL,'Saúde & Bem-estar','Consultas',false),
    ('Denílson','retrovisor',NULL,'Transporte','Carro',false),
    ('Lais','livro',NULL,'Educação & Carreira','Cursos & Estudo',false),
    ('Assinatura','academia',NULL,'Saúde & Bem-estar','Academia',false),
    ('Assinatura','caf[eé]',NULL,'Alimentação','Café & Lanches',false),
    ('Assinatura','^ifood$',NULL,'Alimentação','Restaurantes & Delivery',false),
    ('Alimentação','tempero|mercado',NULL,'Alimentação','Supermercado',false),
    ('Alimentação','iof',NULL,'Finanças & Investimentos','Juros & Tarifas',false),
    ('Alimentação','passgem|passagem',NULL,'Transporte','Apps & Ônibus',false),
    ('Alimentação','pix erika',NULL,'Pessoal & Família','Diversos',false),
    ('Alimentação','churrasco',NULL,'Lazer & Viagens','Passeios & Eventos',false),
    ('Alimentação','caf[eé]|pastel|salgad|dog house',NULL,'Alimentação','Café & Lanches',false),
    ('Cartão de Crédito','anuidade|iof|juros|encargo|multa|tarifa',NULL,'Finanças & Investimentos','Juros & Tarifas',true),
    ('Cartão de Crédito','.*',NULL,'Finanças & Investimentos','Transferências & Faturas',true),
    ('Casa','mercado',NULL,'Alimentação','Supermercado',false),
    ('Casa','^gas',NULL,'Moradia','Contas',false),
    ('Investimento','caixa de som',NULL,'Educação & Carreira','DJ',false),
    ('Investimento','capcut|google',NULL,'Educação & Carreira','IA & Software',false),
    ('Investimento','livro',NULL,'Educação & Carreira','Cursos & Estudo',false),
    ('Investimento','notbook|notebook',NULL,'Pessoal & Família','Eletrônicos & Tecnologia',false),
    ('Salário','.*',NULL,'Renda','Salário',false),
    ('Presente','.*','Receita','Renda','Renda Extra',false),
    ('Lazer','refrigerante|besteiras',NULL,'Alimentação','Café & Lanches',true),
    ('Lazer','restaurante|mc don',NULL,'Alimentação','Restaurantes & Delivery',true),
    ('Lazer','lazer familia',NULL,'Lazer & Viagens','Passeios & Eventos',true),
    ('Lazer','gasolina',NULL,'Transporte','Carro',false),
    ('Lazer','lanche|salgado',NULL,'Alimentação','Café & Lanches',false),
    ('Lazer','caipirinha',NULL,'Lazer & Viagens','Bares & Bebidas',false),
    ('Drogaria','utens',NULL,'Pessoal & Família','Diversos',true),
    ('Eletrônicos','jogo',NULL,'Lazer & Viagens','Passeios & Eventos',true),
    ('Eletrônicos','celular|impressora',NULL,'Pessoal & Família','Eletrônicos & Tecnologia',true),
    ('Juros por Atraso','reajuste',NULL,'Finanças & Investimentos','Ajustes de Saldo',true),
    ('Transporte','moto|pneu',NULL,'Transporte','Moto',false),
    ('Reajuste','compras casa',NULL,'Moradia','Casa & Manutenção',true),
    ('Reajuste','gasolina',NULL,'Transporte','Carro',true),
    ('Outros','reajuste|ajuste de fatura',NULL,'Finanças & Investimentos','Ajustes de Saldo',true),
    ('Outros','estorno vistoria',NULL,'Transporte','Carro',true),
    ('Outros','pagar juros',NULL,'Finanças & Investimentos','Juros & Tarifas',true),
    ('Outros','^(dinheiro|moeda)$',NULL,'Finanças & Investimentos','Ajustes de Saldo',true),
    ('Outros','smartphone|carregador',NULL,'Pessoal & Família','Eletrônicos & Tecnologia',true),
    ('Outros','^cart[aã]o$',NULL,'Finanças & Investimentos','Transferências & Faturas',true),
    ('Pix','.*','Despesa','Moradia','Internet & Telefonia',true),
    ('Operação bancária','transfer|pagamento',NULL,'Finanças & Investimentos','Transferências & Faturas',true)
  ) v(ocat,rx,tipo,ncat,nsub,also);

  -- ===== 5. FONTES (lancamentos, caixinhas, recorrentes) e ALVO =====
  CREATE TEMP TABLE fonte ON COMMIT DROP AS
    SELECT 'l'::text tab, l.id, c.nome cat, s.nome sub, coalesce(l.descricao,'') descricao, l.tipo,
           (l.caixinha_id IS NOT NULL OR l.subtipo IN ('Provisionamento','Consumo Caixinha')) skip_dr
      FROM lancamentos l LEFT JOIN categorias c ON c.id=l.categoria_id LEFT JOIN subcategorias s ON s.id=l.subcategoria_id
     WHERE l.user_id = uid
    UNION ALL
    SELECT 'c', t.id, c.nome, s.nome, coalesce(t.nome,''), NULL, true
      FROM caixinhas_teto t JOIN categorias c ON c.id=t.categoria_id LEFT JOIN subcategorias s ON s.id=t.subcategoria_id
     WHERE t.user_id = uid
    UNION ALL
    SELECT 'r', r.id, c.nome, s.nome, coalesce(r.descricao,''), r.tipo, false
      FROM transacoes_recorrentes r JOIN categorias c ON c.id=r.categoria_id LEFT JOIN subcategorias s ON s.id=r.subcategoria_id
     WHERE r.user_id = uid;

  CREATE TEMP TABLE alvo ON COMMIT DROP AS
  SELECT f.tab, f.id, f.cat, f.sub, f.descricao, f.tipo,
    coalesce(
      (SELECT d.ncat||'|'||d.nsub FROM dr d
        WHERE d.ocat = coalesce(f.cat,'∅') AND (d.also OR f.sub IS NULL OR f.cat IS NULL)
          AND (d.ocat='∅' OR NOT f.skip_dr) AND f.descricao ~* d.rx AND (d.tipo IS NULL OR d.tipo = f.tipo)
        ORDER BY d.prio LIMIT 1),
      (SELECT r.ncat||'|'||r.nsub FROM sr r WHERE r.ocat = f.cat AND (r.osub = f.sub OR r.osub='*')
        ORDER BY (r.osub='*') LIMIT 1)) alvo
  FROM fonte f;

  SELECT count(*) INTO n_null FROM alvo a
   WHERE a.alvo IS NULL OR NOT EXISTS (SELECT 1 FROM ns WHERE ns.cat||'|'||ns.sub = a.alvo);
  IF n_null > 0 THEN RAISE EXCEPTION 'FAXINA: % itens sem destino mapeado', n_null; END IF;

  -- ===== 6. REPONTAR (caixinhas -> recorrentes -> lancamentos) =====
  UPDATE caixinhas_teto t SET categoria_id = ns.cat_id, subcategoria_id = ns.id
    FROM alvo a JOIN ns ON ns.cat||'|'||ns.sub = a.alvo WHERE a.tab='c' AND a.id = t.id;
  UPDATE transacoes_recorrentes t SET categoria_id = ns.cat_id, subcategoria_id = ns.id
    FROM alvo a JOIN ns ON ns.cat||'|'||ns.sub = a.alvo WHERE a.tab='r' AND a.id = t.id;
  UPDATE lancamentos t SET categoria_id = ns.cat_id, subcategoria_id = ns.id
    FROM alvo a JOIN ns ON ns.cat||'|'||ns.sub = a.alvo WHERE a.tab='l' AND a.id = t.id;

  -- ===== 7. PROVAR 0 REFERENCIAS ANTES DE APAGAR =====
  SELECT (SELECT count(*) FROM lancamentos WHERE categoria_id IN (SELECT id FROM old_cat) OR subcategoria_id IN (SELECT id FROM old_sub))
       + (SELECT count(*) FROM caixinhas_teto WHERE categoria_id IN (SELECT id FROM old_cat) OR subcategoria_id IN (SELECT id FROM old_sub))
       + (SELECT count(*) FROM transacoes_recorrentes WHERE categoria_id IN (SELECT id FROM old_cat) OR subcategoria_id IN (SELECT id FROM old_sub))
    INTO n_ref;
  IF n_ref > 0 THEN RAISE EXCEPTION 'FAXINA: % referencias ainda apontam para IDs antigos', n_ref; END IF;

  DELETE FROM subcategorias WHERE id IN (SELECT id FROM old_sub);
  DELETE FROM categorias WHERE id IN (SELECT id FROM old_cat);

  -- ===== 8. AUDITORIA =====
  SELECT count(*), sum(valor), md5(string_agg((to_jsonb(l)-'categoria_id'-'subcategoria_id'-'atualizado_em')::text,'|' ORDER BY id))
    INTO a_cnt, a_sum, a_fl FROM lancamentos l;
  SELECT md5(string_agg((to_jsonb(c)-'atualizado_em')::text,'|' ORDER BY id)) INTO a_fc FROM contas c;
  SELECT md5(string_agg((to_jsonb(t)-'categoria_id'-'subcategoria_id'-'atualizado_em')::text,'|' ORDER BY id)) INTO a_ft FROM caixinhas_teto t;
  SELECT count(*) INTO n_sem FROM lancamentos WHERE user_id = uid AND (categoria_id IS NULL OR subcategoria_id IS NULL);

  IF a_cnt <> b_cnt OR a_sum <> b_sum THEN RAISE EXCEPTION 'FAXINA: contagem/soma divergiu (% / % -> % / %)', b_cnt, b_sum, a_cnt, a_sum; END IF;
  IF a_fl <> b_fl THEN RAISE EXCEPTION 'FAXINA: fingerprint dos lancamentos mudou (trigger alterou outro campo)'; END IF;
  IF a_fc <> b_fc THEN RAISE EXCEPTION 'FAXINA: fingerprint das contas/saldos mudou'; END IF;
  IF a_ft <> b_ft THEN RAISE EXCEPTION 'FAXINA: fingerprint das caixinhas mudou'; END IF;
  IF n_sem > 0 THEN RAISE EXCEPTION 'FAXINA: % lancamentos do usuario sem categoria/subcategoria', n_sem; END IF;

  INSERT INTO bkp_faxina.auditoria VALUES
   ('antes_depois', jsonb_build_object('lanc_antes',b_cnt,'lanc_depois',a_cnt,'soma_antes',b_sum,'soma_depois',a_sum,
      'fp_lanc_igual',a_fl=b_fl,'fp_contas_igual',a_fc=b_fc,'fp_caixinhas_igual',a_ft=b_ft,'sem_categoria_ou_sub',n_sem,'refs_antigas',n_ref)),
   ('distribuicao', (SELECT jsonb_agg(jsonb_build_object('cat',cat,'sub',sub,'qtd',q,'total',t) ORDER BY cat,sub)
      FROM (SELECT c.nome cat, s.nome sub, count(*) q, sum(l.valor) t FROM lancamentos l
            JOIN categorias c ON c.id=l.categoria_id JOIN subcategorias s ON s.id=l.subcategoria_id
            WHERE l.user_id=uid GROUP BY 1,2) x)),
   ('mapa_lancamentos', (SELECT jsonb_agg(jsonb_build_object('id',id,'de',coalesce(cat,'∅')||' › '||coalesce(sub,'—'),'para',alvo,'descricao',descricao)) FROM alvo WHERE tab='l'));
END
$mig$;

SELECT chave, valor FROM bkp_faxina.auditoria WHERE chave = 'antes_depois';
