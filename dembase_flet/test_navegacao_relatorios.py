"""
=============================================================================
DemBase v3 — test_navegacao_relatorios.py
Suite completa de testes automatizados para validação do Flet 1.0.1,
regras_dembase.md, rotas, navegação hierárquica e integridade dos relatórios.
=============================================================================
"""
import sys
import os
import ast
import traceback
from datetime import date
from unittest.mock import MagicMock, patch

# Garante path dembase_flet no sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import flet as ft
from core.periodo import obter_estado_periodo_atual, atualizar_datas_periodo_global
from core.report_context import ReportContext, normalizar_regra, regra_para_slug, normalizar_tipo_filtro
from core.router import (
    RouteMatch,
    separar_rota,
    normalizar_rota_completa,
    resolver_rota,
    montar_pilha,
    ROTAS_TABELA,
    ROTA_DASHBOARD,
    ROTA_CONTAS,
    ROTA_CONTA_DETALHE,
    ROTA_CARTOES,
    ROTA_CARTAO_DETALHE,
    ROTA_RELATORIOS,
    ROTA_RELATORIO_LANCAMENTOS,
    ROTA_RELATORIO_CATEGORIA,
    ROTA_RELATORIO_REGRA,
    ROTA_RELATORIO_FLUXO,
)
from core.nav import (
    montar_url,
    ir_dashboard,
    ir_contas,
    ir_conta,
    ir_cartoes,
    ir_cartao,
    ir_hub_relatorios,
    ir_relatorio_lancamentos,
    ir_relatorio_categoria,
    ir_relatorio_regra,
    ir_relatorio_fluxo,
)


def mock_page(width=1280, height=800):
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.route = "/dashboard"
    page.views = []
    page.session = {}
    page._session_store = {}

    def session_set(key, val):
        page._session_store[key] = val
    def session_get(key, default=None):
        return page._session_store.get(key, default)
    def session_contains(key):
        return key in page._session_store
    def session_clear():
        page._session_store.clear()

    page.client_storage = MagicMock()
    page.client_storage.get.side_effect = lambda k: page._session_store.get(k)
    page.client_storage.set.side_effect = lambda k, v: page._session_store.update({k: v})

    page.navigate = MagicMock(side_effect=lambda r: setattr(page, "route", r))
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    return page


def test_1_ast_and_syntax():
    print("\n--- TESTE 1: Varredura de Sintaxe AST e Conformidade Flet 1.0.1 ---")
    arquivos_verificados = 0
    proibidos = ["page.go(", "ft.app(", "ft.colors.", "ft.icons."]

    for root, _, files in os.walk(BASE_DIR):
        if ".git" in root or "__pycache__" in root or ".venv" in root:
            continue
        for f in files:
            if f.endswith(".py"):
                path_comp = os.path.join(root, f)
                with open(path_comp, "r", encoding="utf-8") as arq:
                    conteudo = arq.read()
                # 1. Verifica AST válida
                try:
                    ast.parse(conteudo, filename=f)
                except SyntaxError as e:
                    raise AssertionError(f"Erro de sintaxe Python em {f}: {e}")

                # 2. Verifica ausência de padrões proibidos (exceto no próprio script de teste)
                if f != "test_navegacao_relatorios.py":
                    for proibido in proibidos:
                        if proibido in conteudo:
                            raise AssertionError(f"Padrão legado proibido '{proibido}' encontrado em {f}!")

                arquivos_verificados += 1

    print(f"[OK] {arquivos_verificados} arquivos Python verificados com sucesso (100% livres de sintaxe legada).")


