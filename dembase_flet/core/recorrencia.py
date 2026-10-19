"""
=============================================================================
DemBase v3 — core/recorrencia.py
Lógica pura de agendamento, clamping de datas e cálculo de parcelamento.
Sem dependências de UI (Flet).
=============================================================================
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import List


FREQUENCIAS_MAP = {
    "diaria": 0,
    "semanal": 0,
    "quinzenal": 0,
    "mensal": 1,
    "bimestral": 2,
    "trimestral": 3,
    "semestral": 6,
    "anual": 12,
}


def dividir_parcelas(total: float, n: int) -> List[float]:
    """
    Divide o valor total em N parcelas sem perda de centavos.
    O resto da divisão é sempre atribuído à última parcela.
    
    Exemplo:
        dividir_parcelas(100.0, 3) -> [33.33, 33.33, 33.34]
        sum([33.33, 33.33, 33.34]) == 100.00
    """
    if n <= 0:
        raise ValueError("Quantidade de parcelas deve ser maior que zero")
    if n == 1:
        return [round(total, 2)]

    centavos_total = int(round(total * 100))
    centavos_base = centavos_total // n
    resto = centavos_total - (centavos_base * n)

    parcelas = []
    for i in range(1, n + 1):
        if i == n:
            parcelas.append(round((centavos_base + resto) / 100.0, 2))
        else:
            parcelas.append(round(centavos_base / 100.0, 2))

    return parcelas


def calcular_proxima_data(data_base: date, frequencia: str, passo: int) -> date:
    """
    Calcula a próxima data a partir de uma data-base e passo,
    ancorando no dia original e realizando clamp no último dia do mês alvo.

    Exemplo para data_base = 31/01/2026, mensal:
        passo 0: 31/01/2026
        passo 1: 28/02/2026
        passo 2: 31/03/2026
        passo 3: 30/04/2026
    """
    if passo == 0:
        return data_base

    freq = frequencia.lower().strip()

    if freq == "diaria":
        return data_base + timedelta(days=passo)
    elif freq == "semanal":
        return data_base + timedelta(days=passo * 7)
    elif freq == "quinzenal":
        return data_base + timedelta(days=passo * 15)

    intervalo_meses = FREQUENCIAS_MAP.get(freq, 1)
    if intervalo_meses == 0:
        intervalo_meses = 1

    total_meses = (data_base.year * 12 + (data_base.month - 1)) + (passo * intervalo_meses)
    ano_alvo = total_meses // 12
    mes_alvo = (total_meses % 12) + 1

    dias_no_mes = calendar.monthrange(ano_alvo, mes_alvo)[1]
    dia_alvo = min(data_base.day, dias_no_mes)

    return date(ano_alvo, mes_alvo, dia_alvo)


def gerar_datas(data_inicio: date, frequencia: str, n: int) -> List[date]:
    """Gera uma lista de N datas sucessivas com a frequência informada."""
    if n <= 0:
        return []
    return [calcular_proxima_data(data_inicio, frequencia, i) for i in range(n)]


def resumo_parcelas(total: float, n: int, modo: str = "parcelado", frequencia: str = "mensal", data_inicio: date | None = None) -> str:
    """
    Gera string explicativa para a UI.
    Modo 'parcelado': '3x de R$ 33,33' (total dividido por N)
    Modo 'repetido': '12x de R$ 83,33 · último em 15/09/2027' (mesmo valor por repetição)
    """
    if n <= 1:
        return ""

    if modo == "parcelado":
        parcelas = dividir_parcelas(total, n)
        valor_base = parcelas[0]
        texto = f"{n}x de R$ {valor_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if data_inicio:
            ultima_data = calcular_proxima_data(data_inicio, frequencia, n - 1)
            texto += f" · término em {ultima_data.strftime('%d/%m/%Y')}"
        return texto
    else:  # repetido
        valor_base = total
        texto = f"{n}x de R$ {valor_base:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if data_inicio:
            ultima_data = calcular_proxima_data(data_inicio, frequencia, n - 1)
            texto += f" · último em {ultima_data.strftime('%d/%m/%Y')}"
        return texto
