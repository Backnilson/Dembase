"""
=============================================================================
DemBase v3 — views/calendario_view.py  (Flet 1.0.1)
Calendário Financeiro Interativo (Mapa de Calor + Gráfico de Rosca + Faturas)
e Histórico de Lançamentos (Ledger).
- Grade mensal completa (DOM a SÁB, 6 semanas) com pílulas de Entrada (verde)
  e Saída (vermelho), intensidade de Mapa de Calor (Heatmap) e marcadores de
  vencimento de faturas de cartão de crédito (💳).
- Hover (Mouse Over): Tooltip rico + Barra de Inspeção Rápida destrinchando
  Total Receita, Total Despesa (Conta/Pix), Total Cartão e Saldo do Dia.
- Clique no Dia: Abre Modal Detalhado das movimentações do dia com opção de
  redirecionar para o relatório/extrato filtrado naquela data ou lançar novo item.
- Painel Lateral: Gráfico de Rosca (Donut Chart) por Categorias/Tags (Despesas x
  Receitas) + Resumo das Faturas dos Cartões no Mês.
=============================================================================
"""
from __future__ import annotations

import asyncio
import calendar
import math
from datetime import date, datetime, timedelta
import flet as ft
import flet.canvas as cv

from core import theme as T
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.constants import formatar_moeda, formatar_data_br, hoje, inicio_mes_atual

MESES_NOMES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]
from core.responsive import is_mobile
from core.router import navegar
from core.nav import ir_cartoes, ir_relatorio_lancamentos, ir_relatorio_categoria
from core.report_context import ReportContext
from core.periodo import (
    avancar_periodo_estado,
    persistir_estado_periodo,
    atualizar_datas_periodo_global,
)
from views.widgets.date_filter import DateFilterBar
from views.widgets.lancamento_sheet import abrir_lancamento
from views.shell_view import criar_shell, ROTA_CALENDARIO, obter_estado_periodo_atual, sincronizar_shell_periodo
import services.supabase_client as db


DIAS_SEMANA_CABECALHO = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"]

PALETA_ROSCA_FALLBACK = [
    "#10B981", "#F59E0B", "#3B82F6", "#8B5CF6",
    "#EC4899", "#06B6D4", "#EF4444", "#94A3B8",
]


def formatar_moeda_curta_cal(valor: float) -> str:
    """Formata valores de forma compacta para caber nos blocos do calendário."""
    v = abs(float(valor or 0.0))
    if v >= 10000:
        return f"R$ {v / 1000:.1f}mil".replace(".", ",")
    if v >= 1000:
        # Ex: R$ 1.272,00 ou R$ 1,3mil quando mobile
        return formatar_moeda(v)
    return formatar_moeda(v)


def formatar_moeda_heatmap(valor: float) -> str:
    """Formato enxuto estilo heatmap ('R$ 299', 'R$ 1,3mil')."""
    v = abs(float(valor or 0.0))
    if v < 0.01:
        return "–"
    if v >= 1000:
        return f"R$ {v / 1000:.1f}mil".replace(".0mil", "mil").replace(".", ",")
    return f"R$ {int(round(v))}"


def calcular_cor_heatmap_saida(valor_saida: float, maior_saida: float) -> tuple[str, str]:
    """
    Retorna (bgcolor_hex, border_color_hex) proporcional à saída do dia (0.0 a 1.0).
    """
    if valor_saida <= 0.005 or maior_saida <= 0.005:
        return (T.SURFACE_ALT, T.BORDER)
    ratio = max(0.12, min(1.0, float(valor_saida) / float(maior_saida)))
    if ratio >= 0.75:
        return (f"{T.DESPESA}48", f"{T.DESPESA}99")
    if ratio >= 0.45:
        return (f"{T.DESPESA}30", f"{T.DESPESA}70")
    if ratio >= 0.20:
        return (f"{T.DESPESA}20", f"{T.DESPESA}50")
    return (f"{T.DESPESA}14", f"{T.DESPESA}38")


def calcular_cor_heatmap_entrada(valor_entrada: float, maior_entrada: float) -> tuple[str, str]:
    if valor_entrada <= 0.005 or maior_entrada <= 0.005:
        return (T.SURFACE_ALT, T.BORDER)
    ratio = max(0.15, min(1.0, float(valor_entrada) / float(maior_entrada)))
    if ratio >= 0.65:
        return (f"{T.RECEITA}42", f"{T.RECEITA}90")
    if ratio >= 0.30:
        return (f"{T.RECEITA}28", f"{T.RECEITA}65")
    return (f"{T.RECEITA}16", f"{T.RECEITA}40")


def construir_grafico_rosca(
    fatias: list[dict],
    total: float,
    cor_vazia: str = "#334155",
    tamanho: int = 176,
    espessura: int = 22,
) -> ft.Control:
    """
    Constrói um Gráfico de Rosca (Donut Chart) vetorial usando flet.canvas.Canvas + cv.Arc,
    com o valor total centralizado no meio do anel (Flet 1.0.1).
    """
    margem = espessura // 2 + 6
    diametro = tamanho - (margem * 2)
    shapes: list = []

    # Círculo base de fundo
    shapes.append(
        cv.Arc(
            x=margem,
            y=margem,
            width=diametro,
            height=diametro,
            start_angle=0,
            sweep_angle=2 * math.pi,
            use_center=False,
            paint=ft.Paint(
                color=f"{cor_vazia}40",
                style=ft.PaintingStyle.STROKE,
                stroke_width=espessura,
            ),
        )
    )

    if total > 0 and fatias:
        angulo_atual = -math.pi / 2  # Começa no topo (12h)
        gap = 0.03 if len(fatias) > 1 else 0.0
        for idx, item in enumerate(fatias):
            val = float(item.get("total", 0) or 0)
            if val <= 0:
                continue
            proporcao = max(0.0, min(1.0, val / total))
            sweep = max(0.02, (proporcao * 2 * math.pi) - gap)
            cor_fatia = item.get("cor") or PALETA_ROSCA_FALLBACK[idx % len(PALETA_ROSCA_FALLBACK)]
            shapes.append(
                cv.Arc(
                    x=margem,
                    y=margem,
                    width=diametro,
                    height=diametro,
                    start_angle=angulo_atual,
                    sweep_angle=sweep,
                    use_center=False,
                    paint=ft.Paint(
                        color=cor_fatia,
                        style=ft.PaintingStyle.STROKE,
                        stroke_width=espessura,
                        stroke_cap=ft.StrokeCap.BUTT,
                    ),
                )
            )
            angulo_atual += proporcao * 2 * math.pi

    canvas_rosca = cv.Canvas(
        shapes=shapes,
        width=tamanho,
        height=tamanho,
    )

    centro_texto = ft.Container(
        width=tamanho,
        height=tamanho,
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            spacing=2,
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    formatar_moeda(total),
                    size=14.5,
                    weight=ft.FontWeight.BOLD,
                    color=T.TEXT_PRIMARY,
                ),
                ft.Text(
                    "total no mês",
                    size=10.5,
                    color=T.TEXT_MUTED,
                ),
            ],
        ),
    )

    return ft.Stack(
        width=tamanho,
        height=tamanho,
        controls=[canvas_rosca, centro_texto],
    )


