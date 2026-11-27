-- 010_padronizar_potes_e_dembox.sql
-- Padronizacao dos 6 Potes Financeiros, seeds para novos usuarios e ajustes de DemBoxes.
-- Preserva 100% dos percentuais salvos, IDs, saldos, slugs internos e contas de teste.
-- Backup local: backup_potes_dembox_pre_padronizacao.json

-- 1. Novos usuarios: 6 Potes padronizados (soma = 100%)
CREATE OR REPLACE FUNCTION public.seed_potes_usuario(p_user uuid)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
BEGIN
  IF EXISTS (SELECT 1 FROM public.potes WHERE user_id = p_user) THEN
    RETURN;
  END IF;

  INSERT INTO public.potes (user_id, posicao, nome, percentual, cor) VALUES
    (p_user, 1, 'Contas Fixas', 35, '#007AFF'),
    (p_user, 2, 'Dia a Dia',    15, '#FF69B4'),
    (p_user, 3, 'Metas',        10, '#800080'),
    (p_user, 4, 'Prazeres',     20, '#FF7A00'),
    (p_user, 5, 'Evolução',      5, '#FFD60A'),
    (p_user, 6, 'Liberdade',    15, '#6C5CE7');
END $function$;

-- 2. Novos usuarios: 9 Categorias macro enxutas + Subcategorias genericas (UTF-8 limpo)
CREATE OR REPLACE FUNCTION public.seed_dados_padrao_usuario()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
DECLARE
    v_cat_id uuid;
BEGIN
    INSERT INTO public.contas (perfil_id, user_id, nome) VALUES
        (NEW.id, NEW.id, 'Santander'),
        (NEW.id, NEW.id, 'Itaú'),
        (NEW.id, NEW.id, 'Inter'),
        (NEW.id, NEW.id, 'Dinheiro');

    -- 1. Renda
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Renda', '💰', '#34D399', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Salário', '#34D399', true),
        (v_cat_id, NEW.id, 'Adiantamento & Benefícios', '#34D399', true),
        (v_cat_id, NEW.id, 'Renda Extra', '#34D399', true);

    -- 2. Moradia
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Moradia', '🏡', '#38BDF8', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Aluguel', '#38BDF8', true),
        (v_cat_id, NEW.id, 'Contas', '#38BDF8', true),
        (v_cat_id, NEW.id, 'Internet & Telefonia', '#38BDF8', true),
        (v_cat_id, NEW.id, 'Casa & Manutenção', '#38BDF8', true);

    -- 3. Alimentação
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Alimentação', '🍔', '#FBBF24', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Supermercado', '#FBBF24', true),
        (v_cat_id, NEW.id, 'Restaurantes & Delivery', '#FBBF24', true),
        (v_cat_id, NEW.id, 'Café & Lanches', '#FBBF24', true);

    -- 4. Transporte
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Transporte', '🚗', '#FB7185', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Moto', '#FB7185', true),
        (v_cat_id, NEW.id, 'Carro', '#FB7185', true),
        (v_cat_id, NEW.id, 'Apps & Ônibus', '#FB7185', true);

    -- 5. Saúde & Bem-estar
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Saúde & Bem-estar', '💊', '#2DD4BF', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Farmácia', '#2DD4BF', true),
        (v_cat_id, NEW.id, 'Academia', '#2DD4BF', true),
        (v_cat_id, NEW.id, 'Consultas', '#2DD4BF', true),
        (v_cat_id, NEW.id, 'Beleza & Barbearia', '#2DD4BF', true);

    -- 6. Lazer & Viagens
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Lazer & Viagens', '🍻', '#FB923C', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Bares & Bebidas', '#FB923C', true),
        (v_cat_id, NEW.id, 'Passeios & Eventos', '#FB923C', true),
        (v_cat_id, NEW.id, 'Viagens', '#FB923C', true),
        (v_cat_id, NEW.id, 'Assinaturas & Streaming', '#FB923C', true);

    -- 7. Educação & Carreira
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Educação & Carreira', '🎓', '#818CF8', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Cursos & Estudo', '#818CF8', true),
        (v_cat_id, NEW.id, 'Projetos & Trabalho', '#818CF8', true),
        (v_cat_id, NEW.id, 'IA & Software', '#818CF8', true);

    -- 8. Pessoal & Família
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Pessoal & Família', '👨‍👩‍👦', '#A78BFA', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Vestuário', '#A78BFA', true),
        (v_cat_id, NEW.id, 'Presentes', '#A78BFA', true),
        (v_cat_id, NEW.id, 'Pets & Filhos', '#A78BFA', true),
        (v_cat_id, NEW.id, 'Eletrônicos & Tecnologia', '#A78BFA', true),
        (v_cat_id, NEW.id, 'Diversos', '#A78BFA', true);

    -- 9. Finanças & Investimentos
    INSERT INTO public.categorias (perfil_id, user_id, nome, icone, cor, tipo, ativo)
    VALUES (NEW.id, NEW.id, 'Finanças & Investimentos', '📈', '#60A5FA', 'ambos', true) RETURNING id INTO v_cat_id;
    INSERT INTO public.subcategorias (categoria_id, user_id, nome, cor, ativo) VALUES
        (v_cat_id, NEW.id, 'Investimentos & Reservas', '#60A5FA', true),
        (v_cat_id, NEW.id, 'Empréstimos & Dívidas', '#60A5FA', true),
        (v_cat_id, NEW.id, 'Juros & Tarifas', '#60A5FA', true),
        (v_cat_id, NEW.id, 'Ajustes de Saldo', '#60A5FA', true),
        (v_cat_id, NEW.id, 'Transferências & Faturas', '#60A5FA', true);

    RETURN NEW;
