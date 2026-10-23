"""
=============================================================================
DemBase v3 — views/relatorios/registry.py  (Flet 1.0.1)
Catálogo declarativo e plug-and-play de relatórios (RELATORIOS_CATALOGO / REPORTS).
Adicionar um novo relatório exige apenas registrá-lo aqui.
=============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
import flet as ft


@dataclass
class RelatorioDef:
    id: str
    titulo: str
    descricao: str
    icone: ft.IconData
    cor: str
    rota_template: str
    pai: str = "/relatorios"
    builder: Callable | None = None
    no_hub: bool = True
    rota_hub: str | None = None
    col: dict | None = None


# Catálogo estruturado em dicionários para consumo dinâmico no Hub
RELATORIOS_CATALOGO: list[dict] = [
    {
        "id": "lancamentos_gerais",
        "titulo": "Extrato Geral de Lançamentos",
        "subtitulo": "Consolidado de movimentações com filtros combinados e busca em tempo real",
        "icone": ft.Icons.RECEIPT_LONG_ROUNDED,
        "cor": "#3B82F6",
        "col": {"xs": 12, "sm": 6, "md": 4},
        "rota_template": "/relatorios/lancamentos",
    },
    {
        "id": "receitas_periodo",
        "titulo": "Entradas & Receitas",
        "subtitulo": "Composição e evolução diária das entradas no período filtrado",
        "icone": ft.Icons.ARROW_UPWARD_ROUNDED,
        "cor": "#10B981",
        "col": {"xs": 12, "sm": 6, "md": 4},
        "rota_template": "/relatorios/lancamentos?tipo=Receita",
    },
    {
        "id": "despesas_periodo",
        "titulo": "Saídas & Despesas",
        "subtitulo": "Análise das saídas por categoria, modalidade e ritmo de gastos",
        "icone": ft.Icons.ARROW_DOWNWARD_ROUNDED,
        "cor": "#EF4444",
        "col": {"xs": 12, "sm": 6, "md": 4},
        "rota_template": "/relatorios/lancamentos?tipo=Despesa",
    },
    {
        "id": "extrato_contas",
        "titulo": "Extrato por Conta Bancária",
        "subtitulo": "Saldo inicial, transferências, entradas e saídas por conta individual",
        "icone": ft.Icons.ACCOUNT_BALANCE_ROUNDED,
        "cor": "#06B6D4",
        "col": {"xs": 12, "sm": 6, "md": 4},
        "rota_template": "/contas",
    },
    {
        "id": "faturas_cartoes",
        "titulo": "Faturas & Cartões de Crédito",
        "subtitulo": "Uso de limites, compras parceladas vs à vista e faturas por cartão",
        "icone": ft.Icons.CREDIT_CARD_ROUNDED,
        "cor": "#F59E0B",
        "col": {"xs": 12, "sm": 6, "md": 4},
        "rota_template": "/cartoes",
    },
    {
        "id": "potes_financeiros",
        "titulo": "6 Potes Financeiros",
        "subtitulo": "Gasto vs Previsto nos 6 potes: Custos Fixos, Conforto, Metas, Prazeres, Conhecimento e Liberdade",
        "icone": ft.Icons.ALL_INBOX_ROUNDED,
        "cor": "#6C5CE7",
        "col": {"xs": 12, "sm": 6, "md": 4},
        "rota_template": "/relatorios/lancamentos?tipo=Despesa",
    },
    {
        "id": "fluxo_mensal",
        "titulo": "Fluxo de Caixa Mensal (6 Meses)",
        "subtitulo": "Comparativo histórico de Receitas, Despesas e Saldo mês a mês",
        "icone": ft.Icons.STACKED_BAR_CHART_ROUNDED,
        "cor": "#8B5CF6",
        "col": {"xs": 12, "sm": 6, "md": 4},
        "rota_template": "/relatorios/fluxo",
    },
]

REPORTS: dict[str, RelatorioDef] = {
    item["id"]: RelatorioDef(
        id=item["id"],
        titulo=item["titulo"],
        descricao=item["subtitulo"],
        icone=item["icone"],
        cor=item["cor"],
        rota_template=item["rota_template"],
        col=item.get("col"),
    )
    for item in RELATORIOS_CATALOGO
}


def registrar_relatorio(defn: RelatorioDef) -> RelatorioDef:
    REPORTS[defn.id] = defn
    return defn


def obter_meta_relatorio(relatorio_id: str) -> dict | None:
    for item in RELATORIOS_CATALOGO:
        if item["id"] == relatorio_id:
            return item
    defn = REPORTS.get(relatorio_id)
    if defn:
        return {
            "id": defn.id,
            "titulo": defn.titulo,
            "subtitulo": defn.descricao,
            "icone": defn.icone,
            "cor": defn.cor,
            "rota_template": defn.rota_template,
            "col": defn.col,
        }
    return None
