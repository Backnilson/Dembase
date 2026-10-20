"""
=============================================================================
DemBase v3 — views/relatorios/regra5030_report.py  (Flet 1.0.1)
Relatório Analítico da Regra 50 / 30 / 20 (/relatorios/regra/:regra).
Exibe:
- Seletor interativo entre os 3 pilares: Essencial (50%), Estilo de Vida (30%), Investimento (20%)
- 4 KPIs: Gasto Real, Teto Ideal da Meta, % da Receita Consumido, Folga / Excesso
- Gráficos: Evolução Diária no Pilar + Categorias que compõem o Pilar
- FilterBar + TransactionList
- Botão "+ Lançar neste pilar"
=============================================================================
"""
from __future__ import annotations
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, formatar_data_br
from core.responsive import is_mobile
from core.periodo import obter_estado_periodo_atual, atualizar_datas_periodo_global
from core.report_context import ReportContext, normalizar_regra, regra_para_slug
from core.nav import ir_relatorio_regra, ir_relatorio_categoria
from views.shell_view import criar_shell, ROTA_RELATORIOS
from views.widgets.lancamento_sheet import abrir_lancamento
from views.widgets.report import (
    criar_report_header,
    criar_kpi_strip,
    criar_filter_bar,
    criar_transaction_list,
    construir_card_evolucao_diaria,
    construir_card_ranking_categorias,
)
import services.supabase_client as db

PILARES_META = {
    "Essencial": {
        "chave_rpc": "essencial",
        "meta_pct": 50.0,
        "label_meta": "Meta 50%",
        "cor": T.PRIMARY,
        "icone": ft.Icons.HOME_ROUNDED,
        "descricao": "Moradia, alimentação básica, saúde, contas fixas e transporte essencial",
    },
    "Estilo de Vida": {
        "chave_rpc": "estilo_vida",
        "meta_pct": 30.0,
        "label_meta": "Meta 30%",
        "cor": T.WARNING,
        "icone": ft.Icons.NIGHTLIFE_ROUNDED,
        "descricao": "Lazer, restaurantes, assinaturas, compras pessoais e conforto",
    },
    "Investimento": {
        "chave_rpc": "investimento",
        "meta_pct": 20.0,
        "label_meta": "Meta 20%",
        "cor": T.SALDO,
        "icone": ft.Icons.SAVINGS_ROUNDED,
        "descricao": "Reserva de emergência, aportes financeiros, previdência e objetivos futuros",
    },
}


