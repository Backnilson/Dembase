"""
=============================================================================
DemBase v3 — core/membro_state.py (Flet 1.0.1)
Gerenciamento centralizado do estado global de Visão Familiar ("Eu, Ela & Nós").
Fonte única da verdade para alternância de perfis (Denilson, Erika, Casa/Todos).
=============================================================================
"""
from __future__ import annotations

from typing import Optional
import flet as ft

from core.constants import session_get, session_set
import services.supabase_client as db


def obter_visao_membro_atual(page: ft.Page | None) -> dict:
    """
    Recupera (ou inicializa) o estado global da visão de membro na sessão.
    Retorno:
        {
            "modo": "casa" | "membro",
            "membro_id": str | None,
            "nome": str,
            "cor": str,
            "icone": str,
            "eh_casa": bool,
        }
    """
    if page is None:
        return {
            "modo": "casa",
            "membro_id": None,
            "nome": "Casa (Todos)",
            "cor": "#818CF8",
            "icone": "home",
            "eh_casa": True,
        }

    modo = session_get(page, "visao_membro_modo", "casa") or "casa"
    m_id = session_get(page, "visao_membro_id", None)
    nome = session_get(page, "visao_membro_nome", "Casa (Todos)")
    cor = session_get(page, "visao_membro_cor", "#818CF8")
    icone = session_get(page, "visao_membro_icone", "home")

    eh_casa = (modo == "casa" or not m_id)

    return {
        "modo": "casa" if eh_casa else "membro",
        "membro_id": None if eh_casa else str(m_id),
        "nome": "Casa (Todos)" if eh_casa else (nome or "Membro"),
        "cor": "#818CF8" if eh_casa else (cor or "#6366F1"),
        "icone": "home" if eh_casa else (icone or "person"),
        "eh_casa": eh_casa,
    }


def definir_visao_membro_atual(
    page: ft.Page | None,
    membro_id: Optional[str] = None,
    membro_info: Optional[dict] = None,
) -> dict:
    """
    Atualiza a visão ativa no PostgreSQL (definir_visao_membros) e na sessão do Flet.
    Se membro_id for None ou vazio: visão familiar consolidada (Casa/Todos).
    Se membro_id for UUID: visão restrita àquele membro.
    """
    eh_casa = not bool(membro_id)

    if eh_casa:
        modo = "casa"
        m_id = None
        nome = "Casa (Todos)"
        cor = "#818CF8"
        icone = "home"
    else:
        modo = "membro"
        m_id = str(membro_id)
        if membro_info:
            nome = membro_info.get("nome", "Membro")
            cor = membro_info.get("cor", "#6366F1")
            icone = membro_info.get("icone", "person")
        else:
            # Busca do cache de membros
            m_dados = db.obter_membro(m_id)
            if m_dados:
                nome = m_dados.get("nome", "Membro")
                cor = m_dados.get("cor", "#6366F1")
                icone = m_dados.get("icone", "person")
            else:
                nome = "Membro"
                cor = "#6366F1"
                icone = "person"

    if page is not None:
        session_set(page, "visao_membro_modo", modo)
        session_set(page, "visao_membro_id", m_id)
        session_set(page, "visao_membro_nome", nome)
        session_set(page, "visao_membro_cor", cor)
        session_set(page, "visao_membro_icone", icone)

    # Executa a RPC no Supabase para sincronizar a RLS e os cálculos em tempo real
    try:
        db.definir_visao_membros([m_id] if m_id else None)
    except Exception as ex:
        print(f"[MembroState] Aviso ao sincronizar visao no Supabase: {ex}")

    estado = {
        "modo": modo,
        "membro_id": m_id,
        "nome": nome,
        "cor": cor,
        "icone": icone,
        "eh_casa": eh_casa,
    }

    # Se a página possuir um listener global registrado para perfil, notifica
    fn_hook = getattr(page, "_shell_atualizar_visao_membro", None) if page else None
    if callable(fn_hook):
        try:
            fn_hook()
        except Exception:
            pass

    return estado


def obter_membro_ativo_id(page: ft.Page | None) -> Optional[str]:
    """Retorna o ID do membro ativo ou None se for visão Casa."""
    vis = obter_visao_membro_atual(page)
    return vis.get("membro_id") if not vis.get("eh_casa") else None


def obter_membro_padrao_para_lancamento(
    page: ft.Page | None,
    conta_id: Optional[str] = None,
    cartao_id: Optional[str] = None,
) -> Optional[str]:
    """
    Inteligência contextual de seleção de perfil para novos lançamentos:
    1. Se o cartão selecionado tem membro_id, retorna-o.
    2. Se a conta selecionada tem membro_id, retorna-o.
    3. Se houver um perfil ativo na tela (ex: Erika), retorna-o.
    4. Se for visão Casa, retorna o perfil principal (Denilson).
    """
    # 1. Cartão
    if cartao_id:
        try:
            cartoes = db.listar_cartoes()
            for c in cartoes:
                if str(c.get("id")) == str(cartao_id) and c.get("membro_id"):
                    return str(c["membro_id"])
        except Exception:
            pass

    # 2. Conta
    if conta_id:
        try:
            contas = db.listar_contas()
            for c in contas:
                if str(c.get("id")) == str(conta_id) and c.get("membro_id"):
                    return str(c["membro_id"])
        except Exception:
            pass

    # 3. Visão ativa na tela
    vis = obter_visao_membro_atual(page)
    if not vis.get("eh_casa") and vis.get("membro_id"):
        return str(vis["membro_id"])

    # 4. Membro principal padrão
    try:
        prin = db.obter_membro_principal()
        if prin and prin.get("id"):
            return str(prin["id"])
    except Exception:
        pass

    return None
