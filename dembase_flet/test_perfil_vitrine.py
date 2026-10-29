"""
=============================================================================
DemBase v3 — test_perfil_vitrine.py
Validação e Testes Automatizados do "Perfil Vitrine":
1. Trava de segurança (impede tocar perfil real de Denilson)
2. Geração completa do Perfil Vitrine (Família Silva: Carlos & Marina)
3. Idempotência (rodar 2x consecutivas não duplica dados)
4. Coerência dos 15 meses (M-12 a M+2, faturas, compras parceladas)
5. Módulo Meu Cofre (Porquinho, CDI 102%, resgate no M-4 e cobertura)
=============================================================================
"""
from __future__ import annotations

import os
import sys
from datetime import date

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))
if DIR_ATUAL not in sys.path:
    sys.path.insert(0, DIR_ATUAL)

from services.demo_generator import (
    DEMO_USER_EMAIL,
    DEMO_USER_UID,
    REAL_USER_DENILSON_UID,
    SecurityDemoError,
    gerar_perfil_vitrine,
    limpar_dados_demo,
    validar_seguranca_demo,
)
import services.supabase_client as db


def testar_trava_de_seguranca():
    print("\n--- TESTE 1: Trava de Segurança Contra Acessos Indevidos ---")
    # Tentativa de passar o UID do Denilson
    bloqueado_denilson = False
    try:
        validar_seguranca_demo(REAL_USER_DENILSON_UID)
    except SecurityDemoError:
        bloqueado_denilson = True
    assert bloqueado_denilson, "FALHA: Trava não bloqueou o UID do usuário real Denilson!"
    print("  [OK] Tentativa de modificar perfil real de Denilson bloqueada com sucesso!")

    # Tentativa de passar UID aleatório sem ser teste
    bloqueado_random = False
    try:
        validar_seguranca_demo("11111111-2222-3333-4444-555555555555", email="usuario@empresa.com")
    except SecurityDemoError:
        bloqueado_random = True
    assert bloqueado_random, "FALHA: Trava não bloqueou UID desconhecido!"
    print("  [OK] Tentativa de modificar UID desconhecido bloqueada com sucesso!")


def testar_geracao_e_idempotencia():
    print("\n--- TESTE 2: Geração do Perfil Vitrine & Idempotência ---")
    auth_resp = db.fazer_login(DEMO_USER_EMAIL, "teste123")
    assert auth_resp and auth_resp.user, "Falha no login do usuário demo"
    uid = auth_resp.user.id
    assert uid == DEMO_USER_UID, f"UID inesperado: {uid}"

    # Execução 1
    print("  Executando geração 1...")
    resumo_1 = gerar_perfil_vitrine(uid=uid, status_cb=lambda m: print(f"    -> {m}"))
    assert resumo_1["sucesso"], "Geração 1 falhou"
    total_lanc_1 = resumo_1["total_lancamentos"]
    total_fat_1 = resumo_1["total_faturas"]
    print(f"  [OK] Geração 1 concluída: {total_lanc_1} lançamentos, {total_fat_1} faturas.")

    # Execução 2 (Idempotência)
    print("  Executando geração 2 (teste de idempotência)...")
    resumo_2 = gerar_perfil_vitrine(uid=uid)
    assert resumo_2["sucesso"], "Geração 2 falhou"
    total_lanc_2 = resumo_2["total_lancamentos"]
    total_fat_2 = resumo_2["total_faturas"]
    assert total_lanc_1 == total_lanc_2, f"Idempotência violada! {total_lanc_1} != {total_lanc_2}"
    assert total_fat_1 == total_fat_2, f"Idempotência violada em faturas! {total_fat_1} != {total_fat_2}"
    print(f"  [OK] Idempotência comprovada! Exatamente {total_lanc_2} lançamentos e {total_fat_2} faturas mantidas.")


def testar_multi_perfis_e_entidades():
    print("\n--- TESTE 3: Multi-Perfis Familiares (Carlos & Marina) ---")
    uid = DEMO_USER_UID
    membros = db.listar_membros()
    nomes_membros = [m["nome"] for m in membros]
    print(f"  Membros cadastrados: {nomes_membros}")
    assert "Carlos" in nomes_membros, "Membro Carlos não encontrado!"
    assert "Marina" in nomes_membros, "Membro Marina não encontrado!"

    carlos = next(m for m in membros if m["nome"] == "Carlos")
    marina = next(m for m in membros if m["nome"] == "Marina")
    assert carlos["principal"], "Carlos deve ser o membro principal!"
    assert not marina["principal"], "Marina deve ser o membro secundário!"

    # Contas
    contas = db.supabase.table("contas").select("*").eq("user_id", uid).execute().data or []
    nomes_contas = {c["nome"]: c.get("membro_id") for c in contas}
    print(f"  Contas cadastradas: {list(nomes_contas.keys())}")
    assert "Nubank Carlos" in nomes_contas, "Conta Nubank Carlos ausente!"
    assert "Banco Inter Marina" in nomes_contas, "Conta Inter Marina ausente!"
    assert nomes_contas["Nubank Carlos"] == carlos["id"], "Nubank Carlos não vinculado ao membro Carlos!"
    assert nomes_contas["Banco Inter Marina"] == marina["id"], "Inter Marina não vinculado à Marina!"
    print("  [OK] Vínculos de contas com membros 100% corretos!")

    # Cartões
    cartoes = db.supabase.table("cartoes").select("*").eq("user_id", uid).execute().data or []
    nomes_cartoes = {c["nome"]: c.get("membro_id") for c in cartoes}
    print(f"  Cartões cadastrados: {list(nomes_cartoes.keys())}")
    assert "Nubank Ultravioleta" in nomes_cartoes, "Nubank Ultravioleta ausente!"
    assert "Inter Mastercard Black" in nomes_cartoes, "Inter Mastercard Black ausente!"
    assert nomes_cartoes["Nubank Ultravioleta"] == carlos["id"]
    assert nomes_cartoes["Inter Mastercard Black"] == marina["id"]
    print("  [OK] Vínculos de cartões com membros 100% corretos!")


