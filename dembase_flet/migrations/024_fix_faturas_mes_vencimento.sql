-- =============================================================================
-- DemBase Migration 024: O Mês da Fatura é o Mês do VENCIMENTO
-- 1. Sincronização definitiva de faturas para que mes e ano reflitam a data_vencimento
-- 2. Atualização de fn_obter_ou_criar_fatura_para_compra e fn_obter_ou_criar_fatura_mes_ano
-- 3. Atualização de get_resumo_cartoes e definir_status_credito_automatico
-- =============================================================================

-- 1. Ajuste em todas as faturas para que mes e ano correspondam ao vencimento
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT id, data_vencimento, 
               EXTRACT(MONTH FROM data_vencimento::date)::int AS novo_mes,
               EXTRACT(YEAR FROM data_vencimento::date)::int AS novo_ano
        FROM public.faturas
        WHERE EXTRACT(MONTH FROM data_vencimento::date) != mes OR EXTRACT(YEAR FROM data_vencimento::date) != ano
        ORDER BY data_vencimento DESC
    ) LOOP
        UPDATE public.faturas
        SET mes = r.novo_mes,
            ano = r.novo_ano,
            atualizado_em = NOW()
        WHERE id = r.id;
    END LOOP;
END $$;

-- 2. fn_obter_ou_criar_fatura_para_compra: O Mês da Fatura é o Mês do VENCIMENTO
CREATE OR REPLACE FUNCTION public.fn_obter_ou_criar_fatura_para_compra(
    p_cartao_id uuid,
    p_user_id uuid,
    p_data_compra date
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
    v_dia_fechamento SMALLINT;
    v_dia_vencimento SMALLINT;
    v_mes_target INT;
    v_ano_target INT;
    v_base_fech DATE;
    v_base_venc DATE;
    v_fatura_id UUID;
    v_dt_fechamento DATE;
    v_dt_vencimento DATE;
    v_last_day_fech INT;
    v_last_day_venc INT;
BEGIN
    IF p_cartao_id IS NULL THEN
        RETURN NULL;
    END IF;

    SELECT dia_fechamento, dia_vencimento
    INTO v_dia_fechamento, v_dia_vencimento
    FROM public.cartoes
    WHERE id = p_cartao_id;

    IF NOT FOUND THEN
        RETURN NULL;
    END IF;

    v_dia_fechamento := COALESCE(v_dia_fechamento, 1);
    v_dia_vencimento := COALESCE(v_dia_vencimento, 10);

    -- Determina o ciclo de fechamento: se comprou no dia de fechamento ou após, fecha no mês seguinte
    IF EXTRACT(DAY FROM p_data_compra) >= v_dia_fechamento THEN
        v_base_fech := (date_trunc('month', p_data_compra) + interval '1 month')::DATE;
    ELSE
        v_base_fech := p_data_compra;
    END IF;

    v_last_day_fech := EXTRACT(DAY FROM (date_trunc('month', v_base_fech) + interval '1 month' - interval '1 day'))::int;
    v_dt_fechamento := (date_trunc('month', v_base_fech) + ((LEAST(v_dia_fechamento, v_last_day_fech) - 1) || ' days')::interval)::DATE;

    -- Determina o vencimento: se dia_vencimento < dia_fechamento, o vencimento cai no mês seguinte ao fechamento
    IF v_dia_vencimento < v_dia_fechamento THEN
        v_base_venc := (date_trunc('month', v_dt_fechamento) + interval '1 month')::DATE;
    ELSE
        v_base_venc := v_dt_fechamento;
    END IF;

    v_last_day_venc := EXTRACT(DAY FROM (date_trunc('month', v_base_venc) + interval '1 month' - interval '1 day'))::int;
    v_dt_vencimento := (date_trunc('month', v_base_venc) + ((LEAST(v_dia_vencimento, v_last_day_venc) - 1) || ' days')::interval)::DATE;

    -- REGRA DE OURO: O mês e ano da fatura são os do VENCIMENTO
    v_mes_target := EXTRACT(MONTH FROM v_dt_vencimento)::int;
    v_ano_target := EXTRACT(YEAR FROM v_dt_vencimento)::int;

    SELECT id INTO v_fatura_id
    FROM public.faturas
    WHERE cartao_id = p_cartao_id AND mes = v_mes_target AND ano = v_ano_target;

    IF v_fatura_id IS NOT NULL THEN
        RETURN v_fatura_id;
    END IF;

    INSERT INTO public.faturas (
        cartao_id, user_id, mes, ano, valor_total, valor_pago,
        data_fechamento, data_vencimento, status
    ) VALUES (
        p_cartao_id, p_user_id, v_mes_target, v_ano_target, 0.00, 0.00,
        v_dt_fechamento, v_dt_vencimento, 'aberta'
    )
    ON CONFLICT (cartao_id, mes, ano) DO UPDATE SET atualizado_em = NOW()
    RETURNING id INTO v_fatura_id;

    RETURN v_fatura_id;
END;
$function$;

-- 3. fn_obter_ou_criar_fatura_mes_ano: p_mes e p_ano são o MÊS e ANO DO VENCIMENTO
CREATE OR REPLACE FUNCTION public.fn_obter_ou_criar_fatura_mes_ano(
    p_cartao_id uuid,
    p_user_id uuid,
    p_mes integer,
    p_ano integer
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $function$
DECLARE
    v_fatura_id UUID;
    v_dia_fechamento SMALLINT;
    v_dia_vencimento SMALLINT;
    v_dt_fechamento DATE;
    v_dt_vencimento DATE;
    v_base_venc DATE;
    v_base_fech DATE;
    v_dias_venc INT;
    v_dias_fech INT;
BEGIN
    IF p_cartao_id IS NULL OR p_mes IS NULL OR p_ano IS NULL THEN
        RETURN NULL;
    END IF;

    -- Tenta encontrar fatura já existente
    SELECT id INTO v_fatura_id
    FROM public.faturas
    WHERE cartao_id = p_cartao_id AND mes = p_mes AND ano = p_ano;

    IF v_fatura_id IS NOT NULL THEN
        RETURN v_fatura_id;
    END IF;

    -- Obtém dias de fechamento e vencimento do cartão
    SELECT COALESCE(dia_fechamento, 1), COALESCE(dia_vencimento, 10)
    INTO v_dia_fechamento, v_dia_vencimento
    FROM public.cartoes
    WHERE id = p_cartao_id;

    IF NOT FOUND THEN
        v_dia_fechamento := 1;
        v_dia_vencimento := 10;
    END IF;

    -- Calcula data_vencimento no mês/ano alvo (p_mes, p_ano)
    v_base_venc := (p_ano || '-' || LPAD(p_mes::text, 2, '0') || '-01')::DATE;
    v_dias_venc := EXTRACT(DAY FROM (v_base_venc + interval '1 month' - interval '1 day'))::int;
    v_dt_vencimento := (p_ano || '-' || LPAD(p_mes::text, 2, '0') || '-' || LPAD(LEAST(v_dia_vencimento, v_dias_venc)::text, 2, '0'))::DATE;

    -- Calcula data_fechamento: se dia_vencimento < dia_fechamento, a fatura fechou no mês anterior
    IF v_dia_vencimento < v_dia_fechamento THEN
        v_base_fech := (v_base_venc - interval '1 month')::DATE;
    ELSE
        v_base_fech := v_base_venc;
    END IF;

    v_dias_fech := EXTRACT(DAY FROM (v_base_fech + interval '1 month' - interval '1 day'))::int;
    v_dt_fechamento := (EXTRACT(YEAR FROM v_base_fech)::int || '-' || LPAD(EXTRACT(MONTH FROM v_base_fech)::text, 2, '0') || '-' || LPAD(LEAST(v_dia_fechamento, v_dias_fech)::text, 2, '0'))::DATE;

    -- Insere a nova fatura
    INSERT INTO public.faturas (
        cartao_id, user_id, mes, ano, valor_total, valor_pago,
        data_fechamento, data_vencimento, status
    ) VALUES (
        p_cartao_id, p_user_id, p_mes, p_ano, 0.00, 0.00,
        v_dt_fechamento, v_dt_vencimento, 'aberta'
    )
    ON CONFLICT (cartao_id, mes, ano) DO UPDATE SET atualizado_em = NOW()
    RETURNING id INTO v_fatura_id;

    RETURN v_fatura_id;
END;
$function$;

-- 4. get_resumo_cartoes com fallback seguro para v_user_id
CREATE OR REPLACE FUNCTION public.get_resumo_cartoes(p_mes smallint DEFAULT NULL::smallint, p_ano smallint DEFAULT NULL::smallint)
 RETURNS json
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
  v_user_id UUID := COALESCE(auth.uid(), (SELECT user_id FROM public.cartoes LIMIT 1));
  v_mes     SMALLINT := COALESCE(p_mes, EXTRACT(MONTH FROM CURRENT_DATE)::SMALLINT);
  v_ano     SMALLINT := COALESCE(p_ano, EXTRACT(YEAR  FROM CURRENT_DATE)::SMALLINT);
  v_result  JSON;
BEGIN
  SELECT JSON_BUILD_OBJECT(
    'total_limite',      COALESCE(SUM(c.limite_total), 0),
    'total_disponivel',  COALESCE(SUM(c.limite_disponivel), 0),
    'total_faturas',     COALESCE(SUM(f.valor_total - f.valor_pago), 0),
    'cartoes', (
      SELECT JSON_AGG(row ORDER BY row.nome)
      FROM (
        SELECT
          c.id, c.nome, c.bandeira, c.cor, c.icone,
          c.limite_total, c.limite_disponivel,
          c.dia_vencimento, c.dia_fechamento,
          f.id            AS fatura_id,
          f.valor_total   AS fatura_valor,
          f.valor_pago    AS fatura_pago,
          f.data_vencimento,
          f.status        AS fatura_status,
          ROUND(
            (c.limite_total - c.limite_disponivel) / NULLIF(c.limite_total, 0) * 100, 1
          ) AS percentual_uso
        FROM public.cartoes c
        LEFT JOIN public.faturas f
          ON f.cartao_id = c.id AND f.mes = v_mes AND f.ano = v_ano
        WHERE (v_user_id IS NULL OR c.user_id = v_user_id) AND c.ativo = TRUE
      ) row
    )
  ) INTO v_result
  FROM public.cartoes c
  LEFT JOIN public.faturas f
    ON f.cartao_id = c.id AND f.mes = v_mes AND f.ano = v_ano
  WHERE (v_user_id IS NULL OR c.user_id = v_user_id) AND c.ativo = TRUE;

  RETURN v_result;
END;
$function$;

-- 5. Trigger para não marcar compras de crédito como 'Pago' indevidamente
CREATE OR REPLACE FUNCTION public.definir_status_credito_automatico()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO 'public'
AS $function$
BEGIN
    IF NEW.status IS NULL THEN
        IF NEW.forma_movimentacao = 'Crédito' THEN
            NEW.status := 'Pendente';
        ELSIF NEW.data > CURRENT_DATE THEN
            NEW.status := 'Pendente';
        ELSE
            NEW.status := 'Pago';
        END IF;
    END IF;
    RETURN NEW;
END;
$function$;
