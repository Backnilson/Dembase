"""
=============================================================================
DemBase v3 — views/relatorios/fluxo_mensal_report.py  (Flet 1.0.1)
Relatório de Fluxo de Caixa Mensal e Evolução 6 Meses (/relatorios/fluxo-mensal).
Exibe:
- 4 KPIs Acumulados do Semestre (Receitas 6M, Despesas 6M, Saldo 6M, Taxa de Poupança)
- Painel Comparativo Interativo de 6 Meses: tocar em um mês filtra o extrato abaixo
- Evolução Diária + Categorias + Lista de Transações do período selecionado
=============================================================================
"""
from __future__ import annotations
import calendar
from datetime import date
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, formatar_data_br
from core.responsive import is_mobile
from core.periodo import obter_estado_periodo_atual, atualizar_datas_periodo_global
from core.report_context import ReportContext
from core.nav import ir_relatorio_fluxo, ir_relatorio_categoria
from views.shell_view import criar_shell, ROTA_RELATORIOS
from views.widgets.report import (
    criar_report_header,
    criar_kpi_strip,
    criar_filter_bar,
    criar_transaction_list,
    construir_card_evolucao_diaria,
    construir_card_ranking_categorias,
)
import services.supabase_client as db


def criar_view_fluxo_mensal(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    est_p = obter_estado_periodo_atual(page)
    contexto_inicial = ctx or ReportContext.from_query(page, None, match)
    contexto_atual: list[ReportContext] = [
        contexto_inicial.com(
            data_inicio=contexto_inicial.data_inicio or est_p["data_inicio"],
            data_fim=contexto_inicial.data_fim or est_p["data_fim"],
        )
    ]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=18, height=18, stroke_width=2.2, visible=False)

    container_header = ft.Container()
    container_kpis = ft.Container()
    container_semestral = ft.Container()
    container_graficos = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])
    container_filter_bar = ft.Container()
    container_lista = ft.Container()

    def _safe_update():
        try:
            page.update()
        except Exception:
            pass

    def _selecionar_mes_historico(mes_num: int, ano_num: int):
        if 1 <= mes_num <= 12 and ano_num >= 2000:
            d1 = date(ano_num, mes_num, 1)
            d2 = date(ano_num, mes_num, calendar.monthrange(ano_num, mes_num)[1])
            atualizar_datas_periodo_global(page, d1.isoformat(), d2.isoformat(), mes_num, ano_num)
            ir_relatorio_fluxo(
                page,
                contexto_atual[0].com(data_inicio=d1, data_fim=d2, pagina=1),
                replace=True,
            )

    def _aplicar_novo_contexto(novo_ctx: ReportContext):
        ir_relatorio_fluxo(page, novo_ctx, replace=True)

    def _ao_mudar_pagina(nova_pag: int):
        c = contexto_atual[0].com(pagina=nova_pag)
        contexto_atual[0] = c
        carregar(inicial=False)

    def _construir_painel_semestral(balanco_6m: list[dict], dt_ini_ativo: date, dt_fim_ativo: date) -> ft.Container:
        if not balanco_6m:
            return ft.Container(
                padding=pad(all_=20),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(),
                content=ft.Text("Histórico semestral ainda sem lançamentos registrados.", color=T.TEXT_MUTED, size=13),
            )

        max_val = max(
            [max(float(m.get("receitas", 0) or 0), float(m.get("despesas", 0) or 0)) for m in balanco_6m] + [1.0]
        )

        cards_meses = []
        for item in balanco_6m[-6:]:
            mm = int(item.get("mes", 0) or 0)
            aa = int(item.get("ano", 0) or 0)
            lbl = item.get("label") or f"{mm:02d}/{aa}"
            rec = float(item.get("receitas", 0) or 0)
            desp = float(item.get("despesas", 0) or 0)
            saldo = float(item.get("saldo", rec - desp) or 0)
            cor_s = T.RECEITA if saldo >= 0 else T.DESPESA

            selecionado = (
                dt_ini_ativo.month == mm
                and dt_ini_ativo.year == aa
                and dt_fim_ativo.month == mm
            )

            cards_meses.append(
                ft.Container(
                    col={"xs": 12, "sm": 6, "md": 4},
                    padding=pad(all_=14),
                    bgcolor=f"{T.PRIMARY}14" if selecionado else T.SURFACE_ALT,
                    border=borda(1.6 if selecionado else 1, T.PRIMARY if selecionado else T.BORDER),
                    border_radius=12,
                    on_click=lambda _, m_i=mm, a_i=aa: _selecionar_mes_historico(m_i, a_i),
                    ink=True,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=6,
                                        controls=[
                                            ft.Icon(
                                                ft.Icons.CALENDAR_MONTH_ROUNDED,
                                                color=T.PRIMARY if selecionado else T.TEXT_MUTED,
                                                size=15,
                                            ),
                                            ft.Text(lbl, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                    ft.Container(
                                        padding=pad(h=8, v=2),
                                        bgcolor=f"{cor_s}1F",
                                        border_radius=8,
                                        content=ft.Text(
                                            formatar_moeda(saldo),
                                            color=cor_s,
                                            size=11.5,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ),
                                ],
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(f"↑ {formatar_moeda(rec)}", color=T.RECEITA, size=11, weight=ft.FontWeight.W_600),
                                    ft.Text(f"↓ {formatar_moeda(desp)}", color=T.DESPESA, size=11, weight=ft.FontWeight.W_600),
                                ],
                            ),
                            ft.ProgressBar(
                                value=min(1.0, max(0.0, rec / max_val)),
                                color=T.RECEITA,
                                bgcolor=f"{T.BORDER}45",
                                height=4,
                                border_radius=2,
                            ),
                            ft.ProgressBar(
                                value=min(1.0, max(0.0, desp / max_val)),
                                color=T.DESPESA,
                                bgcolor=f"{T.BORDER}45",
                                height=4,
                                border_radius=2,
                            ),
                        ],
                    ),
                )
            )

        return ft.Container(
            padding=pad(all_=18),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(),
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=2,
                                controls=[
                                    ft.Text("Comparativo dos Últimos 6 Meses", color=T.TEXT_PRIMARY, size=14.5, weight=ft.FontWeight.BOLD),
                                    ft.Text("Toque em qualquer mês abaixo para inspecionar os lançamentos daquele ciclo", color=T.TEXT_MUTED, size=11),
                                ],
                            ),
                            ft.Icon(ft.Icons.STACKED_BAR_CHART_ROUNDED, color="#8B5CF6", size=20),
                        ],
                    ),
                    ft.Divider(height=1, color=T.BORDER),
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=cards_meses),
                ],
            ),
        )

    def carregar(inicial: bool = False):
        c = contexto_atual[0]
        di_str = c.data_inicio.isoformat()
        df_str = c.data_fim.isoformat()

        if not inicial:
            spinner.visible = True
            _safe_update()

        try:
            balanco_6m = db.obter_balanco_6_meses() or []
            pacote = db.obter_relatorio_lancamentos(
                data_inicio=di_str,
                data_fim=df_str,
                filtros=c.to_rpc_filtros(),
                incluir_transferencias=(c.tipo == "Transferencia"),
            )
            evolucao = pacote.get("evolucao_diaria") or []
            por_cat = pacote.get("por_categoria") or []
            itens = pacote.get("itens") or []
            total_reg = int(pacote.get("total_registros", len(itens)) or 0)

            rec_6m = sum(float(m.get("receitas", 0) or 0) for m in balanco_6m)
            desp_6m = sum(float(m.get("despesas", 0) or 0) for m in balanco_6m)
            saldo_6m = rec_6m - desp_6m
            taxa_poup_6m = ((saldo_6m / rec_6m) * 100.0) if rec_6m > 0 else 0.0

            # 1. Header
            container_header.content = criar_report_header(
                page,
                titulo="Fluxo de Caixa Mensal (6 Meses)",
                subtitulo=(
                    f"Período detalhado abaixo: {formatar_data_br(di_str)} a {formatar_data_br(df_str)} "
                    f"· {total_reg} lançamento{'s' if total_reg != 1 else ''}"
                ),
                icone=ft.Icons.STACKED_BAR_CHART_ROUNDED,
                cor_icone="#8B5CF6",
                breadcrumbs=[
                    ("Relatórios", "/relatorios"),
                    ("Fluxo Mensal", None),
                ],
                acoes_header=[spinner],
            )

            # 2. KPIs Acumulados 6 Meses
            container_kpis.content = criar_kpi_strip(
                page,
                [
                    {
                        "titulo": "Receitas Acumuladas (6M)",
                        "valor": formatar_moeda(rec_6m),
                        "subtitulo": "Soma dos últimos 6 meses",
                        "cor": T.RECEITA,
                        "icone": ft.Icons.ARROW_UPWARD_ROUNDED,
                    },
                    {
                        "titulo": "Despesas Acumuladas (6M)",
                        "valor": formatar_moeda(desp_6m),
                        "subtitulo": "Soma dos últimos 6 meses",
                        "cor": T.DESPESA,
                        "icone": ft.Icons.ARROW_DOWNWARD_ROUNDED,
                    },
                    {
                        "titulo": "Resultado Acumulado (6M)",
                        "valor": formatar_moeda(saldo_6m),
                        "subtitulo": "Superávit" if saldo_6m >= 0 else "Déficit no semestre",
                        "cor": T.RECEITA if saldo_6m >= 0 else T.DESPESA,
                        "icone": ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                    },
                    {
                        "titulo": "Taxa de Poupança Semestral",
                        "valor": f"{taxa_poup_6m:.1f}%",
                        "subtitulo": "Meta recomendada ≥ 20%",
                        "cor": T.RECEITA if taxa_poup_6m >= 20 else (T.WARNING if taxa_poup_6m >= 0 else T.DESPESA),
                        "icone": ft.Icons.SAVINGS_ROUNDED,
                    },
                ],
            )

            # 3. Painel Semestral Clicável
            container_semestral.content = _construir_painel_semestral(balanco_6m, c.data_inicio, c.data_fim)

            # 4. Gráficos do Período Ativo
            card_evolucao = construir_card_evolucao_diaria(
                evolucao,
                titulo="Fluxo Diário no Período Selecionado",
                subtitulo=f"De {formatar_data_br(di_str)} a {formatar_data_br(df_str)}",
                modo_saldo=False,
            )
            card_ranking = construir_card_ranking_categorias(
                por_cat,
                titulo="Top Categorias no Período",
                subtitulo="Toque em uma categoria para abrir seu diagnóstico",
                cor_padrao="#8B5CF6",
                on_categoria_click=lambda cid, _: ir_relatorio_categoria(
                    page,
                    cid,
                    ctx=c.com(categoria_id=cid, pagina=1),
                ),
            )
            container_graficos.controls = [card_evolucao, card_ranking]

            # 5. Barra de Filtros
            container_filter_bar.content = criar_filter_bar(
                page,
                ctx=c,
                on_change=_aplicar_novo_contexto,
                mostrar_chips_tipo=True,
                mostrar_filtro_conta=True,
                mostrar_filtro_cartao=True,
                mostrar_filtro_categoria=True,
                mostrar_filtro_regra=True,
                mostrar_filtro_forma=True,
            )

            # 6. Lista de Transações
            container_lista.content = criar_transaction_list(
                page,
                itens=itens,
                total_registros=total_reg,
                pagina_atual=c.pagina,
                page_size=c.page_size,
                on_page_change=_ao_mudar_pagina,
                on_refresh=lambda: carregar(inicial=False),
                mostrar_transferencias_padrao=(c.tipo == "Transferencia"),
                titulo_vazio="Nenhum lançamento neste período mensal",
                subtitulo_vazio="Toque em outro mês no painel acima ou altere o filtro de datas no topo.",
            )

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar fluxo mensal: {ex}", "erro")
        finally:
            spinner.visible = False
            if not inicial:
                _safe_update()

    def on_periodo(d_ini: str, d_fim: str, m: int, a: int):
        est = atualizar_datas_periodo_global(page, d_ini, d_fim, m, a)
        contexto_atual[0] = contexto_atual[0].com(
            data_inicio=est["data_inicio"],
            data_fim=est["data_fim"],
            pagina=1,
        )
        carregar(inicial=False)

    def on_mes_ano(m: int, a: int):
        est = obter_estado_periodo_atual(page)
        contexto_atual[0] = contexto_atual[0].com(
            data_inicio=est["data_inicio"],
            data_fim=est["data_fim"],
            pagina=1,
        )
        carregar(inicial=False)

    conteudo = ft.Column(
        spacing=14 if mobile else 16,
        controls=[
            container_header,
            container_kpis,
            container_semestral,
            container_graficos,
            container_filter_bar,
            container_lista,
            ft.Container(height=28),
        ],
    )

    carregar(inicial=True)

    url_rota = f"/relatorios/fluxo-mensal{contexto_atual[0].to_query()}"
    return criar_shell(
        page,
        rota_ativa=ROTA_RELATORIOS,
        conteudo=conteudo,
        rota_view=url_rota,
        titulo="Fluxo de Caixa Mensal",
        mostrar_voltar=True,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )


# Alias compatível com core/router.py
criar_view_relatorio_fluxo = criar_view_fluxo_mensal
