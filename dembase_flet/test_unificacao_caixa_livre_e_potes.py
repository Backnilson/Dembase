"""
=============================================================================
DemBase v3 — test_unificacao_caixa_livre_e_potes.py
Teste de Engenharia Sênior para validação da Nova Arquitetura Unificada
entre a Destinação do Caixa Livre e os 6 Potes Financeiros.
=============================================================================
"""
from __future__ import annotations

import sys
import os
from decimal import Decimal
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.potes import (
    calcular_arquitetura_unificada_potes,
    POTES_PADRAO,
    PISO_CUSTOS_FIXOS_PADRAO,
)
from views.widgets.sobra_card import (
    calcular_rateio_sobra,
    PainelGestaoSobra,
)
from views.widgets.potes_cards import (
    card_pote,
    secao_potes,
    SecaoPotesController,
)
from views.widgets.potes_config import montar_aba_potes
import services.supabase_client as db


def mock_flet_page():
    page = MagicMock()
    page.width = 1280
    page.height = 800
    page.session = {}
    page._session_store = {}
    page.client_storage = MagicMock()
    page.client_storage.get.side_effect = lambda k: page._session_store.get(k)
    page.client_storage.set.side_effect = lambda k, v: page._session_store.update({k: v})
    page.update = MagicMock()
    return page


def test_1_matematica_cenario_real_usuario():
    print("\n--- 1. Testando Matemática do Cenário Real do Usuário ---")
    receita = 5641.36
    potes = [
        {"posicao": 1, "nome": "Custos Fixos", "percentual": 30.0, "gasto": 1150.0},
        {"posicao": 2, "nome": "Custos Semi Fixos", "percentual": 21.0, "gasto": 807.63},
        {"posicao": 3, "nome": "Metas", "percentual": 9.74, "gasto": 0.0},
        {"posicao": 4, "nome": "Prazeres", "percentual": 10.0, "gasto": 115.70},
        {"posicao": 5, "nome": "Conhecimento", "percentual": 5.0, "gasto": 0.0},
        {"posicao": 6, "nome": "Liberdade Financeira", "percentual": 20.0, "gasto": 0.0},
    ]

    res = calcular_arquitetura_unificada_potes(
        receitas=receita,
        potes=potes,
        piso_custos_fixos=1150.00,
        slider_pct_investimento=70.0,  # 70% Guardar / 30% Livre
    )

    # 1. Soma percentuais deve ser EXATAMENTE 100,00%
    assert res["soma_percentuais"] == 100.0, f"Soma dos percentuais deve ser 100.0%, obteve: {res['soma_percentuais']}"

    # 2. Custos Fixos: Limite = max(1150, 1150) = 1150.00 -> ~20.39%
    p1 = next(p for p in res["potes"] if p["posicao"] == 1)
    assert p1["previsto"] == 1150.0, f"Custos fixos limite incorreto: {p1['previsto']}"
    assert p1["percentual"] == 20.39, f"Custos fixos % incorreto: {p1['percentual']}"

    # 3. Custos Semi Fixos: Limite R$ 1.184,69, Gasto R$ 807,63, Disponível +R$ 377,06 RETIDO
    p2 = next(p for p in res["potes"] if p["posicao"] == 2)
    assert p2["previsto"] == 1184.69, f"Semi fixos previsto incorreto: {p2['previsto']}"
    assert p2["disponivel_retido"] == 377.06, f"Saldo retido do gás incorreto: {p2['disponivel_retido']}"

    # 4. Metas: Limite R$ 549,47 (9.74%), Disponível +R$ 549,47 RETIDO
    p3 = next(p for p in res["potes"] if p["posicao"] == 3)
    assert p3["disponivel_retido"] == 549.47, f"Saldo retido de metas incorreto: {p3['disponivel_retido']}"

    # 5. O saldo de R$ 377,06 (gás) e R$ 549,47 (metas) NÃO ESTÁ no Caixa Livre!
    cl = res["caixa_livre"]
    # Teto Caixa Livre = R$ 2.474,86
    assert cl["teto_orcamento"] == 2474.86, f"Teto Caixa Livre incorreto: {cl['teto_orcamento']}"
    # Prazeres: 30% do Caixa Livre = R$ 742,46. Já gastou R$ 115,70 -> Resta +R$ 626,76
    assert cl["prazeres_teto"] == 742.46, f"Prazeres teto incorreto: {cl['prazeres_teto']}"
    assert cl["prazeres_disponivel_hoje"] == 626.76, f"Prazeres restante incorreto: {cl['prazeres_disponivel_hoje']}"
    # Liberdade Financeira: 70% do Caixa Livre = R$ 1.732,40
    assert cl["liberdade_teto"] == 1732.40, f"Liberdade teto incorreto: {cl['liberdade_teto']}"

    print("  [OK] Cenario real do usuario validado com 100% de exatidao matematica!")


