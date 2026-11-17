-- Migration 034: elimina dupla contagem residual de consumo de Caixinha
-- (consumo = transferência interna / baixa de provisão; aporte já é o gasto real)

CREATE OR REPLACE FUNCTION public.get_frequencia_gastos_mes(p_mes smallint DEFAULT NULL::smallint, p_ano smallint DEFAULT NULL::smallint)
RETURNS json LANGUAGE plpgsql SECURITY DEFINER AS $function$
DECLARE
  v_user_id UUID := auth.uid();
  v_inicio  DATE;
  v_fim     DATE;
  v_result  JSON;
BEGIN
  IF p_mes IS NOT NULL AND p_ano IS NOT NULL THEN
    v_inicio := DATE(p_ano || '-' || LPAD(p_mes::TEXT, 2, '0') || '-01');
    v_fim    := (v_inicio + INTERVAL '1 month' - INTERVAL '1 day')::DATE;
  ELSE
    v_inicio := DATE_TRUNC('month', CURRENT_DATE)::DATE;
    v_fim    := CURRENT_DATE;
  END IF;

  SELECT JSON_AGG(row ORDER BY row.data) INTO v_result
  FROM (
    SELECT data,
      EXTRACT(DAY FROM data)::INT AS dia,
      SUM(CASE WHEN tipo = 'Despesa' AND NOT public.fn_eh_consumo_caixinha_neutro(caixinha_id, subtipo) THEN valor ELSE 0 END) AS despesas,
      SUM(CASE WHEN tipo = 'Receita' THEN valor ELSE 0 END) AS receitas
    FROM public.lancamentos
    WHERE user_id = v_user_id AND public.fn_membro_visivel(membro_id)
      AND data BETWEEN v_inicio AND v_fim
      AND status = 'Pago'
    GROUP BY data
  ) row;

  RETURN COALESCE(v_result, '[]'::JSON);
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_financial_totals()
RETURNS jsonb LANGUAGE plpgsql SET search_path TO 'public' AS $function$
DECLARE
    v_receitas DECIMAL(12,2);
    v_despesas DECIMAL(12,2);
BEGIN
    SELECT COALESCE(SUM(valor), 0) INTO v_receitas FROM public.lancamentos WHERE tipo = 'Receita';
    SELECT COALESCE(SUM(valor), 0) INTO v_despesas FROM public.lancamentos
     WHERE tipo = 'Despesa' AND NOT public.fn_eh_consumo_caixinha_neutro(caixinha_id, subtipo);
    RETURN jsonb_build_object('receitas', v_receitas, 'despesas', v_despesas, 'saldo', v_receitas - v_despesas);
END;
$function$;

CREATE OR REPLACE FUNCTION public.get_cobertura_reserva(p_data_inicio date, p_data_fim date)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path TO 'public' AS $function$
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
               AND public.fn_eh_despesa_orcamento_ativa(l.caixinha_id, l.subtipo, l.status::text)
               AND pt.posicao IN (1, 2)
               AND l.data_vencimento BETWEEN p_data_inicio AND p_data_fim
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
END $function$;
