"""
=============================================================================
DemBase v3 — core/potes.py
Regras de negócio dos 6 POTES financeiros e Destinação do Caixa Livre (lógica pura).

  * Nova Arquitetura Unificada:
    1. Custos Fixos (pos 1): Automático / Ajustado à Despesa (ou piso configurável R$ 1.150,00).
    2. Custos Semi Fixos (pos 2), Metas (pos 3), Conhecimento (pos 5): Orçamentos Retidos / Intocáveis.
       O saldo disponível fica retido no pote e NÃO infla o Caixa Livre.
    3. Liberdade Financeira (pos 6) e Prazeres (pos 4): Conectados diretamente ao Slider do Caixa Livre.
       Soma dos 6 potes crava SEMPRE 100,00% da Receita do período.
    4. Blindagem contra Sobra Falsa (Teto Seguro / Pior Dia).
=============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Iterable, Any

# =============================================================================
# CONSTANTES
# =============================================================================
QTD_POTES = 6
TOTAL_PERCENTUAL = Decimal("100")
CENTAVO = Decimal("0.01")
NOME_MAX = 40
PISO_CUSTOS_FIXOS_PADRAO = Decimal("1150.00")

POTES_PADRAO = [
    {"posicao": 1, "nome": "Custos Fixos",         "percentual": Decimal("30"), "cor": "#007AFF"},
    {"posicao": 2, "nome": "Custos Semi Fixos",    "percentual": Decimal("20"), "cor": "#FF69B4"},
    {"posicao": 3, "nome": "Metas",                "percentual": Decimal("15"), "cor": "#800080"},
    {"posicao": 4, "nome": "Prazeres",             "percentual": Decimal("10"), "cor": "#FF7A00"},
    {"posicao": 5, "nome": "Conhecimento",         "percentual": Decimal("5"),  "cor": "#FFD60A"},
    {"posicao": 6, "nome": "Liberdade Financeira", "percentual": Decimal("20"), "cor": "#6C5CE7"},
]

REGRAS_VALIDAS = {"Essencial", "Estilo de Vida", "Investimento"}

REGRA_POR_POSICAO = {
    1: "Essencial",       # Custos Fixos
    2: "Essencial",       # Custos Semi Fixos
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


# =============================================================================
# ARQUITETURA UNIFICADA (6 POTES + CAIXA LIVRE)
# =============================================================================
def _extrair_dados_pote(p: Any, pos_default: int) -> dict:
    if isinstance(p, dict):
        return {
            "id": str(p.get("id") or f"pote-{pos_default}"),
            "posicao": int(p.get("posicao") or pos_default),
            "nome": str(p.get("nome") or f"Pote {pos_default}"),
            "cor": str(p.get("cor") or "#94A3B8"),
            "percentual": float(p.get("percentual") or 0.0),
            "gasto": float(p.get("gasto") or 0.0),
            "qtd_transacoes": int(p.get("qtd_transacoes") or 0),
        }
    return {
        "id": str(getattr(p, "id", None) or f"pote-{pos_default}"),
        "posicao": int(getattr(p, "posicao", pos_default)),
        "nome": str(getattr(p, "nome", f"Pote {pos_default}")),
        "cor": str(getattr(p, "cor", "#94A3B8")),
        "percentual": float(getattr(p, "percentual", 0.0)),
        "gasto": float(getattr(p, "gasto", 0.0)),
        "qtd_transacoes": int(getattr(p, "qtd_transacoes", 0)),
    }


def calcular_arquitetura_unificada_potes(
    receitas: float,
    potes: list[dict | Pote],
    piso_custos_fixos: float = 1150.0,
    slider_pct_investimento: float = 50.0,
    protecao_fluxo: dict | None = None,
    travar_pelo_teto_seguro: bool = True,
    potes_liberados: Iterable[int] | None = None,
) -> dict:
    """
    Unificação Matemática Rigorosa entre os 6 Potes e a Destinação do Caixa Livre:
    1. Custos Fixos (pos 1):
       Limite = max(gasto real, piso de R$ 1.150,00). Percentual calculado dinamicamente sobre a receita.
    2. Custos Semi Fixos (pos 2), Metas (pos 3), Conhecimento (pos 5):
       Orçamentos retidos / intocáveis. Os saldos disponíveis pertencem aos potes e são retidos,
       sem inflar o Caixa Livre. Se houver estouro (gasto > limite), o excesso abate do Caixa Livre.
    3. Liberdade Financeira (pos 6) e Prazeres (pos 4):
       A fatia restante da receita é o orçamento do Caixa Livre. O slider divide essa fatia
       entre Liberdade Financeira (Guardar/Investir) e Prazeres (Livre sem Culpa).
       A soma dos 6 potes crava SEMPRE 100,00%!
    4. Desconta os gastos de Prazeres e aportes de Liberdade Financeira, respeitando
       a trava de Teto Seguro do Pior Dia.
    5. `potes_liberados` (posições 2, 3 e/ou 5): a sobra +Disponível desses potes manuais foi
       liberada pelo usuário. O teto do pote é ajustado ao Gasto Real do mês e a folga ociosa
       migra para o Caixa Livre (dividida entre Liberdade e Prazeres conforme o Slider).
    """
    rec = round(max(0.0, float(receitas or 0.0)), 2)
    piso_fix = round(max(0.0, float(piso_custos_fixos if piso_custos_fixos is not None else 1150.0)), 2)
    s_inv = round(max(0.0, min(100.0, float(slider_pct_investimento if slider_pct_investimento is not None else 50.0))), 1)
    s_livre = round(100.0 - s_inv, 1)

    # Organiza os 6 potes por posição (1..6)
    mapa_potes: dict[int, dict] = {}
    if potes:
        for p in potes:
            dados = _extrair_dados_pote(p, len(mapa_potes) + 1)
            mapa_potes[dados["posicao"]] = dados

    padrao_por_pos = {d["posicao"]: d for d in POTES_PADRAO}
    for pos in range(1, 7):
        if pos not in mapa_potes:
            d_pad = padrao_por_pos[pos]
            mapa_potes[pos] = {
                "id": f"pote-padrao-{pos}",
                "posicao": pos,
                "nome": d_pad["nome"],
                "cor": d_pad["cor"],
                "percentual": float(d_pad["percentual"]),
                "gasto": 0.0,
                "qtd_transacoes": 0,
            }

    p1 = mapa_potes[1]
    p2 = mapa_potes[2]
    p3 = mapa_potes[3]
    p4 = mapa_potes[4]
    p5 = mapa_potes[5]
    p6 = mapa_potes[6]

    gasto_total = round(sum(mapa_potes[pos]["gasto"] for pos in range(1, 7)), 2)

    # 1. Custos Fixos (pos 1): Automático / Ajustado à Despesa
    g1 = p1["gasto"]
    if rec > 0:
        lim1 = max(g1, piso_fix)
        pct1 = min(100.0, round((lim1 / rec) * 100.0, 2))
    else:
        lim1 = 0.0
        pct1 = 0.0

    # 2. Custos Semi Fixos (pos 2), Metas (pos 3), Conhecimento (pos 5): Orçamentos Retidos / Intocáveis
    pct2 = round(max(0.0, min(100.0, p2["percentual"])), 2)
    pct3 = round(max(0.0, min(100.0, p3["percentual"])), 2)
    pct5 = round(max(0.0, min(100.0, p5["percentual"])), 2)

    lim2 = round(rec * (pct2 / 100.0), 2)
    lim3 = round(rec * (pct3 / 100.0), 2)
    lim5 = round(rec * (pct5 / 100.0), 2)

    g2 = p2["gasto"]
    g3 = p3["gasto"]
    g5 = p5["gasto"]

    # 2.1 Liberação de sobra: teto = gasto real; a folga ociosa vai para o Caixa Livre
    liberados = {int(x) for x in (potes_liberados or [])} & {2, 3, 5}
    liberado_valor = {2: 0.0, 3: 0.0, 5: 0.0}
    if rec > 0:
        if 2 in liberados and lim2 - g2 > 0.005:
            liberado_valor[2] = round(lim2 - g2, 2)
            lim2 = round(g2, 2)
            pct2 = round((lim2 / rec) * 100.0, 2)
        if 3 in liberados and lim3 - g3 > 0.005:
            liberado_valor[3] = round(lim3 - g3, 2)
            lim3 = round(g3, 2)
            pct3 = round((lim3 / rec) * 100.0, 2)
        if 5 in liberados and lim5 - g5 > 0.005:
            liberado_valor[5] = round(lim5 - g5, 2)
            lim5 = round(g5, 2)
            pct5 = round((lim5 / rec) * 100.0, 2)
    tem_liberacao = any(v > 0 for v in liberado_valor.values())

    retido2 = max(0.0, round(lim2 - g2, 2))
    retido3 = max(0.0, round(lim3 - g3, 2))
    retido5 = max(0.0, round(lim5 - g5, 2))
    retido_total = round(retido2 + retido3 + retido5 + max(0.0, round(lim1 - g1, 2)), 2)

    excesso_outros = round(
        max(0.0, g2 - lim2) + max(0.0, g3 - lim3) + max(0.0, g5 - lim5) + max(0.0, g1 - lim1), 2
    )

    # 3. Orçamento Restante do Caixa Livre (Liberdade Financeira + Prazeres)
    soma_retidos_pct = round(pct1 + pct2 + pct3 + pct5, 2)
    pct_caixa_livre = max(0.0, round(100.0 - soma_retidos_pct, 2))
    if tem_liberacao:
        # Valor exato (sem perda de centavos por arredondamento de percentuais)
        teto_caixa_livre = max(0.0, round(rec - lim1 - lim2 - lim3 - lim5, 2))
    else:
        teto_caixa_livre = round(rec * (pct_caixa_livre / 100.0), 2)

    # 4. Divisão do Slider entre Prazeres (pos 4) e Liberdade Financeira (pos 6)
    pct4 = round(pct_caixa_livre * (s_livre / 100.0), 2)
    lim4 = round(teto_caixa_livre * (s_livre / 100.0), 2)

    # Liberdade Financeira absorve a diferença para fechar SEMPRE exatamente 100,00%
    pct6 = round(100.0 - (pct1 + pct2 + pct3 + pct4 + pct5), 2)
    lim6 = max(0.0, round(teto_caixa_livre - lim4, 2))

    g4 = p4["gasto"]
    g6 = p6["gasto"]

    disp4_proj = max(0.0, round(lim4 - g4 - excesso_outros, 2))
    disp6_proj = max(0.0, round(lim6 - g6, 2))
    sobra_livre_real = round(disp4_proj + disp6_proj, 2)

    # 5. Blindagem contra Sobra Falsa (Teto Seguro / Pior Dia)
    pf = protecao_fluxo if isinstance(protecao_fluxo, dict) else {}
    tem_pf = bool(pf and ("teto_seguro_gasto" in pf or "menor_saldo_futuro" in pf))
    if tem_pf:
        menor_saldo = round(float(pf.get("menor_saldo_futuro", sobra_livre_real) or 0.0), 2)
        teto_seguro = round(max(0.0, min(sobra_livre_real, float(pf.get("teto_seguro_gasto", sobra_livre_real) or 0.0))), 2)
        sobra_falsa = round(max(0.0, sobra_livre_real - teto_seguro), 2)
        tem_armadilha = bool(sobra_falsa > 0.005 or menor_saldo < -0.005)
        fica_negativo = bool(menor_saldo < -0.005)
        dt_gargalo = pf.get("data_gargalo")
        prox_entrada_dt = pf.get("proxima_entrada_data")
        prox_entrada_val = round(float(pf.get("proxima_entrada_valor", 0.0) or 0.0), 2)
    else:
        menor_saldo = sobra_livre_real
        teto_seguro = sobra_livre_real
        sobra_falsa = 0.0
        tem_armadilha = False
        fica_negativo = sobra_livre_real < -0.005
        dt_gargalo = None
        prox_entrada_dt = None
        prox_entrada_val = 0.0

    # Aplicação do Teto Seguro aos dois potes do Caixa Livre
    if travar_pelo_teto_seguro and tem_armadilha and sobra_livre_real > 0:
        val_inv_seguro = round(teto_seguro * (s_inv / 100.0), 2)
        val_livre_seguro = round(teto_seguro - val_inv_seguro, 2)
        disp4_efetivo = min(disp4_proj, val_livre_seguro)
        disp6_efetivo = min(disp6_proj, val_inv_seguro)
    else:
        val_inv_seguro = disp6_proj
        val_livre_seguro = disp4_proj
        disp4_efetivo = disp4_proj
        disp6_efetivo = disp6_proj

    # 6. Montagem dos 6 Potes Consolidados
    potes_resultado = [
        {
            "id": p1["id"],
            "posicao": 1,
            "nome": p1["nome"],
            "cor": p1["cor"],
            "percentual": pct1,
            "previsto": lim1,
            "gasto": g1,
            "qtd_transacoes": p1["qtd_transacoes"],
            "restante": round(lim1 - g1, 2),
            "tipo_comportamento": "automatico_fixo",
            "piso_configurado": piso_fix,
        },
        {
            "id": p2["id"],
            "posicao": 2,
            "nome": p2["nome"],
            "cor": p2["cor"],
            "percentual": pct2,
            "previsto": lim2,
            "gasto": g2,
            "qtd_transacoes": p2["qtd_transacoes"],
            "restante": round(lim2 - g2, 2),
            "tipo_comportamento": "retido_intocavel",
            "disponivel_retido": retido2,
            "liberavel": bool(retido2 > 0.005),
            "liberado": bool(liberado_valor[2] > 0 or 2 in liberados),
            "liberado_valor": liberado_valor[2],
        },
        {
            "id": p3["id"],
            "posicao": 3,
            "nome": p3["nome"],
            "cor": p3["cor"],
            "percentual": pct3,
            "previsto": lim3,
            "gasto": g3,
            "qtd_transacoes": p3["qtd_transacoes"],
            "restante": round(lim3 - g3, 2),
            "tipo_comportamento": "retido_intocavel",
            "disponivel_retido": retido3,
            "liberavel": bool(retido3 > 0.005),
            "liberado": bool(liberado_valor[3] > 0 or 3 in liberados),
            "liberado_valor": liberado_valor[3],
        },
        {
            "id": p4["id"],
            "posicao": 4,
            "nome": p4["nome"],
            "cor": p4["cor"],
            "percentual": pct4,
            "previsto": lim4,
            "gasto": g4,
            "qtd_transacoes": p4["qtd_transacoes"],
            "restante": round(lim4 - g4, 2),
            "tipo_comportamento": "caixa_livre_prazeres",
            "disponivel_efetivo": disp4_efetivo,
        },
        {
            "id": p5["id"],
            "posicao": 5,
            "nome": p5["nome"],
            "cor": p5["cor"],
            "percentual": pct5,
            "previsto": lim5,
            "gasto": g5,
            "qtd_transacoes": p5["qtd_transacoes"],
            "restante": round(lim5 - g5, 2),
            "tipo_comportamento": "retido_intocavel",
            "disponivel_retido": retido5,
            "liberavel": bool(retido5 > 0.005),
            "liberado": bool(liberado_valor[5] > 0 or 5 in liberados),
            "liberado_valor": liberado_valor[5],
        },
        {
            "id": p6["id"],
            "posicao": 6,
            "nome": p6["nome"],
            "cor": p6["cor"],
            "percentual": pct6,
            "previsto": lim6,
            "gasto": g6,
            "qtd_transacoes": p6["qtd_transacoes"],
            "restante": round(lim6 - g6, 2),
            "tipo_comportamento": "caixa_livre_investimento",
            "disponivel_efetivo": disp6_efetivo,
        },
    ]

    soma_pct = round(sum(p["percentual"] for p in potes_resultado), 2)

    return {
        "receitas": rec,
        "despesas_totais": gasto_total,
        "saldo": round(rec - gasto_total, 2),
        "potes": potes_resultado,
        "soma_percentuais": soma_pct,
        "piso_custos_fixos": piso_fix,
        "retido_outros_potes": retido_total,
        "caixa_livre": {
            "teto_orcamento": teto_caixa_livre,
            "pct_orcamento": pct_caixa_livre,
            "pct_slider_investimento": s_inv,
            "pct_slider_livre": s_livre,
            "sobra_livre_projetada": sobra_livre_real,
            "sobra_livre_disponivel": round(disp4_efetivo + disp6_efetivo, 2),
            "prazeres_nome": p4["nome"],
            "prazeres_teto": lim4,
            "prazeres_gasto": g4,
            "prazeres_restante_projetado": disp4_proj,
            "prazeres_disponivel_hoje": disp4_efetivo,
            "liberdade_nome": p6["nome"],
            "liberdade_teto": lim6,
            "liberdade_gasto": g6,
            "liberdade_restante_projetado": disp6_proj,
            "liberdade_disponivel_hoje": disp6_efetivo,
        },
        "blindagem": {
            "menor_saldo_futuro": menor_saldo,
            "teto_seguro_gasto": teto_seguro,
            "sobra_falsa_travada": sobra_falsa,
            "tem_armadilha_fluxo": tem_armadilha,
            "fica_negativo_no_meio": fica_negativo,
            "data_gargalo": dt_gargalo,
            "proxima_entrada_data": prox_entrada_dt,
            "proxima_entrada_valor": prox_entrada_val,
            "travar_pelo_teto_seguro": bool(travar_pelo_teto_seguro),
        },
    }
