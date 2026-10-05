"""
=============================================================================
DemBase v3 — views/widgets/auth/social_buttons.py (Flet 1.0.1)
Divisória elegante e botões oficiais para Login Social (Google & Apple).
Diretrizes visuais premium compatíveis com Dark & Light mode.
=============================================================================
"""
from typing import Callable, Optional
import flet as ft
from core import theme as T
from core.theme import pad, borda


def criar_botoes_sociais(on_social_click: Optional[Callable[[str], None]] = None) -> ft.Column:
    """
    Retorna o bloco com a divisória 'ou continue com' e os botões estilizados
    'Entrar com Google' e 'Entrar com Apple'.
    """
    # 1. Divisória sutil com texto centralizado
    divisor = ft.Row(
        spacing=12,
        alignment=ft.MainAxisAlignment.CENTER,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(expand=True, height=1, bgcolor=T.BORDER),
            ft.Text(
                "ou continue com",
                size=12,
                color=T.TEXT_MUTED,
                weight=ft.FontWeight.W_500,
            ),
            ft.Container(expand=True, height=1, bgcolor=T.BORDER),
        ],
    )

    is_dark = T.IS_DARK

    # Cores e bordas responsivas para o botão do Google
    bg_google_def = T.SURFACE_ALT if is_dark else "#FFFFFF"
    bg_google_hov = "#283548" if is_dark else "#F1F5F9"
    bg_google_press = "#1A2332" if is_dark else "#E2E8F0"
    border_google_def = T.BORDER if is_dark else "#CBD5E1"
    border_google_hov = "#475569" if is_dark else "#94A3B8"

    # Cores e bordas responsivas para o botão da Apple (Diretrizes Human Interface da Apple)
    bg_apple_def = "#000000"
    bg_apple_hov = "#1C1C1E" if is_dark else "#1A1A1A"
    bg_apple_press = "#2C2C2E" if is_dark else "#262626"
    border_apple_def = "#334155" if is_dark else "#000000"
    border_apple_hov = "#475569" if is_dark else "#262626"

    # 2. Botão Google oficial ("Entrar com Google")
    btn_google = ft.OutlinedButton(
        content=ft.Row(
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Image(src="google_g.svg", width=19, height=19, fit=ft.BoxFit.CONTAIN),
                ft.Text(
                    "Entrar com Google",
                    size=13.5,
                    weight=ft.FontWeight.W_600,
                    color=T.TEXT_PRIMARY,
                ),
            ],
            tight=True,
        ),
        on_click=lambda _: on_social_click("google") if on_social_click else None,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.HOVERED: bg_google_hov,
                ft.ControlState.PRESSED: bg_google_press,
                ft.ControlState.DEFAULT: bg_google_def,
            },
            side={
                ft.ControlState.HOVERED: ft.BorderSide(width=1, color=border_google_hov),
                ft.ControlState.DEFAULT: ft.BorderSide(width=1, color=border_google_def),
            },
            elevation={
                ft.ControlState.HOVERED: 3,
                ft.ControlState.PRESSED: 1,
                ft.ControlState.DEFAULT: 0,
            },
            shadow_color="#00000060" if is_dark else "#0000001A",
            overlay_color={
                ft.ControlState.HOVERED: "transparent",
                ft.ControlState.PRESSED: "#FFFFFF0D" if is_dark else "#00000008",
                ft.ControlState.DEFAULT: "transparent",
            },
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(h=16, v=14),
            animation_duration=200,
        ),
    )

    # 3. Botão Apple oficial ("Entrar com Apple")
    # Diretriz da Apple: botão contrastante preto com maçã branca e hover em cinza muito escuro
    btn_apple = ft.FilledButton(
        content=ft.Row(
            spacing=12,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.APPLE, size=21, color=ft.Colors.WHITE),
                ft.Text(
                    "Entrar com Apple",
                    size=13.5,
                    weight=ft.FontWeight.W_600,
                    color=ft.Colors.WHITE,
                ),
            ],
            tight=True,
        ),
        on_click=lambda _: on_social_click("apple") if on_social_click else None,
        style=ft.ButtonStyle(
            bgcolor={
                ft.ControlState.HOVERED: bg_apple_hov,
                ft.ControlState.PRESSED: bg_apple_press,
                ft.ControlState.DEFAULT: bg_apple_def,
            },
            side={
                ft.ControlState.HOVERED: ft.BorderSide(width=1, color=border_apple_hov),
                ft.ControlState.DEFAULT: ft.BorderSide(width=1, color=border_apple_def),
            },
            elevation={
                ft.ControlState.HOVERED: 2,
                ft.ControlState.PRESSED: 0.5,
                ft.ControlState.DEFAULT: 0,
            },
            shadow_color="#00000050" if is_dark else "#00000020",
            overlay_color={
                ft.ControlState.HOVERED: "transparent",
                ft.ControlState.PRESSED: "#FFFFFF14",
                ft.ControlState.DEFAULT: "transparent",
            },
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(h=16, v=14),
            animation_duration=200,
        ),
    )

    return ft.Column(
        spacing=12,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            divisor,
            btn_google,
            btn_apple,
        ],
    )

