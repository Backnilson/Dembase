"""
=============================================================================
DemBase v3 — views/widgets/potes_config.py  (Flet 1.0.1)
Aba "Metas": renda de referência, seletor de Mês/Ano independente,
gráfico de rosca em tempo real e sliders dos 6 potes amarrados à validação
de 100% por período. Sem acesso direto ao banco: usa apenas
services/potes_service.py e core/potes.py.
=============================================================================
"""
from datetime import date
from decimal import Decimal

import flet as ft
try:
    import flet_charts as fch
except ImportError:
    class _MockPieChart(ft.Container):
        def __init__(self, *args, **kwargs):
            super().__init__(width=200, height=200, alignment=ft.Alignment(0, 0), content=ft.Icon(ft.Icons.PIE_CHART_ROUNDED, size=64, color=T.PRIMARY))
            self.sections = []
    class _MockSection:
        def __init__(self, *args, **kwargs):
            pass
    class _MockFch:
        PieChart = _MockPieChart
        PieChartSection = _MockSection
    fch = _MockFch()

from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, MESES_NOMES
from core import potes as P
from services import potes_service as svc
from views.shell_view import obter_estado_periodo_atual

COR_ALERTA = "#F97316"


def _fmt_perc(v: Decimal) -> str:
    return f"{v.normalize():f}%"


