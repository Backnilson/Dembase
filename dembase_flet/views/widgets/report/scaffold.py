"""
=============================================================================
DemBase v3 — views/widgets/report/scaffold.py  (Flet 1.0.1)
Esqueleto visual unificado para todos os relatórios (ReportScaffold) +
componentes analíticos reutilizáveis (ranking clicável de categorias,
evolução diária/saldo).
=============================================================================
"""
from __future__ import annotations

from typing import Any, Callable
import inspect
import flet as ft

from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_moeda


class ReportScaffold(ft.Column):
    """
    Esqueleto padronizado para relatórios no DemBase:
    Header (com breadcrumb + voltar + acoes_header)
    -> Hero opcional (ex: card da Conta ou Cartão)
    -> FilterBar opcional
    -> Loading Indicator (visível enquanto carrega em background)
    -> Conteúdo final (KpiStrip, Seção de Gráficos, Lista de Lançamentos)
    """

    def __init__(
        self,
        header: ft.Control,
        kpi_strip: ft.Control | None = None,
        graficos_row: ft.Control | None = None,
        transaction_list: ft.Control | None = None,
        filter_bar: ft.Control | None = None,
        hero_banner: ft.Control | None = None,
        secao_extra: ft.Control | None = None,
        loading: bool = False,
        loading_text: str = "Carregando relatório...",
    ):
        self.loading = loading
        self.header = header
        self.hero_banner = hero_banner
        self.filter_bar = filter_bar
        self.kpi_strip = kpi_strip
        self.secao_extra = secao_extra
        self.graficos_row = graficos_row
        self.transaction_list = transaction_list

        self.corpo_loading = ft.Container(
            alignment=ft.Alignment(0, 0),
            padding=pad(all_=50),
            content=ft.Column(
                spacing=14,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.ProgressRing(color=T.PRIMARY, width=34, height=34, stroke_width=3),
                    ft.Text(loading_text, color=T.TEXT_MUTED, size=13, weight=ft.FontWeight.W_500),
                ],
            ),
            visible=loading,
        )

        conteudo_inicial = [c for c in [kpi_strip, secao_extra, graficos_row, transaction_list] if c is not None]
        self.corpo_conteudo = ft.Column(
            spacing=14,
            visible=not loading,
            controls=conteudo_inicial,
        )

        blocos: list[ft.Control] = [header]
        if hero_banner is not None:
            blocos.append(hero_banner)
        if filter_bar is not None:
            blocos.append(filter_bar)
        blocos.append(self.corpo_loading)
        blocos.append(self.corpo_conteudo)
        blocos.append(ft.Container(height=28))

        super().__init__(
            spacing=14,
            controls=blocos,
        )

        if hasattr(self, "_dirty"):
            self._dirty.clear()

    def set_loading(self, carregando: bool, page: ft.Page | None = None):
        """Alterna imediatamente entre o indicador de progresso e o conteúdo final."""
        self.loading = carregando
        self.corpo_loading.visible = carregando
        self.corpo_conteudo.visible = not carregando
        if page is not None:
            try:
                page.update()
            except Exception:
                pass

    def atualizar_corpo(
        self,
        kpi_strip: ft.Control | None = None,
        graficos_row: ft.Control | None = None,
        transaction_list: ft.Control | None = None,
        secao_extra: ft.Control | None = None,
        page: ft.Page | None = None,
    ):
        """Atualiza os controles do corpo analítico quando os dados retornam em background."""
        if kpi_strip is not None:
            self.kpi_strip = kpi_strip
        if graficos_row is not None:
            self.graficos_row = graficos_row
        if transaction_list is not None:
            self.transaction_list = transaction_list
        if secao_extra is not None:
            self.secao_extra = secao_extra

        self.corpo_conteudo.controls = [
            c for c in [self.kpi_strip, self.secao_extra, self.graficos_row, self.transaction_list]
            if c is not None
        ]
        if page is not None:
            try:
                page.update()
            except Exception:
                pass


