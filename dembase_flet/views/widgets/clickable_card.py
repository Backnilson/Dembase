"""
=============================================================================
DemBase v3 — views/widgets/clickable_card.py  (Flet 1.0.1)
Componente padrão de Card Clicável (KPI, Conta, Cartão, Hub de Relatórios)
com feedback tátil (ink=True), realce de hover no Desktop e chevron de affordance.
Layout responsivo: 2x2 compacto no Mobile (xs=6, sm=6) e 1x4 normal no Desktop (md=3).
=============================================================================
"""
from __future__ import annotations

from typing import Callable
import flet as ft

from core import theme as T
from core.theme import pad, borda
from core.guard import proteger_clique


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
        on_click=proteger_clique(on_click) if on_click else None,
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
    subtitulo: str | ft.Control = "",
    on_click: Callable | None = None,
    mobile: bool = False,
    col: dict | None = None,
    ativo: bool = False,
    tooltip: str | None = None,
    valor_control: ft.Control | None = None,
    compacto: bool = False,
) -> ft.Container:
    """
    Card de KPI interativo responsivo:
    - Telas pequenas/Mobile: grade 2x2 (xs=6, sm=6) compacta e de alta densidade.
    - Telas grandes/Desktop: grade normal 1x4 (md=3) com espaçamento e preenchimento normais.
    """
    v_ctrl = valor_control if valor_control is not None else valor_ctrl
    is_mob = mobile or compacto

    tam_fonte_padrao = 15 if is_mob else 18
    if v_ctrl is None:
        v_ctrl = ft.Text(
            "R$ 0,00",
            color=cor,
            size=tam_fonte_padrao,
            weight=ft.FontWeight.BOLD,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
    elif isinstance(v_ctrl, ft.Text):
        if is_mob and (v_ctrl.size is None or v_ctrl.size > 16):
            v_ctrl.size = 15
        elif not is_mob and (v_ctrl.size is None or v_ctrl.size < 18):
            v_ctrl.size = 18
        if not getattr(v_ctrl, "max_lines", None):
            v_ctrl.max_lines = 1
        if not getattr(v_ctrl, "overflow", None):
            v_ctrl.overflow = ft.TextOverflow.ELLIPSIS

    icone_direita = [
        ft.Container(
            content=ft.Icon(icone, color=cor, size=14 if is_mob else 18),
            bgcolor=f"{cor}1F",
            border_radius=7 if is_mob else 8,
            padding=pad(all_=4 if is_mob else 6),
        )
    ]
    if on_click is not None:
        icone_direita.append(
            ft.Icon(
                ft.Icons.CHEVRON_RIGHT_ROUNDED,
                color=cor if ativo else T.TEXT_MUTED,
                size=14 if is_mob else 16,
            )
        )

    if isinstance(subtitulo, ft.Control):
        sub_ctrl = subtitulo
    elif subtitulo:
        sub_ctrl = ft.Text(
            str(subtitulo),
            color=T.TEXT_MUTED,
            size=9.5 if is_mob else 11,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
    else:
        sub_ctrl = ft.Container(height=0)

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
                        size=11 if is_mob else 12,
                        weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS,
                        expand=True,
                    ),
                    ft.Row(spacing=3 if is_mob else 4, tight=True, controls=icone_direita),
                ],
            ),
            ft.Container(height=3 if is_mob else 8),
            v_ctrl,
            sub_ctrl,
        ],
    )

    pad_final = pad(h=10, v=8) if is_mob else pad(all_=16)

    card = clickable_card(
        content=corpo,
        on_click=on_click,
        col=col or {"xs": 6, "sm": 6, "md": 3},
        padding=pad_final,
        border_radius=12 if is_mob else 14,
        cor_destaque=cor,
        tooltip=tooltip or (f"Clique para abrir detalhes de {titulo}" if on_click else None),
        bgcolor=f"{cor}10" if ativo else T.SURFACE,
    )
    if ativo:
        card.border = borda(1.5, cor)
    return card
