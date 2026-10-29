"""

=============================================================================

DemBase v3 - views/shell_view.py  (Flet 1.0.1)

Shell principal da aplicação após o login.

Adaptativo:

- Mobile (<768px): BottomAppBar com FAB + Top AppBar + Drawer + Filtro Global Flexível

- Desktop (>=768px): Sidebar Fixa Retrátil + Header com Filtro Global Flexível

=============================================================================

"""

from __future__ import annotations

import calendar

import flet as ft

from datetime import date, datetime, timedelta

from core import theme as T

from core.theme import pad, borda, borda_bottom

from core.router import navegar, ROTA_AUTH

from core.window_manager import ajustar_janela_login

from core.responsive import is_mobile, is_extra_large, setup_responsive_resize

from core.constants import session_clear, session_get, session_set, formatar_data_br

from core.periodo import (

    calcular_ciclo as _calcular_ciclo,

    obter_estado_periodo_atual,
    avancar_periodo_estado,

    persistir_estado_periodo as _persistir_estado_periodo,

)

from core.nav import voltar

from core import storage

from views.widgets.custom_date_picker import abrir_modal_periodo_mobills

from views.widgets.seletor_perfil import criar_seletor_perfil
from core.membro_state import obter_visao_membro_atual, definir_visao_membro_atual
import services.supabase_client as db



ROTA_DASHBOARD   = "/dashboard"

ROTA_CONTAS      = "/contas"

ROTA_CARTOES     = "/cartoes"

ROTA_CAIXINHAS   = "/caixinhas"

ROTA_CATEGORIAS  = "/categorias"

ROTA_LANCAMENTO  = "/lancamento"

ROTA_CALENDARIO  = "/calendario"

ROTA_RELATORIOS  = "/relatorios"

ROTA_CONFIG      = "/configuracoes"
ROTA_INVESTIMENTOS = "/investimentos"



_NAV_ITEMS = [

    {"rota": ROTA_DASHBOARD,   "icone": ft.Icons.DASHBOARD_ROUNDED,          "label": "Dashboard"},
    {"rota": ROTA_INVESTIMENTOS, "icone": ft.Icons.SAVINGS_ROUNDED, "label": "Meu Cofre"},

    {"rota": ROTA_CONTAS,      "icone": ft.Icons.ACCOUNT_BALANCE_ROUNDED,     "label": "Contas"},

    {"rota": ROTA_CARTOES,     "icone": ft.Icons.CREDIT_CARD_ROUNDED,         "label": "Cartões"},







    {"rota": ROTA_CALENDARIO,  "icone": ft.Icons.CALENDAR_MONTH_ROUNDED,      "label": "Calendário"},

    {"rota": ROTA_RELATORIOS,  "icone": ft.Icons.BAR_CHART_ROUNDED,           "label": "Relatórios"},

]



_MESES_PT = [

    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",

    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",

]



_MESES_CURTOS = [

    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",

    "Jul", "Ago", "Set", "Out", "Nov", "Dez",

]



_sidebar_expandida: bool = False





def sincronizar_shell_periodo(page: ft.Page) -> None:

    """Atualiza o texto da pílula de período no Appbar caso as datas tenham mudado externamente."""

    fn = getattr(page, "_shell_atualizar_periodo", None)

    if callable(fn):

        try:

            fn()

        except Exception:

            pass





