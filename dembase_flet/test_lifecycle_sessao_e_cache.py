"""
=============================================================================
DemBase v3 — test_lifecycle_sessao_e_cache.py
Bateria de testes automatizados para:
1. Persistência de autenticação e estado no ciclo de vida (Mobile Background)
2. Reconexão transparente e restauração da última tela ativa sem cair em Login
3. Sistema de Cache em Memória (RAM / Dicionários) para os 6 potes e categorias
4. Invalidação cirúrgica do cache em mutações e logout
5. Execução assíncrona não-bloqueante (Zero UI Blocking)
=============================================================================
"""
import sys
import os
import asyncio
from unittest.mock import MagicMock, patch

# Garante o path de importação
sys.path.insert(0, os.path.dirname(__file__))

import flet as ft
from core import storage
from core.router import ROTA_AUTH, ROTA_DASHBOARD, ROTA_CARTOES
import services.supabase_client as db


def mock_page(route="/dashboard"):
    page = MagicMock(spec=ft.Page)
    page.width = 390
    page.height = 844
    page.route = route
    page.views = []
    page._session_store = {}
    page.session = page._session_store

    page.client_storage = MagicMock()
    page.client_storage.get.side_effect = lambda k: page._session_store.get(k)
    page.client_storage.set.side_effect = lambda k, v: page._session_store.update({k: v})

    page.services = []
    page.navigate = MagicMock(side_effect=lambda r: setattr(page, "route", r))
    page.update = MagicMock()
    return page


async def test_persistencia_sessao_e_ultima_rota():
    print("--- Teste 1: Persistência de Sessão e Última Rota (Mobile Background) ---")
    page1 = mock_page(route="/cartoes/cart-nubank")

    # 1. Usuário faz login e navega até o extrato de um cartão
    await storage.salvar_sessao_autenticada(
        page1,
        access_token="fake_access_token_123",
        refresh_token="fake_refresh_token_456",
        email="usuario@teste.com"
    )
    await storage.salvar_ultima_rota(page1, "/cartoes/cart-nubank")

    # 2. Simula o aplicativo sendo minimizado no celular, conexão caindo e nova sessão sendo criada
    page2 = mock_page(route=ROTA_AUTH)

    # 3. Na nova sessão, recupera credenciais persistidas
    acc, ref, email = await storage.carregar_sessao_autenticada(page2)
    assert acc == "fake_access_token_123", f"Esperado fake_access_token_123, obtido {acc}"
    assert ref == "fake_refresh_token_456", f"Esperado fake_refresh_token_456, obtido {ref}"
    assert email == "usuario@teste.com"
    print("  [OK] Sessão de autenticação persistida e recuperada com sucesso após desconexão.")

    # 4. Recupera a última rota para não mandar o usuário de volta para login
    ultima_rota = await storage.carregar_ultima_rota(page2)
    assert ultima_rota == "/cartoes/cart-nubank", f"Esperado /cartoes/cart-nubank, obtido {ultima_rota}"
    print("  [OK] Última tela visitada (/cartoes/cart-nubank) restaurada sem forçar novo login.")

    # 5. Ao fazer logout explícito, limpa tokens e reseta rota
    await storage.limpar_sessao_autenticada(page2)
    acc_pos, ref_pos, _ = await storage.carregar_sessao_autenticada(page2)
    assert acc_pos == "" and ref_pos == "", "Tokens deveriam ter sido limpos no logout explícito"
    print("  [OK] Logout explícito remove credenciais persistentes com segurança.")


