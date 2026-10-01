"""
=============================================================================
DemBase v3 — views/relatorios_view.py  (Flet 1.0.1)
Relatórios Financeiros: Visão Geral (Categorias, Balanço Semestral, 
Regra 50/30/20) e Extrato de Lançamentos Detalhados com Filtros, 
Edição e Exclusão.
Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
import flet as ft
from datetime import date
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, hoje, session_get, session_set, session_pop, session_remove
from core.router import ROTA_LANCAMENTO, navegar
from views.shell_view import criar_shell, ROTA_RELATORIOS
import services.supabase_client as db


def _formatar_data_br(data_str: str) -> str:
    """Converte 'YYYY-MM-DD' para 'DD/MM/AAAA' de forma segura."""
    if not data_str:
        return "--"
    try:
        partes = str(data_str).split("T")[0].split("-")
        if len(partes) == 3:
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
        return str(data_str)
    except Exception:
        return str(data_str)


def criar_view_relatorios(page: ft.Page) -> ft.View:
    hoje_d = hoje()
    mes_sel = [hoje_d.month]
    ano_sel = [hoje_d.year]

    # Verifica se deve abrir direto na aba de lançamentos (ex: voltando da edição)
    aba_inicial = session_pop(page, "tab_relatorios", 0) or 0
    aba_ativa = [aba_inicial]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    def _safe_update(control: ft.Control):
        try:
            control.update()
        except Exception:
            try:
                page.update()
            except Exception:
                pass

    # =========================================================================
    # ABA 1: VISÃO GERAL (CARDS, CATEGORIAS, BALANÇO, REGRA 50/30/20)
    # =========================================================================
    txt_rec_mes       = ft.Text("R$ 0,00", color=T.RECEITA, size=18, weight=ft.FontWeight.BOLD)
    txt_desp_mes      = ft.Text("R$ 0,00", color=T.DESPESA, size=18, weight=ft.FontWeight.BOLD)
    txt_saldo_mes     = ft.Text("R$ 0,00", color=T.SALDO,   size=18, weight=ft.FontWeight.BOLD)
    txt_taxa_poupanca = ft.Text("0.0%",   color=T.PRIMARY, size=18, weight=ft.FontWeight.BOLD)

    col_categorias = ft.Column(spacing=10, controls=[])
    col_balanco    = ft.Column(spacing=10, controls=[])
    col_regra5030  = ft.Column(spacing=12, controls=[])

    def carregar_visao_geral():
        spinner.visible = True
        _safe_update(spinner)

        m = mes_sel[0]
        a = ano_sel[0]

        try:
            # 1. Overview para os KPIs do Mês
            overview = db.obter_overview_dashboard(m, a)
            rec  = float(overview.get("receitas", 0) or 0)
            desp = float(overview.get("despesas", 0) or 0)
            saldo = rec - desp
            taxa_poup = ((saldo / rec) * 100) if rec > 0 else 0.0

            txt_rec_mes.value       = formatar_moeda(rec)
            txt_desp_mes.value      = formatar_moeda(desp)
            txt_saldo_mes.value     = formatar_moeda(saldo)
            txt_saldo_mes.color     = T.RECEITA if saldo >= 0 else T.DESPESA
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
            _safe_update(container_visao_geral)

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

    container_visao_geral = ft.Column(
        spacing=0,
        visible=(aba_ativa[0] == 0),
        controls=[
            kpis_topo,
            ft.Container(height=20),
            ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[secao_cat, secao_regra]),
            ft.Container(height=16),
            secao_balanco,
            ft.Container(height=30),
        ],
    )

    # =========================================================================
    # ABA 2: LANÇAMENTOS DETALHADOS (EXTRATO COMPLETO COM FILTROS E AÇÕES)
    # =========================================================================
    todos_lancamentos: list[dict] = []
    lancamentos_carregados = [False]
    spinner_extrato = ft.ProgressRing(color=T.PRIMARY, width=18, height=18, stroke_width=2, visible=False)

    # Estado de Paginação
    pagina_atual = [1]
    itens_por_pagina = [25]

    # KPIs de resumo do extrato filtrado
    txt_ext_total_qtd   = ft.Text("0 lançamentos", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD)
    txt_ext_total_rec   = ft.Text("R$ 0,00", color=T.RECEITA, size=16, weight=ft.FontWeight.BOLD)
    txt_ext_total_desp  = ft.Text("R$ 0,00", color=T.DESPESA, size=16, weight=ft.FontWeight.BOLD)
    txt_ext_total_saldo = ft.Text("R$ 0,00", color=T.SALDO,   size=16, weight=ft.FontWeight.BOLD)

    # Controles de Filtros
    dd_filtro_periodo = ft.Dropdown(
        label="Período",
        value="mes",
        options=[
            ft.dropdown.Option("mes", f"Mês ({mes_sel[0]:02d}/{ano_sel[0]})"),
            ft.dropdown.Option("ano", f"Ano Inteiro ({ano_sel[0]})"),
            ft.dropdown.Option("todos", "Todos os Lançamentos"),
        ],
        width=190,
        **T.dropdown_estilo(),
    )

    dd_filtro_tipo = ft.Dropdown(
        label="Tipo",
        value="todos",
        options=[
            ft.dropdown.Option("todos", "Todos os Tipos"),
            ft.dropdown.Option("Receita", "Receitas"),
            ft.dropdown.Option("Despesa", "Despesas"),
            ft.dropdown.Option("Transferência", "Transferências"),
        ],
        width=170,
        **T.dropdown_estilo(),
    )

    dd_filtro_cat = ft.Dropdown(
        label="Categoria",
        value="todas",
        options=[ft.dropdown.Option("todas", "Todas as Categorias")],
        width=210,
        **T.dropdown_estilo(),
    )

    dd_filtro_status = ft.Dropdown(
        label="Situação",
        value="todos",
        options=[
            ft.dropdown.Option("todos", "Todas as Situações"),
            ft.dropdown.Option("Pago", "Pago"),
            ft.dropdown.Option("Pendente", "Pendente"),
        ],
        width=170,
        **T.dropdown_estilo(),
    )

    txt_busca = ft.TextField(
        label="Buscar Lançamento",
        hint_text="Descrição, subtipo, notas...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        width=240,
        **T.campo_estilo(),
    )

    # Tabela e Contêiner de Dados
    tabela_lancamentos = ft.DataTable(
        columns=[
            ft.DataColumn(label=ft.Text("Data", color=T.TEXT_MUTED, weight=ft.FontWeight.BOLD, size=12)),
            ft.DataColumn(label=ft.Text("Descrição", color=T.TEXT_MUTED, weight=ft.FontWeight.BOLD, size=12)),
            ft.DataColumn(label=ft.Text("Categoria", color=T.TEXT_MUTED, weight=ft.FontWeight.BOLD, size=12)),
            ft.DataColumn(label=ft.Text("Conta / Cartão", color=T.TEXT_MUTED, weight=ft.FontWeight.BOLD, size=12)),
            ft.DataColumn(label=ft.Text("Valor", color=T.TEXT_MUTED, weight=ft.FontWeight.BOLD, size=12), numeric=True),
            ft.DataColumn(label=ft.Text("Situação", color=T.TEXT_MUTED, weight=ft.FontWeight.BOLD, size=12)),
            ft.DataColumn(label=ft.Text("Ações", color=T.TEXT_MUTED, weight=ft.FontWeight.BOLD, size=12), heading_row_alignment=ft.MainAxisAlignment.CENTER),
        ],
        rows=[],
        column_spacing=18,
        heading_row_color=T.SURFACE_ALT,
        divider_thickness=0.6,
        horizontal_lines=ft.BorderSide(0.6, f"{T.BORDER}60"),
    )

    # Empty State
    container_vazio = ft.Container(
        padding=pad(all_=36),
        alignment=ft.Alignment(0, 0),
        visible=False,
        content=ft.Column(
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, color=T.TEXT_MUTED, size=42),
                ft.Text("Nenhum lançamento encontrado para os filtros selecionados.", color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.W_500),
                ft.Text("Experimente alterar o período ou limpar os filtros de busca.", color=T.TEXT_MUTED, size=12),
            ],
        ),
    )

    # Elementos de Paginação
    txt_paginacao_info = ft.Text("Exibindo 0 de 0 lançamentos", color=T.TEXT_MUTED, size=12)
    btn_pag_ant = ft.IconButton(icon=ft.Icons.CHEVRON_LEFT_ROUNDED, icon_color=T.TEXT_MUTED, disabled=True)
    btn_pag_prox = ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT_ROUNDED, icon_color=T.TEXT_MUTED, disabled=True)
    txt_pag_atual = ft.Text("Página 1 de 1", color=T.TEXT_PRIMARY, size=12, weight=ft.FontWeight.W_600)

    # =========================================================================
    # LÓGICA DE FILTRAGEM, TABELA E AÇÕES (EDITAR / EXCLUIR)
    # =========================================================================
    def _obter_dados_filtrados() -> list[dict]:
        periodo = dd_filtro_periodo.value
        tipo = dd_filtro_tipo.value
        cat = dd_filtro_cat.value
        status = dd_filtro_status.value
        termo = (txt_busca.value or "").strip().lower()

        m = mes_sel[0]
        a = ano_sel[0]

        filtrados = []
        for item in todos_lancamentos:
            dt = str(item.get("data") or "")

            # 1. Filtro Período
            if periodo == "mes":
                if not dt.startswith(f"{a:04d}-{m:02d}"):
                    continue
            elif periodo == "ano":
                if not dt.startswith(f"{a:04d}"):
                    continue

            # 2. Filtro Tipo
            if tipo and tipo != "todos":
                t_item = (item.get("tipo") or "").lower()
                if tipo.lower() not in t_item:
                    continue

            # 3. Filtro Categoria
            if cat and cat != "todas":
                c_id = str(item.get("categoria_id") or "")
                c_nome = ""
                if isinstance(item.get("categorias"), dict):
                    c_nome = (item["categorias"].get("nome") or "").lower()
                if c_id != cat and cat.lower() != c_nome:
                    continue

            # 4. Filtro Situação
            if status and status != "todos":
                s_item = (item.get("status") or "").lower()
                if status.lower() != s_item:
                    continue

            # 5. Busca por Descrição / Subtipo
            if termo:
                desc = (item.get("descricao") or "").lower()
                subt = (item.get("subtipo") or "").lower()
                cat_n = (item.get("categorias", {}).get("nome") if isinstance(item.get("categorias"), dict) else "").lower()
                subc_n = (item.get("subcategorias", {}).get("nome") if isinstance(item.get("subcategorias"), dict) else "").lower()
                if termo not in desc and termo not in subt and termo not in cat_n and termo not in subc_n:
                    continue

            filtrados.append(item)

        return filtrados

    def _aplicar_filtros(reset_pagina: bool = True):
        if reset_pagina:
            pagina_atual[0] = 1

        filtrados = _obter_dados_filtrados()
        total_itens = len(filtrados)

        # Atualiza métricas rápidas do extrato
        total_rec = sum(float(i.get("valor", 0) or 0) for i in filtrados if (i.get("tipo") or "").lower() == "receita")
        total_desp = sum(float(i.get("valor", 0) or 0) for i in filtrados if (i.get("tipo") or "").lower() == "despesa")
        saldo_extrato = total_rec - total_desp

        txt_ext_total_qtd.value   = f"{total_itens} lançamento{'s' if total_itens != 1 else ''}"
        txt_ext_total_rec.value   = formatar_moeda(total_rec)
        txt_ext_total_desp.value  = formatar_moeda(total_desp)
        txt_ext_total_saldo.value = formatar_moeda(saldo_extrato)
        txt_ext_total_saldo.color = T.RECEITA if saldo_extrato >= 0 else T.DESPESA

        # Paginação
        itens_pag = itens_por_pagina[0]
        total_paginas = max(1, (total_itens + itens_pag - 1) // itens_pag)
        if pagina_atual[0] > total_paginas:
            pagina_atual[0] = total_paginas

        p = pagina_atual[0]
        idx_ini = (p - 1) * itens_pag
        idx_fim = min(idx_ini + itens_pag, total_itens)
        itens_pagina = filtrados[idx_ini:idx_fim]

        txt_paginacao_info.value = f"Exibindo {idx_ini + 1 if total_itens > 0 else 0} a {idx_fim} de {total_itens} lançamentos"
        txt_pag_atual.value = f"Página {p} de {total_paginas}"
        btn_pag_ant.disabled = (p <= 1)
        btn_pag_prox.disabled = (p >= total_paginas)

        # Montagem das linhas da tabela
        tabela_lancamentos.rows.clear()
        if total_itens == 0:
            container_vazio.visible = True
            tabela_lancamentos.visible = False
        else:
            container_vazio.visible = False
            tabela_lancamentos.visible = True

            for it in itens_pagina:
                tabela_lancamentos.rows.append(_criar_linha_tabela(it))

        _safe_update(container_lancamentos)

    def _criar_linha_tabela(item: dict) -> ft.DataRow:
        v = float(item.get("valor", 0) or 0)
        tipo = item.get("tipo") or "Despesa"
        is_rec = tipo.lower() == "receita"
        is_desp = tipo.lower() == "despesa"
        is_transf = "trans" in tipo.lower()

        # Data
        dt_formatada = _formatar_data_br(item.get("data"))

        # Descrição e Subtipo
        desc = item.get("descricao") or ("Transferência" if is_transf else "Lançamento")
        subtipo = item.get("subtipo") or ""
        sub_info = f"{subtipo}" if (subtipo and subtipo.lower() != desc.lower()) else tipo

        # Categoria & Subcategoria
        cat_d = item.get("categorias")
        cat_nome = cat_d.get("nome") if isinstance(cat_d, dict) else (item.get("categoria_id") or "Outros")
        cor_cat = (cat_d.get("cor") if isinstance(cat_d, dict) else None) or T.PRIMARY
        subcat_d = item.get("subcategorias")
        subcat_nome = subcat_d.get("nome") if isinstance(subcat_d, dict) else None

        # Conta / Cartão
        cart_d = item.get("cartoes")
        conta_d = item.get("contas")
        if isinstance(cart_d, dict) and cart_d.get("nome"):
            icone_conta = ft.Icons.CREDIT_CARD_ROUNDED
            cor_icone_conta = T.WARNING
            texto_conta = f"{cart_d.get('nome')} (Crédito)"
        elif isinstance(conta_d, dict) and conta_d.get("nome"):
            icone_conta = ft.Icons.ACCOUNT_BALANCE_ROUNDED
            cor_icone_conta = T.PRIMARY
            dest_d = item.get("destinos")
            if is_transf and isinstance(dest_d, dict) and dest_d.get("nome"):
                texto_conta = f"{conta_d.get('nome')} ➔ {dest_d.get('nome')}"
            else:
                texto_conta = conta_d.get("nome")
        else:
            icone_conta = ft.Icons.PAYMENT_ROUNDED
            cor_icone_conta = T.TEXT_MUTED
            texto_conta = item.get("forma_movimentacao") or "Conta"

        # Valor formatado
        if is_rec:
            cor_v = T.RECEITA
            txt_v = f"+ {formatar_moeda(v)}"
        elif is_desp:
            cor_v = T.DESPESA
            txt_v = f"- {formatar_moeda(v)}"
        else:
            cor_v = T.PRIMARY
            txt_v = formatar_moeda(v)

        # Situação Badge
        status = str(item.get("status") or "Pago")
        is_pago = (status.lower() == "pago")
        badge_status = ft.Container(
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if is_pago else ft.Icons.SCHEDULE_ROUNDED,
                        size=12,
                        color=T.RECEITA if is_pago else T.WARNING,
                    ),
                    ft.Text(
                        "Pago" if is_pago else "Pendente",
                        color=T.RECEITA if is_pago else T.WARNING,
                        size=11,
                        weight=ft.FontWeight.BOLD,
                    ),
                ],
            ),
            bgcolor=f"{T.RECEITA}18" if is_pago else f"{T.WARNING}18",
            border=borda(1, f"{T.RECEITA}40" if is_pago else f"{T.WARNING}40"),
            border_radius=12,
            padding=pad(h=8, v=3),
        )

        # Botões de Ações
        btn_editar = ft.IconButton(
            icon=ft.Icons.EDIT_ROUNDED,
            icon_color=T.PRIMARY,
            icon_size=18,
            tooltip="Editar lançamento",
            on_click=lambda _, it=item: _ao_editar(it),
        )

        btn_excluir = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            icon_color=T.DESPESA,
            icon_size=18,
            tooltip="Excluir lançamento",
            on_click=lambda _, it=item: _ao_excluir(it),
        )

        return ft.DataRow(
            cells=[
                # 1. Data
                ft.DataCell(
                    ft.Text(dt_formatada, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_500)
                ),
                # 2. Descrição + Subtipo
                ft.DataCell(
                    ft.Column(
                        spacing=2,
                        tight=True,
                        controls=[
                            ft.Text(desc, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_600, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(sub_info, color=T.TEXT_MUTED, size=11),
                        ],
                    )
                ),
                # 3. Categoria + Subcategoria
                ft.DataCell(
                    ft.Row(
                        spacing=8,
                        tight=True,
                        controls=[
                            ft.Container(width=8, height=8, bgcolor=cor_cat, border_radius=4),
                            ft.Column(
                                spacing=2,
                                tight=True,
                                controls=[
                                    ft.Text(cat_nome, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.W_500),
                                    *( [ft.Text(subcat_nome, color=T.TEXT_MUTED, size=11)] if subcat_nome else [] )
                                ],
                            ),
                        ],
                    )
                ),
                # 4. Conta / Cartão
                ft.DataCell(
                    ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(icone_conta, color=cor_icone_conta, size=15),
                            ft.Text(texto_conta, color=T.TEXT_PRIMARY, size=13),
                        ],
                    )
                ),
                # 5. Valor
                ft.DataCell(
                    ft.Text(txt_v, color=cor_v, size=13, weight=ft.FontWeight.BOLD)
                ),
                # 6. Situação
                ft.DataCell(badge_status),
                # 7. Ações
                ft.DataCell(
                    ft.Row(
                        spacing=2,
                        tight=True,
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[btn_editar, btn_excluir],
                    )
                ),
            ]
        )

    # ── Ação de Editar Lançamento ─────────────────────────────────────────────
    def _ao_editar(item: dict):
        session_set(page, "edit_lancamento_id", str(item.get("id")))
        session_set(page, "edit_lancamento_dados", item)
        session_set(page, "tab_relatorios", 1)
        navegar(page, ROTA_LANCAMENTO)

    # ── Ação de Excluir Lançamento (Modal Confirmação) ─────────────────────────
    def _ao_excluir(item: dict):
        lanc_id = item.get("id")
        desc = item.get("descricao") or "Lançamento"
        val = formatar_moeda(float(item.get("valor", 0) or 0))
        dt_str = _formatar_data_br(item.get("data", ""))

        def _fechar_modal():
            modal_excluir.open = False
            page.update()
            if modal_excluir in page.overlay:
                page.overlay.remove(modal_excluir)

        def _confirmar(_):
            try:
                db.deletar_lancamento(lanc_id)
                _fechar_modal()
                # Remove da lista em memória
                todos_lancamentos[:] = [l for l in todos_lancamentos if str(l.get("id")) != str(lanc_id)]
                _aplicar_filtros()
                # Atualiza também os dados gerenciais da Visão Geral
                carregar_visao_geral()
                mostrar_feedback(page, "Lançamento excluído com sucesso!", "sucesso")
            except Exception as ex:
                _fechar_modal()
                mostrar_feedback(page, f"Erro ao excluir lançamento: {ex}", "erro")

        modal_excluir = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.WARNING_ROUNDED, color=T.DESPESA, size=24),
                    ft.Text("Excluir Lançamento", size=18, weight=ft.FontWeight.BOLD),
                ],
            ),
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Text("Tem certeza que deseja excluir permanentemente este lançamento?", color=T.TEXT_PRIMARY, size=14),
                    ft.Container(
                        padding=pad(all_=14),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=10,
                        border=borda(),
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row([ft.Text("Descrição:", color=T.TEXT_MUTED, size=12), ft.Text(desc, color=T.TEXT_PRIMARY, size=13, weight=ft.FontWeight.BOLD)]),
                                ft.Row([ft.Text("Valor:", color=T.TEXT_MUTED, size=12), ft.Text(val, color=T.DESPESA, size=13, weight=ft.FontWeight.BOLD)]),
                                ft.Row([ft.Text("Data:", color=T.TEXT_MUTED, size=12), ft.Text(dt_str, color=T.TEXT_MUTED, size=12)]),
                            ],
                        ),
                    ),
                    ft.Text("Esta ação não poderá ser desfeita.", color=T.TEXT_MUTED, size=12),
                ],
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: _fechar_modal(),
                ),
                ft.FilledButton(
                    content=ft.Text("Excluir"),
                    style=ft.ButtonStyle(bgcolor=T.DESPESA),
                    on_click=_confirmar,
                ),
            ],
        )

        page.overlay.append(modal_excluir)
        modal_excluir.open = True
        page.update()

    # ── Navegação de Paginação ────────────────────────────────────────────────
    def _pag_anterior(_):
        if pagina_atual[0] > 1:
            pagina_atual[0] -= 1
            _aplicar_filtros(reset_pagina=False)

    def _pag_proxima(_):
        pagina_atual[0] += 1
        _aplicar_filtros(reset_pagina=False)

    btn_pag_ant.on_click = _pag_anterior
    btn_pag_prox.on_click = _pag_proxima

    # ── Carregamento Inicial do Extrato ───────────────────────────────────────
    def carregar_todos_lancamentos(forcar: bool = False):
        if lancamentos_carregados[0] and not forcar:
            return

        spinner_extrato.visible = True
        _safe_update(spinner_extrato)

        try:
            dados = db.listar_lancamentos()
            todos_lancamentos.clear()
            todos_lancamentos.extend(dados)
            lancamentos_carregados[0] = True

            # Carrega categorias para o filtro
            cats = db.listar_categorias()
            dd_filtro_cat.options = [ft.dropdown.Option("todas", "Todas as Categorias")] + [
                ft.dropdown.Option(str(c.get("id")), c.get("nome", "Sem Nome")) for c in cats
            ]
            dd_filtro_cat.value = "todas"

            _aplicar_filtros(reset_pagina=True)
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao listar lançamentos: {ex}", "erro")
        finally:
            spinner_extrato.visible = False
            _safe_update(container_lancamentos)

    # Listeners de Filtro
    dd_filtro_periodo.on_change = lambda _: _aplicar_filtros(reset_pagina=True)
    dd_filtro_tipo.on_change    = lambda _: _aplicar_filtros(reset_pagina=True)
    dd_filtro_cat.on_change     = lambda _: _aplicar_filtros(reset_pagina=True)
    dd_filtro_status.on_change  = lambda _: _aplicar_filtros(reset_pagina=True)
    txt_busca.on_change         = lambda _: _aplicar_filtros(reset_pagina=True)

    def _limpar_filtros(_):
        dd_filtro_periodo.value = "mes"
        dd_filtro_tipo.value = "todos"
        dd_filtro_cat.value = "todas"
        dd_filtro_status.value = "todos"
        txt_busca.value = ""
        _aplicar_filtros(reset_pagina=True)

    btn_limpar_filtros = T.botao_outline(
        "Limpar Filtros",
        icone=ft.Icons.FILTER_ALT_OFF_ROUNDED,
        on_click=_limpar_filtros,
    )

    # ── KPIs Topo do Extrato ──────────────────────────────────────────────────
    kpis_extrato = ft.ResponsiveRow(
        spacing=12, run_spacing=12,
        controls=[
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(all_=14),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row([ft.Text("Lançamentos", color=T.TEXT_MUTED, size=11), ft.Icon(ft.Icons.LIST_ALT_ROUNDED, color=T.PRIMARY, size=16)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        txt_ext_total_qtd,
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(all_=14),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row([ft.Text("Receitas", color=T.TEXT_MUTED, size=11), ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=T.RECEITA, size=16)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        txt_ext_total_rec,
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(all_=14),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row([ft.Text("Despesas", color=T.TEXT_MUTED, size=11), ft.Icon(ft.Icons.ARROW_DOWNWARD_ROUNDED, color=T.DESPESA, size=16)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        txt_ext_total_desp,
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 6, "sm": 3},
                padding=pad(all_=14),
                bgcolor=T.SURFACE,
                border_radius=12,
                border=borda(),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Row([ft.Text("Saldo Filtrado", color=T.TEXT_MUTED, size=11), ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=T.SALDO, size=16)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        txt_ext_total_saldo,
                    ],
                ),
            ),
        ],
    )

    # ── Barra de Filtros ──────────────────────────────────────────────────────
    card_filtros = ft.Container(
        padding=pad(all_=16),
        bgcolor=T.SURFACE,
        border_radius=14,
        border=borda(),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.FILTER_LIST_ROUNDED, color=T.PRIMARY, size=18),
                                ft.Text("Filtros do Extrato", color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.BOLD),
                                spinner_extrato,
                            ],
                        ),
                        btn_limpar_filtros,
                    ],
                ),
                ft.ResponsiveRow(
                    spacing=10, run_spacing=10,
                    controls=[
                        ft.Container(content=dd_filtro_periodo, col={"xs": 12, "sm": 6, "md": 2.4}),
                        ft.Container(content=dd_filtro_tipo,    col={"xs": 12, "sm": 6, "md": 2.4}),
                        ft.Container(content=dd_filtro_cat,     col={"xs": 12, "sm": 6, "md": 2.4}),
                        ft.Container(content=dd_filtro_status,  col={"xs": 12, "sm": 6, "md": 2.4}),
                        ft.Container(content=txt_busca,         col={"xs": 12, "sm": 12, "md": 2.4}),
                    ],
                ),
            ],
        ),
    )

    # ── Card da Tabela de Lançamentos ─────────────────────────────────────────
    card_tabela = ft.Container(
        padding=pad(all_=16),
        bgcolor=T.SURFACE,
        border_radius=14,
        border=borda(),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.TABLE_ROWS_ROUNDED, color=T.PRIMARY, size=18),
                                ft.Text("Transações", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.IconButton(
                                    icon=ft.Icons.REFRESH_ROUNDED,
                                    icon_color=T.TEXT_MUTED,
                                    tooltip="Recarregar lançamentos do banco",
                                    on_click=lambda _: carregar_todos_lancamentos(forcar=True),
                                ),
                                ft.FilledButton(
                                    content=ft.Row(
                                        spacing=6,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.ADD_ROUNDED, size=16),
                                            ft.Text("Novo Lançamento", size=13),
                                        ],
                                    ),
                                    style=ft.ButtonStyle(
                                        bgcolor=T.PRIMARY,
                                        shape=ft.RoundedRectangleBorder(radius=8),
                                        padding=pad(h=14, v=8),
                                    ),
                                    on_click=lambda _: navegar(page, ROTA_LANCAMENTO),
                                ),
                            ],
                        ),
                    ],
                ),
                ft.Divider(color=T.BORDER, height=1),
                # Tabela envolvida em Row com scroll horizontal para responsividade perfeita
                ft.Row(
                    scroll=ft.ScrollMode.AUTO,
                    controls=[tabela_lancamentos],
                ),
                container_vazio,
                ft.Divider(color=T.BORDER, height=1),
                # Barra Inferior de Paginação
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        txt_paginacao_info,
                        ft.Row(
                            spacing=4,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                btn_pag_ant,
                                txt_pag_atual,
                                btn_pag_prox,
                            ],
                        ),
                    ],
                ),
            ],
        ),
    )

    container_lancamentos = ft.Column(
        spacing=16,
        visible=(aba_ativa[0] == 1),
        controls=[
            kpis_extrato,
            card_filtros,
            card_tabela,
            ft.Container(height=30),
        ],
    )

    # =========================================================================
    # ABAS (ft.Tabs / ft.TabBar)
    # =========================================================================
    def _alternar_aba(novo_indice: int):
        aba_ativa[0] = novo_indice
        container_visao_geral.visible = (novo_indice == 0)
        container_lancamentos.visible = (novo_indice == 1)

        if novo_indice == 1 and not lancamentos_carregados[0]:
            carregar_todos_lancamentos()

        _safe_update(conteudo)

    def _ao_clicar_tabbar(e):
        try:
            idx = int(e.data)
            _alternar_aba(idx)
        except Exception:
            pass

    def _ao_mudar_tabs(e):
        try:
            idx = int(e.data) if (hasattr(e, "data") and e.data is not None) else tabs.selected_index
            _alternar_aba(idx)
        except Exception:
            pass

    tab_bar = ft.TabBar(
        tabs=[
            ft.Tab(label="Visão Geral", icon=ft.Icons.ANALYTICS_ROUNDED),
            ft.Tab(label="Lançamentos Detalhados", icon=ft.Icons.RECEIPT_LONG_ROUNDED),
        ],
        indicator_color=T.PRIMARY,
        label_color=T.PRIMARY,
        unselected_label_color=T.TEXT_MUTED,
        divider_color=T.BORDER,
        indicator_thickness=3.0,
        scrollable=False,
        on_click=_ao_clicar_tabbar,
    )

    tabs = ft.Tabs(
        length=2,
        selected_index=aba_ativa[0],
        on_change=_ao_mudar_tabs,
        content=ft.Column(
            spacing=16,
            controls=[
                tab_bar,
                container_visao_geral,
                container_lancamentos,
            ],
        ),
    )

    # ── Cabeçalho Principal da Tela ──────────────────────────────────────────
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
                    ft.Text("Análises detalhadas por categoria, metas, balanço e extrato completo", color=T.TEXT_MUTED, size=12),
                ],
            ),
        ],
    )

    # ── Listener de Mês/Ano Global do Shell ──────────────────────────────────
    def on_mes_ano_change(m: int, a: int):
        mes_sel[0] = m
        ano_sel[0] = a

        # Atualiza o label da opção de período do extrato
        dd_filtro_periodo.options[0] = ft.dropdown.Option("mes", f"Mês ({m:02d}/{a})")
        dd_filtro_periodo.options[1] = ft.dropdown.Option("ano", f"Ano Inteiro ({a})")
        _safe_update(dd_filtro_periodo)

        # Atualiza visão geral
        carregar_visao_geral()

        # Se período for mês, re-aplica filtros no extrato
        if dd_filtro_periodo.value == "mes" and lancamentos_carregados[0]:
            _aplicar_filtros()

    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=16),
            tabs,
        ],
    )

    # Carrega a Visão Geral de imediato
    carregar_visao_geral()

    # Se a view foi aberta diretamente na aba 2, carrega o extrato
    if aba_ativa[0] == 1:
        carregar_todos_lancamentos()

    return criar_shell(page, rota_ativa=ROTA_RELATORIOS, conteudo=conteudo, on_mes_ano_change=on_mes_ano_change)