def criar_view_relatorio_regra(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    params = match or {}
    regra_raw = params.get("regra") or (ctx.regra_5030 if ctx else None) or "Essencial"
    regra_canonica = normalizar_regra(str(regra_raw)) or "Essencial"

    est_p = obter_estado_periodo_atual(page)
    contexto_inicial = ctx or ReportContext.from_query(page, None, params)
    contexto_atual: list[ReportContext] = [
        contexto_inicial.com(
            regra_5030=regra_canonica,
            tipo=contexto_inicial.tipo or "Despesa",
            data_inicio=contexto_inicial.data_inicio or est_p["data_inicio"],
            data_fim=contexto_inicial.data_fim or est_p["data_fim"],
        )
    ]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=18, height=18, stroke_width=2.2, visible=False)

    container_header = ft.Container()
    container_pilares = ft.Container()
    container_kpis = ft.Container()
    container_graficos = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])
    container_filter_bar = ft.Container()
    container_lista = ft.Container()

    def _safe_update():
        try:
            page.update()
        except Exception:
            pass

    def _trocar_pilar(novo_pilar: str):
        ir_relatorio_regra(
            page,
            novo_pilar,
            contexto_atual[0].com(regra_5030=novo_pilar, pagina=1),
            replace=True,
        )

    def _aplicar_novo_contexto(novo_ctx: ReportContext):
        ir_relatorio_regra(
            page,
            regra_canonica,
            novo_ctx.com(regra_5030=regra_canonica),
            replace=True,
        )

    def _ao_mudar_pagina(nova_pag: int):
        c = contexto_atual[0].com(pagina=nova_pag)
        contexto_atual[0] = c
        carregar(inicial=False)

    def _abrir_novo_lancamento_regra(_=None):
        abrir_lancamento(
            page,
            tipo_inicial="Despesa",
            regra_inicial=regra_canonica,
            on_saved=lambda: carregar(inicial=False),
        )

    btn_lancar_regra = ft.FilledButton(
        content=ft.Row(
            spacing=6,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                ft.Text(
                    "Lançar" if mobile else f"Lançar em {regra_canonica}",
                    color=ft.Colors.WHITE,
                    size=12,
                    weight=ft.FontWeight.W_600,
                ),
            ],
        ),
        style=ft.ButtonStyle(
            bgcolor=PILARES_META[regra_canonica]["cor"],
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=12 if mobile else 14, v=8),
        ),
        on_click=_abrir_novo_lancamento_regra,
    )

    def _construir_seletor_pilares(resumo_5030: dict) -> ft.Control:
        receita_tot = float(resumo_5030.get("receita_total", 0) or 0)
        cards_p = []
        for nome_p, meta_p in PILARES_META.items():
            ativo = (nome_p == regra_canonica)
            cor_p = meta_p["cor"]
            bloco_p = (
                resumo_5030.get(meta_p["chave_rpc"])
                or resumo_5030.get("estilo_de_vida" if meta_p["chave_rpc"] == "estilo_vida" else meta_p["chave_rpc"])
                or {}
            )
            gasto_p = float(bloco_p.get("gasto", 0) or 0)
            orc_p = float(bloco_p.get("orcamento", 0) or (receita_tot * (meta_p["meta_pct"] / 100.0)))
            pct_p = float(bloco_p.get("percentual_usado", 0) or 0)

            cards_p.append(
                ft.Container(
                    col={"xs": 12, "sm": 4},
                    padding=pad(all_=14),
                    bgcolor=f"{cor_p}16" if ativo else T.SURFACE,
                    border=borda(1.8 if ativo else 1, cor_p if ativo else T.BORDER),
                    border_radius=14,
                    on_click=lambda _, np=nome_p: _trocar_pilar(np),
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
                                            ft.Icon(meta_p["icone"], color=cor_p, size=18),
                                            ft.Text(nome_p, color=T.TEXT_PRIMARY, size=13.5, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                    ft.Container(
                                        padding=pad(h=8, v=2),
                                        bgcolor=cor_p if ativo else f"{cor_p}20",
                                        border_radius=8,
                                        content=ft.Text(
                                            meta_p["label_meta"],
                                            color=ft.Colors.WHITE if ativo else cor_p,
                                            size=10.5,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ),
                                ],
                            ),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(formatar_moeda(gasto_p), color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"Teto: {formatar_moeda(orc_p)} ({pct_p:.1f}%)", color=T.TEXT_MUTED, size=11),
                                ],
                            ),
                        ],
                    ),
                )
            )
        return ft.ResponsiveRow(spacing=12, run_spacing=12, controls=cards_p)

    def carregar(inicial: bool = False):
        c = contexto_atual[0]
        di_str = c.data_inicio.isoformat()
        df_str = c.data_fim.isoformat()
        meta_p = PILARES_META[regra_canonica]
        cor_p = meta_p["cor"]

        if not inicial:
            spinner.visible = True
            _safe_update()

        try:
            resumo_5030 = db.obter_resumo_5030(di_str, df_str)
            pacote = db.obter_relatorio_lancamentos(
                data_inicio=di_str,
                data_fim=df_str,
                filtros=c.to_rpc_filtros(),
                incluir_transferencias=False,
            )
            evolucao = pacote.get("evolucao_diaria") or []
            por_cat = pacote.get("por_categoria") or []
            itens = pacote.get("itens") or []
            total_reg = int(pacote.get("total_registros", len(itens)) or 0)

            receita_total = float(resumo_5030.get("receita_total", 0) or 0)
            bloco_p = (
                resumo_5030.get(meta_p["chave_rpc"])
                or resumo_5030.get("estilo_de_vida" if meta_p["chave_rpc"] == "estilo_vida" else meta_p["chave_rpc"])
                or {}
            )
            gasto_real = float(bloco_p.get("gasto", 0) or 0)
            teto_ideal = float(bloco_p.get("orcamento", 0) or (receita_total * (meta_p["meta_pct"] / 100.0)))
            pct_receita = float(bloco_p.get("percentual_usado", 0) or 0)
            folga = teto_ideal - gasto_real
            estourou = gasto_real > teto_ideal and teto_ideal > 0

            # 1. Header
            container_header.content = criar_report_header(
                page,
                titulo=f"Regra 50/30/20 · {regra_canonica}",
                subtitulo=(
                    f"{meta_p['descricao']} · Período {formatar_data_br(di_str)} a {formatar_data_br(df_str)}"
                ),
                icone=meta_p["icone"],
                cor_icone=cor_p,
                breadcrumbs=[
                    ("Relatórios", "/relatorios"),
                    ("Regra 50/30/20", "/relatorios"),
                    (regra_canonica, None),
                ],
                acoes_header=[spinner, btn_lancar_regra],
            )

            # 2. Seletor interativo dos 3 pilares
            container_pilares.content = _construir_seletor_pilares(resumo_5030)

            # 3. KPIs do Pilar
            container_kpis.content = criar_kpi_strip(
                page,
                [
                    {
                        "titulo": f"Gasto em {regra_canonica}",
                        "valor": formatar_moeda(gasto_real),
                        "subtitulo": f"{total_reg} lançamento{'s' if total_reg != 1 else ''}",
                        "cor": T.DESPESA if estourou else cor_p,
                        "icone": meta_p["icone"],
                    },
                    {
                        "titulo": f"Teto Ideal ({meta_p['label_meta']})",
                        "valor": formatar_moeda(teto_ideal),
                        "subtitulo": f"Base: Receita de {formatar_moeda(receita_total)}",
                        "cor": T.INFO,
                        "icone": ft.Icons.FLAG_ROUNDED,
                    },
                    {
                        "titulo": "% da Receita Consumido",
                        "valor": f"{pct_receita:.1f}%",
                        "subtitulo": "Acima da meta recomendada" if estourou else "Dentro da meta recomendada",
                        "cor": T.DESPESA if estourou else T.RECEITA,
                        "icone": ft.Icons.PIE_CHART_ROUNDED,
                    },
                    {
                        "titulo": "Margem Disponível" if folga >= 0 else "Excesso sobre o Teto",
                        "valor": formatar_moeda(abs(folga)),
                        "subtitulo": "Restante para gastar no pilar" if folga >= 0 else "Valor acima do teto ideal",
                        "cor": T.RECEITA if folga >= 0 else T.DESPESA,
                        "icone": ft.Icons.CHECK_CIRCLE_ROUNDED if folga >= 0 else ft.Icons.WARNING_AMBER_ROUNDED,
                    },
                ],
            )

            # 4. Gráficos Analíticos do Pilar
            card_evolucao = construir_card_evolucao_diaria(
                evolucao,
                titulo=f"Ritmo Diário · {regra_canonica}",
                subtitulo="Saídas dia a dia neste pilar",
                modo_saldo=False,
            )
            card_ranking = construir_card_ranking_categorias(
                por_cat,
                titulo=f"Categorias de {regra_canonica}",
                subtitulo="Toque em uma categoria para abrir seu detalhamento",
                cor_padrao=cor_p,
                on_categoria_click=lambda cid, _: ir_relatorio_categoria(
                    page,
                    cid,
                    c.com(categoria_id=cid, pagina=1),
                ),
            )
            container_graficos.controls = [card_evolucao, card_ranking]

            # 5. Barra de Filtros
            container_filter_bar.content = criar_filter_bar(
                page,
                ctx=c,
                on_change=_aplicar_novo_contexto,
                mostrar_chips_tipo=False,
                mostrar_filtro_conta=True,
                mostrar_filtro_cartao=True,
                mostrar_filtro_categoria=True,
                mostrar_filtro_regra=False,
                mostrar_filtro_forma=True,
            )

            # 6. Lista de Transações
            container_lista.content = criar_transaction_list(
                page,
                itens=itens,
                total_registros=total_reg,
                pagina_atual=c.pagina,
                page_size=c.page_size,
                on_page_change=_ao_mudar_pagina,
                on_refresh=lambda: carregar(inicial=False),
                mostrar_transferencias_padrao=False,
                titulo_vazio=f"Nenhum lançamento em '{regra_canonica}' neste período",
                subtitulo_vazio="Associe suas categorias de despesa aos pilares 50/30/20 ou registre um novo lançamento.",
                label_cta_vazio=f"+ Lançar em {regra_canonica}",
                on_cta_vazio=_abrir_novo_lancamento_regra,
            )

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar Regra 50/30/20: {ex}", "erro")
        finally:
            spinner.visible = False
            if not inicial:
                _safe_update()

    def on_periodo(d_ini: str, d_fim: str, m: int, a: int):
        est = atualizar_datas_periodo_global(page, d_ini, d_fim, m, a)
        contexto_atual[0] = contexto_atual[0].com(
            data_inicio=est["data_inicio"],
            data_fim=est["data_fim"],
            pagina=1,
        )
        carregar(inicial=False)

    def on_mes_ano(m: int, a: int):
        est = obter_estado_periodo_atual(page)
        contexto_atual[0] = contexto_atual[0].com(
            data_inicio=est["data_inicio"],
            data_fim=est["data_fim"],
            pagina=1,
        )
        carregar(inicial=False)

    conteudo = ft.Column(
        spacing=14 if mobile else 16,
        controls=[
            container_header,
            container_pilares,
            container_kpis,
            container_graficos,
            container_filter_bar,
            container_lista,
            ft.Container(height=28),
        ],
    )

    carregar(inicial=True)

    slug = regra_para_slug(regra_canonica)
    url_rota = f"/relatorios/regra/{slug}{contexto_atual[0].to_query()}"
    return criar_shell(
        page,
        rota_ativa=ROTA_RELATORIOS,
        conteudo=conteudo,
        rota_view=url_rota,
        titulo=f"Regra 50/30/20 · {regra_canonica}",
        mostrar_voltar=True,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
