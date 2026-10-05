"""
=============================================================================
DemBase v3 — views/widgets/auth/auth_toggle.py (Flet 1.0.1)
Toggle deslizante animado com as abas "Entrar" e "Cadastrar".
=============================================================================
"""
from typing import Callable
import flet as ft
from core import theme as T
from core.theme import pad, borda


def criar_auth_toggle(on_change: Callable[[bool], None], login_inicial: bool = True) -> tuple[ft.Container, Callable[[bool], None]]:
    """
    Cria um Switch/Toggle deslizante animado para alternar entre Login e Cadastro.
    Retorna o container visual e a função `alternar_modo(login: bool)` para sincronização externa.
    """
    modo_atual = [login_inicial]

    # Indicador de fundo deslizante
    indicador = ft.Container(
        width=180,
        height=38,
        bgcolor=T.SURFACE if T.IS_DARK else "#FFFFFF",
        border_radius=10,
        border=borda(width=1, color=f"{T.BORDER}55"),
        shadow=ft.BoxShadow(
            blur_radius=8,
            color="#00000030" if T.IS_DARK else "#00000012",
            offset=ft.Offset(0, 2),
        ),
        animate_offset=ft.Animation(260, ft.AnimationCurve.EASE_IN_OUT),
        offset=ft.Offset(0, 0) if login_inicial else ft.Offset(1, 0),
    )

    txt_entrar = ft.Text(
        "Entrar",
        size=13.5,
        weight=ft.FontWeight.W_700 if login_inicial else ft.FontWeight.W_500,
        color=T.TEXT_PRIMARY if login_inicial else T.TEXT_MUTED,
        text_align=ft.TextAlign.CENTER,
    )

    txt_cadastrar = ft.Text(
        "Cadastrar",
        size=13.5,
        weight=ft.FontWeight.W_500 if login_inicial else ft.FontWeight.W_700,
        color=T.TEXT_MUTED if login_inicial else T.TEXT_PRIMARY,
        text_align=ft.TextAlign.CENTER,
    )

    def atualizar_visual(is_login: bool):
        indicador.offset = ft.Offset(0, 0) if is_login else ft.Offset(1, 0)

        txt_entrar.color = T.TEXT_PRIMARY if is_login else T.TEXT_MUTED
        txt_entrar.weight = ft.FontWeight.W_700 if is_login else ft.FontWeight.W_500

        txt_cadastrar.color = T.TEXT_MUTED if is_login else T.TEXT_PRIMARY
        txt_cadastrar.weight = ft.FontWeight.W_500 if is_login else ft.FontWeight.W_700

    def alternar_modo(is_login: bool, notificar: bool = True):
        if modo_atual[0] == is_login and notificar:
            return
        modo_atual[0] = is_login
        atualizar_visual(is_login)
        if notificar and on_change:
            on_change(is_login)

    btn_entrar = ft.Container(
        content=txt_entrar,
        alignment=ft.Alignment(0, 0),
        expand=True,
        height=38,
        on_click=lambda _: alternar_modo(True),
    )

    btn_cadastrar = ft.Container(
        content=txt_cadastrar,
        alignment=ft.Alignment(0, 0),
        expand=True,
        height=38,
        on_click=lambda _: alternar_modo(False),
    )

    toggle_container = ft.Container(
        width=368,
        height=46,
        bgcolor=T.SURFACE_ALT,
        border_radius=12,
        padding=pad(all_=4),
        border=borda(),
        content=ft.Stack(
            controls=[
                indicador,
                ft.Row(
                    controls=[btn_entrar, btn_cadastrar],
                    spacing=0,
                    alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                ),
            ],
        ),
    )

    return toggle_container, alternar_modo
