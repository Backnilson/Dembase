"""
=============================================================================
DemBase v3 — core/click_guard.py  (Flet 1.0.1)

Proteção GLOBAL de cliques, instalada uma única vez no ponto de entrada
(main.py). Resolve de forma estrutural o "congela e depois abre 6 vezes".

DIAGNÓSTICO (Flet 1.0.1):
  • Todo evento da UI passa por BaseControl._trigger_event (ponto único).
  • Handlers SÍNCRONOS (on_click=def ...) rodam DIRETO no event loop. Se o
    handler faz consultas Supabase (HTTP síncrono), o loop inteiro congela:
    nem o patch visual é enviado ao cliente, nem os próximos cliques são lidos.
  • Cliques dados durante o congelamento ficam na fila do socket e são
    despachados um a um quando o loop destrava → N aberturas repetidas.
  • navigate() só agenda push_route; o rebuild das views (on_route_change,
    síncrono) bloqueia o loop DEPOIS que o handler do clique já retornou.

SOLUÇÃO (um único choke point, vale para os ~370 on_click do app):
  1. Primeiro clique → trava o controle, aplica feedback visual (botão
     desabilitado + overlay global com "rodinha") e FAZ FLUSH do patch para o
     cliente ANTES de executar o handler (a rodinha anima no lado do cliente
     mesmo com o Python ocupado, e o overlay absorve cliques físicos).
  2. Cliques no mesmo controle em andamento são descartados.
  3. Se o handler bloqueou o loop (> _LIMITE_BLOQUEIO_S), abre uma janela de
     descarte curta: elimina os cliques que ficaram na fila durante o bloqueio.
  4. O overlay só some quando o handler E a navegação disparada por ele
     terminarem (rebuild de view incluso). Tudo em try/finally: erro nunca
     deixa a tela travada. Há ainda um watchdog de segurança.
  5. Instrumentação (DEMBASE_PERF=0 desliga): imprime handlers lentos e
     requisições HTTP lentas, para localizar o gargalo real.
=============================================================================
"""
from __future__ import annotations

import asyncio
import inspect
import os
import time
from typing import Any

import flet as ft
from flet.controls.base_control import BaseControl

# ── Parâmetros ────────────────────────────────────────────────────────────────
_EVENTOS_GUARDADOS = frozenset({"click", "tap"})
_FLUSH_S = 0.03                 # tempo para o patch visual chegar ao cliente
_LIMITE_BLOQUEIO_S = 0.12       # handler que bloqueou o loop acima disso
_JANELA_DESCARTE_S = 0.45       # descarta cliques enfileirados durante o bloqueio
_NAV_TIMEOUT_S = 6.0            # teto de espera pela navegação disparada
_WATCHDOG_S = 25.0              # teto absoluto de exibição do overlay
_ATRASO_ASYNC_S = 0.12          # handlers async: só mostra overlay se demorar
_OPACIDADE_BTN = 0.55
_PERF = os.environ.get("DEMBASE_PERF", "1") != "0"
_PERF_LIMITE_S = 0.25

_TIPOS_BOTAO = tuple(
    getattr(ft, _nome) for _nome in (
        "FilledButton", "ElevatedButton", "OutlinedButton", "TextButton",
        "IconButton", "FloatingActionButton", "FilledTonalButton",
    ) if hasattr(ft, _nome)
)

_instalado = False
_orig_trigger = BaseControl._trigger_event


class _Estado:
    """Estado de proteção por página/sessão."""

    def __init__(self) -> None:
        self.em_voo: set[Any] = set()
        self.ativos = 0
        self.overlay: ft.Container | None = None
        self.descartar_ate = 0.0
        self.nav_pendente = False
        self.nav_deadline = 0.0
        self.nav_inicio = 0.0
        self.watchdog: asyncio.TimerHandle | None = None


def _estado(page: ft.Page) -> _Estado:
    est = getattr(page, "_dembase_click_guard", None)
    if est is None:
        est = _Estado()
        page._dembase_click_guard = est
    return est


def _log(msg: str) -> None:
    if _PERF:
        print(f"[ClickGuard] {msg}")


# ── Instrumentação HTTP (diagnóstico do gargalo real) ─────────────────────────
class _HttpStats:
    n = 0
    total = 0.0
    lentas: list[tuple[str, float]] = []

    @classmethod
    def zerar(cls) -> None:
        cls.n, cls.total, cls.lentas = 0, 0.0, []


