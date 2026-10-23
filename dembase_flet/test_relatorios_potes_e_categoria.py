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


if __name__ == "__main__":
    test_filtro_pote_toggle_e_highlight()
    test_categoria_report_sem_tela_branca()
    test_edicao_rapida_pote()
    print("=" * 60)
    print("TODOS OS 3 TESTES PASSARAM COM SUCESSO!")
    print("=" * 60)
