"""
=============================================================================
DemBase v3 — views/widgets/kpi_card.py  (Flet 1.0 compatible)
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_moeda


def kpi_card(titulo: str, valor: float, icone: str, cor: str, subtitulo: str = "") -> ft.Container:
    return ft.Container(
        expand=True,
        padding=pad(all_=20),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=0,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(titulo, color=T.TEXT_MUTED, size=13, weight=ft.FontWeight.W_500),
                        ft.Container(
                            content=ft.Icon(icone, color=cor, size=20),
                            bgcolor=f"{cor}1F",
                            border_radius=8,
                            padding=pad(all_=8),
                        ),
                    ],
                ),
                ft.Container(height=12),
                ft.Text(formatar_moeda(valor), color=cor, size=26, weight=ft.FontWeight.BOLD),
                ft.Text(subtitulo, color=T.TEXT_MUTED, size=11) if subtitulo else ft.Container(height=0),
            ],
        ),
    )
