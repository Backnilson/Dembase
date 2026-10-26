"""
=============================================================================
DemBase v3 — views/caixinhas_view.py  (Flet 1.0.1)
Módulo de Caixinhas de Teto (Provisionamento e Ritmo de Gastos).
- Agendamento de Provisão Pendente na Criação:
  Ao criar a caixinha (ex: R$ 400,00 para o dia 5), gera automaticamente um
  lançamento PENDENTE (Despesa ou Transferência) na conta bancária para a data definida.
- O Cofrinho Enche ao Pagar:
  A caixinha nasce com R$ 0,00. Quando o usuário efetua o pagamento da provisão
  (na lista de lançamentos ou clicando no botão do card), o cofrinho enche com o saldo!
- Vínculo Obrigatório aos 6 Potes Financeiros, Categoria e Subcategoria.
- Consumo em Tempo Real: despesas vinculadas no app abatem do saldo da caixinha.
- Acompanhamento visual de ritmo de gastos diários seguros (burn rate).
- Atalhos rápidos: Pagar/Encher, Aporte (+) e Gastar (-).
=============================================================================
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from calendar import monthrange
import flet as ft

from core import theme as T
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.constants import formatar_moeda
from core.periodo import obter_estado_periodo_atual
from core.responsive import is_mobile
from views.shell_view import criar_shell, ROTA_CAIXINHAS
from views.widgets.clickable_card import kpi_clicavel
from views.widgets.custom_date_picker import (
    abrir_seletor_data_modal,
    formatar_data_amigavel,
    formatar_data_br,
)
import services.supabase_client as db

CORES_CAIXINHAS = [
    {"hex": "#10B981", "label": "Verde Esmeralda"},
    {"hex": "#3B82F6", "label": "Azul Royal"},
    {"hex": "#8B5CF6", "label": "Roxo Violeta"},
    {"hex": "#F59E0B", "label": "Âmbar / Laranja"},
    {"hex": "#EC4899", "label": "Rosa Chiclete"},
    {"hex": "#06B6D4", "label": "Ciano Moderno"},
    {"hex": "#6366F1", "label": "Índigo"},
    {"hex": "#14B8A6", "label": "Teal"},
]

ICONES_OPCOES = [
    {"nome": "inventory_2", "icone": ft.Icons.INVENTORY_2_ROUNDED, "label": "Caixa Geral"},
    {"nome": "two_wheeler", "icone": ft.Icons.TWO_WHEELER_ROUNDED, "label": "Moto / Veículo"},
    {"nome": "local_gas_station", "icone": ft.Icons.LOCAL_GAS_STATION_ROUNDED, "label": "Gasolina"},
    {"nome": "shopping_cart", "icone": ft.Icons.SHOPPING_CART_ROUNDED, "label": "Mercado / Feira"},
    {"nome": "restaurant", "icone": ft.Icons.RESTAURANT_ROUNDED, "label": "Alimentação"},
    {"nome": "local_pharmacy", "icone": ft.Icons.LOCAL_PHARMACY_ROUNDED, "label": "Saúde / Farmácia"},
    {"nome": "celebration", "icone": ft.Icons.CELEBRATION_ROUNDED, "label": "Lazer / Passeios"},
    {"nome": "savings", "icone": ft.Icons.SAVINGS_ROUNDED, "label": "Reserva / Metas"},
]

MAPA_ICONES = {item["nome"]: item["icone"] for item in ICONES_OPCOES}


def montar_aba_caixinhas(page: ft.Page, match=None) -> ft.Control:
    mobile = is_mobile(page)
    caixinhas_lista: list[dict] = []

    # ── Controles de KPIs do Topo ─────────────────────────────────────────────
    tam_kpi = 15 if mobile else 18
    txt_total_meta   = ft.Text("R$ 0,00", color=T.TEXT_PRIMARY, size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_saldo  = ft.Text("R$ 0,00", color=T.PRIMARY,      size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_gasto  = ft.Text("R$ 0,00", color=T.WARNING,      size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_ritmo_diario = ft.Text("R$ 0,00 / dia", color=T.INFO,  size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)

    grid_caixinhas = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    banner_aviso_migracao = ft.Container(
        visible=False,
        bgcolor=f"{T.WARNING}1A",
        border=borda(1, f"{T.WARNING}60"),
        border_radius=12,
        padding=pad(h=14, v=10),
        content=ft.Row([
            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=T.WARNING, size=24),
            ft.Column([
                ft.Text("Tabela 'caixinhas_teto' não encontrada no banco de dados!", size=13, weight=ft.FontWeight.BOLD, color=T.WARNING),
                ft.Text(
                    "Para ativar o módulo de Caixinhas de Teto, execute o arquivo migrations/016_create_caixinhas_teto.sql no Supabase.",
                    size=11.5,
                    color=T.TEXT_PRIMARY,
                ),
            ], spacing=2, expand=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    def _safe_update():
        try:
            txt_total_meta.update()
            txt_total_saldo.update()
            txt_total_gasto.update()
            txt_ritmo_diario.update()
            grid_caixinhas.update()
            banner_aviso_migracao.update()
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

    # ── Carregar Dados ────────────────────────────────────────────────────────
    def carregar_dados(inicial: bool = False, forcar: bool = False):
        if not inicial:
            spinner.visible = True
            _safe_update()

        nonlocal caixinhas_lista
        try:
            resumo = db.obter_resumo_caixinhas(forcar_atualizacao=forcar or not inicial)
            caixinhas_lista = resumo.get("caixinhas") or []
            banner_aviso_migracao.visible = False

            tot_meta   = float(resumo.get("total_meta", 0) or 0)
            tot_saldo  = float(resumo.get("total_saldo", 0) or 0)
            tot_gasto  = float(resumo.get("total_gasto", 0) or 0)
            ritmo_tot  = float(resumo.get("ritmo_diario_total", 0) or 0)

            txt_total_meta.value   = formatar_moeda(tot_meta)
            txt_total_saldo.value  = formatar_moeda(tot_saldo)
            txt_total_gasto.value  = formatar_moeda(tot_gasto)
            txt_ritmo_diario.value = f"{formatar_moeda(ritmo_tot)} / dia"

            renderizar_cards()
        except Exception as ex:
            import traceback
            print("[CaixinhasView] ERRO EM CARREGAR_DADOS:", ex)
            traceback.print_exc()
            err_str = str(ex)
            if "caixinhas_teto" in err_str or "PGRST205" in err_str or "schema cache" in err_str:
                banner_aviso_migracao.visible = True
            if not inicial:
                mostrar_feedback(page, f"Erro ao listar caixinhas: {ex}", "erro")
        finally:
            spinner.visible = False
            _safe_update()

    # ── Ação de Pagar Provisão e Encher o Cofrinho ─────────────────────────────
    def confirmar_pagamento_provisao(caixinha: dict):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "Caixinha")
        meta = float(caixinha.get("valor_meta", 0) or 0)
        tipo_prov = caixinha.get("provisao_tipo") or "Despesa"

        modal_conf = None

        def executar_pagamento(_):
            fechar_dialogo(page, modal_conf)
            try:
                db.pagar_provisao_caixinha(cid)
                mostrar_feedback(
                    page,
                    f"Provisão paga com sucesso! Cofrinho da caixinha '{nome}' cheio com {formatar_moeda(meta)}!",
                    "sucesso",
                )
                carregar_dados(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao efetivar provisão: {ex}", "erro")

        modal_conf = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text(f"Pagar Provisão · {nome}", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=400,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Text(
                            f"Deseja confirmar o pagamento da provisão de {formatar_moeda(meta)}?",
                            size=13,
                            color=T.TEXT_PRIMARY,
                        ),
                        ft.Container(
                            padding=pad(h=10, v=8),
                            bgcolor=f"{T.PRIMARY}12",
                            border_radius=8,
                            border=borda(1, f"{T.PRIMARY}30"),
                            content=ft.Row([
                                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=T.PRIMARY, size=16),
                                ft.Text(
                                    f"O valor será efetivado na sua conta bancária como {tipo_prov} Paga e o cofrinho encherá imediatamente com {formatar_moeda(meta)} para os gastos do período!",
                                    size=11,
                                    color=T.TEXT_PRIMARY,
                                    expand=True,
                                ),
                            ], spacing=8),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal_conf)),
                ft.FilledButton(
                    "Pagar Agora (Encher Caixinha)",
                    on_click=executar_pagamento,
                    style=ft.ButtonStyle(
                        bgcolor=T.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=pad(h=16, v=10),
                    ),
                ),
            ],
        )
        abrir_dialogo(page, modal_conf)

    # ── Modal de Aporte Adicional (Provisionar Mais Recursos) ──────────────────
    def abrir_modal_provisionar(caixinha: dict):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "Caixinha")
        meta = float(caixinha.get("valor_meta", 0) or 0)
        saldo_atual = float(caixinha.get("saldo_atual", 0) or 0)
        cor = caixinha.get("cor") or T.PRIMARY
        ic_nome = caixinha.get("icone", "inventory_2")
        icone_ctrl = MAPA_ICONES.get(ic_nome, ft.Icons.INVENTORY_2_ROUNDED)

        falta_meta = max(0.0, meta - saldo_atual)
        valor_sugerido = falta_meta if falta_meta > 0 else meta

        txt_valor = ft.TextField(
            label="Valor a Provisionar (R$) *",
            hint_text="Ex: 400,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=f"{valor_sugerido:.2f}".replace(".", ","),
            autofocus=True,
            **T.campo_estilo(),
        )

        hoje_data = date.today()
        estado_p = obter_estado_periodo_atual(page)
        mes_ativo = int(estado_p.get("mes") or hoje_data.month)
        ano_ativo = int(estado_p.get("ano") or hoje_data.year)
        _, u_dia_ativo = monthrange(ano_ativo, mes_ativo)
        dia_5_mes = date(ano_ativo, mes_ativo, min(5, u_dia_ativo))
        prox_m = 1 if mes_ativo == 12 else mes_ativo + 1
        prox_a = ano_ativo + (1 if mes_ativo == 12 else 0)
        dia_5_prox = date(prox_a, prox_m, 5)

        dt_sugerida_prov = dia_5_prox if dia_5_mes < hoje_data else dia_5_mes
        data_provisao_sel = [hoje_data if float(caixinha.get("saldo_atual", 0) or 0) > 0 else dt_sugerida_prov]

        txt_data_provisao_label = ft.Text(
            formatar_data_amigavel(data_provisao_sel[0]),
            size=12,
            weight=ft.FontWeight.W_600,
            color=T.TEXT_PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        def _ao_selecionar_data_provisao(nova_dt: date):
            data_provisao_sel[0] = nova_dt
            txt_data_provisao_label.value = formatar_data_amigavel(nova_dt)
            _atualizar_chips_atalhos_provisao()
            try:
                txt_data_provisao_label.update()
            except Exception:
                pass

        card_seletor_provisao = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=16),
                    padding=pad(all_=6),
                    bgcolor=f"{T.PRIMARY}18",
                    border_radius=8,
                ),
                ft.Column([
                    ft.Text("Data da Provisão *", size=10.5, color=T.TEXT_MUTED),
                    txt_data_provisao_label,
                ], spacing=1, expand=True),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=T.TEXT_MUTED, size=20),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=pad(h=10, v=8),
            bgcolor=T.SURFACE,
            border_radius=10,
            border=borda(1, T.BORDER),
            ink=True,
            on_click=lambda _: abrir_seletor_data_modal(
                page=page,
                data_inicial=data_provisao_sel[0],
                on_select=_ao_selecionar_data_provisao,
                titulo="Data da Provisão",
            ),
        )

        row_chips_atalhos_provisao = ft.Row(spacing=6, wrap=True)

        def _atualizar_chips_atalhos_provisao():
            row_chips_atalhos_provisao.controls.clear()
            opcoes_atalhos = []
            if dia_5_mes >= hoje_data:
                opcoes_atalhos.append((f"Dia 5 deste Mês ({mes_ativo:02d})", dia_5_mes))
            opcoes_atalhos.append(("Hoje", hoje_data))
            opcoes_atalhos.append((f"Próximo dia 5 ({prox_m:02d})", dia_5_prox))
            for lbl, dt_val in opcoes_atalhos:
                ativo = (data_provisao_sel[0] == dt_val)
                row_chips_atalhos_provisao.controls.append(
                    ft.Container(
                        content=ft.Text(
                            lbl,
                            size=10,
                            weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                            color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                        ),
                        padding=pad(h=8, v=3),
                        bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                        border_radius=12,
                        border=borda(1, T.PRIMARY if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, dt=dt_val: _ao_selecionar_data_provisao(dt),
                    )
                )
            try:
                row_chips_atalhos_provisao.update()
            except Exception:
                pass

        _atualizar_chips_atalhos_provisao()

        try:
            contas = db.listar_contas()
        except Exception:
            contas = []

        opcoes_contas = [ft.dropdown.Option(key=str(cta["id"]), text=cta.get("nome", "Conta")) for cta in contas]
        conta_id_padrao = str(caixinha.get("conta_id") or "")
        conta_sel_val = conta_id_padrao if any(opt.key == conta_id_padrao for opt in opcoes_contas) else (opcoes_contas[0].key if opcoes_contas else "")

        dd_conta = ft.Dropdown(
            label="Conta Bancária de Origem *",
            options=opcoes_contas,
            value=conta_sel_val,
            **T.dropdown_estilo(),
        )

        txt_desc = ft.TextField(
            label="Descrição / Observação (Opcional)",
            hint_text=f"Ex: Aporte adicional {nome}...",
            value=f"Aporte Caixinha · {nome}",
            **T.campo_estilo(),
        )

        modal = None

        def confirmar_provisao(_):
            val_str = txt_valor.value.replace(",", ".").replace("R$", "").strip()
            try:
                val = float(val_str or 0)
                if val <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
                return

            conta_escolhida = (dd_conta.value or "").strip()
            if not conta_escolhida:
                mostrar_feedback(page, "Selecione a conta bancária de onde sairá o dinheiro.", "alerta")
                return

            nome_conta = "Conta"
            for cta in contas:
                if str(cta.get("id")) == conta_escolhida:
                    nome_conta = cta.get("nome", "Conta")
                    break

            try:
                resp = db.injetar_saldo_caixinha(
                    caixinha_id=cid,
                    valor=val,
                    descricao=txt_desc.value.strip() or f"Provisionamento · {nome}",
                    conta_id=conta_escolhida,
                    data_aporte=data_provisao_sel[0].isoformat(),
                    gerar_despesa=True,
                )
                fechar_dialogo(page, modal)
                mostrar_feedback(
                    page,
                    f"R$ {val:.2f} provisionados na caixinha '{nome}' como despesa pendente na conta '{nome_conta}'!",
                    "sucesso",
                )
                carregar_dados(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao provisionar caixinha: {ex}", "erro")

        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text(f"Aporte na Caixinha · {nome}", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        txt_valor,
                        ft.Column([card_seletor_provisao, row_chips_atalhos_provisao], spacing=4),
                        dd_conta,
                        txt_desc,
                        ft.Container(
                            padding=pad(h=10, v=8),
                            bgcolor=f"{T.PRIMARY}12",
                            border_radius=8,
                            border=borda(1, f"{T.PRIMARY}30"),
                            content=ft.Row([
                                ft.Icon(ft.Icons.SCHEDULE_ROUNDED, color=T.PRIMARY, size=16),
                                ft.Text(
                                    "O valor entrará como Despesa Pendente na conta bancária (reserva de capital) sem abater o saldo real imediatamente, e ficará disponível na caixinha para os gastos do período.",
                                    size=11,
                                    color=T.TEXT_PRIMARY,
                                    expand=True,
                                ),
                            ], spacing=8),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal)),
                ft.FilledButton(
                    "Confirmar Aporte",
                    on_click=confirmar_provisao,
                    style=ft.ButtonStyle(
                        bgcolor=T.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=pad(h=16, v=10),
                    ),
                ),
            ],
        )
        abrir_dialogo(page, modal)

    # ── Modal de Deduzir Saldo (Consumo Manual sem Duplicidade Bancária) ─────────
    def abrir_modal_deduzir(caixinha: dict):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "Caixinha")
        saldo_atual = float(caixinha.get("saldo_atual", 0) or 0)

        txt_valor = ft.TextField(
            label="Valor Gasto (R$) *",
            hint_text="Ex: 50,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            autofocus=True,
            **T.campo_estilo(),
        )
        txt_desc = ft.TextField(
            label="Descrição do Gasto (Opcional)",
            hint_text="Ex: Abastecimento, compra rápida...",
            **T.campo_estilo(),
        )

        modal = None

        def confirmar_deducao(_):
            val_str = txt_valor.value.replace(",", ".").replace("R$", "").strip()
            try:
                val = float(val_str or 0)
                if val <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
                return

            try:
                resp = db.deduzir_saldo_caixinha(cid, val, txt_desc.value.strip())
                fechar_dialogo(page, modal)
                mostrar_feedback(page, f"R$ {val:.2f} deduzidos da caixinha '{nome}'!", "sucesso")
                carregar_dados(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao deduzir saldo: {ex}", "erro")

        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.MONEY_OFF_CSRED_ROUNDED, color=T.DESPESA, size=22),
                ft.Text(f"Deduzir Gasto · {nome}", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Text(f"Saldo atual disponível: {formatar_moeda(saldo_atual)}", color=T.TEXT_MUTED, size=12),
                        txt_valor,
                        txt_desc,
                        ft.Container(
                            padding=pad(h=10, v=6),
                            bgcolor=f"{T.SURFACE_ALT}",
                            border_radius=8,
                            content=ft.Row([
                                ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, color=T.TEXT_MUTED, size=14),
                                ft.Text(
                                    "Reduz o saldo da caixinha sem novo débito bancário (o valor já foi provisionado na entrada).",
                                    size=11,
                                    color=T.TEXT_MUTED,
                                    expand=True,
                                ),
                            ], spacing=6),
                        ),
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal)),
                ft.FilledButton(
                    "Registrar Gasto",
                    on_click=confirmar_deducao,
                    style=ft.ButtonStyle(bgcolor=T.DESPESA, shape=ft.RoundedRectangleBorder(radius=8)),
                ),
            ],
        )
        abrir_dialogo(page, modal)

    # ── Confirmar Exclusão ────────────────────────────────────────────────────
    def confirmar_exclusao(caixinha: dict):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "Caixinha")

        modal_confirma = None

        def executar_exclusao(_):
            fechar_dialogo(page, modal_confirma)
            try:
                db.deletar_caixinha(cid)
                mostrar_feedback(page, f"Caixinha '{nome}' excluída.", "sucesso")
                carregar_dados(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao excluir: {ex}", "erro")

        modal_confirma = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar Exclusão"),
            content=ft.Text(f"Deseja realmente remover a caixinha '{nome}'? O histórico será preservado no banco de dados."),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal_confirma)),
                ft.FilledButton(
                    "Excluir",
                    on_click=executar_exclusao,
                    style=ft.ButtonStyle(bgcolor=T.DESPESA, shape=ft.RoundedRectangleBorder(radius=8)),
                ),
            ],
        )
        abrir_dialogo(page, modal_confirma)

    # ── Modal de Cadastro / Edição com Agendamento de Provisão Pendente ────────
    def abrir_modal_caixinha(caixinha_edicao: dict | None = None):
        eh_edicao = caixinha_edicao is not None
        titulo_modal = "Editar Caixinha de Teto" if eh_edicao else "Nova Caixinha de Teto"

        hoje_data = date.today()
        estado_p = obter_estado_periodo_atual(page)
        mes_ativo = int(estado_p.get("mes") or hoje_data.month)
        ano_ativo = int(estado_p.get("ano") or hoje_data.year)
        _, u_dia = monthrange(ano_ativo, mes_ativo)
        dt_padrao_alvo = date(ano_ativo, mes_ativo, u_dia)

        dia_5_mes = date(ano_ativo, mes_ativo, min(5, u_dia))
        prox_m = 1 if mes_ativo == 12 else mes_ativo + 1
        prox_a = ano_ativo + (1 if mes_ativo == 12 else 0)
        dia_5_prox = date(prox_a, prox_m, 5)

        # Se o dia 5 do mês selecionado já passou em relação a hoje, o padrão inteligente é o Próximo dia 5 futuro
        dt_padrao_provisao = dia_5_prox if dia_5_mes < hoje_data else dia_5_mes

        # 1. Nome
        txt_nome = ft.TextField(
            label="Nome da Caixinha *",
            hint_text="Ex: Gasolina da Moto, Mercado, Lazer Semanal",
            value=caixinha_edicao.get("nome", "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        # 2. Meta / Teto
        txt_meta = ft.TextField(
            label="Valor do Teto / Meta (R$) *",
            hint_text="Ex: 400,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=str(caixinha_edicao.get("valor_meta", "")) if eh_edicao else "",
            **T.campo_estilo(),
        )

        # 3. Data de Provisão / Pagamento (Quando o dinheiro entra)
        if eh_edicao and caixinha_edicao.get("data_provisao"):
            try:
                dt_prov_ini = datetime.strptime(str(caixinha_edicao.get("data_provisao"))[:10], "%Y-%m-%d").date()
            except Exception:
                dt_prov_ini = dt_padrao_provisao
        else:
            dt_prov_ini = dt_padrao_provisao

        data_provisao_sel = [dt_prov_ini]

        txt_data_provisao_label = ft.Text(
            formatar_data_amigavel(data_provisao_sel[0]),
            size=12,
            weight=ft.FontWeight.W_600,
            color=T.TEXT_PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        def _ao_selecionar_data_provisao(nova_dt: date):
            data_provisao_sel[0] = nova_dt
            txt_data_provisao_label.value = formatar_data_amigavel(nova_dt)
            _atualizar_chips_atalhos_provisao()
            try:
                txt_data_provisao_label.update()
            except Exception:
                pass

        card_seletor_provisao = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=16),
                    padding=pad(all_=6),
                    bgcolor=f"{T.PRIMARY}18",
                    border_radius=8,
                ),
                ft.Column([
                    ft.Text("Data da Provisão (Dia do Pagamento) *", size=10.5, color=T.TEXT_MUTED),
                    txt_data_provisao_label,
                ], spacing=1, expand=True),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=T.TEXT_MUTED, size=20),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=pad(h=10, v=8),
            bgcolor=T.SURFACE,
            border_radius=10,
            border=borda(1, T.BORDER),
            ink=True,
            on_click=lambda _: abrir_seletor_data_modal(
                page=page,
                data_inicial=data_provisao_sel[0],
                on_select=_ao_selecionar_data_provisao,
                titulo="Data da Provisão / Pagamento",
            ),
            tooltip="Clique para escolher a data em que o dinheiro entra (ex: dia 5)",
        )

        row_chips_atalhos_provisao = ft.Row(spacing=6, wrap=True)

        def _atualizar_chips_atalhos_provisao():
            row_chips_atalhos_provisao.controls.clear()
            opcoes_atalhos = []
            if dia_5_mes >= hoje_data:
                opcoes_atalhos.append((f"Dia 5 deste Mês ({mes_ativo:02d})", dia_5_mes))
            opcoes_atalhos.append(("Hoje", hoje_data))
            opcoes_atalhos.append((f"Próximo dia 5 ({prox_m:02d})", dia_5_prox))
            opcoes_atalhos.append(("Fim do Mês", dt_padrao_alvo))
            for lbl, dt_val in opcoes_atalhos:
                ativo = (data_provisao_sel[0] == dt_val)
                row_chips_atalhos_provisao.controls.append(
                    ft.Container(
                        content=ft.Text(
                            lbl,
                            size=10,
                            weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                            color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                        ),
                        padding=pad(h=8, v=3),
                        bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                        border_radius=12,
                        border=borda(1, T.PRIMARY if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, dt=dt_val: _ao_selecionar_data_provisao(dt),
                    )
                )
            try:
                row_chips_atalhos_provisao.update()
            except Exception:
                pass

        _atualizar_chips_atalhos_provisao()

        # 4. Contas Bancárias (Origem e Destino opcional para Transferência)
        try:
            contas = db.listar_contas()
        except Exception:
            contas = []

        opcoes_contas_origem = []
        opcoes_contas_destino = [ft.dropdown.Option(key="", text="Mesma conta (Reserva / Despesa)")]

        for cta in contas:
            cid_cta = str(cta.get("id"))
            c_nome = cta.get("nome", "Conta")
            opcoes_contas_origem.append(ft.dropdown.Option(key=cid_cta, text=c_nome))
            opcoes_contas_destino.append(ft.dropdown.Option(key=cid_cta, text=f"Transferir para {c_nome}"))

        conta_id_ini = str(caixinha_edicao.get("conta_id") or "") if eh_edicao else ""
        if not conta_id_ini and opcoes_contas_origem:
            conta_id_ini = opcoes_contas_origem[0].key

        dd_conta_origem = ft.Dropdown(
            label="Conta Bancária de Origem *",
            options=opcoes_contas_origem,
            value=conta_id_ini,
            **T.dropdown_estilo(),
        )

        conta_dest_ini = str(caixinha_edicao.get("conta_destino_id") or "") if eh_edicao else ""
        dd_conta_destino = ft.Dropdown(
            label="Transferir para outra Conta? (Opcional)",
            options=opcoes_contas_destino,
            value=conta_dest_ini,
            **T.dropdown_estilo(),
        )

        # 5. Data Alvo / Fim do Período (Até quando o dinheiro deve durar)
        if eh_edicao and caixinha_edicao.get("data_alvo"):
            try:
                dt_alvo_inicial = datetime.strptime(str(caixinha_edicao.get("data_alvo"))[:10], "%Y-%m-%d").date()
            except Exception:
                dt_alvo_inicial = dt_padrao_alvo
        else:
            dt_alvo_inicial = dt_padrao_alvo

        data_alvo_sel = [dt_alvo_inicial]

        txt_data_alvo_label = ft.Text(
            formatar_data_amigavel(data_alvo_sel[0]),
            size=12,
            weight=ft.FontWeight.W_600,
            color=T.TEXT_PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )

        def _ao_selecionar_data_alvo(nova_dt: date):
            data_alvo_sel[0] = nova_dt
            txt_data_alvo_label.value = formatar_data_amigavel(nova_dt)
            _atualizar_chips_atalhos_alvo()
            try:
                txt_data_alvo_label.update()
            except Exception:
                pass

        card_seletor_alvo = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.FLAG_ROUNDED, color=T.INFO, size=16),
                    padding=pad(all_=6),
                    bgcolor=f"{T.INFO}18",
                    border_radius=8,
                ),
                ft.Column([
                    ft.Text("Data Alvo (Fim do Período) *", size=10.5, color=T.TEXT_MUTED),
                    txt_data_alvo_label,
                ], spacing=1, expand=True),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=T.TEXT_MUTED, size=20),
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=pad(h=10, v=8),
            bgcolor=T.SURFACE,
            border_radius=10,
            border=borda(1, T.BORDER),
            ink=True,
            on_click=lambda _: abrir_seletor_data_modal(
                page=page,
                data_inicial=data_alvo_sel[0],
                on_select=_ao_selecionar_data_alvo,
                titulo="Data Alvo / Fim do Período",
            ),
            tooltip="Clique para escolher até quando o dinheiro deve durar",
        )

        row_chips_atalhos_alvo = ft.Row(spacing=6, wrap=True)

        def _atualizar_chips_atalhos_alvo():
            row_chips_atalhos_alvo.controls.clear()
            opcoes_atalhos = [
                ("Fim deste Mês", dt_padrao_alvo),
                ("Próximo dia 5", date(hoje_data.year + (1 if hoje_data.month == 12 else 0), 1 if hoje_data.month == 12 else hoje_data.month + 1, 5)),
                ("+15 dias", hoje_data + timedelta(days=15)),
                ("+30 dias", hoje_data + timedelta(days=30)),
            ]
            for lbl, dt_val in opcoes_atalhos:
                ativo = (data_alvo_sel[0] == dt_val)
                row_chips_atalhos_alvo.controls.append(
                    ft.Container(
                        content=ft.Text(
                            lbl,
                            size=10,
                            weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                            color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                        ),
                        padding=pad(h=8, v=3),
                        bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                        border_radius=12,
                        border=borda(1, T.PRIMARY if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, dt=dt_val: _ao_selecionar_data_alvo(dt),
                    )
                )
            try:
                row_chips_atalhos_alvo.update()
            except Exception:
                pass

        _atualizar_chips_atalhos_alvo()

        # 6. Dropdown Obrigatório dos 6 Potes Financeiros
        try:
            potes = db.listar_potes()
        except Exception:
            potes = []

        opcoes_potes = []
        for pot in potes:
            pid = str(pot.get("id"))
            p_nome = pot.get("nome", "Pote")
            p_pct = pot.get("percentual", 0)
            opcoes_potes.append(ft.dropdown.Option(key=pid, text=f"{p_nome} ({p_pct}%)"))

        pote_sel_val = str(caixinha_edicao.get("pote_id") or "") if eh_edicao else (str(potes[0]["id"]) if potes else "")

        dd_pote = ft.Dropdown(
            label="Pote Financeiro (Obrigatório) *",
            options=opcoes_potes,
            value=pote_sel_val,
            **T.dropdown_estilo(),
        )

        # 7. Categoria e Subcategoria
        try:
            categorias = db.listar_categorias()
        except Exception:
            categorias = []

        cat_id_inicial = str(caixinha_edicao.get("categoria_id") or "") if eh_edicao else ""
        subcat_id_inicial = str(caixinha_edicao.get("subcategoria_id") or "") if eh_edicao else ""

        opcoes_cat = [ft.dropdown.Option(key="", text="Nenhuma (Geral)")]
        for cat in categorias:
            opcoes_cat.append(ft.dropdown.Option(key=str(cat.get("id")), text=cat.get("nome", "")))

        dd_subcategoria = ft.Dropdown(
            label="Subcategoria (Opcional)",
            options=[ft.dropdown.Option(key="", text="Nenhuma (Geral)")],
            value=subcat_id_inicial,
            **T.dropdown_estilo(),
        )

        def _carregar_opcoes_subcategoria(cat_id: str | None, valor_selecionado: str = ""):
            subcats = []
            if cat_id:
                try:
                    subcats = db.listar_subcategorias(cat_id)
                except Exception:
                    subcats = []
            opts = [ft.dropdown.Option(key="", text="Nenhuma (Geral)")]
            for s in subcats:
                opts.append(ft.dropdown.Option(key=str(s["id"]), text=s.get("nome", "")))
            dd_subcategoria.options = opts
            if any(opt.key == valor_selecionado for opt in opts):
                dd_subcategoria.value = valor_selecionado
            else:
                dd_subcategoria.value = ""
            try:
                dd_subcategoria.update()
            except Exception:
                pass

        def _ao_mudar_categoria(e):
            cat_escolhida = e.data or e.control.value
            _carregar_opcoes_subcategoria(cat_escolhida, "")

        dd_categoria = ft.Dropdown(
            label="Categoria (Opcional)",
            options=opcoes_cat,
            value=cat_id_inicial,
            on_select=_ao_mudar_categoria,
            **T.dropdown_estilo(),
        )

        if cat_id_inicial:
            _carregar_opcoes_subcategoria(cat_id_inicial, subcat_id_inicial)

        # 8. Cor e Ícone
        cor_selecionada = [caixinha_edicao.get("cor", CORES_CAIXINHAS[0]["hex"]) if eh_edicao else CORES_CAIXINHAS[0]["hex"]]
        icone_selecionado = [caixinha_edicao.get("icone", "inventory_2") if eh_edicao else "inventory_2"]

        def _selecionar_cor(h: str):
            cor_selecionada[0] = h
            for c_ctrl in row_cores.controls:
                c_ctrl.border = borda(2, ft.Colors.WHITE) if c_ctrl.data == h else borda(1, T.BORDER)
            row_cores.update()

        row_cores = ft.Row(
            spacing=8,
            wrap=True,
            controls=[
                ft.Container(
                    width=28,
                    height=28,
                    bgcolor=c["hex"],
                    border_radius=14,
                    data=c["hex"],
                    border=borda(2, ft.Colors.WHITE) if c["hex"] == cor_selecionada[0] else borda(1, T.BORDER),
                    tooltip=c["label"],
                    on_click=lambda _, h=c["hex"]: _selecionar_cor(h),
                )
                for c in CORES_CAIXINHAS
            ],
        )

        opcoes_icones = [
            ft.dropdown.Option(key=ic["nome"], text=ic["label"]) for ic in ICONES_OPCOES
        ]
        dd_icone = ft.Dropdown(
            label="Ícone Representativo",
            options=opcoes_icones,
            value=icone_selecionado[0],
            **T.dropdown_estilo(),
        )

        modal = None

        def salvar_caixinha(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da caixinha.", "alerta")
                return

            try:
                meta_num = float(txt_meta.value.replace(",", ".").replace("R$", "").strip() or 0)
                if meta_num <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um teto/meta válido maior que zero.", "alerta")
                return

            pote_id = (dd_pote.value or "").strip()
            if not pote_id:
                mostrar_feedback(page, "Selecione obrigatoriamente o Pote ao qual esta caixinha pertence.", "alerta")
                return

            c_origem = (dd_conta_origem.value or "").strip()
            if not c_origem:
                mostrar_feedback(page, "Selecione a conta bancária de origem da provisão.", "alerta")
                return

            c_destino = (dd_conta_destino.value or "").strip() or None
            dt_prov_str = data_provisao_sel[0].isoformat()
            dt_alvo_str = data_alvo_sel[0].isoformat()

            dados = {
                "nome": nome,
                "valor_meta": meta_num,
                "data_provisao": dt_prov_str,
                "data_alvo": dt_alvo_str,
                "conta_id": c_origem,
                "conta_destino_id": c_destino,
                "tipo_provisao": "transferencia" if (c_destino and c_destino != c_origem) else "despesa",
                "recorrente": sw_recorrente.value,
                "dia_recorrencia": data_provisao_sel[0].day,
                "cor": cor_selecionada[0],
                "icone": dd_icone.value or "inventory_2",
                "pote_id": pote_id,
                "categoria_id": dd_categoria.value or None,
                "subcategoria_id": dd_subcategoria.value or None,
                "ativo": True,
            }

            try:
                if eh_edicao:
                    db.atualizar_caixinha(caixinha_edicao["id"], dados)
                    msg = "Caixinha atualizada com sucesso!"
                else:
                    db.criar_caixinha(dados)
                    tipo_desc = "Transferência" if (c_destino and c_destino != c_origem) else "Despesa"
                    msg = (
                        f"Caixinha '{nome}' criada! {tipo_desc} pendente de {formatar_moeda(meta_num)} "
                        f"agendada para {formatar_data_br(data_provisao_sel[0])}. Quando você pagar, o cofrinho encherá!"
                    )

                fechar_dialogo(page, modal)
                mostrar_feedback(page, msg, "sucesso")
                carregar_dados(inicial=False, forcar=True)
            except Exception as ex:
                err_msg = str(ex)
                mostrar_feedback(page, f"Erro ao salvar caixinha: {err_msg}", "erro")

        sw_recorrente = ft.Switch(
            value=bool(caixinha_edicao.get("recorrente", True)) if eh_edicao else True,
            active_color=T.PRIMARY,
        )

        card_recorrente = ft.Container(
            col={"xs": 12},
            padding=pad(h=12, v=10),
            bgcolor=T.SURFACE,
            border_radius=10,
            border=borda(1, T.BORDER),
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.AUTORENEW_ROUNDED, color=T.PRIMARY, size=20),
                    padding=pad(all_=6),
                    bgcolor=f"{T.PRIMARY}18",
                    border_radius=8,
                ),
                ft.Column([
                    ft.Text("Recorrência Mensal (Repetir todo mês)", size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                    ft.Text(
                        "Gera automaticamente a provisão pendente em todos os meses futuros (ex: todo dia 5), "
                        "mantendo este valor reservado na previsão de despesas pendentes de cada mês.",
                        size=11,
                        color=T.TEXT_MUTED,
                    ),
                ], spacing=2, expand=True),
                sw_recorrente,
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
        )

        controles_modal = [
            ft.Container(content=txt_nome, col={"xs": 12}),
            ft.Container(content=txt_meta, col={"xs": 12, "sm": 6}),
            ft.Container(content=dd_pote, col={"xs": 12, "sm": 6}),
            ft.Container(
                col={"xs": 12, "sm": 6},
                content=ft.Column([
                    card_seletor_provisao,
                    row_chips_atalhos_provisao,
                ], spacing=4),
            ),
            ft.Container(
                col={"xs": 12, "sm": 6},
                content=ft.Column([
                    card_seletor_alvo,
                    row_chips_atalhos_alvo,
                ], spacing=4),
            ),
            ft.Container(content=dd_conta_origem, col={"xs": 12, "sm": 6}),
            ft.Container(content=dd_conta_destino, col={"xs": 12, "sm": 6}),
            ft.Container(content=dd_categoria, col={"xs": 12, "sm": 6}),
            ft.Container(content=dd_subcategoria, col={"xs": 12, "sm": 6}),
            ft.Container(content=dd_icone, col={"xs": 12, "sm": 6}),
            ft.Container(
                col={"xs": 12, "sm": 6},
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Text("Cor de Identificação", size=11.5, color=T.TEXT_MUTED),
                        row_cores,
                    ],
                ),
            ),
            card_recorrente,
            ft.Container(
                col={"xs": 12},
                padding=pad(h=12, v=10),
                bgcolor=f"{T.INFO}12",
                border_radius=10,
                border=borda(1, f"{T.INFO}35"),
                content=ft.Row([
                    ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.INFO, size=20),
                    ft.Column([
                        ft.Text("Agendamento de Provisão Pendente", size=12, weight=ft.FontWeight.BOLD, color=T.INFO),
                        ft.Text(
                            "Ao salvar, o sistema agenda a Despesa PENDENTE para o dia da provisão. "
                            "A caixinha nasce com R$ 0,00 e encherá automaticamente com o valor total quando o pagamento for realizado!",
                            size=11,
                            color=T.TEXT_PRIMARY,
                        ),
                    ], spacing=2, expand=True),
                ], spacing=10),
            ),
        ]

        grid_modal = ft.ResponsiveRow(
            spacing=10,
            run_spacing=10,
            controls=controles_modal,
        )

        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text(titulo_modal, size=17, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=520,
                content=ft.Column([grid_modal], tight=True, scroll=ft.ScrollMode.AUTO),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal)),
                ft.FilledButton(
                    "Salvar Caixinha",
                    on_click=salvar_caixinha,
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=18, v=10)),
                ),
            ],
        )
        abrir_dialogo(page, modal)

    # ── Renderizar Lista de Caixinhas ─────────────────────────────────────────
    def renderizar_cards():
        grid_caixinhas.controls.clear()

        if not caixinhas_lista:
            grid_caixinhas.controls.append(
                ft.Container(
                    col={"xs": 12},
                    padding=pad(all_=36),
                    bgcolor=T.SURFACE,
                    border_radius=16,
                    border=borda(),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, size=52, color=T.TEXT_MUTED),
                            ft.Text("Nenhuma Caixinha de Teto Criada", size=18, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(
                                "Crie caixinhas para reservar verbas do seu salário (ex: Moto, Mercado, Lazer).\n"
                                "O sistema agenda a provisão pendente para a data que você escolher (ex: dia 5). "
                                "Ao pagar, o cofrinho enche e você acompanha os gastos diários em tempo real!",
                                color=T.TEXT_MUTED,
                                size=13,
                                text_align=ft.TextAlign.CENTER,
                            ),
                            ft.Container(height=8),
                            ft.FilledButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.ADD_ROUNDED, size=18, color=T.ON_NEON),
                                    ft.Text("Criar Primeira Caixinha", weight=ft.FontWeight.BOLD, color=T.ON_NEON),
                                ], spacing=6, tight=True),
                                on_click=lambda _: abrir_modal_caixinha(),
                                style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=10), padding=pad(h=20, v=12)),
                            ),
                        ],
                    ),
                )
            )
            return

        hoje_data = date.today()

        for c in caixinhas_lista:
            cid = str(c.get("id"))
            nome = c.get("nome", "Caixinha")
            cor = c.get("cor") or "#10B981"
            meta = float(c.get("valor_meta", 0) or 0)
            saldo = float(c.get("saldo_atual", 0) or 0)
            gasto = float(c.get("total_gasto", 0) or 0)
            pct = min(1.0, max(0.0, saldo / meta)) if meta > 0 else 0.0

            # Informações dos vínculos
            pote_info = c.get("potes")
            pote_nome = pote_info.get("nome") if isinstance(pote_info, dict) else None
            pote_cor = pote_info.get("cor") if isinstance(pote_info, dict) else T.PRIMARY

            conta_info = c.get("contas")
            conta_nome = conta_info.get("nome") if isinstance(conta_info, dict) else None

            conta_dest_info = c.get("conta_destino")
            conta_dest_nome = conta_dest_info.get("nome") if isinstance(conta_dest_info, dict) else None

            cat_info = c.get("categorias")
            cat_nome = cat_info.get("nome") if isinstance(cat_info, dict) else None

            subcat_info = c.get("subcategorias")
            subcat_nome = subcat_info.get("nome") if isinstance(subcat_info, dict) else None

            # Data de provisão e data alvo
            dt_prov_raw = c.get("provisao_data") or c.get("data_provisao")
            tipo_prov = c.get("provisao_tipo") or c.get("tipo_provisao") or "Despesa"
            eh_pendente = (saldo <= 0)

            dt_alvo_raw = c.get("data_alvo")
            dias_rest = 0
            ritmo_dia = 0.0
            texto_ritmo = "Sem data alvo definida"

            if dt_alvo_raw:
                try:
                    d_alvo = datetime.strptime(str(dt_alvo_raw)[:10], "%Y-%m-%d").date()
                    diff = (d_alvo - hoje_data).days
                    if diff >= 0:
                        dias_rest = diff + 1
                        if saldo > 0:
                            ritmo_dia = (saldo / dias_rest)
                            texto_ritmo = f"{dias_rest} dia{'s' if dias_rest > 1 else ''} restantes · {formatar_moeda(ritmo_dia)} / dia seguro"
                        else:
                            texto_ritmo = f"Provisão agendada · Aguardando pagamento para encher cofrinho"
                    else:
                        texto_ritmo = "Ciclo encerrado · Prazo atingido"
                except Exception:
                    pass

            # Estado visual: Vazia (Pendente) vs Com Saldo (Cheia/Em uso)
            if saldo <= 0:
                cor_barra = f"{T.WARNING}40"
                if dt_prov_raw:
                    try:
                        d_prov = datetime.strptime(str(dt_prov_raw)[:10], "%Y-%m-%d").date()
                        status_texto = f"Pendente ({d_prov.strftime('%d/%m')})"
                    except Exception:
                        status_texto = "Aguardando Pagamento"
                else:
                    status_texto = "Aguardando Pagamento"

                cor_badge_bg = f"{T.WARNING}20"
                cor_badge_txt = T.WARNING
                tipo_rotulo = "Transferência" if conta_dest_nome else "Provisão"
                texto_sub_saldo = f"{tipo_rotulo} de {formatar_moeda(meta)} agendada · Pendente"
            elif pct >= 0.50:
                cor_barra = T.PRIMARY
                status_texto = f"{pct * 100:.0f}% restante"
                cor_badge_bg = f"{T.PRIMARY}20"
                cor_badge_txt = T.PRIMARY
                texto_sub_saldo = f"De {formatar_moeda(meta)} provisionado · Consumido: {formatar_moeda(gasto)}"
            elif pct >= 0.20:
                cor_barra = T.WARNING
                status_texto = f"{pct * 100:.0f}% restante"
                cor_badge_bg = f"{T.WARNING}20"
                cor_badge_txt = T.WARNING
                texto_sub_saldo = f"De {formatar_moeda(meta)} provisionado · Consumido: {formatar_moeda(gasto)}"
            else:
                cor_barra = T.DESPESA
                status_texto = "Nível Crítico"
                cor_badge_bg = f"{T.DESPESA}20"
                cor_badge_txt = T.DESPESA
                texto_sub_saldo = f"De {formatar_moeda(meta)} provisionado · Consumido: {formatar_moeda(gasto)}"

            # Ícone personalizado ou padrão
            ic_nome = c.get("icone", "inventory_2")
            icone_ctrl = MAPA_ICONES.get(ic_nome, ft.Icons.INVENTORY_2_ROUNDED)

            # Chips de Metadados (Pote, Categoria, Banco Origem/Destino)
            row_badges_vinculo = ft.Row(spacing=5, wrap=True)
            if pote_nome:
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PIE_CHART_OUTLINE_ROUNDED, size=11, color=pote_cor),
                            ft.Text(pote_nome, size=10, weight=ft.FontWeight.W_600, color=pote_cor),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=f"{pote_cor}18",
                        border_radius=6,
                        border=borda(1, f"{pote_cor}35"),
                    )
                )

            # Recorrência Mensal
            if c.get("recorrente"):
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=11, color=T.PRIMARY),
                            ft.Text("Mensal", size=10, weight=ft.FontWeight.W_600, color=T.PRIMARY),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=f"{T.PRIMARY}18",
                        border_radius=6,
                        border=borda(1, f"{T.PRIMARY}35"),
                        tooltip="Recorrência Mensal ativa (provisão gerada todo mês)",
                    )
                )

            # Categoria / Subcategoria
            rotulo_cat_sub = None
            if cat_nome and subcat_nome:
                rotulo_cat_sub = f"{cat_nome} › {subcat_nome}"
            elif cat_nome:
                rotulo_cat_sub = cat_nome
            elif subcat_nome:
                rotulo_cat_sub = subcat_nome

            if rotulo_cat_sub:
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.LABEL_OUTLINE_ROUNDED, size=11, color=T.TEXT_MUTED),
                            ft.Text(rotulo_cat_sub, size=10, weight=ft.FontWeight.W_500, color=T.TEXT_MUTED),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        border=borda(1, T.BORDER),
                    )
                )

            # Contas
            if conta_nome and conta_dest_nome:
                rotulo_contas = f"{conta_nome} → {conta_dest_nome}"
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SYNC_ALT_ROUNDED, size=11, color=T.PRIMARY),
                            ft.Text(rotulo_contas, size=10, weight=ft.FontWeight.W_500, color=T.TEXT_PRIMARY),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        border=borda(1, T.BORDER),
                    )
                )
            elif conta_nome:
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ACCOUNT_BALANCE_ROUNDED, size=11, color=T.TEXT_MUTED),
                            ft.Text(conta_nome, size=10, weight=ft.FontWeight.W_500, color=T.TEXT_MUTED),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        border=borda(1, T.BORDER),
                    )
                )

            # Botões de Ação na base do card
            if saldo <= 0:
                # Destaque de largura total para pagar a provisão e encher o cofrinho
                botoes_acao_card = ft.FilledButton(
                    content=ft.Row([
                        ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=16, color=T.ON_NEON),
                        ft.Text("Pagar Provisão e Encher Caixinha", size=12.5, weight=ft.FontWeight.BOLD, color=T.ON_NEON),
                    ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                    on_click=lambda _, it=c: confirmar_pagamento_provisao(it),
                    style=ft.ButtonStyle(
                        bgcolor=T.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=pad(v=10),
                    ),
                )
            else:
                # Ações lado a lado: Aportar mais ou Gastar
                botoes_acao_card = ft.Row(
                    spacing=8,
                    controls=[
                        ft.Container(
                            expand=True,
                            content=ft.FilledButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=T.PRIMARY),
                                    ft.Text("Aportar", size=12, weight=ft.FontWeight.W_600, color=T.PRIMARY),
                                ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                                on_click=lambda _, it=c: abrir_modal_provisionar(it),
                                style=ft.ButtonStyle(
                                    bgcolor=f"{T.PRIMARY}18",
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=pad(v=8),
                                ),
                            ),
                        ),
                        ft.Container(
                            expand=True,
                            content=ft.FilledButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.REMOVE_ROUNDED, size=15, color=T.DESPESA),
                                    ft.Text("Gastar", size=12, weight=ft.FontWeight.W_600, color=T.DESPESA),
                                ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                                on_click=lambda _, it=c: abrir_modal_deduzir(it),
                                style=ft.ButtonStyle(
                                    bgcolor=f"{T.DESPESA}18",
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=pad(v=8),
                                ),
                            ),
                        ),
                    ],
                )

            # Card Individual da Caixinha
            card_caixinha = ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=16),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(1.2, f"{cor}40" if pct > 0 else T.BORDER),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        # 1. Header do Card (Ícone + Nome + Badges de Pote/Categoria + Menu)
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.START,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        ft.Container(
                                            content=ft.Icon(icone_ctrl, color=cor, size=20),
                                            bgcolor=f"{cor}1A",
                                            border_radius=10,
                                            padding=pad(all_=8),
                                        ),
                                        ft.Column(
                                            spacing=3,
                                            tight=True,
                                            controls=[
                                                ft.Text(nome, size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                                row_badges_vinculo,
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=4,
                                    controls=[
                                        ft.Container(
                                            content=ft.Text(status_texto, size=10.5, weight=ft.FontWeight.BOLD, color=cor_badge_txt),
                                            bgcolor=cor_badge_bg,
                                            padding=pad(h=8, v=3),
                                            border_radius=8,
                                        ),
                                        ft.PopupMenuButton(
                                            icon=ft.Icons.MORE_VERT_ROUNDED,
                                            icon_size=18,
                                            items=[
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=15, color=T.PRIMARY),
                                                        ft.Text("Pagar e Encher Caixinha" if saldo <= 0 else "Aportar Mais", size=13, color=T.PRIMARY),
                                                    ], spacing=8),
                                                    on_click=lambda _, it=c: confirmar_pagamento_provisao(it) if float(it.get("saldo_atual", 0) or 0) <= 0 else abrir_modal_provisionar(it),
                                                ),
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.REMOVE_ROUNDED, size=15, color=T.DESPESA),
                                                        ft.Text("Gastar / Deduzir", size=13, color=T.DESPESA),
                                                    ], spacing=8),
                                                    on_click=lambda _, it=c: abrir_modal_deduzir(it),
                                                ),
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.EDIT_ROUNDED, size=15),
                                                        ft.Text("Editar Caixinha", size=13),
                                                    ], spacing=8),
                                                    on_click=lambda _, it=c: abrir_modal_caixinha(it),
                                                ),
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.DELETE_OUTLINE_ROUNDED, size=15, color=T.DESPESA),
                                                        ft.Text("Excluir", size=13, color=T.DESPESA),
                                                    ], spacing=8),
                                                    on_click=lambda _, it=c: confirmar_exclusao(it),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),

                        # 2. Saldo e Teto Alocado
                        ft.Column(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Text(
                                    formatar_moeda(saldo),
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                    color=T.TEXT_PRIMARY if saldo > 0 else T.TEXT_MUTED,
                                ),
                                ft.Text(
                                    texto_sub_saldo,
                                    size=11.5,
                                    color=T.TEXT_MUTED,
                                ),
                            ],
                        ),

                        # 3. Barra de Progresso Dinâmica
                        ft.ProgressBar(
                            value=pct,
                            color=cor_barra,
                            bgcolor="#FFFFFF12",
                            height=7,
                            border_radius=4,
                        ),

                        # 4. Indicador de Ritmo Seguro (Burn Rate)
                        ft.Container(
                            padding=pad(h=10, v=6),
                            bgcolor="#FFFFFF08",
                            border_radius=8,
                            content=ft.Row(
                                spacing=6,
                                controls=[
                                    ft.Icon(ft.Icons.SPEED_ROUNDED, size=15, color=T.INFO if saldo > 0 else T.TEXT_MUTED),
                                    ft.Text(texto_ritmo, size=11, color=T.TEXT_PRIMARY if saldo > 0 else T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                                ],
                            ),
                        ),

                        # 5. Ações da Caixinha
                        botoes_acao_card,
                    ],
                ),
            )
            grid_caixinhas.controls.append(card_caixinha)

        _safe_update()

    # ── KPIs Resumo no Topo ───────────────────────────────────────────────────
    strip_kpis = ft.ResponsiveRow(
        spacing=8 if mobile else 12,
        run_spacing=8 if mobile else 12,
        controls=[
            kpi_clicavel(
                titulo="Total dos Tetos",
                valor_control=txt_total_meta,
                subtitulo="Soma das metas",
                icone=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                cor=T.TEXT_PRIMARY,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
            kpi_clicavel(
                titulo="Saldo Disponível",
                valor_control=txt_total_saldo,
                subtitulo="Verba alocada restante",
                icone=ft.Icons.SAVINGS_ROUNDED,
                cor=T.PRIMARY,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
            kpi_clicavel(
                titulo="Total Consumido",
                valor_control=txt_total_gasto,
                subtitulo="Gastos vinculados",
                icone=ft.Icons.SHOPPING_BAG_ROUNDED,
                cor=T.WARNING,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
            kpi_clicavel(
                titulo="Ritmo Diário Seguro",
                valor_control=txt_ritmo_diario,
                subtitulo="Média recomendada",
                icone=ft.Icons.SPEED_ROUNDED,
                cor=T.INFO,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
        ],
    )

    # ── Header da Página ──────────────────────────────────────────────────────
    btn_nova = ft.FilledButton(
        content=ft.Row([
            ft.Icon(ft.Icons.ADD_ROUNDED, size=18, color=T.ON_NEON),
            ft.Text("Nova Caixinha", size=13, weight=ft.FontWeight.BOLD, color=T.ON_NEON),
        ], spacing=6, tight=True),
        on_click=lambda _: abrir_modal_caixinha(),
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=14 if mobile else 16, v=10),
        ),
    )

    header_view = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=2,
                tight=True,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color=T.PRIMARY, size=24),
                        ft.Text("Caixinhas de Teto", size=20 if mobile else 24, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                    ], spacing=8),
                    ft.Text(
                        "Metas de gastos, provisionamento e cálculo de ritmo até o próximo mês" if not mobile else "Provisionamento e ritmo de gastos",
                        color=T.TEXT_MUTED,
                        size=12 if mobile else 13,
                    ),
                ],
            ),
            ft.Row([spinner, btn_nova], spacing=10),
        ],
    )

    # ── Layout da View ────────────────────────────────────────────────────────
    conteudo = ft.Column(
        spacing=18,
        controls=[
            header_view,
            banner_aviso_migracao,
            strip_kpis,
            ft.Divider(height=1, color=T.BORDER),
            grid_caixinhas,
            ft.Container(height=30),
        ],
    )

    carregar_dados(inicial=True)

    return conteudo


def criar_view_caixinhas(page: ft.Page, match=None) -> ft.View:
    conteudo = montar_aba_caixinhas(page, match)
    return criar_shell(
        page,
        rota_ativa=ROTA_CAIXINHAS,
        conteudo=conteudo,
        rota_view="/caixinhas",
        titulo="Caixinhas de Teto",
        mostrar_voltar=False,
    )
