"""
=============================================================================
DemBase v3 — views/dashboard_view.py  (Flet 1.0.1)
Dashboard Principal Multiplataforma (Mobile-First PWA + Desktop).
- Filtro Global de Período Flexível no Topo (tempo real, zero reload)
- KPIs 100% Clicáveis em Grid 2x2 no Mobile (xs=6) e 1x4 no Desktop (md=3)
- Grid Modular de Gráficos Dinâmicos e Drill-down Interativo
=============================================================================
"""
from __future__ import annotations
import random
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import FRASES_MOTIVACIONAIS, formatar_moeda, formatar_data_br
from core.responsive import is_mobile
from core.router import navegar
from core.nav import (
    ir_contas,
    ir_cartoes,
    ir_hub_relatorios,
    ir_relatorio_lancamentos,
)
from core.report_context import ReportContext
from core import storage
from views.widgets.clickable_card import kpi_clicavel
from views.widgets.dashboard_charts import (
    DASHBOARD_CHARTS_CATALOG,
    GRAFICOS_PADRAO_IDS,
    construir_grid_graficos,
)
from views.widgets.lancamento_sheet import abrir_lancamento
from views.shell_view import criar_shell, ROTA_DASHBOARD, obter_estado_periodo_atual
import services.supabase_client as db


