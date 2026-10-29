"""

=============================================================================

DemBase v3 — views/dashboard_view.py  (Flet 1.0.1)

Dashboard Principal Multiplataforma (Mobile-First PWA + Desktop).

- Filtro Global de Período Flexível no Topo (tempo real, zero reload)

- KPI "Caixa Livre" destaca o valor LIVRE para gastar no card principal;

  Total da Sobra e Guardar/Investir aparecem ao clicar no card.

- Ordem personalizável das Seções, KPIs e Gráficos do Dashboard.

=============================================================================

"""

from __future__ import annotations

import random

import asyncio

from calendar import monthrange

import flet as ft

from core import theme as T

from core.theme import pad, borda, mostrar_feedback

from core.constants import session_set, FRASES_MOTIVACIONAIS, formatar_moeda, formatar_data_br, inicio_mes_atual, hoje

from core.responsive import is_mobile

from core.router import ROTA_LANCAMENTO, navegar

from core.nav import (

    ir_contas,

    ir_cartoes,

    ir_hub_relatorios,

    ir_relatorio_lancamentos,

)

from core.report_context import ReportContext

from core import storage

from views.widgets.clickable_card import kpi_clicavel

from views.widgets.dashboard_charts import (

    DASHBOARD_CHARTS_CATALOG,

    GRAFICOS_PADRAO_IDS,

    construir_grid_graficos,

)

from views.widgets.lancamento_sheet import abrir_lancamento

from views.widgets.potes_cards import secao_potes

from views.widgets.sobra_card import PainelGestaoSobra

from views.widgets.calendario_dashboard_card import secao_calendario_dashboard

from views.shell_view import criar_shell, ROTA_DASHBOARD, obter_estado_periodo_atual

import services.supabase_client as db





CATALOGO_SECOES_DASHBOARD = [

    {

        "id": "kpis",

        "titulo": "Indicadores & Caixa Livre (Topo)",

        "subtitulo": "Cards de Caixa Livre, Receitas, Despesas e Faturas",

        "icone": ft.Icons.SPEED_ROUNDED,

        "cor": T.PRIMARY,

    },

    {

        "id": "potes",

        "titulo": "Orçamento dos 6 Potes",

        "subtitulo": "Distribuição percentual das metas do período",

        "icone": ft.Icons.SAVINGS_ROUNDED,

        "cor": "#10B981",

    },

    {

        "id": "calendario",

        "titulo": "Calendário Financeiro (Mapa de Calor)",

        "subtitulo": "Grade mensal interativa de entradas, saídas e vencimentos",

        "icone": ft.Icons.CALENDAR_MONTH_ROUNDED,

        "cor": "#8B5CF6",

    },

    {

        "id": "graficos",

        "titulo": "Análise Visual (Gráficos)",

        "subtitulo": "Gráficos interativos do período selecionado",

        "icone": ft.Icons.ANALYTICS_ROUNDED,

        "cor": "#3B82F6",

    },

    {

        "id": "acoes",

        "titulo": "Ações Rápidas (Desktop)",

        "subtitulo": "Atalhos para lançamentos, contas, cartões e calendário",

        "icone": ft.Icons.FLASH_ON_ROUNDED,

        "cor": "#F59E0B",

    },

]



CATALOGO_KPIS_DASHBOARD = [

    {"id": "caixa_livre", "titulo": "Caixa Livre (Livre p/ Gastar)", "cor": T.PRIMARY, "icone": ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED},

    {"id": "receitas",    "titulo": "Receitas do Período",           "cor": T.RECEITA, "icone": ft.Icons.ARROW_UPWARD_ROUNDED},

    {"id": "despesas",    "titulo": "Despesas do Período",           "cor": T.DESPESA, "icone": ft.Icons.ARROW_DOWNWARD_ROUNDED},

    {"id": "faturas",     "titulo": "Faturas Abertas",               "cor": T.WARNING, "icone": ft.Icons.CREDIT_CARD_ROUNDED},

]