def criar_view_calendario(page: ft.Page) -> ft.View:
    mobile = is_mobile(page)
    hoje_d = hoje()
    estado_global = obter_estado_periodo_atual(page)

    mes_sel = [int(estado_global.get("mes") or hoje_d.month)]
    ano_sel = [int(estado_global.get("ano") or hoje_d.year)]

    # Estado de navegação e filtros (100% sincronizado com o filtro global do topo)
    aba_ativa          = [0]             # 0: Calendário Interativo (padrão), 1: Lista de Transações
    modo_heatmap       = ["completo"]    # "completo" (Entradas + Saídas), "saidas" (Saídas por dia), "entradas"
    aba_rosca_tags     = ["Despesas"]    # "Despesas" ou "Receitas"
    ult_d_init         = calendar.monthrange(ano_sel[0], mes_sel[0])[1]
    d_ini_glob         = estado_global.get("data_inicio")
    d_fim_glob         = estado_global.get("data_fim")
    filtro_data_inicio = [
        d_ini_glob.isoformat() if isinstance(d_ini_glob, date)
        else (str(d_ini_glob)[:10] if d_ini_glob else date(ano_sel[0], mes_sel[0], 1).isoformat())
    ]
    filtro_data_fim    = [
        d_fim_glob.isoformat() if isinstance(d_fim_glob, date)
        else (str(d_fim_glob)[:10] if d_fim_glob else date(ano_sel[0], mes_sel[0], ult_d_init).isoformat())
    ]
    filtro_tipo        = ["Todos"]
    filtro_status      = ["Todos"]
    termo_busca        = [""]

    pacote_calendario: dict = {}
    todos_lancamentos: list = []

    # ── Controles de UI ──────────────────────────────────────────────────────
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2.2, visible=False)

    tam_kpi = 15 if mobile else 19
    txt_resultado_mes = ft.Text("R$ 0,00", color=T.TEXT_PRIMARY, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_receitas_mes  = ft.Text("R$ 0,00", color=T.RECEITA, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_despesas_mes  = ft.Text("R$ 0,00", color=T.DESPESA, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_cartao_mes    = ft.Text("R$ 0,00", color=T.WARNING, size=tam_kpi, weight=ft.FontWeight.BOLD)

    txt_sub_resultado = ft.Text("Receitas − Despesas", color=T.TEXT_MUTED, size=10.5)
    txt_sub_receitas  = ft.Text("0 dias com entrada", color=T.TEXT_MUTED, size=10.5)
    txt_sub_despesas  = ft.Text("0 dias com saída", color=T.TEXT_MUTED, size=10.5)
    txt_sub_cartao    = ft.Text("Compras no crédito", color=T.TEXT_MUTED, size=10.5)

    # Barra de Inspeção Rápida (atualizada no Hover / Mouse Over de qualquer dia)
    txt_hover_data = ft.Text(
        "Passe o mouse ou toque em um dia do calendário para destrinchar o saldo",
        size=12,
        weight=ft.FontWeight.W_600,
        color=T.TEXT_PRIMARY,
    )
    row_hover_detalhes = ft.Row(spacing=10, wrap=True, controls=[])
    barra_inspecao_hover = ft.Container(
        padding=pad(h=14, v=10),
        bgcolor=T.SURFACE_ALT,
        border_radius=12,
        border=borda(1, f"{T.PRIMARY}35"),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
            spacing=8,
            controls=[
                ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons. ADS_CLICK_ROUNDED, color=T.PRIMARY, size=16),
                        txt_hover_data,
                    ],
                ),
                row_hover_detalhes,
            ],
        ),
    )

    col_visao_calendario  = ft.Column(spacing=14, controls=[])
    col_lista_lancamentos = ft.Column(spacing=10, controls=[])
    area_principal        = ft.Column(spacing=16, controls=[])
    row_seletor_abas_ref  = ft.Row(spacing=4, tight=True, controls=[])

    def _nome_mes_ano(m: int, a: int) -> str:
        nome_m = MESES_NOMES[m - 1] if 1 <= m <= 12 else str(m)
        return f"{nome_m.lower()} {a}"

    def _nome_mes_ano_cap(m: int, a: int) -> str:
        nome_m = MESES_NOMES[m - 1] if 1 <= m <= 12 else str(m)
        return f"{nome_m} {a}"

    # ── Atualização da Barra de Inspeção no Hover (Mouse Over — Soma Acumulada Contínua) ──
    def _obter_acum_dia(dt_iso: str, dia_info: dict) -> dict:
        acum_map = pacote_calendario.get("acumulados_por_dia") or {}
        if dt_iso in acum_map:
            return acum_map[dt_iso]
        if isinstance(dia_info.get("acumulado"), dict):
            return dia_info["acumulado"]
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        desp_tot = float(dia_info.get("total_despesas", 0) or 0)
        return {
            "data_inicio_acum": filtro_data_inicio[0],
            "data_ate": dt_iso,
            "receitas_acum": rec_d,
            "despesas_conta_acum": desp_cta,
            "despesas_cartao_acum": desp_crt,
            "despesas_total_acum": desp_tot,
            "saldo_acum": rec_d - desp_tot,
            "qtd_lancamentos_acum": int(dia_info.get("qtd_lancamentos", 0) or 0),
        }

    def _atualizar_painel_hover(dia_info: dict, vencimentos_dia: list[dict]):
        dt_str = str(dia_info.get("data") or "")[:10]
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        saldo_d = rec_d - desp_d
        qtd_d = int(dia_info.get("qtd_lancamentos", 0) or 0)

        acum = _obter_acum_dia(dt_str, dia_info)
        d_ini_ac = str(acum.get("data_inicio_acum") or filtro_data_inicio[0])[:10]
        rec_ac = float(acum.get("receitas_acum", 0) or 0)
        desp_tot_ac = float(acum.get("despesas_total_acum", 0) or 0)
        desp_crt_ac = float(acum.get("despesas_cartao_acum", 0) or 0)
        saldo_ac = float(acum.get("saldo_acum", rec_ac - desp_tot_ac) or 0)

        txt_hover_data.value = (
            f"📅 Acumulado {formatar_data_br(d_ini_ac)[:5]} → {formatar_data_br(dt_str)} "
            f"(Dia: {qtd_d} mov. | {formatar_moeda(saldo_d)})"
        )
        chips = [
            ft.Container(
                padding=pad(h=8, v=3),
                border_radius=6,
                bgcolor=f"{T.RECEITA}18",
                content=ft.Text(f"Rec. Acum: {formatar_moeda(rec_ac)}", size=11, weight=ft.FontWeight.BOLD, color=T.RECEITA),
            ),
            ft.Container(
                padding=pad(h=8, v=3),
                border_radius=6,
                bgcolor=f"{T.DESPESA}18",
                content=ft.Text(f"Desp. Acum: {formatar_moeda(desp_tot_ac)}", size=11, weight=ft.FontWeight.BOLD, color=T.DESPESA),
            ),
            ft.Container(
                padding=pad(h=8, v=3),
                border_radius=6,
                bgcolor=f"{T.WARNING}18",
                content=ft.Text(f"Faturas Acum: {formatar_moeda(desp_crt_ac)}", size=11, weight=ft.FontWeight.BOLD, color=T.WARNING),
            ),
            ft.Container(
                padding=pad(h=9, v=3),
                border_radius=6,
                bgcolor=f"{T.RECEITA}22" if saldo_ac >= 0 else f"{T.DESPESA}22",
                border=borda(1.2, T.RECEITA if saldo_ac >= 0 else T.DESPESA),
                content=ft.Text(
                    f"Saldo Acumulado: {formatar_moeda(saldo_ac)}",
                    size=11.5,
                    weight=ft.FontWeight.BOLD,
                    color=T.RECEITA if saldo_ac >= 0 else T.DESPESA,
                ),
            ),
        ]
        for vf in vencimentos_dia:
            chips.append(
                ft.Container(
                    padding=pad(h=8, v=3),
                    border_radius=6,
                    bgcolor=f"{T.PRIMARY}22",
                    content=ft.Text(
                        f"💳 Venc. {vf.get('cartao_nome')}: {formatar_moeda(float(vf.get('valor_total', 0) or 0))}",
                        size=11,
                        weight=ft.FontWeight.BOLD,
                        color=T.PRIMARY,
                    ),
                )
            )
        for cx_l in (dia_info.get("lancamentos") or []):
            if cx_l.get("caixinha_id") or str(cx_l.get("subtipo") or "").lower() == "provisionamento":
                cx_n = cx_l.get("caixinha_nome") or cx_l.get("descricao") or "Caixinha"
                cx_v = float(cx_l.get("valor", 0) or 0)
                cx_st = str(cx_l.get("status") or "Pendente")
                chips.append(
                    ft.Container(
                        padding=pad(h=8, v=3),
                        border_radius=6,
                        bgcolor=f"{T.INFO}22",
                        content=ft.Text(
                            f"📦 {cx_n}: {formatar_moeda(cx_v)} ({cx_st})",
                            size=11,
                            weight=ft.FontWeight.BOLD,
                            color=T.INFO,
                        ),
                    )
                )
        row_hover_detalhes.controls = chips
        try:
            barra_inspecao_hover.update()
        except Exception:
            pass

    def _montar_tooltip_dia(dia_info: dict, vencimentos_dia: list[dict]) -> str:
        dt_str = str(dia_info.get("data") or "")[:10]
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        saldo_d = rec_d - desp_d
        qtd_d = int(dia_info.get("qtd_lancamentos", 0) or 0)

        acum = _obter_acum_dia(dt_str, dia_info)
        d_ini_ac = str(acum.get("data_inicio_acum") or filtro_data_inicio[0])[:10]
        rec_ac = float(acum.get("receitas_acum", 0) or 0)
        desp_cta_ac = float(acum.get("despesas_conta_acum", 0) or 0)
        desp_crt_ac = float(acum.get("despesas_cartao_acum", 0) or 0)
        desp_tot_ac = float(acum.get("despesas_total_acum", 0) or 0)
        saldo_ac = float(acum.get("saldo_acum", rec_ac - desp_tot_ac) or 0)

        linhas = [
            f"📅 {formatar_data_br(dt_str)} ({qtd_d} mov. no dia)",
            f"── Acumulado ({formatar_data_br(d_ini_ac)} até {formatar_data_br(dt_str)}) ──",
            f"🟢 Receitas Acum.: {formatar_moeda(rec_ac)}",
            f"🔴 Despesas Acum.: {formatar_moeda(desp_tot_ac)} (Conta: {formatar_moeda(desp_cta_ac)} | Faturas: {formatar_moeda(desp_crt_ac)})",
            f"💰 SALDO ACUMULADO: {formatar_moeda(saldo_ac)}",
            f"── Movimento Isolado do Dia ──",
            f"   • Entradas Dia: {formatar_moeda(rec_d)} | Saídas Dia: {formatar_moeda(desp_d)} (Conta: {formatar_moeda(desp_cta)} | Cartão: {formatar_moeda(desp_crt)})",
            f"   • Saldo do Dia: {formatar_moeda(saldo_d)}",
        ]
        for vf in vencimentos_dia:
            st_f = str(vf.get("status") or "aberta").upper()
            linhas.append(
                f"💳 Vencimento {vf.get('cartao_nome')}: {formatar_moeda(float(vf.get('valor_total', 0) or 0))} ({st_f})"
            )
        for cx_l in (dia_info.get("lancamentos") or []):
            if cx_l.get("caixinha_id") or str(cx_l.get("subtipo") or "").lower() == "provisionamento":
                cx_n = cx_l.get("caixinha_nome") or cx_l.get("descricao") or "Caixinha"
                cx_v = float(cx_l.get("valor", 0) or 0)
                cx_st = str(cx_l.get("status") or "Pendente").upper()
                linhas.append(f"📦 Caixinha {cx_n}: {formatar_moeda(cx_v)} ({cx_st})")
        if qtd_d > 0 or vencimentos_dia:
            linhas.append("👆 Clique para abrir os detalhes desta data")
        return "\n".join(linhas)

    # ── Modal Detalhado do Dia ao Clicar em um Bloco do Calendário ───────────
    def _abrir_modal_dia(dia_info: dict, vencimentos_dia: list[dict]):
        dt_str = str(dia_info.get("data") or "")
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        saldo_d = rec_d - desp_d
        lancs_dia = dia_info.get("lancamentos") or []

        def _ir_extrato_data(_):
            fechar_dialogo(page, dlg_dia)
            try:
                dt_obj = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
                ctx_dia = ReportContext(
                    data_inicio=dt_obj,
                    data_fim=dt_obj,
                    origem="calendario",
                )
                ir_relatorio_lancamentos(page, ctx=ctx_dia, origem="calendario")
            except Exception:
                filtro_data_inicio[0] = dt_str
                filtro_data_fim[0] = dt_str
                aba_ativa[0] = 1
                carregar_dados()

        def _filtrar_aba_lista(_):
            fechar_dialogo(page, dlg_dia)
            filtro_data_inicio[0] = dt_str
            filtro_data_fim[0] = dt_str
            aba_ativa[0] = 1
            carregar_dados()

        def _novo_lanc_dia(_):
            fechar_dialogo(page, dlg_dia)
            abrir_lancamento(page, on_saved=carregar_dados)

        itens_modal: list[ft.Control] = []

        # Se houver vencimento de fatura naquele dia, destaca no topo do modal
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
                    on_click=lambda _: (fechar_dialogo(page, dlg_dia), ir_cartoes(page)),
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

        if not lancs_dia and not vencimentos_dia:
            itens_modal.append(
                ft.Container(
                    padding=pad(all_=24),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(
                        "Nenhuma movimentação registrada nesta data.",
                        color=T.TEXT_MUTED,
                        size=13,
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
                    origem_str += f" · Compra {formatar_data_br(dt_compra_orig)[:5]}"
                eh_caixinha = bool(l_it.get("caixinha_id")) or str(l_it.get("subtipo") or "").lower() == "provisionamento"
                if eh_caixinha:
                    cx_nome = l_it.get("caixinha_nome")
                    origem_str += f" · 📦 Caixinha {cx_nome or ''}".strip()
                cat_full = f"{cat_n} · {sub_n}" if sub_n else cat_n

                icone_modal = ft.Icons.SAVINGS_ROUNDED if eh_caixinha else (
                    ft.Icons.ARROW_UPWARD_ROUNDED if eh_rec else ft.Icons.ARROW_DOWNWARD_ROUNDED
                )
                cor_icone_box = T.INFO if eh_caixinha else cor_l

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
                                                ft.Text(
                                                    l_it.get("descricao") or cat_n,
                                                    size=13,
                                                    weight=ft.FontWeight.W_600,
                                                    color=T.TEXT_PRIMARY,
                                                    max_lines=1,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Text(
                                                    f"{cat_full}  {origem_str}".strip(),
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
                            ft.Text("Receitas", size=10, color=T.TEXT_MUTED),
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

        dlg_dia = ft.AlertDialog(
            modal=False,
            bgcolor=T.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.EVENT_NOTE_ROUNDED, color=T.PRIMARY, size=20),
                            ft.Text(
                                f"Movimentações de {formatar_data_br(dt_str)}",
                                size=16,
                                weight=ft.FontWeight.BOLD,
                                color=T.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_color=T.TEXT_MUTED,
                        icon_size=18,
                        on_click=lambda _: fechar_dialogo(page, dlg_dia),
                    ),
                ],
            ),
            content=ft.Container(
                width=500 if not mobile else 340,
                content=ft.Column(
                    tight=True,
                    spacing=10,
                    controls=[
                        resumo_topo_modal,
                        ft.Divider(color=T.BORDER, height=8),
                        ft.Container(
                            height=290,
                            content=ft.Column(
                                spacing=8,
                                scroll=ft.ScrollMode.AUTO,
                                controls=itens_modal,
                            ),
                        ),
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
                            ft.Text("Ver na Aba Lista", color=T.TEXT_MUTED, size=12),
                        ],
                    ),
                    on_click=_filtrar_aba_lista,
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
                    on_click=_ir_extrato_data,
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
                    on_click=_novo_lanc_dia,
                ),
            ],
        )
        abrir_dialogo(page, dlg_dia)

    # ── Navegação Rápida de Mês (< Outubro 2026 >) sincronizada com o Topo ──
    def _mudar_mes_delta(delta: int):
        est_atual = obter_estado_periodo_atual(page)
        avancar_periodo_estado(est_atual, delta)
        persistir_estado_periodo(page, est_atual)
        sincronizar_shell_periodo(page)
        mes_sel[0] = int(est_atual["mes"])
        ano_sel[0] = int(est_atual["ano"])
        filtro_data_inicio[0] = est_atual["data_inicio"].isoformat()
        filtro_data_fim[0] = est_atual["data_fim"].isoformat()
        carregar_dados()

    # ── Construção do Bloco de Dia da Grade 7x6 (Mapa de Calor + Pílulas) ────
    def _construir_celula_dia(
        dt_atual: date,
        dia_info: dict,
        vencimentos_dia: list[dict],
        maior_saida: float,
        maior_entrada: float,
    ) -> ft.Container:
        dt_iso = dt_atual.isoformat()
        no_mes = (dt_atual.month == mes_sel[0] and dt_atual.year == ano_sel[0])
        no_periodo = (filtro_data_inicio[0] <= dt_iso <= filtro_data_fim[0])
        eh_parcial = bool(pacote_calendario.get("eh_periodo_parcial", False))
        ativo_visual = no_periodo if eh_parcial else no_mes

        eh_hoje = (dt_atual == hoje_d)
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        qtd_d = int(dia_info.get("qtd_lancamentos", 0) or 0)

        modo = modo_heatmap[0]

        # Cor de fundo baseada no Modo de Mapa de Calor e no Filtro de Período Ativo
        if modo == "saidas":
            bg_celula, cor_borda_base = calcular_cor_heatmap_saida(desp_d if ativo_visual else 0.0, maior_saida)
            if not ativo_visual:
                bg_celula = f"{T.SURFACE_ALT}50"
        elif modo == "entradas":
            bg_celula, cor_borda_base = calcular_cor_heatmap_entrada(rec_d if ativo_visual else 0.0, maior_entrada)
            if not ativo_visual:
                bg_celula = f"{T.SURFACE_ALT}50"
        else:
            # Modo Completo (estilo Imagem 1 + sutil heatmap)
            if desp_d > 0 and rec_d == 0 and ativo_visual:
                bg_celula, cor_borda_base = calcular_cor_heatmap_saida(desp_d * 0.45, max(1.0, maior_saida))
            elif rec_d > 0 and desp_d == 0 and ativo_visual:
                bg_celula, cor_borda_base = calcular_cor_heatmap_entrada(rec_d * 0.45, max(1.0, maior_entrada))
            else:
                bg_celula = T.SURFACE if ativo_visual else f"{T.SURFACE_ALT}45"
                cor_borda_base = f"{T.PRIMARY}55" if (eh_parcial and ativo_visual) else T.BORDER

        if eh_hoje:
            cor_borda_base = T.WARNING

        borda_normal = borda(1.5 if eh_hoje else 1, cor_borda_base)
        borda_hover = borda(1.8, T.PRIMARY)

        # Conteúdo interno da célula do dia
        pilulas: list[ft.Control] = []

        if modo == "saidas":
            # Estilo Imagem 2 ("Saídas por dia" — número no topo e valor ou "–" embaixo)
            pilulas.append(
                ft.Text(
                    formatar_moeda_heatmap(desp_d) if not mobile else (formatar_moeda_heatmap(desp_d).replace("R$ ", "") if desp_d > 0 else "–"),
                    size=9.5 if mobile else 11.5,
                    weight=ft.FontWeight.BOLD if desp_d > 0 else ft.FontWeight.NORMAL,
                    color=T.TEXT_PRIMARY if desp_d > 0 else T.TEXT_MUTED,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )
        elif modo == "entradas":
            pilulas.append(
                ft.Text(
                    formatar_moeda_heatmap(rec_d) if not mobile else (formatar_moeda_heatmap(rec_d).replace("R$ ", "") if rec_d > 0 else "–"),
                    size=9.5 if mobile else 11.5,
                    weight=ft.FontWeight.BOLD if rec_d > 0 else ft.FontWeight.NORMAL,
                    color=T.RECEITA if rec_d > 0 else T.TEXT_MUTED,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )
        else:
            # Estilo Imagem 1: Pílula vermelha para saídas e pílula verde para entradas!
            if rec_d > 0:
                txt_r = formatar_moeda_heatmap(rec_d) if mobile else formatar_moeda_curta_cal(rec_d)
                pilulas.append(
                    ft.Container(
                        padding=pad(h=4 if mobile else 6, v=1 if mobile else 2),
                        border_radius=8,
                        bgcolor=T.RECEITA,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(
                            txt_r,
                            size=8.5 if mobile else 10,
                            weight=ft.FontWeight.BOLD,
                            color="#FFFFFF",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    )
                )
            if desp_d > 0:
                txt_d = formatar_moeda_heatmap(desp_d) if mobile else formatar_moeda_curta_cal(desp_d)
                pilulas.append(
                    ft.Container(
                        padding=pad(h=4 if mobile else 6, v=1 if mobile else 2),
                        border_radius=8,
                        bgcolor=T.DESPESA,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(
                            txt_d,
                            size=8.5 if mobile else 10,
                            weight=ft.FontWeight.BOLD,
                            color="#FFFFFF",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    )
                )

        # Marcadores especiais no topo direito (💳 Fatura / 📦 Caixinha)
        icones_topo_dir: list[ft.Control] = []
        if vencimentos_dia:
            tem_aberta = any(
                str(v.get("status") or "").lower() != "paga" and float(v.get("valor_total", 0) or 0) > 0.01
                for v in vencimentos_dia
            )
            cor_ic_fat = T.WARNING if tem_aberta else T.RECEITA
            icones_topo_dir.append(
                ft.Container(
                    padding=pad(h=3, v=1),
                    border_radius=5,
                    bgcolor=f"{cor_ic_fat}25",
                    content=ft.Icon(
                        ft.Icons.CREDIT_CARD_ROUNDED,
                        size=10 if mobile else 12,
                        color=cor_ic_fat,
                    ),
                )
            )

        lancs_cel_list = dia_info.get("lancamentos") or []
        tem_caixinha_no_dia = any(
            bool(l.get("caixinha_id")) or str(l.get("subtipo") or "").lower() == "provisionamento"
            for l in lancs_cel_list
        )
        if tem_caixinha_no_dia:
            caixinha_pendente = any(
                (bool(l.get("caixinha_id")) or str(l.get("subtipo") or "").lower() == "provisionamento")
                and str(l.get("status") or "").lower() != "pago"
                for l in lancs_cel_list
            )
            cor_ic_cx = T.WARNING if caixinha_pendente else T.PRIMARY
            icones_topo_dir.append(
                ft.Container(
                    padding=pad(h=3, v=1),
                    border_radius=5,
                    bgcolor=f"{cor_ic_cx}20",
                    tooltip="Provisão de Caixinha agendada",
                    content=ft.Icon(
                        ft.Icons.SAVINGS_ROUNDED,
                        size=9.5 if mobile else 11,
                        color=cor_ic_cx,
                    ),
                )
            )

        cor_num_dia = (
            T.WARNING
            if eh_hoje
            else (T.TEXT_PRIMARY if ativo_visual else f"{T.TEXT_MUTED}75")
        )

        eh_multi_m = bool(pacote_calendario.get("eh_multi_mes", False))
        rotulo_num_dia = (
            f"{dt_atual.day} {MESES_NOMES[dt_atual.month - 1][:3]}"
            if (eh_multi_m and (dt_atual.day == 1 or dt_iso == filtro_data_inicio[0]))
            else str(dt_atual.day)
        )

        celula = ft.Container(
            expand=1,
            height=64 if mobile else 82,
            padding=pad(h=4 if mobile else 7, v=4 if mobile else 6),
            bgcolor=bg_celula,
            border_radius=8 if mobile else 10,
            border=borda_normal,
            opacity=1.0 if ativo_visual else 0.34,
            ink=True,
            tooltip=_montar_tooltip_dia(dia_info, vencimentos_dia),
            on_click=lambda _, di=dia_info, vf=vencimentos_dia: _abrir_modal_dia(di, vf),
            content=ft.Column(
                spacing=2 if mobile else 4,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                rotulo_num_dia,
                                size=10 if (mobile and len(rotulo_num_dia) > 2) else (10.5 if mobile else 12),
                                weight=ft.FontWeight.BOLD if (eh_hoje or qtd_d > 0 or dt_atual.day == 1) else ft.FontWeight.W_500,
                                color=T.PRIMARY if (eh_multi_m and dt_atual.day == 1 and not eh_hoje) else cor_num_dia,
                            ),
                            ft.Row(spacing=2, tight=True, controls=icones_topo_dir),
                        ],
                    ),
                    ft.Column(
                        spacing=2,
                        tight=True,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=pilulas,
                    ),
                ],
            ),
        )

        def _on_hover_celula(e: ft.ControlEvent, c=celula, di=dia_info, vf=vencimentos_dia, bn=borda_normal):
            try:
                is_hov = str(e.data).lower() == "true" if e.data is not None else False
                c.border = borda_hover if is_hov else bn
                c.update()
                if is_hov:
                    _atualizar_painel_hover(di, vf)
            except Exception:
                pass

        celula.on_hover = _on_hover_celula
        return celula

    # ── Construção Completa da Visão Calendário (Grade + Rosca + Cartões) ────
    def _construir_visao_calendario():
        col_visao_calendario.controls.clear()

        m = mes_sel[0]
        a = ano_sel[0]
        kpis_m = pacote_calendario.get("kpis") or {}
        dias_lista = pacote_calendario.get("dias") or []
        faturas_lista = pacote_calendario.get("cartoes_faturas") or []
        desp_cat = pacote_calendario.get("despesas_por_categoria") or []
        rec_cat = pacote_calendario.get("receitas_por_categoria") or []

        rec_mes = float(kpis_m.get("receitas_mes", 0) or 0)
        desp_mes = float(kpis_m.get("despesas_mes", 0) or 0)
        dias_saida = int(kpis_m.get("dias_com_saida", 0) or 0)
        dias_entrada = int(kpis_m.get("dias_com_entrada", 0) or 0)
        maior_saida = float(kpis_m.get("maior_saida_dia", 0) or 0)

        # Mapa rápido de dias (YYYY-MM-DD -> dict)
        mapa_dias: dict[str, dict] = {}
        maior_entrada = 0.0
        for d_item in dias_lista:
            dt_k = str(d_item.get("data") or "")[:10]
            if dt_k:
                mapa_dias[dt_k] = d_item
                if d_item.get("no_mes_atual"):
                    maior_entrada = max(maior_entrada, float(d_item.get("total_receitas", 0) or 0))

        # Mapa rápido de vencimentos de faturas por data (YYYY-MM-DD -> list)
        mapa_vencimentos: dict[str, list[dict]] = {}
        for fat in faturas_lista:
            dv_str = str(fat.get("data_vencimento") or "")[:10]
            if dv_str:
                mapa_vencimentos.setdefault(dv_str, []).append(fat)

        # Calcula o início e fim da grade (suporta mês único 6 semanas ou Multi-Meses com Scroll)
        eh_multi_mes = bool(pacote_calendario.get("eh_multi_mes", False)) or (
            filtro_data_inicio[0][:7] != filtro_data_fim[0][:7]
        )
        eh_parcial = bool(pacote_calendario.get("eh_periodo_parcial", False))

        primeiro_dia_mes = date(a, m, 1)
        try:
            dt_ini_f = datetime.strptime(filtro_data_inicio[0][:10], "%Y-%m-%d").date()
            dt_fim_f = datetime.strptime(filtro_data_fim[0][:10], "%Y-%m-%d").date()
        except Exception:
            dt_ini_f = primeiro_dia_mes
            dt_fim_f = date(a, m, calendar.monthrange(a, m)[1])

        base_inicio_grade = dt_ini_f if eh_multi_mes else min(primeiro_dia_mes, dt_ini_f)
        offset_dom = (base_inicio_grade.weekday() + 1) % 7
        grid_inicio = base_inicio_grade - timedelta(days=offset_dom)

        if eh_multi_mes:
            offset_sab = (5 - dt_fim_f.weekday()) % 7
            grid_fim = dt_fim_f + timedelta(days=offset_sab)
            num_semanas = max(5, ((grid_fim - grid_inicio).days + 1) // 7)
        else:
            num_semanas = 6

        # Cabeçalho fixo dos dias da semana (DOM .. SÁB)
        cabecalho_dias_semana = ft.Row(
            spacing=4 if mobile else 6,
            controls=[
                ft.Container(
                    expand=1,
                    padding=pad(v=4),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(
                        nome_ds,
                        size=10 if mobile else 11,
                        weight=ft.FontWeight.BOLD,
                        color=T.TEXT_MUTED,
                    ),
                )
                for nome_ds in DIAS_SEMANA_CABECALHO
            ],
        )

        linhas_semanas: list[ft.Control] = []
        mes_anterior_semana: tuple[int, int] | None = None

        for sem in range(num_semanas):
            celulas_semana: list[ft.Control] = []
            mes_desta_semana: tuple[int, int] | None = None
            for d_idx in range(7):
                dt_cel = grid_inicio + timedelta(days=sem * 7 + d_idx)
                dt_iso = dt_cel.isoformat()
                if dt_cel.day == 1 or (sem == 0 and d_idx == 0):
                    if filtro_data_inicio[0] <= dt_iso <= filtro_data_fim[0] or sem == 0:
                        mes_desta_semana = (dt_cel.year, dt_cel.month)
                info_d = mapa_dias.get(dt_iso) or {
                    "data": dt_iso,
                    "dia": dt_cel.day,
                    "mes": dt_cel.month,
                    "ano": dt_cel.year,
                    "no_mes_atual": (dt_cel.month == m and dt_cel.year == a),
                    "no_periodo_filtro": (filtro_data_inicio[0] <= dt_iso <= filtro_data_fim[0]),
                    "total_receitas": 0.0,
                    "total_despesas": 0.0,
                    "despesas_conta": 0.0,
                    "despesas_cartao": 0.0,
                    "qtd_lancamentos": 0,
                    "lancamentos": [],
                }
                vencs_d = mapa_vencimentos.get(dt_iso) or []
                celulas_semana.append(
                    _construir_celula_dia(dt_cel, info_d, vencs_d, maior_saida, maior_entrada)
                )

            if eh_multi_mes and mes_desta_semana and mes_desta_semana != mes_anterior_semana:
                mes_anterior_semana = mes_desta_semana
                linhas_semanas.append(
                    ft.Container(
                        padding=pad(h=10, v=4),
                        bgcolor=f"{T.PRIMARY}14",
                        border_radius=8,
                        border=borda(1, f"{T.PRIMARY}35"),
                        content=ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=T.PRIMARY),
                                ft.Text(
                                    f"{MESES_NOMES[mes_desta_semana[1] - 1]} de {mes_desta_semana[0]}",
                                    size=11.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=T.PRIMARY,
                                ),
                            ],
                        ),
                    )
                )

            linhas_semanas.append(
                ft.Row(spacing=4 if mobile else 6, controls=celulas_semana)
            )

        usa_scroll_cal = eh_multi_mes or num_semanas > 6
        bloco_grade_semanas = (
            ft.Container(
                height=440 if mobile else 530,
                content=ft.Column(
                    spacing=4 if mobile else 6,
                    scroll=ft.ScrollMode.AUTO,
                    controls=linhas_semanas,
                ),
            )
            if usa_scroll_cal
            else ft.Column(spacing=4 if mobile else 6, controls=linhas_semanas)
        )

        rotulo_periodo_cal = (
            f"{formatar_data_br(filtro_data_inicio[0])} a {formatar_data_br(filtro_data_fim[0])}"
            if (eh_multi_mes or eh_parcial)
            else _nome_mes_ano(m, a)
        )

        # Chips de Modo do Mapa de Calor
        def _chip_modo_cal(id_modo: str, rotulo: str, icone: ft.IconData, cor_m: str) -> ft.Container:
            ativo = (modo_heatmap[0] == id_modo)
            return ft.Container(
                padding=pad(h=10, v=6),
                border_radius=10,
                bgcolor=f"{cor_m}22" if ativo else T.SURFACE_ALT,
                border=borda(1, cor_m if ativo else T.BORDER),
                ink=True,
                on_click=lambda _, md=id_modo: (modo_heatmap.__setitem__(0, md), _construir_visao_calendario(), page.update()),
                content=ft.Row(
                    spacing=5,
                    tight=True,
                    controls=[
                        ft.Icon(icone, size=14, color=cor_m if ativo else T.TEXT_MUTED),
                        ft.Text(
                            rotulo,
                            size=11.5,
                            weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                            color=cor_m if ativo else T.TEXT_MUTED,
                        ),
                    ],
                ),
            )

        # Cabeçalho dinâmico estilo Imagem 1 + Imagem 2
        if modo_heatmap[0] == "saidas":
            titulo_bloco_cal = "Saídas por dia"
            sub_bloco_cal = f"{rotulo_periodo_cal} · quanto saiu em cada dia"
            destaque_valor_cal = ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.END,
                controls=[
                    ft.Text(formatar_moeda(desp_mes), size=22 if mobile else 26, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                    ft.Text(f"em {dias_saida} dia(s) com saída", size=12, color=T.TEXT_MUTED),
                ],
            )
        elif modo_heatmap[0] == "entradas":
            titulo_bloco_cal = "Entradas por dia"
            sub_bloco_cal = f"{rotulo_periodo_cal} · quanto entrou em cada dia"
            destaque_valor_cal = ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.END,
                controls=[
                    ft.Text(formatar_moeda(rec_mes), size=22 if mobile else 26, weight=ft.FontWeight.BOLD, color=T.RECEITA),
                    ft.Text(f"em {dias_entrada} dia(s) com entrada", size=12, color=T.TEXT_MUTED),
                ],
            )
        else:
            titulo_bloco_cal = (
                f"Calendário Multi-Meses ({num_semanas} semanas · role para navegar)"
                if eh_multi_mes
                else "Calendário Financeiro"
            )
            sub_bloco_cal = f"{rotulo_periodo_cal} · consolidação diária e vencimentos de faturas"
            destaque_valor_cal = ft.Container(height=0)

        card_calendario_principal = ft.Container(
            col={"xs": 12, "md": 7, "lg": 7},
            padding=pad(all_=14 if mobile else 20),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=12,
                controls=[
                    # Barra superior de navegação entre meses (< outubro 2026 >)
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.IconButton(
                                icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                                icon_color=T.TEXT_PRIMARY,
                                bgcolor=T.SURFACE_ALT,
                                tooltip="Período anterior",
                                on_click=lambda _: _mudar_mes_delta(-1),
                            ),
                            ft.Column(
                                spacing=1,
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text(
                                        rotulo_periodo_cal,
                                        size=15 if (mobile or eh_multi_mes) else 18,
                                        weight=ft.FontWeight.BOLD,
                                        color=T.TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        titulo_bloco_cal,
                                        size=11,
                                        color=T.PRIMARY if eh_multi_mes else T.TEXT_MUTED,
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Container(
                                        padding=pad(h=8, v=5),
                                        border_radius=8,
                                        bgcolor=f"{T.PRIMARY}18",
                                        ink=True,
                                        tooltip="Voltar para o mês atual",
                                        on_click=lambda _: (
                                            mes_sel.__setitem__(0, hoje_d.month),
                                            ano_sel.__setitem__(0, hoje_d.year),
                                            carregar_dados(),
                                        ),
                                        content=ft.Text("Hoje", size=11, weight=ft.FontWeight.BOLD, color=T.PRIMARY),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                        icon_color=T.TEXT_PRIMARY,
                                        bgcolor=T.SURFACE_ALT,
                                        tooltip="Próximo período",
                                        on_click=lambda _: _mudar_mes_delta(1),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Modos de visualização (Fluxo Completo | Mapa de Calor: Saídas | Entradas)
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        spacing=8,
                        controls=[
                            ft.Row(
                                spacing=6,
                                wrap=True,
                                controls=[
                                    _chip_modo_cal("completo", "Entradas & Saídas", ft.Icons.CALENDAR_VIEW_MONTH_ROUNDED, T.PRIMARY),
                                    _chip_modo_cal("saidas", "Mapa de Calor (Saídas)", ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED, T.DESPESA),
                                    _chip_modo_cal("entradas", "Entradas por Dia", ft.Icons.TRENDING_UP_ROUNDED, T.RECEITA),
                                ],
                            ),
                            ft.Text(sub_bloco_cal, size=11, color=T.TEXT_MUTED),
                        ],
                    ),
                    destaque_valor_cal,
                    barra_inspecao_hover,
                    cabecalho_dias_semana,
                    bloco_grade_semanas,
                    # Legenda inferior + botão Ver Mais
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        wrap=True,
                        controls=[
                            ft.Row(
                                spacing=12,
                                wrap=True,
                                controls=[
                                    ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Container(width=10, height=10, border_radius=5, bgcolor=T.RECEITA),
                                            ft.Text("Entradas", size=11, color=T.TEXT_MUTED),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Container(width=10, height=10, border_radius=5, bgcolor=T.DESPESA),
                                            ft.Text("Saídas", size=11, color=T.TEXT_MUTED),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, size=12, color=T.WARNING),
                                            ft.Text("Vencimento de Fatura", size=11, color=T.TEXT_MUTED),
                                        ],
                                    ),
                                ],
                            ),
                            ft.TextButton(
                                content=ft.Text("VER EXTRATO DO MÊS", size=11.5, weight=ft.FontWeight.BOLD, color=T.PRIMARY),
                                on_click=lambda _: _trocar_aba(1),
                            ),
                        ],
                    ),
                ],
            ),
        )

        # ── Painel Lateral 1: Gráfico de Rosca "Por Categorias / Tags" (Estilo Imagem 2)
        eh_rosca_desp = (aba_rosca_tags[0] == "Despesas")
        lista_rosca = desp_cat if eh_rosca_desp else rec_cat
        total_rosca = desp_mes if eh_rosca_desp else rec_mes

        def _toggle_rosca(tipo_r: str):
            aba_rosca_tags[0] = tipo_r
            _construir_visao_calendario()
            page.update()

        toggle_rosca_header = ft.Container(
            padding=pad(all_=3),
            bgcolor=T.BG,
            border_radius=10,
            border=borda(),
            content=ft.Row(
                spacing=2,
                tight=True,
                controls=[
                    ft.Container(
                        padding=pad(h=12, v=5),
                        border_radius=8,
                        bgcolor=T.WARNING if eh_rosca_desp else "transparent",
                        ink=True,
                        on_click=lambda _: _toggle_rosca("Despesas"),
                        content=ft.Text(
                            "Despesas",
                            size=11.5,
                            weight=ft.FontWeight.BOLD if eh_rosca_desp else ft.FontWeight.W_500,
                            color="#0F172A" if eh_rosca_desp else T.TEXT_MUTED,
                        ),
                    ),
                    ft.Container(
                        padding=pad(h=12, v=5),
                        border_radius=8,
                        bgcolor=T.RECEITA if not eh_rosca_desp else "transparent",
                        ink=True,
                        on_click=lambda _: _toggle_rosca("Receitas"),
                        content=ft.Text(
                            "Receitas",
                            size=11.5,
                            weight=ft.FontWeight.BOLD if not eh_rosca_desp else ft.FontWeight.W_500,
                            color="#0F172A" if not eh_rosca_desp else T.TEXT_MUTED,
                        ),
                    ),
                ],
            ),
        )

        linhas_ranking_rosca: list[ft.Control] = []
        if not lista_rosca or total_rosca <= 0:
            linhas_ranking_rosca.append(
                ft.Container(
                    padding=pad(v=16),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(
                        f"Sem {aba_rosca_tags[0].lower()} registradas neste mês.",
                        size=12,
                        color=T.TEXT_MUTED,
                    ),
                )
            )
        else:
            for idx_c, item_c in enumerate(lista_rosca[:8]):
                cid = item_c.get("categoria_id")
                nome_c = str(item_c.get("categoria") or "Sem Categoria")
                val_c = float(item_c.get("total", 0) or 0)
                pct_c = float(item_c.get("percentual") or ((val_c / total_rosca * 100.0) if total_rosca > 0 else 0.0))
                cor_c = item_c.get("cor") or PALETA_ROSCA_FALLBACK[idx_c % len(PALETA_ROSCA_FALLBACK)]

                def _clicar_cat_rosca(_e, cat_id=cid, tp_sel="Despesa" if eh_rosca_desp else "Receita"):
                    if cat_id:
                        d_ini_m = date(a, m, 1)
                        d_fim_m = date(a, m, calendar.monthrange(a, m)[1])
                        ctx_c = ReportContext(
                            data_inicio=d_ini_m,
                            data_fim=d_fim_m,
                            tipo=tp_sel,
                            categoria_id=str(cat_id),
                            origem="calendario",
                        )
                        ir_relatorio_categoria(page, str(cat_id), ctx_c)

                linhas_ranking_rosca.append(
                    ft.Container(
                        padding=pad(h=6, v=5),
                        border_radius=8,
                        ink=True,
                        on_click=_clicar_cat_rosca,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    width=130 if not mobile else 110,
                                    controls=[
                                        ft.Container(width=9, height=9, border_radius=5, bgcolor=cor_c),
                                        ft.Text(
                                            nome_c,
                                            size=12,
                                            weight=ft.FontWeight.W_600,
                                            color=T.TEXT_PRIMARY,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            expand=True,
                                        ),
                                    ],
                                ),
                                ft.Container(
                                    expand=True,
                                    padding=pad(h=8),
                                    content=ft.ProgressBar(
                                        value=max(0.0, min(1.0, pct_c / 100.0)),
                                        color=cor_c,
                                        bgcolor=f"{T.BORDER}55",
                                        height=6,
                                        border_radius=4,
                                    ),
                                ),
                                ft.Row(
                                    spacing=8,
                                    tight=True,
                                    controls=[
                                        ft.Text(formatar_moeda(val_c), size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                        ft.Container(
                                            width=44,
                                            alignment=ft.Alignment(1, 0),
                                            content=ft.Text(f"{pct_c:.1f}%", size=11, color=T.TEXT_MUTED),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

        card_rosca_tags = ft.Container(
            padding=pad(all_=16 if mobile else 20),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text("Por Categorias / Tags", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            toggle_rosca_header,
                        ],
                    ),
                    ft.Container(
                        padding=pad(v=6),
                        alignment=ft.Alignment(0, 0),
                        content=construir_grafico_rosca(lista_rosca, total_rosca),
                    ),
                    ft.Column(spacing=4, controls=linhas_ranking_rosca),
                ],
            ),
        )

        # ── Painel Lateral 2: Resumo de Faturas de Cartões no Mês (Estilo Imagem 1)
        linhas_cartoes_mes: list[ft.Control] = []
        soma_faturas_mes = 0.0
        for cf in faturas_lista:
            c_nome = str(cf.get("cartao_nome") or "Cartão")
            v_fat = float(cf.get("valor_total", 0) or 0)
            soma_faturas_mes += v_fat
            lim_tot = float(cf.get("limite_total", 0) or 0)
            lim_disp = float(cf.get("limite_disponivel", 0) or 0)
            usado_pct = round(((lim_tot - lim_disp) / lim_tot * 100.0), 2) if lim_tot > 0 else 0.0
            st_f = str(cf.get("status") or "aberta").lower()
            eh_paga = (st_f == "paga" or v_fat <= 0.01)
            cor_st = T.RECEITA if eh_paga else T.WARNING
            lbl_st = "Fatura zerada" if v_fat <= 0.01 else ("Fatura paga" if eh_paga else f"Vence dia {cf.get('dia_vencimento_efetivo', 10):02d}")

            linhas_cartoes_mes.append(
                ft.Container(
                    padding=pad(v=8),
                    content=ft.Column(
                        spacing=5,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.START,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.Container(
                                                padding=pad(all_=7),
                                                border_radius=8,
                                                bgcolor=f"{cf.get('cartao_cor') or T.PRIMARY}20",
                                                content=ft.Icon(
                                                    ft.Icons.CREDIT_CARD_ROUNDED,
                                                    color=cf.get("cartao_cor") or T.PRIMARY,
                                                    size=16,
                                                ),
                                            ),
                                            ft.Column(
                                                spacing=1,
                                                controls=[
                                                    ft.Text(c_nome, size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                                    ft.Text(lbl_st, size=11, color=cor_st, weight=ft.FontWeight.W_600),
                                                    ft.Text(
                                                        formatar_moeda(v_fat),
                                                        size=12.5,
                                                        weight=ft.FontWeight.BOLD,
                                                        color=T.DESPESA if v_fat > 0 else T.TEXT_MUTED,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Text(lbl_st, size=11.5, weight=ft.FontWeight.BOLD, color=cor_st),
                                ],
                            ),
                            ft.ProgressBar(
                                value=max(0.0, min(1.0, usado_pct / 100.0)),
                                color=T.RECEITA if usado_pct < 70 else T.WARNING,
                                bgcolor=f"{T.BORDER}55",
                                height=6,
                                border_radius=4,
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(f"Limite Disponível {formatar_moeda(lim_disp)}", size=10.5, color=T.TEXT_MUTED),
                                    ft.Text(f"{usado_pct:.1f}%", size=10.5, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                                ],
                            ),
                        ],
                    ),
                )
            )

        card_faturas_lateral = ft.Container(
            padding=pad(all_=16 if mobile else 20),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color=T.WARNING, size=18),
                                    ft.Text(
                                        "Faturas do Período" if eh_multi_mes else "Faturas do Mês",
                                        size=15,
                                        weight=ft.FontWeight.BOLD,
                                        color=T.TEXT_PRIMARY,
                                    ),
                                ],
                            ),
                            ft.Text(
                                rotulo_periodo_cal if (eh_multi_mes or eh_parcial) else _nome_mes_ano_cap(m, a),
                                size=11.5,
                                color=T.TEXT_MUTED,
                            ),
                        ],
                    ),
                    *linhas_cartoes_mes,
                    ft.Divider(color=T.BORDER, height=8),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("TOTAL", size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(formatar_moeda(soma_faturas_mes), size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ],
                    ),
                    ft.Container(
                        alignment=ft.Alignment(0, 0),
                        padding=pad(top=4),
                        content=ft.TextButton(
                            content=ft.Text("VER MAIS EM CARTÕES", size=11.5, weight=ft.FontWeight.BOLD, color=T.PRIMARY),
                            on_click=lambda _: ir_cartoes(page),
                        ),
                    ),
                ],
            ),
        )

        coluna_lateral_direita = ft.Container(
            col={"xs": 12, "md": 5, "lg": 5},
            content=ft.Column(
                spacing=14,
                controls=[
                    card_rosca_tags,
                    card_faturas_lateral,
                ],
            ),
        )

        col_visao_calendario.controls.append(
            ft.ResponsiveRow(
                spacing=14,
                run_spacing=14,
                controls=[
                    card_calendario_principal,
                    coluna_lateral_direita,
                ],
            )
        )

    # ── Funções de Carregamento e Lista Linear (Extrato) ─────────────────────
    def carregar_dados():
        spinner.visible = True
        try:
            page.update()
        except Exception:
            pass

        try:
            nonlocal pacote_calendario, todos_lancamentos
            pacote_calendario = db.obter_calendario_financeiro_mes(
                mes_sel[0],
                ano_sel[0],
                data_inicio=filtro_data_inicio[0],
                data_fim=filtro_data_fim[0],
            )
            if aba_ativa[0] == 1:
                todos_lancamentos = db.listar_lancamentos(
                    data_inicio=filtro_data_inicio[0],
                    data_fim=filtro_data_fim[0],
                )
            else:
                # Reaproveita os lançamentos do período filtrado vindos no pacote do calendário
                lancs_mes = []
                for d_item in (pacote_calendario.get("dias") or []):
                    if d_item.get("no_periodo_filtro", d_item.get("no_mes_atual")):
                        lancs_mes.extend(d_item.get("lancamentos") or [])
                todos_lancamentos = lancs_mes
            atualizar_visao()
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao carregar dados: {ex}", "erro")
        finally:
            spinner.visible = False
            try:
                page.update()
            except Exception:
                pass

    def alternar_status_lancamento(item: dict):
        novo_status = "Pendente" if item.get("status") == "Pago" else "Pago"
        try:
            db.atualizar_lancamento(item["id"], {"status": novo_status})
            item["status"] = novo_status
            mostrar_feedback(page, f"Status alterado para {novo_status}!", "sucesso")
            carregar_dados()
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao atualizar: {ex}", "erro")

    def confirmar_exclusao(item: dict):
        def _executar_exclusao(_):
            fechar_dialogo(page, dialog)
            try:
                db.deletar_lancamento(item["id"])
                mostrar_feedback(page, "Lançamento excluído com sucesso!", "sucesso")
                carregar_dados()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao excluir: {ex}", "erro")

        dialog = ft.AlertDialog(
            title=ft.Text("Excluir Lançamento", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"Tem certeza que deseja excluir o lançamento '{item.get('descricao', 'Sem descrição')}' "
                f"no valor de {formatar_moeda(float(item.get('valor', 0)))}?",
                color=T.TEXT_MUTED,
                size=14,
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: fechar_dialogo(page, dialog),
                ),
                ft.FilledButton(
                    content=ft.Text("Excluir", color=ft.Colors.WHITE),
                    style=ft.ButtonStyle(bgcolor=T.DESPESA),
                    on_click=_executar_exclusao,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dialog)

    def _card_lancamento(item: dict) -> ft.Container:
        tipo = item.get("tipo", "Despesa")
        eh_receita = tipo == "Receita"
        valor = float(item.get("valor", 0) or 0)
        sinal = "+" if eh_receita else "-"
        cor_valor = T.RECEITA if eh_receita else T.DESPESA

        icone_tipo = ft.Icons.ARROW_UPWARD_ROUNDED if eh_receita else ft.Icons.ARROW_DOWNWARD_ROUNDED
        cor_badge_tipo = f"{cor_valor}1A"

        categoria_info = item.get("categorias") or {}
        categoria_nome = item.get("categoria_nome") or categoria_info.get("nome", "Sem Categoria")
        conta_info = item.get("contas") or {}
        conta_nome = item.get("conta_nome") or item.get("cartao_nome") or conta_info.get("nome", "Conta")

        status = item.get("status", "Pago")
        eh_pago = status == "Pago"

        sub_badges = [
            ft.Container(
                content=ft.Text(conta_nome, size=10, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                bgcolor=T.SURFACE_ALT,
                padding=pad(h=6, v=2),
                border_radius=6,
            ),
            ft.Container(
                content=ft.Text(categoria_nome, size=10, color=T.PRIMARY_SOFT, weight=ft.FontWeight.W_500),
                bgcolor=f"{T.PRIMARY}18",
                padding=pad(h=6, v=2),
                border_radius=6,
            ),
        ]

        regra = item.get("regra")
        if regra:
            cor_regra = T.PRIMARY if regra == "Essencial" else (T.WARNING if regra == "Estilo de Vida" else T.SALDO)
            sub_badges.append(
                ft.Container(
                    content=ft.Text(regra, size=10, color=cor_regra, weight=ft.FontWeight.W_600),
                    bgcolor=f"{cor_regra}18",
                    padding=pad(h=6, v=2),
                    border_radius=6,
                )
            )

        if item.get("forma_movimentacao") == "Crédito" and item.get("parcela_atual"):
            parc_atual = item.get("parcela_atual", 1)
            parc_total = item.get("total_parcelas", 1)
            fatura_ref = item.get("fatura", "")
            texto_parc = f"Parcela {parc_atual}/{parc_total}" + (f" • {fatura_ref}" if fatura_ref else "")
            sub_badges.append(
                ft.Container(
                    content=ft.Text(texto_parc, size=10, color=T.WARNING, weight=ft.FontWeight.W_500),
                    bgcolor=f"{T.WARNING}15",
                    padding=pad(h=6, v=2),
                    border_radius=6,
                )
            )

        badge_status = ft.Container(
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if eh_pago else ft.Icons.SCHEDULE_ROUNDED,
                        size=12,
                        color=T.RECEITA if eh_pago else T.WARNING,
                    ),
                    ft.Text(
                        status,
                        size=11,
                        color=T.RECEITA if eh_pago else T.WARNING,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
            bgcolor=f"{T.RECEITA}18" if eh_pago else f"{T.WARNING}18",
            border_radius=12,
            padding=pad(h=8, v=4),
            border=borda(1, f"{T.RECEITA}30" if eh_pago else f"{T.WARNING}30"),
            tooltip="Clique para alterar status",
            on_click=lambda _, it=item: alternar_status_lancamento(it),
        )

        data_str = formatar_data_br(item.get("data", ""))

        if not mobile:
            return ft.Container(
                padding=pad(h=16, v=12),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            expand=True,
                            controls=[
                                ft.Container(
                                    content=ft.Icon(icone_tipo, color=cor_valor, size=18),
                                    bgcolor=cor_badge_tipo,
                                    border_radius=10,
                                    padding=pad(all_=10),
                                ),
                                ft.Column(
                                    spacing=4,
                                    expand=True,
                                    controls=[
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.Text(
                                                    item.get("descricao") or categoria_nome,
                                                    color=T.TEXT_PRIMARY,
                                                    size=14,
                                                    weight=ft.FontWeight.W_600,
                                                    overflow=ft.TextOverflow.ELLIPSIS,
                                                ),
                                                ft.Text(data_str, color=T.TEXT_MUTED, size=11),
                                            ],
                                        ),
                                        ft.Row(spacing=6, wrap=True, controls=sub_badges),
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=12,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                badge_status,
                                ft.Text(
                                    f"{sinal} {formatar_moeda(valor)}",
                                    color=cor_valor,
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color=T.TEXT_MUTED,
                                    icon_size=18,
                                    tooltip="Excluir",
                                    on_click=lambda _, it=item: confirmar_exclusao(it),
                                ),
                            ],
                        ),
                    ],
                ),
            )

        # =========================================================================
        # LAYOUT DEDICADO MOBILE NO CALENDÁRIO: Compacto, 2 linhas, sem espaço vazio
        # =========================================================================
        nome_desc = (item.get("descricao") or "").strip()
        tem_desc = bool(nome_desc and nome_desc.lower() != str(categoria_nome).lower())
        nome_principal = nome_desc if tem_desc else categoria_nome
        subtitulo = categoria_nome if tem_desc else ""

        col_textos_cal_mob: list[ft.Control] = [
            ft.Row(
                spacing=6,
                controls=[
                    ft.Text(
                        nome_principal,
                        color=T.TEXT_PRIMARY,
                        size=13.5,
                        weight=ft.FontWeight.W_600,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Text(data_str, color=T.TEXT_MUTED, size=10.5),
                ],
            )
        ]
        if subtitulo:
            col_textos_cal_mob.append(
                ft.Text(
                    subtitulo,
                    color=T.TEXT_MUTED,
                    size=11,
                    weight=ft.FontWeight.W_500,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )

        linha_topo_cal_mob = ft.Container(
            on_click=lambda _, it=item: abrir_lancamento(page, lancamento=it, on_saved=carregar_dados),
            ink=True,
            tooltip="Clique para editar este lançamento",
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=ft.Icon(icone_tipo, color=cor_valor, size=16),
                        bgcolor=cor_badge_tipo,
                        border_radius=8,
                        padding=pad(all_=8),
                    ),
                    ft.Column(
                        spacing=1,
                        expand=True,
                        controls=col_textos_cal_mob,
                    ),
                    ft.Text(
                        f"{sinal} {formatar_moeda(valor)}",
                        color=cor_valor,
                        size=14,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
        )

        badge_status_cal_mob = ft.Container(
            content=ft.Row(
                spacing=3,
                tight=True,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if eh_pago else ft.Icons.SCHEDULE_ROUNDED,
                        size=11,
                        color=T.RECEITA if eh_pago else T.WARNING,
                    ),
                    ft.Text(
                        status,
                        size=10,
                        color=T.RECEITA if eh_pago else T.WARNING,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
            bgcolor=f"{T.RECEITA}18" if eh_pago else f"{T.WARNING}18",
            border_radius=8,
            padding=pad(h=7, v=3),
            border=borda(1, f"{T.RECEITA}30" if eh_pago else f"{T.WARNING}30"),
            tooltip="Clique para alterar status",
            on_click=lambda _, it=item: alternar_status_lancamento(it),
            ink=True,
        )

        linha_rodape_cal_mob = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=4,
                    scroll=ft.ScrollMode.HIDDEN,
                    expand=True,
                    controls=sub_badges,
                ),
                ft.Row(
                    spacing=4,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        badge_status_cal_mob,
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                            icon_color=T.TEXT_MUTED,
                            icon_size=17,
                            tooltip="Excluir",
                            on_click=lambda _, it=item: confirmar_exclusao(it),
                            style=ft.ButtonStyle(padding=pad(all_=2)),
                        ),
                    ],
                ),
            ],
        )

        return ft.Container(
            padding=pad(h=12, v=10),
            bgcolor=T.SURFACE,
            border_radius=12,
            border=borda(),
            content=ft.Column(
                spacing=8,
                tight=True,
                controls=[
                    linha_topo_cal_mob,
                    linha_rodape_cal_mob,
                ],
            ),
        )

    def _renderizar_seletor_abas():
        def _btn_aba(label: str, icone, idx: int) -> ft.Container:
            ativo = aba_ativa[0] == idx
            return ft.Container(
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(icone, color=T.PRIMARY if ativo else T.TEXT_MUTED, size=16),
                        ft.Text(
                            label,
                            color=T.TEXT_PRIMARY if ativo else T.TEXT_MUTED,
                            size=13,
                            weight=ft.FontWeight.W_600 if ativo else ft.FontWeight.NORMAL,
                        ),
                    ],
                ),
                padding=pad(h=16, v=10),
                bgcolor=f"{T.PRIMARY}18" if ativo else "transparent",
                border_radius=10,
                ink=True,
                on_click=lambda _, i=idx: _trocar_aba(i),
            )

        row_seletor_abas_ref.controls = [
            _btn_aba("Calendário Financeiro", ft.Icons.CALENDAR_MONTH_ROUNDED, 0),
            _btn_aba("Lista de Transações",   ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, 1),
        ]

    def atualizar_visao():
        _renderizar_seletor_abas()

        kpis_m = pacote_calendario.get("kpis") or {}
        rec_m = float(kpis_m.get("receitas_mes", 0) or 0)
        desp_m = float(kpis_m.get("despesas_mes", 0) or 0)
        res_m = float(kpis_m.get("resultado_mes", rec_m - desp_m) or 0)
        cart_m = float(kpis_m.get("despesas_cartao_mes", 0) or 0)
        dias_s = int(kpis_m.get("dias_com_saida", 0) or 0)
        dias_e = int(kpis_m.get("dias_com_entrada", 0) or 0)

        txt_resultado_mes.value = formatar_moeda(res_m)
        txt_resultado_mes.color = T.TEXT_PRIMARY if res_m >= 0 else T.DESPESA
        txt_receitas_mes.value  = formatar_moeda(rec_m)
        txt_despesas_mes.value  = formatar_moeda(desp_m)
        txt_cartao_mes.value    = formatar_moeda(cart_m)

        eh_parcial_k = bool(pacote_calendario.get("eh_periodo_parcial", False))
        rotulo_per = (
            f"{formatar_data_br(filtro_data_inicio[0])} a {formatar_data_br(filtro_data_fim[0])}"
            if eh_parcial_k
            else _nome_mes_ano_cap(mes_sel[0], ano_sel[0])
        )
        txt_sub_resultado.value = f"{rotulo_per} · Receitas − Despesas"
        txt_sub_receitas.value  = f"em {dias_e} dia(s) com entrada"
        txt_sub_despesas.value  = f"em {dias_s} dia(s) com saída"
        txt_sub_cartao.value    = f"Gastos em crédito ({rotulo_per})"

        if aba_ativa[0] == 0:
            _construir_visao_calendario()
            area_principal.controls = [col_visao_calendario]
        else:
            filtrados = list(todos_lancamentos)
            if filtro_tipo[0] != "Todos":
                filtrados = [l for l in filtrados if l.get("tipo") == filtro_tipo[0]]
            if filtro_status[0] != "Todos":
                filtrados = [l for l in filtrados if l.get("status") == filtro_status[0]]
            if termo_busca[0]:
                termo = termo_busca[0].lower()
                filtrados = [
                    l for l in filtrados
                    if termo in (l.get("descricao") or "").lower()
                    or termo in (l.get("categoria_nome") or (l.get("categorias") or {}).get("nome") or "").lower()
                    or termo in (l.get("conta_nome") or (l.get("contas") or {}).get("nome") or "").lower()
                ]

            col_lista_lancamentos.controls.clear()
            if not filtrados:
                col_lista_lancamentos.controls.append(
                    ft.Container(
                        padding=pad(all_=40),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=12,
                            controls=[
                                ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=54, color=T.TEXT_MUTED),
                                ft.Text("Nenhum lançamento encontrado.", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                                ft.Text("Altere os filtros de data ou cadastre uma nova transação.", color=T.TEXT_MUTED, size=13),
                            ],
                        ),
                    )
                )
            else:
                for item in filtrados:
                    col_lista_lancamentos.controls.append(_card_lancamento(item))

            area_principal.controls = [
                DateFilterBar(on_change=on_date_filter_change),
                barra_filtros_lista,
                col_lista_lancamentos,
            ]

        try:
            page.update()
        except Exception:
            pass

    def _trocar_aba(idx: int):
        aba_ativa[0] = idx
        carregar_dados()

    def on_date_filter_change(inicio_str: str, fim_str: str):
        filtro_data_inicio[0] = inicio_str
        filtro_data_fim[0]    = fim_str
        est_novo = atualizar_datas_periodo_global(page, inicio_str, fim_str)
        mes_sel[0] = int(est_novo["mes"])
        ano_sel[0] = int(est_novo["ano"])
        sincronizar_shell_periodo(page)
        carregar_dados()

    def on_mes_ano_change(m: int, a: int):
        est = obter_estado_periodo_atual(page)
        mes_sel[0] = m
        ano_sel[0] = a
        filtro_data_inicio[0] = est["data_inicio"].isoformat()
        filtro_data_fim[0] = est["data_fim"].isoformat()
        carregar_dados()

    def on_periodo_change(d_ini: str, d_fim: str, m: int, a: int):
        mes_sel[0] = m
        ano_sel[0] = a
        filtro_data_inicio[0] = d_ini
        filtro_data_fim[0] = d_fim
        carregar_dados()

    # ── KPI Header do Mês (Estilo Imagem 2) ──────────────────────────────────
    def _kpi_topo(titulo: str, ref_ctrl: ft.Control, sub_ctrl: ft.Control, cor: str, icone):
        return ft.Container(
            col={"xs": 6, "sm": 6, "md": 3},
            padding=pad(all_=12 if mobile else 16),
            bgcolor=T.SURFACE,
            border_radius=14,
            border=borda(),
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(titulo, color=T.TEXT_MUTED, size=11.5, weight=ft.FontWeight.W_600),
                            ft.Icon(icone, color=cor, size=16),
                        ],
                    ),
                    ref_ctrl,
                    sub_ctrl,
                ],
            ),
        )

    kpis_periodo = ft.ResponsiveRow(
        spacing=10,
        run_spacing=10,
        controls=[
            _kpi_topo("Resultado do Período", txt_resultado_mes, txt_sub_resultado, T.PRIMARY, ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED),
            _kpi_topo("Receitas",             txt_receitas_mes,  txt_sub_receitas,  T.RECEITA, ft.Icons.ARROW_UPWARD_ROUNDED),
            _kpi_topo("Despesas",             txt_despesas_mes,  txt_sub_despesas,  T.DESPESA, ft.Icons.ARROW_DOWNWARD_ROUNDED),
            _kpi_topo("Gastos no Cartão",     txt_cartao_mes,    txt_sub_cartao,    T.WARNING, ft.Icons.CREDIT_CARD_ROUNDED),
        ],
    )

    # ── Barra de Busca e Filtros Rápidos (para a Aba 1 - Lista) ──────────────
    txt_busca = ft.TextField(
        hint_text="Buscar por descrição, conta ou categoria...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        expand=True,
        on_change=lambda e: (termo_busca.__setitem__(0, e.control.value), atualizar_visao()),
        **T.campo_estilo(),
    )

    def _chip_filtro(label: str, estado_ref: list, valor: str) -> ft.Container:
        ativo = estado_ref[0] == valor
        return ft.Container(
            content=ft.Text(
                label,
                size=12,
                weight=ft.FontWeight.W_600 if ativo else ft.FontWeight.NORMAL,
                color=T.PRIMARY if ativo else T.TEXT_MUTED,
            ),
            padding=pad(h=12, v=6),
            bgcolor=f"{T.PRIMARY}1A" if ativo else T.SURFACE_ALT,
            border_radius=16,
            border=borda(1, T.PRIMARY if ativo else T.BORDER),
            ink=True,
            on_click=lambda _: (estado_ref.__setitem__(0, valor), atualizar_visao()),
        )

    barra_filtros_lista = ft.Column(
        spacing=10,
        controls=[
            txt_busca,
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
                spacing=10,
                controls=[
                    ft.Row(
                        spacing=6,
                        wrap=True,
                        controls=[
                            ft.Text("Tipo:", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                            _chip_filtro("Todos",    filtro_tipo, "Todos"),
                            _chip_filtro("Receitas", filtro_tipo, "Receita"),
                            _chip_filtro("Despesas", filtro_tipo, "Despesa"),
                        ],
                    ),
                    ft.Row(
                        spacing=6,
                        wrap=True,
                        controls=[
                            ft.Text("Status:", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                            _chip_filtro("Todos",     filtro_status, "Todos"),
                            _chip_filtro("Pagos",     filtro_status, "Pago"),
                            _chip_filtro("Pendentes", filtro_status, "Pendente"),
                        ],
                    ),
                ],
            ),
        ],
    )

    seletor_abas = ft.Container(
        padding=pad(all_=4),
        bgcolor=T.SURFACE,
        border_radius=12,
        border=borda(),
        content=row_seletor_abas_ref,
    )

    # ── Cabeçalho da Página ──────────────────────────────────────────────────
    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        wrap=True,
        spacing=10,
        controls=[
            ft.Column(
                spacing=2,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Text("Calendário Financeiro", color=T.TEXT_PRIMARY, size=20 if mobile else 23, weight=ft.FontWeight.BOLD),
                            spinner,
                        ],
                    ),
                    ft.Text(
                        "Mapa de calor diário, vencimentos de faturas e distribuição por categorias",
                        color=T.TEXT_MUTED,
                        size=12,
                    ),
                ],
            ),
            ft.Row(
                spacing=10,
                wrap=True,
                controls=[
                    seletor_abas,
                    ft.FilledButton(
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                                ft.Text("Novo Lançamento", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        on_click=lambda _: abrir_lancamento(page, on_saved=carregar_dados),
                        style=ft.ButtonStyle(
                            bgcolor=T.PRIMARY,
                            overlay_color=T.PRIMARY_DARK,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=pad(h=16, v=12),
                        ),
                    ),
                ],
            ),
        ],
    )

    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=14),
            kpis_periodo,
            ft.Container(height=14),
            area_principal,
            ft.Container(height=28),
        ],
    )

    carregar_dados()

    v = criar_shell(
        page,
        rota_ativa=ROTA_CALENDARIO,
        conteudo=conteudo,
        on_mes_ano_change=on_mes_ano_change,
        on_periodo_change=on_periodo_change,
        on_lancamento_saved=carregar_dados,
    )
    v._dembase_refresh = carregar_dados
    return v
