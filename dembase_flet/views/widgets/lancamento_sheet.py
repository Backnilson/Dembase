"""
=============================================================================
DemBase v3 — views/widgets/lancamento_sheet.py (Flet 1.0.1)
Hospedeiro responsivo para o formulário de lançamentos:
- Mobile (<768px): BottomSheet rolável (scrollable=True) com drag handle.
- Desktop (>=768px): AlertDialog compacto com title, content e actions nativos.
Gerencia ciclo de vida via page.show_dialog / page.pop_dialog (Flet 1.0.1),
suporte à tecla ESC, persistência e edição de séries/recorrências.
=============================================================================
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Optional

import flet as ft

from core.lancamento_state import LancamentoFormState
from core.responsive import is_mobile
import core.theme as T
from core.theme import pad, mostrar_feedback
import services.supabase_client as db
from views.widgets.lancamento_form import LancamentoForm


def abrir_lancamento(
    page: ft.Page,
    tipo_inicial: Optional[str] = None,
    lancamento: Optional[dict] = None,
    on_saved: Optional[Callable[[], None]] = None,
):
    """
    Abre o modal/bottom sheet de criação ou edição de lançamento financeiro.
    Usa a pilha nativa de diálogos do Flet 1.0.1 (page.show_dialog / page.pop_dialog).
    """
    is_edicao = (lancamento is not None and bool(lancamento.get("id")))

    # 1. Montagem do Estado
    state = LancamentoFormState()
    if is_edicao:
        state.lancamento_id = str(lancamento["id"])
        state.serie_id = str(lancamento.get("serie_id")) if lancamento.get("serie_id") else None
        state.recorrente_id = str(lancamento.get("recorrente_id")) if lancamento.get("recorrente_id") else None
        state.mudar_tipo(lancamento.get("tipo", "Despesa"))
        state.subtipo = lancamento.get("subtipo")
        state.forma_movimentacao = lancamento.get("forma_movimentacao", "Pix")
        state.descricao = lancamento.get("descricao") or ""
        state.valor = float(lancamento.get("valor", 0.0))
        state.conta_id = str(lancamento.get("conta_id")) if lancamento.get("conta_id") else None
        state.cartao_id = str(lancamento.get("cartao_id")) if lancamento.get("cartao_id") else None
        state.categoria_id = str(lancamento.get("categoria_id")) if lancamento.get("categoria_id") else None
        state.subcategoria_id = str(lancamento.get("subcategoria_id")) if lancamento.get("subcategoria_id") else None
        state.destino_id = str(lancamento.get("destino_id")) if lancamento.get("destino_id") else None
        state.regra = lancamento.get("regra", "Essencial")
        state.hora = int(lancamento.get("hora", 12)) if lancamento.get("hora") is not None else 12
        state.status_pago = (lancamento.get("status") == "Pago")
        state.status_manual = True  # Em edição, status gravado tem prioridade absoluta

        d_raw = lancamento.get("data")
        if isinstance(d_raw, str):
            try:
                state.data_selecionada = datetime.fromisoformat(d_raw[:10]).date()
            except Exception:
                state.data_selecionada = date.today()
        elif isinstance(d_raw, (date, datetime)):
            state.data_selecionada = d_raw if isinstance(d_raw, date) else d_raw.date()

        # Abre detalhes caso o registro já tenha dados secundários
        if state.subcategoria_id or state.subtipo or state.serie_id or state.recorrente_id:
            state.mais_detalhes_aberto = True
    elif tipo_inicial:
        state.mudar_tipo(tipo_inicial)

    # 2. Instanciação do formulário
    form = LancamentoForm(page, state)

    # 3. Controle de Fechamento e Tecla ESC (Flet 1.0.1)
    mobile = is_mobile(page)
    container_dialog: Optional[ft.DialogControl] = None
    prev_keyboard_handler = getattr(page, "on_keyboard_event", None)
    ja_fechado = [False]

    def _restaurar_teclado():
        try:
            page.on_keyboard_event = prev_keyboard_handler
        except Exception:
            pass

    def fechar_dialog(_=None):
        nonlocal container_dialog
        if ja_fechado[0]:
            return
        ja_fechado[0] = True
        _restaurar_teclado()

        try:
            page.pop_dialog()
        except Exception:
            pass

        if container_dialog is not None:
            container_dialog.open = False
            try:
                container_dialog.update()
            except Exception:
                pass

        try:
            page.update()
        except Exception:
            pass

    def _ao_dispensar_dialog(_=None):
        ja_fechado[0] = True
        _restaurar_teclado()

    def _ao_pressionar_tecla(e: ft.KeyboardEvent):
        if e.key == "Escape":
            fechar_dialog()
        elif callable(prev_keyboard_handler):
            prev_keyboard_handler(e)

    page.on_keyboard_event = _ao_pressionar_tecla

    # 4. Botões de Ação (com tight=True e dimensões explícitas para nunca cortar/espremer)
    texto_botao_acao = "Salvar Alterações" if is_edicao else "Confirmar Lançamento"

    def _conteudo_padrao_btn_salvar() -> ft.Control:
        return ft.Row(
            controls=[
                ft.Icon(ft.Icons.CHECK_ROUNDED, size=18, color=T.ON_PRIMARY),
                ft.Text(
                    texto_botao_acao,
                    size=14,
                    weight=ft.FontWeight.BOLD,
                    color=T.ON_PRIMARY,
                ),
            ],
            spacing=8,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    btn_salvar = ft.FilledButton(
        content=_conteudo_padrao_btn_salvar(),
        height=44,
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            color=T.ON_PRIMARY,
            padding=pad(h=22, v=10),
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )

    btn_cancelar = ft.TextButton(
        content=ft.Text("Cancelar", size=14, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
        height=44,
        style=ft.ButtonStyle(
            padding=pad(h=16, v=10),
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
        on_click=fechar_dialog,
    )

    def executar_salvamento(modo_serie: str = "individual"):
        btn_salvar.disabled = True
        btn_salvar.content = ft.Row(
            controls=[
                ft.ProgressRing(width=16, height=16, stroke_width=2, color=T.ON_PRIMARY),
                ft.Text("Salvando...", size=14, weight=ft.FontWeight.BOLD, color=T.ON_PRIMARY),
            ],
            spacing=8,
            tight=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )
        try:
            page.update()
        except Exception:
            pass

        try:
            tipo_db = (
                "Transferência"
                if state.eh_transferencia
                else ("Receita" if state.eh_receita else "Despesa")
            )
            desc_final = (state.descricao or "").strip()
            if not desc_final:
                desc_final = "Transferência" if state.eh_transferencia else (state.subtipo or "Lançamento")

            conta_id_final = form._obter_conta_id(state.conta_id) if not state.eh_credito else None
            cartao_id_final = form._obter_cartao_id(state.cartao_id) if state.eh_credito else None
            cat_id_final = form._obter_cat_id(state.categoria_id) if not state.eh_transferencia else None
            subcat_id_final = form._obter_subcat_id(state.subcategoria_id) if not state.eh_transferencia else None
            destino_id_final = form._obter_conta_id(state.destino_id) if state.eh_transferencia else None

            dados = {
                "tipo": tipo_db,
                "subtipo": state.subtipo or tipo_db,
                "forma_movimentacao": state.forma_movimentacao,
                "valor": state.valor,
                "data": str(state.data_selecionada),
                "hora": state.hora,
                "descricao": desc_final,
                "status": "Pago" if (state.status_pago or state.eh_transferencia) else "Pendente",
                "conta_id": conta_id_final,
                "cartao_id": cartao_id_final,
                "categoria_id": cat_id_final,
                "subcategoria_id": subcat_id_final,
                "destino_id": destino_id_final,
                "regra": state.regra if state.eh_despesa else None,
            }

            if is_edicao:
                if modo_serie == "proximos" and state.serie_id:
                    db.atualizar_serie(state.serie_id, dados, a_partir_de=str(state.data_selecionada))
                else:
                    db.atualizar_lancamento(state.lancamento_id, dados)
                mostrar_feedback(page, "Lançamento atualizado com sucesso!", "sucesso")
            else:
                modo = state.modo_recorrencia()
                valor_modo = "parcelado" if state.eh_credito else "repetido"
                res = db.criar_lancamento_recorrente(
                    dados=dados,
                    modo=modo,
                    frequencia=state.frequencia,
                    quantidade=state.quantidade,
                    valor_modo=valor_modo,
                )
                if not res.get("sucesso", True):
                    raise RuntimeError(res.get("erro", "Falha ao gravar lançamento."))
                mostrar_feedback(page, "Lançamento salvo com sucesso!", "sucesso")

            fechar_dialog()

            if on_saved:
                try:
                    on_saved()
                except Exception:
                    pass

        except Exception as ex:
            btn_salvar.disabled = False
            btn_salvar.content = _conteudo_padrao_btn_salvar()
            try:
                page.update()
            except Exception:
                pass
            mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

    def ao_clicar_salvar(_):
        # Garante que os IDs no state estejam normalizados antes de validar
        if state.eh_credito:
            state.cartao_id = form._obter_cartao_id(state.cartao_id or form.dd_conta.value)
        else:
            state.conta_id = form._obter_conta_id(state.conta_id or form.dd_conta.value)

        if state.eh_transferencia:
            state.destino_id = form._obter_conta_id(state.destino_id or form.dd_destino.value)
        else:
            state.categoria_id = form._obter_cat_id(state.categoria_id or form.dd_categoria.value)
            state.subcategoria_id = form._obter_subcat_id(state.subcategoria_id or form.dd_subcategoria.value)

        valido, erro_msg = state.validar()
        if not valido:
            mostrar_feedback(page, erro_msg or "Verifique os campos obrigatórios.", "alerta")
            return

        # Se for edição de lançamento que pertence a uma série/recorrência, perguntar o escopo
        if is_edicao and (state.serie_id or state.recorrente_id):
            modal_serie = None

            def fechar_modal_serie():
                nonlocal modal_serie
                try:
                    page.pop_dialog()
                except Exception:
                    pass
                if modal_serie is not None:
                    modal_serie.open = False
                    try:
                        modal_serie.update()
                    except Exception:
                        pass
                try:
                    page.update()
                except Exception:
                    pass

            def escolher_escopo(escopo: str):
                fechar_modal_serie()
                executar_salvamento(escopo)

            modal_serie = ft.AlertDialog(
                title=ft.Row([
                    ft.Icon(ft.Icons.UPDATE_ROUNDED, color=T.PRIMARY, size=22),
                    ft.Text("Atualizar Recorrência", weight=ft.FontWeight.BOLD),
                ], spacing=8),
                content=ft.Text(
                    "Este lançamento faz parte de uma série ou agendamento recorrente. "
                    "Como você deseja aplicar as alterações?",
                    size=14,
                    color=T.TEXT_MUTED,
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda _: fechar_modal_serie()),
                    ft.FilledButton("Somente este", on_click=lambda _: escolher_escopo("individual")),
                    ft.FilledButton(
                        "Este e os próximos",
                        style=ft.ButtonStyle(bgcolor=T.PRIMARY, color=T.ON_PRIMARY),
                        on_click=lambda _: escolher_escopo("proximos"),
                    ),
                ],
            )
            page.show_dialog(modal_serie)
            return

        executar_salvamento("individual")

    btn_salvar.on_click = ao_clicar_salvar

    # 5. Construção da Janela (Header + Corpo + Rodapé Fixo)
    titulo_texto = "Editar Lançamento" if is_edicao else "Novo Lançamento"
    icone_titulo = ft.Icons.EDIT_ROUNDED if is_edicao else ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED

    header_row = ft.Row(
        controls=[
            ft.Row(
                controls=[
                    ft.Icon(icone_titulo, color=T.PRIMARY, size=22),
                    ft.Text(titulo_texto, size=18, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ],
                spacing=8,
                tight=True,
            ),
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_color=T.TEXT_MUTED,
                tooltip="Fechar (ESC)",
                on_click=fechar_dialog,
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    if mobile:
        # BottomSheet para Mobile (scrollable=True é obrigatório no Flet 1.0.1 para não cortar a metade inferior!)
        altura_sheet = int((page.height or 760) * 0.86)
        conteudo_sheet = ft.Container(
            content=ft.Column(
                controls=[
                    header_row,
                    ft.Divider(height=1, color=T.BORDER),
                    ft.Container(content=form, expand=True),
                    ft.Divider(height=1, color=T.BORDER),
                    ft.Row(
                        controls=[btn_cancelar, ft.Container(content=btn_salvar, expand=True)],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                    ),
                ],
                spacing=10,
                expand=True,
            ),
            padding=pad(h=16, v=12),
            height=altura_sheet,
            bgcolor=T.SURFACE,
        )
        container_dialog = ft.BottomSheet(
            content=conteudo_sheet,
            show_drag_handle=True,
            scrollable=True,
            dismissible=True,
            bgcolor=T.SURFACE,
            on_dismiss=_ao_dispensar_dialog,
        )
    else:
        # AlertDialog para Desktop usando slots nativos title, content e actions
        # Assim o cabeçalho e o botão Salvar ficam 100% fixos e visíveis sem corte.
        altura_disp = int((page.height or 768) * 0.58)
        altura_corpo = max(340, min(440, altura_disp))

        container_dialog = ft.AlertDialog(
            modal=False,  # Permite fechar com tecla ESC ou clique fora
            bgcolor=T.SURFACE,
            shape=ft.RoundedRectangleBorder(radius=16),
            inset_padding=pad(h=20, v=16),
            title_padding=pad(left=20, right=12, top=14, bottom=0),
            content_padding=pad(left=20, right=20, top=8, bottom=8),
            actions_padding=pad(left=20, right=20, top=8, bottom=16),
            actions_alignment=ft.MainAxisAlignment.END,
            title= ft.Column(
                controls=[
                    header_row,
                    ft.Divider(height=1, color=T.BORDER),
                ],
                spacing=6,
                tight=True,
            ),
            content=ft.Container(
                content=form,
                width=480,
                height=altura_corpo,
            ),
            actions=[
                btn_cancelar,
                btn_salvar,
            ],
            on_dismiss=_ao_dispensar_dialog,
        )

    page.show_dialog(container_dialog)
