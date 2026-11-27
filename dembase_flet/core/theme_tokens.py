"""
=============================================================================
DemBase v3 — core/theme_tokens.py  (Flet 1.0.1)
Sistema centralizado de Cores Adaptativas (Dark & Light Mode - WCAG AA),
Emojis Semânticos e Helpers de Contraste para 6 Potes, Categorias e Badges.
=============================================================================
"""
from __future__ import annotations

import hashlib
import unicodedata

from core import theme as T


def _norm(texto: str | None) -> str:
    s = str(texto or "").strip().lower()
    return "".join(
        ch for ch in unicodedata.normalize("NFD", s)
        if unicodedata.category(ch) != "Mn"
    )


def _eh_emoji_real(texto: str | None) -> bool:
    """Retorna True se a string começa com um caractere Unicode não-ASCII (emoji)."""
    s = str(texto or "").strip()
    if not s or len(s) > 8:
        return False
    return ord(s[0]) > 127


# =============================================================================
# 1. PALETA CURADA ADAPTATIVA (Dark ~400 luminoso | Light ~600/700 saturado)
# =============================================================================
PALETA_CATEGORIAS: list[dict[str, str]] = [
    {"id": "sky",     "nome": "Azul Celeste",  "dark": "#38BDF8", "light": "#0284C7"},
    {"id": "teal",    "nome": "Turquesa",      "dark": "#2DD4BF", "light": "#0F766E"},
    {"id": "violet",  "nome": "Violeta",       "dark": "#A78BFA", "light": "#7C3AED"},
    {"id": "orange",  "nome": "Laranja Coral", "dark": "#FB923C", "light": "#EA580C"},
    {"id": "rose",    "nome": "Vermelho Rubi", "dark": "#FB7185", "light": "#E11D48"},
    {"id": "fuchsia", "nome": "Fúcsia",        "dark": "#E879F9", "light": "#C026D3"},
    {"id": "cyan",    "nome": "Ciano",         "dark": "#22D3EE", "light": "#0891B2"},
    {"id": "blue",    "nome": "Azul Royal",    "dark": "#60A5FA", "light": "#1D4ED8"},
    {"id": "amber",   "nome": "Âmbar",         "dark": "#FBBF24", "light": "#D97706"},
    {"id": "mint",    "nome": "Verde Menta",   "dark": "#34D399", "light": "#059669"},
    {"id": "indigo",  "nome": "Índigo",        "dark": "#818CF8", "light": "#4F46E5"},
    {"id": "pink",    "nome": "Rosa",          "dark": "#F472B6", "light": "#DB2777"},
]

_PALETA_POR_ID = {c["id"]: c for c in PALETA_CATEGORIAS}

# Mapa reverso de hex (dark ou light) -> entrada da paleta para adaptação automática
_HEX_PARA_FAMILIA: dict[str, dict[str, str]] = {}
for _c in PALETA_CATEGORIAS:
    _HEX_PARA_FAMILIA[_c["dark"].lower()] = _c
    _HEX_PARA_FAMILIA[_c["light"].lower()] = _c

# Cores genéricas antigas que devem ser substituídas pelo mapa semântico/determinístico
_CORES_GENERICAS = {
    "", "#64748b", "#94a3b8", "#00e676", "#00a152", "#00c853", "#10b981",
}

