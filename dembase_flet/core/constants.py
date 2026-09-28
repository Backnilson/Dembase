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
TIPOS_LANCAMENTO = ["Receita", "Despesa"]

SUBTIPOS_RECEITA  = ["Receita", "Entrada"]
SUBTIPOS_DESPESA  = ["Despesa", "Saída", "Dívida", "Empréstimo"]

# Receita NÃO aceita Crédito (não faz sentido receber em cartão de crédito)
FORMAS_RECEITA  = ["Débito", "Pix", "Dinheiro"]
FORMAS_DESPESA  = ["Crédito", "Débito", "Pix", "Dinheiro"]

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
