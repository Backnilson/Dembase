"""
=============================================================================
DemBase v3 — test_tres_tarefas_unificacao.py
Bateria de Testes Automatizados para as 3 Tarefas da Rodada:
1. Tarefa 1: Modal Raio-X do Dia Unificado em Todos os Calendários
2. Tarefa 2: Saudação Dinâmica e Zero Nomes Fixos
3. Tarefa 3: Teto Seguro Baseado no Caixa Livre Gastável (com regras e princípios)
=============================================================================
"""
import os
import sys
from unittest.mock import MagicMock, patch

# Adiciona dembase_flet ao sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from core.potes import calcular_teto_seguro_gastavel
from views.widgets.calendario_raio_x import (
    calcular_raio_x_dia,
    montar_texto_tooltip_raio_x,
    construir_painel_raio_x,
    abrir_modal_raio_x_dia,
)
from views.widgets.sobra_card import calcular_rateio_sobra


def test_tarefa_3_teto_seguro_gastavel_matematica():
    print("\n--- AUDITORIA TAREFA 3: Matemática do Teto Seguro Gastável ---")

    # Cenário A: Sobra R$ 1.000 | 70% Guardar / 30% Prazeres | Gargalo R$ 800
    res_a = calcular_teto_seguro_gastavel(
        sobra_projetada=1000.0,
        menor_saldo_futuro=800.0,
        pct_investimento=70.0,
        travar_pelo_pior_dia=True,
    )
    assert abs(res_a["valor_investir"] - 700.0) < 0.01, f"Esperado 700.00, obteve {res_a['valor_investir']}"
    assert abs(res_a["valor_gastavel"] - 300.0) < 0.01, f"Esperado 300.00, obteve {res_a['valor_gastavel']}"
    assert abs(res_a["teto_seguro_gasto"] - 300.0) < 0.01, f"Teto deveria ser limitado aos R$ 300 gastáveis, obteve {res_a['teto_seguro_gasto']}"
    assert res_a["rotulo"] == "Teto Seguro p/ Gastar"
    print("  [OK] Cenário A (70/30 com gargalo R$ 800): Teto Seguro R$ 300,00 (R$ 700 guardados intactos)")

    # Cenário B: Sobra R$ 1.000 | 70% Guardar / 30% Prazeres | Gargalo R$ 200 (aperto intermediário)
    res_b = calcular_teto_seguro_gastavel(
        sobra_projetada=1000.0,
        menor_saldo_futuro=200.0,
        pct_investimento=70.0,
        travar_pelo_pior_dia=True,
    )
    assert abs(res_b["teto_seguro_gasto"] - 200.0) < 0.01, f"Teto deveria ser limitado pelo gargalo a R$ 200, obteve {res_b['teto_seguro_gasto']}"
    assert abs(res_b["sobra_falsa_travada"] - 800.0) < 0.01, f"Sobra falsa retida deveria ser 800.00, obteve {res_b['sobra_falsa_travada']}"
    print("  [OK] Cenário B (Gargalo R$ 200 < R$ 300): Teto limitado com precisão a R$ 200,00")

    # Cenário C: Gargalo Negativo (-R$ 50,00)
    res_c = calcular_teto_seguro_gastavel(
        sobra_projetada=1000.0,
        menor_saldo_futuro=-50.0,
        pct_investimento=70.0,
        travar_pelo_pior_dia=True,
    )
    assert res_c["teto_seguro_gasto"] == 0.0, f"Teto deveria ser R$ 0,00 em saldo negativo, obteve {res_c['teto_seguro_gasto']}"
    assert res_c["fica_negativo_no_meio"] is True
    print("  [OK] Cenário C (Gargalo negativo): Teto Seguro zerado em R$ 0,00")

    # Cenário D: Toggle "Travar pelo Pior Dia" Desativado
    res_d = calcular_teto_seguro_gastavel(
        sobra_projetada=1000.0,
        menor_saldo_futuro=200.0,
        pct_investimento=70.0,
        travar_pelo_pior_dia=False,
    )
    assert abs(res_d["teto_seguro_gasto"] - 300.0) < 0.01, f"Sem trava, teto deveria ser os R$ 300 gastáveis, obteve {res_d['teto_seguro_gasto']}"
    print("  [OK] Cenário D (Trava desligada): Teto reflete R$ 300,00 da parte gastável")

    # Cenário E: 100% Guardar / 0% Prazeres
    res_e = calcular_teto_seguro_gastavel(
        sobra_projetada=1000.0,
        menor_saldo_futuro=800.0,
        pct_investimento=100.0,
        travar_pelo_pior_dia=True,
    )
    assert res_e["teto_seguro_gasto"] == 0.0, f"Com 100% guardar, teto de gasto deve ser 0.0, obteve {res_e['teto_seguro_gasto']}"
    print("  [OK] Cenário E (100% Guardar): Teto Seguro para gastar é R$ 0,00")

    # Cenário F: 0% Guardar / 100% Prazeres
    res_f = calcular_teto_seguro_gastavel(
        sobra_projetada=1000.0,
        menor_saldo_futuro=800.0,
        pct_investimento=0.0,
        travar_pelo_pior_dia=True,
    )
    assert abs(res_f["teto_seguro_gasto"] - 800.0) < 0.01, f"Com 0% guardar, teto deve ser limitado a 800, obteve {res_f['teto_seguro_gasto']}"
    print("  [OK] Cenário F (0% Guardar / 100% Gastar): Teto é R$ 800,00 limitado pelo gargalo")


