"""
Testes offline (sem Supabase): Liberar Sobra, espelhamento da Configuração e quebra das tags mobile.
Execute: python test_liberar_sobra_e_espelho_config.py
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from core import potes as P
from core import storage
from services import potes_service as svc
from views.widgets import potes_config
from views.widgets.potes_cards import card_pote, SecaoPotesController
from views.widgets.sobra_card import PainelGestaoSobra


def _potes(gastos):
    base = {1: 1200.0, 2: 0.0, 3: 0.0, 4: 100.0, 5: 0.0, 6: 0.0}
    base.update(gastos)
    return [
        {"id": f"id{d['posicao']}", "posicao": d["posicao"], "nome": d["nome"], "cor": d["cor"],
         "percentual": float(d["percentual"]), "gasto": base[d["posicao"]], "qtd_transacoes": 1}
        for d in P.POTES_PADRAO
    ]


def mock_page():
    page = MagicMock()
    page.width, page.height = 1280, 800
    store = {}
    page.session = MagicMock()
    page.session.get = lambda k, d=None: store.get(k, d)
    page.session.set = lambda k, v: store.__setitem__(k, v)
    return page


def test_calculo_liberar_sobra():
    rec = 5641.36
    potes = _potes({2: 300.0})  # Semi Fixos: limite 20% = 1128,27 | gasto 300
    base = P.calcular_arquitetura_unificada_potes(rec, potes, 1150.0, 50.0, None, False)
    lib = P.calcular_arquitetura_unificada_potes(rec, potes, 1150.0, 50.0, None, False, potes_liberados={2})
    p2b = base["potes"][1]
    p2l = lib["potes"][1]
    assert p2b["liberavel"] and not p2b["liberado"]
    assert p2l["previsto"] == 300.0 and p2l["restante"] == 0.0, p2l
    assert p2l["liberado"] and abs(p2l["liberado_valor"] - round(rec * 0.20 - 300.0, 2)) < 0.01
    folga = lib["caixa_livre"]["teto_orcamento"] - base["caixa_livre"]["teto_orcamento"]
    assert abs(folga - p2l["liberado_valor"]) < 0.30, folga  # base legada arredonda pct a 2 casas
    # Divisão pelo slider 50/50
    dl = lib["caixa_livre"]["liberdade_teto"] - base["caixa_livre"]["liberdade_teto"]
    dp = lib["caixa_livre"]["prazeres_teto"] - base["caixa_livre"]["prazeres_teto"]
    assert abs(dl - folga / 2) < 0.30 and abs(dp - folga / 2) < 0.30
    assert abs(lib["soma_percentuais"] - 100.0) < 0.02, lib["soma_percentuais"]
    # Pote automático (fixos) e Prazeres não são liberáveis por esta via
    lib2 = P.calcular_arquitetura_unificada_potes(rec, potes, 1150.0, 50.0, None, False, potes_liberados={1, 4})
    assert lib2["caixa_livre"]["teto_orcamento"] == base["caixa_livre"]["teto_orcamento"]
    print("  [OK] Liberar Sobra: teto=gasto, folga vai ao Caixa Livre e divide pelo slider")


def test_card_botoes():
    pote = _potes({2: 300.0})
    arq = P.calcular_arquitetura_unificada_potes(5000.0, pote, 1150.0, 50.0, None, False)
    cb = MagicMock()
    c = card_pote(arq["potes"][1], on_liberar=cb)
    textos = []

    def varrer(ctrl):
        if isinstance(ctrl, ft.Text):
            textos.append(ctrl.value)
        for attr in ("controls", "content"):
            v = getattr(ctrl, attr, None)
            if isinstance(v, list):
                [varrer(x) for x in v]
            elif v is not None and not isinstance(v, str):
                varrer(v)
    varrer(c)
    assert any("Liberar Sobra" in (t or "") for t in textos), textos
    c_fix = card_pote(arq["potes"][0], on_liberar=cb)
    t2 = []
    textos.clear(); varrer(c_fix)
    assert not any("Liberar Sobra" in (t or "") for t in textos)
    print("  [OK] Botão Liberar Sobra só aparece em potes manuais com saldo")


def test_painel_atualiza_na_hora():
    page = mock_page()
    storage.salvar_pote_liberado_sync = storage.salvar_pote_liberado_sync
    painel = PainelGestaoSobra(page=page, mobile=False)
    recebidos = []
    painel.on_potes_alterados = lambda ps: recebidos.append(ps)
    painel.mes_atual, painel.ano_atual = 11, 2099
    painel.receitas = 5641.36
    painel.potes_dados = _potes({2: 300.0})
    antes = painel.obter_dados_atuais()["teto_caixa_livre"]
    painel.alternar_liberacao_pote(2, True)
    depois = painel.obter_dados_atuais()["teto_caixa_livre"]
    assert depois > antes and recebidos, (antes, depois)
    assert page.update.called
    painel.alternar_liberacao_pote(2, False)
    assert abs(painel.obter_dados_atuais()["teto_caixa_livre"] - antes) < 0.001
    # isolamento por mês
    assert storage.obter_potes_liberados(page, 12, 2099) == set()
    print("  [OK] Liberar/Restaurar atualiza painel, potes e KPIs; isolado por mês")


def test_config_espelha_dashboard():
    chamadas = {}
    registros = [
        P.Pote(id=f"id{d['posicao']}", posicao=d["posicao"], nome=d["nome"],
               percentual=d["percentual"], cor=d["cor"])
        for d in P.POTES_PADRAO
    ]
    ctxs = {
        "2099-11-01": {"renda": 5641.36, "gastos": {1: 1200.0, 2: 300.0, 4: 100.0}, "qtd": {}, "tem_receita": True},
        "2099-12-01": {"renda": 3000.00, "gastos": {1: 1150.0}, "qtd": {}, "tem_receita": True},
    }

    def fake_ctx(di, df, piso=1150.0):
        chamadas.setdefault("ctx", []).append((di, df))
        return ctxs[di]

    svc.carregar_potes_com_meta_mes = lambda mes=None, ano=None: (registros, False)
    svc.carregar_contexto_mes = fake_ctx
    svc.obter_pct_investimento_db = lambda m, a: (50.0, True)
    svc.ler_renda_referencia = lambda: Decimal("0")

    page = mock_page()
    page.session.set("periodo_mes", 11)
    page.session.set("periodo_ano", 2099)
    salvou = []
    ctrl = potes_config.montar_aba_potes(
        page, mes=11, ano=2099, data_ini="2099-11-01", data_fim="2099-11-30", ao_salvar=lambda: salvou.append(1)
    )
    assert chamadas["ctx"][0] == ("2099-11-01", "2099-11-30")

    # Varre controles para achar o campo da receita e as prévias
    achados = {"tf": [], "prev": 0}

    def varrer(c):
        if isinstance(c, ft.TextField) and c.read_only:
            achados["tf"].append(c.value)
        if isinstance(c, ft.Text) and c.spans:
            achados["prev"] += 1
        for attr in ("controls", "content"):
            v = getattr(c, attr, None)
            if isinstance(v, list):
                [varrer(x) for x in v]
            elif v is not None and not isinstance(v, str):
                varrer(v)
    varrer(ctrl)
    assert any("5.641,36" in (v or "") for v in achados["tf"]), achados
    assert achados["prev"] == 6, achados
    print("  [OK] Config puxa a Receita Real do mês e mostra prévia nos 6 potes")


def test_tags_mobile_quebram():
    import inspect
    from views.widgets.report import transaction_list as tl
    src = inspect.getsource(tl)
    trecho = src[src.index("linha_rodape_mobile = ft.Row("):][:900]
    assert "wrap=True" in trecho and "ScrollMode.HIDDEN" not in trecho
    print("  [OK] Tags mobile usam quebra (wrap) sem corte a seco")


if __name__ == "__main__":
    for t in (test_calculo_liberar_sobra, test_card_botoes, test_painel_atualiza_na_hora,
              test_config_espelha_dashboard, test_tags_mobile_quebram):
        print(t.__name__)
        t()
    print("TODOS OS TESTES PASSARAM")