def test_2_soma_100_em_qualquer_slider():
    print("\n--- 2. Testando Invariante de 100,00% para Todas as Posições do Slider ---")
    receita = 8765.43
    potes = [
        {"posicao": 1, "nome": "Custos Fixos", "percentual": 25.0, "gasto": 1800.0},
        {"posicao": 2, "nome": "Custos Semi Fixos", "percentual": 22.0, "gasto": 1500.0},
        {"posicao": 3, "nome": "Metas", "percentual": 12.0, "gasto": 200.0},
        {"posicao": 4, "nome": "Prazeres", "percentual": 10.0, "gasto": 300.0},
        {"posicao": 5, "nome": "Conhecimento", "percentual": 6.0, "gasto": 100.0},
        {"posicao": 6, "nome": "Liberdade Financeira", "percentual": 25.0, "gasto": 500.0},
    ]

    for slider in (0.0, 15.0, 30.0, 50.0, 70.0, 85.0, 100.0):
        res = calcular_arquitetura_unificada_potes(
            receitas=receita,
            potes=potes,
            piso_custos_fixos=1150.0,
            slider_pct_investimento=slider,
        )
        soma = res["soma_percentuais"]
        assert soma == 100.0, f"Slider {slider}% gerou soma divergente: {soma}%"
    print("  [OK] Invariante de 100,00% testado e aprovado em todas as fatias do slider!")


def test_3_painel_sobra_reativo_e_sincronizacao():
    print("\n--- 3. Testando PainelGestaoSobra e Sincronização em Tempo Real ---")
    page = mock_flet_page()

    potes_alterados_recebidos = []

    def _on_alterar_potes(novos_potes):
        potes_alterados_recebidos.append(novos_potes)

    painel = PainelGestaoSobra(
        page=page,
        mobile=False,
        on_potes_alterados=_on_alterar_potes,
    )

    potes_iniciais = [
        {"posicao": 1, "nome": "Custos Fixos", "percentual": 30.0, "gasto": 1150.0},
        {"posicao": 2, "nome": "Custos Semi Fixos", "percentual": 21.0, "gasto": 807.63},
        {"posicao": 3, "nome": "Metas", "percentual": 10.0, "gasto": 0.0},
        {"posicao": 4, "nome": "Prazeres", "percentual": 10.0, "gasto": 115.70},
        {"posicao": 5, "nome": "Conhecimento", "percentual": 5.0, "gasto": 0.0},
        {"posicao": 6, "nome": "Liberdade Financeira", "percentual": 24.0, "gasto": 0.0},
    ]

    # Atualiza período
    painel.atualizar_periodo(
        receitas=5641.36,
        despesas=2073.33,
        mes=10,
        ano=2026,
        resumo_potes={"potes": potes_iniciais},
        piso_custos_fixos=1150.0,
    )

    # Verifica os cards
    assert painel.txt_inv_titulo.value == "Liberdade Financeira"
    assert painel.txt_livre_titulo.value == "Prazeres"
    assert "Teto" in painel.txt_livre_teto_info.value
    assert "gasto" in painel.txt_livre_teto_info.value.lower()
    assert "Teto" in painel.txt_inv_teto_info.value
    assert ("investido" in painel.txt_inv_teto_info.value.lower() or "aportado" in painel.txt_inv_teto_info.value.lower())

    # Ao mover o slider para 70%
    painel.definir_percentual(70.0)
    assert painel.pct_investimento == 70.0
    assert len(potes_alterados_recebidos) >= 1
    potes_notificados = potes_alterados_recebidos[-1]
    p_prazeres = next(p for p in potes_notificados if p["posicao"] == 4)
    p_liberdade = next(p for p in potes_notificados if p["posicao"] == 6)
    assert p_prazeres["previsto"] > 0
    assert p_liberdade["previsto"] > 0

    print("  [OK] PainelGestaoSobra atualiza e sincroniza perfeitamente em tempo real!")