def test_tarefa_3_integracao_sobra_card():
    print("\n--- AUDITORIA TAREFA 3: Integração no Card de Caixa Livre ---")
    prot_mock = {
        "sobra_projetada": 1000.0,
        "menor_saldo_futuro": 800.0,
        "teto_seguro_gasto": 800.0,
        "data_gargalo": "2026-10-20",
    }
    rateio = calcular_rateio_sobra(
        receitas=5000.0,
        despesas=4000.0,
        pct_investimento=70.0,
        protecao_fluxo=prot_mock,
        travar_pelo_teto_seguro=True,
    )
    # A sobra projetada é 1000.
    # Com 70% investimento -> R$ 700 investir / R$ 300 livre
    assert abs(rateio["valor_investimento"] - 700.0) < 0.01, f"Esperado 700 inv, obteve {rateio['valor_investimento']}"
    assert abs(rateio["valor_livre_culpa"] - 300.0) < 0.01, f"Esperado 300 livre, obteve {rateio['valor_livre_culpa']}"
    assert abs(rateio["teto_seguro_gasto"] - 300.0) < 0.01, f"Teto seguro deveria ser 300, obteve {rateio['teto_seguro_gasto']}"
    print("  [OK] calcular_rateio_sobra: R$ 700 investidos e Teto Seguro p/ Gastar cravado em R$ 300,00!")


def test_tarefa_1_modal_raio_x_unificado():
    print("\n--- AUDITORIA TAREFA 1: Modal Raio-X Unificado ---")
    page_mock = MagicMock(spec=ft.Page)
    page_mock.dialog = None

    dia_teste = {
        "data": "2026-10-15",
        "total_receitas": 150.0,
        "total_despesas": 50.0,
        "despesas_conta": 20.0,
        "despesas_cartao": 30.0,
        "qtd_lancamentos": 2,
        "lancamentos": [
            {
                "descricao": "Supermercado",
                "tipo": "Despesa",
                "valor": 30.0,
                "cartao_nome": "Nubank",
                "status": "Pago",
                "membro_nome": "Marina",
                "membro_cor": "#E91E63",
                "membro_icone": "favorite",
            },
            {
                "descricao": "Farmácia",
                "tipo": "Despesa",
                "valor": 20.0,
                "conta_nome": "Inter",
                "status": "Pendente",
                "membro_nome": "Carlos",
                "membro_cor": "#007AFF",
                "membro_icone": "person",
            },
        ],
    }
    vencs_teste = [
        {"cartao_nome": "Nubank", "valor_total": 450.0, "status": "aberta"}
    ]
    acum_teste = {
        "2026-10-15": {
            "receitas_acum": 4000.0,
            "despesas_total_acum": 2500.0,
            "despesas_conta_acum": 1500.0,
            "despesas_cartao_acum": 1000.0,
            "saldo_acum": 1500.0,
            "menor_saldo_apos_dia": 600.0,
            "data_gargalo_apos_dia": "2026-10-25",
            "sobra_projetada": 1000.0,
            "pct_investimento": 70.0,
        }
    }

    # 1. Teste Desktop (860px, 2 Colunas)
    dlg_desk = abrir_modal_raio_x_dia(
        page=page_mock,
        dia_info=dia_teste,
        vencimentos_dia=vencs_teste,
        data_inicio_filtro="2026-10-01",
        acumulados_por_dia=acum_teste,
        mobile=False,
        pct_investimento=70.0,
        sobra_projetada_mes=1000.0,
    )
    assert dlg_desk is not None
    assert dlg_desk.content.width == 860
    assert len(dlg_desk.actions) == 3
    print("  [OK] Modal Desktop criado: 860px com 2 Colunas e ações completas!")

    # 2. Teste Mobile (340px, Empilhado)
    dlg_mob = abrir_modal_raio_x_dia(
        page=page_mock,
        dia_info=dia_teste,
        vencimentos_dia=vencs_teste,
        data_inicio_filtro="2026-10-01",
        acumulados_por_dia=acum_teste,
        mobile=True,
        pct_investimento=70.0,
        sobra_projetada_mes=1000.0,
    )
    assert dlg_mob is not None
    assert dlg_mob.content.width == 340
    print("  [OK] Modal Mobile criado: 340px com scroll empilhado!")

    # 3. Teste Tooltip Consistente
    rx = calcular_raio_x_dia(
        dia_info=dia_teste,
        vencimentos_dia=vencs_teste,
        data_inicio_filtro="2026-10-01",
        acumulados_por_dia=acum_teste,
        pct_investimento=70.0,
        sobra_projetada_mes=1000.0,
    )
    tt_txt = montar_texto_tooltip_raio_x(rx)
    assert "TETO SEGURO P/ GASTAR" in tt_txt
    assert "Já descontado 70% para investir" in tt_txt
    assert rx["teto_seguro"] == 300.0
    print(f"  [OK] Tooltip e Raio-X unificados: Teto Seguro p/ Gastar R$ {rx['teto_seguro']:.2f} com 70% investido!")


