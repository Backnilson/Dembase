"""
=============================================================================
DemBase v3 - views/shell_view.py  (Flet 1.0.1)
Shell principal da aplicação após o login.
Adaptativo:
- Mobile (<768px): BottomAppBar com FAB + Top AppBar + Drawer
- Desktop (>=768px): Sidebar Fixa + Header
=============================================================================
"""
from __future__ import annotations
import flet as ft
from datetime import date
from core import theme as T
from core.theme import pad, borda, borda_bottom
from core.router import navegar, ROTA_AUTH
from core.window_manager import ajustar_janela_login
from core.responsive import is_mobile, setup_responsive_resize
import services.supabase_client as db

ROTA_DASHBOARD   = "/dashboard"
ROTA_CONTAS      = "/contas"
ROTA_CARTOES     = "/cartoes"
ROTA_LANCAMENTO  = "/lancamento"
ROTA_CALENDARIO  = "/calendario"
ROTA_RELATORIOS  = "/relatorios"
ROTA_CONFIG      = "/configuracoes"

_NAV_ITEMS = [
    {"rota": ROTA_DASHBOARD,  "icone": ft.Icons.DASHBOARD_ROUNDED,          "label": "Dashboard"},
    {"rota": ROTA_CONTAS,     "icone": ft.Icons.ACCOUNT_BALANCE_ROUNDED,     "label": "Contas"},
    {"rota": ROTA_CARTOES,    "icone": ft.Icons.CREDIT_CARD_ROUNDED,         "label": "Cartões"},
    {"rota": ROTA_LANCAMENTO, "icone": ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,  "label": "Lançamento"},
    {"rota": ROTA_CALENDARIO, "icone": ft.Icons.CALENDAR_MONTH_ROUNDED,      "label": "Calendário"},
    {"rota": ROTA_RELATORIOS, "icone": ft.Icons.BAR_CHART_ROUNDED,           "label": "Relatórios"},
]

_MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

_sidebar_expandida: bool = False

