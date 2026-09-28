"""
=============================================================================
DemBase v3 — main.py  (Flet 1.0 — async)
=============================================================================
"""
import flet as ft
from core import theme as T
from core.router import configurar_rotas, navegar, ROTA_AUTH, ROTA_DASHBOARD
from core.window_manager import ajustar_janela_login, ajustar_janela_principal
import services.supabase_client as db


async def main(page: ft.Page):
    page.title      = "DemBase"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = T.BG
    page.padding    = 0
    page.theme      = ft.Theme(font_family="Inter")

    configurar_rotas(page)

    try:
        sessao = db.sessao_atual()
        logado = bool(sessao and getattr(sessao, "user", None))
    except Exception:
        logado = False

    if logado:
        await ajustar_janela_principal(page)
        navegar(page, ROTA_DASHBOARD)
    else:
        await ajustar_janela_login(page)
        navegar(page, ROTA_AUTH)


if __name__ == "__main__":
    ft.run(main)
