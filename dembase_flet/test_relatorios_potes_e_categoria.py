"""
=============================================================================
DemBase v3 — test_relatorios_potes_e_categoria.py  (Flet 1.0.1)
Teste de validação para as 3 correções:
1. Bug no Filtro por Pote Financeiro (Toggle & highlight)
2. Tela Branca no Filtro de Categoria (Montagem limpa e carregamento sem exceção)
3. Edição Rápida de Pote no TransactionList (Abertura de modal e update)
=============================================================================
"""
from unittest.mock import MagicMock, patch
import flet as ft

from core.router import RouteMatch
from core.report_context import ReportContext
from views.relatorios.lancamentos_report import criar_view_relatorio_lancamentos
from views.relatorios.categoria_report import criar_view_relatorio_categoria
from views.widgets.report.transaction_list import TransactionList
from views.widgets.report.scaffold import construir_card_ranking_potes
import services.supabase_client as db


def mock_page(width=1280, height=800):
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.route = "/dashboard"
    page.views = []
    page.session = {}
    page._session_store = {}

    page.client_storage = MagicMock()
    page.client_storage.get.side_effect = lambda k: page._session_store.get(k)
    page.client_storage.set.side_effect = lambda k, v: page._session_store.update({k: v})

    page.navigate = MagicMock(side_effect=lambda r: setattr(page, "route", r))
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    return page


def test_filtro_pote_toggle_e_highlight():
    print("--- Teste 1: Card de Potes com Highlight e Toggle ---")
    potes = [
        {"id": "pote-1", "nome": "Custos Fixos", "cor": "#007AFF", "total": 100.0, "percentual": 50.0, "qtd": 5},
        {"id": "pote-2", "nome": "Conforto", "cor": "#FF69B4", "total": 50.0, "percentual": 25.0, "qtd": 2},
    ]

    clique_capturado = []
    card = construir_card_ranking_potes(
        potes=potes,
        pote_selecionado_id="pote-1",
        on_click_pote=lambda p: clique_capturado.append(p),
    )
    assert card is not None
    # Verifica que o pote selecionado foi renderizado com tooltip de remover filtro
    col = card.content
    linhas = col.controls[2:]
    item_pote1 = linhas[0]
    assert "remover o filtro" in (item_pote1.tooltip or "")
    # Simula clique no pote selecionado
    item_pote1.on_click(MagicMock())
    assert len(clique_capturado) == 1
    assert clique_capturado[0]["id"] == "pote-1"
    print("[OK] Card de Ranking por Pote suporta highlight e evento de clique perfeitamente.")


