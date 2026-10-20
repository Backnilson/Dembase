"""
=============================================================================
DemBase v3 — views/widgets/report/empty_state.py  (Flet 1.0.1)
Estado vazio amigável para relatórios, com botão opcional de novo lançamento.
=============================================================================
"""
from __future__ import annotations

from typing import Callable
import flet as ft

from core import theme as T
from core.theme import pad, borda


def criar_empty_state(
    titulo: str = "Nenhum lançamento encontrado",
    subtitulo: str = "Não há movimentações para os filtros e período selecionados.",
    icone=ft.Icons.RECEIPT_LONG_OUTLINED,
    on_novo_lancamento: Callable | None = None,
    texto_botao: str = "Novo Lançamento",
) -> ft.Container:
    controles: list[ft.Control] = [
        ft.Container(
            padding=pad(all_=16),
            bgcolor=T.SURFACE_ALT,
            border_radius=30,
            content=ft.Icon(icone, size=40, color=T.TEXT_MUTED),
        ),
        ft.Text(
            titulo,
            color=T.TEXT_PRIMARY,
            size=16,
            weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        ),
        ft.Text(
            subtitulo,
            color=T.TEXT_MUTED,
            size=12.5,
            text_align=ft.TextAlign.CENTER,
        ),
    ]

    if on_novo_lancamento is not None:
        controles.append(ft.Container(height=6))
        controles.append(
            ft.FilledButton(
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text(texto_botao, color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                    ],
                ),
                on_click=on_novo_lancamento,
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=pad(h=18, v=12),
                ),
            )
        )

    return ft.Container(
        padding=pad(v=42, h=20),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=controles,
        ),
    )
