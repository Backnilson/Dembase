"""
=============================================================================
DemBase v3 — services/demo_generator.py
Gerador de Dados de Demonstração ("Perfil Vitrine"):
Popula o perfil de demonstração com 15 meses de histórico realista:
- 12 meses fechados com narrativa financeira completa
- Mês atual em andamento (parcialmente pago + pendentes + alerta)
- 2 meses futuros de projeção (contas fixas + parcelas de cartões)
- Multi-Perfis Familiares ("Eu, Ela & Nós": Carlos & Marina)
- Módulo "Meu Cofre" (Porquinho, Renda Fixa 102% CDI, resgate emergencial)
- 6 Potes, Caixinhas de Teto e Cartões com parcelamentos em cascata.

TRAVA DE SEGURANÇA CRÍTICA:
Atua EXCLUSIVAMENTE no perfil teste/demo (teste@dembase.com).
Dados reais de usuários são 100% blindados e intocáveis.
=============================================================================
"""
from __future__ import annotations

import calendar
import os
import sys
import uuid
from datetime import date, timedelta
from typing import Callable, Optional

from services.supabase_client import (
    fazer_login,
    invalidar_cache,
    supabase,
    usuario_atual,
)

# ── IDENTIFICADORES E SEGURANÇA ──────────────────────────────────────────────
DEMO_USER_EMAIL = "teste@dembase.com"
DEMO_USER_UID = "2d3e295a-e0a4-4679-9bfd-cb160b8e0f50"
REAL_USER_DENILSON_UID = "07614dd5-3a3a-4538-8cc0-915a18c1fd85"


class SecurityDemoError(PermissionError):
    """Exceção levantada quando há tentativa de operar em usuário não-demo."""
    pass


def validar_seguranca_demo(uid: str, email: str = "") -> None:
    """
    Trava absoluta contra acidentes: impede qualquer operação em perfil real.
    Garante que a operação ocorra estritamente no UID de teste.
    """
    uid_str = str(uid).strip().lower()
    denilson_str = str(REAL_USER_DENILSON_UID).strip().lower()
    demo_str = str(DEMO_USER_UID).strip().lower()

    if uid_str == denilson_str:
        raise SecurityDemoError(
            "TRAVA DE SEGURANÇA MÁXIMA: Tentativa de modificação no perfil real de Denilson bloqueada!"
        )

    if uid_str != demo_str:
        # Se for outro UID, verifica se o e-mail tem explicitamente 'teste'
        if not email or "teste" not in email.lower():
            raise SecurityDemoError(
                f"TRAVA DE SEGURANÇA: Operação cancelada. O UID '{uid}' não pertence ao usuário de demonstração."
            )


# ── AUXILIARES DE DATA RELATIVA ──────────────────────────────────────────────
def somar_meses(ano: int, mes: int, delta: int) -> tuple[int, int]:
    """Soma delta meses a um ano/mês mantendo integridade 1..12."""
    total = ano * 12 + (mes - 1) + delta
    return total // 12, (total % 12) + 1


def data_relativa(hoje: date, delta_meses: int, dia: int) -> date:
    """Retorna uma data com delta_meses em relação a hoje, limitando o dia ao mês."""
    ano, mes = somar_meses(hoje.year, hoje.month, delta_meses)
    max_dias = calendar.monthrange(ano, mes)[1]
    dia_valido = max(1, min(dia, max_dias))
    return date(ano, mes, dia_valido)


def mes_ano_str(hoje: date, delta_meses: int) -> str:
    """Retorna 'MM/AAAA' relativo a hoje."""
    ano, mes = somar_meses(hoje.year, hoje.month, delta_meses)
    return f"{mes:02d}/{ano}"


# ── LIMPEZA IDEMPOTENTE DO PERFIL DEMO ───────────────────────────────────────
def limpar_dados_demo(uid: str, status_cb: Optional[Callable[[str], None]] = None) -> None:
    """
    Limpa todos os dados anteriores do usuário demo respeitando Foreign Keys.
    """
    def log(msg: str):
        if status_cb:
            status_cb(msg)

    validar_seguranca_demo(uid)

    log("Limpando movimentações e investimentos do perfil demo...")
    supabase.table("cofres_movimentacoes").delete().eq("user_id", uid).execute()
    supabase.table("cofres_investimento").delete().eq("user_id", uid).execute()
    supabase.table("cofres_config").delete().eq("user_id", uid).execute()

    log("Limpando lançamentos e caixinhas...")
    supabase.table("lancamentos").delete().eq("user_id", uid).execute()
    supabase.table("lancamentos").delete().eq("perfil_id", uid).execute()
    supabase.table("caixinhas_teto_movimentacoes").delete().eq("user_id", uid).execute()
    supabase.table("caixinhas_teto").delete().eq("user_id", uid).execute()

    log("Limpando faturas e cartões...")
    supabase.table("faturas").delete().eq("user_id", uid).execute()
    supabase.table("cartoes").delete().eq("user_id", uid).execute()

    log("Limpando subcategorias, categorias e contas...")
    supabase.table("subcategorias").delete().eq("user_id", uid).execute()
    supabase.table("categorias").delete().eq("user_id", uid).execute()
    supabase.table("categorias").delete().eq("perfil_id", uid).execute()
    supabase.table("contas").delete().eq("user_id", uid).execute()
    supabase.table("contas").delete().eq("perfil_id", uid).execute()

    log("Resetando membros familiares secundários...")
    try:
        supabase.table("visao_ativa").delete().eq("user_id", uid).execute()
    except Exception:
        pass
    # Deleta apenas membros não-principais para respeitar a trigger fn_trg_membros_guarda
    supabase.table("membros").delete().eq("user_id", uid).eq("principal", False).execute()