# =============================================================================
# 2. 6 POTES FINANCEIROS (Emoji + Cores Calibradas Dark/Light + Micro-Dicas)
# =============================================================================
MAPA_POTES_VISUAL: dict[int, dict[str, str]] = {
    1: {
        "nome": "Contas Fixas", "emoji": "🏠", "dark": "#3B82F6", "light": "#2563EB",
        "dica": "Obrigações mensais e base da casa (aluguel, contas, mercado, dívidas).",
    },
    2: {
        "nome": "Dia a Dia", "emoji": "⚡", "dark": "#EC4899", "light": "#DB2777",
        "dica": "Gastos variáveis da rotina (transporte, academia, beleza, assinaturas, diversos).",
    },
    3: {
        "nome": "Metas", "emoji": "🎯", "dark": "#A855F7", "light": "#7C3AED",
        "dica": "Projetos, equipamentos (DJ/tech), viagens planejadas e quitações.",
    },
    4: {
        "nome": "Prazeres", "emoji": "🎉", "dark": "#F97316", "light": "#EA580C",
        "dica": "Gastar sem culpa: cafés, delivery, bares, passeios e mimos.",
    },
    5: {
        "nome": "Evolução", "emoji": "📚", "dark": "#FACC15", "light": "#B45309",
        "dica": "Cursos, livros, IA, softwares e crescimento pessoal ou profissional.",
    },
    6: {
        "nome": "Liberdade", "emoji": "🚀", "dark": "#818CF8", "light": "#4F46E5",
        "dica": "Aportes, reserva de emergência e construção de patrimônio.",
    },
}


def _resolver_pos_pote(posicao: int | None, nome: str | None = None) -> int | None:
    if posicao in MAPA_POTES_VISUAL:
        return int(posicao)
    n = _norm(nome)
    if not n:
        return None
    if "dia a dia" in n or "semi" in n or "confort" in n:
        return 2
    if "fixo" in n or "fixa" in n:
        return 1
    if "meta" in n:
        return 3
    if "prazer" in n or "livre" in n:
        return 4
    if "evoluc" in n or "conhec" in n or "estudo" in n:
        return 5
    if "liberdade" in n or "invest" in n:
        return 6
    return None


def emoji_pote(posicao: int | None = None, nome: str | None = None) -> str:
    pos = _resolver_pos_pote(posicao, nome)
    if pos in MAPA_POTES_VISUAL:
        return MAPA_POTES_VISUAL[pos]["emoji"]
    return "🏺"


def dica_pote(posicao: int | None = None, nome: str | None = None) -> str:
    pos = _resolver_pos_pote(posicao, nome)
    if pos in MAPA_POTES_VISUAL:
        return MAPA_POTES_VISUAL[pos]["dica"]
    return ""


def nome_pote_padrao(posicao: int) -> str:
    if posicao in MAPA_POTES_VISUAL:
        return MAPA_POTES_VISUAL[posicao]["nome"]
    return f"Pote {posicao}"


def cor_pote_adaptativa(
    posicao: int | None = None,
    nome: str | None = None,
    cor_salva: str | None = None,
    is_dark: bool | None = None,
) -> str:
    escuro = T.IS_DARK if is_dark is None else bool(is_dark)
    pos = _resolver_pos_pote(posicao, nome)
    if pos in MAPA_POTES_VISUAL:
        return MAPA_POTES_VISUAL[pos]["dark" if escuro else "light"]
    return adaptar_cor(cor_salva or "#60A5FA", is_dark=escuro)


# =============================================================================
# 3. CATEGORIAS (Mapa Semântico das 9 Macro-Categorias + Fallback Determinístico)
# =============================================================================
_REGRAS_CATEGORIAS: list[tuple[tuple[str, ...], str, str]] = [
    (("sem categoria",),                                                      "❓", "gray"),
    (("renda", "salario", "freela", "bonus"),                                 "💰", "mint"),
    (("moradia", "casa", "aluguel", "condom"),                                "🏡", "sky"),
    (("aliment", "mercado", "supermercado", "restaurante", "ifood", "lanche"), "🍔", "amber"),
    (("transporte", "auto", "moto", "carro", "combust", "uber", "gasolina"),  "🚗", "rose"),
    (("saude", "bem-estar", "drogaria", "farmacia", "medico", "dentista", "academia"), "💊", "teal"),
    (("lazer", "viagem", "viagens", "entretenimento", "cinema", "show", "festa", "bebida"), "🍻", "orange"),
    (("educac", "carreira", "curso", "livro", "faculdade", "escola", "dj"),   "🎓", "indigo"),
    (("pessoal", "familia", "denilson", "erika", "brayan", "lais", "pet", "presente", "vestuario"), "👨‍👩‍👦", "violet"),
    (("financas", "invest", "acao", "acoes", "renda fixa", "cdb", "tesouro", "divida", "emprestimo", "juros", "fatura"), "📈", "blue"),
]

