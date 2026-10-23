"""
=============================================================================
DemBase v3 — test_cartao_e_ranking_categorias.py
Validação unitária e de integração da compatibilidade de assinaturas em
construir_card_ranking_categorias, nav.py e telas de extrato de Cartão e Conta.
=============================================================================
"""
import sys
import os
from unittest.mock import MagicMock, patch

# Garante o path de importação de dembase_flet
sys.path.insert(0, os.path.dirname(__file__))

import flet as ft
from core.report_context import ReportContext
from core.router import RouteMatch
from core.nav import (
    ir_relatorio_categoria,
    ir_cartao,
    ir_conta,
    ir_relatorio_fluxo,
    ir_relatorio_regra,
)
from views.widgets.report.scaffold import (
    construir_card_ranking_categorias,
    construir_card_ranking_potes,
    construir_card_evolucao_diaria,
)
from views.relatorios.cartao_report import criar_view_relatorio_cartao
from views.relatorios.conta_report import criar_view_relatorio_conta
from views.relatorios.fluxo_mensal_report import criar_view_fluxo_mensal
from views.relatorios.regra5030_report import criar_view_relatorio_regra


def mock_page():
    page = MagicMock(spec=ft.Page)
    page.width = 390
    page.height = 844
    page.client_storage = MagicMock()
    page.session = MagicMock()
    session_store = {}
    page.session.get.side_effect = lambda k: session_store.get(k)
    page.session.set.side_effect = lambda k, v: session_store.update({k: v})
    page.session.contains_key.side_effect = lambda k: k in session_store
    page.views = []
    page.route = "/cartoes/cart-123"
    page.navigate = MagicMock()
    page.update = MagicMock()
    return page


def test_construir_card_ranking_categorias_compatibilidade():
    print("--- Teste 1: Compatibilidade de Assinaturas em construir_card_ranking_categorias ---")

    cats = [
        {"categoria_id": "c1", "nome": "Alimentação", "total": 150.0, "percentual": 30.0, "qtd": 5, "cor": "#FF0000"},
        {"id": "c2", "nome": "Transporte", "total": 100.0, "percentual": 20.0, "qtd": 3, "cor": "#00FF00"},
    ]

    # Cenário A: Chamada com on_categoria_click com 2 argumentos (cid, dict)
    chamadas_2args = []
    card_a = construir_card_ranking_categorias(
        categorias=cats,
        titulo="Categorias no Cartão",
        on_categoria_click=lambda cid, c: chamadas_2args.append((cid, c)),
    )
    assert isinstance(card_a, ft.Container)
    # Aciona clique no primeiro item (Container -> Column -> Divider + linhas)
    col_content = card_a.content.controls
    item_0 = col_content[2] # Primeiro item de categoria
    assert item_0.on_click is not None
    item_0.on_click(None)
    assert len(chamadas_2args) == 1
    assert chamadas_2args[0][0] == "c1"
    assert chamadas_2args[0][1]["nome"] == "Alimentação"
    print("  [OK] Callback on_categoria_click(cid, cat) com 2 argumentos disparado com sucesso.")

    # Cenário B: Chamada com on_categoria_click com 1 argumento (cid)
    chamadas_1arg_cid = []
    card_b = construir_card_ranking_categorias(
        categorias=cats,
        on_categoria_click=lambda cid: chamadas_1arg_cid.append(cid),
    )
    item_b_0 = card_b.content.controls[2]
    item_b_0.on_click(None)
    assert chamadas_1arg_cid == ["c1"]
    print("  [OK] Callback on_categoria_click(cid) com 1 argumento (cid) disparado com sucesso.")

    # Cenário C: Chamada com on_click_categoria com 1 argumento (cat dict)
    chamadas_1arg_dict = []
    card_c = construir_card_ranking_categorias(
        categorias=cats,
        on_click_categoria=lambda cat: chamadas_1arg_dict.append(cat["nome"]),
    )
    item_c_1 = card_c.content.controls[3]
    item_c_1.on_click(None)
    assert chamadas_1arg_dict == ["Transporte"]
    print("  [OK] Callback on_click_categoria(cat) com 1 argumento (dict) disparado com sucesso.")


def test_construir_card_ranking_potes_e_evolucao_compatibilidade():
    print("--- Teste 2: Compatibilidade de Potes e Evolução Diária ---")

    potes = [
        {"pote_id": "p1", "nome": "Custos Fixos", "total": 500.0, "percentual": 50.0, "cor": "#3B82F6"},
    ]
    cliques_pote = []
    card_p = construir_card_ranking_potes(
        potes=potes,
        on_pote_click=lambda pid, p: cliques_pote.append((pid, p.get("nome"))),
    )
    assert isinstance(card_p, ft.Container)
    item_p_0 = card_p.content.controls[2]
    assert item_p_0.on_click is not None
    item_p_0.on_click(None)
    assert cliques_pote == [("p1", "Custos Fixos")]
    print("  [OK] Card de Ranking por Pote aceita on_pote_click com múltiplos argumentos.")

    dias = [
        {"data": "2026-10-23", "receitas": 100.0, "despesas": 50.0, "label": "23/10"},
    ]
    cliques_dia = []
    card_d = construir_card_evolucao_diaria(
        por_dia=dias,
        on_dia_click=lambda dt: cliques_dia.append(dt),
    )
    assert isinstance(card_d, ft.Container)
    # Acessa barras da evolução
    corpo_row = card_d.content.controls[2].content
    barra_0 = corpo_row.controls[0]
    assert barra_0.on_click is not None
    barra_0.on_click(None)
    assert cliques_dia == ["2026-10-23"]
    print("  [OK] Card de Evolução Diária aceita on_dia_click com sucesso.")


