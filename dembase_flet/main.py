"""
=============================================================================
DemBase v3 — main.py  (Flet 1.0.1 — async)
Ponto de entrada principal com Login Persistente Automático (estilo Mobills),
Splash Screen de inicialização e renovação silenciosa de sessão.
=============================================================================
"""
import asyncio
import flet as ft
from core import theme as T
from core.router import configurar_rotas, navegar, ROTA_AUTH, ROTA_DASHBOARD
from core.window_manager import ajustar_janela_login, ajustar_janela_principal
from core import storage
from core import click_guard
from views.widgets.auth.logo import criar_logo
import services.supabase_client as db


def _criar_view_splash() -> ft.View:
    """Tela de transição/splash limpa com a identidade do DemBase (evita piscar Login)."""
    return ft.View(
        route="/splash",
        bgcolor=T.BG,
        padding=0,
        controls=[
            ft.Container(
                expand=True,
                bgcolor=T.BG,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    tight=True,
                    spacing=22,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        criar_logo(size=72, com_texto=True, centralizado=True),
                        ft.ProgressRing(
                            width=28,
                            height=28,
                            stroke_width=2.8,
                            color=T.NEON,
                        ),
                    ],
                ),
            )
        ],
    )


async def main(page: ft.Page):
    page.title   = "DemBase Finanças"
    page.padding = 0

    # 1. Configuração do Tema - Modo Escuro Padrão Absoluto DemBase
    page.theme_mode = ft.ThemeMode.DARK
    T.aplicar_paleta(True)
    page.bgcolor = T.BG

    # 2. Inicializa SharedPreferences e carrega tema
    storage._obter_sp(page)
    pref_tema = await storage.carregar_preferencia_tema(page)
    T.aplicar_tema_app(page, pref_tema)

    # 3. Exibe imediatamente a Splash Screen antes de qualquer operação de rede
    page.views.clear()
    page.views.append(_criar_view_splash())
    page.update()

    # 4. Proteção global de cliques e configuração das rotas
    click_guard.instalar(page)
    configurar_rotas(page)

    # 5. Registra listener de rotação de tokens do Supabase (TOKEN_REFRESHED / SIGNED_IN)
    def _on_tokens_atualizados(acc: str, ref: str, email: str):
        try:
            storage.salvar_sessao_autenticada_sync(page, acc, ref, email=email, persistir=None)
        except Exception:
            pass

    db.registrar_listener_sessao(_on_tokens_atualizados)

    # 6. Fluxo de Auto-Login Persistente (Restauração + Rotação de Refresh Token)
    sessao_restaurada = False
    try:
        acc_salvo, ref_salvo, email_salvo = await storage.carregar_sessao_autenticada(page)
        if ref_salvo:
            novos_tokens = await asyncio.to_thread(db.restaurar_sessao, acc_salvo, ref_salvo)
            if novos_tokens and novos_tokens.get("access_token") and novos_tokens.get("refresh_token"):
                # Regra Obrigatória de Rotação: salva imediatamente os novos tokens rotacionados
                await storage.salvar_sessao_autenticada(
                    page,
                    novos_tokens["access_token"],
                    novos_tokens["refresh_token"],
                    email=novos_tokens.get("email") or email_salvo,
                    persistir=True,
                )
                sessao_restaurada = True
            else:
                # Refresh token expirado ou revogado: limpa silenciosamente mantendo último e-mail
                await storage.limpar_sessao_autenticada(page)
    except Exception:
        try:
            await storage.limpar_sessao_autenticada(page)
        except Exception:
            pass

    if sessao_restaurada:
        await ajustar_janela_principal(page)
        try:
            await asyncio.to_thread(db.aquecer_cache)
        except Exception:
            pass
        try:
            await asyncio.to_thread(db.gerar_recorrentes_pendentes)
        except Exception:
            pass
        page.route = ROTA_DASHBOARD
        if hasattr(page, "_reconstruir_rota") and callable(page._reconstruir_rota):
            page._reconstruir_rota(forcar_rebuild=True)
        else:
            navegar(page, ROTA_DASHBOARD)
    else:
        await ajustar_janela_login(page)
        page.route = ROTA_AUTH
        if hasattr(page, "_reconstruir_rota") and callable(page._reconstruir_rota):
            page._reconstruir_rota(forcar_rebuild=True)
        else:
            navegar(page, ROTA_AUTH)

    # 7. Renovação Silenciosa de Sessão Durante Uso Prolongado (> 1 hora)
    async def _loop_renovacao_silenciosa():
        while True:
            await asyncio.sleep(300)  # Verifica a cada 5 minutos
            try:
                sess = db.sessao_atual()
                if not sess or not getattr(sess, "user", None):
                    continue
                novos = await asyncio.to_thread(db.renovar_sessao_se_necessario, 600)
                if novos and novos.get("access_token") and novos.get("refresh_token"):
                    persistir = storage.manter_conectado_ativo(page)
                    await storage.salvar_sessao_autenticada(
                        page,
                        novos["access_token"],
                        novos["refresh_token"],
                        email=novos.get("email") or "",
                        persistir=persistir,
                    )
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    page.run_task(_loop_renovacao_silenciosa)

    # 8. Gerenciamento de Ciclo de Vida (Mobile Background / Foreground)
    async def on_app_lifecycle(e: ft.AppLifecycleStateChangeEvent):
        estado = str(getattr(e, "state", "") or "").lower()
        if estado in ("resume", "show"):
            sess = db.sessao_atual()
            if sess and getattr(sess, "user", None):
                # Garante JWT válido ao voltar do background antes de atualizar a tela
                try:
                    novos = await asyncio.to_thread(db.renovar_sessao_se_necessario, 600)
                    if novos and novos.get("access_token") and novos.get("refresh_token"):
                        persistir = storage.manter_conectado_ativo(page)
                        await storage.salvar_sessao_autenticada(
                            page,
                            novos["access_token"],
                            novos["refresh_token"],
                            email=novos.get("email") or "",
                            persistir=persistir,
                        )
                except Exception:
                    pass
                if page.views:
                    refresh_fn = getattr(page.views[-1], "_dembase_refresh", None)
                    if callable(refresh_fn):
                        try:
                            refresh_fn()
                        except Exception:
                            pass

    page.on_app_lifecycle_state_change = on_app_lifecycle


if __name__ == "__main__":
    import os

    _porta_servidor = os.environ.get("PORT")
    if _porta_servidor:
        os.environ.setdefault("FLET_FORCE_WEB_SERVER", "true")
        _assets = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
        ft.run(
            main,
            host="0.0.0.0",
            port=int(_porta_servidor),
            view=ft.AppView.WEB_BROWSER,
            assets_dir=_assets,
        )
    else:
        ft.run(main, assets_dir="assets")
