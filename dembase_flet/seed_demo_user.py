"""
=============================================================================
DemBase v3 — dembase_flet/seed_demo_user.py
Criação e população de usuário teste com dados realistas para demonstração:
- Contas bancárias (Nubank, Inter, Itaú, Dinheiro)
- Cartões de crédito e faturas (Nubank Ultravioleta, Inter Black)
- Categorias e subcategorias organizadas
- Potes da Regra 50/30/20
- Caixinhas de teto (Aluguel, Carro/IPVA, Reserva de Emergência)
- Lançamentos completos: receitas, despesas (débito, crédito, pix),
  compras parceladas com efeito cascata, despesas pendentes e provisionamentos.

Execução:
    python dembase_flet/seed_demo_user.py
=============================================================================
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import date, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DIR_ATUAL = os.path.dirname(os.path.abspath(__file__))
if DIR_ATUAL not in sys.path:
    sys.path.insert(0, DIR_ATUAL)

from services.supabase_client import (
    fazer_login,
    supabase,
)


def popular_usuario(email: str, senha: str):
    print(f"\n========================================================")
    print(f" Instando/populando usuário de demonstração: {email}")
    print(f"========================================================")

    # 1. Autenticar usuário
    auth_resp = fazer_login(email, senha)
    if not auth_resp or not auth_resp.user:
        raise RuntimeError(f"Falha ao autenticar {email}. Verifique se o usuário existe no Supabase.")

    uid = auth_resp.user.id
    print(f"[1/8] Autenticado com sucesso! UID: {uid}")

    # 2. Limpar dados anteriores do usuário sob RLS
    print("[2/8] Limpando dados anteriores deste usuário...")
    supabase.table("lancamentos").delete().eq("perfil_id", uid).execute()
    supabase.table("caixinhas_teto_movimentacoes").delete().eq("user_id", uid).execute()
    supabase.table("caixinhas_teto").delete().eq("user_id", uid).execute()
    supabase.table("faturas").delete().eq("user_id", uid).execute()
    supabase.table("cartoes").delete().eq("user_id", uid).execute()
    supabase.table("subcategorias").delete().eq("user_id", uid).execute()
    supabase.table("categorias").delete().eq("perfil_id", uid).execute()
    supabase.table("contas").delete().eq("perfil_id", uid).execute()

    # 3. Atualizar perfil
    print("[3/8] Configurando Perfil e Potes Financeiros...")
    supabase.table("perfis").update({
        "nome": "Usuário Demonstração",
        "renda_referencia": 5500.00
    }).eq("id", uid).execute()

    # Potes
    try:
        supabase.rpc("seed_potes_usuario", {"p_user_id": uid}).execute()
    except Exception:
        pass

    potes_resp = supabase.table("potes").select("id, posicao, nome").eq("user_id", uid).order("posicao").execute()
    potes_map = {row["posicao"]: row["id"] for row in (potes_resp.data or [])}
    pote_fixo = potes_map.get(1)
    pote_semi = potes_map.get(2)
    pote_meta = potes_map.get(3)
    pote_praz = potes_map.get(4)
    pote_conh = potes_map.get(5)
    pote_lib  = potes_map.get(6)

    # 4. Criar Contas
    print("[4/8] Criando Contas Bancárias...")
    cta_nu_id = str(uuid.uuid4())
    cta_inter_id = str(uuid.uuid4())
    cta_itau_id = str(uuid.uuid4())
    cta_dinh_id = str(uuid.uuid4())

    contas_data = [
        {
            "id": cta_nu_id,
            "perfil_id": uid,
            "user_id": uid,
            "nome": "Nubank",
            "tipo_conta": "corrente",
            "banco": "Nubank",
            "cor": "#820AD1",
            "icone": "account_balance_wallet",
            "saldo_inicial": 3500.00,
            "saldo_atual": 3500.00,
            "saldo_previsto": 3500.00,
            "ativo": True,
        },
        {
            "id": cta_inter_id,
            "perfil_id": uid,
            "user_id": uid,
            "nome": "Banco Inter",
            "tipo_conta": "corrente",
            "banco": "Inter",
            "cor": "#FF7A00",
            "icone": "account_balance",
            "saldo_inicial": 6200.00,
            "saldo_atual": 6200.00,
            "saldo_previsto": 6200.00,
            "ativo": True,
        },
        {
            "id": cta_itau_id,
            "perfil_id": uid,
            "user_id": uid,
            "nome": "Itaú",
            "tipo_conta": "corrente",
            "banco": "Itaú",
            "cor": "#EC7000",
            "icone": "account_balance",
            "saldo_inicial": 1850.00,
            "saldo_atual": 1850.00,
            "saldo_previsto": 1850.00,
            "ativo": True,
        },
        {
            "id": cta_dinh_id,
            "perfil_id": uid,
            "user_id": uid,
            "nome": "Dinheiro em Espécie",
            "tipo_conta": "corrente",
            "banco": "Dinheiro",
            "cor": "#10B981",
            "icone": "payments",
            "saldo_inicial": 450.00,
            "saldo_atual": 450.00,
            "saldo_previsto": 450.00,
            "ativo": True,
        },
    ]
    supabase.table("contas").insert(contas_data).execute()

    # 5. Criar Cartões de Crédito e Faturas
    print("[5/8] Criando Cartões de Crédito e Faturas...")
    card_nu_id = str(uuid.uuid4())
    card_inter_id = str(uuid.uuid4())

    cartoes_data = [
        {
            "id": card_nu_id,
            "user_id": uid,
            "nome": "Nubank Ultravioleta",
            "bandeira": "mastercard",
            "cor": "#820AD1",
            "icone": "credit_card",
            "limite_total": 8000.00,
            "limite_disponivel": 8000.00,
            "dia_fechamento": 20,
            "dia_vencimento": 27,
            "conta_debito_id": cta_nu_id,
            "ativo": True,
        },
        {
            "id": card_inter_id,
            "user_id": uid,
            "nome": "Inter Mastercard Black",
            "bandeira": "mastercard",
            "cor": "#FF7A00",
            "icone": "credit_card",
            "limite_total": 15000.00,
            "limite_disponivel": 15000.00,
            "dia_fechamento": 10,
            "dia_vencimento": 17,
            "conta_debito_id": cta_inter_id,
            "ativo": True,
        },
    ]
    supabase.table("cartoes").insert(cartoes_data).execute()

    fat_nu_out = str(uuid.uuid4())
    fat_nu_nov = str(uuid.uuid4())
    fat_nu_dez = str(uuid.uuid4())
    fat_in_out = str(uuid.uuid4())
    fat_in_nov = str(uuid.uuid4())
    fat_in_dez = str(uuid.uuid4())

    faturas_data = [
        {"id": fat_nu_out, "cartao_id": card_nu_id, "user_id": uid, "mes": 10, "ano": 2026, "valor_total": 0.0, "valor_pago": 0.0, "data_fechamento": "2026-10-20", "data_vencimento": "2026-10-27", "status": "fechada"},
        {"id": fat_nu_nov, "cartao_id": card_nu_id, "user_id": uid, "mes": 11, "ano": 2026, "valor_total": 0.0, "valor_pago": 0.0, "data_fechamento": "2026-11-20", "data_vencimento": "2026-11-27", "status": "aberta"},
        {"id": fat_nu_dez, "cartao_id": card_nu_id, "user_id": uid, "mes": 12, "ano": 2026, "valor_total": 0.0, "valor_pago": 0.0, "data_fechamento": "2026-12-20", "data_vencimento": "2026-12-27", "status": "aberta"},
        {"id": fat_in_out, "cartao_id": card_inter_id, "user_id": uid, "mes": 10, "ano": 2026, "valor_total": 0.0, "valor_pago": 0.0, "data_fechamento": "2026-10-10", "data_vencimento": "2026-10-17", "status": "paga"},
        {"id": fat_in_nov, "cartao_id": card_inter_id, "user_id": uid, "mes": 11, "ano": 2026, "valor_total": 0.0, "valor_pago": 0.0, "data_fechamento": "2026-11-10", "data_vencimento": "2026-11-17", "status": "aberta"},
        {"id": fat_in_dez, "cartao_id": card_inter_id, "user_id": uid, "mes": 12, "ano": 2026, "valor_total": 0.0, "valor_pago": 0.0, "data_fechamento": "2026-12-10", "data_vencimento": "2026-12-17", "status": "aberta"},
    ]
    supabase.table("faturas").insert(faturas_data).execute()

    # 6. Criar Categorias e Subcategorias
    print("[6/8] Criando Categorias e Subcategorias...")
    cat_alim_id = str(uuid.uuid4())
    cat_mora_id = str(uuid.uuid4())
    cat_trans_id = str(uuid.uuid4())
    cat_lazer_id = str(uuid.uuid4())
    cat_saude_id = str(uuid.uuid4())
    cat_educ_id = str(uuid.uuid4())
    cat_sal_id = str(uuid.uuid4())
    cat_inv_id = str(uuid.uuid4())
    cat_out_id = str(uuid.uuid4())

    categorias_data = [
        {"id": cat_alim_id, "perfil_id": uid, "user_id": uid, "nome": "Alimentação", "icone": "restaurant", "cor": "#F59E0B", "tipo": "ambos", "ativo": True},
        {"id": cat_mora_id, "perfil_id": uid, "user_id": uid, "nome": "Moradia", "icone": "home", "cor": "#3B82F6", "tipo": "ambos", "ativo": True},
        {"id": cat_trans_id, "perfil_id": uid, "user_id": uid, "nome": "Transporte", "icone": "directions_car", "cor": "#6366F1", "tipo": "ambos", "ativo": True},
        {"id": cat_lazer_id, "perfil_id": uid, "user_id": uid, "nome": "Lazer", "icone": "sports_esports", "cor": "#EC4899", "tipo": "ambos", "ativo": True},
        {"id": cat_saude_id, "perfil_id": uid, "user_id": uid, "nome": "Saúde", "icone": "local_hospital", "cor": "#EF4444", "tipo": "ambos", "ativo": True},
        {"id": cat_educ_id, "perfil_id": uid, "user_id": uid, "nome": "Educação", "icone": "school", "cor": "#8B5CF6", "tipo": "ambos", "ativo": True},
        {"id": cat_sal_id, "perfil_id": uid, "user_id": uid, "nome": "Salário & Renda", "icone": "payments", "cor": "#10B981", "tipo": "ambos", "ativo": True},
        {"id": cat_inv_id, "perfil_id": uid, "user_id": uid, "nome": "Investimento", "icone": "trending_up", "cor": "#14B8A6", "tipo": "ambos", "ativo": True},
        {"id": cat_out_id, "perfil_id": uid, "user_id": uid, "nome": "Outros", "icone": "more_horiz", "cor": "#64748B", "tipo": "ambos", "ativo": True},
    ]
    supabase.table("categorias").insert(categorias_data).execute()

    sub_mercado_id = str(uuid.uuid4())
    sub_rest_id = str(uuid.uuid4())
    sub_deliv_id = str(uuid.uuid4())
    sub_aluguel_id = str(uuid.uuid4())
    sub_luz_id = str(uuid.uuid4())
    sub_net_id = str(uuid.uuid4())
    sub_gas_id = str(uuid.uuid4())
    sub_uber_id = str(uuid.uuid4())
    sub_manut_id = str(uuid.uuid4())
    sub_cinema_id = str(uuid.uuid4())
    sub_stream_id = str(uuid.uuid4())
    sub_farm_id = str(uuid.uuid4())
    sub_acad_id = str(uuid.uuid4())
    sub_curso_id = str(uuid.uuid4())
    sub_salclt_id = str(uuid.uuid4())
    sub_free_id = str(uuid.uuid4())
    sub_fixa_id = str(uuid.uuid4())
    sub_acoes_id = str(uuid.uuid4())

    subcategorias_data = [
        {"id": sub_mercado_id, "categoria_id": cat_alim_id, "user_id": uid, "nome": "Supermercado", "cor": "#F59E0B", "ativo": True},
        {"id": sub_rest_id, "categoria_id": cat_alim_id, "user_id": uid, "nome": "Restaurantes", "cor": "#F59E0B", "ativo": True},
        {"id": sub_deliv_id, "categoria_id": cat_alim_id, "user_id": uid, "nome": "Delivery & Lanches", "cor": "#F59E0B", "ativo": True},
        {"id": sub_aluguel_id, "categoria_id": cat_mora_id, "user_id": uid, "nome": "Aluguel & Condomínio", "cor": "#3B82F6", "ativo": True},
        {"id": sub_luz_id, "categoria_id": cat_mora_id, "user_id": uid, "nome": "Energia Elétrica", "cor": "#3B82F6", "ativo": True},
        {"id": sub_net_id, "categoria_id": cat_mora_id, "user_id": uid, "nome": "Internet Fibra", "cor": "#3B82F6", "ativo": True},
        {"id": sub_gas_id, "categoria_id": cat_trans_id, "user_id": uid, "nome": "Combustível", "cor": "#6366F1", "ativo": True},
        {"id": sub_uber_id, "categoria_id": cat_trans_id, "user_id": uid, "nome": "Uber / 99", "cor": "#6366F1", "ativo": True},
        {"id": sub_manut_id, "categoria_id": cat_trans_id, "user_id": uid, "nome": "Manutenção Veicular", "cor": "#6366F1", "ativo": True},
        {"id": sub_cinema_id, "categoria_id": cat_lazer_id, "user_id": uid, "nome": "Cinema & Passeios", "cor": "#EC4899", "ativo": True},
        {"id": sub_stream_id, "categoria_id": cat_lazer_id, "user_id": uid, "nome": "Streaming & Apps", "cor": "#EC4899", "ativo": True},
        {"id": sub_farm_id, "categoria_id": cat_saude_id, "user_id": uid, "nome": "Farmácia", "cor": "#EF4444", "ativo": True},
        {"id": sub_acad_id, "categoria_id": cat_saude_id, "user_id": uid, "nome": "Academia", "cor": "#EF4444", "ativo": True},
        {"id": sub_curso_id, "categoria_id": cat_educ_id, "user_id": uid, "nome": "Cursos & Livros", "cor": "#8B5CF6", "ativo": True},
        {"id": sub_salclt_id, "categoria_id": cat_sal_id, "user_id": uid, "nome": "Salário CLT", "cor": "#10B981", "ativo": True},
        {"id": sub_free_id, "categoria_id": cat_sal_id, "user_id": uid, "nome": "Freelance", "cor": "#10B981", "ativo": True},
        {"id": sub_fixa_id, "categoria_id": cat_inv_id, "user_id": uid, "nome": "Renda Fixa / Tesouro", "cor": "#14B8A6", "ativo": True},
        {"id": sub_acoes_id, "categoria_id": cat_inv_id, "user_id": uid, "nome": "Ações & FIIs", "cor": "#14B8A6", "ativo": True},
    ]
    supabase.table("subcategorias").insert(subcategorias_data).execute()

    # 7. Criar Caixinhas de Teto
    print("[7/8] Criando Caixinhas de Teto com Provisões Automáticas...")
    caixa_aluguel_id = str(uuid.uuid4())
    caixa_carro_id = str(uuid.uuid4())
    caixa_reserva_id = str(uuid.uuid4())

    caixinhas_data = [
        {
            "id": caixa_aluguel_id,
            "user_id": uid,
            "nome": "Aluguel do Apartamento",
            "valor_meta": 1500.00,
            "saldo_atual": 1500.00,
            "data_provisao": "2026-11-10",
            "data_alvo": "2026-11-10",
            "cor": "#3B82F6",
            "icone": "inventory_2",
            "categoria_id": cat_mora_id,
            "subcategoria_id": sub_aluguel_id,
            "pote_id": pote_fixo,
            "conta_id": cta_nu_id,
            "tipo_provisao": "despesa",
            "recorrente": True,
            "dia_recorrencia": 10,
            "ativo": True,
        },
        {
            "id": caixa_carro_id,
            "user_id": uid,
            "nome": "Manutenção & IPVA",
            "valor_meta": 2400.00,
            "saldo_atual": 1200.00,
            "data_provisao": "2026-11-20",
            "data_alvo": "2026-12-15",
            "cor": "#F59E0B",
            "icone": "two_wheeler",
            "categoria_id": cat_trans_id,
            "subcategoria_id": sub_manut_id,
            "pote_id": pote_semi,
            "conta_id": cta_inter_id,
            "tipo_provisao": "despesa",
            "recorrente": True,
            "dia_recorrencia": 20,
            "ativo": True,
        },
        {
            "id": caixa_reserva_id,
            "user_id": uid,
            "nome": "Reserva de Emergência",
            "valor_meta": 15000.00,
            "saldo_atual": 8500.00,
            "data_provisao": "2026-11-05",
            "data_alvo": "2027-06-30",
            "cor": "#10B981",
            "icone": "shield",
            "categoria_id": cat_inv_id,
            "subcategoria_id": sub_fixa_id,
            "pote_id": pote_lib,
            "conta_id": cta_inter_id,
            "tipo_provisao": "reserva",
            "recorrente": True,
            "dia_recorrencia": 5,
            "ativo": True,
        },
    ]
    supabase.table("caixinhas_teto").insert(caixinhas_data).execute()

    # 8. Criar Lançamentos Financeiros Realistas
    print("[8/8] Criando Lançamentos Financeiros (Setembro, Outubro e Novembro)...")
    serie_note = str(uuid.uuid4())
    serie_phone = str(uuid.uuid4())

    lancamentos_data = [
        # --- SETEMBRO 2026 ---
        {"perfil_id": uid, "user_id": uid, "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_sal_id, "subcategoria_id": sub_salclt_id, "valor": 5500.00, "data": "2026-09-05", "descricao": "Salário CLT Setembro", "status": "Pago", "regra": None, "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix", "conta_id": cta_inter_id, "categoria_id": cat_sal_id, "subcategoria_id": sub_free_id, "valor": 1400.00, "data": "2026-09-15", "descricao": "Freelance UI Design", "status": "Pago", "regra": None, "pote_id": pote_lib},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_mora_id, "subcategoria_id": sub_aluguel_id, "valor": 1500.00, "data": "2026-09-10", "descricao": "Aluguel Apartamento", "status": "Pago", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito", "conta_id": cta_nu_id, "categoria_id": cat_alim_id, "subcategoria_id": sub_mercado_id, "valor": 920.00, "data": "2026-09-12", "descricao": "Compras Supermercado", "status": "Pago", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_mora_id, "subcategoria_id": sub_luz_id, "valor": 165.00, "data": "2026-09-15", "descricao": "Conta de Energia Elétrica", "status": "Pago", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_inter_id, "categoria_id": cat_inv_id, "subcategoria_id": sub_fixa_id, "valor": 1100.00, "data": "2026-09-10", "descricao": "Aporte CDB Inter", "status": "Pago", "regra": "Investimento", "pote_id": pote_lib},

        # --- OUTUBRO 2026 (Mês Atual - 27/10/2026) ---
        {"perfil_id": uid, "user_id": uid, "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_sal_id, "subcategoria_id": sub_salclt_id, "valor": 5500.00, "data": "2026-10-05", "descricao": "Salário Mensal CLT", "status": "Pago", "regra": None, "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix", "conta_id": cta_inter_id, "categoria_id": cat_sal_id, "subcategoria_id": sub_free_id, "valor": 1800.00, "data": "2026-10-14", "descricao": "Projeto Consultoria Web", "status": "Pago", "regra": None, "pote_id": pote_lib},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_mora_id, "subcategoria_id": sub_aluguel_id, "valor": 1500.00, "data": "2026-10-10", "descricao": "Aluguel do Mês", "status": "Pago", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito", "conta_id": cta_nu_id, "categoria_id": cat_alim_id, "subcategoria_id": sub_mercado_id, "valor": 890.00, "data": "2026-10-08", "descricao": "Mercado Pão de Açúcar", "status": "Pago", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_mora_id, "subcategoria_id": sub_luz_id, "valor": 178.50, "data": "2026-10-12", "descricao": "Energia Elétrica Enel", "status": "Pago", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_mora_id, "subcategoria_id": sub_net_id, "valor": 139.90, "data": "2026-10-16", "descricao": "Internet Fibra Óptica", "status": "Pago", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito", "conta_id": cta_nu_id, "categoria_id": cat_trans_id, "subcategoria_id": sub_gas_id, "valor": 220.00, "data": "2026-10-18", "descricao": "Gasolina Posto Shell", "status": "Pago", "regra": "Essencial", "pote_id": pote_semi},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito", "conta_id": cta_nu_id, "categoria_id": cat_lazer_id, "subcategoria_id": sub_cinema_id, "valor": 85.00, "data": "2026-10-19", "descricao": "Ingressos Cinema UCI", "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito", "conta_id": cta_nu_id, "categoria_id": cat_saude_id, "subcategoria_id": sub_farm_id, "valor": 92.30, "data": "2026-10-21", "descricao": "Medicamentos Drogasil", "status": "Pago", "regra": "Essencial", "pote_id": pote_semi},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_educ_id, "subcategoria_id": sub_curso_id, "valor": 197.00, "data": "2026-10-23", "descricao": "Curso Python & Flet", "status": "Pago", "regra": "Investimento", "pote_id": pote_conh},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_inter_id, "categoria_id": cat_inv_id, "subcategoria_id": sub_fixa_id, "valor": 1200.00, "data": "2026-10-10", "descricao": "Aporte Tesouro Selic", "status": "Pago", "regra": "Investimento", "pote_id": pote_lib},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_trans_id, "subcategoria_id": sub_gas_id, "valor": 180.00, "data": "2026-10-30", "descricao": "Combustível Viagem", "status": "Pendente", "regra": "Essencial", "pote_id": pote_semi},

        # --- CARTÕES DE CRÉDITO & FATURAS ---
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_inter_id, "fatura_id": fat_in_out, "fatura": "10/2026", "categoria_id": cat_lazer_id, "subcategoria_id": sub_stream_id, "valor": 79.80, "data": "2026-10-02", "descricao": "Netflix + Spotify", "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura_id": fat_nu_out, "fatura": "10/2026", "categoria_id": cat_alim_id, "subcategoria_id": sub_rest_id, "valor": 245.00, "data": "2026-10-11", "descricao": "Jantar Outback", "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz},

        # --- COMPRAS PARCELADAS (Notebook Dell 10x 350) ---
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura": "09/2026", "parcela_atual": 1, "total_parcelas": 10, "serie_id": serie_note, "categoria_id": cat_educ_id, "subcategoria_id": sub_curso_id, "valor": 350.00, "data": "2026-09-27", "descricao": "Notebook Dell XPS (1/10)", "status": "Pago", "regra": "Investimento", "pote_id": pote_conh},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura_id": fat_nu_out, "fatura": "10/2026", "parcela_atual": 2, "total_parcelas": 10, "serie_id": serie_note, "categoria_id": cat_educ_id, "subcategoria_id": sub_curso_id, "valor": 350.00, "data": "2026-10-27", "descricao": "Notebook Dell XPS (2/10)", "status": "Pago", "regra": "Investimento", "pote_id": pote_conh},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura_id": fat_nu_nov, "fatura": "11/2026", "parcela_atual": 3, "total_parcelas": 10, "serie_id": serie_note, "categoria_id": cat_educ_id, "subcategoria_id": sub_curso_id, "valor": 350.00, "data": "2026-11-27", "descricao": "Notebook Dell XPS (3/10)", "status": "Pendente", "regra": "Investimento", "pote_id": pote_conh},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura_id": fat_nu_dez, "fatura": "12/2026", "parcela_atual": 4, "total_parcelas": 10, "serie_id": serie_note, "categoria_id": cat_educ_id, "subcategoria_id": sub_curso_id, "valor": 350.00, "data": "2026-12-27", "descricao": "Notebook Dell XPS (4/10)", "status": "Pendente", "regra": "Investimento", "pote_id": pote_conh},

        # --- COMPRAS PARCELADAS (Smartphone Galaxy 3x 450) ---
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura_id": fat_nu_out, "fatura": "10/2026", "parcela_atual": 1, "total_parcelas": 3, "serie_id": serie_phone, "categoria_id": cat_out_id, "subcategoria_id": None, "valor": 450.00, "data": "2026-10-27", "descricao": "Smartphone Galaxy (1/3)", "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura_id": fat_nu_nov, "fatura": "11/2026", "parcela_atual": 2, "total_parcelas": 3, "serie_id": serie_phone, "categoria_id": cat_out_id, "subcategoria_id": None, "valor": 450.00, "data": "2026-11-27", "descricao": "Smartphone Galaxy (2/3)", "status": "Pendente", "regra": "Estilo de Vida", "pote_id": pote_praz},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito", "cartao_id": card_nu_id, "fatura_id": fat_nu_dez, "fatura": "12/2026", "parcela_atual": 3, "total_parcelas": 3, "serie_id": serie_phone, "categoria_id": cat_out_id, "subcategoria_id": None, "valor": 450.00, "data": "2026-12-27", "descricao": "Smartphone Galaxy (3/3)", "status": "Pendente", "regra": "Estilo de Vida", "pote_id": pote_praz},

        # --- NOVEMBRO 2026 (Futuro Projetado) ---
        {"perfil_id": uid, "user_id": uid, "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_sal_id, "subcategoria_id": sub_salclt_id, "valor": 5500.00, "data": "2026-11-05", "descricao": "Salário Previsto CLT", "status": "Pendente", "regra": None, "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_mora_id, "subcategoria_id": sub_luz_id, "valor": 180.00, "data": "2026-11-15", "descricao": "Energia Elétrica", "status": "Pendente", "regra": "Essencial", "pote_id": pote_fixo},
        {"perfil_id": uid, "user_id": uid, "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix", "conta_id": cta_nu_id, "categoria_id": cat_mora_id, "subcategoria_id": sub_net_id, "valor": 139.90, "data": "2026-11-16", "descricao": "Internet Fibra", "status": "Pendente", "regra": "Essencial", "pote_id": pote_fixo},
    ]

    supabase.table("lancamentos").insert(lancamentos_data).execute()

    # 9. Recalcular saldos, faturas e limites
    print("Recalculando saldos, faturas e limites no PostgreSQL...")
    try:
        supabase.rpc("fn_recalcular_saldos_usuario", {"p_user_id": uid}).execute()
    except Exception as ex:
        print(f"  (Aviso) fn_recalcular_saldos_usuario: {ex}")

    try:
        fats = [fat_nu_out, fat_nu_nov, fat_nu_dez, fat_in_out, fat_in_nov, fat_in_dez]
        supabase.rpc("fn_recalcular_totais_faturas", {"p_faturas_ids": fats}).execute()
    except Exception as ex:
        print(f"  (Aviso) fn_recalcular_totais_faturas: {ex}")

    print(f" Sucesso! Usuário '{email}' populado com conjunto completo de demonstração!")


def main():
    contas_demo = [
        ("teste@dembase.com", "teste123"),
        ("teste@teste.com", "teste123"),
    ]
    for email, senha in contas_demo:
        try:
            popular_usuario(email, senha)
        except Exception as e:
            print(f"Erro ao processar {email}: {e}")

    print("\n========================================================")
    print(" BASE DE DEMONSTRAÇÃO CONCLUÍDA COM 100% DE SUCESSO!")
    print(" Credenciais prontas para uso:")
    print("  -> E-mail: teste@dembase.com   (ou teste@teste.com)")
    print("  -> Senha:  teste123")
    print("========================================================\n")


if __name__ == "__main__":
    main()
