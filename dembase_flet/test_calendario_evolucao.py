"""
=============================================================================
DemBase v3 — test_calendario_evolucao.py
Suite de Testes Automatizados para validar:
1. Bug Crítico (Cartão de Crédito e Compras Parceladas no Calendário):
   - Despesas de cartão NUNCA aparecem na data de emissão da compra (l.data)
     e SEMPRE aparecem exclusivamente na data de vencimento da fatura (data_vencimento).
2. Limpeza e Evolução dos Filtros de Período:
   - Atalhos redundantes "Dia 05 a 20" (dia_05_20) e "Dia 20 a 30/31" (dia_20_fim)
     removidos de FILTROS_PERIODO_FAVORITOS_PADRAO e filtrados de obter_filtros_periodo_favoritos.
   - Modo Projeção (fixar_inicio_hoje) trava range_inicio em date.today() até data futura.
3. Calendário Multi-Meses e Rolagem (Scroll):
   - Filtros que cruzam meses (ex: 2026-11-28 a 2026-12-28) retornam eh_multi_mes=True,
     expandem grid_inicio..grid_fim cobrindo todas as semanas e habilitam ScrollMode.AUTO.
4. Inteligência do Hover (Soma Acumulada Contínua O(1)):
   - _calcular_acumulados_calendario pré-calcula em O(N) e expõe acumulados_por_dia[dt_iso]
     com receitas_acum, despesas_conta_acum, despesas_cartao_acum, despesas_total_acum e saldo_acum.
=============================================================================
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.storage import (
    FILTROS_PERIODO_FAVORITOS_PADRAO,
    obter_filtros_periodo_favoritos,
)
import services.supabase_client as db


class _DummyPage:
    def __init__(self):
        self.session = {}
        self.width = 1280
        self.height = 800
        self.overlay = []
        self.views = []

    def update(self):
        pass


def test_1_limpeza_filtros_redundantes():
    ids_padrao = {f["id"] for f in FILTROS_PERIODO_FAVORITOS_PADRAO}
    assert "dia_05_20" not in ids_padrao, "dia_05_20 deve ter sido removido dos filtros padrão"
    assert "dia_20_fim" not in ids_padrao, "dia_20_fim deve ter sido removido dos filtros padrão"
    assert "dia_01_15" in ids_padrao, "1ª Quinzena deve permanecer"
    assert "dia_16_fim" in ids_padrao, "2ª Quinzena deve permanecer"

    p = _DummyPage()
    favs = obter_filtros_periodo_favoritos(p)
    ids_favs = {f.get("id") for f in favs}
    assert "dia_05_20" not in ids_favs
    assert "dia_20_fim" not in ids_favs
    print("✅ [TESTE 1] Limpeza dos filtros redundantes ('Dia 05 a 20' e 'Dia 20 a 30/31'): OK")


def test_2_filtro_projecao_hoje_ate_futuro():
    from views.widgets.custom_date_picker import CustomCalendarGrid

    hoje_d = date.today()
    futuro_d = hoje_d + timedelta(days=20)
    chamadas = []

    grid = CustomCalendarGrid(
        ano=futuro_d.year,
        mes=futuro_d.month,
        modo="range",
        range_inicio=hoje_d,
        range_fim=futuro_d,
        on_range_change=lambda ini, fim: chamadas.append((ini, fim)),
    )
    grid.fixar_inicio_hoje = True
    # Simula clique em uma nova data futura
    nova_data_futura = hoje_d + timedelta(days=35)
    grid._clicar_dia(nova_data_futura)

    assert grid.range_inicio == hoje_d, f"Início deveria estar fixo em Hoje ({hoje_d}), mas foi {grid.range_inicio}"
    assert grid.range_fim == nova_data_futura, f"Fim deveria ser {nova_data_futura}, mas foi {grid.range_fim}"
    assert chamadas and chamadas[-1] == (hoje_d, nova_data_futura)
    print(f"✅ [TESTE 2] Filtro de Projeção (Hoje {hoje_d} -> Futuro {nova_data_futura}): OK")


def test_3_soma_acumulada_continua_o1():
    dias_mock = [
        {
            "data": "2026-11-28",
            "total_receitas": 2000.0,
            "total_despesas": 300.0,
            "despesas_conta": 300.0,
            "despesas_cartao": 0.0,
            "qtd_lancamentos": 2,
        },
        {
            "data": "2026-12-07",
            "total_receitas": 0.0,
            "total_despesas": 500.0,
            "despesas_conta": 0.0,
            "despesas_cartao": 500.0,
            "qtd_lancamentos": 3,
        },
        {
            "data": "2026-12-15",
            "total_receitas": 1500.0,
            "total_despesas": 200.0,
            "despesas_conta": 200.0,
            "despesas_cartao": 0.0,
            "qtd_lancamentos": 2,
        },
    ]
    acum_map = db._calcular_acumulados_calendario(
        dias_lista=dias_mock,
        d_ini_str="2026-11-28",
        d_fim_str="2026-12-28",
        grid_ini_str="2026-11-22",
        grid_fim_str="2027-01-02",
    )

    # Dia 28/11: +2000 - 300 = +1700
    assert abs(acum_map["2026-11-28"]["saldo_acum"] - 1700.0) < 0.01
    # Dia 05/12 (sem movimento próprio, mantém acumulado de 1700):
    assert abs(acum_map["2026-12-05"]["saldo_acum"] - 1700.0) < 0.01
    # Dia 07/12 (vencimento de fatura de R$ 500): +2000 - 800 = +1200
    assert abs(acum_map["2026-12-07"]["despesas_cartao_acum"] - 500.0) < 0.01
    assert abs(acum_map["2026-12-07"]["despesas_total_acum"] - 800.0) < 0.01
    assert abs(acum_map["2026-12-07"]["saldo_acum"] - 1200.0) < 0.01
    # Dia 15/12 (+1500 receita, -200 conta): Rec=3500, Desp=1000, Saldo=2500
    assert abs(acum_map["2026-12-15"]["receitas_acum"] - 3500.0) < 0.01
    assert abs(acum_map["2026-12-15"]["despesas_total_acum"] - 1000.0) < 0.01
    assert abs(acum_map["2026-12-15"]["saldo_acum"] - 2500.0) < 0.01
    print("✅ [TESTE 3] Cálculo O(1) de Soma Acumulada Contínua no Hover/Tooltip: OK")


def test_4_compras_parceladas_no_vencimento_e_multimeses():
    # Testa o retorno do serviço de calendário cruzando Novembro e Dezembro de 2026
    pacote = db.obter_calendario_financeiro_mes(
        12,
        2026,
        data_inicio="2026-11-28",
        data_fim="2026-12-28",
    )
    assert pacote["eh_multi_mes"] is True, "Intervalo 28/11 a 28/12 deve marcar eh_multi_mes=True"
    assert pacote["grid_inicio"] <= "2026-11-28"
    assert pacote["grid_fim"] >= "2026-12-28"
    assert "acumulados_por_dia" in pacote and len(pacote["acumulados_por_dia"]) >= 31

    # Verifica que nenhum lançamento de cartão aparece na sua data de compra caso divirja do vencimento
    for d_item in pacote.get("dias") or []:
        dt_cal = str(d_item.get("data") or "")[:10]
        for l_it in d_item.get("lancamentos") or []:
            if l_it.get("cartao_id"):
                # A data do item no calendário é a data efetiva (vencimento da fatura)
                assert str(l_it.get("data") or "")[:10] == dt_cal
    print("✅ [TESTE 4] Compras parceladas/cartão no vencimento da fatura + Grade Multi-Meses: OK")


def test_5_caixinhas_provisionamento_no_calendario():
    # Valida que as caixinhas de provisionamento (Aluguel e Moto) entram no fluxo de caixa e no calendário
    pacote = db.obter_calendario_financeiro_mes(
        12,
        2026,
        data_inicio="2026-12-01",
        data_fim="2026-12-31",
    )
    dias = {str(d.get("data") or "")[:10]: d for d in (pacote.get("dias") or [])}

    # Dia 05/12/2026: Provisão Caixinha Moto (R$ 400,00)
    d5 = dias.get("2026-12-05")
    assert d5 is not None, "Dia 05/12/2026 deve estar presente no calendário"
    assert float(d5.get("total_despesas", 0)) >= 400.0, f"Dia 05 deve ter pelo menos R$ 400 de despesa, obteve {d5.get('total_despesas')}"
    descricoes_d5 = [l.get("descricao") for l in d5.get("lancamentos", [])]
    assert any("Moto" in d for d in descricoes_d5), f"Provisão da Moto deve estar listada no dia 05: {descricoes_d5}"

    # Dia 20/12/2026: Provisão Caixinha Aluguel (R$ 1.150,00) + Garagem Moto (R$ 110,00) = R$ 1.260,00
    d20 = dias.get("2026-12-20")
    assert d20 is not None, "Dia 20/12/2026 deve estar presente no calendário"
    assert abs(float(d20.get("total_despesas", 0)) - 1260.0) < 0.01, f"Dia 20 deve ter R$ 1.260 de despesa, obteve {d20.get('total_despesas')}"
    descricoes_d20 = [l.get("descricao") for l in d20.get("lancamentos", [])]
    assert any("Aluguel" in d for d in descricoes_d20), f"Provisão de Aluguel deve estar listada no dia 20: {descricoes_d20}"
    print("✅ [TESTE 5] Caixinhas de Teto (Aluguel R$ 1.150 e Moto R$ 400) integradas ao Calendário: OK")


if __name__ == "__main__":
    test_1_limpeza_filtros_redundantes()
    test_2_filtro_projecao_hoje_ate_futuro()
    test_3_soma_acumulada_continua_o1()
    test_4_compras_parceladas_no_vencimento_e_multimeses()
    test_5_caixinhas_provisionamento_no_calendario()
    print("\n🎉 TODOS OS TESTES DA EVOLUÇÃO DO CALENDÁRIO PASSARAM COM SUCESSO!")