def criar_shell(
    page: ft.Page,
    rota_ativa: str = ROTA_DASHBOARD,
    conteudo: ft.Control | None = None,
    on_mes_ano_change=None,
) -> ft.View:
    global _sidebar_expandida
    
    # Registra o evento de resize adaptativo (transição suave Web/Desktop)
    setup_responsive_resize(page)

    hoje = date.today()
    mes_sel = [hoje.month]
    ano_sel = [hoje.year]

    try:
        perfil = db.ler_perfil()
        nome_completo = perfil["nome"] if perfil and perfil.get("nome") else "Usuário"
        nome_curto    = nome_completo.split()[0]
    except Exception:
        nome_curto = nome_completo = "Usuário"

    # --- Seletor de Mês/Ano (usado tanto no Mobile Top AppBar quanto Desktop Header) ---
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

    # -------------------------------------------------------------------------
    # AREA DE CONTEUDO
    # -------------------------------------------------------------------------
    area_conteudo = ft.Container(
        expand=True,
        bgcolor=T.BG,
        padding=pad(h=28 if not is_mobile(page) else 16, v=20),
        content=ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[conteudo] if conteudo else [],
        ),
    )

    # -------------------------------------------------------------------------
    # LAYOUT ADAPTATIVO (MOBILE VS DESKTOP)
    # -------------------------------------------------------------------------
    if is_mobile(page):
        # ================== LAYOUT MOBILE ==================
        
        # 1. AppBar Superior
        appbar = ft.AppBar(
            bgcolor=T.SURFACE,
            title=ft.Text(next((i["label"] for i in _NAV_ITEMS if i["rota"] == rota_ativa), "DemBase"), size=16),
            actions=[seletor_mes, ft.Container(width=8)]
        )
        
        # 2. Drawer (Hamburguer)
        drawer = ft.NavigationDrawer(
            bgcolor=T.SURFACE,
            on_change=lambda e: navegar(page, [ROTA_DASHBOARD, ROTA_CONFIG, ROTA_AUTH][e.control.selected_index]),
            controls=[
                ft.Container(
                    padding=pad(h=20, v=20),
                    content=ft.Column([
                        ft.CircleAvatar(
                            content=ft.Text(nome_curto[0], weight=ft.FontWeight.BOLD),
                            bgcolor=T.PRIMARY,
                            color=T.BG
                        ),
                        ft.Text(nome_completo, weight=ft.FontWeight.BOLD, size=16),
                        ft.Text("DemBase", color=T.TEXT_MUTED, size=12),
                    ])
                ),
                ft.Divider(color=T.BORDER),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.DASHBOARD_ROUNDED,
                    label="Dashboard"
                ),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.SETTINGS_ROUNDED,
                    label="Configurações"
                ),
                ft.Divider(color=T.BORDER),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.LOGOUT_ROUNDED,
                    label="Sair"
                ),
            ]
        )
        
        # 3. Bottom App Bar & FAB
        fab = ft.FloatingActionButton(
            icon=ft.Icons.ADD_ROUNDED,
            bgcolor=T.PRIMARY,
            shape=ft.CircleBorder(),
            on_click=lambda _: navegar(page, ROTA_LANCAMENTO)
        )
        
        # Utiliza CircularRectangleNotchShape suportado no Flet 1.0.1
        notch_shape = ft.CircularRectangleNotchShape()
        
        bottom_appbar = ft.BottomAppBar(
            bgcolor=T.SURFACE,
            shape=notch_shape,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_AROUND,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.ACCOUNT_BALANCE_ROUNDED, 
                        icon_color=T.PRIMARY if rota_ativa == ROTA_CONTAS else T.TEXT_MUTED,
                        on_click=lambda _: navegar(page, ROTA_CONTAS)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CREDIT_CARD_ROUNDED, 
                        icon_color=T.PRIMARY if rota_ativa == ROTA_CARTOES else T.TEXT_MUTED,
                        on_click=lambda _: navegar(page, ROTA_CARTOES)
                    ),
                    ft.Container(expand=True), # Espaço centralizado para acomodar o FAB
                    ft.IconButton(
                        icon=ft.Icons.CALENDAR_MONTH_ROUNDED, 
                        icon_color=T.PRIMARY if rota_ativa == ROTA_CALENDARIO else T.TEXT_MUTED,
                        on_click=lambda _: navegar(page, ROTA_CALENDARIO)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.BAR_CHART_ROUNDED, 
                        icon_color=T.PRIMARY if rota_ativa == ROTA_RELATORIOS else T.TEXT_MUTED,
                        on_click=lambda _: navegar(page, ROTA_RELATORIOS)
                    ),
                ]
            )
        )

        return ft.View(
            route=rota_ativa,
            bgcolor=T.BG,
            padding=0,
            appbar=appbar,
            drawer=drawer,
            bottom_appbar=bottom_appbar,
            floating_action_button=fab,
            floating_action_button_location=ft.FloatingActionButtonLocation.CENTER_DOCKED,
            controls=[area_conteudo]
        )
        
    else:
        # ================== LAYOUT DESKTOP ==================
        W_EXPANDED  = 230
        W_COLLAPSED = 68
        
        textos_colapsaveis: list[ft.Control] = []
        nav_containers: list[tuple[ft.Container, str]] = []

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
                size=14,
                weight=ft.FontWeight.W_500 if ativo else ft.FontWeight.NORMAL,
                visible=_sidebar_expandida
            )
            textos_colapsaveis.append(txt_item)

            c = ft.Container(
                content=ft.Row(
                    spacing=12,
                    controls=[
                        ft.Icon(icone, color=cor_icone, size=20),
                        txt_item,
                    ]
                ),
                bgcolor=cor_bg,
                padding=pad(h=12, v=10),
                border_radius=8,
                on_click=_on_click,
                tooltip=label if not _sidebar_expandida else None,
            )
            nav_containers.append((c, label))
            return c

        lista_nav = ft.Column(
            spacing=4,
            controls=[_nav_item(i["rota"], i["icone"], i["label"]) for i in _NAV_ITEMS]
        )

        txt_logo = ft.Text("DemBase", color=T.TEXT_PRIMARY, size=20, weight=ft.FontWeight.BOLD, visible=_sidebar_expandida)
        textos_colapsaveis.append(txt_logo)
        
        sidebar = ft.Container(
            width=W_EXPANDED if _sidebar_expandida else W_COLLAPSED,
            bgcolor=T.SURFACE,
            padding=pad(all_=14),
            animate=ft.Animation(200, "decelerate"),
            content=ft.Column(
                expand=True,
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Column(spacing=24, controls=[
                        ft.Row(
                            spacing=12,
                            controls=[
                                ft.Container(
                                    content=ft.Icon(ft.Icons.AUTO_GRAPH_ROUNDED, color=ft.Colors.WHITE, size=24),
                                    bgcolor=T.PRIMARY,
                                    border_radius=8,
                                    padding=pad(all_=8),
                                ),
                                txt_logo
                            ]
                        ),
                        lista_nav,
                    ]),
                    ft.Column(spacing=4, controls=[
                        _nav_item(ROTA_CONFIG, ft.Icons.SETTINGS_ROUNDED, "Configurações"),
                        _nav_item(ROTA_AUTH, ft.Icons.LOGOUT_ROUNDED, "Sair"),
                    ]),
                ]
            )
        )

        def _toggle_sidebar(_=None):
            global _sidebar_expandida
            _sidebar_expandida = not _sidebar_expandida

            sidebar.width = W_EXPANDED if _sidebar_expandida else W_COLLAPSED

            for idx, ctrl in enumerate(textos_colapsaveis):
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
                    ]),
                ],
            ),
        )

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

def placeholder_view(titulo: str, descricao: str, icone) -> ft.Column:
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
