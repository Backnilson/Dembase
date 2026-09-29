"""
=============================================================================
DemBase v3 — core/router.py  (Flet 1.0.1)
Centraliza todas as rotas da aplicação.
Todas as views pós-login são montadas DENTRO do Shell (sidebar + header).
=============================================================================
"""
import flet as ft
from services import supabase_client as db

# ── Constantes de rota ────────────────────────────────────────────────────────
ROTA_AUTH        = "/auth"
ROTA_DASHBOARD   = "/dashboard"
ROTA_LANCAMENTO  = "/lancamento"
ROTA_CONTAS      = "/contas"
ROTA_CARTOES     = "/cartoes"
ROTA_CALENDARIO  = "/calendario"
ROTA_RELATORIOS  = "/relatorios"
ROTA_CONFIG      = "/configuracoes"

# Rotas que não usam o shell (login, onboarding futuro, etc.)
_ROTAS_SEM_SHELL = {ROTA_AUTH}


# =============================================================================
# NAVEGAÇÃO
# =============================================================================
def navegar(page: ft.Page, rota: str):
    """Navega para uma rota no Flet 1.0 usando page.navigate."""
    page.navigate(rota)


# =============================================================================
# ROTEADOR PRINCIPAL
# =============================================================================
def configurar_rotas(page: ft.Page):
    from views.auth_view       import criar_view_auth
    from views.dashboard_view  import criar_view_dashboard
    from views.lancamento_view import criar_view_lancamento
    from views.shell_view      import (
        criar_shell, placeholder_view,
        ROTA_CONTAS, ROTA_CARTOES, ROTA_CALENDARIO, ROTA_RELATORIOS, ROTA_CONFIG
    )

    def _logado() -> bool:
        try:
            sessao = db.sessao_atual()
            return bool(sessao and getattr(sessao, "user", None))
        except Exception:
            return False

    def _view_para_rota(rota: str) -> ft.View:
        """Retorna a View correta para a rota solicitada."""

        # ── Auth ──────────────────────────────────────────────────────────────
        if rota == ROTA_AUTH:
            return criar_view_auth(page)

        # ── Dashboard ─────────────────────────────────────────────────────────
        if rota == ROTA_DASHBOARD:
            return criar_view_dashboard(page)

        # ── Lançamento (view empilhada sobre o dashboard) ─────────────────────
        if rota == ROTA_LANCAMENTO:
            return criar_view_lancamento(page)

        # ── Contas Bancárias ──────────────────────────────────────────────────
        if rota == ROTA_CONTAS:
            # Import lazy para não criar dependência circular no startup
            try:
                from views.contas_view import criar_view_contas
                return criar_view_contas(page)
            except ImportError:
                return criar_shell(
                    page, rota_ativa=rota,
                    conteudo=placeholder_view(
                        "Contas Bancárias",
                        "Gerencie suas contas e saldos.\nEm breve disponível.",
                        ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                    ),
                )

        # ── Cartões de Crédito ────────────────────────────────────────────────
        if rota == ROTA_CARTOES:
            try:
                from views.cartoes_view import criar_view_cartoes
                return criar_view_cartoes(page)
            except ImportError:
                return criar_shell(
                    page, rota_ativa=rota,
                    conteudo=placeholder_view(
                        "Cartões de Crédito",
                        "Controle limites, faturas e vencimentos.\nEm breve disponível.",
                        ft.Icons.CREDIT_CARD_ROUNDED,
                    ),
                )

        # ── Calendário ────────────────────────────────────────────────────────
        if rota == ROTA_CALENDARIO:
            try:
                from views.calendario_view import criar_view_calendario
                return criar_view_calendario(page)
            except ImportError:
                return criar_shell(
                    page, rota_ativa=rota,
                    conteudo=placeholder_view(
                        "Calendário",
                        "Visualize seus lançamentos por dia.\nEm breve disponível.",
                        ft.Icons.CALENDAR_MONTH_ROUNDED,
                    ),
                )

        # ── Relatórios ────────────────────────────────────────────────────────
        if rota == ROTA_RELATORIOS:
            try:
                from views.relatorios_view import criar_view_relatorios
                return criar_view_relatorios(page)
            except ImportError:
                return criar_shell(
                    page, rota_ativa=rota,
                    conteudo=placeholder_view(
                        "Relatórios",
                        "Análises detalhadas por categoria e período.\nEm breve disponível.",
                        ft.Icons.BAR_CHART_ROUNDED,
                    ),
                )

        # ── Configurações ─────────────────────────────────────────────────────
        if rota == ROTA_CONFIG:
            try:
                from views.config_view import criar_view_config
                return criar_view_config(page)
            except ImportError:
                return criar_shell(
                    page, rota_ativa=rota,
                    conteudo=placeholder_view(
                        "Configurações",
                        "Perfil, preferências e importação de dados.",
                        ft.Icons.SETTINGS_ROUNDED,
                    ),
                )

        # ── Fallback ──────────────────────────────────────────────────────────
        return criar_view_dashboard(page) if _logado() else criar_view_auth(page)

    # =========================================================================
    # EVENT: on_route_change
    # =========================================================================
    def on_route_change(e: ft.RouteChangeEvent):
        rota = page.route
        logado = _logado()

        # Redireciona não-logado para auth
        if not logado and rota not in _ROTAS_SEM_SHELL:
            page.views.clear()
            page.views.append(criar_view_auth(page))
            page.update()
            return

        # Redireciona logado que tenta ir para auth
        if logado and rota == ROTA_AUTH:
            page.views.clear()
            page.views.append(criar_view_dashboard(page))
            page.update()
            return

        # Views empilhadas (back possível)
        _VIEWS_EMPILHADAS = {ROTA_LANCAMENTO}
        if rota in _VIEWS_EMPILHADAS:
            # Garante que o dashboard está como base
            if not any(v.route == ROTA_DASHBOARD for v in page.views):
                page.views.insert(0, criar_view_dashboard(page))
            page.views.append(_view_para_rota(rota))
        else:
            # Views de nível raiz: substitui tudo
            page.views.clear()
            page.views.append(_view_para_rota(rota))

        page.update()

    # =========================================================================
    # EVENT: on_view_pop (botão voltar)
    # =========================================================================
    def on_view_pop(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            page.views.pop()
        page.update()

    page.on_route_change = on_route_change
    page.on_view_pop     = on_view_pop
