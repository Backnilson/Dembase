"""
=============================================================================
DemBase v3 — core/theme.py  (Flet 1.0 compatible)
Design tokens, paleta de cores e estilos reutilizáveis.
=============================================================================
"""
import flet as ft

# =============================================================================
# PALETA DE CORES
# =============================================================================
BG           = "#0B0F19"
SURFACE      = "#151D2C"
SURFACE_ALT  = "#1E293B"
BORDER       = "#334155"

PRIMARY      = "#10B981"
PRIMARY_DARK = "#059669"
PRIMARY_SOFT = "#34D399"

RECEITA      = "#10B981"
DESPESA      = "#EF4444"
SALDO        = "#6366F1"

TEXT_PRIMARY = "#F8FAFC"
TEXT_MUTED   = "#94A3B8"

ERROR   = "#EF4444"
WARNING = "#F59E0B"
INFO    = "#3B82F6"


# =============================================================================
# HELPERS DE LAYOUT (Flet 1.0 — sem ft.padding.all/symmetric/ft.border.all)
# =============================================================================
def pad(all_: int = None, h: int = 0, v: int = 0,
        left: int = 0, top: int = 0, right: int = 0, bottom: int = 0) -> ft.Padding:
    """Helper de padding compatível com Flet 1.0."""
    if all_ is not None:
        return ft.Padding(left=all_, top=all_, right=all_, bottom=all_)
    if h or v:
        return ft.Padding(left=h, right=h, top=v, bottom=v)
    return ft.Padding(left=left, top=top, right=right, bottom=bottom)


def borda(width: float = 1, color: str = BORDER) -> ft.Border:
    """Cria border em todos os lados."""
    s = ft.BorderSide(width=width, color=color)
    return ft.Border(top=s, right=s, bottom=s, left=s)


def borda_bottom(width: float = 1, color: str = BORDER) -> ft.Border:
    """Cria border apenas embaixo."""
    return ft.Border(bottom=ft.BorderSide(width=width, color=color))


def centro() -> ft.Alignment:
    """Equivalente ao antigo ft.alignment.center."""
    return ft.Alignment(0, 0)


def topo_centro() -> ft.Alignment:
    return ft.Alignment(0, -1)


# =============================================================================
# ESTILO DE CAMPO (TextField / Dropdown) — Flet 1.0
# =============================================================================
def campo_estilo(**kwargs) -> dict:
    base = dict(
        border_color=BORDER,
        focused_border_color=PRIMARY,
        border_radius=10,
        filled=True,
        fill_color=SURFACE_ALT,
        cursor_color=PRIMARY,
        text_size=13,
        color=TEXT_PRIMARY,
        label_style=ft.TextStyle(color=TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=TEXT_MUTED, size=11),
        content_padding=pad(h=14, v=12),
    )
    base.update(kwargs)
    return base


def dropdown_estilo(**kwargs) -> dict:
    base = dict(
        border_color=BORDER,
        focused_border_color=PRIMARY,
        border_radius=10,
        filled=True,
        fill_color=SURFACE_ALT,
        text_size=13,
        color=TEXT_PRIMARY,
        label_style=ft.TextStyle(color=TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=TEXT_MUTED, size=11),
        content_padding=pad(h=14, v=12),
    )
    base.update(kwargs)
    return base


# =============================================================================
# BOTÕES — Flet 1.0 (FilledButton, não ElevatedButton)
# =============================================================================
def botao_primario(texto: str, on_click=None, icone=None, expand=False) -> ft.FilledButton:
    return ft.FilledButton(
        content=texto,
        icon=icone,
        on_click=on_click,
        expand=expand,
        style=ft.ButtonStyle(
            bgcolor=PRIMARY,
            color=ft.Colors.WHITE,
            overlay_color=PRIMARY_DARK,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=24, v=14),
            text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_600),
        ),
    )


def botao_outline(texto: str, on_click=None, icone=None, cor=None) -> ft.OutlinedButton:
    cor = cor or TEXT_MUTED
    return ft.OutlinedButton(
        content=texto,
        icon=icone,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=cor,
            side=ft.BorderSide(width=1, color=BORDER),
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=20, v=12),
            text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_500),
        ),
    )


# =============================================================================
# CONTAINER SURFACE
# =============================================================================
def surface_container(content, padding=20, radius=16, border=True) -> ft.Container:
    p = pad(all_=padding) if isinstance(padding, int) else padding
    return ft.Container(
        content=content,
        padding=p,
        bgcolor=SURFACE,
        border_radius=radius,
        border=borda() if border else None,
    )


# =============================================================================
# FEEDBACK VISUAL (SnackBar)
# =============================================================================
def mostrar_feedback(page: ft.Page, mensagem: str, tipo: str = "info"):
    paleta = {
        "sucesso": {"bg": "#064E3B", "icon_color": "#34D399", "icon": ft.Icons.CHECK_CIRCLE_ROUNDED},
        "erro":    {"bg": "#7F1D1D", "icon_color": "#F87171", "icon": ft.Icons.ERROR_OUTLINE_ROUNDED},
        "alerta":  {"bg": "#78350F", "icon_color": "#FBBF24", "icon": ft.Icons.WARNING_AMBER_ROUNDED},
        "info":    {"bg": "#1E3A8A", "icon_color": "#60A5FA", "icon": ft.Icons.INFO_OUTLINE_ROUNDED},
    }
    c = paleta.get(tipo, paleta["info"])
    snack = ft.SnackBar(
        content=ft.Row(
            controls=[
                ft.Icon(c["icon"], color=c["icon_color"], size=20),
                ft.Text(mensagem, color=TEXT_PRIMARY, size=13,
                        weight=ft.FontWeight.W_500, expand=True),
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=c["bg"],
        behavior=ft.SnackBarBehavior.FLOATING,
        duration=4000,
    )
    page.overlay.append(snack)
    snack.open = True
    page.update()


# =============================================================================
# TRADUÇÃO DE ERROS AUTH
# =============================================================================
def traduzir_erro_auth(msg: str) -> str:
    m = str(msg).lower()
    if "invalid login credentials" in m: return "E-mail ou senha incorretos."
    if "user already registered" in m:   return "Este e-mail já está cadastrado."
    if "password should be at least" in m: return "Senha: mínimo 6 caracteres."
    if "valid email" in m or "invalid email" in m: return "Informe um e-mail válido."
    if "email not confirmed" in m: return "Confirme seu e-mail antes de entrar."
    if "network" in m or "connection" in m: return "Sem conexão. Verifique a internet."
    return f"Erro: {msg}"
