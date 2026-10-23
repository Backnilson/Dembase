"""
=============================================================================
DemBase v3 — test_mascara_moeda_e_recorrencia_cartao.py (Flet 1.0.1)
Validação completa de:
1. Máscara de Moeda Dinâmica (Input de Valor estilo app bancário, da direita para a esquerda)
2. Recorrência Contínua no Cartão de Crédito (UI SegmentedButton, state machine e salvamento)
=============================================================================
"""
from datetime import date
from unittest.mock import MagicMock, patch
import flet as ft

from core.lancamento_state import LancamentoFormState
from views.widgets.lancamento_form import LancamentoForm, formatar_moeda_input
from views.widgets.lancamento_sheet import abrir_lancamento
import services.supabase_client as db


def mock_page(width=1280, height=800):
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.route = "/dashboard"
    page.views = []
    page.overlay = []
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


def test_formatador_moeda_helper():
    print("--- Teste 1: Helper de Formatação de Moeda ---")
    assert formatar_moeda_input(0.0) == "0,00"
    assert formatar_moeda_input(0.01) == "0,01"
    assert formatar_moeda_input(0.12) == "0,12"
    assert formatar_moeda_input(1.23) == "1,23"
    assert formatar_moeda_input(12.34) == "12,34"
    assert formatar_moeda_input(123.45) == "123,45"
    assert formatar_moeda_input(1234.56) == "1.234,56"
    assert formatar_moeda_input(1000000.0) == "1.000.000,00"
    print("[OK] Helper formatar_moeda_input validado com sucesso.")


def test_mascara_moeda_dinamica_input():
    print("--- Teste 2: Digitação Dinâmica no Input de Valor (Estilo App Bancário) ---")
    page = mock_page()
    state = LancamentoFormState()

    with patch("services.supabase_client.listar_contas", return_value=[]), \
         patch("services.supabase_client.listar_cartoes", return_value=[]), \
         patch("services.supabase_client.listar_categorias", return_value=[]):
        form = LancamentoForm(page, state)

        # 1. Digita "1" -> vira 0,01
        ev = MagicMock()
        ev.control.value = "1"
        form._ao_mudar_valor(ev)
        assert form.txt_valor.value == "0,01"
        assert state.valor == 0.01

        # 2. Digita "2" a seguir (buffer "0,012") -> vira 0,12
        ev.control.value = "0,012"
        form._ao_mudar_valor(ev)
        assert form.txt_valor.value == "0,12"
        assert state.valor == 0.12

        # 3. Digita "3" (buffer "0,123") -> vira 1,23
        ev.control.value = "0,123"
        form._ao_mudar_valor(ev)
        assert form.txt_valor.value == "1,23"
        assert state.valor == 1.23

        # 4. Digita "4" (buffer "1,234") -> vira 12,34
        ev.control.value = "1,234"
        form._ao_mudar_valor(ev)
        assert form.txt_valor.value == "12,34"
        assert state.valor == 12.34

        # 5. Digita "5" e "6" (buffer "12,3456") -> vira 1.234,56
        ev.control.value = "12,3456"
        form._ao_mudar_valor(ev)
        assert form.txt_valor.value == "1.234,56"
        assert state.valor == 1234.56

        # 6. Usuário aperta Backspace (apaga último dígito: "1.234,5") -> vira 123,45
        ev.control.value = "1.234,5"
        form._ao_mudar_valor(ev)
        assert form.txt_valor.value == "123,45"
        assert state.valor == 123.45

        # 7. Apaga tudo (campo vazio "") -> vira 0,00
        ev.control.value = ""
        form._ao_mudar_valor(ev)
        assert form.txt_valor.value == "0,00"
        assert state.valor == 0.0

    print("[OK] Máscara de moeda em tempo real validada da direita para a esquerda.")


def test_state_machine_credito_recorrencia():
    print("--- Teste 3: Máquina de Estado para Crédito e Recorrência ---")
    st = LancamentoFormState()
    st.mudar_tipo("Despesa")
    st.mudar_forma("Crédito")
    assert st.eh_credito is True

    # 1. Compra à vista no cartão (quantidade=1, is_fixa=False)
    st.quantidade = 1
    st.is_fixa = False
    assert st.modo_recorrencia() == "unica"

    # 2. Compra parcelada no cartão (quantidade=3, is_fixa=False)
    st.quantidade = 3
    st.is_fixa = False
    assert st.modo_recorrencia() == "parcelada"

    # 3. Assinatura / Recorrência Contínua no cartão (is_fixa=True)
    st.alternar_fixa(True)
    assert st.is_fixa is True
    assert st.quantidade == 1
    assert st.modo_recorrencia() == "fixa"

    # 4. Voltar para parcelas
    st.alternar_fixa(False)
    st.quantidade = 6
    assert st.modo_recorrencia() == "parcelada"

    print("[OK] LancamentoFormState gerencia modos de crédito perfeitamente.")


