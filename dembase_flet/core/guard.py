"""
=============================================================================
DemBase v3 — core/guard.py  (Flet 1.0.1)
Proteções de interface:
  1. proteger_clique(): trava anti-duplo clique (debounce) com feedback visual
     imediato (disabled + opacidade reduzida) até o handler terminar.
  2. view_erro_retry(): view de fallback com mensagem e botão "Tentar novamente"
     para evitar telas em branco quando a construção/consulta falha.
=============================================================================
"""
from __future__ import annotations

import asyncio
import inspect
import threading
import time
from functools import wraps
from typing import Callable

import flet as ft

from core import theme as T

# Tempo mínimo (s) de bloqueio: cobre navegação que retorna antes do rebuild da view.
_HOLD_MIN_S = 0.6
_OPACIDADE_BLOQUEADO = 0.55


def _bloquear(ctrl) -> tuple:
    """Aplica estado de carregamento visual e devolve o estado anterior."""
    anterior = (getattr(ctrl, "disabled", False), getattr(ctrl, "opacity", 1.0))
    try:
        ctrl.disabled = True
        ctrl.opacity = _OPACIDADE_BLOQUEADO
        ctrl.update()
    except Exception:
        pass
    return anterior


def _liberar(ctrl, anterior: tuple) -> None:
    try:
        ctrl.disabled, ctrl.opacity = anterior
        ctrl.update()
    except Exception:
        # Controle pode ter sido removido da página pela navegação — ignora.
        pass


def proteger_clique(handler: Callable, hold: float = _HOLD_MIN_S) -> Callable:
    """
    Envolve um on_click (sync ou async). No primeiro clique bloqueia o controle
    (disabled + opacidade) e descarta cliques subsequentes até o fim da operação.
    """
    if handler is None:
        return handler
    if getattr(handler, "_dembase_protegido", False):
        return handler

    em_execucao = threading.Lock()

    def _entrar(e) -> tuple | None:
        if not em_execucao.acquire(blocking=False):
            return None
        return _bloquear(getattr(e, "control", None)) if getattr(e, "control", None) is not None else ((False, 1.0),)

    if inspect.iscoroutinefunction(handler):
        @wraps(handler)
        async def _wrapper(e=None, *a, **kw):
            estado = _entrar(e)
            if estado is None:
                return None
            t0 = time.monotonic()
            try:
                return await handler(e, *a, **kw)
            finally:
                restante = hold - (time.monotonic() - t0)
                if restante > 0:
                    await asyncio.sleep(restante)
                if getattr(e, "control", None) is not None and len(estado) == 2:
                    _liberar(e.control, estado)
                em_execucao.release()
    else:
        @wraps(handler)
        def _wrapper(e=None, *a, **kw):
            estado = _entrar(e)
            if estado is None:
                return None
            t0 = time.monotonic()
            try:
                return handler(e, *a, **kw)
            finally:
                restante = hold - (time.monotonic() - t0)
                if restante > 0:
                    time.sleep(restante)
                if getattr(e, "control", None) is not None and len(estado) == 2:
                    _liberar(e.control, estado)
                em_execucao.release()

    _wrapper._dembase_protegido = True
    return _wrapper


def view_erro_retry(
    rota: str,
    mensagem: str,
    on_retry: Callable,
) -> ft.View:
    """View de fallback: mensagem de erro + botão 'Tentar novamente' (nunca tela vazia)."""
    return ft.View(
        route=rota,
        bgcolor=T.BG,
        padding=24,
        controls=[
            ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=14,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CLOUD_OFF_ROUNDED, color=T.DESPESA, size=44),
                        ft.Text(
                            "Não foi possível carregar esta tela",
                            color=T.TEXT_PRIMARY, size=17, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                        ft.Text(
                            mensagem, color=T.TEXT_MUTED, size=12,
                            text_align=ft.TextAlign.CENTER, max_lines=4,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.FilledButton(
                            content=ft.Text("Tentar novamente", color=T.ON_NEON, weight=ft.FontWeight.BOLD),
                            icon=ft.Icons.REFRESH_ROUNDED,
                            style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                            on_click=proteger_clique(on_retry),
                        ),
                    ],
                ),
            )
        ],
    )
