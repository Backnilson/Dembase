"""
=============================================================================
DemBase v3 — views/widgets/report/kpi_strip.py  (Flet 1.0.1)
Faixa responsiva de KPIs clicáveis para o topo dos relatórios (2x2 no Mobile,
1x4 no Desktop).
=============================================================================
"""
from __future__ import annotations

import flet as ft
from views.widgets.clickable_card import kpi_clicavel


def criar_kpi_strip(
    itens: list[dict],
    mobile: bool = False,
) -> ft.ResponsiveRow:
    """
    Recebe lista de dicts:
    [
        {
            "titulo": str,
            "valor_ctrl": ft.Text,
            "cor": str,
            "icone": ft.IconData,
            "subtitulo": str (opcional),
            "on_click": Callable (opcional),
            "ativo": bool (opcional),
            "col": dict (opcional),
        },
        ...
    ]
    """
    cards: list[ft.Control] = []
    for item in itens:
        cards.append(
            kpi_clicavel(
                titulo=item["titulo"],
                valor_ctrl=item["valor_ctrl"],
                cor=item["cor"],
                icone=item["icone"],
                subtitulo=item.get("subtitulo", ""),
                on_click=item.get("on_click"),
                mobile=mobile,
                col=item.get("col", {"xs": 6, "sm": 6, "md": 3}),
                ativo=bool(item.get("ativo", False)),
                tooltip=item.get("tooltip"),
            )
        )

    return ft.ResponsiveRow(
        spacing=10 if mobile else 14,
        run_spacing=10 if mobile else 14,
        controls=cards,
    )
