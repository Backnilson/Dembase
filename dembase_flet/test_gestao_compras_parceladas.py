"""
=============================================================================
DemBase v3 — test_gestao_compras_parceladas.py
Testes unitários e de integração para a Gestão Avançada de Compras Parceladas:
1. Efeito Cascata na Mudança de Fatura (Shift de Período)
2. Redimensionamento de Parcelas (Redução Segura e Extensão)
3. Reatividade de UI e Badges em LancamentoForm e LancamentoSheet (Flet 1.0.1)
=============================================================================
"""
import unittest
from unittest.mock import MagicMock, patch
from datetime import date
import flet as ft

from core.lancamento_state import LancamentoFormState
import services.supabase_client as db
from views.widgets.lancamento_form import LancamentoForm
from views.widgets.lancamento_sheet import abrir_lancamento


class TestGestaoComprasParceladas(unittest.TestCase):

    def test_01_estado_deteccao_compra_parcelada(self):
        """Verifica se o estado identifica corretamente uma compra parcelada."""
        # Despesa à vista no Pix
        st1 = LancamentoFormState(tipo="Despesa", forma_movimentacao="Pix", valor=100.0)
        self.assertFalse(st1.is_compra_parcelada)

        # Despesa no Cartão de Crédito com 3 parcelas
        st2 = LancamentoFormState(
            tipo="Despesa",
            forma_movimentacao="Crédito",
            valor=300.0,
            quantidade=3,
            serie_id="serie-uuid-123",
            parcela_atual=1,
            total_parcelas_original=3,
        )
        self.assertTrue(st2.is_compra_parcelada)
        self.assertFalse(st2.quantidade_parcelas_alterada)
        self.assertFalse(st2.fatura_foi_alterada)

        # Altera quantidade de parcelas de 3 para 5
        st2.quantidade = 5
        self.assertTrue(st2.quantidade_parcelas_alterada)

        # Altera fatura
        st2.fatura_id_original = "fat-antiga-id"
        st2.fatura_id = "fat-nova-id"
        self.assertTrue(st2.fatura_foi_alterada)

    def test_02_calculo_modo_parcela_vs_total(self):
        """Verifica precisão matemática nos modos de cálculo de parcela."""
        st = LancamentoFormState(
            tipo="Despesa",
            forma_movimentacao="Crédito",
            quantidade=10,
        )
        # Modo Total: define valor total R$ 1.000,00 -> parcela R$ 100,00
        st.modo_calculo_parcela = "total"
        st.definir_valor_total(1000.0)
        self.assertAlmostEqual(st.valor, 1000.0)
        self.assertAlmostEqual(st.obter_valor_parcela(), 100.0)

        # Modo Parcela: define parcela R$ 150,00 -> total R$ 1.500,00
        st.modo_calculo_parcela = "parcela"
        st.definir_valor_parcela(150.0)
        self.assertAlmostEqual(st.obter_valor_parcela(), 150.0)
        self.assertAlmostEqual(st.valor, 1500.0)
        self.assertAlmostEqual(st.obter_valor_exibicao_input(), 150.0)

    def test_03_controles_ui_lancamento_form(self):
        """Verifica se os controles de UI do formulário suportam até 48x e contêm badges."""
        page = MagicMock(spec=ft.Page)
        st = LancamentoFormState(
            tipo="Despesa",
            forma_movimentacao="Crédito",
            valor=600.0,
            quantidade=6,
            parcela_atual=2,
            total_parcelas_original=6,
            serie_id="serie-test-456",
        )
        form = LancamentoForm(page, st)

        # 48 opções no dropdown
        self.assertEqual(len(form.dd_parcelas.options), 48)
        self.assertEqual(form.dd_parcelas.options[47].key, "48")
        self.assertEqual(form.dd_parcelas.options[47].text, "48x")

        # Badge e avisos presentes
        self.assertTrue(hasattr(form, "badge_edicao_parcela"))
        self.assertTrue(hasattr(form, "lbl_badge_parcela"))
        self.assertTrue(hasattr(form, "lbl_aviso_mudanca_parcelas"))

        # Badge visível com texto correto
        self.assertTrue(form.badge_edicao_parcela.visible)
        self.assertIn("Editando Parcela 2 de 6x", form.lbl_badge_parcela.value)

        # Ao mudar parcelas para menos (redução): aviso de alerta
        form.state.quantidade = 4
        form._atualizar_resumo_parcelas(atualizar_ui=False)
        self.assertTrue(form.lbl_aviso_mudanca_parcelas.visible)
        self.assertIn("Reduzir de 6x para 4x", form.lbl_aviso_mudanca_parcelas.value)

        # Ao mudar parcelas para mais (expansão): aviso de extensão
        form.state.quantidade = 10
        form._atualizar_resumo_parcelas(atualizar_ui=False)
        self.assertTrue(form.lbl_aviso_mudanca_parcelas.visible)
        self.assertIn("Expandir de 6x para 10x", form.lbl_aviso_mudanca_parcelas.value)

    @patch("services.supabase_client.supabase")
    def test_04_wrappers_supabase_client(self, mock_sb):
        """Verifica as chamadas RPC de deslocamento e redimensionamento."""
        # Teste deslocar_faturas_parcelamento
        mock_rpc = MagicMock()
        mock_sb.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value.data = {"sucesso": True, "afetados": 5, "delta": 1}

        res_desloc = db.deslocar_faturas_parcelamento("lanc-1", "fat-2", aplicar_cascata=True)
        self.assertTrue(res_desloc.get("sucesso"))
        self.assertEqual(res_desloc.get("afetados"), 5)
        mock_sb.rpc.assert_called_with("fn_deslocar_faturas_parcelamento", {
            "p_lancamento_id": "lanc-1",
            "p_nova_fatura_id": "fat-2",
            "p_aplicar_cascata": True,
        })

        # Teste redimensionar_parcelamento
        mock_rpc.execute.return_value.data = {"sucesso": True, "novo_total": 8}
        res_redim = db.redimensionar_parcelamento("serie-1", 8, novo_valor_parcela=120.0)
        self.assertTrue(res_redim.get("sucesso"))
        mock_sb.rpc.assert_called_with("fn_redimensionar_parcelamento", {
            "p_serie_id": "serie-1",
            "p_novo_total": 8,
            "p_novo_valor_parcela": 120.0,
        })

    def test_05_abrir_lancamento_em_edicao_parcelada(self):
        """Verifica a abertura do modal em modo de edição de uma compra parcelada."""
        page = MagicMock(spec=ft.Page)
        page.width = 1200
        item_parcelado = {
            "id": "item-uuid-999",
            "descricao": "Monitor Gamer (3/10)",
            "valor": 250.0,
            "tipo": "Despesa",
            "forma_movimentacao": "Crédito",
            "cartao_id": "cartao-uuid-1",
            "fatura_id": "fat-uuid-nov",
            "serie_id": "serie-uuid-mon",
            "parcela_atual": 3,
            "total_parcelas": 10,
            "status": "Pendente",
            "data": "2026-11-15",
        }

        # Abre o lançamento para edição
        abrir_lancamento(page, lancamento=item_parcelado)

        # Dialog deve ter sido apresentado na página
        page.show_dialog.assert_called()
        dlg = page.show_dialog.call_args[0][0]
        self.assertIsNotNone(dlg)

    def test_06_recorrencia_nao_eh_compra_parcelada(self):
        """Garante que assinaturas recorrentes (fixas) jamais são tratadas como compra parcelada."""
        st = LancamentoFormState(
            tipo="Despesa",
            forma_movimentacao="Crédito",
            valor=14.90,
            is_fixa=True,
            recorrente_id="rec-hbo-uuid",
            serie_id="serie-hbo-uuid",
            quantidade=1,
        )
        self.assertFalse(st.is_compra_parcelada)


if __name__ == "__main__":
    unittest.main()
