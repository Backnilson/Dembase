"""
=============================================================================
Projeto: DemBase - MVP de Controle Financeiro
Arquivo: main.py
Etapa 3: Interface Principal, Roteamento Dinâmico, Autenticação e Layout Responsivo (Flet)

UI/UX Moderna, Minimalista e Fluida
- Transição Inteligente de Janela: Compacta no Login (400x600, centralizada) e
  Maximizada no Dashboard.
- Barra do Sistema Operacional Intacta (NÃO utiliza frameless nem oculta botões).
- Layout do Dashboard 100% estruturado com ResponsiveRow.
- Separação Estrita de Responsabilidades: Nenhuma query de banco reside aqui.
  Todas as operações são orquestradas via 'backend.py'.
=============================================================================
"""

import flet as ft
from backend import (
    cadastrar_usuario,
    fazer_login,
    fazer_logout,
    obter_sessao_atual,
    ler_perfil_logado,
    obter_totais_dashboard,
)

from ui_utils import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_ALT, COLOR_BORDER,
    COLOR_PRIMARY, COLOR_PRIMARY_HOVER, COLOR_PRIMARY_LIGHT,
    COLOR_RECEITA, COLOR_DESPESA, COLOR_SALDO,
    COLOR_TEXT_PRIMARY, COLOR_TEXT_MUTED,
    COLOR_ERROR, COLOR_WARNING, COLOR_INFO,
    traduzir_erro_auth, mostrar_feedback
)
from views.lancamentos import criar_view_lancamentos

