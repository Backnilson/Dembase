"""
=============================================================================
DemBase v3 — core/theme.py  (Flet 1.0.1 compatible)
Design tokens, paleta de cores dinâmica (Dark / Light) e estilos reutilizáveis.
=============================================================================
"""
import flet as ft

# =============================================================================
# DEFINIÇÃO DAS PALETAS (DARK & LIGHT)
# =============================================================================
_DARK = {
    "BG": "#0B0F19",
    "SURFACE": "#151D2C",
    "SURFACE_ALT": "#1E293B",
    "BORDER": "#334155",
    "TEXT_PRIMARY": "#F8FAFC",
    "TEXT_MUTED": "#94A3B8",
    "PRIMARY": "#00E676",         # Verde Neon no tema escuro
    "PRIMARY_DARK": "#00C853",
    "PRIMARY_SOFT": "#69F0AE",
    "RECEITA": "#00E676",
    "DESPESA": "#EF4444",
    "SALDO": "#6366F1",
    "ERROR": "#EF4444",
    "WARNING": "#F59E0B",
    "INFO": "#3B82F6",
    "ON_PRIMARY": "#04130B",       # Cor de contraste perfeita sobre PRIMARY no tema escuro (Neon)
}

_LIGHT = {
    "BG": "#F8FAFC",
    "SURFACE": "#FFFFFF",
    "SURFACE_ALT": "#F1F5F9",
    "BORDER": "#E2E8F0",
    "TEXT_PRIMARY": "#0F172A",
    "TEXT_MUTED": "#64748B",
    "PRIMARY": "#00A152",         # Verde legível e de alto contraste sobre fundo claro
    "PRIMARY_DARK": "#007A3D",
    "PRIMARY_SOFT": "#00C853",
    "RECEITA": "#00A152",
    "DESPESA": "#DC2626",
    "SALDO": "#4F46E5",
    "ERROR": "#DC2626",
    "WARNING": "#D97706",
    "INFO": "#2563EB",
    "ON_PRIMARY": "#FFFFFF",       # Cor de contraste perfeita sobre PRIMARY no tema claro
}

# =============================================================================
# CORES DE DESTAQUE NEON (Constantes fixas para botões principais)
# =============================================================================
NEON        = "#00E676"  # Verde Neon vibrante
NEON_HOVER  = "#00C853"  # Verde Neon escuro para hover/overlay
ON_NEON     = "#04130B"  # Texto escuro de alto contraste sobre Verde Neon (WCAG AAA)
NEON_GLOW   = "#00E67626" # 15% opacity neon glow

# Estado global do tema ativo
IS_DARK: bool = True

# Inicialização padrão dos tokens no namespace do módulo
BG: str = _DARK["BG"]
SURFACE: str = _DARK["SURFACE"]
SURFACE_ALT: str = _DARK["SURFACE_ALT"]
BORDER: str = _DARK["BORDER"]
PRIMARY: str = _DARK["PRIMARY"]
PRIMARY_DARK: str = _DARK["PRIMARY_DARK"]
PRIMARY_SOFT: str = _DARK["PRIMARY_SOFT"]
RECEITA: str = _DARK["RECEITA"]
DESPESA: str = _DARK["DESPESA"]
SALDO: str = _DARK["SALDO"]
TEXT_PRIMARY: str = _DARK["TEXT_PRIMARY"]
TEXT_MUTED: str = _DARK["TEXT_MUTED"]
ERROR: str = _DARK["ERROR"]
WARNING: str = _DARK["WARNING"]
INFO: str = _DARK["INFO"]
ON_PRIMARY: str = _DARK["ON_PRIMARY"]

# Constantes de preferência de tema
TEMA_SISTEMA: str = "system"
TEMA_ESCURO: str  = "dark"
TEMA_CLARO: str   = "light"
PREFERENCIA_TEMA: str = "system"


def aplicar_paleta(escuro: bool = True) -> None:
    """
    Atualiza dinamicamente as constantes globais deste módulo para o tema ativo.
    Permite que qualquer chamada subsequente a T.BG, T.SURFACE, etc., receba a cor correta.
    """
    paleta = _DARK if escuro else _LIGHT
    globals().update(paleta)
    globals()["IS_DARK"] = escuro


def aplicar_tema_app(page: ft.Page, preferencia: str = None) -> bool:
    """
    Aplica o tema (system, dark ou light) à página e reconstrói as views em tempo real.
    Retorna True se o tema final aplicado for escuro, False se for claro.
    """
    from core.router import reconstruir_rota_atual
    from core import storage

    pref = preferencia or storage.obter_preferencia_tema_memoria(page) or "system"
    globals()["PREFERENCIA_TEMA"] = pref

    if pref == "dark":
        escuro = True
        page.theme_mode = ft.ThemeMode.DARK
    elif pref == "light":
        escuro = False
        page.theme_mode = ft.ThemeMode.LIGHT
    else:  # "system"
        page.theme_mode = ft.ThemeMode.SYSTEM
        pb = getattr(page, "platform_brightness", None)
        escuro = (pb != ft.Brightness.LIGHT)

    aplicar_paleta(escuro)
    page.bgcolor = BG
    page.theme = ft.Theme(font_family="Inter", color_scheme_seed=PRIMARY)
    page.dark_theme = ft.Theme(font_family="Inter", color_scheme_seed=NEON)
    reconstruir_rota_atual(page)
    return escuro


