"""
=============================================================================
DemBase v3 — core/potes.py
Regras de negócio dos 6 POTES financeiros (lógica pura, sem I/O).

  * Validação matemática rigorosa: soma dos 6 percentuais == 100 (Decimal).
  * Distribuição de receita em centavos pelo método do maior resto, garantindo
    que a soma das parcelas seja EXATAMENTE igual ao valor da receita.
=============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Iterable

# =============================================================================
# CONSTANTES
# =============================================================================
QTD_POTES = 6
TOTAL_PERCENTUAL = Decimal("100")
CENTAVO = Decimal("0.01")
NOME_MAX = 40

POTES_PADRAO = [
    {"posicao": 1, "nome": "Custos Fixos",         "percentual": Decimal("30"), "cor": "#007AFF"},
    {"posicao": 2, "nome": "Conforto",             "percentual": Decimal("15"), "cor": "#FF69B4"},
    {"posicao": 3, "nome": "Metas",                "percentual": Decimal("15"), "cor": "#800080"},
    {"posicao": 4, "nome": "Prazeres",             "percentual": Decimal("10"), "cor": "#FF7A00"},
    {"posicao": 5, "nome": "Conhecimento",         "percentual": Decimal("5"),  "cor": "#FFD60A"},
    {"posicao": 6, "nome": "Liberdade Financeira", "percentual": Decimal("25"), "cor": "#6C5CE7"},
]


# =============================================================================
# EXCEÇÕES / MODELOS
# =============================================================================
class ErroPotes(ValueError):
    """Erro de regra de negócio dos potes. `erros` guarda todas as mensagens."""

    def __init__(self, erros: list[str]):
        self.erros = erros
        super().__init__(" | ".join(erros))


@dataclass(frozen=True)
class Pote:
    id: str
    posicao: int
    nome: str
    percentual: Decimal
    cor: str = "#94A3B8"


# =============================================================================
# CONVERSÕES
# =============================================================================
def para_decimal(valor, default: Decimal | None = None) -> Decimal:
    """Converte int/float/str (aceita '1.234,56' e 'R$') para Decimal."""
    if isinstance(valor, Decimal):
        return valor
    if valor is None:
        if default is not None:
            return default
        raise ErroPotes(["Valor numérico ausente."])
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    texto = str(valor).replace("R$", "").replace("%", "").strip()
    if not texto:
        if default is not None:
            return default
        raise ErroPotes(["Valor numérico vazio."])
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        if default is not None:
            return default
        raise ErroPotes([f"Valor numérico inválido: '{valor}'."])


def potes_de_registros(registros: Iterable[dict]) -> list[Pote]:
    """Converte as linhas da tabela `potes` em objetos Pote ordenados."""
    potes = [
        Pote(
            id=str(r["id"]),
            posicao=int(r["posicao"]),
            nome=str(r["nome"]),
            percentual=para_decimal(r["percentual"]),
            cor=r.get("cor") or "#94A3B8",
        )
        for r in registros
    ]
    return sorted(potes, key=lambda p: p.posicao)


# =============================================================================
# VALIDAÇÃO
# =============================================================================
def soma_percentuais(percentuais: Iterable) -> Decimal:
    return sum((para_decimal(p, Decimal("0")) for p in percentuais), Decimal("0"))


def validar_configuracao(itens: list[dict]) -> list[str]:
    """
    Valida a configuração dos potes. Cada item: {"nome": str, "percentual": num}.
    Retorna a lista de erros (vazia = válida). Regras:
      - exatamente 6 potes; nomes preenchidos (<= 40) e únicos;
      - cada percentual entre 0 e 100;
      - soma dos percentuais estritamente igual a 100.
    """
    erros: list[str] = []

    if len(itens) != QTD_POTES:
        erros.append(f"São necessários exatamente {QTD_POTES} potes (recebidos: {len(itens)}).")

    nomes_vistos: set[str] = set()
    percentuais: list[Decimal] = []
    for item in itens:
        nome = str(item.get("nome", "")).strip()
        if not nome:
            erros.append("Todos os potes precisam de um nome.")
        elif len(nome) > NOME_MAX:
            erros.append(f"O nome '{nome[:12]}…' excede {NOME_MAX} caracteres.")
        elif nome.lower() in nomes_vistos:
            erros.append(f"Nome de pote duplicado: '{nome}'.")
        nomes_vistos.add(nome.lower())

        try:
            perc = para_decimal(item.get("percentual"))
        except ErroPotes:
            erros.append(f"Percentual inválido no pote '{nome or '?'}'.")
            continue
        if perc < 0 or perc > TOTAL_PERCENTUAL:
            erros.append(f"O percentual de '{nome or '?'}' deve estar entre 0 e 100.")
        percentuais.append(perc)

    soma = sum(percentuais, Decimal("0"))
    if soma != TOTAL_PERCENTUAL:
        erros.append(f"A soma dos percentuais deve ser exatamente 100% (atual: {soma.normalize():f}%).")

    return erros


def exigir_configuracao_valida(itens: list[dict]) -> None:
    erros = validar_configuracao(itens)
    if erros:
        raise ErroPotes(erros)


# =============================================================================
# DISTRIBUIÇÃO DE RECEITA
# =============================================================================
def distribuir_valor(valor_total, potes: list[Pote]) -> list[dict]:
    """
    Distribui `valor_total` entre os potes proporcionalmente ao percentual,
    em centavos, pelo método do MAIOR RESTO (Hamilton). A soma das parcelas é
    sempre exatamente igual ao total (sem perda de centavos).

    Retorna: [{"pote_id", "percentual", "valor"}] na ordem dos potes.
    """
    total = para_decimal(valor_total).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    if total <= 0:
        raise ErroPotes(["O valor da receita deve ser maior que zero."])

    exigir_configuracao_valida([{"nome": p.nome, "percentual": p.percentual} for p in potes])

    total_centavos = int((total / CENTAVO).to_integral_value())

    # Parte inteira de centavos + resto fracionário de cada pote
    base: list[int] = []
    restos: list[Decimal] = []
    for p in potes:
        bruto = Decimal(total_centavos) * p.percentual / TOTAL_PERCENTUAL
        inteiro = int(bruto.to_integral_value(rounding="ROUND_FLOOR"))
        base.append(inteiro)
        restos.append(bruto - inteiro)

    sobra = total_centavos - sum(base)
    # Maior resto recebe +1 centavo; empate resolvido pela posição do pote
    ordem = sorted(range(len(potes)), key=lambda i: (-restos[i], potes[i].posicao))
    for i in ordem[:sobra]:
        base[i] += 1

    resultado = [
        {
            "pote_id": p.id,
            "percentual": float(p.percentual),
            "valor": float((Decimal(c) * CENTAVO).quantize(CENTAVO)),
        }
        for p, c in zip(potes, base)
    ]

    # Rede de segurança: invariante da distribuição
    soma = sum((Decimal(str(r["valor"])) for r in resultado), Decimal("0"))
    if soma != total:
        raise ErroPotes([f"Falha interna na distribuição: soma {soma} difere de {total}."])
    return resultado


def calcular_previsto_por_renda(renda, potes: list[Pote]) -> dict[str, Decimal]:
    """Valor planejado de cada pote (R$) sobre a renda de referência."""
    total = para_decimal(renda, Decimal("0"))
    if total <= 0:
        return {p.id: Decimal("0.00") for p in potes}
    return {p.id: (total * p.percentual / TOTAL_PERCENTUAL).quantize(CENTAVO, rounding=ROUND_HALF_UP) for p in potes}
