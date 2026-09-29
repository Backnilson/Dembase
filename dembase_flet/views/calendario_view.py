"""
=============================================================================
DemBase v3 — views/calendario_view.py  (Flet 1.0.1)
Histórico de Lançamentos (Ledger) com Filtros Flexíveis de Data e Visão Calendário.
Montado DENTRO do Shell (sidebar + header).
=============================================================================
"""
import flet as ft
from datetime import date, datetime
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_moeda, formatar_data_br, hoje, inicio_mes_atual
from core.router import ROTA_LANCAMENTO, navegar
from views.widgets.date_filter import DateFilterBar
from views.shell_view import criar_shell, ROTA_CALENDARIO
import services.supabase_client as db


def criar_view_calendario(page: ft.Page) -> ft.View:
    # ── Estado local ─────────────────────────────────────────────────────────
    hoje_d = hoje()
    mes_sel = [hoje_d.month]
    ano_sel = [hoje_d.year]

    filtro_data_inicio = [str(inicio_mes_atual())]
    filtro_data_fim    = [str(hoje_d)]
    filtro_tipo        = ["Todos"]       # "Todos", "Receita", "Despesa"
    filtro_status      = ["Todos"]       # "Todos", "Pago", "Pendente"
    termo_busca        = [""]
    aba_ativa          = [0]             # 0: Histórico/Ledger, 1: Calendário

    todos_lancamentos = []

    # ── Controles de UI ──────────────────────────────────────────────────────
    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    # KPIs do Período Filtrado
    txt_total_receitas = ft.Text("R$ 0,00", color=T.RECEITA, size=18, weight=ft.FontWeight.BOLD)
    txt_total_despesas = ft.Text("R$ 0,00", color=T.DESPESA, size=18, weight=ft.FontWeight.BOLD)
    txt_saldo_periodo  = ft.Text("R$ 0,00", color=T.SALDO,   size=18, weight=ft.FontWeight.BOLD)
    txt_qtd_itens      = ft.Text("0 lançamentos", color=T.TEXT_MUTED, size=12)

    # Contêineres de conteúdo
    col_lista_lancamentos = ft.Column(spacing=10, controls=[])
    col_visao_calendario  = ft.Column(spacing=12, controls=[])
    area_principal        = ft.Column(spacing=16, controls=[])

    # ── Funções de Carregamento ──────────────────────────────────────────────
    def carregar_dados():
        spinner.visible = True
        page.update()

        try:
            nonlocal todos_lancamentos
            # Busca do Supabase no range flexível
            todos_lancamentos = db.listar_lancamentos(
                data_inicio=filtro_data_inicio[0],
                data_fim=filtro_data_fim[0],
            )
            atualizar_visao()
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao carregar dados: {ex}", "erro")
        finally:
            spinner.visible = False
            page.update()

    def alternar_status_lancamento(item: dict):
        novo_status = "Pendente" if item.get("status") == "Pago" else "Pago"
        try:
            db.atualizar_lancamento(item["id"], {"status": novo_status})
            item["status"] = novo_status
            mostrar_feedback(page, f"Status alterado para {novo_status}!", "sucesso")
            atualizar_visao()
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao atualizar: {ex}", "erro")

    def confirmar_exclusao(item: dict):
        def _executar_exclusao(_):
            dialog.open = False
            page.update()
            try:
                db.deletar_lancamento(item["id"])
                mostrar_feedback(page, "Lançamento excluído com sucesso!", "sucesso")
                carregar_dados()
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao excluir: {ex}", "erro")

        def _fechar_dialog(_):
            dialog.open = False
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Excluir Lançamento", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text(
                f"Tem certeza que deseja excluir o lançamento '{item.get('descricao', 'Sem descrição')}' "
                f"no valor de {formatar_moeda(float(item.get('valor', 0)))}?",
                color=T.TEXT_MUTED, size=14,
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=_fechar_dialog,
                ),
                ft.FilledButton(
                    content=ft.Text("Excluir", color=ft.Colors.WHITE),
                    style=ft.ButtonStyle(bgcolor=T.DESPESA),
                    on_click=_executar_exclusao,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.overlay.append(dialog)
        dialog.open = True
        page.update()

    # ── Montagem dos Cards de Lançamento ──────────────────────────────────────
    def _card_lancamento(item: dict) -> ft.Container:
        tipo = item.get("tipo", "Despesa")
        eh_receita = tipo == "Receita"
        valor = float(item.get("valor", 0) or 0)
        sinal = "+" if eh_receita else "-"
        cor_valor = T.RECEITA if eh_receita else T.DESPESA

        # Ícone do tipo / categoria
        icone_tipo = ft.Icons.ARROW_UPWARD_ROUNDED if eh_receita else ft.Icons.ARROW_DOWNWARD_ROUNDED
        cor_badge_tipo = f"{cor_valor}1A"

        # Relações
        categoria_info = item.get("categorias") or {}
        categoria_nome = categoria_info.get("nome", "Sem Categoria")
        conta_info = item.get("contas") or {}
        conta_nome = conta_info.get("nome", "Conta")
        destino_info = item.get("destinos") or {}
        destino_nome = destino_info.get("nome", "")

        status = item.get("status", "Pago")
        eh_pago = status == "Pago"

        # Badges secundárias
        sub_badges = [
            ft.Container(
                content=ft.Text(conta_nome, size=10, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                bgcolor=T.SURFACE_ALT,
                padding=pad(h=6, v=2),
                border_radius=6,
            ),
            ft.Container(
                content=ft.Text(categoria_nome, size=10, color=T.PRIMARY_SOFT, weight=ft.FontWeight.W_500),
                bgcolor=f"{T.PRIMARY}18",
                padding=pad(h=6, v=2),
                border_radius=6,
            ),
        ]

        if destino_nome:
            sub_badges.append(
                ft.Container(
                    content=ft.Text(destino_nome, size=10, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                    bgcolor=T.SURFACE_ALT,
                    padding=pad(h=6, v=2),
                    border_radius=6,
                )
            )

        # Regra 50/30/20 se houver
        regra = item.get("regra")
        if regra:
            cor_regra = T.PRIMARY if regra == "Essencial" else (T.WARNING if regra == "Estilo de Vida" else T.SALDO)
            sub_badges.append(
                ft.Container(
                    content=ft.Text(regra, size=10, color=cor_regra, weight=ft.FontWeight.W_600),
                    bgcolor=f"{cor_regra}18",
                    padding=pad(h=6, v=2),
                    border_radius=6,
                )
            )

        # Cartão / Parcela se houver
        if item.get("forma_movimentacao") == "Crédito" and item.get("parcela_atual"):
            parc_atual = item.get("parcela_atual", 1)
            parc_total = item.get("total_parcelas", 1)
            fatura_ref = item.get("fatura", "")
            texto_parc = f"Parcela {parc_atual}/{parc_total}" + (f" • {fatura_ref}" if fatura_ref else "")
            sub_badges.append(
                ft.Container(
                    content=ft.Text(texto_parc, size=10, color=T.WARNING, weight=ft.FontWeight.W_500),
                    bgcolor=f"{T.WARNING}15",
                    padding=pad(h=6, v=2),
                    border_radius=6,
                )
            )

        # Badge de status interativo
        badge_status = ft.Container(
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE_ROUNDED if eh_pago else ft.Icons.SCHEDULE_ROUNDED,
                        size=12,
                        color=T.RECEITA if eh_pago else T.WARNING,
                    ),
                    ft.Text(
                        status,
                        size=11,
                        color=T.RECEITA if eh_pago else T.WARNING,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
            bgcolor=f"{T.RECEITA}18" if eh_pago else f"{T.WARNING}18",
            border_radius=12,
            padding=pad(h=8, v=4),
            border=borda(1, f"{T.RECEITA}30" if eh_pago else f"{T.WARNING}30"),
            tooltip="Clique para alterar status",
            on_click=lambda _, it=item: alternar_status_lancamento(it),
        )

        data_str = formatar_data_br(item.get("data", ""))
        hora_str = f"{item.get('hora', 0):02d}h" if "hora" in item and item["hora"] is not None else ""

        return ft.Container(
            padding=pad(h=16, v=12),
            bgcolor=T.SURFACE,
            border_radius=12,
            border=borda(),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    # Bloco Esquerdo: Ícone + Descrição + Metadados
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        expand=True,
                        controls=[
                            ft.Container(
                                content=ft.Icon(icone_tipo, color=cor_valor, size=18),
                                bgcolor=cor_badge_tipo,
                                border_radius=10,
                                padding=pad(all_=10),
                            ),
                            ft.Column(
                                spacing=4,
                                expand=True,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        controls=[
                                            ft.Text(
                                                item.get("descricao") or categoria_nome,
                                                color=T.TEXT_PRIMARY,
                                                size=14,
                                                weight=ft.FontWeight.W_600,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Text(
                                                f"{data_str} {hora_str}",
                                                color=T.TEXT_MUTED,
                                                size=11,
                                            ),
                                        ],
                                    ),
                                    ft.Row(
                                        spacing=6,
                                        wrap=True,
                                        controls=sub_badges,
                                    ),
                                ],
                            ),
                        ],
                    ),
                    # Bloco Direito: Status + Valor + Botão de Ação
                    ft.Row(
                        spacing=12,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            badge_status,
                            ft.Text(
                                f"{sinal} {formatar_moeda(valor)}",
                                color=cor_valor,
                                size=15,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                icon_color=T.TEXT_MUTED,
                                icon_size=18,
                                tooltip="Excluir",
                                on_click=lambda _, it=item: confirmar_exclusao(it),
                            ),
                        ],
                    ),
                ],
            ),
        )

    # ── Atualização e Filtragem da Visão ──────────────────────────────────────
    def atualizar_visao():
        # 1. Filtros em memória para busca, tipo e status
        filtrados = todos_lancamentos

        if filtro_tipo[0] != "Todos":
            filtrados = [l for l in filtrados if l.get("tipo") == filtro_tipo[0]]

        if filtro_status[0] != "Todos":
            filtrados = [l for l in filtrados if l.get("status") == filtro_status[0]]

        if termo_busca[0]:
            termo = termo_busca[0].lower()
            filtrados = [
                l for l in filtrados
                if termo in (l.get("descricao") or "").lower()
                or termo in (l.get("categorias", {}).get("nome") or "").lower()
                or termo in (l.get("contas", {}).get("nome") or "").lower()
            ]

        # 2. Recálculo dos KPIs do período
        total_rec = sum(float(l.get("valor", 0) or 0) for l in filtrados if l.get("tipo") == "Receita")
        total_desp = sum(float(l.get("valor", 0) or 0) for l in filtrados if l.get("tipo") == "Despesa")
        saldo = total_rec - total_desp

        txt_total_receitas.value = formatar_moeda(total_rec)
        txt_total_despesas.value = formatar_moeda(total_desp)
        txt_saldo_periodo.value  = formatar_moeda(saldo)
        txt_saldo_periodo.color  = T.RECEITA if saldo >= 0 else T.DESPESA
        txt_qtd_itens.value      = f"{len(filtrados)} lançamento(s) encontrado(s)"

        # 3. Montagem da Lista (Tab 0)
        col_lista_lancamentos.controls.clear()
        if not filtrados:
            col_lista_lancamentos.controls.append(
                ft.Container(
                    padding=pad(all_=40),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, size=54, color=T.TEXT_MUTED),
                            ft.Text("Nenhum lançamento encontrado.", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Altere os filtros de data ou cadastre uma nova transação.", color=T.TEXT_MUTED, size=13),
                            ft.Container(height=8),
                            ft.FilledButton(
                                content=ft.Row(
                                    spacing=6, tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                        ft.Text("Novo Lançamento", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                on_click=lambda _: navegar(page, ROTA_LANCAMENTO),
                                style=ft.ButtonStyle(
                                    bgcolor=T.PRIMARY,
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                    padding=pad(h=16, v=12),
                                ),
                            ),
                        ],
                    ),
                )
            )
        else:
            for item in filtrados:
                col_lista_lancamentos.controls.append(_card_lancamento(item))

        # 4. Montagem do Calendário Diário (Tab 1)
        col_visao_calendario.controls.clear()
        try:
            dados_cal = db.obter_lancamentos_calendario(mes_sel[0], ano_sel[0])
            if not dados_cal:
                col_visao_calendario.controls.append(
                    ft.Container(
                        padding=pad(all_=30),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Text(f"Sem movimentações no mês {mes_sel[0]:02d}/{ano_sel[0]}.", color=T.TEXT_MUTED, size=14),
                    )
                )
            else:
                for dia_info in dados_cal:
                    dia_num = dia_info.get("dia", 1)
                    data_cal = dia_info.get("data", "")
                    desp_dia = float(dia_info.get("total_despesas", 0) or 0)
                    rec_dia  = float(dia_info.get("total_receitas", 0) or 0)
                    lanc_dia = dia_info.get("lancamentos") or []

                    cards_dia = [_card_lancamento(l) for l in lanc_dia]

                    col_visao_calendario.controls.append(
                        ft.Container(
                            padding=pad(all_=16),
                            bgcolor=T.SURFACE,
                            border_radius=12,
                            border=borda(),
                            content=ft.Column(
                                spacing=8,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Row(
                                                spacing=8,
                                                controls=[
                                                    ft.Container(
                                                        content=ft.Text(f"{dia_num:02d}", color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                                                        bgcolor=T.SURFACE_ALT,
                                                        border_radius=8,
                                                        padding=pad(h=10, v=6),
                                                    ),
                                                    ft.Text(formatar_data_br(data_cal), color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.W_600),
                                                ],
                                            ),
                                            ft.Row(
                                                spacing=12,
                                                controls=[
                                                    ft.Text(f"+ {formatar_moeda(rec_dia)}", color=T.RECEITA, size=12, weight=ft.FontWeight.W_600) if rec_dia > 0 else ft.Container(),
                                                    ft.Text(f"- {formatar_moeda(desp_dia)}", color=T.DESPESA, size=12, weight=ft.FontWeight.W_600) if desp_dia > 0 else ft.Container(),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Divider(color=T.BORDER, height=12),
                                    ft.Column(spacing=6, controls=cards_dia),
                                ],
                            ),
                        )
                    )
        except Exception:
            pass

        # Alterna entre abas
        area_principal.controls = [col_lista_lancamentos] if aba_ativa[0] == 0 else [col_visao_calendario]
        page.update()

    # ── Callbacks de Filtros ─────────────────────────────────────────────────
    def on_date_filter_change(inicio_str: str, fim_str: str):
        filtro_data_inicio[0] = inicio_str
        filtro_data_fim[0]    = fim_str
        carregar_dados()

    def on_mes_ano_change(m: int, a: int):
        mes_sel[0] = m
        ano_sel[0] = a
        if aba_ativa[0] == 1:
            atualizar_visao()

    # ── KPI Header do Período ────────────────────────────────────────────────
    def _kpi_pequeno(titulo: str, ref_ctrl: ft.Control, cor: str, icone):
        return ft.Container(
            col={"xs": 6, "sm": 3},
            padding=pad(all_=14),
            bgcolor=T.SURFACE,
            border_radius=12,
            border=borda(),
            content=ft.Column(
                spacing=4,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(titulo, color=T.TEXT_MUTED, size=11, weight=ft.FontWeight.W_500),
                            ft.Icon(icone, color=cor, size=16),
                        ],
                    ),
                    ref_ctrl,
                ],
            ),
        )

    kpis_periodo = ft.ResponsiveRow(
        spacing=10,
        run_spacing=10,
        controls=[
            _kpi_pequeno("Receitas no Período", txt_total_receitas, T.RECEITA, ft.Icons.ARROW_UPWARD_ROUNDED),
            _kpi_pequeno("Despesas no Período", txt_total_despesas, T.DESPESA, ft.Icons.ARROW_DOWNWARD_ROUNDED),
            _kpi_pequeno("Saldo do Período",   txt_saldo_periodo,  T.SALDO,   ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED),
            _kpi_pequeno("Total Registros",     txt_qtd_itens,      T.PRIMARY, ft.Icons.RECEIPT_LONG_ROUNDED),
        ],
    )

    # ── Barra de Busca e Filtros Rápidos ─────────────────────────────────────
    txt_busca = ft.TextField(
        hint_text="Buscar por descrição, conta ou categoria...",
        prefix_icon=ft.Icons.SEARCH_ROUNDED,
        expand=True,
        on_change=lambda e: (termo_busca.__setitem__(0, e.control.value), atualizar_visao()),
        **T.campo_estilo(),
    )

    def _chip_filtro(label: str, estado_ref: list, valor: str, callback=None) -> ft.Container:
        ativo = estado_ref[0] == valor
        return ft.Container(
            content=ft.Text(
                label,
                size=12,
                weight=ft.FontWeight.W_600 if ativo else ft.FontWeight.NORMAL,
                color=T.PRIMARY if ativo else T.TEXT_MUTED,
            ),
            padding=pad(h=12, v=6),
            bgcolor=f"{T.PRIMARY}1A" if ativo else T.SURFACE_ALT,
            border_radius=16,
            border=borda(1, T.PRIMARY if ativo else T.BORDER),
            on_click=lambda _: (estado_ref.__setitem__(0, valor), callback() if callback else atualizar_visao()),
        )

    barra_filtros_rapidos = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        wrap=True,
        spacing=10,
        controls=[
            ft.Row(
                spacing=6,
                wrap=True,
                controls=[
                    ft.Text("Tipo:", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                    _chip_filtro("Todos",    filtro_tipo, "Todos"),
                    _chip_filtro("Receitas", filtro_tipo, "Receita"),
                    _chip_filtro("Despesas", filtro_tipo, "Despesa"),
                ],
            ),
            ft.Row(
                spacing=6,
                wrap=True,
                controls=[
                    ft.Text("Status:", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                    _chip_filtro("Todos",     filtro_status, "Todos"),
                    _chip_filtro("Pagos",     filtro_status, "Pago"),
                    _chip_filtro("Pendentes", filtro_status, "Pendente"),
                ],
            ),
        ],
    )

    # ── Seletor de Abas (Extrato vs Calendário) ──────────────────────────────
    def _trocar_aba(idx: int):
        aba_ativa[0] = idx
        atualizar_visao()

    def _btn_aba(label: str, icone, idx: int) -> ft.Container:
        ativo = aba_ativa[0] == idx
        return ft.Container(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(icone, color=T.PRIMARY if ativo else T.TEXT_MUTED, size=16),
                    ft.Text(
                        label,
                        color=T.TEXT_PRIMARY if ativo else T.TEXT_MUTED,
                        size=13,
                        weight=ft.FontWeight.W_600 if ativo else ft.FontWeight.NORMAL,
                    ),
                ],
            ),
            padding=pad(h=16, v=10),
            bgcolor=f"{T.PRIMARY}18" if ativo else "transparent",
            border_radius=10,
            on_click=lambda _, i=idx: _trocar_aba(i),
        )

    seletor_abas = ft.Container(
        padding=pad(all_=4),
        bgcolor=T.SURFACE,
        border_radius=12,
        border=borda(),
        content=ft.Row(
            spacing=4,
            tight=True,
            controls=[
                _btn_aba("Lista de Transações", ft.Icons.FORMAT_LIST_BULLETED_ROUNDED, 0),
                _btn_aba("Visão Calendário",     ft.Icons.CALENDAR_MONTH_ROUNDED,        1),
            ],
        ),
    )

    # ── Cabeçalho da Página ──────────────────────────────────────────────────
    cabecalho = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Column(
                spacing=2,
                controls=[
                    ft.Row(
                        spacing=8,
                        controls=[
                            ft.Text("Histórico & Extrato", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                            spinner,
                        ],
                    ),
                    ft.Text("Gerencie e acompanhe todos os seus lançamentos financeiros", color=T.TEXT_MUTED, size=12),
                ],
            ),
            ft.FilledButton(
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text("Novo Lançamento", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                    ],
                ),
                on_click=lambda _: navegar(page, ROTA_LANCAMENTO),
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    overlay_color=T.PRIMARY_DARK,
                    shape=ft.RoundedRectangleBorder(radius=10),
                    padding=pad(h=16, v=12),
                ),
            ),
        ],
    )

    # ── Montagem do Conteúdo ─────────────────────────────────────────────────
    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=16),
            DateFilterBar(on_change=on_date_filter_change),
            ft.Container(height=16),
            kpis_periodo,
            ft.Container(height=16),
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
                spacing=10,
                controls=[
                    seletor_abas,
                    ft.Container(content=txt_busca, expand=True, col={"xs": 12, "md": 6}),
                ],
            ),
            ft.Container(height=12),
            barra_filtros_rapidos,
            ft.Container(height=16),
            area_principal,
            ft.Container(height=24),
        ],
    )

    # Carga inicial
    carregar_dados()

    return criar_shell(
        page,
        rota_ativa=ROTA_CALENDARIO,
        conteudo=conteudo,
        on_mes_ano_change=on_mes_ano_change,
    )
