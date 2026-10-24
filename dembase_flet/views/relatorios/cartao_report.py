"""
=============================================================================
DemBase v3 — views/relatorios/cartao_report.py  (Flet 1.0.1)
Relatório Individual de Cartão de Crédito (/cartoes/:cartao_id).
Exibe:
- Banner Hero do Cartão (plástico colorido, bandeira, fechamento, vencimento, barra de limite)
- Seletor de Fatura de Destino (Dropdown com status Aberta/Fechada/Paga)
- 4 KPIs: Gasto na Fatura, Limite Disponível, Compras à Vista, Compras Parceladas
- Gráficos: Ritmo Diário de Compras da Fatura + Ranking de Categorias
- FilterBar + TransactionList com exibição explícita de parcelas ('Parcela X de Y')
- Botão "+ Lançar neste cartão" pré-selecionando o cartão
=============================================================================
"""
from __future__ import annotations
from datetime import date
from calendar import monthrange
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

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]


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
    container_fatura_seletor = ft.Container()
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

    async def _carregar_async(inicial: bool = False):
        c = contexto_atual[0]
        di_str = c.data_inicio.isoformat()
        df_str = c.data_fim.isoformat()

        if not inicial:
            spinner.visible = True
            _safe_update()

        try:
            filtros_rpc = c.to_rpc_filtros()
            filtros_rpc["mes"] = c.data_inicio.month
            filtros_rpc["ano"] = c.data_inicio.year
            if c.fatura_id:
                filtros_rpc["fatura_id"] = c.fatura_id

            pacote = await db.obter_relatorio_cartao_async(
                cartao_id=cartao_id,
                data_inicio=di_str,
                data_fim=df_str,
                filtros=filtros_rpc,
            )
            cartao_info = pacote.get("cartao") or {}
            kpis_rpc = pacote.get("kpis") or pacote.get("totais") or {}
            evolucao = pacote.get("evolucao_diaria") or []
            por_cat = pacote.get("por_categoria") or []
            itens = pacote.get("lancamentos") or []
            faturas_lista = pacote.get("faturas") or []
            fat_sel = pacote.get("fatura_selecionada") or {}

            nome_c = cartao_info.get("nome") or "Cartão de Crédito"
            nome_cartao_ref[0] = nome_c
            cor_c = cartao_info.get("cor") or T.WARNING

            # =================================================================
            # BUG 2 CORRIGIDO: Varrer a lista de transações filtradas daquela
            # fatura específica e somar com precisão matemática os valores.
            # =================================================================
            calc_gasto = 0.0
            calc_avista = 0.0
            calc_parc = 0.0

            for it in itens:
                val = float(it.get("valor", 0) or 0)
                calc_gasto += val
                tot_p = int(it.get("total_parcelas", 1) or 1)
                is_rec = (it.get("tipo_recorrencia") == "fixa" or bool(it.get("recorrente_id")))
                if tot_p > 1 or is_rec:
                    calc_parc += val
                else:
                    calc_avista += val

            total_reg = int(pacote.get("total_registros", len(itens)) or len(itens))

            if len(itens) > 0:
                gasto_per = calc_gasto
                tot_avista = calc_avista
                tot_parc = calc_parc
            else:
                gasto_per = float(kpis_rpc.get("total_gasto_periodo") or kpis_rpc.get("gasto_periodo", 0) or 0)
                tot_avista = float(kpis_rpc.get("total_a_vista") or kpis_rpc.get("total_avista", 0) or 0)
                tot_parc = float(kpis_rpc.get("total_parcelado", 0) or 0)

            lim_total = float(kpis_rpc.get("limite_total", cartao_info.get("limite_total", 0)) or 0)
            lim_disp = float(kpis_rpc.get("limite_disponivel", cartao_info.get("limite_disponivel", 0)) or 0)
            if lim_disp == 0 and lim_total > 0 and gasto_per > 0:
                lim_disp = max(0.0, lim_total - gasto_per)

            # Mês e ano da fatura selecionada
            f_mes_alvo = fat_sel.get("mes") or c.data_inicio.month
            f_ano_alvo = fat_sel.get("ano") or c.data_inicio.year
            nome_mes_alvo = MESES_PT[f_mes_alvo] if 1 <= f_mes_alvo <= 12 else str(f_mes_alvo)

            # 1. Header com referência à fatura
            container_header.content = criar_report_header(
                page,
                titulo=f"Fatura & Extrato · {nome_c}",
                subtitulo=f"Fatura de {nome_mes_alvo}/{f_ano_alvo} · {total_reg} compra{'s' if total_reg != 1 else ''}",
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

            # =================================================================
            # BUG 1 CORRIGIDO: Seletor de Fatura de Destino
            # =================================================================
            faturas_map: dict[str, dict] = {}
            opcoes_dd_faturas: list[ft.dropdown.Option] = []

            for f in faturas_lista:
                fid = str(f.get("id"))
                fm = int(f.get("mes", 1))
                fa = int(f.get("ano", f_ano_alvo))
                st = str(f.get("status") or "aberta").lower()
                st_label = "Aberta" if st == "aberta" else ("Fechada" if st == "fechada" else "Paga")
                m_txt = MESES_PT[fm] if 1 <= fm <= 12 else str(fm)
                v_fatura = float(f.get("valor_total", 0) or 0)
                label = f"{m_txt}/{fa} · {st_label}" + (f" ({formatar_moeda(v_fatura)})" if v_fatura > 0 else "")
                opcoes_dd_faturas.append(ft.dropdown.Option(key=fid, text=label))
                faturas_map[fid] = f

            if not opcoes_dd_faturas:
                dyn_opts = db.listar_faturas_opcoes_cartao(cartao_id)
                for opt in dyn_opts:
                    opcoes_dd_faturas.append(ft.dropdown.Option(key=str(opt["id"]), text=opt["label"]))
                    faturas_map[str(opt["id"])] = opt

            fatura_selecionada_id = str(fat_sel.get("id") or "") if fat_sel.get("id") else (c.fatura_id or "")
            if fatura_selecionada_id not in faturas_map:
                for fid, f_d in faturas_map.items():
                    if f_d.get("mes") == f_mes_alvo and f_d.get("ano") == f_ano_alvo:
                        fatura_selecionada_id = fid
                        break

            def _ao_selecionar_fatura(e):
                escolhido = e.data or e.control.value
                info = faturas_map.get(str(escolhido))
                if info:
                    novo_m = int(info.get("mes", f_mes_alvo))
                    novo_a = int(info.get("ano", f_ano_alvo))
                    _, u_dia = monthrange(novo_a, novo_m)
                    d_ini = date(novo_a, novo_m, 1)
                    d_fim = date(novo_a, novo_m, u_dia)
                    atualizar_datas_periodo_global(page, d_ini, d_fim, novo_m, novo_a)
                    contexto_atual[0] = contexto_atual[0].com(
                        fatura_id=str(escolhido) if not str(escolhido).startswith("futura_") else None,
                        data_inicio=d_ini,
                        data_fim=d_fim,
                        pagina=1,
                    )
                    carregar(inicial=False)

            dd_fatura = ft.Dropdown(
                label="Fatura Selecionada (Destino)",
                value=fatura_selecionada_id or (opcoes_dd_faturas[0].key if opcoes_dd_faturas else ""),
                options=opcoes_dd_faturas,
                expand=True,
                on_select=_ao_selecionar_fatura,
                **T.dropdown_estilo(),
            )

            container_fatura_seletor.content = ft.Container(
                padding=pad(h=14, v=10),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, color=T.PRIMARY, size=22),
                                ft.Column(
                                    spacing=1,
                                    tight=True,
                                    controls=[
                                        ft.Text("Visualizando Fatura", size=11, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                                        ft.Text(f"{nome_mes_alvo}/{f_ano_alvo}", size=13.5, color=T.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                            ],
                        ),
                        ft.Container(
                            content=dd_fatura,
                            expand=True,
                        ),
                    ],
                ),
            )

            # 3. KPIs com valores somados corretamente
            container_kpis.content = criar_kpi_strip(
                page,
                [
                    {
                        "titulo": "Gasto na Fatura",
                        "valor": formatar_moeda(gasto_per),
                        "subtitulo": f"{total_reg} compra{'s' if total_reg != 1 else ''} nesta fatura",
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
                        "subtitulo": "Parcelas e assinaturas",
                        "cor": "#8B5CF6",
                        "icone": ft.Icons.CALENDAR_VIEW_MONTH_ROUNDED,
                    },
                ],
            )

            # 4. Gráficos Analíticos
            card_evolucao = construir_card_evolucao_diaria(
                evolucao,
                titulo="Ritmo de Compras da Fatura",
                subtitulo="Compras computadas nesta fatura por data de transação",
                modo_saldo=False,
            )
            card_ranking = construir_card_ranking_categorias(
                por_cat,
                titulo="Categorias nesta Fatura",
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

            # 6. Lista de Transações da Fatura
            container_lista.content = criar_transaction_list(
                page,
                itens=itens,
                total_registros=total_reg,
                pagina_atual=c.pagina,
                page_size=c.page_size,
                on_page_change=_ao_mudar_pagina,
                on_refresh=lambda: carregar(inicial=False),
                mostrar_transferencias_padrao=False,
                titulo_vazio="Nenhuma compra vinculada a esta fatura",
                subtitulo_vazio="Registre uma despesa no cartão ou selecione outra fatura de destino no topo.",
                label_cta_vazio="+ Lançar neste cartão",
                on_cta_vazio=_abrir_novo_lancamento_cartao,
            )

        except Exception as ex:
            container_loading.visible = False
            container_corpo.visible = True
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar extrato do cartão: {ex}", "erro")
        finally:
            container_loading.visible = False
            container_corpo.visible = True
            spinner.visible = False
            _safe_update()

    def carregar(inicial: bool = False):
        try:
            page.run_task(_carregar_async, inicial)
        except Exception:
            import asyncio
            asyncio.create_task(_carregar_async(inicial))

    def on_periodo(d_ini: str, d_fim: str, m: int, a: int):
        est = atualizar_datas_periodo_global(page, d_ini, d_fim, m, a)
        contexto_atual[0] = contexto_atual[0].com(
            data_inicio=est["data_inicio"],
            data_fim=est["data_fim"],
            fatura_id=None,
            pagina=1,
        )
        carregar(inicial=False)

    def on_mes_ano(m: int, a: int):
        _, u_dia = monthrange(a, m)
        d_ini = date(a, m, 1)
        d_fim = date(a, m, u_dia)
        atualizar_datas_periodo_global(page, d_ini, d_fim, m, a)
        contexto_atual[0] = contexto_atual[0].com(
            data_inicio=d_ini,
            data_fim=d_fim,
            fatura_id=None,
            pagina=1,
        )
        carregar(inicial=False)

    container_loading = ft.Container(
        alignment=ft.Alignment(0, 0),
        padding=pad(all_=50),
        content=ft.Column(
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.ProgressRing(color=T.WARNING, width=32, height=32, stroke_width=3),
                ft.Text("Carregando fatura e extrato do cartão...", color=T.TEXT_MUTED, size=13, weight=ft.FontWeight.W_500),
            ],
        ),
        visible=True,
    )

    container_corpo = ft.Column(
        spacing=14 if mobile else 16,
        visible=False,
        controls=[
            container_hero,
            container_fatura_seletor,
            container_kpis,
            container_graficos,
            container_filter_bar,
            container_lista,
        ],
    )

    conteudo = ft.Column(
        spacing=14 if mobile else 16,
        controls=[
            container_header,
            container_loading,
            container_corpo,
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
