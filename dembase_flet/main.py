"""
=============================================================================
DemBase v3 — main.py  (Flet 1.0.1 — async)
Ponto de entrada principal com suporte a Tema Dinâmico do Sistema (Dark/Light),
detecção de brilho da plataforma e restauração segura de sessão.
=============================================================================
"""
import os
import flet as ft
from core import theme as T
from core.router import configurar_rotas, navegar, reconstruir_rota_atual, ROTA_AUTH, ROTA_DASHBOARD
from core.window_manager import ajustar_janela_login, ajustar_janela_principal
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

    # 2. Configura roteamento
    configurar_rotas(page)

    # 3. Restauração de Sessão (Lembrar de mim / SharedPreferences / Sessão)
    logado = False
    try:
        email, acc, ref, lembrar_ativo = await storage.carregar_lembrar(page)

        if acc and ref:
            logado = db.restaurar_sessao(acc, ref)
        else:
            sessao = db.sessao_atual()
            logado = bool(sessao and getattr(sessao, "user", None))
    except Exception:
        logado = False

    # 4. Navegação inicial
    if logado:
        await ajustar_janela_principal(page)
        navegar(page, ROTA_DASHBOARD)
    else:
        await ajustar_janela_login(page)
        navegar(page, ROTA_AUTH)


if __name__ == "__main__":
    ft.run(main, assets_dir="assets")
