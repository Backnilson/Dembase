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

import asyncio

import flet as ft

from core import theme as T

from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo

from core.constants import formatar_moeda, formatar_data_br

from core.responsive import is_mobile

from core.periodo import obter_estado_periodo_atual, atualizar_datas_periodo_global

from core.report_context import ReportContext

from core.nav import ir_cartao, ir_relatorio_categoria

from views.shell_view import criar_shell, ROTA_CARTOES, sincronizar_shell_periodo

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



    def _construir_hero_cartao(

        cartao_info: dict,

        lim_total: float,

        lim_disp: float,

        valor_usado: float | None = None,

    ) -> ft.Container:

        nome_c = cartao_info.get("nome") or "Cartão de Crédito"

        cor_c = cartao_info.get("cor") or "#1E293B"

        band_k = db.normalizar_bandeira_cartao(cartao_info.get("bandeira"))

        bandeira = LABELS_BANDEIRAS.get(band_k, "Mastercard")

        fech = cartao_info.get("dia_fechamento", 1)

        venc = cartao_info.get("dia_vencimento", 10)

        usado = valor_usado if valor_usado is not None else max(0.0, lim_total - lim_disp)

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

            m_alvo = c.data_inicio.month

            a_alvo = c.data_inicio.year



            fatura_id_efetiva = c.fatura_id

            if not fatura_id_efetiva:

                try:

                    fat_garantida = await asyncio.to_thread(

                        db.obter_ou_criar_fatura_por_mes_ano, cartao_id, m_alvo, a_alvo

                    )

                    if fat_garantida and fat_garantida.get("id"):

                        fatura_id_efetiva = str(fat_garantida["id"])

                except Exception as ex_fat:

                    print(f"[CartaoReport] Aviso ao garantir fatura {m_alvo}/{a_alvo}: {ex_fat}")

            else:

                try:

                    fat_d = await asyncio.to_thread(db.obter_fatura_por_id, fatura_id_efetiva)

                    if fat_d and fat_d.get("mes") and fat_d.get("ano"):

                        m_alvo = int(fat_d["mes"])

                        a_alvo = int(fat_d["ano"])

                except Exception:

                    pass



            filtros_rpc = c.to_rpc_filtros()

            filtros_rpc["mes"] = m_alvo

            filtros_rpc["ano"] = a_alvo

            if fatura_id_efetiva:

                filtros_rpc["fatura_id"] = fatura_id_efetiva



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



            # Prioriza limite cadastrado no cartão, garantindo integridade

            lim_total = float(cartao_info.get("limite_total") or kpis_rpc.get("limite_total") or 0.0)

            if lim_total == 0.0:

                c_direto = await asyncio.to_thread(db.obter_cartao, cartao_id)

                if c_direto:

                    cartao_info = {**(cartao_info or {}), **c_direto}

                    lim_total = float(cartao_info.get("limite_total") or 0.0)



            # Busca saldo devedor real em aberto (compras não pagas)

            saldo_em_uso = float(kpis_rpc.get("limite_usado") or cartao_info.get("limite_usado") or 0.0)

            if saldo_em_uso == 0.0:

                saldo_em_uso = await asyncio.to_thread(db.obter_total_em_uso_cartao, cartao_id)



            # O valor em uso global reflete o saldo devedor, sendo no mínimo o gasto da fatura atual

            usado = max(saldo_em_uso, gasto_per)

            lim_disp = max(0.0, lim_total - usado) if lim_total > 0 else 0.0

            pct_uso = min(1.0, max(0.0, usado / lim_total)) if lim_total > 0 else 0.0



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



            # 2. Hero Plástico do Cartão recalculado com saldo em uso

            container_hero.content = _construir_hero_cartao(cartao_info, lim_total, lim_disp, valor_usado=usado)



            # =================================================================

            # Seletor de Fatura de Destino sincronizado com o período global

            # =================================================================

            dyn_opts = await asyncio.to_thread(db.listar_faturas_opcoes_cartao, cartao_id)

            faturas_map: dict[str, dict] = {}



            for opt in dyn_opts:

                chave_opt = str(opt["id"])

                faturas_map[chave_opt] = opt



            for f in faturas_lista:

                fid = str(f.get("id"))

                fm = int(f.get("mes", 1))

                fa = int(f.get("ano", f_ano_alvo))

                st = str(f.get("status") or "aberta").lower()

                st_label = "Aberta" if st == "aberta" else ("Fechada" if st == "fechada" else "Paga")

                m_txt = MESES_PT[fm] if 1 <= fm <= 12 else str(fm)

                v_fatura = float(f.get("valor_total", 0) or 0)

                label = f"{m_txt}/{fa} · {st_label}" + (f" ({formatar_moeda(v_fatura)})" if v_fatura > 0 else "")

                

                faturas_map[fid] = {

                    "id": fid,

                    "fatura_id_real": fid,

                    "mes": fm,

                    "ano": fa,

                    "label": label,

                    "status": st,

                    "valor_total": v_fatura,

                }

                chave_futura = f"futura_{fm}_{fa}"

                if chave_futura in faturas_map:

                    faturas_map[chave_futura]["fatura_id_real"] = fid

                    faturas_map[chave_futura]["label"] = label



            opcoes_ordenadas = sorted(

                list({(v.get("ano", 0), v.get("mes", 0)): v for v in faturas_map.values()}.values()),

                key=lambda x: (x.get("ano", 0), x.get("mes", 0)),

                reverse=True,

            )



            opcoes_dd_faturas: list[ft.dropdown.Option] = []

            for item_fat in opcoes_ordenadas:

                k = str(item_fat.get("fatura_id_real") or item_fat["id"])

                lbl = item_fat.get("label") or f"{MESES_PT[item_fat['mes']]}/{item_fat['ano']}"

                opcoes_dd_faturas.append(ft.dropdown.Option(key=k, text=lbl))



            fatura_selecionada_id = fatura_id_efetiva or str(fat_sel.get("id") or "")

            chaves_validas = {o.key for o in opcoes_dd_faturas}



            if fatura_selecionada_id not in chaves_validas:

                for o_fat in opcoes_ordenadas:

                    if o_fat.get("mes") == f_mes_alvo and o_fat.get("ano") == f_ano_alvo:

                        fatura_selecionada_id = str(o_fat.get("fatura_id_real") or o_fat["id"])

                        break



            if not fatura_selecionada_id and opcoes_dd_faturas:

                fatura_selecionada_id = opcoes_dd_faturas[0].key



            def _ao_selecionar_fatura(e):

                escolhido = e.data or e.control.value

                info = faturas_map.get(str(escolhido))

                if not info:

                    for v in faturas_map.values():

                        if str(v.get("fatura_id_real")) == str(escolhido):

                            info = v

                            break



                if info:

                    novo_m = int(info.get("mes", f_mes_alvo))

                    novo_a = int(info.get("ano", f_ano_alvo))

                    _, u_dia = monthrange(novo_a, novo_m)

                    d_ini = date(novo_a, novo_m, 1)

                    d_fim = date(novo_a, novo_m, u_dia)



                    fid_real = str(info.get("fatura_id_real") or "")

                    if not fid_real and not str(escolhido).startswith("futura_"):

                        fid_real = str(escolhido)



                    if not fid_real or str(escolhido).startswith("futura_"):

                        try:

                            fat_nova = db.obter_ou_criar_fatura_por_mes_ano(cartao_id, novo_m, novo_a)

                            fid_real = str(fat_nova.get("id")) if fat_nova else None

                        except Exception as ex_fn:

                            print(f"[CartaoReport] Erro ao criar fatura nova: {ex_fn}")



                    atualizar_datas_periodo_global(page, d_ini, d_fim, novo_m, novo_a)

                    sincronizar_shell_periodo(page)



                    contexto_atual[0] = contexto_atual[0].com(

                        fatura_id=fid_real,

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



            # Identifica status e metadados de pagamento da fatura selecionada
            fat_info_atual = faturas_map.get(str(fatura_selecionada_id)) or {}
            item_fat_lista = next((f for f in faturas_lista if str(f.get("id")) == str(fatura_selecionada_id)), None)

            status_fat_atual = "aberta"
            if item_fat_lista:
                status_fat_atual = str(item_fat_lista.get("status") or "aberta").lower()
            elif fat_info_atual:
                status_fat_atual = str(fat_info_atual.get("status") or "aberta").lower()
            elif fat_sel:
                status_fat_atual = str(fat_sel.get("status") or "aberta").lower()

            dt_pag = item_fat_lista.get("data_pagamento") if item_fat_lista else (fat_sel.get("data_pagamento") if fat_sel else None)
            conta_pag_nome = item_fat_lista.get("conta_pagamento_nome") if item_fat_lista else (fat_sel.get("conta_pagamento_nome") if fat_sel else None)
            valor_pago_fat = float(item_fat_lista.get("valor_pago", 0) or fat_sel.get("valor_pago", 0) or 0)

            # ── Funções de Pagamento e Estorno de Fatura ─────────────────────
            def abrir_modal_pagar_fatura():
                try:
                    contas = db.listar_contas()
                except Exception:
                    contas = []

                if not contas:
                    mostrar_feedback(page, "Cadastre ao menos uma conta bancária antes de pagar a fatura.", "aviso")
                    return

                if gasto_per <= 0 and total_reg == 0:
                    mostrar_feedback(page, "Esta fatura não possui compras vinculadas para pagamento.", "aviso")
                    return

                opcoes_contas: list[ft.dropdown.Option] = []
                conta_pref = cartao_info.get("conta_debito_id")
                conta_inicial = None

                for ct in contas:
                    cid = str(ct.get("id"))
                    nome = ct.get("nome", "Conta")
                    banco = ct.get("banco") or ""
                    saldo = float(ct.get("saldo_atual", 0) or 0)
                    desc_saldo = f"Saldo: {formatar_moeda(saldo)}"
                    rotulo = f"{nome} ({desc_saldo})" if not banco else f"{nome} · {banco} ({desc_saldo})"
                    opcoes_contas.append(ft.dropdown.Option(key=cid, text=rotulo))
                    if conta_pref and cid == str(conta_pref):
                        conta_inicial = cid
                    elif not conta_inicial and saldo >= gasto_per:
                        conta_inicial = cid

                if not conta_inicial and opcoes_contas:
                    conta_inicial = opcoes_contas[0].key

                dd_conta_origem = ft.Dropdown(
                    label="Conta Bancária de Origem (Saída do Dinheiro) *",
                    hint_text="Selecione de onde sairá o dinheiro",
                    value=conta_inicial,
                    options=opcoes_contas,
                    **T.dropdown_estilo(),
                )

                txt_data_pag = ft.TextField(
                    label="Data do Pagamento",
                    value=date.today().isoformat(),
                    read_only=True,
                    prefix_icon=ft.Icons.CALENDAR_TODAY_ROUNDED,
                    **T.campo_estilo(),
                )

                txt_aviso_saldo = ft.Text(
                    "",
                    color=T.WARNING,
                    size=11.5,
                    visible=False,
                )

                def _verificar_saldo(e=None):
                    cid = dd_conta_origem.value
                    conta_sel = next((ct for ct in contas if str(ct.get("id")) == cid), None)
                    if conta_sel:
                        saldo = float(conta_sel.get("saldo_atual", 0) or 0)
                        if saldo < gasto_per:
                            txt_aviso_saldo.value = f"Atenção: O saldo atual desta conta ({formatar_moeda(saldo)}) é menor que o valor da fatura."
                            txt_aviso_saldo.visible = True
                        else:
                            txt_aviso_saldo.visible = False
                    else:
                        txt_aviso_saldo.visible = False
                    try:
                        txt_aviso_saldo.update()
                    except Exception:
                        pass

                dd_conta_origem.on_select = _verificar_saldo
                _verificar_saldo()

                btn_confirmar = ft.FilledButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                            ft.Text("Confirmar Pagamento", color=ft.Colors.WHITE, size=13.5, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=T.RECEITA,
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=pad(h=18, v=12),
                    ),
                )

                async def _executar_pagamento(_):
                    if not dd_conta_origem.value:
                        mostrar_feedback(page, "Selecione a conta bancária de origem.", "aviso")
                        return

                    fid_alvo = fatura_selecionada_id
                    if not fid_alvo or str(fid_alvo).startswith("futura_"):
                        try:
                            fat_real = await asyncio.to_thread(db.obter_ou_criar_fatura_por_mes_ano, cartao_id, f_mes_alvo, f_ano_alvo)
                            if fat_real and fat_real.get("id"):
                                fid_alvo = str(fat_real["id"])
                        except Exception as ex_fat:
                            print(f"[CartaoReport] Erro ao assegurar fatura real: {ex_fat}")

                    btn_confirmar.disabled = True
                    btn_confirmar.content = ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE),
                            ft.Text("Processando Baixa...", color=ft.Colors.WHITE, size=13),
                        ],
                    )
                    modal_pagar.update()

                    try:
                        resultado = await asyncio.to_thread(
                            db.liquidar_pagamento_fatura,
                            fid_alvo,
                            dd_conta_origem.value,
                            txt_data_pag.value or date.today().isoformat(),
                            gasto_per,
                        )
                        fechar_dialogo(page, modal_pagar)
                        qtd = resultado.get("qtd_baixadas", total_reg)
                        mostrar_feedback(
                            page,
                            f"Fatura de {nome_mes_alvo}/{f_ano_alvo} liquidada com sucesso! {qtd} despesa{'s' if qtd != 1 else ''} marcada{'s' if qtd != 1 else ''} como Paga.",
                            "sucesso",
                        )
                        carregar(inicial=False)
                    except Exception as ex_pag:
                        btn_confirmar.disabled = False
                        btn_confirmar.content = ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                                ft.Text("Confirmar Pagamento", color=ft.Colors.WHITE, size=13.5, weight=ft.FontWeight.BOLD),
                            ],
                        )
                        try:
                            modal_pagar.update()
                        except Exception:
                            pass
                        mostrar_feedback(page, f"Erro ao liquidar fatura: {ex_pag}", "erro")

                btn_confirmar.on_click = lambda e: page.run_task(_executar_pagamento, e)

                largura_m = min(460, int(page.width - 32)) if (getattr(page, "width", None) and page.width < 500) else 460

                modal_pagar = ft.AlertDialog(
                    title=ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(
                                padding=pad(all_=8),
                                bgcolor=ft.Colors.with_opacity(0.12, T.RECEITA),
                                border_radius=8,
                                content=ft.Icon(ft.Icons.PAYMENTS_ROUNDED, color=T.RECEITA, size=22),
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text("Pagar Fatura do Cartão", size=16, color=T.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                                    ft.Text(f"{nome_c} · {nome_mes_alvo}/{f_ano_alvo}", size=12, color=T.TEXT_MUTED),
                                ],
                            ),
                        ],
                    ),
                    content=ft.Container(
                        width=largura_m,
                        content=ft.Column(
                            spacing=14,
                            tight=True,
                            controls=[
                                ft.Container(
                                    padding=pad(all_=14),
                                    bgcolor=T.SURFACE,
                                    border_radius=10,
                                    border=borda(),
                                    content=ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            ft.Column(
                                                spacing=2,
                                                tight=True,
                                                controls=[
                                                    ft.Text("Valor da Fatura", size=11, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                                                    ft.Text(formatar_moeda(gasto_per), size=20, color=T.WARNING, weight=ft.FontWeight.BOLD),
                                                ],
                                            ),
                                            ft.Container(
                                                padding=pad(h=10, v=6),
                                                bgcolor=ft.Colors.with_opacity(0.08, T.PRIMARY),
                                                border_radius=8,
                                                content=ft.Row(
                                                    spacing=5,
                                                    tight=True,
                                                    controls=[
                                                        ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=15, color=T.PRIMARY),
                                                        ft.Text(f"{total_reg} compra{'s' if total_reg != 1 else ''}", size=12, color=T.PRIMARY, weight=ft.FontWeight.BOLD),
                                                    ],
                                                ),
                                            ),
                                        ],
                                    ),
                                ),
                                ft.Text(
                                    "O valor será deduzido da conta bancária escolhida e todas as compras vinculadas a esta fatura receberão baixa em lote para o status 'Pago'.",
                                    size=12,
                                    color=T.TEXT_MUTED,
                                ),
                                dd_conta_origem,
                                txt_aviso_saldo,
                                txt_data_pag,
                            ],
                        ),
                    ),
                    actions=[
                        ft.TextButton(
                            content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                            on_click=lambda _: fechar_dialogo(page, modal_pagar),
                        ),
                        btn_confirmar,
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                abrir_dialogo(page, modal_pagar)

            def abrir_modal_estorno():
                modal_est = ft.AlertDialog(
                    title=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.RESTORE_ROUNDED, color=T.WARNING, size=22),
                            ft.Text("Estornar Pagamento", size=16, color=T.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                    content=ft.Text(
                        f"Deseja estornar o pagamento da fatura de {nome_mes_alvo}/{f_ano_alvo}?\n\n"
                        f"O débito de {formatar_moeda(valor_pago_fat or gasto_per)} será removido da conta bancária, "
                        f"o limite do cartão será reavaliado e a fatura voltará a constar como aberta/fechada.",
                        size=13,
                        color=T.TEXT_MUTED,
                    ),
                    actions=[
                        ft.TextButton(
                            content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                            on_click=lambda _: fechar_dialogo(page, modal_est),
                        ),
                        ft.FilledButton(
                            content=ft.Text("Estornar Pagamento", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                            style=ft.ButtonStyle(bgcolor=T.DESPESA),
                            on_click=lambda _: page.run_task(_executar_estorno, modal_est),
                        ),
                    ],
                    actions_alignment=ft.MainAxisAlignment.END,
                )
                abrir_dialogo(page, modal_est)

            async def _executar_estorno(modal_est):
                try:
                    await asyncio.to_thread(db.estornar_pagamento_fatura, fatura_selecionada_id)
                    fechar_dialogo(page, modal_est)
                    mostrar_feedback(page, f"Fatura de {nome_mes_alvo}/{f_ano_alvo} reaberta e pagamento estornado!", "sucesso")
                    carregar(inicial=False)
                except Exception as ex_est:
                    mostrar_feedback(page, f"Erro ao estornar fatura: {ex_est}", "erro")

            # Controles visuais de status e ação
            if status_fat_atual == "paga":
                controles_acao_fatura = ft.Row(
                    spacing=8,
                    tight=True,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            padding=pad(h=12, v=7),
                            bgcolor=ft.Colors.with_opacity(0.12, T.RECEITA),
                            border=borda(1, ft.Colors.with_opacity(0.35, T.RECEITA)),
                            border_radius=8,
                            content=ft.Row(
                                spacing=6,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=T.RECEITA, size=16),
                                    ft.Column(
                                        spacing=1,
                                        tight=True,
                                        controls=[
                                            ft.Text(
                                                "Fatura Zerada" if float(valor_pago_fat or gasto_per or 0) <= 0.01 else f"Fatura Paga ({formatar_moeda(valor_pago_fat or gasto_per)})",
                                                color=T.RECEITA,
                                                size=12.5,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                            ft.Text(
                                                f"Pago em {formatar_data_br(str(dt_pag)) if dt_pag else ''}" + (f" · {conta_pag_nome}" if conta_pag_nome else ""),
                                                color=T.TEXT_MUTED,
                                                size=10.5,
                                            ) if (dt_pag or conta_pag_nome) else ft.Container(),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        ft.IconButton(
                            icon=ft.Icons.RESTORE_ROUNDED,
                            icon_color=T.TEXT_MUTED,
                            icon_size=18,
                            tooltip="Estornar pagamento da fatura",
                            on_click=lambda _: abrir_modal_estorno(),
                        ) if float(valor_pago_fat or gasto_per or 0) > 0.01 else ft.Container(),
                    ],
                )
            else:
                controles_acao_fatura = ft.FilledButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.PAYMENTS_ROUNDED, color=ft.Colors.WHITE, size=17),
                            ft.Text("Pagar Fatura", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=T.RECEITA,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=pad(h=14, v=9),
                    ),
                    on_click=lambda _: abrir_modal_pagar_fatura(),
                )

            container_fatura_seletor.content = ft.Container(
                padding=pad(h=14, v=10),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(),
                content=ft.ResponsiveRow(
                    spacing=12,
                    run_spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Container(
                            col={"xs": 12, "sm": 7, "md": 8},
                            content=ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, color=T.PRIMARY, size=22),
                                    ft.Container(content=dd_fatura, expand=True),
                                ],
                            ),
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 5, "md": 4},
                            alignment=ft.Alignment(-1, 0) if mobile else ft.Alignment(1, 0),
                            content=controles_acao_fatura,
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

        sincronizar_shell_periodo(page)

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

        sincronizar_shell_periodo(page)

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

