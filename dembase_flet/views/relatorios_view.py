"""
=============================================================================
DemBase v3 — views/relatorios_view.py  (Flet 1.0.1)
Relatórios Financeiros: Categorias, Balanço Semestral e Regra 50/30/20.
Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
import flet as ft
from datetime import date
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, hoje
from views.shell_view import criar_shell, ROTA_RELATORIOS
import services.supabase_client as db


def criar_view_relatorios(page: ft.Page) -> ft.View:
    hoje_d = hoje()
    mes_sel = [hoje_d.month]
    ano_sel = [hoje_d.year]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    # ── KPIs Topo ─────────────────────────────────────────────────────────────
    txt_rec_mes      = ft.Text("R$ 0,00", color=T.RECEITA, size=18, weight=ft.FontWeight.BOLD)
    txt_desp_mes     = ft.Text("R$ 0,00", color=T.DESPESA, size=18, weight=ft.FontWeight.BOLD)
    txt_saldo_mes    = ft.Text("R$ 0,00", color=T.SALDO,   size=18, weight=ft.FontWeight.BOLD)
    txt_taxa_poupanca = ft.Text("0.0%",  color=T.PRIMARY, size=18, weight=ft.FontWeight.BOLD)

    # Contêineres dinâmicos
    col_categorias = ft.Column(spacing=10, controls=[])
    col_balanco    = ft.Column(spacing=10, controls=[])
    col_regra5030  = ft.Column(spacing=12, controls=[])

    def carregar_relatorios():
        spinner.visible = True
        page.update()

        m = mes_sel[0]
        a = ano_sel[0]

        try:
            # 1. Overview para os KPIs do Mês
            overview = db.obter_overview_dashboard(m, a)
            rec  = float(overview.get("receitas", 0) or 0)
            desp = float(overview.get("despesas", 0) or 0)
            saldo = rec - desp
            taxa_poup = ((saldo / rec) * 100) if rec > 0 else 0.0

            txt_rec_mes.value      = formatar_moeda(rec)
            txt_desp_mes.value     = formatar_moeda(desp)
            txt_saldo_mes.value    = formatar_moeda(saldo)
            txt_saldo_mes.color    = T.RECEITA if saldo >= 0 else T.DESPESA
            txt_taxa_poupanca.value = f"{taxa_poup:.1f}%"
            txt_taxa_poupanca.color = T.RECEITA if taxa_poup >= 20 else (T.WARNING if taxa_poup >= 0 else T.DESPESA)

            # 2. Despesas por Categoria
            _carregar_categorias(m, a, desp)

            # 3. Balanço dos Últimos 6 Meses
            _carregar_balanco_semestral()

            # 4. Regra 50/30/20
            _carregar_regra_5030()

        except Exception as ex:
            mostrar_feedback(page, f"Erro ao gerar relatórios: {ex}", "erro")
        finally:
            spinner.visible = False
            page.update()

    def _carregar_categorias(m: int, a: int, total_desp_mes: float):
        col_categorias.controls.clear()
        try:
            dados_cat = db.obter_despesas_por_categoria(m, a)
            lista = dados_cat.get("categorias", []) if isinstance(dados_cat, dict) else (dados_cat or [])

            if not lista:
                col_categorias.controls.append(
                    ft.Container(
                        padding=pad(all_=20),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text("Nenhuma despesa registrada para este mês.", color=T.TEXT_MUTED, size=13),
                    )
                )
                return

            for item in lista:
                nome_cat = item.get("categoria") or item.get("nome", "Outros")
                total_cat = float(item.get("total", 0) or 0)
                cor_cat   = item.get("cor") or T.PRIMARY
                perc = (total_cat / total_desp_mes) if total_desp_mes > 0 else 0.0

                progresso = min(1.0, max(0.0, perc))

                linha = ft.Container(
                    padding=pad(h=12, v=8),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=10,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Container(width=10, height=10, bgcolor=cor_cat, border_radius=5),
                                            ft.Text(nome_cat, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_500),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=12,
                                        controls=[
                                            ft.Text(f"{perc * 100:.1f}%", color=T.TEXT_MUTED, size=12),
                                            ft.Text(formatar_moeda(total_cat), color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                ],
                            ),
                            ft.ProgressBar(value=progresso, color=cor_cat, bgcolor=f"{T.BORDER}50", height=5),
                        ],
                    ),
                )
                col_categorias.controls.append(linha)
        except Exception:
            col_categorias.controls.append(
                ft.Text("Sem dados de categorias disponíveis.", color=T.TEXT_MUTED, size=13)
            )

    def _carregar_balanco_semestral():
        col_balanco.controls.clear()
        try:
            dados_bal = db.obter_balanco_6_meses()
            if not dados_bal:
                col_balanco.controls.append(
                    ft.Container(
                        padding=pad(all_=20),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text("Dados de balanço indisponíveis no momento.", color=T.TEXT_MUTED, size=13),
                    )
                )
                return

            for item in dados_bal:
                label_mes = item.get("label") or f"{item.get('mes', 0):02d}/{item.get('ano', 0)}"
                r = float(item.get("receitas", 0) or 0)
                d = float(item.get("despesas", 0) or 0)
                s = float(item.get("saldo", r - d) or 0)

                maior_valor = max(r, d, 1.0)
                prop_rec  = min(1.0, r / maior_valor)
                prop_desp = min(1.0, d / maior_valor)

                card_mes = ft.Container(
                    padding=pad(all_=14),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=10,
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(label_mes, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                                    ft.Text(
                                        f"Saldo: {formatar_moeda(s)}",
                                        color=T.RECEITA if s >= 0 else T.DESPESA,
                                        size=13,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                ],
                            ),
                            # Barra de Receita
                            ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text("Receitas", size=11, color=T.TEXT_MUTED, width=65),
                                    ft.ProgressBar(value=prop_rec, color=T.RECEITA, bgcolor=f"{T.BORDER}50", height=6, expand=True),
                                    ft.Text(formatar_moeda(r), size=11, color=T.RECEITA, width=90, text_align=ft.TextAlign.RIGHT),
                                ],
                            ),
                            # Barra de Despesa
                            ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Text("Despesas", size=11, color=T.TEXT_MUTED, width=65),
                                    ft.ProgressBar(value=prop_desp, color=T.DESPESA, bgcolor=f"{T.BORDER}50", height=6, expand=True),
                                    ft.Text(formatar_moeda(d), size=11, color=T.DESPESA, width=90, text_align=ft.TextAlign.RIGHT),
                                ],
                            ),
                        ],
                    ),
                )
                col_balanco.controls.append(card_mes)
        except Exception:
            col_balanco.controls.append(
                ft.Text("Sem histórico de 6 meses no momento.", color=T.TEXT_MUTED, size=13)
            )

    def _carregar_regra_5030():
        col_regra5030.controls.clear()
        try:
            resumo = db.obter_resumo_5030()
            itens_regra = [
                {"titulo": "Essencial (Meta 50%)",      "chave": "essencial",      "cor": T.PRIMARY, "meta": 0.50},
                {"titulo": "Estilo de Vida (Meta 30%)", "chave": "estilo_de_vida", "cor": T.WARNING, "meta": 0.30},
                {"titulo": "Investimento (Meta 20%)",   "chave": "investimento",   "cor": T.SALDO,   "meta": 0.20},
            ]

            for reg in itens_regra:
                dados_reg = resumo.get(reg["chave"], {})
                gasto = float(dados_reg.get("gasto", 0) or 0)
                ideal = float(dados_reg.get("ideal", 0) or 0)
                pct_real = float(dados_reg.get("percentual_real", 0) or 0)

                progresso = min(1.0, max(0.0, gasto / ideal)) if ideal > 0 else 0.0

                col_regra5030.controls.append(
                    ft.Container(
                        padding=pad(all_=14),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=10,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(reg["titulo"], color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600),
                                        ft.Text(f"{pct_real:.1f}% da receita", color=reg["cor"], size=12, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.ProgressBar(value=progresso, color=reg["cor"], bgcolor=f"{T.BORDER}50", height=6),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"Gasto: {formatar_moeda(gasto)}", color=T.TEXT_MUTED, size=11),
                                        ft.Text(f"Meta Ideal: {formatar_moeda(ideal)}", color=T.TEXT_MUTED, size=11),
                                    ],
                                ),
                            ],
                        ),
                    )
                )
        except Exception:
            col_regra5030.controls.append(
                ft.Text("Regra 50/30/20 calculada a partir de receitas e despesas registradas.", color=T.TEXT_MUTED, size=13)
            )

    # ── KPIs Topo ─────────────────────────────────────────────────────────────
    def _kpi(titulo: str, ref_ctrl: ft.Control, cor: str, icone):
        return ft.Container(
            col={"xs": 6, "sm": 3},
            padding=pad(all_=16),
            bgcolor=T.SURFACE,
            border_radius=14,
            border=borda(),
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(titulo, color=T.TEXT_MUTED, size=11, weight=ft.FontWeight.W_500),
                            ft.Icon(icone, color=cor, size=18),
                        ],
                    ),
                    ref_ctrl,
                ],
            ),
        )

    kpis_topo = ft.ResponsiveRow(
        spacing=12, run_spacing=12,
        controls=[
            _kpi("Receitas do Mês",  txt_rec_mes,       T.RECEITA, ft.Icons.ARROW_UPWARD_ROUNDED),
            _kpi("Despesas do Mês",  txt_desp_mes,      T.DESPESA, ft.Icons.ARROW_DOWNWARD_ROUNDED),
            _kpi("Saldo Mensal",     txt_saldo_mes,     T.SALDO,   ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED),
            _kpi("Taxa de Poupança", txt_taxa_poupanca, T.PRIMARY, ft.Icons.SAVINGS_ROUNDED),
        ],
    )

    # ── Seções dos Relatórios ──────────────────────────────────────────────────
    secao_cat = ft.Container(
        col={"xs": 12, "md": 6},
        padding=pad(all_=20),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Despesas por Categoria", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                        ft.Icon(ft.Icons.PIE_CHART_OUTLINE_ROUNDED, color=T.PRIMARY, size=18),
                    ],
                ),
                ft.Divider(color=T.BORDER, height=1),
                col_categorias,
            ],
        ),
    )

    secao_regra = ft.Container(
        col={"xs": 12, "md": 6},
        padding=pad(all_=20),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Acompanhamento Regra 50/30/20", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=T.PRIMARY, size=18),
                    ],
                ),
                ft.Divider(color=T.BORDER, height=1),
                col_regra5030,
            ],
        ),
    )

    secao_balanco = ft.Container(
        col={"xs": 12},
        padding=pad(all_=20),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Balanço dos Últimos 6 Meses", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                        ft.Icon(ft.Icons.BAR_CHART_ROUNDED, color=T.PRIMARY, size=18),
                    ],
                ),
                ft.Divider(color=T.BORDER, height=1),
                col_balanco,
            ],
        ),
    )

    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=2,
                controls=[
                    ft.Row(spacing=8, controls=[
                        ft.Text("Relatórios Financeiros", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                        spinner,
                    ]),
                    ft.Text("Análises detalhadas por categoria, metas e evolução histórica", color=T.TEXT_MUTED, size=12),
                ],
            ),
        ],
    )

    def on_mes_ano_change(m: int, a: int):
        mes_sel[0] = m
        ano_sel[0] = a
        carregar_relatorios()

    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=18),
            kpis_topo,
            ft.Container(height=20),
            ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[secao_cat, secao_regra]),
            ft.Container(height=16),
            secao_balanco,
            ft.Container(height=30),
        ],
    )

    carregar_relatorios()

    return criar_shell(page, rota_ativa=ROTA_RELATORIOS, conteudo=conteudo, on_mes_ano_change=on_mes_ano_change)
