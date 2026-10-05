"""
=============================================================================
DemBase v3 — views/widgets/auth/logo.py (Flet 1.0.1)
Componente de Logo moderna combinando D + $ em Verde Neon.
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad


def criar_logo(size: int = 56, com_texto: bool = False, centralizado: bool = True) -> ft.Control:
    """
    Retorna o logo DemBase em vetor SVG com opção de título e subtítulo.
    """
    img_logo = ft.Image(
        src="logo.svg",
        width=size,
        height=size,
        fit=ft.BoxFit.CONTAIN,
    )

    if not com_texto:
        return img_logo

    alinhamento = (
        ft.CrossAxisAlignment.CENTER if centralizado else ft.CrossAxisAlignment.START
    )
    text_align = ft.TextAlign.CENTER if centralizado else ft.TextAlign.START

    return ft.Column(
        spacing=8,
        horizontal_alignment=alinhamento,
        controls=[
            img_logo,
            ft.Column(
                spacing=3,
                horizontal_alignment=alinhamento,
                controls=[
                    ft.Text(
                        "DemBase",
                        color=T.TEXT_PRIMARY,
                        size=22,
                        weight=ft.FontWeight.W_800,
                        text_align=text_align,
                    ),
                    ft.Text(
                        "Sua vida financeira em harmonia",
                        color=T.TEXT_MUTED,
                        size=13,
                        weight=ft.FontWeight.W_400,
                        text_align=text_align,
                    ),
                ],
            ),
        ],
    )
