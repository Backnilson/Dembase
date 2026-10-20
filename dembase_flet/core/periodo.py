"""
=============================================================================
DemBase v3 — core/periodo.py  (Flet 1.0.1)
Gerenciamento centralizado do estado global de período na sessão do Flet.
Fonte única da verdade para Dashboard, Relatórios, Contas e Cartões.
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


def obter_estado_periodo_atual(page: ft.Page | None) -> dict:
    """
    Recupera (ou inicializa) o estado global do filtro de período na sessão.
    Chaves: modo ('mes' | 'ciclo' | '30d' | 'custom'), data_inicio (date), data_fim (date),
            mes (int), ano (int), dia_ciclo (int).
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
        }

    modo = session_get(page, "periodo_modo", "mes") or "mes"
    mes = int(session_get(page, "periodo_mes", hoje_d.month) or hoje_d.month)
    ano = int(session_get(page, "periodo_ano", hoje_d.year) or hoje_d.year)
    dia_ciclo = storage.obter_dia_ciclo_padrao(page)

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


def atualizar_datas_periodo_global(page: ft.Page | None, data_inicio: date | str, data_fim: date | str) -> dict:
    """
    Atualiza as datas de início e fim na sessão global (mantendo sincronia entre
    Dashboard e Relatórios) e retorna o estado atualizado.
    """
    estado = obter_estado_periodo_atual(page)
    d_ini = date.fromisoformat(str(data_inicio)[:10]) if isinstance(data_inicio, str) else data_inicio
    d_fim = date.fromisoformat(str(data_fim)[:10]) if isinstance(data_fim, str) else data_fim
    if d_fim < d_ini:
        d_ini, d_fim = d_fim, d_ini

    # Verifica se corresponde exatamente a um mês fechado
    ult_dia = calendar.monthrange(d_ini.year, d_ini.month)[1]
    if d_ini.day == 1 and d_fim == date(d_ini.year, d_ini.month, ult_dia):
        estado["modo"] = "mes"
    else:
        estado["modo"] = "custom"

    estado["data_inicio"] = d_ini
    estado["data_fim"] = d_fim
    estado["mes"] = d_fim.month
    estado["ano"] = d_fim.year
    persistir_estado_periodo(page, estado)
    return estado
