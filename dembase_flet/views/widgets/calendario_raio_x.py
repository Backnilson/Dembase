"""
=============================================================================
DemBase v3 — views/widgets/calendario_raio_x.py
Módulo Unificado de Inteligência do Calendário: "Raio-X do Dia"
Fonte única da verdade compartilhada entre o Tooltip de hover e o Modal detalhado.
- Cálculo estruturado do Raio-X diário (acumulados, teto seguro gastável, gargalo, movimentação)
- Gerador de texto compatível para o Tooltip
- Componente visual responsivo do Raio-X para o Modal (Desktop e Mobile)
- Mini-gráfico vetorial (Canvas Sparkline) da evolução do saldo acumulado do mês.
- Componente de Modal Completo Unificado ("Raio-X do Dia" + Lançamentos) consumido
  tanto pelo Calendário quanto pelo Dashboard sem código duplicado.
=============================================================================
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Callable, Optional

import flet as ft
import flet.canvas as cv

from core import theme as T
from core.constants import formatar_data_br, formatar_moeda
from core.theme import abrir_dialogo, fechar_dialogo
from core.potes import calcular_teto_seguro_gastavel
from core.theme import borda, pad


def calcular_raio_x_dia(
    dia_info: dict,
    vencimentos_dia: list[dict],
    data_inicio_filtro: str,
    acumulados_por_dia: dict,
    pct_investimento: float | None = None,
    travar_pelo_pior_dia: bool = True,
    sobra_projetada_mes: float | None = None,
) -> dict:
    """
    FONTE ÚNICA DE VERDADE:
    Extrai e consolida a estrutura de dados completa do dia do calendário.
    Consumida obrigatoriamente tanto pelo Tooltip quanto pelo Modal do Dia.
    Calcula o Teto Seguro Gastável com base na fatia de prazeres/gastável
    sem comprometer o que o usuário decidiu investir.
    """
    dt_str = str(dia_info.get("data") or "")[:10]
    rec_d = float(dia_info.get("total_receitas", 0) or 0.0)
    desp_d = float(dia_info.get("total_despesas", 0) or 0.0)
    desp_cta = float(dia_info.get("despesas_conta", 0) or 0.0)
    desp_crt = float(dia_info.get("despesas_cartao", 0) or 0.0)
    saldo_d = rec_d - desp_d
    qtd_d = int(dia_info.get("qtd_lancamentos", 0) or 0)

    # Obter o acumulado deste dia
    acum = {}
    if acumulados_por_dia and dt_str in acumulados_por_dia:
        acum = acumulados_por_dia[dt_str]
    elif isinstance(dia_info.get("acumulado"), dict):
        acum = dia_info["acumulado"]

    d_ini_ac = str(acum.get("data_inicio_acum") or acum.get("data_inicio_filtro") or data_inicio_filtro or "")[:10]
    rec_ac = float(acum.get("receitas_acum", rec_d) or 0.0)
    desp_cta_ac = float(acum.get("despesas_conta_acum", desp_cta) or 0.0)
    desp_crt_ac = float(acum.get("despesas_cartao_acum", desp_crt) or 0.0)
    desp_tot_ac = float(acum.get("despesas_total_acum", desp_d) or 0.0)
    saldo_ac = float(acum.get("saldo_acum", rec_ac - desp_tot_ac) or 0.0)

    menor_apos = float(acum.get("menor_saldo_apos_dia", dia_info.get("menor_saldo_apos_dia", saldo_ac)) or 0.0)
    dt_garg_apos = acum.get("data_gargalo_apos_dia") or dia_info.get("data_gargalo_apos_dia")

    # Percentual de investimento a ser respeitado (sagrado)
    if pct_investimento is None:
        pct_investimento = float(acum.get("pct_investimento", dia_info.get("pct_investimento", 50.0)) or 50.0)

    sobra_ref = sobra_projetada_mes if sobra_projetada_mes is not None else float(acum.get("sobra_projetada", saldo_ac) or saldo_ac)

    # FONTE ÚNICA: Teto Seguro p/ Gastar
    res_teto = calcular_teto_seguro_gastavel(
        sobra_projetada=max(0.0, sobra_ref),
        menor_saldo_futuro=menor_apos,
        pct_investimento=pct_investimento,
        travar_pelo_pior_dia=travar_pelo_pior_dia,
    )
    teto_apos = res_teto["teto_seguro_gasto"]

    eh_garg_princ = bool(dia_info.get("eh_gargalo_principal") or acum.get("eh_gargalo_principal"))
    eh_garg_jan = bool(dia_info.get("eh_gargalo_janela") or acum.get("eh_gargalo_janela"))
    eh_neg_dia = bool(dia_info.get("eh_dia_negativo") or (saldo_ac < 0))
    dia_fora_mes = bool(dia_info.get("fora_do_mes", False) or not dia_info.get("no_mes_atual", True))

    if eh_garg_princ:
        status_dia = "PIOR DIA (GARGALO)"
    elif eh_neg_dia:
        status_dia = "SALDO NEGATIVO"
    elif eh_garg_jan:
        status_dia = "PISO DA JANELA"
    else:
        status_dia = "EQUILIBRADO"

    caixinhas = [
        cx_l
        for cx_l in (dia_info.get("lancamentos") or [])
        if cx_l.get("caixinha_id") or str(cx_l.get("subtipo") or "").lower() == "provisionamento"
    ]

    return {
        "data": dt_str,
        "data_formatada": formatar_data_br(dt_str) if dt_str else "",
        "status_dia": status_dia,
        "eh_gargalo_principal": eh_garg_princ,
        "eh_gargalo_janela": eh_garg_jan,
        "eh_negativo": eh_neg_dia,
        "dia_fora_mes": dia_fora_mes,
        "qtd_movimentacoes": qtd_d,
        # Acumulado
        "data_inicio_acum": d_ini_ac,
        "periodo_acum_texto": f"{formatar_data_br(d_ini_ac)} até {formatar_data_br(dt_str)}" if d_ini_ac and dt_str else "",
        "receitas_acum": rec_ac,
        "despesas_conta_acum": desp_cta_ac,
        "despesas_cartao_acum": desp_crt_ac,
        "despesas_total_acum": desp_tot_ac,
        "saldo_acum": saldo_ac,
        # Teto Seguro Gastável
        "teto_seguro": teto_apos,
        "pct_investimento": res_teto["pct_investimento"],
        "pct_gastavel": res_teto["pct_gastavel"],
        "valor_investir": res_teto["valor_investir"],
        "valor_gastavel": res_teto["valor_gastavel"],
        "rotulo_teto": res_teto["rotulo"],
        "subtexto_teto": res_teto["subtexto"],
        "menor_saldo_futuro": menor_apos,
        "data_menor_saldo": dt_garg_apos,
        "data_menor_saldo_formatada": formatar_data_br(dt_garg_apos) if dt_garg_apos else "",
        # Movimento Isolado do Dia
        "receita_dia": rec_d,
        "despesa_dia": desp_d,
        "despesa_conta_dia": desp_cta,
        "despesa_cartao_dia": desp_crt,
        "saldo_dia": saldo_d,
        # Entidades e Listas
        "vencimentos": vencimentos_dia or [],
        "caixinhas": caixinhas,
        "lancamentos": dia_info.get("lancamentos") or [],
    }


def montar_texto_tooltip_raio_x(raio_x: dict) -> str:
    """
    Gera o texto completo do Tooltip de hover a partir da estrutura calculada do Raio-X.
    Preserva rigorosamente a formatação e reflete o Teto Seguro p/ Gastar
    descontando a parcela de investimento.
    """
    dt_str = raio_x["data"]
    qtd_d = raio_x["qtd_movimentacoes"]
    eh_garg_princ = raio_x["eh_gargalo_principal"]
    d_ini_ac = raio_x["data_inicio_acum"]
    rec_ac = raio_x["receitas_acum"]
    desp_tot_ac = raio_x["despesas_total_acum"]
    desp_cta_ac = raio_x["despesas_conta_acum"]
    desp_crt_ac = raio_x["despesas_cartao_acum"]
    saldo_ac = raio_x["saldo_acum"]
    teto_apos = raio_x["teto_seguro"]
    pct_inv = raio_x.get("pct_investimento", 50.0)
    menor_apos = raio_x["menor_saldo_futuro"]
    dt_garg_apos = raio_x["data_menor_saldo"]
    rec_d = raio_x["receita_dia"]
    desp_d = raio_x["despesa_dia"]
    desp_cta = raio_x["despesa_conta_dia"]
    desp_crt = raio_x["despesa_cartao_dia"]
    saldo_d = raio_x["saldo_dia"]
    vencimentos_dia = raio_x["vencimentos"]
    caixinhas = raio_x["caixinhas"]

    sub_inv = f"Já descontado {pct_inv:g}% para investir"
    detalhe_garg = (
        f" (Menor saldo futuro: {formatar_moeda(menor_apos)} em {formatar_data_br(dt_garg_apos)})"
        if dt_garg_apos and menor_apos < teto_apos
        else ""
    )

    linhas = [
        f"📅 {formatar_data_br(dt_str)} ({qtd_d} mov. no dia)" + (" — ⚠️ PIOR DIA (GARGALO)" if eh_garg_princ else ""),
        f"── Acumulado ({formatar_data_br(d_ini_ac)} até {formatar_data_br(dt_str)}) ──",
        f"💰 Receitas Acum.: {formatar_moeda(rec_ac)}",
        f"💳 Despesas Acum.: {formatar_moeda(desp_tot_ac)} (Conta: {formatar_moeda(desp_cta_ac)} | Faturas: {formatar_moeda(desp_crt_ac)})",
        f"💵 SALDO ACUMULADO: {formatar_moeda(saldo_ac)}",
        f"🛡️ TETO SEGURO P/ GASTAR: {formatar_moeda(teto_apos)} ({sub_inv}){detalhe_garg}",
        f"── Movimento Isolado do Dia ──",
        f"   • Entradas Dia: {formatar_moeda(rec_d)} | Saídas Dia: {formatar_moeda(desp_d)} (Conta: {formatar_moeda(desp_cta)} | Cartão: {formatar_moeda(desp_crt)})",
        f"   • Saldo do Dia: {formatar_moeda(saldo_d)}",
    ]
    for vf in vencimentos_dia:
        st_f = str(vf.get("status") or "aberta").upper()
        linhas.append(
            f"💳 Vencimento {vf.get('cartao_nome')}: {formatar_moeda(float(vf.get('valor_total', 0) or 0))} ({st_f})"
        )
    for cx_l in caixinhas:
        cx_n = cx_l.get("caixinha_nome") or cx_l.get("descricao") or "Caixinha"
        cx_v = float(cx_l.get("valor", 0) or 0)
        cx_st = str(cx_l.get("status") or "Pendente").upper()
        linhas.append(f"📦 Caixinha {cx_n}: {formatar_moeda(cx_v)} ({cx_st})")
    if qtd_d > 0 or vencimentos_dia:
        linhas.append("👉 Clique para abrir os detalhes desta data")
    return "\n".join(linhas)


def construir_sparkline_saldo_acumulado(
    dias_calendario: list[dict],
    data_selecionada_iso: str,
    data_gargalo_iso: Optional[str] = None,
    largura: int = 370,
    altura: int = 56,
) -> ft.Control:
    """
    Constrói um Sparkline vetorial ultraleve (Canvas) com a evolução do Saldo Acumulado
    ao longo de todos os dias do mês, destacando:
    - O ponto do dia selecionado (Círculo Azul)
    - O ponto do menor saldo / gargalo (Círculo Vermelho/Laranja)
    - A linha zero (eixo neutro).
    """
    pontos: list[tuple[int, str, float]] = []
    for d in dias_calendario:
        if not d.get("no_mes_atual", True):
            continue
        dt_d = str(d.get("data") or "")[:10]
        acum_d = d.get("acumulado") or {}
        saldo_pt = float(acum_d.get("saldo_acum", 0.0) or 0.0)
        dia_num = int(d.get("dia", len(pontos) + 1))
        pontos.append((dia_num, dt_d, saldo_pt))

    if len(pontos) < 2:
        return ft.Container(height=0, visible=False)

    saldos = [p[2] for p in pontos]
    min_s = min(saldos)
    max_s = max(saldos)
    span = max_s - min_s
    if span <= 0.001:
        span = 1.0

    pad_x = 10
    pad_y = 8
    w_draw = max(50, largura - (pad_x * 2))
    h_draw = max(20, altura - (pad_y * 2))
    n_pts = len(pontos)

    shapes: list = []

    # 1. Linha do Eixo Zero (se cruzar)
    if min_s < 0 < max_s:
        zero_y = pad_y + h_draw - ((0.0 - min_s) / span * h_draw)
        shapes.append(
            cv.Line(
                x1=pad_x,
                y1=zero_y,
                x2=largura - pad_x,
                y2=zero_y,
                paint=ft.Paint(color=f"{T.BORDER}99", stroke_width=1, style=ft.PaintingStyle.STROKE),
            )
        )

    # 2. Traçado da Linha do Saldo
    coords: list[tuple[float, float, str, float]] = []
    for i, (dia_num, dt_i, val_i) in enumerate(pontos):
        cx_i = pad_x + (i / (n_pts - 1)) * w_draw
        cy_i = pad_y + h_draw - ((val_i - min_s) / span * h_draw)
        coords.append((cx_i, cy_i, dt_i, val_i))

    for i in range(len(coords) - 1):
        x1, y1, _, v1 = coords[i]
        x2, y2, _, v2 = coords[i + 1]
        cor_seg = T.RECEITA if (v1 >= 0 and v2 >= 0) else (T.DESPESA if (v1 < 0 and v2 < 0) else T.WARNING)
        shapes.append(
            cv.Line(
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                paint=ft.Paint(
                    color=cor_seg,
                    stroke_width=2.2,
                    stroke_cap=ft.StrokeCap.ROUND,
                    style=ft.PaintingStyle.STROKE,
                ),
            )
        )

    # 3. Destaque dos Pontos: Gargalo e Selecionado
    pt_selecionado = None
    pt_gargalo = None

    for cx_i, cy_i, dt_i, val_i in coords:
        if data_gargalo_iso and dt_i == data_gargalo_iso[:10]:
            pt_gargalo = (cx_i, cy_i, val_i)
        if dt_i == data_selecionada_iso[:10]:
            pt_selecionado = (cx_i, cy_i, val_i)

    if not pt_gargalo:
        menor_coord = min(coords, key=lambda c: c[3])
        pt_gargalo = (menor_coord[0], menor_coord[1], menor_coord[3])

    if pt_gargalo:
        shapes.append(
            cv.Circle(
                x=pt_gargalo[0],
                y=pt_gargalo[1],
                radius=4.5,
                paint=ft.Paint(color=T.DESPESA, style=ft.PaintingStyle.FILL),
            )
        )
        shapes.append(
            cv.Circle(
                x=pt_gargalo[0],
                y=pt_gargalo[1],
                radius=6.0,
                paint=ft.Paint(color=f"{T.DESPESA}55", stroke_width=1.5, style=ft.PaintingStyle.STROKE),
            )
        )

    if pt_selecionado:
        shapes.append(
            cv.Circle(
                x=pt_selecionado[0],
                y=pt_selecionado[1],
                radius=5.5,
                paint=ft.Paint(color="#3B82F6", style=ft.PaintingStyle.FILL),
            )
        )
        shapes.append(
            cv.Circle(
                x=pt_selecionado[0],
                y=pt_selecionado[1],
                radius=7.5,
                paint=ft.Paint(color="#FFFFFF", stroke_width=1.8, style=ft.PaintingStyle.STROKE),
            )
        )

    canvas_ctrl = cv.Canvas(
        width=largura,
        height=altura,
        shapes=shapes,
    )

    legenda = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Text(f"Min: {formatar_moeda(min_s)}", size=10, color=T.TEXT_MUTED),
            ft.Row([
                ft.Container(width=7, height=7, border_radius=4, bgcolor="#3B82F6"),
                ft.Text("Dia Atual", size=10, color=T.TEXT_MUTED),
                ft.Container(width=7, height=7, border_radius=4, bgcolor=T.DESPESA),
                ft.Text("Pior Dia", size=10, color=T.TEXT_MUTED),
            ], spacing=4),
            ft.Text(f"Max: {formatar_moeda(max_s)}", size=10, color=T.TEXT_MUTED),
        ],
    )

    return ft.Container(
        padding=pad(h=12, v=8),
        bgcolor=T.SURFACE_ALT,
        border_radius=10,
        border=borda(),
        content=ft.Column(
            spacing=4,
            tight=True,
            controls=[
                ft.Row([
                    ft.Icon(ft.Icons.SHOW_CHART_ROUNDED, size=14, color=T.PRIMARY),
                    ft.Text("Evolução do Saldo Acumulado no Mês", size=11, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ], spacing=6),
                canvas_ctrl,
                legenda,
            ],
        ),
    )


def construir_painel_raio_x(
    raio_x: dict,
    dias_calendario: Optional[list[dict]] = None,
    on_click_fatura: Optional[Callable[[], None]] = None,
    mobile: bool = False,
) -> ft.Control:
    """
    Constrói a coluna/seção 'Raio-X do Dia' para ser exibida com destaque visual
    dentro do Modal do Dia, usando cards desacoplados, ícones, badges e mini-gráfico.
    """
    eh_gargalo = raio_x["eh_gargalo_principal"]
    eh_negativo = raio_x["eh_negativo"]
    saldo_ac = raio_x["saldo_acum"]
    teto_seguro = raio_x["teto_seguro"]
    pct_inv = raio_x.get("pct_investimento", 50.0)
    menor_saldo = raio_x["menor_saldo_futuro"]
    dt_garg = raio_x["data_menor_saldo"]
    dia_fora = raio_x["dia_fora_mes"]

    cor_saldo_ac = T.RECEITA if saldo_ac >= 0 else T.DESPESA
    cor_teto = "#06B6D4" if menor_saldo >= 0 else T.DESPESA

    itens_raio_x: list[ft.Control] = []

    # 1. Badge de Alerta se for Pior Dia ou se for Fora do Mês
    if dia_fora:
        itens_raio_x.append(
            ft.Container(
                padding=pad(h=10, v=6),
                bgcolor=f"{T.TEXT_MUTED}18",
                border_radius=8,
                border=borda(1, f"{T.TEXT_MUTED}44"),
                content=ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=15, color=T.TEXT_MUTED),
                    ft.Text(
                        "Data fora do mês corrente. Valores acumulados respeitam o período do filtro.",
                        size=11,
                        color=T.TEXT_MUTED,
                        expand=True,
                    ),
                ], spacing=8),
            )
        )
    elif eh_gargalo:
        itens_raio_x.append(
            ft.Container(
                padding=pad(h=12, v=8),
                bgcolor=f"{T.DESPESA}1A",
                border_radius=8,
                border=borda(1.2, T.DESPESA),
                content=ft.Row([
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, size=18, color=T.DESPESA),
                    ft.Column([
                        ft.Text("PIOR DIA DO MÊS (GARGALO)", size=12, weight=ft.FontWeight.BOLD, color=T.DESPESA),
                        ft.Text(
                            f"Nesta data seu saldo chega ao menor valor do período ({formatar_moeda(saldo_ac)}).",
                            size=10.5,
                            color=T.TEXT_PRIMARY,
                        ),
                    ], spacing=1, expand=True),
                ], spacing=8),
            )
        )
    elif eh_negativo:
        itens_raio_x.append(
            ft.Container(
                padding=pad(h=10, v=6),
                bgcolor=f"{T.WARNING}18",
                border_radius=8,
                border=borda(1, f"{T.WARNING}55"),
                content=ft.Row([
                    ft.Icon(ft.Icons.WARNING_ROUNDED, size=15, color=T.WARNING),
                    ft.Text("Saldo acumulado em alerta negativo nesta data.", size=11, weight=ft.FontWeight.BOLD, color=T.WARNING),
                ], spacing=8),
            )
        )

    # 2. Card Principal: Saldo Acumulado
    itens_raio_x.append(
        ft.Container(
            padding=pad(all_=14),
            bgcolor=T.SURFACE_ALT,
            border_radius=12,
            border=borda(1.2, cor_saldo_ac if abs(saldo_ac) > 0.01 else T.BORDER),
            content=ft.Row([
                ft.Container(
                    width=42, height=42,
                    bgcolor=f"{cor_saldo_ac}1E",
                    border_radius=10,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=cor_saldo_ac, size=22),
                ),
                ft.Column([
                    ft.Text("SALDO ACUMULADO NO MÊS", size=10.5, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                    ft.Text(formatar_moeda(saldo_ac), size=20, weight=ft.FontWeight.BOLD, color=cor_saldo_ac),
                    ft.Text(
                        f"Período: {raio_x['periodo_acum_texto']}",
                        size=10.5,
                        color=T.TEXT_MUTED,
                    ),
                ], spacing=2, expand=True),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )
    )

    # 3. Card Teto Seguro p/ Gastar (Regra de Negócio Centralizada)
    sub_inv = f"Já descontado {pct_inv:g}% para investir"
    if dt_garg and menor_saldo < teto_seguro:
        detalhe_teto = f"Gargalo em {raio_x['data_menor_saldo_formatada']} ({formatar_moeda(menor_saldo)}) | {sub_inv}"
    else:
        detalhe_teto = f"{sub_inv} | Fluxo protegido contra faturas e gargalos futuros."

    itens_raio_x.append(
        ft.Container(
            padding=pad(all_=14),
            bgcolor=T.SURFACE_ALT,
            border_radius=12,
            border=borda(1.2, cor_teto),
            content=ft.Row([
                ft.Container(
                    width=42, height=42,
                    bgcolor=f"{cor_teto}1E",
                    border_radius=10,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.SHIELD_ROUNDED, color=cor_teto, size=22),
                ),
                ft.Column([
                    ft.Row([
                        ft.Text("TETO SEGURO P/ GASTAR", size=10.5, weight=ft.FontWeight.BOLD, color=cor_teto),
                    ]),
                    ft.Text(formatar_moeda(teto_seguro), size=18, weight=ft.FontWeight.BOLD, color=cor_teto),
                    ft.Text(detalhe_teto, size=10.5, color=T.TEXT_MUTED),
                ], spacing=2, expand=True),
            ], spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )
    )

    # 4. Grid de Entradas e Saídas Acumuladas
    itens_raio_x.append(
        ft.ResponsiveRow(
            spacing=8,
            run_spacing=8,
            controls=[
                ft.Container(
                    col={"xs": 12, "sm": 6},
                    padding=pad(all_=10),
                    bgcolor=f"{T.RECEITA}10",
                    border_radius=10,
                    border=borda(1, f"{T.RECEITA}30"),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=T.RECEITA, size=15),
                            ft.Text("Receitas Acumuladas", size=11, color=T.TEXT_MUTED),
                        ], spacing=4),
                        ft.Text(formatar_moeda(raio_x["receitas_acum"]), size=14, weight=ft.FontWeight.BOLD, color=T.RECEITA),
                    ], spacing=2),
                ),
                ft.Container(
                    col={"xs": 12, "sm": 6},
                    padding=pad(all_=10),
                    bgcolor=f"{T.DESPESA}10",
                    border_radius=10,
                    border=borda(1, f"{T.DESPESA}30"),
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.ARROW_DOWNWARD_ROUNDED, color=T.DESPESA, size=15),
                            ft.Text("Despesas Acumuladas", size=11, color=T.TEXT_MUTED),
                        ], spacing=4),
                        ft.Text(formatar_moeda(raio_x["despesas_total_acum"]), size=14, weight=ft.FontWeight.BOLD, color=T.DESPESA),
                        ft.Text(
                            f"Conta: {formatar_moeda(raio_x['despesas_conta_acum'])} | Faturas: {formatar_moeda(raio_x['despesas_cartao_acum'])}",
                            size=9.5,
                            color=T.TEXT_MUTED,
                        ),
                    ], spacing=2),
                ),
            ],
        )
    )

    # 5. Mini-Gráfico de Saldo Acumulado (se houver dias do mês fornecidos)
    if dias_calendario:
        spark = construir_sparkline_saldo_acumulado(
            dias_calendario=dias_calendario,
            data_selecionada_iso=raio_x["data"],
            data_gargalo_iso=raio_x["data_menor_saldo"],
            largura=350 if not mobile else 300,
            altura=52,
        )
        itens_raio_x.append(spark)

    # 6. Alertas Adicionais: Faturas ou Caixinhas no Dia
    if raio_x.get("vencimentos"):
        for vf in raio_x["vencimentos"]:
            v_fat = float(vf.get("valor_total", 0) or 0)
            st_fat = str(vf.get("status") or "aberta").lower()
            eh_paga = (st_fat == "paga" or v_fat <= 0.01)
            cor_vf = T.RECEITA if eh_paga else T.WARNING
            lbl_st = "Fatura Paga / Zerada" if eh_paga else "Vencimento de Fatura"

            itens_raio_x.append(
                ft.Container(
                    padding=pad(h=10, v=8),
                    bgcolor=f"{cor_vf}14",
                    border_radius=8,
                    border=borda(1, f"{cor_vf}40"),
                    ink=True,
                    on_click=lambda _: on_click_fatura() if on_click_fatura else None,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row([
                                ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color=cor_vf, size=16),
                                ft.Column([
                                    ft.Text(f"Cartão {vf.get('cartao_nome')}", size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                    ft.Text(lbl_st, size=10, color=cor_vf),
                                ], spacing=1),
                            ], spacing=8),
                            ft.Text(formatar_moeda(v_fat), size=13, weight=ft.FontWeight.BOLD, color=cor_vf),
                        ],
                    ),
                )
            )

    return ft.Column(
        spacing=10,
        tight=True,
        controls=itens_raio_x,
    )


def abrir_modal_raio_x_dia(
    page: ft.Page,
    dia_info: dict,
    vencimentos_dia: list[dict],
    data_inicio_filtro: str,
    acumulados_por_dia: dict,
    dias_calendario: Optional[list[dict]] = None,
    mobile: bool = False,
    pct_investimento: float | None = None,
    travar_pelo_pior_dia: bool = True,
    sobra_projetada_mes: float | None = None,
    on_novo_lancamento: Optional[Callable[[], None]] = None,
    on_filtrar_lista: Optional[Callable[[str], None]] = None,
    on_extrato_dia: Optional[Callable[[str], None]] = None,
    on_abrir_cartoes: Optional[Callable[[], None]] = None,
) -> ft.AlertDialog:
    """
    COMPONENTE ÚNICO E CENTRALIZADO: "Raio-X do Dia" em Dialog (Modal).
    Consumido igualmente pela aba Calendário e pela seção do Dashboard.
    Exibe:
    - Resumo das movimentações diárias (Receitas Dia, Desp. Conta, Cartão, Saldo Dia)
    - Painel Raio-X com Sparkline vetorial do saldo acumulado e Teto Seguro p/ Gastar
    - Lista detalhada de lançamentos do dia com badges de membros da família (Multi-Perfis)
    - Ações no rodapé (Lista/Extrato/Novo Lançamento).
    """
    dt_str = str(dia_info.get("data") or "")[:10]
    lancs_dia = dia_info.get("lancamentos") or []

    # FONTE ÚNICA DE VERDADE: cálculo unificado
    raio_x = calcular_raio_x_dia(
        dia_info=dia_info,
        vencimentos_dia=vencimentos_dia,
        data_inicio_filtro=data_inicio_filtro,
        acumulados_por_dia=acumulados_por_dia or {},
        pct_investimento=pct_investimento,
        travar_pelo_pior_dia=travar_pelo_pior_dia,
        sobra_projetada_mes=sobra_projetada_mes,
    )

    rec_d = raio_x["receita_dia"]
    desp_cta = raio_x["despesa_conta_dia"]
    desp_crt = raio_x["despesa_cartao_dia"]
    saldo_d = raio_x["saldo_dia"]

    # Callbacks de Navegação com Fallbacks Seguros
    def _fechar():
        fechar_dialogo(page, dlg_dia)

    def _ir_cartoes_act():
        _fechar()
        if callable(on_abrir_cartoes):
            on_abrir_cartoes()
        else:
            try:
                from views.shell_view import ir_cartoes
                ir_cartoes(page)
            except Exception:
                pass

    def _ir_extrato_act(_=None):
        _fechar()
        if callable(on_extrato_dia):
            on_extrato_dia(dt_str)
        else:
            try:
                from core.report_types import ReportContext
                from views.shell_view import ir_relatorio_lancamentos
                dt_obj = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
                ctx_dia = ReportContext(data_inicio=dt_obj, data_fim=dt_obj, origem="calendario")
                ir_relatorio_lancamentos(page, ctx=ctx_dia, origem="calendario")
            except Exception:
                try:
                    from views.shell_view import navegar
                    navegar(page, "/relatorios")
                except Exception:
                    pass

    def _filtrar_lista_act(_=None):
        _fechar()
        if callable(on_filtrar_lista):
            on_filtrar_lista(dt_str)
        else:
            try:
                from views.shell_view import navegar
                navegar(page, "/calendario")
            except Exception:
                pass

    def _novo_lanc_act(_=None):
        _fechar()
        if callable(on_novo_lancamento):
            on_novo_lancamento()
        else:
            try:
                from views.widgets.lancamento_form import abrir_lancamento
                abrir_lancamento(page)
            except Exception:
                pass

    itens_modal: list[ft.Control] = []

    # 1. Destaque de Vencimentos de Faturas no Dia
    for vf in vencimentos_dia:
        v_fat = float(vf.get("valor_total", 0) or 0)
        st_fat = str(vf.get("status") or "aberta").lower()
        eh_paga = (st_fat == "paga" or v_fat <= 0.01)
        cor_vf = T.RECEITA if eh_paga else T.WARNING
        lbl_st = "Fatura Paga / Zerada" if eh_paga else "Vencimento de Fatura"
        itens_modal.append(
            ft.Container(
                padding=pad(h=12, v=10),
                bgcolor=f"{cor_vf}15",
                border_radius=10,
                border=borda(1, f"{cor_vf}45"),
                ink=True,
                on_click=lambda _: _ir_cartoes_act(),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color=cor_vf, size=18),
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Text(
                                            f"Cartão {vf.get('cartao_nome')}",
                                            size=13,
                                            weight=ft.FontWeight.BOLD,
                                            color=T.TEXT_PRIMARY,
                                        ),
                                        ft.Text(lbl_st, size=11, color=cor_vf),
                                    ],
                                ),
                            ],
                        ),
                        ft.Text(formatar_moeda(v_fat), size=14, weight=ft.FontWeight.BOLD, color=cor_vf),
                    ],
                ),
            )
        )

    # 2. Lista de Lançamentos do Dia
    if not lancs_dia and not vencimentos_dia:
        itens_modal.append(
            ft.Container(
                padding=pad(all_=36),
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.EVENT_AVAILABLE_ROUNDED, color=T.TEXT_MUTED, size=38),
                        ft.Text(
                            "Nenhum lançamento neste dia",
                            color=T.TEXT_PRIMARY,
                            size=13,
                            weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            "O Raio-X Acumulado e o Teto Seguro continuam calculados ao lado.",
                            color=T.TEXT_MUTED,
                            size=11,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ],
                ),
            )
        )
    else:
        for l_it in lancs_dia:
            tp_l = str(l_it.get("tipo") or "Despesa")
            eh_rec = (tp_l == "Receita")
            val_l = float(l_it.get("valor", 0) or 0)
            cor_l = T.RECEITA if eh_rec else T.DESPESA
            sinal_l = "+" if eh_rec else "-"
            cat_n = l_it.get("categoria_nome") or (l_it.get("categorias") or {}).get("nome") or "Sem Categoria"
            sub_n = l_it.get("subcategoria_nome") or (l_it.get("subcategorias") or {}).get("nome") or ""
            cta_n = l_it.get("conta_nome") or (l_it.get("contas") or {}).get("nome") or ""
            crt_n = l_it.get("cartao_nome") or (l_it.get("cartoes") or {}).get("nome") or ""
            origem_str = f"💳 {crt_n}" if crt_n else (f"🏦 {cta_n}" if cta_n else "")
            if l_it.get("parcela_atual") and l_it.get("total_parcelas"):
                origem_str += f" ({l_it['parcela_atual']}/{l_it['total_parcelas']})"
            dt_compra_orig = str(l_it.get("data_compra") or "")[:10]
            if crt_n and dt_compra_orig and dt_compra_orig != dt_str[:10]:
                origem_str += f" • Compra {formatar_data_br(dt_compra_orig)[:5]}"
            eh_caixinha = bool(l_it.get("caixinha_id")) or str(l_it.get("subtipo") or "").lower() == "provisionamento"
            if eh_caixinha:
                cx_nome = l_it.get("caixinha_nome")
                origem_str += f" • 📦 Caixinha {cx_nome or ''}".strip()
            cat_full = f"{cat_n} › {sub_n}" if sub_n else cat_n

            # Identificação de Membro da Família (Multi-Perfis)
            m_nome = l_it.get("membro_nome") or (l_it.get("membros") or {}).get("nome")
            m_cor = l_it.get("membro_cor") or (l_it.get("membros") or {}).get("cor") or T.PRIMARY
            m_icone = l_it.get("membro_icone") or (l_it.get("membros") or {}).get("icone") or "person"
            badge_membro = None
            if m_nome:
                badge_membro = ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{m_cor}1A",
                    border_radius=4,
                    border=borda(1, f"{m_cor}40"),
                    content=ft.Row([
                        ft.Icon(ft.Icons.FAVORITE_ROUNDED if m_icone == "favorite" else ft.Icons.PERSON_ROUNDED, size=10, color=m_cor),
                        ft.Text(m_nome, size=10, color=m_cor, weight=ft.FontWeight.W_600),
                    ], spacing=3, tight=True),
                )

            icone_modal = ft.Icons.SAVINGS_ROUNDED if eh_caixinha else (
                ft.Icons.ARROW_UPWARD_ROUNDED if eh_rec else ft.Icons.ARROW_DOWNWARD_ROUNDED
            )
            cor_icone_box = T.INFO if eh_caixinha else cor_l

            linha_titulo = [
                ft.Text(
                    l_it.get("descricao") or cat_n,
                    size=13,
                    weight=ft.FontWeight.W_600,
                    color=T.TEXT_PRIMARY,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
            ]
            if badge_membro:
                linha_titulo.append(badge_membro)

            itens_modal.append(
                ft.Container(
                    padding=pad(h=12, v=10),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=10,
                    border=borda(),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                expand=True,
                                controls=[
                                    ft.Container(
                                        padding=pad(all_=8),
                                        border_radius=8,
                                        bgcolor=f"{cor_icone_box}1A",
                                        content=ft.Icon(
                                            icone_modal,
                                            color=cor_icone_box,
                                            size=16,
                                        ),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Row(linha_titulo, spacing=6, wrap=False),
                                            ft.Text(
                                                f"{cat_full} • {origem_str}".strip(" •"),
                                                size=11,
                                                color=T.TEXT_MUTED,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Column(
                                spacing=2,
                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                controls=[
                                    ft.Text(
                                        f"{sinal_l} {formatar_moeda(val_l)}",
                                        size=13.5,
                                        weight=ft.FontWeight.BOLD,
                                        color=cor_l,
                                    ),
                                    ft.Text(
                                        str(l_it.get("status") or "Pago"),
                                        size=10,
                                        weight=ft.FontWeight.W_600,
                                        color=T.RECEITA if str(l_it.get("status") or "").lower() == "pago" else T.WARNING,
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )

    # 3. Resumo Topo do Modal (4 cards)
    resumo_topo_modal = ft.ResponsiveRow(
        spacing=8,
        run_spacing=8,
        controls=[
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(h=10, v=8),
                bgcolor=f"{T.RECEITA}14",
                border_radius=8,
                content=ft.Column(
                    spacing=1,
                    controls=[
                        ft.Text("Receitas Dia", size=10, color=T.TEXT_MUTED),
                        ft.Text(formatar_moeda(rec_d), size=13, weight=ft.FontWeight.BOLD, color=T.RECEITA),
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(h=10, v=8),
                bgcolor=f"{T.DESPESA}14",
                border_radius=8,
                content=ft.Column(
                    spacing=1,
                    controls=[
                        ft.Text("Desp. Conta", size=10, color=T.TEXT_MUTED),
                        ft.Text(formatar_moeda(desp_cta), size=13, weight=ft.FontWeight.BOLD, color=T.DESPESA),
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(h=10, v=8),
                bgcolor=f"{T.WARNING}14",
                border_radius=8,
                content=ft.Column(
                    spacing=1,
                    controls=[
                        ft.Text("Total Cartão", size=10, color=T.TEXT_MUTED),
                        ft.Text(formatar_moeda(desp_crt), size=13, weight=ft.FontWeight.BOLD, color=T.WARNING),
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=8,
                content=ft.Column(
                    spacing=1,
                    controls=[
                        ft.Text("Saldo do Dia", size=10, color=T.TEXT_MUTED),
                        ft.Text(
                            formatar_moeda(saldo_d),
                            size=13,
                            weight=ft.FontWeight.BOLD,
                            color=T.RECEITA if saldo_d >= 0 else T.DESPESA,
                        ),
                    ],
                ),
            ),
        ],
    )

    # 4. Header do Modal com status de Pior Dia (Gargalo)
    tag_status_topo = []
    if raio_x["eh_gargalo_principal"]:
        tag_status_topo.append(
            ft.Container(
                padding=pad(h=8, v=3),
                bgcolor=f"{T.DESPESA}1F",
                border_radius=6,
                border=borda(1, T.DESPESA),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=T.DESPESA, size=13),
                        ft.Text("PIOR DIA (GARGALO)", color=T.DESPESA, size=10.5, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=4,
                    tight=True,
                ),
            )
        )

    title_modal_ctrl = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.EVENT_NOTE_ROUNDED, color=T.PRIMARY, size=20),
                    ft.Text(
                        f"Movimentações de {formatar_data_br(dt_str)}",
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=T.TEXT_PRIMARY,
                    ),
                    *tag_status_topo,
                ],
            ),
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_color=T.TEXT_MUTED,
                icon_size=18,
                on_click=lambda _: _fechar(),
            ),
        ],
    )

    # 5. Organização do Layout (Desktop: 2 Colunas | Mobile: Empilhado)
    if not mobile:
        coluna_raio_x = ft.Container(
            width=380,
            content=ft.Column(
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=15, color=T.PRIMARY),
                            ft.Text("Raio-X Financeiro", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(f"({raio_x['periodo_acum_texto']})", size=10.5, color=T.TEXT_MUTED),
                        ],
                        spacing=6,
                    ),
                    construir_painel_raio_x(
                        raio_x=raio_x,
                        dias_calendario=dias_calendario or [],
                        on_click_fatura=_ir_cartoes_act,
                        mobile=False,
                    ),
                ],
            ),
        )

        coluna_lancamentos = ft.Container(
            width=450,
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=15, color=T.PRIMARY),
                                    ft.Text("Lançamentos do Dia", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                ],
                                spacing=6,
                            ),
                            ft.Text(f"{len(lancs_dia)} itens", size=11, color=T.TEXT_MUTED),
                        ],
                    ),
                    ft.Container(
                        height=380,
                        content=ft.Column(
                            spacing=8,
                            scroll=ft.ScrollMode.AUTO,
                            controls=itens_modal,
                        ),
                    ),
                ],
            ),
        )

        corpo_modal = ft.Container(
            height=420,
            content=ft.Row(
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.START,
                controls=[
                    coluna_raio_x,
                    ft.VerticalDivider(width=1, color=T.BORDER),
                    coluna_lancamentos,
                ],
            ),
        )
    else:
        corpo_modal = ft.Container(
            height=480,
            content=ft.Column(
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=14, color=T.PRIMARY),
                            ft.Text("Raio-X Financeiro", size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ],
                        spacing=6,
                    ),
                    construir_painel_raio_x(
                        raio_x=raio_x,
                        dias_calendario=dias_calendario or [],
                        on_click_fatura=_ir_cartoes_act,
                        mobile=True,
                    ),
                    ft.Divider(color=T.BORDER, height=10),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=14, color=T.PRIMARY),
                                    ft.Text("Lançamentos do Dia", size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                ],
                                spacing=6,
                            ),
                            ft.Text(f"{len(lancs_dia)} itens", size=11, color=T.TEXT_MUTED),
                        ],
                    ),
                    *itens_modal,
                ],
            ),
        )

    # 6. Botões de Rodapé
    texto_botao_lista = "Ver na Aba Lista" if on_filtrar_lista else "Ir para Calendário"
    dlg_dia = ft.AlertDialog(
        modal=False,
        bgcolor=T.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=16),
        title=title_modal_ctrl,
        content=ft.Container(
            width=860 if not mobile else 340,
            content=ft.Column(
                tight=True,
                spacing=10,
                controls=[
                    resumo_topo_modal,
                    ft.Divider(color=T.BORDER, height=8),
                    corpo_modal,
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.FILTER_LIST_ROUNDED, size=15, color=T.TEXT_MUTED),
                        ft.Text(texto_botao_lista, color=T.TEXT_MUTED, size=12),
                    ],
                ),
                on_click=_filtrar_lista_act,
            ),
            ft.TextButton(
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.OPEN_IN_NEW_ROUNDED, size=15, color=T.PRIMARY),
                        ft.Text("Abrir Extrato do Dia", color=T.PRIMARY, size=12, weight=ft.FontWeight.BOLD),
                    ],
                ),
                on_click=_ir_extrato_act,
            ),
            ft.FilledButton(
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=ft.Colors.WHITE),
                        ft.Text("Novo", color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                    ],
                ),
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=8),
                ),
                on_click=_novo_lanc_act,
            ),
        ],
    )

    abrir_dialogo(page, dlg_dia)
    return dlg_dia
