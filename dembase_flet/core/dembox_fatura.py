"""
DemBox Fatura — FONTE ÚNICA DE VERDADE (módulo puro, sem I/O).

Calcula fatura relevante, meta, cobertura, dias até o vencimento e status dos
boxes de fatura. Todas as telas e serviços DEVEM consumir este módulo.

Regras:
- Fatura relevante: fechada (data_fechamento <= hoje) com vencimento mais próximo e
  ainda com restante > 0; se não houver, a fatura aberta atual (a de menor
  vencimento ainda não fechada e não paga).
- Guardado considera SOMENTE movimentos efetivados (pendente é previsão).
- Status: neutro (fatura zerada) | coberto | parcial | risco (vence em <= 3 dias
  com cobertura < 100%).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, Optional

CENT = 0.005
DIAS_RISCO = 3

STATUS_NEUTRO = "neutro"
STATUS_AGUARDANDO = "aguardando"
STATUS_COBERTO = "coberto"
STATUS_PARCIAL = "parcial"
STATUS_RISCO = "risco"

ROTULOS_STATUS = {
    STATUS_NEUTRO: "Sem fatura a pagar",
    STATUS_AGUARDANDO: "⏳ Aguardando",
    STATUS_COBERTO: "🟢 Coberto",
    STATUS_PARCIAL: "🟡 Parcial",
    STATUS_RISCO: "🔴 Em risco",
}

_ENTRADAS = {"aporte", "transf_entrada"}
_SAIDAS = {"retirada", "transf_saida", "pagamento"}


def _d(v) -> Optional[date]:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _f(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def calcular_saldo_guardado(movimentos: Iterable[dict]) -> float:
    """Soma movimentos EFETIVADOS. Pendente e cancelado nunca contam."""
    total = 0.0
    for m in movimentos or []:
        if (m.get("status") or "efetivado") != "efetivado":
            continue
        tipo = m.get("tipo")
        if tipo in _ENTRADAS:
            total += _f(m.get("valor"))
        elif tipo in _SAIDAS:
            total -= _f(m.get("valor"))
    return round(total, 2)


def calcular_agendado_pendente(movimentos: Iterable[dict]) -> float:
    """Previsão: aportes pendentes (nunca entra em saldo/Caixa Livre/Teto)."""
    return round(sum(
        _f(m.get("valor")) for m in (movimentos or [])
        if m.get("status") == "pendente" and m.get("tipo") == "aporte"
    ), 2)


def restante_fatura(fatura: dict) -> float:
    """Restante a pagar = total - pagamentos já feitos (nunca negativo)."""
    total = _f(fatura.get("valor_total"))
    pago = _f(fatura.get("valor_pago_parcial", fatura.get("valor_pago")))
    if (fatura.get("status") or "") == "paga":
        return 0.0
    return round(max(0.0, total - pago), 2)


def escolher_fatura_relevante(faturas: Iterable[dict], hoje: Optional[date] = None) -> Optional[dict]:
    """Fechada com vencimento mais próximo não paga; senão a aberta atual."""
    hoje = hoje or date.today()
    candidatas = [f for f in (faturas or []) if (f.get("status") or "") != "paga"]
    fechadas, abertas = [], []
    for f in candidatas:
        fech, venc = _d(f.get("data_fechamento")), _d(f.get("data_vencimento"))
        if venc is None:
            continue
        (fechadas if (fech is not None and fech <= hoje) else abertas).append((venc, f))
    # Fechada com restante > 0 tem prioridade
    fechadas = [(v, f) for v, f in fechadas if restante_fatura(f) > CENT]
    if fechadas:
        return min(fechadas, key=lambda t: t[0])[1]
    if abertas:
        return min(abertas, key=lambda t: t[0])[1]
    return None


@dataclass(frozen=True)
class SituacaoBox:
    guardado: float
    fatura: float          # meta (restante da fatura relevante)
    falta: float
    pct: float             # 0..1
    vencimento: Optional[date]
    dias_ate_vencimento: Optional[int]
    status: str
    rotulo: str
    agendado_pendente: float
    fatura_id: Optional[str]
    neutro: bool


def calcular_situacao(
    faturas: Iterable[dict],
    movimentos: Iterable[dict],
    hoje: Optional[date] = None,
) -> SituacaoBox:
    hoje = hoje or date.today()
    guardado = calcular_saldo_guardado(movimentos)
    pendente = calcular_agendado_pendente(movimentos)
    rel = escolher_fatura_relevante(faturas, hoje)
    meta = restante_fatura(rel) if rel else 0.0
    venc = _d(rel.get("data_vencimento")) if rel else None
    dias = (venc - hoje).days if venc else None

    if meta <= CENT:
        return SituacaoBox(guardado, 0.0, 0.0, 0.0, venc, dias, STATUS_NEUTRO,
                           ROTULOS_STATUS[STATUS_NEUTRO], pendente,
                           rel.get("id") if rel else None, True)

    falta = round(max(0.0, meta - guardado), 2)
    pct = max(0.0, min(1.0, guardado / meta))
    if guardado + CENT >= meta:
        status = STATUS_COBERTO
    elif dias is not None and dias <= DIAS_RISCO:
        status = STATUS_RISCO
    elif guardado <= CENT:
        status = STATUS_AGUARDANDO
    else:
        status = STATUS_PARCIAL
    return SituacaoBox(guardado, meta, falta, pct, venc, dias, status,
                       ROTULOS_STATUS[status], pendente, rel.get("id"), False)


def validar_retirada(saldo: float, valor: float) -> tuple[bool, str]:
    if valor <= 0:
        return False, "Informe um valor maior que zero."
    if valor > saldo + CENT:
        return False, "Valor maior que o saldo guardado neste box."
    return True, ""


def calcular_pagamento(situacao: SituacaoBox, valor: float) -> dict:
    """Simula pagamento (parcial ou total) sem tocar em Potes."""
    restante = situacao.fatura
    if restante <= CENT:
        return {"ok": False, "erro": "Fatura sem valor a pagar."}
    if valor <= 0:
        return {"ok": False, "erro": "Informe um valor maior que zero."}
    if valor > restante + CENT:
        return {"ok": False, "erro": "Valor maior que o restante da fatura."}
    debito_box = round(min(valor, max(0.0, situacao.guardado)), 2)
    return {
        "ok": True,
        "quitada": valor + CENT >= restante,
        "restante": round(max(0.0, restante - valor), 2),
        "debito_box": debito_box,
        "saldo_box": round(situacao.guardado - debito_box, 2),
    }


def cartoes_sem_box(cartoes: Iterable[dict], boxes: Iterable[dict]) -> list[dict]:
    """Cartões ativos que ainda não têm box de fatura (para o banner)."""
    com_box = {str(b.get("cartao_id")) for b in (boxes or [])
               if b.get("tipo_box") == "fatura" and b.get("ativo", True)}
    return [c for c in (cartoes or [])
            if c.get("ativo", True) and str(c.get("id")) not in com_box]


def somar_resumo(situacoes: Iterable[SituacaoBox]) -> dict:
    """Totais p/ cards de resumo. Coberto = min(guardado, fatura) evita sobra inflar a meta."""
    sit = list(situacoes)
    return {
        "guardado": round(sum(s.guardado for s in sit), 2),
        "meta": round(sum(s.fatura for s in sit), 2),
        "falta": round(sum(s.falta for s in sit), 2),
    }


def calcular_abatido(movimentos: Iterable[dict]) -> float:
    """Total já pago de faturas a partir do box (movimentos 'pagamento' efetivados)."""
    return round(sum(
        _f(m.get("valor")) for m in (movimentos or [])
        if m.get("tipo") == "pagamento" and (m.get("status") or "efetivado") == "efetivado"
    ), 2)


def parse_valor_br(txt: str) -> float:
    """'1.234,56' | '1234,56' | '1234.56' -> float. Levanta ValueError se inválido."""
    s = (txt or "").replace("R$", "").strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)