# ── GERADOR DO PERFIL VITRINE ────────────────────────────────────────────────
def gerar_perfil_vitrine(
    uid: Optional[str] = None,
    status_cb: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Popula o usuário de teste com 15 meses de vida financeira realista da Família Silva:
    - Carlos (Principal) & Marina (Esposa)
    - Nubank Carlos, Inter Marina e Carteira Dinheiro
    - Nubank Ultravioleta e Inter Mastercard Black com faturas e parcelas
    - Meu Cofre (Porquinho da Reserva + Renda Fixa 102% CDI + resgate no imprevisto)
    - 6 Potes e Caixinhas
    - 15 meses com narrativa (Vermelho -> Amarelo -> Verde -> Imprevisto -> Recuperação -> Atual -> Futuro)
    """
    def log(msg: str):
        if status_cb:
            status_cb(msg)

    # 1. Obter e validar usuário
    u = usuario_atual()
    user_email = u.email if u and u.email else DEMO_USER_EMAIL

    if not uid:
        if u and u.id:
            uid = u.id
        else:
            auth_resp = fazer_login(DEMO_USER_EMAIL, "teste123")
            if not auth_resp or not auth_resp.user:
                raise RuntimeError("Falha ao autenticar o usuário demo (teste@dembase.com).")
            uid = auth_resp.user.id
            user_email = auth_resp.user.email or DEMO_USER_EMAIL

    validar_seguranca_demo(uid, user_email)
    log(f"Iniciando Perfil Vitrine para usuário de demonstração ({user_email})...")

    hoje = date.today()

    # 2. Limpar dados anteriores (Idempotência garantida)
    limpar_dados_demo(uid, status_cb=status_cb)

    # 3. Configurar Perfil e Membros da Família
    log("Configurando Família Silva (Carlos & Marina)...")
    try:
        supabase.table("perfis").update({
            "nome": "Carlos & Marina Silva",
            "renda_referencia": 10500.00,
        }).eq("id", uid).execute()
    except Exception:
        pass

    # Membro Principal (Carlos)
    membros_existentes = supabase.table("membros").select("id, principal").eq("user_id", uid).execute().data or []
    carlos_id = None
    for m in membros_existentes:
        if m.get("principal"):
            carlos_id = m["id"]
            supabase.table("membros").update({
                "nome": "Carlos",
                "cor": "#3B82F6",
                "icone": "person",
                "ativo": True,
                "ordem": 0,
            }).eq("id", carlos_id).execute()
            break

    if not carlos_id:
        carlos_id = str(uuid.uuid4())
        supabase.table("membros").insert({
            "id": carlos_id,
            "user_id": uid,
            "nome": "Carlos",
            "cor": "#3B82F6",
            "icone": "person",
            "principal": True,
            "ativo": True,
            "ordem": 0,
        }).execute()

    # Membro Secundário (Marina)
    marina_id = str(uuid.uuid4())
    supabase.table("membros").insert({
        "id": marina_id,
        "user_id": uid,
        "nome": "Marina",
        "cor": "#EC4899",
        "icone": "favorite",
        "principal": False,
        "ativo": True,
        "ordem": 1,
    }).execute()

    # Visão Inicial: Casa (todos os membros = NULL)
    try:
        supabase.table("visao_ativa").upsert({
            "user_id": uid,
            "membro_ids": None,
        }).execute()
    except Exception:
        pass

    # 4. Configurar Potes Financeiros
    log("Configurando os 6 Potes Financeiros...")
    try:
        supabase.rpc("seed_potes_usuario", {"p_user": uid}).execute()
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

    # 5. Criar Contas Bancárias
    log("Criando Contas Bancárias familiares...")
    cta_nu_carlos = str(uuid.uuid4())
    cta_in_marina = str(uuid.uuid4())
    cta_dinheiro  = str(uuid.uuid4())

    contas_data = [
        {
            "id": cta_nu_carlos,
            "perfil_id": uid,
            "user_id": uid,
            "membro_id": carlos_id,
            "nome": "Nubank Carlos",
            "tipo_conta": "corrente",
            "banco": "Nubank",
            "cor": "#820AD1",
            "icone": "account_balance_wallet",
            "saldo_inicial": 3200.00,
            "saldo_atual": 3200.00,
            "saldo_previsto": 3200.00,
            "ativo": True,
        },
        {
            "id": cta_in_marina,
            "perfil_id": uid,
            "user_id": uid,
            "membro_id": marina_id,
            "nome": "Banco Inter Marina",
            "tipo_conta": "corrente",
            "banco": "Inter",
            "cor": "#FF7A00",
            "icone": "account_balance",
            "saldo_inicial": 4150.00,
            "saldo_atual": 4150.00,
            "saldo_previsto": 4150.00,
            "ativo": True,
        },
        {
            "id": cta_dinheiro,
            "perfil_id": uid,
            "user_id": uid,
            "membro_id": carlos_id,
            "nome": "Carteira Física",
            "tipo_conta": "corrente",
            "banco": "Dinheiro",
            "cor": "#10B981",
            "icone": "payments",
            "saldo_inicial": 350.00,
            "saldo_atual": 350.00,
            "saldo_previsto": 350.00,
            "ativo": True,
        },
    ]
    supabase.table("contas").insert(contas_data).execute()

    # 6. Criar Cartões de Crédito e Faturas dos 15 Meses (-12 a +2)
    log("Criando Cartões de Crédito e Faturas (15 Meses)...")
    card_nu_carlos = str(uuid.uuid4())
    card_in_marina = str(uuid.uuid4())

    cartoes_data = [
        {
            "id": card_nu_carlos,
            "user_id": uid,
            "membro_id": carlos_id,
            "nome": "Nubank Ultravioleta",
            "bandeira": "mastercard",
            "cor": "#820AD1",
            "icone": "credit_card",
            "limite_total": 12000.00,
            "limite_disponivel": 12000.00,
            "dia_fechamento": 20,
            "dia_vencimento": 27,
            "conta_debito_id": cta_nu_carlos,
            "ativo": True,
        },
        {
            "id": card_in_marina,
            "user_id": uid,
            "membro_id": marina_id,
            "nome": "Inter Mastercard Black",
            "bandeira": "mastercard",
            "cor": "#FF7A00",
            "icone": "credit_card",
            "limite_total": 15000.00,
            "limite_disponivel": 15000.00,
            "dia_fechamento": 10,
            "dia_vencimento": 17,
            "conta_debito_id": cta_in_marina,
            "ativo": True,
        },
    ]
    supabase.table("cartoes").insert(cartoes_data).execute()

    # Faturas para cada mês de -12 a +2
    faturas_data = []
    fat_map_nu: dict[tuple[int, int], str] = {}
    fat_map_in: dict[tuple[int, int], str] = {}

    for delta in range(-12, 3):
        ano_m, mes_m = somar_meses(hoje.year, hoje.month, delta)

        # Nubank Carlos (fechamento 20, vencimento 27)
        dt_fech_nu = data_relativa(hoje, delta, 20)
        dt_venc_nu = data_relativa(hoje, delta, 27)
        if dt_venc_nu < hoje:
            status_nu = "paga"
        elif dt_fech_nu <= hoje <= dt_venc_nu:
            status_nu = "fechada"
        else:
            status_nu = "aberta"

        fid_nu = str(uuid.uuid4())
        fat_map_nu[(ano_m, mes_m)] = fid_nu
        faturas_data.append({
            "id": fid_nu,
            "cartao_id": card_nu_carlos,
            "user_id": uid,
            "mes": mes_m,
            "ano": ano_m,
            "valor_total": 0.0,
            "valor_pago": 0.0,
            "data_fechamento": dt_fech_nu.isoformat(),
            "data_vencimento": dt_venc_nu.isoformat(),
            "status": status_nu,
        })

        # Inter Marina (fechamento 10, vencimento 17)
        dt_fech_in = data_relativa(hoje, delta, 10)
        dt_venc_in = data_relativa(hoje, delta, 17)
        if dt_venc_in < hoje:
            status_in = "paga"
        elif dt_fech_in <= hoje <= dt_venc_in:
            status_in = "fechada"
        else:
            status_in = "aberta"

        fid_in = str(uuid.uuid4())
        fat_map_in[(ano_m, mes_m)] = fid_in
        faturas_data.append({
            "id": fid_in,
            "cartao_id": card_in_marina,
            "user_id": uid,
            "mes": mes_m,
            "ano": ano_m,
            "valor_total": 0.0,
            "valor_pago": 0.0,
            "data_fechamento": dt_fech_in.isoformat(),
            "data_vencimento": dt_venc_in.isoformat(),
            "status": status_in,
        })

    supabase.table("faturas").insert(faturas_data).execute()

    # 7. Criar Categorias e Subcategorias
    log("Criando Categorias e Subcategorias financeiras...")
    cat_alim_id  = str(uuid.uuid4())
    cat_mora_id  = str(uuid.uuid4())
    cat_trans_id = str(uuid.uuid4())
    cat_lazer_id = str(uuid.uuid4())
    cat_saude_id = str(uuid.uuid4())
    cat_educ_id  = str(uuid.uuid4())
    cat_sal_id   = str(uuid.uuid4())
    cat_inv_id   = str(uuid.uuid4())
    cat_out_id   = str(uuid.uuid4())

    categorias_data = [
        {"id": cat_alim_id,  "perfil_id": uid, "user_id": uid, "nome": "Alimentação",      "icone": "restaurant",      "cor": "#F59E0B", "tipo": "ambos", "ativo": True},
        {"id": cat_mora_id,  "perfil_id": uid, "user_id": uid, "nome": "Moradia",          "icone": "home",            "cor": "#3B82F6", "tipo": "ambos", "ativo": True},
        {"id": cat_trans_id, "perfil_id": uid, "user_id": uid, "nome": "Transporte",       "icone": "directions_car",  "cor": "#6366F1", "tipo": "ambos", "ativo": True},
        {"id": cat_lazer_id, "perfil_id": uid, "user_id": uid, "nome": "Lazer & Prazer",   "icone": "sports_esports",  "cor": "#EC4899", "tipo": "ambos", "ativo": True},
        {"id": cat_saude_id, "perfil_id": uid, "user_id": uid, "nome": "Saúde",            "icone": "local_hospital",  "cor": "#EF4444", "tipo": "ambos", "ativo": True},
        {"id": cat_educ_id,  "perfil_id": uid, "user_id": uid, "nome": "Educação & Metas", "icone": "school",          "cor": "#8B5CF6", "tipo": "ambos", "ativo": True},
        {"id": cat_sal_id,   "perfil_id": uid, "user_id": uid, "nome": "Salário & Renda",  "icone": "payments",        "cor": "#10B981", "tipo": "ambos", "ativo": True},
        {"id": cat_inv_id,   "perfil_id": uid, "user_id": uid, "nome": "Investimento",     "icone": "trending_up",     "cor": "#14B8A6", "tipo": "ambos", "ativo": True},
        {"id": cat_out_id,   "perfil_id": uid, "user_id": uid, "nome": "Outros",           "icone": "more_horiz",      "cor": "#64748B", "tipo": "ambos", "ativo": True},
    ]
    supabase.table("categorias").insert(categorias_data).execute()

    sub_mercado_id = str(uuid.uuid4())
    sub_rest_id    = str(uuid.uuid4())
    sub_deliv_id   = str(uuid.uuid4())
    sub_aluguel_id = str(uuid.uuid4())
    sub_luz_id     = str(uuid.uuid4())
    sub_agua_id    = str(uuid.uuid4())
    sub_net_id     = str(uuid.uuid4())
    sub_gas_id     = str(uuid.uuid4())
    sub_uber_id    = str(uuid.uuid4())
    sub_manut_id   = str(uuid.uuid4())
    sub_cinema_id  = str(uuid.uuid4())
    sub_stream_id  = str(uuid.uuid4())
    sub_farm_id    = str(uuid.uuid4())
    sub_acad_id    = str(uuid.uuid4())
    sub_curso_id   = str(uuid.uuid4())
    sub_sal_carlos = str(uuid.uuid4())
    sub_sal_marina = str(uuid.uuid4())
    sub_free_id    = str(uuid.uuid4())
    sub_reserva_id = str(uuid.uuid4())
    sub_cdi_id     = str(uuid.uuid4())

    subcategorias_data = [
        {"id": sub_mercado_id, "categoria_id": cat_alim_id,  "user_id": uid, "nome": "Supermercado",          "cor": "#F59E0B", "ativo": True},
        {"id": sub_rest_id,    "categoria_id": cat_alim_id,  "user_id": uid, "nome": "Restaurantes & Bares",  "cor": "#F59E0B", "ativo": True},
        {"id": sub_deliv_id,   "categoria_id": cat_alim_id,  "user_id": uid, "nome": "Delivery & Lanches",    "cor": "#F59E0B", "ativo": True},
        {"id": sub_aluguel_id, "categoria_id": cat_mora_id,  "user_id": uid, "nome": "Aluguel & Condomínio",  "cor": "#3B82F6", "ativo": True},
        {"id": sub_luz_id,     "categoria_id": cat_mora_id,  "user_id": uid, "nome": "Energia Elétrica",      "cor": "#3B82F6", "ativo": True},
        {"id": sub_agua_id,    "categoria_id": cat_mora_id,  "user_id": uid, "nome": "Água & Saneamento",     "cor": "#3B82F6", "ativo": True},
        {"id": sub_net_id,     "categoria_id": cat_mora_id,  "user_id": uid, "nome": "Internet Fibra",        "cor": "#3B82F6", "ativo": True},
        {"id": sub_gas_id,     "categoria_id": cat_trans_id, "user_id": uid, "nome": "Combustível",           "cor": "#6366F1", "ativo": True},
        {"id": sub_uber_id,    "categoria_id": cat_trans_id, "user_id": uid, "nome": "Uber / Aplicativos",    "cor": "#6366F1", "ativo": True},
        {"id": sub_manut_id,   "categoria_id": cat_trans_id, "user_id": uid, "nome": "Manutenção do Carro",   "cor": "#6366F1", "ativo": True},
        {"id": sub_cinema_id,  "categoria_id": cat_lazer_id, "user_id": uid, "nome": "Cinema & Passeios",     "cor": "#EC4899", "ativo": True},
        {"id": sub_stream_id,  "categoria_id": cat_lazer_id, "user_id": uid, "nome": "Streaming (Netflix)",   "cor": "#EC4899", "ativo": True},
        {"id": sub_farm_id,    "categoria_id": cat_saude_id, "user_id": uid, "nome": "Farmácia & Saúde",      "cor": "#EF4444", "ativo": True},
        {"id": sub_acad_id,    "categoria_id": cat_saude_id, "user_id": uid, "nome": "Academia",              "cor": "#EF4444", "ativo": True},
        {"id": sub_curso_id,   "categoria_id": cat_educ_id,  "user_id": uid, "nome": "Cursos & Livros",       "cor": "#8B5CF6", "ativo": True},
        {"id": sub_sal_carlos, "categoria_id": cat_sal_id,   "user_id": uid, "nome": "Salário Carlos (CLT)",  "cor": "#10B981", "ativo": True},
        {"id": sub_sal_marina, "categoria_id": cat_sal_id,   "user_id": uid, "nome": "Salário Marina (CLT)",  "cor": "#10B981", "ativo": True},
        {"id": sub_free_id,    "categoria_id": cat_sal_id,   "user_id": uid, "nome": "Freelance & Renda Extra","cor": "#10B981", "ativo": True},
        {"id": sub_reserva_id, "categoria_id": cat_inv_id,   "user_id": uid, "nome": "Reserva de Emergência", "cor": "#14B8A6", "ativo": True},
        {"id": sub_cdi_id,     "categoria_id": cat_inv_id,   "user_id": uid, "nome": "Renda Fixa 102% CDI",   "cor": "#14B8A6", "ativo": True},
    ]
    supabase.table("subcategorias").insert(subcategorias_data).execute()

    # 8. Caixinhas de Teto
    log("Criando Caixinhas de Teto com Provisões...")
    cx_aluguel = str(uuid.uuid4())
    cx_mercado = str(uuid.uuid4())
    cx_carro   = str(uuid.uuid4())

    caixinhas_data = [
        {
            "id": cx_aluguel,
            "user_id": uid,
            "membro_id": carlos_id,
            "nome": "Aluguel & Condomínio",
            "valor_meta": 2200.00,
            "saldo_atual": 2200.00,
            "data_provisao": data_relativa(hoje, 0, 10).isoformat(),
            "data_alvo": data_relativa(hoje, 0, 10).isoformat(),
            "cor": "#3B82F6",
            "icone": "home",
            "categoria_id": cat_mora_id,
            "subcategoria_id": sub_aluguel_id,
            "pote_id": pote_fixo,
            "conta_id": cta_nu_carlos,
            "tipo_provisao": "despesa",
            "recorrente": True,
            "dia_recorrencia": 10,
            "ativo": True,
        },
        {
            "id": cx_mercado,
            "user_id": uid,
            "membro_id": marina_id,
            "nome": "Supermercado Mensal",
            "valor_meta": 1800.00,
            "saldo_atual": 1800.00,
            "data_provisao": data_relativa(hoje, 0, 5).isoformat(),
            "data_alvo": data_relativa(hoje, 0, 5).isoformat(),
            "cor": "#F59E0B",
            "icone": "shopping_cart",
            "categoria_id": cat_alim_id,
            "subcategoria_id": sub_mercado_id,
            "pote_id": pote_fixo,
            "conta_id": cta_in_marina,
            "tipo_provisao": "despesa",
            "recorrente": True,
            "dia_recorrencia": 5,
            "ativo": True,
        },
        {
            "id": cx_carro,
            "user_id": uid,
            "membro_id": carlos_id,
            "nome": "Manutenção & Seguro Carro",
            "valor_meta": 3000.00,
            "saldo_atual": 1800.00,
            "data_provisao": data_relativa(hoje, 0, 15).isoformat(),
            "data_alvo": data_relativa(hoje, 2, 15).isoformat(),
            "cor": "#6366F1",
            "icone": "directions_car",
            "categoria_id": cat_trans_id,
            "subcategoria_id": sub_manut_id,
            "pote_id": pote_semi,
            "conta_id": cta_nu_carlos,
            "tipo_provisao": "despesa",
            "recorrente": True,
            "dia_recorrencia": 15,
            "ativo": True,
        },
    ]
    supabase.table("caixinhas_teto").insert(caixinhas_data).execute()

    # 9. Configurar Módulo "Meu Cofre" (Investimentos e Patrimônio)
    log("Configurando Módulo Meu Cofre (Porquinho e CDI 102%)...")
    cofre_reserva_id = str(uuid.uuid4())
    cofre_cdi_id     = str(uuid.uuid4())

    supabase.table("cofres_config").upsert({
        "user_id": uid,
        "taxa_cdi_anual": 10.75,
    }).execute()

    # Cofres
    supabase.table("cofres_investimento").insert([
        {
            "id": cofre_reserva_id,
            "user_id": uid,
            "nome": "Porquinho (Reserva de Emergência)",
            "tipo": "reserva_emergencia",
            "cor": "#10B981",
            "icone": "savings",
            "meta_valor": 30000.00,
            "percentual_cdi": 100.00,
            "saldo_atual": 0.0,
            "total_aportado": 0.0,
            "total_rendimentos": 0.0,
            "total_resgatado": 0.0,
            "ordem": 1,
            "ativo": True,
        },
        {
            "id": cofre_cdi_id,
            "user_id": uid,
            "nome": "Renda Fixa (102% CDI)",
            "tipo": "renda_fixa",
            "cor": "#00E676",
            "icone": "trending_up",
            "meta_valor": 50000.00,
            "percentual_cdi": 102.00,
            "saldo_atual": 0.0,
            "total_aportado": 0.0,
            "total_rendimentos": 0.0,
            "total_resgatado": 0.0,
            "ordem": 2,
            "ativo": True,
        },
    ]).execute()

    # 10. Gerar Lançamentos com Narrativa dos 15 Meses (-12 a +2)
    log("Gerando narrativa financeira completa de 15 meses...")
    lancamentos: list[dict] = []
    cofres_movs: list[dict] = []

    # Estado acumulado dos cofres
    saldo_reserva = 0.0
    tot_aport_reserva = 0.0
    tot_rend_reserva = 0.0
    tot_resg_reserva = 0.0

    saldo_cdi = 0.0
    tot_aport_cdi = 0.0
    tot_rend_cdi = 0.0

    # Compras Parceladas: Séries
    serie_notebook = str(uuid.uuid4())   # Notebook Dell XPS: 10x 380.00 no Nubank Carlos (iniciado em M-4)
    serie_geladeira = str(uuid.uuid4())  # Geladeira Brastemp: 8x 420.00 no Inter Marina (iniciado em M-2)

    for delta in range(-12, 3):
        ano_m, mes_m = somar_meses(hoje.year, hoje.month, delta)
        fatura_str = f"{mes_m:02d}/{ano_m}"
        fid_nu = fat_map_nu[(ano_m, mes_m)]
        fid_in = fat_map_in[(ano_m, mes_m)]

        def dt(dia: int) -> str:
            return data_relativa(hoje, delta, dia).isoformat()

        def status_para(dia: int) -> str:
            if delta < 0:
                return "Pago"
            elif delta > 0:
                return "Pendente"
            else:
                # Mês atual: pago se dia <= hoje.day
                return "Pago" if dia <= hoje.day else "Pendente"

        # --- A. RECEITAS BÁSICAS DA FAMÍLIA (Dia 05) ---
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
            "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix",
            "conta_id": cta_nu_carlos, "categoria_id": cat_sal_id, "subcategoria_id": sub_sal_carlos,
            "valor": 6200.00, "data": dt(5), "descricao": f"Salário Carlos CLT ({fatura_str})",
            "status": status_para(5), "pote_id": pote_fixo,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
            "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix",
            "conta_id": cta_in_marina, "categoria_id": cat_sal_id, "subcategoria_id": sub_sal_marina,
            "valor": 4300.00, "data": dt(5), "descricao": f"Salário Marina CLT ({fatura_str})",
            "status": status_para(5), "pote_id": pote_fixo,
        })

        # --- B. CUSTOS FIXOS ESSENCIAIS MENSAIS ---
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
            "conta_id": cta_nu_carlos, "categoria_id": cat_mora_id, "subcategoria_id": sub_aluguel_id,
            "valor": 2200.00, "data": dt(10), "descricao": "Aluguel & Condomínio Apartamento",
            "status": status_para(10), "regra": "Essencial", "pote_id": pote_fixo, "caixinha_id": cx_aluguel,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
            "conta_id": cta_nu_carlos, "categoria_id": cat_mora_id, "subcategoria_id": sub_net_id,
            "valor": 139.90, "data": dt(15), "descricao": "Internet Fibra Residencial",
            "status": status_para(15), "regra": "Essencial", "pote_id": pote_fixo,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
            "conta_id": cta_in_marina, "categoria_id": cat_mora_id, "subcategoria_id": sub_luz_id,
            "valor": 235.00, "data": dt(12), "descricao": "Energia Elétrica (Enel)",
            "status": status_para(12), "regra": "Essencial", "pote_id": pote_fixo,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
            "conta_id": cta_in_marina, "categoria_id": cat_mora_id, "subcategoria_id": sub_agua_id,
            "valor": 88.50, "data": dt(14), "descricao": "Água & Saneamento (Sabesp)",
            "status": status_para(14), "regra": "Essencial", "pote_id": pote_fixo,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
            "conta_id": cta_in_marina, "categoria_id": cat_alim_id, "subcategoria_id": sub_mercado_id,
            "valor": 850.00, "data": dt(6), "descricao": "Supermercado - Compra Quinzena 1",
            "status": status_para(6), "regra": "Essencial", "pote_id": pote_fixo, "caixinha_id": cx_mercado,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
            "conta_id": cta_in_marina, "categoria_id": cat_alim_id, "subcategoria_id": sub_mercado_id,
            "valor": 920.00, "data": dt(20), "descricao": "Supermercado - Compra Quinzena 2",
            "status": status_para(20), "regra": "Essencial", "pote_id": pote_fixo, "caixinha_id": cx_mercado,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
            "conta_id": cta_nu_carlos, "categoria_id": cat_trans_id, "subcategoria_id": sub_gas_id,
            "valor": 380.00, "data": dt(11), "descricao": "Gasolina Mensal Carro",
            "status": status_para(11), "regra": "Essencial", "pote_id": pote_semi,
        })

        # Assinaturas no Cartão
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito",
            "cartao_id": card_nu_carlos, "fatura_id": fid_nu, "fatura": fatura_str,
            "categoria_id": cat_lazer_id, "subcategoria_id": sub_stream_id,
            "valor": 89.90, "data": dt(4), "descricao": "Streaming Netflix + Spotify Família",
            "status": status_para(27), "regra": "Estilo de Vida", "pote_id": pote_praz,
        })
        lancamentos.append({
            "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
            "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito",
            "cartao_id": card_in_marina, "fatura_id": fid_in, "fatura": fatura_str,
            "categoria_id": cat_saude_id, "subcategoria_id": sub_acad_id,
            "valor": 220.00, "data": dt(7), "descricao": "Mensalidade Academia Casal",
            "status": status_para(17), "regra": "Essencial", "pote_id": pote_semi,
        })

        # --- C. COMPRAS PARCELADAS EM CASCATA ---
        # Notebook Dell XPS: 10x 380.00 (iniciado em M-4)
        if delta >= -4:
            parcela_nb = delta - (-4) + 1
            if 1 <= parcela_nb <= 10:
                lancamentos.append({
                    "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                    "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito",
                    "cartao_id": card_nu_carlos, "fatura_id": fid_nu, "fatura": fatura_str,
                    "serie_id": serie_notebook, "parcela_atual": parcela_nb, "total_parcelas": 10,
                    "categoria_id": cat_educ_id, "subcategoria_id": sub_curso_id,
                    "valor": 380.00, "data": dt(27), "descricao": f"Notebook Dell XPS Trabalho ({parcela_nb}/10)",
                    "status": status_para(27), "regra": "Investimento", "pote_id": pote_conh,
                })

        # Geladeira Brastemp: 8x 420.00 (iniciada em M-2)
        if delta >= -2:
            parcela_gel = delta - (-2) + 1
            if 1 <= parcela_gel <= 8:
                lancamentos.append({
                    "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                    "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito",
                    "cartao_id": card_in_marina, "fatura_id": fid_in, "fatura": fatura_str,
                    "serie_id": serie_geladeira, "parcela_atual": parcela_gel, "total_parcelas": 8,
                    "categoria_id": cat_mora_id, "subcategoria_id": sub_aluguel_id,
                    "valor": 420.00, "data": dt(17), "descricao": f"Geladeira Frost Free Brastemp ({parcela_gel}/8)",
                    "status": status_para(17), "regra": "Essencial", "pote_id": pote_fixo,
                })

        # --- D. NARRATIVA ESPECÍFICA DO MÊS ---
        if delta in (-12, -11):
            # MESES 1-2: VERMELHO FORTE (Faturas estouradas, compras sem controle, rombo)
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito",
                "cartao_id": card_nu_carlos, "fatura_id": fid_nu, "fatura": fatura_str,
                "categoria_id": cat_lazer_id, "subcategoria_id": sub_cinema_id,
                "valor": 2800.00 if delta == -12 else 2400.00, "data": dt(12),
                "descricao": "Viagem Fim de Semana & Resort (Impulso)",
                "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Credito",
                "cartao_id": card_in_marina, "fatura_id": fid_in, "fatura": fatura_str,
                "categoria_id": cat_lazer_id, "subcategoria_id": sub_rest_id,
                "valor": 1900.00 if delta == -12 else 1700.00, "data": dt(16),
                "descricao": "Compras Shopping & Roupas de Grife",
                "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_nu_carlos, "categoria_id": cat_alim_id, "subcategoria_id": sub_deliv_id,
                "valor": 850.00, "data": dt(18), "descricao": "Deliveries & Restaurantes Caros (iFood)",
                "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz,
            })

        elif delta in (-10, -9):
            # MESES 3-4: AMARELO / VERDE FRACO (Corte de excessos, sobra de 2% a 4%)
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_nu_carlos, "categoria_id": cat_alim_id, "subcategoria_id": sub_rest_id,
                "valor": 320.00, "data": dt(19), "descricao": "Jantar Moderado de Fim de Semana",
                "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_in_marina, "categoria_id": cat_saude_id, "subcategoria_id": sub_farm_id,
                "valor": 180.00, "data": dt(22), "descricao": "Farmácia & Vitaminas",
                "status": "Pago", "regra": "Essencial", "pote_id": pote_semi,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
                "conta_id": cta_nu_carlos, "categoria_id": cat_trans_id, "subcategoria_id": sub_uber_id,
                "valor": 140.00, "data": dt(24), "descricao": "Uber Trabalho",
                "status": "Pago", "regra": "Essencial", "pote_id": pote_semi,
            })
            # Aporte simbólico inicial na reserva (R$ 200)
            val_ap = 200.00
            ant_res = saldo_reserva
            saldo_reserva += val_ap
            tot_aport_reserva += val_ap
            cofres_movs.append({
                "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                "tipo": "aporte", "valor": val_ap, "saldo_anterior": ant_res,
                "saldo_posterior": saldo_reserva, "descricao": "Início da Reserva de Emergência",
                "data": dt(28), "conta_origem_id": cta_nu_carlos,
            })

        elif delta in (-8, -7, -6, -5):
            # MESES 5-8: VERDE CONSISTENTE (Sobra saudável de 20% a 28%, aportes regulares)
            if delta == -6:
                # Freelance de Carlos no mês 7
                lancamentos.append({
                    "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                    "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix",
                    "conta_id": cta_nu_carlos, "categoria_id": cat_sal_id, "subcategoria_id": sub_free_id,
                    "valor": 1500.00, "data": dt(16), "descricao": "Projeto Freelance Consultoria Web",
                    "status": "Pago", "pote_id": pote_lib,
                })

            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_nu_carlos, "categoria_id": cat_lazer_id, "subcategoria_id": sub_cinema_id,
                "valor": 240.00, "data": dt(15), "descricao": "Passeio em Família & Cinema",
                "status": "Pago", "regra": "Estilo de Vida", "pote_id": pote_praz,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_in_marina, "categoria_id": cat_saude_id, "subcategoria_id": sub_farm_id,
                "valor": 120.00, "data": dt(21), "descricao": "Medicamentos de Rotina",
                "status": "Pago", "regra": "Essencial", "pote_id": pote_semi,
            })

            # Aportes Regulares no Porquinho e no CDI
            val_ap_res = 1400.00 if delta == -6 else 1200.00
            ant_res = saldo_reserva
            saldo_reserva += val_ap_res
            tot_aport_reserva += val_ap_res
            cofres_movs.append({
                "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                "tipo": "aporte", "valor": val_ap_res, "saldo_anterior": ant_res,
                "saldo_posterior": saldo_reserva, "descricao": f"Aporte Mensal Reserva ({fatura_str})",
                "data": dt(10), "conta_origem_id": cta_nu_carlos,
            })

            val_ap_cdi = 800.00
            ant_cdi = saldo_cdi
            saldo_cdi += val_ap_cdi
            tot_aport_cdi += val_ap_cdi
            cofres_movs.append({
                "id": str(uuid.uuid4()), "cofre_id": cofre_cdi_id, "user_id": uid,
                "tipo": "aporte", "valor": val_ap_cdi, "saldo_anterior": ant_cdi,
                "saldo_posterior": saldo_cdi, "descricao": f"Aporte Mensal 102% CDI ({fatura_str})",
                "data": dt(10), "conta_origem_id": cta_in_marina,
            })

            # Rendimentos mensais
            rend_res = round(saldo_reserva * 0.0085, 2)
            if rend_res > 0:
                ant_res = saldo_reserva
                saldo_reserva += rend_res
                tot_rend_reserva += rend_res
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                    "tipo": "rendimento", "valor": rend_res, "saldo_anterior": ant_res,
                    "saldo_posterior": saldo_reserva, "descricao": f"Rendimento CDI Reserva ({fatura_str})",
                    "data": dt(28),
                })

            rend_cdi = round(saldo_cdi * 0.0087, 2)
            if rend_cdi > 0:
                ant_cdi = saldo_cdi
                saldo_cdi += rend_cdi
                tot_rend_cdi += rend_cdi
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_cdi_id, "user_id": uid,
                    "tipo": "rendimento", "valor": rend_cdi, "saldo_anterior": ant_cdi,
                    "saldo_posterior": saldo_cdi, "descricao": f"Rendimento 102% CDI ({fatura_str})",
                    "data": dt(28),
                })

        elif delta == -4:
            # MÊS 9: VERMELHO POR IMPREVISTO - O TESTE DA RESERVA!
            # Despesas pontuais gigantes: conserto do carro + tratamento de saúde
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
                "conta_id": cta_nu_carlos, "categoria_id": cat_trans_id, "subcategoria_id": sub_manut_id,
                "valor": 3200.00, "data": dt(14), "descricao": "Quebra do Cabeçote e Radiador do Carro (Oficina)",
                "status": "Pago", "regra": "Essencial", "pote_id": pote_semi, "caixinha_id": cx_carro,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
                "conta_id": cta_in_marina, "categoria_id": cat_saude_id, "subcategoria_id": sub_farm_id,
                "valor": 1600.00, "data": dt(18), "descricao": "Cirurgia Odontológica de Urgência Marina",
                "status": "Pago", "regra": "Essencial", "pote_id": pote_semi,
            })

            # MOMENTO HERÓICO: Resgate de R$ 4.000 da Reserva de Emergência para cobrir o rombo!
            val_resgate = 4000.00
            ant_res = saldo_reserva
            saldo_reserva = max(0.0, saldo_reserva - val_resgate)
            tot_resg_reserva += val_resgate
            cofres_movs.append({
                "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                "tipo": "resgate", "valor": val_resgate, "saldo_anterior": ant_res,
                "saldo_posterior": saldo_reserva,
                "descricao": "Resgate Emergencial — Conserto do Carro e Cirurgia Odontológica",
                "data": dt(15), "conta_origem_id": cta_nu_carlos,
            })

            # Lançamento do Resgate como entrada/transferência na conta corrente
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Receita", "subtipo": "Transferência", "forma_movimentacao": "Pix",
                "conta_id": cta_nu_carlos, "categoria_id": cat_inv_id, "subcategoria_id": sub_reserva_id,
                "valor": val_resgate, "data": dt(15),
                "descricao": "Resgate Cobertura Meu Cofre (Porquinho)",
                "status": "Pago", "pote_id": pote_fixo,
            })

        elif delta in (-3, -2, -1):
            # MESES 10-12: RECUPERAÇÃO E 13º SALÁRIO (Sobra de até 40%!)
            if delta == -2:
                # 13º Salário de Carlos e Marina (Mega Sobra!)
                lancamentos.append({
                    "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                    "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix",
                    "conta_id": cta_nu_carlos, "categoria_id": cat_sal_id, "subcategoria_id": sub_sal_carlos,
                    "valor": 6200.00, "data": dt(15), "descricao": "13º Salário Carlos CLT",
                    "status": "Pago", "pote_id": pote_lib,
                })
                lancamentos.append({
                    "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                    "tipo": "Receita", "subtipo": "Receita", "forma_movimentacao": "Pix",
                    "conta_id": cta_in_marina, "categoria_id": cat_sal_id, "subcategoria_id": sub_sal_marina,
                    "valor": 4300.00, "data": dt(15), "descricao": "13º Salário Marina CLT",
                    "status": "Pago", "pote_id": pote_lib,
                })

                # Mega Aporte de Reposição da Reserva e Aporte no CDI
                val_rep = 4000.00
                ant_res = saldo_reserva
                saldo_reserva += val_rep
                tot_aport_reserva += val_rep
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                    "tipo": "aporte", "valor": val_rep, "saldo_anterior": ant_res,
                    "saldo_posterior": saldo_reserva,
                    "descricao": "Reposição Integral da Reserva de Emergência (13º)",
                    "data": dt(20), "conta_origem_id": cta_nu_carlos,
                })

                val_inv_cdi = 4500.00
                ant_cdi = saldo_cdi
                saldo_cdi += val_inv_cdi
                tot_aport_cdi += val_inv_cdi
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_cdi_id, "user_id": uid,
                    "tipo": "aporte", "valor": val_inv_cdi, "saldo_anterior": ant_cdi,
                    "saldo_posterior": saldo_cdi,
                    "descricao": "Aporte Estratégico Renda Fixa 102% CDI (13º)",
                    "data": dt(20), "conta_origem_id": cta_in_marina,
                })

            else:
                # Aportes normais de recuperação
                val_ap_res = 1500.00
                ant_res = saldo_reserva
                saldo_reserva += val_ap_res
                tot_aport_reserva += val_ap_res
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                    "tipo": "aporte", "valor": val_ap_res, "saldo_anterior": ant_res,
                    "saldo_posterior": saldo_reserva, "descricao": f"Aporte Reserva ({fatura_str})",
                    "data": dt(10), "conta_origem_id": cta_nu_carlos,
                })

                val_ap_cdi = 1000.00
                ant_cdi = saldo_cdi
                saldo_cdi += val_ap_cdi
                tot_aport_cdi += val_ap_cdi
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_cdi_id, "user_id": uid,
                    "tipo": "aporte", "valor": val_ap_cdi, "saldo_anterior": ant_cdi,
                    "saldo_posterior": saldo_cdi, "descricao": f"Aporte 102% CDI ({fatura_str})",
                    "data": dt(10), "conta_origem_id": cta_in_marina,
                })

            # Rendimentos
            rend_res = round(saldo_reserva * 0.0085, 2)
            if rend_res > 0:
                ant_res = saldo_reserva
                saldo_reserva += rend_res
                tot_rend_reserva += rend_res
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                    "tipo": "rendimento", "valor": rend_res, "saldo_anterior": ant_res,
                    "saldo_posterior": saldo_reserva, "descricao": f"Rendimento CDI Reserva ({fatura_str})",
                    "data": dt(28),
                })

            rend_cdi = round(saldo_cdi * 0.0087, 2)
            if rend_cdi > 0:
                ant_cdi = saldo_cdi
                saldo_cdi += rend_cdi
                tot_rend_cdi += rend_cdi
                cofres_movs.append({
                    "id": str(uuid.uuid4()), "cofre_id": cofre_cdi_id, "user_id": uid,
                    "tipo": "rendimento", "valor": rend_cdi, "saldo_anterior": ant_cdi,
                    "saldo_posterior": saldo_cdi, "descricao": f"Rendimento 102% CDI ({fatura_str})",
                    "data": dt(28),
                })

        elif delta == 0:
            # MÊS ATUAL: Parcialmente preenchido
            # 1 despesa com dia anterior ao de hoje marcada como "Pendente" para simular conta em atraso!
            dia_atraso = max(1, hoje.day - 3) if hoje.day > 3 else 1
            status_atraso = "Pendente"  # Vencida mas ainda pendente!

            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Pix",
                "conta_id": cta_nu_carlos, "categoria_id": cat_saude_id, "subcategoria_id": sub_farm_id,
                "valor": 78.50, "data": dt(dia_atraso),
                "descricao": "Medicamentos Farmácia (Vencida/Atrasada)",
                "status": status_atraso, "regra": "Essencial", "pote_id": pote_semi,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_in_marina, "categoria_id": cat_alim_id, "subcategoria_id": sub_deliv_id,
                "valor": 95.00, "data": dt(min(hoje.day, 22)),
                "descricao": "Jantar Comemoração Conquista Pessoal",
                "status": status_para(min(hoje.day, 22)), "regra": "Estilo de Vida", "pote_id": pote_praz,
            })

            # Aporte mês atual
            val_ap_res = 1200.00
            ant_res = saldo_reserva
            saldo_reserva += val_ap_res
            tot_aport_reserva += val_ap_res
            cofres_movs.append({
                "id": str(uuid.uuid4()), "cofre_id": cofre_reserva_id, "user_id": uid,
                "tipo": "aporte", "valor": val_ap_res, "saldo_anterior": ant_res,
                "saldo_posterior": saldo_reserva, "descricao": f"Aporte Reserva ({fatura_str})",
                "data": dt(5), "conta_origem_id": cta_nu_carlos,
            })

        elif delta in (1, 2):
            # 2 MESES FUTUROS: Contas programadas para o Calendário e Projeção
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": carlos_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_nu_carlos, "categoria_id": cat_trans_id, "subcategoria_id": sub_gas_id,
                "valor": 380.00, "data": dt(12), "descricao": "Gasolina Prevista Carro",
                "status": "Pendente", "regra": "Essencial", "pote_id": pote_semi,
            })
            lancamentos.append({
                "perfil_id": uid, "user_id": uid, "membro_id": marina_id,
                "tipo": "Despesa", "subtipo": "Despesa", "forma_movimentacao": "Debito",
                "conta_id": cta_in_marina, "categoria_id": cat_lazer_id, "subcategoria_id": sub_cinema_id,
                "valor": 150.00, "data": dt(19), "descricao": "Passeio Programado Teatro/Cinema",
                "status": "Pendente", "regra": "Estilo de Vida", "pote_id": pote_praz,
            })

    # Inserir em lotes no Supabase para não exceder limites de payload
    log(f"Inserindo {len(lancamentos)} lançamentos financeiros no banco de dados...")
    batch_size = 80
    for i in range(0, len(lancamentos), batch_size):
        chunk = lancamentos[i : i + batch_size]
        supabase.table("lancamentos").insert(chunk).execute()

    # Inserir movimentações dos cofres
    log(f"Inserindo {len(cofres_movs)} movimentações históricas no Meu Cofre...")
    for i in range(0, len(cofres_movs), batch_size):
        chunk = cofres_movs[i : i + batch_size]
        supabase.table("cofres_movimentacoes").insert(chunk).execute()

    # Atualizar saldos consolidados dos cofres
    supabase.table("cofres_investimento").update({
        "saldo_atual": round(saldo_reserva, 2),
        "total_aportado": round(tot_aport_reserva, 2),
        "total_rendimentos": round(tot_rend_reserva, 2),
        "total_resgatado": round(tot_resg_reserva, 2),
    }).eq("id", cofre_reserva_id).execute()

    supabase.table("cofres_investimento").update({
        "saldo_atual": round(saldo_cdi, 2),
        "total_aportado": round(tot_aport_cdi, 2),
        "total_rendimentos": round(tot_rend_cdi, 2),
        "total_resgatado": 0.0,
    }).eq("id", cofre_cdi_id).execute()

    # 11. Recalcular Saldos, Faturas e Limites no PostgreSQL
    log("Recalculando saldos, faturas e limites no PostgreSQL...")
    try:
        supabase.rpc("fn_recalcular_saldos_usuario", {"p_user_id": uid}).execute()
    except Exception as ex:
        print(f"  (Aviso) fn_recalcular_saldos_usuario: {ex}")

    try:
        todas_fats = list(fat_map_nu.values()) + list(fat_map_in.values())
        supabase.rpc("fn_recalcular_totais_faturas", {"p_faturas_ids": todas_fats}).execute()
    except Exception as ex:
        print(f"  (Aviso) fn_recalcular_totais_faturas: {ex}")

    # Limpar caches em memória
    invalidar_cache(f"cofres_investimento_{uid}")
    invalidar_cache(f"contas_{uid}")
    invalidar_cache(f"cartoes_{uid}")
    invalidar_cache(f"membros_{uid}")

    resumo = {
        "sucesso": True,
        "usuario": user_email,
        "uid": uid,
        "total_lancamentos": len(lancamentos),
        "total_faturas": len(faturas_data),
        "total_movimentacoes_cofre": len(cofres_movs),
        "saldo_reserva": round(saldo_reserva, 2),
        "saldo_cdi": round(saldo_cdi, 2),
        "patrimonio_total": round(saldo_reserva + saldo_cdi, 2),
        "membros": ["Carlos (Principal)", "Marina (Esposa)"],
        "contas": ["Nubank Carlos", "Banco Inter Marina", "Carteira Física"],
        "cartoes": ["Nubank Ultravioleta", "Inter Mastercard Black"],
    }
    log("Perfil Vitrine populado com 100% de sucesso!")
    return resumo


def resetar_perfil_vitrine(
    uid: Optional[str] = None,
    status_cb: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Limpa completamente o perfil demo, deixando-o zerado.
    """
    def log(msg: str):
        if status_cb:
            status_cb(msg)

    u = usuario_atual()
    user_email = u.email if u and u.email else DEMO_USER_EMAIL

    if not uid:
        if u and u.id:
            uid = u.id
        else:
            auth_resp = fazer_login(DEMO_USER_EMAIL, "teste123")
            if not auth_resp or not auth_resp.user:
                raise RuntimeError("Falha ao autenticar o usuário demo (teste@dembase.com).")
            uid = auth_resp.user.id
            user_email = auth_resp.user.email or DEMO_USER_EMAIL

    validar_seguranca_demo(uid, user_email)
    log(f"Resetando perfil demo ({user_email})...")
    limpar_dados_demo(uid, status_cb=status_cb)

    invalidar_cache(f"cofres_investimento_{uid}")
    invalidar_cache(f"contas_{uid}")
    invalidar_cache(f"cartoes_{uid}")
    invalidar_cache(f"membros_{uid}")

    log("Perfil demo resetado e limpo com sucesso!")
    return {"sucesso": True, "uid": uid, "mensagem": "Perfil demo limpo com sucesso."}
