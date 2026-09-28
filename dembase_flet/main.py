"""
=============================================================================
DemBase v3 — main.py  (Flet 1.0 — async)
=============================================================================
"""
import flet as ft
from core import theme as T
from core.router import configurar_rotas, ROTA_AUTH, ROTA_DASHBOARD
import services.supabase_client as db


async def main(page: ft.Page):
    page.title      = "DemBase"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor    = T.BG
    page.padding    = 0
    page.theme      = ft.Theme(font_family="Inter")

    page.window.width  = 480
    page.window.height = 680
    page.update()
    await page.window.center()

    configurar_rotas(page)

    try:
        sessao = db.sessao_atual()
        logado = bool(sessao and getattr(sessao, "user", None))
    except Exception:
        logado = False

    if logado:
        page.window.width  = 1280
        page.window.height = 800
        page.update()
        await page.window.center()
        await page.push_route(ROTA_DASHBOARD)
    else:
        await page.push_route(ROTA_AUTH)


if __name__ == "__main__":
    ft.run(main)
