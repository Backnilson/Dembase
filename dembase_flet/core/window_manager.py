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
    da tela principal no Windows, descontando a barra de tarefas.
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
                return w, h, rect.left, rect.top
        except Exception:
            pass

    # Fallback padrão seguro para telas não-Windows ou falhas
    return 1366, 768, 0, 0


async def ajustar_janela_login(page: ft.Page) -> None:
    """
    Configura a janela para a tela de autenticação (/auth).
    Tamanho compacto, centralizado e com redimensionamento travado (resizable = False).
    Garante top >= 20 para manter a barra de título sempre visível.
    """
    work_w, work_h, off_left, off_top = obter_area_de_trabalho()

    largura = min(460, int(work_w * 0.90))
    altura = min(660, int(work_h * 0.88))

    top = max(20, off_top + (work_h - altura) // 2)
    left = max(20, off_left + (work_w - largura) // 2)

    page.window.maximized = False
    page.window.resizable = False
    page.window.width = largura
    page.window.height = altura
    page.window.top = top
    page.window.left = left
    page.update()


async def ajustar_janela_principal(page: ft.Page) -> None:
    """
    Configura a janela para a tela principal (Dashboard e demais módulos).
    Redimensionamento dinâmico (Opção A) respeitando a resolução da tela:
    - Ocupa aproximadamente 92% da largura útil e 88% da altura útil.
    - Garante top >= 20 para que a barra de título do Windows fique SEMPRE visível.
    - Define limites mínimos (min_width, min_height) para manter o layout legível.
    - Libera o redimensionamento do usuário (resizable = True).
    """
    work_w, work_h, off_left, off_top = obter_area_de_trabalho()

    largura = min(1360, max(960, int(work_w * 0.92)))
    altura = min(840, max(580, int(work_h * 0.88)))

    top = max(20, off_top + (work_h - altura) // 2)
    left = max(20, off_left + (work_w - largura) // 2)

    page.window.min_width = 960
    page.window.min_height = 580
    page.window.maximized = False
    page.window.resizable = True
    page.window.width = largura
    page.window.height = altura
    page.window.top = top
    page.window.left = left
    page.update()
