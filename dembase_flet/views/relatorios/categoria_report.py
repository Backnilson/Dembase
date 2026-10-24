"""
=============================================================================
DemBase v3 — views/relatorios/categoria_report.py  (Flet 1.0.1)
Diagnóstico e Relatório Analítico por Categoria (/relatorios/categoria/:cat_id).
Exibe:
- Header com Breadcrumbs + botão rápido "+ Lançar nesta categoria"
- Seletor rápido de Categorias em chips horizontais
- 4 KPIs do Período: Total na Categoria, Pagos, Pendentes, Média Diária
- Barra de Filtros (FilterBar) com fixar_categoria=True
- Gráficos analíticos: Subcategorias, Participação por Pote e Evolução Diária
- Lista de Transações (TransactionList) com edição rápida de Pote e Status
=============================================================================
"""
from __future__ import annotations

import flet as ft

from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, formatar_data_br
from core.responsive import is_mobile
from core.report_context import ReportContext
from core.router import RouteMatch
from core.nav import ir_relatorio_categoria
from views.shell_view import criar_shell, ROTA_RELATORIOS
from views.widgets.lancamento_sheet import abrir_lancamento
from views.widgets.report import (
    ReportScaffold,
    FilterBar,
    TransactionList,
    criar_report_header,
    criar_kpi_strip,
    construir_card_ranking_categorias,
    construir_card_ranking_potes,
    construir_card_evolucao_diaria,
)
import services.supabase_client as db

LIMITE_PAGINA = 50


