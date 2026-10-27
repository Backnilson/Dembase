"""
=============================================================================
DemBase v3 — views/widgets/calendario_dashboard_card.py  (Flet 1.0.1)
Card Interativo do Calendário Financeiro (Mapa de Calor) para a Tela Inicial
(Dashboard). Pode ser reordenado e ativado/ocultado pelo usuário junto com
os 6 Potes, KPIs e Gráficos.
=============================================================================
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
import flet as ft

from core import theme as T
from core.theme import pad, borda, abrir_dialogo, fechar_dialogo
from core.constants import formatar_moeda, formatar_data_br, hoje
from core.responsive import is_mobile
from core.router import navegar
from core.nav import ir_cartoes, ir_relatorio_lancamentos
from core.report_context import ReportContext
from views.calendario_view import (
    DIAS_SEMANA_CABECALHO,
    MESES_NOMES,
    formatar_moeda_curta_cal,
    formatar_moeda_heatmap,
    calcular_cor_heatmap_saida,
    calcular_cor_heatmap_entrada,
)
from views.widgets.lancamento_sheet import abrir_lancamento


def secao_calendario_dashboard(
    page: ft.Page,
    pacote_cal: dict,
    mes: int,
    ano: int,
    on_refresh=None,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> ft.Container:
    """
    Renderiza o Card do Calendário Financeiro (Mapa de Calor) diretamente no Dashboard,
    sincronizado com o filtro global de datas [data_inicio, data_fim].
    """
    mobile = is_mobile(page)
    hoje_d = hoje()
    m = max(1, min(12, int(mes or hoje_d.month)))
    a = int(ano or hoje_d.year)
    ult_m = calendar.monthrange(a, m)[1]
    ini_m_iso = date(a, m, 1).isoformat()
    fim_m_iso = date(a, m, ult_m).isoformat()

    d_ini_ef = str(data_inicio or (pacote_cal or {}).get("filtro_inicio") or ini_m_iso)[:10]
    d_fim_ef = str(data_fim or (pacote_cal or {}).get("filtro_fim") or fim_m_iso)[:10]
    eh_parcial = bool((pacote_cal or {}).get("eh_periodo_parcial")) or (d_ini_ef != ini_m_iso or d_fim_ef != fim_m_iso)
    eh_multi_mes = bool((pacote_cal or {}).get("eh_multi_mes")) or (d_ini_ef[:7] != d_fim_ef[:7])

    nome_mes_cap = (
        f"{formatar_data_br(d_ini_ef)} a {formatar_data_br(d_fim_ef)}"
        if (eh_parcial or eh_multi_mes)
        else f"{MESES_NOMES[m - 1]} {a}"
    )

    modo_cal = ["completo"]  # "completo" ou "saidas"

    kpis_m = (pacote_cal or {}).get("kpis") or {}
    dias_lista = (pacote_cal or {}).get("dias") or []
    faturas_lista = (pacote_cal or {}).get("cartoes_faturas") or []
    acumulados_map = (pacote_cal or {}).get("acumulados_por_dia") or {}

    rec_mes = float(kpis_m.get("receitas_mes", 0) or 0)
    desp_mes = float(kpis_m.get("despesas_mes", 0) or 0)
    dias_saida = int(kpis_m.get("dias_com_saida", 0) or 0)
    maior_saida = float(kpis_m.get("maior_saida_dia", 0) or 0)

    mapa_dias: dict[str, dict] = {}
    maior_entrada = 0.0
    for d_item in dias_lista:
        dt_k = str(d_item.get("data") or "")[:10]
        if dt_k:
            mapa_dias[dt_k] = d_item
            if d_item.get("no_mes_atual") or d_item.get("no_periodo_filtro"):
                maior_entrada = max(maior_entrada, float(d_item.get("total_receitas", 0) or 0))

    mapa_vencimentos: dict[str, list[dict]] = {}
    for fat in faturas_lista:
        dv_str = str(fat.get("data_vencimento") or "")[:10]
        if dv_str:
            mapa_vencimentos.setdefault(dv_str, []).append(fat)

    txt_hover_info = ft.Text(
        "Passe o mouse ou toque em um dia para ver o acumulado contínuo até a data",
        size=11.5,
        color=T.TEXT_MUTED,
        weight=ft.FontWeight.W_500,
    )
    row_hover_chips = ft.Row(spacing=8, wrap=True, controls=[])
    barra_hover = ft.Container(
        padding=pad(h=12, v=8),
        bgcolor=T.SURFACE_ALT,
        border_radius=10,
        border=borda(),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
            spacing=8,
            controls=[
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.ADS_CLICK_ROUNDED, color=T.PRIMARY, size=15),
                        txt_hover_info,
                    ],
                ),
                row_hover_chips,
            ],
        ),
    )

    col_grade_semanas = ft.Column(spacing=4 if mobile else 6, controls=[])
    row_botoes_modo = ft.Row(spacing=6, tight=True, controls=[])

    def _obter_acum_dash(dt_s: str, dia_info: dict) -> dict:
        if dt_s in acumulados_map:
            return acumulados_map[dt_s]
        if isinstance(dia_info.get("acumulado"), dict):
            return dia_info["acumulado"]
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        desp_tot = float(dia_info.get("total_despesas", 0) or 0)
        return {
            "data_inicio_acum": d_ini_ef,
            "data_ate": dt_s,
            "receitas_acum": rec_d,
            "despesas_conta_acum": desp_cta,
            "despesas_cartao_acum": desp_crt,
            "despesas_total_acum": desp_tot,
            "saldo_acum": rec_d - desp_tot,
        }

    def _atualizar_hover(dia_info: dict, vencs: list[dict]):
        dt_s = str(dia_info.get("data") or "")[:10]
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        saldo_d = rec_d - desp_d
        qtd_d = int(dia_info.get("qtd_lancamentos", 0) or 0)

        acum = _obter_acum_dash(dt_s, dia_info)
        d_ini_ac = str(acum.get("data_inicio_acum") or d_ini_ef)[:10]
        rec_ac = float(acum.get("receitas_acum", 0) or 0)
        desp_tot_ac = float(acum.get("despesas_total_acum", 0) or 0)
        desp_crt_ac = float(acum.get("despesas_cartao_acum", 0) or 0)
        saldo_ac = float(acum.get("saldo_acum", rec_ac - desp_tot_ac) or 0)
        teto_apos = float(acum.get("teto_seguro_apos_dia", max(0.0, saldo_ac)) or 0)
        menor_apos = float(acum.get("menor_saldo_apos_dia", saldo_ac) or 0)
        eh_garg_princ = bool(dia_info.get("eh_gargalo_principal") or acum.get("eh_gargalo_principal"))

        txt_hover_info.value = (
            f"📅 Acum. {formatar_data_br(d_ini_ac)[:5]} → {formatar_data_br(dt_s)} "
            f"(Dia: {qtd_d} mov. | {formatar_moeda(saldo_d)})"
            + (" · ⚠️ GARGALO" if eh_garg_princ else "")
        )
        txt_hover_info.color = T.TEXT_PRIMARY
        row_hover_chips.controls = [
            ft.Text(f"Rec. Acum: {formatar_moeda(rec_ac)}", size=11, weight=ft.FontWeight.BOLD, color=T.RECEITA),
            ft.Text(f"Desp. Acum: {formatar_moeda(desp_tot_ac)}", size=11, weight=ft.FontWeight.BOLD, color=T.DESPESA),
            ft.Text(f"Faturas Acum: {formatar_moeda(desp_crt_ac)}", size=11, weight=ft.FontWeight.BOLD, color=T.WARNING),
            ft.Container(
                padding=pad(h=7, v=2),
                border_radius=6,
                bgcolor=f"{T.RECEITA}22" if saldo_ac >= 0 else f"{T.DESPESA}22",
                border=borda(1, T.RECEITA if saldo_ac >= 0 else T.DESPESA),
                content=ft.Text(
                    f"Saldo Acumulado: {formatar_moeda(saldo_ac)}",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color=T.RECEITA if saldo_ac >= 0 else T.DESPESA,
                ),
            ),
            ft.Container(
                padding=pad(h=7, v=2),
                border_radius=6,
                bgcolor="#06B6D422" if menor_apos >= 0 else f"{T.DESPESA}22",
                border=borda(1, "#06B6D4" if menor_apos >= 0 else T.DESPESA),
                content=ft.Text(
                    f"🛡️ Teto Seguro: {formatar_moeda(teto_apos)}",
                    size=11,
                    weight=ft.FontWeight.BOLD,
                    color="#06B6D4" if menor_apos >= 0 else T.DESPESA,
                ),
            ),
        ]
        for cx_l in (dia_info.get("lancamentos") or []):
            if cx_l.get("caixinha_id") or str(cx_l.get("subtipo") or "").lower() == "provisionamento":
                cx_n = cx_l.get("caixinha_nome") or cx_l.get("descricao") or "Caixinha"
                cx_v = float(cx_l.get("valor", 0) or 0)
                cx_st = str(cx_l.get("status") or "Pendente")
                row_hover_chips.controls.append(
                    ft.Text(f"📦 {cx_n}: {formatar_moeda(cx_v)} ({cx_st})", size=11, weight=ft.FontWeight.BOLD, color=T.INFO)
                )
        try:
            barra_hover.update()
        except Exception:
            pass

    def _tooltip_dia(dia_info: dict, vencs: list[dict]) -> str:
        dt_s = str(dia_info.get("data") or "")[:10]
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        saldo_d = rec_d - desp_d

        acum = _obter_acum_dash(dt_s, dia_info)
        d_ini_ac = str(acum.get("data_inicio_acum") or d_ini_ef)[:10]
        rec_ac = float(acum.get("receitas_acum", 0) or 0)
        desp_cta_ac = float(acum.get("despesas_conta_acum", 0) or 0)
        desp_crt_ac = float(acum.get("despesas_cartao_acum", 0) or 0)
        desp_tot_ac = float(acum.get("despesas_total_acum", 0) or 0)
        saldo_ac = float(acum.get("saldo_acum", rec_ac - desp_tot_ac) or 0)
        teto_apos = float(acum.get("teto_seguro_apos_dia", max(0.0, saldo_ac)) or 0)
        menor_apos = float(acum.get("menor_saldo_apos_dia", saldo_ac) or 0)
        dt_garg_apos = acum.get("data_gargalo_apos_dia")
        eh_garg_princ = bool(dia_info.get("eh_gargalo_principal") or acum.get("eh_gargalo_principal"))

        linhas = [
            f"📅 {formatar_data_br(dt_s)}" + (" · ⚠️ PIOR DIA (GARGALO)" if eh_garg_princ else ""),
            f"── Acumulado ({formatar_data_br(d_ini_ac)} até {formatar_data_br(dt_s)}) ──",
            f"🟢 Receitas Acum.: {formatar_moeda(rec_ac)}",
            f"🔴 Despesas Acum.: {formatar_moeda(desp_tot_ac)} (Conta: {formatar_moeda(desp_cta_ac)} | Faturas: {formatar_moeda(desp_crt_ac)})",
            f"💰 SALDO ACUMULADO: {formatar_moeda(saldo_ac)}",
            f"🛡️ TETO SEGURO A PARTIR DAQUI: {formatar_moeda(teto_apos)}"
            + (f" (Menor saldo: {formatar_moeda(menor_apos)} em {formatar_data_br(dt_garg_apos)})" if dt_garg_apos else ""),
            f"── Movimento do Dia ──",
            f"   • Receita: {formatar_moeda(rec_d)} | Despesa: {formatar_moeda(desp_d)} (Conta: {formatar_moeda(desp_cta)} | Cartão: {formatar_moeda(desp_crt)})",
            f"   • Saldo do Dia: {formatar_moeda(saldo_d)}",
        ]
        for vf in vencs:
            linhas.append(f"💳 Vencimento {vf.get('cartao_nome')}: {formatar_moeda(float(vf.get('valor_total', 0) or 0))}")
        for cx_l in (dia_info.get("lancamentos") or []):
            if cx_l.get("caixinha_id") or str(cx_l.get("subtipo") or "").lower() == "provisionamento":
                cx_n = cx_l.get("caixinha_nome") or cx_l.get("descricao") or "Caixinha"
                cx_v = float(cx_l.get("valor", 0) or 0)
                cx_st = str(cx_l.get("status") or "Pendente").upper()
                linhas.append(f"📦 Caixinha {cx_n}: {formatar_moeda(cx_v)} ({cx_st})")
        return "\n".join(linhas)

    def _abrir_modal_dia_dash(dia_info: dict, vencs: list[dict]):
        dt_str = str(dia_info.get("data") or "")
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        lancs_dia = dia_info.get("lancamentos") or []

        def _ir_extrato_data(_):
            fechar_dialogo(page, dlg)
            try:
                dt_obj = datetime.strptime(dt_str[:10], "%Y-%m-%d").date()
                ctx_d = ReportContext(data_inicio=dt_obj, data_fim=dt_obj, origem="dashboard")
                ir_relatorio_lancamentos(page, ctx=ctx_d, origem="dashboard")
            except Exception:
                navegar(page, "/calendario")

        itens_m: list[ft.Control] = []
        for vf in vencs:
            v_fat = float(vf.get("valor_total", 0) or 0)
            itens_m.append(
                ft.Container(
                    padding=pad(h=10, v=8),
                    bgcolor=f"{T.WARNING}15",
                    border_radius=8,
                    border=borda(1, f"{T.WARNING}40"),
                    ink=True,
                    on_click=lambda _: (fechar_dialogo(page, dlg), ir_cartoes(page)),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(f"💳 Vencimento {vf.get('cartao_nome')}", size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(formatar_moeda(v_fat), size=12.5, weight=ft.FontWeight.BOLD, color=T.WARNING),
                        ],
                    ),
                )
            )

        if not lancs_dia and not vencs:
            itens_m.append(
                ft.Container(
                    padding=pad(all_=20),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("Sem movimentações registradas nesta data.", size=12.5, color=T.TEXT_MUTED),
                )
            )
        else:
            for l_it in lancs_dia:
                eh_rec = (str(l_it.get("tipo")) == "Receita")
                val_l = float(l_it.get("valor", 0) or 0)
                cor_l = T.RECEITA if eh_rec else T.DESPESA
                sinal_l = "+" if eh_rec else "-"
                cat_n = l_it.get("categoria_nome") or "Sem Categoria"
                origem_n = l_it.get("cartao_nome") or l_it.get("conta_nome") or ""
                eh_caixinha = bool(l_it.get("caixinha_id")) or str(l_it.get("subtipo") or "").lower() == "provisionamento"
                if eh_caixinha:
                    cx_nome = l_it.get("caixinha_nome")
                    origem_n = f"{origem_n} · 📦 Caixinha {cx_nome or ''}".strip(" ·")
                st_l = str(l_it.get("status") or "Pago")
                eh_pago = st_l.lower() == "pago"
                itens_m.append(
                    ft.Container(
                        padding=pad(h=10, v=8),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=8,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        ft.Text(l_it.get("descricao") or cat_n, size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(f"{cat_n} · {origem_n}".strip(" ·"), size=10.5, color=T.TEXT_MUTED),
                                    ],
                                ),
                                ft.Column(
                                    spacing=1,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    controls=[
                                        ft.Text(f"{sinal_l} {formatar_moeda(val_l)}", size=12.5, weight=ft.FontWeight.BOLD, color=cor_l),
                                        ft.Text(st_l, size=10, color=T.RECEITA if eh_pago else T.WARNING, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

        dlg = ft.AlertDialog(
            modal=False,
            bgcolor=T.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=16),
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text(f"📅 {formatar_data_br(dt_str)}", size=15.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_size=18, on_click=lambda _: fechar_dialogo(page, dlg)),
                ],
            ),
            content=ft.Container(
                width=440 if not mobile else 320,
                content=ft.Column(
                    tight=True,
                    spacing=8,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(f"Receita: {formatar_moeda(rec_d)}", size=11.5, weight=ft.FontWeight.BOLD, color=T.RECEITA),
                                ft.Text(f"Conta: {formatar_moeda(desp_cta)}", size=11.5, weight=ft.FontWeight.BOLD, color=T.DESPESA),
                                ft.Text(f"Cartão: {formatar_moeda(desp_crt)}", size=11.5, weight=ft.FontWeight.BOLD, color=T.WARNING),
                            ],
                        ),
                        ft.Divider(color=T.BORDER, height=6),
                        ft.Container(
                            height=240,
                            content=ft.Column(spacing=6, scroll=ft.ScrollMode.AUTO, controls=itens_m),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Abrir Extrato do Dia", on_click=_ir_extrato_data),
                ft.FilledButton(
                    content=ft.Text("+ Novo Lançamento", color=ft.Colors.WHITE, size=12),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=lambda _: (fechar_dialogo(page, dlg), abrir_lancamento(page, on_saved=on_refresh)),
                ),
            ],
        )
        abrir_dialogo(page, dlg)

    def _render_grade():
        # Botões de modo
        opcoes_m = [
            ("completo", "Entradas & Saídas", T.PRIMARY),
            ("saidas", "Mapa de Calor (Saídas)", T.DESPESA),
        ]
        row_botoes_modo.controls = [
            ft.Container(
                padding=pad(h=9, v=4),
                border_radius=8,
                bgcolor=f"{cor_op}22" if modo_cal[0] == id_op else T.SURFACE_ALT,
                border=borda(1, cor_op if modo_cal[0] == id_op else T.BORDER),
                ink=True,
                on_click=lambda _, md=id_op: (modo_cal.__setitem__(0, md), _render_grade(), page.update()),
                content=ft.Text(
                    lbl_op,
                    size=11,
                    weight=ft.FontWeight.BOLD if modo_cal[0] == id_op else ft.FontWeight.W_500,
                    color=cor_op if modo_cal[0] == id_op else T.TEXT_MUTED,
                ),
            )
            for id_op, lbl_op, cor_op in opcoes_m
        ]

        col_grade_semanas.controls.clear()
        col_grade_semanas.controls.append(
            ft.Row(
                spacing=4 if mobile else 6,
                controls=[
                    ft.Container(
                        expand=1,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(ds, size=10, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                    )
                    for ds in DIAS_SEMANA_CABECALHO
                ],
            )
        )

        primeiro_dia_mes = date(a, m, 1)
        try:
            dt_ini_f = datetime.strptime(d_ini_ef[:10], "%Y-%m-%d").date()
            dt_fim_f = datetime.strptime(d_fim_ef[:10], "%Y-%m-%d").date()
        except Exception:
            dt_ini_f = primeiro_dia_mes
            dt_fim_f = date(a, m, ult_m)

        base_ini_g = dt_ini_f if eh_multi_mes else min(primeiro_dia_mes, dt_ini_f)
        offset_dom = (base_ini_g.weekday() + 1) % 7
        grid_inicio = base_ini_g - timedelta(days=offset_dom)

        if eh_multi_mes:
            offset_sab = (5 - dt_fim_f.weekday()) % 7
            grid_fim = dt_fim_f + timedelta(days=offset_sab)
            num_semanas = max(5, ((grid_fim - grid_inicio).days + 1) // 7)
        else:
            num_semanas = 6

        linhas_sem_dash: list[ft.Control] = []
        mes_ant_sem: tuple[int, int] | None = None

        for sem in range(num_semanas):
            celulas: list[ft.Control] = []
            mes_desta_sem: tuple[int, int] | None = None
            for d_idx in range(7):
                dt_cel = grid_inicio + timedelta(days=sem * 7 + d_idx)
                dt_iso = dt_cel.isoformat()
                if dt_cel.day == 1 or (sem == 0 and d_idx == 0):
                    if d_ini_ef <= dt_iso <= d_fim_ef or sem == 0:
                        mes_desta_sem = (dt_cel.year, dt_cel.month)
                no_mes = (dt_cel.month == m and dt_cel.year == a)
                no_periodo = (d_ini_ef <= dt_iso <= d_fim_ef)
                ativo_visual = no_periodo if (eh_parcial or eh_multi_mes) else no_mes
                eh_hoje = (dt_cel == hoje_d)
                info_d = mapa_dias.get(dt_iso) or {
                    "data": dt_iso,
                    "dia": dt_cel.day,
                    "mes": dt_cel.month,
                    "ano": dt_cel.year,
                    "no_mes_atual": no_mes,
                    "no_periodo_filtro": no_periodo,
                    "total_receitas": 0.0,
                    "total_despesas": 0.0,
                    "despesas_conta": 0.0,
                    "despesas_cartao": 0.0,
                    "qtd_lancamentos": 0,
                    "lancamentos": [],
                }
                vencs_d = mapa_vencimentos.get(dt_iso) or []
                rec_d = float(info_d.get("total_receitas", 0) or 0)
                desp_d = float(info_d.get("total_despesas", 0) or 0)

                if modo_cal[0] == "saidas":
                    bg_c, bd_c = calcular_cor_heatmap_saida(desp_d if ativo_visual else 0.0, maior_saida)
                    if not ativo_visual:
                        bg_c = f"{T.SURFACE_ALT}50"
                else:
                    if desp_d > 0 and rec_d == 0 and ativo_visual:
                        bg_c, bd_c = calcular_cor_heatmap_saida(desp_d * 0.45, max(1.0, maior_saida))
                    elif rec_d > 0 and desp_d == 0 and ativo_visual:
                        bg_c, bd_c = calcular_cor_heatmap_entrada(rec_d * 0.45, max(1.0, maior_entrada))
                    else:
                        bg_c = T.BG if ativo_visual else f"{T.SURFACE_ALT}45"
                        bd_c = f"{T.PRIMARY}55" if ((eh_parcial or eh_multi_mes) and ativo_visual) else T.BORDER

                if eh_hoje:
                    bd_c = T.WARNING
                borda_norm = borda(1.5 if eh_hoje else 1, bd_c)
                borda_hov = borda(1.8, T.PRIMARY)

                pilulas: list[ft.Control] = []
                if modo_cal[0] == "saidas":
                    pilulas.append(
                        ft.Text(
                            formatar_moeda_heatmap(desp_d) if not mobile else (formatar_moeda_heatmap(desp_d).replace("R$ ", "") if desp_d > 0 else "–"),
                            size=9 if mobile else 11,
                            weight=ft.FontWeight.BOLD if desp_d > 0 else ft.FontWeight.NORMAL,
                            color=T.TEXT_PRIMARY if desp_d > 0 else T.TEXT_MUTED,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        )
                    )
                else:
                    if rec_d > 0:
                        pilulas.append(
                            ft.Container(
                                padding=pad(h=3 if mobile else 5, v=1),
                                border_radius=6,
                                bgcolor=T.RECEITA,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Text(
                                    formatar_moeda_heatmap(rec_d) if mobile else formatar_moeda_curta_cal(rec_d),
                                    size=8 if mobile else 9.5,
                                    weight=ft.FontWeight.BOLD,
                                    color="#FFFFFF",
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            )
                        )
                    if desp_d > 0:
                        pilulas.append(
                            ft.Container(
                                padding=pad(h=3 if mobile else 5, v=1),
                                border_radius=6,
                                bgcolor=T.DESPESA,
                                alignment=ft.Alignment(0, 0),
                                content=ft.Text(
                                    formatar_moeda_heatmap(desp_d) if mobile else formatar_moeda_curta_cal(desp_d),
                                    size=8 if mobile else 9.5,
                                    weight=ft.FontWeight.BOLD,
                                    color="#FFFFFF",
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            )
                        )

                ic_venc = []
                if vencs_d:
                    ic_venc.append(
                        ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, size=10 if mobile else 11, color=T.WARNING)
                    )
                l_cel_list = info_d.get("lancamentos") or []
                tem_cx_cel = any(
                    bool(l.get("caixinha_id")) or str(l.get("subtipo") or "").lower() == "provisionamento"
                    for l in l_cel_list
                )
                if tem_cx_cel:
                    cx_pend = any(
                        (bool(l.get("caixinha_id")) or str(l.get("subtipo") or "").lower() == "provisionamento")
                        and str(l.get("status") or "").lower() != "pago"
                        for l in l_cel_list
                    )
                    ic_venc.append(
                        ft.Icon(
                            ft.Icons.SAVINGS_ROUNDED,
                            size=9.5 if mobile else 10.5,
                            color=T.WARNING if cx_pend else T.PRIMARY,
                        )
                    )

                acum_cel = _obter_acum_dash(dt_iso, info_d)
                eh_garg_princ = bool(info_d.get("eh_gargalo_principal") or acum_cel.get("eh_gargalo_principal"))
                eh_neg_dia = bool(info_d.get("eh_dia_negativo") or acum_cel.get("eh_dia_negativo"))
                if ativo_visual and (eh_garg_princ or eh_neg_dia):
                    cor_g_cel = T.DESPESA if eh_neg_dia else "#F59E0B"
                    borda_norm = borda(1.8, cor_g_cel)
                    ic_venc.append(
                        ft.Icon(
                            ft.Icons.WARNING_AMBER_ROUNDED if eh_neg_dia else ft.Icons.SHIELD_ROUNDED,
                            size=9.5 if mobile else 10.5,
                            color=cor_g_cel,
                        )
                    )

                rotulo_d = (
                    f"{dt_cel.day} {MESES_NOMES[dt_cel.month - 1][:3]}"
                    if (eh_multi_mes and (dt_cel.day == 1 or dt_iso == d_ini_ef))
                    else str(dt_cel.day)
                )

                cel = ft.Container(
                    expand=1,
                    height=54 if mobile else 68,
                    padding=pad(h=3 if mobile else 6, v=3 if mobile else 5),
                    bgcolor=bg_c,
                    border_radius=8,
                    border=borda_norm,
                    opacity=1.0 if ativo_visual else 0.34,
                    ink=True,
                    tooltip=_tooltip_dia(info_d, vencs_d),
                    on_click=lambda _, di=info_d, vf=vencs_d: _abrir_modal_dia_dash(di, vf),
                    content=ft.Column(
                        spacing=2,
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(
                                        rotulo_d,
                                        size=9.5 if (mobile and len(rotulo_d) > 2) else (10 if mobile else 11),
                                        weight=ft.FontWeight.BOLD if (eh_hoje or dt_cel.day == 1) else ft.FontWeight.W_500,
                                        color=T.WARNING if eh_hoje else (T.PRIMARY if (eh_multi_mes and dt_cel.day == 1) else (T.TEXT_PRIMARY if ativo_visual else f"{T.TEXT_MUTED}70")),
                                    ),
                                    ft.Row(spacing=1, tight=True, controls=ic_venc),
                                ],
                            ),
                            ft.Column(
                                spacing=1.5,
                                tight=True,
                                horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                                controls=pilulas,
                            ),
                        ],
                    ),
                )

                def _on_hov(e: ft.ControlEvent, c=cel, di=info_d, vf=vencs_d, bn=borda_norm):
                    try:
                        hov = str(e.data).lower() == "true" if e.data is not None else False
                        c.border = borda_hov if hov else bn
                        c.update()
                        if hov:
                            _atualizar_hover(di, vf)
                    except Exception:
                        pass

                cel.on_hover = _on_hov
                celulas.append(cel)

            if eh_multi_mes and mes_desta_sem and mes_desta_sem != mes_ant_sem:
                mes_ant_sem = mes_desta_sem
                linhas_sem_dash.append(
                    ft.Container(
                        padding=pad(h=8, v=3),
                        bgcolor=f"{T.PRIMARY}14",
                        border_radius=6,
                        border=borda(1, f"{T.PRIMARY}35"),
                        content=ft.Text(
                            f"📅 {MESES_NOMES[mes_desta_sem[1] - 1]} de {mes_desta_sem[0]}",
                            size=10.5,
                            weight=ft.FontWeight.BOLD,
                            color=T.PRIMARY,
                        ),
                    )
                )

            linhas_sem_dash.append(
                ft.Row(spacing=4 if mobile else 6, controls=celulas)
            )

        if eh_multi_mes or num_semanas > 6:
            col_grade_semanas.controls.append(
                ft.Container(
                    height=360 if mobile else 440,
                    content=ft.Column(
                        spacing=4 if mobile else 6,
                        scroll=ft.ScrollMode.AUTO,
                        controls=linhas_sem_dash,
                    ),
                )
            )
        else:
            col_grade_semanas.controls.extend(linhas_sem_dash)

    _render_grade()

    prot_fluxo = (pacote_cal or {}).get("protecao_fluxo") or {}
    sobra_proj_d = float(prot_fluxo.get("sobra_projetada", rec_mes - desp_mes) or 0.0)
    teto_seg_d = float(prot_fluxo.get("teto_seguro_gasto", max(0.0, sobra_proj_d)) or 0.0)
    sobra_falsa_d = float(prot_fluxo.get("sobra_falsa_travada", max(0.0, sobra_proj_d - teto_seg_d)) or 0.0)
    menor_saldo_d = float(prot_fluxo.get("menor_saldo_futuro", sobra_proj_d) or 0.0)
    dt_garg_d = prot_fluxo.get("data_gargalo")
    prox_dt_d = prot_fluxo.get("proxima_entrada_data")
    prox_val_d = float(prot_fluxo.get("proxima_entrada_valor", 0.0) or 0.0)
    tem_arm_d = bool(prot_fluxo.get("tem_armadilha_fluxo", False))
    fica_neg_d = bool(prot_fluxo.get("fica_negativo_no_meio", False))

    cor_prot_d = T.DESPESA if fica_neg_d else ("#F59E0B" if tem_arm_d else "#06B6D4")
    faixa_gargalo_dash = ft.Container(
        padding=pad(h=12, v=8),
        bgcolor=f"{cor_prot_d}12",
        border_radius=10,
        border=borda(1, f"{cor_prot_d}45"),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
            spacing=8,
            controls=[
                ft.Row(
                    spacing=6,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(
                            ft.Icons.WARNING_AMBER_ROUNDED if (fica_neg_d or tem_arm_d) else ft.Icons.SHIELD_ROUNDED,
                            color=cor_prot_d,
                            size=15,
                        ),
                        ft.Text(
                            (
                                f"🛡️ Teto Seguro Agora: {formatar_moeda(teto_seg_d)} "
                                f"(Pior dia: {formatar_moeda(menor_saldo_d)} em {formatar_data_br(dt_garg_d)[:5]})"
                            )
                            if dt_garg_d
                            else f"🛡️ Teto Seguro Agora: {formatar_moeda(teto_seg_d)}",
                            size=11.5,
                            weight=ft.FontWeight.BOLD,
                            color=T.TEXT_PRIMARY,
                        ),
                    ],
                ),
                ft.Row(
                    spacing=8,
                    wrap=True,
                    controls=[
                        ft.Text(
                            f"Sobra Mês: {formatar_moeda(sobra_proj_d)}",
                            size=11,
                            weight=ft.FontWeight.W_600,
                            color=T.PRIMARY,
                        ),
                        *(
                            [
                                ft.Text(
                                    f"🔒 Retido: {formatar_moeda(sobra_falsa_d)}",
                                    size=11,
                                    weight=ft.FontWeight.BOLD,
                                    color="#F59E0B",
                                )
                            ]
                            if sobra_falsa_d > 0.005
                            else []
                        ),
                        *(
                            [
                                ft.Text(
                                    f"Próx. Entrada: {formatar_moeda(prox_val_d)} ({formatar_data_br(prox_dt_d)[:5]})",
                                    size=11,
                                    weight=ft.FontWeight.W_600,
                                    color=T.RECEITA,
                                )
                            ]
                            if prox_dt_d and prox_val_d > 0
                            else []
                        ),
                    ],
                ),
            ],
        ),
    )

    return ft.Container(
        padding=pad(all_=14 if mobile else 18),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=12,
            controls=[
                # Cabeçalho do Card de Calendário no Dashboard
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                    spacing=8,
                    controls=[
                        ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    padding=pad(all_=8),
                                    border_radius=10,
                                    bgcolor=f"{T.PRIMARY}1F",
                                    content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=18),
                                ),
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Row(
                                            spacing=8,
                                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                            controls=[
                                                ft.Text(
                                                    "Calendário Financeiro",
                                                    size=15 if mobile else 16,
                                                    weight=ft.FontWeight.BOLD,
                                                    color=T.TEXT_PRIMARY,
                                                ),
                                                ft.Container(
                                                    padding=pad(h=8, v=2),
                                                    border_radius=8,
                                                    bgcolor=f"{T.PRIMARY}18",
                                                    content=ft.Text(nome_mes_cap, size=11, weight=ft.FontWeight.BOLD, color=T.PRIMARY),
                                                ),
                                            ],
                                        ),
                                        ft.Text(
                                            f"Saídas: {formatar_moeda(desp_mes)} ({dias_saida} dias) · Entradas: {formatar_moeda(rec_mes)}",
                                            size=11.5,
                                            color=T.TEXT_MUTED,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=8,
                            wrap=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                row_botoes_modo,
                                ft.TextButton(
                                    content=ft.Row(
                                        spacing=3,
                                        tight=True,
                                        controls=[
                                            ft.Text("Ver completo", size=12, weight=ft.FontWeight.W_600, color=T.PRIMARY),
                                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=15, color=T.PRIMARY),
                                        ],
                                    ),
                                    on_click=lambda _: navegar(page, "/calendario"),
                                ),
                            ],
                        ),
                    ],
                ),
                faixa_gargalo_dash,
                barra_hover,
                col_grade_semanas,
            ],
        ),
    )