def _invocar_callback_categoria(cb: Callable | None, cat: dict, cat_id: Any) -> None:
    """Invoca o callback de categoria com tolerância a assinaturas (1 ou 2 parâmetros)."""
    if not cb:
        return
    try:
        sig = inspect.signature(cb)
        params = [
            p for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if len(params) >= 2:
            cb(cat_id, cat)
            return
        if len(params) == 1:
            p_name = params[0].name.lower()
            if p_name in ("cid", "cat_id", "categoria_id", "id"):
                cb(cat_id)
            else:
                cb(cat)
            return
    except Exception:
        pass

    try:
        cb(cat)
    except TypeError:
        try:
            cb(cat_id, cat)
        except TypeError:
            cb(cat_id)


def _invocar_callback_pote(cb: Callable | None, pote: dict, pote_id: Any) -> None:
    """Invoca o callback de pote com tolerância a assinaturas (1 ou 2 parâmetros)."""
    if not cb:
        return
    try:
        sig = inspect.signature(cb)
        params = [
            p for p in sig.parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if len(params) >= 2:
            cb(pote_id, pote)
            return
        if len(params) == 1:
            p_name = params[0].name.lower()
            if p_name in ("pid", "pote_id", "id"):
                cb(pote_id)
            else:
                cb(pote)
            return
    except Exception:
        pass

    try:
        cb(pote)
    except TypeError:
        try:
            cb(pote_id, pote)
        except TypeError:
            cb(pote_id)


def construir_card_ranking_categorias(
    categorias: list[dict],
    titulo: str = "Ranking por Categoria",
    subtitulo: str = "Clique em uma categoria para aprofundar a análise",
    cor_padrao: str | None = None,
    on_click_categoria: Callable[[dict], None] | None = None,
    on_categoria_click: Callable | None = None,
    col: dict | None = None,
) -> ft.Container:
    """
    Card analítico que exibe barra segmentada + lista de categorias com percentual,
    valor e clique para drill-down (/relatorios/categoria/<id>).
    """
    cb_categoria = on_click_categoria or on_categoria_click
    cor_base = cor_padrao or T.PRIMARY
    linhas: list[ft.Control] = []

    if not categorias:
        linhas.append(
            ft.Container(
                padding=pad(v=24, h=12),
                alignment=ft.Alignment(0, 0),
                content=ft.Text("Sem categorias movimentadas no período.", color=T.TEXT_MUTED, size=12.5),
            )
        )
    else:
        for cat in categorias[:10]:
            nome = cat.get("nome") or cat.get("categoria") or "Sem Categoria"
            cor = cat.get("cor") or cor_base
            total = float(cat.get("total") or cat.get("valor") or 0)
            perc = float(cat.get("percentual") or 0)
            qtd = int(cat.get("qtd") or 0)
            cat_id = cat.get("categoria_id") or cat.get("id")
            clicavel = bool(cb_categoria and cat_id)

            linhas.append(
                ft.Container(
                    padding=pad(h=12, v=9),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=10,
                    on_click=(lambda _, c=cat, cid=cat_id: _invocar_callback_categoria(cb_categoria, c, cid)) if clicavel else None,
                    ink=clicavel,
                    tooltip=f"Ver relatório da categoria {nome}" if clicavel else None,
                    content=ft.Column(
                        spacing=5,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                                            ft.Text(nome, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                                            ft.Text(f"({qtd})", color=T.TEXT_MUTED, size=11) if qtd > 0 else ft.Container(),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=6,
                                        controls=[
                                            ft.Text(f"{perc:.1f}%", color=T.TEXT_MUTED, size=11),
                                            ft.Text(formatar_moeda(total), color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, size=15, color=T.TEXT_MUTED)
                                            if clicavel
                                            else ft.Container(),
                                        ],
                                    ),
                                ],
                            ),
                            ft.ProgressBar(
                                value=min(1.0, max(0.0, perc / 100.0)),
                                color=cor,
                                bgcolor=f"{T.BORDER}50",
                                height=5,
                                border_radius=3,
                            ),
                        ],
                    ),
                )
            )

    return ft.Container(
        col=col or {"xs": 12, "md": 6},
        padding=pad(all_=18),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.DONUT_LARGE_ROUNDED, color=cor_base, size=18),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(titulo, color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(subtitulo, color=T.TEXT_MUTED, size=11),
                            ],
                        ),
                    ],
                ),
                ft.Divider(height=1, color=T.BORDER),
                *linhas,
            ],
        ),
    )


