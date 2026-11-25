"""Smoke de UI: monta a seção de fatura e os cards com db simulado (valida API Flet 1.0.1)."""
from datetime import date, timedelta
from unittest import mock

import flet as ft

from core import dembox_fatura as D


def _box(nome, venc_dias, total, guardado, cartao="c1"):
    hoje = date.today()
    fat = [{"id": f"f-{nome}", "cartao_id": cartao, "valor_total": total, "status": "aberta",
            "data_fechamento": str(hoje - timedelta(days=5)),
            "data_vencimento": str(hoje + timedelta(days=venc_dias)), "valor_pago_parcial": 0}]
    movs = [{"tipo": "aporte", "valor": guardado, "status": "efetivado", "caixinha_id": nome}] if guardado else []
    return {"id": nome, "nome": f"Fatura {nome}", "cartao_id": cartao, "cartoes": {"nome": nome},
            "faturas": fat, "movimentos": movs, "situacao": D.calcular_situacao(fat, movs)}


def test_secao_renderiza_tres_status_e_banner():
    from views.widgets import dembox_fatura_ui as UI
    boxes = [_box("Coberto", 20, 500, 500), _box("Parcial", 15, 500, 100), _box("Risco", 2, 500, 50),
             _box("Zerada", 5, 0, 0)]
    page = mock.MagicMock()
    with mock.patch.object(UI.db, "listar_boxes_fatura", return_value=boxes), \
         mock.patch.object(UI.db, "listar_cartoes_sem_box_fatura", return_value=[{"id": "x", "nome": "Nubank"}]):
        raiz, recarregar, totais, buscar = UI.montar_secao_fatura(page)
        recarregar()
    grid = raiz.controls[2]
    assert len(grid.controls) == 4
    assert raiz.controls[0].visible is True
    assert len(raiz.controls[1].controls) == 1  # banner
    t = totais()
    assert t["qtd"] == 4 and t["guardado"] == 650 and t["meta"] == 1500
    textos = []
    def coletar(c):
        if isinstance(c, ft.Text):
            textos.append(c.value)
        for attr in ("content", "controls"):
            v = getattr(c, attr, None)
            if v is None: continue
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, ft.Control): coletar(x)
    coletar(grid)
    assert "🟢 Coberto" in textos and "🟡 Parcial" in textos and "🔴 Em risco" in textos
    assert "Sem fatura a pagar" in textos and "Fatura" in textos
