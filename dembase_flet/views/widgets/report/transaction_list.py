"""
=============================================================================
DemBase v3 — views/widgets/report/transaction_list.py  (Flet 1.0.1)
Lista responsiva de lançamentos agrupada por dia, com paginação ("Carregar mais"),
clique na linha para edição no modal oficial e exclusão com suporte a séries.
=============================================================================
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable
import flet as ft

from core import theme as T
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.constants import formatar_moeda, formatar_data_br
from core.responsive import is_mobile
from views.widgets.lancamento_sheet import abrir_lancamento
from views.widgets.report.empty_state import criar_empty_state
import services.supabase_client as db

_DIAS_SEMANA_CURTOS = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def _cabecalho_dia(data_iso: str, total_dia: float) -> ft.Container:
    try:
        dt = datetime.strptime(str(data_iso)[:10], "%Y-%m-%d").date()
        dia_sem = _DIAS_SEMANA_CURTOS[dt.weekday()]
        lbl_data = f"{dia_sem}, {formatar_data_br(dt)}"
    except Exception:
        lbl_data = formatar_data_br(data_iso)

    sinal = "+" if total_dia > 0 else ("-" if total_dia < 0 else "")
    cor_tot = T.RECEITA if total_dia > 0 else (T.DESPESA if total_dia < 0 else T.TEXT_MUTED)

    return ft.Container(
        padding=pad(h=12, v=6),
        bgcolor=T.SURFACE_ALT,
        border_radius=8,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=6,
                    controls=[
                        ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=13, color=T.PRIMARY),
                        ft.Text(lbl_data, color=T.TEXT_PRIMARY, size=12, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Text(
                    f"{sinal} {formatar_moeda(abs(total_dia))}".strip(),
                    color=cor_tot,
                    size=12,
                    weight=ft.FontWeight.BOLD,
                ),
            ],
        ),
    )


class TransactionList(ft.Column):
    """
    Lista agrupada por data com edição ao clicar no item, toggle rápido de status,
    exclusão segura e paginação incremental ("Carregar mais").
    """

    def __init__(
        self,
        page: ft.Page,
        on_refresh: Callable[[], None],
        on_carregar_mais: Callable[[], None] | None = None,
        on_novo_lancamento: Callable | None = None,
    ):
        self._page = page
        self.on_refresh = on_refresh
        self.on_carregar_mais = on_carregar_mais
        self.on_novo_lancamento = on_novo_lancamento
        self.mobile = is_mobile(page)

        self.lbl_contador = ft.Text(
            "0 lançamentos",
            color=T.TEXT_MUTED,
            size=12,
            weight=ft.FontWeight.W_500,
        )
        self.col_itens = ft.Column(spacing=8, controls=[])
        self.btn_mais = ft.Container(
            visible=False,
            alignment=ft.Alignment(0, 0),
            padding=pad(v=10),
            content=ft.OutlinedButton(
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.EXPAND_MORE_ROUNDED, color=T.PRIMARY, size=18),
                        ft.Text("Carregar mais lançamentos", color=T.PRIMARY, size=13, weight=ft.FontWeight.W_600),
                    ],
                ),
                on_click=lambda _: self.on_carregar_mais() if callable(self.on_carregar_mais) else None,
            ),
        )

        super().__init__(
            spacing=10,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.LIST_ALT_ROUNDED, color=T.PRIMARY, size=18),
                                ft.Text("Lançamentos do Período", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        self.lbl_contador,
                    ],
                ),
                self.col_itens,
                self.btn_mais,
            ],
        )

        if hasattr(self, "_dirty"):
            self._dirty.clear()

    def renderizar(self, lancamentos: list[dict], total_registros: int | None = None):
        total = total_registros if total_registros is not None else len(lancamentos)
        self.lbl_contador.value = f"Exibindo {len(lancamentos)} de {total} registro(s)"
        self.col_itens.controls.clear()

        if not lancamentos:
            self.col_itens.controls.append(
                criar_empty_state(on_novo_lancamento=self.on_novo_lancamento)
            )
            self.btn_mais.visible = False
            self._atualizar_ui()
            return

        # Agrupa por data mantendo a ordem decrescente
        grupos: dict[str, list[dict]] = {}
        for item in lancamentos:
            dt_key = str(item.get("data") or "")[:10]
            grupos.setdefault(dt_key, []).append(item)

        for dt_key, itens_dia in grupos.items():
            saldo_dia = 0.0
            for it in itens_dia:
                val = float(it.get("valor", 0) or 0)
                direcao = it.get("direcao_conta")
                tipo = (it.get("tipo") or "Despesa").lower()
                if direcao == "Entrada" or (not direcao and "rec" in tipo):
                    saldo_dia += val
                elif direcao == "Saida" or (not direcao and "desp" in tipo):
                    saldo_dia -= val

            self.col_itens.controls.append(_cabecalho_dia(dt_key, saldo_dia))
            for it in itens_dia:
                self.col_itens.controls.append(self._criar_card_lancamento(it))

        self.btn_mais.visible = len(lancamentos) < total and callable(self.on_carregar_mais)
        self._atualizar_ui()

    def _atualizar_ui(self):
        try:
            self.update()
        except Exception:
            pass
        try:
            self._page.update()
        except Exception:
            pass

    def _alternar_status(self, item: dict):
        novo_status = "Pendente" if item.get("status") == "Pago" else "Pago"
        try:
            db.atualizar_lancamento(str(item["id"]), {"status": novo_status})
            mostrar_feedback(self._page, f"Status alterado para {novo_status}.", "sucesso")
            if callable(self.on_refresh):
                self.on_refresh()
        except Exception as ex:
            mostrar_feedback(self._page, f"Erro ao alterar status: {ex}", "erro")

    def _confirmar_exclusao(self, item: dict):
        tem_serie = bool(item.get("serie_id") or item.get("recorrente_id"))

        def _excluir_unico(_=None):
            fechar_dialogo(self._page, dlg)
            try:
                db.deletar_lancamento(str(item["id"]))
                mostrar_feedback(self._page, "Lançamento excluído!", "sucesso")
                if callable(self.on_refresh):
                    self.on_refresh()
            except Exception as ex:
                mostrar_feedback(self._page, f"Erro ao excluir: {ex}", "erro")

        def _excluir_proximos(_=None):
            fechar_dialogo(self._page, dlg)
            try:
                sid = str(item.get("serie_id") or item.get("recorrente_id"))
                db.excluir_serie(sid, a_partir_de=str(item.get("data"))[:10])
                mostrar_feedback(self._page, "Série excluída a partir desta data!", "sucesso")
                if callable(self.on_refresh):
                    self.on_refresh()
            except Exception as ex:
                mostrar_feedback(self._page, f"Erro ao excluir série: {ex}", "erro")

        acoes = [
            ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(self._page, dlg)),
            ft.FilledButton(
                "Excluir este",
                style=ft.ButtonStyle(bgcolor=T.DESPESA, color=ft.Colors.WHITE),
                on_click=_excluir_unico,
            ),
        ]
        if tem_serie:
            acoes.append(
                ft.FilledButton(
                    "Este e próximos",
                    style=ft.ButtonStyle(bgcolor=T.WARNING, color=ft.Colors.WHITE),
                    on_click=_excluir_proximos,
                )
            )

        dlg = ft.AlertDialog(
            title=ft.Text("Confirmar Exclusão", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"Deseja excluir '{item.get('descricao') or 'Lançamento'}' ({formatar_moeda(float(item.get('valor', 0) or 0))})?",
                color=T.TEXT_MUTED,
                size=13.5,
            ),
            actions=acoes,
        )
        abrir_dialogo(self._page, dlg)

    def _criar_card_lancamento(self, item: dict) -> ft.Container:
        tipo = item.get("tipo") or "Despesa"
        direcao = item.get("direcao_conta")
        eh_transf = "trans" in tipo.lower()
        eh_rec = (direcao == "Entrada") if direcao else ("rec" in tipo.lower())

        if eh_transf and not direcao:
            cor_valor = T.INFO
            icone_tipo = ft.Icons.SWAP_HORIZ_ROUNDED
            sinal = "⇄"
        elif eh_rec:
            cor_valor = T.RECEITA
            icone_tipo = ft.Icons.SWAP_HORIZ_ROUNDED if eh_transf else ft.Icons.ARROW_UPWARD_ROUNDED
            sinal = "+"
        else:
            cor_valor = T.DESPESA
            icone_tipo = ft.Icons.SWAP_HORIZ_ROUNDED if eh_transf else ft.Icons.ARROW_DOWNWARD_ROUNDED
            sinal = "-"

        valor = float(item.get("valor", 0) or 0)
        status = item.get("status") or "Pago"
        eh_pago = (status == "Pago")

        cat_nome = item.get("categoria_nome") or (
            (item.get("categorias") or {}).get("nome") if isinstance(item.get("categorias"), dict) else None
        ) or ("Transferência" if eh_transf else "Sem Categoria")
        subcat_nome = item.get("subcategoria_nome") or (
            (item.get("subcategorias") or {}).get("nome") if isinstance(item.get("subcategorias"), dict) else None
        )
        conta_nome = item.get("conta_nome") or (
            (item.get("contas") or {}).get("nome") if isinstance(item.get("contas"), dict) else None
        )
        destino_nome = item.get("destino_nome")
        cartao_nome = item.get("cartao_nome") or (
            (item.get("cartoes") or {}).get("nome") if isinstance(item.get("cartoes"), dict) else None
        )
        forma = item.get("forma_movimentacao") or "Pix"

        badges: list[ft.Control] = [
            ft.Container(
                padding=pad(h=6, v=2),
                bgcolor=T.SURFACE_ALT,
                border_radius=6,
                content=ft.Text(
                    f"{cat_nome} › {subcat_nome}" if subcat_nome else cat_nome,
                    size=10.5,
                    color=T.TEXT_MUTED,
                    weight=ft.FontWeight.W_600,
                ),
            ),
            ft.Container(
                padding=pad(h=6, v=2),
                bgcolor=T.SURFACE_ALT,
                border_radius=6,
                content=ft.Text(forma, size=10.5, color=T.TEXT_MUTED),
            ),
        ]

        if eh_transf and conta_nome and destino_nome:
            badges.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{T.INFO}18",
                    border_radius=6,
                    content=ft.Text(f"{conta_nome} → {destino_nome}", size=10.5, color=T.INFO, weight=ft.FontWeight.W_600),
                )
            )
        elif cartao_nome:
            parc_txt = ""
            if item.get("parcela_atual") and item.get("total_parcelas") and int(item.get("total_parcelas", 1)) > 1:
                parc_txt = f" ({item['parcela_atual']}/{item['total_parcelas']})"
            badges.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{T.WARNING}18",
                    border_radius=6,
                    content=ft.Text(f"Cartão {cartao_nome}{parc_txt}", size=10.5, color=T.WARNING, weight=ft.FontWeight.W_600),
                )
            )
        elif conta_nome:
            badges.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=6,
                    content=ft.Text(conta_nome, size=10.5, color=T.TEXT_MUTED),
                )
            )

        pote_nome = item.get("pote_nome")
        pote_cor = item.get("pote_cor") or T.PRIMARY
        if pote_nome:
            badges.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{pote_cor}18",
                    border_radius=6,
                    content=ft.Row(
                        spacing=3,
                        tight=True,
                        controls=[
                            ft.Container(width=6, height=6, border_radius=3, bgcolor=pote_cor),
                            ft.Text(pote_nome, size=10, color=pote_cor, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                )
            )
        elif item.get("regra"):
            regra = item.get("regra")
            cor_r = T.PRIMARY if regra == "Essencial" else (T.WARNING if regra == "Estilo de Vida" else T.SALDO)
            badges.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{cor_r}18",
                    border_radius=6,
                    content=ft.Text(regra, size=10, color=cor_r, weight=ft.FontWeight.BOLD),
                )
            )

        badge_status = ft.Container(
            padding=pad(h=8, v=4),
            bgcolor=f"{T.RECEITA}18" if eh_pago else f"{T.WARNING}18",
            border_radius=10,
            border=borda(1, f"{T.RECEITA}35" if eh_pago else f"{T.WARNING}35"),
            tooltip="Toque para alternar Pago / Pendente",
            on_click=lambda _, it=item: self._alternar_status(it),
            ink=True,
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if eh_pago else ft.Icons.SCHEDULE_ROUNDED,
                        size=12,
                        color=T.RECEITA if eh_pago else T.WARNING,
                    ),
                    ft.Text(
                        status,
                        size=10.5,
                        color=T.RECEITA if eh_pago else T.WARNING,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
        )

        area_clicavel_edicao = ft.Container(
            expand=True,
            on_click=lambda _, it=item: abrir_lancamento(
                self._page,
                lancamento=it,
                on_saved=self.on_refresh,
            ),
            ink=True,
            tooltip="Clique para editar este lançamento",
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=ft.Icon(icone_tipo, color=cor_valor, size=18),
                        bgcolor=f"{cor_valor}1A",
                        border_radius=10,
                        padding=pad(all_=9),
                    ),
                    ft.Column(
                        spacing=4,
                        expand=True,
                        controls=[
                            ft.Text(
                                item.get("descricao") or cat_nome,
                                color=T.TEXT_PRIMARY,
                                size=13.5,
                                weight=ft.FontWeight.W_600,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            ft.Row(spacing=5, wrap=True, controls=badges),
                        ],
                    ),
                    ft.Text(
                        f"{sinal} {formatar_moeda(valor)}",
                        color=cor_valor,
                        size=14 if self.mobile else 15,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
        )

        return ft.Container(
            padding=pad(h=14, v=10),
            bgcolor=T.SURFACE,
            border_radius=12,
            border=borda(),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=8,
                controls=[
                    area_clicavel_edicao,
                    badge_status,
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                        icon_color=T.TEXT_MUTED,
                        icon_size=18,
                        tooltip="Excluir lançamento",
                        on_click=lambda _, it=item: self._confirmar_exclusao(it),
                    ),
                ],
            ),
        )


def criar_transaction_list(
    page: ft.Page,
    itens: list[dict],
    total_registros: int | None = None,
    pagina_atual: int = 1,
    page_size: int = 25,
    on_page_change: Callable[[int], None] | None = None,
    on_refresh: Callable[[], None] | None = None,
    conta_perspectiva_id: str | None = None,
    mostrar_transferencias_padrao: bool = True,
    titulo_vazio: str | None = None,
    subtitulo_vazio: str | None = None,
    label_cta_vazio: str | None = None,
    on_cta_vazio: Callable | None = None,
) -> TransactionList:
    """Helper de fábrica que instancia e renderiza TransactionList imediatamente."""
    def _ao_carregar_mais():
        if callable(on_page_change):
            on_page_change(pagina_atual + 1)

    tl = TransactionList(
        page=page,
        on_refresh=on_refresh or (lambda: None),
        on_carregar_mais=_ao_carregar_mais if total_registros and len(itens) < total_registros else None,
        on_novo_lancamento=on_cta_vazio,
    )

    # Se informado conta_perspectiva_id, pré-calcula a direção de transferências
    itens_processados = []
    for it in itens:
        it_copia = dict(it)
        if conta_perspectiva_id and "trans" in str(it_copia.get("tipo", "")).lower():
            if str(it_copia.get("conta_id")) == str(conta_perspectiva_id):
                it_copia["direcao_conta"] = "Saida"
            elif str(it_copia.get("destino_id")) == str(conta_perspectiva_id):
                it_copia["direcao_conta"] = "Entrada"
        itens_processados.append(it_copia)

    tl.renderizar(itens_processados, total_registros)
    return tl

