"""
=============================================================================
DemBase v3 — views/relatorios/cartao_report.py  (Flet 1.0.1)
Relatório Individual de Cartão de Crédito (/cartoes/:cartao_id).
Exibe:
- Banner Hero do Cartão (plástico colorido, bandeira, fechamento, vencimento, barra de limite)
- 4 KPIs: Gasto no Período, Limite Total, Limite Disponível, Parcelados vs À Vista
- Gráficos: Ritmo Diário de Compras + Categorias no Cartão
- FilterBar + TransactionList
- Botão "+ Lançar neste cartão" pré-selecionando o cartão
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
from core.nav import ir_cartao, ir_relatorio_categoria
from views.shell_view import criar_shell, ROTA_CARTOES
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

LABELS_BANDEIRAS = {
    "mastercard": "Mastercard",
    "visa": "Visa",
    "elo": "Elo",
    "amex": "American Express",
    "hipercard": "Hipercard",
    "outro": "Outra",
}


def criar_view_relatorio_cartao(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    params = match or {}
    cartao_id = str(params.get("cartao_id") or (ctx.cartao_id if ctx else "") or "")

    est_p = obter_estado_periodo_atual(page)
    contexto_inicial = ctx or ReportContext.from_query(page, None, params)
    contexto_atual: list[ReportContext] = [
        contexto_inicial.com(
            cartao_id=cartao_id,
            data_inicio=contexto_inicial.data_inicio or est_p["data_inicio"],
            data_fim=contexto_inicial.data_fim or est_p["data_fim"],
        )
    ]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=18, height=18, stroke_width=2.2, visible=False)
    nome_cartao_ref = ["Cartão de Crédito"]

    container_header = ft.Container()
    container_hero = ft.Container()
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
        ir_cartao(page, cartao_id, novo_ctx.com(cartao_id=cartao_id), replace=True)

    def _ao_mudar_pagina(nova_pag: int):
        c = contexto_atual[0].com(pagina=nova_pag)
        contexto_atual[0] = c
        carregar(inicial=False)

    def _abrir_novo_lancamento_cartao(_=None):
        abrir_lancamento(
            page,
            tipo_inicial="Despesa",
            cartao_inicial=cartao_id,
            on_saved=lambda: carregar(inicial=False),
        )

    btn_lancar_cartao = ft.FilledButton(
        content=ft.Row(
            spacing=6,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                ft.Text(
                    "Lançar" if mobile else "Lançar neste cartão",
                    color=ft.Colors.WHITE,
                    size=12,
                    weight=ft.FontWeight.W_600,
                ),
            ],
        ),
        style=ft.ButtonStyle(
            bgcolor=T.WARNING,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=12 if mobile else 14, v=8),
        ),
        on_click=_abrir_novo_lancamento_cartao,
    )

    def _construir_hero_cartao(cartao_info: dict, lim_total: float, lim_disp: float) -> ft.Container:
        nome_c = cartao_info.get("nome") or "Cartão de Crédito"
        cor_c = cartao_info.get("cor") or "#1E293B"
        band_k = db.normalizar_bandeira_cartao(cartao_info.get("bandeira"))
        bandeira = LABELS_BANDEIRAS.get(band_k, "Mastercard")
        fech = cartao_info.get("dia_fechamento", 1)
        venc = cartao_info.get("dia_vencimento", 10)
        usado = max(0.0, lim_total - lim_disp)
        pct_uso = min(1.0, max(0.0, usado / lim_total)) if lim_total > 0 else 0.0

        return ft.Container(
            padding=pad(all_=18 if mobile else 22),
            bgcolor=cor_c,
            border_radius=16,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Icon(ft.Icons.CONTACTLESS_ROUNDED, color=ft.Colors.WHITE_70, size=24),
                                    ft.Text(nome_c, color=ft.Colors.WHITE, size=18 if mobile else 20, weight=ft.FontWeight.BOLD),
                                ],
                            ),
                            ft.Container(
                                padding=pad(h=10, v=4),
                                bgcolor="#FFFFFF24",
                                border_radius=8,
                                content=ft.Text(bandeira.upper(), color=ft.Colors.WHITE, size=11, weight=ft.FontWeight.BOLD),
                            ),
                        ],
                    ),
                    ft.ProgressBar(
                        value=pct_uso,
                        color=T.DESPESA if pct_uso > 0.8 else T.WARNING,
                        bgcolor="#FFFFFF30",
                        height=7,
                        border_radius=4,
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(f"Fecha dia {fech} · Vence dia {venc}", color=ft.Colors.WHITE_70, size=12),
                            ft.Text(
                                f"Em uso: {formatar_moeda(usado)} ({pct_uso * 100:.1f}%)",
                                color=ft.Colors.WHITE,
                                size=12,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ],
                    ),
                ],
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
            pacote = db.obter_relatorio_cartao(
                cartao_id=cartao_id,
                data_inicio=di_str,
                data_fim=df_str,
                filtros=c.to_rpc_filtros(),
            )
            cartao_info = pacote.get("cartao") or {}
            kpis = pacote.get("kpis") or {}
            evolucao = pacote.get("evolucao_diaria") or []
            por_cat = pacote.get("por_categoria") or []
            itens = pacote.get("lancamentos") or []
            total_reg = int(pacote.get("total_registros", len(itens)) or 0)

            nome_c = cartao_info.get("nome") or "Cartão de Crédito"
            nome_cartao_ref[0] = nome_c
            cor_c = cartao_info.get("cor") or T.WARNING

            gasto_per = float(kpis.get("total_gasto_periodo", 0) or 0)
            lim_total = float(kpis.get("limite_total", cartao_info.get("limite_total", 0)) or 0)
            lim_disp = float(kpis.get("limite_disponivel", cartao_info.get("limite_disponivel", 0)) or 0)
            tot_parc = float(kpis.get("total_parcelado", 0) or 0)
            tot_avista = float(kpis.get("total_a_vista", 0) or 0)

            # 1. Header
            container_header.content = criar_report_header(
                page,
                titulo=f"Fatura & Extrato · {nome_c}",
                subtitulo=(
                    f"Período de {formatar_data_br(di_str)} a {formatar_data_br(df_str)} "
                    f"· {total_reg} compra{'s' if total_reg != 1 else ''}"
                ),
                icone=ft.Icons.CREDIT_CARD_ROUNDED,
                cor_icone=cor_c,
                breadcrumbs=[
                    ("Cartões", "/cartoes"),
                    (nome_c, None),
                ],
                acoes_header=[spinner, btn_lancar_cartao],
            )

            # 2. Hero Plástico do Cartão
            container_hero.content = _construir_hero_cartao(cartao_info, lim_total, lim_disp)

            # 3. KPIs
            container_kpis.content = criar_kpi_strip(
                page,
                [
                    {
                        "titulo": "Gasto no Período",
                        "valor": formatar_moeda(gasto_per),
                        "subtitulo": f"{total_reg} compra{'s' if total_reg != 1 else ''} no período",
                        "cor": T.WARNING,
                        "icone": ft.Icons.SHOPPING_BAG_ROUNDED,
                    },
                    {
                        "titulo": "Limite Disponível",
                        "valor": formatar_moeda(lim_disp),
                        "subtitulo": f"De {formatar_moeda(lim_total)} total",
                        "cor": T.RECEITA if lim_disp > 0 else T.DESPESA,
                        "icone": ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                    },
                    {
                        "titulo": "Compras à Vista",
                        "valor": formatar_moeda(tot_avista),
                        "subtitulo": "Parcela única (1x)",
                        "cor": T.INFO,
                        "icone": ft.Icons.BOLT_ROUNDED,
                    },
                    {
                        "titulo": "Compras Parceladas",
                        "valor": formatar_moeda(tot_parc),
                        "subtitulo": "Parcelas no período",
                        "cor": "#8B5CF6",
                        "icone": ft.Icons.CALENDAR_VIEW_MONTH_ROUNDED,
                    },
                ],
            )

            # 4. Gráficos Analíticos do Cartão
            card_evolucao = construir_card_evolucao_diaria(
                evolucao,
                titulo="Ritmo Diário de Compras",
                subtitulo="Compras registradas no cartão dia a dia",
                modo_saldo=False,
            )
            card_ranking = construir_card_ranking_categorias(
                por_cat,
                titulo="Categorias neste Cartão",
                subtitulo="Toque em uma categoria para abrir seu detalhamento",
                cor_padrao=cor_c,
                on_categoria_click=lambda cid, _: ir_relatorio_categoria(
                    page,
                    cid,
                    ctx=c.com(categoria_id=cid, cartao_id=cartao_id, pagina=1),
                ),
            )
            container_graficos.controls = [card_evolucao, card_ranking]

            # 5. Barra de Filtros
            container_filter_bar.content = criar_filter_bar(
                page,
                ctx=c,
                on_change=_aplicar_novo_contexto,
                mostrar_chips_tipo=False,
                mostrar_filtro_conta=False,
                mostrar_filtro_cartao=False,
                mostrar_filtro_categoria=True,
                mostrar_filtro_regra=True,
                mostrar_filtro_forma=False,
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
                titulo_vazio="Nenhuma compra neste cartão para o período selecionado",
                subtitulo_vazio="Registre uma despesa no cartão de crédito ou altere o filtro de período.",
                label_cta_vazio="+ Lançar neste cartão",
                on_cta_vazio=_abrir_novo_lancamento_cartao,
            )

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar extrato do cartão: {ex}", "erro")
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
            container_hero,
            container_kpis,
            container_graficos,
            container_filter_bar,
            container_lista,
            ft.Container(height=28),
        ],
    )

    carregar(inicial=True)

    url_rota = f"/cartoes/{cartao_id}{contexto_atual[0].to_query()}"
    return criar_shell(
        page,
        rota_ativa=ROTA_CARTOES,
        conteudo=conteudo,
        rota_view=url_rota,
        titulo=nome_cartao_ref[0],
        mostrar_voltar=True,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
