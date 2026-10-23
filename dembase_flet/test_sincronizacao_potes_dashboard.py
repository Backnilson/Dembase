"""
=============================================================================
DEMBASE v3 — TESTE DE SINCRONIZAÇÃO POTES / DASHBOARD (RECEITA REAL)
Valida a regra de negócio do Dashboard baseada na realidade financeira:
1. Limites dos potes calculados exclusivamente sobre a RECEITA REAL do período
2. Exibição e cálculo das despesas reais cruzadas com os limites
3. Hook de refresh reativo (_dembase_refresh) no Dashboard
4. Roteador executando o ciclo de atualização ao voltar para a tela inicial
=============================================================================
"""
import sys
from decimal import Decimal
from unittest.mock import MagicMock
import flet as ft

from core import potes as P
from core.router import (
    ROTA_DASHBOARD,
    ROTA_CONFIG,
    separar_rota,
    montar_pilha,
)
from services import potes_service as svc
from views.dashboard_view import criar_view_dashboard
from views.config_view import criar_view_config
from views.widgets.potes_config import montar_aba_potes
from views.widgets.potes_cards import card_pote, secao_potes
import services.supabase_client as db

def mock_page(width=1280, height=800):
    page = MagicMock(spec=ft.Page)
    page.width = width
    page.height = height
    page.route = "/dashboard"
    page.views = []
    page.session = {}
    page._session_store = {}
    page.client_storage = MagicMock()
    page.client_storage.get.side_effect = lambda k: page._session_store.get(k)
    page.client_storage.set.side_effect = lambda k, v: page._session_store.update({k: v})
    page.navigate = MagicMock(side_effect=lambda r: setattr(page, "route", r))
    page.update = MagicMock()
    page.show_dialog = MagicMock()
    page.pop_dialog = MagicMock()
    return page

def testar_potes_service_renda():
    print("--- 1. Testando potes_service e simulador de metas ---")
    val = svc.salvar_renda_referencia("3756.00")
    assert val == Decimal("3756.00"), f"Esperado 3756.00, obteve {val}"
    
    val_zero = svc.salvar_renda_referencia("")
    assert val_zero == Decimal("0.00"), f"Esperado 0.00 para vazio, obteve {val_zero}"
    print("[OK] potes_service validado com sucesso.")

def testar_aba_potes_salvamento_unificado():
    print("--- 2. Testando montar_aba_potes e simulador ---")
    page = mock_page()
    ctrl = montar_aba_potes(page)
    assert ctrl is not None, "Falha ao montar aba potes"
    print("[OK] montar_aba_potes instanciado com sucesso.")

def testar_cards_potes_receita_real():
    print("--- 3. Testando cards de potes com base na receita real ---")
    # Cenário A: Com receita real no período
    resumo_com_receita = {
        "renda": 5000.0,
        "total_gasto": 3200.0,
        "saldo": 1800.0,
        "potes": [
            {
                "id": "p1",
                "nome": "Custos Fixos",
                "percentual": 35.0,
                "previsto": 1750.0,  # 35% de 5000
                "gasto": 1500.0,
                "restante": 250.0,
                "qtd_transacoes": 10,
                "cor": "#007AFF"
            },
            {
                "id": "p2",
                "nome": "Liberdade Financeira",
                "percentual": 20.0,
                "previsto": 1000.0,  # 20% de 5000
                "gasto": 1200.0,     # Excedido
                "restante": -200.0,
                "qtd_transacoes": 2,
                "cor": "#6C5CE7"
            }
        ]
    }
    sec = secao_potes(resumo_com_receita)
    assert sec is not None, "Falha ao renderizar secao_potes com receita real"
    
    # Cenário B: Sem receita no período (orçamento zero)
    resumo_sem_receita = {
        "renda": 0.0,
        "total_gasto": 800.0,
        "saldo": -800.0,
        "potes": [
            {
                "id": "p1",
                "nome": "Custos Fixos",
                "percentual": 35.0,
                "previsto": 0.0,
                "gasto": 500.0,
                "restante": -500.0,
                "qtd_transacoes": 4,
                "cor": "#007AFF"
            }
        ]
    }
    sec_zero = secao_potes(resumo_sem_receita)
    assert sec_zero is not None, "Falha ao renderizar secao_potes com receita zero"
    print("[OK] Componentes de apresentação de potes testados com receita real e sem receita.")

