"""
=============================================================================
DemBase v3 — views/cartoes_view.py  (Flet 1.0.1)
Gestão de Cartões de Crédito, Limites e Faturas.
Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
import flet as ft
from datetime import date
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, hoje
from views.shell_view import criar_shell, ROTA_CARTOES
import services.supabase_client as db

BANDEIRAS = ["Mastercard", "Visa", "Elo", "American Express", "Hipercard", "Outra"]

CORES_CARTOES = [
    {"label": "Roxo Nubank",   "hex": "#820AD1"},
    {"label": "Laranja Inter", "hex": "#FF7A00"},
    {"label": "Azul Escuro",   "hex": "#0F172A"},
    {"label": "Dourado Black", "hex": "#1E293B"},
    {"label": "Esmeralda",     "hex": "#10B981"},
    {"label": "Vermelho",      "hex": "#DC2626"},
    {"label": "Azul Itaú",     "hex": "#003399"},
]


def criar_view_cartoes(page: ft.Page) -> ft.View:
    hoje_d = hoje()
    mes_sel = [hoje_d.month]
    ano_sel = [hoje_d.year]

    cartoes_lista = []
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    txt_total_limite     = ft.Text("R$ 0,00", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD)
    txt_total_disponivel = ft.Text("R$ 0,00", color=T.PRIMARY,      size=18, weight=ft.FontWeight.BOLD)
    txt_total_faturas    = ft.Text("R$ 0,00", color=T.WARNING,      size=18, weight=ft.FontWeight.BOLD)
    txt_qtd_cartoes      = ft.Text("0 cartões", color=T.TEXT_MUTED,  size=18, weight=ft.FontWeight.BOLD)

    grid_cartoes = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])

    # ── Carregar Dados ────────────────────────────────────────────────────────
    def carregar_cartoes():
        spinner.visible = True
        page.update()
        nonlocal cartoes_lista
        try:
            cartoes_lista = db.listar_cartoes()

            resumo = {}
            try:
                resumo = db.obter_resumo_cartoes(mes_sel[0], ano_sel[0])
            except Exception:
                pass

            total_limite = resumo.get("total_limite")
            total_disp   = resumo.get("total_disponivel")
            total_fat    = resumo.get("total_faturas")

            if total_limite is None:
                total_limite = sum(float(c.get("limite_total", 0) or 0) for c in cartoes_lista)
            if total_disp is None:
                total_disp   = sum(float(c.get("limite_disponivel", c.get("limite_total", 0)) or 0) for c in cartoes_lista)
            if total_fat is None:
                total_fat    = max(0.0, float(total_limite) - float(total_disp))

            txt_total_limite.value     = formatar_moeda(float(total_limite or 0))
            txt_total_disponivel.value = formatar_moeda(float(total_disp or 0))
            txt_total_faturas.value    = formatar_moeda(float(total_fat or 0))
            txt_qtd_cartoes.value      = f"{len(cartoes_lista)} ativo(s)"

            renderizar_cards()
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao listar cartões: {ex}", "erro")
        finally:
            spinner.visible = False
            page.update()

    # ── Modal de Criação / Edição ─────────────────────────────────────────────
    def abrir_modal_cartao(cartao_edicao: dict = None):
        eh_edicao = cartao_edicao is not None
        titulo_modal = "Editar Cartão" if eh_edicao else "Novo Cartão de Crédito"

        txt_nome = ft.TextField(
            label="Nome do Cartão *",
            hint_text="Ex: Nubank Mastercard, XP Visa Infinite",
            value=cartao_edicao.get("nome", "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        dd_bandeira = ft.Dropdown(
            label="Bandeira *",
            options=[ft.dropdown.Option(b) for b in BANDEIRAS],
            value=cartao_edicao.get("bandeira", BANDEIRAS[0]) if eh_edicao else BANDEIRAS[0],
            **T.dropdown_estilo(),
        )

        txt_limite = ft.TextField(
            label="Limite Total (R$) *",
            hint_text="Ex: 5000,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=str(cartao_edicao.get("limite_total", "")) if eh_edicao else "",
            **T.campo_estilo(),
        )

        txt_fechamento = ft.TextField(
            label="Dia Fechamento *",
            hint_text="1 a 31",
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(cartao_edicao.get("dia_fechamento", "1")) if eh_edicao else "1",
            **T.campo_estilo(),
        )

        txt_vencimento = ft.TextField(
            label="Dia Vencimento *",
            hint_text="1 a 31",
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(cartao_edicao.get("dia_vencimento", "10")) if eh_edicao else "10",
            **T.campo_estilo(),
        )

        # Contas para débito automático (opcional)
        contas_disponiveis = db.listar_contas()
        opts_contas = [ft.dropdown.Option(key="", text="Nenhuma (Manual)")] + [
            ft.dropdown.Option(key=str(c["id"]), text=c["nome"]) for c in contas_disponiveis
        ]
        dd_conta_debito = ft.Dropdown(
            label="Conta para Débito Automático (Opcional)",
            options=opts_contas,
            value=str(cartao_edicao.get("conta_debito_id") or "") if eh_edicao else "",
            **T.dropdown_estilo(),
        )

        cor_selecionada = [cartao_edicao.get("cor", CORES_CARTOES[0]["hex"]) if eh_edicao else CORES_CARTOES[0]["hex"]]

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
                for c in CORES_CARTOES
            ],
        )

        def salvar_cartao(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome do cartão.", "alerta")
                return

            try:
                limite_num = float(txt_limite.value.replace(",", ".").replace("R$", "").strip() or 0)
                if limite_num <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um limite válido maior que zero.", "alerta")
                return

            try:
                fech = int(txt_fechamento.value or 1)
                venc = int(txt_vencimento.value or 1)
                if not (1 <= fech <= 31 and 1 <= venc <= 31):
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Dias de fechamento e vencimento devem ser entre 1 e 31.", "alerta")
                return

            dados = {
                "nome": nome,
                "bandeira": dd_bandeira.value,
                "cor": cor_selecionada[0],
                "icone": "credit_card",
                "limite_total": limite_num,
                "dia_fechamento": fech,
                "dia_vencimento": venc,
                "conta_debito_id": dd_conta_debito.value or None,
                "ativo": True,
            }

            try:
                if eh_edicao:
                    db.atualizar_cartao(cartao_edicao["id"], dados)
                    mostrar_feedback(page, "Cartão atualizado!", "sucesso")
                else:
                    db.criar_cartao(dados)
                    mostrar_feedback(page, "Cartão criado com sucesso!", "sucesso")

                modal.open = False
                page.update()
                carregar_cartoes()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

        def fechar_modal(_):
            modal.open = False
            page.update()

        modal = ft.AlertDialog(
            title=ft.Text(titulo_modal, color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=450,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        txt_nome,
                        ft.Row([ft.Container(content=dd_bandeira, expand=True), ft.Container(content=txt_limite, expand=True)], spacing=10),
                        ft.Row([ft.Container(content=txt_fechamento, expand=True), ft.Container(content=txt_vencimento, expand=True)], spacing=10),
                        dd_conta_debito,
                        ft.Text("Cor do Cartão", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                        row_cores,
                    ],
                ),
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=fechar_modal),
                ft.FilledButton(content=ft.Text("Salvar Cartão", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600), style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar_cartao),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(modal)
        modal.open = True
        page.update()

    def confirmar_exclusao_cartao(cartao: dict):
        def _executar(_):
            dialog.open = False
            page.update()
            try:
                db.deletar_cartao(cartao["id"])
                mostrar_feedback(page, "Cartão inativado!", "sucesso")
                carregar_cartoes()
            except Exception as ex:
                mostrar_feedback(page, f"Erro: {ex}", "erro")

        dialog = ft.AlertDialog(
            title=ft.Text("Inativar Cartão", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text(f"Deseja inativar o cartão '{cartao.get('nome')}'? As faturas existentes serão mantidas.", color=T.TEXT_MUTED, size=14),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: (setattr(dialog, "open", False), page.update())),
                ft.FilledButton(content=ft.Text("Inativar", color=ft.Colors.WHITE), style=ft.ButtonStyle(bgcolor=T.DESPESA), on_click=_executar),
            ],
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # ── Renderizar Cards dos Cartões ──────────────────────────────────────────
    def renderizar_cards():
        grid_cartoes.controls.clear()

        if not cartoes_lista:
            grid_cartoes.controls.append(
                ft.Container(
                    col={"xs": 12},
                    padding=pad(all_=50),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.CREDIT_CARD_OUTLINED, size=54, color=T.TEXT_MUTED),
                            ft.Text("Nenhum cartão cadastrado", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Cadastre seus cartões de crédito para controlar faturas, limites e parcelamentos.", color=T.TEXT_MUTED, size=13),
                            ft.Container(height=8),
                            ft.FilledButton(
                                content=ft.Row(
                                    spacing=6, tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                        ft.Text("Cadastrar Cartão", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                on_click=lambda _: abrir_modal_cartao(),
                                style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=16, v=12)),
                            ),
                        ],
                    ),
                )
            )
            return

        for cartao in cartoes_lista:
            cor_cartao = cartao.get("cor") or "#1E293B"
            lim_total = float(cartao.get("limite_total", 0) or 0)
            lim_disp  = float(cartao.get("limite_disponivel", lim_total) or 0)
            fatura_est = max(0.0, lim_total - lim_disp)
            progresso = min(1.0, max(0.0, (lim_total - lim_disp) / lim_total)) if lim_total > 0 else 0.0

            fech = cartao.get("dia_fechamento", 1)
            venc = cartao.get("dia_vencimento", 10)
            bandeira = cartao.get("bandeira", "Mastercard")

            card = ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=20),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(),
                content=ft.Column(
                    spacing=14,
                    controls=[
                        # Visual do "Plástico" do Cartão
                        ft.Container(
                            padding=pad(all_=16),
                            bgcolor=cor_cartao,
                            border_radius=12,
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Icon(ft.Icons.CONTACTLESS_ROUNDED, color=ft.Colors.WHITE70, size=24),
                                            ft.Text(bandeira.upper(), color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                    ft.Container(height=8),
                                    ft.Text(cartao.get("nome", "Cartão"), color=ft.Colors.WHITE, size=16, weight=ft.FontWeight.BOLD),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(f"Fecha dia {fech}", color=ft.Colors.WHITE70, size=11),
                                            ft.Text(f"Vence dia {venc}", color=ft.Colors.WHITE, size=11, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        # Detalhes de Limite e Uso
                        ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text("Fatura Estimada", color=T.TEXT_MUTED, size=12),
                                        ft.Text(formatar_moeda(fatura_est), color=T.WARNING, size=13, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.ProgressBar(value=progresso, color=T.WARNING if progresso < 0.8 else T.DESPESA, bgcolor=T.SURFACE_ALT, height=6),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"Disponível: {formatar_moeda(lim_disp)}", color=T.PRIMARY, size=11, weight=ft.FontWeight.W_500),
                                        ft.Text(f"Limite: {formatar_moeda(lim_total)}", color=T.TEXT_MUTED, size=11),
                                    ],
                                ),
                            ],
                        ),
                        # Botões de Edição e Ações
                        ft.Row(
                            alignment=ft.MainAxisAlignment.END,
                            spacing=8,
                            controls=[
                                ft.TextButton(
                                    content=ft.Row([ft.Icon(ft.Icons.EDIT_OUTLINED, size=14, color=T.TEXT_MUTED), ft.Text("Editar", color=T.TEXT_MUTED, size=12)]),
                                    on_click=lambda _, c=cartao: abrir_modal_cartao(c),
                                ),
                                ft.TextButton(
                                    content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINE, size=14, color=T.DESPESA), ft.Text("Inativar", color=T.DESPESA, size=12)]),
                                    on_click=lambda _, c=cartao: confirmar_exclusao_cartao(c),
                                ),
                            ],
                        ),
                    ],
                ),
            )
            grid_cartoes.controls.append(card)

    # ── KPIs Topo ─────────────────────────────────────────────────────────────
    def _kpi(titulo: str, ref_ctrl: ft.Control, cor: str, icone):
        return ft.Container(
            col={"xs": 6, "sm": 3},
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
            _kpi("Limite Total",        txt_total_limite,     T.TEXT_PRIMARY, ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED),
            _kpi("Limite Disponível",   txt_total_disponivel, T.PRIMARY,      ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED),
            _kpi("Faturas Abertas",     txt_total_faturas,    T.WARNING,      ft.Icons.CREDIT_CARD_ROUNDED),
            _kpi("Cartões Ativos",      txt_qtd_cartoes,      T.INFO,         ft.Icons.PAYMENTS_OUTLINED),
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
                        ft.Text("Cartões de Crédito", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                        spinner,
                    ]),
                    ft.Text("Controle limites, faturas e parcelamentos em um só lugar", color=T.TEXT_MUTED, size=12),
                ],
            ),
            ft.FilledButton(
                content=ft.Row(
                    spacing=6, tight=True,
                    controls=[
                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text("Novo Cartão", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                    ],
                ),
                on_click=lambda _: abrir_modal_cartao(),
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    overlay_color=T.PRIMARY_DARK,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=pad(h=16, v=12),
                ),
            ),
        ],
    )

    def on_mes_ano_change(m: int, a: int):
        mes_sel[0] = m
        ano_sel[0] = a
        carregar_cartoes()

    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=18),
            kpis_topo,
            ft.Container(height=24),
            grid_cartoes,
            ft.Container(height=30),
        ],
    )

    carregar_cartoes()

    return criar_shell(page, rota_ativa=ROTA_CARTOES, conteudo=conteudo, on_mes_ano_change=on_mes_ano_change)
