"""
=============================================================================
DemBase v3 — core/periodo.py  (Flet 1.0.1)
Gerenciamento centralizado do estado global de período na sessão do Flet.
Fonte única da verdade para Dashboard, Calendário, Relatórios, Contas e Cartões.
=============================================================================
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
import flet as ft

from core.constants import session_get, session_set
from core import storage


def calcular_ciclo(mes_ref: int, ano_ref: int, dia_inicio: int) -> tuple[date, date]:
    """
    Calcula um ciclo personalizado que começa em `dia_inicio` do mês anterior
    e termina em `dia_inicio - 1` do mês de referência (ex: 20/Set a 19/Out).
    Se dia_inicio <= 1, retorna o mês fechado normal.
    """
    if dia_inicio <= 1:
        ultimo_dia = calendar.monthrange(ano_ref, mes_ref)[1]
        return date(ano_ref, mes_ref, 1), date(ano_ref, mes_ref, ultimo_dia)

    if mes_ref == 1:
        mes_ant, ano_ant = 12, ano_ref - 1
    else:
        mes_ant, ano_ant = mes_ref - 1, ano_ref

    max_dia_ant = calendar.monthrange(ano_ant, mes_ant)[1]
    d_ini = date(ano_ant, mes_ant, min(dia_inicio, max_dia_ant))

    max_dia_atual = calendar.monthrange(ano_ref, mes_ref)[1]
    d_fim = date(ano_ref, mes_ref, min(dia_inicio, max_dia_atual)) - timedelta(days=1)
    return d_ini, d_fim


def calcular_intervalo_dias_mes(
    mes_ref: int,
    ano_ref: int,
    dia_ini: int,
    dia_fim: int,
    ate_fim_mes: bool = False,
) -> tuple[date, date]:
    """
    Calcula um intervalo de dias dentro do mês de referência
    (ex: Dia 05 a 20, ou Dia 20 a 30/31 com ate_fim_mes=True).
    """
    m = max(1, min(12, int(mes_ref)))
    a = int(ano_ref)
    ult_dia = calendar.monthrange(a, m)[1]
    d1 = max(1, min(ult_dia, int(dia_ini)))
    d2 = ult_dia if ate_fim_mes else max(d1, min(ult_dia, int(dia_fim)))
    return date(a, m, d1), date(a, m, d2)


def avancar_periodo_estado(estado_p: dict, direcao: int) -> dict:
    """
    Avança ou retrocede o período ativo em 1 passo (direcao = -1 ou +1),
    preservando faixas como 'Dia 05 a 20' ou 'Dia 20 a 30/31' ao trocar de mês.
    """
    modo = estado_p.get("modo", "mes")
    d_ini = estado_p["data_inicio"]
    d_fim = estado_p["data_fim"]
    if isinstance(d_ini, str):
        d_ini = date.fromisoformat(d_ini[:10])
    if isinstance(d_fim, str):
        d_fim = date.fromisoformat(d_fim[:10])

    mes_atual = int(estado_p.get("mes") or d_fim.month)
    ano_atual = int(estado_p.get("ano") or d_fim.year)
    mesmo_mes = (d_ini.month == d_fim.month and d_ini.year == d_fim.year)

    if modo in ("mes", "ciclo", "faixa_mes") or mesmo_mes:
        m = mes_atual + direcao
        a = ano_atual
        if m < 1:
            m = 12
            a -= 1
        elif m > 12:
            m = 1
            a += 1
        estado_p["mes"] = m
        estado_p["ano"] = a

        if modo == "mes":
            ult = calendar.monthrange(a, m)[1]
            estado_p["data_inicio"] = date(a, m, 1)
            estado_p["data_fim"] = date(a, m, ult)
        elif modo == "ciclo":
            ni, nf = calcular_ciclo(m, a, int(estado_p.get("dia_ciclo") or 1))
            estado_p["data_inicio"] = ni
            estado_p["data_fim"] = nf
        else:
            ult_ant = calendar.monthrange(d_fim.year, d_fim.month)[1]
            ate_fim = bool(estado_p.get("ate_fim_mes")) or (d_fim.day == ult_ant)
            ni, nf = calcular_intervalo_dias_mes(m, a, d_ini.day, d_fim.day, ate_fim_mes=ate_fim)
            estado_p["data_inicio"] = ni
            estado_p["data_fim"] = nf
            estado_p["ate_fim_mes"] = ate_fim
    else:
        dias = max(1, (d_fim - d_ini).days + 1)
        delta = timedelta(days=dias * direcao)
        estado_p["data_inicio"] = d_ini + delta
        estado_p["data_fim"] = d_fim + delta
        estado_p["mes"] = estado_p["data_fim"].month
        estado_p["ano"] = estado_p["data_fim"].year

    return estado_p


def obter_estado_periodo_atual(page: ft.Page | None) -> dict:
    """
    Recupera (ou inicializa) o estado global do filtro de período na sessão.
    Chaves: modo ('mes' | 'ciclo' | 'faixa_mes' | '30d' | 'custom'),
            data_inicio (date), data_fim (date), mes (int), ano (int),
            dia_ciclo (int), ate_fim_mes (bool), filtro_id (str | None).
    """
    hoje_d = date.today()
    if page is None:
        ult = calendar.monthrange(hoje_d.year, hoje_d.month)[1]
        return {
            "modo": "mes",
            "data_inicio": date(hoje_d.year, hoje_d.month, 1),
            "data_fim": date(hoje_d.year, hoje_d.month, ult),
            "mes": hoje_d.month,
            "ano": hoje_d.year,
            "dia_ciclo": 1,
            "ate_fim_mes": False,
            "filtro_id": None,
        }

    modo = session_get(page, "periodo_modo", "mes") or "mes"
    mes = int(session_get(page, "periodo_mes", hoje_d.month) or hoje_d.month)
    ano = int(session_get(page, "periodo_ano", hoje_d.year) or hoje_d.year)
    dia_ciclo = storage.obter_dia_ciclo_padrao(page)
    ate_fim_mes = bool(session_get(page, "periodo_ate_fim_mes", False))
    filtro_id = session_get(page, "periodo_filtro_id", None)

    ini_str = session_get(page, "periodo_inicio")
    fim_str = session_get(page, "periodo_fim")

    try:
        if ini_str and fim_str:
            d_ini = date.fromisoformat(str(ini_str)[:10])
            d_fim = date.fromisoformat(str(fim_str)[:10])
            if d_fim < d_ini:
                d_ini, d_fim = d_fim, d_ini
        else:
            raise ValueError()
    except Exception:
        ultimo_dia = calendar.monthrange(ano, mes)[1]
        d_ini = date(ano, mes, 1)
        d_fim = date(ano, mes, ultimo_dia)

    return {
        "modo": modo,
        "data_inicio": d_ini,
        "data_fim": d_fim,
        "mes": mes,
        "ano": ano,
        "dia_ciclo": dia_ciclo,
        "ate_fim_mes": ate_fim_mes,
        "filtro_id": filtro_id,
    }


def persistir_estado_periodo(page: ft.Page | None, estado: dict) -> None:
    """Salva o estado de período na sessão global da página."""
    if page is None:
        return
    d_ini = estado["data_inicio"]
    d_fim = estado["data_fim"]
    if isinstance(d_ini, str):
        d_ini = date.fromisoformat(d_ini[:10])
    if isinstance(d_fim, str):
        d_fim = date.fromisoformat(d_fim[:10])

    session_set(page, "periodo_modo", estado.get("modo", "custom"))
    session_set(page, "periodo_inicio", d_ini.isoformat())
    session_set(page, "periodo_fim", d_fim.isoformat())
    session_set(page, "periodo_mes", int(estado.get("mes", d_fim.month)))
    session_set(page, "periodo_ano", int(estado.get("ano", d_fim.year)))
    session_set(page, "periodo_ate_fim_mes", bool(estado.get("ate_fim_mes", False)))
    session_set(page, "periodo_filtro_id", estado.get("filtro_id"))


def atualizar_datas_periodo_global(
    page: ft.Page | None,
    data_inicio: date | str,
    data_fim: date | str,
    mes: int | None = None,
    ano: int | None = None,
    ate_fim_mes: bool | None = None,
    filtro_id: str | None = None,
) -> dict:
    """
    Atualiza as datas de início e fim na sessão global (mantendo sincronia entre
    Dashboard, Calendário, Contas, Cartões e Relatórios) e retorna o estado atualizado.
    """
    estado = obter_estado_periodo_atual(page)
    d_ini = date.fromisoformat(str(data_inicio)[:10]) if isinstance(data_inicio, str) else data_inicio
    d_fim = date.fromisoformat(str(data_fim)[:10]) if isinstance(data_fim, str) else data_fim
    if d_fim < d_ini:
        d_ini, d_fim = d_fim, d_ini

    ult_dia = calendar.monthrange(d_ini.year, d_ini.month)[1]
    if d_ini.day == 1 and d_fim == date(d_ini.year, d_ini.month, ult_dia):
        estado["modo"] = "mes"
        estado["ate_fim_mes"] = True
    elif d_ini.month == d_fim.month and d_ini.year == d_fim.year:
        estado["modo"] = "faixa_mes"
        estado["ate_fim_mes"] = bool(ate_fim_mes) if ate_fim_mes is not None else (d_fim.day == ult_dia)
    else:
        estado["modo"] = "custom"
        estado["ate_fim_mes"] = False

    estado["data_inicio"] = d_ini
    estado["data_fim"] = d_fim
    estado["mes"] = int(mes) if mes is not None else d_fim.month
    estado["ano"] = int(ano) if ano is not None else d_fim.year
    if filtro_id is not None:
        estado["filtro_id"] = filtro_id
    persistir_estado_periodo(page, estado)
    return estado
