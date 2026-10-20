"""
=============================================================================
DemBase v3 — core/nav.py  (Flet 1.0.1)
Helpers tipados de navegação e construção segura de URLs com query string.
Usa page.navigate(rota) oficial do Flet 1.0.1 (nunca page.go).
=============================================================================
"""
from __future__ import annotations

from datetime import date
from urllib.parse import urlencode
import flet as ft

from core.periodo import obter_estado_periodo_atual
from core.report_context import ReportContext, regra_para_slug


def montar_url(path: str, params: dict | None = None) -> str:
    """Monta uma URL interna combinando path limpo e query string codificada."""
    clean_path = (path or "/").rstrip("/") or "/"
    if not params:
        return clean_path
    limpos = {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}
    if not limpos:
        return clean_path
    return f"{clean_path}?{urlencode(limpos)}"


def _periodo_base_query(page: ft.Page | None, ctx: ReportContext | None = None) -> dict[str, str]:
    if ctx is not None:
        return {
            "ini": ctx.data_inicio.isoformat(),
            "fim": ctx.data_fim.isoformat(),
        }
    est = obter_estado_periodo_atual(page)
    return {
        "ini": est["data_inicio"].isoformat(),
        "fim": est["data_fim"].isoformat(),
    }


def navegar(page: ft.Page, rota: str) -> None:
    """Wrapper seguro para page.navigate no Flet 1.0.1."""
    page.navigate(rota)


def voltar(page: ft.Page, rota_fallback: str = "/dashboard") -> None:
    """
    Desempilha a view atual e navega para a anterior na pilha de views do Flet 1.0.1.
    Se houver apenas 1 view na pilha, navega para rota_fallback.
    """
    views = getattr(page, "views", None)
    if views and len(views) > 1:
        views.pop()
        destino = getattr(views[-1], "route", None) or rota_fallback
        page.navigate(destino)
    else:
        page.navigate(rota_fallback)


def ir_dashboard(page: ft.Page) -> None:
    navegar(page, "/dashboard")


def ir_contas(page: ft.Page, ctx: ReportContext | None = None) -> None:
    q = _periodo_base_query(page, ctx)
    navegar(page, montar_url("/contas", q))


def ir_conta(
    page: ft.Page,
    conta_id: str,
    ctx: ReportContext | None = None,
    **filtros_extras,
) -> None:
    q = ctx.to_query() if ctx else _periodo_base_query(page, None)
    q.pop("conta", None)
    q.update({k: v for k, v in filtros_extras.items() if v is not None})
    navegar(page, montar_url(f"/contas/{conta_id}", q))


def ir_cartoes(page: ft.Page) -> None:
    navegar(page, "/cartoes")


def ir_cartao(
    page: ft.Page,
    cartao_id: str,
    ctx: ReportContext | None = None,
    fatura_id: str | None = None,
) -> None:
    q = ctx.to_query() if ctx else _periodo_base_query(page, None)
    q.pop("cartao", None)
    if fatura_id:
        q["fatura"] = str(fatura_id)
    navegar(page, montar_url(f"/cartoes/{cartao_id}", q))


def ir_hub_relatorios(page: ft.Page, ctx: ReportContext | None = None) -> None:
    q = _periodo_base_query(page, ctx)
    navegar(page, montar_url("/relatorios", q))


def ir_relatorio_lancamentos(
    page: ft.Page,
    tipo: str | None = None,
    ctx: ReportContext | None = None,
    origem: str | None = None,
    data_inicio: date | str | None = None,
    data_fim: date | str | None = None,
    **filtros,
) -> None:
    q = ctx.to_query() if ctx else _periodo_base_query(page, None)
    if data_inicio is not None:
        q["ini"] = data_inicio.isoformat() if isinstance(data_inicio, date) else str(data_inicio)[:10]
    if data_fim is not None:
        q["fim"] = data_fim.isoformat() if isinstance(data_fim, date) else str(data_fim)[:10]
    if tipo is not None:
        if str(tipo).lower() in ("todos", "all", ""):
            q.pop("tipo", None)
        elif "trans" in str(tipo).lower():
            q["tipo"] = "Transferencia"
        else:
            q["tipo"] = str(tipo)
    if origem:
        q["origem"] = origem
    for k, v in filtros.items():
        if v is not None and str(v) != "":
            q[k] = str(v)
    navegar(page, montar_url("/relatorios/lancamentos", q))


def ir_relatorio_categoria(
    page: ft.Page,
    categoria_id: str,
    tipo: str | None = "Despesa",
    ctx: ReportContext | None = None,
    origem: str | None = None,
) -> None:
    q = ctx.to_query() if ctx else _periodo_base_query(page, None)
    q.pop("cat", None)
    if tipo:
        q["tipo"] = tipo
    if origem:
        q["origem"] = origem
    navegar(page, montar_url(f"/relatorios/categoria/{categoria_id}", q))


def ir_relatorio_regra(
    page: ft.Page,
    regra: str,
    ctx: ReportContext | None = None,
    origem: str | None = None,
) -> None:
    slug = regra_para_slug(regra)
    q = ctx.to_query() if ctx else _periodo_base_query(page, None)
    q.pop("regra", None)
    if origem:
        q["origem"] = origem
    navegar(page, montar_url(f"/relatorios/regra/{slug}", q))


def ir_relatorio_fluxo(
    page: ft.Page,
    meses: int = 6,
    origem: str | None = None,
) -> None:
    q: dict[str, str] = {"meses": str(meses)}
    if origem:
        q["origem"] = origem
    navegar(page, montar_url("/relatorios/fluxo", q))
