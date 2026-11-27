"""
=============================================================================
DemBase v3 — test_fatura_potes_e_rastreio_datas.py
Auditoria automatizada de ponta a ponta das regras financeiras:
1. Cartão de Crédito Baseado na Fatura (6 Potes, Relatórios e Trava de Status)
2. Correção e exibição de Potes nos Relatórios do Cartão
3. Rastreabilidade de Datas: Criação, Vencimento Original e Pagamento Adiantado
=============================================================================
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

import flet as ft
from core.constants import formatar_rastreio_datas, formatar_data_curta_br
from core.lancamento_state import LancamentoFormState
from core.report_context import ReportContext
from core.router import RouteMatch
from services import supabase_client as db
from views.calendario_view import criar_view_calendario
from views.relatorios.cartao_report import criar_view_relatorio_cartao
from views.widgets.lancamento_form import LancamentoForm
from views.widgets.lancamento_sheet import abrir_lancamento
from views.widgets.report.transaction_list import TransactionList


def criar_mock_page(width: int = 1280, height: int = 800) -> ft.Page:
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.platform = ft.PagePlatform.WINDOWS if width >= 768 else ft.PagePlatform.ANDROID
    page.client_storage = MagicMock()
    page.session = MagicMock()
    session_store = {}
    page.session.get.side_effect = lambda k: session_store.get(k)
    page.session.set.side_effect = lambda k, v: session_store.update({k: v})
    page.session.contains_key.side_effect = lambda k: k in session_store
    page.views = []
    page.route = "/dashboard"
    page.navigate = MagicMock()
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    page.run_task = MagicMock()
    return page


def buscar_textos_arvore(ctrl) -> list[str]:
    textos: list[str] = []
    if ctrl is None:
        return textos
    if isinstance(ctrl, ft.Text) and ctrl.value:
        textos.append(str(ctrl.value))
    if hasattr(ctrl, "controls") and ctrl.controls:
        for c in ctrl.controls:
            textos.extend(buscar_textos_arvore(c))
    if hasattr(ctrl, "content") and ctrl.content:
        textos.extend(buscar_textos_arvore(ctrl.content))
    return textos


def test_1_trava_status_credito_state_e_ui():
    print("--- 1. Testando Trava de Status 'Pago' Vinculada à Fatura (State + UI) ---")
    page = criar_mock_page()

    # Compra feita em Outubro (passado), mas no Cartão de Crédito (fatura em aberto)
    st = LancamentoFormState(
        tipo="Despesa",
        forma_movimentacao="Crédito",
        data_selecionada=date(2026, 10, 25),
        cartao_id="card-itau",
        categoria_id="cat-1",
        pote_id="2df4dd2f-4353-42cc-a5c9-8983085a5301",
        valor=250.0,
    )
    assert st.eh_credito is True
    assert st.status_pago is False, "Compra em fatura aberta NUNCA pode iniciar como Pago!"

    # Mesmo mudando a data para outra data passada, continua Pendente
    st.atualizar_data(date(2026, 10, 10))
    assert st.status_pago is False, "Mudar data da compra no cartão não pode marcar como Pago!"

    # Mesmo tentando forçar o switch manualmente, a trava mantém False enquanto a fatura estiver aberta
    st.tocar_switch_status(True)
    assert st.status_pago is False, "Trava deve impedir status Pago solto em fatura aberta!"

    # Se a fatura já estiver paga, preserva status_pago = True
    st_paga = LancamentoFormState(
        tipo="Despesa",
        forma_movimentacao="Crédito",
        data_selecionada=date(2026, 10, 25),
        cartao_id="card-santander",
        fatura_status="paga",
        status_pago=True,
    )
    assert st_paga.status_pago is True

    # Verifica UI do LancamentoForm (switch desabilitado com label 'Paga na fatura')
    with patch("services.supabase_client.listar_contas", return_value=[]), \
         patch("services.supabase_client.listar_cartoes", return_value=[{"id": "card-itau", "nome": "Itaú"}]), \
         patch("services.supabase_client.listar_categorias", return_value=[{"id": "cat-1", "nome": "Moradia"}]), \
         patch("services.supabase_client.listar_faturas_opcoes_cartao", return_value=[]):
        form = LancamentoForm(page, st)
        assert form.switch_status.value is False
        assert form.switch_status.disabled is True
        assert form.switch_status.label == "Paga na fatura"

    # Verifica bloqueio de toggle manual na TransactionList para compras de cartão
    tl = TransactionList(page=page, on_refresh=MagicMock())
    with patch("services.supabase_client.atualizar_lancamento") as mock_upd:
        tl._alternar_status({
            "id": "lanc-credito-1",
            "tipo": "Despesa",
            "forma_movimentacao": "Crédito",
            "cartao_id": "card-itau",
            "fatura_id": "fat-nov",
            "status": "Pendente",
        })
        assert not mock_upd.called, "Não deve permitir dar baixa avulsa em compra de cartão fora da fatura!"

    print("  [OK] Trava de status 'Pago' vinculada à fatura validada em State, Form e TransactionList.")


def test_2_pote_nos_relatorios_do_cartao():
    print("--- 2. Testando Potes Financeiros nos Relatórios do Cartão ---")
    page = criar_mock_page()
    tl = TransactionList(page=page, on_refresh=MagicMock())

    # Cenário A: Item retornado pela RPC get_relatorio_cartao com pote_id e pote_nome
    item_fatura_a = {
        "id": "it-1",
        "tipo": "Despesa",
        "forma_movimentacao": "Crédito",
        "cartao_id": "card-itau",
        "cartao_nome": "Itaú",
        "fatura_id": "fat-nov-2026",
        "valor": 130.90,
        "data": "2026-10-28",
        "data_vencimento": "2026-11-23",
        "descricao": "Internet Móvel",
        "status": "Pendente",
        "categoria_nome": "Moradia",
        "pote_id": "2df4dd2f-4353-42cc-a5c9-8983085a5301",
        "pote_nome": "Custos Fixos",
        "pote_cor": "#007AFF",
    }
    card_a = tl._criar_card_lancamento(item_fatura_a)
    textos_a = buscar_textos_arvore(card_a)
    assert "Custos Fixos" in textos_a, f"Pote 'Custos Fixos' deveria aparecer no card! Textos: {textos_a}"
    assert "Definir Pote" not in textos_a, "Não deve exibir 'Definir Pote' quando o pote já está definido!"
    assert "Compra 28/10 · Venc. 23/11" in textos_a, f"Rastreio Compra x Vencimento ausente! Textos: {textos_a}"

    # Cenário B: Item com pote_id definido mas sem pote_nome hidratado (fallback automático)
    item_fatura_b = {
        "id": "it-2",
        "tipo": "Despesa",
        "forma_movimentacao": "Crédito",
        "cartao_id": "card-itau",
        "cartao_nome": "Itaú",
        "fatura_id": "fat-nov-2026",
        "valor": 89.90,
        "data": "2026-10-30",
        "data_vencimento": "2026-11-23",
        "descricao": "Restaurante Sábado",
        "status": "Pendente",
        "categoria_nome": "Lazer",
        "pote_id": "c82b0736-fb01-419f-8155-923ebfec82b2",
        "pote_nome": None,
    }
    card_b = tl._criar_card_lancamento(item_fatura_b)
    textos_b = buscar_textos_arvore(card_b)
    assert "Prazeres" in textos_b, f"Fallback por pote_id deveria resolver 'Prazeres'! Textos: {textos_b}"
    assert "Definir Pote" not in textos_b

    # Cenário C: Hidratação no supabase_client.obter_relatorio_cartao
    pacote_rpc_mock = {
        "cartao": {"id": "card-itau", "nome": "Itaú", "limite_total": 5000, "limite_disponivel": 4000},
        "totais": {"gasto_periodo": 220.80, "qtd_compras": 2},
        "kpis": {"gasto_periodo": 220.80, "qtd_compras": 2},
        "categorias": [{"categoria_id": "c1", "nome": "Moradia", "total": 220.80, "percentual": 100.0, "qtd": 2}],
        "por_pote": [{"pote_id": "2df4dd2f-4353-42cc-a5c9-8983085a5301", "nome": "Custos Fixos", "total": 220.80, "percentual": 100.0, "qtd": 2, "cor": "#007AFF"}],
        "lancamentos": [
            {"id": "l1", "valor": 220.80, "pote_id": "2df4dd2f-4353-42cc-a5c9-8983085a5301", "pote_nome": None}
        ],
        "total_registros": 1,
    }
    with patch.object(db.supabase, "rpc") as mock_rpc, \
         patch("services.supabase_client.obter_total_em_uso_cartao", return_value=220.80), \
         patch("services.supabase_client.listar_potes", return_value=[]):
        mock_rpc.return_value.execute.return_value.data = pacote_rpc_mock
        res_cartao = db.obter_relatorio_cartao("card-itau", "2026-11-01", "2026-11-30")
        assert len(res_cartao["por_pote"]) == 1
        assert res_cartao["por_pote"][0]["nome"] == "Custos Fixos"
        assert res_cartao["lancamentos"][0]["pote_nome"] == "Contas Fixas"
        assert res_cartao["lancamentos"][0]["pote_cor"] == "#007AFF"

    print("  [OK] Potes Financeiros preservados e exibidos com perfeição nos Relatórios do Cartão.")


def test_3_pagamento_adiantado_e_rastreabilidade_datas():
    print("--- 3. Testando Rastreabilidade de Datas: Vencimento Original vs. Pagamento Adiantado ---")
    hoje_dt = date.today()
    venc_dt = date(hoje_dt.year, hoje_dt.month, 20) if hoje_dt.day != 20 else (hoje_dt + timedelta(days=4))
    hoje_iso = hoje_dt.isoformat()
    venc_iso = venc_dt.isoformat()

    # Despesa agendada para o dia 20 (ex: Aluguel da Moto), paga adiantado hoje
    item_moto = {
        "id": "lanc-moto-20",
        "tipo": "Despesa",
        "forma_movimentacao": "Pix",
        "conta_id": "conta-inter",
        "conta_nome": "Inter",
        "valor": 450.00,
        "descricao": "Aluguel da Moto",
        "categoria_nome": "Transporte",
        "pote_id": "2df4dd2f-4353-42cc-a5c9-8983085a5301",
        "pote_nome": "Custos Fixos",
        "pote_cor": "#007AFF",
        "data": venc_iso,
        "data_vencimento": venc_iso,
        "data_pagamento": hoje_iso,
        "status": "Pago",
    }

    esperado = f"Pago em {formatar_data_curta_br(hoje_iso)} · Venc. {formatar_data_curta_br(venc_iso)}"
    rastreio = formatar_rastreio_datas(item_moto)
    assert rastreio == esperado, f"Esperado '{esperado}', obtido '{rastreio}'"

    # Verifica exibição no card da TransactionList (Desktop e Mobile)
    page_desk = criar_mock_page(width=1280, height=800)
    tl_desk = TransactionList(page=page_desk, on_refresh=MagicMock())
    card_desk = tl_desk._criar_card_lancamento(item_moto)
    textos_desk = buscar_textos_arvore(card_desk)
    assert esperado in textos_desk, f"Texto '{esperado}' deveria estar no card Desktop: {textos_desk}"

    page_mob = criar_mock_page(width=390, height=844)
    tl_mob = TransactionList(page=page_mob, on_refresh=MagicMock())
    card_mob = tl_mob._criar_card_lancamento(item_moto)
    textos_mob = buscar_textos_arvore(card_mob)
    assert esperado in textos_mob, f"Texto '{esperado}' deveria estar no card Mobile: {textos_mob}"

    print(f"  [OK] Baixa adiantada exibe '{esperado}' claramente no extrato Desktop e Mobile.")


if __name__ == "__main__":
    print("=" * 70)
    print("AUDITORIA PONTA A PONTA: FATURA NOS 6 POTES & RASTREIO DE DATAS")
    print("=" * 70)
    test_1_trava_status_credito_state_e_ui()
    test_2_pote_nos_relatorios_do_cartao()
    test_3_pagamento_adiantado_e_rastreabilidade_datas()
    print("=" * 70)
    print("TODOS OS TESTES DE AUDITORIA PASSARAM COM 100% DE SUCESSO!")
    print("=" * 70)
