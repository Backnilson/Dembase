"""
Teste Automatizado Ponta a Ponta — DemBoxes (Provisões Mensais + Quitação de Dívidas + Raio-X)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
import services.supabase_client as db
from views.caixinhas_view import montar_aba_caixinhas
from views.widgets.dashboard_charts import DASHBOARD_CHARTS_CATALOG, _render_minhas_caixinhas


def main():
    print("1. Autenticando sessão de teste...")
    res_auth = db.fazer_login("teste@dembase.com", "teste123")
    assert res_auth and res_auth.user, f"Falha no login: {res_auth}"
    print("   Logado com sucesso como teste@dembase.com")

    contas = db.listar_contas() or []
    potes = db.listar_potes() or []
    assert contas and potes, "Contas e Potes devem existir para o teste"
    conta_id = str(contas[0]["id"])
    pote_id = str(potes[0]["id"])

    id_provisao = None
    id_divida = None

    try:
        # 2. Teste Modo A: Provisão do Mês
        print("2. Criando DemBox no modo Provisão do Mês...")
        cx_prov = db.criar_caixinha({
            "nome": "Teste Provisão Mensal",
            "modalidade": "provisao_mensal",
            "valor_meta": 400.0,
            "conta_id": conta_id,
            "pote_id": pote_id,
            "icone": "two_wheeler",
            "cor": "#10B981",
        })
        id_provisao = str(cx_prov["id"])
        res_pag = db.pagar_provisao_caixinha(
            caixinha_id=id_provisao,
            conta_id=conta_id,
            pote_id=pote_id,
            valor=400.0,
        )
        assert res_pag.get("sucesso"), f"Erro ao pagar provisão: {res_pag}"
        print(f"   Provisão Mensal abastecida! ID={id_provisao}")

        # 3. Teste Modo B: Quitar Dívida / Juntar ("Dívida com a Chefe")
        print("3. Criando DemBox no modo Dívida / Acumulação ('Dívida com a Chefe' R$ 1.000,00)...")
        cx_div = db.criar_caixinha({
            "nome": "Dívida com a Chefe (Teste)",
            "modalidade": "divida",
            "valor_meta": 1000.0,
            "conta_id": conta_id,
            "pote_id": pote_id,
            "icone": "person",
            "cor": "#F59E0B",
        })
        id_divida = str(cx_div["id"])
        assert cx_div.get("modalidade") == "divida"
        print(f"   Dívida criada com ID={id_divida}, saldo inicial=0.0")

        # 4. Guardar Dinheiro (+ R$ 300,00) descontando da conta bancária e do Pote
        print("4. Testando '+ Guardar Dinheiro' (R$ 300,00) na Dívida com a Chefe...")
        res_guardar = db.injetar_saldo_caixinha(
            caixinha_id=id_divida,
            valor=300.0,
            descricao="Guardado p/ Dívida · Dívida com a Chefe (Teste)",
            conta_id=conta_id,
            pote_id=pote_id,
            gerar_despesa=True,
        )
        assert res_guardar.get("sucesso"), f"Erro ao guardar dinheiro: {res_guardar}"

        # 5. Abater parte da dívida ao credor (R$ 100,00)
        print("5. Testando 'Pagar / Abater Divida' (R$ 100,00 entregues a chefe)...")
        res_abater = db.deduzir_saldo_caixinha(
            caixinha_id=id_divida,
            valor=100.0,
            descricao="Pagamento parcial p/ Chefe",
        )
        assert res_abater is not None

        # 6. Verificar comportamento ACUMULATIVO na virada do mês (ex: Dezembro 2026)
        print("6. Verificando que a Dívida NÃO zera na virada do mês (Dezembro/2026)...")
        lista_dez = db.listar_caixinhas(forcar_atualizacao=True, data_inicio="2026-12-01", data_fim="2026-12-31")
        div_dez = next((x for x in lista_dez if str(x.get("id")) == id_divida), None)
        assert div_dez is not None, "Dívida deve aparecer na listagem"
        assert div_dez.get("modalidade") == "divida"
        assert abs(float(div_dez.get("total_guardado", 0)) - 300.0) < 0.01, f"Total guardado esperado 300, veio {div_dez.get('total_guardado')}"
        assert abs(float(div_dez.get("total_abatido", 0)) - 100.0) < 0.01, f"Total abatido esperado 100, veio {div_dez.get('total_abatido')}"
        assert abs(float(div_dez.get("saldo_atual", 0)) - 200.0) < 0.01, f"Saldo em caixa esperado 200, veio {div_dez.get('saldo_atual')}"
        assert abs(float(div_dez.get("falta_guardar", 0)) - 700.0) < 0.01, f"Falta guardar esperado 700, veio {div_dez.get('falta_guardar')}"
        print(f"   Acumulado preservado perfeitamente! Guardado=R$ 300 | Abatido=R$ 100 | Em Caixa=R$ 200 | Falta=R$ 700 (30%)")

        # 7. Testar Raio-X (obter_extrato_caixinha)
        print("7. Testando Raio-X completo (db.obter_extrato_caixinha)...")
        rx = db.obter_extrato_caixinha(id_divida)
        hist = rx.get("historico") or []
        assert len(hist) >= 2, f"Esperado ao menos 2 registros no histórico do Raio-X, veio {len(hist)}"
        naturezas = {h.get("natureza") for h in hist}
        assert "entrada" in naturezas and "saida" in naturezas, f"Naturezas esperadas entrada e saida, veio {naturezas}"
        print(f"   Raio-X retornou {len(hist)} registros com precisão contábil!")

        # 8. Testar UI de DemBoxes e Card do Dashboard
        print("8. Validando UI de DemBoxes e Card 'Meus DemBoxes' no Dashboard...")
        cat_dembox = next((item for item in DASHBOARD_CHARTS_CATALOG if item["id"] == "minhas_caixinhas"), None)
        assert cat_dembox and cat_dembox["titulo"] == "Meus DemBoxes", f"Título no catálogo deveria ser Meus DemBoxes: {cat_dembox}"

        class DummyPage:
            width = 1280
            height = 800
            overlay = []
            views = []
            session = {}
            def update(self):
                pass

        dummy_page = DummyPage()
        view_ctrl = montar_aba_caixinhas(dummy_page)
        assert view_ctrl is not None

        resumo_atual = db.obter_resumo_caixinhas(forcar_atualizacao=True)
        card_dash = _render_minhas_caixinhas(dummy_page, {"resumo_caixinhas": resumo_atual}, cat_dembox)
        assert card_dash is not None
        print("   View DemBoxes e Card do Dashboard renderizados com sucesso!")

    finally:
        print("9. Limpando dados temporários do teste...")
        for cid_limpar in (id_provisao, id_divida):
            if cid_limpar:
                try:
                    db.supabase.table("lancamentos").delete().eq("caixinha_id", cid_limpar).execute()
                    db.supabase.table("caixinhas_teto_movimentacoes").delete().eq("caixinha_id", cid_limpar).execute()
                    db.supabase.table("caixinhas_teto").delete().eq("id", cid_limpar).execute()
                except Exception as ex_c:
                    print(f"   Aviso limpeza {cid_limpar}: {ex_c}")
        db.invalidar_cache("caixinhas")
        db.invalidar_cache("resumo_caixinhas")
        print("   Limpeza concluída.")

    print("\nTODOS OS TESTES DO MÓDULO DEMBOXES PASSARAM COM 100% DE SUCESSO!")


if __name__ == "__main__":
    main()
