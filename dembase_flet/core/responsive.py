import flet as ft

MOBILE_BREAKPOINT = 768
EXTRA_LARGE_BREAKPOINT = 1800


def is_mobile(page: ft.Page) -> bool:
    """
    Retorna True se a tela atual for considerada 'Mobile' (abaixo do breakpoint ou plataforma mobile).
    Usado para alternar entre BottomAppBar (Mobile) e Sidebar (Desktop).
    """
    if not page:
        return False
    if getattr(page, "platform", None) in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
        if getattr(page, "width", None) and page.width >= MOBILE_BREAKPOINT:
            return False
        return True
    if getattr(page, "width", None) is not None:
        return page.width < MOBILE_BREAKPOINT
    return False


def is_extra_large(page: ft.Page) -> bool:
    """
    Retorna True se a tela atual for considerada 'Extra Grande' (monitores ultrawide, >= 1800px).
    Usado para aplicar contenção proporcional e elegante evitando esticamento excessivo.
    """
    if not page or getattr(page, "width", None) is None:
        return False
    # Telas mobile/touch nativas nunca são tratadas como ultrawide
    if getattr(page, "platform", None) in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
        return False
    return page.width >= EXTRA_LARGE_BREAKPOINT


def get_screen_category(page: ft.Page) -> str:
    """
    Retorna a categoria de dimensão atual da tela:
    - 'mobile': < 768px (ou SO mobile)
    - 'desktop': 768px a 1799px (Desktop padrão aprovado — NUNCA alterado)
    - 'extra_large': >= 1800px (Monitores Ultrawide / Grandes)
    """
    if is_mobile(page):
        return "mobile"
    if is_extra_large(page):
        return "extra_large"
    return "desktop"


def setup_responsive_resize(page: ft.Page):
    """
    Registra o evento on_resized para redesenhar a tela atual caso a janela 
    atravesse os breakpoints (Mobile <-> Desktop <-> Extra Grande), garantindo 
    transição em tempo real sem reload.
    """
    from core.router import navegar
    from core.constants import session_set, session_get

    cat_inicial = get_screen_category(page)
    session_set(page, "screen_category", cat_inicial)
    session_set(page, "was_mobile", is_mobile(page))

    def on_resize(e: ft.ControlEvent):
        cat_anterior = session_get(page, "screen_category")
        cat_atual = get_screen_category(page)

        if cat_anterior != cat_atual:
            session_set(page, "screen_category", cat_atual)
            session_set(page, "was_mobile", is_mobile(page))

            # Reconstrói a rota ativa preservando o estado
            if hasattr(page, "_reconstruir_rota") and callable(page._reconstruir_rota):
                page._reconstruir_rota(forcar_rebuild=True)
            else:
                navegar(page, page.route)
            try:
                page.update()
            except Exception:
                pass

    page.on_resize = on_resize
