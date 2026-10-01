"""
=============================================================================
DemBase v3 — views/contas_view.py  (Flet 1.0.1)
Gestão de Contas Bancárias e Carteiras.
Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda
from views.shell_view import criar_shell, ROTA_CONTAS
import services.supabase_client as db

TIPOS_CONTA = ["Conta Corrente", "Conta Poupança", "Carteira / Dinheiro", "Investimento", "Outros"]

CORES_PRESET = [
    {"label": "Esmeralda", "hex": "#10B981"},
    {"label": "Azul",      "hex": "#3B82F6"},
    {"label": "Roxo",      "hex": "#8B5CF6"},
    {"label": "Laranja",   "hex": "#F97316"},
    {"label": "Vermelho",  "hex": "#EF4444"},
    {"label": "Dourado",   "hex": "#F59E0B"},
    {"label": "Grafite",   "hex": "#64748B"},
]


def criar_view_contas(page: ft.Page) -> ft.View:
    contas_lista = []
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    txt_total_atual    = ft.Text("R$ 0,00", color=T.PRIMARY, size=20, weight=ft.FontWeight.BOLD)
    txt_total_previsto = ft.Text("R$ 0,00", color=T.TEXT_MUTED, size=20, weight=ft.FontWeight.BOLD)
    txt_qtd_contas     = ft.Text("0 contas", color=T.TEXT_PRIMARY, size=20, weight=ft.FontWeight.BOLD)

    grid_contas = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])

    # ── Carregar Dados ────────────────────────────────────────────────────────
    def carregar_contas():
        spinner.visible = True
        page.update()
        nonlocal contas_lista
        try:
            contas_lista = db.listar_contas()
            resumo = {}
            try:
                resumo = db.obter_resumo_contas()
            except Exception:
                pass

            total_atual = resumo.get("saldo_total_atual")
            total_prev  = resumo.get("saldo_total_previsto")

            if total_atual is None:
                total_atual = sum(float(c.get("saldo_atual", c.get("saldo_inicial", 0)) or 0) for c in contas_lista)
            if total_prev is None:
                total_prev  = sum(float(c.get("saldo_previsto", c.get("saldo_inicial", 0)) or 0) for c in contas_lista)

            txt_total_atual.value    = formatar_moeda(float(total_atual or 0))
            txt_total_previsto.value = formatar_moeda(float(total_prev or 0))
            txt_qtd_contas.value     = f"{len(contas_lista)} ativa(s)"

            renderizar_cards()
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao listar contas: {ex}", "erro")
        finally:
            spinner.visible = False
            page.update()

    # ── Modal de Criação / Edição ─────────────────────────────────────────────
    def abrir_modal_conta(conta_edicao: dict = None):
        eh_edicao = conta_edicao is not None
        titulo_modal = "Editar Conta" if eh_edicao else "Nova Conta"

        txt_nome = ft.TextField(
            label="Nome da Conta *",
            hint_text="Ex: Santander, Nubank, Carteira",
            value=conta_edicao.get("nome", "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        dd_tipo = ft.Dropdown(
            label="Tipo de Conta *",
            options=[ft.dropdown.Option(t) for t in TIPOS_CONTA],
            value=conta_edicao.get("tipo_conta", TIPOS_CONTA[0]) if eh_edicao else TIPOS_CONTA[0],
            **T.dropdown_estilo(),
        )

        txt_banco = ft.TextField(
            label="Instituição / Banco (Opcional)",
            hint_text="Ex: Itaú Unibanco, Inter",
            value=conta_edicao.get("banco", "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        txt_saldo_ini = ft.TextField(
            label="Saldo Inicial (R$)",
            hint_text="0,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=str(conta_edicao.get("saldo_inicial", "0.00")) if eh_edicao else "0,00",
            **T.campo_estilo(),
        )

        cor_selecionada = [conta_edicao.get("cor", CORES_PRESET[0]["hex"]) if eh_edicao else CORES_PRESET[0]["hex"]]

        def _selecionar_cor(hex_cor):
            cor_selecionada[0] = hex_cor
            for c_box in row_cores.controls:
                c_box.border = borda(2, ft.Colors.WHITE) if c_box.data == hex_cor else borda(1, T.BORDER)
            page.update()

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
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da conta.", "alerta")
                return

            try:
                saldo_ini = float(txt_saldo_ini.value.replace(",", ".").replace("R$", "").strip() or 0)
            except ValueError:
                saldo_ini = 0.0

            dados = {
                "nome": nome,
                "tipo_conta": dd_tipo.value,
                "banco": txt_banco.value.strip() or None,
                "saldo_inicial": saldo_ini,
                "cor": cor_selecionada[0],
                "icone": "account_balance",
                "ativo": True,
            }

            try:
                if eh_edicao:
                    db.atualizar_conta(conta_edicao["id"], dados)
                    mostrar_feedback(page, "Conta atualizada com sucesso!", "sucesso")
                else:
                    db.criar_conta(dados)
                    mostrar_feedback(page, "Conta criada com sucesso!", "sucesso")

                modal.open = False
                page.update()
                carregar_contas()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

        def fechar_modal(_):
            modal.open = False
            page.update()

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
                        txt_saldo_ini,
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

        page.overlay.append(modal)
        modal.open = True
        page.update()

    def confirmar_exclusao_conta(conta: dict):
        def _executar(_):
            dialog.open = False
            page.update()
            try:
                db.deletar_conta(conta["id"])
                mostrar_feedback(page, "Conta inativada com sucesso!", "sucesso")
                carregar_contas()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao excluir: {ex}", "erro")

        dialog = ft.AlertDialog(
            title=ft.Text("Inativar Conta", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"Deseja inativar a conta '{conta.get('nome')}'? Os lançamentos históricos permanecerão seguros.",
                color=T.TEXT_MUTED, size=14,
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: (setattr(dialog, "open", False), page.update())),
                ft.FilledButton(content=ft.Text("Inativar", color=ft.Colors.WHITE), style=ft.ButtonStyle(bgcolor=T.DESPESA), on_click=_executar),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # ── Renderizar Cards ──────────────────────────────────────────────────────
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
            cor_conta = conta.get("cor") or T.PRIMARY
            saldo_atual = float(conta.get("saldo_atual", conta.get("saldo_inicial", 0)) or 0)
            saldo_prev  = float(conta.get("saldo_previsto", conta.get("saldo_inicial", 0)) or 0)

            card = ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=18),
                bgcolor=T.SURFACE,
                border_radius=14,
                border=borda(),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        # Topo do Card: Ícone colorido + Nome + Menu Ações
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
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
                                            controls=[
                                                ft.Text(conta.get("nome", "Conta"), color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                                                ft.Text(conta.get("tipo_conta", "Conta Corrente"), color=T.TEXT_MUTED, size=11),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.PopupMenuButton(
                                    icon=ft.Icons.MORE_VERT_ROUNDED,
                                    icon_color=T.TEXT_MUTED,
                                    icon_size=18,
                                    items=[
                                        ft.PopupMenuItem(
                                            content=ft.Row([ft.Icon(ft.Icons.EDIT_OUTLINED, size=16), ft.Text("Editar")]),
                                            on_click=lambda _, c=conta: abrir_modal_conta(c),
                                        ),
                                        ft.PopupMenuItem(
                                            content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE, size=16, color=T.DESPESA), ft.Text("Inativar", color=T.DESPESA)]),
                                            on_click=lambda _, c=conta: confirmar_exclusao_conta(c),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.Divider(color=T.BORDER, height=1),
                        # Saldos
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text("Saldo Atual", color=T.TEXT_MUTED, size=11),
                                        ft.Text(formatar_moeda(saldo_atual), color=T.PRIMARY if saldo_atual >= 0 else T.DESPESA, size=16, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.Column(
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    spacing=2,
                                    controls=[
                                        ft.Text("Saldo Previsto", color=T.TEXT_MUTED, size=11),
                                        ft.Text(formatar_moeda(saldo_prev), color=T.TEXT_MUTED, size=14, weight=ft.FontWeight.W_500),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )
            grid_contas.controls.append(card)

    # ── KPIs Topo ─────────────────────────────────────────────────────────────
    def _kpi(titulo: str, ref_ctrl: ft.Control, cor: str, icone):
        return ft.Container(
            col={"xs": 12, "sm": 4},
            padding=pad(all_=16),
            bgcolor=T.SURFACE,
            border_radius=14,
            border=borda(),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(titulo, color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                            ft.Icon(icone, color=cor, size=18),
                        ],
                    ),
                    ref_ctrl,
                ],
            ),
        )

    kpis_topo = ft.ResponsiveRow(
        spacing=12, run_spacing=12,
        controls=[
            _kpi("Saldo Total em Contas", txt_total_atual,    T.PRIMARY, ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED),
            _kpi("Saldo Previsto Total",   txt_total_previsto, T.TEXT_MUTED, ft.Icons.SAVINGS_OUTLINED),
            _kpi("Contas Cadastradas",     txt_qtd_contas,     T.INFO,    ft.Icons.CREDIT_CARD_ROUNDED),
        ],
    )

    # ── Cabeçalho ─────────────────────────────────────────────────────────────
    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=2,
                controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Text("Contas Bancárias", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                        spinner,
                    ]),
                    ft.Text("Gerencie seus saldos, instituições e carteiras", color=T.TEXT_MUTED, size=12),
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

    carregar_contas()

    return criar_shell(page, rota_ativa=ROTA_CONTAS, conteudo=conteudo)
