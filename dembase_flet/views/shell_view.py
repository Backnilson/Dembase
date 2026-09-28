"""
=============================================================================
DemBase v3 — views/shell_view.py  (Flet 1.0.1)
Shell principal da aplicação após o login.
Contém a Sidebar de navegação + Header superior + área de conteúdo.

Uso:
    from views.shell_view import criar_shell
    shell = criar_shell(page, rota_ativa="/dashboard", conteudo=meu_conteudo)
=============================================================================
"""
from __future__ import annotations
import flet as ft
from datetime import date
from core import theme as T
from core.theme import pad, borda, borda_bottom
from core.router import navegar, ROTA_AUTH
from core.window_manager import ajustar_janela_login
import services.supabase_client as db

# ── Rotas disponíveis na Sidebar ──────────────────────────────────────────────
ROTA_DASHBOARD   = "/dashboard"
ROTA_CONTAS      = "/contas"
ROTA_CARTOES     = "/cartoes"
ROTA_LANCAMENTO  = "/lancamento"
ROTA_CALENDARIO  = "/calendario"
ROTA_RELATORIOS  = "/relatorios"
ROTA_CONFIG      = "/configuracoes"

# ── Definição dos itens da Sidebar ─────────────────────────────────────────────
_NAV_ITEMS = [
    {"rota": ROTA_DASHBOARD,  "icone": ft.Icons.DASHBOARD_ROUNDED,          "label": "Dashboard"},
    {"rota": ROTA_CONTAS,     "icone": ft.Icons.ACCOUNT_BALANCE_ROUNDED,     "label": "Contas"},
    {"rota": ROTA_CARTOES,    "icone": ft.Icons.CREDIT_CARD_ROUNDED,         "label": "Cartões"},
    {"rota": ROTA_LANCAMENTO, "icone": ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,  "label": "Lançamento"},
    {"rota": ROTA_CALENDARIO, "icone": ft.Icons.CALENDAR_MONTH_ROUNDED,      "label": "Calendário"},
    {"rota": ROTA_RELATORIOS, "icone": ft.Icons.BAR_CHART_ROUNDED,           "label": "Relatórios"},
]

# Meses para o seletor do Header
_MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

# Estado compartilhado da Sidebar (persiste durante a navegação entre rotas)
# Padrão: False (modo minificado / 68px de largura)
_sidebar_expandida: bool = False


