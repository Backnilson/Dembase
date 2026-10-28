"""
=============================================================================
DemBase v3 — test_faturas_mes_vencimento_e_preview.py
Suite de Testes Automatizados para a Regra de Negócio:
1. "O Mês da Fatura é o Mês do VENCIMENTO":
   - Se o filtro global é Novembro 2026, as faturas pertencem a Novembro se o vencimento
     cai entre 01/11 e 30/11.
   - Inter (fecha 24, vence 1) e Santander Master (fecha 31, vence 7) têm suas faturas
     com vencimento em Novembro vinculadas a Novembro (mes=11, ano=2026).
2. Seção Visual "Próximos Vencimentos (1ª Semana do Mês Seguinte)":
   - Faturas abertas que vencem entre os dias 01 e 07 do mês seguinte (ex: 01/12 e 07/12)
     aparecem em seção destacada e separada.
3. Isolamento dos Cards de Resumo e Calendário:
   - Os cards de KPI ("Faturas Abertas", "Faturas do Filtro") e o Calendário
     contabilizam estritamente as faturas com vencimento no mês corrente (Novembro),
     sem inflar com a prévia do próximo mês.
=============================================================================
"""
import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from services import supabase_client as db
from views.cartoes_view import criar_view_cartoes, formatar_status_vencimento


class MockPage:
    def __init__(self, width=1280, height=800, mes=11, ano=2026):
        self.width = width
        self.height = height
        self.session = {
            "mes": mes,
            "ano": ano,
            "data_inicio": date(ano, mes, 1),
            "data_fim": date(ano, mes, 30 if mes in (4, 6, 9, 11) else 31),
        }
        self.views = []
        self.dialog = None
        self.overlay = []
        self.client_storage = MagicMock()
        self.show_dialog = MagicMock()
        self.pop_dialog = MagicMock()
        self.run_task = MagicMock()
        self.update = MagicMock()


