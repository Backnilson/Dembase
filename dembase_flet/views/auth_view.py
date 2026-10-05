"""
=============================================================================
DemBase v3 — views/auth_view.py  (Flet 1.0.1 compatible)
Tela de Login / Cadastro totalmente reescrita do zero.
Design minimalista, moderno, com acento Verde Neon e 100% responsivo
(Desktop maximizado em tela dividida / Mobile em coluna única fluida).
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import pad, borda, centro, mostrar_feedback, traduzir_erro_auth
from core.router import ROTA_DASHBOARD, navegar
from core.window_manager import ajustar_janela_principal
from core.constants import session_clear
from core import storage
import services.supabase_client as db

from views.widgets.auth.logo import criar_logo
from views.widgets.auth.auth_toggle import criar_auth_toggle
from views.widgets.auth.brand_panel import criar_painel_marca
from views.widgets.auth.social_buttons import criar_botoes_sociais


def criar_view_auth(page: ft.Page) -> ft.View:
    modo_login = [True]
    loading = [False]

    # ---- Campos do Formulário ----
    def _campo(label: str, hint: str, icone, password: bool = False, keyboard=ft.KeyboardType.TEXT, valor: str = ""):
        return ft.TextField(
            label=label,
            hint_text=hint,
            prefix_icon=icone,
            value=valor,
            password=password,
            can_reveal_password=password,
            keyboard_type=keyboard,
            **T.campo_estilo(),
        )

    txt_email_login = _campo(
        "E-mail", "seu@email.com", ft.Icons.ALTERNATE_EMAIL_ROUNDED,
        keyboard=ft.KeyboardType.EMAIL
    )
    txt_senha_login = _campo(
        "Senha", "Sua senha de acesso", ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True
    )

    txt_nome_cad = _campo(
        "Nome Completo", "Como quer ser chamado", ft.Icons.PERSON_OUTLINE_ROUNDED
    )
    txt_email_cad = _campo(
        "E-mail", "seu@email.com", ft.Icons.ALTERNATE_EMAIL_ROUNDED,
        keyboard=ft.KeyboardType.EMAIL
    )
    txt_senha_cad = _campo(
        "Senha", "Mínimo 6 caracteres", ft.Icons.LOCK_OUTLINE_ROUNDED,
        password=True
    )
    txt_confirma_cad = _campo(
        "Confirmar Senha", "Repita a senha", ft.Icons.LOCK_RESET_ROUNDED,
        password=True
    )

    # Checkbox estilizado "Lembrar de mim"
    chk_lembrar = ft.Checkbox(
        label="Lembrar de mim",
        value=True,
        check_color=T.ON_NEON,
        active_color=T.NEON,
        label_style=ft.TextStyle(
            color=T.TEXT_MUTED,
            size=13,
            weight=ft.FontWeight.W_500,
        ),
    )

    # Carrega credenciais salvas de forma assíncrona
    async def carregar_dados_iniciais():
        try:
            email_salvo, _, _, ativo = await storage.carregar_lembrar(page)
            if email_salvo:
                txt_email_login.value = email_salvo
                chk_lembrar.value = ativo
                page.update()
        except Exception:
            pass

    page.run_task(carregar_dados_iniciais)

    # ---- Diálogo Esqueceu a Senha ----
    def abrir_esqueci_senha(_):
        txt_email_recup = ft.TextField(
            label="E-mail cadastrado",
            hint_text="seu@email.com",
            prefix_icon=ft.Icons.ALTERNATE_EMAIL_ROUNDED,
            value=txt_email_login.value or "",
            **T.campo_estilo(),
        )

        def enviar_recuperacao(_):
            email = (txt_email_recup.value or "").strip()
            if not email or "@" not in email:
                txt_email_recup.error_text = "Informe um e-mail válido."
                dlg.update()
                return
            try:
                db.recuperar_senha(email)
                dlg.open = False
                page.update()
                mostrar_feedback(page, "Link de recuperação enviado para seu e-mail!", "sucesso")
            except Exception as ex:
                txt_email_recup.error_text = str(ex)
                dlg.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Recuperar Senha", weight=ft.FontWeight.W_700, color=T.TEXT_PRIMARY),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Text(
                        "Digite seu e-mail para receber as instruções de redefinição de senha.",
                        size=13, color=T.TEXT_MUTED
                    ),
                    txt_email_recup,
                ],
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: setattr(dlg, "open", False) or page.update()),
                ft.FilledButton(
                    "Enviar Link",
                    on_click=enviar_recuperacao,
                    style=ft.ButtonStyle(
                        bgcolor=T.NEON, color=T.ON_NEON,
                        shape=ft.RoundedRectangleBorder(radius=8),
                    ),
                ),
            ],
            bgcolor=T.SURFACE,
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    link_esqueci_senha = ft.TextButton(
        content=ft.Text(
            "Esqueceu a senha?",
            size=12.5,
            color=T.PRIMARY if not T.IS_DARK else T.NEON,
            weight=ft.FontWeight.W_600,
        ),
        on_click=abrir_esqueci_senha,
        style=ft.ButtonStyle(padding=pad(h=4, v=4)),
    )

    # Linha com Lembre de mim + Esqueceu a senha
    linha_opcoes_login = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            chk_lembrar,
            link_esqueci_senha,
        ],
    )

    # ---- Botões de Ação Principal (Verde Neon) ----
    spinner_login = ft.ProgressRing(color=T.ON_NEON, width=20, height=20, stroke_width=2.5, visible=False)
    txt_btn_login = ft.Text("Entrar", color=T.ON_NEON, size=14.5, weight=ft.FontWeight.W_700)

    btn_entrar = ft.FilledButton(
        content=ft.Row([spinner_login, txt_btn_login], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True),
        expand=True,
        style=ft.ButtonStyle(
            bgcolor=T.NEON,
            overlay_color=T.NEON_HOVER,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(h=24, v=16),
        ),
    )

    spinner_cad = ft.ProgressRing(color=T.ON_NEON, width=20, height=20, stroke_width=2.5, visible=False)
    txt_btn_cad = ft.Text("Cadastrar", color=T.ON_NEON, size=14.5, weight=ft.FontWeight.W_700)

    btn_cadastrar = ft.FilledButton(
        content=ft.Row([spinner_cad, txt_btn_cad], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True),
        expand=True,
        style=ft.ButtonStyle(
            bgcolor=T.NEON,
            overlay_color=T.NEON_HOVER,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(h=24, v=16),
        ),
    )

    # ---- Alternador de Rodapé ----
    txt_rodape_link = ft.Text(
        "Criar conta",
        color=T.PRIMARY if not T.IS_DARK else T.NEON,
        size=13.5,
        weight=ft.FontWeight.W_700,
    )
    txt_rodape_prefixo = ft.Text(
        "Não tem uma conta? ",
        color=T.TEXT_MUTED,
        size=13.5,
    )

    linha_rodape = ft.Row(
        alignment=ft.MainAxisAlignment.CENTER,
        spacing=4,
        controls=[
            txt_rodape_prefixo,
            ft.Container(
                content=txt_rodape_link,
                on_click=lambda _: alternar_modo(not modo_login[0]),
            ),
        ],
    )

    # ---- Login Social ----
    def on_social_click(provedor: str):
        try:
            url = db.login_social(provedor)
            if url:
                db.abrir_url_navegador(url)
                mostrar_feedback(page, f"Conectando com {provedor.capitalize()}... Conclua a autorização no navegador.", "info")
            else:
                mostrar_feedback(page, f"Iniciando autenticação com {provedor.capitalize()}...", "info")
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao conectar com {provedor.capitalize()}: {ex}", "erro")

    botoes_sociais = criar_botoes_sociais(on_social_click=on_social_click)

    # ---- Estrutura dos Formulários ----
    col_login = ft.Column(
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            txt_email_login,
            txt_senha_login,
            linha_opcoes_login,
            btn_entrar,
        ],
    )

    col_cadastro = ft.Column(
        spacing=16,
        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        controls=[
            txt_nome_cad,
            txt_email_cad,
            txt_senha_cad,
            txt_confirma_cad,
            btn_cadastrar,
        ],
    )

    conteudo_form = ft.AnimatedSwitcher(
        content=col_login,
        transition=ft.AnimatedSwitcherTransition.FADE,
        duration=220,
        reverse_duration=180,
    )

    # ---- Sincronização do Toggle e Transição ----
    def on_toggle_change(is_login: bool):
        modo_login[0] = is_login
        conteudo_form.content = col_login if is_login else col_cadastro
        txt_rodape_prefixo.value = "Não tem uma conta? " if is_login else "Já tem uma conta? "
        txt_rodape_link.value = "Criar conta" if is_login else "Entrar"

        # Limpa erros visuais ao alternar
        txt_email_login.error_text = txt_senha_login.error_text = None
        txt_nome_cad.error_text = txt_email_cad.error_text = txt_senha_cad.error_text = txt_confirma_cad.error_text = None
        page.update()

    toggle_widget, alternar_modo = criar_auth_toggle(on_toggle_change, login_inicial=True)

    # Suporte a Gestos de Deslize (Swipe)
    def on_drag_end(e: ft.DragEndEvent):
        vel = getattr(e, "primary_velocity", 0) or 0
        if vel < -120 and modo_login[0]:
            alternar_modo(False)
        elif vel > 120 and not modo_login[0]:
            alternar_modo(True)

    # ---- Submissão e Validações ----
    def set_loading(ativo: bool):
        loading[0] = ativo
        spinner_login.visible = ativo and modo_login[0]
        btn_entrar.disabled = ativo
        spinner_cad.visible = ativo and not modo_login[0]
        btn_cadastrar.disabled = ativo
        page.update()

    def validar_login() -> bool:
        ok = True
        em = (txt_email_login.value or "").strip()
        pw = txt_senha_login.value or ""
        if not em or "@" not in em:
            txt_email_login.error_text = "Informe um e-mail válido."
            ok = False
        else:
            txt_email_login.error_text = None

        if not pw or len(pw) < 6:
            txt_senha_login.error_text = "Mínimo 6 caracteres."
            ok = False
        else:
            txt_senha_login.error_text = None
        page.update()
        return ok

    def validar_cadastro() -> bool:
        ok = True
        nome = (txt_nome_cad.value or "").strip()
        em = (txt_email_cad.value or "").strip()
        pw = txt_senha_cad.value or ""
        conf = txt_confirma_cad.value or ""

        if not nome:
            txt_nome_cad.error_text = "Informe seu nome completo."
            ok = False
        else:
            txt_nome_cad.error_text = None

        if not em or "@" not in em:
            txt_email_cad.error_text = "Informe um e-mail válido."
            ok = False
        else:
            txt_email_cad.error_text = None

        if not pw or len(pw) < 6:
            txt_senha_cad.error_text = "Mínimo 6 caracteres."
            ok = False
        else:
            txt_senha_cad.error_text = None

        if conf != pw:
            txt_confirma_cad.error_text = "Senhas não coincidem."
            ok = False
        else:
            txt_confirma_cad.error_text = None
        page.update()
        return ok

    async def on_submit_login(_):
        if not validar_login() or loading[0]:
            return
        set_loading(True)
        try:
            email = txt_email_login.value.strip()
            senha = txt_senha_login.value
            resp = db.fazer_login(email, senha)

            sess = getattr(resp, "session", None)
            if sess:
                acc = getattr(sess, "access_token", "") or ""
                ref = getattr(sess, "refresh_token", "") or ""
                if chk_lembrar.value:
                    await storage.salvar_lembrar(page, email, acc, ref)
                else:
                    await storage.limpar_lembrar(page)
                    storage.salvar_sessao_temporaria(page, acc, ref)

            await ajustar_janela_principal(page)
            navegar(page, ROTA_DASHBOARD)
        except Exception as ex:
            mostrar_feedback(page, traduzir_erro_auth(str(ex)), "erro")
            set_loading(False)

    async def on_submit_cadastro(_):
        if not validar_cadastro() or loading[0]:
            return
        set_loading(True)
        try:
            email = txt_email_cad.value.strip()
            senha = txt_senha_cad.value
            nome = txt_nome_cad.value.strip()
            db.cadastrar_usuario(email, senha, nome)
            mostrar_feedback(page, "Conta criada com sucesso! Verifique seu e-mail.", "sucesso")
            txt_email_login.value = email
            alternar_modo(True)
            set_loading(False)
        except Exception as ex:
            mostrar_feedback(page, traduzir_erro_auth(str(ex)), "erro")
            set_loading(False)

    btn_entrar.on_click = on_submit_login
    txt_senha_login.on_submit = on_submit_login

    btn_cadastrar.on_click = on_submit_cadastro
    txt_confirma_cad.on_submit = on_submit_cadastro

    # ---- Container Card do Formulário (Lado Direito ou Central) ----
    logo_mobile = ft.Container(
        content=criar_logo(size=58, com_texto=True, centralizado=True),
        margin=pad(bottom=10),
    )

    card_conteudo = ft.Column(
        spacing=24,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            logo_mobile,
            toggle_widget,
            conteudo_form,
            botoes_sociais,
            linha_rodape,
        ],
    )

    # GestureDetector para captura de gestos de swipe
    card_com_gestos = ft.GestureDetector(
        content=card_conteudo,
        on_horizontal_drag_end=on_drag_end,
    )

    area_formulario = ft.Container(
        expand=True,
        alignment=ft.Alignment(0, 0),
        padding=pad(h=24, v=32),
        content=ft.Container(
            width=400,
            content=card_com_gestos,
            alignment=ft.Alignment(0, 0),
        ),
    )

    # ---- Layout Responsivo (Split no Desktop / Coluna no Mobile) ----
    painel_marca = criar_painel_marca()

    def montar_layout():
        largura = page.width or 1200
        is_desktop = largura >= 920

        # No desktop, logo já aparece no painel esquerdo da marca
        logo_mobile.visible = not is_desktop
        painel_marca.visible = is_desktop

        if is_desktop:
            return ft.Row(
                expand=True,
                spacing=0,
                controls=[
                    painel_marca,
                    area_formulario,
                ],
            )
        else:
            return ft.Column(
                expand=True,
                scroll=ft.ScrollMode.ADAPTIVE,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        alignment=ft.Alignment(0, 0),
                        padding=pad(v=20),
                        content=area_formulario,
                    ),
                ],
            )

    layout_root = ft.Container(
        expand=True,
        bgcolor=T.BG,
        content=montar_layout(),
    )

    # Re-avalia o breakpoint ao redimensionar
    def on_resize(e):
        layout_root.content = montar_layout()
        page.update()

    page.on_resize = on_resize

    return ft.View(
        route="/auth",
        bgcolor=T.BG,
        padding=0,
        controls=[layout_root],
    )
