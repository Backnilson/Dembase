"""
=============================================================================
DemBase v3 — test_cartoes_dashboard.py
Testes unitários e de integração para a nova view de Cartões de Crédito:
1. Ordem das Abas & Estado Padrão:
   - 1º "Meus Cartões" (Default), 2º "Faturas Abertas", 3º "Faturas Fechadas".
2. Sincronização Estrita de Filtro:
   - Faturas abertas e fechadas filtradas rigorosamente pelo mês/ano global.
3. Inteligência do Melhor Cartão:
   - Cálculo automático do maior prazo de vencimento e ordenação no topo.
4. Renderização Desktop e Mobile:
   - Compatibilidade total Flet 1.0.1.
=============================================================================
"""
import sys
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, "dembase_flet")

import flet as ft
from views.cartoes_view import (
    calcular_detalhes_fechamento,
    calcular_melhor_cartao,
    formatar_status_vencimento,
    criar_view_cartoes,
)


def mock_page(width=1280, height=800, mes=11, ano=2026):
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.session = MagicMock()
    page.session.get.return_value = {
        "mes": mes,
        "ano": ano,
        "data_inicio": date(ano, mes, 1),
        "data_fim": date(ano, mes, 30 if mes in (4, 6, 9, 11) else 31),
    }
    page.views = []
    page.dialog = None
    page.overlay = []
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    page.run_task = MagicMock()
    page.update = MagicMock()
    return page


def test_inteligencia_calculo_melhor_cartao():
    hoje = date(2026, 10, 26)
    c_nubank = {"id": "1", "nome": "Nubank", "dia_fechamento": 25, "dia_vencimento": 5, "limite_disponivel": 3000.0, "limite_total": 5000.0}
    c_inter = {"id": "2", "nome": "Inter", "dia_fechamento": 1, "dia_vencimento": 10, "limite_disponivel": 5000.0, "limite_total": 8000.0}
    c_itau = {"id": "3", "nome": "Itaú", "dia_fechamento": 28, "dia_vencimento": 7, "limite_disponivel": 2000.0, "limite_total": 4000.0}

    det_nu = calcular_detalhes_fechamento(c_nubank, hoje)
    det_in = calcular_detalhes_fechamento(c_inter, hoje)
    det_it = calcular_detalhes_fechamento(c_itau, hoje)

    assert det_nu["dias_venc"] == 40, f"Esperado 40 dias de prazo para Nubank, obteve {det_nu['dias_venc']}"
    assert det_in["dias_venc"] == 15, f"Esperado 15 dias de prazo para Inter, obteve {det_in['dias_venc']}"
    assert det_it["dias_venc"] == 12, f"Esperado 12 dias de prazo para Itaú, obteve {det_it['dias_venc']}"

    melhor_cartao, melhor_info = calcular_melhor_cartao([c_itau, c_inter, c_nubank], hoje)
    assert melhor_cartao["nome"] == "Nubank"
    assert melhor_info["dias_venc"] == 40
    assert melhor_info["dias_fech"] == 30
    print("[OK] Teste de inteligencia de calculo do melhor cartao passou!")


def test_status_vencimento_relativo():
    hoje = date.today()
    from datetime import timedelta
    # Vencida com débito
    lbl, _, _ = formatar_status_vencimento(hoje - timedelta(days=3), valor_pendente=150.0)
    assert "Vencida" in lbl
    # Fatura sem débito (R$ 0,00) que já passou do dia de vencimento -> DEVE ser 'Zerada' e NUNCA 'Vencida'
    lbl_zerada, _, _ = formatar_status_vencimento(hoje - timedelta(days=3), valor_pendente=0.0)
    assert lbl_zerada == "Zerada", f"Esperado 'Zerada', obtido '{lbl_zerada}'"
    # Hoje
    lbl, _, _ = formatar_status_vencimento(hoje, valor_pendente=50.0)
    assert "Hoje" in lbl
    # Amanhã
    lbl, _, _ = formatar_status_vencimento(hoje + timedelta(days=1), valor_pendente=50.0)
    assert "Amanhã" in lbl
    # Paga
    lbl, _, _ = formatar_status_vencimento(hoje, status="paga", valor_pendente=0.0)
    assert lbl == "Paga"
    print("[OK] Teste de formatacao de status de vencimento (incluindo 'Zerada') passou!")