def test_ui_lancamento_form_credito_recorrencia():
    print("--- Teste 4: Interface do LancamentoForm com SegmentedButton de Crédito ---")
    page = mock_page()
    state = LancamentoFormState()
    state.mudar_tipo("Despesa")
    state.mudar_forma("Crédito")

    with patch("services.supabase_client.listar_contas", return_value=[]), \
         patch("services.supabase_client.listar_cartoes", return_value=[{"id": "card-1", "nome": "Nubank"}]), \
         patch("services.supabase_client.listar_categorias", return_value=[]):
        form = LancamentoForm(page, state)

        # Verifica se o container de crédito e o segmented button foram criados
        assert hasattr(form, "seg_credito_tipo")
        assert hasattr(form, "row_detalhe_parcelas")
        assert hasattr(form, "card_credito_recorrente_info")
        assert form.row_parcelas.visible is True

        # Modo inicial: parcelado
        assert "parcelado" in form.seg_credito_tipo.selected
        assert form.row_detalhe_parcelas.visible is True
        assert form.card_credito_recorrente_info.visible is False

        # Usuário clica no segmento "Recorrência"
        ev_seg = MagicMock()
        ev_seg.control.selected = ["recorrente"]
        form._ao_mudar_credito_tipo(ev_seg)

        # Estado e UI devem refletir recorrência contínua
        assert state.is_fixa is True
        assert state.modo_recorrencia() == "fixa"
        assert form.row_detalhe_parcelas.visible is False
        assert form.card_credito_recorrente_info.visible is True

        # Usuário clica de volta em "Parcelas"
        ev_seg.control.selected = ["parcelado"]
        form._ao_mudar_credito_tipo(ev_seg)
        assert state.is_fixa is False
        assert form.row_detalhe_parcelas.visible is True
        assert form.card_credito_recorrente_info.visible is False

    print("[OK] Alternância visual entre Parcelas e Recorrência no Cartão validada.")


def test_salvamento_recorrencia_cartao_sheet():
    print("--- Teste 5: Fluxo de Criação de Assinatura no Cartão via BottomSheet / Dialog ---")
    page = mock_page()

    with patch("services.supabase_client.listar_contas", return_value=[]), \
         patch("services.supabase_client.listar_cartoes", return_value=[{"id": "card-nubank", "nome": "Nubank"}]), \
         patch("services.supabase_client.listar_categorias", return_value=[{"id": "cat-lazer", "nome": "Lazer"}]), \
         patch("services.potes_service.carregar_potes", return_value=[{"id": "pote-prazeres", "nome": "Prazeres", "cor": "#FF7A00"}]), \
         patch("services.supabase_client.criar_lancamento_recorrente", return_value={"sucesso": True, "serie_id": "serie-123"}) as mock_criar:

        abrir_lancamento(
            page=page,
            cartao_inicial="card-nubank",
            pote_inicial="pote-prazeres",
        )
        assert page.show_dialog.called
        dialog = page.show_dialog.call_args[0][0]
        form = dialog.content.content
        assert isinstance(form, LancamentoForm)

        # Configura os dados da assinatura (ex: Netflix R$ 55,90)
        form.state.categoria_id = "cat-lazer"
        form.state.descricao = "Netflix"
        form.state.valor = 55.90
        form.state.is_fixa = True  # Marca como Assinatura / Recorrência

        # Recupera o botão de salvar do diálogo
        btn_salvar = None
        for a in dialog.actions:
            if isinstance(a, ft.FilledButton):
                btn_salvar = a
                break
        assert btn_salvar is not None

        # Simula o clique em salvar
        btn_salvar.on_click(MagicMock())

        # Valida que criar_lancamento_recorrente foi chamado com os parâmetros exatos
        assert mock_criar.called
        call_kwargs = mock_criar.call_args[1]
        assert call_kwargs["modo"] == "fixa"
        assert call_kwargs["valor_modo"] == "repetido"
        assert call_kwargs["dados"]["cartao_id"] == "card-nubank"
        assert call_kwargs["dados"]["forma_movimentacao"] == "Crédito"
        assert call_kwargs["dados"]["valor"] == 55.90
        assert call_kwargs["dados"]["pote_id"] == "pote-prazeres"

    print("[OK] Salvamento de assinatura contínua no cartão gravado no Supabase com sucesso.")


if __name__ == "__main__":
    test_formatador_moeda_helper()
    test_mascara_moeda_dinamica_input()
    test_state_machine_credito_recorrencia()
    test_ui_lancamento_form_credito_recorrencia()
    test_salvamento_recorrencia_cartao_sheet()
    print("=" * 60)
    print("TODOS OS TESTES DE MOEDA E RECORRÊNCIA PASSARAM COM 100%!")
    print("=" * 60)
