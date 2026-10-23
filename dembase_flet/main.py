"""
=============================================================================
DemBase v3 — main.py  (Flet 1.0.1 — async)
Ponto de entrada principal com suporte a Tema Dinâmico do Sistema (Dark/Light),
detecção de ciclo de vida (Mobile Background/Resume) e reconexão transparente
com persistência de sessão e restauração da última tela ativa.
=============================================================================
"""
import flet as ft
from core import theme as T
from core.router import configurar_rotas, navegar, ROTA_AUTH, ROTA_DASHBOARD
from core.window_manager import ajustar_janela_login, ajustar_janela_principal
from core import storage
import services.supabase_client as db


async def main(page: ft.Page):
    page.title   = "DemBase Finanças"
    page.padding = 0

    # 1. Configuração do Tema Dinâmico (Automático e Manual)
    pref_tema = await storage.carregar_preferencia_tema(page)

    def on_brightness_change(e=None):
        pref = storage.obter_preferencia_tema_memoria(page)
        if pref == "system":
            T.aplicar_tema_app(page, "system")

    page.on_platform_brightness_change = on_brightness_change
    T.aplicar_tema_app(page, pref_tema)

    # 2. Inicializa SharedPreferences e roteador
    storage._obter_sp(page)
    configurar_rotas(page)

    # 3. Tenta reconexão transparente com tokens persistidos (Mobile Background / PWA / Desktop)
    autenticado = False
    try:
        acc, ref, _ = await storage.carregar_sessao_autenticada(page)
        if acc and ref:
            autenticado = db.restaurar_sessao(acc, ref)
    except Exception:
        autenticado = False

    # 4. Restaura a tela em que o usuário estava ou direciona para Login
    if autenticado:
        await ajustar_janela_principal(page)
        # Pré-aquece potes, categorias, contas e cartões em background
        db.aquecer_cache()
        ultima_rota = await storage.carregar_ultima_rota(page)
        destino = ultima_rota if (ultima_rota and not ultima_rota.startswith("/auth")) else ROTA_DASHBOARD
        page.route = destino
        if hasattr(page, "_reconstruir_rota") and callable(page._reconstruir_rota):
            page._reconstruir_rota(forcar_rebuild=True)
        else:
            navegar(page, destino)
    else:
        await ajustar_janela_login(page)
        page.route = ROTA_AUTH
        if hasattr(page, "_reconstruir_rota") and callable(page._reconstruir_rota):
            page._reconstruir_rota(forcar_rebuild=True)
        else:
            navegar(page, ROTA_AUTH)

    # 5. Gerenciamento de Ciclo de Vida (Lifecycle: background -> foreground no mobile)
    async def on_app_lifecycle(e: ft.AppLifecycleStateChangeEvent):
        estado = str(getattr(e, "state", "") or "").lower()
        if estado in ("resume", "show"):
            sess = db.sessao_atual()
            if not sess or not getattr(sess, "user", None):
                try:
                    a, r, _ = await storage.carregar_sessao_autenticada(page)
                    if a and r:
                        db.restaurar_sessao(a, r)
                except Exception:
                    pass
            # Revalida view ativa se possuir hook de refresh
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
