"""
=============================================================================
DemBase v3 — views/widgets/report/header.py  (Flet 1.0.1)
Cabeçalho de relatório com breadcrumb clicável (Desktop), título, subtítulo de
período, spinner de carregamento e slot acoes_header (sem exportação no MVP).
=============================================================================
"""
from __future__ import annotations

from typing import Callable
import flet as ft

from core import theme as T
from core.theme import pad
from core.nav import navegar, voltar


def criar_report_header(
    page: ft.Page,
    titulo_ctrl: ft.Text | str | None = None,
    subtitulo_ctrl: ft.Text | str | None = None,
    spinner: ft.ProgressRing | None = None,
    breadcrumbs: list[tuple[str, str | None]] | None = None,
    icone=ft.Icons.ASSESSMENT_ROUNDED,
    cor_icone: str | None = None,
    acoes_header: list[ft.Control] | None = None,
    mobile: bool = False,
    on_voltar: Callable | None = None,
    titulo: str | None = None,
    subtitulo: str | None = None,
) -> ft.Column:
    """
    Constrói o topo do relatório:
    - Breadcrumb clicável no Desktop: ex: [('Dashboard', '/dashboard'), ('Contas', '/contas'), ('Nubank', None)]
    - Linha principal com botão voltar, ícone colorido, título dinâmico, spinner e ações.
    Suporta tanto ft.Text em titulo_ctrl/subtitulo_ctrl quanto strings em titulo/subtitulo.
    """
    if titulo_ctrl is None:
        titulo_ctrl = titulo or "Relatório"
    if isinstance(titulo_ctrl, str):
        titulo_ctrl = ft.Text(
            titulo_ctrl,
            color=T.TEXT_PRIMARY,
            size=18 if mobile else 20,
            weight=ft.FontWeight.BOLD,
        )

    if subtitulo_ctrl is None:
        subtitulo_ctrl = subtitulo or ""
    if isinstance(subtitulo_ctrl, str):
        subtitulo_ctrl = ft.Text(
            subtitulo_ctrl,
            color=T.TEXT_MUTED,
            size=11.5,
        )

    if spinner is None:
        spinner = ft.ProgressRing(width=16, height=16, visible=False, color=T.PRIMARY)

    cor_ic = cor_icone or T.PRIMARY
    linhas_topo: list[ft.Control] = []

    if breadcrumbs and not mobile:
        itens_bc: list[ft.Control] = []
        for idx, (lbl, rota_bc) in enumerate(breadcrumbs):
            eh_ultimo = idx == len(breadcrumbs) - 1
            if rota_bc and not eh_ultimo:
                itens_bc.append(
                    ft.Container(
                        padding=pad(h=6, v=2),
                        border_radius=6,
                        on_click=lambda _, r=rota_bc: navegar(page, r),
                        ink=True,
                        content=ft.Text(
                            lbl,
                            color=T.TEXT_MUTED,
                            size=12,
                            weight=ft.FontWeight.W_500,
                        ),
                    )
                )
            else:
                itens_bc.append(
                    ft.Text(
                        lbl,
                        color=T.PRIMARY if eh_ultimo else T.TEXT_MUTED,
                        size=12,
                        weight=ft.FontWeight.BOLD if eh_ultimo else ft.FontWeight.W_500,
                    )
                )
            if not eh_ultimo:
                itens_bc.append(
                    ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=14, color=T.TEXT_MUTED)
                )
        linhas_topo.append(
            ft.Row(
                spacing=2,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=itens_bc,
            )
        )

    btn_voltar = ft.IconButton(
        icon=ft.Icons.ARROW_BACK_ROUNDED,
        icon_color=T.TEXT_PRIMARY,
        bgcolor=T.SURFACE,
        icon_size=18 if mobile else 20,
        tooltip="Voltar",
        on_click=on_voltar or (lambda _: voltar(page)),
    )

    bloco_titulo = ft.Row(
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        expand=True,
        controls=[
            btn_voltar,
            ft.Container(
                content=ft.Icon(icone, color=cor_ic, size=20 if not mobile else 18),
                bgcolor=f"{cor_ic}1F",
                border_radius=10,
                padding=pad(all_=9 if not mobile else 7),
            ),
            ft.Column(
                spacing=2,
                expand=True,
                controls=[
                    ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            titulo_ctrl,
                            spinner,
                        ],
                    ),
                    subtitulo_ctrl,
                ],
            ),
        ],
    )

    controles_linha_principal: list[ft.Control] = [bloco_titulo]
    if acoes_header:
        controles_linha_principal.append(
            ft.Row(spacing=8, tight=True, controls=list(acoes_header))
        )

    linhas_topo.append(
        ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True if mobile else False,
            spacing=8,
            controls=controles_linha_principal,
        )
    )

    return ft.Column(spacing=6, controls=linhas_topo)
