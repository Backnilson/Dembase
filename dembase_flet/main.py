"""
=============================================================================
DemBase v3 — main.py  (Flet 1.0.1 — async)
Ponto de entrada principal com suporte a Tema Dinâmico do Sistema (Dark/Light),
detecção de brilho da plataforma e inicialização obrigatória na tela de início (Auth).
=============================================================================
"""
import flet as ft
from core import theme as T
from core.constants import session_remove
from core.router import configurar_rotas, navegar, ROTA_AUTH
from core.window_manager import ajustar_janela_login
from core import storage
import services.supabase_client as db


async def main(page: ft.Page):
    page.title   = "DemBase"
    page.padding = 0

    # 1. Configuração do Tema Dinâmico (Automático e Manual)
    pref_tema = await storage.carregar_preferencia_tema(page)

    def on_brightness_change(e=None):
        pref = storage.obter_preferencia_tema_memoria(page)
        if pref == "system":
            T.aplicar_tema_app(page, "system")

    page.on_platform_brightness_change = on_brightness_change
    T.aplicar_tema_app(page, pref_tema)

    # 2. Limpa qualquer sessão residual em memória para garantir abertura na tela de início (Auth).
    # O e-mail salvo em 'Lembrar de mim' permanece disponível para preenchimento na tela de login.
    try:
        db.fazer_logout()
        session_remove(page, "auth_access_token")
        session_remove(page, "auth_refresh_token")
    except Exception:
        pass

    # 3. Configura roteamento
    configurar_rotas(page)

    # 4. Navegação inicial sempre para a tela de início (ROTA_AUTH)
    await ajustar_janela_login(page)
    page.route = ROTA_AUTH
    if hasattr(page, "_reconstruir_rota") and callable(page._reconstruir_rota):
        page._reconstruir_rota()
    else:
        navegar(page, ROTA_AUTH)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