def criar_shell(

    page: ft.Page,

    rota_ativa: str = ROTA_DASHBOARD,

    conteudo: ft.Control | None = None,

    on_mes_ano_change=None,

    on_periodo_change=None,

    on_lancamento_saved=None,

    rota_view: str | None = None,

    titulo: str | None = None,

    mostrar_voltar: bool = False,

    can_pop: bool | None = None,
    on_perfil_change=None,
) -> ft.View:

    global _sidebar_expandida



    rota_efetiva = rota_view or rota_ativa

    pode_voltar = (rota_efetiva != ROTA_DASHBOARD and rota_efetiva != ROTA_AUTH) if can_pop is None else can_pop



    setup_responsive_resize(page)

    mobile = is_mobile(page)
    extra_large = is_extra_large(page)



    estado_p = obter_estado_periodo_atual(page)



    try:

        perfil = db.ler_perfil()

        nome_completo = perfil["nome"] if perfil and perfil.get("nome") else "Usuário"

        nome_curto    = nome_completo.split()[0]

    except Exception:

        nome_curto = nome_completo = "Usuário"



    # --- Formatação responsiva do rótulo da Pílula de Período ---

    def _formatar_label_periodo() -> str:

        modo = estado_p["modo"]

        m = estado_p["mes"]

        a = estado_p["ano"]

        d_ini = estado_p["data_inicio"]

        d_fim = estado_p["data_fim"]



        if modo == "mes":

            if 1 <= m <= 12:

                nome_m = _MESES_CURTOS[m - 1] if mobile else _MESES_PT[m - 1]

                return f"{nome_m} {a}"

            return f"{m:02d}/{a}"



        if isinstance(d_ini, str):

            try:

                d_ini = date.fromisoformat(d_ini[:10])

            except Exception:

                d_ini = date.today()

        if isinstance(d_fim, str):

            try:

                d_fim = date.fromisoformat(d_fim[:10])

            except Exception:

                d_fim = date.today()



        if mobile:

            return f"{d_ini.day:02d}/{d_ini.month:02d} – {d_fim.day:02d}/{d_fim.month:02d}"

        return f"{d_ini.day:02d}/{d_ini.month:02d}/{d_ini.year % 100:02d} → {d_fim.day:02d}/{d_fim.month:02d}/{d_fim.year % 100:02d}"

    txt_mes_ano = ft.Text(

        _formatar_label_periodo(),

        color=T.TEXT_PRIMARY,

        size=12.5 if mobile else 14,

        weight=ft.FontWeight.W_600,

    )



    def _atualizar_label_periodo_externo():

        est_atual = obter_estado_periodo_atual(page)

        estado_p.update(est_atual)

        txt_mes_ano.value = _formatar_label_periodo()

        try:

            txt_mes_ano.update()

        except Exception:

            try:

                page.update()

            except Exception:

                pass



    page._shell_atualizar_periodo = _atualizar_label_periodo_externo



    def _sincronizar_e_emitir():

        _persistir_estado_periodo(page, estado_p)

        txt_mes_ano.value = _formatar_label_periodo()

        page.update()

        if callable(on_periodo_change):

            on_periodo_change(

                estado_p["data_inicio"].isoformat(),

                estado_p["data_fim"].isoformat(),

                estado_p["mes"],

                estado_p["ano"],

            )

        elif callable(on_mes_ano_change):

            on_mes_ano_change(estado_p["mes"], estado_p["ano"])



    def _passo_periodo(direcao: int):
        avancar_periodo_estado(estado_p, direcao)
        _sincronizar_e_emitir()

    def _passo_periodo_legado(direcao: int):

        modo = estado_p["modo"]

        if modo in ("mes", "ciclo"):

            m = estado_p["mes"] + direcao

            a = estado_p["ano"]

            if m < 1:

                m = 12

                a -= 1

            elif m > 12:

                m = 1

                a += 1

            estado_p["mes"] = m

            estado_p["ano"] = a

            if modo == "mes":

                ult = calendar.monthrange(a, m)[1]

                estado_p["data_inicio"] = date(a, m, 1)

                estado_p["data_fim"] = date(a, m, ult)

            else:

                d_ini, d_fim = _calcular_ciclo(m, a, estado_p["dia_ciclo"])

                estado_p["data_inicio"] = d_ini

                estado_p["data_fim"] = d_fim

        else:

            dias = max(1, (estado_p["data_fim"] - estado_p["data_inicio"]).days + 1)

            delta = timedelta(days=dias * direcao)

            estado_p["data_inicio"] = estado_p["data_inicio"] + delta

            estado_p["data_fim"] = estado_p["data_fim"] + delta

            estado_p["mes"] = estado_p["data_fim"].month

            estado_p["ano"] = estado_p["data_fim"].year



        _sincronizar_e_emitir()



    # --- Modal de Filtro de Período Flexível Estilo Mobills (Flet 1.0.1) ---

    def _abrir_modal_periodo(_=None):

        def _ao_confirmar_periodo(novo_estado: dict):

            estado_p["modo"] = novo_estado["modo"]

            estado_p["data_inicio"] = novo_estado["data_inicio"]

            estado_p["data_fim"] = novo_estado["data_fim"]

            estado_p["dia_ciclo"] = novo_estado.get("dia_ciclo", estado_p["dia_ciclo"])

            estado_p["mes"] = novo_estado.get("mes", novo_estado["data_fim"].month)

            estado_p["ano"] = novo_estado.get("ano", novo_estado["data_fim"].year)
            estado_p["ate_fim_mes"] = bool(novo_estado.get("ate_fim_mes", False))
            estado_p["filtro_id"] = novo_estado.get("filtro_id")

            storage.salvar_dia_ciclo_padrao(page, estado_p["dia_ciclo"])

            _sincronizar_e_emitir()



        abrir_modal_periodo_mobills(

            page=page,

            estado_periodo=estado_p,

            on_confirm=_ao_confirmar_periodo,

        )



    seletor_mes = ft.Container(

        content=ft.Row(

            spacing=2 if mobile else 4,

            tight=True,

            controls=[

                ft.IconButton(

                    icon=ft.Icons.CHEVRON_LEFT_ROUNDED,

                    icon_color=T.TEXT_MUTED,

                    icon_size=18 if mobile else 20,

                    tooltip="Período anterior",

                    on_click=lambda _: _passo_periodo(-1),

                ),

                ft.Container(

                    content=ft.Row(

                        spacing=4,

                        tight=True,

                        controls=[

                            ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, color=T.PRIMARY, size=13),

                            txt_mes_ano,

                            ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, color=T.TEXT_MUTED, size=15),

                        ],

                    ),

                    padding=pad(h=10 if mobile else 12, v=5 if mobile else 6),

                    bgcolor=T.SURFACE_ALT,

                    border_radius=20,

                    border=borda(),

                    on_click=_abrir_modal_periodo,

                    ink=True,

                    tooltip="Clique para alterar o período (Ex: dia 20 ao dia 10)",

                ),

                ft.IconButton(

                    icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,

                    icon_color=T.TEXT_MUTED,

                    icon_size=18 if mobile else 20,

                    tooltip="Próximo período",

                    on_click=lambda _: _passo_periodo(1),

                ),

            ],

        ),

    )



    # -------------------------------------------------------------------------

    
    def _ao_mudar_perfil(novo_membro_id: str | None):
        if callable(on_perfil_change):
            try:
                on_perfil_change(novo_membro_id)
            except Exception as ex:
                print(f"[ShellView] Erro no on_perfil_change: {ex}")
        elif callable(on_periodo_change):
            try:
                on_periodo_change(
                    estado_p["data_inicio"].isoformat(),
                    estado_p["data_fim"].isoformat(),
                    estado_p["mes"],
                    estado_p["ano"],
                )
            except Exception as ex:
                print(f"[ShellView] Erro ao recarregar periodo apos troca de perfil: {ex}")
        else:
            try:
                navegar(page, rota_efetiva)
            except Exception as ex:
                print(f"[ShellView] Erro ao navegar apos troca de perfil: {ex}")

    seletor_perfil = criar_seletor_perfil(page, on_change=_ao_mudar_perfil, is_mobile=False)
    seletor_perfil_mobile = criar_seletor_perfil(page, on_change=_ao_mudar_perfil, is_mobile=True)


    # AREA DE CONTEUDO

    # -------------------------------------------------------------------------
    conteudo_adaptado = (
        ft.Container(
            content=conteudo,
            width=1540,
            alignment=ft.Alignment(-1, -1),
        )
        if (extra_large and conteudo)
        else conteudo
    )

    area_conteudo = ft.Container(
        expand=True,
        bgcolor=T.BG,
        padding=pad(h=28 if not mobile else 14, v=18 if not mobile else 12),
        content=ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=0,
            controls=[conteudo_adaptado] if conteudo_adaptado else [],
        ),
    )



    def _ao_salvar_lancamento():

        if callable(on_lancamento_saved):

            on_lancamento_saved()

        else:

            navegar(page, rota_ativa)



    def _abrir_novo_lancamento(_=None):

        from views.widgets.lancamento_sheet import abrir_lancamento

        abrir_lancamento(page, on_saved=_ao_salvar_lancamento)



    # -------------------------------------------------------------------------

    # LAYOUT ADAPTATIVO (MOBILE VS DESKTOP)

    # -------------------------------------------------------------------------

    if mobile:

        # ================== LAYOUT MOBILE ==================

        titulo_rota = titulo or next((i["label"] for i in _NAV_ITEMS if i["rota"] == rota_ativa), "DemBase")



        leading_ctrl = (

            ft.IconButton(

                icon=ft.Icons.ARROW_BACK_ROUNDED,

                icon_color=T.TEXT_PRIMARY,

                tooltip="Voltar",

                on_click=lambda _: voltar(page),

            )

            if mostrar_voltar

            else None

        )



        appbar = ft.AppBar(

            bgcolor=T.SURFACE,

            leading=leading_ctrl,

            automatically_imply_leading=not mostrar_voltar,

            title=ft.GestureDetector(

                on_tap=lambda _: navegar(page, ROTA_DASHBOARD) if rota_ativa != ROTA_DASHBOARD else None,

                content=ft.Row(

                    spacing=6,

                    tight=True,

                    controls=[

                        ft.Text(

                            titulo_rota,

                            size=15,

                            weight=ft.FontWeight.BOLD,

                            color=T.TEXT_PRIMARY,

                            max_lines=1,

                            overflow=ft.TextOverflow.ELLIPSIS,

                        ),

                    ],

                ),

            ),

            actions=[seletor_perfil_mobile, seletor_mes, ft.Container(width=4)],

        )



        # 2. Drawer (Hambúrguer)
        rotas_drawer = [
            ROTA_DASHBOARD,
            ROTA_INVESTIMENTOS,
            "/configuracoes?aba=categorias",
            ROTA_CONFIG,
            ROTA_AUTH,
        ]

        async def _drawer_change(e):
            idx = e.control.selected_index
            if idx is not None and 0 <= idx < len(rotas_drawer):
                r = rotas_drawer[idx]
                if r == ROTA_AUTH:
                    try:
                        await storage.limpar_sessao_autenticada(page)
                        await storage.salvar_ultima_rota(page, ROTA_AUTH)
                        db.fazer_logout()
                        await storage.limpar_lembrar(page)
                        session_clear(page)
                    except Exception:
                        pass
                    await ajustar_janela_login(page)
                navegar(page, r)

        drawer_selected_idx = None
        if rota_ativa == ROTA_DASHBOARD:
            drawer_selected_idx = 0
        elif rota_ativa in (ROTA_INVESTIMENTOS, "/investimentos", "/cofre"):
            drawer_selected_idx = 1
        elif rota_ativa in (ROTA_CATEGORIAS, "/categorias", "/configuracoes?aba=categorias"):
            drawer_selected_idx = 2
        elif rota_ativa == ROTA_CONFIG or "/configuracoes" in rota_ativa:
            drawer_selected_idx = 3

        drawer = ft.NavigationDrawer(
            bgcolor=T.SURFACE,
            selected_index=drawer_selected_idx,
            on_change=_drawer_change,
            controls=[
                ft.Container(
                    padding=pad(h=20, v=20),
                    content=ft.Column([
                        ft.CircleAvatar(
                            content=ft.Text(nome_curto[0], weight=ft.FontWeight.BOLD),
                            bgcolor=T.PRIMARY,
                            color=T.BG,
                        ),
                        ft.Text(nome_completo, weight=ft.FontWeight.BOLD, size=16),
                        ft.Text("DemBase Controle Financeiro", color=T.TEXT_MUTED, size=12),
                    ]),
                ),
                ft.Divider(color=T.BORDER),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.DASHBOARD_ROUNDED,
                    label="Tela Inicial (Dashboard)",
                ),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.SAVINGS_ROUNDED,
                    label="Meu Cofre",
                ),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.CATEGORY_ROUNDED,
                    label="Categorias & Subcategorias",
                ),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.SETTINGS_ROUNDED,
                    label="Configurações & Gráficos",
                ),
                ft.Divider(color=T.BORDER),
                ft.NavigationDrawerDestination(
                    icon=ft.Icons.LOGOUT_ROUNDED,
                    label="Sair",
                ),
            ],
        )

        # 3. Bottom App Bar & FAB (sem ícone redundante de Dashboard, foco 1 mão)

        fab = ft.FloatingActionButton(

            icon=ft.Icons.ADD_ROUNDED,

            bgcolor=T.PRIMARY,

            shape=ft.CircleBorder(),

            tooltip="Novo Lançamento",

            on_click=_abrir_novo_lancamento,

        )



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

                        tooltip="Contas",

                        on_click=lambda _: navegar(page, ROTA_CONTAS),

                    ),

                    ft.IconButton(

                        icon=ft.Icons.CREDIT_CARD_ROUNDED,

                        icon_color=T.PRIMARY if rota_ativa == ROTA_CARTOES else T.TEXT_MUTED,

                        tooltip="Cartões",

                        on_click=lambda _: navegar(page, ROTA_CARTOES),

                    ),

                    ft.Container(expand=True),  # Espaço centralizado para acomodar o FAB

                    ft.IconButton(

                        icon=ft.Icons.CALENDAR_MONTH_ROUNDED,

                        icon_color=T.PRIMARY if rota_ativa == ROTA_CALENDARIO else T.TEXT_MUTED,

                        tooltip="Calendário",

                        on_click=lambda _: navegar(page, ROTA_CALENDARIO),

                    ),

                    ft.IconButton(

                        icon=ft.Icons.BAR_CHART_ROUNDED,

                        icon_color=T.PRIMARY if rota_ativa == ROTA_RELATORIOS else T.TEXT_MUTED,

                        tooltip="Relatórios e Extrato",

                        on_click=lambda _: navegar(page, ROTA_RELATORIOS),

                    ),

                ],

            ),

        )



        return ft.View(

            route=rota_efetiva,

            can_pop=pode_voltar,

            bgcolor=T.BG,

            padding=0,

            appbar=appbar,

            drawer=None if mostrar_voltar else drawer,

            bottom_appbar=bottom_appbar,

            floating_action_button=fab,

            floating_action_button_location=ft.FloatingActionButtonLocation.CENTER_DOCKED,

            controls=[area_conteudo],

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



            async def _on_click(_):

                if rota == ROTA_AUTH:

                    try:

                        await storage.limpar_sessao_autenticada(page)

                        await storage.salvar_ultima_rota(page, ROTA_AUTH)

                        db.fazer_logout()

                        await storage.limpar_lembrar(page)

                        session_clear(page)

                    except Exception:

                        pass

                    await ajustar_janela_login(page)

                    navegar(page, rota)

                    return

                if rota == ROTA_LANCAMENTO:

                    _abrir_novo_lancamento()

                    return

                navegar(page, rota)



            txt_item = ft.Text(

                label,

                color=cor_texto,

                size=14,

                weight=ft.FontWeight.W_500 if ativo else ft.FontWeight.NORMAL,

                visible=_sidebar_expandida,

            )

            textos_colapsaveis.append(txt_item)



            c = ft.Container(

                content=ft.Row(

                    spacing=12,

                    controls=[

                        ft.Icon(icone, color=cor_icone, size=20),

                        txt_item,

                    ],

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

            controls=[_nav_item(i["rota"], i["icone"], i["label"]) for i in _NAV_ITEMS],

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

                                txt_logo,

                            ],

                        ),

                        lista_nav,

                    ]),

                    ft.Column(spacing=4, controls=[

                        _nav_item(ROTA_CONFIG, ft.Icons.SETTINGS_ROUNDED, "Configurações"),

                        _nav_item(ROTA_AUTH, ft.Icons.LOGOUT_ROUNDED, "Sair"),

                    ]),

                ],

            ),

        )



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



        titulo_header = titulo or next((i["label"] for i in _NAV_ITEMS if i["rota"] == rota_ativa), "DemBase")

        controles_esq_header: list[ft.Control] = [

            btn_toggle,

            ft.VerticalDivider(width=1, color=T.BORDER),

        ]

        if mostrar_voltar:

            controles_esq_header.append(

                ft.IconButton(

                    icon=ft.Icons.ARROW_BACK_ROUNDED,

                    icon_color=T.PRIMARY,

                    icon_size=20,

                    tooltip="Voltar",

                    on_click=lambda _: voltar(page),

                )

            )

        controles_esq_header.append(

            ft.Text(

                titulo_header,

                color=T.TEXT_PRIMARY,

                size=16,

                weight=ft.FontWeight.BOLD,

            )

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

                    ft.Row(spacing=8, controls=controles_esq_header),

                    ft.Row(spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=[

                        seletor_perfil,

                        seletor_mes,

                        ft.FilledButton(

                            content=ft.Row(

                                spacing=6,

                                tight=True,

                                controls=[

                                    ft.Icon(ft.Icons.ADD_ROUNDED, color=T.ON_PRIMARY, size=18),

                                    ft.Text("Novo", color=T.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600),

                                ],

                            ),

                            on_click=_abrir_novo_lancamento,

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

            route=rota_efetiva,

            can_pop=pode_voltar,

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

