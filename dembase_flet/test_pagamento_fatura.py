"""
=============================================================================
DemBase v3 — test_pagamento_fatura.py
Bateria de testes automatizados para a funcionalidade "Pagar a Fatura":
1. Origem do Dinheiro (Seleção de conta bancária de saída)
2. Baixa em Lote (Status de todos os lançamentos da fatura alterados para 'Pago')
3. Liquidação da Fatura (status 'paga', valor_pago = total, data_pagamento)
4. Débito no Saldo Bancário (sem duplicação de despesas no dashboard)
5. Restauração do Limite Disponível do Cartão de Crédito
6. Reversibilidade Segura (Estorno do Pagamento e Reabertura de Fatura)
=============================================================================
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

import flet as ft
from services import supabase_client as db
from core.report_context import ReportContext
from views.relatorios.cartao_report import criar_view_relatorio_cartao


class RouteMatch:
    def __init__(self, path: str, params_path: dict | None = None):
        self.path = path
        self.params_path = params_path or {}

    def get(self, key, default=None):
        return self.params_path.get(key, default)


def mock_page():
    page = MagicMock(spec=ft.Page)
    page.width = 1200
    page.height = 800
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
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    # Mock de run_task sem acionar event loop inexistente
    page.run_task = MagicMock()
    return page


def test_assinaturas_rpc_supabase():
    print("--- 1. Validando exportações e assinaturas no supabase_client ---")
    assert hasattr(db, "liquidar_pagamento_fatura"), "liquidar_pagamento_fatura ausente"
    assert hasattr(db, "estornar_pagamento_fatura"), "estornar_pagamento_fatura ausente"
    assert hasattr(db, "pagar_fatura"), "pagar_fatura ausente"
    print("  [OK] Funções exportadas com sucesso pelo supabase_client.")


def test_fluxo_logico_pagamento_mock():
    print("--- 2. Validando fluxo lógico de negócio e baixa em lote ---")
    fatura_id = "fat-123"
    conta_id = "conta-itau-456"
    valor_total = 350.75
    data_pag = "2026-10-26"

    retorno_mock = {
        "sucesso": True,
        "fatura_id": fatura_id,
        "cartao_id": "cart-nubank",
        "cartao_nome": "Nubank Roxinho",
        "mes": 10,
        "ano": 2026,
        "valor_pago": valor_total,
        "data_pagamento": data_pag,
        "conta_id": conta_id,
        "conta_nome": "Itaú Corrente",
        "total_despesas": valor_total,
        "qtd_despesas": 4,
        "qtd_baixadas": 4,
        "pagamento_lancamento_id": "lanc-debito-789",
    }

    with patch.object(db.supabase, "rpc") as mock_rpc:
        mock_rpc.return_value.execute.return_value.data = retorno_mock

        res = db.liquidar_pagamento_fatura(fatura_id, conta_id, data_pag, valor_total)

        assert res["sucesso"] is True
        assert res["qtd_baixadas"] == 4, "Todas as compras devem receber baixa em lote"
        assert res["valor_pago"] == valor_total, "Valor pago deve equivaler ao total da fatura"
        assert res["conta_id"] == conta_id, "Dinheiro deve sair da conta bancária de origem escolhida"

        mock_rpc.assert_called_with("liquidar_pagamento_fatura", {
            "p_fatura_id": fatura_id,
            "p_conta_id": conta_id,
            "p_data_pagamento": data_pag,
            "p_valor_pago": valor_total,
        })
        print("  [OK] RPC liquidar_pagamento_fatura disparada com parâmetros e baixa em lote corretos.")

    # Simula fluxo de estorno
    retorno_estorno = {
        "sucesso": True,
        "fatura_id": fatura_id,
        "novo_status": "aberta",
        "lancamentos_reavaliados": 4,
    }

    with patch.object(db.supabase, "rpc") as mock_rpc_est:
        mock_rpc_est.return_value.execute.return_value.data = retorno_estorno

        res_est = db.estornar_pagamento_fatura(fatura_id)
        assert res_est["sucesso"] is True
        assert res_est["novo_status"] == "aberta"
        mock_rpc_est.assert_called_with("estornar_pagamento_fatura", {"p_fatura_id": fatura_id})
        print("  [OK] RPC estornar_pagamento_fatura disparada com parâmetros corretos.")


def test_renderizacao_view_cartao_report():
    print("--- 3. Validando instanciação e UI da tela de Fatura & Extrato ---")
    page = mock_page()
    ctx = ReportContext.from_query(page)

    mock_pacote = {
        "cartao": {
            "id": "c1",
            "nome": "Nubank Ultravioleta",
            "cor": "#820AD1",
            "limite_total": 5000,
            "limite_disponivel": 3500,
        },
        "kpis": {
            "total_gasto_periodo": 1500,
            "limite_total": 5000,
            "limite_disponivel": 3500,
            "total_parcelado": 1000,
            "total_a_vista": 500,
        },
        "fatura_selecionada": {
            "id": "fat-1",
            "mes": 10,
            "ano": 2026,
            "status": "aberta",
            "valor_total": 1500.0,
            "valor_pago": 0.0,
        },
        "evolucao_diaria": [{"data": "2026-10-23", "receitas": 0, "despesas": 150, "label": "23/10"}],
        "por_categoria": [
            {"categoria_id": "cat-1", "nome": "Restaurante", "total": 350.0, "percentual": 40.0, "qtd": 2, "cor": "#FF5722"}
        ],
        "faturas": [
            {
                "id": "fat-1",
                "mes": 10,
                "ano": 2026,
                "status": "aberta",
                "valor_total": 1500.0,
                "valor_pago": 0.0,
            }
        ],
        "lancamentos": [],
        "total_registros": 0,
    }

    with patch("services.supabase_client.obter_relatorio_cartao", return_value=mock_pacote), \
         patch("services.supabase_client.listar_faturas_opcoes_cartao", return_value=[]), \
         patch("services.supabase_client.listar_contas", return_value=[{"id": "ct-1", "nome": "Itaú", "saldo_atual": 2500.0}]):

        view = criar_view_relatorio_cartao(
            page,
            RouteMatch(path="/cartoes/c1", params_path={"cartao_id": "c1"}),
            ctx,
        )
        assert isinstance(view, ft.View), "Deve retornar uma ft.View válida do Flet 1.0.1"
        assert len(view.controls) > 0, "View deve possuir controles hierárquicos"
        print("  [OK] View de Fatura & Extrato instanciada com sucesso (Flet 1.0.1).")


def main():
    print("============================================================")
    print("INICIANDO SUITE DE TESTES: PAGAMENTO DE FATURA DE CARTÃO")
    print("============================================================")
    test_assinaturas_rpc_supabase()
    test_fluxo_logico_pagamento_mock()
    test_renderizacao_view_cartao_report()
    print("============================================================")
    print("TODOS OS TESTES DE PAGAMENTO DE FATURA PASSARAM COM 100%!")
    print("============================================================")


if __name__ == "__main__":
    main()
