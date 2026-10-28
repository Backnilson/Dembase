"""
=============================================================================
DemBase v3 — test_meu_cofre_investimentos.py
Teste ponta a ponta do Módulo de Investimentos & Patrimônio ("Meu Cofre"):
- Criação e garantia dos cofres padrão (Porquinho e 102% CDI)
- Lançamento de Aporte (+ Suor)
- Opção A: Lançamento de Rendimento Direto (+ Juros)
- Opção B: Ajuste Inteligente por Saldo Atual (Diferença positiva = Rendimento)
- Resgate com validação de saldo
- Verificação do resumo patrimonial, taxa CDI e Gamificação (Badges)
- Teste da abertura de view no Flet 1.0.1
- Limpeza dos registros de teste
=============================================================================
"""
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock
from datetime import date

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import flet as ft
import services.supabase_client as db
from views.investimentos_view import (
    criar_view_investimentos,
    abrir_modal_aporte_sobra_dashboard,
)

class MockPage:
    def __init__(self, width: int = 1280):
        self.width = width
        self.height = 800
        self.route = "/investimentos"
        self.views = []
        self.overlay = []
        self.session = {}
        self.services = []
        self.theme_mode = ft.ThemeMode.DARK

    def update(self):
        pass

    def run_task(self, task):
        pass

    def show_dialog(self, dlg):
        self.overlay.append(dlg)

    def pop_dialog(self):
        if self.overlay:
            self.overlay.pop()


