"""
=============================================================================
DemBase v3 — views/widgets/regra_5030.py  (Flet 1.0 compatible)
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_moeda, REGRAS_META


def _barra(label: str, gasto: float, orcamento: float, percentual: float, meta: float, on_click=None) -> ft.Container:
    if percentual <= meta * 100:
        cor = T.PRIMARY
    elif percentual <= (meta * 100) + 5:
        cor = T.WARNING
    else:
        cor = T.DESPESA

    progresso = min(percentual / 100.0, 1.0)

    return ft.Container(
        on_click=on_click,
        ink=True if on_click else False,
        padding=pad(all_=5),
        border_radius=8,
        content=ft.Column(
            spacing=6,
            controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                        ft.Text(label, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_500),
                    ]),
                    ft.Row(spacing=4, controls=[
                        ft.Text(formatar_moeda(gasto), color=cor, size=13, weight=ft.FontWeight.BOLD),
                        ft.Text(f"de {formatar_moeda(orcamento)}", color=T.TEXT_MUTED, size=12),
                        ft.Container(
                            content=ft.Text(f"{percentual:.1f}%", color=cor, size=11, weight=ft.FontWeight.W_600),
                            bgcolor=f"{cor}22", border_radius=20,
                            padding=pad(h=8, v=3),
                        ),
                    ]),
                ],
            ),
            ft.ProgressBar(value=progresso, bgcolor=T.SURFACE_ALT, color=cor, height=8, border_radius=4),
        ],
    ))


def secao_regra_5030(dados: dict, nav_func=None) -> ft.Container:
    receita = float(dados.get("receita_total", 0) or 0)

    def ex(chave):
        b = dados.get(chave, {}) or {}
        return (
            float(b.get("gasto", 0) or 0),
            float(b.get("orcamento", 0) or 0),
            float(b.get("percentual_usado", 0) or 0),
        )

    ge, oe, pe = ex("essencial")
    gs, os_, ps = ex("estilo_vida")
    gi, oi, pi = ex("investimento")

    return ft.Container(
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
                        ft.Row(spacing=8, controls=[
                            ft.Icon(ft.Icons.PIE_CHART_OUTLINE_ROUNDED, color=T.TEXT_PRIMARY, size=20),
                            ft.Text("Regra 50/30/20", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                        ]),
                        ft.Column(spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END, controls=[
                            ft.Text("Baseado em", color=T.TEXT_MUTED, size=11),
                            ft.Text(formatar_moeda(receita), color=T.RECEITA, size=13, weight=ft.FontWeight.BOLD),
                        ]),
                    ],
                ),
                ft.Container(height=20),
                _barra("Essencial (50%)",      ge, oe, pe, REGRAS_META["Essencial"], lambda _: nav_func("Essencial") if nav_func else None),
                ft.Divider(color=T.BORDER, height=20),
                _barra("Estilo de Vida (30%)", gs, os_, ps, REGRAS_META["Estilo de Vida"], lambda _: nav_func("Estilo de Vida") if nav_func else None),
                ft.Divider(color=T.BORDER, height=20),
                _barra("Investimento (20%)",   gi, oi, pi, REGRAS_META["Investimento"], lambda _: nav_func("Investimento") if nav_func else None),
            ],
        ),
    )