def test_categoria_report_sem_tela_branca():
    print("--- Teste 2: Diagnóstico por Categoria (Sem tela branca) ---")
    page = mock_page()

    mock_pacote = {
        "totais": {
            "total_filtrado": 1500.0,
            "pago": 1200.0,
            "pendente": 300.0,
            "media_diaria": 50.0,
        },
        "por_subcategoria": [
            {"subcategoria_id": "sub-1", "nome": "Combustível", "total": 500.0, "percentual": 33.3, "qtd": 4}
        ],
        "por_pote": [
            {"pote_id": "pote-1", "nome": "Custos Fixos", "cor": "#007AFF", "total": 1500.0, "percentual": 100.0, "qtd": 10}
        ],
        "por_dia": [
            {"data": "2026-10-01", "total": 200.0, "receitas": 0.0, "despesas": 200.0}
        ],
        "lancamentos": [
            {
                "id": "tx-1",
                "tipo": "Despesa",
                "valor": 150.0,
                "data": "2026-10-01",
                "descricao": "Gasolina",
                "categoria_id": "cat-automoveis",
                "categoria_nome": "Automóveis",
                "pote_id": "pote-1",
                "pote_nome": "Custos Fixos",
                "pote_cor": "#007AFF",
                "status": "Pago",
            }
        ],
        "total_registros": 1,
    }

    with patch("services.supabase_client.obter_relatorio_lancamentos", return_value=mock_pacote) as mock_rpc, \
         patch("services.supabase_client.listar_categorias", return_value=[{"id": "cat-automoveis", "nome": "Automóveis", "cor": "#FF5722"}]):
        match = RouteMatch(
            path="/relatorios/categoria/cat-automoveis",
            params_path={"categoria_id": "cat-automoveis"},
            rota_completa="/relatorios/categoria/cat-automoveis",
        )
        ctx = ReportContext(
            data_inicio=ReportContext.from_query(page).data_inicio,
            data_fim=ReportContext.from_query(page).data_fim,
            categoria_id="cat-automoveis",
        )
        view = criar_view_relatorio_categoria(page, match=match, ctx=ctx)

        assert isinstance(view, ft.View)
        assert mock_rpc.called
        # Verifica que obter_relatorio_lancamentos foi chamado sem argumentos inválidos
        args, kwargs = mock_rpc.call_args
        assert "incluir_transferencias" not in kwargs

        # Valida que a view e seus controles foram instanciados (eliminação completa da tela branca)
        assert len(view.controls) > 0
        shell_root = view.controls[0]
        assert shell_root is not None
        print("[OK] Categoria Report instanciado e populado com sucesso, 0 tela branca.")


def test_edicao_rapida_pote():
    print("--- Teste 3: Edição Rápida de Pote Financeiro no TransactionList ---")
    page = mock_page()
    on_refresh = MagicMock()
    tl = TransactionList(page=page, on_refresh=on_refresh)

    item_despesa = {
        "id": "tx-99",
        "tipo": "Despesa",
        "valor": 80.0,
        "descricao": "Almoço",
        "categoria_nome": "Alimentação",
        "pote_id": None,
        "pote_nome": None,
        "status": "Pago",
    }

    # Renderiza item sem pote
    tl.renderizar([item_despesa], 1)
    # Abre o seletor rápido
    with patch("services.supabase_client.listar_potes", return_value=[
        {"id": "pote-1", "nome": "Custos Fixos", "cor": "#007AFF", "percentual": 35},
        {"id": "pote-2", "nome": "Prazeres", "cor": "#FF7A00", "percentual": 10},
    ]):
        tl._abrir_seletor_pote(item_despesa)
        assert page.show_dialog.called
        dialog = page.show_dialog.call_args[0][0]
        assert isinstance(dialog, ft.AlertDialog)

        # Simula seleção do pote "Custos Fixos"
        col_content = dialog.content.content
        linhas_potes = col_content.controls[2:]
        assert len(linhas_potes) == 2

        with patch("services.supabase_client.atualizar_lancamento") as mock_update:
            linhas_potes[0].on_click(MagicMock())
            assert mock_update.called
            mock_update.assert_called_with("tx-99", {"pote_id": "pote-1"})
            assert on_refresh.called
            assert page.pop_dialog.called

    print("[OK] Edição rápida de pote testada e validada com sucesso.")




def test_atualizar_datas_periodo_global_compatibilidade():
    print("--- Teste 4: Compatibilidade de Argumentos em atualizar_datas_periodo_global ---")
    page = mock_page()
    from core.periodo import atualizar_datas_periodo_global

    # 1. Chamada legada / 3 argumentos (page, d_ini, d_fim)
    est1 = atualizar_datas_periodo_global(page, "2026-10-01", "2026-10-31")
    assert est1["mes"] == 10
    assert est1["ano"] == 2026
    assert est1["modo"] == "mes"

    # 2. Chamada com 5 argumentos (page, d_ini, d_fim, mes, ano) do shell_view / hub_view
    est2 = atualizar_datas_periodo_global(page, "2026-11-01", "2026-11-30", 11, 2026)
    assert est2["mes"] == 11
    assert est2["ano"] == 2026
    assert est2["modo"] == "mes"

    print("[OK] atualizar_datas_periodo_global aceita tanto 3 quanto 5 argumentos sem TypeError.")


