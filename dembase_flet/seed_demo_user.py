"""
=============================================================================
DemBase v3 — dembase_flet/seed_demo_user.py
Criação e população do "Perfil Vitrine" de demonstração:
- Família Silva: Carlos (Principal) & Marina (Esposa)
- 15 meses de vida financeira realista (-12 a +2 meses relativos à data atual)
- Curva narrativa: Vermelho -> Amarelo -> Verde -> Imprevisto -> Recuperação -> Atual -> Futuro
- Contas bancárias: Nubank Carlos, Inter Marina e Carteira Física
- Cartões de crédito e faturas: Nubank Ultravioleta e Inter Mastercard Black
- Compras parceladas em cascata (Notebook Dell 10x, Geladeira Frost Free 8x)
- Módulo "Meu Cofre": Porquinho da Reserva com resgate emergencial no M-4 e Renda Fixa 102% CDI
- 6 Potes e Caixinhas de Teto integrados.

Execução:
    python dembase_flet/seed_demo_user.py
=============================================================================
"""
from __future__ import annotations

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))
if DIR_ATUAL not in sys.path:
    sys.path.insert(0, DIR_ATUAL)

from services.demo_generator import (
    DEMO_USER_EMAIL,
    gerar_perfil_vitrine,
)
import services.supabase_client as db


def main():
    print("\n========================================================")
    print(" DEMBASE v3 — GERADOR DO PERFIL VITRINE (DEMO)")
    print("========================================================")
    print(" Autenticando usuário de demonstração...")

    auth_resp = db.fazer_login(DEMO_USER_EMAIL, "teste123")
    if not auth_resp or not auth_resp.user:
        print(f"[ERRO] Falha ao autenticar {DEMO_USER_EMAIL}. Verifique as credenciais no Supabase.")
        sys.exit(1)

    uid = auth_resp.user.id
    print(f" Autenticado com sucesso! UID Demo: {uid}")
    print(" Iniciando geração dos 15 meses de dados narrativos...\n")

    def status_callback(msg: str):
        print(f"  [VITRINE] {msg}")

    try:
        resumo = gerar_perfil_vitrine(uid=uid, status_cb=status_callback)
        print("\n========================================================")
        print(" PERFIL VITRINE GERADO COM 100% DE SUCESSO!")
        print("========================================================")
        print(f"  -> Usuário:            {resumo['usuario']}")
        print(f"  -> Total Lançamentos:  {resumo['total_lancamentos']}")
        print(f"  -> Total Faturas:      {resumo['total_faturas']}")
        print(f"  -> Movs. Meu Cofre:    {resumo['total_movimentacoes_cofre']}")
        print(f"  -> Reserva de Emerg.:  R$ {resumo['saldo_reserva']:,.2f}")
        print(f"  -> Renda Fixa 102% CDI: R$ {resumo['saldo_cdi']:,.2f}")
        print(f"  -> Membros:            {', '.join(resumo['membros'])}")
        print(f"  -> Contas:             {', '.join(resumo['contas'])}")
        print(f"  -> Cartões:            {', '.join(resumo['cartoes'])}")
        print("========================================================")
        print(" Credenciais prontas para gravação e testes:")
        print(f"  -> E-mail: {DEMO_USER_EMAIL}")
        print("  -> Senha:  teste123")
        print("========================================================\n")
    except Exception as ex:
        print(f"\n[ERRO FATAL] Falha ao gerar perfil vitrine: {ex}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