# =============================================================================
# 3. TELA DE AUTENTICAÇÃO (LOGIN & CADASTRO COMPACTA)
# =============================================================================
def criar_view_auth(page: ft.Page) -> ft.View:
    """
    Cria a View de autenticação compacta, otimizada para janelas de 400x600,
    com alternância instantânea entre Login e Cadastro, validações e loading.
    """
    # Estado da tela (True: Login, False: Cadastro)
    modo_login = [True]

    # --- Campos de Entrada ---
    txt_nome = ft.TextField(
        label="Nome Completo",
        hint_text="Seu nome ou apelido",
        prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
        border_color=COLOR_BORDER,
        focused_border_color=COLOR_PRIMARY,
        border_radius=10,
        filled=True,
        fill_color=COLOR_SURFACE_ALT,
        cursor_color=COLOR_PRIMARY,
        text_size=13,
        label_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=11),
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        visible=False,
    )

    txt_email = ft.TextField(
        label="E-mail",
        hint_text="exemplo@email.com",
        prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED,
        border_color=COLOR_BORDER,
        focused_border_color=COLOR_PRIMARY,
        border_radius=10,
        filled=True,
        fill_color=COLOR_SURFACE_ALT,
        cursor_color=COLOR_PRIMARY,
        text_size=13,
        label_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=11),
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        keyboard_type=ft.KeyboardType.EMAIL,
    )

    txt_senha = ft.TextField(
        label="Senha",
        hint_text="Mínimo 6 caracteres",
        prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True,
        can_reveal_password=True,
        border_color=COLOR_BORDER,
        focused_border_color=COLOR_PRIMARY,
        border_radius=10,
        filled=True,
        fill_color=COLOR_SURFACE_ALT,
        cursor_color=COLOR_PRIMARY,
        text_size=13,
        label_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=11),
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
    )

    txt_confirmar_senha = ft.TextField(
        label="Confirmar Senha",
        hint_text="Repita sua senha",
        prefix_icon=ft.Icons.LOCK_RESET_ROUNDED,
        password=True,
        can_reveal_password=True,
        border_color=COLOR_BORDER,
        focused_border_color=COLOR_PRIMARY,
        border_radius=10,
        filled=True,
        fill_color=COLOR_SURFACE_ALT,
        cursor_color=COLOR_PRIMARY,
        text_size=13,
        label_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=COLOR_TEXT_MUTED, size=11),
        content_padding=ft.padding.symmetric(horizontal=12, vertical=10),
        visible=False,
    )

    # --- Elementos do Botão Principal com Loading ---
    spinner_loading = ft.ProgressRing(
        width=16,
        height=16,
        stroke_width=2.2,
        color=COLOR_TEXT_PRIMARY,
        visible=False,
    )

    lbl_btn_principal = ft.Text(
        "Acessar Conta",
        size=14,
        weight=ft.FontWeight.BOLD,
        color=COLOR_TEXT_PRIMARY,
    )

    btn_principal = ft.Container(
        content=ft.Row(
            controls=[spinner_loading, lbl_btn_principal],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        bgcolor=COLOR_PRIMARY,
        border_radius=10,
        height=44,
        alignment=ft.alignment.center,
        animate=ft.Animation(180, ft.AnimationCurve.EASE_OUT),
        ink=True,
    )

    # Subtítulo explicativo dinâmico
    lbl_subtitulo = ft.Text(
        "Controle Financeiro Pessoal",
        size=12,
        color=COLOR_TEXT_MUTED,
        text_align=ft.TextAlign.CENTER,
    )

    # Botão de alternância inferior
    lbl_alternar = ft.Text(
        "Não possui conta? Cadastre-se",
        size=11,
        color=COLOR_PRIMARY_LIGHT,
        weight=ft.FontWeight.W_500,
        text_align=ft.TextAlign.CENTER,
    )

    # --- Abas Superiores (Pills) ---
    btn_tab_login = ft.Container(
        content=ft.Text("Entrar", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
        padding=ft.padding.symmetric(vertical=6, horizontal=18),
        border_radius=8,
        bgcolor=COLOR_PRIMARY,
        alignment=ft.alignment.center,
        animate=ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT),
    )

    btn_tab_cadastro = ft.Container(
        content=ft.Text("Cadastrar", size=12, weight=ft.FontWeight.W_500, color=COLOR_TEXT_MUTED),
        padding=ft.padding.symmetric(vertical=6, horizontal=18),
        border_radius=8,
        bgcolor=ft.Colors.TRANSPARENT,
        alignment=ft.alignment.center,
        animate=ft.Animation(180, ft.AnimationCurve.EASE_IN_OUT),
    )

    def atualizar_modo_interface(e=None):
        if modo_login[0]:
            btn_tab_login.bgcolor = COLOR_PRIMARY
            btn_tab_login.content.color = COLOR_TEXT_PRIMARY
            btn_tab_login.content.weight = ft.FontWeight.BOLD

            btn_tab_cadastro.bgcolor = ft.Colors.TRANSPARENT
            btn_tab_cadastro.content.color = COLOR_TEXT_MUTED
            btn_tab_cadastro.content.weight = ft.FontWeight.W_500

            txt_nome.visible = False
            txt_confirmar_senha.visible = False
            lbl_btn_principal.value = "Acessar Conta"
            lbl_subtitulo.value = "Controle Financeiro Pessoal"
            lbl_alternar.value = "Não possui conta? Cadastre-se"
        else:
            btn_tab_login.bgcolor = ft.Colors.TRANSPARENT
            btn_tab_login.content.color = COLOR_TEXT_MUTED
            btn_tab_login.content.weight = ft.FontWeight.W_500

            btn_tab_cadastro.bgcolor = COLOR_PRIMARY
            btn_tab_cadastro.content.color = COLOR_TEXT_PRIMARY
            btn_tab_cadastro.content.weight = ft.FontWeight.BOLD

            txt_nome.visible = True
            txt_confirmar_senha.visible = True
            lbl_btn_principal.value = "Criar Minha Conta"
            lbl_subtitulo.value = "Crie sua conta para começar"
            lbl_alternar.value = "Já possui uma conta? Entrar"

        page.update()

    def alternar_para_login(e):
        if not modo_login[0]:
            modo_login[0] = True
            atualizar_modo_interface()

    def alternar_para_cadastro(e):
        if modo_login[0]:
            modo_login[0] = False
            atualizar_modo_interface()

    def alternar_modo_toggle(e):
        modo_login[0] = not modo_login[0]
        atualizar_modo_interface()

    btn_tab_login.on_click = alternar_para_login
    btn_tab_cadastro.on_click = alternar_para_cadastro

    # --- Ação Principal de Autenticação ---
    def executar_autenticacao(e):
        email = txt_email.value.strip() if txt_email.value else ""
        senha = txt_senha.value.strip() if txt_senha.value else ""

        # Validações de entrada
        if not email:
            mostrar_feedback(page, "Por favor, informe seu e-mail.", "alerta")
            txt_email.focus()
            return

        if "@" not in email or "." not in email:
            mostrar_feedback(page, "Formato de e-mail inválido.", "alerta")
            txt_email.focus()
            return

        if not senha:
            mostrar_feedback(page, "Por favor, digite sua senha.", "alerta")
            txt_senha.focus()
            return

        if len(senha) < 6:
            mostrar_feedback(page, "A senha deve ter no mínimo 6 caracteres.", "alerta")
            txt_senha.focus()
            return

        if not modo_login[0]:
            nome = txt_nome.value.strip() if txt_nome.value else ""
            conf_senha = txt_confirmar_senha.value.strip() if txt_confirmar_senha.value else ""

            if not nome:
                mostrar_feedback(page, "Por favor, informe seu nome.", "alerta")
                txt_nome.focus()
                return

            if senha != conf_senha:
                mostrar_feedback(page, "As senhas não coincidem.", "erro")
                txt_confirmar_senha.focus()
                return

        # Ativa feedback visual de loading
        spinner_loading.visible = True
        btn_principal.disabled = True
        lbl_btn_principal.value = "Verificando..." if modo_login[0] else "Cadastrando..."
        btn_principal.opacity = 0.8
        page.update()

        try:
            if modo_login[0]:
                resposta = fazer_login(email=email, password=senha)
                if resposta and hasattr(resposta, "user") and resposta.user:
                    mostrar_feedback(page, "Login efetuado com sucesso!", "sucesso")
                    # Roteia para o Dashboard (que expandirá a janela para tela cheia)
                    page.go("/dashboard")
                else:
                    mostrar_feedback(page, "Credenciais inválidas.", "erro")
            else:
                nome = txt_nome.value.strip()
                cadastrar_usuario(email=email, password=senha, nome=nome)
                mostrar_feedback(
                    page,
                    "Conta criada com sucesso! Faça login para entrar.",
                    "sucesso",
                )
                modo_login[0] = True
                txt_senha.value = ""
                txt_confirmar_senha.value = ""
                atualizar_modo_interface()

        except Exception as ex:
            msg_traduzida = traduzir_erro_auth(str(ex))
            mostrar_feedback(page, msg_traduzida, "erro")

        finally:
            spinner_loading.visible = False
            btn_principal.disabled = False
            btn_principal.opacity = 1.0
            lbl_btn_principal.value = "Acessar Conta" if modo_login[0] else "Criar Minha Conta"
            page.update()

    btn_principal.on_click = executar_autenticacao
    txt_senha.on_submit = executar_autenticacao
    txt_confirmar_senha.on_submit = executar_autenticacao

    # --- Card de Autenticação Compacto e Otimizado ---
    card_auth = ft.Container(
        content=ft.Column(
            controls=[
                # Topo: Ícone + Título
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Container(
                                content=ft.Icon(
                                    ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                                    size=24,
                                    color=COLOR_PRIMARY,
                                ),
                                bgcolor="#064E3B",
                                border_radius=12,
                                padding=8,
                            ),
                            ft.Text(
                                "DemBase",
                                size=24,
                                weight=ft.FontWeight.BOLD,
                                color=COLOR_TEXT_PRIMARY,
                            ),
                            lbl_subtitulo,
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(bottom=10),
                ),

                # Seletor de Abas (Entrar / Cadastrar)
                ft.Container(
                    content=ft.Row(
                        controls=[btn_tab_login, btn_tab_cadastro],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=4,
                    ),
                    bgcolor=COLOR_SURFACE_ALT,
                    border_radius=10,
                    padding=3,
                    margin=ft.margin.only(bottom=12),
                ),

                # Campos
                txt_nome,
                txt_email,
                txt_senha,
                txt_confirmar_senha,

                # Espaçamento e Botão Principal
                ft.Container(height=4),
                btn_principal,

                # Alternância Inferior
                ft.Container(
                    content=lbl_alternar,
                    on_click=alternar_modo_toggle,
                    alignment=ft.alignment.center,
                    margin=ft.margin.only(top=8),
                ),
            ],
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.ADAPTIVE,  # Garante fluidez caso expanda os campos
        ),
        width=350,
        bgcolor=COLOR_SURFACE,
        border=ft.border.all(1, COLOR_BORDER),
        border_radius=16,
        padding=ft.padding.symmetric(horizontal=24, vertical=20),
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=25,
            color=ft.Colors.with_opacity(0.35, "#000000"),
        ),
    )

    return ft.View(
        route="/login",
        controls=[
            ft.Container(
                content=card_auth,
                alignment=ft.alignment.center,
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_center,
                    end=ft.alignment.bottom_center,
                    colors=["#0B0F19", "#111827"],
                ),
            )
        ],
        padding=0,
        bgcolor=COLOR_BG,
    )


