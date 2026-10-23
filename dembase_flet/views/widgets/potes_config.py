"""
=============================================================================
DemBase v3 — views/widgets/potes_config.py  (Flet 1.0.1)
Aba "Metas": renda de referência, gráfico de rosca em tempo real e sliders dos
6 potes amarrados à validação de 100%. Sem acesso direto ao banco: usa apenas
services/potes_service.py e core/potes.py.
=============================================================================
"""
from decimal import Decimal

import flet as ft
import flet_charts as fch

from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda
from core import potes as P
from services import potes_service as svc

COR_ALERTA = "#F97316"


def _fmt_perc(v: Decimal) -> str:
    return f"{v.normalize():f}%"


def montar_aba_potes(page: ft.Page) -> ft.Control:
    # ── Estado ───────────────────────────────────────────────────────────────
    try:
        potes = svc.carregar_potes()
        renda = svc.ler_renda_referencia()
    except Exception as ex:
        mostrar_feedback(page, f"Erro ao carregar metas: {ex}", "erro")
        return ft.Container(
            padding=pad(all_=24), bgcolor=T.SURFACE, border_radius=16, border=borda(),
            content=ft.Text("Não foi possível carregar os potes.", color=T.TEXT_MUTED),
        )

    renda_ref = [renda]                       # renda de referência atual
    linhas: list[dict] = []                   # uma por pote (controles + estado)

    # ── Renda de referência ──────────────────────────────────────────────────
    txt_renda = ft.TextField(
        value=formatar_moeda(float(renda)),
        keyboard_type=ft.KeyboardType.NUMBER,
        text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
        **T.campo_estilo(),
    )
    btn_renda = ft.FilledButton(
        content="Salvar renda",
        style=ft.ButtonStyle(bgcolor=T.PRIMARY, color=ft.Colors.WHITE,
                             shape=ft.RoundedRectangleBorder(radius=10), padding=pad(h=24, v=14)),
    )

    # ── Gráfico de rosca ─────────────────────────────────────────────────────
    donut = fch.PieChart(
        sections=[],
        sections_space=2,
        center_space_radius=78,
        start_degree_offset=-90,
        animation=ft.Animation(250, ft.AnimationCurve.EASE_OUT),
    )
    txt_centro_valor = ft.Text("100%", size=26, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY)
    txt_centro_sub = ft.Text("Total", size=12, color=T.TEXT_MUTED)
    legenda = ft.ResponsiveRow(spacing=6, run_spacing=6)

    # ── Rodapé do controle ───────────────────────────────────────────────────
    txt_alocado = ft.Text("100% / 100%", size=13, weight=ft.FontWeight.BOLD, color=T.PRIMARY)
    txt_erro = ft.Text("", size=11, color=COR_ALERTA, visible=False)
    btn_salvar = ft.FilledButton(
        content="Salvar Metas",
        expand=True,
        style=ft.ButtonStyle(bgcolor=T.PRIMARY, color=ft.Colors.WHITE,
                             shape=ft.RoundedRectangleBorder(radius=10), padding=pad(v=16)),
    )

    # ── Núcleo reativo ───────────────────────────────────────────────────────
    def _percentual(linha: dict) -> Decimal:
        return Decimal(str(int(linha["slider"].value or 0)))

    def _itens() -> list[dict]:
        return [
            {"id": l["pote"].id, "nome": l["nome"].value, "percentual": _percentual(l)}
            for l in linhas
        ]

    def _atualizar_tela(montado: bool = True):
        """Recalcula donut, legenda, valores em R$, 'Alocado' e botão Salvar."""
        itens = _itens()
        soma = P.soma_percentuais(i["percentual"] for i in itens)
        valido = not P.validar_configuracao(itens)
        previsto = P.calcular_previsto_por_renda(renda_ref[0], [
            P.Pote(l["pote"].id, l["pote"].posicao, l["nome"].value, _percentual(l)) for l in linhas
        ])

        donut.sections = [
            fch.PieChartSection(
                value=float(_percentual(l)) if soma > 0 else 1,
                color=l["pote"].cor,
                radius=34,
                title="",
            )
            for l in linhas
        ]

        legenda.controls = [
            ft.Container(
                col={"xs": 12, "sm": 6},
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=6, expand=True, controls=[
                            ft.Container(width=8, height=8, bgcolor=l["pote"].cor, border_radius=4),
                            ft.Text(l["nome"].value or "—", size=12, color=T.TEXT_PRIMARY,
                                    max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                        ]),
                        ft.Text(_fmt_perc(_percentual(l)), size=12, color=T.TEXT_MUTED),
                    ],
                ),
            )
            for l in linhas
        ]

        for l in linhas:
            l["valor_rs"].value = formatar_moeda(float(previsto[l["pote"].id]))

        cor_estado = T.PRIMARY if valido else COR_ALERTA
        txt_centro_valor.value = _fmt_perc(soma)
        txt_centro_valor.color = T.TEXT_PRIMARY if soma == P.TOTAL_PERCENTUAL else COR_ALERTA
        txt_alocado.value = f"{_fmt_perc(soma)} / 100%"
        txt_alocado.color = cor_estado

        erros = P.validar_configuracao(itens)
        txt_erro.value = erros[0] if erros else ""
        txt_erro.visible = bool(erros)
        btn_salvar.disabled = bool(erros)
        if montado:
            page.update()

    def _ao_mover_slider(e):
        for l in linhas:
            if l["slider"] is e.control:
                l["perc"].value = str(int(e.control.value))
                break
        _atualizar_tela()

    def _ao_digitar_percentual(e):
        for l in linhas:
            if l["perc"] is e.control:
                try:
                    v = int(e.control.value or 0)
                except ValueError:
                    v = 0
                v = max(0, min(100, v))
                l["slider"].value = v
                break
        _atualizar_tela()

    def _ao_alterar_nome(_):
        _atualizar_tela()

    # ── Linhas dos 6 potes (sem botão de criar/remover: limite fixo) ─────────
    for pote in potes:
        slider = ft.Slider(
            min=0, max=100, divisions=100, value=int(pote.percentual),
            active_color=pote.cor, inactive_color=T.SURFACE_ALT, thumb_color=pote.cor,
            expand=True, on_change=_ao_mover_slider,
        )
        perc = ft.TextField(
            value=str(int(pote.percentual)), width=64, text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(), max_length=3, counter=ft.Text(""),
            on_change=_ao_digitar_percentual,
            **T.campo_estilo(content_padding=pad(h=6, v=8)),
        )
        nome = ft.TextField(
            value=pote.nome, max_length=P.NOME_MAX, counter=ft.Text(""),
            text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
            on_change=_ao_alterar_nome, expand=True,
            **T.campo_estilo(border_color="transparent", fill_color="transparent",
                             content_padding=pad(h=0, v=6)),
        )
        valor_rs = ft.Text("", size=11, color=T.TEXT_MUTED)
        linhas.append({"pote": pote, "slider": slider, "perc": perc, "nome": nome, "valor_rs": valor_rs})

    # ── Ações ────────────────────────────────────────────────────────────────
    def _salvar_renda(_):
        try:
            nova = svc.salvar_renda_referencia(txt_renda.value)
        except P.ErroPotes as ex:
            mostrar_feedback(page, " ".join(ex.erros), "alerta")
            return
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao salvar renda: {ex}", "erro")
            return
        renda_ref[0] = nova
        txt_renda.value = formatar_moeda(float(nova))
        mostrar_feedback(page, "Renda de referência salva. Valores recalculados.", "sucesso")
        _atualizar_tela()

    def _salvar_metas(_):
        itens = _itens()
        try:
            salvos = svc.salvar_configuracao(itens)   # revalida soma == 100
        except P.ErroPotes as ex:
            mostrar_feedback(page, " ".join(ex.erros), "alerta")
            return
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao salvar metas: {ex}", "erro")
            return
        for l, novo in zip(linhas, salvos):
            l["pote"] = novo
        mostrar_feedback(page, "Metas salvas com sucesso!", "sucesso")
        _atualizar_tela()

    def _resetar(_):
        padrao = {d["posicao"]: d for d in P.POTES_PADRAO}
        for l in linhas:
            d = padrao[l["pote"].posicao]
            l["nome"].value = d["nome"]
            l["slider"].value = int(d["percentual"])
            l["perc"].value = str(int(d["percentual"]))
        _atualizar_tela()

    btn_renda.on_click = _salvar_renda
    btn_salvar.on_click = _salvar_metas

    # ── Layout ───────────────────────────────────────────────────────────────
    def _linha_ui(l: dict) -> ft.Column:
        return ft.Column(spacing=0, controls=[
            ft.Row(
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    l["nome"],
                    l["valor_rs"],
                    l["perc"],
                    ft.Text("%", size=11, color=T.TEXT_MUTED),
                ],
            ),
            l["slider"],
        ])

    card_renda = ft.Container(
        padding=pad(all_=20), bgcolor=T.SURFACE, border_radius=16, border=borda(),
        content=ft.ResponsiveRow(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=20, run_spacing=12,
            controls=[
                ft.Column(col={"xs": 12, "md": 5}, spacing=6, controls=[
                    ft.Text("RENDA DE REFERÊNCIA MENSAL", size=10, color=T.TEXT_MUTED,
                            weight=ft.FontWeight.W_600),
                    txt_renda,
                    ft.Text("Ao salvar, os valores em R$ dos potes são recalculados.",
                            size=11, color=T.TEXT_MUTED),
                ]),
                ft.Text(
                    "Use este valor como base para planejar e distribuir suas metas financeiras. "
                    "Ele não representa suas receitas reais e não cria lançamentos.",
                    col={"xs": 12, "md": 4}, size=12, color=T.TEXT_MUTED,
                ),
                ft.Container(col={"xs": 12, "md": 3}, alignment=ft.Alignment(1, 0), content=btn_renda),
            ],
        ),
    )

    card_donut = ft.Container(
        col={"xs": 12, "md": 5}, padding=pad(all_=20), bgcolor=T.SURFACE, border_radius=16, border=borda(),
        content=ft.Column(spacing=14, controls=[
            ft.Text("Visualização de uso", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
            ft.Container(
                height=240,
                content=ft.Stack(alignment=ft.Alignment(0, 0), controls=[
                    donut,
                    ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=0,
                        controls=[txt_centro_valor, txt_centro_sub],
                    ),
                ]),
            ),
            legenda,
            ft.OutlinedButton(
                content="Resetar Valores", on_click=_resetar,
                style=ft.ButtonStyle(color=T.TEXT_MUTED, side=ft.BorderSide(1, T.BORDER),
                                     shape=ft.RoundedRectangleBorder(radius=10), padding=pad(v=14)),
            ),
        ]),
    )

    card_controle = ft.Container(
        col={"xs": 12, "md": 7}, padding=pad(all_=20), bgcolor=T.SURFACE, border_radius=16, border=borda(),
        content=ft.Column(spacing=10, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text("Controle de Orçamento", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ft.Text("% da renda de referência — o valor é recalculado", size=10, color=T.TEXT_MUTED),
            ]),
            *[_linha_ui(l) for l in linhas],
            ft.Divider(color=T.BORDER, height=16),
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text("Alocado", size=13, color=T.TEXT_MUTED), txt_alocado,
            ]),
            txt_erro,
            ft.Row(controls=[btn_salvar]),
        ]),
    )

    nota = ft.Container(
        padding=pad(h=16, v=12), bgcolor=T.SURFACE, border_radius=12, border=borda(),
        content=ft.Row(spacing=10, controls=[
            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16, color=T.TEXT_MUTED),
            ft.Text(
                "Planejamento, não lançamento. Alterações valem para novas receitas; "
                "distribuições passadas mantêm o percentual aplicado na época.",
                size=11, color=T.TEXT_MUTED, expand=True,
            ),
        ]),
    )

    conteudo = ft.Column(spacing=16, controls=[
        card_renda,
        ft.ResponsiveRow(spacing=16, run_spacing=16, controls=[card_donut, card_controle]),
        nota,
    ])

    # Estado visual inicial (controles ainda não montados na página)
    _atualizar_tela(montado=False)
    return conteudo
