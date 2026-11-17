"""
Teste Automatizado de Ponta a Ponta (Auditoria Sênior):
1. Modal "Reajustar Fatura": Alterar Data de Vencimento + Ocultar Quando Paga
2. Indicador Visual de Status da Fatura (Pendente / Aberta / Vencida / Paga) no Dropdown e Fora do Dropdown
3. Calendário Financeiro: Fatura Paga em 17/11/2026 (MercadoPago R$ 341,57) migra do dia 19 para o dia 17
4. Aba "Faturas Fechadas" em Cartões de Crédito: Exibe a fatura paga do MercadoPago (R$ 341,57) com card clicável
"""
from __future__ import annotations

import asyncio
from datetime import date
from unittest.mock import MagicMock, patch
import flet as ft

import services.supabase_client as db
from core.report_context import ReportContext
from views.cartoes_view import criar_view_cartoes
from views.calendario_view import criar_view_calendario
from views.relatorios.cartao_report import criar_view_relatorio_cartao


class DummyPage:
    def __init__(self):
        self.width = 1280
        self.height = 800
        self.platform = ft.PagePlatform.WINDOWS
        self.overlay = []
        self.views = []
        self.route = "/cartoes"
        self.session = {}
        self.data = {
            "periodo_global": {
                "mes": 11,
                "ano": 2026,
                "data_inicio": date(2026, 11, 1),
                "data_fim": date(2026, 11, 30),
                "modo": "Mensal",
            }
        }
        self.loop = None

    def update(self, *args):
        pass

    def open(self, dlg):
        if dlg not in self.overlay:
            self.overlay.append(dlg)
        dlg.open = True

    def close(self, dlg):
        dlg.open = False

    def show_dialog(self, dlg):
        self.open(dlg)

    def pop_dialog(self):
        if self.overlay:
            self.overlay[-1].open = False

    def run_task(self, coro_func, *args, **kwargs):
        if asyncio.iscoroutinefunction(coro_func):
            asyncio.run(coro_func(*args, **kwargs))


def _coletar_textos(ctrl, acum: list[str] | None = None) -> list[str]:
    if acum is None:
        acum = []
    if ctrl is None:
        return acum
    if isinstance(ctrl, ft.Text) and getattr(ctrl, "value", None):
        acum.append(str(ctrl.value))
    if isinstance(ctrl, ft.Dropdown):
        for op in (getattr(ctrl, "options", None) or []):
            if getattr(op, "text", None):
                acum.append(str(op.text))
    for attr in ("content", "title", "subtitle", "leading", "trailing"):
        sub = getattr(ctrl, attr, None)
        if sub is not None:
            _coletar_textos(sub, acum)
    for list_attr in ("controls", "actions"):
        lst = getattr(ctrl, list_attr, None)
        if isinstance(lst, (list, tuple)):
            for item in lst:
                _coletar_textos(item, acum)
    return acum


def _coletar_controles(ctrl, predicado, acum: list | None = None) -> list:
    if acum is None:
        acum = []
    if ctrl is None:
        return acum
    try:
        if predicado(ctrl):
            acum.append(ctrl)
    except Exception:
        pass
    for attr in ("content", "title", "subtitle", "leading", "trailing"):
        sub = getattr(ctrl, attr, None)
        if sub is not None:
            _coletar_controles(sub, predicado, acum)
    for list_attr in ("controls", "actions"):
        lst = getattr(ctrl, list_attr, None)
        if isinstance(lst, (list, tuple)):
            for item in lst:
                _coletar_controles(item, predicado, acum)
    return acum


