"""
=============================================================================
DemBase v3 — core/report_context.py  (Flet 1.0.1)
Dataclass imutável ReportContext: serializa/desserializa filtros e período
entre URL (query string), sessão global e chamadas RPC do Supabase.
=============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
import uuid
import flet as ft

from core.periodo import obter_estado_periodo_atual, atualizar_datas_periodo_global


_MAPA_REGRA_SLUG = {
    "essencial": "Essencial",
    "estilo-de-vida": "Estilo de Vida",
    "estilo_vida": "Estilo de Vida",
    "estilo de vida": "Estilo de Vida",
    "investimento": "Investimento",
    "investimentos": "Investimento",
}

_MAPA_REGRA_PARA_SLUG = {
    "Essencial": "essencial",
    "Estilo de Vida": "estilo-de-vida",
    "Investimento": "investimento",
}


def normalizar_regra(valor: str | None) -> str | None:
    """Converte slug ou texto livre em valor canônico do enum regra_financeira."""
    if not valor:
        return None
    v = str(valor).strip()
    if v in ("Essencial", "Estilo de Vida", "Investimento"):
        return v
    return _MAPA_REGRA_SLUG.get(v.lower())


def regra_para_slug(regra: str | None) -> str:
    """Converte regra canônica em slug para URL."""
    canon = normalizar_regra(regra) or "essencial"
    return _MAPA_REGRA_PARA_SLUG.get(canon, "essencial")


def normalizar_tipo_filtro(valor: str | None) -> str | None:
    """Normaliza tipo de lançamento ('Receita', 'Despesa', 'Transferência', None=Todos)."""
    if not valor:
        return None
    v = str(valor).strip().lower()
    if v in ("todos", "all", ""):
        return None
    if "rec" in v:
        return "Receita"
    if "desp" in v:
        return "Despesa"
    if "trans" in v:
        return "Transferência"
    return None


def _validar_uuid(val: str | None) -> str | None:
    if not val:
        return None
    s = str(val).strip()
    try:
        return str(uuid.UUID(s))
    except (ValueError, TypeError, AttributeError):
        return None


def _parse_date_safe(val: str | date | None) -> date | None:
    if not val:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except Exception:
        return None


@dataclass(frozen=True)
class ReportContext:
    data_inicio: date
    data_fim: date
    tipo: str | None = None          # 'Receita' | 'Despesa' | 'Transferência' | None (=Receita+Despesa)
    conta_id: str | None = None
    cartao_id: str | None = None
    categoria_id: str | None = None
    subcategoria_id: str | None = None
    regra: str | None = None         # 'Essencial' | 'Estilo de Vida' | 'Investimento'
    status: str | None = None        # 'Pago' | 'Pendente'
    forma: str | None = None         # 'Pix' | 'Crédito' | 'Débito' | 'Dinheiro'
    busca: str | None = None
    origem: str | None = None        # 'dashboard' | 'relatorios' | 'contas' | 'cartoes'
    pagina: int = 1
    page_size: int = 25

    @property
    def regra_5030(self) -> str | None:
        """Alias compatível para regra."""
        return self.regra

    @classmethod
    def from_query(
        cls,
        params: dict | ft.Page | None = None,
        page: ft.Page | None = None,
        extra_params: dict | None = None,
    ) -> "ReportContext":
        """
        Constrói ReportContext com flexibilidade total de argumentos:
        - from_query(page)
        - from_query(params, page)
        - from_query(query_dict, page, match_params)
        Datas ou UUIDs inválidos são descartados com segurança.
        """
        # Se o primeiro argumento for ft.Page, inverte
        if isinstance(params, ft.Page):
            page, params = params, None

        raw_params: dict = {}
        if isinstance(params, dict):
            raw_params.update(params)
        elif hasattr(params, "query") and hasattr(params, "params_path"):
            # Objeto RouteMatch
            raw_params.update(getattr(params, "query", {}) or {})
            raw_params.update(getattr(params, "params_path", {}) or {})
        elif hasattr(params, "get"):
            try:
                raw_params.update(dict(params))
            except Exception:
                pass

        if extra_params and isinstance(extra_params, dict):
            raw_params.update(extra_params)

        estado_sessao = obter_estado_periodo_atual(page)

        d_ini = _parse_date_safe(raw_params.get("ini") or raw_params.get("data_inicio"))
        d_fim = _parse_date_safe(raw_params.get("fim") or raw_params.get("data_fim"))

        if d_ini and d_fim:
            if d_fim < d_ini:
                d_ini, d_fim = d_fim, d_ini
            # Sincroniza a sessão global se vier explícito na URL
            if page is not None:
                atualizar_datas_periodo_global(page, d_ini, d_fim)
        else:
            d_ini = estado_sessao["data_inicio"]
            d_fim = estado_sessao["data_fim"]
            if d_fim < d_ini:
                d_ini, d_fim = d_fim, d_ini

        status_raw = (raw_params.get("status") or "").strip().capitalize()
        status_val = status_raw if status_raw in ("Pago", "Pendente") else None

        forma_raw = (raw_params.get("forma") or "").strip()
        forma_val = forma_raw if forma_raw else None

        busca_raw = (raw_params.get("q") or raw_params.get("busca") or "").strip()
        busca_val = busca_raw if busca_raw else None

        origem_raw = (raw_params.get("origem") or "").strip().lower()
        origem_val = origem_raw if origem_raw else None

        try:
            pag_val = max(1, int(raw_params.get("p") or raw_params.get("pagina") or 1))
        except (ValueError, TypeError):
            pag_val = 1

        try:
            ps_val = max(5, int(raw_params.get("ps") or raw_params.get("page_size") or 25))
        except (ValueError, TypeError):
            ps_val = 25

        regra_val = normalizar_regra(raw_params.get("regra") or raw_params.get("regra_5030"))

        return cls(
            data_inicio=d_ini,
            data_fim=d_fim,
            tipo=normalizar_tipo_filtro(raw_params.get("tipo")),
            conta_id=_validar_uuid(raw_params.get("conta") or raw_params.get("conta_id")),
            cartao_id=_validar_uuid(raw_params.get("cartao") or raw_params.get("cartao_id")),
            categoria_id=_validar_uuid(raw_params.get("cat") or raw_params.get("categoria_id")),
            subcategoria_id=_validar_uuid(raw_params.get("sub") or raw_params.get("subcategoria_id")),
            regra=regra_val,
            status=status_val,
            forma=forma_val,
            busca=busca_val,
            origem=origem_val,
            pagina=pag_val,
            page_size=ps_val,
        )

    def to_query(self, incluir_periodo: bool = True) -> dict[str, str]:
        """Retorna dicionário apenas com chaves preenchidas para query string."""
        q: dict[str, str] = {}
        if incluir_periodo:
            q["ini"] = self.data_inicio.isoformat()
            q["fim"] = self.data_fim.isoformat()
        if self.tipo:
            q["tipo"] = "Transferencia" if "trans" in self.tipo.lower() else self.tipo
        if self.conta_id:
            q["conta"] = self.conta_id
        if self.cartao_id:
            q["cartao"] = self.cartao_id
        if self.categoria_id:
            q["cat"] = self.categoria_id
        if self.subcategoria_id:
            q["sub"] = self.subcategoria_id
        if self.regra:
            q["regra"] = regra_para_slug(self.regra)
        if self.status:
            q["status"] = self.status
        if self.forma:
            q["forma"] = self.forma
        if self.busca:
            q["q"] = self.busca
        if self.origem:
            q["origem"] = self.origem
        if self.pagina > 1:
            q["p"] = str(self.pagina)
        return q

    def com(self, **alteracoes) -> "ReportContext":
        """Retorna cópia atualizada (imutável) sanitizando datas, tipos e aliases."""
        if "regra_5030" in alteracoes:
            alteracoes["regra"] = alteracoes.pop("regra_5030")

        if "data_inicio" in alteracoes and isinstance(alteracoes["data_inicio"], str):
            alteracoes["data_inicio"] = date.fromisoformat(alteracoes["data_inicio"][:10])
        if "data_fim" in alteracoes and isinstance(alteracoes["data_fim"], str):
            alteracoes["data_fim"] = date.fromisoformat(alteracoes["data_fim"][:10])
        if "tipo" in alteracoes:
            alteracoes["tipo"] = normalizar_tipo_filtro(alteracoes["tipo"])
        if "regra" in alteracoes:
            alteracoes["regra"] = normalizar_regra(alteracoes["regra"])
        novo = replace(self, **alteracoes)
        if novo.data_fim < novo.data_inicio:
            novo = replace(novo, data_inicio=novo.data_fim, data_fim=novo.data_inicio)
        return novo

    def to_rpc_filtros(self) -> dict:
        """Gera dicionário JSONB limpo para enviar às RPCs do Supabase."""
        f: dict = {}
        if self.tipo:
            f["tipo"] = self.tipo
        if self.conta_id:
            f["conta_id"] = self.conta_id
        if self.cartao_id:
            f["cartao_id"] = self.cartao_id
        if self.categoria_id:
            f["categoria_id"] = self.categoria_id
        if self.subcategoria_id:
            f["subcategoria_id"] = self.subcategoria_id
        if self.regra:
            f["regra"] = self.regra
        if self.status:
            f["status"] = self.status
        if self.forma:
            f["forma"] = self.forma
        if self.busca:
            f["busca"] = self.busca
        return f

    def qtd_filtros_avancados(self) -> int:
        """Conta quantos filtros adicionais além de período e tipo estão ativos."""
        return sum(
            1
            for v in (
                self.conta_id,
                self.cartao_id,
                self.categoria_id,
                self.subcategoria_id,
                self.regra,
                self.status,
                self.forma,
                self.busca,
            )
            if v
        )
