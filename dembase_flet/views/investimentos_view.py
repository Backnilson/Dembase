"""
=============================================================================
DemBase v3 — views/investimentos_view.py (Flet 1.0.1)
Módulo de Investimentos & Patrimônio ("Meu Cofre").
Experiência Wealth Management de Altíssimo Nível:
- Header de Impacto: O Efeito Bola de Neve (Patrimônio Total Acumulado).
- Card "Meu Suor vs. Juros": Total Aportado vs Rendimentos Acumulados + % Lucro.
- Card "Máquina de Renda Passiva": Estimativa em R$/mês e R$/dia a 102% do CDI.
- Cards dos Ativos: Porquinho (Reserva de Emergência) + Renda Fixa (102% CDI).
- Experiência Dupla de Rendimento:
    * Opção A: Lançar Rendimento Direto (+ R$ no dia/mês).
    * Opção B: Ajuste por Saldo Atual (Inteligente - calcula diferença automaticamente).
- Gráficos Estimulantes: Evolução Patrimonial (Bola de Neve) e Histórico Mensal.
- Gamificação: Badges de Conquistas e Marcos Patrimoniais (R$ 1k, 5k, 10k, Constância).
- Reatividade Imediata (.update()) em todas as operações sem reload.
=============================================================================
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
import flet as ft

from core import theme as T
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.constants import (
    formatar_moeda,
    formatar_moeda_input,
    parse_moeda_seguro,
    formatar_data_br,
    MESES_NOMES,
)
from core.responsive import is_mobile
from views.shell_view import criar_shell
from views.widgets.clickable_card import kpi_clicavel
from views.widgets.custom_date_picker import abrir_seletor_data_modal
import services.supabase_client as db

ROTA_INVESTIMENTOS = "/investimentos"

# Paleta de Investimentos e Dopamina Visual
COR_PORQUINHO = "#10B981"     # Esmeralda Vibrante (Reserva)
COR_CDI       = "#00E676"     # Verde Neon Primário (102% CDI)
COR_SUOR      = "#6366F1"     # Índigo / Roxo Suave (Meu Suor / Aportes)
COR_JUROS     = "#00E676"     # Verde Neon (Juros Compostos)
COR_RESGATE   = "#F59E0B"     # Âmbar (Resgates)
COR_RENDA_PAS = "#06B6D4"     # Ciano Luminoso (Máquina de Renda Passiva)


def criar_view_investimentos(page: ft.Page, match=None) -> ft.View:
    mobile = is_mobile(page)

    # Estado local mutável para reatividade imediata
    estado: dict = {
        "resumo": {},
        "cofres": [],
        "carregando": True,
        "filtro_cofre_id": None,
    }

    # ── Controles de KPIs do Topo ─────────────────────────────────────────────
    tam_kpi_grande = 26 if mobile else 34
    tam_kpi_medio  = 18 if mobile else 22

    txt_patrimonio_total = ft.Text(
        "R$ 0,00",
        size=tam_kpi_grande,
        weight=ft.FontWeight.BOLD,
        color=T.PRIMARY,
    )
    txt_sub_patrimonio = ft.Text(
        "Patrimônio total acumulado nos cofres",
        size=12,
        color=T.TEXT_MUTED,
    )

    txt_meu_suor = ft.Text(
        "R$ 0,00",
        size=tam_kpi_medio,
        weight=ft.FontWeight.BOLD,
        color=COR_SUOR,
    )
    txt_juros_ganhos = ft.Text(
        "R$ 0,00",
        size=tam_kpi_medio,
        weight=ft.FontWeight.BOLD,
        color=COR_JUROS,
    )
    txt_lucro_pct = ft.Text(
        "+0,00%",
        size=13,
        weight=ft.FontWeight.BOLD,
        color=COR_JUROS,
    )
    pb_suor_vs_juros = ft.ProgressBar(
        value=0.5,
        color=COR_JUROS,
        bgcolor=COR_SUOR,
        height=10,
        border_radius=5,
    )

    txt_renda_mensal = ft.Text(
        "R$ 0,00 / mês",
        size=tam_kpi_medio,
        weight=ft.FontWeight.BOLD,
        color=COR_RENDA_PAS,
    )
    txt_renda_diaria = ft.Text(
        "R$ 0,00 / dia",
        size=13,
        weight=ft.FontWeight.W_600,
        color=T.TEXT_PRIMARY,
    )
    txt_detalhe_cdi = ft.Text(
        "Taxa CDI: 10,75% a.a. (102% = 10,97% a.a.)",
        size=11,
        color=T.TEXT_MUTED,
    )

    # Containers dinâmicos
    container_cards_ativos = ft.ResponsiveRow(spacing=14, run_spacing=14)
    container_grafico_bola_neve = ft.Container()
    container_grafico_historico = ft.Container()
    container_badges_gamificacao = ft.ResponsiveRow(spacing=10, run_spacing=10)
    container_historico_movimentacoes = ft.Column(spacing=8)

    spinner = ft.ProgressRing(color=T.PRIMARY, width=24, height=24, stroke_width=2.5, visible=False)

    # ── Função Central de Carregamento e Reatividade ──────────────────────────
    def carregar_dados(forcar: bool = False):
        spinner.visible = True
        try:
            page.update()
        except Exception:
            pass

        try:
            dados = db.obter_resumo_investimentos_patrimonio(forcar_atualizacao=forcar)
            estado["resumo"] = dados
            estado["cofres"] = dados.get("cofres", [])
            _renderizar_tudo()
        except Exception as ex:
            print(f"[ERRO] carregar_dados investimentos: {ex}")
            mostrar_feedback(page, f"Erro ao carregar investimentos: {ex}", "erro")
        finally:
            spinner.visible = False
            estado["carregando"] = False
            try:
                page.update()
            except Exception:
                pass

    def _renderizar_tudo():
        res = estado.get("resumo") or {}
        patr = float(res.get("patrimonio_total", 0.0) or 0.0)
        suor = float(res.get("total_aportado_liquido", 0.0) or 0.0)
        juros = float(res.get("total_rendimentos", 0.0) or 0.0)
        lucro_p = float(res.get("lucro_pct", 0.0) or 0.0)
        r_mes = float(res.get("renda_mensal_estimada", 0.0) or 0.0)
        r_dia = float(res.get("renda_diaria_estimada", 0.0) or 0.0)
        taxa_cdi = float(res.get("taxa_cdi_anual", 10.75) or 10.75)
        cdi_efet = round(taxa_cdi * 1.02, 2)

        # Atualiza KPIs
        txt_patrimonio_total.value = formatar_moeda(patr)
        txt_meu_suor.value = formatar_moeda(suor)
        txt_juros_ganhos.value = formatar_moeda(juros)
        txt_lucro_pct.value = f"+{lucro_p:.2f}%".replace(".", ",") if lucro_p >= 0 else f"{lucro_p:.2f}%".replace(".", ",")

        # Barra proporcional Suor vs Juros
        soma_total_base = suor + juros
        if soma_total_base > 0:
            pct_juros = juros / soma_total_base
            pb_suor_vs_juros.value = pct_juros
        else:
            pb_suor_vs_juros.value = 0.0

        txt_renda_mensal.value = f"{formatar_moeda(r_mes)} / mês"
        txt_renda_diaria.value = f"{formatar_moeda(r_dia)} / dia"
        txt_detalhe_cdi.value = f"CDI Base: {taxa_cdi:.2f}% a.a. · Ativo (102%): {cdi_efet:.2f}% a.a."

        # Renderiza Ativos
        _renderizar_cards_ativos()

        # Renderiza Gráficos
        _renderizar_grafico_bola_neve()
        _renderizar_grafico_historico_mensal()

        # Renderiza Badges
        _renderizar_badges()

        # Renderiza Histórico
        _renderizar_historico_movimentacoes()

    # ── Cards dos Ativos (Porquinho e 102% CDI) ───────────────────────────────
    def _renderizar_cards_ativos():
        cofres = estado.get("cofres", [])
        controls_cards = []

        for c in cofres:
            cid = c["id"]
            nome = c["nome"]
            tipo = c["tipo"]
            cor = c.get("cor") or (COR_PORQUINHO if tipo == "reserva_emergencia" else COR_CDI)
            saldo = float(c.get("saldo_atual", 0.0) or 0.0)
            tot_ap = float(c.get("total_aportado", 0.0) or 0.0)
            tot_resg = float(c.get("total_resgatado", 0.0) or 0.0)
            ap_liq = max(0.0, tot_ap - tot_resg)
            tot_rend = float(c.get("total_rendimentos", 0.0) or 0.0)
            meta = float(c.get("meta_valor", 0.0) or 0.0)
            pct_cdi = float(c.get("percentual_cdi", 102.0) or 102.0)

            # Ícone específico
            if tipo == "reserva_emergencia":
                icone_d = ft.Icons.SAVINGS_ROUNDED
                sub_rotulo = "🛡️ Reserva de Emergência · Liquidez Imediata"
            elif tipo == "renda_fixa":
                icone_d = ft.Icons.ROCKET_LAUNCH_ROUNDED
                sub_rotulo = f"📈 {pct_cdi:.0f}% do CDI · Acumulação & Juros Compostos"
            else:
                icone_d = ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED
                sub_rotulo = "💼 Cofrinho Personalizado"

            # Barra de meta (para reserva ou outros com meta > 0)
            progresso_meta = min(1.0, saldo / meta) if meta > 0 else 0.0
            pct_meta_txt = f"{(progresso_meta * 100):.1f}%".replace(".", ",")

            meta_section = ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Meta da Reserva", size=11, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                            ft.Row(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Text(f"{formatar_moeda(saldo)} de {formatar_moeda(meta)} ({pct_meta_txt})", size=11, color=cor, weight=ft.FontWeight.BOLD),
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_ROUNDED,
                                        icon_size=13,
                                        icon_color=T.TEXT_MUTED,
                                        tooltip="Editar meta da reserva",
                                        padding=0,
                                        width=20,
                                        height=20,
                                        on_click=lambda _, cf=c: _abrir_modal_editar_meta(cf),
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.ProgressBar(
                        value=progresso_meta,
                        color=cor,
                        bgcolor=f"{cor}22",
                        height=8,
                        border_radius=4,
                    ),
                ],
            ) if meta > 0 else ft.Container()

            # Lucro do ativo
            lucro_ativo = round((tot_rend / ap_liq * 100), 1) if ap_liq > 0 else 0.0

            # Card Individual
            card_ativo = ft.Container(
                col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
                padding=pad(all_=18),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(1.2, f"{cor}50"),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        # Cabeçalho do Card
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=10,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Container(
                                            padding=pad(all_=10),
                                            bgcolor=f"{cor}18",
                                            border_radius=12,
                                            border=borda(1, f"{cor}40"),
                                            content=ft.Icon(icone_d, color=cor, size=24),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            controls=[
                                                ft.Text(nome, size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                                ft.Text(sub_rotulo, size=11, color=T.TEXT_MUTED),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Container(
                                    padding=pad(h=8, v=4),
                                    bgcolor=f"{cor}15",
                                    border_radius=8,
                                    border=borda(1, f"{cor}30"),
                                    content=ft.Text(f"+{lucro_ativo}% lucro", size=11, weight=ft.FontWeight.BOLD, color=cor),
                                ),
                            ],
                        ),

                        # Saldo Atual em Destaque
                        ft.Container(
                            padding=pad(h=14, v=12),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=12,
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text("Saldo Acumulado", size=11, color=T.TEXT_MUTED),
                                            ft.Text(formatar_moeda(saldo), size=22, weight=ft.FontWeight.BOLD, color=cor),
                                        ],
                                    ),
                                    ft.Column(
                                        horizontal_alignment=ft.CrossAxisAlignment.END,
                                        spacing=2,
                                        controls=[
                                            ft.Text(f"Aportes: {formatar_moeda(ap_liq)}", size=11, color=T.TEXT_MUTED),
                                            ft.Text(f"Juros: +{formatar_moeda(tot_rend)}", size=11, color=cor, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                ],
                            ),
                        ),

                        # Meta (se houver)
                        meta_section,

                        # Botões Rápidos de Ação
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(
                                    expand=True,
                                    padding=pad(v=10),
                                    bgcolor=cor,
                                    border_radius=10,
                                    ink=True,
                                    alignment=ft.Alignment(0, 0),
                                    on_click=lambda _, cf=c: _abrir_modal_aporte(cf),
                                    content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.ADD_ROUNDED, color=T.ON_NEON, size=16),
                                            ft.Text("Aportar", color=T.ON_NEON, size=12.5, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                ),
                                ft.Container(
                                    expand=True,
                                    padding=pad(v=10),
                                    bgcolor=f"{cor}18",
                                    border=borda(1, f"{cor}50"),
                                    border_radius=10,
                                    ink=True,
                                    alignment=ft.Alignment(0, 0),
                                    on_click=lambda _, cf=c: _abrir_modal_rendimento_duplo(cf),
                                    content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.TRENDING_UP_ROUNDED, color=cor, size=16),
                                            ft.Text("Rendimento / Saldo", color=cor, size=12, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                ),
                                ft.Container(
                                    padding=pad(h=12, v=10),
                                    bgcolor=T.SURFACE_ALT,
                                    border=borda(1, T.BORDER),
                                    border_radius=10,
                                    ink=True,
                                    tooltip="Resgatar para o caixa",
                                    on_click=lambda _, cf=c: _abrir_modal_resgate(cf),
                                    content=ft.Icon(ft.Icons.CALL_RECEIVED_ROUNDED, color=T.WARNING, size=16),
                                ),
                            ],
                        ),
                    ],
                ),
            )
            controls_cards.append(card_ativo)

        container_cards_ativos.controls = controls_cards

    # ── Gráfico 1: Evolução Patrimonial (Efeito Bola de Neve) ─────────────────
    def _renderizar_grafico_bola_neve():
        res = estado.get("resumo") or {}
        evol = res.get("evolucao_patrimonial") or []

        if not evol:
            container_grafico_bola_neve.content = ft.Container(
                padding=pad(all_=20),
                content=ft.Text("Sem histórico suficiente para exibir o gráfico de evolução.", color=T.TEXT_MUTED, size=12),
            )
            return

        max_valor = max([float(it.get("patrimonio_total", 0.0) or 0.0) for it in evol] + [100.0])
        ALTURA_MAX = 130

        colunas = []
        for it in evol:
            lbl = it["label"]
            tot = float(it.get("patrimonio_total", 0.0) or 0.0)
            ap = float(it.get("aporte_acumulado", 0.0) or 0.0)
            jr = float(it.get("rendimento_acumulado", 0.0) or 0.0)

            # Alturas proporcionais empilhadas
            h_tot = max(6, int((tot / max_valor) * ALTURA_MAX)) if tot > 0 else 4
            h_ap = max(3, int((ap / max_valor) * ALTURA_MAX)) if ap > 0 else 2
            h_jr = max(0, h_tot - h_ap)

            dica = (
                f"Período: {lbl}\n"
                f"Patrimônio: {formatar_moeda(tot)}\n"
                f"  • Aportes (Suor): {formatar_moeda(ap)}\n"
                f"  • Juros Ganhos: {formatar_moeda(jr)}"
            )

            colunas.append(
                ft.Container(
                    expand=True,
                    tooltip=dica,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Text(formatar_moeda(tot) if not mobile else f"{tot/1000:.1f}k", size=10, color=T.PRIMARY, weight=ft.FontWeight.BOLD),
                            # Barra Empilhada
                            ft.Container(
                                width=mobile and 22 or 32,
                                height=ALTURA_MAX,
                                alignment=ft.Alignment(0, 1),
                                content=ft.Column(
                                    spacing=0,
                                    alignment=ft.MainAxisAlignment.END,
                                    controls=[
                                        # Topo: Juros (Verde Neon)
                                        ft.Container(
                                            height=h_jr,
                                            width=mobile and 22 or 32,
                                            bgcolor=COR_JUROS,
                                            border_radius=ft.BorderRadius(top_left=6, top_right=6, bottom_left=0, bottom_right=0) if h_jr > 0 else None,
                                        ),
                                        # Base: Aportes (Índigo)
                                        ft.Container(
                                            height=h_ap,
                                            width=mobile and 22 or 32,
                                            bgcolor=COR_SUOR,
                                            border_radius=ft.BorderRadius(
                                                top_left=6 if h_jr <= 0 else 0,
                                                top_right=6 if h_jr <= 0 else 0,
                                                bottom_left=6,
                                                bottom_right=6,
                                            ),
                                        ),
                                    ],
                                ),
                            ),
                            ft.Text(lbl, size=11, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                        ],
                    ),
                )
            )

        container_grafico_bola_neve.content = ft.Container(
            padding=pad(all_=18),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(1, T.BORDER),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.SSID_CHART_ROUNDED, color=T.PRIMARY, size=20),
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text("O Efeito Bola de Neve (Evolução Patrimonial)", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                            ft.Text("A curva exponencial dos juros compostos descolando do seu esforço", size=11, color=T.TEXT_MUTED),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=12,
                                controls=[
                                    ft.Row(spacing=4, controls=[ft.Container(width=10, height=10, bgcolor=COR_SUOR, border_radius=2), ft.Text("Seu Suor (Aportes)", size=10, color=T.TEXT_MUTED)]),
                                    ft.Row(spacing=4, controls=[ft.Container(width=10, height=10, bgcolor=COR_JUROS, border_radius=2), ft.Text("Juros Compostos", size=10, color=COR_JUROS, weight=ft.FontWeight.BOLD)]),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        padding=pad(h=10, v=12),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=12,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            controls=colunas,
                        ),
                    ),
                ],
            ),
        )

    # ── Gráfico 2: Histórico de Rendimentos vs Aportes Mensais ────────────────
    def _renderizar_grafico_historico_mensal():
        res = estado.get("resumo") or {}
        hist = res.get("historico_mensal") or []

        if not hist:
            container_grafico_historico.content = ft.Container()
            return

        max_mes = max(
            [max(float(it.get("aportes", 0.0) or 0.0), float(it.get("rendimentos", 0.0) or 0.0)) for it in hist] + [50.0]
        )
        ALT_H = 110

        colunas_h = []
        for it in hist:
            lbl = it["label"]
            ap = float(it.get("aportes", 0.0) or 0.0)
            jr = float(it.get("rendimentos", 0.0) or 0.0)

            h_ap = max(3, int((ap / max_mes) * ALT_H)) if ap > 0 else 2
            h_jr = max(3, int((jr / max_mes) * ALT_H)) if jr > 0 else 2

            dica = f"{lbl}:\n• Aporte: {formatar_moeda(ap)}\n• Rendimento Ganho: {formatar_moeda(jr)}"

            colunas_h.append(
                ft.Container(
                    expand=True,
                    tooltip=dica,
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.CENTER,
                                vertical_alignment=ft.CrossAxisAlignment.END,
                                spacing=4,
                                height=ALT_H,
                                controls=[
                                    ft.Container(
                                        width=mobile and 10 or 14,
                                        height=h_ap,
                                        bgcolor=COR_SUOR,
                                        border_radius=ft.BorderRadius(top_left=4, top_right=4, bottom_left=0, bottom_right=0),
                                    ),
                                    ft.Container(
                                        width=mobile and 10 or 14,
                                        height=h_jr,
                                        bgcolor=COR_JUROS,
                                        border_radius=ft.BorderRadius(top_left=4, top_right=4, bottom_left=0, bottom_right=0),
                                    ),
                                ],
                            ),
                            ft.Text(lbl, size=11, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                        ],
                    ),
                )
            )

        container_grafico_historico.content = ft.Container(
            padding=pad(all_=18),
            bgcolor=T.SURFACE,
            border_radius=16,
            border=borda(1, T.BORDER),
            content=ft.Column(
                spacing=14,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.BAR_CHART_ROUNDED, color=COR_JUROS, size=20),
                                    ft.Column(
                                        spacing=2,
                                        controls=[
                                            ft.Text("Histórico Mensal: Aportes vs. Juros", size=14, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                                            ft.Text("Quanto saiu do seu bolso vs. quanto o dinheiro trabalhou para você", size=11, color=T.TEXT_MUTED),
                                        ],
                                    ),
                                ],
                            ),
                        ],
                    ),
                    ft.Container(
                        padding=pad(h=10, v=12),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=12,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.END,
                            controls=colunas_h,
                        ),
                    ),
                ],
            ),
        )

    # ── Gamificação: Badges de Marcos Atingidos ───────────────────────────────
    def _renderizar_badges():
        res = estado.get("resumo") or {}
        badges = res.get("badges") or []
        itens = []

        mapa_icones = {
            "emoji_events": ft.Icons.EMOJI_EVENTS_ROUNDED,
            "military_tech": ft.Icons.MILITARY_TECH_ROUNDED,
            "shield": ft.Icons.SHIELD_ROUNDED,
            "workspace_premium": ft.Icons.WORKSPACE_PREMIUM_ROUNDED,
            "local_fire_department": ft.Icons.LOCAL_FIRE_DEPARTMENT_ROUNDED,
            "auto_awesome": ft.Icons.AUTO_AWESOME_ROUNDED,
        }

        for b in badges:
            atingido = bool(b.get("atingido", False))
            cor_b = "#FBBF24" if atingido else T.TEXT_MUTED  # Dourado se ativo
            ic_data = mapa_icones.get(b.get("icone"), ft.Icons.STAR_ROUNDED)

            itens.append(
                ft.Container(
                    col={"xs": 6, "sm": 4, "md": 2, "lg": 2},
                    padding=pad(h=10, v=12),
                    bgcolor=f"{cor_b}14" if atingido else T.SURFACE_ALT,
                    border_radius=12,
                    border=borda(1.2, f"{cor_b}50" if atingido else T.BORDER),
                    tooltip=f"{b['titulo']}: {b['descricao']}",
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            ft.Icon(ic_data, color=cor_b, size=24),
                            ft.Text(b["titulo"], size=11.5, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY if atingido else T.TEXT_MUTED, text_align=ft.TextAlign.CENTER, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Container(
                                padding=pad(h=6, v=2),
                                bgcolor=f"{cor_b}20" if atingido else f"{T.BORDER}40",
                                border_radius=6,
                                content=ft.Text(
                                    "✨ CONQUISTADO" if atingido else b.get("meta_label", "Bloqueado"),
                                    size=9,
                                    weight=ft.FontWeight.BOLD,
                                    color=cor_b if atingido else T.TEXT_MUTED,
                                ),
                            ),
                        ],
                    ),
                )
            )

        container_badges_gamificacao.controls = itens

    # ── Histórico Recente de Movimentações ─────────────────────────────────────
    def _renderizar_historico_movimentacoes():
        res = estado.get("resumo") or {}
        movs = res.get("movimentacoes_recentes") or []

        if not movs:
            container_historico_movimentacoes.controls = [
                ft.Container(
                    padding=pad(all_=20),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text("Nenhuma movimentação registrada no cofre ainda. Faça seu 1º aporte acima!", color=T.TEXT_MUTED, size=12),
                )
            ]
            return

        linhas = []
        for m in movs:
            mid = m["id"]
            tp = m.get("tipo", "aporte")
            val = float(m.get("valor", 0.0) or 0.0)
            dt_s = formatar_data_br(m.get("data", ""))
            desc = m.get("descricao") or ("Aporte" if tp == "aporte" else "Rendimento" if tp == "rendimento" else "Resgate")
            cf_nome = m.get("cofre_nome", "Cofre")
            cf_cor = m.get("cofre_cor", COR_PORQUINHO)

            if tp == "aporte":
                icone_m = ft.Icons.ARROW_UPWARD_ROUNDED
                cor_m = COR_SUOR
                prefixo = "+"
                label_tp = "Aporte"
            elif tp == "rendimento":
                icone_m = ft.Icons.AUTO_AWESOME_ROUNDED
                cor_m = COR_JUROS
                prefixo = "+ "
                label_tp = "Rendimento"
            else:
                icone_m = ft.Icons.ARROW_DOWNWARD_ROUNDED
                cor_m = COR_RESGATE
                prefixo = "-"
                label_tp = "Resgate"

            def _excluir_mov(_e, mov_id=mid):
                _confirmar_exclusao_movimentacao(mov_id)

            linha = ft.Container(
                padding=pad(h=12, v=10),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    padding=pad(all_=8),
                                    bgcolor=f"{cor_m}18",
                                    border_radius=8,
                                    content=ft.Icon(icone_m, color=cor_m, size=16),
                                ),
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Row(
                                            spacing=6,
                                            tight=True,
                                            controls=[
                                                ft.Text(label_tp, size=12.5, weight=ft.FontWeight.BOLD, color=cor_m),
                                                ft.Container(
                                                    padding=pad(h=6, v=2),
                                                    bgcolor=f"{cf_cor}20",
                                                    border_radius=4,
                                                    content=ft.Text(cf_nome, size=10, color=cf_cor, weight=ft.FontWeight.W_600),
                                                ),
                                            ],
                                        ),
                                        ft.Text(f"{dt_s} · {desc}", size=11, color=T.TEXT_MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=6,
                            tight=True,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(f"{prefixo}{formatar_moeda(val)}", size=13, weight=ft.FontWeight.BOLD, color=cor_m),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                    icon_color=T.TEXT_MUTED,
                                    icon_size=16,
                                    tooltip="Excluir movimentação",
                                    on_click=_excluir_mov,
                                ),
                            ],
                        ),
                    ],
                ),
            )
            linhas.append(linha)

        container_historico_movimentacoes.controls = linhas

    def _confirmar_exclusao_movimentacao(mov_id: str):
        def _executar(_):
            fechar_dialogo(page, dlg)
            try:
                db.excluir_movimentacao_cofre(mov_id)
                mostrar_feedback(page, "Movimentação excluída e saldos recalculados!", "sucesso")
                carregar_dados(forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao excluir: {ex}", "erro")

        dlg = ft.AlertDialog(
            title=ft.Text("Excluir Movimentação?", color=T.TEXT_PRIMARY),
            content=ft.Text("O saldo do cofre será recalculado atomicamente.", color=T.TEXT_MUTED, size=13),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dlg)),
                ft.FilledButton("Excluir", style=ft.ButtonStyle(bgcolor=T.DESPESA, color=T.TEXT_PRIMARY), on_click=_executar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dlg)

    # ── MODAL DE NOVO APORTE ──────────────────────────────────────────────────
    def _abrir_modal_aporte(cofre_alvo: dict | None = None, valor_predefinido: float = 0.0):
        cofres = estado.get("cofres", [])
        if not cofres:
            mostrar_feedback(page, "Nenhum cofre disponível.", "alerta")
            return

        cid_inicial = cofre_alvo["id"] if cofre_alvo else cofres[0]["id"]
        cofre_sel_ref = [next((c for c in cofres if c["id"] == cid_inicial), cofres[0])]

        contas = []
        try:
            contas = db.listar_contas()
        except Exception:
            pass

        txt_valor = ft.TextField(
            label="Valor do Aporte (R$)",
            value=formatar_moeda_input(valor_predefinido) if valor_predefinido > 0 else "",
            hint_text="Ex: 500,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            **T.campo_estilo(),
            autofocus=True,
        )

        dt_sel_ref = [date.today().isoformat()]
        btn_data = ft.OutlinedButton(
            content=ft.Text(formatar_data_br(dt_sel_ref[0])),
            icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
            style=ft.ButtonStyle(color=T.TEXT_PRIMARY),
            on_click=lambda _: abrir_seletor_data_modal(page, dt_sel_ref[0], lambda nova_dt: _atualizar_data(nova_dt)),
        )

        def _atualizar_data(d_str):
            dt_sel_ref[0] = d_str
            btn_data.content = ft.Text(formatar_data_br(d_str))
            btn_data.update()

        txt_desc = ft.TextField(
            label="Descrição (Opcional)",
            hint_text="Ex: Aporte da sobra do mês",
            **T.campo_estilo(),
        )

        # Seleção de Cofre (Porquinho vs CDI vs outros)
        def _criar_opcoes_cofres():
            chips = []
            for c in cofres:
                ativo = c["id"] == cofre_sel_ref[0]["id"]
                cor_c = c.get("cor") or COR_PORQUINHO
                chips.append(
                    ft.Container(
                        padding=pad(h=12, v=8),
                        border_radius=10,
                        bgcolor=f"{cor_c}25" if ativo else T.SURFACE_ALT,
                        border=borda(1.2, cor_c if ativo else T.BORDER),
                        ink=True,
                        on_click=lambda _, cf=c: _selecionar_cofre(cf),
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.SAVINGS_ROUNDED if c["tipo"] == "reserva_emergencia" else ft.Icons.ROCKET_LAUNCH_ROUNDED, color=cor_c, size=15),
                                ft.Text(c["nome"].split("(")[0].strip(), size=12, weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.NORMAL, color=T.TEXT_PRIMARY),
                            ],
                        ),
                    )
                )
            return chips

        row_cofres = ft.Row(spacing=8, wrap=True, controls=_criar_opcoes_cofres())

        def _selecionar_cofre(cf):
            cofre_sel_ref[0] = cf
            row_cofres.controls = _criar_opcoes_cofres()
            row_cofres.update()

        # Opcional: debitar de uma conta bancária
        sw_debitar_conta = ft.Switch(value=False, active_color=T.PRIMARY)
        dropdown_conta = ft.Dropdown(
            label="Conta Bancária de Origem",
            options=[ft.dropdown.Option(c["id"], c["nome"]) for c in contas],
            value=contas[0]["id"] if contas else None,
            visible=False,
            **T.dropdown_estilo(),
        )

        def _toggle_debitar(_):
            dropdown_conta.visible = sw_debitar_conta.value
            dropdown_conta.update()

        sw_debitar_conta.on_change = _toggle_debitar

        def _salvar_aporte(_):
            val = parse_moeda_seguro(txt_valor.value)
            if val <= 0:
                mostrar_feedback(page, "Informe um valor válido para o aporte.", "alerta")
                return

            fechar_dialogo(page, dlg)
            try:
                db.registrar_aporte_cofre(
                    cofre_id=cofre_sel_ref[0]["id"],
                    valor=val,
                    data=dt_sel_ref[0],
                    descricao=txt_desc.value.strip(),
                    conta_origem_id=dropdown_conta.value if sw_debitar_conta.value else None,
                    lancar_no_extrato=sw_debitar_conta.value,
                )
                mostrar_feedback(page, f"Aporte de {formatar_moeda(val)} registrado com sucesso!", "sucesso")
                carregar_dados(forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao registrar aporte: {ex}", "erro")

        dlg = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.ADD_CIRCLE_ROUNDED, color=T.PRIMARY, size=24),
                    ft.Text("Novo Aporte no Cofre", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ],
            ),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Text("Escolha o cofre de destino:", size=12, color=T.TEXT_MUTED),
                        row_cofres,
                        txt_valor,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Data do Aporte:", size=12, color=T.TEXT_MUTED),
                                btn_data,
                            ],
                        ),
                        txt_desc,
                        ft.Divider(color=T.BORDER, height=1),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Debitar da conta bancária?", size=12, color=T.TEXT_PRIMARY),
                                sw_debitar_conta,
                            ],
                        ),
                        dropdown_conta,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dlg)),
                T.botao_primario("Confirmar Aporte", on_click=_salvar_aporte),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dlg)

    # ── MODAL DUPLO: RENDIMENTO DIRETO VS AJUSTE INTELIGENTE ─────────────────
    def _abrir_modal_rendimento_duplo(cofre_alvo: dict):
        aba_ativa_ref = ["saldo_inteligente"]  # Padrão: Opção B (Mais rápida e inteligente)

        saldo_atual_cofre = float(cofre_alvo.get("saldo_atual", 0.0) or 0.0)
        cid = cofre_alvo["id"]
        cor_c = cofre_alvo.get("cor") or COR_CDI

        # ── Componentes Opção B: Ajuste por Saldo Atual (Inteligente) ────────
        txt_saldo_banco = ft.TextField(
            label="Saldo Líquido que está no Banco Hoje (R$)",
            hint_text=f"Ex: {formatar_moeda_input(saldo_atual_cofre + 50)}",
            keyboard_type=ft.KeyboardType.NUMBER,
            **T.campo_estilo(),
            autofocus=True,
        )

        txt_preview_diferenca = ft.Text(
            f"Saldo atual no DemBase: {formatar_moeda(saldo_atual_cofre)}\nDigite o saldo atual do app do seu banco para calcular o rendimento automático.",
            size=12,
            color=T.TEXT_MUTED,
        )

        def _recalcular_preview_diferenca(_):
            val_digitado = parse_moeda_seguro(txt_saldo_banco.value)
            diff = round(val_digitado - saldo_atual_cofre, 2)
            if abs(diff) < 0.005:
                txt_preview_diferenca.value = f"Saldo atual: {formatar_moeda(saldo_atual_cofre)}\nSem alteração no saldo."
                txt_preview_diferenca.color = T.TEXT_MUTED
            elif diff > 0:
                txt_preview_diferenca.value = (
                    f"🎉 Rendimento Identificado: +{formatar_moeda(diff)}!\n"
                    f"O saldo passará de {formatar_moeda(saldo_atual_cofre)} para {formatar_moeda(val_digitado)}."
                )
                txt_preview_diferenca.color = COR_JUROS
            else:
                txt_preview_diferenca.value = (
                    f"⚠️ Saldo digitado é menor (-{formatar_moeda(abs(diff))}).\n"
                    f"Será registrado como ajuste/resgate de saldo."
                )
                txt_preview_diferenca.color = T.WARNING
            txt_preview_diferenca.update()

        txt_saldo_banco.on_change = _recalcular_preview_diferenca

        # ── Componentes Opção A: Lançar Rendimento Direto ─────────────────────
        txt_valor_rendimento = ft.TextField(
            label="Valor que Rendeu (R$)",
            hint_text="Ex: 38,50",
            keyboard_type=ft.KeyboardType.NUMBER,
            **T.campo_estilo(),
        )

        dt_sel_rend_ref = [date.today().isoformat()]
        btn_data_rend = ft.OutlinedButton(
            content=ft.Text(formatar_data_br(dt_sel_rend_ref[0])),
            icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
            style=ft.ButtonStyle(color=T.TEXT_PRIMARY),
            on_click=lambda _: abrir_seletor_data_modal(page, dt_sel_rend_ref[0], lambda nova_dt: _atualizar_dt_rend(nova_dt)),
        )

        def _atualizar_dt_rend(d_str):
            dt_sel_rend_ref[0] = d_str
            btn_data_rend.content = ft.Text(formatar_data_br(d_str))
            btn_data_rend.update()

        txt_desc_rend = ft.TextField(
            label="Descrição (Opcional)",
            hint_text="Ex: Rendimento CDI Novembro",
            **T.campo_estilo(),
        )

        # Alternador Visual de Abas (Opção A vs Opção B)
        container_conteudo_aba = ft.Column(spacing=12)

        def _construir_conteudo_aba():
            if aba_ativa_ref[0] == "saldo_inteligente":
                return ft.Column(
                    spacing=12,
                    controls=[
                        ft.Container(
                            padding=pad(h=12, v=10),
                            bgcolor=f"{COR_JUROS}15",
                            border=borda(1, f"{COR_JUROS}40"),
                            border_radius=10,
                            content=ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=COR_JUROS, size=18),
                                    ft.Text(
                                        "Basta olhar o saldo líquido hoje no app do seu banco e digitar abaixo. "
                                        "O DemBase compara com o saldo anterior e grava os juros ganhos automaticamente!",
                                        size=11.5,
                                        color=T.TEXT_PRIMARY,
                                        expand=True,
                                    ),
                                ],
                            ),
                        ),
                        txt_saldo_banco,
                        txt_preview_diferenca,
                    ],
                )
            else:
                return ft.Column(
                    spacing=12,
                    controls=[
                        ft.Container(
                            padding=pad(h=12, v=10),
                            bgcolor=T.SURFACE_ALT,
                            border=borda(1, T.BORDER),
                            border_radius=10,
                            content=ft.Row(
                                spacing=8,
                                controls=[
                                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=T.INFO, size=18),
                                    ft.Text(
                                        "Informe o valor exato que rendeu no dia ou no fechamento do mês.",
                                        size=11.5,
                                        color=T.TEXT_PRIMARY,
                                        expand=True,
                                    ),
                                ],
                            ),
                        ),
                        txt_valor_rendimento,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Data do Rendimento:", size=12, color=T.TEXT_MUTED),
                                btn_data_rend,
                            ],
                        ),
                        txt_desc_rend,
                    ],
                )

        btn_aba_inteligente = ft.Container()
        btn_aba_direta = ft.Container()

        def _atualizar_botoes_aba():
            ativo_int = aba_ativa_ref[0] == "saldo_inteligente"
            btn_aba_inteligente.bgcolor = f"{COR_JUROS}25" if ativo_int else T.SURFACE_ALT
            btn_aba_inteligente.border = borda(1.2, COR_JUROS if ativo_int else T.BORDER)
            btn_aba_direta.bgcolor = f"{COR_JUROS}25" if not ativo_int else T.SURFACE_ALT
            btn_aba_direta.border = borda(1.2, COR_JUROS if not ativo_int else T.BORDER)

        def _selecionar_aba(aba_nome):
            aba_ativa_ref[0] = aba_nome
            _atualizar_botoes_aba()
            container_conteudo_aba.controls = [_construir_conteudo_aba()]
            dlg.update()

        btn_aba_inteligente = ft.Container(
            expand=True,
            padding=pad(v=8),
            border_radius=10,
            ink=True,
            alignment=ft.Alignment(0, 0),
            on_click=lambda _: _selecionar_aba("saldo_inteligente"),
            content=ft.Text("⚡ Ajuste Inteligente por Saldo", size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
        )
        btn_aba_direta = ft.Container(
            expand=True,
            padding=pad(v=8),
            border_radius=10,
            ink=True,
            alignment=ft.Alignment(0, 0),
            on_click=lambda _: _selecionar_aba("direto"),
            content=ft.Text("✍️ Lançar Rendimento Direto", size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
        )
        _atualizar_botoes_aba()

        container_conteudo_aba.controls = [_construir_conteudo_aba()]

        def _confirmar_rendimento(_):
            fechar_dialogo(page, dlg)
            try:
                if aba_ativa_ref[0] == "saldo_inteligente":
                    novo_s = parse_moeda_seguro(txt_saldo_banco.value)
                    if novo_s <= 0:
                        mostrar_feedback(page, "Informe o saldo atual exibido no banco.", "alerta")
                        return
                    res = db.registrar_ajuste_por_saldo_atual(
                        cofre_id=cid,
                        saldo_digitado=novo_s,
                    )
                    mostrar_feedback(page, res.get("mensagem", "Saldo atualizado!"), "sucesso")
                else:
                    v_rend = parse_moeda_seguro(txt_valor_rendimento.value)
                    if v_rend <= 0:
                        mostrar_feedback(page, "Informe um valor de rendimento válido.", "alerta")
                        return
                    db.registrar_rendimento_direto(
                        cofre_id=cid,
                        valor=v_rend,
                        data=dt_sel_rend_ref[0],
                        descricao=txt_desc_rend.value.strip(),
                    )
                    mostrar_feedback(page, f"Rendimento de {formatar_moeda(v_rend)} registrado com sucesso!", "sucesso")

                carregar_dados(forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao registrar rendimento: {ex}", "erro")

        dlg = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.TRENDING_UP_ROUNDED, color=COR_JUROS, size=24),
                    ft.Text(f"Atualizar Rendimento · {cofre_alvo['nome']}", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ],
            ),
            content=ft.Container(
                width=450,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        # Seletor de Opção A vs Opção B
                        ft.Row(spacing=8, controls=[btn_aba_inteligente, btn_aba_direta]),
                        ft.Divider(color=T.BORDER, height=1),
                        container_conteudo_aba,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dlg)),
                T.botao_primario("Confirmar Atualização", on_click=_confirmar_rendimento),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dlg)

    # ── MODAL DE RESGATE ──────────────────────────────────────────────────────
    def _abrir_modal_resgate(cofre_alvo: dict):
        cid = cofre_alvo["id"]
        saldo_disp = float(cofre_alvo.get("saldo_atual", 0.0) or 0.0)
        if saldo_disp <= 0:
            mostrar_feedback(page, "Este cofre não possui saldo disponível para resgate.", "alerta")
            return

        contas = []
        try:
            contas = db.listar_contas()
        except Exception:
            pass

        txt_valor_resg = ft.TextField(
            label=f"Valor a Resgatar (Máx: {formatar_moeda(saldo_disp)})",
            hint_text=f"Ex: {formatar_moeda_input(saldo_disp)}",
            keyboard_type=ft.KeyboardType.NUMBER,
            **T.campo_estilo(),
            autofocus=True,
        )

        dt_sel_resg_ref = [date.today().isoformat()]
        btn_dt_resg = ft.OutlinedButton(
            content=ft.Text(formatar_data_br(dt_sel_resg_ref[0])),
            icon=ft.Icons.CALENDAR_MONTH_ROUNDED,
            style=ft.ButtonStyle(color=T.TEXT_PRIMARY),
            on_click=lambda _: abrir_seletor_data_modal(page, dt_sel_resg_ref[0], lambda nova_dt: _atualizar_dt_resg(nova_dt)),
        )

        def _atualizar_dt_resg(d_str):
            dt_sel_resg_ref[0] = d_str
            btn_dt_resg.content = ft.Text(formatar_data_br(d_str))
            btn_dt_resg.update()

        sw_creditar_conta = ft.Switch(value=False, active_color=T.PRIMARY)
        dropdown_conta_resg = ft.Dropdown(
            label="Conta Bancária de Destino",
            options=[ft.dropdown.Option(c["id"], c["nome"]) for c in contas],
            value=contas[0]["id"] if contas else None,
            visible=False,
            **T.dropdown_estilo(),
        )

        def _toggle_creditar(_):
            dropdown_conta_resg.visible = sw_creditar_conta.value
            dropdown_conta_resg.update()

        sw_creditar_conta.on_change = _toggle_creditar

        def _executar_resgate(_):
            val = parse_moeda_seguro(txt_valor_resg.value)
            if val <= 0:
                mostrar_feedback(page, "Informe um valor válido para resgate.", "alerta")
                return
            if val > (saldo_disp + 0.005):
                mostrar_feedback(page, f"Valor excede o saldo disponível ({formatar_moeda(saldo_disp)}).", "erro")
                return

            fechar_dialogo(page, dlg)
            try:
                db.registrar_resgate_cofre(
                    cofre_id=cid,
                    valor=val,
                    data=dt_sel_resg_ref[0],
                    conta_destino_id=dropdown_conta_resg.value if sw_creditar_conta.value else None,
                    lancar_no_extrato=sw_creditar_conta.value,
                )
                mostrar_feedback(page, f"Resgate de {formatar_moeda(val)} realizado com sucesso!", "sucesso")
                carregar_dados(forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao realizar resgate: {ex}", "erro")

        dlg = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.CALL_RECEIVED_ROUNDED, color=T.WARNING, size=24),
                    ft.Text(f"Resgatar · {cofre_alvo['nome']}", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ],
            ),
            content=ft.Container(
                width=420,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    controls=[
                        ft.Text(f"Saldo atual disponível: {formatar_moeda(saldo_disp)}", size=12, color=T.TEXT_MUTED),
                        txt_valor_resg,
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Data do Resgate:", size=12, color=T.TEXT_MUTED),
                                btn_dt_resg,
                            ],
                        ),
                        ft.Divider(color=T.BORDER, height=1),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Text("Creditar em conta bancária?", size=12, color=T.TEXT_PRIMARY),
                                sw_creditar_conta,
                            ],
                        ),
                        dropdown_conta_resg,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dlg)),
                T.botao_primario("Confirmar Resgate", on_click=_executar_resgate),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dlg)

    # ── MODAL DE EDITAR META DA RESERVA ───────────────────────────────────────
    def _abrir_modal_editar_meta(cofre_alvo: dict):
        cid = cofre_alvo["id"]
        meta_atual = float(cofre_alvo.get("meta_valor", 0.0) or 0.0)

        txt_meta = ft.TextField(
            label="Meta da Reserva de Emergência (R$)",
            value=formatar_moeda_input(meta_atual),
            keyboard_type=ft.KeyboardType.NUMBER,
            **T.campo_estilo(),
            autofocus=True,
        )

        def _salvar_meta(_):
            n_meta = parse_moeda_seguro(txt_meta.value)
            fechar_dialogo(page, dlg)
            try:
                db.atualizar_cofre_investimento(cid, {"meta_valor": n_meta})
                mostrar_feedback(page, f"Meta atualizada para {formatar_moeda(n_meta)}!", "sucesso")
                carregar_dados(forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao atualizar meta: {ex}", "erro")

        dlg = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.TRACK_CHANGES_ROUNDED, color=COR_PORQUINHO, size=24),
                    ft.Text("Meta da Reserva de Emergência", size=15, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ],
            ),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Text("Defina o valor alvo que você deseja atingir para sua segurança total (ex: 6 meses do seu custo de vida).", size=12, color=T.TEXT_MUTED),
                        txt_meta,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dlg)),
                T.botao_primario("Salvar Meta", on_click=_salvar_meta),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dlg)

    # ── MODAL DE CONFIGURAÇÃO DO CDI ──────────────────────────────────────────
    def _abrir_modal_config_cdi(_=None):
        res = estado.get("resumo") or {}
        cdi_atual = float(res.get("taxa_cdi_anual", 10.75) or 10.75)

        txt_cdi = ft.TextField(
            label="Taxa CDI Anual Vigente (% a.a.)",
            value=f"{cdi_atual:.2f}".replace(".", ","),
            hint_text="Ex: 10,75",
            keyboard_type=ft.KeyboardType.NUMBER,
            **T.campo_estilo(),
            autofocus=True,
        )

        def _salvar_cdi(_):
            s_val = txt_cdi.value.replace("%", "").strip()
            val_cdi = parse_moeda_seguro(s_val)
            if val_cdi <= 0 or val_cdi > 100:
                mostrar_feedback(page, "Informe uma taxa CDI válida entre 1% e 50%.", "alerta")
                return

            fechar_dialogo(page, dlg)
            try:
                db.salvar_config_taxa_cdi(val_cdi)
                mostrar_feedback(page, f"Taxa CDI definida em {val_cdi:.2f}% a.a.!", "sucesso")
                carregar_dados(forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar CDI: {ex}", "erro")

        dlg = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.SETTINGS_ROUNDED, color=COR_RENDA_PAS, size=24),
                    ft.Text("Configurar Taxa do CDI", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                ],
            ),
            content=ft.Container(
                width=380,
                content=ft.Column(
                    spacing=10,
                    tight=True,
                    controls=[
                        ft.Text(
                            "O DemBase utiliza a taxa CDI anual para projetar os rendimentos passivos diários e mensais do seu patrimônio acumulado.",
                            size=12,
                            color=T.TEXT_MUTED,
                        ),
                        txt_cdi,
                    ],
                ),
            ),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dlg)),
                T.botao_primario("Salvar Taxa", on_click=_salvar_cdi),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, dlg)

    # ── Construção do Header de Impacto (Efeito Bola de Neve) ─────────────────
    header_impacto = ft.Container(
        padding=pad(all_=20 if mobile else 24),
        bgcolor=T.SURFACE,
        border_radius=18,
        border=borda(1.5, f"{T.PRIMARY}50"),
        content=ft.Column(
            spacing=18,
            controls=[
                # Topo: Rótulo e Botão de Aporte Geral
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=10,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Container(
                                    padding=pad(all_=10),
                                    bgcolor=f"{T.PRIMARY}18",
                                    border_radius=12,
                                    border=borda(1, f"{T.PRIMARY}40"),
                                    content=ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.PRIMARY, size=26),
                                ),
                                ft.Column(
                                    spacing=2,
                                    controls=[
                                        ft.Text("MEU COFRE · PATRIMÔNIO ACUMULADO", size=11.5, weight=ft.FontWeight.BOLD, color=T.PRIMARY),
                                        txt_sub_patrimonio,
                                    ],
                                ),
                            ],
                        ),
                        ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                spinner,
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH_ROUNDED,
                                    icon_color=T.TEXT_MUTED,
                                    tooltip="Recarregar dados",
                                    on_click=lambda _: carregar_dados(forcar=True),
                                ),
                                T.botao_primario(
                                    "+ Novo Aporte",
                                    on_click=lambda _: _abrir_modal_aporte(),
                                    icone=ft.Icons.ADD_ROUNDED,
                                ),
                            ],
                        ),
                    ],
                ),

                # Valor Gigante do Patrimônio Total
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        txt_patrimonio_total,
                        ft.Container(
                            padding=pad(h=12, v=6),
                            bgcolor=f"{COR_JUROS}18",
                            border_radius=10,
                            border=borda(1, f"{COR_JUROS}40"),
                            content=ft.Row(
                                spacing=4,
                                tight=True,
                                controls=[
                                    ft.Icon(ft.Icons.TRENDING_UP_ROUNDED, color=COR_JUROS, size=16),
                                    txt_lucro_pct,
                                    ft.Text("de lucro geral", size=12, color=T.TEXT_PRIMARY),
                                ],
                            ),
                        ),
                    ],
                ),

                ft.Divider(color=T.BORDER, height=1),

                # Grid com os 2 Cards Centrais: Meu Suor vs Juros & Máquina de Renda Passiva
                ft.ResponsiveRow(
                    spacing=14,
                    run_spacing=14,
                    controls=[
                        # Card: Meu Suor vs Juros
                        ft.Container(
                            col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
                            padding=pad(all_=14),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=14,
                            content=ft.Column(
                                spacing=8,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text("MEU SUOR vs. JUROS COMPOSTOS", size=11, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                                            ft.Text("Proporção", size=11, color=T.TEXT_MUTED),
                                        ],
                                    ),
                                    pb_suor_vs_juros,
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Column(
                                                spacing=2,
                                                controls=[
                                                    ft.Row(spacing=4, controls=[ft.Container(width=8, height=8, bgcolor=COR_SUOR, border_radius=2), ft.Text("Total Aportado (Suor)", size=10.5, color=T.TEXT_MUTED)]),
                                                    txt_meu_suor,
                                                ],
                                            ),
                                            ft.Column(
                                                horizontal_alignment=ft.CrossAxisAlignment.END,
                                                spacing=2,
                                                controls=[
                                                    ft.Row(spacing=4, controls=[ft.Container(width=8, height=8, bgcolor=COR_JUROS, border_radius=2), ft.Text("Juros Ganhos (Lucro)", size=10.5, color=COR_JUROS, weight=ft.FontWeight.BOLD)]),
                                                    txt_juros_ganhos,
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                        ),

                        # Card: Máquina de Renda Passiva
                        ft.Container(
                            col={"xs": 12, "sm": 12, "md": 6, "lg": 6},
                            padding=pad(all_=14),
                            bgcolor=T.SURFACE_ALT,
                            border_radius=14,
                            content=ft.Column(
                                spacing=8,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Row(
                                                spacing=6,
                                                tight=True,
                                                controls=[
                                                    ft.Icon(ft.Icons.ELECTRIC_BOLT_ROUNDED, color=COR_RENDA_PAS, size=16),
                                                    ft.Text("MÁQUINA DE RENDA PASSIVA", size=11, weight=ft.FontWeight.BOLD, color=COR_RENDA_PAS),
                                                ],
                                            ),
                                            ft.IconButton(
                                                icon=ft.Icons.SETTINGS_ROUNDED,
                                                icon_size=15,
                                                icon_color=T.TEXT_MUTED,
                                                tooltip="Configurar taxa CDI",
                                                padding=0,
                                                width=22,
                                                height=22,
                                                on_click=_abrir_modal_config_cdi,
                                            ),
                                        ],
                                    ),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                        controls=[
                                            txt_renda_mensal,
                                            ft.Container(
                                                padding=pad(h=8, v=4),
                                                bgcolor=f"{COR_RENDA_PAS}18",
                                                border_radius=8,
                                                content=txt_renda_diaria,
                                            ),
                                        ],
                                    ),
                                    txt_detalhe_cdi,
                                ],
                            ),
                        ),
                    ],
                ),
            ],
        ),
    )

    # ── Montagem do Layout Completo ───────────────────────────────────────────
    conteudo_principal = ft.Column(
        spacing=20,
        controls=[
            header_impacto,

            # Seção: Cards dos Ativos
            ft.Column(
                spacing=10,
                controls=[
                    ft.Text("MEUS ATIVOS NO COFRE", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                    container_cards_ativos,
                ],
            ),

            # Seção: Gráficos Estimulantes (Evolução & Histórico)
            ft.Column(
                spacing=14,
                controls=[
                    container_grafico_bola_neve,
                    container_grafico_historico,
                ],
            ),

            # Seção: Gamificação e Marcos Atingidos
            ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.EMOJI_EVENTS_ROUNDED, color="#FBBF24", size=18),
                            ft.Text("CONQUISTAS E MARCOS PATRIMONIAIS", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ],
                    ),
                    container_badges_gamificacao,
                ],
            ),

            # Seção: Histórico Recente de Movimentações
            ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("HISTÓRICO RECENTE DE MOVIMENTAÇÕES", size=13, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                            ft.Text("Últimos lançamentos no cofre", size=11, color=T.TEXT_MUTED),
                        ],
                    ),
                    container_historico_movimentacoes,
                ],
            ),
        ],
    )

    # Carregamento inicial dos dados do cofre
    try:
        carregar_dados(forcar=False)
    except Exception as ex:
        print(f"[AVISO] Carregamento inicial investimentos: {ex}")

    view = criar_shell(
        page=page,
        rota_ativa=ROTA_INVESTIMENTOS,
        titulo="Meu Cofre · Investimentos",
        conteudo=conteudo_principal,
        mostrar_voltar=False,
    )
    return view



# =============================================================================
# MODAL DE APORTE DA SOBRA DO CAIXA LIVRE (INTEGRAÇÃO COM O DASHBOARD)
# =============================================================================

def abrir_modal_aporte_sobra_dashboard(
    page: ft.Page,
    valor_sugerido: float = 0.0,
    on_saved: callable = None,
):
    """
    Modal de Aporte da Sobra do Caixa Livre integrado com o Dashboard.
    Puxa o valor sugerido (ex: 70% da sobra destinada a investimento) e
    permite ao usuário alocar de forma prática e imediata entre o Porquinho
    (Reserva de Emergência) e a Renda Fixa (102% CDI).
    """
    cofres = db.listar_cofres_investimento()
    porquinho = next((c for c in cofres if c.get("tipo") == "reserva_emergencia"), None)
    cdi_cofre = next((c for c in cofres if c.get("tipo") == "renda_fixa"), None)

    if not porquinho or not cdi_cofre:
        db.garantir_cofres_padrao()
        cofres = db.listar_cofres_investimento(forcar_atualizacao=True)
        porquinho = next((c for c in cofres if c.get("tipo") == "reserva_emergencia"), cofres[0] if cofres else None)
        cdi_cofre = next((c for c in cofres if c.get("tipo") == "renda_fixa"), cofres[-1] if cofres else None)

    val_base = max(0.0, round(float(valor_sugerido or 0.0), 2))

    if porquinho and porquinho.get("meta_valor", 0) > 0 and porquinho.get("saldo_atual", 0) >= porquinho.get("meta_valor", 0):
        val_inicial_porquinho = 0.0
        val_inicial_cdi = val_base
    else:
        val_inicial_porquinho = round(val_base * 0.5, 2)
        val_inicial_cdi = round(val_base - val_inicial_porquinho, 2)

    txt_valor_total = ft.TextField(
        label="Valor Total a Guardar/Investir (R$)",
        value=formatar_moeda_input(val_base) if val_base > 0 else "",
        hint_text="Ex: 500,00",
        keyboard_type=ft.KeyboardType.NUMBER,
        **T.campo_estilo(),
    )

    txt_val_porquinho = ft.TextField(
        label="Para o Porquinho (Reserva de Emergência)",
        value=formatar_moeda_input(val_inicial_porquinho),
        hint_text="R$ 0,00",
        keyboard_type=ft.KeyboardType.NUMBER,
        **T.campo_estilo(),
    )

    txt_val_cdi = ft.TextField(
        label="Para a Renda Fixa (102% do CDI)",
        value=formatar_moeda_input(val_inicial_cdi),
        hint_text="R$ 0,00",
        keyboard_type=ft.KeyboardType.NUMBER,
        **T.campo_estilo(),
    )

    txt_conferencia = ft.Text(
        f"Total alocado: {formatar_moeda(val_base)}",
        size=12,
        color=T.PRIMARY,
        weight=ft.FontWeight.W_600,
    )

    def _conferir_soma(_=None):
        vp = parse_moeda_seguro(txt_val_porquinho.value)
        vc = parse_moeda_seguro(txt_val_cdi.value)
        soma = round(vp + vc, 2)
        v_tot = parse_moeda_seguro(txt_valor_total.value)
        diff = round(v_tot - soma, 2)
        if abs(diff) < 0.005:
            txt_conferencia.value = f"✓ Perfeito! 100% da sobra distribuída ({formatar_moeda(soma)})."
            txt_conferencia.color = T.PRIMARY
        elif diff > 0:
            txt_conferencia.value = f"Ainda falta distribuir {formatar_moeda(diff)} da sobra."
            txt_conferencia.color = T.WARNING
        else:
            txt_conferencia.value = f"Distribuição ultrapassou a sobra em {formatar_moeda(abs(diff))}."
            txt_conferencia.color = T.DESPESA
        try:
            txt_conferencia.update()
        except Exception:
            pass

    txt_val_porquinho.on_change = _conferir_soma
    txt_val_cdi.on_change = _conferir_soma

    def _ao_mudar_total(_):
        vt = parse_moeda_seguro(txt_valor_total.value)
        p1 = round(vt * 0.5, 2)
        p2 = round(vt - p1, 2)
        txt_val_porquinho.value = formatar_moeda_input(p1)
        txt_val_cdi.value = formatar_moeda_input(p2)
        txt_val_porquinho.update()
        txt_val_cdi.update()
        _conferir_soma()

    txt_valor_total.on_change = _ao_mudar_total

    def _aplicar_proporcao(pct_porquinho: float):
        vt = parse_moeda_seguro(txt_valor_total.value)
        if vt <= 0:
            return
        vp = round(vt * (pct_porquinho / 100.0), 2)
        vc = round(vt - vp, 2)
        txt_val_porquinho.value = formatar_moeda_input(vp)
        txt_val_cdi.value = formatar_moeda_input(vc)
        txt_val_porquinho.update()
        txt_val_cdi.update()
        _conferir_soma()

    btn_50_50 = ft.Container(
        padding=pad(h=8, v=6),
        bgcolor=T.SURFACE_ALT,
        border=borda(1, T.BORDER),
        border_radius=8,
        ink=True,
        on_click=lambda _: _aplicar_proporcao(50.0),
        content=ft.Text("50% / 50%", size=11, color=T.TEXT_PRIMARY, weight=ft.FontWeight.W_600),
    )
    btn_100_cdi = ft.Container(
        padding=pad(h=8, v=6),
        bgcolor=T.SURFACE_ALT,
        border=borda(1, T.BORDER),
        border_radius=8,
        ink=True,
        on_click=lambda _: _aplicar_proporcao(0.0),
        content=ft.Text("100% CDI", size=11, color=COR_CDI, weight=ft.FontWeight.W_600),
    )
    btn_100_porq = ft.Container(
        padding=pad(h=8, v=6),
        bgcolor=T.SURFACE_ALT,
        border=borda(1, T.BORDER),
        border_radius=8,
        ink=True,
        on_click=lambda _: _aplicar_proporcao(100.0),
        content=ft.Text("100% Porquinho", size=11, color=COR_PORQUINHO, weight=ft.FontWeight.W_600),
    )

    contas = []
    try:
        contas = db.listar_contas()
    except Exception:
        pass

    sw_debitar = ft.Switch(value=False, active_color=T.PRIMARY)
    dropdown_c = ft.Dropdown(
        label="Debitar da Conta Bancária",
        options=[ft.dropdown.Option(c["id"], c["nome"]) for c in contas],
        value=contas[0]["id"] if contas else None,
        visible=False,
        **T.dropdown_estilo(),
    )
    def _toggle_deb(_):
        dropdown_c.visible = sw_debitar.value
        dropdown_c.update()
    sw_debitar.on_change = _toggle_deb

    def _salvar(_):
        vp = parse_moeda_seguro(txt_val_porquinho.value)
        vc = parse_moeda_seguro(txt_val_cdi.value)
        if vp <= 0 and vc <= 0:
            mostrar_feedback(page, "Defina ao menos um valor para o Porquinho ou Renda Fixa.", "alerta")
            return

        fechar_dialogo(page, dlg)
        try:
            dt_hoje = date.today().isoformat()
            conta_id = dropdown_c.value if sw_debitar.value else None
            deb = sw_debitar.value

            msgs = []
            if vp > 0 and porquinho:
                db.registrar_aporte_cofre(
                    cofre_id=porquinho["id"],
                    valor=vp,
                    data=dt_hoje,
                    descricao="Aporte Sobra: Porquinho",
                    conta_origem_id=conta_id,
                    lancar_no_extrato=deb,
                )
                msgs.append(f"{formatar_moeda(vp)} no Porquinho")

            if vc > 0 and cdi_cofre:
                db.registrar_aporte_cofre(
                    cofre_id=cdi_cofre["id"],
                    valor=vc,
                    data=dt_hoje,
                    descricao="Aporte Sobra: 102% CDI",
                    conta_origem_id=conta_id,
                    lancar_no_extrato=deb,
                )
                msgs.append(f"{formatar_moeda(vc)} no 102% CDI")

            mostrar_feedback(page, f"🎉 Aporte realizado com sucesso: {' e '.join(msgs)}!", "sucesso")
            if callable(on_saved):
                on_saved()
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao realizar aporte da sobra: {ex}", "erro")

    dlg = ft.AlertDialog(
        title=ft.Row(
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.PRIMARY, size=24),
                ft.Text("Separar & Investir a Sobra do Caixa", size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
            ],
        ),
        content=ft.Container(
            width=460,
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    ft.Text(
                        "Distribua o valor separado da sua sobra entre sua Reserva de Emergência e sua Renda Fixa 102% CDI.",
                        size=12,
                        color=T.TEXT_MUTED,
                    ),
                    txt_valor_total,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text("Divisão rápida:", size=11, color=T.TEXT_MUTED),
                            ft.Row(spacing=6, controls=[btn_50_50, btn_100_cdi, btn_100_porq]),
                        ],
                    ),
                    txt_val_porquinho,
                    txt_val_cdi,
                    txt_conferencia,
                    ft.Divider(color=T.BORDER, height=1),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text("Debitar da conta bancária?", size=12, color=T.TEXT_PRIMARY),
                            sw_debitar,
                        ],
                    ),
                    dropdown_c,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, dlg)),
            T.botao_primario("Confirmar e Guardar", on_click=_salvar),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    )
    abrir_dialogo(page, dlg)