END;
$function$;

-- 3. Padronizar prefixo de descricao nas novas provisoes automaticas: 'Provisão DemBox · '
CREATE OR REPLACE FUNCTION public.fn_sincronizar_provisoes_caixinha(p_caixinha_id uuid, p_meses integer DEFAULT 12)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
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

    IF v_cx.recorrente = TRUE AND v_inicio < CURRENT_DATE THEN
        IF EXTRACT(DAY FROM CURRENT_DATE) > v_dia THEN
            v_inicio := (DATE_TRUNC('month', CURRENT_DATE) + INTERVAL '1 month')::DATE;
        ELSE
            v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
        END IF;
    END IF;

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

        IF v_cx.recorrente = TRUE AND v_dt < CURRENT_DATE THEN
            CONTINUE;
        END IF;

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
                v_cx.valor_meta, v_dt, 'Provisão DemBox · ' || v_cx.nome, 'Pendente',
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
                descricao = 'Provisão DemBox · ' || v_cx.nome,
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
$function$;

-- 4. Renomeacao atomica de potes/potes_mensais + ajustes nos 2 DemBoxes (apenas conta principal)
DO $mig$
DECLARE
    uid uuid := '07614dd5-3a3a-4538-8cc0-915a18c1fd85';
    v_cat_fin uuid;
    v_sub_div uuid;
    b_potes_fp text; a_potes_fp text;
    b_pm_fp text;    a_pm_fp text;
    b_cx_fp text;    a_cx_fp text;
    b_lanc_sum numeric; a_lanc_sum numeric;