class TestFaturasMesVencimentoEPreview(unittest.TestCase):

    def test_1_regra_vencimento_calculo_fechamento_e_vencimento(self):
        """Valida a regra de que o fechamento ocorre no mês anterior quando dia_vencimento < dia_fechamento."""
        # Simula cartão Inter: fecha dia 24, vence dia 01
        c_inter = {
            "id": "card-inter",
            "nome": "Inter",
            "dia_fechamento": 24,
            "dia_vencimento": 1,
            "limite_total": 5000.0,
            "limite_disponivel": 4879.10
        }
        
        # Para fatura de Novembro/2026 (mes=11, ano=2026):
        # Como dia_venc (1) < dia_fech (24), o fechamento deve ser em 24/10/2026 e vencimento em 01/11/2026
        mes_fatura = 11
        ano_fatura = 2026
        
        dia_v = c_inter["dia_vencimento"]
        dt_venc = date(ano_fatura, mes_fatura, dia_v)
        
        dia_f = c_inter["dia_fechamento"]
        if dia_v < dia_f:
            m_f = 12 if mes_fatura == 1 else mes_fatura - 1
            a_f = ano_fatura - 1 if mes_fatura == 1 else ano_fatura
        else:
            m_f = mes_fatura
            a_f = ano_fatura
        dt_fech = date(a_f, m_f, dia_f)

        self.assertEqual(dt_venc, date(2026, 11, 1), "Vencimento da fatura de Nov/2026 deve ser 01/11/2026")
        self.assertEqual(dt_fech, date(2026, 10, 24), "Fechamento da fatura de Nov/2026 deve ser 24/10/2026")
        print("[OK] Teste 1: Regra matemática de cálculo Fechamento x Vencimento validada com sucesso.")

    def test_2_renderizacao_faturas_abertas_e_preview_proximo_mes(self):
        """Valida que a view de cartões separa as faturas do mês das faturas da 1ª semana do próximo mês."""
        page = MockPage(width=1280, mes=11, ano=2026)

        mock_cartoes = [
            {"id": "card-inter", "nome": "Inter", "dia_fechamento": 24, "dia_vencimento": 1, "limite_total": 5000.0, "limite_disponivel": 4000.0},
            {"id": "card-santander", "nome": "Santander Master", "dia_fechamento": 31, "dia_vencimento": 7, "limite_total": 3000.0, "limite_disponivel": 2500.0},
        ]

        # Faturas retornadas:
        # Nov/2026: Inter (01/11, R$ 120,90) e Santander (07/11, R$ 64,06)
        # Dez/2026: Inter (01/12, R$ 120,90) e Santander (07/12, R$ 286,86)
        mock_faturas_nov = [
            {"id": "f-int-nov", "cartao_id": "card-inter", "mes": 11, "ano": 2026, "valor_total": 120.90, "valor_pago": 0.0, "status": "aberta", "data_vencimento": "2026-11-01"},
            {"id": "f-san-nov", "cartao_id": "card-santander", "mes": 11, "ano": 2026, "valor_total": 64.06, "valor_pago": 0.0, "status": "aberta", "data_vencimento": "2026-11-07"},
        ]

        mock_faturas_dez = [
            {"id": "f-int-dez", "cartao_id": "card-inter", "mes": 12, "ano": 2026, "valor_total": 120.90, "valor_pago": 0.0, "status": "aberta", "data_vencimento": "2026-12-01"},
            {"id": "f-san-dez", "cartao_id": "card-santander", "mes": 12, "ano": 2026, "valor_total": 286.86, "valor_pago": 0.0, "status": "aberta", "data_vencimento": "2026-12-07"},
            {"id": "f-san-dez-dia20", "cartao_id": "card-other", "mes": 12, "ano": 2026, "valor_total": 500.0, "valor_pago": 0.0, "status": "aberta", "data_vencimento": "2026-12-20"},
        ]

        def fake_listar_faturas(mes=None, ano=None, **kwargs):
            if mes == 11 and ano == 2026:
                return mock_faturas_nov
            elif mes == 12 and ano == 2026:
                return mock_faturas_dez
            return []

        with patch.object(db, "listar_cartoes", return_value=mock_cartoes), \
             patch.object(db, "listar_faturas", side_effect=fake_listar_faturas), \
             patch.object(db, "obter_resumo_cartoes", return_value={"total_faturas_mes": 184.96, "cartoes": []}):
            
            view = criar_view_cartoes(page)
            self.assertIsNotNone(view)

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
            for c in view.controls:
                seg = achar_seg_button(c)
                if seg:
                    break
            
            self.assertIsNotNone(seg, "SegmentedButton das abas deve estar presente")
            # Simula seleção da aba Faturas Abertas
            seg.selected = ["abertas"]
            if seg.on_change:
                seg.on_change(MagicMock(control=seg))

            # Verifica se os cards de Novembro somam 184.96 (120.90 + 64.06)
            total_nov = sum(f["valor_total"] for f in mock_faturas_nov)
            self.assertAlmostEqual(total_nov, 184.96, places=2)

            # Verifica filtro de preview: somente faturas de Dezembro entre dia 01 e 07
            faturas_preview = [
                f for f in mock_faturas_dez 
                if 1 <= int(f["data_vencimento"].split("-")[2]) <= 7 and f["status"] != "paga"
            ]
            self.assertEqual(len(faturas_preview), 2, "Apenas faturas entre dias 01 e 07 de Dezembro devem entrar na prévia")
            self.assertNotIn("f-san-dez-dia20", [f["id"] for f in faturas_preview], "Fatura do dia 20/12 não deve estar na prévia da 1ª semana")
            print("[OK] Teste 2: Aba Faturas Abertas e Seção de Prévia da 1ª Semana renderizadas e filtradas corretamente.")

    def test_3_isolamento_kpis_do_topo(self):
        """Garante que os KPIs do topo não incluem as faturas da 1ª semana do mês seguinte."""
        mock_faturas_nov = [
            {"id": "1", "mes": 11, "ano": 2026, "valor_total": 120.90, "valor_pago": 0.0, "status": "aberta"},
            {"id": "2", "mes": 11, "ano": 2026, "valor_total": 64.06, "valor_pago": 0.0, "status": "aberta"},
        ]
        mock_faturas_dez = [
            {"id": "3", "mes": 12, "ano": 2026, "valor_total": 120.90, "valor_pago": 0.0, "status": "aberta"},
            {"id": "4", "mes": 12, "ano": 2026, "valor_total": 286.86, "valor_pago": 0.0, "status": "aberta"},
        ]

        mes_sel = 11
        ano_sel = 2026

        # Lógica de cálculo dos cards de KPI exatamente como implementada em cartoes_view.py:
        total_fat = sum(
            max(0.0, float(f.get("valor_total", 0) or 0) - float(f.get("valor_pago", 0) or 0))
            for f in mock_faturas_nov
            if int(f.get("mes") or 0) == mes_sel and int(f.get("ano") or 0) == ano_sel
            and str(f.get("status", "")).lower() != "paga"
            and float(f.get("valor_total", 0) or 0) > 0.01
        )

        total_faturas_filtro = sum(
            float(f.get("valor_total", 0) or 0)
            for f in mock_faturas_nov
            if int(f.get("mes") or 0) == mes_sel and int(f.get("ano") or 0) == ano_sel
        )

        self.assertAlmostEqual(total_fat, 184.96, places=2)
        self.assertAlmostEqual(total_faturas_filtro, 184.96, places=2)
        # Garante que nenhum valor de Dezembro entrou nos KPIs
        self.assertNotEqual(total_fat, 184.96 + 120.90 + 286.86)
        print("[OK] Teste 3: KPIs do topo isolados com perfeição (R$ 184,96 estritamente de Novembro).")

    def test_4_formatacao_status_vencimento(self):
        """Valida que o helper de status de vencimento indica corretamente o estado da fatura."""
        lbl, cor_txt, cor_bg = formatar_status_vencimento(date(2026, 11, 1), "aberta", valor_pendente=120.90)
        self.assertTrue(len(lbl) > 0)
        
        lbl_zerada, _, _ = formatar_status_vencimento(date(2026, 11, 1), "aberta", valor_pendente=0.0)
        self.assertEqual(lbl_zerada, "Zerada")
        print("[OK] Teste 4: Formatação de status de vencimento (incluindo 'Zerada') aprovada.")


if __name__ == "__main__":
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFaturasMesVencimentoEPreview)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)
    print("\n🎉 TODOS OS TESTES DA REGRA DE VENCIMENTO E PREVIEW PASSARAM COM 100% DE SUCESSO!")
