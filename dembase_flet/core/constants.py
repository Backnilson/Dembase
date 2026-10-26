"""
=============================================================================
DemBase v3 — core/constants.py
Constantes de negócio: opções de dropdowns, regras 50/30/20 e frases.
Esta é a única fonte de verdade sobre as regras de negócio do domínio.
=============================================================================
"""
from datetime import datetime, date

# =============================================================================
# DROPDOWNS E OPÇÕES DE NEGÓCIO
# =============================================================================
TIPOS_LANCAMENTO = ["Receita", "Despesa", "Transferência"]

SUBTIPOS_RECEITA        = ["Receita", "Entrada"]
SUBTIPOS_DESPESA        = ["Despesa", "Saída", "Dívida", "Empréstimo"]
SUBTIPOS_TRANSFERENCIA  = ["Transferência", "TED", "DOC", "Pix"]

# Receita e Transferência NÃO aceitam Crédito
FORMAS_RECEITA        = ["Débito", "Pix", "Dinheiro"]
FORMAS_DESPESA        = ["Crédito", "Débito", "Pix", "Dinheiro"]
FORMAS_TRANSFERENCIA  = ["Débito", "Pix", "Dinheiro"]

STATUS_OPCOES = ["Pago", "Pendente"]

# Regra 50/30/20 — só aparece em Despesas
REGRAS_5030 = ["Essencial", "Estilo de Vida", "Investimento"]
REGRAS_META = {
    "Essencial":       0.50,
    "Estilo de Vida":  0.30,
    "Investimento":    0.20,
}

# =============================================================================
# FRASES MOTIVACIONAIS (rotacionadas no Dashboard)
# =============================================================================
FRASES_MOTIVACIONAIS = [
    "O segredo da riqueza não está em ganhar muito, mas em gastar com sabedoria.",
    "Cuide dos centavos e os reais cuidarão de si mesmos.",
    "Não é sobre quanto você ganha, é sobre quanto você mantém.",
    "Liberdade financeira é construída um dia de cada vez.",
    "O melhor momento para começar a economizar foi ontem. O segundo melhor é agora.",
    "Disciplina hoje, liberdade amanhã.",
    "Seu eu do futuro agradecerá as decisões financeiras que você toma hoje.",
    "Pequenos gastos diários se tornam grandes fortunas perdidas.",
    "Investir em conhecimento é o ativo que nunca se deprecia.",
    "Uma vida financeira saudável não é sorte, é hábito.",
]

# =============================================================================
# HELPERS DE DATA
# =============================================================================
def inicio_mes_atual() -> date:
    hoje = date.today()
    return date(hoje.year, hoje.month, 1)

def hoje() -> date:
    return date.today()

def formatar_data_br(d: date | str) -> str:
    """Converte date ou string ISO para formato brasileiro DD/MM/AAAA."""
    if isinstance(d, str):
        d = datetime.strptime(d[:10], "%Y-%m-%d").date()
    return d.strftime("%d/%m/%Y")

def formatar_moeda(valor: float) -> str:
    """Formata valor para o padrão monetário brasileiro."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def parse_moeda_seguro(val: object) -> float:
    """
    Converte qualquer valor (string, int, float, None, formatado em PT-BR ou EN-US)
    para float de forma ultra segura, tratando números negativos e símbolos monetários.
    Exemplos:
      "-150,00" -> -150.0
      "R$ -150,00" -> -150.0
      "-R$ 150,00" -> -150.0
      "R$ 1.250,50" -> 1250.5
      "-1.250,50" -> -1250.5
      None -> 0.0
    """
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        try:
            import math
            if math.isnan(val) or math.isinf(val):
                return 0.0
            return round(float(val), 2)
        except Exception:
            return 0.0

    s = str(val).strip()
    if not s:
        return 0.0

    # Normalizar espaços não-quebráveis
    s = s.replace("\u00a0", " ").replace("\xa0", " ").strip()

    # Detectar se é negativo
    negativo = False
    if s.startswith("(") and s.endswith(")"):
        negativo = True
        s = s[1:-1].strip()
    if "-" in s:
        negativo = True
        s = s.replace("-", "").strip()

    # Remover símbolos monetários e prefixos
    s = s.replace("R$", "").replace("r$", "").replace("$", "").strip()

    if not s:
        return 0.0

    # Se contiver vírgula e ponto (ex: 1.250,50 ou 1,250.50)
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif "." in s:
        partes = s.split(".")
        if len(partes) > 2:
            s = "".join(partes)

    import re
    s_limpo = re.sub(r"[^\d.]", "", s)
    if not s_limpo:
        return 0.0

    if s_limpo.count(".") > 1:
        partes = s_limpo.split(".")
        s_limpo = "".join(partes[:-1]) + "." + partes[-1]

    try:
        resultado = float(s_limpo)
        if negativo:
            resultado = -resultado
        return round(resultado, 2)
    except (ValueError, TypeError):
        return 0.0


def formatar_moeda_input(valor: object) -> str:
    """
    Formata valor para exibição limpa em TextField monetário (sem prefixo 'R$ ').
    Exemplos:
      -150.5 -> "-150,50"
      1250.0 -> "1.250,00"
      None -> "0,00"
    """
    num = parse_moeda_seguro(valor)
    s = f"{abs(num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-{s}" if num < 0 else s


# =============================================================================
# HELPERS DE SESSÃO (FLET 1.0.1 — Session.store compatível)
# =============================================================================
def session_get(page, key: str, default=None):
    """Obtém um valor da sessão de forma segura no Flet 1.0.1."""
    try:
        if hasattr(page, "session") and page.session is not None:
            store = getattr(page.session, "store", None)
            if store:
                val = store.get(key)
                return val if val is not None else default
            if isinstance(page.session, dict):
                return page.session.get(key, default)
            if hasattr(page.session, "get"):
                return page.session.get(key, default)
    except Exception:
        pass
    return default


def session_set(page, key: str, value):
    """Define um valor na sessão de forma segura no Flet 1.0.1."""
    try:
        if hasattr(page, "session") and page.session is not None:
            store = getattr(page.session, "store", None)
            if store:
                store.set(key, value)
                return
            if isinstance(page.session, dict):
                page.session[key] = value
                return
            if hasattr(page.session, "set"):
                page.session.set(key, value)
                return
    except Exception:
        pass


def session_remove(page, key: str):
    """Remove uma chave da sessão de forma segura no Flet 1.0.1."""
    try:
        if hasattr(page, "session") and page.session is not None:
            store = getattr(page.session, "store", None)
            if store:
                if store.contains_key(key):
                    store.remove(key)
                return
            if isinstance(page.session, dict):
                page.session.pop(key, None)
                return
            if hasattr(page.session, "remove"):
                page.session.remove(key)
                return
    except Exception:
        pass


def session_pop(page, key: str, default=None):
    """Obtém e remove uma chave da sessão de forma segura no Flet 1.0.1."""
    val = session_get(page, key, default)
    session_remove(page, key)
    return val


def session_clear(page):
    """Limpa toda a sessão de forma segura no Flet 1.0.1."""
    try:
        if hasattr(page, "session") and page.session is not None:
            store = getattr(page.session, "store", None)
            if store:
                store.clear()
                return
            if isinstance(page.session, dict):
                page.session.clear()
                return
            if hasattr(page.session, "clear"):
                page.session.clear()
                return
    except Exception:
        pass

