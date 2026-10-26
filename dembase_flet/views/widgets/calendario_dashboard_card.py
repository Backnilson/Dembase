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

    nome_mes_cap = (
        f"{formatar_data_br(d_ini_ef)} a {formatar_data_br(d_fim_ef)}"
        if eh_parcial
        else f"{MESES_NOMES[m - 1]} {a}"
    )

    modo_cal = ["completo"]  # "completo" ou "saidas"

    kpis_m = (pacote_cal or {}).get("kpis") or {}
    dias_lista = (pacote_cal or {}).get("dias") or []
    faturas_lista = (pacote_cal or {}).get("cartoes_faturas") or []

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
            if d_item.get("no_mes_atual"):
                maior_entrada = max(maior_entrada, float(d_item.get("total_receitas", 0) or 0))

    mapa_vencimentos: dict[str, list[dict]] = {}
    for fat in faturas_lista:
        dv_str = str(fat.get("data_vencimento") or "")[:10]
        if dv_str:
            mapa_vencimentos.setdefault(dv_str, []).append(fat)

    txt_hover_info = ft.Text(
        "Passe o mouse ou toque em um dia para destrinchar receitas, despesas e cartão",
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

    def _atualizar_hover(dia_info: dict, vencs: list[dict]):
        dt_s = str(dia_info.get("data") or "")
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        saldo_d = rec_d - desp_d
        qtd_d = int(dia_info.get("qtd_lancamentos", 0) or 0)

        txt_hover_info.value = f"📅 {formatar_data_br(dt_s)} ({qtd_d} mov.)"
        txt_hover_info.color = T.TEXT_PRIMARY
        row_hover_chips.controls = [
            ft.Text(f"Receita: {formatar_moeda(rec_d)}", size=11, weight=ft.FontWeight.BOLD, color=T.RECEITA),
            ft.Text(f"Conta: {formatar_moeda(desp_cta)}", size=11, weight=ft.FontWeight.BOLD, color=T.DESPESA),
            ft.Text(f"Cartão: {formatar_moeda(desp_crt)}", size=11, weight=ft.FontWeight.BOLD, color=T.WARNING),
            ft.Text(
                f"Saldo: {formatar_moeda(saldo_d)}",
                size=11,
                weight=ft.FontWeight.BOLD,
                color=T.RECEITA if saldo_d >= 0 else T.DESPESA,
            ),
        ]
        try:
            barra_hover.update()
        except Exception:
            pass

    def _tooltip_dia(dia_info: dict, vencs: list[dict]) -> str:
        dt_s = str(dia_info.get("data") or "")
        rec_d = float(dia_info.get("total_receitas", 0) or 0)
        desp_d = float(dia_info.get("total_despesas", 0) or 0)
        desp_cta = float(dia_info.get("despesas_conta", 0) or 0)
        desp_crt = float(dia_info.get("despesas_cartao", 0) or 0)
        saldo_d = rec_d - desp_d
        linhas = [
            f"📅 {formatar_data_br(dt_s)}",
            f"🟢 Receita: {formatar_moeda(rec_d)}",
            f"🔴 Despesa Total: {formatar_moeda(desp_d)} (Conta: {formatar_moeda(desp_cta)} | Cartão: {formatar_moeda(desp_crt)})",
            f"⚖️ Saldo do Dia: {formatar_moeda(saldo_d)}",
        ]
        for vf in vencs:
            linhas.append(f"💳 Vencimento {vf.get('cartao_nome')}: {formatar_moeda(float(vf.get('valor_total', 0) or 0))}")
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
                itens_m.append(
                    ft.Container(
                        padding=pad(h=10, v=8),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=8,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        ft.Text(l_it.get("descricao") or cat_n, size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ft.Text(f"{cat_n} · {origem_n}".strip(" ·"), size=10.5, color=T.TEXT_MUTED),
                                    ],
                                ),
                                ft.Text(f"{sinal_l} {formatar_moeda(val_l)}", size=12.5, weight=ft.FontWeight.BOLD, color=cor_l),
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
        offset_dom = (primeiro_dia_mes.weekday() + 1) % 7
        grid_inicio = primeiro_dia_mes - timedelta(days=offset_dom)

        for sem in range(6):
            celulas: list[ft.Control] = []
            for d_idx in range(7):
                dt_cel = grid_inicio + timedelta(days=sem * 7 + d_idx)
                dt_iso = dt_cel.isoformat()
                no_mes = (dt_cel.month == m and dt_cel.year == a)
                no_periodo = (d_ini_ef <= dt_iso <= d_fim_ef)
                ativo_visual = no_periodo if eh_parcial else no_mes
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
                        bd_c = f"{T.PRIMARY}55" if (eh_parcial and ativo_visual) else T.BORDER

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

                ic_venc = [
                    ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, size=10 if mobile else 11, color=T.WARNING)
                ] if vencs_d else []

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
                                        str(dt_cel.day),
                                        size=10 if mobile else 11,
                                        weight=ft.FontWeight.BOLD if eh_hoje else ft.FontWeight.W_500,
                                        color=T.WARNING if eh_hoje else (T.TEXT_PRIMARY if ativo_visual else f"{T.TEXT_MUTED}70"),
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

            col_grade_semanas.controls.append(
                ft.Row(spacing=4 if mobile else 6, controls=celulas)
            )

    _render_grade()

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
                barra_hover,
                col_grade_semanas,
            ],
        ),
    )