def montar_aba_potes(page: ft.Page) -> ft.Control:
    # ── Estado do Mês/Ano selecionado ─────────────────────────────────────────
    est_periodo = obter_estado_periodo_atual(page)
    mes_ini = int(est_periodo.get("mes") or date.today().month)
    ano_ini = int(est_periodo.get("ano") or date.today().year)
    estado_periodo = {"mes": mes_ini, "ano": ano_ini, "herdado": False}

    try:
        potes, herdado_ini = svc.carregar_potes_com_meta_mes(
            mes=estado_periodo["mes"], ano=estado_periodo["ano"]
        )
        estado_periodo["herdado"] = herdado_ini
        renda = svc.ler_renda_referencia()
    except Exception as ex:
        mostrar_feedback(page, f"Erro ao carregar metas: {ex}", "erro")
        return ft.Container(
            padding=pad(all_=24), bgcolor=T.SURFACE, border_radius=16, border=borda(),
            content=ft.Text("Não foi possível carregar os potes.", color=T.TEXT_MUTED),
        )

    renda_ref = [renda]                       # renda de referência atual
    linhas: list[dict] = []                   # uma por pote (controles + estado)

    # ── Seletor de Mês/Ano independente ──────────────────────────────────────
    txt_mes_ano = ft.Text(
        "",
        size=15,
        weight=ft.FontWeight.BOLD,
        color=T.TEXT_PRIMARY,
    )
    txt_badge_escopo = ft.Text(
        "",
        size=11,
        weight=ft.FontWeight.W_600,
        color=T.RECEITA,
    )
    box_badge_escopo = ft.Container(
        padding=pad(h=10, v=4),
        border_radius=20,
        bgcolor=f"{T.RECEITA}18",
        border=borda(color=f"{T.RECEITA}55"),
        content=ft.Row(
            spacing=5,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=T.RECEITA),
                txt_badge_escopo,
            ],
        ),
    )

    def _nome_mes_ano(m: int, a: int) -> str:
        nm = MESES_NOMES[m - 1] if 1 <= m <= 12 else f"Mês {m}"
        return f"{nm} / {a}"

    def _atualizar_cabecalho_mes():
        m = estado_periodo["mes"]
        a = estado_periodo["ano"]
        rot = _nome_mes_ano(m, a)
        txt_mes_ano.value = rot
        if estado_periodo["herdado"]:
            txt_badge_escopo.value = f"Herdado do mês anterior · Salve para fixar em {rot}"
            txt_badge_escopo.color = T.WARNING
            box_badge_escopo.bgcolor = f"{T.WARNING}18"
            box_badge_escopo.border = borda(color=f"{T.WARNING}55")
        else:
            txt_badge_escopo.value = f"Metas exclusivas de {rot}"
            txt_badge_escopo.color = T.RECEITA
            box_badge_escopo.bgcolor = f"{T.RECEITA}18"
            box_badge_escopo.border = borda(color=f"{T.RECEITA}55")
        btn_salvar.content = f"Salvar Metas de {rot}"

    def _recarregar_mes_selecionado():
        m = estado_periodo["mes"]
        a = estado_periodo["ano"]
        try:
            novos_potes, herd = svc.carregar_potes_com_meta_mes(mes=m, ano=a)
            estado_periodo["herdado"] = herd
            por_pos = {p.posicao: p for p in novos_potes}
            for l in linhas:
                pos = l["pote"].posicao
                if pos in por_pos:
                    np = por_pos[pos]
                    l["pote"] = np
                    l["nome"].value = np.nome
                    l["slider"].value = int(np.percentual)
                    l["perc"].value = str(int(np.percentual))
            _atualizar_cabecalho_mes()
            _atualizar_tela(montado=True)
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao carregar metas de {_nome_mes_ano(m, a)}: {ex}", "erro")

    def _mudar_mes(delta: int):
        m = estado_periodo["mes"] + delta
        a = estado_periodo["ano"]
        if m < 1:
            m = 12
            a -= 1
        elif m > 12:
            m = 1
            a += 1
        estado_periodo["mes"] = m
        estado_periodo["ano"] = a
        _recarregar_mes_selecionado()

    # ── Renda de referência ──────────────────────────────────────────────────
    def _ao_alterar_renda(e):
        try:
            val = P.para_decimal(txt_renda.value, default=Decimal("0"))
            renda_ref[0] = max(Decimal("0"), val)
        except Exception:
            pass
        _atualizar_tela()

    txt_renda = ft.TextField(
        value=formatar_moeda(float(renda)),
        keyboard_type=ft.KeyboardType.NUMBER,
        text_style=ft.TextStyle(size=16, weight=ft.FontWeight.BOLD),
        on_change=_ao_alterar_renda,
        **T.campo_estilo(),
    )
    btn_renda = ft.FilledButton(
        content="Simular",
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
        m_alvo = estado_periodo["mes"]
        a_alvo = estado_periodo["ano"]
        rot_alvo = _nome_mes_ano(m_alvo, a_alvo)
        try:
            nova = svc.salvar_renda_referencia(txt_renda.value)
            renda_ref[0] = nova
            txt_renda.value = formatar_moeda(float(nova))
            salvos = svc.salvar_configuracao(itens, mes=m_alvo, ano=a_alvo)   # revalida soma == 100 e salva só neste mês/ano
        except P.ErroPotes as ex:
            mostrar_feedback(page, " ".join(ex.erros), "alerta")
            return
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao salvar metas: {ex}", "erro")
            return
        for l, novo in zip(linhas, salvos):
            l["pote"] = novo
        estado_periodo["herdado"] = False
        _atualizar_cabecalho_mes()
        mostrar_feedback(
            page,
            f"Metas de {rot_alvo} salvas com sucesso! (Os demais meses permanecem intactos)",
            "sucesso",
        )
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

    # ── Barra de Escopo Mensal ───────────────────────────────────────────────
    card_escopo_mes = ft.Container(
        padding=pad(h=18, v=14),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(color=f"{T.PRIMARY}55"),
        content=ft.ResponsiveRow(
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            run_spacing=10,
            controls=[
                ft.Column(
                    col={"xs": 12, "md": 6},
                    spacing=4,
                    controls=[
                        ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.SHIELD_OUTLINED, size=18, color=T.PRIMARY),
                                ft.Text(
                                    "METAS INDEPENDENTES POR MÊS / PERÍODO",
                                    size=11,
                                    color=T.PRIMARY,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                        ft.Text(
                            "Alterar as porcentagens deste mês aplica-se exclusivamente a ele, sem alterar meses anteriores ou futuros.",
                            size=11,
                            color=T.TEXT_MUTED,
                        ),
                    ],
                ),
                ft.Container(
                    col={"xs": 12, "md": 6},
                    alignment=ft.Alignment(1, 0),
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.END,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        wrap=True,
                        controls=[
                            box_badge_escopo,
                            ft.Container(
                                padding=pad(h=6, v=4),
                                bgcolor=T.SURFACE_ALT,
                                border_radius=10,
                                border=borda(),
                                content=ft.Row(
                                    spacing=4,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                                            icon_size=18,
                                            icon_color=T.TEXT_PRIMARY,
                                            tooltip="Mês anterior",
                                            on_click=lambda _: _mudar_mes(-1),
                                        ),
                                        ft.Container(
                                            padding=pad(h=8, v=2),
                                            content=txt_mes_ano,
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                                            icon_size=18,
                                            icon_color=T.TEXT_PRIMARY,
                                            tooltip="Próximo mês",
                                            on_click=lambda _: _mudar_mes(1),
                                        ),
                                    ],
                                ),
                            ),
                        ],
                    ),
                ),
            ],
        ),
    )

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
                    ft.Text("SIMULADOR DE DISTRIBUIÇÃO (R$)", size=10, color=T.TEXT_MUTED,
                            weight=ft.FontWeight.W_600),
                    txt_renda,
                    ft.Text("Digite um valor para simular a distribuição das porcentagens.",
                            size=11, color=T.TEXT_MUTED),
                ]),
                ft.Text(
                    "Use este valor como simulador para pré-visualizar as metas em R$. "
                    "No Dashboard, os limites são calculados automaticamente em cima da receita real do período.",
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
            ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, size=16, color=T.PRIMARY),
            ft.Text(
                "Regra do Dashboard: Os limites dos 6 potes são calculados aplicando as porcentagens "
                "configuradas neste mês exclusivamente sobre o dinheiro que entrou na conta no período filtrado.",
                size=11, color=T.TEXT_PRIMARY, expand=True,
            ),
        ]),
    )

    conteudo = ft.Column(spacing=16, controls=[
        card_escopo_mes,
        card_renda,
        ft.ResponsiveRow(spacing=16, run_spacing=16, controls=[card_donut, card_controle]),
        nota,
    ])

    _atualizar_cabecalho_mes()
    # Estado visual inicial (controles ainda não montados na página)
    _atualizar_tela(montado=False)
    return conteudo