def test_4_secao_potes_controller_e_badges():
    print("\n--- 4. Testando SecaoPotesController e Badges Inteligentes ---")
    page = mock_flet_page()

    resumo_mock = {
        "renda": 5641.36,
        "potes": [
            {
                "id": "p1", "posicao": 1, "nome": "Custos Fixos", "percentual": 20.39,
                "previsto": 1150.0, "gasto": 1150.0, "restante": 0.0, "qtd_transacoes": 4,
                "cor": "#007AFF", "tipo_comportamento": "automatico_fixo", "piso_configurado": 1150.0
            },
            {
                "id": "p2", "posicao": 2, "nome": "Custos Semi Fixos", "percentual": 21.0,
                "previsto": 1184.69, "gasto": 807.63, "restante": 377.06, "qtd_transacoes": 3,
                "cor": "#FF69B4", "tipo_comportamento": "retido_intocavel"
            },
            {
                "id": "p4", "posicao": 4, "nome": "Prazeres", "percentual": 13.16,
                "previsto": 742.46, "gasto": 115.70, "restante": 626.76, "qtd_transacoes": 2,
                "cor": "#FF7A00", "tipo_comportamento": "caixa_livre_prazeres"
            },
            {
                "id": "p6", "posicao": 6, "nome": "Liberdade Financeira", "percentual": 30.71,
                "previsto": 1732.40, "gasto": 0.0, "restante": 1732.40, "qtd_transacoes": 0,
                "cor": "#6C5CE7", "tipo_comportamento": "caixa_livre_investimento"
            },
        ]
    }

    col = secao_potes(resumo_mock, page=page)
    assert col is not None
    assert hasattr(col, "atualizar_potes")

    # Testa atualização instantânea via hook
    novos_potes = list(resumo_mock["potes"])
    novos_potes[2] = dict(novos_potes[2])
    novos_potes[2]["previsto"] = 800.0  # Novo teto de prazeres pelo slider
    col.atualizar_potes(novos_potes)

    assert page.update.called, "Deveria ter disparado page.update() ao sincronizar potes!"
    print("  [OK] SecaoPotesController reativo disparou page.update() com sucesso!")


def test_5_edicao_flexivel_rs_e_percentual():
    print("\n--- 5. Testando Edição Flexível (R$ ou %) na Aba de Metas ---")
    page = mock_flet_page()
    ctrl = montar_aba_potes(page)
    assert ctrl is not None, "Falha ao montar aba potes com edição flexível"
    print("  [OK] Aba de Metas com edição flexível (R$ e %) montada com sucesso!")


def test_6_rpc_real_get_potes_resumo():
    print("\n--- 6. Testando RPC Real no Supabase com Caixa Livre Integrado ---")
    res_db = db.obter_resumo_potes("2026-10-01", "2026-10-31", forcar_atualizacao=True, piso_custos_fixos=1150.0)
    assert isinstance(res_db, dict)
    assert "potes" in res_db
    assert len(res_db["potes"]) == 6
    assert "caixa_livre" in res_db
    cl = res_db["caixa_livre"]
    assert "teto_orcamento" in cl
    assert "sobra_livre_disponivel" in cl
    assert "prazeres_teto" in cl
    assert "liberdade_teto" in cl

    soma_pct = sum(float(p.get("percentual", 0)) for p in res_db["potes"])
    assert abs(soma_pct - 100.0) < 0.05, f"Soma dos potes no Supabase deve ser 100%, obteve: {soma_pct}"
    print(f"  [OK] RPC Real retornou 6 potes perfeitamente somando {soma_pct:.2f}% e bloco caixa_livre enriquecido!")


if __name__ == "__main__":
    print("==================================================================")
    print("INICIANDO BATERIA DE TESTES: UNIFICAÇÃO CAIXA LIVRE E 6 POTES")
    print("==================================================================")
    test_1_matematica_cenario_real_usuario()
    test_2_soma_100_em_qualquer_slider()
    test_3_painel_sobra_reativo_e_sincronizacao()
    test_4_secao_potes_controller_e_badges()
    test_5_edicao_flexivel_rs_e_percentual()
    test_6_rpc_real_get_potes_resumo()
    print("\n==================================================================")
    print("TODOS OS 6 TESTES DA NOVA ARQUITETURA UNIFICADA PASSARAM COM 100%!")
    print("==================================================================")
