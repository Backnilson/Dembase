"""
=============================================================================
DemBase v3 — views/relatorios/conta_report.py  (Flet 1.0.1)
Relatório Individual de Conta Bancária / Carteira (/contas/:conta_id).
Exibe:
- Banner Hero da Conta (cor, banco, tipo e Saldo Atual Global)
- 4 KPIs do Período: Saldo Inicial, Entradas (clicável), Saídas (clicável), Saldo Final
- Gráficos analíticos: Evolução do Saldo Acumulado + Ranking de Categorias
- FilterBar + TransactionList com perspectiva da conta (transferências sempre visíveis)
- Botão rápido "+ Lançar nesta conta" pré-selecionando a conta
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
from core.nav import ir_conta, ir_relatorio_categoria
from views.shell_view import criar_shell, ROTA_CONTAS
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

LABELS_TIPOS_CONTA = {
    "corrente": "Conta Corrente",
    "poupanca": "Conta Poupança",
    "dinheiro": "Carteira / Dinheiro",
    "investimento": "Investimento",
    "outro": "Outros",
}


def criar_view_relatorio_conta(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    params = match or {}
    conta_id = str(params.get("conta_id") or (ctx.conta_id if ctx else "") or "")

    est_p = obter_estado_periodo_atual(page)
    contexto_inicial = ctx or ReportContext.from_query(page, None, params)
    contexto_atual: list[ReportContext] = [
        contexto_inicial.com(
            conta_id=conta_id,
            data_inicio=contexto_inicial.data_inicio or est_p["data_inicio"],
            data_fim=contexto_inicial.data_fim or est_p["data_fim"],
        )
    ]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=18, height=18, stroke_width=2.2, visible=False)

    # Referências mutáveis para o Hero da Conta
    cor_conta_ref = [T.PRIMARY]
    txt_nome_conta = ft.Text("Carregando conta...", color=T.TEXT_PRIMARY, size=18 if mobile else 20, weight=ft.FontWeight.BOLD)
    txt_sub_conta = ft.Text("Conta Bancária", color=T.TEXT_MUTED, size=12)
    txt_saldo_global = ft.Text("R$ 0,00", color=T.PRIMARY, size=20 if mobile else 24, weight=ft.FontWeight.BOLD)
    icone_hero_box = ft.Container(
        content=ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, color=T.PRIMARY, size=22),
        bgcolor=f"{T.PRIMARY}1F",
        border_radius=12,
        padding=pad(all_=12),
    )

    container_header = ft.Container()
    container_kpis = ft.Container()
    container_graficos = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])
    container_filter_bar = ft.Container()
    container_lista = ft.Container()

    def _safe_update():
        try:
            page.update()
        except Exception:
            pass

    def _Alternar_filtro_tipo(tipo_alvo: str):
        c = contexto_atual[0]
        novo_tipo = None if c.tipo == tipo_alvo else tipo_alvo
        ir_conta(page, conta_id, c.com(tipo=novo_tipo, pagina=1), replace=True)

    def _aplicar_novo_contexto(novo_ctx: ReportContext):
        ir_conta(page, conta_id, novo_ctx.com(conta_id=conta_id), replace=True)

    def _ao_mudar_pagina(nova_pag: int):
        c = contexto_atual[0].com(pagina=nova_pag)
        contexto_atual[0] = c
        carregar(inicial=False)

    def _abrir_novo_lancamento_conta(_=None):
        c = contexto_atual[0]
        tipo_padrao = c.tipo if c.tipo in ("Receita", "Despesa", "Transferencia") else "Despesa"
        abrir_lancamento(
            page,
            tipo_inicial=tipo_padrao,
            conta_inicial=conta_id,
            on_saved=lambda: carregar(inicial=False),
        )

    btn_lancar_conta = ft.FilledButton(
        content=ft.Row(
            spacing=6,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                ft.Text(
                    "Lançar" if mobile else "Lançar nesta conta",
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
        on_click=_abrir_novo_lancamento_conta,
    )

    hero_conta = ft.Container(
        padding=pad(all_=16 if mobile else 20),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    spacing=12,
                    expand=True,
                    controls=[
                        icone_hero_box,
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                txt_nome_conta,
                                txt_sub_conta,
                            ],
                        ),
                    ],
                ),
                ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    spacing=2,
                    controls=[
                        ft.Text("Saldo Atual Global", color=T.TEXT_MUTED, size=11),
                        txt_saldo_global,
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
            pacote = db.obter_relatorio_conta(
                conta_id=conta_id,
                data_inicio=di_str,
                data_fim=df_str,
                filtros=c.to_rpc_filtros(),
            )
            conta_info = pacote.get("conta") or {}
            kpis = pacote.get("kpis") or {}
            evolucao = pacote.get("evolucao_saldo") or []
            por_cat = pacote.get("por_categoria") or []
            itens = pacote.get("lancamentos") or []
            total_reg = int(pacote.get("total_registros", len(itens)) or 0)

            nome_conta = conta_info.get("nome") or "Conta Bancária"
            cor_c = conta_info.get("cor") or T.PRIMARY
            cor_conta_ref[0] = cor_c
            tipo_c = LABELS_TIPOS_CONTA.get(
                db.normalizar_tipo_conta(conta_info.get("tipo_conta")),
                "Conta Corrente",
            )
            banco_c = conta_info.get("banco") or ""
            sub_c = f"{tipo_c} · {banco_c}" if banco_c else tipo_c
            saldo_atual_global = float(conta_info.get("saldo_atual", 0) or 0)

            txt_nome_conta.value = nome_conta
            txt_sub_conta.value = sub_c
            txt_saldo_global.value = formatar_moeda(saldo_atual_global)
            txt_saldo_global.color = T.PRIMARY if saldo_atual_global >= 0 else T.DESPESA
            icone_hero_box.bgcolor = f"{cor_c}22"
            icone_hero_box.content = ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, color=cor_c, size=22)

            saldo_ini_per = float(kpis.get("saldo_inicial_periodo", 0) or 0)
            entradas_per = float(kpis.get("entradas", 0) or 0)
            saidas_per = float(kpis.get("saidas", 0) or 0)
            saldo_fim_per = float(kpis.get("saldo_final_periodo", saldo_ini_per + entradas_per - saidas_per) or 0)
            transf_rec = float(kpis.get("transferencias_recebidas", 0) or 0)
            transf_env = float(kpis.get("transferencias_enviadas", 0) or 0)

            # 1. Header
            container_header.content = criar_report_header(
                page,
                titulo=f"Extrato · {nome_conta}",
                subtitulo=(
                    f"Período de {formatar_data_br(di_str)} a {formatar_data_br(df_str)} "
                    f"· {total_reg} movimentaç{'ão' if total_reg == 1 else 'ões'}"
                ),
                icone=ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                cor_icone=cor_c,
                breadcrumbs=[
                    ("Contas", "/contas"),
                    (nome_conta, None),
                ],
                acoes_header=[spinner, btn_lancar_conta],
            )

            # 2. KPIs (Entradas e Saídas clicáveis para filtrar in-place)
            container_kpis.content = criar_kpi_strip(
                page,
                [
                    {
                        "titulo": "Saldo Inicial do Período",
                        "valor": formatar_moeda(saldo_ini_per),
                        "subtitulo": f"Em {formatar_data_br(di_str)}",
                        "cor": T.INFO if saldo_ini_per >= 0 else T.DESPESA,
                        "icone": ft.Icons.HISTORY_ROUNDED,
                    },
                    {
                        "titulo": "Entradas no Período",
                        "valor": formatar_moeda(entradas_per),
                        "subtitulo": (
                            f"Inclui +{formatar_moeda(transf_rec)} transf."
                            if transf_rec > 0
                            else "Clique para filtrar entradas"
                        ),
                        "cor": T.RECEITA,
                        "icone": ft.Icons.ARROW_UPWARD_ROUNDED,
                        "ativo": c.tipo == "Receita",
                        "on_click": lambda _: _Alternar_filtro_tipo("Receita"),
                    },
                    {
                        "titulo": "Saídas no Período",
                        "valor": formatar_moeda(saidas_per),
                        "subtitulo": (
                            f"Inclui -{formatar_moeda(transf_env)} transf."
                            if transf_env > 0
                            else "Clique para filtrar saídas"
                        ),
                        "cor": T.DESPESA,
                        "icone": ft.Icons.ARROW_DOWNWARD_ROUNDED,
                        "ativo": c.tipo == "Despesa",
                        "on_click": lambda _: _Alternar_filtro_tipo("Despesa"),
                    },
                    {
                        "titulo": "Saldo Final do Período",
                        "valor": formatar_moeda(saldo_fim_per),
                        "subtitulo": f"Em {formatar_data_br(df_str)}",
                        "cor": T.RECEITA if saldo_fim_per >= 0 else T.DESPESA,
                        "icone": ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                    },
                ],
            )

            # 3. Gráficos Analíticos da Conta
            card_evolucao = construir_card_evolucao_diaria(
                evolucao,
                titulo="Evolução do Saldo no Período",
                subtitulo="Saldo acumulado dia a dia após entradas e saídas",
                modo_saldo=True,
            )
            card_ranking = construir_card_ranking_categorias(
                por_cat,
                titulo="Principais Categorias nesta Conta",
                subtitulo="Toque em uma categoria para abrir seu relatório",
                cor_padrao=cor_c,
                on_categoria_click=lambda cid, _: ir_relatorio_categoria(
                    page,
                    cid,
                    c.com(categoria_id=cid, conta_id=conta_id, pagina=1),
                ),
            )
            container_graficos.controls = [card_evolucao, card_ranking]

            # 4. Barra de Filtros (sem seletor de conta, pois já estamos na conta)
            container_filter_bar.content = criar_filter_bar(
                page,
                ctx=c,
                on_change=_aplicar_novo_contexto,
                mostrar_chips_tipo=True,
                mostrar_filtro_conta=False,
                mostrar_filtro_cartao=False,
                mostrar_filtro_categoria=True,
                mostrar_filtro_regra=False,
                mostrar_filtro_forma=True,
            )

            # 5. Lista de Transações (com perspectiva da conta para transferências)
            container_lista.content = criar_transaction_list(
                page,
                itens=itens,
                total_registros=total_reg,
                pagina_atual=c.pagina,
                page_size=c.page_size,
                on_page_change=_ao_mudar_pagina,
                on_refresh=lambda: carregar(inicial=False),
                conta_perspectiva_id=conta_id,
                mostrar_transferencias_padrao=True,
                titulo_vazio="Nenhuma movimentação nesta conta para o período",
                subtitulo_vazio="Registre uma receita, despesa ou transferência nesta conta.",
                label_cta_vazio="+ Lançar nesta conta",
                on_cta_vazio=_abrir_novo_lancamento_conta,
            )

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar extrato da conta: {ex}", "erro")
        finally:
            spinner.visible = False
            if not inicial:
                _safe_update()

    # Callbacks do seletor global de período no Shell
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
            hero_conta,
            container_kpis,
            container_graficos,
            container_filter_bar,
            container_lista,
            ft.Container(height=28),
        ],
    )

    carregar(inicial=True)

    url_rota = f"/contas/{conta_id}{contexto_atual[0].to_query()}"
    return criar_shell(
        page,
        rota_ativa=ROTA_CONTAS,
        conteudo=conteudo,
        rota_view=url_rota,
        titulo=txt_nome_conta.value or "Extrato da Conta",
        mostrar_voltar=True,
        on_mes_ano_change=on_mes_ano,
        on_periodo_change=on_periodo,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
