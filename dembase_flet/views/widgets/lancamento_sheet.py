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
from core.potes import obter_regra_pote
from core.responsive import is_mobile
import core.theme as T
from core.theme import pad, mostrar_feedback
import services.supabase_client as db
import services.potes_service as potes_svc
from views.widgets.lancamento_form import LancamentoForm


def abrir_lancamento(
    page: ft.Page,
    tipo_inicial: Optional[str] = None,
    lancamento: Optional[dict] = None,
    on_saved: Optional[Callable[[], None]] = None,
    conta_inicial: Optional[str] = None,
    cartao_inicial: Optional[str] = None,
    categoria_inicial: Optional[str] = None,
    regra_inicial: Optional[str] = None,
    pote_inicial: Optional[str] = None,
):
    """
    Abre o modal/bottom sheet de criação ou edição de lançamento financeiro.
    Usa a pilha nativa de diálogos do Flet 1.0.1 (page.show_dialog / page.pop_dialog).
    """
    raw_id = None
    if lancamento is not None and isinstance(lancamento, dict):
        raw_id = lancamento.get("id") or lancamento.get("lancamento_id") or lancamento.get("id_lancamento")
    is_edicao = bool(raw_id)

    # 1. Montagem do Estado
    state = LancamentoFormState()
    if is_edicao:
        state.lancamento_id = str(raw_id)
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
        regra_salva = lancamento.get("regra")
        pote_salvo = lancamento.get("pote_id")
        state.pote_id = str(pote_salvo) if pote_salvo else None
        state.regra = obter_regra_pote(regra_salva or pote_salvo)
        state.fatura_id = str(lancamento.get("fatura_id")) if lancamento.get("fatura_id") else None
        state.hora = int(lancamento.get("hora", 12)) if lancamento.get("hora") is not None else 12
        state.status_pago = (lancamento.get("status") == "Pago")
        state.status_manual = True  # Em edição, status gravado tem prioridade absoluta

        # Inicializa dados específicos de compras parceladas
        p_atual = lancamento.get("parcela_atual")
        if p_atual is not None:
            try:
                state.parcela_atual = int(p_atual)
            except Exception:
                pass

        t_parc = lancamento.get("total_parcelas")
        if t_parc is not None:
            try:
                tot_int = int(t_parc)
                if tot_int > 0:
                    state.total_parcelas_original = tot_int
                    state.quantidade = tot_int
            except Exception:
                pass

        # Se tiver serie_id mas os campos de parcela vieram nulos, busca resumo da série
        if state.serie_id and (state.parcela_atual is None or state.total_parcelas_original is None):
            try:
                resumo_s = db.obter_resumo_serie_parcelamento(state.serie_id)
                if resumo_s.get("sucesso") and resumo_s.get("parcelas"):
                    parcs = resumo_s["parcelas"]
                    curr = next((p for p in parcs if str(p.get("id")) == str(state.lancamento_id)), None)
                    if curr:
                        if state.parcela_atual is None:
                            state.parcela_atual = curr.get("parcela_atual") or 1
                        if state.total_parcelas_original is None:
                            tot_orig = curr.get("total_parcelas") or resumo_s.get("max_parcela") or len(parcs)
                            state.total_parcelas_original = int(tot_orig)
                            state.quantidade = int(tot_orig)
                        if not state.fatura_id and curr.get("fatura_id"):
                            state.fatura_id = str(curr.get("fatura_id"))
            except Exception as ex_load_serie:
                print(f"[LancamentoSheet] Aviso ao carregar detalhes da série: {ex_load_serie}")

        state.fatura_id_original = state.fatura_id

        # Se for compra parcelada no cartão, ajusta cálculo para modo parcela
        if state.is_compra_parcelada and state.quantidade > 1:
            state.modo_calculo_parcela = "parcela"
            state.definir_valor_parcela(state.valor)

        d_raw = lancamento.get("data")
        if isinstance(d_raw, str):
            try:
                state.data_selecionada = datetime.fromisoformat(d_raw[:10]).date()
            except Exception:
                state.data_selecionada = date.today()
        elif isinstance(d_raw, (date, datetime)):
            state.data_selecionada = d_raw if isinstance(d_raw, date) else d_raw.date()

        if lancamento.get("tipo_recorrencia") == "fixa" or bool(lancamento.get("recorrente_id")):
            state.is_fixa = True

        # Abre detalhes caso o registro já tenha dados secundários
        if state.subcategoria_id or state.subtipo or state.serie_id or state.recorrente_id:
            state.mais_detalhes_aberto = True
    else:
        if tipo_inicial:
            state.mudar_tipo(tipo_inicial)
        if cartao_inicial:
            state.mudar_tipo("Despesa")
            state.mudar_forma("Crédito")
            state.cartao_id = str(cartao_inicial)
        elif conta_inicial:
            state.conta_id = str(conta_inicial)
        if categoria_inicial:
            state.categoria_id = str(categoria_inicial)
        if regra_inicial and state.eh_despesa:
            state.regra = obter_regra_pote(regra_inicial)
            state.mais_detalhes_aberto = True
        if pote_inicial and state.eh_despesa:
            state.pote_id = str(pote_inicial)
            state.regra = obter_regra_pote(pote_inicial)

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

    salvando_lock = [False]

    def executar_salvamento(modo_serie: str = "individual", aplicar_cascata: bool = False, redimensionar: bool = False):
        if salvando_lock[0]:
            return
        salvando_lock[0] = True
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

            # Resolução da Fatura Manual (se selecionada pelo usuário)
            fatura_id_final = None
            if state.eh_credito and cartao_id_final and state.fatura_id:
                fat_str = str(state.fatura_id).strip()
                if fat_str.startswith("futura_"):
                    try:
                        fat_obj = db.obter_ou_criar_fatura_por_mes_ano(
                            cartao_id_final,
                            state.fatura_manual_mes,
                            state.fatura_manual_ano,
                        )
                        if fat_obj and fat_obj.get("id"):
                            fatura_id_final = str(fat_obj["id"])
                    except Exception as ex_fat:
                        print(f"[LancamentoSheet] Aviso ao criar fatura futura: {ex_fat}")
                else:
                    fatura_id_final = fat_str

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
                "fatura_id": fatura_id_final,
                "categoria_id": cat_id_final,
                "subcategoria_id": subcat_id_final,
                "destino_id": destino_id_final,
                "regra": obter_regra_pote(state.regra or state.pote_id) if state.eh_despesa else None,
                "pote_id": str(state.pote_id) if (state.eh_despesa and state.pote_id) else None,
                "caixinha_id": form._obter_caixinha_id(state.caixinha_id) if state.eh_despesa else None,
            }

            if is_edicao:
                if not state.lancamento_id:
                    raise ValueError("ID da transação não encontrado para atualização.")

                # 1. Redimensionamento de Parcelas (se alterado)
                if redimensionar and state.quantidade_parcelas_alterada and state.serie_id:
                    novo_val_parc = (
                        round(state.obter_valor_parcela(), 2)
                        if (state.eh_credito and not state.is_fixa and state.quantidade > 1)
                        else None
                    )
                    res_redim = db.redimensionar_parcelamento(
                        state.serie_id,
                        state.quantidade,
                        novo_valor_parcela=novo_val_parc,
                    )
                    if not res_redim.get("sucesso", True):
                        raise RuntimeError(res_redim.get("erro", "Erro ao redimensionar parcelas."))

                # 2. Deslocamento de Fatura (se alterada)
                if state.fatura_foi_alterada and state.fatura_id:
                    # Aplica lógica de cascata exclusivamente para COMPRAS PARCELADAS reais
                    if state.is_compra_parcelada and state.serie_id and not state.is_fixa and not state.recorrente_id:
                        res_desloc = db.deslocar_faturas_parcelamento(
                            state.lancamento_id,
                            state.fatura_id,
                            aplicar_cascata=aplicar_cascata,
                        )
                        if not res_desloc.get("sucesso", True):
                            raise RuntimeError(res_desloc.get("erro", "Erro ao deslocar faturas."))
                        delta = res_desloc.get("delta", 0)
                        if delta and aplicar_cascata:
                            d = state.data_selecionada
                            total_m = (d.year * 12 + d.month - 1) + delta
                            n_ano = total_m // 12
                            n_mes = (total_m % 12) + 1
                            import calendar
                            max_d = calendar.monthrange(n_ano, n_mes)[1]
                            dados["data"] = str(date(n_ano, n_mes, min(d.day, max_d)))
                    else:
                        # Assinatura recorrente ou lançamento avulso:
                        # APENAS associa à nova fatura, mantendo estritamente a data original da transação
                        # para evitar qualquer colisão na restrição de data única (idx_lancamentos_rec_data)
                        dados["fatura_id"] = state.fatura_id
                        fats_recalc = [f for f in [state.fatura_id_original, state.fatura_id] if f]
                        if fats_recalc:
                            try:
                                db.recalcular_totais_faturas(fats_recalc)
                            except Exception:
                                pass

                # 3. Atualização do registro corrente
                if state.eh_credito and not state.is_fixa and state.quantidade > 1:
                    dados["valor"] = round(state.obter_valor_parcela(), 2)
                    dados["total_parcelas"] = state.quantidade
                    if state.parcela_atual:
                        dados["parcela_atual"] = state.parcela_atual

                # Realiza OBRIGATORIAMENTE o UPDATE na linha existente (jamais INSERT duplicado)
                db.atualizar_lancamento(state.lancamento_id, dados)

                if modo_serie == "proximos" and (state.serie_id or state.recorrente_id):
                    try:
                        db.atualizar_serie(
                            state.serie_id or state.recorrente_id,
                            dados,
                            a_partir_de=str(state.data_selecionada),
                        )
                    except Exception as ex_serie:
                        print(f"[LancamentoSheet] Aviso ao atualizar série: {ex_serie}")

                if state.eh_receita:
                    try:
                        potes_svc.redistribuir_receita(state.lancamento_id, dados["valor"])
                    except Exception:
                        pass

                # Invalida caches para atualizar telas imediatamente
                db.invalidar_cache("faturas")
                db.invalidar_cache("cartoes")
                db.invalidar_cache("lancamentos")

                mostrar_feedback(page, "Lançamento atualizado com sucesso!", "sucesso")
            else:
                modo = state.modo_recorrencia()
                valor_modo = "parcelado" if (state.eh_credito and modo == "parcelada") else "repetido"
                res = db.criar_lancamento_recorrente(
                    dados=dados,
                    modo=modo,
                    frequencia=state.frequencia,
                    quantidade=state.quantidade,
                    valor_modo=valor_modo,
                )
                if not res.get("sucesso", True):
                    raise RuntimeError(res.get("erro", "Falha ao gravar lançamento."))

                if state.eh_receita:
                    try:
                        lanc_id = res.get("id") or (res.get("lancamento", {}).get("id") if isinstance(res.get("lancamento"), dict) else None)
                        if lanc_id:
                            potes = potes_svc.carregar_potes()
                            dist = potes_svc.P.distribuir_valor(dados["valor"], potes)
                            db.registrar_distribuicao_receita(lanc_id, dist)
                    except Exception:
                        pass

                if state.caixinha_id:
                    try:
                        db.recalcular_saldo_caixinha(state.caixinha_id)
                        db.invalidar_cache("caixinhas")
                    except Exception as ex_cx:
                        print(f"[LancamentoSheet] Aviso ao atualizar saldo da caixinha: {ex_cx}")

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
        finally:
            salvando_lock[0] = False

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
            state.caixinha_id = form._obter_caixinha_id(state.caixinha_id or form.dd_caixinha.value) if state.eh_despesa else None

        valido, erro_msg = state.validar()
        if not valido:
            mostrar_feedback(page, erro_msg or "Verifique os campos obrigatórios.", "alerta")
            return

        # Modal Helper para fechar caixas de diálogo no Flet 1.0.1
        def _fechar_modal(dlg):
            try:
                page.pop_dialog()
            except Exception:
                pass
            if dlg is not None:
                dlg.open = False
                try:
                    dlg.update()
                except Exception:
                    pass
            try:
                page.update()
            except Exception:
                pass

        # CENÁRIO 1: Edição de Compra Parcelada com Shift de Fatura ou Mudança de Parcelas
        if is_edicao and state.is_compra_parcelada and state.serie_id and not state.is_fixa and not state.recorrente_id:
            mudou_fatura = state.fatura_foi_alterada
            mudou_qtd = state.quantidade_parcelas_alterada

            # Validação prévia de redução menor que parcelas pagas
            if mudou_qtd and state.quantidade < (state.total_parcelas_original or 1):
                try:
                    resumo_chk = db.obter_resumo_serie_parcelamento(state.serie_id)
                    pagas_cnt = resumo_chk.get("pagas", 0)
                    if state.quantidade < pagas_cnt:
                        mostrar_feedback(
                            page,
                            f"Não é possível reduzir para {state.quantidade}x pois já existem {pagas_cnt} parcelas pagas no histórico.",
                            "alerta",
                        )
                        return
                except Exception:
                    pass

            def _abrir_dialogo_redimensionamento(aplicar_cascata_val: bool):
                orig = state.total_parcelas_original or 1
                novo = state.quantidade
                modal_redim = None

                def _confirmar_redim():
                    _fechar_modal(modal_redim)
                    executar_salvamento(modo_serie="individual", aplicar_cascata=aplicar_cascata_val, redimensionar=True)

                if novo < orig:
                    msg = (
                        f"Você está reduzindo o total de parcelas de {orig}x para {novo}x.\n\n"
                        f"As {orig - novo} parcelas finais pendentes serão canceladas e excluídas do cartão.\n\n"
                        "Deseja confirmar a alteração?"
                    )
                    btn_text = "Confirmar Redução"
                else:
                    msg = (
                        f"Você está expandindo o total de parcelas de {orig}x para {novo}x.\n\n"
                        f"Serão geradas automaticamente {novo - orig} novas parcelas nos meses seguintes.\n\n"
                        "Deseja confirmar a alteração?"
                    )
                    btn_text = "Confirmar Expansão"

                modal_redim = ft.AlertDialog(
                    title=ft.Row([
                        ft.Icon(ft.Icons.LAYERS_CLEAR_ROUNDED if novo < orig else ft.Icons.LAYERS_ROUNDED, color=T.PRIMARY, size=22),
                        ft.Text("Redimensionar Compra", weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    content=ft.Text(msg, size=14, color=T.TEXT_MUTED),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda _: _fechar_modal(modal_redim)),
                        ft.FilledButton(
                            btn_text,
                            style=ft.ButtonStyle(bgcolor=T.PRIMARY, color=T.ON_PRIMARY),
                            on_click=lambda _: _confirmar_redim(),
                        ),
                    ],
                )
                page.show_dialog(modal_redim)

            if mudou_fatura:
                modal_cascata = None

                def _escolher_cascata(aplicar: bool):
                    _fechar_modal(modal_cascata)
                    if mudou_qtd:
                        _abrir_dialogo_redimensionamento(aplicar_cascata_val=aplicar)
                    else:
                        executar_salvamento(modo_serie="individual", aplicar_cascata=aplicar, redimensionar=False)

                modal_cascata = ft.AlertDialog(
                    title=ft.Row([
                        ft.Icon(ft.Icons.MOVE_UP_ROUNDED, color=T.PRIMARY, size=22),
                        ft.Text("Deslocamento de Fatura", weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    content=ft.Text(
                        f"Você alterou a fatura da Parcela {state.parcela_atual or 1}.\n\n"
                        "Deseja aplicar esse mesmo deslocamento em efeito cascata nas parcelas seguintes desta compra?",
                        size=14,
                        color=T.TEXT_MUTED,
                    ),
                    actions=[
                        ft.TextButton("Cancelar", on_click=lambda _: _fechar_modal(modal_cascata)),
                        ft.OutlinedButton("Apenas esta parcela", on_click=lambda _: _escolher_cascata(False)),
                        ft.FilledButton(
                            "Sim, em cascata",
                            style=ft.ButtonStyle(bgcolor=T.PRIMARY, color=T.ON_PRIMARY),
                            on_click=lambda _: _escolher_cascata(True),
                        ),
                    ],
                )
                page.show_dialog(modal_cascata)
                return

            if mudou_qtd:
                _abrir_dialogo_redimensionamento(aplicar_cascata_val=False)
                return

        # CENÁRIO 2: Edição geral de série existente (recorrente ou parcelada sem mudança de fatura/qtd)
        total_parc = int(lancamento.get("total_parcelas", 1) or 1) if (lancamento and isinstance(lancamento, dict)) else 1
        tem_serie_real = bool(state.recorrente_id) or (bool(state.serie_id) and (total_parc > 1 or state.is_fixa))

        if is_edicao and tem_serie_real:
            modal_serie = None

            def escolher_escopo(escopo: str):
                _fechar_modal(modal_serie)
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
                    ft.TextButton("Cancelar", on_click=lambda _: _fechar_modal(modal_serie)),
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