def test_edicao_rapida_pote_recorrencia():
    print("--- Teste 5: Edição Rápida com Pergunta de Recorrência (Somente este vs Este e próximos) ---")
    page = mock_page()
    on_refresh = MagicMock()
    tl = TransactionList(page=page, on_refresh=on_refresh)

    item_recorrente = {
        "id": "tx-rec-1",
        "serie_id": "serie-uuid-123",
        "recorrente_id": "rec-uuid-123",
        "tipo": "Despesa",
        "valor": 120.0,
        "data": "2026-10-15",
        "descricao": "Internet Fibra",
        "pote_id": None,
        "status": "Pago",
    }

    # 1. Testa aplicar a "Este e os próximos"
    with patch("services.supabase_client.listar_potes", return_value=[
        {"id": "pote-1", "nome": "Custos Fixos", "cor": "#007AFF", "percentual": 35},
    ]):
        page.show_dialog.reset_mock()
        tl._abrir_seletor_pote(item_recorrente)
        dialog_pote = page.show_dialog.call_args[0][0]

        # Clica no pote Custos Fixos
        linhas_potes = dialog_pote.content.content.controls[2:]
        page.show_dialog.reset_mock()
        linhas_potes[0].on_click(MagicMock())

        # Deve abrir o modal de escopo de recorrência
        assert page.show_dialog.called
        dialog_escopo = page.show_dialog.call_args[0][0]
        assert "Atualizar Recorrência" in dialog_escopo.title.controls[1].value
        assert len(dialog_escopo.actions) == 3  # Cancelar, Somente este, Este e os próximos

        btn_proximos = dialog_escopo.actions[2]
        assert (btn_proximos.content == "Este e os próximos" or getattr(btn_proximos.content, "value", None) == "Este e os próximos")

        with patch("services.supabase_client.atualizar_serie") as mock_serie:
            btn_proximos.on_click(MagicMock())
            assert mock_serie.called
            mock_serie.assert_called_with("serie-uuid-123", {"pote_id": "pote-1"}, a_partir_de="2026-10-15")
            assert on_refresh.called

    # 2. Testa aplicar a "Somente este"
    on_refresh.reset_mock()
    with patch("services.supabase_client.listar_potes", return_value=[
        {"id": "pote-1", "nome": "Custos Fixos", "cor": "#007AFF", "percentual": 35},
    ]):
        page.show_dialog.reset_mock()
        tl._abrir_seletor_pote(item_recorrente)
        dialog_pote = page.show_dialog.call_args[0][0]
        linhas_potes = dialog_pote.content.content.controls[2:]
        page.show_dialog.reset_mock()
        linhas_potes[0].on_click(MagicMock())

        dialog_escopo = page.show_dialog.call_args[0][0]
        btn_somente_este = dialog_escopo.actions[1]
        assert (btn_somente_este.content == "Somente este" or getattr(btn_somente_este.content, "value", None) == "Somente este")

        with patch("services.supabase_client.atualizar_lancamento") as mock_lanc:
            btn_somente_este.on_click(MagicMock())
            assert mock_lanc.called
            mock_lanc.assert_called_with("tx-rec-1", {"pote_id": "pote-1"})
            assert on_refresh.called

    print("[OK] Edição rápida com recorrência perguntou escopo e atualizou Supabase com perfeição.")


if __name__ == "__main__":
    test_filtro_pote_toggle_e_highlight()
    test_categoria_report_sem_tela_branca()
    test_edicao_rapida_pote()
    test_atualizar_datas_periodo_global_compatibilidade()
    test_edicao_rapida_pote_recorrencia()
    print("=" * 60)
    print("TODOS OS 5 TESTES PASSARAM COM SUCESSO!")
    print("=" * 60)