def _instrumentar_http() -> None:
    if not _PERF:
        return
    try:
        import httpx

        if getattr(httpx.Client.send, "_dembase_perf", False):
            return
        _send_orig = httpx.Client.send

        def _send(self, request, *a, **kw):
            t0 = time.perf_counter()
            try:
                return _send_orig(self, request, *a, **kw)
            finally:
                dt = time.perf_counter() - t0
                _HttpStats.n += 1
                _HttpStats.total += dt
                if dt > 0.35:
                    _HttpStats.lentas.append((f"{request.method} {request.url.path}", dt))

        _send._dembase_perf = True  # type: ignore[attr-defined]
        httpx.Client.send = _send  # type: ignore[method-assign]
    except Exception as ex:  # instrumentação nunca pode quebrar o app
        _log(f"instrumentação HTTP indisponível: {ex}")


# ── Overlay global com "rodinha" ──────────────────────────────────────────────
def _garantir_overlay(page: ft.Page, est: _Estado) -> ft.Container | None:
    try:
        if est.overlay is None:
            from core import theme as T

            est.overlay = ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                bgcolor=ft.Colors.with_opacity(0.30, "#000000"),
                opacity=0,
                animate_opacity=ft.Animation(200, ft.AnimationCurve.EASE_IN),
                ignore_interactions=True,
                content=ft.ProgressRing(
                    width=46, height=46, stroke_width=4, color=T.PRIMARY,
                ),
            )
        if not any(c is est.overlay for c in page.overlay):
            page.overlay.append(est.overlay)
            page.update()
        return est.overlay
    except Exception as ex:
        _log(f"overlay indisponível: {ex}")
        return None


def _mostrar_overlay(page: ft.Page, est: _Estado) -> None:
    est.ativos += 1
    ovl = _garantir_overlay(page, est)
    if ovl is None:
        return
    try:
        ovl.ignore_interactions = False
        ovl.opacity = 1
        ovl.update()
        loop = asyncio.get_running_loop()
        if est.watchdog is not None:
            est.watchdog.cancel()
        est.watchdog = loop.call_later(_WATCHDOG_S, _forcar_ocultar, page, est)
    except Exception as ex:
        _log(f"falha ao mostrar overlay: {ex}")


def _ocultar_overlay(page: ft.Page, est: _Estado) -> None:
    est.ativos = max(0, est.ativos - 1)
    if est.ativos > 0:
        return
    _forcar_ocultar(page, est)


def _forcar_ocultar(page: ft.Page, est: _Estado) -> None:
    est.ativos = 0
    if est.watchdog is not None:
        est.watchdog.cancel()
        est.watchdog = None
    ovl = est.overlay
    if ovl is None:
        return
    try:
        ovl.ignore_interactions = True
        ovl.opacity = 0
        ovl.update()
    except Exception:
        pass  # página pode ter sido fechada/reconstruída


# ── Feedback no próprio botão ─────────────────────────────────────────────────
def _bloquear_botao(ctrl: Any) -> bool:
    if not isinstance(ctrl, _TIPOS_BOTAO) or getattr(ctrl, "disabled", False):
        return False
    try:
        ctrl.disabled = True
        ctrl.opacity = _OPACIDADE_BTN
        return True
    except Exception:
        return False


def _liberar_botao(ctrl: Any) -> None:
    # Só desfaz se o handler não alterou o estado por conta própria.
    try:
        if getattr(ctrl, "disabled", False) and getattr(ctrl, "opacity", None) == _OPACIDADE_BTN:
            ctrl.disabled = False
            ctrl.opacity = 1.0
            ctrl.update()
    except Exception:
        pass  # controle removido da página pela navegação


async def _flush() -> None:
    """Cede o loop para o patch visual sair antes de um handler que bloqueia."""
    await asyncio.sleep(0)
    await asyncio.sleep(_FLUSH_S)


# ── Navegação (sincronizada com o roteador) ───────────────────────────────────
def nav_iniciada(page: ft.Page) -> None:
    est = _estado(page)
    est.nav_pendente = True
    est.nav_inicio = time.monotonic()
    est.nav_deadline = est.nav_inicio + _NAV_TIMEOUT_S


def nav_concluida(page: ft.Page) -> None:
    """Chamada pelo roteador ao fim do on_route_change (sucesso ou erro)."""
    est = _estado(page)
    agora = time.monotonic()
    if est.nav_pendente and agora - est.nav_inicio > _LIMITE_BLOQUEIO_S:
        est.descartar_ate = agora + _JANELA_DESCARTE_S
    est.nav_pendente = False