# =============================================================================
# 4. VIEW DO DASHBOARD (Totalmente Estruturada com ResponsiveRow)
# =============================================================================
def criar_view_dashboard(page: ft.Page) -> ft.View:
    """
    Tela inicial do Dashboard após autenticação.
    Utiliza ResponsiveRow em toda a sua estrutura interna para adaptação perfeita
    ao modo desktop maximizado, mantendo fluidez caso a janela seja redimensionada.
    """
    nome_usuario = "Usuário"
    email_usuario = "usuario@dembase.com"

    # Dados de Totais Financeiros (Consumidos via RPC no PostgreSQL)
    totais = {"receitas": 0.0, "despesas": 0.0, "saldo": 0.0}

    try:
        sessao = obter_sessao_atual()
        if sessao and hasattr(sessao, "user") and sessao.user:
            email_usuario = sessao.user.email or email_usuario
            perfil_res = ler_perfil_logado()
            if perfil_res and perfil_res.data:
                nome_usuario = perfil_res.data.get("nome", nome_usuario)
            elif hasattr(sessao.user, "user_metadata") and sessao.user.user_metadata:
                nome_usuario = sessao.user.user_metadata.get("full_name", nome_usuario)

        # Consulta os totais agregados através da função do backend
        res_totais = obter_totais_dashboard()
        if res_totais and isinstance(res_totais, dict):
            totais["receitas"] = float(res_totais.get("receitas", 0.0) or 0.0)
            totais["despesas"] = float(res_totais.get("despesas", 0.0) or 0.0)
            totais["saldo"] = float(res_totais.get("saldo", 0.0) or 0.0)
    except Exception:
        pass

    def acao_logout(e):
        try:
            fazer_logout()
            mostrar_feedback(page, "Sessão encerrada com sucesso.", "info")
            page.go("/login")
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao deslogar: {ex}", "erro")

    # --- Header da Aplicação ---
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(
                                ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                                color=COLOR_PRIMARY,
                                size=24,
                            ),
                            bgcolor="#064E3B",
                            border_radius=10,
                            padding=8,
                        ),
                        ft.Text(
                            "DemBase",
                            size=22,
                            weight=ft.FontWeight.BOLD,
                            color=COLOR_TEXT_PRIMARY,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.PERSON_ROUNDED, size=16, color=COLOR_PRIMARY_LIGHT),
                                    ft.Text(nome_usuario, size=13, weight=ft.FontWeight.W_500, color=COLOR_TEXT_PRIMARY),
                                ],
                                spacing=6,
                            ),
                            bgcolor=COLOR_SURFACE_ALT,
                            border=ft.border.all(1, COLOR_BORDER),
                            border_radius=20,
                            padding=ft.padding.symmetric(horizontal=12, vertical=6),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.LOGOUT_ROUNDED,
                            icon_color=COLOR_TEXT_MUTED,
                            tooltip="Sair da Conta",
                            on_click=acao_logout,
                        ),
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=COLOR_SURFACE,
        border=ft.border.only(bottom=ft.BorderSide(1, COLOR_BORDER)),
        padding=ft.padding.symmetric(horizontal=24, vertical=14),
    )

    # =========================================================================
    # COMPONENTES RESPONSIVOS COM RESPONSIVEROW
    # =========================================================================

    # 1. Row de Boas-Vindas e Frase Motivacional
    row_boas_vindas = ft.ResponsiveRow(
        controls=[
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row(
                            controls=[
                                ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=COLOR_PRIMARY_LIGHT, size=22),
                                ft.Text(
                                    f"Olá, {nome_usuario}!",
                                    size=22,
                                    weight=ft.FontWeight.BOLD,
                                    color=COLOR_TEXT_PRIMARY,
                                ),
                            ],
                            spacing=8,
                        ),
                        ft.Text(
                            "\"O segredo da riqueza não está em ganhar muito, mas em gastar com sabedoria.\"",
                            size=13,
                            italic=True,
                            color=COLOR_TEXT_MUTED,
                        ),
                    ],
                    spacing=4,
                ),
                col={"xs": 12, "md": 8},
            ),
            ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CLOUD_DONE_ROUNDED, color=COLOR_PRIMARY_LIGHT, size=16),
                                    ft.Text("Nuvem Supabase Conectada", size=12, color=COLOR_PRIMARY_LIGHT, weight=ft.FontWeight.W_500),
                                ],
                                spacing=6,
                            ),
                            bgcolor="#064E3B",
                            border_radius=8,
                            padding=ft.padding.symmetric(horizontal=12, vertical=8),
                        )
                    ],
                    alignment=ft.MainAxisAlignment.END,
                ),
                col={"xs": 12, "md": 4},
                alignment=ft.alignment.center_right,
            ),
        ],
        columns=12,
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    # 2. Cards de Indicadores (KPIs) - Totalmente Adaptativos
    def criar_kpi_card(titulo: str, valor: float, icone: str, cor_destaque: str, subtitulo: str) -> ft.Container:
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(titulo, size=13, weight=ft.FontWeight.W_500, color=COLOR_TEXT_MUTED),
                            ft.Container(
                                content=ft.Icon(icone, color=cor_destaque, size=18),
                                bgcolor=ft.Colors.with_opacity(0.12, cor_destaque),
                                border_radius=8,
                                padding=6,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Text(
                        f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        size=24,
                        weight=ft.FontWeight.BOLD,
                        color=COLOR_TEXT_PRIMARY,
                    ),
                    ft.Row(
                        controls=[
                            ft.Text(subtitulo, size=11, color=COLOR_TEXT_MUTED),
                        ],
                        spacing=4,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=COLOR_SURFACE,
            border=ft.border.all(1, COLOR_BORDER),
            border_radius=14,
            padding=20,
            col={"xs": 12, "sm": 6, "md": 4},  # No desktop ocupa 1/3; no mobile ocupa 12
        )

    card_receitas = criar_kpi_card(
        "Total de Receitas",
        totais["receitas"],
        ft.Icons.ARROW_UPWARD_ROUNDED,
        COLOR_RECEITA,
        "Entradas no período selecionado",
    )

    card_despesas = criar_kpi_card(
        "Total de Despesas",
        totais["despesas"],
        ft.Icons.ARROW_DOWNWARD_ROUNDED,
        COLOR_DESPESA,
        "Saídas e dívidas computadas",
    )

    card_saldo = criar_kpi_card(
        "Saldo em Conta",
        totais["saldo"],
        ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
        COLOR_SALDO,
        "Disponibilidade líquida consolidada",
    )

    row_kpis = ft.ResponsiveRow(
        controls=[card_receitas, card_despesas, card_saldo],
        columns=12,
        spacing=16,
        run_spacing=16,
    )

    # 3. Seção do Diferencial DemBase: Sistema de Filtros Flexíveis de Data & Ações
    container_filtros = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=COLOR_PRIMARY_LIGHT, size=18),
                        ft.Text("Filtros Flexíveis de Período", size=15, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                        ft.Container(
                            content=ft.Text("Diferencial DemBase", size=10, color=COLOR_PRIMARY_LIGHT, weight=ft.FontWeight.BOLD),
                            bgcolor="#064E3B",
                            border_radius=6,
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                        ),
                    ],
                    spacing=8,
                ),
                ft.Text(
                    "Filtre períodos personalizados sem ficar preso a meses fechados (ex: do dia 01 ao dia 23):",
                    size=12,
                    color=COLOR_TEXT_MUTED,
                ),
                ft.Row(
                    controls=[
                        ft.ElevatedButton(
                            text="Mês Atual",
                            style=ft.ButtonStyle(
                                bgcolor=COLOR_SURFACE_ALT,
                                color=COLOR_TEXT_PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                        ),
                        ft.ElevatedButton(
                            text="Do dia 01 ao dia 23",
                            style=ft.ButtonStyle(
                                bgcolor=COLOR_PRIMARY,
                                color=COLOR_TEXT_PRIMARY,
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                        ),
                        ft.ElevatedButton(
                            text="Personalizar Datas...",
                            style=ft.ButtonStyle(
                                bgcolor=COLOR_SURFACE_ALT,
                                color=COLOR_TEXT_MUTED,
                                shape=ft.RoundedRectangleBorder(radius=8),
                            ),
                        ),
                    ],
                    spacing=10,
                    wrap=True,
                ),
            ],
            spacing=10,
        ),
        bgcolor=COLOR_SURFACE,
        border=ft.border.all(1, COLOR_BORDER),
        border_radius=14,
        padding=20,
        col={"xs": 12, "lg": 8},
    )

    container_acoes_rapidas = ft.Container(
        content=ft.Column(
            controls=[
                ft.Text("Ações Rápidas", size=15, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                ft.ElevatedButton(
                    text="+ Novo Lançamento",
                    icon=ft.Icons.ADD_ROUNDED,
                    style=ft.ButtonStyle(
                        bgcolor=COLOR_PRIMARY,
                        color=COLOR_TEXT_PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                    height=42,
                    width=300,
                    on_click=lambda e: page.go("/lancamentos"),
                ),
                ft.Row(
                    controls=[
                        ft.OutlinedButton(
                            text="Contas",
                            icon=ft.Icons.CREDIT_CARD_ROUNDED,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                color=COLOR_TEXT_PRIMARY,
                            ),
                            on_click=lambda e: mostrar_feedback(page, "Gerenciador de Contas (Etapa 4)", "info"),
                        ),
                        ft.OutlinedButton(
                            text="Categorias",
                            icon=ft.Icons.CATEGORY_ROUNDED,
                            style=ft.ButtonStyle(
                                shape=ft.RoundedRectangleBorder(radius=8),
                                color=COLOR_TEXT_PRIMARY,
                            ),
                            on_click=lambda e: mostrar_feedback(page, "Gerenciador de Categorias (Etapa 4)", "info"),
                        ),
                    ],
                    spacing=8,
                ),
            ],
            spacing=12,
        ),
        bgcolor=COLOR_SURFACE,
        border=ft.border.all(1, COLOR_BORDER),
        border_radius=14,
        padding=20,
        col={"xs": 12, "lg": 4},
    )

    row_filtros_e_acoes = ft.ResponsiveRow(
        controls=[container_filtros, container_acoes_rapidas],
        columns=12,
        spacing=16,
        run_spacing=16,
    )

    # 4. Painel de Gráficos e Lançamentos Recentes com ResponsiveRow
    container_grafico_preview = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Fluxo de Caixa no Período", size=15, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                        ft.Icon(ft.Icons.BAR_CHART_ROUNDED, color=COLOR_PRIMARY_LIGHT, size=20),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Icon(ft.Icons.INSIGHTS_ROUNDED, size=48, color=COLOR_PRIMARY_LIGHT),
                            ft.Text("Visualização Gráfica Dinâmica", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                            ft.Text(
                                "Os gráficos dinâmicos de receitas e despesas serão renderizados aqui na Etapa 4 com base nos lançamentos reais.",
                                size=12,
                                color=COLOR_TEXT_MUTED,
                                text_align=ft.TextAlign.CENTER,
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=8,
                    ),
                    height=200,
                    alignment=ft.alignment.center,
                    bgcolor=COLOR_SURFACE_ALT,
                    border_radius=12,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.4, COLOR_BORDER)),
                ),
            ],
            spacing=14,
        ),
        bgcolor=COLOR_SURFACE,
        border=ft.border.all(1, COLOR_BORDER),
        border_radius=14,
        padding=20,
        col={"xs": 12, "lg": 8},
    )

    container_atividades_recentes = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Contas & Destinos", size=15, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                        ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, color=COLOR_PRIMARY_LIGHT, size=20),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, color=COLOR_PRIMARY, size=18),
                                    ft.Text("Contas Suportadas:", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                                ],
                                spacing=6,
                            ),
                            ft.Text("Santander • Itaú • Inter • Dinheiro", size=12, color=COLOR_TEXT_MUTED),
                            ft.Divider(color=COLOR_BORDER, height=1),
                            ft.Row(
                                controls=[
                                    ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color="#F59E0B", size=18),
                                    ft.Text("Automação de Crédito:", size=12, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                                ],
                                spacing=6,
                            ),
                            ft.Text("Compras no crédito têm status automático (Pendente para datas futuras, Pago para hoje).", size=11, color=COLOR_TEXT_MUTED),
                        ],
                        spacing=8,
                    ),
                    bgcolor=COLOR_SURFACE_ALT,
                    border_radius=12,
                    padding=14,
                ),
            ],
            spacing=14,
        ),
        bgcolor=COLOR_SURFACE,
        border=ft.border.all(1, COLOR_BORDER),
        border_radius=14,
        padding=20,
        col={"xs": 12, "lg": 4},
    )

    row_graficos_e_atividades = ft.ResponsiveRow(
        controls=[container_grafico_preview, container_atividades_recentes],
        columns=12,
        spacing=16,
        run_spacing=16,
    )

    # Conteúdo Principal com Scroll Adaptativo
    conteudo_scrollavel = ft.Container(
        content=ft.Column(
            controls=[
                row_boas_vindas,
                ft.Container(height=4),
                row_kpis,
                ft.Container(height=4),
                row_filtros_e_acoes,
                ft.Container(height=4),
                row_graficos_e_atividades,
                ft.Container(height=16),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=ft.padding.symmetric(horizontal=28, vertical=20),
        expand=True,
    )

    return ft.View(
        route="/dashboard",
        controls=[
            ft.Column(
                controls=[
                    header,
                    conteudo_scrollavel,
                ],
                spacing=0,
                expand=True,
            )
        ],
        padding=0,
        bgcolor=COLOR_BG,
    )


# =============================================================================
# 5. GERENCIADOR DE ROTEAMENTO DINÂMICO E TRANSIÇÃO DE JANELA
# =============================================================================
def aplicar_tamanho_janela(page: ft.Page, rota: str):
    """
    Ajusta dinamicamente a janela conforme a rota:
    - Login: Janela compacta (width=400, height=600) e centralizada.
    - Dashboard: Janela maximizada em tela cheia (page.window.maximized = True).
    A barra de título nativa e botões do sistema operacional permanecem 100% intactos.
    """
    if not hasattr(page, "window"):
        return

    if rota == "/dashboard":
        # Expansão para modo desktop maximizado
        page.window.min_width = 800
        page.window.min_height = 600
        page.window.maximized = True
    else:
        # Modo compacto fixo e centralizado para a tela de autenticação
        page.window.maximized = False
        page.window.width = 400
        page.window.height = 600
        page.window.min_width = 380
        page.window.min_height = 580
        page.window.center()


def main(page: ft.Page):
    # Configurações Globais da Página
    page.title = "DemBase - Gestão Financeira Pessoal"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    # Tema personalizado com fontes e cores minimalistas
    page.theme = ft.Theme(
        font_family="Segoe UI",
        color_scheme=ft.ColorScheme(
            primary=COLOR_PRIMARY,
            on_primary=COLOR_TEXT_PRIMARY,
            surface=COLOR_SURFACE,
            on_surface=COLOR_TEXT_PRIMARY,
            background=COLOR_BG,
            error=COLOR_ERROR,
        ),
    )

    # Mantém a janela nativa com botões do SO intactos (sem frameless nem title_bar_hidden)
    if hasattr(page, "window"):
        page.window.resizable = True
        page.window.minimizable = True
        page.window.maximizable = True

    def route_change(e):
        """Gerencia as transições de tela e adapta o tamanho da janela dinamicamente."""
        page.views.clear()

        rota = page.route if page.route else "/login"

        if rota == "/dashboard":
            sessao = obter_sessao_atual()
            if not sessao or not hasattr(sessao, "user") or not sessao.user:
                mostrar_feedback(page, "Sessão não autenticada. Faça login para continuar.", "alerta")
                page.route = "/login"
                aplicar_tamanho_janela(page, "/login")
                page.views.append(criar_view_auth(page))
            else:
                aplicar_tamanho_janela(page, "/dashboard")
                page.views.append(criar_view_dashboard(page))
        elif rota == "/lancamentos":
            sessao = obter_sessao_atual()
            if not sessao or not hasattr(sessao, "user") or not sessao.user:
                mostrar_feedback(page, "Sessão não autenticada.", "alerta")
                page.route = "/login"
                aplicar_tamanho_janela(page, "/login")
                page.views.append(criar_view_auth(page))
            else:
                aplicar_tamanho_janela(page, "/dashboard") # Mantém maximizado
                page.views.append(criar_view_lancamentos(page))
        else:
            aplicar_tamanho_janela(page, "/login")
            page.views.append(criar_view_auth(page))

        page.update()

    def view_pop(e):
        """Gerencia a navegação de retorno."""
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Validação da sessão de inicialização
    sessao_ativa = obter_sessao_atual()
    if sessao_ativa and hasattr(sessao_ativa, "user") and sessao_ativa.user:
        page.go("/dashboard")
    else:
        page.go("/login")


# =============================================================================
# INICIALIZAÇÃO DA APLICAÇÃO
# =============================================================================
if __name__ == "__main__":
    ft.app(target=main)
