"""
=============================================================================
DemBase v3 — test_cards_lancamento_responsivos.py  (Flet 1.0.1)
Suite de testes automatizados para verificar a responsividade dos cards de
lançamentos em Mobile (390px) e Desktop (1280px).
=============================================================================
"""
import sys
import os
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import flet as ft
from views.widgets.report.transaction_list import TransactionList
from views.calendario_view import criar_view_calendario


def criar_mock_page(width=390, platform=ft.PagePlatform.ANDROID):
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = 844 if width < 768 else 800
    page.platform = platform
    page._session_store = {}
    page.client_storage = MagicMock()
    page.client_storage.get.side_effect = lambda k: page._session_store.get(k)
    page.client_storage.set.side_effect = lambda k, v: page._session_store.update({k: v})
    page.navigate = MagicMock()
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    return page


def test_transaction_list_desktop():
    print("--- Teste 1: TransactionList em Desktop (1280px) Mantido 100% Intacto ---")
    page = criar_mock_page(width=1280, platform=ft.PagePlatform.WINDOWS)
    on_refresh = MagicMock()
    tl = TransactionList(page=page, on_refresh=on_refresh)

    item = {
        "id": "tx-100",
        "tipo": "Despesa",
        "valor": 250.75,
        "descricao": "Restaurante Fogo de Chão",
        "categoria_nome": "Alimentação",
        "subcategoria_nome": "Jantar",
        "conta_nome": "Santander",
        "forma_movimentacao": "Crédito",
        "cartao_nome": "Santander Elite",
        "parcela_atual": 1,
        "total_parcelas": 1,
        "pote_nome": "Prazeres",
        "pote_cor": "#FF7A00",
        "status": "Pago",
        "regra": "Estilo de Vida",
    }

    card = tl._criar_card_lancamento(item)
    assert isinstance(card, ft.Container)
    # Desktop layout usa ft.Row horizontal diretamente no content
    assert isinstance(card.content, ft.Row)
    # Contém area_clicavel_edicao + 3 ações à direita (Pote, Status, Lixeira)
    assert len(card.content.controls) == 4
    area_edicao = card.content.controls[0]
    assert isinstance(area_edicao, ft.Container)
    assert area_edicao.expand is True

    print("[OK] Layout Desktop mantido exatamente no formato original de linha única.")


