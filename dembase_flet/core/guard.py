"""
=============================================================================
DemBase v3 — core/guard.py  (Flet 1.0.1)
Proteções de interface:
  1. proteger_clique(): trava anti-duplo clique (debounce) com feedback visual
     imediato (disabled + opacidade reduzida) até o handler terminar.
  2. view_erro_retry(): view de fallback com mensagem e botão "Tentar novamente"
     para evitar telas em branco quando a construção/consulta falha.
=============================================================================
"""
from __future__ import annotations

from typing import Callable

import flet as ft

from core import theme as T

def proteger_clique(handler: Callable, hold: float = 0.0) -> Callable:
    """
    Mantido por compatibilidade. A proteção anti-duplo-clique agora é GLOBAL e
    vive em core/click_guard.py (instalada no main.py): cobre todos os on_click
    com feedback visual imediato, descarte de cliques repetidos e liberação
    garantida em caso de erro. Esta função apenas devolve o handler intacto
    (a versão anterior usava time.sleep no event loop, que congelava a UI).
    """
    return handler



def view_erro_retry(
    rota: str,
    mensagem: str,
    on_retry: Callable,
) -> ft.View:
    """View de fallback: mensagem de erro + botão 'Tentar novamente' (nunca tela vazia)."""
    return ft.View(
        route=rota,
        bgcolor=T.BG,
        padding=24,
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=14,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CLOUD_OFF_ROUNDED, color=T.DESPESA, size=44),
                        ft.Text(
                            "Não foi possível carregar esta tela",
                            color=T.TEXT_PRIMARY, size=17, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            mensagem, color=T.TEXT_MUTED, size=12,
                            text_align=ft.TextAlign.CENTER, max_lines=4,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.FilledButton(
                            content=ft.Text("Tentar novamente", color=T.ON_NEON, weight=ft.FontWeight.BOLD),
                            icon=ft.Icons.REFRESH_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                            on_click=proteger_clique(on_retry),
                        ),
                    ],
                ),
            )
        ],
    )
