"""
=============================================================================
DemBase v3 — views/contas_view.py  (Flet 1.0.1)
Gestão de Contas Bancárias e Carteiras com Drill-down para Extrato Analítico.
- Clicar em qualquer conta abre /contas/:conta_id (Extrato e Gráficos da Conta)
- Menu ⋮ isolado para Editar / Inativar sem conflito de clique
- Exibe entradas, saídas e qtd de movimentações no período global ativo
=============================================================================
"""
from __future__ import annotations
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.constants import (
    formatar_moeda,
    formatar_data_br,
    parse_moeda_seguro,
    formatar_moeda_input,
)
from core.periodo import obter_estado_periodo_atual
from core.nav import ir_conta, ir_relatorio_lancamentos
from core.report_context import ReportContext
from core.responsive import is_mobile
from views.shell_view import criar_shell, ROTA_CONTAS
from views.widgets.clickable_card import kpi_clicavel
import services.supabase_client as db

TIPOS_CONTA_OPCOES = [
    ("corrente", "Conta Corrente"),
    ("poupanca", "Conta Poupança"),
    ("dinheiro", "Carteira / Dinheiro"),
    ("investimento", "Investimento"),
    ("outro", "Outros"),
]
LABELS_TIPOS_CONTA = dict(TIPOS_CONTA_OPCOES)

CORES_PRESET = [
    {"label": "Esmeralda", "hex": "#10B981"},
    {"label": "Azul",      "hex": "#3B82F6"},
    {"label": "Roxo",      "hex": "#8B5CF6"},
    {"label": "Laranja",   "hex": "#F97316"},
    {"label": "Vermelho",  "hex": "#EF4444"},
    {"label": "Dourado",   "hex": "#F59E0B"},
    {"label": "Grafite",   "hex": "#64748B"},
]


