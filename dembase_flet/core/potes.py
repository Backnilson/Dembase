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

REGRAS_VALIDAS = {"Essencial", "Estilo de Vida", "Investimento"}

REGRA_POR_POSICAO = {
    1: "Essencial",       # Custos Fixos
    2: "Essencial",       # Conforto / Custos Semi Fixos
    3: "Investimento",    # Metas
    4: "Estilo de Vida",  # Prazeres
    5: "Investimento",    # Conhecimento
    6: "Investimento",    # Liberdade Financeira
}

REGRA_POR_ID = {
    "2df4dd2f-4353-42cc-a5c9-8983085a5301": "Essencial",       # Custos Fixos
    "da6e1d2b-c611-481d-b48d-065cc5d584b4": "Essencial",       # Custos Semi Fixos
    "986da9e8-3042-4562-b1df-c1f5cf0138b9": "Investimento",    # Metas
    "c82b0736-fb01-419f-8155-923ebfec82b2": "Estilo de Vida",  # Prazeres
    "1f1f7449-d985-4c2a-b807-0570a5526614": "Investimento",    # Conhecimento
    "34a47be1-9879-46bd-96b1-4082703bf388": "Investimento",    # Liberdade Financeira
}


def _regra_por_nome(nome: str) -> str:
    n = (nome or "").lower().strip()
    if any(k in n for k in ("fix", "confort", "semi", "essenc", "morad", "aliment", "saud", "transp")):
        return "Essencial"
    if any(k in n for k in ("prazer", "estilo", "lazer", "vida", "desejo", "restaur", "divers")):
        return "Estilo de Vida"
    if any(k in n for k in ("meta", "conhec", "liberdad", "invest", "poupanc", "futuro", "reserva", "educac")):
        return "Investimento"
    return "Essencial"


def obter_regra_pote(pote_ref: str | int | None, potes: list | None = None) -> str:
    """
    Retorna o valor válido do enum regra_financeira ('Essencial', 'Estilo de Vida', 'Investimento')
    a partir de um pote_id (UUID), posição (1-6), nome do pote ou da própria regra já existente.
    Garante que NUNCA um UUID ou string inválida seja gravado na coluna `regra`.
    """
    if not pote_ref:
        return "Essencial"

    texto = str(pote_ref).strip()
    if texto in REGRAS_VALIDAS:
        return texto

    # Se já é um ID canônico padrão
    if texto.lower() in REGRA_POR_ID:
        return REGRA_POR_ID[texto.lower()]

    # Se uma lista de potes foi informada (ou cache), busca correspondência por id, posição ou nome
    if potes:
        for p in potes:
            pid = str(getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else "") or "")
            pos = getattr(p, "posicao", None) or (p.get("posicao") if isinstance(p, dict) else None)
            pnome = str(getattr(p, "nome", None) or (p.get("nome") if isinstance(p, dict) else "") or "")
            if pid and pid.lower() == texto.lower():
                if pos is not None:
                    try:
                        pos_int = int(pos)
                        if pos_int in REGRA_POR_POSICAO:
                            return REGRA_POR_POSICAO[pos_int]
                    except (ValueError, TypeError):
                        pass
                return _regra_por_nome(pnome)
            if pnome and pnome.lower() == texto.lower():
                if pos is not None:
                    try:
                        pos_int = int(pos)
                        if pos_int in REGRA_POR_POSICAO:
                            return REGRA_POR_POSICAO[pos_int]
                    except (ValueError, TypeError):
                        pass
                return _regra_por_nome(pnome)
            if pos is not None and str(pos) == texto:
                try:
                    return REGRA_POR_POSICAO.get(int(pos), "Essencial")
                except (ValueError, TypeError):
                    pass

    return _regra_por_nome(texto)


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
