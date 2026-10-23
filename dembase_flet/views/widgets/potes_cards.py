"""
=============================================================================
DemBase v3 — views/widgets/potes_cards.py  (Flet 1.0.1)
Cards do Dashboard: Gasto vs Previsto de cada um dos 6 potes.
Apenas apresentação — recebe o dict de db.obter_resumo_potes().
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_moeda

COR_EXCEDIDO = "#DC2626"


def _pct_br(valor: float) -> str:
    return f"{valor:.2f}%".replace(".", ",")


def _badge(texto: str, cor: str, bg: str = None) -> ft.Container:
    return ft.Container(
        content=ft.Text(texto, color=cor, size=11, weight=ft.FontWeight.W_600),
        padding=pad(h=10, v=3),
        border_radius=20,
        bgcolor=bg or f"{cor}22",
        border=borda(color=f"{cor}55"),
    )


def _caixa_valor(rotulo: str, valor: float, cor_valor: str) -> ft.Container:
    return ft.Container(
        expand=True,
        padding=pad(h=12, v=8),
        bgcolor=T.SURFACE_ALT,
        border_radius=10,
        border=borda(),
        content=ft.Column(spacing=2, controls=[
            ft.Text(rotulo, color=T.TEXT_MUTED, size=10, weight=ft.FontWeight.W_600),
            ft.Text(formatar_moeda(valor), color=cor_valor, size=14, weight=ft.FontWeight.BOLD),
        ]),
    )


def card_pote(pote: dict, on_click=None) -> ft.Container:
    gasto = float(pote.get("gasto") or 0)
    previsto = float(pote.get("previsto") or 0)
    restante = previsto - gasto
    qtd = int(pote.get("qtd_transacoes") or 0)
    cor_pote = pote.get("cor") or T.PRIMARY

    excedido = gasto > previsto
    sem_gastos = gasto == 0
    pct = (gasto / previsto * 100) if previsto > 0 else (100.0 if gasto > 0 else 0.0)

    if excedido:
        cor_barra, cor_valor = COR_EXCEDIDO, COR_EXCEDIDO
        badge = _badge("Excedido", COR_EXCEDIDO)
        borda_card = borda(color=f"{COR_EXCEDIDO}80")
    elif sem_gastos:
        cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
        badge = _badge("Sem gastos", T.TEXT_MUTED, bg=T.SURFACE_ALT)
        borda_card = borda()
    else:
        cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
        badge = _badge(_pct_br(pct), T.TEXT_PRIMARY, bg=T.SURFACE_ALT)
        borda_card = borda()

    if restante > 0:
        txt_restante = ft.Text(f"+{formatar_moeda(restante)} restante", color=T.RECEITA, size=11)
    elif excedido:
        txt_restante = ft.Text(f"{formatar_moeda(abs(restante))} acima", color=COR_EXCEDIDO, size=11)
    else:
        txt_restante = ft.Text(f"{formatar_moeda(0)} restante", color=T.TEXT_MUTED, size=11)

    rotulo_qtd = "transação" if qtd == 1 else "transações"

    return ft.Container(
        col={"xs": 12, "sm": 6, "md": 4},
        padding=pad(all_=16),
        bgcolor=T.SURFACE,
        border_radius=14,
        border=borda_card,
        on_click=on_click,
        ink=bool(on_click),
        content=ft.Column(spacing=12, controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Container(width=10, height=10, bgcolor=cor_pote, border_radius=5),
                        ft.Text(pote.get("nome", ""), color=T.TEXT_PRIMARY, size=14,
                                weight=ft.FontWeight.BOLD),
                    ]),
                    badge,
                ],
            ),
            ft.ProgressBar(
                value=min(pct / 100.0, 1.0),
                bar_height=8,
                color=cor_barra,
                bgcolor=T.SURFACE_ALT,
                border_radius=4,
            ),
            ft.Row(spacing=10, controls=[
                _caixa_valor("GASTO", gasto, cor_valor),
                _caixa_valor("PREVISTO", previsto, T.TEXT_PRIMARY),
            ]),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    txt_restante,
                    ft.Row(spacing=4, tight=True, controls=[
                        ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, color=T.TEXT_MUTED, size=14),
                        ft.Text(f"{qtd} {rotulo_qtd}", color=T.TEXT_MUTED, size=11),
                    ]),
                ],
            ),
        ]),
    )


def secao_potes(resumo: dict, nav_func=None, on_ajustar=None) -> ft.Column:
    """Seção 'Metas financeiras' com os cards dos 6 potes."""
    potes = resumo.get("potes") or []
    sem_pote = resumo.get("sem_pote") or {}

    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.END,
        controls=[
            ft.Column(spacing=2, controls=[
                ft.Text("Metas financeiras", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                ft.Text("Distribuição da sua renda mensal por pote", color=T.TEXT_MUTED, size=12),
            ]),
            ft.TextButton(
                content=ft.Text("Ajustar metas ›", color=T.WARNING, size=12, weight=ft.FontWeight.W_600),
                on_click=on_ajustar,
            ) if on_ajustar else ft.Container(),
        ],
    )

    cards = ft.ResponsiveRow(
        spacing=14, run_spacing=14,
        controls=[
            card_pote(p, (lambda _, pid=p.get("id"): nav_func(pid)) if nav_func else None)
            for p in potes
        ],
    )

    controles = [cabecalho, ft.Container(height=12), cards]

    qtd_sem = int(sem_pote.get("qtd") or 0)
    if qtd_sem > 0:
        controles += [
            ft.Container(height=12),
            ft.Container(
                padding=pad(h=16, v=12),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(color=f"{T.WARNING}66"),
                content=ft.Row(spacing=10, controls=[
                    ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=T.WARNING, size=18),
                    ft.Text(
                        f"{qtd_sem} despesa(s) sem pote — {formatar_moeda(float(sem_pote.get('total') or 0))}",
                        color=T.TEXT_PRIMARY, size=12, expand=True,
                    ),
                ]),
            ),
        ]

    return ft.Column(spacing=0, controls=controles)