def test_2_report_context_and_period():
    print("\n--- TESTE 2: ReportContext e Gestão de Período ---")
    page = mock_page()

    # 1. Período padrão
    est = obter_estado_periodo_atual(page)
    assert "data_inicio" in est and "data_fim" in est
    assert est["data_fim"] >= est["data_inicio"]

    # 2. Atualização global
    d1 = "2026-10-01"
    d2 = "2026-10-31"
    est_up = atualizar_datas_periodo_global(page, d1, d2)
    assert est_up["data_inicio"] == date(2026, 10, 1)
    assert est_up["data_fim"] == date(2026, 10, 31)

    # 3. ReportContext.from_query flexível
    ctx = ReportContext.from_query(page)
    assert ctx.data_inicio == date(2026, 10, 1)
    assert ctx.data_fim == date(2026, 10, 31)

    # Com query
    query = {"tipo": "Despesa", "regra": "essencial", "forma": "Pix", "q": "Mercado"}
    ctx2 = ReportContext.from_query(query, page)
    assert ctx2.tipo == "Despesa"
    assert ctx2.regra == "Essencial"
    assert ctx2.regra_5030 == "Essencial"
    assert ctx2.forma == "Pix"
    assert ctx2.busca == "Mercado"
    assert ctx2.qtd_filtros_avancados() >= 3

    # Imutabilidade via .com(...)
    ctx3 = ctx2.com(tipo="Receita", regra_5030="Investimento")
    assert ctx3.tipo == "Receita"
    assert ctx3.regra == "Investimento"
    assert ctx2.tipo == "Despesa"  # original preservado

    # Roundtrip para query string
    q_dict = ctx3.to_query()
    assert q_dict["tipo"] == "Receita"
    assert q_dict["regra"] == "investimento"

    # Regras e slugs
    assert normalizar_regra("estilo-de-vida") == "Estilo de Vida"
    assert regra_para_slug("Estilo de Vida") == "estilo-de-vida"
    assert normalizar_tipo_filtro("transferencia") == "Transferência"

    print("[OK] ReportContext e Periodo testados com sucesso.")


def test_3_router_and_stack():
    print("\n--- TESTE 3: Roteador, Templates e Pilha Hierárquica ---")

    # 1. Separação de rota e query
    p, q = separar_rota("/relatorios/lancamentos?tipo=Despesa&ini=2026-10-01")
    assert p == "/relatorios/lancamentos"
    assert q["tipo"] == "Despesa"
    assert q["ini"] == "2026-10-01"

    # 2. Resolução de rota
    defn, match = resolver_rota("/contas/c123")
    assert defn is not None
    assert defn.template == ROTA_CONTA_DETALHE
    assert match.params_path["conta_id"] == "c123"
    assert match.get("conta_id") == "c123"

    defn_cat, match_cat = resolver_rota("/relatorios/categoria/cat456")
    assert defn_cat is not None
    assert match_cat.get("categoria_id") == "cat456"

    defn_regra, match_regra = resolver_rota("/relatorios/regra/essencial")
    assert defn_regra is not None
    assert match_regra.get("regra") == "essencial"

    # 3. Montagem da pilha hierárquica
    # Dashboard
    pilha_dash = montar_pilha("/dashboard", logado=True)
    assert pilha_dash == ["/dashboard"]

    # Contas
    pilha_contas = montar_pilha("/contas", logado=True)
    assert pilha_contas == ["/dashboard", "/contas"]

    # Drill-down Conta específica -> ['/dashboard', '/contas?ini=...&fim=...', '/contas/c123?ini=...&fim=...']
    pilha_conta_det = montar_pilha("/contas/c123?ini=2026-10-01&fim=2026-10-31", logado=True)
    assert len(pilha_conta_det) == 3
    assert pilha_conta_det[0] == "/dashboard"
    assert pilha_conta_det[1].startswith("/contas?")
    assert "ini=2026-10-01" in pilha_conta_det[1]
    assert pilha_conta_det[2].startswith("/contas/c123?")

    # Relatório de lançamentos vindo do Dashboard -> ['/dashboard', '/relatorios/lancamentos?origem=dashboard']
    pilha_lanc_dash = montar_pilha("/relatorios/lancamentos?origem=dashboard&tipo=Receita", logado=True)
    assert len(pilha_lanc_dash) == 2
    assert pilha_lanc_dash[0] == "/dashboard"
    assert "/relatorios/lancamentos" in pilha_lanc_dash[1]

    # Relatório de categoria vindo da Central de Relatórios -> ['/dashboard', '/relatorios', '/relatorios/categoria/cat1?origem=relatorios']
    pilha_cat_rel = montar_pilha("/relatorios/categoria/cat1?origem=relatorios", logado=True)
    assert len(pilha_cat_rel) == 3
    assert pilha_cat_rel[0] == "/dashboard"
    assert pilha_cat_rel[1] == "/relatorios"
    assert "/relatorios/categoria/cat1" in pilha_cat_rel[2]

    # Cartão detalhe -> ['/dashboard', '/cartoes', '/cartoes/cart1']
    pilha_cart = montar_pilha("/cartoes/cart1", logado=True)
    assert len(pilha_cart) == 3
    assert pilha_cart[0] == "/dashboard"
    assert pilha_cart[1] == "/cartoes"
    assert pilha_cart[2] == "/cartoes/cart1"

    print("[OK] Roteador, templates e pilhas hierárquicas testados com sucesso.")