def rodar_testes():
    print("=" * 60)
    print("INICIANDO TESTES DO MODULO 'MEU COFRE' / INVESTIMENTOS")
    print("=" * 60)

    # 1. Login com usuário de demonstração
    print("\n1. Autenticando com usuario demo...")
    auth_resp = None
    for em in ["teste@dembase.com", "teste@teste.com"]:
        try:
            auth_resp = db.fazer_login(em, "teste123")
            if auth_resp and auth_resp.user:
                print(f"  Logado com sucesso como {em} (UID: {auth_resp.user.id})")
                break
        except Exception as ex:
            print(f"  Tentativa com {em}: {ex}")

    u = db.usuario_atual()
    assert u is not None, "Usuario deve estar autenticado para os testes!"

    # 2. Garantir cofres padrão
    print("\n2. Verificando / garantindo cofres padrao (Porquinho e 102% CDI)...")
    db.garantir_cofres_padrao(u.id)
    cofres = db.listar_cofres_investimento(forcar_atualizacao=True)
    print(f"  Total de cofres ativos: {len(cofres)}")
    for c in cofres:
        print(f"   • {c['nome']} (Tipo: {c['tipo']}) | Saldo: R$ {c['saldo_atual']:.2f}")

    porquinho = next((c for c in cofres if c['tipo'] == 'reserva_emergencia'), None)
    cdi = next((c for c in cofres if c['tipo'] == 'renda_fixa'), None)

    assert porquinho is not None, "Cofre 'Porquinho' deve existir"
    assert cdi is not None, "Cofre '102% CDI' deve existir"

    # 3. Teste de Aporte
    print("\n3. Testando Aporte no Porquinho...")
    saldo_ant = porquinho['saldo_atual']
    mov_ap = db.registrar_aporte_cofre(
        cofre_id=porquinho['id'],
        valor=300.00,
        descricao="Aporte Automatizado Teste (+300)",
    )
    print(f"  Aporte registrado! Mov ID: {mov_ap['id']}")
    pq_pos = db.obter_cofre_por_id(porquinho['id'])
    assert pq_pos['saldo_atual'] == round(saldo_ant + 300.00, 2), "Saldo deve incrementar 300.00"

    # 4. Teste Opção A: Rendimento Direto
    print("\n4. Testando Opcao A: Rendimento Direto no 102% CDI (+R$ 45,50)...")
    cdi_ant = cdi['saldo_atual']
    mov_rd = db.registrar_rendimento_direto(
        cofre_id=cdi['id'],
        valor=45.50,
        descricao="Rendimento Direto Teste (+45,50)",
    )
    print(f"  Rendimento direto registrado! Mov ID: {mov_rd['id']}")
    cdi_pos = db.obter_cofre_por_id(cdi['id'])
    assert cdi_pos['saldo_atual'] == round(cdi_ant + 45.50, 2), "Saldo CDI deve incrementar 45.50"

    # 5. Teste Opção B: Ajuste Inteligente por Saldo Atual
    print("\n5. Testando Opcao B: Ajuste Inteligente por Saldo Atual (+R$ 54,50)...")
    saldo_digitado = round(cdi_pos['saldo_atual'] + 54.50, 2)
    res_ajuste = db.registrar_ajuste_por_saldo_atual(
        cofre_id=cdi['id'],
        saldo_digitado=saldo_digitado,
        descricao="Ajuste Inteligente Teste",
    )
    print(f"  Resultado: {res_ajuste['mensagem']}")
    assert res_ajuste['tipo_ajuste'] == 'rendimento', "Diferenca positiva deve ser detectada como rendimento"
    assert res_ajuste['diferenca'] == 54.50, "Diferenca deve ser exatamente 54.50"

    # 6. Teste de Resgate
    print("\n6. Testando Resgate no Porquinho (R$ 50,00)...")
    mov_resg = db.registrar_resgate_cofre(
        cofre_id=porquinho['id'],
        valor=50.00,
        descricao="Resgate Teste",
    )
    print(f"  Resgate registrado! Mov ID: {mov_resg['id']}")
    pq_resg = db.obter_cofre_por_id(porquinho['id'])
    assert pq_resg['saldo_atual'] == round(pq_pos['saldo_atual'] - 50.00, 2)

    # 7. Teste de Configuração da Taxa CDI
    print("\n7. Testando salvar e ler Taxa CDI...")
    db.salvar_config_taxa_cdi(11.25)
    taxa_lida = db.obter_config_taxa_cdi()
    assert taxa_lida == 11.25, f"Taxa CDI lida deve ser 11.25, retornou {taxa_lida}"
    # Restaura para 10.75
    db.salvar_config_taxa_cdi(10.75)

    # 8. Teste do Pacote Consolidado de Resumo Patrimonial
    print("\n8. Testando Resumo Patrimonial e Maquina de Renda Passiva...")
    resumo = db.obter_resumo_investimentos_patrimonio(forcar_atualizacao=True)
    print(f"  Patrimonio Total Acumulado: R$ {resumo['patrimonio_total']:.2f}")
    print(f"  Meu Suor (Aportes Liquidos): R$ {resumo['total_aportado_liquido']:.2f}")
    print(f"  Total Juros Ganhos: R$ {resumo['total_rendimentos']:.2f}")
    print(f"  Lucro % sobre capital: {resumo['lucro_pct']:.2f}%")
    print(f"  Estimativa Renda Passiva Mensal: R$ {resumo['renda_mensal_estimada']:.2f} / mes")
    print(f"  Estimativa Renda Passiva Diaria: R$ {resumo['renda_diaria_estimada']:.2f} / dia")
    print(f"  Total de Badges: {len(resumo['badges'])} (Ativos: {sum(1 for b in resumo['badges'] if b['atingido'])})")

    assert resumo['patrimonio_total'] > 0
    assert resumo['total_rendimentos'] >= 100.0  # 45.50 + 54.50 = 100.00
    assert len(resumo['badges']) >= 6

    # 9. Teste de Renderização da View no Flet 1.0.1
    print("\n9. Testando criacao da view Flet 1.0.1...")
    mock_p = MockPage()
    view = criar_view_investimentos(mock_p)
    assert isinstance(view, ft.View), "Deve retornar uma instancia valida de ft.View"
    assert view.route == "/investimentos", "Rota da view deve ser /investimentos"
    print("  View de Investimentos criada com sucesso no Flet 1.0.1!")

    # 10. Teste do Modal de Aporte Integrado com o Dashboard
    print("\n10. Testando Modal de Aporte da Sobra do Dashboard...")
    callback_chamado = [False]
    abrir_modal_aporte_sobra_dashboard(
        mock_p,
        valor_sugerido=700.00,
        on_saved=lambda: callback_chamado.__setitem__(0, True),
    )
    assert len(mock_p.overlay) > 0, "Modal deve ser adicionado ao overlay do Flet"
    print("  Modal de Aporte da Sobra renderizado com sucesso no overlay!")

    # 11. Limpar movimentações de teste para manter a base limpa
    print("\n11. Limpando registros de teste...")
    db.excluir_movimentacao_cofre(mov_ap['id'])
    db.excluir_movimentacao_cofre(mov_rd['id'])
    if res_ajuste.get('movimentacao') and res_ajuste['movimentacao'].get('id'):
        db.excluir_movimentacao_cofre(res_ajuste['movimentacao']['id'])
    db.excluir_movimentacao_cofre(mov_resg['id'])
    print("  Saldos e registros restaurados com perfeicao!")

    print("\n" + "=" * 60)
    print("TODOS OS TESTES DE INVESTIMENTOS PASSARAM COM 100% DE SUCESSO!")
    print("=" * 60)


if __name__ == "__main__":
    rodar_testes()
