"""
=============================================================================
DemBase v3 — core/router.py  (Flet 1.0.1)
Roteador declarativo com parser de query string, suporte a parâmetros de rota
(ft.TemplateRoute sem vazamento de query) e pilha hierárquica de ft.View.
=============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
import inspect
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlsplit
import flet as ft

from core.constants import session_get
from core import storage
from core.report_context import ReportContext
from services import supabase_client as db

# ── Constantes de rota ────────────────────────────────────────────────────────
ROTA_AUTH                  = "/auth"
ROTA_DASHBOARD             = "/dashboard"
ROTA_LANCAMENTO            = "/lancamento"
ROTA_CONTAS                = "/contas"
ROTA_CONTA_DETALHE         = "/contas/:conta_id"
ROTA_CARTOES               = "/cartoes"
ROTA_CARTAO_DETALHE        = "/cartoes/:cartao_id"
ROTA_CATEGORIAS            = "/categorias"
ROTA_CALENDARIO            = "/calendario"
ROTA_RELATORIOS            = "/relatorios"
ROTA_RELATORIO_LANCAMENTOS = "/relatorios/lancamentos"
ROTA_RELATORIO_CATEGORIA   = "/relatorios/categoria/:categoria_id"
ROTA_RELATORIO_REGRA       = "/relatorios/regra/:regra"
ROTA_RELATORIO_FLUXO       = "/relatorios/fluxo"
ROTA_CONFIG                = "/configuracoes"

_ROTAS_SEM_SHELL = {ROTA_AUTH}


@dataclass
class RouteMatch:
    path: str
    params_path: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    rota_completa: str = "/dashboard"
    template: str = "/dashboard"

    def get(self, key: str, default=None):
        if key in self.params_path:
            return self.params_path[key]
        if key in self.query:
            return self.query[key]
        return default

    def __getitem__(self, key: str):
        val = self.get(key)
        if val is None:
            raise KeyError(key)
        return val

    def __contains__(self, key: str):
        return key in self.params_path or key in self.query


@dataclass
class RotaDef:
    template: str
    builder: Callable[[ft.Page, RouteMatch], ft.View]
    pai: str | Callable[[RouteMatch], str | None] | None = None
    requer_login: bool = True


def separar_rota(rota_completa: str | None) -> tuple[str, dict[str, str]]:
    """
    Separa o path limpo e os parâmetros de query string antes de usar TemplateRoute.
    Resolve o comportamento do Flet 1.0.1 onde TemplateRoute não remove '?query'.
    """
    bruta = (rota_completa or "/").strip()
    if not bruta.startswith("/"):
        bruta = "/" + bruta
    partes = urlsplit(bruta)
    path = partes.path.rstrip("/") or "/"
    params: dict[str, str] = {}
    for k, vals in parse_qs(partes.query, keep_blank_values=False).items():
        if vals:
            params[k] = vals[0]
    return path, params


def normalizar_rota_completa(rota_completa: str | None) -> str:
    path, params = separar_rota(rota_completa)
    if not params:
        return path
    return f"{path}?{urlencode(params)}"


def navegar(page: ft.Page, rota: str):
    """Navega para uma rota no Flet 1.0.1 usando page.navigate."""
    page.navigate(rota)


def reconstruir_rota_atual(page: ft.Page):
    """Reconstrói todas as views da pilha atual (ex: ao trocar tema Claro/Escuro)."""
    fn = getattr(page, "_reconstruir_rota", None)
    if callable(fn):
        fn(forcar_rebuild=True)
    else:
        page.update()


# =============================================================================
# BUILDERS DAS ROTAS (Lazy imports para evitar ciclos e acelerar startup)
# =============================================================================
def _build_auth(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.auth_view import criar_view_auth
    v = criar_view_auth(page)
    v.route = ROTA_AUTH
    v.can_pop = False
    return v


def _build_dashboard(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.dashboard_view import criar_view_dashboard
    v = criar_view_dashboard(page)
    v.route = ROTA_DASHBOARD
    v.can_pop = False
    return v


def _build_lancamento(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.lancamento_view import criar_view_lancamento
    v = criar_view_lancamento(page)
    v.route = match.rota_completa
    return v


def _build_contas(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.contas_view import criar_view_contas
    sig = inspect.signature(criar_view_contas)
    if len(sig.parameters) >= 2:
        v = criar_view_contas(page, match)
    else:
        v = criar_view_contas(page)
    v.route = match.rota_completa
    return v


def _build_conta_detalhe(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.relatorios.conta_report import criar_view_relatorio_conta
    ctx = ReportContext.from_query(match.query, page)
    conta_id = match.params_path.get("conta_id", "")
    ctx = ctx.com(conta_id=conta_id)
    v = criar_view_relatorio_conta(page, match, ctx)
    v.route = match.rota_completa
    return v


def _build_cartoes(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.cartoes_view import criar_view_cartoes
    sig = inspect.signature(criar_view_cartoes)
    if len(sig.parameters) >= 2:
        v = criar_view_cartoes(page, match)
    else:
        v = criar_view_cartoes(page)
    v.route = match.rota_completa
    return v


def _build_cartao_detalhe(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.relatorios.cartao_report import criar_view_relatorio_cartao
    ctx = ReportContext.from_query(match.query, page)
    cartao_id = match.params_path.get("cartao_id", "")
    ctx = ctx.com(cartao_id=cartao_id)
    v = criar_view_relatorio_cartao(page, match, ctx)
    v.route = match.rota_completa
    return v


def _build_categorias(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.categorias_view import criar_view_categorias
    v = criar_view_categorias(page)
    v.route = match.rota_completa
    return v


def _build_calendario(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.calendario_view import criar_view_calendario
    v = criar_view_calendario(page)
    v.route = match.rota_completa
    return v


def _build_config(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.config_view import criar_view_config
    v = criar_view_config(page, match=match)
    v.route = match.rota_completa
    return v


def _build_relatorios_hub_ou_atalho(page: ft.Page, match: RouteMatch) -> ft.View:
    """
    Se /relatorios for chamado com filtros diretos (ex: ?tipo=Receita ou ?regra=Essencial),
    abre diretamente o relatório correspondente; caso contrário abre o Hub de Relatórios.
    """
    q = match.query
    if q.get("regra") and not q.get("tipo"):
        from views.relatorios.regra5030_report import criar_view_relatorio_regra
        ctx = ReportContext.from_query(q, page)
        match_regra = RouteMatch(
            path=match.path,
            params_path={"regra": q["regra"]},
            query=q,
            rota_completa=match.rota_completa,
            template=ROTA_RELATORIO_REGRA,
        )
        v = criar_view_relatorio_regra(page, match_regra, ctx)
        v.route = match.rota_completa
        return v

    if any(k in q for k in ("tipo", "conta", "cat", "sub", "status", "forma", "q")):
        from views.relatorios.lancamentos_report import criar_view_relatorio_lancamentos
        ctx = ReportContext.from_query(q, page)
        v = criar_view_relatorio_lancamentos(page, match, ctx)
        v.route = match.rota_completa
        return v

    from views.relatorios.hub_view import criar_view_hub_relatorios
    ctx = ReportContext.from_query(q, page)
    v = criar_view_hub_relatorios(page, match, ctx)
    v.route = match.rota_completa
    return v


def _build_relatorio_lancamentos(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.relatorios.lancamentos_report import criar_view_relatorio_lancamentos
    ctx = ReportContext.from_query(match.query, page)
    v = criar_view_relatorio_lancamentos(page, match, ctx)
    v.route = match.rota_completa
    return v


def _build_relatorio_categoria(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.relatorios.categoria_report import criar_view_relatorio_categoria
    ctx = ReportContext.from_query(match.query, page)
    cat_id = match.params_path.get("categoria_id") or match.params_path.get("cat_id") or ""
    ctx = ctx.com(categoria_id=cat_id)
    v = criar_view_relatorio_categoria(page, match, ctx)
    v.route = match.rota_completa
    return v


def _build_relatorio_regra(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.relatorios.regra5030_report import criar_view_relatorio_regra
    ctx = ReportContext.from_query(match.query, page)
    regra_param = match.params_path.get("regra", "")
    ctx = ctx.com(regra=regra_param)
    v = criar_view_relatorio_regra(page, match, ctx)
    v.route = match.rota_completa
    return v


def _build_relatorio_fluxo(page: ft.Page, match: RouteMatch) -> ft.View:
    from views.relatorios.fluxo_mensal_report import criar_view_relatorio_fluxo
    ctx = ReportContext.from_query(match.query, page)
    v = criar_view_relatorio_fluxo(page, match, ctx)
    v.route = match.rota_completa
    return v


def _pai_relatorio_dinamico(match: RouteMatch) -> str:
    origem = (match.query.get("origem") or "").strip().lower()
    if origem == "dashboard":
        return ROTA_DASHBOARD
    if origem == "contas" and match.query.get("conta"):
        return f"/contas/{match.query['conta']}"
    if origem == "cartoes" and match.query.get("cartao"):
        return f"/cartoes/{match.query['cartao']}"
    return ROTA_RELATORIOS


# =============================================================================
# TABELA DECLARATIVA DE ROTAS (Mais específicas primeiro)
# =============================================================================
ROTAS_TABELA: list[RotaDef] = [
    RotaDef(ROTA_AUTH,                  _build_auth,                  pai=None,                     requer_login=False),
    RotaDef(ROTA_DASHBOARD,             _build_dashboard,             pai=None),
    RotaDef("/",                        _build_dashboard,             pai=None),
    RotaDef(ROTA_LANCAMENTO,            _build_lancamento,            pai=ROTA_DASHBOARD),
    RotaDef(ROTA_CONTA_DETALHE,         _build_conta_detalhe,         pai=ROTA_CONTAS),
    RotaDef(ROTA_CONTAS,                _build_contas,                pai=ROTA_DASHBOARD),
    RotaDef(ROTA_CARTAO_DETALHE,        _build_cartao_detalhe,        pai=ROTA_CARTOES),
    RotaDef(ROTA_CARTOES,               _build_cartoes,               pai=ROTA_DASHBOARD),
    RotaDef(ROTA_CATEGORIAS,            _build_categorias,            pai=ROTA_DASHBOARD),
    RotaDef(ROTA_CALENDARIO,            _build_calendario,            pai=ROTA_DASHBOARD),
    RotaDef(ROTA_CONFIG,                _build_config,                pai=ROTA_DASHBOARD),
    RotaDef(ROTA_RELATORIO_LANCAMENTOS, _build_relatorio_lancamentos, pai=_pai_relatorio_dinamico),
    RotaDef(ROTA_RELATORIO_CATEGORIA,   _build_relatorio_categoria,   pai=_pai_relatorio_dinamico),
    RotaDef("/relatorios/categoria/:cat_id", _build_relatorio_categoria, pai=_pai_relatorio_dinamico),
    RotaDef(ROTA_RELATORIO_REGRA,       _build_relatorio_regra,       pai=_pai_relatorio_dinamico),
    RotaDef(ROTA_RELATORIO_FLUXO,       _build_relatorio_fluxo,       pai=_pai_relatorio_dinamico),
    RotaDef("/relatorios/fluxo-mensal", _build_relatorio_fluxo,       pai=_pai_relatorio_dinamico),
    RotaDef(ROTA_RELATORIOS,            _build_relatorios_hub_ou_atalho, pai=ROTA_DASHBOARD),
]


def _extrair_nomes_parametros(template: str) -> list[str]:
    nomes = []
    for seg in template.split("/"):
        if seg.startswith(":") and len(seg) > 1:
            nomes.append(seg[1:])
    return nomes


def resolver_rota(rota_completa: str | None) -> tuple[RotaDef | None, RouteMatch]:
    """
    Faz o match da rota completa contra ROTAS_TABELA usando ft.TemplateRoute
    apenas no path limpo (sem query string).
    """
    path, query = separar_rota(rota_completa)
    rota_norm = normalizar_rota_completa(rota_completa)
    tr = ft.TemplateRoute(path)

    for defn in ROTAS_TABELA:
        if tr.match(defn.template):
            nomes = _extrair_nomes_parametros(defn.template)
            params_path = {
                nome: str(getattr(tr, nome))
                for nome in nomes
                if getattr(tr, nome, None) is not None
            }
            match = RouteMatch(
                path=path,
                params_path=params_path,
                query=query,
                rota_completa=rota_norm if path != "/" else ROTA_DASHBOARD,
                template=defn.template,
            )
            return defn, match

    # Fallback para rota desconhecida
    fallback_match = RouteMatch(
        path=ROTA_DASHBOARD,
        params_path={},
        query={},
        rota_completa=ROTA_DASHBOARD,
        template=ROTA_DASHBOARD,
    )
    return None, fallback_match


def montar_pilha(rota_completa: str | None) -> list[str]:
    """
    Deriva a pilha hierárquica de rotas a partir da URL alvo.
    Propaga ini/fim para o pai intermediário quando aplicável.
    Ex: '/contas/abc?ini=2026-10-01&fim=2026-10-31' ->
        ['/dashboard', '/contas?ini=2026-10-01&fim=2026-10-31', '/contas/abc?ini=2026-10-01&fim=2026-10-31']
    """
    defn, match = resolver_rota(rota_completa)
    if defn is None:
        return [ROTA_DASHBOARD]

    if defn.template == ROTA_AUTH:
        return [ROTA_AUTH]

    cadeia: list[str] = [match.rota_completa]
    visitados: set[str] = {match.path}

    atual_defn = defn
    atual_match = match

    while atual_defn and atual_defn.pai is not None:
        pai_raw = atual_defn.pai(atual_match) if callable(atual_defn.pai) else atual_defn.pai
        if not pai_raw:
            break

        pai_path, pai_q = separar_rota(pai_raw)
        if pai_path in visitados:
            break
        visitados.add(pai_path)

        # Propaga ini/fim para pais intermediários (/contas, /relatorios)
        if pai_path not in (ROTA_DASHBOARD, ROTA_AUTH):
            for k_per in ("ini", "fim"):
                if k_per in match.query and k_per not in pai_q:
                    pai_q[k_per] = match.query[k_per]

        pai_completo = normalizar_rota_completa(
            f"{pai_path}?{urlencode(pai_q)}" if pai_q else pai_path
        )
        cadeia.insert(0, pai_completo)
        atual_defn, atual_match = resolver_rota(pai_completo)

    return cadeia


# =============================================================================
# CONFIGURAÇÃO DO ROTEADOR NA PÁGINA
# =============================================================================
def configurar_rotas(page: ft.Page):
    def _logado() -> bool:
        try:
            sessao = db.sessao_atual()
            if sessao and getattr(sessao, "user", None):
                return True
            acc, ref, _ = storage.carregar_sessao_autenticada_sync(page)
            if not acc or not ref:
                acc = session_get(page, "auth_access_token")
                ref = session_get(page, "auth_refresh_token")
            if acc and ref:
                return db.restaurar_sessao(acc, ref)
            return False
        except Exception:
            return False

    def _construir_view(rota_str: str) -> ft.View:
        defn, match = resolver_rota(rota_str)
        if defn is None:
            return _build_dashboard(page, match) if _logado() else _build_auth(page, match)
        return defn.builder(page, match)

    def on_route_change(e: ft.RouteChangeEvent | None = None, forcar_rebuild: bool = False):
        rota = page.route or ROTA_DASHBOARD
        path_atual, _ = separar_rota(rota)
        logado = _logado()

        # Redireciona não-logado para auth
        if not logado and path_atual not in _ROTAS_SEM_SHELL:
            page.views.clear()
            page.views.append(_build_auth(page, RouteMatch(path=ROTA_AUTH, rota_completa=ROTA_AUTH, template=ROTA_AUTH)))
            page.update()
            return

        # Redireciona logado que tenta ir para auth
        if logado and path_atual == ROTA_AUTH:
            page.views.clear()
            page.views.append(_build_dashboard(page, RouteMatch(path=ROTA_DASHBOARD, rota_completa=ROTA_DASHBOARD, template=ROTA_DASHBOARD)))
            page.update()
            return

        # Persiste a última rota ativa para restauração automática no mobile/background
        if logado and path_atual not in _ROTAS_SEM_SHELL:
            storage.salvar_ultima_rota_sync(page, rota)

        pilha = montar_pilha(rota)
        views_atuais = list(page.views)

        if forcar_rebuild:
            page.views.clear()
            for r_str in pilha:
                page.views.append(_construir_view(r_str))
            page.update()
            return

        # Reaproveita views ancestrais já instanciadas na pilha para voltar instantâneo
        novas_views: list[ft.View] = []
        divergiu = False
        reaproveitou_topo = False
        topo_reaproveitado: ft.View | None = None

        for idx, r_alvo in enumerate(pilha):
            eh_topo = (idx == len(pilha) - 1)
            if not divergiu and idx < len(views_atuais):
                v_existente = views_atuais[idx]
                rota_v = getattr(v_existente, "route", "") or ""
                path_v, _ = separar_rota(rota_v)
                path_alvo, _ = separar_rota(r_alvo)

                # Se for view ancestral com mesmo path, reaproveita
                if not eh_topo and path_v == path_alvo:
                    novas_views.append(v_existente)
                    continue

                # Topo idêntico (caso de pop/voltar ou navegar para rota já no topo):
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
            novas_views.append(_construir_view(r_alvo))

        page.views.clear()
        for v in novas_views:
            page.views.append(v)

        page.update()

        if reaproveitou_topo and topo_reaproveitado:
            refresh_fn = getattr(topo_reaproveitado, "_dembase_refresh", None)
            if callable(refresh_fn):
                try:
                    refresh_fn()
                except Exception:
                    pass

    def on_view_pop(e: ft.ViewPopEvent):
        if len(page.views) > 1:
            page.views.pop()
            destino = getattr(page.views[-1], "route", None) or ROTA_DASHBOARD
            page.navigate(destino)
        else:
            page.update()

    page.on_route_change = on_route_change
    page.on_view_pop     = on_view_pop
    page._reconstruir_rota = lambda forcar_rebuild=False: on_route_change(None, forcar_rebuild=forcar_rebuild)
