"""
=============================================================================
DemBase v3 — views/dashboard_view.py  (Flet 1.0.1)
Dashboard principal. Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
import random
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import FRASES_MOTIVACIONAIS, formatar_moeda, inicio_mes_atual, hoje
from core.router import ROTA_LANCAMENTO, navegar
from views.widgets.kpi_card import kpi_card
from views.widgets.regra_5030 import secao_regra_5030
from views.shell_view import criar_shell, ROTA_DASHBOARD
import services.supabase_client as db
from datetime import date


def criar_view_dashboard(page: ft.Page) -> ft.View:
    hoje_d = date.today()
    mes_sel = [hoje_d.month]
    ano_sel = [hoje_d.year]
    frase   = random.choice(FRASES_MOTIVACIONAIS)

    # ── Perfil ────────────────────────────────────────────────────────────────
    try:
        perfil = db.ler_perfil()
        nome = perfil["nome"].split()[0] if perfil and perfil.get("nome") else "Usuário"
    except Exception:
        nome = "Usuário"

    # ── Referências mutáveis para KPIs ────────────────────────────────────────
    txt_receitas     = ft.Text("R$ 0,00", color=T.RECEITA, size=22, weight=ft.FontWeight.BOLD)
    txt_despesas     = ft.Text("R$ 0,00", color=T.DESPESA, size=22, weight=ft.FontWeight.BOLD)
    txt_saldo        = ft.Text("R$ 0,00", color=T.SALDO,   size=22, weight=ft.FontWeight.BOLD)
    txt_faturas      = ft.Text("R$ 0,00", color=T.WARNING, size=22, weight=ft.FontWeight.BOLD)
    txt_saldo_contas = ft.Text("R$ 0,00", color=T.PRIMARY, size=22, weight=ft.FontWeight.BOLD)

    spinner  = ft.ProgressRing(color=T.PRIMARY, width=22, height=22, stroke_width=2, visible=False)
    area_5030 = ft.Column(controls=[], spacing=0)

    # ── Loader ────────────────────────────────────────────────────────────────
    def carregar(mes: int = None, ano: int = None, inicial: bool = False):
        m = mes or mes_sel[0]
        a = ano or ano_sel[0]
        if not inicial:
            spinner.visible = True
            page.update()
        try:
            # Overview principal
            overview = db.obter_overview_dashboard(m, a)
            txt_receitas.value     = formatar_moeda(float(overview.get("receitas",    0) or 0))
            txt_despesas.value     = formatar_moeda(float(overview.get("despesas",    0) or 0))
            txt_saldo.value        = formatar_moeda(float(overview.get("saldo",       0) or 0))
            txt_faturas.value      = formatar_moeda(float(overview.get("total_faturas", 0) or 0))
            txt_saldo_contas.value = formatar_moeda(float(overview.get("saldo_contas", 0) or 0))

            # Regra 50/30/20 (legado — mantém compatibilidade)
            dados_5030 = db.obter_resumo_5030()
            area_5030.controls = [secao_regra_5030(dados_5030, lambda regra: navegar(page, f"/relatorios?regra={regra}"))]
        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar dados: {ex}", "erro")
        finally:
            spinner.visible = False
            if not inicial:
                page.update()

    # ── Callback do seletor de mês do Shell ───────────────────────────────────
    def on_mes_ano(m: int, a: int):
        mes_sel[0] = m
        ano_sel[0] = a
        carregar(m, a)

    # =========================================================================
    # KPI CARDS — linha superior
    # =========================================================================
    def _kpi(titulo, ref_txt, cor, icone, sub, on_click=None):
        return ft.Container(
            col={"xs": 12, "sm": 6, "md": 3},
            padding=pad(all_=18),
            bgcolor=T.SURFACE,
            border_radius=14,
            border=borda(),
            on_click=on_click,
            ink=True if on_click else False,
            content=ft.Column(spacing=0, controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(titulo, color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                        ft.Container(
                            content=ft.Icon(icone, color=cor, size=18),
                            bgcolor=f"{cor}1F", border_radius=8, padding=pad(all_=7),
                        ),
                    ],
                ),
                ft.Container(height=10),
                ref_txt,
                ft.Text(sub, color=T.TEXT_MUTED, size=11),
            ]),
        )

    kpis = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[
        _kpi("Saldo em Conta",   txt_saldo_contas, T.PRIMARY, ft.Icons.ACCOUNT_BALANCE_ROUNDED,    "Total nas contas", lambda _: navegar(page, "/contas")),
        _kpi("Receitas",         txt_receitas,     T.RECEITA, ft.Icons.ARROW_UPWARD_ROUNDED,        "No mês", lambda _: navegar(page, "/relatorios?tipo=Receita")),
        _kpi("Despesas",         txt_despesas,     T.DESPESA, ft.Icons.ARROW_DOWNWARD_ROUNDED,      "No mês", lambda _: navegar(page, "/relatorios?tipo=Despesa")),
        _kpi("Faturas Abertas",  txt_faturas,      T.WARNING, ft.Icons.CREDIT_CARD_ROUNDED,         "Cartões de crédito", lambda _: navegar(page, "/cartoes")),
    ])

    # =========================================================================
    # BOAS-VINDAS + SPINNER
    # =========================================================================
    boas_vindas = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(spacing=4, expand=True, controls=[
                ft.Row(spacing=8, controls=[
                    ft.Text(f"Olá, {nome}! 👋", color=T.TEXT_PRIMARY, size=24, weight=ft.FontWeight.BOLD),
                ]),
                ft.Text(f'"{frase}"', color=T.TEXT_MUTED, size=12, italic=True, max_lines=2),
            ]),
            spinner,
        ],
    )

    # =========================================================================
    # AÇÕES RÁPIDAS
    # =========================================================================
    acoes = ft.Container(
        padding=pad(all_=20),
        bgcolor=T.SURFACE,
        border_radius=14,
        border=borda(),
        content=ft.Column(spacing=0, controls=[
            ft.Text("Ações Rápidas", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
            ft.Container(height=14),
            ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                ft.Container(
                    col={"xs": 12, "sm": 4},
                    content=ft.FilledButton(
                        content=ft.Row(
                            spacing=6, tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ADD_ROUNDED, color=T.ON_PRIMARY, size=18),
                                ft.Text("Novo Lançamento", color=T.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        on_click=lambda _: navegar(page, ROTA_LANCAMENTO),
                        expand=True,
                        style=ft.ButtonStyle(
                            bgcolor=T.PRIMARY, overlay_color=T.PRIMARY_DARK,
                            shape=ft.RoundedRectangleBorder(radius=10),
                            padding=pad(h=20, v=14),
                        ),
                    ),
                ),
                ft.Container(col={"xs": 6, "sm": 2},
                    content=T.botao_outline("Contas",      icone=ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                                            on_click=lambda _: navegar(page, "/contas"))),
                ft.Container(col={"xs": 6, "sm": 2},
                    content=T.botao_outline("Cartões",     icone=ft.Icons.CREDIT_CARD_ROUNDED,
                                            on_click=lambda _: navegar(page, "/cartoes"))),
                ft.Container(col={"xs": 6, "sm": 2},
                    content=T.botao_outline("Calendário",  icone=ft.Icons.CALENDAR_MONTH_ROUNDED,
                                            on_click=lambda _: navegar(page, "/calendario"))),
                ft.Container(col={"xs": 6, "sm": 2},
                    content=T.botao_outline("Relatórios",  icone=ft.Icons.BAR_CHART_ROUNDED,
                                            on_click=lambda _: navegar(page, "/relatorios"))),
            ]),
        ]),
    )

    # =========================================================================
    # CORPO PRINCIPAL (conteúdo que vai para dentro do Shell)
    # =========================================================================
    conteudo = ft.Column(
        spacing=0,
        controls=[
            boas_vindas,
            ft.Container(height=20),
            kpis,
            ft.Container(height=16),
            area_5030,
            ft.Container(height=16),
            acoes,
            ft.Container(height=24),
        ],
    )

    # Carrega dados ao montar
    carregar(inicial=True)

    return criar_shell(
        page,
        rota_ativa=ROTA_DASHBOARD,
        conteudo=conteudo,
        on_mes_ano_change=on_mes_ano,
    )
