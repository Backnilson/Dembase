"""
=============================================================================
DemBase v3 — views/widgets/report/kpi_strip.py  (Flet 1.0.1)
Faixa responsiva de KPIs clicáveis para o topo dos relatórios:
- Telas pequenas/Mobile: grade 2x2 compacta (xs=6, sm=6).
- Telas grandes/Desktop: grade normal 1x4 (md=3).
=============================================================================
"""
from __future__ import annotations

import flet as ft
from core import theme as T
from views.widgets.clickable_card import kpi_clicavel


def criar_kpi_strip(
    *args,
    **kwargs,
) -> ft.ResponsiveRow:
    """
    Recebe lista de dicts com flexibilidade total de chamada:
    - criar_kpi_strip(itens, mobile=False)
    - criar_kpi_strip(page, itens, mobile=False)
    - criar_kpi_strip(itens=itens, mobile=mobile)

    Cada item no dict pode ter:
    {
        "titulo": str,
        "valor_ctrl": ft.Text (ou "valor": str),
        "cor": str,
        "icone": ft.IconData,
        "subtitulo": str (opcional),
        "on_click": Callable (opcional),
        "ativo": bool (opcional),
        "col": dict (opcional),
    }
    """
    arg_list = list(args)
    if arg_list and (isinstance(arg_list[0], ft.Page) or hasattr(arg_list[0], "views") or hasattr(arg_list[0], "route")):
        arg_list.pop(0)

    if arg_list:
        itens = arg_list[0]
        mobile = arg_list[1] if len(arg_list) > 1 else kwargs.get("mobile", False)
    else:
        itens = kwargs.get("itens", [])
        mobile = kwargs.get("mobile", False)

    cards: list[ft.Control] = []
    for item in itens:
        v_ctrl = item.get("valor_ctrl")
        if v_ctrl is None:
            v_val = str(item.get("valor") or "R$ 0,00")
            v_cor = item.get("cor") or T.TEXT_PRIMARY
            v_ctrl = ft.Text(
                v_val,
                color=v_cor,
                size=15 if mobile else 18,
                weight=ft.FontWeight.BOLD,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )

        cards.append(
            kpi_clicavel(
                titulo=item["titulo"],
                valor_ctrl=v_ctrl,
                cor=item.get("cor") or T.PRIMARY,
                icone=item.get("icone") or ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                subtitulo=item.get("subtitulo", ""),
                on_click=item.get("on_click"),
                mobile=mobile,
                col=item.get("col", {"xs": 6, "sm": 6, "md": 3}),
                ativo=bool(item.get("ativo", False)),
                tooltip=item.get("tooltip"),
                compacto=mobile,
            )
        )

    return ft.ResponsiveRow(
        spacing=8 if mobile else 12,
        run_spacing=8 if mobile else 12,
        controls=cards,
    )
