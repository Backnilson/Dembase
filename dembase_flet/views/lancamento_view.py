"""
=============================================================================
DemBase v3 — views/lancamento_view.py (Flet 1.0.1)
Adaptador de rota para /lancamento:
Abre o formulário moderno (BottomSheet no mobile ou AlertDialog no desktop)
hospedado sobre a visualização do Dashboard.
=============================================================================
"""
from __future__ import annotations

import flet as ft

from core.constants import session_get, session_remove
from core.router import ROTA_DASHBOARD, navegar
from views.dashboard_view import criar_view_dashboard
from views.widgets.lancamento_sheet import abrir_lancamento


def criar_view_lancamento(page: ft.Page) -> ft.View:
    """
    Renderiza o Dashboard ao fundo e abre imediatamente o novo modal/sheet de lançamento.
    Garante compatibilidade total com navegações diretas à rota /lancamento.
    """
    lanc = session_get(page, "edit_lancamento_dados")
    session_remove(page, "edit_lancamento_dados")
    session_remove(page, "edit_lancamento_id")

    # Dispara a abertura do modal moderno
    abrir_lancamento(
        page,
        lancamento=lanc,
        on_saved=lambda: navegar(page, ROTA_DASHBOARD),
    )

    return criar_view_dashboard(page)