def criar_view_dashboard(

    page: ft.Page,

    match: dict | None = None,

    ctx: ReportContext | None = None,

) -> ft.View:

    mobile = is_mobile(page)

    estado_inicial = obter_estado_periodo_atual(page)



    data_ini_sel = [estado_inicial["data_inicio"].isoformat()]

    data_fim_sel = [estado_inicial["data_fim"].isoformat()]

    mes_sel      = [estado_inicial["mes"]]

    ano_sel      = [estado_inicial["ano"]]



    frase = random.choice(FRASES_MOTIVACIONAIS)



    # ── Saudação Dinâmica (Perfil / Auth) ──────────────────────────────────────
    primeiro_nome = ""
    try:
        perfil = db.ler_perfil()
        if perfil and perfil.get("nome"):
            partes = str(perfil["nome"]).strip().split()
            if partes and partes[0].lower() not in ("usuário", "usuario"):
                primeiro_nome = partes[0].capitalize()
    except Exception:
        pass

    if not primeiro_nome:
        try:
            usr = db.usuario_atual()
            if usr and getattr(usr, "user_metadata", None):
                meta = usr.user_metadata or {}
                raw_n = meta.get("nome") or meta.get("full_name") or meta.get("first_name")
                if raw_n:
                    partes = str(raw_n).strip().split()
                    if partes and partes[0].lower() not in ("usuário", "usuario"):
                        primeiro_nome = partes[0].capitalize()
        except Exception:
            pass

    saudacao_usuario = f"Olá, {primeiro_nome}! 👋" if primeiro_nome else "Olá! 👋"



    # ── Referências mutáveis para KPIs ────────────────────────────────────────

    # No card "Caixa Livre", o valor grande em destaque é o valor LIVRE (para gastar sem culpa).

    # O Total da Sobra e o valor de Guardar/Investir aparecem apenas ao clicar para expandir!

    tam_fonte_kpi = 16 if mobile else 20

    tam_fonte_kpi_outros = 15 if mobile else 18



    txt_caixa_livre = ft.Text(

        "R$ 0,00",

        color=T.PRIMARY,

        size=tam_fonte_kpi,

        weight=ft.FontWeight.BOLD,

        max_lines=1,

        overflow=ft.TextOverflow.ELLIPSIS,

    )

    txt_sub_caixa_livre = ft.Text(

        "Livre p/ gastar · Toque p/ detalhes",

        color=T.TEXT_MUTED,

        size=9.5 if mobile else 11,

        max_lines=1,

        overflow=ft.TextOverflow.ELLIPSIS,

    )

    txt_receitas = ft.Text(

        "R$ 0,00",

        color=T.RECEITA,

        size=tam_fonte_kpi_outros,

        weight=ft.FontWeight.BOLD,

        max_lines=1,

        overflow=ft.TextOverflow.ELLIPSIS,

    )

    txt_despesas = ft.Text(

        "R$ 0,00",

        color=T.DESPESA,

        size=tam_fonte_kpi_outros,

        weight=ft.FontWeight.BOLD,

        max_lines=1,

        overflow=ft.TextOverflow.ELLIPSIS,

    )

    txt_faturas = ft.Text(

        "R$ 0,00",

        color=T.WARNING,

        size=tam_fonte_kpi_outros,

        weight=ft.FontWeight.BOLD,

        max_lines=1,

        overflow=ft.TextOverflow.ELLIPSIS,

    )

    txt_sub_periodo = ft.Text(

        f"Período: {formatar_data_br(data_ini_sel[0])} a {formatar_data_br(data_fim_sel[0])}",

        color=T.TEXT_MUTED,

        size=11.5,

    )



    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2.2, visible=False)

    grid_graficos = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])



    area_potes = ft.Column(spacing=0, controls=[])

    area_calendario = ft.Column(spacing=0, controls=[])

    card_kpi_caixa_livre_ref: list[ft.Container] = []



    def _atualizar_subtitulo_kpi_sobra(dados: dict, expandido: bool):

        sobra_val = float(dados.get("sobra", 0.0) or 0.0)

        livre_val = float(dados.get("valor_livre_culpa", 0.0) or 0.0)

        tem_armadilha = bool(dados.get("tem_armadilha_fluxo", False))

        travado = bool(dados.get("travar_pelo_teto_seguro", True))

        teto_seguro = float(dados.get("teto_seguro_gasto", sobra_val) or 0.0)

        livre_proj = float(dados.get("valor_livre_projetado", livre_val) or 0.0)



        if dados.get("tem_sobra"):

            # Destaca em tamanho maior o valor Livre no card Caixa Livre (blindado pelo Teto Seguro se ativo)

            txt_caixa_livre.value = formatar_moeda(livre_val)

            if tem_armadilha and travado:

                txt_caixa_livre.color = "#06B6D4" if teto_seguro > 0 else T.WARNING

                txt_sub_caixa_livre.value = (

                    f"🛡️ Seguro hoje (Mês: {formatar_moeda(livre_proj)})"

                    if not expandido

                    else f"🛡️ Blindado pelo Pior Dia · Teto {formatar_moeda(teto_seguro)}"

                )

                txt_sub_caixa_livre.color = "#06B6D4" if teto_seguro > 0 else T.WARNING

            else:

                txt_caixa_livre.color = T.PRIMARY

                txt_sub_caixa_livre.value = (

                    "Livre p/ gastar · Ocultar total e guardar"

                    if expandido

                    else "Livre p/ gastar · Toque p/ ver total e guardar"

                )

                txt_sub_caixa_livre.color = T.TEXT_MUTED

        elif dados.get("em_deficit"):

            txt_caixa_livre.value = formatar_moeda(sobra_val)

            txt_caixa_livre.color = T.DESPESA

            txt_sub_caixa_livre.value = "Déficit no período · Toque p/ detalhes"

            txt_sub_caixa_livre.color = T.DESPESA

        else:

            txt_caixa_livre.value = "R$ 0,00"

            txt_caixa_livre.color = T.PRIMARY

            txt_sub_caixa_livre.value = "Livre p/ gastar · Toque p/ ratear sobra"

            txt_sub_caixa_livre.color = T.TEXT_MUTED



        if card_kpi_caixa_livre_ref:

            card_kpi_caixa_livre_ref[0].border = (

                borda(1.5, T.PRIMARY) if expandido else borda()

            )

            card_kpi_caixa_livre_ref[0].bgcolor = (

                f"{T.PRIMARY}10" if expandido else T.SURFACE

            )



    def _abrir_lancamento_aporte(valor_sugerido: float):

        from views.investimentos_view import abrir_modal_aporte_sobra_dashboard

        abrir_modal_aporte_sobra_dashboard(

            page=page,

            valor_sugerido=valor_sugerido,

            on_saved=lambda: carregar(inicial=False),

        )



    def _ao_alterar_potes_no_slider(novos_potes: list[dict]):

        if area_potes.controls:

            ctrl_p = getattr(area_potes.controls[0], "atualizar_potes", None)

            if callable(ctrl_p):

                ctrl_p(novos_potes)

            elif hasattr(area_potes.controls[0], "controller"):

                area_potes.controls[0].controller.atualizar_potes_em_tempo_real(novos_potes)



    painel_sobra = PainelGestaoSobra(

        page=page,

        mobile=mobile,

        on_atualizar_kpi_subtitulo=_atualizar_subtitulo_kpi_sobra,

        on_lancar_investimento=_abrir_lancamento_aporte,

        on_potes_alterados=_ao_alterar_potes_no_slider,

    )



    def _ao_liberar_sobra_pote(posicao: int, liberar: bool):

        """Libera/restaura a sobra de um pote manual e atualiza cards + Caixa Livre na hora."""

        try:

            painel_sobra.alternar_liberacao_pote(posicao, liberar)

            mostrar_feedback(

                page,

                "Sobra liberada para o Caixa Livre." if liberar else "Reserva do pote restaurada.",

                "sucesso",

            )

        except Exception as ex:

            mostrar_feedback(page, f"Não foi possível atualizar o pote: {ex}", "erro")



    def _abrir_configurador_metas(_=None):

        """Abre o configurador espelhado (mesmo período/receita/gastos do Dashboard) sem trocar de tela."""

        from views.widgets.potes_config import montar_aba_potes



        def _fechar_e_recarregar():

            try:

                page.pop_dialog()

            except Exception:

                pass

            carregar(inicial=False)



        conteudo = montar_aba_potes(

            page,

            mes=mes_sel[0],

            ano=ano_sel[0],

            data_ini=data_ini_sel[0],

            data_fim=data_fim_sel[0],

            ao_salvar=_fechar_e_recarregar,

        )

        largura = max(320, min(1120, int((page.width or 1000) - 24)))

        altura = max(420, int((page.height or 800) * 0.82))

        dlg = ft.AlertDialog(

            modal=False,

            bgcolor=T.BG,

            inset_padding=pad(h=8, v=12),

            title=ft.Row(

                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,

                controls=[

                    ft.Text("Ajustar metas do mês", size=17, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),

                    ft.IconButton(icon=ft.Icons.CLOSE_ROUNDED, icon_color=T.TEXT_MUTED,

                                  on_click=lambda _: page.pop_dialog()),

                ],

            ),

            content=ft.Container(

                width=largura,

                height=altura,

                content=ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, controls=[conteudo]),

            ),

        )

        page.show_dialog(dlg)



    def _abrir_extrato_pote(pote_id):

        session_set(page, "filtro_pote_id", pote_id)

        ir_relatorio_lancamentos(page, filtros={"pote_id": pote_id})



    # Cache do último pacote de dados para re-renderizar instantaneamente ao ligar/desligar gráficos

    ultimo_pacote: dict = {}



    def _renderizar_graficos_atuais():

        ids_ativos = storage.obter_graficos_dashboard_memoria(page, GRAFICOS_PADRAO_IDS)

        grid_graficos.controls = construir_grid_graficos(page, ultimo_pacote, ids_ativos)



    # ── Loader em Tempo Real (In-Place) ───────────────────────────────────────

    def carregar(

        d_ini: str | None = None,

        d_fim: str | None = None,

        mes: int | None = None,

        ano: int | None = None,

        inicial: bool = False,

    ):

        m = mes or mes_sel[0]

        a = ano or ano_sel[0]

        if d_ini and d_fim:

            di = d_ini

            df = d_fim

        elif mes or ano:

            ult_dia = monthrange(a, m)[1]

            di = f"{a:04d}-{m:02d}-01"

            df = f"{a:04d}-{m:02d}-{ult_dia:02d}"

        else:

            di = d_ini or data_ini_sel[0]

            df = d_fim or data_fim_sel[0]



        data_ini_sel[0] = di

        data_fim_sel[0] = df

        mes_sel[0] = m

        ano_sel[0] = a



        txt_sub_periodo.value = f"Período: {formatar_data_br(di)} a {formatar_data_br(df)}"



        if not inicial:

            spinner.visible = True

            try:

                page.update()

            except Exception:

                pass



        def _aplicar_dados(pacote_p, d_5030, b_6m, r_cart, r_potes, r_cal=None):

            overview = pacote_p.get("overview") if isinstance(pacote_p, dict) else None

            if not overview:

                overview = db.obter_overview_dashboard(m, a, data_inicio=di, data_fim=df)



            rec = float(overview.get("receitas", 0) or 0)

            desp = float(overview.get("despesas", 0) or 0)

            faturas_ab = float(overview.get("total_faturas", 0) or 0)



            txt_receitas.value = formatar_moeda(rec)

            txt_despesas.value = formatar_moeda(desp)

            txt_faturas.value  = formatar_moeda(faturas_ab)



            pacote_cal_efetivo = r_cal if isinstance(r_cal, dict) else db.obter_calendario_financeiro_mes(m, a, di, df)

            modo_s_dash = storage.obter_modo_saldo_calendario(page)

            s_contas_d = float(pacote_cal_efetivo.get("saldo_contas_consolidado") or 0.0)

            db.recalcular_modo_calendario(pacote_cal_efetivo, modo_s_dash, saldo_contas=s_contas_d)

            prot_fluxo = pacote_cal_efetivo.get("protecao_fluxo") if isinstance(pacote_cal_efetivo, dict) else None



            # Fallback inteligente: se r_potes vier sem potes, carrega os 6 potes do usuário para o mês/ano

            resumo_potes_efetivo = dict(r_potes) if (isinstance(r_potes, dict) and r_potes.get("potes")) else {}

            if not resumo_potes_efetivo.get("potes"):

                try:

                    potes_base = db.obter_potes(mes=m, ano=a)

                except Exception:

                    potes_base = []

                resumo_potes_efetivo = {

                    "renda": rec,

                    "base_utilizada": rec,

                    "total_gasto": desp,

                    "saldo": rec - desp,

                    "mes_ref": m,

                    "ano_ref": a,

                    "potes": potes_base or [],

                    "sem_pote": {"qtd": 0, "total": 0},

                }



            # Atualiza o painel de sobra com a arquitetura unificada dos 6 potes (utilizando a receita oficial do período)

            piso_fix_local = storage.obter_piso_custos_fixos(page, 1150.0)

            painel_sobra.atualizar_periodo(

                rec, desp, mes=m, ano=a, protecao_fluxo=prot_fluxo,

                resumo_potes=resumo_potes_efetivo, piso_custos_fixos=piso_fix_local,

            )



            ultimo_pacote.clear()

            ultimo_pacote.update({

                "data_inicio": di,

                "data_fim": df,

                "overview": overview,

                "regra_5030": d_5030 if isinstance(d_5030, dict) else {},

                "despesas_por_categoria": (

                    pacote_p.get("despesas_por_categoria")

                    if isinstance(pacote_p, dict) and "despesas_por_categoria" in pacote_p

                    else db.obter_despesas_por_categoria(m, a, data_inicio=di, data_fim=df)

                ),

                "receitas_por_categoria": (

                    pacote_p.get("receitas_por_categoria")

                    if isinstance(pacote_p, dict) and "receitas_por_categoria" in pacote_p

                    else db.obter_receitas_por_categoria(m, a, data_inicio=di, data_fim=df)

                ),

                "frequencia_diaria": (

                    pacote_p.get("frequencia_diaria")

                    if isinstance(pacote_p, dict) and "frequencia_diaria" in pacote_p

                    else db.obter_frequencia_gastos(m, a, data_inicio=di, data_fim=df)

                ),

                "despesas_por_forma": (

                    pacote_p.get("despesas_por_forma")

                    if isinstance(pacote_p, dict)

                    else []

                ),

                "balanco_6_meses": b_6m if isinstance(b_6m, list) else [],

                "resumo_cartoes": r_cart if isinstance(r_cart, dict) else {},

            })



            _renderizar_graficos_atuais()



            # Alinha estritamente a fonte de receita dos 6 potes com a receita oficial do período (rec)

            r_potes_ui = dict(resumo_potes_efetivo)

            r_potes_ui["renda"] = rec

            r_potes_ui["base_utilizada"] = rec

            r_potes_ui["mes_referencia"] = m

            r_potes_ui["ano_referencia"] = a



            try:

                pot_calc = painel_sobra.obter_dados_atuais().get("potes_atualizados")

                if pot_calc:

                    r_potes_ui["potes"] = pot_calc

            except Exception:

                pass



            area_potes.controls = [secao_potes(

                r_potes_ui,

                nav_func=_abrir_extrato_pote,

                on_ajustar=_abrir_configurador_metas,

                page=page,

                on_liberar=_ao_liberar_sobra_pote,

            )]



            def _ao_trocar_modo_saldo_dashboard(novo_modo: str = None):

                m_modo = novo_modo or storage.obter_modo_saldo_calendario(page)

                s_c = float(pacote_cal_efetivo.get("saldo_contas_consolidado") or 0.0)

                if s_c == 0.0:

                    try:

                        s_c = float(db.obter_saldo_consolidado_contas())

                    except Exception:

                        s_c = 0.0

                db.recalcular_modo_calendario(pacote_cal_efetivo, m_modo, saldo_contas=s_c)

                p_flx = pacote_cal_efetivo.get("protecao_fluxo") if isinstance(pacote_cal_efetivo, dict) else None

                painel_sobra.atualizar_periodo(rec, desp, mes=m, ano=a, protecao_fluxo=p_flx)

                try:

                    painel_sobra.container.update()

                except Exception:

                    pass

                try:

                    if card_kpi_caixa_livre_ref:

                        card_kpi_caixa_livre_ref[0].update()

                except Exception:

                    pass

                try:

                    page.update()

                except Exception:

                    pass



            area_calendario.controls = [

                secao_calendario_dashboard(

                    page=page,

                    pacote_cal=pacote_cal_efetivo,

                    mes=m,

                    ano=a,

                    on_refresh=_ao_trocar_modo_saldo_dashboard,

                    data_inicio=di,

                    data_fim=df,

                )

            ]



        if inicial:

            try:

                p_periodo = db.obter_dashboard_periodo(di, df)

                d_5030 = db.obter_resumo_5030(di, df)

                b_6m = db.obter_balanco_6_meses()

                r_cart = db.obter_resumo_cartoes(m, a)

                piso_f = storage.obter_piso_custos_fixos(page, 1150.0)

                r_potes = db.obter_resumo_potes(di, df, piso_custos_fixos=piso_f)

                r_cal = db.obter_calendario_financeiro_mes(m, a, di, df)

                _aplicar_dados(p_periodo, d_5030, b_6m, r_cart, r_potes, r_cal)

            except Exception:

                pass

            finally:

                spinner.visible = False

        else:

            spinner.visible = True

            try:

                page.update()

            except Exception:

                pass



            async def _executar_async():

                try:

                    res = await asyncio.gather(

                        db.executar_async(db.obter_dashboard_periodo, di, df),

                        db.executar_async(db.obter_resumo_5030, di, df),

                        db.executar_async(db.obter_balanco_6_meses),

                        db.executar_async(db.obter_resumo_cartoes, m, a),

                        db.executar_async(db.obter_resumo_potes, di, df, False, storage.obter_piso_custos_fixos(page, 1150.0)),

                        db.executar_async(db.obter_calendario_financeiro_mes, m, a, di, df),

                        return_exceptions=True,

                    )

                    p_periodo = res[0] if not isinstance(res[0], Exception) else {}

                    d_5030 = res[1] if not isinstance(res[1], Exception) else {}

                    b_6m = res[2] if not isinstance(res[2], Exception) else []

                    r_cart = res[3] if not isinstance(res[3], Exception) else {}

                    r_potes = res[4] if not isinstance(res[4], Exception) else {}

                    r_cal = res[5] if len(res) > 5 and not isinstance(res[5], Exception) else {}



                    _aplicar_dados(p_periodo, d_5030, b_6m, r_cart, r_potes, r_cal)

                except Exception as ex:

                    mostrar_feedback(page, f"Erro ao atualizar dashboard: {ex}", "erro")

                finally:

                    spinner.visible = False

                    try:

                        area_potes.update()

                    except Exception:

                        pass

                    try:

                        painel_sobra.container.update()

                    except Exception:

                        pass

                    try:

                        page.update()

                    except Exception:

                        pass



            try:

                loop = getattr(page, "loop", None)

                if loop and loop.is_running() and hasattr(page, "run_task"):

                    page.run_task(_executar_async)

                else:

                    p_periodo = db.obter_dashboard_periodo(di, df)

                    d_5030 = db.obter_resumo_5030(di, df)

                    b_6m = db.obter_balanco_6_meses()

                    r_cart = db.obter_resumo_cartoes(m, a)

                    piso_f = storage.obter_piso_custos_fixos(page, 1150.0)

                    r_potes = db.obter_resumo_potes(di, df, piso_custos_fixos=piso_f)

                    r_cal = db.obter_calendario_financeiro_mes(m, a, di, df)

                    _aplicar_dados(p_periodo, d_5030, b_6m, r_cart, r_potes, r_cal)

                    spinner.visible = False

                    try:

                        area_potes.update()

                    except Exception:

                        pass

                    try:

                        painel_sobra.container.update()

                    except Exception:

                        pass

                    try:

                        page.update()

                    except Exception:

                        pass

            except Exception:

                pass



    # ── Callbacks do Filtro Global do Shell ───────────────────────────────────

    def on_periodo(d_ini: str, d_fim: str, m: int, a: int):

        carregar(d_ini=d_ini, d_fim=d_fim, mes=m, ano=a, inicial=False)



    def on_mes_ano(m: int, a: int):

        carregar(mes=m, ano=a, inicial=False)



    # =========================================================================

    # KPI CARDS CLICÁVEIS — Com suporte a reordenação dinâmica

    # =========================================================================

    card_caixa_livre = kpi_clicavel(

        titulo="Caixa Livre",

        valor_control=txt_caixa_livre,

        subtitulo=txt_sub_caixa_livre,

        icone=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,

        cor=T.PRIMARY,

        col={"xs": 6, "sm": 6, "md": 3},

        mobile=mobile,

        compacto=mobile,

        ativo=painel_sobra.expandido,

        tooltip="Clique para ver o Total da Sobra e o valor para Guardar/Investir",

        on_click=lambda _: painel_sobra.alternar_expansao(),

    )

    card_kpi_caixa_livre_ref.append(card_caixa_livre)



    mapa_cards_kpis = {

        "caixa_livre": card_caixa_livre,

        "receitas": kpi_clicavel(

            titulo="Receitas",

            valor_control=txt_receitas,

            subtitulo="Ver receitas do período",

            icone=ft.Icons.ARROW_UPWARD_ROUNDED,

            cor=T.RECEITA,

            col={"xs": 6, "sm": 6, "md": 3},

            mobile=mobile,

            compacto=mobile,

            on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Receita", origem="dashboard"),

        ),

        "despesas": kpi_clicavel(

            titulo="Despesas",

            valor_control=txt_despesas,

            subtitulo="Ver despesas do período",

            icone=ft.Icons.ARROW_DOWNWARD_ROUNDED,

            cor=T.DESPESA,

            col={"xs": 6, "sm": 6, "md": 3},

            mobile=mobile,

            compacto=mobile,

            on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Despesa", origem="dashboard"),

        ),

        "faturas": kpi_clicavel(

            titulo="Faturas Abertas",

            valor_control=txt_faturas,

            subtitulo="Ver cartões e faturas",

            icone=ft.Icons.CREDIT_CARD_ROUNDED,

            cor=T.WARNING,

            col={"xs": 6, "sm": 6, "md": 3},

            mobile=mobile,

            compacto=mobile,

            on_click=lambda _: ir_cartoes(page),

        ),

    }



    kpis = ft.ResponsiveRow(

        spacing=8 if mobile else 12,

        run_spacing=8 if mobile else 12,

        controls=[],

    )



    def _montar_kpis_ordenados():

        ordem_kpis = storage.obter_ordem_kpis_dashboard(page)

        kpis.controls = [

            mapa_cards_kpis[kid]

            for kid in ordem_kpis

            if kid in mapa_cards_kpis

        ]



    _montar_kpis_ordenados()



    bloco_kpis_e_sobra = ft.Column(

        spacing=0,

        controls=[

            kpis,

            ft.Container(height=12 if mobile else 14),

            painel_sobra.container,

        ],

    )



    # =========================================================================

    # MODAL DE PERSONALIZAÇÃO: ORDEM DAS SEÇÕES, ORDEM DOS KPIS E GRÁFICOS

    # =========================================================================

    corpo_secoes_dinamicas = ft.Column(spacing=16 if mobile else 20, controls=[])



    def _abrir_seletor_graficos(_=None):

        ordem_secoes_atual = list(storage.obter_ordem_secoes_dashboard(page))

        for s_item in CATALOGO_SECOES_DASHBOARD:

            if s_item["id"] not in ordem_secoes_atual:

                ordem_secoes_atual.append(s_item["id"])

        secoes_visiveis_set = set(storage.obter_ordem_secoes_dashboard(page))



        ordem_kpis_atual = list(storage.obter_ordem_kpis_dashboard(page))



        ativos_graf_lista = list(storage.obter_graficos_dashboard_memoria(page, GRAFICOS_PADRAO_IDS))

        ativos_graf_set = set(ativos_graf_lista)

        ordem_graf_catalogo = list(ativos_graf_lista) + [

            g["id"] for g in DASHBOARD_CHARTS_CATALOG if g["id"] not in ativos_graf_set

        ]



        aba_modal = [0]  # 0: Ordem das Seções, 1: Ordem dos Cards Topo, 2: Gráficos

        col_conteudo_modal = ft.Column(tight=True, spacing=8, scroll=ft.ScrollMode.AUTO, controls=[])

        row_abas_modal = ft.Row(spacing=6, wrap=True, controls=[])



        def _mover_item(lista: list, idx: int, delta: int):

            novo_idx = idx + delta

            if 0 <= novo_idx < len(lista):

                lista[idx], lista[novo_idx] = lista[novo_idx], lista[idx]

                _render_modal_body()

                page.update()



        def _render_modal_body():

            # Atualiza abas do modal

            opcoes_abas = [

                (0, "1. Ordem das Seções", ft.Icons.VIEW_AGENDA_ROUNDED),

                (1, "2. Ordem dos Cards", ft.Icons.VIEW_COLUMN_ROUNDED),

                (2, "3. Gráficos", ft.Icons.DONUT_LARGE_ROUNDED),

            ]

            row_abas_modal.controls = [

                ft.Container(

                    padding=pad(h=10, v=6),

                    border_radius=10,

                    bgcolor=T.PRIMARY if aba_modal[0] == i else T.SURFACE_ALT,

                    ink=True,

                    on_click=lambda _, ix=i: (aba_modal.__setitem__(0, ix), _render_modal_body(), page.update()),

                    content=ft.Row(

                        spacing=5,

                        tight=True,

                        controls=[

                            ft.Icon(ic, size=14, color="#FFFFFF" if aba_modal[0] == i else T.TEXT_MUTED),

                            ft.Text(

                                lbl,

                                size=11.5,

                                weight=ft.FontWeight.BOLD if aba_modal[0] == i else ft.FontWeight.W_500,

                                color="#FFFFFF" if aba_modal[0] == i else T.TEXT_MUTED,

                            ),

                        ],

                    ),

                )

                for i, lbl, ic in opcoes_abas

            ]



            col_conteudo_modal.controls.clear()



            if aba_modal[0] == 0:

                col_conteudo_modal.controls.append(

                    ft.Text(

                        "Defina a ordem de exibição dos blocos no Dashboard (use ↑ e ↓):",

                        size=12,

                        color=T.TEXT_MUTED,

                    )

                )

                mapa_sec = {s["id"]: s for s in CATALOGO_SECOES_DASHBOARD}

                for idx, sid in enumerate(ordem_secoes_atual):

                    info = mapa_sec.get(sid)

                    if not info:

                        continue

                    visivel = sid in secoes_visiveis_set



                    def _toggle_sec(e, s_id=sid):

                        if e.control.value:

                            secoes_visiveis_set.add(s_id)

                        elif len(secoes_visiveis_set) > 1:

                            secoes_visiveis_set.discard(s_id)

                        else:

                            e.control.value = True

                        page.update()



                    col_conteudo_modal.controls.append(

                        ft.Container(

                            padding=pad(h=10, v=8),

                            bgcolor=T.SURFACE_ALT,

                            border_radius=10,

                            border=borda(1, f"{info['cor']}40" if visivel else T.BORDER),

                            content=ft.Row(

                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,

                                controls=[

                                    ft.Row(

                                        spacing=8,

                                        expand=True,

                                        controls=[

                                            ft.Container(

                                                padding=pad(h=7, v=3),

                                                border_radius=6,

                                                bgcolor=f"{info['cor']}20",

                                                content=ft.Text(f"{idx + 1}º", size=11, weight=ft.FontWeight.BOLD, color=info["cor"]),

                                            ),

                                            ft.Icon(info["icone"], color=info["cor"], size=18),

                                            ft.Column(

                                                spacing=1,

                                                expand=True,

                                                controls=[

                                                    ft.Text(info["titulo"], size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),

                                                    ft.Text(info["subtitulo"], size=10.5, color=T.TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),

                                                ],

                                            ),

                                        ],

                                    ),

                                    ft.Row(

                                        spacing=2,

                                        tight=True,

                                        controls=[

                                            ft.IconButton(

                                                icon=ft.Icons.ARROW_UPWARD_ROUNDED,

                                                icon_size=16,

                                                icon_color=T.TEXT_PRIMARY if idx > 0 else T.TEXT_MUTED,

                                                disabled=(idx == 0),

                                                tooltip="Mover para cima",

                                                on_click=lambda _, i=idx: _mover_item(ordem_secoes_atual, i, -1),

                                            ),

                                            ft.IconButton(

                                                icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,

                                                icon_size=16,

                                                icon_color=T.TEXT_PRIMARY if idx < len(ordem_secoes_atual) - 1 else T.TEXT_MUTED,

                                                disabled=(idx == len(ordem_secoes_atual) - 1),

                                                tooltip="Mover para baixo",

                                                on_click=lambda _, i=idx: _mover_item(ordem_secoes_atual, i, 1),

                                            ),

                                            ft.Switch(

                                                value=visivel,

                                                active_color=T.PRIMARY,

                                                on_change=_toggle_sec,

                                            ),

                                        ],

                                    ),

                                ],

                            ),

                        )

                    )



            elif aba_modal[0] == 1:

                col_conteudo_modal.controls.append(

                    ft.Text(

                        "Escolha a ordem da esquerda para a direita dos 4 Cards Superiores:",

                        size=12,

                        color=T.TEXT_MUTED,

                    )

                )

                mapa_k = {k["id"]: k for k in CATALOGO_KPIS_DASHBOARD}

                for idx, kid in enumerate(ordem_kpis_atual):

                    info = mapa_k.get(kid)

                    if not info:

                        continue

                    col_conteudo_modal.controls.append(

                        ft.Container(

                            padding=pad(h=10, v=8),

                            bgcolor=T.SURFACE_ALT,

                            border_radius=10,

                            border=borda(),

                            content=ft.Row(

                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,

                                controls=[

                                    ft.Row(

                                        spacing=8,

                                        expand=True,

                                        controls=[

                                            ft.Container(

                                                padding=pad(h=7, v=3),

                                                border_radius=6,

                                                bgcolor=f"{info['cor']}20",

                                                content=ft.Text(f"{idx + 1}º", size=11, weight=ft.FontWeight.BOLD, color=info["cor"]),

                                            ),

                                            ft.Icon(info["icone"], color=info["cor"], size=18),

                                            ft.Text(info["titulo"], size=13, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),

                                        ],

                                    ),

                                    ft.Row(

                                        spacing=2,

                                        tight=True,

                                        controls=[

                                            ft.IconButton(

                                                icon=ft.Icons.ARROW_UPWARD_ROUNDED,

                                                icon_size=16,

                                                icon_color=T.TEXT_PRIMARY if idx > 0 else T.TEXT_MUTED,

                                                disabled=(idx == 0),

                                                on_click=lambda _, i=idx: _mover_item(ordem_kpis_atual, i, -1),

                                            ),

                                            ft.IconButton(

                                                icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,

                                                icon_size=16,

                                                icon_color=T.TEXT_PRIMARY if idx < len(ordem_kpis_atual) - 1 else T.TEXT_MUTED,

                                                disabled=(idx == len(ordem_kpis_atual) - 1),

                                                on_click=lambda _, i=idx: _mover_item(ordem_kpis_atual, i, 1),

                                            ),

                                        ],

                                    ),

                                ],

                            ),

                        )

                    )



            else:

                col_conteudo_modal.controls.append(

                    ft.Text(

                        "Ordene e escolha quais gráficos aparecem no Dashboard:",

                        size=12,

                        color=T.TEXT_MUTED,

                    )

                )

                mapa_g = {g["id"]: g for g in DASHBOARD_CHARTS_CATALOG}

                for idx, gid in enumerate(ordem_graf_catalogo):

                    item = mapa_g.get(gid)

                    if not item:

                        continue

                    ativo_g = gid in ativos_graf_set



                    def _toggle_g(e, g_id=gid):

                        if e.control.value:

                            ativos_graf_set.add(g_id)

                        elif len(ativos_graf_set) > 1:

                            ativos_graf_set.discard(g_id)

                        else:

                            e.control.value = True

                        page.update()



                    col_conteudo_modal.controls.append(

                        ft.Container(

                            padding=pad(h=10, v=8),

                            bgcolor=T.SURFACE_ALT,

                            border_radius=10,

                            border=borda(),

                            content=ft.Row(

                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,

                                controls=[

                                    ft.Row(

                                        spacing=8,

                                        expand=True,

                                        controls=[

                                            ft.Icon(item["icone"], color=item["cor"], size=18),

                                            ft.Column(

                                                spacing=1,

                                                expand=True,

                                                controls=[

                                                    ft.Text(item["titulo"].strip(), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_600),

                                                    ft.Text(item["subtitulo"], color=T.TEXT_MUTED, size=10.5, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),

                                                ],

                                            ),

                                        ],

                                    ),

                                    ft.Row(

                                        spacing=2,

                                        tight=True,

                                        controls=[

                                            ft.IconButton(

                                                icon=ft.Icons.ARROW_UPWARD_ROUNDED,

                                                icon_size=16,

                                                disabled=(idx == 0),

                                                on_click=lambda _, i=idx: _mover_item(ordem_graf_catalogo, i, -1),

                                            ),

                                            ft.IconButton(

                                                icon=ft.Icons.ARROW_DOWNWARD_ROUNDED,

                                                icon_size=16,

                                                disabled=(idx == len(ordem_graf_catalogo) - 1),

                                                on_click=lambda _, i=idx: _mover_item(ordem_graf_catalogo, i, 1),

                                            ),

                                            ft.Switch(

                                                value=ativo_g,

                                                active_color=T.PRIMARY,

                                                on_change=_toggle_g,

                                            ),

                                        ],

                                    ),

                                ],

                            ),

                        )

                    )



        _render_modal_body()



        def _salvar_escolha(_):

            secoes_finais = [s for s in ordem_secoes_atual if s in secoes_visiveis_set]

            if not secoes_finais:

                secoes_finais = ["kpis"]

            storage.salvar_ordem_secoes_dashboard_sync(page, secoes_finais)

            storage.salvar_ordem_kpis_dashboard_sync(page, ordem_kpis_atual)



            graficos_finais = [g for g in ordem_graf_catalogo if g in ativos_graf_set]

            if not graficos_finais:

                graficos_finais = [GRAFICOS_PADRAO_IDS[0]]

            storage.salvar_graficos_dashboard_sync(page, graficos_finais)



            page.pop_dialog()

            _montar_kpis_ordenados()

            _renderizar_graficos_atuais()

            _montar_secoes_ordenadas()

            mostrar_feedback(page, "Ordem e layout do Dashboard atualizados!", "sucesso")

            page.update()



        dlg_graf = ft.AlertDialog(

            modal=False,

            bgcolor=T.SURFACE,

            shape=ft.RoundedRectangleBorder(radius=18),

            title=ft.Column(

                spacing=10,

                tight=True,

                controls=[

                    ft.Row(

                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,

                        controls=[

                            ft.Row(

                                spacing=8,

                                controls=[

                                    ft.Icon(ft.Icons.DASHBOARD_CUSTOMIZE_ROUNDED, color=T.PRIMARY, size=20),

                                    ft.Text("Ordenar e Personalizar Dashboard", color=T.TEXT_PRIMARY, size=15.5, weight=ft.FontWeight.BOLD),

                                ],

                            ),

                            ft.IconButton(

                                icon=ft.Icons.CLOSE_ROUNDED,

                                icon_color=T.TEXT_MUTED,

                                icon_size=18,

                                on_click=lambda _: page.pop_dialog(),

                            ),

                        ],

                    ),

                    row_abas_modal,

                ],

            ),

            content=ft.Container(

                width=460,

                height=370,

                content=col_conteudo_modal,

            ),

            actions=[

                ft.TextButton("Cancelar", on_click=lambda _: page.pop_dialog()),

                ft.FilledButton(

                    content=ft.Text("Salvar Ordem", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),

                    style=ft.ButtonStyle(

                        bgcolor=T.PRIMARY,

                        shape=ft.RoundedRectangleBorder(radius=10),

                    ),

                    on_click=_salvar_escolha,

                ),

            ],

        )

        page.show_dialog(dlg_graf)



    # =========================================================================

    # BOAS-VINDAS + SUBTÍTULO DO PERÍODO + PERSONALIZAR ORDEM/GRÁFICOS

    # =========================================================================

    boas_vindas = ft.Row(

        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,

        vertical_alignment=ft.CrossAxisAlignment.CENTER,

        controls=[

            ft.Column(

                spacing=3,

                expand=True,

                controls=[

                    ft.Row(

                        spacing=8,

                        vertical_alignment=ft.CrossAxisAlignment.CENTER,

                        controls=[

                            ft.Text(

                                saudacao_usuario,

                                color=T.TEXT_PRIMARY,

                                size=20 if mobile else 24,

                                weight=ft.FontWeight.BOLD,

                            ),

                            spinner,

                        ],

                    ),

                    txt_sub_periodo,

                    ft.Text(

                        f'"{frase}"',

                        color=T.TEXT_MUTED,

                        size=11.5,

                        italic=True,

                        max_lines=1 if mobile else 2,

                        overflow=ft.TextOverflow.ELLIPSIS,

                    ),

                ],

            ),

            ft.Container(

                padding=pad(h=10, v=7),

                border_radius=10,

                bgcolor=f"{T.PRIMARY}18",

                border=borda(1, f"{T.PRIMARY}40"),

                ink=True,

                tooltip="Escolher a ordem das seções, cards e gráficos do Dashboard",

                on_click=_abrir_seletor_graficos,

                content=ft.Row(

                    spacing=6,

                    tight=True,

                    controls=[

                        ft.Icon(ft.Icons.DASHBOARD_CUSTOMIZE_ROUNDED, color=T.PRIMARY, size=16),

                        ft.Text(

                            "Ordenar Tela" if not mobile else "Ordem",

                            color=T.PRIMARY,

                            size=12,

                            weight=ft.FontWeight.W_600,

                        ),

                    ],

                ),

            ),

        ],

    )



    # =========================================================================

    # CABEÇALHO DA SEÇÃO DE GRÁFICOS

    # =========================================================================

    barra_titulo_graficos = ft.Row(

        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,

        vertical_alignment=ft.CrossAxisAlignment.CENTER,

        wrap=True if mobile else False,

        spacing=8,

        controls=[

            ft.Row(

                spacing=8,

                tight=True,

                controls=[

                    ft.Icon(ft.Icons.ANALYTICS_ROUNDED, color=T.PRIMARY, size=18),

                    ft.Text(

                        "Análise Visual do Período",

                        color=T.TEXT_PRIMARY,

                        size=15,

                        weight=ft.FontWeight.BOLD,

                    ),

                ],

            ),

            ft.Row(

                spacing=4,

                wrap=True,

                controls=[

                    ft.TextButton(

                        content=ft.Row(

                            spacing=4,

                            tight=True,

                            controls=[

                                ft.Icon(ft.Icons.ASSESSMENT_ROUNDED, color=T.TEXT_MUTED, size=14),

                                ft.Text("Central de Relatórios", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),

                            ],

                        ),

                        on_click=lambda _: ir_hub_relatorios(page),

                    ),

                    ft.TextButton(

                        content=ft.Row(

                            spacing=4,

                            tight=True,

                            controls=[

                                ft.Icon(ft.Icons.TUNE_ROUNDED, color=T.PRIMARY, size=14),

                                ft.Text("Ordenar / Configurar", color=T.PRIMARY, size=12, weight=ft.FontWeight.W_600),

                            ],

                        ),

                        on_click=_abrir_seletor_graficos,

                    ),

                ],

            ),

        ],

    )



    bloco_graficos = ft.Column(

        spacing=8,

        controls=[

            barra_titulo_graficos,

            grid_graficos,

        ],

    )



    # =========================================================================

    # AÇÕES RÁPIDAS (Apenas no Desktop — no Mobile já estão na BottomAppBar/FAB)

    # =========================================================================

    acoes_desktop = ft.Container(

        visible=not mobile,

        padding=pad(all_=20),

        bgcolor=T.SURFACE,

        border_radius=14,

        border=borda(),

        content=ft.Column(

            spacing=0,

            controls=[

                ft.Text("Ações Rápidas", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),

                ft.Container(height=14),

                ft.ResponsiveRow(

                    spacing=10,

                    run_spacing=10,

                    controls=[

                        ft.Container(

                            col={"xs": 12, "sm": 4},

                            content=ft.FilledButton(

                                content=ft.Row(

                                    spacing=6,

                                    tight=True,

                                    controls=[

                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=T.ON_PRIMARY, size=18),

                                        ft.Text("Novo Lançamento", color=T.ON_PRIMARY, size=13, weight=ft.FontWeight.W_600),

                                    ],

                                ),

                                on_click=lambda _: abrir_lancamento(page, on_saved=lambda: carregar(inicial=False)),

                                expand=True,

                                style=ft.ButtonStyle(

                                    bgcolor=T.PRIMARY,

                                    overlay_color=T.PRIMARY_DARK,

                                    shape=ft.RoundedRectangleBorder(radius=10),

                                    padding=pad(h=20, v=14),

                                ),

                            ),

                        ),

                        ft.Container(

                            col={"xs": 6, "sm": 2},

                            content=T.botao_outline("Contas", icone=ft.Icons.ACCOUNT_BALANCE_ROUNDED, on_click=lambda _: ir_contas(page)),

                        ),

                        ft.Container(

                            col={"xs": 6, "sm": 2},

                            content=T.botao_outline("Cartões", icone=ft.Icons.CREDIT_CARD_ROUNDED, on_click=lambda _: ir_cartoes(page)),

                        ),

                        ft.Container(

                            col={"xs": 6, "sm": 2},

                            content=T.botao_outline("Calendário", icone=ft.Icons.CALENDAR_MONTH_ROUNDED, on_click=lambda _: navegar(page, "/calendario")),

                        ),

                        ft.Container(

                            col={"xs": 6, "sm": 2},

                            content=T.botao_outline("Relatórios", icone=ft.Icons.BAR_CHART_ROUNDED, on_click=lambda _: ir_hub_relatorios(page)),

                        ),

                    ],

                ),

            ],

        ),

    )



    mapa_secoes_widgets = {

        "kpis": bloco_kpis_e_sobra,

        "potes": area_potes,

        "calendario": area_calendario,

        "graficos": bloco_graficos,

        "acoes": acoes_desktop,

    }



    def _montar_secoes_ordenadas():

        ordem = storage.obter_ordem_secoes_dashboard(page)

        corpo_secoes_dinamicas.controls = [

            mapa_secoes_widgets[sid]

            for sid in ordem

            if sid in mapa_secoes_widgets

        ]



    _montar_secoes_ordenadas()



    # =========================================================================

    # CORPO PRINCIPAL

    # =========================================================================

    conteudo = ft.Column(

        spacing=0,

        controls=[

            boas_vindas,

            ft.Container(height=14 if mobile else 18),

            corpo_secoes_dinamicas,

            ft.Container(height=28),

        ],

    )



    # Carrega dados iniciais

    carregar(inicial=True)



    v = criar_shell(

        page,

        rota_ativa=ROTA_DASHBOARD,

        conteudo=conteudo,

        on_mes_ano_change=on_mes_ano,

        on_periodo_change=on_periodo,

        on_lancamento_saved=lambda: carregar(inicial=False),

    )

    v._dembase_refresh = lambda: carregar(inicial=False)

    return v