def test_1_e_2_fatura_paga_vs_aberta_e_reajuste_vencimento():
    print("▶ [1 & 2] Testando Fatura Paga (Nov/2026) vs Aberta (Dez/2026), Badge de Status e Reajuste de Vencimento...")
    cartao_mp_id = "10308cc4-85e8-4113-a4b8-bb33b0504ec5"
    fatura_nov_id = "2878513e-4fe6-444a-bcb0-f034d7aae0b3"  # Nov/2026 Paga (R$ 341,57)
    fatura_dez_id = "602fb51f-cc44-4fa9-aad5-e7c9068bbbd5"  # Dez/2026 Aberta (R$ 110,16)

    # A) Carrega Fatura PAGA de Novembro/2026 do MercadoPago (usando RPC real do Supabase!)
    page_nov = DummyPage()
    ctx_nov = ReportContext(
        cartao_id=cartao_mp_id,
        fatura_id=fatura_nov_id,
        data_inicio=date(2026, 11, 1),
        data_fim=date(2026, 11, 30),
    )
    view_nov = criar_view_relatorio_cartao(page_nov, {"cartao_id": cartao_mp_id}, ctx_nov)
    textos_nov = _coletar_textos(view_nov)

    # Confirma que o botão "Reajustar Fatura" e "Toque p/ reajustar" sumiram na fatura paga!
    assert "Reajustar Fatura" not in textos_nov, "ERRO: O botão 'Reajustar Fatura' deveria estar oculto na fatura PAGA!"
    assert not any("Toque p/ reajustar" in t for t in textos_nov), "ERRO: 'Toque p/ reajustar' não deve aparecer em fatura PAGA!"
    assert any("Fatura Paga (R$ 341,57)" in t for t in textos_nov), f"ERRO: Badge 'Fatura Paga (R$ 341,57)' não encontrado: {textos_nov}"
    assert any("Pago em 17/11/2026" in t for t in textos_nov), "ERRO: Data de pagamento 17/11/2026 não exibida no badge!"
    assert any("Novembro/2026 · Paga" in t for t in textos_nov), "ERRO: Opção do dropdown deve manter 'Novembro/2026 · Paga'!"
    assert any("Dezembro/2026 · Aberta" in t for t in textos_nov), "ERRO: Opção do dropdown deve manter 'Dezembro/2026 · Aberta'!"

    # Confirma bloqueio no backend ao tentar reajustar fatura paga
    with patch.object(
        db,
        "obter_fatura_por_id",
        return_value={
            "id": fatura_nov_id,
            "cartao_id": cartao_mp_id,
            "mes": 11,
            "ano": 2026,
            "status": "paga",
            "valor_total": 341.57,
            "valor_pago": 341.57,
            "data_vencimento": "2026-11-19",
            "data_pagamento": "2026-11-17",
        },
    ):
        bloqueou_paga = False
        try:
            db.reajustar_valor_fatura(
                cartao_id=cartao_mp_id,
                fatura_id=fatura_nov_id,
                mes=11,
                ano=2026,
                valor_atual=341.57,
                novo_valor_total=350.00,
            )
        except ValueError:
            bloqueou_paga = True
        assert bloqueou_paga, "ERRO: O backend deveria bloquear reajuste em fatura já paga!"

    # B) Carrega Fatura ABERTA de Dezembro/2026 do MercadoPago (usando RPC real do Supabase!)
    page_dez = DummyPage()
    page_dez.data["periodo_global"] = {
        "mes": 12,
        "ano": 2026,
        "data_inicio": date(2026, 12, 1),
        "data_fim": date(2026, 12, 31),
        "modo": "Mensal",
    }
    ctx_dez = ReportContext(
        cartao_id=cartao_mp_id,
        fatura_id=fatura_dez_id,
        data_inicio=date(2026, 12, 1),
        data_fim=date(2026, 12, 31),
    )
    view_dez = criar_view_relatorio_cartao(page_dez, {"cartao_id": cartao_mp_id}, ctx_dez)
    textos_dez = _coletar_textos(view_dez)

    assert "Reajustar Fatura" in textos_dez, "ERRO: O botão 'Reajustar Fatura' deve aparecer na fatura ABERTA!"
    assert any("Toque p/ reajustar" in t for t in textos_dez), "ERRO: 'Toque p/ reajustar' deve aparecer na fatura ABERTA!"
    assert any("Fatura Aberta" in t for t in textos_dez), f"ERRO: Badge 'Fatura Aberta' deve aparecer fora do dropdown! Textos: {textos_dez}"

    # Abre o modal de Reajustar Fatura na fatura de Dezembro/2026 e verifica opção de trocar Data de Vencimento
    btns_reajuste = _coletar_controles(
        view_dez,
        lambda c: isinstance(c, ft.OutlinedButton) and "Reajustar Fatura" in _coletar_textos(c),
    )
    assert len(btns_reajuste) >= 1, "ERRO: Botão OutlinedButton 'Reajustar Fatura' não encontrado!"
    btns_reajuste[0].on_click(None)
    assert len(page_dez.overlay) >= 1, "ERRO: Modal de Reajustar Fatura não abriu!"
    modal_textos = _coletar_textos(page_dez.overlay[-1])
    assert any("Data de Vencimento da Fatura" in t for t in modal_textos), "ERRO: Campo 'Data de Vencimento da Fatura' não encontrado no modal!"
    assert any("Trocar Data" in t for t in modal_textos), "ERRO: Botão 'Trocar Data' não encontrado no modal!"
    assert any("Próx. Dia Útil" in t for t in modal_textos), "ERRO: Atalho 'Próx. Dia Útil' não encontrado no modal!"

    # C) Testa alterar somente a Data de Vencimento e alterar Valor + Data de Vencimento no serviço
    fat_dez_mock = {
        "id": fatura_dez_id,
        "cartao_id": cartao_mp_id,
        "mes": 12,
        "ano": 2026,
        "status": "aberta",
        "valor_total": 110.16,
        "valor_pago": 0.0,
        "data_vencimento": "2026-12-19",
        "data_fechamento": "2026-12-12",
    }
    mock_table = MagicMock()
    with patch.object(db, "obter_fatura_por_id", side_effect=lambda *_: dict(fat_dez_mock)), \
         patch.object(db.supabase, "table", return_value=mock_table), \
         patch.object(db, "criar_lancamento", return_value=MagicMock(data=[{"id": "lanc-aj-1", "valor": 9.84}])), \
         patch.object(db, "recalcular_totais_faturas"):
        res_so_venc = db.reajustar_valor_fatura(
            cartao_id=cartao_mp_id,
            fatura_id=fatura_dez_id,
            mes=12,
            ano=2026,
            valor_atual=110.16,
            novo_valor_total=110.16,
            nova_data_vencimento="2026-12-21",
        )
        assert res_so_venc["mudou_vencimento"] is True
        assert res_so_venc["mudou_valor"] is False
        assert res_so_venc["nova_data_vencimento"] == "2026-12-21"

        res_ambos = db.reajustar_valor_fatura(
            cartao_id=cartao_mp_id,
            fatura_id=fatura_dez_id,
            mes=12,
            ano=2026,
            valor_atual=110.16,
            novo_valor_total=120.00,
            nova_data_vencimento="2026-12-21",
        )
        assert res_ambos["mudou_vencimento"] is True
        assert res_ambos["mudou_valor"] is True
        assert abs(res_ambos["diferenca"] - 9.84) < 0.01

    print("   ✅ Fatura Paga oculta Reajuste, Fatura Aberta exibe Badge + Reajuste de Valor e Vencimento perfeitamente!")