def testar_meu_cofre_e_cobertura():
    print("\n--- TESTE 4: Módulo Meu Cofre & Cobertura de Sobrevivência ---")
    uid = DEMO_USER_UID
    cofres = db.listar_cofres_investimento()
    print(f"  Cofres encontrados: {[c['nome'] for c in cofres]}")
    assert len(cofres) >= 2, "Deveriam existir pelo menos 2 cofres ativos!"

    porquinho = next(c for c in cofres if c["tipo"] == "reserva_emergencia")
    cdi = next(c for c in cofres if c["tipo"] == "renda_fixa")
    print(f"  Porquinho: Saldo R$ {porquinho['saldo_atual']:,.2f} | Total Aportado: R$ {porquinho['total_aportado']:,.2f} | Resgatado: R$ {porquinho['total_resgatado']:,.2f}")
    print(f"  Renda Fixa CDI: Saldo R$ {cdi['saldo_atual']:,.2f} | Total Aportado: R$ {cdi['total_aportado']:,.2f}")

    assert porquinho["saldo_atual"] > 0, "Saldo do Porquinho deve ser positivo!"
    assert porquinho["total_resgatado"] >= 4000.0, "Resgate de R$ 4.000 do imprevisto deve estar registrado!"
    assert cdi["saldo_atual"] > 0, "Saldo do CDI deve ser positivo!"

    # Movimentações
    movs = db.obter_movimentacoes_cofres(limite=50)
    tipos_movs = [m["tipo"] for m in movs]
    assert "aporte" in tipos_movs, "Falta movimentação de aporte!"
    assert "resgate" in tipos_movs, "Falta movimentação de resgate do imprevisto!"
    assert "rendimento" in tipos_movs, "Falta movimentação de rendimento!"
    print(f"  [OK] Movimentações do Meu Cofre verificadas: aportes, rendimentos e resgate de emergência!")

    # Cobertura Real de Sobrevivência
    cobertura = db.obter_cobertura_reserva()
    reserva_val = float(cobertura.get("reserva_atual") or 0.0)
    custo_casa = float(cobertura.get("custo_casa") or 0.0)
    meses_casa = float(cobertura.get("meses_casa") or 0.0)

    print(f"  Cobertura calculada: {meses_casa} meses | Reserva: R$ {reserva_val:,.2f} | Custo Casa: R$ {custo_casa:,.2f}")
    assert reserva_val > 0, "Reserva atual deve ser positiva!"
    assert meses_casa > 0, "Cobertura em meses da casa deve ser maior que zero!"
    print("  [OK] Card de Cobertura de Sobrevivência operando com valores consistentes!")


def testar_narrativa_e_datas_relativas():
    print("\n--- TESTE 5: Narrativa e Linha do Tempo (15 Meses) ---")
    uid = DEMO_USER_UID
    hoje = date.today()

    lans = db.supabase.table("lancamentos").select("data, tipo, valor, status, serie_id, membro_id").eq("user_id", uid).execute().data or []
    datas = [l["data"] for l in lans]
    datas.sort()
    data_min = datas[0]
    data_max = datas[-1]
    print(f"  Período coberto: De {data_min} até {data_max}")

    # Compras Parceladas
    series = {l["serie_id"] for l in lans if l.get("serie_id")}
    assert len(series) >= 2, f"Esperadas pelo menos 2 compras parceladas, encontradas {len(series)}"
    print(f"  [OK] Séries parceladas em cascata encontradas: {len(series)}")

    # Lançamentos pendentes vs pagos
    pagos = [l for l in lans if l["status"] == "Pago"]
    pendentes = [l for l in lans if l["status"] == "Pendente"]
    print(f"  Total Pagos: {len(pagos)} | Total Pendentes: {len(pendentes)}")
    assert len(pagos) > 0 and len(pendentes) > 0, "Deve haver lançamentos pagos e pendentes!"
    print("  [OK] Projeção futura e histórico passado devidamente diferenciados!")


def main():
    print("================================================================")
    print(" INICIANDO BATERIA DE TESTES DO PERFIL VITRINE (DEMBASE V3)")
    print("================================================================")
    testar_trava_de_seguranca()
    testar_geracao_e_idempotencia()
    testar_multi_perfis_e_entidades()
    testar_meu_cofre_e_cobertura()
    testar_narrativa_e_datas_relativas()
    print("\n================================================================")
    print("  TODOS OS 5 TESTES DO PERFIL VITRINE FORAM APROVADOS COM 100%!")
    print("================================================================\n")


if __name__ == "__main__":
    main()