def criar_view_dashboard(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    estado_inicial = obter_estado_periodo_atual(page)

    data_ini_sel = [estado_inicial["data_inicio"].isoformat()]
    data_fim_sel = [estado_inicial["data_fim"].isoformat()]
    mes_sel      = [estado_inicial["mes"]]
    ano_sel      = [estado_inicial["ano"]]

    frase = random.choice(FRASES_MOTIVACIONAIS)

    # ── Perfil ────────────────────────────────────────────────────────────────
    try:
        perfil = db.ler_perfil()
        nome = perfil["nome"].split()[0] if perfil and perfil.get("nome") else "Usuário"
    except Exception:
        nome = "Usuário"

    # ── Referências mutáveis para KPIs ────────────────────────────────────────
    tam_fonte_kpi = 17 if mobile else 21
    txt_saldo_contas = ft.Text("R$ 0,00", color=T.PRIMARY, size=tam_fonte_kpi, weight=ft.FontWeight.BOLD)
    txt_receitas     = ft.Text("R$ 0,00", color=T.RECEITA, size=tam_fonte_kpi, weight=ft.FontWeight.BOLD)
    txt_despesas     = ft.Text("R$ 0,00", color=T.DESPESA, size=tam_fonte_kpi, weight=ft.FontWeight.BOLD)
    txt_faturas      = ft.Text("R$ 0,00", color=T.WARNING, size=tam_fonte_kpi, weight=ft.FontWeight.BOLD)
    txt_sub_periodo  = ft.Text(
        f"Período: {formatar_data_br(data_ini_sel[0])} a {formatar_data_br(data_fim_sel[0])}",
        color=T.TEXT_MUTED,
        size=11.5,
    )

    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2.2, visible=False)
    grid_graficos = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])

    # Cache do último pacote de dados para re-renderizar instantaneamente ao ligar/desligar gráficos
    ultimo_pacote: dict = {}

    def _renderizar_graficos_atuais():
        ids_ativos = storage.obter_graficos_dashboard_memoria(page, GRAFICOS_PADRAO_IDS)
        grid_graficos.controls = construir_grid_graficos(page, ultimo_pacote, ids_ativos)

    # ── Loader em Tempo Real (In-Place) ───────────────────────────────────────
    def carregar(
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

        txt_sub_periodo.value = f"Período: {formatar_data_br(di)} a {formatar_data_br(df)}"

        if not inicial:
            spinner.visible = True
            try:
                page.update()
            except Exception:
                pass

        try:
            # 1. Pacote consolidado do período (overview, categorias com ID, frequência, modalidades)
            pacote_periodo = db.obter_dashboard_periodo(di, df)
            overview = pacote_periodo.get("overview") if isinstance(pacote_periodo, dict) else None
            if not overview:
                overview = db.obter_overview_dashboard(m, a, data_inicio=di, data_fim=df)

            rec = float(overview.get("receitas", 0) or 0)
            desp = float(overview.get("despesas", 0) or 0)
            saldo_c = float(overview.get("saldo_contas", 0) or 0)
            faturas_ab = float(overview.get("total_faturas", 0) or 0)

            txt_saldo_contas.value = formatar_moeda(saldo_c)
            txt_receitas.value     = formatar_moeda(rec)
            txt_despesas.value     = formatar_moeda(desp)
            txt_faturas.value      = formatar_moeda(faturas_ab)

            # 2. Dados complementares para os gráficos
            dados_5030 = db.obter_resumo_5030(di, df)
            balanco_6m = db.obter_balanco_6_meses()
            resumo_cartoes = db.obter_resumo_cartoes(m, a)

            ultimo_pacote.clear()
            ultimo_pacote.update({
                "data_inicio": di,
                "data_fim": df,
                "overview": overview,
                "regra_5030": dados_5030,
                "despesas_por_categoria": (
                    pacote_periodo.get("despesas_por_categoria")
                    if isinstance(pacote_periodo, dict) and "despesas_por_categoria" in pacote_periodo
                    else db.obter_despesas_por_categoria(m, a, data_inicio=di, data_fim=df)
                ),
                "receitas_por_categoria": (
                    pacote_periodo.get("receitas_por_categoria")
                    if isinstance(pacote_periodo, dict) and "receitas_por_categoria" in pacote_periodo
                    else db.obter_receitas_por_categoria(m, a, data_inicio=di, data_fim=df)
                ),
                "frequencia_diaria": (
                    pacote_periodo.get("frequencia_diaria")
                    if isinstance(pacote_periodo, dict) and "frequencia_diaria" in pacote_periodo
                    else db.obter_frequencia_gastos(m, a, data_inicio=di, data_fim=df)
                ),
                "despesas_por_forma": (
                    pacote_periodo.get("despesas_por_forma")
                    if isinstance(pacote_periodo, dict)
                    else []
                ),
                "balanco_6_meses": balanco_6m,
                "resumo_cartoes": resumo_cartoes,
            })

            _renderizar_graficos_atuais()

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao atualizar dashboard: {ex}", "erro")
        finally:
            spinner.visible = False
            if not inicial:
                try:
                    page.update()
                except Exception:
                    pass

    # ── Callbacks do Filtro Global do Shell ───────────────────────────────────
    def on_periodo(d_ini: str, d_fim: str, m: int, a: int):
        carregar(d_ini=d_ini, d_fim=d_fim, mes=m, ano=a, inicial=False)

    def on_mes_ano(m: int, a: int):
        carregar(mes=m, ano=a, inicial=False)

    # ── Modal Rápido de Escolha de Gráficos (também disponível em Configurações)
    def _abrir_seletor_graficos(_=None):
        ativos_atuais = set(storage.obter_graficos_dashboard_memoria(page, GRAFICOS_PADRAO_IDS))
        switches_map: dict[str, ft.Switch] = {}

        linhas_opcoes = []
        for item in DASHBOARD_CHARTS_CATALOG:
            cid = item["id"]
            sw = ft.Switch(
                value=(cid in ativos_atuais),
                active_color=T.PRIMARY,
            )
            switches_map[cid] = sw
            linhas_opcoes.append(
                ft.Container(
                    padding=pad(h=12, v=8),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=12,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=10,
                                expand=True,
                                controls=[
                                    ft.Icon(item["icone"], color=item["cor"], size=18),
                                    ft.Column(
                                        spacing=1,
                                        expand=True,
                                        controls=[
                                            ft.Text(item["titulo"].strip(), color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                                            ft.Text(item["subtitulo"], color=T.TEXT_MUTED, size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                        ],
                                    ),
                                ],
                            ),
                            sw,
                        ],
                    ),
                )
            )

        def _salvar_escolha(_):
            selecionados = [
                item["id"]
                for item in DASHBOARD_CHARTS_CATALOG
                if switches_map[item["id"]].value
            ]
            if not selecionados:
                mostrar_feedback(page, "Mantenha pelo menos 1 gráfico visível.", "alerta")
                return
            storage.salvar_graficos_dashboard_sync(page, selecionados)
            page.pop_dialog()
            _renderizar_graficos_atuais()
            page.update()

        dlg_graf = ft.AlertDialog(
            modal=False,
            bgcolor=T.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=18),
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.DASHBOARD_CUSTOMIZE_ROUNDED, color=T.PRIMARY, size=20),
                            ft.Text("Gráficos Visíveis", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CLOSE_ROUNDED,
                        icon_color=T.TEXT_MUTED,
                        icon_size=18,
                        on_click=lambda _: page.pop_dialog(),
                    ),
                ],
            ),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    tight=True,
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    controls=linhas_opcoes,
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: page.pop_dialog()),
                ft.FilledButton(
                    content=ft.Text("Salvar Layout", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    style=ft.ButtonStyle(
                        bgcolor=T.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                    on_click=_salvar_escolha,
                ),
            ],
        )
        page.show_dialog(dlg_graf)

    # =========================================================================
    # KPI CARDS CLICÁVEIS — Grid 2x2 no Mobile (xs=6) e 1x4 no Desktop (md=3)
    # =========================================================================
    kpis = ft.ResponsiveRow(
        spacing=10 if mobile else 14,
        run_spacing=10 if mobile else 14,
        controls=[
            kpi_clicavel(
                titulo="Saldo em Conta",
                valor_control=txt_saldo_contas,
                subtitulo="Ver contas e saldos",
                icone=ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                cor=T.PRIMARY,
                compacto=mobile,
                on_click=lambda _: ir_contas(page),
            ),
            kpi_clicavel(
                titulo="Receitas",
                valor_control=txt_receitas,
                subtitulo="Ver receitas do período",
                icone=ft.Icons.ARROW_UPWARD_ROUNDED,
                cor=T.RECEITA,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Receita", origem="dashboard"),
            ),
            kpi_clicavel(
                titulo="Despesas",
                valor_control=txt_despesas,
                subtitulo="Ver despesas do período",
                icone=ft.Icons.ARROW_DOWNWARD_ROUNDED,
                cor=T.DESPESA,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Despesa", origem="dashboard"),
            ),
            kpi_clicavel(
                titulo="Faturas Abertas",
                valor_control=txt_faturas,
                subtitulo="Ver cartões e faturas",
                icone=ft.Icons.CREDIT_CARD_ROUNDED,
                cor=T.WARNING,
                compacto=mobile,
                on_click=lambda _: ir_cartoes(page),
            ),
        ],
    )

    # =========================================================================
    # BOAS-VINDAS + SUBTÍTULO DO PERÍODO + PERSONALIZAR GRÁFICOS
    # =========================================================================
    boas_vindas = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=3,
                expand=True,
                controls=[
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                f"Olá, {nome}! 👋",
                                color=T.TEXT_PRIMARY,
                                size=20 if mobile else 24,
                                weight=ft.FontWeight.BOLD,
                            ),
                            spinner,
                        ],
                    ),
                    txt_sub_periodo,
                    ft.Text(
                        f'"{frase}"',
                        color=T.TEXT_MUTED,
                        size=11.5,
                        italic=True,
                        max_lines=1 if mobile else 2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                ],
            ),
            ft.IconButton(
                icon=ft.Icons.DASHBOARD_CUSTOMIZE_ROUNDED,
                icon_color=T.PRIMARY,
                bgcolor=f"{T.PRIMARY}18",
                tooltip="Escolher gráficos visíveis",
                on_click=_abrir_seletor_graficos,
            ),
        ],
    )

    # =========================================================================
    # CABEÇALHO DA SEÇÃO DE GRÁFICOS
    # =========================================================================
    barra_titulo_graficos = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color=T.PRIMARY, size=18),
                    ft.Text(
                        "Análise Visual do Período",
                        color=T.TEXT_PRIMARY,
                        size=15,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
            ft.Row(
                spacing=4,
                controls=[
                    ft.TextButton(
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ASSESSMENT_ROUNDED, color=T.TEXT_MUTED, size=14),
                                ft.Text("Central de Relatórios", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                            ],
                        ),
                        on_click=lambda _: ir_hub_relatorios(page),
                    ),
                    ft.TextButton(
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.TUNE_ROUNDED, color=T.PRIMARY, size=14),
                                ft.Text("Configurar Gráficos", color=T.PRIMARY, size=12, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        on_click=_abrir_seletor_graficos,
                    ),
                ],
            ),
        ],
    )

    # =========================================================================
    # AÇÕES RÁPIDAS (Apenas no Desktop — no Mobile já estão na BottomAppBar/FAB)
    # =========================================================================
    acoes_desktop = ft.Container(
        visible=not mobile,
        padding=pad(all_=20),
        bgcolor=T.SURFACE,
        border_radius=14,
        border=borda(),
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Text("Ações Rápidas", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                ft.Container(height=14),
                ft.ResponsiveRow(
                    spacing=10,
                    run_spacing=10,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "sm": 4},
                            content=ft.FilledButton(
                                content=ft.Row(
                                    spacing=6,
                                    tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=T.ON_PRIMARY, size=18),
                                        ft.Text("Novo Lançamento", color=T.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                on_click=lambda _: abrir_lancamento(page, on_saved=lambda: carregar(inicial=False)),
                                expand=True,
                                style=ft.ButtonStyle(
                                    bgcolor=T.PRIMARY,
                                    overlay_color=T.PRIMARY_DARK,
                                    shape=ft.RoundedRectangleBorder(radius=10),
                                    padding=pad(h=20, v=14),
                                ),
                            ),
                        ),
                        ft.Container(
                            col={"xs": 6, "sm": 2},
                            content=T.botao_outline("Contas", icone=ft.Icons.ACCOUNT_BALANCE_ROUNDED, on_click=lambda _: ir_contas(page)),
                        ),
                        ft.Container(
                            col={"xs": 6, "sm": 2},
                            content=T.botao_outline("Cartões", icone=ft.Icons.CREDIT_CARD_ROUNDED, on_click=lambda _: ir_cartoes(page)),
                        ),
                        ft.Container(
                            col={"xs": 6, "sm": 2},
                            content=T.botao_outline("Calendário", icone=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda _: navegar(page, "/calendario")),
                        ),
                        ft.Container(
                            col={"xs": 6, "sm": 2},
                            content=T.botao_outline("Relatórios", icone=ft.Icons.BAR_CHART_ROUNDED, on_click=lambda _: ir_hub_relatorios(page)),
                        ),
                    ],
                ),
            ],
        ),
    )

    # =========================================================================
    # CORPO PRINCIPAL
    # =========================================================================
    conteudo = ft.Column(
        spacing=0,
        controls=[
            boas_vindas,
            ft.Container(height=14 if mobile else 18),
            kpis,
            ft.Container(height=16 if mobile else 20),
            barra_titulo_graficos,
            ft.Container(height=8),
            grid_graficos,
            ft.Container(height=16),
            acoes_desktop,
            ft.Container(height=28),
        ],
    )

    # Carrega dados iniciais
    carregar(inicial=True)

    return criar_shell(
        page,
        rota_ativa=ROTA_DASHBOARD,
        conteudo=conteudo,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
