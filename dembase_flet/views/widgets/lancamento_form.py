"""
=============================================================================
DemBase v3 — views/widgets/lancamento_form.py (Flet 1.0.1)
Formulário de Novo / Edição de Lançamento com UI/UX moderna, layout compacto,
chips de data rápida, switch de status, progressive disclosure e regras de negócio.
=============================================================================
"""
from __future__ import annotations

import unicodedata
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import flet as ft

from core.constants import REGRAS_5030
from core.lancamento_state import LancamentoFormState
from core.recorrencia import resumo_parcelas
import core.theme as T
from core.theme import pad, borda, mostrar_feedback
import services.supabase_client as db


def _norm(texto: str) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


class LancamentoForm(ft.Column):
    """
    Componente reutilizável do formulário de lançamento.
    Gerencia a reatividade dos controles e reflete o estado em LancamentoFormState.
    """

    def __init__(
        self,
        page: ft.Page,
        state: LancamentoFormState,
        on_state_change: Optional[Callable[[], None]] = None,
    ):
        super().__init__(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self._page = page
        self.state = state
        self.on_state_change = on_state_change

        # Listas de dados carregadas do Supabase
        self.contas: list[dict] = []
        self.cartoes: list[dict] = []
        self.categorias: list[dict] = []
        self.subcategorias: list[dict] = []

        # Inicialização dos Controles
        self._construir_controles()
        self._carregar_dados_iniciais()
        self._sincronizar_estado_com_ui()

    def _safe_update(self, ctrl: ft.Control):
        try:
            ctrl.update()
        except Exception:
            pass

    def _notificar_mudanca(self):
        if self.on_state_change:
            self.on_state_change()

    # =========================================================================
    # CONSTRUÇÃO DOS CONTROLES
    # =========================================================================
    def _construir_controles(self):
        # 1. Seletor de Tipo (SegmentedButton)
        self.btn_tipo = ft.SegmentedButton(
            selected={self.state.tipo},
            allow_multiple_selection=False,
            segments=[
                ft.Segment(
                    value="Despesa",
                    label=ft.Text("Despesa", weight=ft.FontWeight.BOLD),
                    icon=ft.Icon(ft.Icons.ARROW_DOWNWARD_ROUNDED, color=T.DESPESA),
                ),
                ft.Segment(
                    value="Receita",
                    label=ft.Text("Receita", weight=ft.FontWeight.BOLD),
                    icon=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=T.RECEITA),
                ),
                ft.Segment(
                    value="Transferencia",
                    label=ft.Text("Transf.", weight=ft.FontWeight.BOLD),
                    icon=ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, color=T.PRIMARY),
                ),
            ],
            on_change=self._ao_mudar_tipo,
        )

        # 2. Input de Valor Grande e Destacado
        cor_valor = T.DESPESA if self.state.tipo == "Despesa" else (T.RECEITA if self.state.tipo == "Receita" else T.PRIMARY)
        str_val = f"{self.state.valor:.2f}".replace(".", ",") if self.state.valor > 0 else "0,00"
        self.txt_valor = ft.TextField(
            label="Valor da transação",
            value=str_val,
            prefix=ft.Text("R$ ", size=22, weight=ft.FontWeight.BOLD, color=cor_valor),
            text_size=28,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True,
            color=cor_valor,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            border_radius=12,
            border_color=T.BORDER,
            focused_border_color=cor_valor,
            on_change=self._ao_mudar_valor,
        )

        # 3. Chips de Data Rápida
        self.chip_hoje = ft.Chip(
            label=ft.Text("Hoje"),
            selected=False,
            on_click=lambda _: self._selecionar_data_rapida(date.today()),
        )
        self.chip_ontem = ft.Chip(
            label=ft.Text("Ontem"),
            selected=False,
            on_click=lambda _: self._selecionar_data_rapida(date.today() - timedelta(days=1)),
        )
        self.chip_outros = ft.Chip(
            label=ft.Text("Outros..."),
            selected=False,
            leading=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=16),
            on_click=self._abrir_seletor_data,
        )
        self.row_chips_data = ft.Row(
            controls=[self.chip_hoje, self.chip_ontem, self.chip_outros],
            spacing=8,
        )

        # 4. Switch de Status
        label_switch = "Foi paga" if self.state.tipo == "Despesa" else "Foi recebida"
        self.switch_status = ft.Switch(
            label=label_switch,
            value=self.state.status_pago,
            active_color=T.PRIMARY,
            on_change=self._ao_tocar_switch_status,
        )

        # 5. Descrição
        self.txt_descricao = ft.TextField(
            label="Descrição *",
            hint_text="Ex: Supermercado, Aluguel, Salário...",
            value=self.state.descricao,
            border_radius=10,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            on_change=lambda e: setattr(self.state, "descricao", e.control.value),
        )

        # 6. Forma de Movimentação (Sempre Visível)
        self.dd_forma = ft.Dropdown(
            label="Forma de movimentação *",
            value=self.state.forma_movimentacao,
            expand=True,
            on_select=self._ao_mudar_forma,
            **T.dropdown_estilo(),
        )

        # 7. Conta ou Cartão de Crédito
        self.dd_conta = ft.Dropdown(
            label="Conta *",
            value=self.state.conta_id,
            expand=True,
            on_select=self._ao_mudar_conta,
            **T.dropdown_estilo(),
        )
        self.btn_add_conta = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_color=T.PRIMARY,
            tooltip="Nova Conta",
            on_click=self._abrir_modal_nova_conta,
        )
        self.row_conta = ft.Row(
            controls=[self.dd_conta, self.btn_add_conta],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
        )

        # 8. Conta de Destino (Só Transferência)
        self.dd_destino = ft.Dropdown(
            label="Conta de destino *",
            value=self.state.destino_id,
            expand=True,
            on_select=lambda e: setattr(self.state, "destino_id", e.control.value),
            **T.dropdown_estilo(),
        )
        self.btn_add_destino = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_color=T.PRIMARY,
            tooltip="Nova Conta",
            on_click=self._abrir_modal_nova_conta,
        )
        self.row_destino = ft.Row(
            controls=[self.dd_destino, self.btn_add_destino],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
            visible=(self.state.tipo == "Transferencia"),
        )

        # 9. Parcelas (Só Crédito)
        self.dd_parcelas = ft.Dropdown(
            label="Número de Parcelas *",
            value=str(self.state.quantidade if self.state.quantidade > 1 else 1),
            options=[ft.dropdown.Option(key=str(i), text=f"{i}x") for i in range(1, 25)],
            width=160,
            on_select=self._ao_mudar_parcelas,
            **T.dropdown_estilo(),
        )
        self.lbl_resumo_parcelas = ft.Text(
            "",
            size=12,
            weight=ft.FontWeight.W_500,
            color=T.TEXT_MUTED,
        )
        self.row_parcelas = ft.Row(
            controls=[self.dd_parcelas, self.lbl_resumo_parcelas],
            alignment=ft.MainAxisAlignment.START,
            spacing=12,
            visible=False,
        )

        # 10. Categoria Universal
        self.dd_categoria = ft.Dropdown(
            label="Categoria *",
            value=self.state.categoria_id,
            expand=True,
            on_select=self._ao_mudar_categoria,
            **T.dropdown_estilo(),
        )
        self.btn_add_categoria = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_color=T.PRIMARY,
            tooltip="Nova Categoria",
            on_click=self._abrir_modal_nova_categoria,
        )
        self.row_categoria = ft.Row(
            controls=[self.dd_categoria, self.btn_add_categoria],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
            visible=(self.state.tipo != "Transferencia"),
        )

        # =====================================================================
        # SEÇÃO PROGRESSIVE DISCLOSURE: "Mais detalhes"
        # =====================================================================
        # Subcategoria
        self.dd_subcategoria = ft.Dropdown(
            label="Subcategoria",
            value=self.state.subcategoria_id,
            expand=True,
            on_select=lambda e: setattr(self.state, "subcategoria_id", e.control.value),
            **T.dropdown_estilo(),
        )
        self.btn_add_subcategoria = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_color=T.PRIMARY,
            tooltip="Nova Subcategoria",
            on_click=self._abrir_modal_nova_subcategoria,
        )
        self.row_subcategoria = ft.Row(
            controls=[self.dd_subcategoria, self.btn_add_subcategoria],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
        )

        # Subtipo
        self.dd_subtipo = ft.Dropdown(
            label="Subtipo",
            value=self.state.subtipo,
            expand=True,
            on_select=lambda e: setattr(self.state, "subtipo", e.control.value),
            **T.dropdown_estilo(),
        )
        self.btn_add_subtipo = ft.IconButton(
            icon=ft.Icons.ADD_ROUNDED,
            icon_color=T.PRIMARY,
            tooltip="Novo Subtipo",
            on_click=self._abrir_modal_novo_subtipo,
        )
        self.row_subtipo = ft.Row(
            controls=[self.dd_subtipo, self.btn_add_subtipo],
            alignment=ft.MainAxisAlignment.START,
            spacing=8,
        )

        # Regra 50/30/20 (Obrigatória em Despesa)
        self.dd_regra = ft.Dropdown(
            label="Classificação Orçamentária (Regra 50/30/20) *",
            value=self.state.regra or "Essencial",
            options=[ft.dropdown.Option(key=r, text=r) for r in REGRAS_5030],
            expand=True,
            on_select=lambda e: setattr(self.state, "regra", e.control.value),
            **T.dropdown_estilo(),
        )

        # Hora
        self.txt_hora = ft.TextField(
            label="Hora do lançamento (0 a 23)",
            value=str(self.state.hora),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=180,
            border_radius=10,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            on_change=self._ao_mudar_hora,
        )

        # Recorrência: Fixa e Repetir
        self.switch_fixa = ft.Switch(
            label="Despesa Fixa" if self.state.tipo == "Despesa" else "Receita Fixa",
            value=self.state.is_fixa,
            active_color=T.PRIMARY,
            on_change=self._ao_mudar_switch_fixa,
        )
        self.switch_repetir = ft.Switch(
            label="Repetir lançamento",
            value=self.state.is_repetir,
            active_color=T.PRIMARY,
            on_change=self._ao_mudar_switch_repetir,
        )
        self.row_switches_recorrencia = ft.Row(
            controls=[self.switch_fixa, self.switch_repetir],
            alignment=ft.MainAxisAlignment.START,
            spacing=16,
        )

        self.dd_frequencia = ft.Dropdown(
            label="Frequência *",
            value=self.state.frequencia,
            options=[
                ft.dropdown.Option(key="semanal", text="Semanal"),
                ft.dropdown.Option(key="quinzenal", text="Quinzenal"),
                ft.dropdown.Option(key="mensal", text="Mensal"),
                ft.dropdown.Option(key="bimestral", text="Bimestral"),
                ft.dropdown.Option(key="trimestral", text="Trimestral"),
                ft.dropdown.Option(key="semestral", text="Semestral"),
                ft.dropdown.Option(key="anual", text="Anual"),
            ],
            expand=True,
            on_select=self._ao_mudar_frequencia,
            **T.dropdown_estilo(),
        )

        self.txt_repetir_qtd = ft.TextField(
            label="Quantidade de repetições *",
            value=str(self.state.quantidade if self.state.quantidade >= 2 else 2),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=180,
            border_radius=10,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            on_change=self._ao_mudar_repetir_qtd,
        )

        self.lbl_resumo_repetir = ft.Text(
            "",
            size=12,
            weight=ft.FontWeight.W_500,
            color=T.PRIMARY,
        )

        self.col_opcoes_recorrencia = ft.Column(
            controls=[
                ft.Row([self.dd_frequencia, self.txt_repetir_qtd], spacing=10),
                self.lbl_resumo_repetir,
            ],
            spacing=8,
            visible=False,
        )

        self.col_detalhes = ft.Column(
            controls=[
                self.row_subcategoria,
                self.row_subtipo,
                self.dd_regra,
                self.txt_hora,
                self.row_switches_recorrencia,
                self.col_opcoes_recorrencia,
            ],
            spacing=12,
            visible=self.state.mais_detalhes_aberto,
        )

        self.btn_toggle_detalhes = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Text(
                        "Menos detalhes" if self.state.mais_detalhes_aberto else "Mais detalhes",
                        size=13,
                        weight=ft.FontWeight.BOLD,
                        color=T.PRIMARY,
                    ),
                    ft.Icon(
                        ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
                        if self.state.mais_detalhes_aberto
                        else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
                        size=18,
                        color=T.PRIMARY,
                    ),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=4,
            ),
            on_click=self._toggle_mais_detalhes,
        )

        # Montagem do Layout Principal
        self.controls = [
            self.btn_tipo,
            self.txt_valor,
            ft.Row(
                controls=[self.row_chips_data, self.switch_status],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            self.txt_descricao,
            self.dd_forma,
            self.row_conta,
            self.row_destino,
            self.row_parcelas,
            self.row_categoria,
            ft.Divider(height=1, color=T.BORDER),
            self.btn_toggle_detalhes,
            self.col_detalhes,
        ]

    # =========================================================================
    # CARREGAMENTO DE DADOS
    # =========================================================================
    def _carregar_dados_iniciais(self):
        try:
            self.contas = db.listar_contas()
            self.cartoes = db.listar_cartoes()
            self.categorias = db.listar_categorias()
        except Exception as ex:
            mostrar_feedback(self._page, f"Erro ao obter dados: {ex}", "erro")

        self._atualizar_opcoes_forma()
        self._atualizar_opcoes_conta_ou_cartao()
        self._atualizar_opcoes_categoria()
        self._atualizar_opcoes_subtipo()

        if self.state.categoria_id:
            self._carregar_subcategorias(self.state.categoria_id)

    def _carregar_subcategorias(self, cat_id: str):
        try:
            self.subcategorias = db.listar_subcategorias(cat_id)
            self.dd_subcategoria.options = [
                ft.dropdown.Option(key=str(s["id"]), text=s.get("nome", ""))
                for s in self.subcategorias
            ]
            self.dd_subcategoria.value = self.state.subcategoria_id
            self._safe_update(self.dd_subcategoria)
        except Exception:
            self.subcategorias = []
            self.dd_subcategoria.options = []
            self._safe_update(self.dd_subcategoria)

    # =========================================================================
    # SINCRONIZAÇÃO E ATUALIZAÇÃO DA UI
    # =========================================================================
    def _sincronizar_estado_com_ui(self):
        # 1. Chips de Data
        hoje = date.today()
        ontem = hoje - timedelta(days=1)
        if self.state.data_selecionada == hoje:
            self.chip_hoje.selected = True
            self.chip_ontem.selected = False
            self.chip_outros.selected = False
            self.chip_outros.label = ft.Text("Outros...")
        elif self.state.data_selecionada == ontem:
            self.chip_hoje.selected = False
            self.chip_ontem.selected = True
            self.chip_outros.selected = False
            self.chip_outros.label = ft.Text("Outros...")
        else:
            self.chip_hoje.selected = False
            self.chip_ontem.selected = False
            self.chip_outros.selected = True
            self.chip_outros.label = ft.Text(self.state.data_selecionada.strftime("%d/%m"))

        # 2. Switch Status
        self.switch_status.value = self.state.status_pago
        self.switch_status.visible = (self.state.tipo != "Transferencia")
        self.switch_status.label = "Foi recebida" if self.state.tipo == "Receita" else "Foi paga"

        # 3. Cores e Segmentos
        cor_tema = T.DESPESA if self.state.tipo == "Despesa" else (T.RECEITA if self.state.tipo == "Receita" else T.PRIMARY)
        self.txt_valor.color = cor_tema
        self.txt_valor.prefix.color = cor_tema
        self.txt_valor.focused_border_color = cor_tema

        # 4. Visibilidade de Campos Específicos
        is_transf = (self.state.tipo == "Transferencia")
        is_credito = (self.state.tipo == "Despesa" and self.state.forma_movimentacao == "Credito")

        self.row_destino.visible = is_transf
        self.row_categoria.visible = not is_transf
        self.row_parcelas.visible = is_credito
        self.dd_regra.visible = (self.state.tipo == "Despesa")

        # Switches Fixa e Repetir: Ocultos em Transferência e em Despesa+Crédito
        self.row_switches_recorrencia.visible = (not is_transf and not is_credito)
        self.switch_fixa.label = "Receita Fixa" if self.state.tipo == "Receita" else "Despesa Fixa"

        # Opções de Recorrência
        if self.state.is_fixa:
            self.col_opcoes_recorrencia.visible = True
            self.txt_repetir_qtd.visible = False
            self.lbl_resumo_repetir.value = "Lançamento agendado e materializado para os próximos 12 meses."
            self.lbl_resumo_repetir.color = T.PRIMARY
        elif self.state.is_repetir:
            self.col_opcoes_recorrencia.visible = True
            self.txt_repetir_qtd.visible = True
            self._atualizar_resumo_repetir()
        else:
            self.col_opcoes_recorrencia.visible = False

        if is_credito:
            self._atualizar_resumo_parcelas()

    def _atualizar_opcoes_forma(self):
        if self.state.tipo == "Receita":
            opcoes = ["Pix", "Dinheiro", "Boleto", "Depósito", "Transferência TED/DOC", "Outros"]
        elif self.state.tipo == "Transferencia":
            opcoes = ["Pix", "TED", "DOC", "Entre Contas"]
        else:  # Despesa
            opcoes = ["Pix", "Crédito", "Débito", "Dinheiro", "Boleto", "TED", "Outros"]

        self.dd_forma.options = [ft.dropdown.Option(key=op, text=op) for op in opcoes]
        if self.state.forma_movimentacao not in opcoes:
            self.state.forma_movimentacao = opcoes[0]
        self.dd_forma.value = self.state.forma_movimentacao
        self._safe_update(self.dd_forma)

    def _atualizar_opcoes_conta_ou_cartao(self):
        is_credito = (self.state.tipo == "Despesa" and self.state.forma_movimentacao == "Credito")
        if is_credito:
            self.dd_conta.label = "Cartão de crédito *"
            self.btn_add_conta.tooltip = "Novo Cartão"
            self.dd_conta.options = [
                ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
                for c in self.cartoes
            ]
            if not self.state.cartao_id and self.cartoes:
                self.state.cartao_id = str(self.cartoes[0]["id"])
            self.dd_conta.value = self.state.cartao_id
        else:
            self.dd_conta.label = "Conta de origem *" if self.state.tipo == "Transferencia" else "Conta *"
            self.btn_add_conta.tooltip = "Nova Conta"
            self.dd_conta.options = [
                ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
                for c in self.contas
            ]
            if not self.state.conta_id and self.contas:
                self.state.conta_id = str(self.contas[0]["id"])
            self.dd_conta.value = self.state.conta_id

        # Conta de destino para Transferência
        self.dd_destino.options = [
            ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
            for c in self.contas
        ]
        if not self.state.destino_id and len(self.contas) > 1:
            self.state.destino_id = str(self.contas[1]["id"])
        self.dd_destino.value = self.state.destino_id

        self._safe_update(self.row_conta)
        self._safe_update(self.row_destino)

    def _atualizar_opcoes_categoria(self):
        self.dd_categoria.options = [
            ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
            for c in self.categorias
        ]
        if not self.state.categoria_id and self.categorias:
            self.state.categoria_id = str(self.categorias[0]["id"])
        self.dd_categoria.value = self.state.categoria_id
        self._safe_update(self.dd_categoria)

    def _atualizar_opcoes_subtipo(self):
        if self.state.tipo == "Receita":
            opcoes = ["Salário", "Investimento", "Freelance", "Renda Extra", "Vendas", "Outros"]
        elif self.state.tipo == "Transferencia":
            opcoes = ["Entre Contas", "Reserva", "Investimento", "Outros"]
        else:
            opcoes = ["Despesa", "Alimentação", "Transporte", "Moradia", "Lazer", "Saúde", "Educação", "DJ", "Outros"]

        self.dd_subtipo.options = [ft.dropdown.Option(key=op, text=op) for op in opcoes]
        if self.state.subtipo and self.state.subtipo not in opcoes:
            self.dd_subtipo.options.append(ft.dropdown.Option(key=self.state.subtipo, text=self.state.subtipo))
        self.dd_subtipo.value = self.state.subtipo
        self._safe_update(self.dd_subtipo)

    def _atualizar_resumo_parcelas(self):
        res = resumo_parcelas(
            self.state.valor,
            self.state.quantidade,
            modo="parcelado",
            frequencia="mensal",
            data_inicio=self.state.data_selecionada,
        )
        self.lbl_resumo_parcelas.value = res
        self._safe_update(self.lbl_resumo_parcelas)

    def _atualizar_resumo_repetir(self):
        res = resumo_parcelas(
            self.state.valor,
            self.state.quantidade,
            modo="repetido",
            frequencia=self.state.frequencia,
            data_inicio=self.state.data_selecionada,
        )
        self.lbl_resumo_repetir.value = res
        self.lbl_resumo_repetir.color = T.PRIMARY
        self._safe_update(self.lbl_resumo_repetir)

    # =========================================================================
    # HANDLERS DE EVENTOS REATIVOS
    # =========================================================================
    def _ao_mudar_tipo(self, e):
        novo = list(e.control.selected)[0]
        self.state.mudar_tipo(novo)
        self._atualizar_opcoes_forma()
        self._atualizar_opcoes_conta_ou_cartao()
        self._atualizar_opcoes_subtipo()
        self._sincronizar_estado_com_ui()
        self._safe_update(self)
        self._notificar_mudanca()

    def _ao_mudar_valor(self, e):
        texto = e.control.value.replace("R$", "").strip().replace(".", "").replace(",", ".")
        try:
            val = float(texto)
            self.state.valor = max(0.0, val)
        except ValueError:
            self.state.valor = 0.0

        if self.state.tipo == "Despesa" and self.state.forma_movimentacao == "Credito":
            self._atualizar_resumo_parcelas()
        elif self.state.is_repetir:
            self._atualizar_resumo_repetir()

    def _selecionar_data_rapida(self, dt: date):
        self.state.atualizar_data(dt)
        self._sincronizar_estado_com_ui()
        self._safe_update(self.row_chips_data)
        self._safe_update(self.switch_status)
        self._notificar_mudanca()

    def _abrir_seletor_data(self, _):
        def on_date_change(e):
            val = e.control.value
            if val:
                if isinstance(val, str):
                    try:
                        d = datetime.fromisoformat(val).date()
                    except Exception:
                        d = date.today()
                elif isinstance(val, datetime):
                    d = val.date()
                else:
                    d = val
                self.state.atualizar_data(d)
                self._sincronizar_estado_com_ui()
                self._safe_update(self.row_chips_data)
                self._safe_update(self.switch_status)
                self._notificar_mudanca()

        dp = ft.DatePicker(
            value=self.state.data_selecionada,
            first_date=datetime(2020, 1, 1),
            last_date=datetime(2035, 12, 31),
            on_change=on_date_change,
        )
        self._page.show_dialog(dp)

    def _ao_tocar_switch_status(self, e):
        self.state.tocar_switch_status(bool(e.control.value))
        self._notificar_mudanca()

    def _ao_mudar_forma(self, e):
        nova_forma = e.control.value
        self.state.mudar_forma(nova_forma)
        self._atualizar_opcoes_conta_ou_cartao()
        self._sincronizar_estado_com_ui()
        self._safe_update(self)
        self._notificar_mudanca()

    def _ao_mudar_conta(self, e):
        is_credito = (self.state.tipo == "Despesa" and self.state.forma_movimentacao == "Credito")
        if is_credito:
            self.state.cartao_id = e.control.value
        else:
            self.state.conta_id = e.control.value
        self._notificar_mudanca()

    def _ao_mudar_parcelas(self, e):
        try:
            self.state.quantidade = int(e.control.value)
        except ValueError:
            self.state.quantidade = 1
        self._atualizar_resumo_parcelas()
        self._notificar_mudanca()

    def _ao_mudar_categoria(self, e):
        nova_cat = e.control.value
        self.state.mudar_categoria(nova_cat)
        self._carregar_subcategorias(nova_cat)
        self._notificar_mudanca()

    def _ao_mudar_hora(self, e):
        try:
            h = int(e.control.value)
            self.state.hora = min(23, max(0, h))
        except ValueError:
            self.state.hora = 12

    def _ao_mudar_switch_fixa(self, e):
        self.state.alternar_fixa(bool(e.control.value))
        self.switch_repetir.value = self.state.is_repetir
        self._sincronizar_estado_com_ui()
        self._safe_update(self.col_detalhes)
        self._notificar_mudanca()

    def _ao_mudar_switch_repetir(self, e):
        self.state.alternar_repetir(bool(e.control.value))
        self.switch_fixa.value = self.state.is_fixa
        self.txt_repetir_qtd.value = str(self.state.quantidade)
        self._sincronizar_estado_com_ui()
        self._safe_update(self.col_detalhes)
        self._notificar_mudanca()

    def _ao_mudar_frequencia(self, e):
        self.state.frequencia = e.control.value
        if self.state.is_repetir:
            self._atualizar_resumo_repetir()
        self._notificar_mudanca()

    def _ao_mudar_repetir_qtd(self, e):
        try:
            q = int(e.control.value)
            self.state.quantidade = max(2, q)
        except ValueError:
            self.state.quantidade = 2
        self._atualizar_resumo_repetir()
        self._notificar_mudanca()

    def _toggle_mais_detalhes(self, _):
        self.state.mais_detalhes_aberto = not self.state.mais_detalhes_aberto
        self.col_detalhes.visible = self.state.mais_detalhes_aberto
        self.btn_toggle_detalhes.content.controls[0].value = (
            "Menos detalhes" if self.state.mais_detalhes_aberto else "Mais detalhes"
        )
        self.btn_toggle_detalhes.content.controls[1].name = (
            ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
            if self.state.mais_detalhes_aberto
            else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
        )
        self._safe_update(self.btn_toggle_detalhes)
        self._safe_update(self.col_detalhes)

    # =========================================================================
    # MODAIS INLINE (+): Conta, Categoria, Subcategoria, Subtipo
    # =========================================================================
    def _abrir_modal_nova_conta(self, _):
        txt_nome = ft.TextField(
            label="Nome da Conta *",
            hint_text="Ex: Nubank, Itaú, Carteira",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o nome da conta.", "alerta")
                return
            try:
                res = db.criar_conta({"nome": nome, "tipo": "corrente", "cor": T.PRIMARY})
                modal.open = False
                self._page.update()
                self.contas = db.listar_contas()
                self._atualizar_opcoes_conta_ou_cartao()
                if res and res.data:
                    self.state.conta_id = str(res.data[0]["id"])
                    self.dd_conta.value = self.state.conta_id
                    self._safe_update(self.dd_conta)
                mostrar_feedback(self._page, f"Conta '{nome}' criada!", "sucesso")
            except Exception as ex:
                mostrar_feedback(self._page, f"Erro ao criar conta: {ex}", "erro")

        modal = ft.AlertDialog(
            title=ft.Text("Nova Conta", weight=ft.FontWeight.BOLD),
            content=ft.Column([txt_nome], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: (setattr(modal, "open", False), self._page.update())),
                ft.FilledButton("Criar Conta", style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar),
            ],
        )
        self._page.show_dialog(modal)

    def _abrir_modal_nova_categoria(self, _):
        txt_nome = ft.TextField(
            label="Nome da Categoria Universal *",
            hint_text="Ex: Alimentação, DJ, Investimento",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o nome da categoria.", "alerta")
                return
            try:
                res = db.criar_categoria({"nome": nome, "tipo": "ambos", "cor": T.PRIMARY, "icone": "category"})
                modal.open = False
                self._page.update()
                self.categorias = db.listar_categorias()
                self._atualizar_opcoes_categoria()
                if res and res.data:
                    self.state.categoria_id = str(res.data[0]["id"])
                    self.dd_categoria.value = self.state.categoria_id
                    self._carregar_subcategorias(self.state.categoria_id)
                    self._safe_update(self.dd_categoria)
                mostrar_feedback(self._page, f"Categoria '{nome}' criada!", "sucesso")
            except Exception as ex:
                mostrar_feedback(self._page, f"Erro ao criar categoria: {ex}", "erro")

        modal = ft.AlertDialog(
            title=ft.Text("Nova Categoria Universal", weight=ft.FontWeight.BOLD),
            content=ft.Column([txt_nome], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: (setattr(modal, "open", False), self._page.update())),
                ft.FilledButton("Criar", style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar),
            ],
        )
        self._page.show_dialog(modal)

    def _abrir_modal_nova_subcategoria(self, _):
        if not self.state.categoria_id:
            mostrar_feedback(self._page, "Selecione uma categoria primeiro.", "alerta")
            return

        txt_nome = ft.TextField(
            label="Nome da Subcategoria *",
            hint_text="Ex: Notebook, Gasolina, Cursos...",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o nome da subcategoria.", "alerta")
                return
            try:
                res = db.criar_subcategoria({"nome": nome, "categoria_id": self.state.categoria_id})
                modal.open = False
                self._page.update()
                self._carregar_subcategorias(self.state.categoria_id)
                if res and res.data:
                    self.state.subcategoria_id = str(res.data[0]["id"])
                    self.dd_subcategoria.value = self.state.subcategoria_id
                    self._safe_update(self.dd_subcategoria)
                mostrar_feedback(self._page, f"Subcategoria '{nome}' criada!", "sucesso")
            except Exception as ex:
                mostrar_feedback(self._page, f"Erro ao criar subcategoria: {ex}", "erro")

        modal = ft.AlertDialog(
            title=ft.Text("Nova Subcategoria", weight=ft.FontWeight.BOLD),
            content=ft.Column([txt_nome], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: (setattr(modal, "open", False), self._page.update())),
                ft.FilledButton("Criar", style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar),
            ],
        )
        self._page.show_dialog(modal)

    def _abrir_modal_novo_subtipo(self, _):
        txt_nome = ft.TextField(
            label="Novo Subtipo *",
            hint_text="Ex: Combustível, Assinatura...",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o subtipo.", "alerta")
                return
            self.state.subtipo = nome
            self.dd_subtipo.options.append(ft.dropdown.Option(key=nome, text=nome))
            self.dd_subtipo.value = nome
            self._safe_update(self.dd_subtipo)
            modal.open = False
            self._page.update()
            mostrar_feedback(self._page, f"Subtipo '{nome}' selecionado!", "sucesso")

        modal = ft.AlertDialog(
            title=ft.Text("Novo Subtipo", weight=ft.FontWeight.BOLD),
            content=ft.Column([txt_nome], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: (setattr(modal, "open", False), self._page.update())),
                ft.FilledButton("Adicionar", style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar),
            ],
        )
        self._page.show_dialog(modal)
