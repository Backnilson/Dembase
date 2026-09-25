import flet as ft

# =============================================================================
# DESIGN TOKENS E CORES (Estilo Minimalista Fintech / Dark Slate)
# =============================================================================
COLOR_BG = "#0B0F19"          # Fundo ultra-dark Slate
COLOR_SURFACE = "#151D2C"     # Cartões e superfícies principais
COLOR_SURFACE_ALT = "#1E293B" # Elementos secundários / campos
COLOR_BORDER = "#334155"      # Bordas suaves
COLOR_PRIMARY = "#10B981"     # Emerald Green (Fintech de alto padrão)
COLOR_PRIMARY_HOVER = "#059669"
COLOR_PRIMARY_LIGHT = "#34D399"
COLOR_RECEITA = "#10B981"     # Verde Receitas
COLOR_DESPESA = "#EF4444"     # Vermelho Despesas
COLOR_SALDO = "#6366F1"       # Índigo Saldo
COLOR_TEXT_PRIMARY = "#F8FAFC"
COLOR_TEXT_MUTED = "#94A3B8"
COLOR_ERROR = "#EF4444"
COLOR_WARNING = "#F59E0B"
COLOR_INFO = "#3B82F6"


# =============================================================================
# SISTEMA DE FEEDBACK VISUAL
# =============================================================================
def traduzir_erro_auth(erro_msg: str) -> str:
    """Traduz mensagens comuns do Supabase Auth para português amigável."""
    msg = str(erro_msg).lower()
    if "invalid login credentials" in msg:
        return "E-mail ou senha incorretos. Verifique suas credenciais."
    elif "user already registered" in msg:
        return "Este e-mail já está cadastrado. Alterne para a aba 'Entrar'."
    elif "password should be at least" in msg:
        return "A senha deve conter no mínimo 6 caracteres."
    elif "valid email" in msg or "invalid email" in msg:
        return "Por favor, informe um endereço de e-mail válido."
    elif "email not confirmed" in msg:
        return "E-mail ainda não confirmado. Verifique a sua caixa de entrada."
    elif "network" in msg or "connection" in msg:
        return "Erro de conexão com o servidor. Verifique sua internet."
    return f"Ocorreu um erro: {erro_msg}"

def mostrar_feedback(page: ft.Page, mensagem: str, tipo: str = "info"):
    """
    Exibe um feedback visual flutuante e moderno para o usuário.
    Tipos: 'sucesso', 'erro', 'alerta', 'info'.
    """
    paleta = {
        "sucesso": {
            "bg": "#064E3B",
            "icon_color": "#34D399",
            "icon": ft.Icons.CHECK_CIRCLE_ROUNDED,
        },
        "erro": {
            "bg": "#7F1D1D",
            "icon_color": "#F87171",
            "icon": ft.Icons.ERROR_OUTLINE_ROUNDED,
        },
        "alerta": {
            "bg": "#78350F",
            "icon_color": "#FBBF24",
            "icon": ft.Icons.WARNING_AMBER_ROUNDED,
        },
        "info": {
            "bg": "#1E3A8A",
            "icon_color": "#60A5FA",
            "icon": ft.Icons.INFO_OUTLINE_ROUNDED,
        },
    }
    config = paleta.get(tipo, paleta["info"])

    snack = ft.SnackBar(
        content=ft.Row(
            controls=[
                ft.Icon(config["icon"], color=config["icon_color"], size=20),
                ft.Text(
                    mensagem,
                    color=COLOR_TEXT_PRIMARY,
                    size=13,
                    weight=ft.FontWeight.W_500,
                    expand=True,
                ),
            ],
            spacing=10,
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=config["bg"],
        behavior=ft.SnackBarBehavior.FLOATING,
        duration=4000,
    )

    if hasattr(page, "open"):
        page.open(snack)
    else:
        page.snack_bar = snack
        page.snack_bar.open = True
        page.update()