def test_nav_helpers_robustez():
    print("--- Teste 3: Robustez de Helpers de Navegação (core/nav.py) ---")
    page = mock_page()
    ctx = ReportContext.from_query(page)

    # 1. ir_relatorio_categoria passando ReportContext como 3º argumento posicional
    ir_relatorio_categoria(page, "cat-abc", ctx)
    nav_url = page.navigate.call_args[0][0]
    assert nav_url.startswith("/relatorios/categoria/cat-abc")
    assert "cat=" not in nav_url
    print("  [OK] ir_relatorio_categoria aceita ReportContext no 3º argumento posicional.")

    # 2. ir_cartao aceita replace=True e **filtros_extras
    ir_cartao(page, "cart-xyz", ctx=ctx, replace=True, origem="dashboard")
    url_cartao = page.navigate.call_args[0][0]
    assert url_cartao.startswith("/cartoes/cart-xyz")
    assert "origem=dashboard" in url_cartao
    assert "replace=" not in url_cartao
    print("  [OK] ir_cartao aceita replace=True sem erro de keyword argument.")

    # 3. ir_conta aceita replace=True
    ir_conta(page, "conta-1", ctx=ctx, replace=True)
    url_conta = page.navigate.call_args[0][0]
    assert url_conta.startswith("/contas/conta-1")
    assert "replace=" not in url_conta
    print("  [OK] ir_conta aceita replace=True com segurança.")

    # 4. ir_relatorio_fluxo aceita ReportContext e replace=True
    ir_relatorio_fluxo(page, ctx, replace=True)
    url_fluxo = page.navigate.call_args[0][0]
    assert url_fluxo.startswith("/relatorios/fluxo")
    print("  [OK] ir_relatorio_fluxo aceita ReportContext e replace=True.")


def test_telas_de_relatorio_sem_erro_de_extrato():
    print("--- Teste 4: Instanciação Real de Telas com Extrato e Categorias ---")
    page = mock_page()
    ctx = ReportContext.from_query(page)

    mock_pacote_cartao = {
        "cartao": {"id": "c1", "nome": "Nubank Ultravioleta", "cor": "#820AD1", "limite_total": 5000, "limite_disponivel": 3500},
        "kpis": {"total_gasto_periodo": 1500, "limite_total": 5000, "limite_disponivel": 3500, "total_parcelado": 1000, "total_a_vista": 500},
        "evolucao_diaria": [{"data": "2026-10-23", "receitas": 0, "despesas": 150, "label": "23/10"}],
        "por_categoria": [
            {"categoria_id": "cat-1", "nome": "Restaurante", "total": 350.0, "percentual": 40.0, "qtd": 2, "cor": "#FF5722"}
        ],
        "lancamentos": [],
        "total_registros": 0,
    }

    with patch("services.supabase_client.obter_relatorio_cartao", return_value=mock_pacote_cartao):
        view_cartao = criar_view_relatorio_cartao(
            page,
            RouteMatch(path="/cartoes/c1", params_path={"cartao_id": "c1"}),
            ctx,
        )
        assert isinstance(view_cartao, ft.View)
        # Varre a árvore de controles garantindo que NÃO há nenhum texto de erro
        def buscar_erros(ctrl):
            erros = []
            if isinstance(ctrl, ft.Text) and "Erro ao carregar extrato" in str(ctrl.value):
                erros.append(ctrl.value)
            if hasattr(ctrl, "controls") and ctrl.controls:
                for c in ctrl.controls:
                    erros.extend(buscar_erros(c))
            if hasattr(ctrl, "content") and ctrl.content:
                erros.extend(buscar_erros(ctrl.content))
            return erros

        erros_encontrados = buscar_erros(view_cartao)
        assert len(erros_encontrados) == 0, f"Erro encontrado na view de cartão: {erros_encontrados}"
        print("  [OK] Extrato de Cartão renderizou 100% livre de erros (0 'Erro ao carregar extrato').")

    mock_pacote_conta = {
        "conta": {"id": "cnt1", "nome": "Itaú Corrente", "cor": "#EC7000", "saldo_atual": 2500},
        "kpis": {"total_entradas": 3000, "total_saidas": 1500, "saldo_inicial": 1000, "saldo_final": 2500},
        "evolucao_diaria": [{"data": "2026-10-23", "saldo": 2500, "label": "23/10"}],
        "por_categoria": [
            {"categoria_id": "cat-2", "nome": "Supermercado", "total": 450.0, "percentual": 30.0, "qtd": 3, "cor": "#4CAF50"}
        ],
        "lancamentos": [],
        "total_registros": 0,
    }

    with patch("services.supabase_client.obter_relatorio_conta", return_value=mock_pacote_conta):
        view_conta = criar_view_relatorio_conta(
            page,
            RouteMatch(path="/contas/cnt1", params_path={"conta_id": "cnt1"}),
            ctx,
        )
        assert isinstance(view_conta, ft.View)
        erros_conta = buscar_erros(view_conta)
        assert len(erros_conta) == 0, f"Erro encontrado na view de conta: {erros_conta}"
        print("  [OK] Extrato de Conta renderizou 100% livre de erros.")


if __name__ == "__main__":
    test_construir_card_ranking_categorias_compatibilidade()
    test_construir_card_ranking_potes_e_evolucao_compatibilidade()
    test_nav_helpers_robustez()
    test_telas_de_relatorio_sem_erro_de_extrato()
    print("\n" + "=" * 60)
    print("TODOS OS TESTES DE CARTÃO E CATEGORIAS PASSARAM COM 100%!")
    print("=" * 60)
