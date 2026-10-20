"""
=============================================================================
DemBase v3 — views/relatorios/__init__.py  (Flet 1.0.1)
Pacote Modular de Relatórios Analíticos e Drill-down.
=============================================================================
"""
from views.relatorios.registry import RELATORIOS_CATALOGO, obter_meta_relatorio
from views.relatorios.hub_view import criar_view_hub_relatorios
from views.relatorios.lancamentos_report import criar_view_relatorio_lancamentos
from views.relatorios.conta_report import criar_view_relatorio_conta
from views.relatorios.cartao_report import criar_view_relatorio_cartao
from views.relatorios.categoria_report import criar_view_relatorio_categoria
from views.relatorios.regra5030_report import criar_view_relatorio_regra
from views.relatorios.fluxo_mensal_report import criar_view_fluxo_mensal, criar_view_relatorio_fluxo

__all__ = [
    "RELATORIOS_CATALOGO",
    "obter_meta_relatorio",
    "criar_view_hub_relatorios",
    "criar_view_relatorio_lancamentos",
    "criar_view_relatorio_conta",
    "criar_view_relatorio_cartao",
    "criar_view_relatorio_categoria",
    "criar_view_relatorio_regra",
    "criar_view_fluxo_mensal",
    "criar_view_relatorio_fluxo",
]