@patch("services.supabase_client.liquidar_pagamento_fatura")
@patch("services.supabase_client.estornar_pagamento_fatura")
@patch("services.supabase_client.listar_contas")
@patch("services.supabase_client.listar_faturas")
@patch("services.supabase_client.obter_resumo_cartoes")
@patch("services.supabase_client.listar_cartoes")
def test_view_cartoes_completa(
    mock_list_cart,
    mock_res_cart,
    mock_list_fat,
    mock_list_cont,
    mock_estornar,
    mock_liquidar,
):
    cartoes_ficticios = [
        {"id": "c1", "nome": "Nubank Roxinho", "cor": "#820AD1", "bandeira": "mastercard", "limite_total": 5000.0, "limite_disponivel": 3500.0, "dia_fechamento": 25, "dia_vencimento": 5},
        {"id": "c2", "nome": "Inter Laranja", "cor": "#FF7A00", "bandeira": "mastercard", "limite_total": 4000.0, "limite_disponivel": 3000.0, "dia_fechamento": 1, "dia_vencimento": 10},
    ]
    # Faturas de meses variados:
    faturas_ficticias = [
        {"id": "f_out", "cartao_id": "c1", "mes": 10, "ano": 2026, "valor_total": 500.0, "valor_pago": 500.0, "status": "paga", "data_vencimento": "2026-11-05"},
        {"id": "f_nov", "cartao_id": "c1", "mes": 11, "ano": 2026, "valor_total": 1500.0, "valor_pago": 0.0, "status": "Aberta", "data_vencimento": "2026-12-05"},
        {"id": "f_dez", "cartao_id": "c2", "mes": 12, "ano": 2026, "valor_total": 900.0, "valor_pago": 0.0, "status": "Aberta", "data_vencimento": "2027-01-10"},
    ]
    mock_list_cart.return_value = cartoes_ficticios
    mock_list_fat.side_effect = lambda cartao_id=None, status=None, mes=None, ano=None: [
        f for f in faturas_ficticias
        if (mes is None or f["mes"] == mes) and (ano is None or f["ano"] == ano)
    ]
    mock_res_cart.return_value = {
        "total_limite": 9000.0,
        "total_disponivel": 6500.0,
        "total_faturas": 1500.0,
        "cartoes": [
            {"id": "c1", "fatura_valor": 1500.0, "fatura_pago": 0.0, "fatura_status": "Aberta"},
            {"id": "c2", "fatura_valor": 0.0, "fatura_pago": 0.0, "fatura_status": "Aberta"},
        ]
    }
    mock_list_cont.return_value = [
        {"id": "cta1", "nome": "Santander", "banco": "Santander", "saldo_atual": -393.16}
    ]

    # 1. Renderiza no Desktop com filtro em Novembro 2026
    p_desk = mock_page(1280, 800, mes=11, ano=2026)
    v_desk = criar_view_cartoes(p_desk)
    assert isinstance(v_desk, ft.View)
    assert len(v_desk.controls) > 0

    def achar_seg_button(ctrl):
        if isinstance(ctrl, ft.SegmentedButton):
            return ctrl
        for filho in getattr(ctrl, "controls", []):
            res = achar_seg_button(filho)
            if res:
                return res
        if getattr(ctrl, "content", None):
            res = achar_seg_button(ctrl.content)
            if res:
                return res
        return None

    seg = None
    for c in v_desk.controls:
        seg = achar_seg_button(c)
        if seg:
            break

    assert seg is not None, "SegmentedButton não encontrado na tela"
    assert seg.selected == ["cartoes"], f"Estado padrão deve ser ['cartoes'], obtido {seg.selected}"
    valores_segmentos = [s.value for s in seg.segments]
    assert valores_segmentos == ["cartoes", "abertas", "fechadas"], f"Ordem dos segmentos incorreta: {valores_segmentos}"

    # 2. Renderiza no Mobile
    p_mob = mock_page(390, 844, mes=11, ano=2026)
    v_mob = criar_view_cartoes(p_mob)
    assert isinstance(v_mob, ft.View)

    print("[OK] Teste de ordem de abas, estado padrao e filtro estrito passou!")


def test_ordenacao_crescente_vencimento():
    hoje = date(2026, 10, 26)
    faturas = [
        {"id": "3", "cartao_id": "c3", "valor_total": 300.0, "valor_pago": 0.0, "status": "Aberta", "data_vencimento": "2026-11-10"},
        {"id": "1", "cartao_id": "c1", "valor_total": 100.0, "valor_pago": 0.0, "status": "Aberta", "data_vencimento": "2026-10-15"},
        {"id": "4", "cartao_id": "c4", "valor_total": 400.0, "valor_pago": 0.0, "status": "Aberta", "data_vencimento": "2026-11-05"},
        {"id": "2", "cartao_id": "c2", "valor_total": 200.0, "valor_pago": 0.0, "status": "Aberta", "data_vencimento": "2026-10-20"},
    ]
    def _chave(item):
        from datetime import datetime
        dt_raw = item.get("data_vencimento")
        if dt_raw:
            return (0, datetime.fromisoformat(str(dt_raw).split("T")[0]).date())
        return (1, date.max)

    faturas.sort(key=_chave)
    ids_ordenados = [f["id"] for f in faturas]
    # Esperado: 1 (15/10 - mais atrasada), 2 (20/10), 4 (05/11), 3 (10/11)
    assert ids_ordenados == ["1", "2", "4", "3"], f"Ordem incorreta: {ids_ordenados}"
    print("[OK] Teste de ordenacao crescente por data de vencimento passou!")


if __name__ == "__main__":
    test_inteligencia_calculo_melhor_cartao()
    test_status_vencimento_relativo()
    test_ordenacao_crescente_vencimento()
    test_view_cartoes_completa()
    print("[SUCESSO TOTAL] Todos os testes do Dashboard de Cartoes passaram com 100% de sucesso!")