def construir_card_evolucao_diaria(
    por_dia: list[dict],
    titulo: str = "Evolução Diária no Período",
    subtitulo: str = "Toque em um dia para filtrar os lançamentos daquela data",
    modo_saldo: bool = False,
    on_click_dia: Callable[[str], None] | None = None,
    on_dia_click: Callable | None = None,
    col: dict | None = None,
) -> ft.Container:
    cb_dia = on_click_dia or on_dia_click
    """
    Histograma / curva de barras interativa dia a dia para relatórios gerais
    ou evolução de saldo de conta bancária.
    """
    if not por_dia:
        corpo = ft.Container(
            padding=pad(v=24, h=12),
            alignment=ft.Alignment(0, 0),
            content=ft.Text("Sem movimentações diárias no intervalo.", color=T.TEXT_MUTED, size=12.5),
        )
    else:
        amostra = por_dia[-14:]
        ALTURA_MAX = 110
        barras: list[ft.Control] = []

        if modo_saldo:
            vals = [abs(float(d.get("saldo", 0) or 0)) for d in amostra] + [1.0]
            max_v = max(vals)
            for d in amostra:
                saldo_v = float(d.get("saldo", 0) or 0)
                lbl = d.get("label") or str(d.get("data", ""))[-5:]
                dt_iso = str(d.get("data") or "")[:10]
                h_bar = max(6, int((abs(saldo_v) / max_v) * ALTURA_MAX))
                cor_b = T.PRIMARY if saldo_v >= 0 else T.DESPESA
                barras.append(
                    ft.Container(
                        expand=True,
                        on_click=(lambda _, dt=dt_iso: cb_dia(dt)) if cb_dia and dt_iso else None,
                        ink=bool(cb_dia),
                        tooltip=f"{lbl}: Saldo {formatar_moeda(saldo_v)}",
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.END,
                            spacing=4,
                            controls=[
                                ft.Container(
                                    height=ALTURA_MAX + 6,
                                    alignment=ft.Alignment(0, 1),
                                    content=ft.Container(
                                        width=12,
                                        height=h_bar,
                                        bgcolor=cor_b,
                                        border_radius=4,
                                    ),
                                ),
                                ft.Text(lbl.split("/")[0], color=T.TEXT_MUTED, size=10),
                            ],
                        ),
                    )
                )
        else:
            max_v = max(
                [
                    max(
                        float(d.get("receitas", 0) or 0),
                        float(d.get("despesas", 0) or 0),
                        float(d.get("total", 0) or 0),
                    )
                    for d in amostra
                ]
                + [1.0]
            )
            for d in amostra:
                rec = float(d.get("receitas", 0) or 0)
                desp = float(d.get("despesas", 0) or 0)
                lbl = d.get("label") or str(d.get("data", ""))[-5:]
                dt_iso = str(d.get("data") or "")[:10]
                h_rec = max(4, int((rec / max_v) * ALTURA_MAX)) if rec > 0 else 3
                h_desp = max(4, int((desp / max_v) * ALTURA_MAX)) if desp > 0 else 3
                barras.append(
                    ft.Container(
                        expand=True,
                        on_click=(lambda _, dt=dt_iso: cb_dia(dt)) if cb_dia and dt_iso else None,
                        ink=bool(cb_dia),
                        tooltip=f"{lbl}\nReceitas: {formatar_moeda(rec)}\nDespesas: {formatar_moeda(desp)}",
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.END,
                            spacing=4,
                            controls=[
                                ft.Container(
                                    height=ALTURA_MAX + 6,
                                    alignment=ft.Alignment(0, 1),
                                    content=ft.Row(
                                        spacing=2,
                                        tight=True,
                                        vertical_alignment=ft.CrossAxisAlignment.END,
                                        controls=[
                                            ft.Container(
                                                width=7,
                                                height=h_rec,
                                                bgcolor=T.RECEITA if rec > 0 else f"{T.BORDER}40",
                                                border_radius=3,
                                            ),
                                            ft.Container(
                                                width=7,
                                                height=h_desp,
                                                bgcolor=T.DESPESA if desp > 0 else f"{T.BORDER}40",
                                                border_radius=3,
                                            ),
                                        ],
                                    ),
                                ),
                                ft.Text(lbl.split("/")[0], color=T.TEXT_MUTED, size=10),
                            ],
                        ),
                    )
                )

        corpo = ft.Container(
            padding=pad(h=10, v=12),
            bgcolor=T.SURFACE_ALT,
            border_radius=12,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.END,
                controls=barras,
            ),
        )

    return ft.Container(
        col=col or {"xs": 12, "md": 6},
        padding=pad(all_=18),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.SHOW_CHART_ROUNDED if modo_saldo else ft.Icons.EQUALIZER_ROUNDED, color=T.PRIMARY, size=18),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(titulo, color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(subtitulo, color=T.TEXT_MUTED, size=11),
                            ],
                        ),
                    ],
                ),
                ft.Divider(height=1, color=T.BORDER),
                corpo,
            ],
        ),
    )


