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
    Dimensiona de forma segura e proporcional dentro da área útil da tela,
    garantindo que o topo nunca corte a barra de título e a base nunca encoste na barra de tarefas.
    """
    if getattr(page, "web", False) or getattr(page, "platform", None) in (
        ft.PagePlatform.ANDROID,
        ft.PagePlatform.IOS,
    ):
        return

    # 1. Configurações base da janela
    page.window.maximized = False
    page.window.resizable = True
    page.window.title_bar_hidden = False
    page.window.frameless = False

    # 2. Resolução real e área útil (descontando barra de tarefas)
    w_util, h_util, off_x, off_y = obter_area_de_trabalho()

    # 3. Dimensões compactas e seguras:
    # Largura: ideal entre 440px e 460px (proporcional, máx 70% da tela)
    largura = min(460, max(380, int(w_util * 0.70)))

    # Altura: NUNCA maior que (h_util - 80px) para garantir folga visual no topo e base
    altura = min(540, max(420, h_util - 80))

    # Limites mínimos para o redimensionamento manual
    page.window.min_width = 360
    page.window.min_height = 380

    page.window.width = largura
    page.window.height = altura

    # 4. Posicionamento centralizado com margens de segurança matemática:
    # Garante que 'top' seja no mínimo 28px abaixo do topo do monitor (barra de título 100% visível)
    pos_top = off_y + max(28, (h_util - altura) // 2)
    pos_left = off_x + max(20, (w_util - largura) // 2)

    page.window.top = pos_top
    page.window.left = pos_left

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