EMOJIS_CURADOS: list[str] = [
    "💰", "🏡", "🍔", "🚗", "💊", "🍻", "🎓", "👨‍👩‍👦", "📈",
    "🏠", "⚡", "🎯", "🎉", "📚", "🚀", "🏍️", "🎁", "✈️",
    "🌐", "🐶", "💳", "💻", "🎧", "🛍️", "🛒", "☕", "🏋️",
    "🎬", "📱", "🔧", "🏦", "🧾", "🏷️", "❓",
]


def _familia_por_nome(nome: str | None) -> tuple[str, str]:
    n = _norm(nome)
    if not n:
        return "❓", "gray"
    for palavras, emoji, fam in _REGRAS_CATEGORIAS:
        if any(p in n for p in palavras):
            return emoji, fam
    # Fallback determinístico por hash estável do nome (nunca repete tudo em cinza/verde)
    idx = int(hashlib.md5(n.encode("utf-8")).hexdigest()[:8], 16) % len(PALETA_CATEGORIAS)
    return "🏷️", PALETA_CATEGORIAS[idx]["id"]


def emoji_categoria(nome: str | None, icone_salvo: str | None = None) -> str:
    if _eh_emoji_real(icone_salvo):
        return str(icone_salvo).strip()
    emoji, _ = _familia_por_nome(nome)
    return emoji


def adaptar_cor(cor_hex: str | None, is_dark: bool | None = None) -> str:
    escuro = T.IS_DARK if is_dark is None else bool(is_dark)
    c = str(cor_hex or "").strip()
    if not c.startswith("#") or len(c) < 7:
        return "#94A3B8" if escuro else "#64748B"
    fam = _HEX_PARA_FAMILIA.get(c[:7].lower())
    if fam:
        return fam["dark" if escuro else "light"]
    return c[:7]


def cor_categoria_adaptativa(
    nome: str | None,
    cor_salva: str | None = None,
    is_dark: bool | None = None,
) -> str:
    escuro = T.IS_DARK if is_dark is None else bool(is_dark)
    n = _norm(nome)
    if n in ("", "sem categoria"):
        return "#94A3B8" if escuro else "#64748B"

    c_raw = str(cor_salva or "").strip().lower()
    if c_raw and c_raw not in _CORES_GENERICAS:
        return adaptar_cor(c_raw, is_dark=escuro)

    _, fam_id = _familia_por_nome(nome)
    if fam_id == "gray":
        return "#94A3B8" if escuro else "#64748B"
    fam = _PALETA_POR_ID.get(fam_id, PALETA_CATEGORIAS[0])
    return fam["dark" if escuro else "light"]


# =============================================================================
# 4. HELPER DE CONTRASTE PARA BADGES / PÍLULAS (WCAG AA)
# =============================================================================
def estilo_badge_adaptativo(
    cor_hex: str | None,
    is_dark: bool | None = None,
    solido: bool = False,
) -> tuple[str, str]:
    """
    Retorna (bgcolor, text_color) calibrados para Dark & Light Mode:
    - Suave (padrão): fundo ~15% opacidade no Dark / ~12% no Light + texto da mesma família.
    - Sólido: fundo cheio + texto branco (ou escuro se a cor for muito clara).
    """
    escuro = T.IS_DARK if is_dark is None else bool(is_dark)
    cor = adaptar_cor(cor_hex, is_dark=escuro)
    if solido:
        try:
            r = int(cor[1:3], 16)
            g = int(cor[3:5], 16)
            b = int(cor[5:7], 16)
            lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
            txt = "#0F172A" if lum > 0.68 else "#FFFFFF"
        except Exception:
            txt = "#FFFFFF"
        return cor, txt

    alpha = "26" if escuro else "1F"  # ~15% no Dark, ~12% no Light
    return f"{cor}{alpha}", cor