# =============================================================================
# CONSTRUTOR DO SHELL
# =============================================================================
def criar_shell(
    page: ft.Page,
    rota_ativa: str = ROTA_DASHBOARD,
    conteudo: ft.Control | None = None,
    on_mes_ano_change=None,  # callback(mes: int, ano: int)
) -> ft.View:
    """
    Retorna um ft.View completo com:
      - Sidebar colapsável à esquerda (modo minificado padrão com ícones e tooltips)
      - Header superior com botão hambúrguer e seletor de mês/ano
      - Área de conteúdo scrollável à direita
    """
    global _sidebar_expandida

    hoje = date.today()
    mes_sel = [hoje.month]
    ano_sel = [hoje.year]

    # ── Perfil ──────────────────────────────────────────────────────────────
    try:
        perfil = db.ler_perfil()
        nome_completo = perfil["nome"] if perfil and perfil.get("nome") else "Usuário"
        nome_curto    = nome_completo.split()[0]
    except Exception:
        nome_curto = nome_completo = "Usuário"

    # ── Dimensões da sidebar ────────────────────────────────────────────────
    W_EXPANDED  = 230
    W_COLLAPSED = 68

    # Rastrear controles que devem sumir quando colapsar
    textos_colapsaveis: list[ft.Control] = []
    nav_containers: list[tuple[ft.Container, str]] = []

    # =========================================================================
    # ITEM DE NAVEGAÇÃO
    # =========================================================================
    def _nav_item(rota: str, icone, label: str) -> ft.Container:
        ativo = rota == rota_ativa
        cor_icone = T.PRIMARY if ativo else T.TEXT_MUTED
        cor_bg    = f"{T.PRIMARY}18" if ativo else "transparent"
        cor_texto = T.TEXT_PRIMARY if ativo else T.TEXT_MUTED

        def _on_click(_):
            navegar(page, rota)

        txt_item = ft.Text(
            label,
            color=cor_texto,
            size=13,
            weight=ft.FontWeight.W_600 if ativo else ft.FontWeight.W_400,
            visible=_sidebar_expandida,
            no_wrap=True,
        )
        textos_colapsaveis.append(txt_item)

        icon_box = ft.Container(
            content=ft.Icon(icone, color=cor_icone, size=20),
            width=38,
            height=38,
            alignment=ft.Alignment(0, 0),
        )

        item = ft.Container(
            content=ft.Row(
                spacing=8,
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    icon_box,
                    txt_item,
                ],
            ),
            bgcolor=cor_bg,
            border_radius=10,
            padding=pad(h=5, v=3),
            on_click=_on_click,
            tooltip=label if not _sidebar_expandida else None,
            border=borda(1, f"{T.PRIMARY}40") if ativo else None,
            animate=ft.Animation(duration=150, curve=ft.AnimationCurve.EASE_OUT),
        )
        nav_containers.append((item, label))
        return item

    # =========================================================================
    # SIDEBAR
    # =========================================================================
    nav_items_col = ft.Column(
        spacing=4,
        controls=[_nav_item(i["rota"], i["icone"], i["label"]) for i in _NAV_ITEMS],
    )

    # Logo
    txt_logo = ft.Text(
        "DemBase",
        color=T.TEXT_PRIMARY,
        size=17,
        weight=ft.FontWeight.BOLD,
        visible=_sidebar_expandida,
        no_wrap=True,
    )
    textos_colapsaveis.append(txt_logo)

    logo_icon = ft.Container(
        content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=T.PRIMARY, size=22),
        bgcolor=f"{T.PRIMARY}22",
        border_radius=10,
        width=38,
        height=38,
        alignment=ft.Alignment(0, 0),
    )

    sidebar_logo = ft.Container(
        content=ft.Row(
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                logo_icon,
                txt_logo,
            ],
        ),
        padding=pad(h=14, v=14),
        border=borda_bottom(color=T.BORDER),
    )

    # ── Avatar e Perfil no rodapé (com Logout ao clicar no Avatar) ─────────────
    async def _on_logout(_=None):
        try:
            db.fazer_logout()
            await ajustar_janela_login(page)
        finally:
            navegar(page, ROTA_AUTH)

    _avatar_circle = ft.Container(
        content=ft.Text(
            nome_curto[0].upper() if nome_curto else "U",
            color=ft.Colors.WHITE,
            size=15,
            weight=ft.FontWeight.BOLD,
        ),
        bgcolor=T.PRIMARY,
        border_radius=18,
        width=36,
        height=36,
        alignment=ft.Alignment(0, 0),
    )

    menu_avatar = ft.PopupMenuButton(
        content=_avatar_circle,
        tooltip=f"{nome_completo}\nClique para opções de conta",
        items=[
            ft.PopupMenuItem(
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.ACCOUNT_CIRCLE_ROUNDED, size=18, color=T.PRIMARY),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(nome_completo, size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                                ft.Text("Conta ativa", size=10, color=T.TEXT_MUTED),
                            ],
                        ),
                    ],
                ),
                disabled=True,
            ),
            ft.PopupMenuItem(),
            ft.PopupMenuItem(
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.LOGOUT_ROUNDED, size=18, color=T.DESPESA),
                        ft.Text("Sair da conta", size=13, color=T.DESPESA, weight=ft.FontWeight.W_600),
                    ],
                ),
                on_click=_on_logout,
            ),
        ],
    )

    col_perfil_info = ft.Column(
        spacing=0,
        expand=True,
        visible=_sidebar_expandida,
        controls=[
            ft.Text(nome_curto, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600, no_wrap=True),
            ft.Text("Conta pessoal", color=T.TEXT_MUTED, size=11, no_wrap=True),
        ],
    )
    textos_colapsaveis.append(col_perfil_info)

    btn_logout_rapido = ft.IconButton(
        icon=ft.Icons.LOGOUT_ROUNDED,
        icon_color=T.DESPESA,
        icon_size=18,
        tooltip="Sair",
        on_click=_on_logout,
        visible=_sidebar_expandida,
    )
    textos_colapsaveis.append(btn_logout_rapido)

    avatar_slot = ft.Container(
        content=menu_avatar,
        width=38,
        height=38,
        alignment=ft.Alignment(0, 0),
    )

    sidebar_footer = ft.Container(
        content=ft.Row(
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                avatar_slot,
                col_perfil_info,
                btn_logout_rapido,
            ],
        ),
        padding=pad(h=15, v=12),
        border=borda_bottom(color=T.BORDER),
    )

    sidebar_col = ft.Column(
        expand=True,
        spacing=0,
        controls=[
            sidebar_logo,
            ft.Container(
                content=nav_items_col,
                padding=pad(h=10, v=12),
                expand=True,
            ),
            ft.Container(height=1, bgcolor=T.BORDER),
            sidebar_footer,
        ],
    )

    sidebar = ft.Container(
        width=W_EXPANDED if _sidebar_expandida else W_COLLAPSED,
        bgcolor=T.SURFACE,
        border=borda(1, T.BORDER),
        animate=ft.Animation(duration=250, curve=ft.AnimationCurve.FAST_OUT_SLOWIN),
        content=sidebar_col,
    )

    # ── Toggle da Sidebar (Gatilho do Botão Hambúrguer) ───────────────────────
    def _toggle_sidebar(_=None):
        global _sidebar_expandida
        _sidebar_expandida = not _sidebar_expandida

        sidebar.width = W_EXPANDED if _sidebar_expandida else W_COLLAPSED

        for ctrl in textos_colapsaveis:
            ctrl.visible = _sidebar_expandida

        for container, label in nav_containers:
            container.tooltip = label if not _sidebar_expandida else None

        btn_toggle.icon = ft.Icons.MENU_OPEN_ROUNDED if _sidebar_expandida else ft.Icons.MENU_ROUNDED
        btn_toggle.icon_color = T.PRIMARY if _sidebar_expandida else T.TEXT_MUTED
        btn_toggle.tooltip = "Recolher menu" if _sidebar_expandida else "Expandir menu"

        page.update()

    btn_toggle = ft.IconButton(
        icon=ft.Icons.MENU_OPEN_ROUNDED if _sidebar_expandida else ft.Icons.MENU_ROUNDED,
        icon_color=T.PRIMARY if _sidebar_expandida else T.TEXT_MUTED,
        icon_size=20,
        tooltip="Recolher menu" if _sidebar_expandida else "Expandir menu",
        on_click=_toggle_sidebar,
    )

    # =========================================================================
    # SELETOR DE MÊS/ANO (Header)
    # =========================================================================
    txt_mes_ano = ft.Text(
        f"{_MESES_PT[hoje.month - 1]} {hoje.year}",
        color=T.TEXT_PRIMARY,
        size=15,
        weight=ft.FontWeight.W_600,
    )

    def _emitir_mes_ano():
        if on_mes_ano_change:
            on_mes_ano_change(mes_sel[0], ano_sel[0])

    def _mes_anterior(_):
        if mes_sel[0] == 1:
            mes_sel[0] = 12
            ano_sel[0] -= 1
        else:
            mes_sel[0] -= 1
        txt_mes_ano.value = f"{_MESES_PT[mes_sel[0] - 1]} {ano_sel[0]}"
        page.update()
        _emitir_mes_ano()

    def _mes_proximo(_):
        if mes_sel[0] == 12:
            mes_sel[0] = 1
            ano_sel[0] += 1
        else:
            mes_sel[0] += 1
        txt_mes_ano.value = f"{_MESES_PT[mes_sel[0] - 1]} {ano_sel[0]}"
        page.update()
        _emitir_mes_ano()

    seletor_mes = ft.Container(
        content=ft.Row(
            spacing=4,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                    icon_color=T.TEXT_MUTED,
                    icon_size=20,
                    on_click=_mes_anterior,
                ),
                ft.Container(
                    content=txt_mes_ano,
                    padding=pad(h=12, v=6),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=20,
                    border=borda(),
                ),
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                    icon_color=T.TEXT_MUTED,
                    icon_size=20,
                    on_click=_mes_proximo,
                ),
            ],
        ),
    )

    # =========================================================================
    # HEADER SUPERIOR
    # =========================================================================
    header = ft.Container(
        height=64,
        bgcolor=T.SURFACE,
        border=borda_bottom(),
        padding=pad(h=20, v=0),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(spacing=8, controls=[
                    btn_toggle,
                    ft.VerticalDivider(width=1, color=T.BORDER),
                    ft.Text(
                        next((i["label"] for i in _NAV_ITEMS if i["rota"] == rota_ativa), "DemBase"),
                        color=T.TEXT_PRIMARY,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                    ),
                ]),
                ft.Row(spacing=12, controls=[
                    seletor_mes,
                    ft.FilledButton(
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                                ft.Text("Novo", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        on_click=lambda _: navegar(page, ROTA_LANCAMENTO),
                        style=ft.ButtonStyle(
                            bgcolor=T.PRIMARY,
                            overlay_color=T.PRIMARY_DARK,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=pad(h=14, v=10),
                        ),
                    ),
                    ft.Container(
                        content=ft.Row(spacing=5, tight=True, controls=[
                            ft.Icon(ft.Icons.CLOUD_DONE_OUTLINED, color=T.PRIMARY, size=13),
                            ft.Text("Conectado", color=T.PRIMARY, size=11, weight=ft.FontWeight.W_600),
                        ]),
                        bgcolor=f"{T.PRIMARY}15",
                        border_radius=20,
                        padding=pad(h=10, v=5),
                        border=borda(1, f"{T.PRIMARY}40"),
                    ),
                ]),
            ],
        ),
    )

    # =========================================================================
    # ÁREA DE CONTEÚDO
    # =========================================================================
    area_conteudo = ft.Container(
        expand=True,
        bgcolor=T.BG,
        padding=pad(h=28, v=20),
        content=ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[conteudo] if conteudo else [],
        ),
    )

    # =========================================================================
    # LAYOUT FINAL
    # =========================================================================
    return ft.View(
        route=rota_ativa,
        bgcolor=T.BG,
        padding=0,
        controls=[
            ft.Column(
                expand=True,
                spacing=0,
                controls=[
                    header,
                    ft.Row(
                        expand=True,
                        spacing=0,
                        controls=[
                            sidebar,
                            ft.VerticalDivider(width=1, color=T.BORDER),
                            area_conteudo,
                        ],
                    ),
                ],
            )
        ],
    )


# =============================================================================
# HELPER: constrói conteúdo de placeholder para views ainda não implementadas
# =============================================================================
def placeholder_view(titulo: str, descricao: str, icone) -> ft.Column:
    """Retorna um Column de placeholder para views em construção."""
    return ft.Column(
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        alignment=ft.MainAxisAlignment.CENTER,
        expand=True,
        controls=[
            ft.Container(height=80),
            ft.Icon(icone, color=f"{T.PRIMARY}60", size=72),
            ft.Container(height=20),
            ft.Text(titulo, color=T.TEXT_PRIMARY, size=24, weight=ft.FontWeight.BOLD),
            ft.Container(height=8),
            ft.Text(descricao, color=T.TEXT_MUTED, size=14, text_align=ft.TextAlign.CENTER),
            ft.Container(height=24),
            ft.Container(
                content=ft.Text("Em construção", color=T.WARNING, size=12, weight=ft.FontWeight.W_600),
                bgcolor=f"{T.WARNING}20",
                border_radius=20,
                padding=pad(h=16, v=6),
                border=borda(1, f"{T.WARNING}40"),
            ),
        ],
    )
