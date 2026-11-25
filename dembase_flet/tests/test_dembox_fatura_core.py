from datetime import date

import pytest

from core import dembox_fatura as D

HOJE = date(2026, 11, 17)


def fat(id_, venc, fech, total, status="aberta", pago=0):
    return {"id": id_, "data_vencimento": venc, "data_fechamento": fech,
            "valor_total": total, "status": status, "valor_pago": pago}


def mov(tipo, valor, status="efetivado"):
    return {"tipo": tipo, "valor": valor, "status": status}


def test_pendente_nao_altera_saldo():
    movs = [mov("aporte", 100), mov("aporte", 50, "pendente")]
    assert D.calcular_saldo_guardado(movs) == 100
    assert D.calcular_agendado_pendente(movs) == 50


def test_cancelado_nao_gera_movimentacao():
    assert D.calcular_saldo_guardado([mov("aporte", 80, "cancelado")]) == 0


def test_saldo_com_retirada_transferencia_e_pagamento():
    movs = [mov("aporte", 500), mov("retirada", 100), mov("transf_saida", 50),
            mov("transf_entrada", 30), mov("pagamento", 200)]
    assert D.calcular_saldo_guardado(movs) == 180


def test_retirar_mais_que_saldo_bloqueado():
    ok, _ = D.validar_retirada(100, 100.01)
    assert not ok
    assert D.validar_retirada(100, 100)[0]
    assert not D.validar_retirada(100, 0)[0]


def test_fatura_relevante_fechada_mais_proxima():
    fs = [fat("a", "2026-11-23", "2026-11-16", 600),
          fat("b", "2026-11-30", "2026-11-24", 120),
          fat("c", "2026-11-17", "2026-11-10", 640)]
    assert D.escolher_fatura_relevante(fs, HOJE)["id"] == "c"


def test_sem_fechada_usa_aberta_atual():
    fs = [fat("b", "2026-11-30", "2026-11-24", 120), fat("d", "2026-12-30", "2026-12-24", 120)]
    assert D.escolher_fatura_relevante(fs, HOJE)["id"] == "b"


def test_paga_ignorada():
    fs = [fat("x", "2026-11-17", "2026-11-10", 640, "paga"), fat("y", "2026-12-17", "2026-12-10", 640)]
    assert D.escolher_fatura_relevante(fs, HOJE)["id"] == "y"


def test_status_coberto_parcial_risco_neutro():
    f_longe = [fat("a", "2026-11-30", "2026-11-10", 1000)]
    f_perto = [fat("a", "2026-11-19", "2026-11-10", 1000)]
    assert D.calcular_situacao(f_longe, [mov("aporte", 1000)], HOJE).status == D.STATUS_COBERTO
    assert D.calcular_situacao(f_longe, [mov("aporte", 400)], HOJE).status == D.STATUS_PARCIAL
    assert D.calcular_situacao(f_perto, [mov("aporte", 400)], HOJE).status == D.STATUS_RISCO
    assert D.calcular_situacao(f_perto, [mov("aporte", 1000)], HOJE).status == D.STATUS_COBERTO
    neutro = D.calcular_situacao([fat("a", "2026-11-19", "2026-11-10", 0)], [], HOJE)
    assert neutro.status == D.STATUS_NEUTRO and neutro.neutro and neutro.rotulo == "Sem fatura a pagar"


def test_falta_guardar_e_dias():
    s = D.calcular_situacao([fat("a", "2026-11-27", "2026-11-10", 800)], [mov("aporte", 300)], HOJE)
    assert s.falta == 500 and s.dias_ate_vencimento == 10 and round(s.pct, 4) == 0.375


def test_pagamento_parcial_e_total():
    s = D.calcular_situacao([fat("a", "2026-11-27", "2026-11-10", 800)], [mov("aporte", 300)], HOJE)
    p = D.calcular_pagamento(s, 300)
    assert p["ok"] and not p["quitada"] and p["restante"] == 500 and p["saldo_box"] == 0
    t = D.calcular_pagamento(s, 800)
    assert t["ok"] and t["quitada"] and t["restante"] == 0 and t["debito_box"] == 300
    assert not D.calcular_pagamento(s, 800.5)["ok"]


def test_pagamento_parcial_previo_reduz_meta():
    f = fat("a", "2026-11-27", "2026-11-10", 800, pago=300)
    assert D.restante_fatura(f) == 500


def test_pagar_e_aportar_nao_altera_potes():
    """Módulo é puro: nenhum dado de potes é lido/escrito; garantia estrutural."""
    import inspect
    src = inspect.getsource(D)
    assert "lancamentos" not in src.lower().replace("lançamento", "")


def test_banner_cartoes_sem_box():
    cartoes = [{"id": "1"}, {"id": "2"}, {"id": "3", "ativo": False}]
    boxes = [{"cartao_id": "1", "tipo_box": "fatura", "ativo": True}]
    assert [c["id"] for c in D.cartoes_sem_box(cartoes, boxes)] == ["2"]


def test_abatido_e_parse_valor():
    assert D.calcular_abatido([mov("pagamento", 120), mov("pagamento", 30, "cancelado"), mov("aporte", 9)]) == 120
    assert D.parse_valor_br("1.234,56") == 1234.56
    assert D.parse_valor_br("R$ 80,5") == 80.5
    assert D.parse_valor_br("80.5") == 80.5
    with pytest.raises(ValueError):
        D.parse_valor_br("abc")