def test_4_nav_helpers():
    print("\n--- TESTE 4: Helpers Tipados de Navegação (core.nav) ---")
    page = mock_page()

    ir_dashboard(page)
    assert page.navigate.call_args[0][0] == "/dashboard"

    ir_contas(page)
    assert "/contas?" in page.navigate.call_args[0][0]

    ir_conta(page, "uuid-conta-1")
    assert "/contas/uuid-conta-1?" in page.navigate.call_args[0][0]

    ir_cartoes(page)
    assert page.navigate.call_args[0][0] == "/cartoes"

    ir_cartao(page, "uuid-cart-1")
    assert "/cartoes/uuid-cart-1?" in page.navigate.call_args[0][0]

    ir_hub_relatorios(page)
    assert "/relatorios?" in page.navigate.call_args[0][0]

    ir_relatorio_lancamentos(page, tipo="Despesa", origem="dashboard")
    call_lanc = page.navigate.call_args[0][0]
    assert "/relatorios/lancamentos?" in call_lanc
    assert "tipo=Despesa" in call_lanc
    assert "origem=dashboard" in call_lanc

    ir_relatorio_categoria(page, "cat-99", tipo="Despesa", origem="dashboard")
    call_cat = page.navigate.call_args[0][0]
    assert "/relatorios/categoria/cat-99?" in call_cat

    ir_relatorio_regra(page, "Estilo de Vida")
    call_regra = page.navigate.call_args[0][0]
    assert "/relatorios/regra/estilo-de-vida?" in call_regra

    ir_relatorio_fluxo(page)
    call_fluxo = page.navigate.call_args[0][0]
    assert "/relatorios/fluxo?" in call_fluxo

    print("[OK] Helpers de navegação verificados com sucesso.")


