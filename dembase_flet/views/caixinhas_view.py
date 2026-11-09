"""
=============================================================================
DemBase v3 — views/caixinhas_view.py  (Flet 1.0.1)
Módulo DemBoxes (Provisões do Mês & Quitação de Dívidas / Acumulação).
- Dois Modos Operacionais Inteligentes na Mesma Tela:
  1) 📦 Provisão do Mês (Consumo Mensal — Ex: Moto, Aluguel, Mercado):
     Controla teto mensal, % restante e ritmo diário seguro (R$ / dia).
  2) 🎯 Quitar Dívida / Juntar (Acumulação Contínua — Ex: Dívida com a Chefe, Acordo):
     Saldo cumulativo que atravessa os meses sem zerar na virada do mês.
     Destaca Quanto Já Guardei vs. Valor Total da Dívida, Quanto Falta Guardar
     (barra de conquista de 0% a 100%), e botões + Guardar Dinheiro e ✓ Pagar / Abater Dívida.
- Raio-X ao Clicar no Card:
  Abre visão detalhada com todo o histórico cronológico de depósitos (+ Guardado)
  e saídas (✓ Abatimentos / Gastos), evolução e saldo na ponta do lápis.
- Modal de Criação 1-Clique (Zero Dropdowns):
  Seletor de propósito no topo, sugestões inteligentes, pílulas para os 6 Potes,
  Perfil Familiar, Conta Bancária, Ícone e Cor em 1 toque.
=============================================================================
"""
from __future__ import annotations

import asyncio
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
    {"hex": "#F59E0B", "label": "Âmbar / Alerta"},
    {"hex": "#EC4899", "label": "Rosa Vibrante"},
    {"hex": "#06B6D4", "label": "Ciano Moderno"},
    {"hex": "#6366F1", "label": "Índigo"},
    {"hex": "#14B8A6", "label": "Teal"},
]

ICONES_OPCOES = [
    {"nome": "two_wheeler",       "icone": ft.Icons.TWO_WHEELER_ROUNDED,       "label": "Moto"},
    {"nome": "home",              "icone": ft.Icons.HOME_ROUNDED,              "label": "Casa / Aluguel"},
    {"nome": "person",            "icone": ft.Icons.PERSON_ROUNDED,            "label": "Pessoa / Chefe"},
    {"nome": "handshake",         "icone": ft.Icons.HANDSHAKE_ROUNDED,         "label": "Acordo / Dívida"},
    {"nome": "warning",           "icone": ft.Icons.WARNING_AMBER_ROUNDED,     "label": "Alerta / Urgente"},
    {"nome": "directions_car",    "icone": ft.Icons.DIRECTIONS_CAR_ROUNDED,    "label": "Carro"},
    {"nome": "credit_card",       "icone": ft.Icons.CREDIT_CARD_ROUNDED,       "label": "Cartão"},
    {"nome": "shopping_cart",     "icone": ft.Icons.SHOPPING_CART_ROUNDED,     "label": "Mercado"},
    {"nome": "local_gas_station", "icone": ft.Icons.LOCAL_GAS_STATION_ROUNDED, "label": "Combustível"},
    {"nome": "local_pharmacy",    "icone": ft.Icons.LOCAL_PHARMACY_ROUNDED,    "label": "Saúde"},
    {"nome": "celebration",       "icone": ft.Icons.CELEBRATION_ROUNDED,       "label": "Lazer"},
    {"nome": "savings",           "icone": ft.Icons.SAVINGS_ROUNDED,           "label": "Cofre / Reserva"},
    {"nome": "flag",              "icone": ft.Icons.FLAG_ROUNDED,              "label": "Alvo / Meta"},
    {"nome": "inventory_2",       "icone": ft.Icons.INVENTORY_2_ROUNDED,       "label": "DemBox"},
]

MAPA_ICONES = {item["nome"]: item["icone"] for item in ICONES_OPCOES}

SUGESTOES_PROVISAO = [
    {"nome": "Moto",              "icone": "two_wheeler",       "cor": "#10B981", "pote_hint": "Custos Semi Fixos"},
    {"nome": "Aluguel",           "icone": "home",              "cor": "#3B82F6", "pote_hint": "Custos Fixos"},
    {"nome": "Mercado",           "icone": "shopping_cart",     "cor": "#F59E0B", "pote_hint": "Custos Semi Fixos"},
    {"nome": "Combustível",       "icone": "local_gas_station", "cor": "#06B6D4", "pote_hint": "Custos Semi Fixos"},
    {"nome": "Lazer do Mês",      "icone": "celebration",       "cor": "#EC4899", "pote_hint": "Prazeres"},
    {"nome": "Farmácia & Saúde",  "icone": "local_pharmacy",    "cor": "#14B8A6", "pote_hint": "Custos Semi Fixos"},
]

SUGESTOES_DIVIDA = [
    {"nome": "Dívida com a Chefe",   "icone": "person",         "cor": "#F59E0B", "pote_hint": "Metas"},
    {"nome": "Acordo / Empréstimo",  "icone": "handshake",      "cor": "#8B5CF6", "pote_hint": "Metas"},
    {"nome": "Quitar Cartão",        "icone": "credit_card",    "cor": "#EC4899", "pote_hint": "Liberdade Financeira"},
    {"nome": "Empréstimo Familiar",  "icone": "person",         "cor": "#06B6D4", "pote_hint": "Metas"},
    {"nome": "Quitar Financiamento", "icone": "directions_car", "cor": "#3B82F6", "pote_hint": "Custos Fixos"},
    {"nome": "Objetivo / Conquista", "icone": "flag",           "cor": "#10B981", "pote_hint": "Metas"},
]


def _eh_modo_divida(caixinha: dict) -> bool:
    return str(caixinha.get("modalidade") or "provisao_mensal").strip().lower() in ("divida", "quitacao")