def construir_card_ranking_potes(
    potes: list[dict],
    titulo: str = "Participação por Pote",
    subtitulo: str = "Toque em um pote para filtrar os lançamentos dele",
    cor_padrao: str | None = None,
    on_click_pote: Callable[[dict], None] | None = None,
    on_pote_click: Callable | None = None,
    pote_selecionado_id: str | None = None,
    col: dict | None = None,
) -> ft.Container:
    """
    Card analítico dos 6 Potes Financeiros:
    Exibe barra de progresso colorida, nome, percentual e valor total gasto/filtrado.
    Destaca visualmente o pote filtrado.
    """
    cb_pote = on_click_pote or on_pote_click
    cor_base = cor_padrao or T.PRIMARY
    linhas: list[ft.Control] = []

    if not potes:
        linhas.append(
            ft.Container(
                padding=pad(v=24, h=12),
                alignment=ft.Alignment(0, 0),
                content=ft.Text("Sem movimentações por pote no período.", color=T.TEXT_MUTED, size=12.5),
            )
        )
    else:
        for p in potes:
            nome = p.get("nome") or "Sem Pote"
            cor = p.get("cor") or cor_base
            total = float(p.get("total") or 0)
            perc = float(p.get("percentual") or 0)
            qtd = int(p.get("qtd") or 0)
            pote_id = p.get("pote_id") or p.get("id")
            clicavel = bool(cb_pote and pote_id)
            pote_id_str = str(pote_id or "")
            sel_id_str = str(pote_selecionado_id or "")
            is_selecionado = bool(sel_id_str and pote_id_str == sel_id_str)

            controles_badge: list[ft.Control] = [
                ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                ft.Text(nome, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD if is_selecionado else ft.FontWeight.W_600),
            ]
            if qtd > 0:
                controles_badge.append(ft.Text(f"({qtd})", color=T.TEXT_MUTED, size=11))
            if is_selecionado:
                controles_badge.append(
                    ft.Container(
                        padding=pad(h=6, v=2),
                        bgcolor=f"{cor}30",
                        border_radius=6,
                        content=ft.Text("Filtrado ✕", size=10, color=cor, weight=ft.FontWeight.BOLD),
                    )
                )

            linhas.append(
                ft.Container(
                    padding=pad(h=12, v=9),
                    bgcolor=f"{cor}18" if is_selecionado else T.SURFACE_ALT,
                    border=borda(1.5, cor) if is_selecionado else borda(1, f"{T.BORDER}40"),
                    border_radius=10,
                    on_click=(lambda _, pt=p, pid=pote_id: _invocar_callback_pote(cb_pote, pt, pid)) if clicavel else None,
                    ink=clicavel,
                    tooltip=f"Pote {nome} selecionado. Toque para remover o filtro" if is_selecionado else (f"Filtrar lançamentos do pote {nome}" if clicavel else None),
                    content=ft.Column(
                        spacing=5,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=controles_badge,
                                    ),
                                    ft.Row(
                                        spacing=6,
                                        controls=[
                                            ft.Text(f"{perc:.1f}%", color=T.TEXT_MUTED, size=11),
                                            ft.Text(formatar_moeda(total), color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                                            ft.Icon(
                                                ft.Icons.CHECK_CIRCLE_ROUNDED if is_selecionado else ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                                size=15,
                                                color=cor if is_selecionado else T.TEXT_MUTED,
                                            )
                                            if clicavel
                                            else ft.Container(),
                                        ],
                                    ),
                                ],
                            ),
                            ft.ProgressBar(
                                value=min(1.0, max(0.0, perc / 100.0)),
                                color=cor,
                                bgcolor=f"{T.BORDER}50",
                                height=5,
                                border_radius=3,
                            ),
                        ],
                    ),
                )
            )

    return ft.Container(
        col=col or {"xs": 12, "md": 6},
        padding=pad(all_=18),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.ALL_INBOX_ROUNDED, color=cor_base, size=18),
                        ft.Column(
                            spacing=1,
                            controls=[
                                ft.Text(titulo, color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD),
                                ft.Text(subtitulo, color=T.TEXT_MUTED, size=11),
                            ],
                        ),
                    ],
                ),
                ft.Divider(height=1, color=T.BORDER),
                *linhas,
            ],
        ),
    )
