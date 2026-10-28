"""
=============================================================================
Teste Automatizado — Caixa Livre, Ordenação do Dashboard e Calendário Financeiro
Valida (Flet 1.0.1):
  1. Card KPI "Caixa Livre": exibe em destaque o valor LIVRE (para gastar);
     o Total da Sobra e o valor de Guardar/Investir aparecem ao clicar no card.
  2. Seleção de Ordem do Dashboard: persistência e reordenação das Seções,
     dos Cards de KPI e dos Gráficos.
  3. Calendário Financeiro Interativo:
     - Grade mensal 7x6 com Mapa de Calor (Heatmap), pílulas verdes/vermelhas
       e marcadores de vencimento de fatura.
     - Gráfico de Rosca (Donut Chart) por Categorias/Tags + Resumo de Faturas.
     - Correção de relacionamento PostgREST (sem erro PGRST201 em faturas).
=============================================================================
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import flet as ft
from views.widgets.sobra_card import calcular_rateio_sobra, PainelGestaoSobra
from views.dashboard_view import criar_view_dashboard
from views.contas_view import criar_view_contas
from views.calendario_view import (
    criar_view_calendario,
    calcular_cor_heatmap_saida,
    calcular_cor_heatmap_entrada,
    construir_grafico_rosca,
)
from core import storage
import services.supabase_client as db


class DummySession:
    def __init__(self):
        self.store = {}


class MockPage:
    def __init__(self, width: int = 1280):
        self.width = width
        self.height = 800
        self.route = "/dashboard"
        self.views = []
        self.overlay = []
        self.session = {}
        self.services = []
        self.theme_mode = ft.ThemeMode.DARK

    def update(self):
        pass

    def show_dialog(self, dlg):
        self.overlay.append(dlg)

    def pop_dialog(self):
        if self.overlay:
            self.overlay.pop()


def _coletar_textos(ctrl: ft.Control, acumulador: list[str]):
    if ctrl is None:
        return
    if isinstance(ctrl, ft.Text) and ctrl.value:
        acumulador.append(str(ctrl.value))
    for attr in ("content", "title", "subtitle", "leading", "trailing"):
        sub = getattr(ctrl, attr, None)
        if isinstance(sub, ft.Control):
            _coletar_textos(sub, acumulador)
    for attr in ("controls", "actions"):
        lista = getattr(ctrl, attr, None)
        if isinstance(lista, (list, tuple)):
            for item in lista:
                if isinstance(item, ft.Control):
                    _coletar_textos(item, acumulador)


def test_matematica_sobra():
    r1 = calcular_rateio_sobra(10000.0, 6500.0, 50.0)
    assert r1["sobra"] == 3500.00
    assert r1["tem_sobra"] is True
    assert r1["valor_investimento"] == 1750.00
    assert r1["valor_livre_culpa"] == 1750.00

    r2 = calcular_rateio_sobra(5432.15, 3100.04, 30.0)
    assert r2["sobra"] == 2332.11
    assert round(r2["valor_investimento"] + r2["valor_livre_culpa"], 2) == r2["sobra"]
    assert r2["pct_investimento"] == 30.0
    assert r2["pct_livre"] == 70.0

    r3 = calcular_rateio_sobra(3000.0, 4200.0, 60.0)
    assert r3["sobra"] == -1200.00
    assert r3["tem_sobra"] is False
    assert r3["em_deficit"] is True
    assert r3["valor_investimento"] == 0.0
    assert r3["valor_livre_culpa"] == 0.0
    print("[OK] test_matematica_sobra passou com sucesso.")


def test_ordenacao_dashboard_e_caixa_livre():
    page = MockPage(width=1280)

    # Testa persistência da ordem das seções e KPIs do Dashboard
    nova_ordem_secoes = ["potes", "calendario", "kpis", "graficos", "acoes"]
    storage.salvar_ordem_secoes_dashboard_sync(page, nova_ordem_secoes)
    assert storage.obter_ordem_secoes_dashboard(page) == nova_ordem_secoes

    nova_ordem_kpis = ["receitas", "despesas", "caixa_livre", "faturas"]
    storage.salvar_ordem_kpis_dashboard_sync(page, nova_ordem_kpis)
    assert storage.obter_ordem_kpis_dashboard(page) == nova_ordem_kpis

    # Restaura padrão
    storage.salvar_ordem_secoes_dashboard_sync(page, storage.SECOES_DASHBOARD_PADRAO)
    storage.salvar_ordem_kpis_dashboard_sync(page, storage.KPIS_DASHBOARD_PADRAO)

    for largura in (1280, 390):
        p = MockPage(width=largura)
        view_dash = criar_view_dashboard(p)
        textos_dash: list[str] = []
        for c in view_dash.controls:
            _coletar_textos(c, textos_dash)

        assert "Caixa Livre" in textos_dash
        assert "Saldo em Conta" not in textos_dash
        assert any("investir" in t.lower() or "investimento" in t.lower() for t in textos_dash)
        assert any("livre" in t.lower() for t in textos_dash)
        assert "Calendário Financeiro" in textos_dash

    print("[OK] test_ordenacao_dashboard_e_caixa_livre passou com sucesso.")


def test_menu_configuracoes_inline_e_calendario_dashboard():
    from views.shell_view import _NAV_ITEMS
    from views.config_view import criar_view_config

    labels_menu = [item["label"] for item in _NAV_ITEMS]
    assert "Lançamento" not in labels_menu, "Lançamento não deve estar no menu lateral/hambúrguer"
    assert "Caixinhas" not in labels_menu, "Caixinhas deve ficar dentro de Configurações"
    assert "Categorias" not in labels_menu, "Categorias deve ficar dentro de Configurações"
    assert labels_menu == ["Dashboard", "Meu Cofre", "Contas", "Cartões", "Calendário", "Relatórios"]

    assert "calendario" in storage.SECOES_DASHBOARD_PADRAO

    # Testa Configurações com abas inline (Metas, Caixinhas, Categorias)
    for rota_cfg, texto_esperado in (
        ("/configuracoes?aba=metas", "Potes"),
        ("/configuracoes?aba=caixinhas", "NOVA CAIXINHA"),
        ("/configuracoes?aba=categorias", "Categorias & Subcategorias"),
    ):
        p = MockPage(width=1280)
        p.route = rota_cfg
        v_cfg = criar_view_config(p)
        txts: list[str] = []
        for ctrl in v_cfg.controls:
            _coletar_textos(ctrl, txts)
        assert "Metas (Potes)" in txts
        assert "Caixinhas" in txts
        assert "Categorias" in txts
        assert any(texto_esperado.lower() in t.lower() for t in txts), f"Esperado '{texto_esperado}' na rota {rota_cfg}"

    print("[OK] test_menu_configuracoes_inline_e_calendario_dashboard passou com sucesso.")


def test_calendario_financeiro_heatmap_e_rosca():
    # Testa funções visuais do Mapa de Calor e Gráfico de Rosca
    bg_s, bd_s = calcular_cor_heatmap_saida(500.0, 1000.0)
    assert bg_s and bd_s
    bg_e, bd_e = calcular_cor_heatmap_entrada(800.0, 1000.0)
    assert bg_e and bd_e

    rosca = construir_grafico_rosca(
        [
            {"categoria": "Moradia", "total": 1150.0, "cor": "#10B981"},
            {"categoria": "Alimentação", "total": 427.11, "cor": "#EAB308"},
        ],
        total=1577.11,
    )
    assert isinstance(rosca, ft.Stack)

    # Testa renderização completa da view de Calendário em Desktop e Mobile
    for largura in (1280, 390):
        p = MockPage(width=largura)
        view_cal = criar_view_calendario(p)
        textos_cal: list[str] = []
        for c in view_cal.controls:
            _coletar_textos(c, textos_cal)

        assert "Calendário Financeiro" in textos_cal
        assert "Por Categorias / Tags" in textos_cal
        assert "Faturas do Mês" in textos_cal
        assert "DOM" in textos_cal and "SÁB" in textos_cal

    print("[OK] test_calendario_financeiro_heatmap_e_rosca (Desktop e Mobile) passou com sucesso.")


def test_filtro_global_favoritos_e_calendario_sincronizado():
    from datetime import date
    from core.periodo import (
        calcular_intervalo_dias_mes,
        avancar_periodo_estado,
        atualizar_datas_periodo_global,
    )

    p = MockPage(width=1280)
    favs = storage.obter_filtros_periodo_favoritos(p)
    ids_favs = [f["id"] for f in favs]
    assert "dia_01_15" in ids_favs, "Filtro '1ª Quinzena' deve vir salvo por padrão"
    assert "dia_16_fim" in ids_favs, "Filtro '2ª Quinzena' deve vir salvo por padrão"

    # Testa salvar e remover um filtro favorito customizado
    favs_apos_salvar = storage.salvar_filtro_periodo_favorito_sync(p, "Dia 10 a 25", 10, 25, False)
    assert any(f["id"] == "custom_10_25" for f in favs_apos_salvar)
    favs_apos_rm = storage.remover_filtro_periodo_favorito_sync(p, "custom_10_25")
    assert not any(f["id"] == "custom_10_25" for f in favs_apos_rm)

    # Testa cálculo e avanço de 'Dia 05 a 20' e 'Dia 20 a 30/31'
    d_i_5_20, d_f_5_20 = calcular_intervalo_dias_mes(10, 2026, 5, 20, ate_fim_mes=False)
    assert d_i_5_20 == date(2026, 10, 5) and d_f_5_20 == date(2026, 10, 20)

    est_20_fim = {
        "modo": "faixa_mes",
        "mes": 10,
        "ano": 2026,
        "data_inicio": date(2026, 10, 20),
        "data_fim": date(2026, 10, 31),
        "ate_fim_mes": True,
    }
    avancar_periodo_estado(est_20_fim, 1)  # Avança de Outubro (31 dias) para Novembro (30 dias)
    assert est_20_fim["data_inicio"] == date(2026, 11, 20)
    assert est_20_fim["data_fim"] == date(2026, 11, 30)

    # Testa filtro parcial no Calendário Financeiro (Ex: 05/10 a 20/10 vs 20/10 a 31/10)
    pacote_ficticio = {
        "mes": 10,
        "ano": 2026,
        "inicio_mes": "2026-10-01",
        "fim_mes": "2026-10-31",
        "kpis": {},
        "dias": [
            {
                "data": "2026-10-10",
                "dia": 10,
                "mes": 10,
                "ano": 2026,
                "no_mes_atual": True,
                "total_receitas": 2000.0,
                "total_despesas": 400.0,
                "despesas_conta": 400.0,
                "despesas_cartao": 0.0,
                "qtd_lancamentos": 2,
                "lancamentos": [
                    {"tipo": "Receita", "valor": 2000.0, "categoria_id": "c1", "categoria_nome": "Salário", "categoria_cor": "#10B981"},
                    {"tipo": "Despesa", "valor": 400.0, "categoria_id": "c2", "categoria_nome": "Mercado", "categoria_cor": "#EF4444"},
                ],
            },
            {
                "data": "2026-10-25",
                "dia": 25,
                "mes": 10,
                "ano": 2026,
                "no_mes_atual": True,
                "total_receitas": 0.0,
                "total_despesas": 950.0,
                "despesas_conta": 250.0,
                "despesas_cartao": 700.0,
                "qtd_lancamentos": 2,
                "lancamentos": [
                    {"tipo": "Despesa", "valor": 950.0, "categoria_id": "c3", "categoria_nome": "Lazer", "categoria_cor": "#F59E0B"},
                ],
            },
        ],
    }
    import copy
    res_05_20 = db._aplicar_filtro_periodo_ao_calendario(copy.deepcopy(pacote_ficticio), "2026-10-05", "2026-10-20")
    assert res_05_20["eh_periodo_parcial"] is True
    assert res_05_20["kpis"]["receitas_mes"] == 2000.0
    assert res_05_20["kpis"]["despesas_mes"] == 400.0
    assert res_05_20["kpis"]["resultado_mes"] == 1600.0

    res_20_31 = db._aplicar_filtro_periodo_ao_calendario(copy.deepcopy(pacote_ficticio), "2026-10-20", "2026-10-31")
    assert res_20_31["eh_periodo_parcial"] is True
    assert res_20_31["kpis"]["receitas_mes"] == 0.0
    assert res_20_31["kpis"]["despesas_mes"] == 950.0
    assert res_20_31["kpis"]["despesas_cartao_mes"] == 700.0

    # Testa renderização da tela de Calendário e Dashboard com filtro '05/10/2026 a 20/10/2026' ativo
    atualizar_datas_periodo_global(p, "2026-10-05", "2026-10-20", mes=10, ano=2026)
    v_cal_parcial = criar_view_calendario(p)
    txts_cal_p: list[str] = []
    for c in v_cal_parcial.controls:
        _coletar_textos(c, txts_cal_p)
    assert any("05/10/2026 a 20/10/2026" in t for t in txts_cal_p)

    print("[OK] test_filtro_global_favoritos_e_calendario_sincronizado passou com sucesso.")


if __name__ == "__main__":
    test_matematica_sobra()
    test_ordenacao_dashboard_e_caixa_livre()
    test_menu_configuracoes_inline_e_calendario_dashboard()
    test_calendario_financeiro_heatmap_e_rosca()
    test_filtro_global_favoritos_e_calendario_sincronizado()
    print("\n=== TODOS OS TESTES PASSARAM COM 100% DE SUCESSO! ===")