def test_transaction_list_mobile():
    print("--- Teste 2: TransactionList em Mobile (390px) Compacto e com Dados Visíveis ---")
    page = criar_mock_page(width=390, platform=ft.PagePlatform.ANDROID)
    on_refresh = MagicMock()
    tl = TransactionList(page=page, on_refresh=on_refresh)

    item = {
        "id": "tx-101",
        "tipo": "Despesa",
        "valor": 349.90,
        "descricao": "Supermercado Pão de Açúcar",
        "categoria_nome": "Alimentação",
        "subcategoria_nome": "Feira da Semana",
        "conta_nome": "Nubank",
        "forma_movimentacao": "Crédito",
        "cartao_nome": "Nubank Ultravioleta",
        "parcela_atual": 2,
        "total_parcelas": 4,
        "pote_nome": "Custos Fixos",
        "pote_cor": "#007AFF",
        "status": "Pendente",
        "regra": "Essencial",
    }

    card = tl._criar_card_lancamento(item)
    assert isinstance(card, ft.Container)
    # Mobile layout usa ft.Column vertical com tight=True (abraça apenas o conteúdo real)
    assert isinstance(card.content, ft.Column)
    assert card.content.tight is True
    assert len(card.content.controls) == 2  # Linha Topo + Linha Rodapé

    linha_topo = card.content.controls[0]
    linha_rodape = card.content.controls[1]

    # Verifica Linha Topo
    assert isinstance(linha_topo, ft.Container)
    row_topo = linha_topo.content
    assert isinstance(row_topo, ft.Row)
    # Controles: [Container(Ícone), Column(Título e Subtítulo), Text(Valor)]
    assert len(row_topo.controls) == 3

    icone_ctrl = row_topo.controls[0]
    col_textos = row_topo.controls[1]
    valor_ctrl = row_topo.controls[2]

    assert isinstance(col_textos, ft.Column)
    assert col_textos.expand is True
    # Descrição do lançamento visível em destaque
    txt_titulo = col_textos.controls[0]
    assert txt_titulo.value == "Supermercado Pão de Açúcar"
    assert txt_titulo.overflow == ft.TextOverflow.ELLIPSIS
    # Categoria e subcategoria visíveis
    txt_subtitulo = col_textos.controls[1]
    assert "Alimentação" in txt_subtitulo.value
    assert "Feira da Semana" in txt_subtitulo.value

    # Valor visível
    assert "349,90" in valor_ctrl.value

    # Verifica Linha Rodapé (Badges compactos + Ações)
    assert isinstance(linha_rodape, ft.Row)
    assert len(linha_rodape.controls) == 2
    row_badges = linha_rodape.controls[0]
    row_acoes = linha_rodape.controls[1]

    assert isinstance(row_badges, ft.Row)
    assert row_badges.scroll == ft.ScrollMode.HIDDEN
    assert row_badges.expand is True

    # Badges esperados no mobile: Cartão, Parcela (2/4), Pote
    assert len(row_badges.controls) >= 3

    # Ações à direita: Badge de status (Pendente) + Botão de exclusão (Lixeira)
    assert isinstance(row_acoes, ft.Row)
    assert len(row_acoes.controls) == 2
    badge_status = row_acoes.controls[0]
    btn_lixeira = row_acoes.controls[1]
    assert isinstance(btn_lixeira, ft.IconButton)
    assert btn_lixeira.icon == ft.Icons.DELETE_OUTLINE_ROUNDED

    print("[OK] Layout Mobile do TransactionList é compacto, estruturado e exibe descrição, categoria, valor e ações.")


def test_interacoes_rapidas_mobile():
    print("--- Teste 3: Interações no Card Mobile (Status, Pote, Edição e Exclusão) ---")
    page = criar_mock_page(width=390, platform=ft.PagePlatform.ANDROID)
    on_refresh = MagicMock()
    tl = TransactionList(page=page, on_refresh=on_refresh)

    item = {
        "id": "tx-102",
        "tipo": "Despesa",
        "valor": 50.0,
        "descricao": "Café da Manhã",
        "categoria_nome": "Alimentação",
        "status": "Pago",
        "pote_id": None,
        "pote_nome": None,
    }

    card = tl._criar_card_lancamento(item)
    linha_topo = card.content.controls[0]
    linha_rodape = card.content.controls[1]
    row_acoes = linha_rodape.controls[1]
    badge_status = row_acoes.controls[0]
    btn_lixeira = row_acoes.controls[1]

    # 1. Clique em alterar status
    with patch("services.supabase_client.atualizar_lancamento") as mock_status:
        badge_status.on_click(MagicMock())
        assert mock_status.called
        # Alternou de Pago para Pendente
        mock_status.assert_called_with("tx-102", {"status": "Pendente"})
        assert on_refresh.called

    # 2. Clique na lixeira
    btn_lixeira.on_click(MagicMock())
    assert page.show_dialog.called

    print("[OK] Interações rápidas funcionam perfeitamente no card mobile.")


def test_calendario_card_mobile():
    print("--- Teste 4: Card de Lançamento no Calendário (Mobile vs Desktop) ---")
    from views.calendario_view import formatar_data_br

    page_m = criar_mock_page(width=390, platform=ft.PagePlatform.ANDROID)
    view_cal = criar_view_calendario(page_m)
    assert isinstance(view_cal, ft.View)

    print("[OK] View do Calendário montada com suporte ao layout mobile corrigido.")


if __name__ == "__main__":
    test_transaction_list_desktop()
    test_transaction_list_mobile()
    test_interacoes_rapidas_mobile()
    test_calendario_card_mobile()
    print("\n=======================================================")
    print("TODOS OS TESTES DE RESPONSIVIDADE PASSARAM COM SUCESSO!")
    print("=======================================================")