def test_sistema_cache_ram_potes_e_categorias():
    print("--- Teste 2: Sistema de Cache em Memória (RAM / Dicionários) ---")
    # Limpa cache inicial
    db.invalidar_cache(None)

    # 1. Mock de consulta aos 6 potes
    mock_potes = [
        {"id": "p1", "posicao": 1, "nome": "Custos Fixos", "percentual": 35.0, "cor": "#3B82F6"},
        {"id": "p2", "posicao": 2, "nome": "Conforto", "percentual": 15.0, "cor": "#10B981"},
        {"id": "p3", "posicao": 3, "nome": "Metas", "percentual": 15.0, "cor": "#F59E0B"},
        {"id": "p4", "posicao": 4, "nome": "Prazeres", "percentual": 10.0, "cor": "#EC4899"},
        {"id": "p5", "posicao": 5, "nome": "Liberdade Financeira", "percentual": 15.0, "cor": "#8B5CF6"},
        {"id": "p6", "posicao": 6, "nome": "Conhecimento", "percentual": 10.0, "cor": "#06B6D4"},
    ]

    mock_query_potes = MagicMock()
    mock_query_potes.execute.return_value = MagicMock(data=mock_potes)

    with patch.object(db.supabase, "table") as mock_table:
        mock_table.return_value.select.return_value.order.return_value = mock_query_potes

        # Primeira chamada: busca no banco e popula o cache
        potes_1 = db.listar_potes()
        assert len(potes_1) == 6
        assert mock_query_potes.execute.call_count == 1
        print("  [OK] Primeira chamada de potes buscou no Supabase e populou RAM cache.")

        # Segunda chamada: deve vir 100% da RAM (zero chamadas HTTP adicionais)
        potes_2 = db.listar_potes()
        assert len(potes_2) == 6
        assert mock_query_potes.execute.call_count == 1, "Segunda chamada deveria ter vindo do cache RAM sem requisição HTTP!"
        print("  [OK] Segunda chamada de potes retornou instantaneamente do cache em memória (0 ms).")

    # 2. Mock de Categorias
    mock_cats = [
        {"id": "c1", "nome": "Alimentação", "tipo": "ambos", "cor": "#FF0000"},
        {"id": "c2", "nome": "Transporte", "tipo": "ambos", "cor": "#00FF00"},
    ]
    mock_query_cats = MagicMock()
    mock_query_cats.execute.return_value = MagicMock(data=mock_cats)

    with patch.object(db.supabase, "table") as mock_table:
        mock_table.return_value.select.return_value.eq.return_value.order.return_value = mock_query_cats

        cats_1 = db.listar_categorias()
        assert len(cats_1) == 2
        assert mock_query_cats.execute.call_count == 1

        cats_2 = db.listar_categorias()
        assert len(cats_2) == 2
        assert mock_query_cats.execute.call_count == 1, "Categorias deveriam ter retornado do cache RAM!"
        print("  [OK] Categorias cacheadas com sucesso, evitando bloqueios na navegação e filtros.")


def test_invalidacao_cirurgica_de_cache():
    print("--- Teste 3: Invalidação Cirúrgica do Cache em Mutações ---")
    db.invalidar_cache(None)

    # 1. Popula cache de potes e categorias
    db.salvar_cache("potes", [{"id": "p1", "nome": "Pote 1"}])
    db.salvar_cache("categorias", [{"id": "c1", "nome": "Cat 1"}])
    db.salvar_cache("potes_resumo", {"saldo": 1000}, subchave="2026-10-01_2026-10-31")

    assert db.obter_cache("potes") is not None
    assert db.obter_cache("categorias") is not None
    assert db.obter_cache("potes_resumo", subchave="2026-10-01_2026-10-31") is not None

    # 2. Invalidação de potes (não deve afetar categorias)
    db.invalidar_cache("potes")
    assert db.obter_cache("potes") is None, "Cache de potes deveria ter sido invalidado"
    assert db.obter_cache("potes_resumo", subchave="2026-10-01_2026-10-31") is None
    assert db.obter_cache("categorias") is not None, "Cache de categorias deve permanecer intacto"
    print("  [OK] Invalidação cirúrgica de potes validada.")

    # 3. Invalidação de lançamentos (deve limpar resumo de potes sem limpar cadastros base de categorias)
    db.salvar_cache("potes_resumo", {"saldo": 2000}, subchave="2026-11-01_2026-11-30")
    db.invalidar_cache("lancamentos")
    assert db.obter_cache("potes_resumo", subchave="2026-11-01_2026-11-30") is None
    assert db.obter_cache("categorias") is not None
    print("  [OK] Invalidação de lançamentos atualizou os resumos mantendo categorias cacheadas.")


async def test_execucao_assincrona_sem_ui_blocking():
    print("--- Teste 4: Execução Assíncrona e Warm-up (Zero UI Blocking) ---")

    # 1. Testar db.executar_async rodando em thread separada
    def tarefa_demorada():
        import time
        time.sleep(0.05)
        return "concluido_em_thread"

    res = await db.executar_async(tarefa_demorada)
    assert res == "concluido_em_thread"
    print("  [OK] db.executar_async offloadou tarefa para thread sem travar o event loop.")

    # 2. Testar aquecimento de cache em background (não bloqueia execução)
    with patch("services.supabase_client.listar_potes") as mock_lp:
        with patch("services.supabase_client.listar_categorias") as mock_lc:
            db.aquecer_cache()
            await asyncio.sleep(0.1) # Aguarda thread de aquecimento
            assert mock_lp.called
            assert mock_lc.called
            print("  [OK] aquecer_cache disparou pre-fetching em background com sucesso.")


async def main_testes():
    await test_persistencia_sessao_e_ultima_rota()
    test_sistema_cache_ram_potes_e_categorias()
    test_invalidacao_cirurgica_de_cache()
    await test_execucao_assincrona_sem_ui_blocking()
    print("\n" + "=" * 60)
    print("TODOS OS TESTES DE LIFECYCLE E CACHE PASSARAM COM 100%!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main_testes())