# Aplica paleta escura por padrão no carregamento
aplicar_paleta(True)


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


def borda(width: float = 1, color: str = None) -> ft.Border:
    """Cria border em todos os lados. Resolve dinamicamente a cor da borda se None."""
    cor = color if color is not None else BORDER
    s = ft.BorderSide(width=width, color=cor)
    return ft.Border(top=s, right=s, bottom=s, left=s)


def borda_bottom(width: float = 1, color: str = None) -> ft.Border:
    """Cria border apenas embaixo. Resolve dinamicamente a cor da borda se None."""
    cor = color if color is not None else BORDER
    return ft.Border(bottom=ft.BorderSide(width=width, color=cor))


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
        focused_border_color=NEON if IS_DARK else PRIMARY,
        border_radius=12,
        filled=True,
        fill_color=SURFACE_ALT,
        cursor_color=NEON if IS_DARK else PRIMARY,
        text_size=13.5,
        color=TEXT_PRIMARY,
        label_style=ft.TextStyle(color=TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=TEXT_MUTED, size=12),
        content_padding=pad(h=16, v=14),
    )
    base.update(kwargs)
    return base


def dropdown_estilo(**kwargs) -> dict:
    base = dict(
        border_color=BORDER,
        focused_border_color=NEON if IS_DARK else PRIMARY,
        border_radius=12,
        filled=True,
        fill_color=SURFACE_ALT,
        text_size=13.5,
        color=TEXT_PRIMARY,
        label_style=ft.TextStyle(color=TEXT_MUTED, size=13),
        hint_style=ft.TextStyle(color=TEXT_MUTED, size=12),
        content_padding=pad(h=16, v=14),
    )
    base.update(kwargs)
    return base


# =============================================================================
# BOTÕES — Flet 1.0 (FilledButton & OutlinedButton com Acento Neon)
# =============================================================================
def botao_primario(texto: str, on_click=None, icone=None, expand=False) -> ft.FilledButton:
    """Botão principal de ação em Verde Neon com texto escuro de alto contraste."""
    return ft.FilledButton(
        content=texto,
        icon=icone,
        on_click=on_click,
        expand=expand,
        style=ft.ButtonStyle(
            bgcolor=NEON,
            color=ON_NEON,
            icon_color=ON_NEON,
            overlay_color=NEON_HOVER,
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(h=24, v=15),
            text_style=ft.TextStyle(size=14, weight=ft.FontWeight.W_700),
        ),
    )


def botao_outline(texto: str, on_click=None, icone=None, cor=None) -> ft.OutlinedButton:
    cor_txt = cor or TEXT_PRIMARY
    return ft.OutlinedButton(
        content=texto,
        icon=icone,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=cor_txt,
            side=ft.BorderSide(width=1, color=BORDER),
            shape=ft.RoundedRectangleBorder(radius=12),
            padding=pad(h=20, v=14),
            text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
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
    paleta_dark = {
        "sucesso": {"bg": "#064E3B", "icon_color": "#34D399", "icon": ft.Icons.CHECK_CIRCLE_ROUNDED},
        "erro":    {"bg": "#7F1D1D", "icon_color": "#F87171", "icon": ft.Icons.ERROR_OUTLINE_ROUNDED},
        "alerta":  {"bg": "#78350F", "icon_color": "#FBBF24", "icon": ft.Icons.WARNING_AMBER_ROUNDED},
        "info":    {"bg": "#1E3A8A", "icon_color": "#60A5FA", "icon": ft.Icons.INFO_OUTLINE_ROUNDED},
    }
    paleta_light = {
        "sucesso": {"bg": "#DCFCE7", "icon_color": "#166534", "icon": ft.Icons.CHECK_CIRCLE_ROUNDED, "text_color": "#14532D"},
        "erro":    {"bg": "#FEE2E2", "icon_color": "#991B1B", "icon": ft.Icons.ERROR_OUTLINE_ROUNDED, "text_color": "#7F1D1D"},
        "alerta":  {"bg": "#FEF3C7", "icon_color": "#92400E", "icon": ft.Icons.WARNING_AMBER_ROUNDED, "text_color": "#78350F"},
        "info":    {"bg": "#DBEAFE", "icon_color": "#1E40AF", "icon": ft.Icons.INFO_OUTLINE_ROUNDED, "text_color": "#1E3A8A"},
    }
    fonte_paleta = paleta_dark if IS_DARK else paleta_light
    c = fonte_paleta.get(tipo, fonte_paleta["info"])
    txt_cor = c.get("text_color", TEXT_PRIMARY)

    snack = ft.SnackBar(
        content=ft.Row(
            controls=[
                ft.Icon(c["icon"], color=c["icon_color"], size=20),
                ft.Text(mensagem, color=txt_cor, size=13,
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
