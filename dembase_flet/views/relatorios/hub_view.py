"""
=============================================================================
DemBase v3 — views/relatorios/hub_view.py  (Flet 1.0.1)
Central de Relatórios (/relatorios).
- Exibe os 4 KPIs consolidados do período (100% clicáveis)
- Renderiza dinamicamente o Catálogo de Relatórios (RELATORIOS_CATALOGO)
- Exibe painéis interativos de Categorias, Regra 50/30/20 e Balanço 6 Meses
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
from core.nav import (
    ir_contas,
    ir_cartoes,
    ir_relatorio_lancamentos,
    ir_relatorio_categoria,
    ir_relatorio_regra,
    ir_relatorio_fluxo,
)
from views.shell_view import criar_shell, ROTA_RELATORIOS
from views.widgets.clickable_card import clickable_card, kpi_clicavel
from views.relatorios.registry import RELATORIOS_CATALOGO
import services.supabase_client as db


def criar_view_hub_relatorios(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    est_p = obter_estado_periodo_atual(page)

    mes_sel = [est_p["mes"]]
    ano_sel = [est_p["ano"]]
    data_ini_sel = [est_p["data_inicio"].isoformat()]
    data_fim_sel = [est_p["data_fim"].isoformat()]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2.2, visible=False)

    txt_rec_mes       = ft.Text("R$ 0,00", color=T.RECEITA, size=18 if mobile else 20, weight=ft.FontWeight.BOLD)
    txt_desp_mes      = ft.Text("R$ 0,00", color=T.DESPESA, size=18 if mobile else 20, weight=ft.FontWeight.BOLD)
    txt_saldo_mes     = ft.Text("R$ 0,00", color=T.SALDO,   size=18 if mobile else 20, weight=ft.FontWeight.BOLD)
    txt_taxa_poupanca = ft.Text("0.0%",   color=T.PRIMARY, size=18 if mobile else 20, weight=ft.FontWeight.BOLD)
    txt_sub_periodo   = ft.Text(
        f"Período analisado: {formatar_data_br(data_ini_sel[0])} a {formatar_data_br(data_fim_sel[0])}",
        color=T.TEXT_MUTED,
        size=12,
    )

    col_categorias = ft.Column(spacing=8, controls=[])
    col_regra5030  = ft.Column(spacing=10, controls=[])
    col_balanco    = ft.Column(spacing=8, controls=[])

    def _safe_update():
        try:
            page.update()
        except Exception:
            pass

    def _acionar_card_catalogo(item_cat: dict):
        cid = item_cat["id"]
        if cid == "lancamentos_gerais":
            ir_relatorio_lancamentos(page, origem="relatorios")
        elif cid == "receitas_periodo":
            ir_relatorio_lancamentos(page, tipo="Receita", origem="relatorios")
        elif cid == "despesas_periodo":
            ir_relatorio_lancamentos(page, tipo="Despesa", origem="relatorios")
        elif cid == "extrato_contas":
            ir_contas(page)
        elif cid == "faturas_cartoes":
            ir_cartoes(page)
        elif cid in ("potes_financeiros", "regra_5030"):
            ir_relatorio_lancamentos(page, tipo="Despesa", origem="relatorios")
        elif cid == "fluxo_mensal":
            ir_relatorio_fluxo(page)
        else:
            ir_relatorio_lancamentos(page, origem="relatorios")

    # ── Catálogo Modular de Relatórios (Grid Clicável) ────────────────────────
    cards_catalogo = []
    for item in RELATORIOS_CATALOGO:
        cor_item = item["cor"]
        cards_catalogo.append(
            clickable_card(
                col=item.get("col", {"xs": 12, "sm": 6, "md": 4}),
                cor_hover=cor_item,
                padding=pad(all_=14 if mobile else 16),
                on_click=lambda _, it=item: _acionar_card_catalogo(it),
                content=ft.Row(
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            content=ft.Icon(item["icone"], color=cor_item, size=22),
                            bgcolor=f"{cor_item}1F",
                            border_radius=12,
                            padding=pad(all_=10),
                        ),
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text(
                                    item["titulo"],
                                    color=T.TEXT_PRIMARY,
                                    size=13.5,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    item["subtitulo"],
                                    color=T.TEXT_MUTED,
                                    size=11,
                                    max_lines=2,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                        ),
                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=cor_item, size=18),
                    ],
                ),
            )
        )

    grid_catalogo = ft.ResponsiveRow(spacing=12, run_spacing=12, controls=cards_catalogo)

    async def _carregar_async(
        d_ini: str | None = None,
        d_fim: str | None = None,
        mes: int | None = None,
        ano: int | None = None,
        inicial: bool = False,
    ):
        di = d_ini or data_ini_sel[0]
        df = d_fim or data_fim_sel[0]
        m = mes or mes_sel[0]
        a = ano or ano_sel[0]

        data_ini_sel[0] = di
        data_fim_sel[0] = df
        mes_sel[0] = m
        ano_sel[0] = a

        txt_sub_periodo.value = f"Período analisado: {formatar_data_br(di)} a {formatar_data_br(df)}"

        if not inicial:
            spinner.visible = True
            _safe_update()

        try:
            pacote = await db.obter_dashboard_periodo_async(di, df)
            overview = pacote.get("overview") if isinstance(pacote, dict) else None
            if not overview:
                overview = await db.obter_overview_dashboard_async(m, a, data_inicio=di, data_fim=df)

            rec  = float(overview.get("receitas", 0) or 0)
            desp = float(overview.get("despesas", 0) or 0)
            saldo = rec - desp
            taxa_poup = ((saldo / rec) * 100) if rec > 0 else 0.0

            txt_rec_mes.value       = formatar_moeda(rec)
            txt_desp_mes.value      = formatar_moeda(desp)
            txt_saldo_mes.value     = formatar_moeda(saldo)
            txt_saldo_mes.color     = T.RECEITA if saldo >= 0 else T.DESPESA
            txt_taxa_poupanca.value = f"{taxa_poup:.1f}%"
            txt_taxa_poupanca.color = T.RECEITA if taxa_poup >= 20 else (T.WARNING if taxa_poup >= 0 else T.DESPESA)

            bloco_cat = (
                pacote.get("despesas_por_categoria")
                if isinstance(pacote, dict) and "despesas_por_categoria" in pacote
                else await db.obter_despesas_por_categoria_async(m, a, data_inicio=di, data_fim=df)
            )
            _popular_categorias(bloco_cat, desp)

            resumo_potes = await db.obter_resumo_potes_async(di, df)
            _popular_potes(resumo_potes)

            dados_bal = await db.obter_balanco_6_meses_async()
            _popular_balanco_semestral(dados_bal)

            secao_analitica_loading.visible = False
            secao_analitica_conteudo.visible = True

        except Exception as ex:
            secao_analitica_loading.visible = False
            secao_analitica_conteudo.visible = True
            if not inicial:
                mostrar_feedback(page, f"Erro ao atualizar relatórios: {ex}", "erro")
        finally:
            spinner.visible = False
            _safe_update()

    def carregar(
        d_ini: str | None = None,
        d_fim: str | None = None,
        mes: int | None = None,
        ano: int | None = None,
        inicial: bool = False,
    ):
        try:
            page.run_task(_carregar_async, d_ini, d_fim, mes, ano, inicial)
        except Exception:
            import asyncio
            asyncio.create_task(_carregar_async(d_ini, d_fim, mes, ano, inicial))

    def _popular_categorias(dados_cat: dict | list, total_desp: float):
        col_categorias.controls.clear()
        lista = dados_cat.get("categorias", []) if isinstance(dados_cat, dict) else (dados_cat or [])
        if not lista:
            col_categorias.controls.append(
                ft.Container(
                    padding=pad(all_=20),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("Nenhuma despesa registrada neste período.", color=T.TEXT_MUTED, size=12.5),
                )
            )
            return

        for item in lista[:8]:
            cid = item.get("categoria_id") or item.get("id")
            nome_cat = item.get("categoria") or item.get("nome", "Outros")
            total_cat = float(item.get("valor") or item.get("total") or 0)
            cor_cat   = item.get("cor") or T.PRIMARY
            perc = (total_cat / total_desp) if total_desp > 0 else 0.0
            progresso = min(1.0, max(0.0, perc))

            def _abrir_cat(_=None, cat_id=cid):
                if cat_id:
                    ctx_cat = ReportContext.from_query(page).com(
                        tipo="Despesa",
                        categoria_id=str(cat_id),
                        origem="relatorios",
                    )
                    ir_relatorio_categoria(page, str(cat_id), ctx_cat)
                else:
                    ir_relatorio_lancamentos(page, tipo="Despesa", origem="relatorios")

            col_categorias.controls.append(
                ft.Container(
                    padding=pad(h=12, v=8),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=10,
                    on_click=_abrir_cat,
                    ink=True,
                    content=ft.Column(
                        spacing=5,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Container(width=10, height=10, bgcolor=cor_cat, border_radius=5),
                                            ft.Text(nome_cat, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Text(f"{perc * 100:.1f}%", color=T.TEXT_MUTED, size=11.5),
                                            ft.Text(formatar_moeda(total_cat), color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=15),
                                        ],
                                    ),
                                ],
                            ),
                            ft.ProgressBar(value=progresso, color=cor_cat, bgcolor=f"{T.BORDER}50", height=5, border_radius=3),
                        ],
                    ),
                )
            )

    def _popular_potes(resumo_dados: dict | None = None, di: str | None = None, df: str | None = None):
        col_regra5030.controls.clear()
        try:
            resumo = resumo_dados if isinstance(resumo_dados, dict) else db.obter_resumo_potes(di or data_ini_sel[0], df or data_fim_sel[0])
            potes = resumo.get("potes") or []
            if not potes:
                col_regra5030.controls.append(
                    ft.Text("Nenhum pote configurado.", color=T.TEXT_MUTED, size=12.5)
                )
                return

            for p in potes:
                nome = p.get("nome", "Pote")
                cor = p.get("cor") or T.PRIMARY
                gasto = float(p.get("gasto", 0) or 0)
                previsto = float(p.get("previsto", 0) or 0)
                pid = p.get("id")
                pct_meta = float(p.get("percentual", 0) or 0)
                progresso = min(1.0, max(0.0, gasto / previsto)) if previsto > 0 else (1.0 if gasto > 0 else 0.0)

                col_regra5030.controls.append(
                    ft.Container(
                        padding=pad(h=12, v=10),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=12,
                        on_click=(lambda _, pt_id=pid: ir_relatorio_lancamentos(page, tipo="Despesa", pote=pt_id, origem="relatorios")) if pid else None,
                        ink=bool(pid),
                        tooltip=f"Ver lançamentos do pote {nome}",
                        content=ft.Column(
                            spacing=5,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row(
                                            spacing=8,
                                            controls=[
                                                ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                                                ft.Text(f"{nome} ({pct_meta:.0f}%)", color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                                            ],
                                        ),
                                        ft.Row(
                                            spacing=4,
                                            controls=[
                                                ft.Text(formatar_moeda(gasto), color=cor, size=12, weight=ft.FontWeight.BOLD),
                                                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=16),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.ProgressBar(value=progresso, color=cor, bgcolor=f"{T.BORDER}50", height=5, border_radius=3),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"Gasto: {formatar_moeda(gasto)}", color=T.TEXT_MUTED, size=10.5),
                                        ft.Text(f"Previsto: {formatar_moeda(previsto)}", color=T.TEXT_MUTED, size=10.5),
                                    ],
                                ),
                            ],
                        ),
                    )
                )
        except Exception:
            col_regra5030.controls.append(
                ft.Text("Potes financeiros indisponíveis no momento.", color=T.TEXT_MUTED, size=12.5)
            )

    def _popular_balanco_semestral(dados_bal: list | None = None):
        col_balanco.controls.clear()
        try:
            itens_bal = dados_bal if isinstance(dados_bal, list) else db.obter_balanco_6_meses()
            if not itens_bal:
                col_balanco.controls.append(
                    ft.Text("Sem histórico de 6 meses no momento.", color=T.TEXT_MUTED, size=12.5)
                )
                return

            for item in dados_bal:
                mm = int(item.get("mes", 0) or 0)
                aa = int(item.get("ano", 0) or 0)
                label_mes = item.get("label") or f"{mm:02d}/{aa}"
                r = float(item.get("receitas", 0) or 0)
                d = float(item.get("despesas", 0) or 0)
                s = float(item.get("saldo", r - d) or 0)

                maior_valor = max(r, d, 1.0)
                prop_rec  = min(1.0, r / maior_valor)
                prop_desp = min(1.0, d / maior_valor)

                def _abrir_mes(_=None, mes_i=mm, ano_i=aa):
                    if 1 <= mes_i <= 12 and ano_i >= 2000:
                        d1 = date(ano_i, mes_i, 1)
                        d2 = date(ano_i, mes_i, calendar.monthrange(ano_i, mes_i)[1])
                        ir_relatorio_lancamentos(
                            page,
                            ctx=ReportContext(data_inicio=d1, data_fim=d2, origem="relatorios"),
                        )
                    else:
                        ir_relatorio_fluxo(page)

                col_balanco.controls.append(
                    ft.Container(
                        padding=pad(all_=12),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=10,
                        on_click=_abrir_mes,
                        ink=True,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Row(
                                            spacing=4,
                                            controls=[
                                                ft.Text(label_mes, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                                                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=15),
                                            ],
                                        ),
                                        ft.Text(
                                            f"Saldo: {formatar_moeda(s)}",
                                            color=T.RECEITA if s >= 0 else T.DESPESA,
                                            size=12.5,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text("Receitas", size=11, color=T.TEXT_MUTED, width=62),
                                        ft.ProgressBar(value=prop_rec, color=T.RECEITA, bgcolor=f"{T.BORDER}50", height=5, expand=True),
                                        ft.Text(formatar_moeda(r), size=11, color=T.RECEITA, width=90, text_align=ft.TextAlign.RIGHT),
                                    ],
                                ),
                                ft.Row(
                                    spacing=8,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Text("Despesas", size=11, color=T.TEXT_MUTED, width=62),
                                        ft.ProgressBar(value=prop_desp, color=T.DESPESA, bgcolor=f"{T.BORDER}50", height=5, expand=True),
                                        ft.Text(formatar_moeda(d), size=11, color=T.DESPESA, width=90, text_align=ft.TextAlign.RIGHT),
                                    ],
                                ),
                            ],
                        ),
                    )
                )
        except Exception:
            col_balanco.controls.append(
                ft.Text("Sem histórico de 6 meses no momento.", color=T.TEXT_MUTED, size=12.5)
            )

    # ── KPIs Topo Clicáveis ───────────────────────────────────────────────────
    kpis_topo = ft.ResponsiveRow(
        spacing=12, run_spacing=12,
        controls=[
            kpi_clicavel(
                titulo="Receitas no Período",
                valor_control=txt_rec_mes,
                subtitulo="Abrir extrato de receitas",
                icone=ft.Icons.ARROW_UPWARD_ROUNDED,
                cor=T.RECEITA,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Receita", origem="relatorios"),
            ),
            kpi_clicavel(
                titulo="Despesas no Período",
                valor_control=txt_desp_mes,
                subtitulo="Abrir extrato de despesas",
                icone=ft.Icons.ARROW_DOWNWARD_ROUNDED,
                cor=T.DESPESA,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Despesa", origem="relatorios"),
            ),
            kpi_clicavel(
                titulo="Resultado Líquido",
                valor_control=txt_saldo_mes,
                subtitulo="Abrir extrato completo",
                icone=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                cor=T.SALDO,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, origem="relatorios"),
            ),
            kpi_clicavel(
                titulo="Taxa de Poupança",
                valor_control=txt_taxa_poupanca,
                subtitulo="Analisar pilar de Investimentos",
                icone=ft.Icons.SAVINGS_ROUNDED,
                cor=T.PRIMARY,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_regra(page, "Investimento"),
            ),
        ],
    )

    # ── Painéis Analíticos Clicáveis ──────────────────────────────────────────
    secao_cat = ft.Container(
        col={"xs": 12, "md": 6},
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
                        ft.Text("Despesas por Categoria", color=T.TEXT_PRIMARY, size=14.5, weight=ft.FontWeight.BOLD),
                        ft.TextButton(
                            content=ft.Text("Ver todas →", color=T.PRIMARY, size=11.5, weight=ft.FontWeight.W_600),
                            on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Despesa", origem="relatorios"),
                        ),
                    ],
                ),
                ft.Divider(color=T.BORDER, height=1),
                col_categorias,
            ],
        ),
    )

    secao_regra = ft.Container(
        col={"xs": 12, "md": 6},
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
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.ALL_INBOX_ROUNDED, color="#6C5CE7", size=18),
                                ft.Text("6 Potes Financeiros", color=T.TEXT_PRIMARY, size=14.5, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        ft.TextButton(
                            content=ft.Text("Ver despesas →", color=T.PRIMARY, size=11.5, weight=ft.FontWeight.W_600),
                            on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Despesa", origem="relatorios"),
                        ),
                    ],
                ),
                ft.Divider(color=T.BORDER, height=1),
                col_regra5030,
            ],
        ),
    )

    secao_balanco = ft.Container(
        col={"xs": 12},
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
                        ft.Text("Balanço dos Últimos 6 Meses", color=T.TEXT_PRIMARY, size=14.5, weight=ft.FontWeight.BOLD),
                        ft.TextButton(
                            content=ft.Text("Ver relatório mensal →", color=T.PRIMARY, size=11.5, weight=ft.FontWeight.W_600),
                            on_click=lambda _: ir_relatorio_fluxo(page),
                        ),
                    ],
                ),
                ft.Divider(color=T.BORDER, height=1),
                col_balanco,
            ],
        ),
    )

    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=2,
                expand=True,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Text(
                                "Central de Relatórios",
                                color=T.TEXT_PRIMARY,
                                size=20 if mobile else 24,
                                weight=ft.FontWeight.BOLD,
                            ),
                            spinner,
                        ],
                    ),
                    txt_sub_periodo,
                ],
            ),
            ft.FilledButton(
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, color=ft.Colors.WHITE, size=16),
                        ft.Text(
                            "Extrato Geral",
                            color=ft.Colors.WHITE,
                            size=12.5,
                            weight=ft.FontWeight.W_600,
                        ),
                    ],
                ),
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=pad(h=14, v=10),
                ),
                on_click=lambda _: ir_relatorio_lancamentos(page, origem="relatorios"),
            ),
        ],
    )

    def on_periodo(d_ini: str, d_fim: str, m: int, a: int):
        atualizar_datas_periodo_global(page, d_ini, d_fim, m, a)
        carregar(d_ini=d_ini, d_fim=d_fim, mes=m, ano=a, inicial=False)

    def on_mes_ano(m: int, a: int):
        est = obter_estado_periodo_atual(page)
        carregar(
            d_ini=est["data_inicio"].isoformat(),
            d_fim=est["data_fim"].isoformat(),
            mes=m,
            ano=a,
            inicial=False,
        )

    secao_analitica_loading = ft.Container(
        alignment=ft.Alignment(0, 0),
        padding=pad(all_=50),
        content=ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=T.PRIMARY, width=32, height=32, stroke_width=3),
                ft.Text("Carregando indicadores financeiros...", color=T.TEXT_MUTED, size=13, weight=ft.FontWeight.W_500),
            ],
        ),
        visible=True,
    )

    secao_analitica_conteudo = ft.Column(
        spacing=16,
        visible=False,
        controls=[
            kpis_topo,
            ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[secao_cat, secao_regra]),
            secao_balanco,
        ],
    )

    conteudo = ft.Column(
        spacing=16,
        controls=[
            cabecalho,
            ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.GRID_VIEW_ROUNDED, color=T.PRIMARY, size=16),
                            ft.Text("Relatórios Especializados", color=T.TEXT_PRIMARY, size=14.5, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                    grid_catalogo,
                ],
            ),
            secao_analitica_loading,
            secao_analitica_conteudo,
            ft.Container(height=28),
        ],
    )

    carregar(inicial=True)

    return criar_shell(
        page,
        rota_ativa=ROTA_RELATORIOS,
        conteudo=conteudo,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
