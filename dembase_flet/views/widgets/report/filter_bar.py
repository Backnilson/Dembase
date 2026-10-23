"""
=============================================================================
DemBase v3 — views/widgets/report/filter_bar.py  (Flet 1.0.1)
Barra de filtros interativa para relatórios:
- Chips rápidos horizontais: Todos (Receita+Despesa), Receitas, Despesas,
  Transferências, Pagos, Pendentes + botão "Filtros (n)".
- Busca textual rápida.
- Pílulas de filtros ativos removíveis (ex: "Conta: Nubank ✕").
- Modal/BottomSheet(scrollable=True) de filtros avançados (Flet 1.0.1).
=============================================================================
"""
from __future__ import annotations

from typing import Callable
import flet as ft

from core import theme as T
from core.theme import pad, borda
from core.constants import REGRAS_5030, FORMAS_DESPESA
from core.responsive import is_mobile
from core.report_context import ReportContext
import services.supabase_client as db


class FilterBar(ft.Column):
    """
    Componente reativo de filtragem para relatórios (Flet 1.0.1).
    Notifica on_change(novo_ctx: ReportContext) sempre que um filtro muda in-place.
    """

    def __init__(
        self,
        page: ft.Page,
        ctx: ReportContext,
        on_change: Callable[[ReportContext], None],
        mostrar_chips_tipo: bool = True,
        fixar_conta: bool = False,
        fixar_cartao: bool = False,
        fixar_categoria: bool = False,
        fixar_regra: bool = False,
        fixar_pote: bool = False,
    ):
        self._page = page
        self.ctx = ctx
        self.on_change = on_change
        self.mostrar_chips_tipo = mostrar_chips_tipo
        self.fixar_conta = fixar_conta
        self.fixar_cartao = fixar_cartao
        self.fixar_categoria = fixar_categoria
        self.fixar_regra = fixar_regra
        self.fixar_pote = fixar_pote
        self.mobile = is_mobile(page)

        self.contas_cache: list[dict] = []
        self.cartoes_cache: list[dict] = []
        self.categorias_cache: list[dict] = []
        self.potes_cache: list[dict] = []

        self._carregar_metadados()

        self.row_chips = ft.Row(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.row_ativos = ft.Row(
            spacing=6,
            wrap=True,
            visible=False,
        )
        estilo_busca = dict(T.campo_estilo())
        estilo_busca["content_padding"] = pad(h=12, v=8)

        self.txt_busca = ft.TextField(
            hint_text="Buscar descrição, subtipo ou categoria...",
            value=self.ctx.busca or "",
            prefix_icon=ft.Icons.SEARCH_ROUNDED,
            width=260 if not self.mobile else None,
            expand=self.mobile,
            height=40,
            on_submit=self._ao_submeter_busca,
            **estilo_busca,
        )

        self._popular_chips()
        self._popular_pilulas_ativas()

        if self.mobile:
            layout_topo = ft.Column(
                spacing=8,
                controls=[
                    self.row_chips,
                    ft.Row(
                        spacing=8,
                        controls=[
                            self.txt_busca,
                            ft.IconButton(
                                icon=ft.Icons.CHECK_ROUNDED,
                                icon_color=ft.Colors.WHITE,
                                bgcolor=T.PRIMARY,
                                icon_size=18,
                                width=40,
                                height=40,
                                tooltip="Buscar",
                                on_click=self._ao_submeter_busca,
                            ),
                        ],
                    ),
                ],
            )
        else:
            layout_topo = ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(expand=True, content=self.row_chips),
                    ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            self.txt_busca,
                            ft.IconButton(
                                icon=ft.Icons.SEARCH_ROUNDED,
                                icon_color=T.PRIMARY,
                                bgcolor=f"{T.PRIMARY}18",
                                icon_size=18,
                                tooltip="Aplicar busca",
                                on_click=self._ao_submeter_busca,
                            ),
                        ],
                    ),
                ],
            )

        super().__init__(
            spacing=8,
            controls=[
                ft.Container(
                    padding=pad(h=14, v=10),
                    bgcolor=T.SURFACE,
                    border_radius=14,
                    border=borda(),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            layout_topo,
                            self.row_ativos,
                        ],
                    ),
                )
            ],
        )

        if hasattr(self, "_dirty"):
            self._dirty.clear()

    def _carregar_metadados(self):
        try:
            self.contas_cache = db.listar_contas() or []
        except Exception:
            self.contas_cache = []
        try:
            self.cartoes_cache = db.listar_cartoes() or []
        except Exception:
            self.cartoes_cache = []
        try:
            self.categorias_cache = db.listar_categorias() or []
        except Exception:
            self.categorias_cache = []
        try:
            self.potes_cache = db.listar_potes() or []
        except Exception:
            self.potes_cache = []

    def atualizar_contexto(self, novo_ctx: ReportContext, emitir: bool = True):
        self.ctx = novo_ctx
        self.txt_busca.value = self.ctx.busca or ""
        self._popular_chips()
        self._popular_pilulas_ativas()
        try:
            self.update()
        except Exception:
            pass
        try:
            self._page.update()
        except Exception:
            pass
        if emitir and callable(self.on_change):
            self.on_change(self.ctx)

    def _ao_submeter_busca(self, _=None):
        val = (self.txt_busca.value or "").strip() or None
        self.atualizar_contexto(self.ctx.com(busca=val), emitir=True)

    def _chip_visual(
        self,
        label: str,
        ativo: bool,
        cor_ativa: str,
        on_click: Callable,
        icone=None,
    ) -> ft.Container:
        controles_row: list[ft.Control] = []
        if icone:
            controles_row.append(
                ft.Icon(icone, size=14, color=ft.Colors.WHITE if ativo else cor_ativa)
            )
        controles_row.append(
            ft.Text(
                label,
                size=12,
                weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                color=ft.Colors.WHITE if ativo else T.TEXT_PRIMARY,
            )
        )
        return ft.Container(
            padding=pad(h=12, v=7),
            bgcolor=cor_ativa if ativo else T.SURFACE_ALT,
            border_radius=18,
            border=borda(1, cor_ativa if ativo else T.BORDER),
            on_click=on_click,
            ink=True,
            content=ft.Row(spacing=5, tight=True, controls=controles_row),
        )

    def _popular_chips(self):
        self.row_chips.controls.clear()

        if self.mostrar_chips_tipo:
            opcoes_tipo = [
                (None, "Todos", T.PRIMARY, ft.Icons.ALL_INBOX_ROUNDED),
                ("Receita", "Receitas", T.RECEITA, ft.Icons.ARROW_UPWARD_ROUNDED),
                ("Despesa", "Despesas", T.DESPESA, ft.Icons.ARROW_DOWNWARD_ROUNDED),
                ("Transferência", "Transferências", T.INFO, ft.Icons.SWAP_HORIZ_ROUNDED),
            ]
            for valor_t, lbl_t, cor_t, ic_t in opcoes_tipo:
                ativo_t = (self.ctx.tipo == valor_t)
                self.row_chips.controls.append(
                    self._chip_visual(
                        lbl_t,
                        ativo_t,
                        cor_t,
                        lambda _, vt=valor_t: self.atualizar_contexto(self.ctx.com(tipo=vt)),
                        icone=ic_t,
                    )
                )

        # Chips de Status (Pago / Pendente)
        for st_val, st_lbl, st_cor, st_ic in [
            ("Pago", "Pagos", T.RECEITA, ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED),
            ("Pendente", "Pendentes", T.WARNING, ft.Icons.SCHEDULE_ROUNDED),
        ]:
            ativo_st = (self.ctx.status == st_val)
            novo_st = None if ativo_st else st_val
            self.row_chips.controls.append(
                self._chip_visual(
                    st_lbl,
                    ativo_st,
                    st_cor,
                    lambda _, ns=novo_st: self.atualizar_contexto(self.ctx.com(status=ns)),
                    icone=st_ic,
                )
            )

        # Botão de Filtros Avançados
        qtd_av = self.ctx.qtd_filtros_avancados()
        lbl_filtros = f"Filtros ({qtd_av})" if qtd_av > 0 else "Filtros"
        self.row_chips.controls.append(
            self._chip_visual(
                lbl_filtros,
                qtd_av > 0,
                T.PRIMARY,
                self._abrir_modal_filtros_avancados,
                icone=ft.Icons.FILTER_LIST_ROUNDED,
            )
        )

    def _nome_por_id(self, lista: list[dict], item_id: str | None, padrao: str) -> str:
        if not item_id:
            return padrao
        for it in lista:
            if str(it.get("id")) == str(item_id):
                return it.get("nome") or padrao
        return padrao

    def _popular_pilulas_ativas(self):
        self.row_ativos.controls.clear()
        pilulas: list[tuple[str, Callable]] = []

        if self.ctx.conta_id and not self.fixar_conta:
            nome_c = self._nome_por_id(self.contas_cache, self.ctx.conta_id, "Conta")
            pilulas.append((f"Conta: {nome_c}", lambda _: self.atualizar_contexto(self.ctx.com(conta_id=None))))

        if self.ctx.cartao_id and not self.fixar_cartao:
            nome_ca = self._nome_por_id(self.cartoes_cache, self.ctx.cartao_id, "Cartão")
            pilulas.append((f"Cartão: {nome_ca}", lambda _: self.atualizar_contexto(self.ctx.com(cartao_id=None))))

        if self.ctx.categoria_id and not self.fixar_categoria:
            nome_cat = self._nome_por_id(self.categorias_cache, self.ctx.categoria_id, "Categoria")
            pilulas.append((f"Categoria: {nome_cat}", lambda _: self.atualizar_contexto(self.ctx.com(categoria_id=None, subcategoria_id=None))))

        if self.ctx.pote_id and not self.fixar_pote:
            nome_pote = self._nome_por_id(self.potes_cache, self.ctx.pote_id, "Pote")
            pilulas.append((f"Pote: {nome_pote}", lambda _: self.atualizar_contexto(self.ctx.com(pote_id=None))))

        if self.ctx.regra and not self.fixar_regra:
            pilulas.append((f"Regra: {self.ctx.regra}", lambda _: self.atualizar_contexto(self.ctx.com(regra=None))))

        if self.ctx.forma:
            pilulas.append((f"Modalidade: {self.ctx.forma}", lambda _: self.atualizar_contexto(self.ctx.com(forma=None))))

        if self.ctx.busca:
            pilulas.append((f'Busca: "{self.ctx.busca}"', lambda _: self.atualizar_contexto(self.ctx.com(busca=None))))

        for texto_p, acao_remover in pilulas:
            self.row_ativos.controls.append(
                ft.Container(
                    padding=pad(h=10, v=4),
                    bgcolor=f"{T.PRIMARY}18",
                    border_radius=12,
                    border=borda(1, f"{T.PRIMARY}40"),
                    on_click=acao_remover,
                    ink=True,
                    tooltip="Clique para remover este filtro",
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Text(texto_p, color=T.PRIMARY, size=11, weight=ft.FontWeight.W_600),
                            ft.Icon(ft.Icons.CLOSE_ROUNDED, color=T.PRIMARY, size=13),
                        ],
                    ),
                )
            )

        if len(pilulas) > 1:
            self.row_ativos.controls.append(
                ft.TextButton(
                    content=ft.Text("Limpar todos", color=T.DESPESA, size=11, weight=ft.FontWeight.W_600),
                    on_click=lambda _: self.atualizar_contexto(
                        self.ctx.com(
                            conta_id=self.ctx.conta_id if self.fixar_conta else None,
                            cartao_id=self.ctx.cartao_id if self.fixar_cartao else None,
                            categoria_id=self.ctx.categoria_id if self.fixar_categoria else None,
                            subcategoria_id=None,
                            pote_id=self.ctx.pote_id if self.fixar_pote else None,
                            regra=self.ctx.regra if self.fixar_regra else None,
                            status=None,
                            forma=None,
                            busca=None,
                        )
                    ),
                )
            )

        self.row_ativos.visible = len(self.row_ativos.controls) > 0

    def _abrir_modal_filtros_avancados(self, _=None):
        dd_conta = ft.Dropdown(
            label="Conta Bancária",
            value=self.ctx.conta_id or "",
            disabled=self.fixar_conta,
            options=[ft.dropdown.Option(key="", text="Todas as contas")] + [
                ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", "Conta"))
                for c in self.contas_cache
            ],
            **T.dropdown_estilo(),
        )

        dd_cartao = ft.Dropdown(
            label="Cartão de Crédito",
            value=self.ctx.cartao_id or "",
            disabled=self.fixar_cartao,
            options=[ft.dropdown.Option(key="", text="Todos os cartões")] + [
                ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", "Cartão"))
                for c in self.cartoes_cache
            ],
            **T.dropdown_estilo(),
        )

        dd_cat = ft.Dropdown(
            label="Categoria",
            value=self.ctx.categoria_id or "",
            disabled=self.fixar_categoria,
            options=[ft.dropdown.Option(key="", text="Todas as categorias")] + [
                ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", "Categoria"))
                for c in self.categorias_cache
            ],
            **T.dropdown_estilo(),
        )

        dd_forma = ft.Dropdown(
            label="Forma de Movimentação",
            value=self.ctx.forma or "",
            options=[ft.dropdown.Option(key="", text="Todas as modalidades")] + [
                ft.dropdown.Option(key=f, text=f) for f in FORMAS_DESPESA
            ],
            **T.dropdown_estilo(),
        )

        dd_pote = ft.Dropdown(
            label="Pote Financeiro",
            value=self.ctx.pote_id or "",
            disabled=self.fixar_pote,
            options=[ft.dropdown.Option(key="", text="Todos os potes")] + [
                ft.dropdown.Option(
                    key=str(p["id"]),
                    text=f"{p.get('posicao', '')}. {p.get('nome', 'Pote')} ({float(p.get('percentual', 0)):.0f}%)"
                )
                for p in self.potes_cache
            ],
            **T.dropdown_estilo(),
        )

        dd_regra = ft.Dropdown(
            label="Regra 50/30/20 (Legado)",
            value=self.ctx.regra or "",
            disabled=self.fixar_regra,
            options=[ft.dropdown.Option(key="", text="Todas as faixas")] + [
                ft.dropdown.Option(key=r, text=r) for r in REGRAS_5030
            ],
            **T.dropdown_estilo(),
        )

        def _aplicar(_):
            self._page.pop_dialog()
            self.atualizar_contexto(
                self.ctx.com(
                    conta_id=(dd_conta.value or None) if not self.fixar_conta else self.ctx.conta_id,
                    cartao_id=(dd_cartao.value or None) if not self.fixar_cartao else self.ctx.cartao_id,
                    categoria_id=(dd_cat.value or None) if not self.fixar_categoria else self.ctx.categoria_id,
                    pote_id=(dd_pote.value or None) if not self.fixar_pote else self.ctx.pote_id,
                    forma=dd_forma.value or None,
                    regra=(dd_regra.value or None) if not self.fixar_regra else self.ctx.regra,
                ),
                emitir=True,
            )

        def _limpar(_):
            self._page.pop_dialog()
            self.atualizar_contexto(
                self.ctx.com(
                    conta_id=self.ctx.conta_id if self.fixar_conta else None,
                    cartao_id=self.ctx.cartao_id if self.fixar_cartao else None,
                    categoria_id=self.ctx.categoria_id if self.fixar_categoria else None,
                    subcategoria_id=None,
                    pote_id=self.ctx.pote_id if self.fixar_pote else None,
                    forma=None,
                    regra=self.ctx.regra if self.fixar_regra else None,
                    status=None,
                    busca=None,
                ),
                emitir=True,
            )

        campos: list[ft.Control] = []
        if not self.fixar_conta:
            campos.append(dd_conta)
        if not self.fixar_cartao:
            campos.append(dd_cartao)
        if not self.fixar_categoria:
            campos.append(dd_cat)
        if not self.fixar_pote:
            campos.append(dd_pote)
        campos.append(dd_forma)
        if not self.fixar_regra:
            campos.append(dd_regra)

        if self.mobile:
            sheet = ft.BottomSheet(
                scrollable=True,
                show_drag_handle=True,
                bgcolor=T.SURFACE,
                content=ft.Container(
                    padding=pad(h=18, v=16),
                    content=ft.Column(
                        tight=True,
                        spacing=12,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text("Filtros Avançados", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                                    ft.TextButton("Limpar", on_click=_limpar),
                                ],
                            ),
                            *campos,
                            ft.Container(height=6),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.END,
                                spacing=10,
                                controls=[
                                    ft.TextButton("Cancelar", on_click=lambda _: self._page.pop_dialog()),
                                    ft.FilledButton(
                                        content=ft.Text("Aplicar Filtros", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                                        style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=10)),
                                        on_click=_aplicar,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ),
            )
            self._page.show_dialog(sheet)
        else:
            dlg = ft.AlertDialog(
                bgcolor=T.SURFACE,
                shape=ft.RoundedRectangleBorder(radius=16),
                title=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.FILTER_LIST_ROUNDED, color=T.PRIMARY, size=20),
                                ft.Text("Filtros Avançados", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        ft.IconButton(
                            icon=ft.Icons.CLOSE_ROUNDED,
                            icon_color=T.TEXT_MUTED,
                            icon_size=18,
                            on_click=lambda _: self._page.pop_dialog(),
                        ),
                    ],
                ),
                content=ft.Container(
                    width=420,
                    content=ft.Column(tight=True, spacing=12, controls=campos),
                ),
                actions=[
                    ft.TextButton("Limpar Filtros", on_click=_limpar),
                    ft.TextButton("Cancelar", on_click=lambda _: self._page.pop_dialog()),
                    ft.FilledButton(
                        content=ft.Text("Aplicar Filtros", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                        style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=_aplicar,
                    ),
                ],
            )
            self._page.show_dialog(dlg)


def criar_filter_bar(
    page: ft.Page,
    ctx: ReportContext,
    on_change: Callable[[ReportContext], None],
    mostrar_chips_tipo: bool = True,
    mostrar_filtro_conta: bool = True,
    mostrar_filtro_cartao: bool = True,
    mostrar_filtro_categoria: bool = True,
    mostrar_filtro_regra: bool = True,
    mostrar_filtro_forma: bool = True,
    fixar_conta: bool = False,
    fixar_cartao: bool = False,
    fixar_categoria: bool = False,
    fixar_regra: bool = False,
) -> FilterBar:
    """Helper de conveniência para instanciar FilterBar com flags explícitas."""
    return FilterBar(
        page=page,
        ctx=ctx,
        on_change=on_change,
        mostrar_chips_tipo=mostrar_chips_tipo,
        fixar_conta=fixar_conta or not mostrar_filtro_conta,
        fixar_cartao=fixar_cartao or not mostrar_filtro_cartao,
        fixar_categoria=fixar_categoria or not mostrar_filtro_categoria,
        fixar_regra=fixar_regra or not mostrar_filtro_regra,
    )

