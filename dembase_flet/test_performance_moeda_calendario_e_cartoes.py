"""
=============================================================================
DemBase v3 — test_performance_moeda_calendario_e_cartoes.py (Flet 1.0.1)
Auditoria Automatizada de Ponta a Ponta das 3 Frentes:
1. Performance e Anti-Reentrância na Digitação de Moeda + Abertura Instantânea
   do Calendário (Pré-instanciação + 0 chamadas de rede na troca de data).
2. UX em Cartões de Crédito: Card inteiro clicável em "Meus Cartões",
   "Faturas Abertas" e "Faturas Fechadas" (com isolamento do botão PAGAR FATURA).
3. Função "Reajustar Valor Total da Fatura": Cálculo automático da diferença
   (+ acréscimo ou - desconto/estorno), lançamento automático na fatura,
   escolha de Pote Financeiro em 1 clique e atualização imediata via .update().
=============================================================================
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from core.lancamento_state import LancamentoFormState
from core.report_context import ReportContext
from services import supabase_client as db
from views.cartoes_view import criar_view_cartoes
from views.relatorios.cartao_report import criar_view_relatorio_cartao
from views.widgets.custom_date_picker import (
    CustomCalendarGrid,
    abrir_modal_periodo_mobills,
    abrir_seletor_data_modal,
)
from views.widgets.lancamento_form import LancamentoForm, formatar_moeda_input


def criar_mock_page(width: int = 1280, height: int = 800, mes: int = 11, ano: int = 2026) -> ft.Page:
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.platform = ft.PagePlatform.WINDOWS if width >= 768 else ft.PagePlatform.ANDROID
    page.views = []
    page.overlay = []
    page.dialog = None
    page.route = "/cartoes"

    session_store = {
        "periodo_modo": "mes",
        "periodo_mes": mes,
        "periodo_ano": ano,
        "periodo_inicio": date(ano, mes, 1).isoformat(),
        "periodo_fim": date(ano, mes, 30 if mes in (4, 6, 9, 11) else 31).isoformat(),
        "mes": mes,
        "ano": ano,
        "data_inicio": date(ano, mes, 1),
        "data_fim": date(ano, mes, 30 if mes in (4, 6, 9, 11) else 31),
    }
    page.session = session_store

    page.client_storage = MagicMock()
    page.client_storage.get.side_effect = lambda k: session_store.get(k)
    page.client_storage.set.side_effect = lambda k, v: session_store.update({k: v})

    page.navigate = MagicMock(side_effect=lambda r: setattr(page, "route", r))
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    page.run_task = MagicMock()
    return page


def test_1_digitacao_rapida_moeda_sem_lag_ou_reentrancia():
    print("--- 1. Testando Digitação Rápida de Valores (Vírgula Automática Sem Lag/Loops) ---")
    page = criar_mock_page()
    state = LancamentoFormState()
    state.mudar_tipo("Despesa")
    state.mudar_forma("Crédito")
    state.cartao_id = "card-mp"

    with patch("services.supabase_client.listar_contas", return_value=[]), \
         patch("services.supabase_client.listar_cartoes", return_value=[{"id": "card-mp", "nome": "MercadoPago"}]), \
         patch("services.supabase_client.listar_categorias", return_value=[{"id": "cat-1", "nome": "Outros"}]), \
         patch("services.supabase_client.listar_faturas_opcoes_cartao", return_value=[]) as mock_faturas_opts:

        form = LancamentoForm(page, state)
        assert mock_faturas_opts.call_count == 1, (
            f"listar_faturas_opcoes_cartao deve ser chamado apenas 1 vez na inicialização, não {mock_faturas_opts.call_count}!"
        )

        # Mock update específico do txt_valor para provar atualização cirúrgica (sem page.update)
        form.txt_valor.update = MagicMock()
        form.lbl_resumo_parcelas.update = MagicMock()
        page.update.reset_mock()

        # Simula foco no campo de valor: NÃO deve disparar .update() nem limpar o campo causando corrida
        form._ao_focar_valor(MagicMock())
        assert form.txt_valor.update.call_count == 0
        assert page.update.call_count == 0

        # Simula digitação rápida dígito a dígito: 3 -> 4 -> 1 -> 6 -> 8 (R$ 341,68)
        sequencia = [
            ("3", "0,03", 0.03),
            ("0,034", "0,34", 0.34),
            ("0,341", "3,41", 3.41),
            ("3,416", "34,16", 34.16),
            ("34,168", "341,68", 341.68),
        ]
        t0 = time.perf_counter()
        for raw_in, esperado_str, esperado_val in sequencia:
            ev = MagicMock()
            ev.control.value = raw_in
            form._ao_mudar_valor(ev)
            assert form.txt_valor.value == esperado_str, f"Esperado {esperado_str}, obteve {form.txt_valor.value}"
            assert abs(state.valor - esperado_val) < 1e-6

            # Simula eco reentrante do WebSocket com o valor já formatado: deve ser ignorado em 0ms!
            updates_antes = form.txt_valor.update.call_count
            ev_reentrante = MagicMock()
            ev_reentrante.control.value = esperado_str
            form._ao_mudar_valor(ev_reentrante)
            assert form.txt_valor.update.call_count == updates_antes, "Reentrância não deve disparar novo .update()!"

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        assert page.update.call_count == 0, "Digitar no campo de valor NUNCA deve chamar page.update() inteiro!"
        assert mock_faturas_opts.call_count == 1, "Digitar valor nunca deve consultar banco!"

        # Simula sair do campo (on_blur) quando já está formatado -> 0 updates extras
        updates_antes_blur = form.txt_valor.update.call_count
        form._ao_sair_do_valor(MagicMock())
        assert form.txt_valor.update.call_count == updates_antes_blur

    print(f"  [OK] 10 eventos de digitação + anti-reentrância processados em {elapsed_ms:.2f}ms com 0 page.update()!")


def test_2_abertura_instantanea_calendario_sem_bloqueio():
    print("--- 2. Testando Pré-Instanciação e Abertura Instantânea do Calendário ---")
    page = criar_mock_page()
    state = LancamentoFormState()
    state.mudar_tipo("Despesa")
    state.mudar_forma("Crédito")
    state.cartao_id = "card-mp"

    with patch("services.supabase_client.listar_contas", return_value=[]), \
         patch("services.supabase_client.listar_cartoes", return_value=[{"id": "card-mp", "nome": "MercadoPago"}]), \
         patch("services.supabase_client.listar_categorias", return_value=[{"id": "cat-1", "nome": "Outros"}]), \
         patch("services.supabase_client.listar_faturas_opcoes_cartao", return_value=[]) as mock_faturas_opts:

        form = LancamentoForm(page, state)

        # Verifica que o modal de calendário já foi pré-instanciado na inicialização do formulário
        cache_cal = getattr(page, "_dembase_seletor_data_cache", None)
        assert isinstance(cache_cal, dict) and isinstance(cache_cal.get("dlg"), ft.AlertDialog)
        dlg_ref_original = cache_cal["dlg"]
        grid_ref_original: CustomCalendarGrid = cache_cal["grid_cal"]
        celulas_originais = [id(c) for c, _ in grid_ref_original._celulas_dias]

        # Abre o calendário 5 vezes seguidas e navega entre meses
        t0 = time.perf_counter()
        for i in range(5):
            form._abrir_seletor_data()
            assert page.show_dialog.call_args[0][0] is dlg_ref_original, "Deve reutilizar o mesmo AlertDialog pré-instanciado!"
            grid_ref_original._mudar_mes(1)
            grid_ref_original._mudar_mes(-1)
            # Simula confirmação de uma nova data no calendário
            nova_dt = date.today() - timedelta(days=i)
            cb = cache_cal["estado"]["on_select"]
            cb(nova_dt)
            assert form.state.data_selecionada == nova_dt

        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        celulas_depois = [id(c) for c, _ in grid_ref_original._celulas_dias]
        assert celulas_originais == celulas_depois, "As 42 células do calendário devem ser atualizadas in-place sem recriação!"
        assert mock_faturas_opts.call_count == 1, "Trocar a data no calendário NÃO deve disparar queries de faturas!"

        # Também testa abrir_modal_periodo_mobills repetidas vezes (reutilizando grid_range)
        est_p = {
            "modo": "mes",
            "data_inicio": date(2026, 11, 1),
            "data_fim": date(2026, 11, 30),
            "mes": 11,
            "ano": 2026,
            "dia_ciclo": 1,
        }
        abrir_modal_periodo_mobills(page, est_p, on_confirm=lambda _: None)
        grid_range_1 = getattr(page, "_dembase_grid_range_cache", None)
        assert isinstance(grid_range_1, CustomCalendarGrid)
        abrir_modal_periodo_mobills(page, est_p, on_confirm=lambda _: None)
        grid_range_2 = getattr(page, "_dembase_grid_range_cache", None)
        assert grid_range_1 is grid_range_2, "Modal de período deve reutilizar a instância de CustomCalendarGrid!"

    print(f"  [OK] 5 aberturas seguidas do calendário + navegação de meses executadas em {elapsed_ms:.2f}ms!")


def test_3_card_inteiro_clicavel_faturas_abertas_e_isolamento_botao_pagar():
    print("--- 3. Testando Card Inteiro Clicável em Faturas Abertas/Meus Cartões/Fechadas ---")
    page = criar_mock_page(width=1280, height=800, mes=11, ano=2026)

    mock_cartoes = [
        {"id": "card-mp", "nome": "MercadoPago", "cor": "#009EE3", "bandeira": "mastercard", "dia_fechamento": 16, "dia_vencimento": 23, "limite_total": 1000.0, "limite_disponivel": 658.32},
        {"id": "card-itau", "nome": "Itau", "cor": "#003399", "bandeira": "mastercard", "dia_fechamento": 16, "dia_vencimento": 23, "limite_total": 3100.0, "limite_disponivel": 1906.27},
        {"id": "card-inter", "nome": "Inter", "cor": "#FF7A00", "bandeira": "mastercard", "dia_fechamento": 24, "dia_vencimento": 1, "limite_total": 5000.0, "limite_disponivel": 4879.10},
    ]
    mock_faturas_nov = [
        {"id": "fat-mp-nov", "cartao_id": "card-mp", "mes": 11, "ano": 2026, "valor_total": 341.68, "valor_pago": 0.0, "status": "aberta", "data_vencimento": "2026-11-23"},
        {"id": "fat-itau-nov", "cartao_id": "card-itau", "mes": 11, "ano": 2026, "valor_total": 1193.73, "valor_pago": 0.0, "status": "aberta", "data_vencimento": "2026-11-23"},
        {"id": "fat-inter-nov", "cartao_id": "card-inter", "mes": 11, "ano": 2026, "valor_total": 120.90, "valor_pago": 120.90, "status": "paga", "data_vencimento": "2026-11-01", "data_pagamento": "2026-11-01"},
    ]

    with patch.object(db, "listar_cartoes", return_value=mock_cartoes), \
         patch.object(db, "listar_faturas", side_effect=lambda mes=None, ano=None, **kw: mock_faturas_nov if mes == 11 else []), \
         patch.object(db, "obter_resumo_cartoes", return_value={"cartoes": []}), \
         patch.object(db, "listar_contas", return_value=[{"id": "cta-1", "nome": "Inter Conta", "saldo_atual": 2000.0}]):

        view = criar_view_cartoes(page)

        # Localiza SegmentedButton e grid_conteudo
        def achar_controle(ctrl, pred):
            if pred(ctrl):
                return ctrl
            for f in getattr(ctrl, "controls", []) or []:
                r = achar_controle(f, pred)
                if r is not None:
                    return r
            if getattr(ctrl, "content", None) is not None:
                return achar_controle(ctrl.content, pred)
            return None

        seg = achar_controle(view, lambda c: isinstance(c, ft.SegmentedButton))
        grid = achar_controle(view, lambda c: isinstance(c, ft.ResponsiveRow) and len(getattr(c, "controls", [])) == 3 and all(isinstance(x, ft.Container) and x.col == {"xs": 12, "sm": 6, "md": 4} for x in c.controls))
        assert seg is not None and grid is not None

        # 3.1 Aba "Meus Cartões": Verifica que os 3 cards inteiros são clicáveis
        for card_c in grid.controls:
            assert callable(card_c.on_click), "Card em 'Meus Cartões' deve ter on_click no Container principal!"
            assert card_c.ink is True
            assert callable(card_c.on_hover)

        # 3.2 Muda para a aba "Faturas Abertas"
        seg.selected = ["abertas"]
        seg.on_change(MagicMock(control=seg))

        cards_abertas = [c for c in grid.controls if isinstance(c, ft.Container) and c.col == {"xs": 12, "sm": 6, "md": 4}]
        assert len(cards_abertas) == 2, f"Deveria haver 2 faturas abertas (MercadoPago e Itau), encontrou {len(cards_abertas)}"

        card_mp = cards_abertas[0]
        assert callable(card_mp.on_click), "Card inteiro de MercadoPago em 'Faturas Abertas' deve ser clicável!"
        assert card_mp.ink is True
        assert callable(card_mp.on_hover)

        # Clicar no card do MercadoPago deve navegar direto para /cartoes/card-mp?fatura=fat-mp-nov
        page.navigate.reset_mock()
        card_mp.on_click(MagicMock())
        assert page.navigate.called, "Clicar no card deve navegar para Fatura & Extrato!"
        rota_nav = page.navigate.call_args[0][0]
        assert "/cartoes/card-mp" in rota_nav and "fatura=fat-mp-nov" in rota_nav, f"Rota inesperada: {rota_nav}"

        # Clicar no botão verde PAGAR FATURA dentro do card deve abrir o modal de pagamento isoladamente!
        btn_pagar = achar_controle(card_mp, lambda c: isinstance(c, ft.FilledButton))
        assert btn_pagar is not None
        page.navigate.reset_mock()
        page.show_dialog.reset_mock()
        btn_pagar.on_click(MagicMock())
        assert page.show_dialog.called, "Botão PAGAR FATURA deve abrir o modal de pagamento!"
        assert not page.navigate.called, "Botão PAGAR FATURA NÃO deve navegar para outra rota!"

        # 3.3 Muda para a aba "Faturas Fechadas"
        seg.selected = ["fechadas"]
        seg.on_change(MagicMock(control=seg))
        cards_fechadas = [c for c in grid.controls if isinstance(c, ft.Container) and c.col == {"xs": 12, "sm": 6, "md": 4}]
        assert len(cards_fechadas) == 1
        card_inter = cards_fechadas[0]
        assert callable(card_inter.on_click), "Card em 'Faturas Fechadas' também deve ser inteiramente clicável!"
        page.navigate.reset_mock()
        card_inter.on_click(MagicMock())
        assert "/cartoes/card-inter" in page.navigate.call_args[0][0]

    print("  [OK] Cards inteiros clicáveis em 'Meus Cartões', 'Faturas Abertas' e 'Faturas Fechadas' validados!")


def test_4_reajustar_valor_total_fatura_positivo_e_negativo():
    print("--- 4. Testando Função 'Reajustar Valor Total da Fatura' (Serviço + UI Fatura & Extrato) ---")
    # 4.1 Teste unitário de db.reajustar_valor_fatura (+ R$ 8,32 e - R$ 11,68)
    with patch.object(db, "obter_fatura_por_id", return_value={"id": "fat-mp-nov", "mes": 11, "ano": 2026, "status": "aberta", "data_fechamento": "2026-11-16"}), \
         patch.object(db, "listar_potes", return_value=[{"id": "pote-semi", "nome": "Custos Semi Fixos", "posicao": 2}]), \
         patch.object(db, "listar_categorias", return_value=[{"id": "cat-outros", "nome": "Outros"}]), \
         patch.object(db, "obter_cartao", return_value={"id": "card-mp", "nome": "MercadoPago", "membro_id": "membro-1"}), \
         patch.object(db, "criar_lancamento") as mock_criar_lanc, \
         patch.object(db, "recalcular_totais_faturas") as mock_recalc:

        mock_resp = MagicMock()
        mock_resp.data = [{"id": "lanc-ajuste-1", "valor": 8.32, "descricao": "Ajuste de Fatura"}]
        mock_criar_lanc.return_value = mock_resp

        # Caso A: Fatura está em R$ 341,68 e o valor real no banco é R$ 350,00 -> Diferença = +R$ 8,32
        res_pos = db.reajustar_valor_fatura(
            cartao_id="card-mp",
            fatura_id="fat-mp-nov",
            mes=11,
            ano=2026,
            valor_atual=341.68,
            novo_valor_total=350.00,
            pote_id="pote-semi",
        )
        assert res_pos["sucesso"] is True
        assert res_pos["diferenca"] == 8.32
        assert res_pos["novo_valor_total"] == 350.00
        dados_enviados = mock_criar_lanc.call_args[0][0]
        assert dados_enviados["cartao_id"] == "card-mp"
        assert dados_enviados["fatura_id"] == "fat-mp-nov"
        assert dados_enviados["valor"] == 8.32
        assert dados_enviados["pote_id"] == "pote-semi"
        assert dados_enviados["descricao"] == "Ajuste de Fatura"
        assert dados_enviados["forma_movimentacao"] == "Crédito"
        assert mock_recalc.called

        # Caso B: Fatura está em R$ 341,68 e o valor real no banco é R$ 330,00 -> Diferença = -R$ 11,68 (Desconto)
        res_neg = db.reajustar_valor_fatura(
            cartao_id="card-mp",
            fatura_id="fat-mp-nov",
            mes=11,
            ano=2026,
            valor_atual=341.68,
            novo_valor_total=330.00,
            pote_id="pote-semi",
        )
        assert res_neg["sucesso"] is True
        assert res_neg["diferenca"] == -11.68
        dados_neg = mock_criar_lanc.call_args[0][0]
        assert dados_neg["valor"] == -11.68
        assert "Desconto" in dados_neg["descricao"]

    # 4.2 Teste de integração na UI de Fatura & Extrato (cartao_report.py)
    page = criar_mock_page(width=1280, height=800, mes=11, ano=2026)

    def _run_task_imediato(coro_fn, *args):
        coro = coro_fn(*args) if callable(coro_fn) else coro_fn
        asyncio.run(coro)

    page.run_task = MagicMock(side_effect=_run_task_imediato)

    pacote_mp = {
        "cartao": {"id": "card-mp", "nome": "MercadoPago", "cor": "#009EE3", "limite_total": 1000.0, "limite_disponivel": 658.32},
        "kpis": {"total_gasto_periodo": 341.68, "limite_total": 1000.0, "limite_disponivel": 658.32, "total_a_vista": 53.79, "total_parcelado": 287.89},
        "fatura_selecionada": {"id": "fat-mp-nov", "mes": 11, "ano": 2026, "status": "aberta", "valor_total": 341.68, "valor_pago": 0.0},
        "faturas": [{"id": "fat-mp-nov", "mes": 11, "ano": 2026, "status": "aberta", "valor_total": 341.68, "valor_pago": 0.0}],
        "lancamentos": [
            {"id": "l1", "tipo": "Despesa", "valor": 341.68, "data": "2026-11-10", "descricao": "Compras MP", "total_parcelas": 1}
        ],
        "total_registros": 1,
    }

    with patch.object(db, "obter_ou_criar_fatura_por_mes_ano", return_value={"id": "fat-mp-nov", "mes": 11, "ano": 2026}), \
         patch.object(db, "obter_relatorio_cartao_async", return_value=pacote_mp), \
         patch.object(db, "listar_faturas_opcoes_cartao", return_value=[{"id": "fat-mp-nov", "fatura_id_real": "fat-mp-nov", "mes": 11, "ano": 2026, "label": "Novembro/2026 (Aberta)"}]), \
         patch.object(db, "reajustar_valor_fatura", return_value={"sucesso": True, "fatura_id": "fat-mp-nov", "diferenca": 8.32, "novo_valor_total": 350.00}) as mock_reajustar_ui:

        ctx = ReportContext(cartao_id="card-mp", data_inicio=date(2026, 11, 1), data_fim=date(2026, 11, 30))
        view = criar_view_relatorio_cartao(page, {"cartao_id": "card-mp"}, ctx)

        def achar_botao_reajustar(ctrl):
            if isinstance(ctrl, ft.OutlinedButton):
                for sub in getattr(ctrl.content, "controls", []) or []:
                    if isinstance(sub, ft.Text) and "Reajustar Fatura" in str(sub.value):
                        return ctrl
            for f in getattr(ctrl, "controls", []) or []:
                r = achar_botao_reajustar(f)
                if r is not None:
                    return r
            if getattr(ctrl, "content", None) is not None:
                return achar_botao_reajustar(ctrl.content)
            return None

        btn_reaj = achar_botao_reajustar(view)
        assert btn_reaj is not None, "Botão 'Reajustar Fatura' deve estar presente na tela Fatura & Extrato!"

        # Clica em "Reajustar Fatura" -> abre o modal
        page.show_dialog.reset_mock()
        btn_reaj.on_click(MagicMock())
        assert page.show_dialog.called
        modal_reaj = page.show_dialog.call_args[0][0]
        assert isinstance(modal_reaj, ft.AlertDialog)

        # Localiza o TextField do Novo Valor Total dentro do modal e digita "35000" (R$ 350,00)
        col_modal = modal_reaj.content.content
        txt_novo = next(c for c in col_modal.controls if isinstance(c, ft.TextField))
        assert isinstance(txt_novo, ft.TextField)
        ev_dig = MagicMock()
        ev_dig.control.value = "35000"
        txt_novo.on_change(ev_dig)
        assert txt_novo.value == "350,00"

        # Confirma o reajuste
        btn_conf = modal_reaj.actions[1]
        btn_conf.on_click(MagicMock())
        assert mock_reajustar_ui.called
        args_chamada = mock_reajustar_ui.call_args[0]
        assert args_chamada[0] == "card-mp"
        assert args_chamada[4] == 341.68
        assert args_chamada[5] == 350.00

    print("  [OK] Reajuste de Fatura (+R$ 8,32 e -R$ 11,68) e integração com Fatura & Extrato validados!")


if __name__ == "__main__":
    print("=" * 75)
    print("INICIANDO AUDITORIA COMPLETA: MOEDA, CALENDÁRIO E CARTÕES DE CRÉDITO")
    print("=" * 75)
    test_1_digitacao_rapida_moeda_sem_lag_ou_reentrancia()
    test_2_abertura_instantanea_calendario_sem_bloqueio()
    test_3_card_inteiro_clicavel_faturas_abertas_e_isolamento_botao_pagar()
    test_4_reajustar_valor_total_fatura_positivo_e_negativo()
    print("=" * 75)
    print("🎉 TODOS OS TESTES PASSARAM COM 100% DE SUCESSO E ZERO REGRESSÕES!")
    print("=" * 75)
