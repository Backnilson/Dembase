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
