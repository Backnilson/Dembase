"""
=============================================================================
DemBase v3 — test_protecao_fluxo_e_metas_mensais.py
Testes automatizados das duas evoluções arquiteturais:
1. Inteligência de Proteção de Fluxo de Caixa (Contra a "Sobra Falsa"):
   - Teto Seguro de Gasto (baseado no Pior Dia / Gargalo)
   - Destaque de Gargalos e Janelas de Sobrevivência entre entradas (dias 6, 20 e 30)
   - Trava no Caixa Livre diferenciando Sobra Projetada do Mês vs Disponível Agora s/ Ficar Negativo
2. Metas Mensais Independentes (6 Potes e Caixa Livre por Período):
   - Escopo de porcentagens dos 6 Potes por Mês/Ano no Supabase (`listar_potes_mes`, `salvar_potes_mes`)
   - Escopo da retenção do Caixa Livre (`pct_investimento`) por Mês/Ano em `storage.py` e no Supabase
=============================================================================
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import supabase_client as db
from services import potes_service as svc
from core import storage
from views.widgets.sobra_card import calcular_rateio_sobra


class FakePage:
    def __init__(self):
        self._mem = {}


def test_1_cenario_real_sobra_falsa_dia_29_e_30():
    """
    Reproduz exatamente o cenário real descrito pelo usuário:
    - Entradas espalhadas nos dias 6, 20 e 30 (sendo R$ 484,00 no dia 30).
    - Contas pesadas nos dias 5, 7, 19, 20, 23 e 26.
    - No dia 29 o saldo acumulado chega ao limite crítico de R$ 192,95.
    - No dia 30 cai R$ 484,00, fechando o mês com Sobra Projetada = R$ 676,95.
    Verifica que:
      * Sobra Projetada do Mês = R$ 676,95
      * Menor Saldo Futuro (Gargalo) = R$ 192,95 (data_gargalo = 2026-10-29)
      * Teto Seguro de Gasto (Disponível Agora s/ Ficar Negativo) = R$ 192,95
      * Sobra Falsa Travada = R$ 484,00
      * Se gastar mais que R$ 192,95 antes do dia 30, ficaria negativo no dia 29!
    """
    print("\n[Teste 1] Cenário Real: Blindagem contra 'Sobra Falsa' (Gargalo de R$ 192,95 no dia 29 vs R$ 484,00 no dia 30)...")

    # Monta os lançamentos dos dias citados (5, 6, 7, 19, 20, 23, 26, 30)
    # Dia 05: Despesa R$ 100,00 -> Acum: -100,00
    # Dia 06: Receita R$ 1.500,00 -> Acum: +1.400,00
    # Dia 07: Despesa R$ 600,00 -> Acum: +800,00
    # Dia 19: Despesa R$ 300,00 -> Acum: +500,00
    # Dia 20: Receita R$ 1.200,00 e Despesa R$ 700,00 -> Acum: +1.000,00
    # Dia 23: Despesa R$ 450,00 -> Acum: +550,00
    # Dia 26: Despesa R$ 357,05 -> Acum: +192,95 (Mantém R$ 192,95 nos dias 26, 27, 28 e 29!)
    # Dia 30: Receita R$ 484,00 -> Acum: +676,95
    dias_lista = [
        {"data": "2026-10-05", "total_receitas": 0.0, "total_despesas": 100.0, "despesas_conta": 100.0, "despesas_cartao": 0.0, "qtd_lancamentos": 1},
        {"data": "2026-10-06", "total_receitas": 1500.0, "total_despesas": 0.0, "despesas_conta": 0.0, "despesas_cartao": 0.0, "qtd_lancamentos": 1},
        {"data": "2026-10-07", "total_receitas": 0.0, "total_despesas": 600.0, "despesas_conta": 600.0, "despesas_cartao": 0.0, "qtd_lancamentos": 1},
        {"data": "2026-10-19", "total_receitas": 0.0, "total_despesas": 300.0, "despesas_conta": 300.0, "despesas_cartao": 0.0, "qtd_lancamentos": 1},
        {"data": "2026-10-20", "total_receitas": 1200.0, "total_despesas": 700.0, "despesas_conta": 300.0, "despesas_cartao": 400.0, "qtd_lancamentos": 2},
        {"data": "2026-10-23", "total_receitas": 0.0, "total_despesas": 450.0, "despesas_conta": 450.0, "despesas_cartao": 0.0, "qtd_lancamentos": 1},
        {"data": "2026-10-26", "total_receitas": 0.0, "total_despesas": 357.05, "despesas_conta": 357.05, "despesas_cartao": 0.0, "qtd_lancamentos": 1},
        {"data": "2026-10-30", "total_receitas": 484.0, "total_despesas": 0.0, "despesas_conta": 0.0, "despesas_cartao": 0.0, "qtd_lancamentos": 1},
    ]

    acum_map = db._calcular_acumulados_calendario(
        dias_lista,
        "2026-10-01",
        "2026-10-31",
        "2026-09-27",
        "2026-11-07",
    )

    # Analisando a partir do dia 10/10/2026 (após o pagamento do dia 06, no meio do mês)
    prot = db.calcular_protecao_fluxo_caixa(
        dias_lista,
        acum_map,
        "2026-10-01",
        "2026-10-31",
        data_ref_str="2026-10-10",
    )

    assert abs(prot["sobra_projetada"] - 676.95) < 0.01, f"Esperado 676.95, obteve {prot['sobra_projetada']}"
    assert abs(prot["menor_saldo_futuro"] - 192.95) < 0.01, f"Esperado 192.95, obteve {prot['menor_saldo_futuro']}"
    assert prot["data_gargalo"] == "2026-10-29", f"Gargalo deveria apontar para a véspera da entrada (2026-10-29), obteve {prot['data_gargalo']}"
    assert prot["data_inicio_gargalo"] == "2026-10-26", f"Início do vale deveria ser 2026-10-26, obteve {prot['data_inicio_gargalo']}"
    assert abs(prot["teto_seguro_gasto"] - 192.95) < 0.01, f"Teto seguro deveria ser 192.95, obteve {prot['teto_seguro_gasto']}"
    assert abs(prot["sobra_falsa_travada"] - 484.00) < 0.01, f"Sobra falsa travada deveria ser 484.00, obteve {prot['sobra_falsa_travada']}"
    assert prot["tem_armadilha_fluxo"] is True
    assert prot["fica_negativo_no_meio"] is False
    assert prot["proxima_entrada_data"] == "2026-10-20"
    assert abs(prot["proxima_entrada_valor"] - 1200.00) < 0.01

    # Verifica as Janelas de Sobrevivência
    janelas = prot["janelas_sobrevivencia"]
    assert len(janelas) >= 3, f"Deveria ter janelas de sobrevivência para cada ciclo de entrada, obteve {len(janelas)}"

    # Verifica o rateio no Painel de Caixa Livre com a trava ativa vs desativada
    rateio_travado = calcular_rateio_sobra(
        receitas=3184.00,
        despesas=2507.05,
        pct_investimento=50.0,
        protecao_fluxo=prot,
        travar_pelo_teto_seguro=True,
    )
    assert abs(rateio_travado["sobra_projetada"] - 676.95) < 0.01
    assert abs(rateio_travado["teto_seguro_gasto"] - 192.95) < 0.01
    assert abs(rateio_travado["sobra_falsa_travada"] - 484.00) < 0.01
    # Com 50% de retenção sobre o Teto Seguro (R$ 192,95):
    assert abs(rateio_travado["valor_investimento"] - 96.48) < 0.02
    assert abs(rateio_travado["valor_livre_culpa"] - 96.47) < 0.02
    # E preserva os valores projetados do mês inteiro (50% de R$ 676,95 = R$ 338,48):
    assert abs(rateio_travado["valor_investimento_projetado"] - 338.48) < 0.02
    assert abs(rateio_travado["valor_livre_projetado"] - 338.47) < 0.02

    print("  -> OK! Sobra Projetada = R$ 676,95 | Teto Seguro (Dia 29) = R$ 192,95 | Sobra Falsa Retida (Dia 30) = R$ 484,00")


def test_2_isolamento_mensal_caixa_livre_storage():
    """
    Verifica que alterar a porcentagem do Caixa Livre (ex: 70% em Novembro/2026 vs 30% em Outubro/2026)
    salva e recupera cada mês de forma totalmente independente, com herança para meses futuros ainda não configurados.
    """
    print("\n[Teste 2] Isolamento Mensal do Caixa Livre (Sobra do Período) por Mês/Ano...")
    page = FakePage()
    # Limpa mapa local de teste antes de iniciar o cenário
    d_loc = storage._ler_local_json()
    d_loc.pop("sobra_pct_por_mes", None)
    storage._salvar_local_json(d_loc)

    # Configura Outubro/2026 com 30% para investir (mês mais apertado)
    storage.salvar_percentual_sobra_investimento_sync(page, 30.0, mes=10, ano=2026)
    # Configura Novembro/2026 com 70% para investir (mês forte)
    storage.salvar_percentual_sobra_investimento_sync(page, 70.0, mes=11, ano=2026)

    pct_out = storage.obter_percentual_sobra_investimento(page, 50.0, mes=10, ano=2026)
    pct_nov = storage.obter_percentual_sobra_investimento(page, 50.0, mes=11, ano=2026)
    # Dezembro/2026 ainda não configurado -> herda automaticamente do último mês anterior configurado (Nov/2026 = 70%)
    pct_dez_herdado = storage.obter_percentual_sobra_investimento(page, 50.0, mes=12, ano=2026)

    assert abs(pct_out - 30.0) < 0.01, f"Outubro/2026 deveria ser 30%, obteve {pct_out}"
    assert abs(pct_nov - 70.0) < 0.01, f"Novembro/2026 deveria ser 70%, obteve {pct_nov}"
    assert abs(pct_dez_herdado - 70.0) < 0.01, f"Dezembro/2026 (novo) deveria herdar 70% de Novembro, obteve {pct_dez_herdado}"

    # Agora muda Dezembro/2026 para 40% e garante que Outubro (30%) e Novembro (70%) não mudaram!
    storage.salvar_percentual_sobra_investimento_sync(page, 40.0, mes=12, ano=2026)
    assert abs(storage.obter_percentual_sobra_investimento(page, 50.0, mes=10, ano=2026) - 30.0) < 0.01
    assert abs(storage.obter_percentual_sobra_investimento(page, 50.0, mes=11, ano=2026) - 70.0) < 0.01
    assert abs(storage.obter_percentual_sobra_investimento(page, 50.0, mes=12, ano=2026) - 40.0) < 0.01

    print("  -> OK! Out/2026 = 30%, Nov/2026 = 70%, Dez/2026 = 40% (100% independentes!)")


def test_3_isolamento_mensal_6_potes_supabase():
    """
    Autentica com o usuário de demonstração (`teste@dembase.com` / `teste123`) no Supabase
    e valida que salvar as metas dos 6 Potes e do Caixa Livre em Novembro/2026 jamais
    altera Outubro/2026 ou Dezembro/2026.
    """
    print("\n[Teste 3] Isolamento Mensal dos 6 Potes e Caixa Livre no Supabase (Banco Real)...")
    try:
        db.fazer_login("teste@dembase.com", "teste123")
    except Exception as ex:
        print(f"  [Aviso] Login demo indisponivel ({ex}), pulando teste online.")
        return

    # 1. Carrega potes de Outubro/2026 e define configuração A: [55, 10, 10, 10, 10, 5]
    potes_out = svc.carregar_potes(mes=10, ano=2026)
    assert len(potes_out) == 6
    cfg_outubro = [
        {"id": potes_out[0].id, "nome": potes_out[0].nome, "percentual": Decimal("55")},
        {"id": potes_out[1].id, "nome": potes_out[1].nome, "percentual": Decimal("10")},
        {"id": potes_out[2].id, "nome": potes_out[2].nome, "percentual": Decimal("10")},
        {"id": potes_out[3].id, "nome": potes_out[3].nome, "percentual": Decimal("10")},
        {"id": potes_out[4].id, "nome": potes_out[4].nome, "percentual": Decimal("10")},
        {"id": potes_out[5].id, "nome": potes_out[5].nome, "percentual": Decimal("5")},
    ]
    svc.salvar_configuracao(cfg_outubro, mes=10, ano=2026)

    # 2. Define configuração B exclusiva para Novembro/2026 (mês forte): [40, 25, 15, 10, 5, 5]
    cfg_novembro = [
        {"id": potes_out[0].id, "nome": potes_out[0].nome, "percentual": Decimal("40")},
        {"id": potes_out[1].id, "nome": potes_out[1].nome, "percentual": Decimal("25")},
        {"id": potes_out[2].id, "nome": potes_out[2].nome, "percentual": Decimal("15")},
        {"id": potes_out[3].id, "nome": potes_out[3].nome, "percentual": Decimal("10")},
        {"id": potes_out[4].id, "nome": potes_out[4].nome, "percentual": Decimal("5")},
        {"id": potes_out[5].id, "nome": potes_out[5].nome, "percentual": Decimal("5")},
    ]
    svc.salvar_configuracao(cfg_novembro, mes=11, ano=2026)

    # 3. Verifica que Outubro/2026 continua [55, 10, 10, 10, 10, 5] e Novembro/2026 é [40, 25, 15, 10, 5, 5]
    p_out_check = svc.carregar_potes(mes=10, ano=2026)
    p_nov_check = svc.carregar_potes(mes=11, ano=2026)

    assert [int(p.percentual) for p in p_out_check] == [55, 10, 10, 10, 10, 5], f"Outubro foi alterado indevidamente: {p_out_check}"
    assert [int(p.percentual) for p in p_nov_check] == [40, 25, 15, 10, 5, 5], f"Novembro incorreto: {p_nov_check}"

    # 4. Verifica get_potes_resumo respeitando as metas de cada mês
    res_out = db.obter_resumo_potes("2026-10-01", "2026-10-31")
    res_nov = db.obter_resumo_potes("2026-11-01", "2026-11-30")
    pcts_res_out = [int(float(p["percentual"])) for p in (res_out.get("potes") or [])]
    pcts_res_nov = [int(float(p["percentual"])) for p in (res_nov.get("potes") or [])]
    assert pcts_res_out == [55, 10, 10, 10, 10, 5], f"Resumo Potes Out/2026 divergente: {pcts_res_out}"
    assert pcts_res_nov == [40, 25, 15, 10, 5, 5], f"Resumo Potes Nov/2026 divergente: {pcts_res_nov}"

    # 5. Verifica persistência mensal do Caixa Livre no Supabase
    db.salvar_config_caixa_livre_mes(10, 2026, 30.0)
    db.salvar_config_caixa_livre_mes(11, 2026, 70.0)
    cfg_cl_out = db.obter_config_caixa_livre_mes(10, 2026, forcar_atualizacao=True)
    cfg_cl_nov = db.obter_config_caixa_livre_mes(11, 2026, forcar_atualizacao=True)
    assert abs(float(cfg_cl_out.get("pct_investimento", 0)) - 30.0) < 0.01
    assert abs(float(cfg_cl_nov.get("pct_investimento", 0)) - 70.0) < 0.01

    # Restaura Outubro/2026 e Novembro/2026 para o padrão 55/10/10/10/10/5 para manter a demo limpa
    svc.salvar_configuracao(cfg_outubro, mes=11, ano=2026)
    db.salvar_config_caixa_livre_mes(10, 2026, 50.0)
    db.salvar_config_caixa_livre_mes(11, 2026, 50.0)

    print("  -> OK! 6 Potes e Caixa Livre 100% isolados por Mês/Ano no PostgreSQL/Supabase!")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    test_1_cenario_real_sobra_falsa_dia_29_e_30()
    test_2_isolamento_mensal_caixa_livre_storage()
    test_3_isolamento_mensal_6_potes_supabase()
    print("\n[OK] TODOS OS TESTES DE PROTECAO DE FLUXO DE CAIXA E METAS MENSAIS PASSARAM COM SUCESSO!")