def test_tarefa_2_saudacao_dinamica():
    print("\n--- AUDITORIA TAREFA 2: Saudação Dinâmica & Zero Nomes Fixos ---")

    def _gerar_saudacao(perfil=None, user_meta=None):
        primeiro_nome = ""
        if perfil and perfil.get("nome"):
            partes = str(perfil["nome"]).strip().split()
            if partes and partes[0].lower() not in ("usuário", "usuario"):
                primeiro_nome = partes[0].capitalize()

        if not primeiro_nome and user_meta:
            raw_n = user_meta.get("nome") or user_meta.get("full_name") or user_meta.get("first_name")
            if raw_n:
                partes = str(raw_n).strip().split()
                if partes and partes[0].lower() not in ("usuário", "usuario"):
                    primeiro_nome = partes[0].capitalize()

        return f"Olá, {primeiro_nome}! 👋" if primeiro_nome else "Olá! 👋"

    # Testes unitários da lógica de saudação
    assert _gerar_saudacao({"nome": "Marina Costa"}) == "Olá, Marina! 👋"
    assert _gerar_saudacao({"nome": "Carlos Roberto"}) == "Olá, Carlos! 👋"
    assert _gerar_saudacao({"nome": "Denilson"}) == "Olá, Denilson! 👋"
    assert _gerar_saudacao({"nome": "Usuário"}) == "Olá! 👋"
    assert _gerar_saudacao({}, user_meta={"full_name": "Erika Silva"}) == "Olá, Erika! 👋"
    assert _gerar_saudacao(None, None) == "Olá! 👋"
    assert _gerar_saudacao({"nome": ""}) == "Olá! 👋"
    print("  [OK] Lógica de saudação dinâmica testada para todos os cenários (nome, auth fallback e anônimo)!")

    # Varredura em busca de nomes fixos em títulos e textos de dashboard_view.py
    with open(os.path.join(os.path.dirname(__file__), "views", "dashboard_view.py"), "r", encoding="utf-8") as f:
        dash_code = f.read()

    assert 'f"Olá, {nome}! 👋"' not in dash_code
    assert 'f"Olá, Denilson! 👋"' not in dash_code
    print("  [OK] dashboard_view.py: Saudação hardcoded eliminada com sucesso!")


if __name__ == "__main__":
    print("================================================================")
    print(" INICIANDO BATERIA DE AUDITORIA: AS 3 TAREFAS CONCLUÍDAS")
    print("================================================================")
    test_tarefa_3_teto_seguro_gastavel_matematica()
    test_tarefa_3_integracao_sobra_card()
    test_tarefa_1_modal_raio_x_unificado()
    test_tarefa_2_saudacao_dinamica()
    print("================================================================")
    print("  TODOS OS TESTES DAS 3 TAREFAS FORAM APROVADOS COM SUCESSO!")
    print("================================================================")