def criar_view_contas(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    est_p = obter_estado_periodo_atual(page)
    data_ini_sel = [est_p["data_inicio"].isoformat()]
    data_fim_sel = [est_p["data_fim"].isoformat()]

    contas_lista: list[dict] = []
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    tam_kpi = 15 if mobile else 18
    txt_total_atual    = ft.Text("R$ 0,00", color=T.PRIMARY, size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_previsto = ft.Text("R$ 0,00", color=T.TEXT_MUTED, size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_mov      = ft.Text("R$ 0,00", color=T.RECEITA, size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_qtd_contas     = ft.Text("0 ativa(s)", color=T.INFO, size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_sub_periodo    = ft.Text(
        f"Movimentação no período: {formatar_data_br(data_ini_sel[0])} a {formatar_data_br(data_fim_sel[0])}",
        color=T.TEXT_MUTED,
        size=12,
    )

    grid_contas = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])

    def _safe_update():
        try:
            txt_total_atual.update()
            txt_total_previsto.update()
            txt_total_mov.update()
            txt_qtd_contas.update()
            grid_contas.update()
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

    # ── Carregar Dados ────────────────────────────────────────────────────────
    def carregar_contas(d_ini: str | None = None, d_fim: str | None = None, inicial: bool = False):
        if d_ini:
            data_ini_sel[0] = d_ini
        if d_fim:
            data_fim_sel[0] = d_fim

        txt_sub_periodo.value = (
            f"Movimentação no período: {formatar_data_br(data_ini_sel[0])} a {formatar_data_br(data_fim_sel[0])}"
        )

        if not inicial:
            spinner.visible = True
            _safe_update()

        nonlocal contas_lista
        try:
            pacote = db.obter_lista_contas_resumo(data_ini_sel[0], data_fim_sel[0])
            contas_lista = pacote.get("contas") or []
            total_atual = pacote.get("saldo_total_atual")
            total_prev  = pacote.get("saldo_total_previsto")
            total_ent   = pacote.get("entradas_periodo_total")
            total_sai   = pacote.get("saidas_periodo_total")

            if total_atual is None:
                total_atual = sum(float(c.get("saldo_atual", c.get("saldo_inicial", 0)) or 0) for c in contas_lista)
            if total_prev is None:
                total_prev  = sum(float(c.get("saldo_previsto", c.get("saldo_inicial", 0)) or 0) for c in contas_lista)
            if total_ent is None:
                total_ent   = sum(float(c.get("entradas_periodo", 0) or 0) for c in contas_lista)
            if total_sai is None:
                total_sai   = sum(float(c.get("saidas_periodo", 0) or 0) for c in contas_lista)

            mov_periodo = float(total_ent or 0) - float(total_sai or 0)

            txt_total_atual.value    = formatar_moeda(float(total_atual or 0))
            txt_total_previsto.value = formatar_moeda(float(total_prev or 0))
            txt_total_mov.value      = formatar_moeda(mov_periodo)
            txt_total_mov.color      = T.RECEITA if mov_periodo >= 0 else T.DESPESA
            txt_qtd_contas.value     = f"{len(contas_lista)} ativa(s)"

            renderizar_cards()
        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao listar contas: {ex}", "erro")
        finally:
            spinner.visible = False
            if not inicial:
                _safe_update()

    # ── Modal de Criação / Edição ─────────────────────────────────────────────
    def abrir_modal_conta(conta_edicao: dict | None = None):
        eh_edicao = conta_edicao is not None
        titulo_modal = "Editar Conta" if eh_edicao else "Nova Conta"

        txt_nome = ft.TextField(
            label="Nome da Conta *",
            hint_text="Ex: Santander, Nubank, Carteira",
            value=(conta_edicao.get("nome") or "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        tipo_inicial = (
            db.normalizar_tipo_conta(conta_edicao.get("tipo_conta"))
            if eh_edicao
            else "corrente"
        )
        dd_tipo = ft.Dropdown(
            label="Tipo de Conta *",
            options=[ft.dropdown.Option(key=k, text=lbl) for k, lbl in TIPOS_CONTA_OPCOES],
            value=tipo_inicial,
            **T.dropdown_estilo(),
        )

        txt_banco = ft.TextField(
            label="Instituição / Banco (Opcional)",
            hint_text="Ex: Itaú Unibanco, Inter",
            value=(conta_edicao.get("banco") or "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        # No modo edição, o saldo exibido e manipulado pelo usuário é o Saldo Atual da Conta
        saldo_base = (
            float(conta_edicao.get("saldo_atual", conta_edicao.get("saldo_inicial", 0.0)) or 0.0)
            if eh_edicao
            else 0.0
        )
        val_saldo = formatar_moeda_input(saldo_base)

        lbl_saldo = "Saldo da Conta (R$)" if eh_edicao else "Saldo Inicial (R$)"
        hlp_saldo = (
            "Saldo atual da conta bancária (o valor digitado atualizará o card imediatamente)."
            if eh_edicao
            else "Saldo de partida ao cadastrar a conta (valores negativos permitidos, ex: -150,00)."
        )

        txt_saldo = ft.TextField(
            label=lbl_saldo,
            hint_text="0,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=val_saldo,
            helper=hlp_saldo,
            helper_style=ft.TextStyle(size=11, color=T.TEXT_MUTED),
            **T.campo_estilo(),
        )

        cor_padrao = conta_edicao.get("cor") if eh_edicao else None
        cor_selecionada = [cor_padrao or CORES_PRESET[0]["hex"]]

        def _selecionar_cor(hex_cor):
            cor_selecionada[0] = hex_cor
            for c_box in row_cores.controls:
                c_box.border = borda(2, ft.Colors.WHITE) if c_box.data == hex_cor else borda(1, T.BORDER)
            _safe_update()

        row_cores = ft.Row(
            spacing=8,
            controls=[
                ft.Container(
                    width=28,
                    height=28,
                    bgcolor=c["hex"],
                    border_radius=14,
                    data=c["hex"],
                    border=borda(2, ft.Colors.WHITE) if c["hex"] == cor_selecionada[0] else borda(1, T.BORDER),
                    tooltip=c["label"],
                    on_click=lambda _, h=c["hex"]: _selecionar_cor(h),
                )
                for c in CORES_PRESET
            ],
        )

        def salvar_conta(_):
            nome = (txt_nome.value or "").strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da conta.", "alerta")
                return

            saldo_digitado = parse_moeda_seguro(txt_saldo.value)
            banco_val = (txt_banco.value or "").strip() or None

            dados = {
                "nome": nome,
                "tipo_conta": db.normalizar_tipo_conta(dd_tipo.value),
                "banco": banco_val,
                "cor": cor_selecionada[0],
                "icone": "account_balance",
                "ativo": True,
            }

            try:
                if eh_edicao:
                    old_atual = float(conta_edicao.get("saldo_atual", conta_edicao.get("saldo_inicial", 0.0)) or 0.0)
                    old_ini = float(conta_edicao.get("saldo_inicial", 0.0) or 0.0)
                    old_prev = float(conta_edicao.get("saldo_previsto", old_atual) or 0.0)

                    # Diferença exata entre o saldo desejado pelo usuário e o saldo atual anterior
                    diff = saldo_digitado - old_atual

                    # Atualiza os 3 saldos de forma matematicamente alinhada
                    dados["saldo_atual"] = float(round(saldo_digitado, 2))
                    dados["saldo_inicial"] = float(round(old_ini + diff, 2))
                    dados["saldo_previsto"] = float(round(old_prev + diff, 2))

                    resp = db.atualizar_conta(conta_edicao["id"], dados)
                    if not (resp and resp.data):
                        raise RuntimeError(
                            "O banco de dados não confirmou a atualização da conta. "
                            "Verifique suas permissões de acesso ou conexão com o Supabase."
                        )
                    msg_ok = "Conta atualizada com sucesso!"
                else:
                    saldo_val = float(round(saldo_digitado, 2))
                    dados["saldo_inicial"] = saldo_val
                    dados["saldo_atual"] = saldo_val
                    dados["saldo_previsto"] = saldo_val
                    resp = db.criar_conta(dados)
                    if not (resp and resp.data):
                        raise RuntimeError(
                            "O banco de dados não confirmou a criação da conta. "
                            "Verifique suas permissões de acesso ou conexão com o Supabase."
                        )
                    msg_ok = "Conta criada com sucesso!"

                fechar_dialogo(page, modal)
                mostrar_feedback(page, msg_ok, "sucesso")
                carregar_contas(inicial=False)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

        def fechar_modal(_):
            fechar_dialogo(page, modal)

        modal = ft.AlertDialog(
            title=ft.Text(titulo_modal, color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        txt_nome,
                        dd_tipo,
                        txt_banco,
                        txt_saldo,
                        ft.Text("Cor da Conta", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                        row_cores,
                    ],
                ),
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=fechar_modal),
                ft.FilledButton(
                    content=ft.Text("Salvar", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar_conta,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        abrir_dialogo(page, modal)

    def confirmar_exclusao_conta(conta: dict):
        def _executar(_):
            fechar_dialogo(page, dialog)
            try:
                db.deletar_conta(conta["id"])
                mostrar_feedback(page, "Conta inativada com sucesso!", "sucesso")
                carregar_contas(inicial=False)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao excluir: {ex}", "erro")

        dialog = ft.AlertDialog(
            title=ft.Text("Inativar Conta", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"Deseja inativar a conta '{conta.get('nome')}'? Os lançamentos históricos permanecerão seguros.",
                color=T.TEXT_MUTED, size=14,
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: fechar_dialogo(page, dialog)),
                ft.FilledButton(content=ft.Text("Inativar", color=ft.Colors.WHITE), style=ft.ButtonStyle(bgcolor=T.DESPESA), on_click=_executar),
            ],
        )
        abrir_dialogo(page, dialog)

    # ── Renderizar Cards Clicáveis (Drill-down para /contas/:conta_id) ────────
    def renderizar_cards():
        grid_contas.controls.clear()

        if not contas_lista:
            grid_contas.controls.append(
                ft.Container(
                    col={"xs": 12},
                    padding=pad(all_=50),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.ACCOUNT_BALANCE_OUTLINED, size=54, color=T.TEXT_MUTED),
                            ft.Text("Nenhuma conta cadastrada ainda", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Cadastre suas contas bancárias ou carteiras para organizar seu saldo.", color=T.TEXT_MUTED, size=13),
                            ft.Container(height=8),
                            ft.FilledButton(
                                content=ft.Row(
                                    spacing=6, tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                        ft.Text("Criar Primeira Conta", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                on_click=lambda _: abrir_modal_conta(),
                                style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=16, v=12)),
                            ),
                        ],
                    ),
                )
            )
            return

        for conta in contas_lista:
            cid = str(conta.get("id") or "")
            cor_conta = conta.get("cor") or T.PRIMARY
            saldo_atual = float(conta.get("saldo_atual", conta.get("saldo_inicial", 0)) or 0)
            saldo_prev  = float(conta.get("saldo_previsto", conta.get("saldo_inicial", 0)) or 0)
            entradas_p  = float(conta.get("entradas_periodo", 0) or 0)
            saidas_p    = float(conta.get("saidas_periodo", 0) or 0)
            qtd_mov     = int(conta.get("qtd_movimentos", 0) or 0)

            def _ir_extrato_conta(_=None, conta_id_alvo=cid):
                if conta_id_alvo:
                    ir_conta(page, conta_id_alvo)

            # Área superior esquerda clicável (Ícone + Nome da Conta)
            area_identificacao = ft.Container(
                expand=True,
                on_click=_ir_extrato_conta,
                ink=True,
                border_radius=10,
                padding=pad(v=2, h=2),
                content=ft.Row(
                    spacing=10,
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, color=cor_conta, size=20),
                            bgcolor=f"{cor_conta}1A",
                            border_radius=10,
                            padding=pad(all_=10),
                        ),
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text(
                                    conta.get("nome", "Conta"),
                                    color=T.TEXT_PRIMARY,
                                    size=15,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                                ft.Text(
                                    LABELS_TIPOS_CONTA.get(
                                        db.normalizar_tipo_conta(conta.get("tipo_conta")),
                                        "Conta Corrente",
                                    ),
                                    color=T.TEXT_MUTED,
                                    size=11,
                                ),
                            ],
                        ),
                    ],
                ),
            )

            # Menu ⋮ separado da área de clique principal para evitar propagação acidental
            menu_acoes = ft.PopupMenuButton(
                icon=ft.Icons.MORE_VERT_ROUNDED,
                icon_color=T.TEXT_MUTED,
                icon_size=18,
                tooltip="Opções da conta",
                items=[
                    ft.PopupMenuItem(
                        content=ft.Row([ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=16, color=T.PRIMARY), ft.Text("Ver Extrato da Conta")]),
                        on_click=_ir_extrato_conta,
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row([ft.Icon(ft.Icons.EDIT_OUTLINED, size=16), ft.Text("Editar Conta")]),
                        on_click=lambda _, c=conta: abrir_modal_conta(c),
                    ),
                    ft.PopupMenuItem(
                        content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE, size=16, color=T.DESPESA), ft.Text("Inativar", color=T.DESPESA)]),
                        on_click=lambda _, c=conta: confirmar_exclusao_conta(c),
                    ),
                ],
            )

            # Corpo inferior clicável (Saldos + Resumo de Entradas/Saídas no Período + Call-to-action)
            corpo_clicavel = ft.Container(
                on_click=_ir_extrato_conta,
                ink=True,
                border_radius=10,
                padding=pad(v=4, h=2),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text("Saldo Atual", color=T.TEXT_MUTED, size=11),
                                        ft.Text(
                                            formatar_moeda(saldo_atual),
                                            color=T.PRIMARY if saldo_atual >= 0 else T.DESPESA,
                                            size=17,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ],
                                ),
                                ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    spacing=2,
                                    controls=[
                                        ft.Text("Saldo Previsto", color=T.TEXT_MUTED, size=11),
                                        ft.Text(formatar_moeda(saldo_prev), color=T.TEXT_MUTED, size=13.5, weight=ft.FontWeight.W_500),
                                    ],
                                ),
                            ],
                        ),
                        # Faixa de movimentação do período selecionado
                        ft.Container(
                            padding=pad(h=10, v=7),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=10,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                wrap=True if mobile else False,
                                spacing=4,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        controls=[
                                            ft.Text(
                                                f"↑ {formatar_moeda(entradas_p)}",
                                                color=T.RECEITA,
                                                size=11,
                                                weight=ft.FontWeight.W_600,
                                            ),
                                            ft.Text(
                                                f"↓ {formatar_moeda(saidas_p)}",
                                                color=T.DESPESA,
                                                size=11,
                                                weight=ft.FontWeight.W_600,
                                            ),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=4,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Text(
                                                f"{qtd_mov} mov." if qtd_mov > 0 else "Ver extrato",
                                                color=cor_conta,
                                                size=11,
                                                weight=ft.FontWeight.W_600,
                                            ),
                                            ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=cor_conta, size=15),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                    ],
                ),
            )

            card_box = ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=16),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(1, T.BORDER),
                animate=ft.Animation(150, ft.AnimationCurve.EASE_OUT),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[area_identificacao, menu_acoes],
                        ),
                        ft.Divider(color=T.BORDER, height=1),
                        corpo_clicavel,
                    ],
                ),
            )

            def _on_hover_card(e, box=card_box, cor_h=cor_conta):
                try:
                    hovered = str(e.data).lower() == "true" or e.data is True
                    box.border = borda(1.4, f"{cor_h}80") if hovered else borda(1, T.BORDER)
                    box.update()
                except Exception:
                    pass

            card_box.on_hover = _on_hover_card
            grid_contas.controls.append(card_box)

    # ── KPIs Topo Clicáveis (2x2 no Mobile, 1x4 no Desktop) ───────────────────
    kpis_topo = ft.ResponsiveRow(
        spacing=8 if mobile else 12, run_spacing=8 if mobile else 12,
        controls=[
            kpi_clicavel(
                titulo="Saldo em Contas",
                valor_control=txt_total_atual,
                subtitulo="Saldo consolidado",
                icone=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                cor=T.PRIMARY,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, origem="contas"),
            ),
            kpi_clicavel(
                titulo="Saldo Previsto",
                valor_control=txt_total_previsto,
                subtitulo="Com pendentes",
                icone=ft.Icons.SAVINGS_OUTLINED,
                cor=T.TEXT_MUTED,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, status="Pendente", origem="contas"),
            ),
            kpi_clicavel(
                titulo="Movimentação",
                valor_control=txt_total_mov,
                subtitulo="Fluxo no período",
                icone=ft.Icons.SWAP_VERT_ROUNDED,
                cor=T.RECEITA,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
                on_click=lambda _: ir_relatorio_lancamentos(page, origem="contas"),
            ),
            kpi_clicavel(
                titulo="Contas Ativas",
                valor_control=txt_qtd_contas,
                subtitulo="Cadastradas no app",
                icone=ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                cor=T.INFO,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
        ],
    )

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
        controls=[
            ft.Column(
                spacing=2,
                expand=True,
                controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Text("Contas Bancárias", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                        spinner,
                    ]),
                    txt_sub_periodo,
                ],
            ),
            ft.FilledButton(
                content=ft.Row(
                    spacing=6, tight=True,
                    controls=[
                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text("Nova Conta", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                    ],
                ),
                on_click=lambda _: abrir_modal_conta(),
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    overlay_color=T.PRIMARY_DARK,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=pad(h=16, v=12),
                ),
            ),
        ],
    )

    def on_periodo(d_ini: str, d_fim: str, m: int, a: int):
        carregar_contas(d_ini=d_ini, d_fim=d_fim, inicial=False)

    def on_mes_ano(m: int, a: int):
        est = obter_estado_periodo_atual(page)
        carregar_contas(
            d_ini=est["data_inicio"].isoformat(),
            d_fim=est["data_fim"].isoformat(),
            inicial=False,
        )

    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=18),
            kpis_topo,
            ft.Container(height=24),
            grid_contas,
            ft.Container(height=30),
        ],
    )

    carregar_contas(inicial=True)

    return criar_shell(
        page,
        rota_ativa=ROTA_CONTAS,
        conteudo=conteudo,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar_contas(inicial=False),
    )
