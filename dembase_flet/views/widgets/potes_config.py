"""
=============================================================================
DemBase v3 — views/widgets/potes_config.py  (Flet 1.0.1)
Aba "Metas": renda de referência, seletor de Mês/Ano independente,
gráfico de rosca em tempo real e controle flexível (R$ ou %) dos 6 potes.
Unificado com a matemática do Caixa Livre e 100% de precisão.
=============================================================================
"""
from __future__ import annotations

import calendar
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
from core.constants import formatar_moeda, formatar_data_br, MESES_NOMES
from core import potes as P
from core import storage
from services import potes_service as svc
from views.shell_view import obter_estado_periodo_atual

COR_ALERTA = "#F97316"


def _fmt_perc(v: Decimal | float) -> str:
    val = float(v)
    if abs(val - round(val)) < 0.05:
        return f"{int(round(val))}%"
    return f"{val:.1f}%".replace(".", ",")


def _intervalo_mes(m: int, a: int) -> tuple[str, str]:
    ult = calendar.monthrange(a, m)[1]
    return f"{a:04d}-{m:02d}-01", f"{a:04d}-{m:02d}-{ult:02d}"


def _iso(d) -> str:
    return d.isoformat() if hasattr(d, "isoformat") else str(d)[:10]


def montar_aba_potes(
    page: ft.Page,
    mes: int | None = None,
    ano: int | None = None,
    data_ini: str | None = None,
    data_fim: str | None = None,
    ao_salvar=None,
) -> ft.Control:
    """
    Configurador de metas dos 6 potes ESPELHADO no Dashboard: base de cálculo = Receita Real do
    período selecionado, Gasto Real por pote e reflexo imediato em Custos Fixos e Caixa Livre.
    `mes/ano/data_ini/data_fim` permitem abrir já no período exato do Dashboard.
    `ao_salvar` é chamado após salvar (ex.: fechar modal e recarregar o Dashboard).
    """
    # ── Estado do Mês/Ano selecionado ─────────────────────────────────────────
    est_periodo = obter_estado_periodo_atual(page)
    mes_ini = int(mes or est_periodo.get("mes") or date.today().month)
    ano_ini = int(ano or est_periodo.get("ano") or date.today().year)
    if data_ini and data_fim:
        di_ini, df_ini = str(data_ini)[:10], str(data_fim)[:10]
    elif mes is None and est_periodo.get("data_inicio") and est_periodo.get("data_fim"):
        di_ini, df_ini = _iso(est_periodo["data_inicio"]), _iso(est_periodo["data_fim"])
    else:
        di_ini, df_ini = _intervalo_mes(mes_ini, ano_ini)
    estado_periodo = {"mes": mes_ini, "ano": ano_ini, "herdado": False, "di": di_ini, "df": df_ini}

    piso_fixos_atual = storage.obter_piso_custos_fixos(page, 1150.0)
    ctx_ref: list[dict] = [{"renda": 0.0, "gastos": {}, "qtd": {}, "tem_receita": False}]
    simulando = [False]
    fonte_renda = ["real"]  # real | referencia | padrao | simulada

    def _definir_renda_base() -> Decimal:
        """Receita Real do período (igual ao Dashboard); fallback só se não houver receita."""
        real = float(ctx_ref[0].get("renda") or 0.0)
        if real > 0:
            fonte_renda[0] = "real"
            return Decimal(str(round(real, 2)))
        try:
            ref = svc.ler_renda_referencia()
        except Exception:
            ref = Decimal("0")
        if ref > 0:
            fonte_renda[0] = "referencia"
            return ref
        fonte_renda[0] = "padrao"
        return Decimal("5000.00")

    try:
        potes, herdado_ini = svc.carregar_potes_com_meta_mes(
            mes=estado_periodo["mes"], ano=estado_periodo["ano"]
        )
        estado_periodo["herdado"] = herdado_ini
        ctx_ref[0] = svc.carregar_contexto_mes(di_ini, df_ini, piso_fixos_atual)
        renda = _definir_renda_base()
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
            # Espelho do mês: nova janela = mês cheio, Receita Real e Gastos Reais do mês escolhido
            estado_periodo["di"], estado_periodo["df"] = _intervalo_mes(m, a)
            ctx_ref[0] = svc.carregar_contexto_mes(
                estado_periodo["di"], estado_periodo["df"], storage.obter_piso_custos_fixos(page, 1150.0)
            )
            if not simulando[0]:
                renda_ref[0] = _definir_renda_base()
                txt_renda.value = formatar_moeda(float(renda_ref[0]))
            por_pos = {p.posicao: p for p in novos_potes}
            for l in linhas:
                pos = l["pote"].posicao
                if pos in por_pos:
                    np = por_pos[pos]
                    l["pote"] = np
                    l["nome"].value = np.nome
                    val_pct = float(np.percentual)
                    l["slider"].value = int(round(val_pct))
                    l["perc"].value = str(int(round(val_pct)))
                    if renda_ref[0] > 0:
                        v_rs = float(renda_ref[0]) * (val_pct / 100.0)
                        l["tf_rs"].value = f"{v_rs:.2f}".replace(".", ",")
            _atualizar_cabecalho_mes()
            _atualizar_info_renda()
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
        read_only=True,
        **T.campo_estilo(),
    )
    txt_titulo_renda = ft.Text("", size=10, color=T.TEXT_MUTED, weight=ft.FontWeight.W_600)
    txt_info_renda = ft.Text("", size=11, color=T.TEXT_MUTED)

    def _atualizar_info_renda():
        m, a = estado_periodo["mes"], estado_periodo["ano"]
        rot = _nome_mes_ano(m, a)
        if simulando[0]:
            txt_titulo_renda.value = "RECEITA SIMULADA (MANUAL)"
            txt_info_renda.value = "Valor digitado por você. Desligue a simulação para voltar à receita real."
            txt_info_renda.color = T.WARNING
        elif fonte_renda[0] == "real":
            txt_titulo_renda.value = f"RECEITA REAL DE {rot.upper()}"
            txt_info_renda.value = (
                f"Mesma receita do Dashboard · Período {formatar_data_br(estado_periodo['di'])} "
                f"a {formatar_data_br(estado_periodo['df'])}"
            )
            txt_info_renda.color = T.TEXT_MUTED
        else:
            txt_titulo_renda.value = f"SEM RECEITA REGISTRADA EM {rot.upper()}"
            txt_info_renda.value = (
                "Usando a renda de referência do perfil como base."
                if fonte_renda[0] == "referencia"
                else "Usando R$ 5.000,00 apenas como base de simulação."
            )
            txt_info_renda.color = T.WARNING
        txt_renda.read_only = not simulando[0]

    def _ao_alternar_simulacao(e):
        simulando[0] = bool(e.control.value)
        if not simulando[0]:
            renda_ref[0] = _definir_renda_base()
            txt_renda.value = formatar_moeda(float(renda_ref[0]))
            r_flt = float(renda_ref[0])
            for l in linhas:
                l["tf_rs"].value = f"{r_flt * (float(_percentual(l)) / 100.0):.2f}".replace(".", ",")
        _atualizar_info_renda()
        _atualizar_tela()

    sw_simular = ft.Switch(label="Simular outro valor", value=False, on_change=_ao_alternar_simulacao)

    # ── Campo Piso de Custos Fixos ───────────────────────────────────────────
    def _ao_alterar_piso_fixos(e):
        try:
            val = P.para_decimal(tf_piso_fixos.value, default=Decimal("1150.00"))
            storage.salvar_piso_custos_fixos_sync(page, float(val))
        except Exception:
            pass
        _atualizar_tela()

    tf_piso_fixos = ft.TextField(
        value=formatar_moeda(piso_fixos_atual),
        width=130,
        height=38,
        text_size=13,
        text_align=ft.TextAlign.RIGHT,
        keyboard_type=ft.KeyboardType.NUMBER,
        content_padding=pad(h=8, v=6),
        bgcolor=T.BG,
        border_color=T.BORDER,
        border_radius=8,
        on_change=_ao_alterar_piso_fixos,
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
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            color=ft.Colors.WHITE,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(v=16),
        ),
    )

    # ── Núcleo reativo ───────────────────────────────────────────────────────
    def _percentual(linha: dict) -> Decimal:
        try:
            return Decimal(str(int(linha["slider"].value or 0)))
        except Exception:
            return Decimal("0")

    def _itens() -> list[dict]:
        return [
            {"id": l["pote"].id, "nome": l["nome"].value, "percentual": _percentual(l)}
            for l in linhas
        ]

    reflexo_col = ft.Column(spacing=6)
    pct_cache: dict[tuple[int, int], float] = {}

    def _pct_invest_mes() -> float:
        """Slider do Caixa Livre do mês (mesma precedência usada pelo painel do Dashboard)."""
        m, a = estado_periodo["mes"], estado_periodo["ano"]
        if (m, a) not in pct_cache:
            pct = storage.obter_percentual_sobra_investimento(page, 50.0, mes=m, ano=a)
            pdb, personalizado = svc.obter_pct_investimento_db(m, a)
            if pdb is not None and personalizado:
                pct = pdb
            pct_cache[(m, a)] = float(pct)
        return pct_cache[(m, a)]

    def _linha_reflexo(rotulo: str, valor: str, cor: str = T.TEXT_PRIMARY, sub: str = "", negrito: bool = False):
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Column(spacing=0, expand=True, controls=[
                    ft.Text(rotulo, size=12, color=T.TEXT_PRIMARY,
                            weight=ft.FontWeight.BOLD if negrito else ft.FontWeight.W_500),
                    *([ft.Text(sub, size=10.5, color=T.TEXT_MUTED)] if sub else []),
                ]),
                ft.Text(valor, size=13, color=cor, weight=ft.FontWeight.BOLD),
            ],
        )

    def _atualizar_espelho(itens: list[dict]):
        """Reflexo em tempo real: Limite, Gasto Real e +Disponível por pote + Caixa Livre."""
        rec = float(renda_ref[0])
        ctx = ctx_ref[0]
        m, a = estado_periodo["mes"], estado_periodo["ano"]
        liberados = storage.obter_potes_liberados(page, m, a)
        potes_in = [
            {
                "id": l["pote"].id,
                "posicao": l["pote"].posicao,
                "nome": l["nome"].value or l["pote"].nome,
                "cor": l["pote"].cor,
                "percentual": float(_percentual(l)),
                "gasto": float(ctx["gastos"].get(l["pote"].posicao, 0.0)),
                "qtd_transacoes": int(ctx["qtd"].get(l["pote"].posicao, 0)),
            }
            for l in linhas
        ]
        piso = storage.obter_piso_custos_fixos(page, 1150.0)
        pct_inv = _pct_invest_mes()
        arch = P.calcular_arquitetura_unificada_potes(
            rec, potes_in, piso_custos_fixos=piso, slider_pct_investimento=pct_inv,
            protecao_fluxo=None, travar_pelo_teto_seguro=False, potes_liberados=liberados,
        )
        por_pos = {p["posicao"]: p for p in arch["potes"]}

        for l in linhas:
            p = por_pos.get(l["pote"].posicao)
            if not p:
                continue
            lim, g = p["previsto"], p["gasto"]
            disp = p.get("disponivel_efetivo", p["restante"])
            estourou = p["restante"] < -0.005
            cor_disp = COR_ALERTA if estourou else T.RECEITA
            txt_disp = (
                f"{formatar_moeda(abs(p['restante']))} acima do limite"
                if estourou else f"+{formatar_moeda(disp)} disponível"
            )
            extra = ""
            if p.get("liberado"):
                extra = " · sobra liberada p/ Caixa Livre"
            l["preview"].spans = [
                ft.TextSpan(f"Limite {formatar_moeda(lim)} ({_fmt_perc(p['percentual'])})",
                            style=ft.TextStyle(color=T.TEXT_PRIMARY)),
                ft.TextSpan(f"  ·  Gasto real {formatar_moeda(g)}", style=ft.TextStyle(color=T.TEXT_MUTED)),
                ft.TextSpan(f"  ·  {txt_disp}", style=ft.TextStyle(color=cor_disp, weight=ft.FontWeight.W_600)),
                ft.TextSpan(extra, style=ft.TextStyle(color="#06B6D4")),
            ]

        cl = arch["caixa_livre"]
        p1 = por_pos[1]
        retido_manuais = round(sum(por_pos[k].get("disponivel_retido", 0.0) for k in (2, 3, 5)), 2)
        lib_total = round(sum(por_pos[k].get("liberado_valor", 0.0) for k in (2, 3, 5)), 2)
        reflexo_col.controls = [
            _linha_reflexo(
                "Receita base do mês", formatar_moeda(rec), T.PRIMARY, negrito=True,
                sub="Receita real do Dashboard" if fonte_renda[0] == "real" and not simulando[0] else "Base de simulação",
            ),
            _linha_reflexo(
                "Custos Fixos (automático)", formatar_moeda(p1["previsto"]),
                COR_ALERTA if p1["restante"] < -0.005 else T.TEXT_PRIMARY,
                sub=f"{_fmt_perc(p1['percentual'])} da receita · gasto real {formatar_moeda(p1['gasto'])} · piso {formatar_moeda(piso)}",
            ),
            _linha_reflexo(
                "Retido em Semi Fixos + Metas + Conhecimento", formatar_moeda(retido_manuais), T.RECEITA,
                sub="Reservas protegidas: não inflam o Caixa Livre"
                    + (f" · {formatar_moeda(lib_total)} liberados" if lib_total > 0 else ""),
            ),
            ft.Divider(color=T.BORDER, height=10),
            _linha_reflexo(
                "Caixa Livre do mês", formatar_moeda(cl["teto_orcamento"]), "#06B6D4", negrito=True,
                sub=f"{_fmt_perc(cl['pct_orcamento'])} da receita · slider {_fmt_perc(cl['pct_slider_investimento'])} "
                    f"Liberdade / {_fmt_perc(cl['pct_slider_livre'])} Prazeres",
            ),
            _linha_reflexo(
                f"{cl['liberdade_nome']}", formatar_moeda(cl["liberdade_teto"]), por_pos[6]["cor"],
                sub=f"Aportado {formatar_moeda(cl['liberdade_gasto'])} · +{formatar_moeda(cl['liberdade_restante_projetado'])} disponível",
            ),
            _linha_reflexo(
                f"{cl['prazeres_nome']}", formatar_moeda(cl["prazeres_teto"]), por_pos[4]["cor"],
                sub=f"Gasto {formatar_moeda(cl['prazeres_gasto'])} · +{formatar_moeda(cl['prazeres_restante_projetado'])} disponível",
            ),
        ]
        if rec <= 0:
            reflexo_col.controls.append(
                ft.Text("Sem receita no período: limites zerados.", size=11, color=COR_ALERTA)
            )

    def _atualizar_tela(montado: bool = True):
        """Recalcula donut, legenda, valores em R$, 'Alocado' e botão Salvar."""
        itens = _itens()
        try:
            _atualizar_espelho(itens)
        except Exception as ex_esp:
            reflexo_col.controls = [ft.Text(f"Não foi possível calcular o espelho: {ex_esp}", size=11, color=COR_ALERTA)]
        soma = P.soma_percentuais(i["percentual"] for i in itens)
        valido = not P.validar_configuracao(itens)

        r_flt = float(renda_ref[0])

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
                        ft.Row(
                            spacing=6,
                            expand=True,
                            controls=[
                                ft.Container(width=8, height=8, bgcolor=l["pote"].cor, border_radius=4),
                                ft.Text(
                                    l["nome"].value or "—",
                                    size=12,
                                    color=T.TEXT_PRIMARY,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                            ],
                        ),
                        ft.Text(_fmt_perc(_percentual(l)), size=12, color=T.TEXT_MUTED),
                    ],
                ),
            )
            for l in linhas
        ]

        for l in linhas:
            p_val = float(_percentual(l))
            val_calc = r_flt * (p_val / 100.0)
            # Atualiza o valor formatado visível
            l["valor_rs"].value = formatar_moeda(val_calc)

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
            try:
                page.update()
            except Exception:
                pass

    def _ao_mover_slider(e):
        for l in linhas:
            if l["slider"] is e.control:
                v = int(e.control.value)
                l["perc"].value = str(v)
                r_flt = float(renda_ref[0])
                if r_flt > 0:
                    l["tf_rs"].value = f"{r_flt * (v / 100.0):.2f}".replace(".", ",")
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
                r_flt = float(renda_ref[0])
                if r_flt > 0:
                    l["tf_rs"].value = f"{r_flt * (v / 100.0):.2f}".replace(".", ",")
                break
        _atualizar_tela()

    def _ao_digitar_reais(e):
        for l in linhas:
            if l["tf_rs"] is e.control:
                try:
                    txt = str(e.control.value or "0").replace("R$", "").replace(".", "").replace(",", ".").strip()
                    val_rs = float(txt or 0.0)
                except ValueError:
                    val_rs = 0.0
                r_flt = float(renda_ref[0])
                if r_flt > 0:
                    v_pct = int(round(max(0.0, min(100.0, (val_rs / r_flt) * 100.0))))
                else:
                    v_pct = 0
                l["slider"].value = v_pct
                l["perc"].value = str(v_pct)
                break
        _atualizar_tela()

    def _ao_alterar_nome(_):
        _atualizar_tela()

    # ── Linhas dos 6 potes com Edição Flexível (R$ e %) ─────────────────────
    for pote in potes:
        pos = pote.posicao
        val_pct = int(round(float(pote.percentual)))
        slider = ft.Slider(
            min=0, max=100, divisions=100, value=val_pct,
            active_color=pote.cor, inactive_color=T.SURFACE_ALT, thumb_color=pote.cor,
            expand=True, on_change=_ao_mover_slider,
        )
        perc = ft.TextField(
            value=str(val_pct), width=58, text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.NumbersOnlyInputFilter(), max_length=3, counter=ft.Text(""),
            on_change=_ao_digitar_percentual,
            **T.campo_estilo(content_padding=pad(h=4, v=6)),
        )

        r_flt = float(renda)
        val_rs_ini = r_flt * (val_pct / 100.0) if r_flt > 0 else 0.0
        tf_rs = ft.TextField(
            value=f"{val_rs_ini:.2f}".replace(".", ","),
            width=92,
            text_align=ft.TextAlign.RIGHT,
            prefix=ft.Text("R$ ", size=11, color=T.TEXT_MUTED),
            keyboard_type=ft.KeyboardType.NUMBER,
            counter=ft.Text(""),
            on_change=_ao_digitar_reais,
            **T.campo_estilo(content_padding=pad(h=6, v=6)),
        )

        nome = ft.TextField(
            value=pote.nome, max_length=P.NOME_MAX, counter=ft.Text(""),
            text_style=ft.TextStyle(size=13, weight=ft.FontWeight.W_600),
            on_change=_ao_alterar_nome, expand=True,
            **T.campo_estilo(border_color="transparent", fill_color="transparent",
                             content_padding=pad(h=0, v=6)),
        )
        valor_rs = ft.Text(formatar_moeda(val_rs_ini), size=11, color=T.TEXT_MUTED)
        preview = ft.Text("", size=11, color=T.TEXT_MUTED)

        # Tag de comportamento inteligente
        if pos == 1:
            tag_comp = ft.Container(
                content=ft.Text("Automático", size=9.5, color=T.PRIMARY, weight=ft.FontWeight.BOLD),
                padding=pad(h=6, v=2), border_radius=6, bgcolor=f"{T.PRIMARY}18",
            )
        elif pos in (2, 3, 5):
            tag_comp = ft.Container(
                content=ft.Text("Retido", size=9.5, color=T.RECEITA, weight=ft.FontWeight.BOLD),
                padding=pad(h=6, v=2), border_radius=6, bgcolor=f"{T.RECEITA}18",
            )
        else:
            tag_comp = ft.Container(
                content=ft.Text("Caixa Livre", size=9.5, color="#8B5CF6", weight=ft.FontWeight.BOLD),
                padding=pad(h=6, v=2), border_radius=6, bgcolor="#8B5CF618",
            )

        linhas.append({
            "pote": pote,
            "slider": slider,
            "perc": perc,
            "tf_rs": tf_rs,
            "nome": nome,
            "valor_rs": valor_rs,
            "preview": preview,
            "tag_comp": tag_comp,
        })

    # ── Ações ────────────────────────────────────────────────────────────────
    def _salvar_metas(_):
        itens = _itens()
        m_alvo = estado_periodo["mes"]
        a_alvo = estado_periodo["ano"]
        rot_alvo = _nome_mes_ano(m_alvo, a_alvo)
        try:
            salvos = svc.salvar_configuracao(itens, mes=m_alvo, ano=a_alvo)
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
            f"Metas de {rot_alvo} salvas com sucesso! (100% cravado)",
            "sucesso",
        )
        _atualizar_tela()
        if callable(ao_salvar):
            try:
                ao_salvar()
            except Exception:
                pass

    def _resetar(_):
        padrao = {d["posicao"]: d for d in P.POTES_PADRAO}
        r_flt = float(renda_ref[0])
        for l in linhas:
            d = padrao[l["pote"].posicao]
            l["nome"].value = d["nome"]
            v = int(d["percentual"])
            l["slider"].value = v
            l["perc"].value = str(v)
            if r_flt > 0:
                l["tf_rs"].value = f"{r_flt * (v / 100.0):.2f}".replace(".", ",")
        _atualizar_tela()

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
                            "Altere as porcentagens ou valores em R$ deste mês exclusivamente. Os demais meses ficam intactos.",
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

    # ── Linha UI para cada Pote ───────────────────────────────────────────────
    def _linha_ui(l: dict) -> ft.Column:
        return ft.Column(
            spacing=2,
            controls=[
                ft.Row(
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Container(width=10, height=10, bgcolor=l["pote"].cor, border_radius=5),
                        l["nome"],
                        l["tag_comp"],
                        l["tf_rs"],
                        l["perc"],
                        ft.Text("%", size=11, color=T.TEXT_MUTED),
                    ],
                ),
                l["slider"],
                ft.Container(padding=pad(left=18), content=l["preview"]),
            ],
        )

    card_renda = ft.Container(
        padding=pad(all_=20), bgcolor=T.SURFACE, border_radius=16, border=borda(),
        content=ft.ResponsiveRow(
            vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=20, run_spacing=12,
            controls=[
                ft.Column(col={"xs": 12, "md": 5}, spacing=6, controls=[
                    txt_titulo_renda,
                    txt_renda,
                    txt_info_renda,
                ]),
                ft.Column(col={"xs": 12, "md": 4}, spacing=4, controls=[
                    ft.Text("PISO DE CUSTOS FIXOS (R$):", size=10, color=T.TEXT_MUTED, weight=ft.FontWeight.W_600),
                    tf_piso_fixos,
                    ft.Text("Garante o teto mínimo de fixos mesmo com poucos lançamentos.", size=10.5, color=T.TEXT_MUTED),
                ]),
                ft.Container(col={"xs": 12, "md": 3}, alignment=ft.Alignment(1, 0), content=sw_simular),
            ],
        ),
    )

    card_donut = ft.Container(
        col={"xs": 12, "md": 5}, padding=pad(all_=20), bgcolor=T.SURFACE, border_radius=16, border=borda(),
        content=ft.Column(spacing=14, controls=[
            ft.Text("Visualização de Uso (100% Cravado)", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
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
                content="Resetar Padrões", on_click=_resetar,
                style=ft.ButtonStyle(color=T.TEXT_MUTED, side=ft.BorderSide(1, T.BORDER),
                                     shape=ft.RoundedRectangleBorder(radius=10), padding=pad(v=14)),
            ),
        ]),
    )

    card_reflexo = ft.Container(
        padding=pad(all_=20), bgcolor=T.SURFACE, border_radius=16, border=borda(color=f"{T.PRIMARY}40"),
        content=ft.Column(spacing=10, controls=[
            ft.Row(spacing=8, controls=[
                ft.Icon(ft.Icons.SYNC_ALT_ROUNDED, size=18, color=T.PRIMARY),
                ft.Text("Espelho do Dashboard em tempo real", size=15, weight=ft.FontWeight.BOLD,
                        color=T.TEXT_PRIMARY),
            ]),
            ft.Text("Veja o efeito das metas na Receita Real, Gastos Reais e Caixa Livre deste mês antes de salvar.",
                    size=11, color=T.TEXT_MUTED),
            reflexo_col,
        ]),
    )

    card_controle = ft.Container(
        col={"xs": 12, "md": 7}, padding=pad(all_=20), bgcolor=T.SURFACE, border_radius=16, border=borda(),
        content=ft.Column(spacing=10, controls=[
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text("Controle de Metas Flexível (R$ ou %)", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ft.Text("Digite em R$ ou % · Converte na hora", size=10.5, color=T.TEXT_MUTED),
            ]),
            *[_linha_ui(l) for l in linhas],
            ft.Divider(color=T.BORDER, height=16),
            ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Text("Total Alocado:", size=13, color=T.TEXT_MUTED), txt_alocado,
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
                "Regra de Ouro DemBase: Custos Fixos são ajustados às despesas reais (ou piso); "
                "os saldos de Semi Fixos, Metas e Conhecimento ficam retidos nos potes (sem inflar o Caixa Livre); "
                "e o restante fecha 100% entre Liberdade Financeira e Prazeres via Slider.",
                size=11, color=T.TEXT_PRIMARY, expand=True,
            ),
        ]),
    )

    conteudo = ft.Column(spacing=16, controls=[
        card_escopo_mes,
        card_renda,
        ft.ResponsiveRow(spacing=16, run_spacing=16, controls=[card_donut, card_controle]),
        card_reflexo,
        nota,
    ])

    _atualizar_cabecalho_mes()
    _atualizar_info_renda()
    _atualizar_tela(montado=False)
    return conteudo
