"""
=============================================================================
DemBase v3 — views/widgets/dashboard_charts.py  (Flet 1.0.1)
Catálogo Modular de Gráficos do Dashboard (Plug-and-Play).
Permite renderizar N gráficos responsivos em Grid (1 col Mobile / 2 cols Desktop)
e escolher quais gráficos exibir nas Configurações.
=============================================================================
"""
from __future__ import annotations
import flet as ft
from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_moeda
from core.router import navegar


# Catálogo oficial de gráficos disponíveis para o Dashboard
DASHBOARD_CHARTS_CATALOG: list[dict] = [
    {
        "id": "regra_5030",
        "titulo": "Regra 50 / 30 / 20",
        "subtitulo": "Equilíbrio entre Essencial, Estilo de Vida e Investimentos",
        "icone": ft.Icons.PIE_CHART_ROUNDED,
        "cor": "#10B981",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "despesas_categoria",
        "titulo": "Despesas por Categoria",
        "subtitulo": "Distribuição das saídas no período selecionado",
        "icone": ft.Icons.DONUT_LARGE_ROUNDED,
        "cor": "#EF4444",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "fluxo_diario",
        "titulo": "Ritmo Diário no Período",
        "subtitulo": "Picos de movimentação dia a dia no intervalo ativo",
        "icone": ft.Icons.EQUALIZER_ROUNDED,
        "cor": "#3B82F6",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "balanco_semestral",
        "titulo": "Evolução Mensal (6 Meses)",
        "subtitulo": "Comparativo histórico de Receitas vs. Despesas",
        "icone": ft.Icons.STACKED_BAR_CHART_ROUNDED,
        "cor": "#8B5CF6",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "receitas_categoria",
        "titulo": " Fontes de Receita",
        "subtitulo": "Composição das entradas no período filtrado",
        "icone": ft.Icons.TRENDING_UP_ROUNDED,
        "cor": "#10B981",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "formas_e_cartoes",
        "titulo": "Meios de Pagamento & Cartões",
        "subtitulo": "Uso por modalidade (Pix, Crédito, Débito) e limite de cartões",
        "icone": ft.Icons.CREDIT_SCORE_ROUNDED,
        "cor": "#F59E0B",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
]

# Por padrão, todos os 6 gráficos vêm habilitados no início
GRAFICOS_PADRAO_IDS: list[str] = [item["id"] for item in DASHBOARD_CHARTS_CATALOG]


def _card_base_grafico(
    titulo: str,
    subtitulo: str,
    icone,
    cor_icone: str,
    corpo: ft.Control,
    col_span: dict,
    acao_extra: ft.Control | None = None,
) -> ft.Container:
    """Envelope visual padronizado para todos os gráficos do Dashboard."""
    header_controls = [
        ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            controls=[
                ft.Container(
                    content=ft.Icon(icone, color=cor_icone, size=18),
                    bgcolor=f"{cor_icone}1F",
                    border_radius=10,
                    padding=pad(all_=8),
                ),
                ft.Column(
                    spacing=1,
                    expand=True,
                    controls=[
                        ft.Text(
                            titulo.strip(),
                            color=T.TEXT_PRIMARY,
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            subtitulo,
                            color=T.TEXT_MUTED,
                            size=11,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
            ],
        )
    ]
    if acao_extra:
        header_controls.append(acao_extra)

    return ft.Container(
        col=col_span,
        padding=pad(all_=18),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=header_controls,
                ),
                ft.Divider(height=1, color=T.BORDER),
                corpo,
            ],
        ),
    )