def test_3_calendario_financeiro_fatura_paga_dia_17():
    print("▶ [3] Testando Calendário Financeiro de Novembro/2026 (Migração do dia 19 para o dia 17)...")
    cal = db.obter_calendario_financeiro_mes(11, 2026, "2026-11-01", "2026-11-30")
    dias_map = {str(d.get("data"))[:10]: d for d in (cal.get("dias") or [])}

    dia_17 = dias_map.get("2026-11-17")
    dia_19 = dias_map.get("2026-11-19")

    assert dia_17 is not None, "ERRO: Dia 2026-11-17 deveria conter a saída da fatura paga hoje!"
    assert abs(float(dia_17.get("total_despesas", 0)) - 341.57) < 0.01, (
        f"ERRO: Dia 17 deveria ter R$ 341,57 de saída, mas tem {dia_17.get('total_despesas')}"
    )
    assert abs(float(dia_17.get("despesas_cartao", 0)) - 341.57) < 0.01
    assert dia_19 is None or float(dia_19.get("total_despesas", 0) or 0) < 0.01, (
        f"ERRO: Dia 19 não deveria mais ter os R$ 341,57 presos nele! Encontrado: {dia_19}"
    )

    faturas_cal = cal.get("cartoes_faturas") or []
    fat_mp = next((f for f in faturas_cal if f.get("cartao_nome") == "MercadoPago"), None)
    assert fat_mp is not None, "ERRO: MercadoPago não encontrado em cartoes_faturas do calendário!"
    assert str(fat_mp.get("data_vencimento"))[:10] == "2026-11-17", "ERRO: data efetiva no calendário deve ser 2026-11-17!"
    assert str(fat_mp.get("data_vencimento_original"))[:10] == "2026-11-19", "ERRO: vencimento original deve ser preservado como 2026-11-19!"
    assert str(fat_mp.get("data_pagamento"))[:10] == "2026-11-17"

    print("   ✅ No Calendário Financeiro de Novembro/2026, os R$ 341,57 saíram do dia 19 e migraram para o dia 17!")


