"""
=============================================================================
DemBase v3 — views/auth_view.py  (Flet 1.0 compatible)
Tela de Login / Cadastro.
=============================================================================
"""
import flet as ft
from core import theme as T
from core.theme import mostrar_feedback, traduzir_erro_auth, pad, borda, centro
from core.router import ROTA_DASHBOARD, navegar
import services.supabase_client as db


def criar_view_auth(page: ft.Page) -> ft.View:
    modo_login = [True]

    # ---- Campos ----
    def _campo(label, hint, icone, password=False, visible=True, keyboard=ft.KeyboardType.TEXT):
        return ft.TextField(
            label=label, hint_text=hint,
            prefix_icon=icone,
            password=password,
            can_reveal_password=password,
            visible=visible,
            keyboard_type=keyboard,
            **T.campo_estilo(),
        )

    txt_nome     = _campo("Nome Completo", "Seu nome", ft.Icons.PERSON_OUTLINE_ROUNDED, visible=False)
    txt_email    = _campo("E-mail", "exemplo@email.com", ft.Icons.ALTERNATE_EMAIL_ROUNDED, keyboard=ft.KeyboardType.EMAIL)
    txt_senha    = _campo("Senha", "Mínimo 6 caracteres", ft.Icons.LOCK_OUTLINE_ROUNDED, password=True)
    txt_confirma = _campo("Confirmar Senha", "Repita a senha", ft.Icons.LOCK_RESET_ROUNDED, password=True, visible=False)

    # ---- Botão ----
    spinner  = ft.ProgressRing(color=ft.Colors.WHITE, width=18, height=18, stroke_width=2, visible=False)
    txt_btn  = ft.Text("Entrar", color=ft.Colors.WHITE, size=14, weight=ft.FontWeight.W_600)
    btn_acao = ft.FilledButton(
        content=ft.Row([spinner, txt_btn], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True),
        expand=True,
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY, overlay_color=T.PRIMARY_DARK,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=24, v=16),
        ),
    )

    txt_alternar = ft.Text(
        "Não possui conta? Cadastre-se",
        color=T.TEXT_MUTED, size=13, text_align=ft.TextAlign.CENTER,
    )

    # ---- Títulos ----
    txt_titulo    = ft.Text("Bem-vindo de volta", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD)
    txt_subtitulo = ft.Text("Acesse sua conta DemBase", color=T.TEXT_MUTED, size=13)

    # ---- Chips de modo ----
    chip_entrar    = ft.Container(content=ft.Text("Entrar",    size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                                  padding=pad(h=20, v=8), bgcolor=T.PRIMARY, border_radius=8)
    chip_cadastrar = ft.Container(content=ft.Text("Cadastrar", size=13, weight=ft.FontWeight.W_500, color=T.TEXT_MUTED),
                                  padding=pad(h=20, v=8), bgcolor=ft.Colors.TRANSPARENT, border_radius=8)

    def alternar(login: bool):
        modo_login[0] = login
        chip_entrar.bgcolor    = T.PRIMARY if login else ft.Colors.TRANSPARENT
        chip_cadastrar.bgcolor = T.PRIMARY if not login else ft.Colors.TRANSPARENT
        chip_entrar.content.color    = T.TEXT_PRIMARY if login else T.TEXT_MUTED
        chip_cadastrar.content.color = T.TEXT_PRIMARY if not login else T.TEXT_MUTED
        chip_entrar.content.weight    = ft.FontWeight.W_600 if login else ft.FontWeight.W_500
        chip_cadastrar.content.weight = ft.FontWeight.W_600 if not login else ft.FontWeight.W_500

        txt_nome.visible     = not login
        txt_confirma.visible = not login
        txt_titulo.value     = "Bem-vindo de volta" if login else "Criar Conta"
        txt_subtitulo.value  = "Acesse sua conta DemBase" if login else "Preencha seus dados"
        txt_btn.value        = "Entrar" if login else "Cadastrar"
        txt_alternar.value   = "Não possui conta? Cadastre-se" if login else "Já tem conta? Entrar"
        txt_nome.value = txt_senha.value = txt_confirma.value = ""
        txt_email.error_text = txt_senha.error_text = None
        page.update()

    chip_entrar.on_click    = lambda _: alternar(True)
    chip_cadastrar.on_click = lambda _: alternar(False)
    txt_alternar.on_click   = lambda _: alternar(not modo_login[0])

    # ---- Validação e Submit ----
    def set_loading(ativo: bool):
        spinner.visible = ativo
        btn_acao.disabled = ativo
        page.update()

    def validar() -> bool:
        ok = True
        if not txt_email.value or "@" not in txt_email.value:
            txt_email.error_text = "E-mail inválido."; ok = False
        else:
            txt_email.error_text = None
        if not txt_senha.value or len(txt_senha.value) < 6:
            txt_senha.error_text = "Mínimo 6 caracteres."; ok = False
        else:
            txt_senha.error_text = None
        if not modo_login[0]:
            if not txt_nome.value.strip():
                txt_nome.error_text = "Informe seu nome."; ok = False
            else:
                txt_nome.error_text = None
            if txt_confirma.value != txt_senha.value:
                txt_confirma.error_text = "Senhas não coincidem."; ok = False
            else:
                txt_confirma.error_text = None
        page.update()
        return ok

    def on_submit(_):
        if not validar(): return
        set_loading(True)
        try:
            if modo_login[0]:
                db.fazer_login(txt_email.value.strip(), txt_senha.value)
                page.window.width = 1280
                page.window.height = 800
                page.update()
                page.run_task(page.window.center)
                navegar(page, ROTA_DASHBOARD)
            else:
                db.cadastrar_usuario(txt_email.value.strip(), txt_senha.value, txt_nome.value.strip())
                mostrar_feedback(page, "Conta criada! Verifique o e-mail e faça login.", "sucesso")
                alternar(True)
                set_loading(False)
        except Exception as ex:
            mostrar_feedback(page, traduzir_erro_auth(str(ex)), "erro")
            set_loading(False)

    btn_acao.on_click   = on_submit
    txt_senha.on_submit = on_submit
    txt_confirma.on_submit = on_submit

    # ---- Card central ----
    card = ft.Container(
        width=420,
        padding=pad(all_=36),
        bgcolor=T.SURFACE,
        border_radius=20,
        border=borda(),
        shadow=ft.BoxShadow(blur_radius=40, color="#00000066", offset=ft.Offset(0, 8)),
        content=ft.Column(
            spacing=10,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
            controls=[
                # Logo
                ft.Row(spacing=14, controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=T.PRIMARY, size=30),
                        bgcolor=f"{T.PRIMARY}22", border_radius=12, padding=pad(all_=12),
                    ),
                    ft.Column(spacing=2, controls=[
                        ft.Text("DemBase", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Controle Financeiro Premium", color=T.TEXT_MUTED, size=11),
                    ]),
                ]),
                ft.Container(height=16),
                # Chips
                ft.Container(
                    content=ft.Row([chip_entrar, chip_cadastrar], spacing=0),
                    bgcolor=T.SURFACE_ALT, border_radius=10,
                    padding=pad(all_=4), border=borda(),
                ),
                ft.Container(height=12),
                txt_titulo,
                txt_subtitulo,
                ft.Container(height=12),
                txt_nome,
                txt_email,
                txt_senha,
                txt_confirma,
                ft.Container(height=8),
                btn_acao,
                ft.Container(height=4),
                ft.Container(
                    content=txt_alternar,
                    alignment=centro(),
                    on_click=lambda _: alternar(not modo_login[0]),
                ),
            ],
        ),
    )

    return ft.View(
        route="/auth",
        bgcolor=T.BG,
        padding=0,
        controls=[
            ft.Container(
                expand=True,
                alignment=centro(),
                bgcolor=T.BG,
                content=card,
            )
        ],
    )