def _estado_vazio(mensagem: str, icone=ft.Icons.INSERT_CHART_OUTLINED_ROUNDED) -> ft.Container:
    return ft.Container(
        padding=pad(v=28, h=12),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Icon(icone, color=f"{T.TEXT_MUTED}70", size=34),
                ft.Text(
                    mensagem,
                    color=T.TEXT_MUTED,
                    size=12,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )


def _barra_empilhada_proporcional(fatias: list[tuple[float, str, str]]) -> ft.Container:
    """
    Renderiza uma barra horizontal segmentada proporcional (estilo Donut linear)
    totalmente compatível com Flet 1.0.1.
    fatias: [(percentual_0_a_100, cor_hex, tooltip_str), ...]
    """
    segmentos = []
    for perc, cor, dica in fatias:
        peso = max(1, int(round(perc)))
        if perc <= 0:
            continue
        segmentos.append(
            ft.Container(
                expand=peso,
                height=10,
                bgcolor=cor,
                border_radius=4,
                tooltip=dica,
            )
        )
    if not segmentos:
        segmentos.append(
            ft.Container(expand=1, height=10, bgcolor=T.SURFACE_ALT, border_radius=4)
        )
    return ft.Container(
        border_radius=6,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Row(spacing=2, controls=segmentos),
    )


# =============================================================================
# 1. GRÁFICO: REGRA 50 / 30 / 20
# =============================================================================
def _render_regra_5030(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    dados = pacote.get("regra_5030") or {}
    receita_total = float(dados.get("receita_total", 0) or 0)

    pilares = [
        ("essencial", "Essencial", "Meta 50%", 50.0, T.PRIMARY, ft.Icons.HOME_ROUNDED),
        ("estilo_vida", "Estilo de Vida", "Meta 30%", 30.0, T.WARNING, ft.Icons.NIGHTLIFE_ROUNDED),
        ("investimento", "Investimento", "Meta 20%", 20.0, T.SALDO, ft.Icons.SAVINGS_ROUNDED),
    ]

    linhas = []
    fatias_topo = []

    for chave, nome, label_meta, meta_pct, cor_padrao, icone in pilares:
        bloco = dados.get(chave) or {}
        gasto = float(bloco.get("gasto", 0) or 0)
        orcamento = float(bloco.get("orcamento", 0) or (receita_total * (meta_pct / 100.0)))
        pct_real = float(bloco.get("percentual_usado", 0) or 0)

        ratio_orcamento = (gasto / orcamento) if orcamento > 0 else (1.0 if gasto > 0 else 0.0)
        estourou = gasto > orcamento and orcamento > 0
        cor_barra = T.DESPESA if estourou else cor_padrao

        fatias_topo.append((max(0.0, pct_real), cor_padrao, f"{nome}: {formatar_moeda(gasto)} ({pct_real:.1f}%)"))

        status_txt = "Acima do teto" if estourou else ("Dentro da meta" if gasto > 0 else "Sem gastos")
        cor_status = T.DESPESA if estourou else (T.RECEITA if gasto > 0 else T.TEXT_MUTED)

        linhas.append(
            ft.Container(
                padding=pad(h=12, v=10),
                bgcolor=T.SURFACE_ALT,
                border_radius=12,
                on_click=lambda _, r=nome: navegar(page, f"/relatorios?regra={r}"),
                ink=True,
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Icon(icone, color=cor_padrao, size=16),
                                        ft.Text(nome, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                                        ft.Container(
                                            padding=pad(h=6, v=2),
                                            bgcolor=f"{cor_padrao}20",
                                            border_radius=6,
                                            content=ft.Text(label_meta, color=cor_padrao, size=10, weight=ft.FontWeight.BOLD),
                                        ),
                                    ],
                                ),
                                ft.Text(formatar_moeda(gasto), color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, ratio_orcamento)),
                            color=cor_barra,
                            bgcolor=f"{T.BORDER}55",
                            height=6,
                            border_radius=4,
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(f"Teto ideal: {formatar_moeda(orcamento)}", color=T.TEXT_MUTED, size=11),
                                ft.Text(f"{pct_real:.1f}% da receita · {status_txt}", color=cor_status, size=11, weight=ft.FontWeight.W_500),
                            ],
                        ),
                    ],
                ),
            )
        )

    corpo = ft.Column(
        spacing=10,
        controls=[
            _barra_empilhada_proporcional(fatias_topo),
            *linhas,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
    )


# =============================================================================
# 2. GRÁFICO: DESPESAS POR CATEGORIA
# =============================================================================
def _render_despesas_categoria(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    bloco = pacote.get("despesas_por_categoria") or {}
    lista = bloco.get("categorias") or []
    total = float(bloco.get("total", 0) or 0)

    if not lista or total <= 0:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Nenhuma despesa registrada neste período."),
            meta["col"],
        )

    fatias = []
    itens_ui = []
    for item in lista[:6]:
        nome = item.get("categoria") or item.get("nome") or "Outros"
        valor = float(item.get("valor") or item.get("total") or 0)
        cor = item.get("cor") or T.DESPESA
        perc = float(item.get("percentual") or ((valor / total * 100) if total > 0 else 0))
        fatias.append((perc, cor, f"{nome}: {formatar_moeda(valor)} ({perc:.1f}%)"))

        itens_ui.append(
            ft.Container(
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=lambda _: navegar(page, "/relatorios?tipo=Despesa"),
                ink=True,
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                                        ft.Text(nome, color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Text(f"{perc:.1f}%", color=T.TEXT_MUTED, size=11),
                                        ft.Text(formatar_moeda(valor), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, perc / 100.0)),
                            color=cor,
                            bgcolor=f"{T.BORDER}50",
                            height=5,
                            border_radius=3,
                        ),
                    ],
                ),
            )
        )

    badge_total = ft.Container(
        padding=pad(h=10, v=4),
        bgcolor=f"{T.DESPESA}18",
        border_radius=12,
        content=ft.Text(formatar_moeda(total), color=T.DESPESA, size=11.5, weight=ft.FontWeight.BOLD),
    )

    corpo = ft.Column(
        spacing=8,
        controls=[
            _barra_empilhada_proporcional(fatias),
            *itens_ui,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=badge_total,
    )


# =============================================================================
# 3. GRÁFICO: RITMO DIÁRIO NO PERÍODO (HISTOGRAMA VERTICAL)
# =============================================================================
def _render_fluxo_diario(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    freq = pacote.get("frequencia_diaria") or []
    if not freq:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Sem movimentações diárias no período selecionado.", ft.Icons.BAR_CHART_ROUNDED),
            meta["col"],
        )

    # Limita aos últimos 14 dias com movimento para caber perfeitamente em telas mobile
    amostra = freq[-14:]
    max_val = max(
        [max(float(d.get("despesas", 0) or 0), float(d.get("receitas", 0) or 0)) for d in amostra] + [1.0]
    )

    total_desp_periodo = sum(float(d.get("despesas", 0) or 0) for d in freq)
    maior_dia = max(freq, key=lambda d: float(d.get("despesas", 0) or 0))
    maior_gasto = float(maior_dia.get("despesas", 0) or 0)
    media_dia = total_desp_periodo / max(1, len(freq))

    colunas_barras = []
    ALTURA_MAX = 110

    for item in amostra:
        desp = float(item.get("despesas", 0) or 0)
        rec = float(item.get("receitas", 0) or 0)
        lbl = item.get("label") or f"{int(item.get('dia', 1)):02d}"

        h_desp = max(4, int((desp / max_val) * ALTURA_MAX)) if desp > 0 else 3
        h_rec = max(4, int((rec / max_val) * ALTURA_MAX)) if rec > 0 else 3

        dica = f"Dia {lbl}\nSaídas: {formatar_moeda(desp)}\nEntradas: {formatar_moeda(rec)}"

        colunas_barras.append(
            ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.END,
                spacing=4,
                expand=True,
                controls=[
                    ft.Container(
                        height=ALTURA_MAX + 6,
                        alignment=ft.Alignment(0, 1),
                        tooltip=dica,
                        content=ft.Row(
                            spacing=2,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Container(
                                    width=7,
                                    height=h_rec,
                                    bgcolor=T.RECEITA if rec > 0 else f"{T.BORDER}40",
                                    border_radius=3,
                                    animate=ft.Animation(300, ft.AnimationCurve.DECELERATE),
                                ),
                                ft.Container(
                                    width=7,
                                    height=h_desp,
                                    bgcolor=T.DESPESA if desp > 0 else f"{T.BORDER}40",
                                    border_radius=3,
                                    animate=ft.Animation(300, ft.AnimationCurve.DECELERATE),
                                ),
                            ],
                        ),
                    ),
                    ft.Text(
                        str(lbl).split("/")[0],
                        color=T.TEXT_MUTED,
                        size=10,
                        weight=ft.FontWeight.W_500,
                    ),
                ],
            )
        )

    resumo_inferior = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Container(
                expand=True,
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Média / Dia Ativo", color=T.TEXT_MUTED, size=10),
                        ft.Text(formatar_moeda(media_dia), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ),
            ft.Container(
                expand=True,
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Pico de Saída", color=T.TEXT_MUTED, size=10),
                        ft.Text(formatar_moeda(maior_gasto), color=T.DESPESA, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ),
            ft.Container(
                expand=True,
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Dias Movimentados", color=T.TEXT_MUTED, size=10),
                        ft.Text(f"{len(freq)} dias", color=T.INFO, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ),
        ],
    )

    corpo = ft.Column(
        spacing=12,
        controls=[
            ft.Container(
                padding=pad(h=8, v=10),
                bgcolor=T.SURFACE_ALT,
                border_radius=12,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    controls=colunas_barras,
                ),
            ),
            resumo_inferior,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
    )


# =============================================================================
# 4. GRÁFICO: EVOLUÇÃO MENSAL (6 MESES)
# =============================================================================
def _render_balanco_semestral(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    balanco = pacote.get("balanco_6_meses") or []
    if not balanco:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Histórico semestral ainda sem lançamentos pagos."),
            meta["col"],
        )

    max_v = max(
        [max(float(m.get("receitas", 0) or 0), float(m.get("despesas", 0) or 0)) for m in balanco] + [1.0]
    )

    linhas = []
    for m in balanco[-6:]:
        lbl = m.get("label") or f"{int(m.get('mes', 1)):02d}/{m.get('ano', '')}"
        rec = float(m.get("receitas", 0) or 0)
        desp = float(m.get("despesas", 0) or 0)
        saldo = rec - desp
        cor_saldo = T.RECEITA if saldo >= 0 else T.DESPESA

        linhas.append(
            ft.Container(
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(lbl, color=T.TEXT_PRIMARY, size=12, weight=ft.FontWeight.BOLD),
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        ft.Text(f"+{formatar_moeda(rec)}", color=T.RECEITA, size=11),
                                        ft.Text(f"-{formatar_moeda(desp)}", color=T.DESPESA, size=11),
                                        ft.Container(
                                            padding=pad(h=6, v=2),
                                            bgcolor=f"{cor_saldo}1A",
                                            border_radius=6,
                                            content=ft.Text(
                                                formatar_moeda(saldo),
                                                color=cor_saldo,
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, rec / max_v)),
                            color=T.RECEITA,
                            bgcolor=f"{T.BORDER}40",
                            height=4,
                            border_radius=2,
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, desp / max_v)),
                            color=T.DESPESA,
                            bgcolor=f"{T.BORDER}40",
                            height=4,
                            border_radius=2,
                        ),
                    ],
                ),
            )
        )

    corpo = ft.Column(spacing=8, controls=linhas)
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
    )