def test_4_aba_faturas_fechadas_exibe_mercadopago():
    print("▶ [4] Testando Aba '✓ Faturas Fechadas' em Cartões de Crédito (Novembro/2026)...")
    page = DummyPage()
    faturas_nov_mock = [
        {
            "id": "2878513e-4fe6-444a-bcb0-f034d7aae0b3",
            "cartao_id": "10308cc4-85e8-4113-a4b8-bb33b0504ec5",
            "mes": 11,
            "ano": 2026,
            "valor_total": 341.57,
            "valor_pago": 341.57,
            "status": "paga",
            "data_vencimento": "2026-11-19",
            "data_fechamento": "2026-11-12",
            "data_pagamento": "2026-11-17",
            "cartoes": {"nome": "MercadoPago", "cor": "#009EE3", "dia_vencimento": 19, "dia_fechamento": 12},
        },
        {
            "id": "fat-itau-nov",
            "cartao_id": "0db6535f-51d2-4d30-a551-271f7ef8d34a",
            "mes": 11,
            "ano": 2026,
            "valor_total": 609.67,
            "valor_pago": 0.0,
            "status": "aberta",
            "data_vencimento": "2026-11-23",
            "data_fechamento": "2026-11-16",
            "data_pagamento": None,
            "cartoes": {"nome": "Itau", "cor": "#EC7000", "dia_vencimento": 23, "dia_fechamento": 16},
        },
    ]
    cartoes_mock = [
        {"id": "10308cc4-85e8-4113-a4b8-bb33b0504ec5", "nome": "MercadoPago", "cor": "#009EE3", "limite_total": 5000.0, "limite_disponivel": 4889.84, "dia_vencimento": 19, "dia_fechamento": 12},
        {"id": "0db6535f-51d2-4d30-a551-271f7ef8d34a", "nome": "Itau", "cor": "#EC7000", "limite_total": 8000.0, "limite_disponivel": 7390.33, "dia_vencimento": 23, "dia_fechamento": 16},
    ]

    with patch.object(db, "listar_cartoes", return_value=cartoes_mock), \
         patch.object(db, "listar_faturas", side_effect=lambda cartao_id=None, status=None, mes=None, ano=None: faturas_nov_mock if (mes == 11 or status == 11) else []), \
         patch.object(db, "obter_resumo_cartoes", return_value={"cartoes": []}):
        view_cartoes = criar_view_cartoes(page)

        # Localiza o SegmentedButton de abas e muda para a aba "fechadas"
        segs = _coletar_controles(view_cartoes, lambda c: isinstance(c, ft.SegmentedButton))
        assert len(segs) >= 1, "ERRO: SegmentedButton não encontrado em Cartões de Crédito!"
        seg = segs[0]
        seg.selected = ["fechadas"]

        class DummyEvt:
            def __init__(self, control):
                self.control = control
                self.data = '["fechadas"]'

        seg.on_change(DummyEvt(seg))
        textos_fechadas = _coletar_textos(view_cartoes)

        assert "Nenhuma fatura fechada ou paga" not in textos_fechadas, (
            f"ERRO: A aba Faturas Fechadas ainda exibiu 'Nenhuma fatura fechada ou paga'! Textos: {textos_fechadas}"
        )
        assert "MercadoPago" in textos_fechadas, f"ERRO: Cartão MercadoPago não apareceu em Faturas Fechadas! Textos: {textos_fechadas}"
        assert any("341,57" in t for t in textos_fechadas), f"ERRO: Valor R$ 341,57 não apareceu em Faturas Fechadas! Textos: {textos_fechadas}"
        assert any("Pago em 17/11/2026" in t for t in textos_fechadas), f"ERRO: 'Pago em 17/11/2026' não apareceu! Textos: {textos_fechadas}"

        # Verifica que o card da fatura fechada/paga é clicável (ink=True e on_click definido)
        cards_clicaveis = _coletar_controles(
            view_cartoes,
            lambda c: isinstance(c, ft.Container)
            and getattr(c, "ink", False) is True
            and callable(getattr(c, "on_click", None))
            and "MercadoPago" in _coletar_textos(c),
        )
        assert len(cards_clicaveis) >= 1, "ERRO: O card do MercadoPago na aba Faturas Fechadas deve ser inteiro clicável!"

    print("   ✅ Aba '✓ Faturas Fechadas' exibe perfeitamente a fatura paga do MercadoPago (R$ 341,57) com card clicável!")


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 75)
    print("AUDITORIA AUTOMATIZADA — FATURAS PAGAS, REAJUSTE DE VENCIMENTO E CALENDÁRIO")
    print("=" * 75)
    test_1_e_2_fatura_paga_vs_aberta_e_reajuste_vencimento()
    test_3_calendario_financeiro_fatura_paga_dia_17()
    test_4_aba_faturas_fechadas_exibe_mercadopago()
    print("=" * 75)
    print("🎉 TODOS OS TESTES DO CHECKLIST PASSARAM COM 100% DE SUCESSO!")
    print("=" * 75)