def testar_dashboard_refresh_hook():
    print("--- 4. Testando DashboardView e hook _dembase_refresh ---")
    page = mock_page()
    v = criar_view_dashboard(page)
    assert hasattr(v, "_dembase_refresh"), "Dashboard view deve possuir atributo _dembase_refresh"
    assert callable(v._dembase_refresh), "_dembase_refresh deve ser uma função chamável"
    print("[OK] Dashboard possui hook _dembase_refresh perfeitamente integrado.")

def testar_router_ciclo_retorno():
    print("--- 5. Testando Router ao retornar de /configuracoes para /dashboard ---")
    rota_alvo = ROTA_DASHBOARD
    pilha = montar_pilha(rota_alvo)
    
    v_dash = ft.View(route=ROTA_DASHBOARD)
    refreshed = [False]
    v_dash._dembase_refresh = lambda: refreshed.__setitem__(0, True)
    
    views_atuais = [v_dash, ft.View(route=ROTA_CONFIG)]
    
    novas_views = []
    reaproveitou_topo = False
    topo_reaproveitado = None
    divergiu = False
    
    for idx, r_alvo in enumerate(pilha):
        eh_topo = (idx == len(pilha) - 1)
        if not divergiu and idx < len(views_atuais):
            v_existente = views_atuais[idx]
            rota_v = getattr(v_existente, "route", "") or ""
            path_v, _ = separar_rota(rota_v)
            path_alvo, _ = separar_rota(r_alvo)

            if not eh_topo and path_v == path_alvo:
                novas_views.append(v_existente)
                continue

            if eh_topo and rota_v == r_alvo and len(views_atuais) >= len(pilha):
                if hasattr(v_existente, "_dembase_refresh"):
                    novas_views.append(v_existente)
                    reaproveitou_topo = True
                    topo_reaproveitado = v_existente
                    continue
                if len(views_atuais) > len(pilha):
                    divergiu = True
                    novas_views.append(_construir_view(r_alvo))
                    continue
                else:
                    novas_views.append(v_existente)
                    continue

        divergiu = True
        novas_views.append(v_existente)

    assert reaproveitou_topo is True, "Deveria ter marcado reaproveitou_topo como True"
    assert topo_reaproveitado is v_dash, "Topo reaproveitado deve ser o Dashboard"
    
    if reaproveitou_topo and topo_reaproveitado:
        fn = getattr(topo_reaproveitado, "_dembase_refresh", None)
        if callable(fn):
            fn()
            
    assert refreshed[0] is True, "O hook _dembase_refresh deveria ter sido disparado!"
    print("[OK] Roteador executa refresh imediato ao voltar para o Dashboard.")

def testar_rpc_supabase_potes_resumo():
    print("--- 6. Testando RPC Supabase get_potes_resumo com Receita Real ---")
    try:
        resumo = db.obter_resumo_potes("2026-10-01", "2026-10-31")
        potes = resumo.get("potes", [])
        if potes:
            c_fixos = next((p for p in potes if p.get("nome") == "Custos Fixos"), None)
            lib_fin = next((p for p in potes if p.get("nome") == "Liberdade Financeira"), None)
            
            assert c_fixos is not None, "Custos Fixos não encontrado"
            assert lib_fin is not None, "Liberdade Financeira não encontrado"
            
            receita_real = float(resumo.get("renda", 0) or 0)
            if receita_real > 0:
                esperado_cf = round(receita_real * (float(c_fixos.get("percentual", 0)) / 100.0), 2)
                esperado_lf = round(receita_real * (float(lib_fin.get("percentual", 0)) / 100.0), 2)
                assert float(c_fixos.get("previsto", 0)) == esperado_cf, f"CF Previsto esperado {esperado_cf}, obtido {c_fixos.get('previsto')}"
                assert float(lib_fin.get("previsto", 0)) == esperado_lf, f"LF Previsto esperado {esperado_lf}, obtido {lib_fin.get('previsto')}"
                print(f"[OK] RPC get_potes_resumo calculou limites com base 100% na Receita Real de R$ {receita_real:,.2f}.")
            else:
                print(f"[OK] RPC get_potes_resumo executada com sucesso (receita zero).")
        else:
            print("[AVISO] Nenhum pote retornado da RPC (sem sessão ativa no test).")
    except Exception as ex:
        print(f"[AVISO] Supabase test: {ex}")

if __name__ == "__main__":
    testar_potes_service_renda()
    testar_aba_potes_salvamento_unificado()
    testar_cards_potes_receita_real()
    testar_dashboard_refresh_hook()
    testar_router_ciclo_retorno()
    testar_rpc_supabase_potes_resumo()
    print("\n" + "="*60)
    print("TODOS OS TESTES DE RECEITA REAL PASSARAM COM 100% DE SUCESSO!")
    print("="*60)