async def _aguardar_navegacao(est: _Estado) -> None:
    while est.nav_pendente and time.monotonic() < est.nav_deadline:
        await asyncio.sleep(0.03)
    est.nav_pendente = False


def _instalar_navigate() -> None:
    orig = ft.Page.navigate
    if getattr(orig, "_dembase_guard", False):
        return

    def navigate(self, route: str, **kwargs: Any) -> None:
        try:
            from core.router import normalizar_rota_completa

            if normalizar_rota_completa(route) != normalizar_rota_completa(self.route):
                nav_iniciada(self)
        except Exception:
            pass
        return orig(self, route, **kwargs)

    navigate._dembase_guard = True  # type: ignore[attr-defined]
    ft.Page.navigate = navigate  # type: ignore[method-assign]


# ── Choke point ───────────────────────────────────────────────────────────────
def _pagina_de(ctrl: Any) -> ft.Page | None:
    try:
        return ctrl.page
    except Exception:
        return None


async def _trigger_event_guardado(self, event_name, event_data, e=None):
    if event_name not in _EVENTOS_GUARDADOS:
        return await _orig_trigger(self, event_name, event_data, e)

    handler = getattr(self, f"on_{event_name}", None)
    page = _pagina_de(self)
    if handler is None or page is None:
        return await _orig_trigger(self, event_name, event_data, e)

    est = _estado(page)
    chave = getattr(self, "_i", None) or id(self)
    agora = time.monotonic()

    if chave in est.em_voo or agora < est.descartar_ate:
        _log(f"clique descartado em {type(self).__name__} (ação em andamento)")
        return None

    eh_async = (
        inspect.iscoroutinefunction(handler) or inspect.isasyncgenfunction(handler)
    )
    est.em_voo.add(chave)
    botao_bloqueado = False
    overlay_ativo = False
    timer_async: asyncio.TimerHandle | None = None
    t0 = time.perf_counter()
    _HttpStats.zerar()

    try:
        loop = asyncio.get_running_loop()

        # 1) Feedback visual ANTES de qualquer trabalho pesado.
        botao_bloqueado = _bloquear_botao(self)
        if botao_bloqueado:
            try:
                self.update()
            except Exception:
                pass

        if eh_async:
            # Loop livre: só mostra a rodinha se a ação demorar.
            def _mostrar_tardio() -> None:
                nonlocal overlay_ativo
                if chave in est.em_voo and not overlay_ativo:
                    overlay_ativo = True
                    _mostrar_overlay(page, est)

            timer_async = loop.call_later(_ATRASO_ASYNC_S, _mostrar_tardio)
        else:
            # Handler síncrono pode congelar o loop: rodinha + flush AGORA.
            overlay_ativo = True
            _mostrar_overlay(page, est)
            await _flush()

        # 2) Execução original (handler do app).
        t_exec = time.perf_counter()
        resultado = await _orig_trigger(self, event_name, event_data, e)
        dur_exec = time.perf_counter() - t_exec
        if not eh_async and dur_exec > _LIMITE_BLOQUEIO_S:
            est.descartar_ate = time.monotonic() + _JANELA_DESCARTE_S
        return resultado
    finally:
        if timer_async is not None:
            timer_async.cancel()
        try:
            # 3) A rodinha só some depois da navegação disparada terminar.
            if est.nav_pendente:
                await _aguardar_navegacao(est)
        finally:
            if overlay_ativo:
                _ocultar_overlay(page, est)
            if botao_bloqueado:
                _liberar_botao(self)
            est.em_voo.discard(chave)
            if _PERF:
                total = time.perf_counter() - t0
                if total > _PERF_LIMITE_S or _HttpStats.lentas:
                    lentas = ", ".join(f"{u} {d:.2f}s" for u, d in _HttpStats.lentas[:4])
                    _log(
                        f"{type(self).__name__}.on_{event_name} "
                        f"[{getattr(handler, '__qualname__', handler)}] "
                        f"{total:.2f}s | HTTP: {_HttpStats.n} req / {_HttpStats.total:.2f}s"
                        + (f" | lentas: {lentas}" if lentas else "")
                    )


def instalar(page: ft.Page | None = None) -> None:
    """Instala a proteção global (idempotente). Chamar uma vez no main()."""
    global _instalado
    if not _instalado:
        BaseControl._trigger_event = _trigger_event_guardado  # type: ignore[method-assign]
        _instalar_navigate()
        _instrumentar_http()
        _instalado = True
    if page is not None:
        _garantir_overlay(page, _estado(page))
