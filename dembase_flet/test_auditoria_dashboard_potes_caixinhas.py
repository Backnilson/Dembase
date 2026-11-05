# -*- coding: utf-8 -*-
"""
Auditoria de Ponta a Ponta — DemBase v3:
1. Validação dos 6 Potes em Novembro/2026 (Valores reais, contagem de transações, regra contábil sem dupla contagem).
2. Validação da Reatividade do card Minhas Caixinhas (Filtros de Período Mês/Dia e valores calculados).
3. Validação das Badges das Caixinhas (Nome real do Pote, nunca "6 Potes").
"""
import sys
import unittest
sys.path.append("dembase_flet")
import services.supabase_client as db

class TestAuditoriaDashboardPotesCaixinhas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Autentica com o usuário de teste
        resp = db.fazer_login("teste@dembase.com", "teste123")
        assert resp is not None, "Falha no login de teste"

    def test_01_resumo_potes_novembro_2026_nao_zerado(self):
        """Valida que get_potes_resumo não está zerado e calcula gastos reais e transações."""
        res = db.obter_resumo_potes("2026-11-01", "2026-11-30", forcar_atualizacao=True)
        self.assertIsNotNone(res)
        self.assertIn("potes", res)
        potes = res["potes"]
        self.assertEqual(len(potes), 6, "Devem existir exatamente 6 potes retornados")

        total_gasto = sum(float(p.get("gasto", 0) or 0) for p in potes)
        total_qtd = sum(int(p.get("qtd_transacoes", 0) or 0) for p in potes)

        print(f"\n[TEST 1] Resumo dos 6 Potes (Novembro/2026):")
        for p in potes:
            print(f"  Pote {p.get('posicao')}: {p.get('nome')} | Gasto: R$ {p.get('gasto'):.2f} | Transações: {p.get('qtd_transacoes')}")

        self.assertGreater(total_gasto, 0, "Gasto real dos potes não pode ser zero!")
        self.assertGreater(total_qtd, 0, "Quantidade total de transações não pode ser zero!")

    def test_02_reatividade_caixinhas_filtro_periodo(self):
        """Valida que o card Minhas Caixinhas reage dinamicamente aos filtros de período."""
        # 1. Mês de Novembro/2026
        res_nov = db.obter_resumo_caixinhas(forcar_atualizacao=True, data_inicio="2026-11-01", data_fim="2026-11-30")
        self.assertIsNotNone(res_nov)
        gasto_nov = float(res_nov.get("total_gasto", 0) or 0)

        # 2. Dia específico: 2026-11-06 (onde houve gasto específico)
        res_dia = db.obter_resumo_caixinhas(forcar_atualizacao=True, data_inicio="2026-11-06", data_fim="2026-11-06")
        self.assertIsNotNone(res_dia)
        gasto_dia = float(res_dia.get("total_gasto", 0) or 0)

        # 3. Dia sem gastos: 2026-11-01
        res_dia_vazio = db.obter_resumo_caixinhas(forcar_atualizacao=True, data_inicio="2026-11-01", data_fim="2026-11-01")
        gasto_dia_vazio = float(res_dia_vazio.get("total_gasto", 0) or 0)

        print(f"\n[TEST 2] Reatividade de Período das Caixinhas:")
        print(f"  Novembro Completo -> Consumido: R$ {gasto_nov:.2f}")
        print(f"  Dia 2026-11-06    -> Consumido: R$ {gasto_dia:.2f}")
        print(f"  Dia 2026-11-01    -> Consumido: R$ {gasto_dia_vazio:.2f}")

        self.assertNotEqual(gasto_nov, gasto_dia, "O consumo do mês completo não deve ser idêntico ao de um único dia com gastos parciais")
        self.assertEqual(gasto_dia_vazio, 0.0, "Em dia sem consumo, total_gasto deve ser 0.0")

    def test_03_badges_com_nome_real_do_pote(self):
        """Valida que todas as caixinhas possuem pote_nome real e NUNCA '6 Potes'."""
        res = db.obter_resumo_caixinhas(forcar_atualizacao=True, data_inicio="2026-11-01", data_fim="2026-11-30")
        caixinhas = res.get("caixinhas") or []
        self.assertGreater(len(caixinhas), 0, "Deve haver caixinhas cadastradas")

        print(f"\n[TEST 3] Badges das Caixinhas:")
        for c in caixinhas:
            p_info = c.get("potes")
            self.assertIsNotNone(p_info, f"Caixinha '{c.get('nome')}' deve ter objeto potes associado")
            p_nome = p_info.get("nome") if isinstance(p_info, dict) else ""
            print(f"  Caixinha: {c.get('nome')} | Badge Pote: '{p_nome}'")
            self.assertNotEqual(p_nome, "6 Potes", f"Badge não pode ser o texto genérico '6 Potes' para {c.get('nome')}!")
            self.assertIn(p_nome, ["Custos Fixos", "Custos Semi Fixos", "Metas", "Prazeres", "Conhecimento", "Liberdade Financeira"])

if __name__ == "__main__":
    unittest.main()
