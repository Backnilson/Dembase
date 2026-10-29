"""
=============================================================================
DemBase v3 — views/widgets/report/transaction_list.py  (Flet 1.0.1)
Lista responsiva de lançamentos agrupada por dia, com paginação ("Carregar mais"),
clique na linha para edição no modal oficial, exclusão com suporte a séries e
edição rápida de Pote Financeiro in-line.
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

POTES_PADRAO = [
    {"id": "2df4dd2f-4353-42cc-a5c9-8983085a5301", "nome": "Custos Fixos", "cor": "#007AFF", "percentual": 35},
    {"id": "da6e1d2b-c611-481d-b48d-065cc5d584b4", "nome": "Custos Semi Fixos", "cor": "#FF69B4", "percentual": 15},
    {"id": "986da9e8-3042-4562-b1df-c1f5cf0138b9", "nome": "Metas", "cor": "#800080", "percentual": 15},
    {"id": "c82b0736-fb01-419f-8155-923ebfec82b2", "nome": "Prazeres", "cor": "#FF7A00", "percentual": 10},
    {"id": "1f1f7449-d985-4c2a-b807-0570a5526614", "nome": "Conhecimento", "cor": "#FFD60A", "percentual": 5},
    {"id": "34a47be1-9879-46bd-96b1-4082703bf388", "nome": "Liberdade Financeira", "cor": "#6C5CE7", "percentual": 20},
]


def _cabecalho_dia(data_iso: str, total_dia: float) -> ft.Container:
    if not data_iso:
        lbl_data = "Sem data"
    else:
        try:
            dt = datetime.strptime(str(data_iso)[:10], "%Y-%m-%d").date()
            dia_sem = _DIAS_SEMANA_CURTOS[dt.weekday()]
            lbl_data = f"{dia_sem}, {formatar_data_br(dt)}"
        except Exception:
            try:
                lbl_data = formatar_data_br(data_iso)
            except Exception:
                lbl_data = str(data_iso)

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
    edição rápida de Pote Financeiro, exclusão segura e paginação incremental ("Carregar mais").
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
        self.mobile = is_mobile(self._page)
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

    def _abrir_seletor_pote(self, item: dict):
        """
        Abre modal rápido para reclassificar o Pote Financeiro da despesa.
        Se o lançamento fizer parte de uma série/recorrência, pergunta o escopo
        (somente este ou este e os próximos).
        Executa UPDATE no Supabase e recarrega a lista sem formulário complexo.
        """
        pote_id_atual = str(item.get("pote_id") or "")
        desc = item.get("descricao") or item.get("categoria_nome") or "Lançamento"
        valor = float(item.get("valor", 0) or 0)
        tem_serie = bool(item.get("serie_id") or item.get("recorrente_id"))

        try:
            potes = db.listar_potes() or []
        except Exception:
            potes = []
        if not potes:
            potes = list(POTES_PADRAO)

        def _executar_salvamento(pid: str | None, pnome: str, escopo: str = "individual"):
            try:
                from core.potes import obter_regra_pote
                regra_pote = obter_regra_pote(pid, potes) if pid else None
                if escopo == "proximos" and tem_serie:
                    sid = str(item.get("serie_id") or item.get("recorrente_id"))
                    dt = str(item.get("data"))[:10] if item.get("data") else None
                    db.atualizar_serie(sid, {"pote_id": pid, "regra": regra_pote}, a_partir_de=dt)
                    if pid:
                        mostrar_feedback(self._page, f"Pote '{pnome}' aplicado a este e aos próximos lançamentos!", "sucesso")
                    else:
                        mostrar_feedback(self._page, "Pote desvinculado deste e dos próximos lançamentos!", "info")
                else:
                    db.atualizar_lancamento(str(item["id"]), {"pote_id": pid, "regra": regra_pote})
                    if pid:
                        mostrar_feedback(self._page, f"Classificado no pote '{pnome}'!", "sucesso")
                    else:
                        mostrar_feedback(self._page, "Pote desvinculado do lançamento.", "info")

                if callable(self.on_refresh):
                    self.on_refresh()
            except Exception as ex:
                mostrar_feedback(self._page, f"Erro ao atualizar pote: {ex}", "erro")

        def _perguntar_escopo(pid: str | None, pnome: str):
            dlg_escopo = None

            def _acao(escopo: str):
                fechar_dialogo(self._page, dlg_escopo)
                _executar_salvamento(pid, pnome, escopo)

            if pid:
                texto_pergunta = (
                    f"Este lançamento faz parte de uma despesa fixa/recorrente. "
                    f"Deseja aplicar a alteração do Pote ({pnome}) apenas a este lançamento "
                    f"ou a todas as despesas da série a partir desta data?"
                )
            else:
                texto_pergunta = (
                    "Este lançamento faz parte de uma despesa fixa/recorrente. "
                    "Deseja remover o Pote apenas deste lançamento "
                    "ou de todas as despesas da série a partir desta data?"
                )

            dlg_escopo = ft.AlertDialog(
                title=ft.Row(
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(ft.Icons.UPDATE_ROUNDED, color=T.PRIMARY, size=22),
                        ft.Text("Atualizar Recorrência", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                    ],
                ),
                content=ft.Text(
                    texto_pergunta,
                    color=T.TEXT_MUTED,
                    size=13.5,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(self._page, dlg_escopo)),
                    ft.FilledButton(
                        "Somente este",
                        style=ft.ButtonStyle(bgcolor=T.SURFACE_ALT, color=T.TEXT_PRIMARY),
                        on_click=lambda _: _acao("individual"),
                    ),
                    ft.FilledButton(
                        "Este e os próximos",
                        style=ft.ButtonStyle(bgcolor=T.PRIMARY, color=T.ON_PRIMARY),
                        on_click=lambda _: _acao("proximos"),
                    ),
                ],
            )
            abrir_dialogo(self._page, dlg_escopo)

        def _selecionar(pt: dict):
            fechar_dialogo(self._page, dlg)
            pid = pt.get("id")
            pnome = pt.get("nome", "Pote")
            if tem_serie:
                _perguntar_escopo(pid, pnome)
            else:
                _executar_salvamento(pid, pnome, "individual")

        def _desvincular(_=None):
            fechar_dialogo(self._page, dlg)
            if tem_serie:
                _perguntar_escopo(None, "Sem Pote")
            else:
                _executar_salvamento(None, "Sem Pote", "individual")

        linhas_potes: list[ft.Control] = []
        for p in potes:
            pid = str(p.get("id") or "")
            pnome = p.get("nome") or "Pote"
            pcor = p.get("cor") or T.PRIMARY
            perc = p.get("percentual") or 0
            selecionado = bool(pid and pid == pote_id_atual)

            linhas_potes.append(
                ft.Container(
                    padding=pad(h=12, v=10),
                    bgcolor=f"{pcor}1A" if selecionado else T.SURFACE_ALT,
                    border=borda(1.5, pcor) if selecionado else borda(1, T.BORDER),
                    border_radius=12,
                    ink=True,
                    on_click=lambda _, pt=p: _selecionar(pt),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(width=12, height=12, border_radius=6, bgcolor=pcor),
                                    ft.Column(
                                        spacing=1,
                                        controls=[
                                            ft.Text(
                                                pnome,
                                                color=T.TEXT_PRIMARY,
                                                size=13.5,
                                                weight=ft.FontWeight.BOLD if selecionado else ft.FontWeight.W_500,
                                            ),
                                            ft.Text(f"Orçamento sugerido: {float(perc):.0f}%", color=T.TEXT_MUTED, size=11),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=pcor, size=18)
                            if selecionado
                            else ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=16),
                        ],
                    ),
                )
            )

        acoes_dlg = [
            ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(self._page, dlg)),
        ]
        if pote_id_atual:
            acoes_dlg.insert(
                0,
                ft.TextButton(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.CLEAR_ROUNDED, size=14, color=T.DESPESA),
                            ft.Text("Remover do Pote", color=T.DESPESA, size=12),
                        ],
                    ),
                    on_click=_desvincular,
                ),
            )

        dlg = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.PRIMARY, size=20),
                    ft.Text("Classificar Pote Financeiro", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                ],
            ),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    tight=True,
                    spacing=8,
                    controls=[
                        ft.Text(f"{desc} · {formatar_moeda(valor)}", color=T.TEXT_MUTED, size=12.5),
                        ft.Divider(height=1, color=T.BORDER),
                        *linhas_potes,
                    ],
                ),
            ),
            actions=acoes_dlg,
        )
        abrir_dialogo(self._page, dlg)

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

        # Identificacao de Perfil Familiar ("Eu, Ela & Nos")
        membro_nome = item.get("membro_nome")
        membro_cor = item.get("membro_cor")
        if not membro_nome and isinstance(item.get("membros"), dict):
            membro_nome = item["membros"].get("nome")
            membro_cor = item["membros"].get("cor")
        if not membro_nome and item.get("membro_id"):
            m_info = db.obter_membro(item["membro_id"])
            if m_info:
                membro_nome = m_info.get("nome")
                membro_cor = m_info.get("cor")

        badge_membro = None
        if membro_nome:
            cor_mb = membro_cor or "#6366F1"
            badge_membro = ft.Container(
                padding=pad(h=6, v=2),
                bgcolor=f"{cor_mb}1A",
                border_radius=6,
                border=borda(1, f"{cor_mb}4D"),
                content=ft.Row(
                    spacing=3,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.PERSON_ROUNDED, size=11, color=cor_mb),
                        ft.Text(membro_nome, size=10.5, color=cor_mb, weight=ft.FontWeight.BOLD),
                    ],
                ),
                tooltip=f"Perfil: {membro_nome}",
            )

        badges: list[ft.Control] = []
        if badge_membro:
            badges.append(badge_membro)

        badges.extend([
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
        ])

        if eh_transf and conta_nome and destino_nome:
            badges.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{T.INFO}18",
                    border_radius=6,
                    content=ft.Text(f"{conta_nome} → {destino_nome}", size=10.5, color=T.INFO, weight=ft.FontWeight.W_600),
                )
            )
        else:
            eh_credito = ("cred" in str(forma).lower()) or bool(item.get("cartao_id")) or bool(cartao_nome)
            parc_atual = item.get("parcela_atual")
            tot_parc = item.get("total_parcelas")
            is_fixa_rec = (item.get("tipo_recorrencia") == "fixa" or bool(item.get("recorrente_id")))

            if eh_credito:
                if cartao_nome:
                    badges.append(
                        ft.Container(
                            padding=pad(h=6, v=2),
                            bgcolor=f"{T.WARNING}18",
                            border_radius=6,
                            content=ft.Text(f"Cartão {cartao_nome}", size=10.5, color=T.WARNING, weight=ft.FontWeight.W_600),
                        )
                    )

                if tot_parc and int(tot_parc) > 1:
                    p_atual_num = parc_atual or 1
                    badges.append(
                        ft.Container(
                            padding=pad(h=7, v=2),
                            bgcolor="#8B5CF622",
                            border_radius=6,
                            border=borda(1, "#8B5CF660"),
                            content=ft.Row(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.PAYMENTS_ROUNDED, size=11, color="#8B5CF6"),
                                    ft.Text(f"Parcela {p_atual_num} de {tot_parc}", size=10.5, color="#8B5CF6", weight=ft.FontWeight.BOLD),
                                ],
                            ),
                        )
                    )
                elif is_fixa_rec:
                    badges.append(
                        ft.Container(
                            padding=pad(h=7, v=2),
                            bgcolor=f"{T.PRIMARY}22",
                            border_radius=6,
                            border=borda(1, f"{T.PRIMARY}55"),
                            content=ft.Row(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.ALL_INCLUSIVE_ROUNDED, size=11, color=T.PRIMARY),
                                    ft.Text("Recorrência", size=10.5, color=T.PRIMARY, weight=ft.FontWeight.BOLD),
                                ],
                            ),
                        )
                    )
                else:
                    badges.append(
                        ft.Container(
                            padding=pad(h=6, v=2),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=6,
                            content=ft.Text("À vista", size=10.5, color=T.TEXT_MUTED, weight=ft.FontWeight.W_600),
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
                    padding=pad(h=7, v=3),
                    bgcolor=f"{pote_cor}20",
                    border_radius=8,
                    border=borda(1, f"{pote_cor}45"),
                    on_click=lambda _, it=item: self._abrir_seletor_pote(it),
                    ink=True,
                    tooltip=f"Pote: {pote_nome}. Clique para reclassificar rapidamente",
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Container(width=7, height=7, border_radius=3.5, bgcolor=pote_cor),
                            ft.Text(pote_nome, size=10.5, color=pote_cor, weight=ft.FontWeight.BOLD),
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, size=14, color=pote_cor),
                        ],
                    ),
                )
            )
        elif not eh_transf and not eh_rec:
            # Despesa sem pote -> badge de ação rápida chamando a atenção
            badges.append(
                ft.Container(
                    padding=pad(h=7, v=3),
                    bgcolor=f"{T.WARNING}1A",
                    border_radius=8,
                    border=borda(1, f"{T.WARNING}50"),
                    on_click=lambda _, it=item: self._abrir_seletor_pote(it),
                    ink=True,
                    tooltip="Despesa sem Pote Financeiro! Clique para classificar",
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.SAVINGS_OUTLINED, size=12, color=T.WARNING),
                            ft.Text("Definir Pote", size=10, color=T.WARNING, weight=ft.FontWeight.BOLD),
                            ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, size=14, color=T.WARNING),
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

        is_mob = getattr(self, "mobile", False) or is_mobile(self._page)

        if not is_mob:
            # === DESKTOP LAYOUT (100% INTACTO) ===
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
                            size=15,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ],
                ),
            )

            acoes_direita: list[ft.Control] = []
            if not eh_transf and not eh_rec:
                acoes_direita.append(
                    ft.IconButton(
                        icon=ft.Icons.SAVINGS_ROUNDED,
                        icon_color=pote_cor if pote_nome else T.WARNING,
                        icon_size=18,
                        tooltip=f"Pote: {pote_nome or 'Não classificado'} (toque para alterar rapidamente)",
                        on_click=lambda _, it=item: self._abrir_seletor_pote(it),
                    )
                )
            acoes_direita.append(badge_status)
            acoes_direita.append(
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                    icon_color=T.TEXT_MUTED,
                    icon_size=18,
                    tooltip="Excluir lançamento",
                    on_click=lambda _, it=item: self._confirmar_exclusao(it),
                )
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
                        *acoes_direita,
                    ],
                ),
            )

        # =========================================================================
        # LAYOUT DEDICADO MOBILE: Compacto, estruturado em 2 linhas, sem estouro vertical
        # =========================================================================
        nome_desc = (item.get("descricao") or "").strip()
        tem_desc = bool(nome_desc and nome_desc.lower() != str(cat_nome).lower())
        nome_principal = nome_desc if tem_desc else cat_nome
        subtitulo = (f"{cat_nome} › {subcat_nome}" if subcat_nome else cat_nome) if tem_desc else (subcat_nome or "")

        col_textos_mobile: list[ft.Control] = [
            ft.Text(
                nome_principal,
                color=T.TEXT_PRIMARY,
                size=13.5,
                weight=ft.FontWeight.W_600,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
        ]
        if subtitulo:
            col_textos_mobile.append(
                ft.Text(
                    subtitulo,
                    color=T.TEXT_MUTED,
                    size=11,
                    weight=ft.FontWeight.W_500,
                    max_lines=1,
                    overflow=ft.TextOverflow.ELLIPSIS,
                )
            )

        linha_topo_mobile = ft.Container(
            on_click=lambda _, it=item: abrir_lancamento(
                self._page,
                lancamento=it,
                on_saved=self.on_refresh,
            ),
            ink=True,
            tooltip="Clique para editar este lançamento",
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=ft.Icon(icone_tipo, color=cor_valor, size=16),
                        bgcolor=f"{cor_valor}1A",
                        border_radius=8,
                        padding=pad(all_=8),
                    ),
                    ft.Column(
                        spacing=1,
                        expand=True,
                        controls=col_textos_mobile,
                    ),
                    ft.Text(
                        f"{sinal} {formatar_moeda(valor)}",
                        color=cor_valor,
                        size=14,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
        )

        # Badges contextuais compactos no rodapé mobile
        badges_mobile: list[ft.Control] = []
        if eh_transf and conta_nome and destino_nome:
            badges_mobile.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{T.INFO}18",
                    border_radius=6,
                    content=ft.Text(f"{conta_nome} → {destino_nome}", size=10, color=T.INFO, weight=ft.FontWeight.W_600),
                )
            )
        else:
            eh_credito = ("cred" in str(forma).lower()) or bool(item.get("cartao_id")) or bool(cartao_nome)
            parc_atual = item.get("parcela_atual")
            tot_parc = item.get("total_parcelas")
            is_fixa_rec = (item.get("tipo_recorrencia") == "fixa" or bool(item.get("recorrente_id")))

            if eh_credito:
                cartao_lbl = f"Cartão {cartao_nome}" if cartao_nome else "Crédito"
                badges_mobile.append(
                    ft.Container(
                        padding=pad(h=6, v=2),
                        bgcolor=f"{T.WARNING}18",
                        border_radius=6,
                        content=ft.Text(cartao_lbl, size=10, color=T.WARNING, weight=ft.FontWeight.W_600),
                    )
                )
                if tot_parc and int(tot_parc) > 1:
                    p_num = parc_atual or 1
                    badges_mobile.append(
                        ft.Container(
                            padding=pad(h=6, v=2),
                            bgcolor="#8B5CF622",
                            border_radius=6,
                            content=ft.Text(f"{p_num}/{tot_parc}", size=10, color="#8B5CF6", weight=ft.FontWeight.BOLD),
                        )
                    )
                elif is_fixa_rec:
                    badges_mobile.append(
                        ft.Container(
                            padding=pad(h=6, v=2),
                            bgcolor=f"{T.PRIMARY}22",
                            border_radius=6,
                            content=ft.Text("Recorrência", size=10, color=T.PRIMARY, weight=ft.FontWeight.BOLD),
                        )
                    )
            elif conta_nome:
                badges_mobile.append(
                    ft.Container(
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        content=ft.Text(f"{forma} • {conta_nome}", size=10, color=T.TEXT_MUTED),
                    )
                )
            else:
                badges_mobile.append(
                    ft.Container(
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        content=ft.Text(forma, size=10, color=T.TEXT_MUTED),
                    )
                )

        if pote_nome:
            badges_mobile.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{pote_cor}20",
                    border_radius=6,
                    border=borda(1, f"{pote_cor}45"),
                    on_click=lambda _, it=item: self._abrir_seletor_pote(it),
                    ink=True,
                    tooltip=f"Pote: {pote_nome}. Clique para alterar",
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
        elif not eh_transf and not eh_rec:
            badges_mobile.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{T.WARNING}1A",
                    border_radius=6,
                    border=borda(1, f"{T.WARNING}50"),
                    on_click=lambda _, it=item: self._abrir_seletor_pote(it),
                    ink=True,
                    tooltip="Definir Pote",
                    content=ft.Row(
                        spacing=3,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.SAVINGS_OUTLINED, size=11, color=T.WARNING),
                            ft.Text("Definir Pote", size=10, color=T.WARNING, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                )
            )
        elif item.get("regra"):
            regra = item.get("regra")
            cor_r = T.PRIMARY if regra == "Essencial" else (T.WARNING if regra == "Estilo de Vida" else T.SALDO)
            badges_mobile.append(
                ft.Container(
                    padding=pad(h=6, v=2),
                    bgcolor=f"{cor_r}18",
                    border_radius=6,
                    content=ft.Text(regra, size=10, color=cor_r, weight=ft.FontWeight.BOLD),
                )
            )

        badge_status_mobile = ft.Container(
            padding=pad(h=7, v=3),
            bgcolor=f"{T.RECEITA}18" if eh_pago else f"{T.WARNING}18",
            border_radius=8,
            border=borda(1, f"{T.RECEITA}35" if eh_pago else f"{T.WARNING}35"),
            tooltip="Toque para alternar Pago / Pendente",
            on_click=lambda _, it=item: self._alternar_status(it),
            ink=True,
            content=ft.Row(
                spacing=3,
                tight=True,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if eh_pago else ft.Icons.SCHEDULE_ROUNDED,
                        size=11,
                        color=T.RECEITA if eh_pago else T.WARNING,
                    ),
                    ft.Text(
                        status,
                        size=10,
                        color=T.RECEITA if eh_pago else T.WARNING,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
        )

        linha_rodape_mobile = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                # Quebra inteligente: tags nunca são cortadas a seco; se não couberem,
                # descem para a linha seguinte (sem depender de scroll horizontal invisível).
                ft.Row(
                    spacing=4,
                    run_spacing=4,
                    wrap=True,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=badges_mobile,
                ),
                ft.Row(
                    spacing=4,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        badge_status_mobile,
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                            icon_color=T.TEXT_MUTED,
                            icon_size=17,
                            tooltip="Excluir lançamento",
                            on_click=lambda _, it=item: self._confirmar_exclusao(it),
                            style=ft.ButtonStyle(padding=pad(all_=2)),
                        ),
                    ],
                ),
            ],
        )

        return ft.Container(
            padding=pad(h=12, v=10),
            bgcolor=T.SURFACE,
            border_radius=12,
            border=borda(),
            content=ft.Column(
                spacing=8,
                tight=True,
                controls=[
                    linha_topo_mobile,
                    linha_rodape_mobile,
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
