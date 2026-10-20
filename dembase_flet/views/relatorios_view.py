"""
=============================================================================
DemBase v3 — views/relatorios_view.py  (Flet 1.0.1)
Shim de compatibilidade que delega a Central de Relatórios (/relatorios)
para views/relatorios/hub_view.py e os relatórios modulares em views/relatorios/.
=============================================================================
"""
from __future__ import annotations
import flet as ft
from core.report_context import ReportContext
from views.relatorios.hub_view import criar_view_hub_relatorios


def criar_view_relatorios(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    """Delega para a Central de Relatórios modular."""
    return criar_view_hub_relatorios(page, match, ctx)