def criar_view_relatorio_categoria(
    page: ft.Page,
    match: RouteMatch | dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)

    # Extrai o ID da categoria com resiliência total a RouteMatch ou dict
    if hasattr(match, "params_path") and match.params_path:
        cat_id = str(match.params_path.get("categoria_id") or match.params_path.get("cat_id") or "")
    elif isinstance(match, dict):
        cat_id = str(match.get("categoria_id") or match.get("cat_id") or "")
    else:
        cat_id = ""

    if not cat_id and ctx and ctx.categoria_id:
        cat_id = str(ctx.categoria_id)

    # Carrega metadados de todas as categorias para o seletor horizontal
    try:
        todas_categorias = db.listar_categorias() or []
    except Exception:
        todas_categorias = []

    cat_map = {str(c.get("id")): c for c in todas_categorias if c.get("id")}

    if not cat_id and todas_categorias:
        cat_id = str(todas_categorias[0].get("id"))

    cat_meta = cat_map.get(cat_id) or {}
    nome_cat_inicial = cat_meta.get("nome") or "Categoria"
    cor_cat_inicial = cat_meta.get("cor") or T.PRIMARY

    contexto_inicial = ctx or ReportContext.from_query(page, match)
    ctx_atual = [
        contexto_inicial.com(
            categoria_id=cat_id,
            tipo=contexto_inicial.tipo or cat_meta.get("tipo") or "Despesa",
        )
    ]
    limite_atual = [LIMITE_PAGINA]

    spinner = ft.ProgressRing(color=cor_cat_inicial, width=18, height=18, stroke_width=2, visible=False)
    tam_kpi = 17 if mobile else 20

    txt_titulo = ft.Text(
        f"Categoria · {nome_cat_inicial}",
        color=T.TEXT_PRIMARY,
        size=20 if mobile else 22,
        weight=ft.FontWeight.BOLD,
    )
    txt_subtitulo = ft.Text("", color=T.TEXT_MUTED, size=12)

    txt_kpi_total    = ft.Text("R$ 0,00", color=cor_cat_inicial, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_kpi_pago     = ft.Text("R$ 0,00", color=T.RECEITA, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_kpi_pendente = ft.Text("R$ 0,00", color=T.WARNING, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_kpi_media    = ft.Text("R$ 0,00", color=T.INFO,    size=tam_kpi, weight=ft.FontWeight.BOLD)

    kpi_container = ft.Container()
    graficos_row = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])

    def _construir_seletor_categorias() -> ft.Container:
        """Chips horizontais para navegar com 1 toque entre qualquer categoria."""
        if not todas_categorias:
            return ft.Container()

        chips: list[ft.Control] = []
        for c in todas_categorias:
            cid = str(c.get("id") or "")
            cnome = c.get("nome") or "Categoria"
            ccor = c.get("cor") or T.PRIMARY
            selecionada = (cid == cat_id)

            chips.append(
                ft.Container(
                    padding=pad(h=12, v=6),
                    bgcolor=f"{ccor}22" if selecionada else T.SURFACE_ALT,
                    border=borda(1.5, ccor) if selecionada else borda(1, f"{T.BORDER}40"),
                    border_radius=20,
                    ink=True,
                    on_click=(
                        (lambda _, cid_alvo=cid: ir_relatorio_categoria(page, cid_alvo, tipo=ctx_atual[0].tipo, ctx=ctx_atual[0]))
                        if not selecionada
                        else None
                    ),
                    tooltip=f"Ver lançamentos de {cnome}" if not selecionada else "Categoria atual",
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Container(
                                width=8,
                                height=8,
                                bgcolor=ccor,
                                border_radius=4,
                            ),
                            ft.Text(
                                cnome,
                                color=ccor if selecionada else T.TEXT_PRIMARY,
                                size=12,
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

    def _ao_clicar_subcategoria(sub: dict):
        sid = sub.get("subcategoria_id")
        novo_sid = None if str(ctx_atual[0].subcategoria_id or "") == str(sid or "") else str(sid or "")
        filter_bar.atualizar_contexto(ctx_atual[0].com(subcategoria_id=novo_sid), emitir=True)

    def _ao_clicar_pote(pt: dict):
        pid = pt.get("pote_id") or pt.get("id")
        if pid:
            novo_pid = None if str(ctx_atual[0].pote_id or "") == str(pid or "") else str(pid or "")
            filter_bar.atualizar_contexto(ctx_atual[0].com(pote_id=novo_pid), emitir=True)

    def _ao_clicar_dia(dt_iso: str):
        novo = ctx_atual[0].com(data_inicio=dt_iso, data_fim=dt_iso)
        filter_bar.atualizar_contexto(novo, emitir=True)

    async def _carregar_async(inicial: bool = False):
        c = ctx_atual[0]
        meta = cat_map.get(cat_id) or {}
        nome_c = meta.get("nome") or "Categoria"
        cor_c = meta.get("cor") or T.PRIMARY

        txt_titulo.value = f"Categoria · {nome_c}"
        txt_subtitulo.value = f"Período: {formatar_data_br(c.data_inicio)} a {formatar_data_br(c.data_fim)}"
        txt_kpi_total.color = cor_c

        if not inicial:
            spinner.visible = True
            try:
                page.update()
            except Exception:
                pass

        try:
            pacote = await db.obter_relatorio_lancamentos_async(
                data_inicio=c.data_inicio.isoformat(),
                data_fim=c.data_fim.isoformat(),
                filtros=c.to_rpc_filtros(),
                limite=limite_atual[0],
                offset=0,
            )
            totais = pacote.get("totais") or {}
            tot_val = float(totais.get("total_filtrado", 0) or 0)
            pago_val = float(totais.get("pago", 0) or 0)
            pend_val = float(totais.get("pendente", 0) or 0)
            med_val = float(totais.get("media_diaria", 0) or 0)
            qtd_reg = int(pacote.get("total_registros", 0) or 0)

            txt_kpi_total.value    = formatar_moeda(tot_val)
            txt_kpi_pago.value     = formatar_moeda(pago_val)
            txt_kpi_pendente.value = formatar_moeda(pend_val)
            txt_kpi_media.value    = formatar_moeda(med_val)

            lbl_pago = "Recebido" if c.tipo == "Receita" else "Pago / Realizado"
            kpi_container.content = criar_kpi_strip(
                [
                    {
                        "titulo": f"Total em {nome_c}",
                        "valor_ctrl": txt_kpi_total,
                        "cor": cor_c,
                        "icone": ft.Icons.DONUT_LARGE_ROUNDED,
                        "subtitulo": f"{qtd_reg} lançamento(s)",
                        "ativo": c.status is None,
                        "on_click": lambda _: filter_bar.atualizar_contexto(c.com(status=None)),
                    },
                    {
                        "titulo": lbl_pago,
                        "valor_ctrl": txt_kpi_pago,
                        "cor": T.RECEITA,
                        "icone": ft.Icons.CHECK_CIRCLE_ROUNDED,
                        "subtitulo": "Clique para filtrar pagos",
                        "ativo": c.status == "Pago",
                        "on_click": lambda _: filter_bar.atualizar_contexto(
                            c.com(status=None if c.status == "Pago" else "Pago")
                        ),
                    },
                    {
                        "titulo": "Pendente / Previsto",
                        "valor_ctrl": txt_kpi_pendente,
                        "cor": T.WARNING,
                        "icone": ft.Icons.SCHEDULE_ROUNDED,
                        "subtitulo": "Clique para filtrar pendentes",
                        "ativo": c.status == "Pendente",
                        "on_click": lambda _: filter_bar.atualizar_contexto(
                            c.com(status=None if c.status == "Pendente" else "Pendente")
                        ),
                    },
                    {
                        "titulo": "Média Diária",
                        "valor_ctrl": txt_kpi_media,
                        "cor": T.INFO,
                        "icone": ft.Icons.TIMELINE_ROUNDED,
                        "subtitulo": "Gasto diário médio",
                    },
                ],
                mobile=mobile,
            )

            por_subcat = pacote.get("por_subcategoria") or []
            por_pote = pacote.get("por_pote") or []
            por_dia = pacote.get("por_dia") or []

            cards_graficos = []

            # 1. Ranking de Subcategorias desta categoria
            if por_subcat:
                subcat_formatadas = [
                    {
                        "nome": s.get("nome") or "Geral",
                        "cor": cor_c,
                        "total": float(s.get("total", 0) or 0),
                        "percentual": float(s.get("percentual", 0) or 0),
                        "qtd": int(s.get("qtd", 0) or 0),
                        "subcategoria_id": s.get("subcategoria_id"),
                    }
                    for s in por_subcat
                ]
                cards_graficos.append(
                    construir_card_ranking_categorias(
                        categorias=subcat_formatadas,
                        titulo="Subcategorias",
                        subtitulo="Toque em uma subcategoria para filtrar",
                        cor_padrao=cor_c,
                        on_click_categoria=_ao_clicar_subcategoria,
                        col={"xs": 12, "md": 4},
                    )
                )

            # 2. Potes Financeiros desta categoria
            potes_com_dados = [p for p in por_pote if p.get("pote_id") is not None]
            if potes_com_dados and c.tipo != "Receita":
                cards_graficos.append(
                    construir_card_ranking_potes(
                        potes=potes_com_dados,
                        titulo="Participação por Pote",
                        subtitulo="Toque em um pote para filtrar",
                        cor_padrao=cor_c,
                        on_click_pote=_ao_clicar_pote,
                        pote_selecionado_id=c.pote_id,
                        col={"xs": 12, "md": 4 if por_subcat else 6},
                    )
                )

            # 3. Evolução Diária
            cards_graficos.append(
                construir_card_evolucao_diaria(
                    por_dia=por_dia,
                    titulo="Movimentação Dia a Dia",
                    subtitulo="Toque em uma coluna para focar naquele dia",
                    modo_saldo=False,
                    on_click_dia=_ao_clicar_dia,
                    col={"xs": 12, "md": 4 if por_subcat and potes_com_dados else 6},
                )
            )
            graficos_row.controls = cards_graficos

            lista_tx.renderizar(
                lancamentos=pacote.get("lancamentos") or [],
                total_registros=qtd_reg,
            )

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar categoria: {ex}", "erro")
        finally:
            scaffold.set_loading(False, page)
            spinner.visible = False
            try:
                page.update()
            except Exception:
                pass

    def carregar(inicial: bool = False):
        try:
            page.run_task(_carregar_async, inicial)
        except Exception:
            import asyncio
            asyncio.create_task(_carregar_async(inicial))

    def _ao_mudar_filtro(novo_ctx: ReportContext):
        ctx_atual[0] = novo_ctx.com(categoria_id=cat_id)
        limite_atual[0] = LIMITE_PAGINA
        carregar(inicial=False)

    def _carregar_mais():
        limite_atual[0] += LIMITE_PAGINA
        carregar(inicial=False)

    def _abrir_novo(_=None):
        abrir_lancamento(
            page,
            tipo_inicial=ctx_atual[0].tipo or "Despesa",
            categoria_inicial=cat_id,
            conta_inicial=ctx_atual[0].conta_id,
            cartao_inicial=ctx_atual[0].cartao_id,
            pote_inicial=ctx_atual[0].pote_id,
            on_saved=lambda: carregar(inicial=False),
        )

    filter_bar = FilterBar(
        page=page,
        ctx=ctx_atual[0],
        on_change=_ao_mudar_filtro,
        mostrar_chips_tipo=True,
        fixar_categoria=True,
    )

    lista_tx = TransactionList(
        page=page,
        on_refresh=lambda: carregar(inicial=False),
        on_carregar_mais=_carregar_mais,
        on_novo_lancamento=_abrir_novo,
    )

    breadcrumbs = [
        ("Dashboard", "/dashboard"),
        ("Relatórios", "/relatorios"),
        (f"Categoria: {nome_cat_inicial}", None),
    ]

    btn_lancar_header = ft.FilledButton(
        content=ft.Row(
            spacing=6,
            tight=True,
            controls=[
                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                ft.Text("Lançar", color=ft.Colors.WHITE, size=12.5, weight=ft.FontWeight.W_600),
            ],
        ),
        on_click=_abrir_novo,
        style=ft.ButtonStyle(
            bgcolor=cor_cat_inicial,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=14, v=10),
        ),
    )

    header = criar_report_header(
        page=page,
        titulo_ctrl=txt_titulo,
        subtitulo_ctrl=txt_subtitulo,
        spinner=spinner,
        breadcrumbs=breadcrumbs,
        icone=ft.Icons.CATEGORY_ROUNDED,
        cor_icone=cor_cat_inicial,
        acoes_header=[btn_lancar_header],
        mobile=mobile,
    )

    scaffold = ReportScaffold(
        header=header,
        filter_bar=filter_bar,
        kpi_strip=kpi_container,
        secao_extra=_construir_seletor_categorias(),
        graficos_row=graficos_row,
        transaction_list=lista_tx,
        loading=True,
        loading_text=f"Carregando {nome_cat_inicial}...",
    )

    def _on_periodo_shell(d_ini: str, d_fim: str, _m: int, _a: int):
        ctx_atual[0] = ctx_atual[0].com(data_inicio=d_ini, data_fim=d_fim, categoria_id=cat_id)
        filter_bar.ctx = ctx_atual[0]
        carregar(inicial=False)

    carregar(inicial=True)

    rota_view_url = getattr(match, "rota_completa", None) or f"/relatorios/categoria/{cat_id}"
    return criar_shell(
        page=page,
        rota_ativa=ROTA_RELATORIOS,
        rota_view=rota_view_url,
        titulo=f"Categoria · {nome_cat_inicial}",
        mostrar_voltar=True,
        conteudo=scaffold,
        on_periodo_change=_on_periodo_shell,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