BEGIN
    PERFORM set_config('dembase.pular_recalculo', 'on', true);
    PERFORM set_config('dembase.fluxo_fatura', 'on', true);

    -- Baseline (preservar percentuais, IDs, saldos e totais)
    SELECT md5(string_agg(id::text || ':' || posicao::text || ':' || percentual::text || ':' || cor, '|' ORDER BY posicao))
      INTO b_potes_fp FROM public.potes WHERE user_id = uid;
    SELECT md5(string_agg(id::text || ':' || ano::text || ':' || mes::text || ':' || posicao::text || ':' || percentual::text, '|' ORDER BY ano, mes, posicao))
      INTO b_pm_fp FROM public.potes_mensais WHERE user_id = uid;
    SELECT md5(string_agg(id::text || ':' || valor_meta::text || ':' || saldo_atual::text || ':' || ativo::text, '|' ORDER BY id))
      INTO b_cx_fp FROM public.caixinhas_teto WHERE user_id = uid;
    SELECT COALESCE(SUM(valor), 0) INTO b_lanc_sum FROM public.lancamentos WHERE user_id = uid;

    -- Renomear potes (preservando 100% dos percentuais salvos)
    UPDATE public.potes SET nome = CASE posicao
        WHEN 1 THEN 'Contas Fixas'
        WHEN 2 THEN 'Dia a Dia'
        WHEN 3 THEN 'Metas'
        WHEN 4 THEN 'Prazeres'
        WHEN 5 THEN 'Evolução'
        WHEN 6 THEN 'Liberdade'
        ELSE nome
    END
    WHERE user_id = uid;

    -- Renomear potes_mensais (snapshots historicos do mesmo usuario)
    UPDATE public.potes_mensais SET nome = CASE posicao
        WHEN 1 THEN 'Contas Fixas'
        WHEN 2 THEN 'Dia a Dia'
        WHEN 3 THEN 'Metas'
        WHEN 4 THEN 'Prazeres'
        WHEN 5 THEN 'Evolução'
        WHEN 6 THEN 'Liberdade'
        ELSE nome
    END
    WHERE user_id = uid;

    -- Vincular 'Dívida com a Chefe' -> Finanças & Investimentos > Empréstimos & Dívidas
    SELECT c.id, s.id INTO v_cat_fin, v_sub_div
      FROM public.categorias c
      JOIN public.subcategorias s ON s.categoria_id = c.id
     WHERE c.user_id = uid
       AND c.nome = 'Finanças & Investimentos'
       AND s.nome = 'Empréstimos & Dívidas'
     LIMIT 1;

    IF v_cat_fin IS NOT NULL AND v_sub_div IS NOT NULL THEN
        UPDATE public.caixinhas_teto
           SET categoria_id = v_cat_fin,
               subcategoria_id = v_sub_div
         WHERE id = 'f3a1ab42-4eac-4597-91f5-934c7703f60b'
           AND user_id = uid;
    END IF;

    -- Corrigir acento em 'Fatura Itau' -> 'Fatura Itaú'
    UPDATE public.caixinhas_teto
       SET nome = 'Fatura Itaú'
     WHERE id = '15452bc4-3068-45fc-95e3-56625239e572'
       AND user_id = uid;

    -- Conferencia pos-execucao (aborta com ROLLBACK se qualquer numero mudar)
    SELECT md5(string_agg(id::text || ':' || posicao::text || ':' || percentual::text || ':' || cor, '|' ORDER BY posicao))
      INTO a_potes_fp FROM public.potes WHERE user_id = uid;
    SELECT md5(string_agg(id::text || ':' || ano::text || ':' || mes::text || ':' || posicao::text || ':' || percentual::text, '|' ORDER BY ano, mes, posicao))
      INTO a_pm_fp FROM public.potes_mensais WHERE user_id = uid;
    SELECT md5(string_agg(id::text || ':' || valor_meta::text || ':' || saldo_atual::text || ':' || ativo::text, '|' ORDER BY id))
      INTO a_cx_fp FROM public.caixinhas_teto WHERE user_id = uid;
    SELECT COALESCE(SUM(valor), 0) INTO a_lanc_sum FROM public.lancamentos WHERE user_id = uid;

    IF a_potes_fp IS DISTINCT FROM b_potes_fp THEN RAISE EXCEPTION 'PADRONIZACAO: percentual/ID/cor de potes alterado!'; END IF;
    IF a_pm_fp IS DISTINCT FROM b_pm_fp THEN RAISE EXCEPTION 'PADRONIZACAO: percentual de potes_mensais alterado!'; END IF;
    IF a_cx_fp IS DISTINCT FROM b_cx_fp THEN RAISE EXCEPTION 'PADRONIZACAO: saldo/meta de caixinhas_teto alterado!'; END IF;
    IF a_lanc_sum IS DISTINCT FROM b_lanc_sum THEN RAISE EXCEPTION 'PADRONIZACAO: soma de lancamentos alterada!'; END IF;
END
$mig$;

-- Conferencia imediata
SELECT p.posicao, p.nome, p.percentual,
       (SELECT count(*) FROM public.lancamentos l WHERE l.pote_id = p.id) AS qtd_lanc,
       (SELECT COALESCE(SUM(valor), 0) FROM public.lancamentos l WHERE l.pote_id = p.id) AS soma_lanc
  FROM public.potes p
 WHERE p.user_id = '07614dd5-3a3a-4538-8cc0-915a18c1fd85'
 ORDER BY p.posicao;
