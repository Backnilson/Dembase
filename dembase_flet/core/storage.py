"""
=============================================================================
DemBase v3 — core/storage.py (Flet 1.0.1 compatible)
Armazenamento seguro e resiliente de credenciais e sessão.
Substitui o antigo page.client_storage (que não existe no Flet 1.0.1)
utilizando SharedPreferences + fallback local persistente em JSON.
=============================================================================
"""
import os
import json
import asyncio
from pathlib import Path
from typing import Optional, Tuple
import flet as ft
from core.constants import session_set, session_get, session_clear, session_remove

# Diretório local seguro para fallback de persistência no computador do usuário
_LOCAL_DIR = Path.home() / ".dembase"
_LOCAL_FILE = _LOCAL_DIR / "auth_prefs.json"


def _ler_local_json() -> dict:
    try:
        if _LOCAL_FILE.exists():
            with open(_LOCAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _salvar_local_json(dados: dict) -> None:
    try:
        _LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        with open(_LOCAL_FILE, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _obter_sp(page: ft.Page) -> Optional[ft.SharedPreferences]:
    """Recupera ou registra a instância de SharedPreferences na página."""
    try:
        for s in getattr(page, "services", []):
            if isinstance(s, ft.SharedPreferences):
                return s
        sp = ft.SharedPreferences()
        page.services.append(sp)
        return sp
    except Exception:
        return None


async def salvar_lembrar(page: ft.Page, email: str, access_token: str = "", refresh_token: str = "") -> None:
    """
    Grava o e-mail e os tokens de autenticação quando 'Lembrar de mim' está ativado.
    NUNCA armazena a senha do usuário em texto.
    """
    dados = {
        "lembrar_ativo": True,
        "lembrar_email": email.strip(),
        "auth_access_token": access_token or "",
        "auth_refresh_token": refresh_token or "",
    }

    # 1. Tenta via SharedPreferences
    sp = _obter_sp(page)
    if sp:
        try:
            await sp.set("lembrar_ativo", True)
            await sp.set("lembrar_email", email.strip())
            if access_token:
                await sp.set("auth_access_token", access_token)
            if refresh_token:
                await sp.set("auth_refresh_token", refresh_token)
        except Exception:
            pass

    # 2. Persiste em fallback local (para confiabilidade no Desktop)
    _salvar_local_json(dados)

    # 3. Mantém também na sessão da memória em runtime
    session_set(page, "lembrar_ativo", True)
    session_set(page, "lembrar_email", email.strip())
    if access_token:
        session_set(page, "auth_access_token", access_token)
    if refresh_token:
        session_set(page, "auth_refresh_token", refresh_token)


async def carregar_lembrar(page: ft.Page) -> Tuple[str, str, str, bool]:
    """
    Retorna (email, access_token, refresh_token, lembrar_ativo).
    """
    email = ""
    acc = ""
    ref = ""
    ativo = False

    # 1. Tenta SharedPreferences
    sp = _obter_sp(page)
    if sp:
        try:
            ativo = bool(await sp.get("lembrar_ativo"))
            email = str(await sp.get("lembrar_email") or "")
            acc = str(await sp.get("auth_access_token") or "")
            ref = str(await sp.get("auth_refresh_token") or "")
        except Exception:
            pass

    # 2. Se vazio, consulta o fallback local
    if not email and not acc:
        local = _ler_local_json()
        if local.get("lembrar_ativo"):
            ativo = True
            email = local.get("lembrar_email", "")
            acc = local.get("auth_access_token", "")
            ref = local.get("auth_refresh_token", "")

    # 3. Se ainda vazio, consulta sessão em memória
    if not email:
        email = session_get(page, "lembrar_email", "")
    if not acc:
        acc = session_get(page, "auth_access_token", "")
    if not ref:
        ref = session_get(page, "auth_refresh_token", "")
    if not ativo:
        ativo = bool(session_get(page, "lembrar_ativo", False))

    return email, acc, ref, ativo


async def limpar_lembrar(page: ft.Page) -> None:
    """Limpa credenciais persistentes e arquivo local."""
    sp = _obter_sp(page)
    if sp:
        try:
            await sp.remove("lembrar_ativo")
            await sp.remove("lembrar_email")
            await sp.remove("auth_access_token")
            await sp.remove("auth_refresh_token")
        except Exception:
            pass

    try:
        if _LOCAL_FILE.exists():
            _LOCAL_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    session_remove(page, "lembrar_ativo")
    session_remove(page, "lembrar_email")
    session_remove(page, "auth_access_token")
    session_remove(page, "auth_refresh_token")


def salvar_sessao_temporaria(page: ft.Page, access_token: str, refresh_token: str) -> None:
    """Salva tokens apenas na sessão volátil do app (quando 'Lembrar de mim' não está marcado)."""
    session_set(page, "auth_access_token", access_token)
    session_set(page, "auth_refresh_token", refresh_token)


def obter_tokens_sessao(page: ft.Page) -> Tuple[str, str]:
    """Recupera tokens da sessão volátil."""
    acc = session_get(page, "auth_access_token", "") or ""
    ref = session_get(page, "auth_refresh_token", "") or ""
    return acc, ref


async def salvar_preferencia_tema(page: ft.Page, tema: str) -> None:
    """
    Salva a preferência de tema do usuário: 'system', 'dark' ou 'light'.
    Persiste em SharedPreferences e em arquivo local.
    """
    tema_valido = tema if tema in ("system", "dark", "light") else "system"
    sp = _obter_sp(page)
    if sp:
        try:
            await sp.set("preferencia_tema", tema_valido)
        except Exception:
            pass

    dados = _ler_local_json()
    dados["preferencia_tema"] = tema_valido
    _salvar_local_json(dados)

    session_set(page, "preferencia_tema", tema_valido)


async def carregar_preferencia_tema(page: ft.Page) -> str:
    """
    Recupera a preferência de tema ('system', 'dark' ou 'light').
    Retorna 'system' por padrão se não configurado.
    """
    sp = _obter_sp(page)
    if sp:
        try:
            val = await sp.get("preferencia_tema")
            if val in ("system", "dark", "light"):
                session_set(page, "preferencia_tema", val)
                return str(val)
        except Exception:
            pass

    local = _ler_local_json()
    val = local.get("preferencia_tema")
    if val in ("system", "dark", "light"):
        session_set(page, "preferencia_tema", val)
        return str(val)

    val_sess = session_get(page, "preferencia_tema")
    if val_sess in ("system", "dark", "light"):
        return str(val_sess)

    return "system"


def obter_preferencia_tema_memoria(page: ft.Page) -> str:
    """Retorna de forma síncrona a preferência atual da sessão ou arquivo local."""
    val = session_get(page, "preferencia_tema")
    if val in ("system", "dark", "light"):
        return str(val)
    local = _ler_local_json()
    return local.get("preferencia_tema", "system")


# =============================================================================
# PREFERÊNCIAS DE GRÁFICOS DO DASHBOARD
# =============================================================================
def obter_graficos_dashboard_memoria(page: ft.Page, padrao: list[str]) -> list[str]:
    """Retorna a lista ordenada de IDs de gráficos ativos para o Dashboard."""
    val_sess = session_get(page, "graficos_dashboard")
    if isinstance(val_sess, list) and val_sess:
        return list(val_sess)
    local = _ler_local_json()
    val_local = local.get("graficos_dashboard")
    if isinstance(val_local, list) and val_local:
        session_set(page, "graficos_dashboard", val_local)
        return list(val_local)
    return list(padrao)


def salvar_graficos_dashboard_sync(page: ft.Page, ids: list[str]) -> None:
    """Salva de forma síncrona a lista de IDs de gráficos ativos na sessão e em disco."""
    lista = list(ids)
    session_set(page, "graficos_dashboard", lista)
    dados = _ler_local_json()
    dados["graficos_dashboard"] = lista
    _salvar_local_json(dados)


async def salvar_graficos_dashboard(page: ft.Page, ids: list[str]) -> None:
    """Salva também no SharedPreferences quando disponível."""
    salvar_graficos_dashboard_sync(page, ids)
    sp = _obter_sp(page)
    if sp:
        try:
            await sp.set("graficos_dashboard", json.dumps(list(ids)))
        except Exception:
            pass


# =============================================================================
# ESTADO GLOBAL DO FILTRO DE PERÍODO FLEXÍVEL
# =============================================================================
def obter_dia_ciclo_padrao(page: ft.Page) -> int:
    """Retorna o dia inicial do ciclo financeiro personalizado (ex: dia 20)."""
    val = session_get(page, "dia_ciclo_financeiro")
    if isinstance(val, int) and 1 <= val <= 28:
        return val
    local = _ler_local_json()
    dia_local = local.get("dia_ciclo_financeiro")
    if isinstance(dia_local, int) and 1 <= dia_local <= 28:
        session_set(page, "dia_ciclo_financeiro", dia_local)
        return dia_local
    return 20


def salvar_dia_ciclo_padrao(page: ft.Page, dia: int) -> None:
    """Persiste o dia inicial do ciclo financeiro (1 a 28)."""
    d = max(1, min(28, int(dia)))
    session_set(page, "dia_ciclo_financeiro", d)
    dados = _ler_local_json()
    dados["dia_ciclo_financeiro"] = d
    _salvar_local_json(dados)



# =============================================================================
# PERSISTÊNCIA DE SESSÃO AUTENTICADA (MOBILE BACKGROUND E RESILIÊNCIA)
# =============================================================================
async def salvar_sessao_autenticada(page: ft.Page, access_token: str, refresh_token: str, email: str = "") -> None:
    """
    Grava os tokens da sessão autenticada ativa no SharedPreferences e fallback local.
    Permite reconexão invisível ao minimizar e restaurar o app no celular sem cair na tela de login.
    """
    if not access_token or not refresh_token:
        return

    dados = _ler_local_json()
    dados["auth_access_token"] = access_token
    dados["auth_refresh_token"] = refresh_token
    if email:
        dados["auth_email"] = email.strip()
    _salvar_local_json(dados)

    sp = _obter_sp(page)
    if sp:
        try:
            await sp.set("auth_access_token", access_token)
            await sp.set("auth_refresh_token", refresh_token)
            if email:
                await sp.set("auth_email", email.strip())
        except Exception:
            pass

    session_set(page, "auth_access_token", access_token)
    session_set(page, "auth_refresh_token", refresh_token)
    if email:
        session_set(page, "auth_email", email.strip())


def salvar_sessao_autenticada_sync(page: ft.Page, access_token: str, refresh_token: str, email: str = "") -> None:
    """Versão síncrona para gravação imediata em memória e disco local."""
    if not access_token or not refresh_token:
        return
    dados = _ler_local_json()
    dados["auth_access_token"] = access_token
    dados["auth_refresh_token"] = refresh_token
    if email:
        dados["auth_email"] = email.strip()
    _salvar_local_json(dados)

    session_set(page, "auth_access_token", access_token)
    session_set(page, "auth_refresh_token", refresh_token)
    if email:
        session_set(page, "auth_email", email.strip())


async def carregar_sessao_autenticada(page: ft.Page) -> Tuple[str, str, str]:
    """
    Recupera (access_token, refresh_token, email) persistidos.
    Consulta SharedPreferences, fallback local e sessão de runtime.
    """
    acc = ""
    ref = ""
    email = ""

    sp = _obter_sp(page)
    if sp:
        try:
            acc = str(await sp.get("auth_access_token") or "")
            ref = str(await sp.get("auth_refresh_token") or "")
            email = str(await sp.get("auth_email") or "")
        except Exception:
            pass

    if not acc or not ref:
        local = _ler_local_json()
        acc = local.get("auth_access_token", "") or acc
        ref = local.get("auth_refresh_token", "") or ref
        email = local.get("auth_email", "") or email

    if not acc or not ref:
        acc = session_get(page, "auth_access_token", "") or acc
        ref = session_get(page, "auth_refresh_token", "") or ref
        email = session_get(page, "auth_email", "") or email

    return acc, ref, email


def carregar_sessao_autenticada_sync(page: ft.Page) -> Tuple[str, str, str]:
    """Consulta síncrona imediata para uso no roteador e verificações de rota."""
    acc = session_get(page, "auth_access_token", "")
    ref = session_get(page, "auth_refresh_token", "")
    email = session_get(page, "auth_email", "")

    if not acc or not ref:
        local = _ler_local_json()
        acc = local.get("auth_access_token", "") or acc
        ref = local.get("auth_refresh_token", "") or ref
        email = local.get("auth_email", "") or email

    return acc, ref, email


async def limpar_sessao_autenticada(page: ft.Page) -> None:
    """Limpa tokens de sessão autenticada em todos os níveis (usado no logout explícito)."""
    sp = _obter_sp(page)
    if sp:
        try:
            await sp.remove("auth_access_token")
            await sp.remove("auth_refresh_token")
            await sp.remove("auth_email")
            await sp.remove("ultima_rota")
        except Exception:
            pass

    dados = _ler_local_json()
    dados.pop("auth_access_token", None)
    dados.pop("auth_refresh_token", None)
    dados.pop("auth_email", None)
    dados.pop("ultima_rota", None)
    _salvar_local_json(dados)

    session_remove(page, "auth_access_token")
    session_remove(page, "auth_refresh_token")
    session_remove(page, "auth_email")
    session_remove(page, "ultima_rota")


# =============================================================================
# RESTAURAÇÃO DA ÚLTIMA TELA / ROTA
# =============================================================================
def salvar_ultima_rota_sync(page: ft.Page, rota: str) -> None:
    """Salva a última rota ativa para restauração automática após backgrounding."""
    if not rota or str(rota).strip() in ("", "/auth", "auth", "/login", "login"):
        return
    r_limpa = str(rota).strip()
    session_set(page, "ultima_rota", r_limpa)
    dados = _ler_local_json()
    dados["ultima_rota"] = r_limpa
    _salvar_local_json(dados)


async def salvar_ultima_rota(page: ft.Page, rota: str) -> None:
    salvar_ultima_rota_sync(page, rota)
    if not rota or str(rota).strip() in ("", "/auth", "auth", "/login", "login"):
        return
    sp = _obter_sp(page)
    if sp:
        try:
            await sp.set("ultima_rota", str(rota).strip())
        except Exception:
            pass


async def carregar_ultima_rota(page: ft.Page) -> str:
    """Recupera a última tela visitada pelo usuário, com fallback para /dashboard."""
    sp = _obter_sp(page)
    if sp:
        try:
            val = await sp.get("ultima_rota")
            if val and str(val).strip() not in ("", "/auth", "auth", "/login", "login"):
                return str(val).strip()
        except Exception:
            pass

    local = _ler_local_json()
    val_local = local.get("ultima_rota")
    if val_local and str(val_local).strip() not in ("", "/auth", "auth", "/login", "login"):
        return str(val_local).strip()

    val_sess = session_get(page, "ultima_rota")
    if val_sess and str(val_sess).strip() not in ("", "/auth", "auth", "/login", "login"):
        return str(val_sess).strip()

    return "/dashboard"


def carregar_ultima_rota_sync(page: ft.Page) -> str:
    """Versão síncrona para recuperação da última rota."""
    local = _ler_local_json()
    val_local = local.get("ultima_rota")
    if val_local and str(val_local).strip() not in ("", "/auth", "auth", "/login", "login"):
        return str(val_local).strip()

    val_sess = session_get(page, "ultima_rota")
    if val_sess and str(val_sess).strip() not in ("", "/auth", "auth", "/login", "login"):
        return str(val_sess).strip()

    return "/dashboard"
