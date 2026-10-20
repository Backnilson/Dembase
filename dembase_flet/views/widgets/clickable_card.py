"""
=============================================================================
DemBase v3 — views/widgets/clickable_card.py  (Flet 1.0.1)
Componente padrão de Card Clicável (KPI, Conta, Cartão, Hub de Relatórios)
com feedback tátil (ink=True), realce de hover no Desktop e chevron de affordance.
=============================================================================
"""
from __future__ import annotations

from typing import Callable
import flet as ft

from core import theme as T
from core.theme import pad, borda


def clickable_card(
    content: ft.Control,
    on_click: Callable | None = None,
    col: dict | None = None,
    padding_val: int = 18,
    border_radius: int = 14,
    cor_destaque: str | None = None,
    tooltip: str | None = None,
    bgcolor: str | None = None,
    cor_hover: str | None = None,
    padding: ft.Padding | None = None,
) -> ft.Container:
    """
    Envelope clicável padronizado para Flet 1.0.1.
    Garante ink=True, área mínima de toque (>= 48px) e transição suave de borda no hover.
    """
    cor_borda_hover = cor_hover or cor_destaque or T.PRIMARY
    borda_padrao = borda()
    pad_final = padding if padding is not None else pad(all_=padding_val)

    container = ft.Container(
        col=col,
        padding=pad_final,
        bgcolor=bgcolor or T.SURFACE,
        border_radius=border_radius,
        border=borda_padrao,
        on_click=on_click,
        ink=bool(on_click),
        tooltip=tooltip,
        animate=ft.Animation(150, ft.AnimationCurve.DECELERATE),
        content=content,
    )

    if on_click is not None:
        def _on_hover(e: ft.ControlEvent):
            try:
                hover = (str(e.data).lower() == "true") if e.data is not None else False
                container.border = borda(1.5, cor_borda_hover) if hover else borda_padrao
                container.update()
            except Exception:
                pass

        container.on_hover = _on_hover

    return container


def kpi_clicavel(
    titulo: str,
    valor_ctrl: ft.Control | None = None,
    cor: str = T.PRIMARY,
    icone: ft.IconData = ft.Icons.TRENDING_UP_ROUNDED,
    subtitulo: str = "",
    on_click: Callable | None = None,
    mobile: bool = False,
    col: dict | None = None,
    ativo: bool = False,
    tooltip: str | None = None,
    valor_control: ft.Control | None = None,
    compacto: bool = False,
) -> ft.Container:
    """
    Card de KPI interativo com ícone colorido, valor dinâmico (ft.Text),
    subtítulo e seta indicativa (chevron) quando clicável.
    """
    v_ctrl = valor_control if valor_control is not None else valor_ctrl
    if v_ctrl is None:
        v_ctrl = ft.Text("R$ 0,00", color=cor, size=18, weight=ft.FontWeight.BOLD)

    is_mob = mobile or compacto

    icone_direita = [
        ft.Container(
            content=ft.Icon(icone, color=cor, size=16 if is_mob else 18),
            bgcolor=f"{cor}1F",
            border_radius=8,
            padding=pad(all_=6 if is_mob else 7),
        )
    ]
    if on_click is not None:
        icone_direita.append(
            ft.Icon(
                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                color=cor if ativo else T.TEXT_MUTED,
                size=16,
            )
        )

    corpo = ft.Column(
        spacing=0,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Text(
                        titulo,
                        color=cor if ativo else T.TEXT_MUTED,
                        size=11.5 if is_mob else 12,
                        weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.Row(spacing=4, tight=True, controls=icone_direita),
                ],
            ),
            ft.Container(height=8 if is_mob else 10),
            v_ctrl,
            ft.Text(
                subtitulo,
                color=T.TEXT_MUTED,
                size=10.5 if is_mob else 11,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
            if subtitulo
            else ft.Container(height=0),
        ],
    )

    card = clickable_card(
        content=corpo,
        on_click=on_click,
        col=col or {"xs": 6, "sm": 6, "md": 3},
        padding_val=14 if is_mob else 18,
        border_radius=14,
        cor_destaque=cor,
        tooltip=tooltip or (f"Clique para abrir detalhes de {titulo}" if on_click else None),
        bgcolor=f"{cor}10" if ativo else T.SURFACE,
    )
    if ativo:
        card.border = borda(1.5, cor)
    return card