# =============================================================================
# 5. GRÁFICO: FONTES DE RECEITA POR CATEGORIA
# =============================================================================
def _render_receitas_categoria(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    bloco = pacote.get("receitas_por_categoria") or {}
    lista = bloco.get("categorias") or []
    total = float(bloco.get("total", 0) or 0)

    if not lista or total <= 0:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Nenhuma receita registrada no período selecionado."),
            meta["col"],
        )

    fatias = []
    itens_ui = []
    for item in lista[:6]:
        nome = item.get("categoria") or item.get("nome") or "Outros"
        valor = float(item.get("valor") or item.get("total") or 0)
        cor = item.get("cor") or T.RECEITA
        perc = float(item.get("percentual") or ((valor / total * 100) if total > 0 else 0))
        fatias.append((perc, cor, f"{nome}: {formatar_moeda(valor)} ({perc:.1f}%)"))

        itens_ui.append(
            ft.Container(
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=lambda _: navegar(page, "/relatorios?tipo=Receita"),
                ink=True,
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                                        ft.Text(nome, color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Text(f"{perc:.1f}%", color=T.TEXT_MUTED, size=11),
                                        ft.Text(formatar_moeda(valor), color=T.RECEITA, size=12.5, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, perc / 100.0)),
                            color=cor,
                            bgcolor=f"{T.BORDER}50",
                            height=5,
                            border_radius=3,
                        ),
                    ],
                ),
            )
        )

    badge_total = ft.Container(
        padding=pad(h=10, v=4),
        bgcolor=f"{T.RECEITA}18",
        border_radius=12,
        content=ft.Text(formatar_moeda(total), color=T.RECEITA, size=11.5, weight=ft.FontWeight.BOLD),
    )

    corpo = ft.Column(
        spacing=8,
        controls=[
            _barra_empilhada_proporcional(fatias),
            *itens_ui,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=badge_total,
    )


# =============================================================================
# 6. GRÁFICO: MEIOS DE PAGAMENTO & SAÚDE DOS CARTÕES
# =============================================================================
def _render_formas_e_cartoes(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    formas = pacote.get("despesas_por_forma") or []
    resumo_cartoes = pacote.get("resumo_cartoes") or {}

    limite_total = float(resumo_cartoes.get("total_limite", 0) or 0)
    disponivel = float(resumo_cartoes.get("total_disponivel", 0) or 0)
    usado_cartao = max(0.0, limite_total - disponivel)
    pct_cartao = (usado_cartao / limite_total) if limite_total > 0 else 0.0

    cores_forma = {
        "Pix": "#10B981",
        "Crédito": "#F59E0B",
        "Débito": "#3B82F6",
        "Dinheiro": "#22C55E",
        "Boleto": "#8B5CF6",
        "Transferência": "#06B6D4",
    }

    bloco_cartao = ft.Container(
        padding=pad(h=12, v=10),
        bgcolor=T.SURFACE_ALT,
        border_radius=12,
        on_click=lambda _: navegar(page, "/cartoes"),
        ink=True,
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color=T.WARNING, size=16),
                                ft.Text("Limite Consolidado de Cartões", color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        ft.Text(f"{pct_cartao * 100:.1f}% em uso", color=T.WARNING, size=11.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.ProgressBar(
                    value=min(1.0, max(0.0, pct_cartao)),
                    color=T.DESPESA if pct_cartao > 0.8 else T.WARNING,
                    bgcolor=f"{T.BORDER}50",
                    height=6,
                    border_radius=4,
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(f"Disponível: {formatar_moeda(disponivel)}", color=T.RECEITA, size=11),
                        ft.Text(f"Limite: {formatar_moeda(limite_total)}", color=T.TEXT_MUTED, size=11),
                    ],
                ),
            ],
        ),
    )

    itens_formas = []
    for f in formas[:5]:
        nome_f = f.get("forma") or "Outros"
        val_f = float(f.get("valor", 0) or 0)
        qtd_f = int(f.get("qtd", 0) or 0)
        perc_f = float(f.get("percentual", 0) or 0)
        cor_f = cores_forma.get(nome_f, T.PRIMARY)

        itens_formas.append(
            ft.Container(
                padding=pad(h=10, v=7),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(width=8, height=8, bgcolor=cor_f, border_radius=4),
                                ft.Text(nome_f, color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_500),
                                ft.Text(f"({qtd_f}x)", color=T.TEXT_MUTED, size=11),
                            ],
                        ),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Text(f"{perc_f:.1f}%", color=T.TEXT_MUTED, size=11),
                                ft.Text(formatar_moeda(val_f), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                    ],
                ),
            )
        )

    if not itens_formas:
        itens_formas.append(
            ft.Text("Sem despesas por modalidade neste período.", color=T.TEXT_MUTED, size=12)
        )

    corpo = ft.Column(
        spacing=8,
        controls=[
            bloco_cartao,
            ft.Text("Saídas por Modalidade no Período", color=T.TEXT_MUTED, size=11, weight=ft.FontWeight.W_600),
            *itens_formas,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
    )


_RENDERERS = {
    "regra_5030": _render_regra_5030,
    "despesas_categoria": _render_despesas_categoria,
    "fluxo_diario": _render_fluxo_diario,
    "balanco_semestral": _render_balanco_semestral,
    "receitas_categoria": _render_receitas_categoria,
    "formas_e_cartoes": _render_formas_e_cartoes,
}


def construir_grid_graficos(
    page: ft.Page,
    pacote_dados: dict,
    ids_ativos: list[str] | None = None,
) -> list[ft.Control]:
    """
    Constrói dinamicamente a lista de cards de gráficos habilitados pelo usuário
    para popular o ft.ResponsiveRow do Dashboard.
    """
    ativos = ids_ativos if ids_ativos is not None else GRAFICOS_PADRAO_IDS
    catalogo_map = {item["id"]: item for item in DASHBOARD_CHARTS_CATALOG}

    cards: list[ft.Control] = []
    for cid in ativos:
        meta = catalogo_map.get(cid)
        renderer = _RENDERERS.get(cid)
        if meta and renderer:
            cards.append(renderer(page, pacote_dados, meta))
    return cards
