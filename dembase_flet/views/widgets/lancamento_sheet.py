"""
=============================================================================
DemBase v3 — views/widgets/lancamento_sheet.py (Flet 1.0.1)
Hospedeiro responsivo para o formulário de lançamentos:
- Mobile (<768px): BottomSheet rolável com drag handle.
- Desktop (>=768px): AlertDialog compacto com largura controlada.
Gerencia ciclo de vida, persistência e suporte a edição de séries/recorrências.
=============================================================================
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Optional

import flet as ft

from core.lancamento_state import LancamentoFormState
from core.responsive import is_mobile
import core.theme as T
from core.theme import pad, borda, mostrar_feedback
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
    """
    is_edicao = (lancamento is not None and bool(lancamento.get("id")))

    # 1. Montagem do Estado
    state = LancamentoFormState()
    if is_edicao:
        state.lancamento_id = str(lancamento["id"])
        state.serie_id = str(lancamento.get("serie_id")) if lancamento.get("serie_id") else None
        state.recorrente_id = str(lancamento.get("recorrente_id")) if lancamento.get("recorrente_id") else None
        state.tipo = lancamento.get("tipo", "Despesa")
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
                state.data_selecionada = datetime.fromisoformat(d_raw).date()
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

    # 3. Definição do Contêiner (Mobile vs Desktop)
    mobile = is_mobile(page)
    container_dialog = None

    def fechar_dialog():
        nonlocal container_dialog
        if container_dialog:
            container_dialog.open = False
            try:
                page.pop_dialog()
            except Exception:
                pass
            try:
                page.update()
            except Exception:
                pass

    # Botões de Ação
    btn_salvar = ft.FilledButton(
        content=ft.Row(
            controls=[
                ft.Icon(ft.Icons.CHECK_ROUNDED, size=18),
                ft.Text("Salvar" if is_edicao else "Confirmar", weight=ft.FontWeight.BOLD),
            ],
            spacing=6,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            color=T.ON_PRIMARY,
        ),
    )

    btn_cancelar = ft.TextButton(
        content=ft.Text("Cancelar", color=T.TEXT_MUTED),
        on_click=lambda _: fechar_dialog(),
    )

    def executar_salvamento(modo_serie: str = "individual"):
        btn_salvar.disabled = True
        btn_salvar.content = ft.ProgressRing(width=16, height=16, stroke_width=2, color=T.ON_PRIMARY)
        try:
            page.update()
        except Exception:
            pass

        try:
            dados = {
                "tipo": state.tipo,
                "subtipo": state.subtipo,
                "forma_movimentacao": state.forma_movimentacao,
                "valor": state.valor,
                "data": str(state.data_selecionada),
                "hora": state.hora,
                "descricao": state.descricao.strip(),
                "status": "Pago" if state.status_pago else "Pendente",
                "conta_id": state.conta_id,
                "cartao_id": state.cartao_id,
                "categoria_id": state.categoria_id,
                "subcategoria_id": state.subcategoria_id,
                "destino_id": state.destino_id,
                "regra": state.regra if state.tipo == "Despesa" else None,
            }

            if is_edicao:
                if modo_serie == "proximos" and state.serie_id:
                    db.atualizar_serie(state.serie_id, dados, a_partir_de=str(state.data_selecionada))
                else:
                    db.atualizar_lancamento(state.lancamento_id, dados)
                mostrar_feedback(page, "Lançamento atualizado com sucesso!", "sucesso")
            else:
                modo = state.modo_recorrencia()
                valor_modo = "parcelado" if (state.tipo == "Despesa" and state.forma_movimentacao == "Credito") else "repetido"
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
            btn_salvar.content = ft.Row(
                controls=[
                    ft.Icon(ft.Icons.CHECK_ROUNDED, size=18),
                    ft.Text("Salvar" if is_edicao else "Confirmar", weight=ft.FontWeight.BOLD),
                ],
                spacing=6,
                alignment=ft.MainAxisAlignment.CENTER,
            )
            try:
                page.update()
            except Exception:
                pass
            mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

    def ao_clicar_salvar(_):
        valido, erro_msg = state.validar()
        if not valido:
            mostrar_feedback(page, erro_msg or "Verifique os campos obrigatórios.", "alerta")
            return

        # Se for edição de lançamento que pertence a uma série/recorrência, perguntar o escopo
        if is_edicao and (state.serie_id or state.recorrente_id):
            modal_serie = None

            def escolher_escopo(escopo: str):
                nonlocal modal_serie
                if modal_serie:
                    modal_serie.open = False
                    try:
                        page.update()
                    except Exception:
                        pass
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
                    ft.TextButton("Cancelar", on_click=lambda _: (setattr(modal_serie, "open", False), page.update())),
                    ft.FilledButton("Somente este", on_click=lambda _: escolher_escopo("individual")),
                    ft.FilledButton(
                        "Este e os próximos",
                        style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                        on_click=lambda _: escolher_escopo("proximos"),
                    ),
                ],
            )
            page.overlay.append(modal_serie)
            modal_serie.open = True
            page.update()
            return

        executar_salvamento("individual")

    btn_salvar.on_click = ao_clicar_salvar

    # 4. Construção da Janela
    titulo_texto = "Editar Lançamento" if is_edicao else "Novo Lançamento"
    icone_titulo = ft.Icons.EDIT_ROUNDED if is_edicao else ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED

    header_row = ft.Row(
        controls=[
            ft.Row(
                controls=[
                    ft.Icon(icone_titulo, color=T.PRIMARY, size=22),
                    ft.Text(titulo_texto, size=18, weight=ft.FontWeight.BOLD),
                ],
                spacing=8,
            ),
            ft.IconButton(
                icon=ft.Icons.CLOSE_ROUNDED,
                icon_color=T.TEXT_MUTED,
                tooltip="Fechar",
                on_click=lambda _: fechar_dialog(),
            ),
        ],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )

    actions_row = ft.Row(
        controls=[btn_cancelar, btn_salvar],
        alignment=ft.MainAxisAlignment.END,
        spacing=10,
    )

    if mobile:
        # BottomSheet para Mobile
        conteudo_sheet = ft.Container(
            content=ft.Column(
                controls=[
                    header_row,
                    ft.Divider(height=1, color=T.BORDER),
                    ft.Container(content=form, expand=True),
                    ft.Divider(height=1, color=T.BORDER),
                    actions_row,
                ],
                spacing=12,
                expand=True,
            ),
            padding=pad(h=16, v=14),
            height=page.height * 0.88 if getattr(page, "height", None) else 660,
        )
        container_dialog = ft.BottomSheet(
            content=conteudo_sheet,
            show_drag_handle=True,
            scrollable=False,
        )
    else:
        # AlertDialog para Desktop
        conteudo_dialog = ft.Container(
            content=ft.Column(
                controls=[
                    header_row,
                    ft.Divider(height=1, color=T.BORDER),
                    ft.Container(content=form, height=480),
                    ft.Divider(height=1, color=T.BORDER),
                    actions_row,
                ],
                spacing=12,
                tight=True,
            ),
            width=500,
            padding=pad(h=20, v=16),
            border_radius=16,
        )
        container_dialog = ft.AlertDialog(
            content=conteudo_dialog,
            modal=True,
            inset_padding=pad(20),
        )

    page.overlay.append(container_dialog)
    container_dialog.open = True
    page.update()