@patch("services.supabase_client.sessao_atual", return_value=MagicMock(user=MagicMock(id="user-123")))
@patch("services.supabase_client.ler_perfil", return_value={"nome": "Denilson Silva"})
@patch("services.supabase_client.obter_dashboard_periodo")
@patch("services.supabase_client.obter_resumo_5030")
@patch("services.supabase_client.obter_balanco_6_meses")
@patch("services.supabase_client.obter_resumo_cartoes")
@patch("services.supabase_client.obter_lista_contas_resumo")
@patch("services.supabase_client.listar_contas")
@patch("services.supabase_client.listar_cartoes")
@patch("services.supabase_client.listar_categorias")
@patch("services.supabase_client.obter_relatorio_lancamentos")
@patch("services.supabase_client.obter_relatorio_conta")
@patch("services.supabase_client.obter_relatorio_cartao")
def test_5_view_rendering_and_responsiveness(
    mock_rel_cartao,
    mock_rel_conta,
    mock_rel_lanc,
    mock_list_cat,
    mock_list_cart,
    mock_list_cont,
    mock_res_cont,
    mock_res_cart,
    mock_bal_6m,
    mock_res_5030,
    mock_dash_per,
    mock_ler_perfil,
    mock_sessao,
):
    print("\n--- TESTE 5: Renderização Real de Todas as Telas e Relatórios (Mobile 390px e Desktop 1280px) ---")

    # Mocks de dados
    mock_dash_per.return_value = {
        "overview": {"receitas": 5000.0, "despesas": 3000.0, "saldo_contas": 12000.0, "total_faturas": 1500.0},
        "despesas_por_categoria": {"total": 3000.0, "categorias": [{"categoria_id": "c1", "categoria": "Alimentação", "total": 1200.0, "cor": "#EF4444", "percentual": 40.0}]},
        "receitas_por_categoria": {"total": 5000.0, "categorias": [{"categoria_id": "c2", "categoria": "Salário", "total": 5000.0, "cor": "#10B981", "percentual": 100.0}]},
        "frequencia_diaria": [{"data": "2026-10-15", "dia": 15, "receitas": 5000.0, "despesas": 300.0}],
        "despesas_por_forma": [{"forma": "Pix", "valor": 2000.0, "qtd": 10, "percentual": 66.7}],
    }
    mock_res_5030.return_value = {
        "receita_total": 5000.0,
        "essencial": {"gasto": 2000.0, "orcamento": 2500.0, "percentual_usado": 40.0},
        "estilo_vida": {"gasto": 800.0, "orcamento": 1500.0, "percentual_usado": 16.0},
        "investimento": {"gasto": 200.0, "orcamento": 1000.0, "percentual_usado": 4.0},
    }
    mock_bal_6m.return_value = [
        {"mes": 5, "ano": 2026, "label": "05/2026", "receitas": 4500.0, "despesas": 3200.0, "saldo": 1300.0},
        {"mes": 10, "ano": 2026, "label": "10/2026", "receitas": 5000.0, "despesas": 3000.0, "saldo": 2000.0},
    ]
    mock_res_cart.return_value = {"total_limite": 10000.0, "total_disponivel": 8500.0, "total_faturas": 1500.0}
    mock_res_cont.return_value = {
        "contas": [
            {"id": "c1", "nome": "Nubank", "cor": "#820AD1", "tipo_conta": "corrente", "saldo_atual": 5000.0, "saldo_previsto": 5200.0, "entradas_periodo": 5000.0, "saidas_periodo": 1000.0, "qtd_movimentos": 12}
        ],
        "saldo_total_atual": 5000.0,
        "saldo_total_previsto": 5200.0,
    }
    mock_list_cont.return_value = mock_res_cont.return_value["contas"]
    mock_list_cart.return_value = [
        {"id": "cart1", "nome": "Nubank Roxinho", "cor": "#820AD1", "bandeira": "mastercard", "limite_total": 5000.0, "limite_disponivel": 3500.0, "dia_fechamento": 5, "dia_vencimento": 12}
    ]
    mock_list_cat.return_value = [
        {"id": "cat1", "nome": "Alimentação", "cor": "#EF4444", "tipo": "Despesa", "regra_5030": "Essencial"}
    ]
    mock_rel_lanc.return_value = {
        "kpis": {"total_receitas": 5000.0, "total_despesas": 3000.0, "saldo_periodo": 2000.0, "total_registros": 1},
        "evolucao_diaria": [{"data": "2026-10-15", "dia": 15, "receitas": 5000.0, "despesas": 300.0, "saldo_diario": 4700.0}],
        "por_categoria": [{"categoria": "Alimentação", "valor": 1200.0, "cor": "#EF4444", "percentual": 40.0}],
        "itens": [
            {
                "id": "lanc-1",
                "data": "2026-10-15",
                "tipo": "Despesa",
                "descricao": "Supermercado Semanal",
                "valor": 350.50,
                "status": "Pago",
                "categoria_nome": "Alimentação",
                "categoria_cor": "#EF4444",
                "forma_movimentacao": "Pix",
                "conta_nome": "Nubank",
                "regra_5030": "Essencial",
            }
        ],
        "total_registros": 1,
    }
    mock_rel_conta.return_value = {
        "conta": {"id": "c1", "nome": "Nubank", "cor": "#820AD1", "tipo_conta": "corrente", "saldo_atual": 5000.0},
        "kpis": {"saldo_inicial_periodo": 1000.0, "entradas": 5000.0, "saidas": 1000.0, "saldo_final_periodo": 5000.0, "transferencias_recebidas": 0.0, "transferencias_enviadas": 0.0},
        "evolucao_saldo": [{"data": "2026-10-15", "dia": 15, "saldo_acumulado": 5000.0, "entradas": 5000.0, "saidas": 1000.0}],
        "por_categoria": [{"categoria": "Alimentação", "valor": 1000.0, "cor": "#EF4444", "percentual": 100.0}],
        "lancamentos": mock_rel_lanc.return_value["itens"],
        "total_registros": 1,
    }
    mock_rel_cartao.return_value = {
        "cartao": {"id": "cart1", "nome": "Nubank Roxinho", "cor": "#820AD1", "bandeira": "mastercard", "limite_total": 5000.0, "limite_disponivel": 3500.0, "dia_fechamento": 5, "dia_vencimento": 12},
        "kpis": {"total_gasto_periodo": 1500.0, "limite_total": 5000.0, "limite_disponivel": 3500.0, "total_a_vista": 500.0, "total_parcelado": 1000.0},
        "evolucao_diaria": [{"data": "2026-10-15", "dia": 15, "despesas": 1500.0}],
        "por_categoria": [{"categoria": "Alimentação", "valor": 500.0, "cor": "#EF4444", "percentual": 33.3}],
        "lancamentos": mock_rel_lanc.return_value["itens"],
        "total_registros": 1,
    }

    from views.dashboard_view import criar_view_dashboard
    from views.contas_view import criar_view_contas
    from views.cartoes_view import criar_view_cartoes
    from views.relatorios.hub_view import criar_view_hub_relatorios
    from views.relatorios.lancamentos_report import criar_view_relatorio_lancamentos
    from views.relatorios.conta_report import criar_view_relatorio_conta
    from views.relatorios.cartao_report import criar_view_relatorio_cartao
    from views.relatorios.categoria_report import criar_view_relatorio_categoria
    from views.relatorios.regra5030_report import criar_view_relatorio_regra
    from views.relatorios.fluxo_mensal_report import criar_view_fluxo_mensal

    resolucoes = [
        ("Mobile (iPhone/Android 390x844)", 390, 844),
        ("Desktop (1280x800)", 1280, 800),
    ]

    for label_res, w, h in resolucoes:
        page = mock_page(width=w, height=h)
        match_padrao = RouteMatch(path="/", template="/")
        ctx_padrao = ReportContext.from_query(page)

        # 1. Dashboard
        v_dash = criar_view_dashboard(page)
        assert isinstance(v_dash, ft.View)
        assert len(v_dash.controls) > 0

        # 2. Contas (com drill-down)
        v_contas = criar_view_contas(page, match_padrao)
        assert isinstance(v_contas, ft.View)

        # 3. Conta Detalhe
        v_conta_det = criar_view_relatorio_conta(page, RouteMatch(path="/contas/c1", params_path={"conta_id": "c1"}), ctx_padrao)
        assert isinstance(v_conta_det, ft.View)

        # 4. Cartões (com drill-down)
        v_cartoes = criar_view_cartoes(page, match_padrao)
        assert isinstance(v_cartoes, ft.View)

        # 5. Cartão Detalhe
        v_cartao_det = criar_view_relatorio_cartao(page, RouteMatch(path="/cartoes/cart1", params_path={"cartao_id": "cart1"}), ctx_padrao)
        assert isinstance(v_cartao_det, ft.View)

        # 6. Hub de Relatórios
        v_hub = criar_view_hub_relatorios(page, match_padrao, ctx_padrao)
        assert isinstance(v_hub, ft.View)

        # 7. Relatório Geral de Lançamentos
        v_lanc = criar_view_relatorio_lancamentos(page, match_padrao, ctx_padrao)
        assert isinstance(v_lanc, ft.View)

        # 8. Relatório por Categoria
        v_cat = criar_view_relatorio_categoria(page, RouteMatch(path="/relatorios/categoria/cat1", params_path={"categoria_id": "cat1"}), ctx_padrao)
        assert isinstance(v_cat, ft.View)

        # 9. Relatório Regra 50/30/20
        v_regra = criar_view_relatorio_regra(page, RouteMatch(path="/relatorios/regra/essencial", params_path={"regra": "essencial"}), ctx_padrao)
        assert isinstance(v_regra, ft.View)

        # 10. Fluxo Mensal
        v_fluxo = criar_view_fluxo_mensal(page, match_padrao, ctx_padrao)
        assert isinstance(v_fluxo, ft.View)

        # 11. Categorias, Calendário, Config, Auth, Lançamento
        from views.categorias_view import criar_view_categorias
        from views.calendario_view import criar_view_calendario
        from views.config_view import criar_view_config
        from views.auth_view import criar_view_auth
        from views.lancamento_view import criar_view_lancamento
        from views.widgets.lancamento_sheet import abrir_lancamento

        v_categ = criar_view_categorias(page)
        assert isinstance(v_categ, ft.View)

        v_cal = criar_view_calendario(page)
        assert isinstance(v_cal, ft.View)

        v_cfg = criar_view_config(page)
        assert isinstance(v_cfg, ft.View)

        v_auth = criar_view_auth(page)
        assert isinstance(v_auth, ft.View)

        v_lanca = criar_view_lancamento(page)
        assert isinstance(v_lanca, ft.View)

        # Teste de abertura contextual do modal de lançamentos
        abrir_lancamento(
            page,
            conta_inicial="c1",
            cartao_inicial="cart1",
            categoria_inicial="cat1",
            regra_inicial="Essencial",
        )
        assert page.show_dialog.called

        print(f"[OK] Todas as 15 views e modais contextuais instanciados com sucesso em {label_res}.")


def main():
    print("=" * 78)
    print("DEMBASE v3 — EXECUÇÃO DA SUITE DE TESTES AUTOMATIZADOS (FLET 1.0.1)")
    print("=" * 78)
    try:
        test_1_ast_and_syntax()
        test_2_report_context_and_period()
        test_3_router_and_stack()
        test_4_nav_helpers()
        test_5_view_rendering_and_responsiveness()
        print("\n" + "=" * 78)
        print("TODOS OS TESTES FORAM CONCLUÍDOS COM 100% DE SUCESSO!")
        print("=" * 78)
    except Exception as e:
        print("\n" + "!" * 78)
        print(f"FALHA NO TESTE: {e}")
        print("!" * 78)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
