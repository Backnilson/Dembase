"""
=============================================================================
DemBase v3 — views/relatorios/categoria_report.py  (Flet 1.0.1)
Relatório Analítico por Categoria (/relatorios/categoria/:cat_id).
Exibe:
- Header com Breadcrumbs + Seletor Rápido para trocar de Categoria
- 4 KPIs: Total na Categoria, Média por Lançamento, Maior Valor, Qtd. Registros
- Gráficos: Evolução Diária na Categoria + Composição por Subcategoria/Modalidade
- FilterBar + TransactionList
- Botão "+ Lançar nesta categoria" pré-selecionando a categoria
=============================================================================
"""
from __future__ import annotations
import flet as ft
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, formatar_data_br
from core.responsive import is_mobile
from core.periodo import obter_estado_periodo_atual, atualizar_datas_periodo_global
from core.report_context import ReportContext
from core.nav import ir_relatorio_categoria, ir_relatorio_regra
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


def criar_view_relatorio_categoria(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    params = match or {}
    cat_id = str(params.get("cat_id") or (ctx.categoria_id if ctx else "") or "")

    est_p = obter_estado_periodo_atual(page)
    contexto_inicial = ctx or ReportContext.from_query(page, None, params)
    contexto_atual: list[ReportContext] = [
        contexto_inicial.com(
            categoria_id=cat_id,
            data_inicio=contexto_inicial.data_inicio or est_p["data_inicio"],
            data_fim=contexto_inicial.data_fim or est_p["data_fim"],
        )
    ]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=18, height=18, stroke_width=2.2, visible=False)

    # Lista de categorias para seletor rápido e metadados
    try:
        todas_categorias = db.listar_categorias()
    except Exception:
        todas_categorias = []

    cat_map = {str(c.get("id")): c for c in todas_categorias if c.get("id")}
    cat_meta = cat_map.get(cat_id) or {}

    nome_cat_ref = [cat_meta.get("nome") or "Categoria"]
    cor_cat_ref = [cat_meta.get("cor") or T.PRIMARY]
    tipo_cat_ref = [cat_meta.get("tipo") or contexto_atual[0].tipo or "Despesa"]
    regra_cat_ref = [cat_meta.get("regra_5030") or ""]

    container_header = ft.Container()
    container_seletor_cat = ft.Container()
    container_kpis = ft.Container()
    container_graficos = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])
    container_filter_bar = ft.Container()
    container_lista = ft.Container()

    def _safe_update():
        try:
            page.update()
        except Exception:
            pass

    def _aplicar_novo_contexto(novo_ctx: ReportContext):
        ir_relatorio_categoria(page, cat_id, novo_ctx.com(categoria_id=cat_id), replace=True)

    def _ao_mudar_pagina(nova_pag: int):
        c = contexto_atual[0].com(pagina=nova_pag)
        contexto_atual[0] = c
        carregar(inicial=False)

    def _abrir_novo_lancamento_cat(_=None):
        tipo_padrao = tipo_cat_ref[0] if tipo_cat_ref[0] in ("Receita", "Despesa") else "Despesa"
        abrir_lancamento(
            page,
            tipo_inicial=tipo_padrao,
            categoria_inicial=cat_id,
            regra_inicial=regra_cat_ref[0] or None,
            on_saved=lambda: carregar(inicial=False),
        )

    btn_lancar_cat = ft.FilledButton(
        content=ft.Row(
            spacing=6,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                ft.Text(
                    "Lançar" if mobile else "Lançar nesta categoria",
                    color=ft.Colors.WHITE,
                    size=12,
                    weight=ft.FontWeight.W_600,
                ),
            ],
        ),
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=12 if mobile else 14, v=8),
        ),
        on_click=_abrir_novo_lancamento_cat,
    )

    # Seletor rápido de categorias em chips horizontais
    def _construir_seletor_categorias() -> ft.Control:
        if not todas_categorias:
            return ft.Container()
        chips = []
        for cat_item in todas_categorias:
            cid_it = str(cat_item.get("id") or "")
            nome_it = cat_item.get("nome") or "Categoria"
            cor_it = cat_item.get("cor") or T.PRIMARY
            selecionada = (cid_it == cat_id)

            chips.append(
                ft.Container(
                    padding=pad(h=12, v=6),
                    bgcolor=cor_it if selecionada else T.SURFACE_ALT,
                    border=borda(1, cor_it if selecionada else T.BORDER),
                    border_radius=20,
                    on_click=lambda _, c_alvo=cid_it: ir_relatorio_categoria(
                        page,
                        c_alvo,
                        contexto_atual[0].com(categoria_id=c_alvo, pagina=1),
                        replace=True,
                    ),
                    ink=True,
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=8,
                                height=8,
                                bgcolor=ft.Colors.WHITE if selecionada else cor_it,
                                border_radius=4,
                            ),
                            ft.Text(
                                nome_it,
                                color=ft.Colors.WHITE if selecionada else T.TEXT_PRIMARY,
                                size=11.5,
                                weight=ft.FontWeight.BOLD if selecionada else ft.FontWeight.W_500,
                            ),
                        ],
                    ),
                )
            )
        return ft.Container(
            padding=pad(h=14, v=10),
            bgcolor=T.SURFACE,
            border_radius=14,
            border=borda(),
            content=ft.Row(
                spacing=8,
                scroll=ft.ScrollMode.AUTO,
                controls=chips,
            ),
        )

    def carregar(inicial: bool = False):
        c = contexto_atual[0]
        di_str = c.data_inicio.isoformat()
        df_str = c.data_fim.isoformat()

        if not inicial:
            spinner.visible = True
            _safe_update()

        try:
            pacote = db.obter_relatorio_lancamentos(
                data_inicio=di_str,
                data_fim=df_str,
                filtros=c.to_rpc_filtros(),
                incluir_transferencias=True,
            )
            kpis = pacote.get("kpis") or {}
            evolucao = pacote.get("evolucao_diaria") or []
            itens = pacote.get("itens") or []
            total_reg = int(pacote.get("total_registros", len(itens)) or 0)

            # Atualiza metadados caso algum item traga a categoria
            if itens and not cat_meta:
                primeiro = itens[0]
                if primeiro.get("categoria_nome"):
                    nome_cat_ref[0] = primeiro["categoria_nome"]
                if primeiro.get("categoria_cor"):
                    cor_cat_ref[0] = primeiro["categoria_cor"]
                if primeiro.get("regra_5030"):
                    regra_cat_ref[0] = primeiro["regra_5030"]

            nome_cat = nome_cat_ref[0]
            cor_cat = cor_cat_ref[0]
            regra_cat = regra_cat_ref[0]

            total_rec = float(kpis.get("total_receitas", 0) or 0)
            total_desp = float(kpis.get("total_despesas", 0) or 0)
            total_cat_val = total_desp if total_desp >= total_rec else total_rec
            cor_principal = T.DESPESA if total_desp >= total_rec else T.RECEITA

            media_val = (total_cat_val / total_reg) if total_reg > 0 else 0.0
            maior_val = max([float(i.get("valor", 0) or 0) for i in itens] + [0.0])

            # Agrupamento por Subcategoria ou Forma de Movimentação nos itens carregados
            agrup_sub: dict[str, float] = {}
            for it in itens:
                chave_sub = (
                    it.get("subcategoria_nome")
                    or it.get("subtipo")
                    or it.get("forma_movimentacao")
                    or "Geral"
                )
                agrup_sub[chave_sub] = agrup_sub.get(chave_sub, 0.0) + float(it.get("valor", 0) or 0)

            soma_sub = sum(agrup_sub.values()) or 1.0
            lista_sub = [
                {
                    "categoria": k,
                    "valor": v,
                    "cor": cor_cat,
                    "percentual": round((v / soma_sub) * 100.0, 1),
                }
                for k, v in sorted(agrup_sub.items(), key=lambda x: x[1], reverse=True)
            ]

            breadcrumbs = [
                ("Dashboard", "/dashboard") if c.origem == "dashboard" else ("Relatórios", "/relatorios"),
                ("Categorias", "/relatorios"),
                (nome_cat, None),
            ]

            acoes_h = [spinner]
            if regra_cat:
                acoes_h.append(
                    ft.Container(
                        padding=pad(h=10, v=5),
                        bgcolor=f"{T.PRIMARY}1A",
                        border_radius=12,
                        on_click=lambda _: ir_relatorio_regra(page, regra_cat),
                        ink=True,
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.PIE_CHART_ROUNDED, color=T.PRIMARY, size=14),
                                ft.Text(regra_cat, color=T.PRIMARY, size=11.5, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                    )
                )
            acoes_h.append(btn_lancar_cat)

            # 1. Header
            container_header.content = criar_report_header(
                page,
                titulo=f"Categoria · {nome_cat}",
                subtitulo=(
                    f"Período de {formatar_data_br(di_str)} a {formatar_data_br(df_str)} "
                    f"· {total_reg} lançamento{'s' if total_reg != 1 else ''}"
                ),
                icone=ft.Icons.CATEGORY_ROUNDED,
                cor_icone=cor_cat,
                breadcrumbs=breadcrumbs,
                acoes_header=acoes_h,
            )

            # 2. Seletor Rápido de Categorias
            container_seletor_cat.content = _construir_seletor_categorias()

            # 3. KPIs
            container_kpis.content = criar_kpi_strip(
                page,
                [
                    {
                        "titulo": f"Total em {nome_cat}",
                        "valor": formatar_moeda(total_cat_val),
                        "subtitulo": "No período selecionado",
                        "cor": cor_principal,
                        "icone": ft.Icons.DONUT_LARGE_ROUNDED,
                    },
                    {
                        "titulo": "Ticket Médio",
                        "valor": formatar_moeda(media_val),
                        "subtitulo": "Valor médio por lançamento",
                        "cor": T.INFO,
                        "icone": ft.Icons.EQUALIZER_ROUNDED,
                    },
                    {
                        "titulo": "Maior Lançamento",
                        "valor": formatar_moeda(maior_val),
                        "subtitulo": "Pico individual na categoria",
                        "cor": T.WARNING,
                        "icone": ft.Icons.TRENDING_UP_ROUNDED,
                    },
                    {
                        "titulo": "Volume de Registros",
                        "valor": f"{total_reg} item{'s' if total_reg != 1 else ''}",
                        "subtitulo": f"Pilar: {regra_cat or 'Não classificado'}",
                        "cor": cor_cat,
                        "icone": ft.Icons.RECEIPT_LONG_ROUNDED,
                    },
                ],
            )

            # 4. Gráficos Analíticos
            card_evolucao = construir_card_evolucao_diaria(
                evolucao,
                titulo=f"Ritmo Diário · {nome_cat}",
                subtitulo="Movimentação dia a dia nesta categoria",
                modo_saldo=False,
            )
            card_sub = construir_card_ranking_categorias(
                lista_sub,
                titulo="Detalhamento por Subcategoria / Forma",
                subtitulo="Divisão interna dos lançamentos desta categoria",
                cor_padrao=cor_cat,
            )
            container_graficos.controls = [card_evolucao, card_sub]

            # 5. Barra de Filtros
            container_filter_bar.content = criar_filter_bar(
                page,
                ctx=c,
                on_change=_aplicar_novo_contexto,
                mostrar_chips_tipo=True,
                mostrar_filtro_conta=True,
                mostrar_filtro_cartao=True,
                mostrar_filtro_categoria=False,
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
                mostrar_transferencias_padrao=True,
                titulo_vazio=f"Nenhum lançamento em '{nome_cat}' neste período",
                subtitulo_vazio="Experimente ampliar o período ou registrar um novo lançamento nesta categoria.",
                label_cta_vazio=f"+ Lançar em {nome_cat}",
                on_cta_vazio=_abrir_novo_lancamento_cat,
            )

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar categoria: {ex}", "erro")
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
            container_seletor_cat,
            container_kpis,
            container_graficos,
            container_filter_bar,
            container_lista,
            ft.Container(height=28),
        ],
    )

    carregar(inicial=True)

    url_rota = f"/relatorios/categoria/{cat_id}{contexto_atual[0].to_query()}"
    return criar_shell(
        page,
        rota_ativa=ROTA_RELATORIOS,
        conteudo=conteudo,
        rota_view=url_rota,
        titulo=f"Categoria · {nome_cat_ref[0]}",
        mostrar_voltar=True,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
