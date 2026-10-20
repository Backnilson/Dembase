"""
=============================================================================
DemBase v3 — test_custom_date_picker.py
Testes unitários e de integração para os novos componentes de seleção de data
e período estilo Mobills (Flet 1.0.1).
=============================================================================
"""
import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import flet as ft
from views.widgets.custom_date_picker import (
    CustomCalendarGrid,
    abrir_seletor_data_modal,
    abrir_modal_periodo_mobills,
    CampoSeletorData,
    formatar_data_amigavel,
    formatar_data_curta_amigavel,
    MESES_PT,
    MESES_CURTOS_PT,
)
from views.widgets.lancamento_form import LancamentoForm
from core.lancamento_state import LancamentoFormState
from views.widgets.date_filter import DateFilterBar
from views.shell_view import criar_shell


def mock_page():
    page = MagicMock(spec=ft.Page)
    page.width = 1280
    page.height = 800
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
    page.navigate = MagicMock()
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    return page


def test_formatadores():
    print("--- Testando formatadores de data amigável ---")
    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    amanha = hoje + timedelta(days=1)
    outra = date(2026, 10, 20)

    assert "Hoje" in formatar_data_amigavel(hoje), "Deveria conter 'Hoje'"
    assert "Ontem" in formatar_data_amigavel(ontem), "Deveria conter 'Ontem'"
    assert "Amanhã" in formatar_data_amigavel(amanha), "Deveria conter 'Amanhã'"
    assert formatar_data_curta_amigavel(hoje) == "Hoje"
    assert formatar_data_curta_amigavel(ontem) == "Ontem"
    assert formatar_data_curta_amigavel(amanha) == "Amanhã"
    print("[OK] Formatadores testados com sucesso.")


def test_custom_calendar_grid():
    print("--- Testando CustomCalendarGrid ---")
    data_sel = [None]
    def on_click(d):
        data_sel[0] = d

    cal = CustomCalendarGrid(
        ano=2026,
        mes=10,
        data_selecionada=date(2026, 10, 20),
        modo="single",
        on_date_click=on_click,
    )
    assert cal.ano == 2026
    assert cal.mes == 10
    assert len(cal.col_dias.controls) > 1, "Deveria ter cabeçalho e semanas"

    # Teste de navegação de mês
    cal._mudar_mes(1)
    assert cal.mes == 11
    cal._mudar_mes(-1)
    assert cal.mes == 10

    # Teste de clique em dia
    cal._clicar_dia(date(2026, 10, 25))
    assert data_sel[0] == date(2026, 10, 25)
    assert cal.data_selecionada == date(2026, 10, 25)

    # Teste de modo range
    range_res = [None, None]
    def on_range(i, f):
        range_res[0], range_res[1] = i, f

    cal_range = CustomCalendarGrid(
        ano=2026,
        mes=10,
        range_inicio=date(2026, 10, 5),
        range_fim=date(2026, 10, 15),
        modo="range",
        on_range_change=on_range,
    )
    # Clica no início
    cal_range._clicar_dia(date(2026, 10, 8))
    assert cal_range.range_inicio == date(2026, 10, 8)
    assert cal_range.range_fim is None

    # Clica no fim
    cal_range._clicar_dia(date(2026, 10, 22))
    assert cal_range.range_inicio == date(2026, 10, 8)
    assert cal_range.range_fim == date(2026, 10, 22)

    # Teste de toggle de visão rápida de 12 meses
    cal._toggle_visao_meses()
    assert cal.mostrar_grade_meses is True
    assert cal.col_meses.visible is True
    assert cal.col_dias.visible is False
    cal._selecionar_mes_direto(3)
    assert cal.mes == 3
    assert cal.mostrar_grade_meses is False
    print("[OK] CustomCalendarGrid testado com sucesso.")


def test_modais():
    print("--- Testando Modais de Data e Período ---")
    page = mock_page()

    # 1. Modal de data única
    data_escolhida = [None]
    abrir_seletor_data_modal(
        page=page,
        data_inicial=date(2026, 10, 20),
        on_select=lambda d: data_escolhida.__setitem__(0, d),
    )
    assert page.show_dialog.called
    dialog_arg = page.show_dialog.call_args[0][0]
    assert isinstance(dialog_arg, ft.AlertDialog)

    # 2. Modal de período Mobills
    periodo_escolhido = [None]
    estado_p = {
        "modo": "mes",
        "data_inicio": date(2026, 10, 1),
        "data_fim": date(2026, 10, 31),
        "mes": 10,
        "ano": 2026,
        "dia_ciclo": 1,
    }
    abrir_modal_periodo_mobills(
        page=page,
        estado_periodo=estado_p,
        on_confirm=lambda res: periodo_escolhido.__setitem__(0, res),
    )
    assert page.show_dialog.call_count == 2
    print("[OK] Modais instanciados com sucesso.")


def test_lancamento_form_integracao():
    print("--- Testando LançamentoForm com novo seletor de data ---")
    page = mock_page()
    state = LancamentoFormState()

    with patch("services.supabase_client.listar_contas", return_value=[]), \
         patch("services.supabase_client.listar_cartoes", return_value=[]), \
         patch("services.supabase_client.listar_categorias", return_value=[]):
        form = LancamentoForm(page, state)

        # Verifica atributos de data
        assert hasattr(form, "card_seletor_data")
        assert hasattr(form, "row_chips_data")
        assert hasattr(form, "txt_data_label")

        # Testa seleção rápida de data (Ontem)
        ontem = date.today() - timedelta(days=1)
        form._selecionar_data_rapida(ontem)
        assert state.data_selecionada == ontem
        assert "Ontem" in form.txt_data_label.value

        # Testa abertura do modal
        form._abrir_seletor_data()
        assert page.show_dialog.called

    print("[OK] LançamentoForm integrado e verificado com sucesso.")


def test_date_filter_bar_integracao():
    print("--- Testando DateFilterBar com seletor customizado ---")
    page = mock_page()
    dfb = DateFilterBar()
    dfb._page = page

    # Mock page property para retornar mock_page
    with patch.object(ft.Control, "page", new_callable=lambda: property(lambda self: page)):
        dfb._abrir_picker()
        assert page.show_dialog.called
        dlg = page.show_dialog.call_args[0][0]
        assert isinstance(dlg, ft.AlertDialog)

    print("[OK] DateFilterBar integrado e verificado com sucesso.")


def test_shell_view_periodo_modal():
    print("--- Testando ShellView com abrir_modal_periodo_mobills ---")
    page = mock_page()
    with patch("services.supabase_client.listar_contas", return_value=[]):
        shell = criar_shell(page, rota_ativa="/dashboard", conteudo=ft.Text("Conteúdo"))
        assert isinstance(shell, ft.View)

    print("[OK] ShellView integrado e verificado com sucesso.")


def main():
    print("\n==============================================================================")
    print("DEMBASE v3 — TESTES DO NOVO SELETOR DE DATAS E PERÍODOS (MOBILLS STYLE)")
    print("==============================================================================")
    test_formatadores()
    test_custom_calendar_grid()
    test_modais()
    test_lancamento_form_integracao()
    test_date_filter_bar_integracao()
    test_shell_view_periodo_modal()
    print("\n==============================================================================")
    print("TODOS OS TESTES DE DATAS E CALENDÁRIO PASSARAM COM 100% DE SUCESSO!")
    print("==============================================================================\n")


if __name__ == "__main__":
    main()
