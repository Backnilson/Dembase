"""
=============================================================================
DemBase v3 — main.py  (Flet 1.0.1 — async)
Ponto de entrada principal com barreira mandatória de autenticação:
toda inicialização abre obrigatoriamente na tela de Login (/auth).
=============================================================================
"""
import flet as ft
from core import theme as T
from core.router import configurar_rotas, navegar, ROTA_AUTH
from core.window_manager import ajustar_janela_login
from core import storage
import services.supabase_client as db


async def main(page: ft.Page):
    page.title   = "DemBase Finanças"
    page.padding = 0

    # 1. Configuração do Tema - Modo Escuro Padrão Absoluto DemBase
    page.theme_mode = ft.ThemeMode.DARK
    T.aplicar_paleta(True)
    page.bgcolor = T.BG

    pref_tema = await storage.carregar_preferencia_tema(page)
    T.aplicar_tema_app(page, pref_tema)

    # 2. Inicializa SharedPreferences
    storage._obter_sp(page)

    # 3. Barreira de Segurança Inicial:
    # Garante que qualquer sessão residual de execuções anteriores seja desfeita
    try:
        db.fazer_logout()
    except Exception:
        pass

    # 4. Configuração das rotas (com guarda estrito de autenticação)
    configurar_rotas(page)

    # 5. Inicialização Obrigatória na Tela de Login (/auth)
    # Bloqueia qualquer acesso direto ao Dashboard até confirmação de credenciais
    await ajustar_janela_login(page)
    page.route = ROTA_AUTH
    if hasattr(page, "_reconstruir_rota") and callable(page._reconstruir_rota):
        page._reconstruir_rota(forcar_rebuild=True)
    else:
        navegar(page, ROTA_AUTH)

    # 6. Gerenciamento de Ciclo de Vida (Mobile Background / Foreground)
    async def on_app_lifecycle(e: ft.AppLifecycleStateChangeEvent):
        estado = str(getattr(e, "state", "") or "").lower()
        if estado in ("resume", "show"):
            sess = db.sessao_atual()
            if sess and getattr(sess, "user", None):
                # Revalida view ativa apenas se o usuário já estiver autenticado em memória
                if page.views:
                    refresh_fn = getattr(page.views[-1], "_dembase_refresh", None)
                    if callable(refresh_fn):
                        try:
                            refresh_fn()
                        except Exception:
                            pass

    page.on_app_lifecycle_state_change = on_app_lifecycle


if __name__ == "__main__":
    import os

    _porta_servidor = os.environ.get("PORT")
    if _porta_servidor:
        os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")
        _assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        ft.run(
            main,
            host="0.0.0.0",
            port=int(_porta_servidor),
            view=ft.AppView.WEB_BROWSER,
            assets_dir=_assets,
        )
    else:
        ft.run(main, assets_dir="assets")
