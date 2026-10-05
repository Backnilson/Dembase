"""
=============================================================================
DemBase v3 — views/widgets/auth/brand_panel.py (Flet 1.0.1)
Painel institucional de marca para Desktop (lado esquerdo da tela dividida).
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda


def criar_painel_marca() -> ft.Container:
    """
    Retorna o painel de boas-vindas com a identidade visual da DemBase,
    brilho neon sutil e os pilares de valor do produto.
    """
    def _diferencial_item(icone, titulo: str, desc: str) -> ft.Row:
        return ft.Row(
            spacing=16,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(
                    width=42,
                    height=42,
                    bgcolor=f"{T.NEON}18",
                    border_radius=12,
                    border=borda(width=1, color=f"{T.NEON}40"),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(icone, color=T.NEON, size=22),
                ),
                ft.Column(
                    spacing=2,
                    expand=True,
                    controls=[
                        ft.Text(titulo, color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.W_700),
                        ft.Text(desc, color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_400),
                    ],
                ),
            ],
        )

    conteudo = ft.Column(
        spacing=32,
        alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.START,
        controls=[
            # Logo grande com destaque
            ft.Row(
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Image(src="logo.svg", width=72, height=72, fit=ft.BoxFit.CONTAIN),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Row(
                                spacing=4,
                                controls=[
                                    ft.Text("DemBase", color=T.TEXT_PRIMARY, size=32, weight=ft.FontWeight.W_900),
                                    ft.Container(width=8, height=8, bgcolor=T.NEON, border_radius=4, margin=pad(top=16)),
                                ],
                            ),
                            ft.Text("Controle Financeiro Premium", color=T.TEXT_MUTED, size=13, weight=ft.FontWeight.W_500),
                        ],
                    ),
                ],
            ),
            # Slogan
            ft.Column(
                spacing=6,
                controls=[
                    ft.Text(
                        "Sua vida financeira\nem perfeita harmonia.",
                        color=T.TEXT_PRIMARY,
                        size=28,
                        weight=ft.FontWeight.W_800,
                        height=1.2,
                    ),
                    ft.Text(
                        "Controle gastos, acompanhe sua regra orçamentária e tome decisões com clareza absoluta.",
                        color=T.TEXT_MUTED,
                        size=14,
                        height=1.4,
                    ),
                ],
            ),
            # Lista de Diferenciais
            ft.Container(
                padding=pad(v=10),
                content=ft.Column(
                    spacing=20,
                    controls=[
                        _diferencial_item(
                            ft.Icons.PIE_CHART_OUTLINE_ROUNDED,
                            "Regra Orçamentária 50/30/20",
                            "Distribuição inteligente entre essenciais, estilo de vida e investimentos.",
                        ),
                        _diferencial_item(
                            ft.Icons.DATE_RANGE_ROUNDED,
                            "Filtros de Datas Flexíveis",
                            "Analise qualquer período personalizado sem amarras de mês fechado.",
                        ),
                        _diferencial_item(
                            ft.Icons.SHIELD_OUTLINED,
                            "Segurança em Nuvem",
                            "Seus dados seguros com infraestrutura PostgreSQL de alta disponibilidade.",
                        ),
                    ],
                ),
            ),
        ],
    )

    return ft.Container(
        expand=1,
        padding=pad(all_=48),
        alignment=ft.Alignment(0, 0),
        bgcolor=T.SURFACE if T.IS_DARK else "#F1F5F9",
        border=ft.Border(right=ft.BorderSide(1, T.BORDER)),
        content=ft.Stack(
            controls=[
                # Glow de fundo sutil
                ft.Container(
                    width=300,
                    height=300,
                    top=-40,
                    left=-40,
                    bgcolor=f"{T.NEON}08",
                    border_radius=150,
                ),
                conteudo,
            ],
        ),
    )
