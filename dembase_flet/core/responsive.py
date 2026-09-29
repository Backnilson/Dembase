import flet as ft

MOBILE_BREAKPOINT = 768

def is_mobile(page: ft.Page) -> bool:
    """
    Retorna True se a tela atual for considerada 'Mobile' (abaixo do breakpoint).
    Usado para alternar entre BottomAppBar (Mobile) e Sidebar (Desktop).
    """
    if not page:
        return False
        
    return page.width < MOBILE_BREAKPOINT

def setup_responsive_resize(page: ft.Page):
    """
    Registra o evento on_resized para redesenhar a tela atual caso a janela 
    atravesse o breakpoint Mobile <-> Desktop, garantindo transição em tempo real.
    """
    from core.router import navegar
    page.session.store.set("was_mobile", is_mobile(page))

    def on_resize(e: ft.ControlEvent):
        was_mobile = page.session.store.get("was_mobile")
        currently_mobile = is_mobile(page)
        
        if was_mobile != currently_mobile:
            page.session.store.set("was_mobile", currently_mobile)
            navegar(page, page.route)
            
    page.on_resize = on_resize
