"""
=============================================================================
DemBase v3 — views/widgets/report/__init__.py  (Flet 1.0.1)
Componentes modulares para construção padronizada de relatórios.
=============================================================================
"""
from views.widgets.report.empty_state import criar_empty_state
from views.widgets.report.header import criar_report_header
from views.widgets.report.kpi_strip import criar_kpi_strip
from views.widgets.report.filter_bar import FilterBar, criar_filter_bar
from views.widgets.report.transaction_list import TransactionList, criar_transaction_list
from views.widgets.report.scaffold import (
    ReportScaffold,
    construir_card_ranking_categorias,
    construir_card_ranking_potes,
    construir_card_evolucao_diaria,
)

__all__ = [
    "criar_empty_state",
    "criar_report_header",
    "criar_kpi_strip",
    "FilterBar",
    "criar_filter_bar",
    "TransactionList",
    "criar_transaction_list",
    "ReportScaffold",
    "construir_card_ranking_categorias",
    "construir_card_ranking_potes",
    "construir_card_evolucao_diaria",
]