def montar_aba_caixinhas(page: ft.Page, match=None) -> ft.Control:
    mobile = is_mobile(page)
    caixinhas_lista: list[dict] = []
    filtro_aba_atual = ["todos"]  # "todos" | "provisao_mensal" | "divida"

    # ── Controles de KPIs do Topo ─────────────────────────────────────────────
    tam_kpi = 15 if mobile else 18
    txt_total_meta   = ft.Text("R$ 0,00", color=T.TEXT_PRIMARY, size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_saldo  = ft.Text("R$ 0,00", color=T.PRIMARY,      size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_gasto  = ft.Text("R$ 0,00", color=T.WARNING,      size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_ritmo_diario = ft.Text("R$ 0,00 / dia", color=T.INFO,   size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)

    grid_caixinhas = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])
    row_filtros_modo = ft.Row(spacing=8, wrap=True)
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    banner_aviso_migracao = ft.Container(
        visible=False,
        bgcolor=T.SURFACE_ALT,
        border=borda(1, T.WARNING),
        border_radius=12,
        padding=pad(h=14, v=10),
        content=ft.Row([
            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=T.WARNING, size=24),
            ft.Column([
                ft.Text("Tabela 'caixinhas_teto' não encontrada no banco de dados!", size=13, weight=ft.FontWeight.BOLD, color=T.WARNING),
                ft.Text(
                    "Para ativar o módulo DemBoxes, execute o arquivo migrations/016_create_caixinhas_teto.sql no Supabase.",
                    size=11.5,
                    color=T.TEXT_PRIMARY,
                ),
            ], spacing=2, expand=True),
        ], spacing=10, vertical_alignment=ft.CrossAxisAlignment.CENTER),
    )

    def _safe_update():
        for ctrl in (txt_total_meta, txt_total_saldo, txt_total_gasto, txt_ritmo_diario, row_filtros_modo, grid_caixinhas, banner_aviso_migracao):
            try:
                ctrl.update()
            except Exception:
                pass
        try:
            page.update()
        except Exception:
            pass

    def _atualizar_kpis_e_abas():
        provisoes = [c for c in caixinhas_lista if not _eh_modo_divida(c)]
        dividas = [c for c in caixinhas_lista if _eh_modo_divida(c)]

        aba = filtro_aba_atual[0]
        if aba == "divida":
            itens_kpi = dividas
            tot_meta = sum(float(c.get("valor_meta", 0) or 0) for c in itens_kpi)
            tot_guardado = sum(float(c.get("total_guardado", c.get("saldo_atual", 0)) or 0) for c in itens_kpi)
            tot_abatido = sum(float(c.get("total_abatido", 0) or 0) for c in itens_kpi)
            tot_falta = sum(float(c.get("falta_guardar", max(0.0, float(c.get("valor_meta", 0) or 0) - float(c.get("total_guardado", 0) or 0))) or 0) for c in itens_kpi)
            txt_total_meta.value = formatar_moeda(tot_meta)
            txt_total_saldo.value = formatar_moeda(tot_guardado)
            txt_total_gasto.value = formatar_moeda(tot_abatido)
            txt_ritmo_diario.value = f"Falta {formatar_moeda(tot_falta)}"
        else:
            itens_kpi = provisoes if aba == "provisao_mensal" else caixinhas_lista
            tot_meta = sum(float(c.get("valor_provisionado_periodo", c.get("valor_meta", 0)) or 0) for c in itens_kpi)
            tot_saldo = sum(float(c.get("saldo_atual", 0) or 0) for c in itens_kpi)
            tot_gasto = sum(float(c.get("total_gasto", 0) or 0) for c in itens_kpi)

            hoje = date.today()
            ritmo_tot = 0.0
            for c in provisoes:
                s = float(c.get("saldo_atual", 0) or 0)
                dt_str = c.get("data_alvo")
                if dt_str and s > 0:
                    try:
                        d_alvo = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d").date()
                        dias = max(1, (d_alvo - hoje).days + 1)
                        ritmo_tot += (s / dias)
                    except Exception:
                        pass

            txt_total_meta.value = formatar_moeda(tot_meta)
            txt_total_saldo.value = formatar_moeda(tot_saldo)
            txt_total_gasto.value = formatar_moeda(tot_gasto)
            if dividas and aba == "todos" and ritmo_tot <= 0:
                tot_falta_div = sum(float(c.get("falta_guardar", 0) or 0) for c in dividas)
                txt_ritmo_diario.value = f"Falta {formatar_moeda(tot_falta_div)}"
            else:
                txt_ritmo_diario.value = f"{formatar_moeda(ritmo_tot)} / dia"

        # Abas de filtro rápido (1 clique)
        row_filtros_modo.controls.clear()
        opcoes_abas = [
            ("todos",           f"Todos ({len(caixinhas_lista)})",                  ft.Icons.APPS_ROUNDED,        T.PRIMARY),
            ("provisao_mensal", f"Provisões do Mês ({len(provisoes)})",             ft.Icons.INVENTORY_2_ROUNDED, "#10B981"),
            ("divida",          f"Dívidas & Quitações ({len(dividas)})",            ft.Icons.TRACK_CHANGES_ROUNDED, "#F59E0B"),
        ]
        for chave_aba, rotulo_aba, icone_aba, cor_aba in opcoes_abas:
            ativo = (filtro_aba_atual[0] == chave_aba)
            row_filtros_modo.controls.append(
                ft.Container(
                    padding=pad(h=12, v=7),
                    bgcolor=cor_aba if ativo else T.SURFACE,
                    border_radius=20,
                    border=borda(1.5 if ativo else 1, cor_aba if ativo else T.BORDER),
                    ink=True,
                    on_click=lambda _, k=chave_aba: _selecionar_aba(k),
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(icone_aba, size=15, color=T.ON_PRIMARY if ativo else cor_aba),
                            ft.Text(
                                rotulo_aba,
                                size=12,
                                weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_600,
                                color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                )
            )

    def _selecionar_aba(nova_aba: str):
        filtro_aba_atual[0] = nova_aba
        _atualizar_kpis_e_abas()
        renderizar_cards()

    # ── Carregar Dados ────────────────────────────────────────────────────────
    def _aplicar_resumo_caixinhas(resumo: dict):
        nonlocal caixinhas_lista
        caixinhas_lista = resumo.get("caixinhas") or []
        banner_aviso_migracao.visible = False
        _atualizar_kpis_e_abas()
        renderizar_cards()

    def carregar_dados(inicial: bool = False, forcar: bool = False):
        loop_check = getattr(page, "loop", None)
        eh_loop_ativo = isinstance(loop_check, asyncio.AbstractEventLoop) and loop_check.is_running() and hasattr(page, "run_task")

        if eh_loop_ativo:
            spinner.visible = True
            if not inicial:
                _safe_update()

            async def _carregar_caixinhas_async():
                try:
                    resumo = await asyncio.to_thread(db.obter_resumo_caixinhas, forcar)
                    _aplicar_resumo_caixinhas(resumo or {})
                except Exception as ex:
                    err_str = str(ex)
                    if "caixinhas_teto" in err_str or "PGRST205" in err_str or "schema cache" in err_str:
                        banner_aviso_migracao.visible = True
                    if not inicial:
                        mostrar_feedback(page, f"Erro ao listar DemBoxes: {ex}", "erro")
                finally:
                    spinner.visible = False
                    _safe_update()

            page.run_task(_carregar_caixinhas_async)
            return

        if not inicial:
            spinner.visible = True
            _safe_update()
        try:
            resumo = db.obter_resumo_caixinhas(forcar_atualizacao=forcar)
            _aplicar_resumo_caixinhas(resumo or {})
        except Exception as ex:
            err_str = str(ex)
            if "caixinhas_teto" in err_str or "PGRST205" in err_str or "schema cache" in err_str:
                banner_aviso_migracao.visible = True
            if not inicial:
                mostrar_feedback(page, f"Erro ao listar DemBoxes: {ex}", "erro")
        finally:
            spinner.visible = False
            _safe_update()

    # ── Helper de Pílulas 1-Clique para Modais Rápidos ─────────────────────────
    def _criar_seletor_pilulas_contas(contas: list[dict], conta_inicial: str) -> tuple[list[str], ft.Row]:
        sel = [conta_inicial or (str(contas[0]["id"]) if contas else "")]
        row = ft.Row(spacing=6, run_spacing=6, wrap=True)

        def _render():
            row.controls.clear()
            for cta in contas:
                cid_cta = str(cta.get("id"))
                nome_cta = cta.get("nome", "Conta")
                cor_cta = cta.get("cor") or T.PRIMARY
                ativo = (sel[0] == cid_cta)
                row.controls.append(
                    ft.Container(
                        padding=pad(h=10, v=6),
                        bgcolor=cor_cta if ativo else T.SURFACE_ALT,
                        border_radius=16,
                        border=borda(1.5 if ativo else 1, cor_cta if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, k=cid_cta: _pick(k),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED if ativo else ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                                    size=13,
                                    color=T.ON_PRIMARY if ativo else cor_cta,
                                ),
                                ft.Text(
                                    nome_cta,
                                    size=11.5,
                                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                    )
                )
            try:
                row.update()
            except Exception:
                pass

        def _pick(k: str):
            sel[0] = k
            _render()

        _render()
        return sel, row

    def _criar_seletor_pilulas_potes(potes: list[dict], pote_inicial: str) -> tuple[list[str], ft.Row]:
        sel = [pote_inicial or (str(potes[0]["id"]) if potes else "")]
        row = ft.Row(spacing=6, run_spacing=6, wrap=True)

        def _render():
            row.controls.clear()
            for p in potes:
                pid = str(p.get("id"))
                p_nome = p.get("nome", "Pote")
                p_pct = p.get("percentual", 0)
                p_cor = p.get("cor") or T.PRIMARY
                ativo = (sel[0] == pid)
                row.controls.append(
                    ft.Container(
                        padding=pad(h=10, v=6),
                        bgcolor=p_cor if ativo else T.SURFACE_ALT,
                        border_radius=16,
                        border=borda(1.5 if ativo else 1, p_cor if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, k=pid: _pick(k),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED if ativo else ft.Icons.PIE_CHART_ROUNDED,
                                    size=13,
                                    color=T.ON_PRIMARY if ativo else p_cor,
                                ),
                                ft.Text(
                                    f"{p_nome} ({p_pct:.0f}%)" if isinstance(p_pct, (int, float)) else p_nome,
                                    size=11,
                                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                    )
                )
            try:
                row.update()
            except Exception:
                pass

        def _pick(k: str):
            sel[0] = k
            _render()

        _render()
        return sel, row

    # ── Ação de Pagar Provisão e Encher o DemBox (Etapa A) ─────────────────────
    def confirmar_pagamento_provisao(caixinha: dict, ao_concluir=None):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "DemBox")
        meta = float(caixinha.get("valor_meta", 0) or 0)

        try:
            contas = db.listar_contas() or []
        except Exception:
            contas = []
        conta_id_padrao = str(caixinha.get("conta_id") or "")
        conta_sel, row_contas = _criar_seletor_pilulas_contas(contas, conta_id_padrao)

        try:
            potes = db.listar_potes() or []
        except Exception:
            potes = []
        pote_id_padrao = str(caixinha.get("pote_id") or "")
        pote_sel, row_potes = _criar_seletor_pilulas_potes(potes, pote_id_padrao)

        txt_valor_pag = ft.TextField(
            label="Valor a Abastecer (R$) *",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=f"{meta:.2f}".replace(".", ","),
            **T.campo_estilo(),
        )

        modal_conf = None

        def executar_pagamento(_):
            val_str = (txt_valor_pag.value or "").replace(",", ".").replace("R$", "").strip()
            try:
                val_num = float(val_str or 0)
                if val_num <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
                return

            conta_escolhida = (conta_sel[0] or "").strip()
            if not conta_escolhida:
                mostrar_feedback(page, "Selecione a Conta Bancária de origem.", "alerta")
                return

            pote_escolhido = (pote_sel[0] or "").strip()
            if not pote_escolhido:
                mostrar_feedback(page, "Selecione a qual dos 6 Potes este abastecimento pertence.", "alerta")
                return

            fechar_dialogo(page, modal_conf)
            spinner.visible = True
            _safe_update()
            try:
                db.pagar_provisao_caixinha(
                    caixinha_id=cid,
                    conta_id=conta_escolhida,
                    pote_id=pote_escolhido,
                    valor=val_num,
                    data_pagamento=date.today().isoformat(),
                )
                mostrar_feedback(
                    page,
                    f"DemBox '{nome}' abastecido com {formatar_moeda(val_num)}! Valor descontado do banco e contabilizado no Pote.",
                    "sucesso",
                )
                carregar_dados(inicial=False, forcar=True)
                if callable(ao_concluir):
                    ao_concluir()
            except Exception as ex:
                spinner.visible = False
                _safe_update()
                mostrar_feedback(page, f"Erro ao efetivar abastecimento: {ex}", "erro")

        modal_conf = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text(f"Encher DemBox · {nome}", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        txt_valor_pag,
                        ft.Column([
                            ft.Text("Conta Bancária de Origem (1 Clique) *", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                            row_contas,
                        ], spacing=5),
                        ft.Column([
                            ft.Text("Pote Financeiro (6 Potes) *", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                            row_potes,
                        ], spacing=5),
                        ft.Container(
                            padding=pad(h=10, v=8),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=8,
                            border=borda(1, T.PRIMARY),
                            content=ft.Row([
                                ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=T.PRIMARY, size=16),
                                ft.Text(
                                    "O valor sai imediatamente da Conta Bancária escolhida, abastece o saldo disponível deste DemBox e é contabilizado como Gasto Real no Pote selecionado.",
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
                    "Confirmar e Encher",
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

    # ── Modal de Guardar Dinheiro / Aporte Adicional (Etapa A - 1 Clique) ──────
    def abrir_modal_provisionar(caixinha: dict, ao_concluir=None):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "DemBox")
        eh_divida = _eh_modo_divida(caixinha)
        meta = float(caixinha.get("valor_meta", 0) or 0)
        saldo_atual = float(caixinha.get("saldo_atual", 0) or 0)
        total_guardado = float(caixinha.get("total_guardado", saldo_atual) or 0)

        base_acum = total_guardado if eh_divida else saldo_atual
        falta_meta = max(0.0, meta - base_acum)
        valor_sugerido = falta_meta if (not eh_divida and falta_meta > 0) else (falta_meta if (eh_divida and falta_meta <= 500 and falta_meta > 0) else 0.0)

        txt_valor = ft.TextField(
            label="Quanto você quer guardar agora? (R$) *" if eh_divida else "Valor a Abastecer (R$) *",
            hint_text="Ex: 200,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=f"{valor_sugerido:.2f}".replace(".", ",") if valor_sugerido > 0 else "",
            autofocus=True,
            **T.campo_estilo(),
        )

        # Atalhos rápidos de valor para facilitar em 1 toque
        row_valores_rapidos = ft.Row(spacing=6, wrap=True)
        sugestoes_val = [50.0, 100.0, 200.0, 300.0, 500.0]
        if falta_meta > 0 and falta_meta not in sugestoes_val:
            sugestoes_val.append(falta_meta)
        for v_sug in sugestoes_val[:6]:
            eh_quitar_tudo = (abs(v_sug - falta_meta) < 0.01 and falta_meta > 0)
            lbl_v = f"Falta Total ({formatar_moeda(v_sug)})" if eh_quitar_tudo else f"+ R$ {v_sug:.0f}"
            row_valores_rapidos.controls.append(
                ft.Container(
                    padding=pad(h=9, v=4),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=12,
                    border=borda(1, T.PRIMARY if eh_quitar_tudo else T.BORDER),
                    ink=True,
                    on_click=lambda _, v=v_sug: _preencher_val_rapido(v),
                    content=ft.Text(
                        lbl_v,
                        size=10.5,
                        weight=ft.FontWeight.BOLD if eh_quitar_tudo else ft.FontWeight.W_600,
                        color=T.PRIMARY if eh_quitar_tudo else T.TEXT_PRIMARY,
                    ),
                )
            )

        def _preencher_val_rapido(v: float):
            txt_valor.value = f"{v:.2f}".replace(".", ",")
            try:
                txt_valor.update()
            except Exception:
                pass

        hoje_data = date.today()
        data_provisao_sel = [hoje_data]

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
            try:
                txt_data_provisao_label.update()
            except Exception:
                pass

        card_seletor_provisao = ft.Container(
            content=ft.Row([
                ft.Container(
                    content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=16),
                    padding=pad(all_=6),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=8,
                ),
                ft.Column([
                    ft.Text("Data em que guardou *" if eh_divida else "Data do Abastecimento *", size=10.5, color=T.TEXT_MUTED),
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
                titulo="Selecionar Data",
            ),
        )

        try:
            contas = db.listar_contas() or []
        except Exception:
            contas = []
        conta_id_padrao = str(caixinha.get("conta_id") or "")
        conta_sel, row_contas = _criar_seletor_pilulas_contas(contas, conta_id_padrao)

        try:
            potes = db.listar_potes() or []
        except Exception:
            potes = []
        pote_id_padrao = str(caixinha.get("pote_id") or "")
        pote_sel, row_potes = _criar_seletor_pilulas_potes(potes, pote_id_padrao)

        txt_desc = ft.TextField(
            label="Observação / Descrição (Opcional)",
            hint_text=f"Ex: Guardado p/ {nome}...",
            value=f"Guardado p/ Dívida · {nome}" if eh_divida else f"Provisão DemBox · {nome}",
            **T.campo_estilo(),
        )

        modal = None

        def confirmar_provisao(_):
            val_str = (txt_valor.value or "").replace(",", ".").replace("R$", "").strip()
            try:
                val = float(val_str or 0)
                if val <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
                return

            conta_escolhida = (conta_sel[0] or "").strip()
            if not conta_escolhida:
                mostrar_feedback(page, "Selecione a Conta Bancária de onde sairá o dinheiro.", "alerta")
                return

            pote_escolhido = (pote_sel[0] or "").strip()
            if not pote_escolhido:
                mostrar_feedback(page, "Selecione a qual dos 6 Potes este valor pertence.", "alerta")
                return

            nome_conta = "Conta"
            for cta in contas:
                if str(cta.get("id")) == conta_escolhida:
                    nome_conta = cta.get("nome", "Conta")
                    break

            fechar_dialogo(page, modal)
            spinner.visible = True
            _safe_update()
            try:
                db.injetar_saldo_caixinha(
                    caixinha_id=cid,
                    valor=val,
                    descricao=txt_desc.value.strip() or (f"Guardado p/ Dívida · {nome}" if eh_divida else f"Provisão DemBox · {nome}"),
                    conta_id=conta_escolhida,
                    pote_id=pote_escolhido,
                    data_aporte=data_provisao_sel[0].isoformat(),
                    gerar_despesa=True,
                )
                msg_ok = (
                    f"{formatar_moeda(val)} guardados para '{nome}'! Descontado da conta '{nome_conta}' e abatido do Pote."
                    if eh_divida
                    else f"{formatar_moeda(val)} abastecidos em '{nome}' (conta '{nome_conta}')!"
                )
                mostrar_feedback(page, msg_ok, "sucesso")
                carregar_dados(inicial=False, forcar=True)
                if callable(ao_concluir):
                    ao_concluir()
            except Exception as ex:
                spinner.visible = False
                _safe_update()
                mostrar_feedback(page, f"Erro ao guardar valor: {ex}", "erro")

        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.SAVINGS_ROUNDED if eh_divida else ft.Icons.ADD_CARD_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text(f"{'Guardar Dinheiro' if eh_divida else 'Abastecer DemBox'} · {nome}", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=460,
                content=ft.Column(
                    spacing=11,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        ft.Container(
                            padding=pad(h=10, v=7),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=8,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(
                                        f"Já guardado: {formatar_moeda(base_acum)} de {formatar_moeda(meta)}",
                                        size=11.5,
                                        weight=ft.FontWeight.W_600,
                                        color=T.PRIMARY,
                                    ),
                                    ft.Text(
                                        f"Falta: {formatar_moeda(falta_meta)}",
                                        size=11.5,
                                        weight=ft.FontWeight.BOLD,
                                        color=T.WARNING if falta_meta > 0 else T.PRIMARY,
                                    ),
                                ],
                            ),
                        ),
                        txt_valor,
                        row_valores_rapidos,
                        card_seletor_provisao,
                        ft.Column([
                            ft.Text("De qual Conta Bancária vai sair? (1 Clique) *", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                            row_contas,
                        ], spacing=5),
                        ft.Column([
                            ft.Text("Contabilizar em qual dos 6 Potes neste mês? *", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                            row_potes,
                        ], spacing=5),
                        txt_desc,
                        ft.Container(
                            padding=pad(h=10, v=8),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=8,
                            border=borda(1, T.PRIMARY),
                            content=ft.Row([
                                ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=T.PRIMARY, size=16),
                                ft.Text(
                                    "Tira do saldo da Conta Bancária escolhida, abate do Pote vinculado neste mês e soma no saldo acumulado deste DemBox.",
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
                    "Guardar Dinheiro" if eh_divida else "Confirmar Abastecimento",
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

    # ── Modal de Pagar/Abater Dívida ou Deduzir Gasto (Etapa B) ────────────────
    def abrir_modal_deduzir(caixinha: dict, ao_concluir=None):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "DemBox")
        eh_divida = _eh_modo_divida(caixinha)
        saldo_atual = float(caixinha.get("saldo_atual", 0) or 0)

        txt_valor = ft.TextField(
            label="Valor Entregue ao Credor / Abatido (R$) *" if eh_divida else "Valor Gasto (R$) *",
            hint_text="Ex: 150,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=f"{saldo_atual:.2f}".replace(".", ",") if (eh_divida and saldo_atual > 0) else "",
            autofocus=True,
            **T.campo_estilo(),
        )
        txt_desc = ft.TextField(
            label="Observação do Pagamento / Abatimento" if eh_divida else "Descrição do Gasto (Opcional)",
            hint_text=f"Ex: Pagamento p/ {nome}..." if eh_divida else "Ex: Abastecimento, compra rápida...",
            value=f"Pagamento / Abatimento · {nome}" if eh_divida else "",
            **T.campo_estilo(),
        )

        modal = None

        def confirmar_deducao(_):
            val_str = (txt_valor.value or "").replace(",", ".").replace("R$", "").strip()
            try:
                val = float(val_str or 0)
                if val <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
                return

            try:
                db.deduzir_saldo_caixinha(
                    cid,
                    val,
                    txt_desc.value.strip() or ("Abatimento de Dívida" if eh_divida else "Gasto registrado"),
                )
                fechar_dialogo(page, modal)
                msg = (
                    f"{formatar_moeda(val)} registrados como pagos/abatidos na dívida '{nome}'!"
                    if eh_divida
                    else f"{formatar_moeda(val)} deduzidos do DemBox '{nome}'!"
                )
                mostrar_feedback(page, msg, "sucesso")
                carregar_dados(inicial=False, forcar=True)
                if callable(ao_concluir):
                    ao_concluir()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao registrar: {ex}", "erro")

        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED if eh_divida else ft.Icons.MONEY_OFF_CSRED_ROUNDED, color=T.INFO if eh_divida else T.DESPESA, size=22),
                ft.Text(f"{'Pagar / Abater Dívida' if eh_divida else 'Deduzir Gasto'} · {nome}", size=16, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=400,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Container(
                            padding=pad(h=10, v=7),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=8,
                            content=ft.Text(
                                f"Saldo guardado disponível para usar: {formatar_moeda(saldo_atual)}",
                                color=T.PRIMARY if saldo_atual > 0 else T.TEXT_MUTED,
                                weight=ft.FontWeight.W_600,
                                size=12,
                            ),
                        ),
                        txt_valor,
                        txt_desc,
                        ft.Container(
                            padding=pad(h=10, v=8),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=8,
                            content=ft.Row([
                                ft.Icon(ft.Icons.LOCK_CLOCK_ROUNDED, color=T.TEXT_MUTED, size=15),
                                ft.Text(
                                    "Utiliza o dinheiro que você já havia guardado neste DemBox para pagar o credor (sem debitar sua conta bancária uma segunda vez)."
                                    if eh_divida
                                    else "Reduz o saldo disponível deste DemBox sem novo débito bancário (pois o valor já foi provisionado na entrada).",
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
                    "Confirmar Abatimento" if eh_divida else "Registrar Gasto",
                    on_click=confirmar_deducao,
                    style=ft.ButtonStyle(
                        bgcolor=T.INFO if eh_divida else T.DESPESA,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=pad(h=16, v=10),
                    ),
                ),
            ],
        )
        abrir_dialogo(page, modal)

    # ── Raio-X Detalhado ao Clicar no Card (Histórico na Ponta do Lápis) ──────
    def abrir_raio_x_dembox(caixinha: dict):
        cid = str(caixinha.get("id"))
        modal_rx = None
        corpo_rx = ft.Column(spacing=12, tight=True, scroll=ft.ScrollMode.AUTO)

        def _popular_raio_x():
            corpo_rx.controls.clear()
            pacote_rx = db.obter_extrato_caixinha(cid) or {}
            cx = pacote_rx.get("caixinha") or caixinha
            historico = pacote_rx.get("historico") or []

            eh_divida = _eh_modo_divida(cx)
            meta = float(pacote_rx.get("valor_meta", cx.get("valor_meta", 0)) or 0)
            guardado = float(pacote_rx.get("total_guardado", cx.get("total_guardado", 0)) or 0)
            abatido = float(pacote_rx.get("total_abatido", cx.get("total_abatido", 0)) or 0)
            saldo = float(pacote_rx.get("saldo_atual", cx.get("saldo_atual", 0)) or 0)
            falta = float(pacote_rx.get("falta_guardar", max(0.0, meta - (guardado if eh_divida else saldo))) or 0)
            pct = float(pacote_rx.get("pct_conquista", 0) or 0)
            cor_cx = cx.get("cor") or T.PRIMARY

            def _mini_kpi(lbl: str, val_str: str, cor_v: str, sub: str = "") -> ft.Container:
                return ft.Container(
                    col={"xs": 6, "sm": 3},
                    padding=pad(h=10, v=8),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=10,
                    border=borda(1, T.BORDER),
                    content=ft.Column(
                        spacing=2,
                        tight=True,
                        controls=[
                            ft.Text(lbl, size=10, color=T.TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(val_str, size=14, weight=ft.FontWeight.BOLD, color=cor_v, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            *([ft.Text(sub, size=9.5, color=T.TEXT_MUTED)] if sub else []),
                        ],
                    ),
                )

            if eh_divida:
                kpis_rx = ft.ResponsiveRow(
                    spacing=8,
                    run_spacing=8,
                    controls=[
                        _mini_kpi("Valor da Dívida", formatar_moeda(meta), T.TEXT_PRIMARY, "Meta total"),
                        _mini_kpi("Já Guardado", formatar_moeda(guardado), T.PRIMARY, f"{pct * 100:.0f}% alcançado"),
                        _mini_kpi("Já Entregue/Pago", formatar_moeda(abatido), T.INFO, f"Em caixa: {formatar_moeda(saldo)}"),
                        _mini_kpi("Falta Guardar", formatar_moeda(falta), T.WARNING if falta > 0 else T.PRIMARY, "Quitado!" if falta <= 0 else "Para 100%"),
                    ],
                )
                txt_status_barra = (
                    "✅ Dívida 100% alcançada!" if falta <= 0
                    else f"🎯 Progresso da Quitação: {pct * 100:.1f}% conquistado · Faltam {formatar_moeda(falta)}"
                )
            else:
                kpis_rx = ft.ResponsiveRow(
                    spacing=8,
                    run_spacing=8,
                    controls=[
                        _mini_kpi("Teto do Mês", formatar_moeda(meta), T.TEXT_PRIMARY, "Meta mensal"),
                        _mini_kpi("Total Abastecido", formatar_moeda(guardado), T.PRIMARY, "Entradas"),
                        _mini_kpi("Consumido", formatar_moeda(abatido), T.WARNING, "Saídas"),
                        _mini_kpi("Saldo Disponível", formatar_moeda(saldo), T.INFO, f"{pct * 100:.0f}% restante"),
                    ],
                )
                txt_status_barra = f"📦 Disponível no período: {formatar_moeda(saldo)} de {formatar_moeda(meta)} ({pct * 100:.0f}%)"

            bloco_barra = ft.Container(
                padding=pad(h=12, v=10),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                border=borda(1, cor_cx),
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text(txt_status_barra, size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY, expand=True),
                                ft.Text(f"{pct * 100:.0f}%", size=12, weight=ft.FontWeight.BOLD, color=cor_cx),
                            ],
                        ),
                        ft.ProgressBar(
                            value=pct,
                            color=cor_cx,
                            bgcolor=T.SURFACE,
                            height=8,
                            border_radius=4,
                        ),
                    ],
                ),
            )

            # Botões de ação rápida dentro do Raio-X
            def _acao_guardar_rx(_):
                fechar_dialogo(page, modal_rx)
                abrir_modal_provisionar(cx)

            def _acao_abater_rx(_):
                fechar_dialogo(page, modal_rx)
                abrir_modal_deduzir(cx)

            def _acao_editar_rx(_):
                fechar_dialogo(page, modal_rx)
                abrir_modal_caixinha(cx)

            barra_acoes_rx = ft.Row(
                spacing=8,
                wrap=True,
                controls=[
                    ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=T.ON_NEON),
                            ft.Text("Guardar Dinheiro" if eh_divida else "Abastecer / Aportar", size=12, weight=ft.FontWeight.BOLD, color=T.ON_NEON),
                        ], spacing=5, tight=True),
                        on_click=_acao_guardar_rx,
                        style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=12, v=8)),
                    ),
                    ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.CHECK_ROUNDED if eh_divida else ft.Icons.REMOVE_ROUNDED, size=16, color=T.ON_PRIMARY),
                            ft.Text("Pagar / Abater Dívida" if eh_divida else "Registrar Gasto", size=12, weight=ft.FontWeight.BOLD, color=T.ON_PRIMARY),
                        ], spacing=5, tight=True),
                        on_click=_acao_abater_rx,
                        style=ft.ButtonStyle(bgcolor=T.INFO if eh_divida else T.DESPESA, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=12, v=8)),
                    ),
                    ft.OutlinedButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.EDIT_ROUNDED, size=15, color=T.TEXT_PRIMARY),
                            ft.Text("Editar", size=12, color=T.TEXT_PRIMARY),
                        ], spacing=4, tight=True),
                        on_click=_acao_editar_rx,
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=10, v=8)),
                    ),
                ],
            )

            # Lista de movimentações na ponta do lápis
            itens_hist_ui = []
            if not historico:
                itens_hist_ui.append(
                    ft.Container(
                        padding=pad(all_=20),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=10,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Column(
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=30, color=T.TEXT_MUTED),
                                ft.Text("Nenhuma movimentação registrada ainda", size=12.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                ft.Text(
                                    "Clique em '+ Guardar Dinheiro' para fazer seu primeiro depósito neste DemBox!",
                                    size=11,
                                    color=T.TEXT_MUTED,
                                    text_align=ft.TextAlign.CENTER,
                                ),
                            ],
                        ),
                    )
                )
            else:
                for h in historico:
                    nat = h.get("natureza", "entrada")
                    val_h = float(h.get("valor", 0) or 0)
                    dt_raw = str(h.get("data") or "")[:10]
                    try:
                        dt_fmt = datetime.strptime(dt_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
                    except Exception:
                        dt_fmt = dt_raw or "—"
                    desc_h = h.get("descricao") or "Movimentação"
                    cta_h = h.get("conta_nome")

                    if nat == "entrada":
                        ic_h = ft.Icons.ARROW_UPWARD_ROUNDED
                        cor_h = T.PRIMARY
                        sinal = "+"
                        tag_h = "Guardado" if eh_divida else "Abastecido"
                    elif nat == "pendente":
                        ic_h = ft.Icons.SCHEDULE_ROUNDED
                        cor_h = T.WARNING
                        sinal = "•"
                        tag_h = "Agendado Pendente"
                    else:
                        ic_h = ft.Icons.CHECK_ROUNDED if eh_divida else ft.Icons.ARROW_DOWNWARD_ROUNDED
                        cor_h = T.INFO if eh_divida else T.DESPESA
                        sinal = "-"
                        tag_h = "Abatido ao Credor" if eh_divida else "Gasto / Consumido"

                    sub_parts = [dt_fmt, tag_h]
                    if cta_h:
                        sub_parts.append(f"Conta: {cta_h}")

                    itens_hist_ui.append(
                        ft.Container(
                            padding=pad(h=10, v=8),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=10,
                            border=borda(1, T.BORDER),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Row(
                                        spacing=10,
                                        expand=True,
                                        controls=[
                                            ft.Container(
                                                padding=pad(all_=6),
                                                bgcolor=T.SURFACE,
                                                border_radius=8,
                                                border=borda(1, cor_h),
                                                content=ft.Icon(ic_h, color=cor_h, size=15),
                                            ),
                                            ft.Column(
                                                spacing=2,
                                                expand=True,
                                                controls=[
                                                    ft.Text(desc_h, size=12.5, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                                    ft.Text(" · ".join(sub_parts), size=10.5, color=T.TEXT_MUTED),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Text(
                                        f"{sinal} {formatar_moeda(val_h)}",
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                        color=cor_h,
                                    ),
                                ],
                            ),
                        )
                    )

            corpo_rx.controls.extend([
                kpis_rx,
                bloco_barra,
                barra_acoes_rx,
                ft.Divider(height=1, color=T.BORDER),
                ft.Row([
                    ft.Icon(ft.Icons.HISTORY_EDU_ROUNDED, size=16, color=T.PRIMARY),
                    ft.Text(f"Histórico na Ponta do Lápis ({len(historico)} registro{'s' if len(historico) != 1 else ''})", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ], spacing=6),
                ft.Column(spacing=6, controls=itens_hist_ui),
            ])

        _popular_raio_x()

        ic_nome = caixinha.get("icone", "inventory_2")
        icone_ctrl = MAPA_ICONES.get(ic_nome, ft.Icons.INVENTORY_2_ROUNDED)
        cor_cx = caixinha.get("cor") or T.PRIMARY
        eh_div = _eh_modo_divida(caixinha)

        modal_rx = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row([
                        ft.Container(
                            padding=pad(all_=7),
                            bgcolor=T.SURFACE_ALT,
                            border=borda(1, cor_cx),
                            border_radius=10,
                            content=ft.Icon(icone_ctrl, color=cor_cx, size=20),
                        ),
                        ft.Column([
                            ft.Text(f"Raio-X · {caixinha.get('nome', 'DemBox')}", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(
                                "🎯 Quitação de Dívida / Acumulação Contínua" if eh_div else "📦 Provisão de Consumo Mensal",
                                size=11,
                                color=cor_cx,
                                weight=ft.FontWeight.W_600,
                            ),
                        ], spacing=1),
                    ], spacing=10),
                ],
            ),
            content=ft.Container(
                width=540,
                content=corpo_rx,
            ),
            actions=[
                ft.TextButton("Fechar Raio-X", on_click=lambda _: fechar_dialogo(page, modal_rx)),
            ],
        )
        abrir_dialogo(page, modal_rx)

    # ── Confirmar Exclusão ────────────────────────────────────────────────────
    def confirmar_exclusao(caixinha: dict):
        cid = str(caixinha.get("id"))
        nome = caixinha.get("nome", "DemBox")

        modal_confirma = None

        def executar_exclusao(_):
            fechar_dialogo(page, modal_confirma)
            try:
                db.deletar_caixinha(cid)
                mostrar_feedback(page, f"DemBox '{nome}' excluído.", "sucesso")
                carregar_dados(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao excluir: {ex}", "erro")

        modal_confirma = ft.AlertDialog(
            modal=True,
            title=ft.Text("Confirmar Exclusão"),
            content=ft.Text(f"Deseja realmente remover o DemBox '{nome}'? O histórico contábil será preservado."),
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

    # ── Modal de Criação / Edição 1-Clique (Zero Dropdowns Desnecessários) ────
    def abrir_modal_caixinha(caixinha_edicao: dict | None = None, modo_inicial: str | None = None):
        eh_edicao = caixinha_edicao is not None
        modo_padrao = (
            ("divida" if _eh_modo_divida(caixinha_edicao) else "provisao_mensal")
            if eh_edicao
            else (modo_inicial or ("divida" if filtro_aba_atual[0] == "divida" else "provisao_mensal"))
        )
        modo_sel = [modo_padrao]

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
        dt_padrao_provisao = dia_5_prox if dia_5_mes < hoje_data else dia_5_mes

        # Carrega dados base para as pílulas de 1 clique
        try:
            potes = db.listar_potes() or []
        except Exception:
            potes = []
        try:
            contas = db.listar_contas() or []
        except Exception:
            contas = []
        try:
            membros = db.listar_membros_familia() or []
        except Exception:
            membros = []

        # Estados selecionados em 1 clique
        pote_sel = [str(caixinha_edicao.get("pote_id") or "") if eh_edicao else (str(potes[0]["id"]) if potes else "")]
        conta_sel = [str(caixinha_edicao.get("conta_id") or "") if eh_edicao else (str(contas[0]["id"]) if contas else "")]
        membro_sel = [str(caixinha_edicao.get("membro_id") or "") if eh_edicao else (str(membros[0]["id"]) if membros else "")]
        cor_sel = [caixinha_edicao.get("cor", CORES_CAIXINHAS[0]["hex"]) if eh_edicao else ("#F59E0B" if modo_sel[0] == "divida" else "#10B981")]
        icone_sel = [caixinha_edicao.get("icone", "inventory_2") if eh_edicao else ("handshake" if modo_sel[0] == "divida" else "two_wheeler")]

        # Campos de texto no topo com foco imediato
        txt_nome = ft.TextField(
            label="Nome da Dívida / Credor *" if modo_sel[0] == "divida" else "Nome da Provisão do Mês *",
            hint_text="Ex: Dívida com a Chefe, Acordo..." if modo_sel[0] == "divida" else "Ex: Moto, Aluguel, Mercado...",
            value=caixinha_edicao.get("nome", "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        txt_meta = ft.TextField(
            label="Valor Total da Dívida (R$) *" if modo_sel[0] == "divida" else "Teto / Meta do Mês (R$) *",
            hint_text="Ex: 1.200,00" if modo_sel[0] == "divida" else "Ex: 400,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=str(caixinha_edicao.get("valor_meta", "")).replace(".", ",") if eh_edicao else "",
            autofocus=not eh_edicao,
            **T.campo_estilo(),
        )

        txt_aporte_inicial = ft.TextField(
            label="Já quero guardar agora (Opcional - R$)",
            hint_text="0,00 (deixe vazio p/ guardar depois)",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value="",
            visible=not eh_edicao,
            **T.campo_estilo(),
        )

        # Data de provisão e alvo (para modo Provisão do Mês)
        if eh_edicao and caixinha_edicao.get("data_provisao"):
            try:
                dt_prov_ini = datetime.strptime(str(caixinha_edicao.get("data_provisao"))[:10], "%Y-%m-%d").date()
            except Exception:
                dt_prov_ini = dt_padrao_provisao
        else:
            dt_prov_ini = dt_padrao_provisao
        data_provisao_sel = [dt_prov_ini]

        if eh_edicao and caixinha_edicao.get("data_alvo"):
            try:
                dt_alvo_ini = datetime.strptime(str(caixinha_edicao.get("data_alvo"))[:10], "%Y-%m-%d").date()
            except Exception:
                dt_alvo_ini = dt_padrao_alvo
        else:
            dt_alvo_ini = dt_padrao_alvo
        data_alvo_sel = [dt_alvo_ini]

        sw_recorrente = ft.Switch(
            value=bool(caixinha_edicao.get("recorrente", True)) if eh_edicao else (modo_sel[0] != "divida"),
            active_color=T.PRIMARY,
        )

        # Containers dinâmicos para re-renderização instantânea em 1 clique
        row_seletor_proposito = ft.ResponsiveRow(spacing=8, run_spacing=8)
        row_sugestoes = ft.Row(spacing=6, run_spacing=6, wrap=True)
        row_pilulas_potes = ft.Row(spacing=6, run_spacing=6, wrap=True)
        row_pilulas_membros = ft.Row(spacing=6, run_spacing=6, wrap=True)
        row_pilulas_contas = ft.Row(spacing=6, run_spacing=6, wrap=True)
        row_pilulas_icones = ft.Row(spacing=6, run_spacing=6, wrap=True)
        row_pilulas_cores = ft.Row(spacing=8, run_spacing=8, wrap=True)
        secao_condicional_modo = ft.Column(spacing=8)

        def _selecionar_pote_por_nome(nome_hint: str):
            nh = nome_hint.strip().lower()
            for p in potes:
                if nh in str(p.get("nome") or "").strip().lower():
                    pote_sel[0] = str(p.get("id"))
                    break

        def _aplicar_sugestao(sug: dict):
            txt_nome.value = sug["nome"]
            icone_sel[0] = sug["icone"]
            cor_sel[0] = sug["cor"]
            if sug.get("pote_hint"):
                _selecionar_pote_por_nome(sug["pote_hint"])
            _render_sugestoes()
            _render_potes()
            _render_icones()
            _render_cores()
            try:
                txt_nome.update()
            except Exception:
                pass

        def _alternar_proposito(novo_modo: str):
            modo_sel[0] = novo_modo
            eh_div = (novo_modo == "divida")
            txt_nome.label = "Nome da Dívida / Credor *" if eh_div else "Nome da Provisão do Mês *"
            txt_nome.hint_text = "Ex: Dívida com a Chefe, Acordo..." if eh_div else "Ex: Moto, Aluguel, Mercado..."
            txt_meta.label = "Valor Total da Dívida (R$) *" if eh_div else "Teto / Meta do Mês (R$) *"
            txt_meta.hint_text = "Ex: 1.200,00" if eh_div else "Ex: 400,00"
            if not eh_edicao:
                if eh_div:
                    icone_sel[0] = "person"
                    cor_sel[0] = "#F59E0B"
                    _selecionar_pote_por_nome("Metas")
                else:
                    icone_sel[0] = "two_wheeler"
                    cor_sel[0] = "#10B981"
                    _selecionar_pote_por_nome("Custos Semi Fixos")
            _render_proposito()
            _render_sugestoes()
            _render_potes()
            _render_icones()
            _render_cores()
            _render_secao_condicional()
            for ctrl in (txt_nome, txt_meta):
                try:
                    ctrl.update()
                except Exception:
                    pass

        def _render_proposito():
            row_seletor_proposito.controls.clear()
            opcoes_prop = [
                (
                    "provisao_mensal",
                    "📦 Provisão do Mês",
                    "Ex: Moto, Aluguel, Mercado (Ciclo Mensal)",
                    "#10B981",
                ),
                (
                    "divida",
                    "🎯 Quitar Dívida / Juntar",
                    "Ex: Chefe, Acordo (Acumulativo até 100%)",
                    "#F59E0B",
                ),
            ]
            for k_mod, tit_mod, sub_mod, cor_mod in opcoes_prop:
                ativo = (modo_sel[0] == k_mod)
                row_seletor_proposito.controls.append(
                    ft.Container(
                        col={"xs": 12, "sm": 6},
                        padding=pad(h=12, v=10),
                        bgcolor=T.SURFACE_ALT if ativo else T.SURFACE,
                        border_radius=12,
                        border=borda(2 if ativo else 1, cor_mod if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, m=k_mod: _alternar_proposito(m),
                        content=ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(
                                    ft.Icons.RADIO_BUTTON_CHECKED_ROUNDED if ativo else ft.Icons.RADIO_BUTTON_UNCHECKED_ROUNDED,
                                    color=cor_mod if ativo else T.TEXT_MUTED,
                                    size=18,
                                ),
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        ft.Text(tit_mod, size=13, weight=ft.FontWeight.BOLD, color=cor_mod if ativo else T.TEXT_PRIMARY),
                                        ft.Text(sub_mod, size=10.5, color=T.TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                ),
                            ],
                        ),
                    )
                )
            try:
                row_seletor_proposito.update()
            except Exception:
                pass

        def _render_sugestoes():
            row_sugestoes.controls.clear()
            lista_sug = SUGESTOES_DIVIDA if modo_sel[0] == "divida" else SUGESTOES_PROVISAO
            for s in lista_sug:
                ic_s = MAPA_ICONES.get(s["icone"], ft.Icons.INVENTORY_2_ROUNDED)
                ativo_s = (txt_nome.value.strip().lower() == s["nome"].lower())
                row_sugestoes.controls.append(
                    ft.Container(
                        padding=pad(h=9, v=5),
                        bgcolor=s["cor"] if ativo_s else T.SURFACE_ALT,
                        border_radius=14,
                        border=borda(1, s["cor"] if ativo_s else T.BORDER),
                        ink=True,
                        on_click=lambda _, sg=s: _aplicar_sugestao(sg),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(ic_s, size=13, color=T.ON_PRIMARY if ativo_s else s["cor"]),
                                ft.Text(
                                    s["nome"],
                                    size=11,
                                    weight=ft.FontWeight.BOLD if ativo_s else ft.FontWeight.W_500,
                                    color=T.ON_PRIMARY if ativo_s else T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                    )
                )
            try:
                row_sugestoes.update()
            except Exception:
                pass

        def _render_potes():
            row_pilulas_potes.controls.clear()
            for p in potes:
                pid = str(p.get("id"))
                p_nome = p.get("nome", "Pote")
                p_pct = p.get("percentual", 0)
                p_cor = p.get("cor") or T.PRIMARY
                ativo = (pote_sel[0] == pid)
                row_pilulas_potes.controls.append(
                    ft.Container(
                        padding=pad(h=10, v=6),
                        bgcolor=p_cor if ativo else T.SURFACE_ALT,
                        border_radius=16,
                        border=borda(1.5 if ativo else 1, p_cor if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, k=pid: _pick_pote(k),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED if ativo else ft.Icons.PIE_CHART_ROUNDED,
                                    size=13,
                                    color=T.ON_PRIMARY if ativo else p_cor,
                                ),
                                ft.Text(
                                    f"{p_nome} ({p_pct:.0f}%)" if isinstance(p_pct, (int, float)) else p_nome,
                                    size=11,
                                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                    )
                )
            try:
                row_pilulas_potes.update()
            except Exception:
                pass

        def _pick_pote(k: str):
            pote_sel[0] = k
            _render_potes()

        def _render_membros():
            row_pilulas_membros.controls.clear()
            for m in membros:
                mid = str(m.get("id"))
                m_nome = m.get("nome", "Perfil")
                m_cor = m.get("cor") or T.PRIMARY
                ativo = (membro_sel[0] == mid)
                row_pilulas_membros.controls.append(
                    ft.Container(
                        padding=pad(h=10, v=6),
                        bgcolor=m_cor if ativo else T.SURFACE_ALT,
                        border_radius=16,
                        border=borda(1.5 if ativo else 1, m_cor if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, k=mid: _pick_membro(k),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(
                                    ft.Icons.PERSON_ROUNDED,
                                    size=13,
                                    color=T.ON_PRIMARY if ativo else m_cor,
                                ),
                                ft.Text(
                                    m_nome,
                                    size=11.5,
                                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                    )
                )
            try:
                row_pilulas_membros.update()
            except Exception:
                pass

        def _pick_membro(k: str):
            membro_sel[0] = k
            _render_membros()

        def _render_contas():
            row_pilulas_contas.controls.clear()
            for cta in contas:
                cid_c = str(cta.get("id"))
                c_nome = cta.get("nome", "Conta")
                c_cor = cta.get("cor") or T.PRIMARY
                ativo = (conta_sel[0] == cid_c)
                row_pilulas_contas.controls.append(
                    ft.Container(
                        padding=pad(h=10, v=6),
                        bgcolor=c_cor if ativo else T.SURFACE_ALT,
                        border_radius=16,
                        border=borda(1.5 if ativo else 1, c_cor if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, k=cid_c: _pick_conta(k),
                        content=ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(
                                    ft.Icons.CHECK_CIRCLE_ROUNDED if ativo else ft.Icons.ACCOUNT_BALANCE_ROUNDED,
                                    size=13,
                                    color=T.ON_PRIMARY if ativo else c_cor,
                                ),
                                ft.Text(
                                    c_nome,
                                    size=11.5,
                                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                    )
                )
            try:
                row_pilulas_contas.update()
            except Exception:
                pass

        def _pick_conta(k: str):
            conta_sel[0] = k
            _render_contas()

        def _render_icones():
            row_pilulas_icones.controls.clear()
            for ic in ICONES_OPCOES:
                k_ic = ic["nome"]
                ativo = (icone_sel[0] == k_ic)
                row_pilulas_icones.controls.append(
                    ft.Container(
                        padding=pad(h=9, v=6),
                        bgcolor=cor_sel[0] if ativo else T.SURFACE_ALT,
                        border_radius=12,
                        border=borda(1.5 if ativo else 1, cor_sel[0] if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, k=k_ic: _pick_icone(k),
                        content=ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ic["icone"], size=14, color=T.ON_PRIMARY if ativo else cor_sel[0]),
                                ft.Text(
                                    ic["label"],
                                    size=10.5,
                                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                    )
                )
            try:
                row_pilulas_icones.update()
            except Exception:
                pass

        def _pick_icone(k: str):
            icone_sel[0] = k
            _render_icones()

        def _render_cores():
            row_pilulas_cores.controls.clear()
            for c in CORES_CAIXINHAS:
                h = c["hex"]
                ativo = (cor_sel[0] == h)
                row_pilulas_cores.controls.append(
                    ft.Container(
                        width=28,
                        height=28,
                        bgcolor=h,
                        border_radius=14,
                        border=borda(2.5, ft.Colors.WHITE) if ativo else borda(1, T.BORDER),
                        tooltip=c["label"],
                        ink=True,
                        on_click=lambda _, hx=h: _pick_cor(hx),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(ft.Icons.CHECK_ROUNDED, size=14, color=ft.Colors.WHITE) if ativo else None,
                    )
                )
            try:
                row_pilulas_cores.update()
            except Exception:
                pass

        def _pick_cor(hx: str):
            cor_sel[0] = hx
            _render_cores()
            _render_icones()

        def _render_secao_condicional():
            secao_condicional_modo.controls.clear()
            if modo_sel[0] == "divida":
                secao_condicional_modo.controls.append(
                    ft.Container(
                        padding=pad(h=12, v=10),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=10,
                        border=borda(1, "#F59E0B"),
                        content=ft.Row([
                            ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, color="#F59E0B", size=20),
                            ft.Column([
                                ft.Text("Modo Quitação de Dívida / Acumulação Contínua", size=12, weight=ft.FontWeight.BOLD, color="#F59E0B"),
                                ft.Text(
                                    "O saldo guardado NÃO zera na virada do mês. Sempre que guardar um valor (+ Guardar Dinheiro), "
                                    "ele sai da conta bancária, abate do Pote no mês e acumula até atingir 100% da dívida!",
                                    size=11,
                                    color=T.TEXT_PRIMARY,
                                ),
                            ], spacing=2, expand=True),
                        ], spacing=10),
                    )
                )
            else:
                # Chips rápidos de data de provisão para modo mensal
                row_datas_prov = ft.Row(spacing=6, wrap=True)
                opcoes_dt = [
                    (f"Dia 5 ({mes_ativo:02d})", dia_5_mes),
                    ("Hoje", hoje_data),
                    (f"Próximo dia 5 ({prox_m:02d})", dia_5_prox),
                    ("Escolher Data...", None),
                ]
                for lbl_d, dt_v in opcoes_dt:
                    eh_custom = (dt_v is None)
                    ativo_d = (not eh_custom and data_provisao_sel[0] == dt_v)
                    row_datas_prov.controls.append(
                        ft.Container(
                            padding=pad(h=9, v=5),
                            bgcolor=T.PRIMARY if ativo_d else T.SURFACE_ALT,
                            border_radius=14,
                            border=borda(1, T.PRIMARY if ativo_d else T.BORDER),
                            ink=True,
                            on_click=(
                                (lambda _: abrir_seletor_data_modal(
                                    page=page,
                                    data_inicial=data_provisao_sel[0],
                                    on_select=lambda nd: (data_provisao_sel.__setitem__(0, nd), _render_secao_condicional()),
                                    titulo="Data da Provisão",
                                ))
                                if eh_custom
                                else (lambda _, d=dt_v: (data_provisao_sel.__setitem__(0, d), _render_secao_condicional()))
                            ),
                            content=ft.Text(
                                lbl_d if not eh_custom else f"📅 {formatar_data_br(data_provisao_sel[0])}",
                                size=11,
                                weight=ft.FontWeight.BOLD if ativo_d else ft.FontWeight.W_500,
                                color=T.ON_PRIMARY if ativo_d else T.TEXT_PRIMARY,
                            ),
                        )
                    )

                secao_condicional_modo.controls.extend([
                    ft.Column([
                        ft.Text("Dia do Abastecimento / Provisão (1 Clique)", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                        row_datas_prov,
                    ], spacing=5),
                    ft.Container(
                        padding=pad(h=12, v=8),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=10,
                        border=borda(1, T.BORDER),
                        content=ft.Row([
                            ft.Icon(ft.Icons.AUTORENEW_ROUNDED, color=T.PRIMARY, size=18),
                            ft.Column([
                                ft.Text("Repetir Todo Mês (Recorrência Mensal)", size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                ft.Text("Renova o envelope automaticamente a cada ciclo mensal.", size=10.5, color=T.TEXT_MUTED),
                            ], spacing=1, expand=True),
                            sw_recorrente,
                        ], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ),
                ])
            try:
                secao_condicional_modo.update()
            except Exception:
                pass

        # Inicializa todas as seções visuais
        _render_proposito()
        _render_sugestoes()
        _render_potes()
        _render_membros()
        _render_contas()
        _render_icones()
        _render_cores()
        _render_secao_condicional()

        modal = None

        def salvar_caixinha(_):
            nome = (txt_nome.value or "").strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome do DemBox.", "alerta")
                return

            try:
                meta_num = float((txt_meta.value or "").replace(".", "").replace(",", ".").replace("R$", "").strip() if "," in (txt_meta.value or "") and "." in (txt_meta.value or "") else (txt_meta.value or "").replace(",", ".").replace("R$", "").strip() or 0)
                if meta_num <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um valor de meta/dívida válido maior que zero.", "alerta")
                return

            aporte_ini_num = 0.0
            val_ap_raw = (txt_aporte_inicial.value or "").replace(",", ".").replace("R$", "").strip()
            if val_ap_raw:
                try:
                    aporte_ini_num = max(0.0, float(val_ap_raw))
                except ValueError:
                    aporte_ini_num = 0.0

            pote_id = (pote_sel[0] or "").strip()
            if not pote_id:
                mostrar_feedback(page, "Selecione o Pote Financeiro em 1 clique.", "alerta")
                return

            c_origem = (conta_sel[0] or "").strip()
            if not c_origem:
                mostrar_feedback(page, "Selecione a Conta Bancária padrão em 1 clique.", "alerta")
                return

            eh_div = (modo_sel[0] == "divida")
            dados = {
                "nome": nome,
                "modalidade": "divida" if eh_div else "provisao_mensal",
                "valor_meta": meta_num,
                "data_provisao": data_provisao_sel[0].isoformat(),
                "data_alvo": None if eh_div else data_alvo_sel[0].isoformat(),
                "conta_id": c_origem,
                "membro_id": (membro_sel[0] or "").strip() or None,
                "tipo_provisao": "despesa",
                "recorrente": False if eh_div else bool(sw_recorrente.value),
                "dia_recorrencia": data_provisao_sel[0].day,
                "cor": cor_sel[0],
                "icone": icone_sel[0] or ("person" if eh_div else "inventory_2"),
                "pote_id": pote_id,
                "ativo": True,
                "aporte_inicial": aporte_ini_num,
            }

            try:
                if eh_edicao:
                    db.atualizar_caixinha(caixinha_edicao["id"], dados)
                    msg = f"DemBox '{nome}' atualizado com sucesso!"
                else:
                    db.criar_caixinha(dados)
                    if eh_div:
                        if aporte_ini_num > 0:
                            msg = f"Dívida '{nome}' criada já com {formatar_moeda(aporte_ini_num)} guardados!"
                        else:
                            msg = f"Dívida '{nome}' ({formatar_moeda(meta_num)}) criada! Use '+ Guardar Dinheiro' sempre que separar um valor."
                    else:
                        if aporte_ini_num > 0:
                            msg = f"Provisão '{nome}' criada e abastecida com {formatar_moeda(aporte_ini_num)}!"
                        else:
                            msg = f"Provisão '{nome}' ({formatar_moeda(meta_num)}) criada!"

                fechar_dialogo(page, modal)
                mostrar_feedback(page, msg, "sucesso")
                carregar_dados(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar DemBox: {ex}", "erro")

        corpo_modal = ft.Column(
            spacing=12,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            controls=[
                # 1. Seletor de Propósito no Topo (1 Clique)
                ft.Column([
                    ft.Text("1. Qual é o propósito deste DemBox? (1 Clique)", size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                    row_seletor_proposito,
                ], spacing=5),

                # 2. Sugestões Inteligentes + Nome e Valor no Topo
                ft.Column([
                    ft.Text("Sugestões Rápidas (1 Toque):", size=11, color=T.TEXT_MUTED),
                    row_sugestoes,
                ], spacing=4),

                ft.ResponsiveRow(
                    spacing=10,
                    run_spacing=10,
                    controls=[
                        ft.Container(content=txt_nome, col={"xs": 12, "sm": 12 if eh_edicao else 5}),
                        ft.Container(content=txt_meta, col={"xs": 12, "sm": 6 if eh_edicao else 4}),
                        *(
                            [ft.Container(content=txt_aporte_inicial, col={"xs": 12, "sm": 3})]
                            if not eh_edicao
                            else []
                        ),
                    ],
                ),

                # 3. Pílulas dos 6 Potes Financeiros (1 Clique)
                ft.Column([
                    ft.Text("2. Pote Financeiro Vinculado (6 Potes) *", size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                    row_pilulas_potes,
                ], spacing=5),

                # 4. Pílulas de Perfil Familiar e Conta Padrão (1 Clique)
                ft.ResponsiveRow(
                    spacing=10,
                    run_spacing=8,
                    controls=[
                        *(
                            [
                                ft.Container(
                                    col={"xs": 12, "sm": 5},
                                    content=ft.Column([
                                        ft.Text("3. Perfil Familiar", size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                                        row_pilulas_membros,
                                    ], spacing=5),
                                )
                            ]
                            if membros
                            else []
                        ),
                        ft.Container(
                            col={"xs": 12, "sm": 7 if membros else 12},
                            content=ft.Column([
                                ft.Text("4. Conta Bancária Padrão *", size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                                row_pilulas_contas,
                            ], spacing=5),
                        ),
                    ],
                ),

                # 5. Seletor Visual Rápido de Ícone e Cor (1 Toque)
                ft.Column([
                    ft.Text("5. Ícone e Cor de Identificação (1 Toque)", size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                    row_pilulas_icones,
                    row_pilulas_cores,
                ], spacing=6),

                # 6. Seção Condicional (Provisão Mensal vs Quitação de Dívida)
                secao_condicional_modo,
            ],
        )

        modal = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Editar DemBox" if eh_edicao else "Novo DemBox (1 Clique)", size=17, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Container(
                width=580,
                content=corpo_modal,
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal)),
                ft.FilledButton(
                    "Salvar DemBox",
                    on_click=salvar_caixinha,
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=18, v=10)),
                ),
            ],
        )
        abrir_dialogo(page, modal)

    # ── Renderizar Lista de DemBoxes ──────────────────────────────────────────
    def renderizar_cards():
        grid_caixinhas.controls.clear()

        aba = filtro_aba_atual[0]
        if aba == "divida":
            itens_visiveis = [c for c in caixinhas_lista if _eh_modo_divida(c)]
        elif aba == "provisao_mensal":
            itens_visiveis = [c for c in caixinhas_lista if not _eh_modo_divida(c)]
        else:
            itens_visiveis = list(caixinhas_lista)

        if not itens_visiveis:
            msg_vazio = (
                "Nenhuma Dívida ou Meta em Acumulação cadastrada"
                if aba == "divida"
                else ("Nenhuma Provisão do Mês cadastrada" if aba == "provisao_mensal" else "Nenhum DemBox Criado")
            )
            sub_vazio = (
                "Crie um DemBox no modo 'Quitar Dívida / Juntar' (ex: Dívida com a Chefe) para guardar dinheiro aos poucos sem zerar na virada do mês!"
                if aba == "divida"
                else "Crie DemBoxes para controlar despesas mensais (Moto, Aluguel) ou juntar dinheiro para quitar dívidas!"
            )
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
                            ft.Text(msg_vazio, size=18, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                            ft.Text(sub_vazio, color=T.TEXT_MUTED, size=13, text_align=ft.TextAlign.CENTER),
                            ft.Container(height=6),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                spacing=10,
                                wrap=True,
                                controls=[
                                    ft.FilledButton(
                                        content=ft.Row([
                                            ft.Icon(ft.Icons.ADD_ROUNDED, size=18, color=T.ON_NEON),
                                            ft.Text("Nova Provisão do Mês", weight=ft.FontWeight.BOLD, color=T.ON_NEON),
                                        ], spacing=6, tight=True),
                                        on_click=lambda _: abrir_modal_caixinha(modo_inicial="provisao_mensal"),
                                        style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=10), padding=pad(h=16, v=11)),
                                    ),
                                    ft.FilledButton(
                                        content=ft.Row([
                                            ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=18, color=T.ON_PRIMARY),
                                            ft.Text("Nova Dívida / Quitação", weight=ft.FontWeight.BOLD, color=T.ON_PRIMARY),
                                        ], spacing=6, tight=True),
                                        on_click=lambda _: abrir_modal_caixinha(modo_inicial="divida"),
                                        style=ft.ButtonStyle(bgcolor="#F59E0B", shape=ft.RoundedRectangleBorder(radius=10), padding=pad(h=16, v=11)),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )
            _safe_update()
            return

        hoje_data = date.today()

        for c in itens_visiveis:
            cid = str(c.get("id"))
            nome = c.get("nome", "DemBox")
            eh_divida = _eh_modo_divida(c)
            cor = c.get("cor") or ("#F59E0B" if eh_divida else "#10B981")
            meta = float(c.get("valor_meta", 0) or 0)
            saldo = float(c.get("saldo_atual", 0) or 0)
            gasto = float(c.get("total_gasto", 0) or 0)
            total_guardado = float(c.get("total_guardado", saldo + gasto) or 0)
            total_abatido = float(c.get("total_abatido", gasto) or 0)
            falta_guardar = max(0.0, meta - (total_guardado if eh_divida else saldo))

            # Informações dos vínculos
            pote_info = c.get("potes")
            pote_nome = pote_info.get("nome") if isinstance(pote_info, dict) else None
            pote_cor = pote_info.get("cor") if isinstance(pote_info, dict) else T.PRIMARY

            conta_info = c.get("contas")
            conta_nome = conta_info.get("nome") if isinstance(conta_info, dict) else None

            ic_nome = c.get("icone", "inventory_2")
            icone_ctrl = MAPA_ICONES.get(ic_nome, ft.Icons.INVENTORY_2_ROUNDED)

            # Chips de Metadados (Modo, Pote, Conta, Raio-X)
            row_badges_vinculo = ft.Row(spacing=5, run_spacing=5, wrap=True)

            # Badge de Modalidade (Dívida Acumulativa vs Provisão Mensal)
            if eh_divida:
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=11, color="#F59E0B"),
                            ft.Text("Dívida / Acumulativo", size=10, weight=ft.FontWeight.BOLD, color="#F59E0B"),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        border=borda(1, "#F59E0B"),
                    )
                )
            elif c.get("recorrente"):
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.AUTORENEW_ROUNDED, size=11, color=T.PRIMARY),
                            ft.Text("Mensal", size=10, weight=ft.FontWeight.W_600, color=T.PRIMARY),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        border=borda(1, T.PRIMARY),
                    )
                )

            if pote_nome:
                row_badges_vinculo.controls.append(
                    ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.PIE_CHART_OUTLINE_ROUNDED, size=11, color=pote_cor),
                            ft.Text(pote_nome, size=10, weight=ft.FontWeight.W_600, color=pote_cor),
                        ], spacing=3, tight=True),
                        padding=pad(h=6, v=2),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=6,
                        border=borda(1, pote_cor),
                    )
                )

            if conta_nome:
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

            # Badge clicável de Raio-X
            row_badges_vinculo.controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ANALYTICS_ROUNDED, size=11, color=T.INFO),
                        ft.Text("Raio-X", size=10, weight=ft.FontWeight.W_600, color=T.INFO),
                    ], spacing=3, tight=True),
                    padding=pad(h=6, v=2),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=6,
                    border=borda(1, T.INFO),
                    tooltip="Ver extrato completo e evolução na ponta do lápis",
                )
            )

            # ── MODO A: QUITAÇÃO DE DÍVIDAS / ACUMULAÇÃO CONTÍNUA ─────────────
            if eh_divida:
                pct_conquista = min(1.0, max(0.0, total_guardado / meta)) if meta > 0 else 0.0
                cor_barra = T.PRIMARY if pct_conquista >= 1.0 else cor

                if falta_guardar <= 0 and saldo <= 0 and total_abatido >= meta:
                    status_texto = "✅ 100% Quitado"
                    cor_badge_txt = T.PRIMARY
                    cor_badge_borda = T.PRIMARY
                elif falta_guardar <= 0:
                    status_texto = "🎉 100% Guardado"
                    cor_badge_txt = T.PRIMARY
                    cor_badge_borda = T.PRIMARY
                else:
                    status_texto = f"{pct_conquista * 100:.0f}% conquistado"
                    cor_badge_txt = cor if total_guardado > 0 else T.TEXT_MUTED
                    cor_badge_borda = cor if total_guardado > 0 else T.BORDER

                sub_detalhe_guardado = (
                    f"Em caixa p/ pagar: {formatar_moeda(saldo)} · Já entregue ao credor: {formatar_moeda(total_abatido)}"
                    if total_abatido > 0
                    else f"Acumulado p/ quitar · Meta total: {formatar_moeda(meta)}"
                )

                bloco_metricas_card = ft.Column(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    controls=[
                                        ft.Text("Quanto Já Guardei", size=10.5, color=T.TEXT_MUTED),
                                        ft.Text(
                                            formatar_moeda(total_guardado),
                                            size=23,
                                            weight=ft.FontWeight.BOLD,
                                            color=T.PRIMARY if total_guardado > 0 else T.TEXT_MUTED,
                                        ),
                                    ],
                                ),
                                ft.Column(
                                    spacing=1,
                                    horizontal_alignment=ft.CrossAxisAlignment.END,
                                    controls=[
                                        ft.Text("Valor Total da Dívida", size=10.5, color=T.TEXT_MUTED),
                                        ft.Text(
                                            formatar_moeda(meta),
                                            size=15,
                                            weight=ft.FontWeight.BOLD,
                                            color=T.TEXT_PRIMARY,
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.Text(sub_detalhe_guardado, size=11, color=T.TEXT_MUTED),
                    ],
                )

                if falta_guardar > 0:
                    icone_faixa = ft.Icons.FLAG_ROUNDED
                    cor_faixa = "#F59E0B"
                    texto_faixa = f"Falta guardar {formatar_moeda(falta_guardar)} para atingir 100% e quitar"
                elif saldo > 0:
                    icone_faixa = ft.Icons.CELEBRATION_ROUNDED
                    cor_faixa = T.PRIMARY
                    texto_faixa = f"100% Guardado! Transfira {formatar_moeda(saldo)} para quitar a dívida"
                else:
                    icone_faixa = ft.Icons.VERIFIED_ROUNDED
                    cor_faixa = T.PRIMARY
                    texto_faixa = "Dívida 100% quitada! Meta cumprida com sucesso"

                faixa_status_card = ft.Container(
                    padding=pad(h=10, v=7),
                    bgcolor=T.SURFACE_ALT,
                    border=borda(1, cor_faixa),
                    border_radius=8,
                    content=ft.Row(
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(icone_faixa, size=15, color=cor_faixa),
                            ft.Text(
                                texto_faixa,
                                size=11,
                                color=T.TEXT_PRIMARY,
                                weight=ft.FontWeight.W_600,
                                expand=True,
                            ),
                        ],
                    ),
                )

                botoes_acao_card = ft.Row(
                    spacing=8,
                    controls=[
                        ft.Container(
                            expand=True,
                            border_radius=8,
                            border=borda(1, T.PRIMARY),
                            content=ft.FilledButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=T.ON_NEON),
                                    ft.Text("Guardar Dinheiro", size=11.5, weight=ft.FontWeight.BOLD, color=T.ON_NEON),
                                ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                                on_click=lambda _, it=c: abrir_modal_provisionar(it),
                                style=ft.ButtonStyle(
                                    bgcolor=T.PRIMARY,
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=pad(v=8),
                                ),
                            ),
                        ),
                        ft.Container(
                            expand=True,
                            border_radius=8,
                            border=borda(1, T.INFO),
                            content=ft.FilledButton(
                                content=ft.Row([
                                    ft.Icon(ft.Icons.CHECK_ROUNDED, size=15, color=T.INFO),
                                    ft.Text("Pagar / Abater", size=11.5, weight=ft.FontWeight.W_600, color=T.INFO),
                                ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                                on_click=lambda _, it=c: abrir_modal_deduzir(it),
                                style=ft.ButtonStyle(
                                    bgcolor=T.SURFACE_ALT,
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=pad(v=8),
                                ),
                            ),
                        ),
                    ],
                )
                pct_barra = pct_conquista

            # ── MODO B: PROVISÃO DE CONSUMO DO MÊS (MOTO, ALUGUEL, ETC.) ──────
            else:
                pct = min(1.0, max(0.0, saldo / meta)) if meta > 0 else 0.0
                dt_prov_raw = c.get("provisao_data") or c.get("data_provisao")
                dt_alvo_raw = c.get("data_alvo")
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
                                texto_ritmo = "Provisão agendada · Aguardando pagamento para encher"
                        else:
                            texto_ritmo = "Ciclo encerrado · Prazo atingido"
                    except Exception:
                        pass

                if saldo <= 0:
                    cor_barra = T.BORDER
                    if dt_prov_raw:
                        try:
                            d_prov = datetime.strptime(str(dt_prov_raw)[:10], "%Y-%m-%d").date()
                            status_texto = f"Pendente ({d_prov.strftime('%d/%m')})"
                        except Exception:
                            status_texto = "Aguardando"
                    else:
                        status_texto = "Aguardando"
                    cor_badge_txt = T.WARNING
                    cor_badge_borda = T.WARNING
                    texto_sub_saldo = f"Provisão de {formatar_moeda(meta)} agendada · Pendente"
                elif pct >= 0.50:
                    cor_barra = T.PRIMARY
                    status_texto = f"{pct * 100:.0f}% restante"
                    cor_badge_txt = T.PRIMARY
                    cor_badge_borda = T.PRIMARY
                    texto_sub_saldo = f"De {formatar_moeda(meta)} provisionado · Consumido: {formatar_moeda(gasto)}"
                elif pct >= 0.20:
                    cor_barra = T.WARNING
                    status_texto = f"{pct * 100:.0f}% restante"
                    cor_badge_txt = T.WARNING
                    cor_badge_borda = T.WARNING
                    texto_sub_saldo = f"De {formatar_moeda(meta)} provisionado · Consumido: {formatar_moeda(gasto)}"
                else:
                    cor_barra = T.DESPESA
                    status_texto = "Nível Crítico"
                    cor_badge_txt = T.DESPESA
                    cor_badge_borda = T.DESPESA
                    texto_sub_saldo = f"De {formatar_moeda(meta)} provisionado · Consumido: {formatar_moeda(gasto)}"

                bloco_metricas_card = ft.Column(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Text(
                            formatar_moeda(saldo),
                            size=24,
                            weight=ft.FontWeight.BOLD,
                            color=T.TEXT_PRIMARY if saldo > 0 else T.TEXT_MUTED,
                        ),
                        ft.Text(texto_sub_saldo, size=11.5, color=T.TEXT_MUTED),
                    ],
                )

                faixa_status_card = ft.Container(
                    padding=pad(h=10, v=7),
                    bgcolor=T.SURFACE_ALT,
                    border=borda(1, T.INFO if saldo > 0 else T.BORDER),
                    border_radius=8,
                    content=ft.Row(
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.SPEED_ROUNDED, size=15, color=T.INFO if saldo > 0 else T.WARNING),
                            ft.Text(
                                texto_ritmo,
                                size=11,
                                color=T.TEXT_PRIMARY if saldo > 0 else T.TEXT_MUTED,
                                weight=ft.FontWeight.W_600 if saldo > 0 else ft.FontWeight.W_500,
                                expand=True,
                            ),
                        ],
                    ),
                )

                if saldo <= 0:
                    botoes_acao_card = ft.FilledButton(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=16, color=T.ON_NEON),
                            ft.Text("Pagar Provisão e Encher DemBox", size=12.5, weight=ft.FontWeight.BOLD, color=T.ON_NEON),
                        ], spacing=6, alignment=ft.MainAxisAlignment.CENTER),
                        on_click=lambda _, it=c: confirmar_pagamento_provisao(it),
                        style=ft.ButtonStyle(
                            bgcolor=T.PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=8),
                            padding=pad(v=10),
                        ),
                    )
                else:
                    botoes_acao_card = ft.Row(
                        spacing=8,
                        controls=[
                            ft.Container(
                                expand=True,
                                border_radius=8,
                                border=borda(1, T.PRIMARY),
                                content=ft.FilledButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.ADD_ROUNDED, size=15, color=T.PRIMARY),
                                        ft.Text("Aportar", size=12, weight=ft.FontWeight.W_600, color=T.PRIMARY),
                                    ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                                    on_click=lambda _, it=c: abrir_modal_provisionar(it),
                                    style=ft.ButtonStyle(
                                        bgcolor=T.SURFACE_ALT,
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=pad(v=8),
                                    ),
                                ),
                            ),
                            ft.Container(
                                expand=True,
                                border_radius=8,
                                border=borda(1, T.DESPESA),
                                content=ft.FilledButton(
                                    content=ft.Row([
                                        ft.Icon(ft.Icons.REMOVE_ROUNDED, size=15, color=T.DESPESA),
                                        ft.Text("Gastar", size=12, weight=ft.FontWeight.W_600, color=T.DESPESA),
                                    ], spacing=4, alignment=ft.MainAxisAlignment.CENTER),
                                    on_click=lambda _, it=c: abrir_modal_deduzir(it),
                                    style=ft.ButtonStyle(
                                        bgcolor=T.SURFACE_ALT,
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=pad(v=8),
                                    ),
                                ),
                            ),
                        ],
                    )
                pct_barra = pct

            # Card Individual do DemBox (Clicável para abrir Raio-X)
            card_caixinha = ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=16),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(1.3, cor if (pct_barra > 0 or eh_divida) else T.BORDER),
                ink=True,
                on_click=lambda _, it=c: abrir_raio_x_dembox(it),
                content=ft.Column(
                    spacing=10,
                    controls=[
                        # 1. Header do Card
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    expand=True,
                                    controls=[
                                        ft.Container(
                                            content=ft.Icon(icone_ctrl, color=cor, size=20),
                                            bgcolor=T.SURFACE_ALT,
                                            border=borda(1, cor),
                                            border_radius=10,
                                            padding=pad(all_=8),
                                        ),
                                        ft.Text(
                                            nome,
                                            size=15.5,
                                            weight=ft.FontWeight.BOLD,
                                            color=T.TEXT_PRIMARY,
                                            max_lines=1,
                                            overflow=ft.TextOverflow.ELLIPSIS,
                                            expand=True,
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.Container(
                                            content=ft.Text(status_texto, size=10.5, weight=ft.FontWeight.BOLD, color=cor_badge_txt),
                                            bgcolor=T.SURFACE_ALT,
                                            border=borda(1, cor_badge_borda),
                                            padding=pad(h=8, v=3),
                                            border_radius=8,
                                        ),
                                        ft.PopupMenuButton(
                                            icon=ft.Icons.MORE_VERT_ROUNDED,
                                            icon_size=18,
                                            items=[
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.ANALYTICS_ROUNDED, size=15, color=T.INFO),
                                                        ft.Text("Abrir Raio-X / Histórico", size=13, color=T.INFO),
                                                    ], spacing=8),
                                                    on_click=lambda _, it=c: abrir_raio_x_dembox(it),
                                                ),
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.SAVINGS_ROUNDED, size=15, color=T.PRIMARY),
                                                        ft.Text(
                                                            "Guardar Dinheiro" if eh_divida else ("Pagar e Encher" if saldo <= 0 else "Aportar Mais"),
                                                            size=13,
                                                            color=T.PRIMARY,
                                                        ),
                                                    ], spacing=8),
                                                    on_click=lambda _, it=c, ed=eh_divida: (
                                                        abrir_modal_provisionar(it)
                                                        if ed or float(it.get("saldo_atual", 0) or 0) > 0
                                                        else confirmar_pagamento_provisao(it)
                                                    ),
                                                ),
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.CHECK_ROUNDED if eh_divida else ft.Icons.REMOVE_ROUNDED, size=15, color=T.INFO if eh_divida else T.DESPESA),
                                                        ft.Text("Pagar / Abater Dívida" if eh_divida else "Gastar / Deduzir", size=13, color=T.INFO if eh_divida else T.DESPESA),
                                                    ], spacing=8),
                                                    on_click=lambda _, it=c: abrir_modal_deduzir(it),
                                                ),
                                                ft.PopupMenuItem(
                                                    content=ft.Row([
                                                        ft.Icon(ft.Icons.EDIT_ROUNDED, size=15),
                                                        ft.Text("Editar DemBox", size=13),
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

                        # 1.b Linha de Badges de Vínculo + Raio-X
                        row_badges_vinculo,

                        # 2. Métricas (Provisão Mensal ou Dívida Acumulativa)
                        bloco_metricas_card,

                        # 3. Barra de Progresso Dinâmica
                        ft.ProgressBar(
                            value=pct_barra,
                            color=cor_barra,
                            bgcolor=T.SURFACE_ALT,
                            height=7,
                            border_radius=4,
                        ),

                        # 4. Faixa de Status (Ritmo Diário Seguro ou Quanto Falta p/ Quitar)
                        faixa_status_card,

                        # 5. Botões de Ação
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
                titulo="Total Metas & Dívidas",
                valor_control=txt_total_meta,
                subtitulo="Soma dos alvos ativos",
                icone=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                cor=T.TEXT_PRIMARY,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
            kpi_clicavel(
                titulo="Guardado / Disponível",
                valor_control=txt_total_saldo,
                subtitulo="Saldo acumulado nos boxes",
                icone=ft.Icons.SAVINGS_ROUNDED,
                cor=T.PRIMARY,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
            kpi_clicavel(
                titulo="Consumido / Abatido",
                valor_control=txt_total_gasto,
                subtitulo="Gastos e quitações",
                icone=ft.Icons.SHOPPING_BAG_ROUNDED,
                cor=T.WARNING,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
            kpi_clicavel(
                titulo="Ritmo / Meta Restante",
                valor_control=txt_ritmo_diario,
                subtitulo="Média diária ou falta quitar",
                icone=ft.Icons.SPEED_ROUNDED,
                cor=T.INFO,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
            ),
        ],
    )

    # ── Header da Página ──────────────────────────────────────────────────────
    btn_nova_divida = ft.OutlinedButton(
        content=ft.Row([
            ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, size=16, color="#F59E0B"),
            ft.Text("+ Quitar Dívida", size=12.5, weight=ft.FontWeight.BOLD, color="#F59E0B"),
        ], spacing=5, tight=True),
        on_click=lambda _: abrir_modal_caixinha(modo_inicial="divida"),
        style=ft.ButtonStyle(
            side=ft.BorderSide(1.2, "#F59E0B"),
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=12, v=10),
        ),
    )

    btn_nova = ft.FilledButton(
        content=ft.Row([
            ft.Icon(ft.Icons.ADD_ROUNDED, size=18, color=T.ON_NEON),
            ft.Text("Novo DemBox", size=13, weight=ft.FontWeight.BOLD, color=T.ON_NEON),
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
        wrap=True,
        controls=[
            ft.Column(
                spacing=2,
                tight=True,
                controls=[
                    ft.Row([
                        ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color=T.PRIMARY, size=24),
                        ft.Text("Meus DemBoxes", size=20 if mobile else 24, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                    ], spacing=8),
                    ft.Text(
                        "Provisões mensais de consumo e acumulação contínua para quitação de dívidas" if not mobile else "Provisões do mês e quitação de dívidas",
                        color=T.TEXT_MUTED,
                        size=12 if mobile else 13,
                    ),
                ],
            ),
            ft.Row([spinner, btn_nova_divida, btn_nova], spacing=8, tight=True),
        ],
    )

    # ── Layout da View ────────────────────────────────────────────────────────
    conteudo = ft.Column(
        spacing=16,
        controls=[
            header_view,
            banner_aviso_migracao,
            strip_kpis,
            row_filtros_modo,
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
        titulo="DemBoxes",
        mostrar_voltar=False,
    )
