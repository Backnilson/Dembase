"""
=============================================================================
DemBase v3 — views/relatorios/lancamentos_report.py  (Flet 1.0.1)
Relatório Geral de Lançamentos (/relatorios/lancamentos):
- Atende o clique nos cards de "Receitas" e "Despesas" do Dashboard
- Herda o período global selecionado no Dashboard
- Troca de período ou filtros recarrega in-place via RPC get_relatorio_lancamentos
=============================================================================
"""
from __future__ import annotations

import flet as ft

from core import theme as T
from core.theme import mostrar_feedback
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
)
from views.widgets.report.scaffold import (
    construir_card_ranking_categorias,
    construir_card_evolucao_diaria,
)
import services.supabase_client as db

LIMITE_PAGINA = 50


def criar_view_relatorio_lancamentos(
    page: ft.Page,
    match: RouteMatch,
    ctx_inicial: ReportContext,
) -> ft.View:
    mobile = is_mobile(page)
    ctx_atual = [ctx_inicial]
    limite_atual = [LIMITE_PAGINA]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=18, height=18, stroke_width=2, visible=False)
    tam_kpi = 17 if mobile else 20

    txt_titulo = ft.Text("Relatório de Lançamentos", color=T.TEXT_PRIMARY, size=20 if mobile else 22, weight=ft.FontWeight.BOLD)
    txt_subtitulo = ft.Text("", color=T.TEXT_MUTED, size=12)

    txt_kpi_total    = ft.Text("R$ 0,00", color=T.PRIMARY, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_kpi_pago     = ft.Text("R$ 0,00", color=T.RECEITA, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_kpi_pendente = ft.Text("R$ 0,00", color=T.WARNING, size=tam_kpi, weight=ft.FontWeight.BOLD)
    txt_kpi_media    = ft.Text("R$ 0,00", color=T.INFO,    size=tam_kpi, weight=ft.FontWeight.BOLD)

    kpi_container = ft.Container()
    graficos_row = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])

    def _titulo_por_tipo(tipo: str | None) -> tuple[str, str, ft.IconData]:
        if tipo == "Receita":
            return "Relatório de Receitas", T.RECEITA, ft.Icons.ARROW_UPWARD_ROUNDED
        if tipo == "Despesa":
            return "Relatório de Despesas", T.DESPESA, ft.Icons.ARROW_DOWNWARD_ROUNDED
        if tipo == "Transferência":
            return "Relatório de Transferências", T.INFO, ft.Icons.SWAP_HORIZ_ROUNDED
        return "Relatório Geral de Lançamentos", T.PRIMARY, ft.Icons.ASSESSMENT_ROUNDED

    def _ao_clicar_categoria(cat: dict):
        cat_id = cat.get("categoria_id") or cat.get("id")
        if cat_id:
            ir_relatorio_categoria(
                page,
                categoria_id=str(cat_id),
                tipo=ctx_atual[0].tipo or "Despesa",
                ctx=ctx_atual[0],
            )

    def _ao_clicar_dia(dt_iso: str):
        novo = ctx_atual[0].com(data_inicio=dt_iso, data_fim=dt_iso)
        filter_bar.atualizar_contexto(novo, emitir=True)

    def carregar(inicial: bool = False):
        c = ctx_atual[0]
        tit, cor_t, _ = _titulo_por_tipo(c.tipo)
        txt_titulo.value = tit
        txt_subtitulo.value = f"Período: {formatar_data_br(c.data_inicio)} a {formatar_data_br(c.data_fim)}"
        txt_kpi_total.color = cor_t

        if not inicial:
            spinner.visible = True
            try:
                page.update()
            except Exception:
                pass

        try:
            pacote = db.obter_relatorio_lancamentos(
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
                        "titulo": "Total no Período",
                        "valor_ctrl": txt_kpi_total,
                        "cor": cor_t,
                        "icone": ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
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
                        "subtitulo": "No intervalo filtrado",
                    },
                ],
                mobile=mobile,
            )

            por_cat = pacote.get("por_categoria") or []
            por_dia = pacote.get("por_dia") or []

            graficos_row.controls = [
                construir_card_ranking_categorias(
                    categorias=por_cat,
                    titulo="Participação por Categoria",
                    subtitulo="Toque em uma categoria para abrir o relatório exclusivo dela",
                    cor_padrao=cor_t,
                    on_click_categoria=_ao_clicar_categoria,
                ),
                construir_card_evolucao_diaria(
                    por_dia=por_dia,
                    titulo="Movimentação Dia a Dia",
                    subtitulo="Toque em uma coluna para focar naquele dia",
                    modo_saldo=False,
                    on_click_dia=_ao_clicar_dia,
                ),
            ]

            lista_tx.renderizar(
                lancamentos=pacote.get("lancamentos") or [],
                total_registros=qtd_reg,
            )

        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao carregar relatório: {ex}", "erro")
        finally:
            spinner.visible = False
            if not inicial:
                try:
                    page.update()
                except Exception:
                    pass

    def _ao_mudar_filtro(novo_ctx: ReportContext):
        ctx_atual[0] = novo_ctx
        limite_atual[0] = LIMITE_PAGINA
        carregar(inicial=False)

    def _carregar_mais():
        limite_atual[0] += LIMITE_PAGINA
        carregar(inicial=False)

    def _abrir_novo(_=None):
        abrir_lancamento(
            page,
            tipo_inicial=ctx_atual[0].tipo or "Despesa",
            conta_inicial=ctx_atual[0].conta_id,
            cartao_inicial=ctx_atual[0].cartao_id,
            categoria_inicial=ctx_atual[0].categoria_id,
            regra_inicial=ctx_atual[0].regra,
            on_saved=lambda: carregar(inicial=False),
        )

    filter_bar = FilterBar(
        page=page,
        ctx=ctx_atual[0],
        on_change=_ao_mudar_filtro,
        mostrar_chips_tipo=True,
    )

    lista_tx = TransactionList(
        page=page,
        on_refresh=lambda: carregar(inicial=False),
        on_carregar_mais=_carregar_mais,
        on_novo_lancamento=_abrir_novo,
    )

    tit_ini, cor_ini, ic_ini = _titulo_por_tipo(ctx_atual[0].tipo)
    txt_titulo.value = tit_ini

    breadcrumbs = [
        ("Dashboard", "/dashboard"),
        ("Relatórios", "/relatorios"),
        (tit_ini, None),
    ]

    btn_novo_header = ft.FilledButton(
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
            bgcolor=T.PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=T.pad(h=14, v=10),
        ),
    )

    header = criar_report_header(
        page=page,
        titulo_ctrl=txt_titulo,
        subtitulo_ctrl=txt_subtitulo,
        spinner=spinner,
        breadcrumbs=breadcrumbs,
        icone=ic_ini,
        cor_icone=cor_ini,
        acoes_header=[btn_novo_header],
        mobile=mobile,
    )

    scaffold = ReportScaffold(
        header=header,
        filter_bar=filter_bar,
        kpi_strip=kpi_container,
        graficos_row=graficos_row,
        transaction_list=lista_tx,
    )

    def _on_periodo_shell(d_ini: str, d_fim: str, _m: int, _a: int):
        ctx_atual[0] = ctx_atual[0].com(data_inicio=d_ini, data_fim=d_fim)
        filter_bar.ctx = ctx_atual[0]
        carregar(inicial=False)

    carregar(inicial=True)

    return criar_shell(
        page=page,
        rota_ativa=ROTA_RELATORIOS,
        rota_view=match.rota_completa,
        titulo=tit_ini,
        mostrar_voltar=True,
        conteudo=scaffold,
        on_periodo_change=_on_periodo_shell,
        on_lancamento_saved=lambda: carregar(inicial=False),
    )
