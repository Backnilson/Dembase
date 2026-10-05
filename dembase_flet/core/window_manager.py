"""
=============================================================================
DemBase v3 — core/window_manager.py (Flet 1.0.1)
Gerenciamento responsivo e seguro do tamanho e posicionamento de janela no Windows.
Garante que a barra de título nunca seja cortada ou posicionada fora da tela.
=============================================================================
"""
import sys
import ctypes
from ctypes import wintypes
import flet as ft


def obter_area_de_trabalho() -> tuple[int, int, int, int]:
    """
    Retorna (largura_util, altura_util, offset_left, offset_top) da área de trabalho
    da tela principal no Windows, descontando a barra de tarefas e respeitando o DPI.
    """
    if sys.platform == "win32":
        try:
            # Habilita Per-Monitor DPI awareness para obter coordenadas reais em monitores com escala (>100%)
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

            rect = wintypes.RECT()
            # SPI_GETWORKAREA = 0x0030
            if ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0):
                w = rect.right - rect.left
                h = rect.bottom - rect.top
                if w > 0 and h > 0:
                    return w, h, rect.left, rect.top
        except Exception:
            pass

    # Fallback padrão seguro para telas não-Windows ou falhas
    return 1366, 768, 0, 0


async def ajustar_janela_login(page: ft.Page) -> None:
    """
    Configura a janela para a tela de autenticação (/auth).
    Inicia maximizada por padrão no desktop para experiência imersiva e responsiva,
    garantindo que a barra de título e botões nativos permaneçam visíveis.
    """
    if getattr(page, "web", False) or getattr(page, "platform", None) in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.IOS,
    ):
        return

    page.window.min_width = 380
    page.window.min_height = 560
    page.window.resizable = True
    page.window.title_bar_hidden = False
    page.window.frameless = False
    page.window.maximized = True
    page.window.visible = True
    page.update()


async def ajustar_janela_principal(page: ft.Page) -> None:
    """
    Configura a janela para a tela principal pós-login (Dashboard e demais módulos).
    Maximiza a janela na tela do usuário gerando o efeito de expansão visual,
    mantendo obrigatoriamente a barra de título e os botões nativos do SO visíveis.
    """
    if getattr(page, "web", False) or getattr(page, "platform", None) in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.IOS,
    ):
        return

    page.window.min_width = 960
    page.window.min_height = 580
    page.window.resizable = True
    page.window.title_bar_hidden = False
    page.window.frameless = False
    page.window.maximized = True
    page.window.visible = True
    page.update()
