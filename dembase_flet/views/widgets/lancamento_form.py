"""
=============================================================================
DemBase v3 — views/widgets/lancamento_form.py (Flet 1.0.1)
Formulário de Novo / Edição de Lançamento com UI/UX moderna, layout compacto,
chips de data rápida, switch de status, progressive disclosure e regras de negócio.
=============================================================================
"""
from __future__ import annotations

import unicodedata
import uuid
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import flet as ft

from core.constants import (
    REGRAS_5030,
    FORMAS_RECEITA,
    FORMAS_DESPESA,
    FORMAS_TRANSFERENCIA,
    SUBTIPOS_RECEITA,
    SUBTIPOS_DESPESA,
    SUBTIPOS_TRANSFERENCIA,
)
from core.lancamento_state import LancamentoFormState, is_credito_str
from core.recorrencia import resumo_parcelas
import core.theme as T
from core.theme import pad, borda, mostrar_feedback
import services.supabase_client as db


def _norm(texto: Optional[str]) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def _is_uuid(val) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val).strip())
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _botao_add_verde(on_click, tooltip: str) -> ft.IconButton:
    """Botão verde (+) colado ao lado direito do Dropdown (Flet 1.0.1)."""
    return ft.IconButton(
        icon=ft.Icons.ADD_ROUNDED,
        icon_color=ft.Colors.WHITE,
        bgcolor=T.PRIMARY,
        width=44,
        height=44,
        tooltip=tooltip,
        on_click=on_click,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=10),
        ),
    )


class LancamentoForm(ft.Column):
    """
    Componente reutilizável do formulário de lançamento (Flet 1.0.1).
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
            if getattr(ctrl, "page", None) is not None:
                ctrl.update()
        except Exception:
            pass

    def _notificar_mudanca(self):
        if self.on_state_change:
            self.on_state_change()

    # =========================================================================
    # RESOLUÇÃO SEGURA DE UUIDs DE DROPDOWNS (FLET 1.0.1)
    # =========================================================================
    def _obter_cat_id(self, val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        val_str = str(val).strip()
        if _is_uuid(val_str):
            return val_str
        for c in self.categorias:
            if str(c.get("id")) == val_str or str(c.get("nome", "")).strip().lower() == val_str.lower():
                return str(c["id"])
        return None

    def _obter_subcat_id(self, val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        val_str = str(val).strip()
        if _is_uuid(val_str):
            return val_str
        for s in self.subcategorias:
            if str(s.get("id")) == val_str or str(s.get("nome", "")).strip().lower() == val_str.lower():
                return str(s["id"])
        return None

    def _obter_conta_id(self, val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        val_str = str(val).strip()
        if _is_uuid(val_str):
            return val_str
        for c in self.contas:
            if str(c.get("id")) == val_str or str(c.get("nome", "")).strip().lower() == val_str.lower():
                return str(c["id"])
        return None

    def _obter_cartao_id(self, val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        val_str = str(val).strip()
        if _is_uuid(val_str):
            return val_str
        for c in self.cartoes:
            if str(c.get("id")) == val_str or str(c.get("nome", "")).strip().lower() == val_str.lower():
                return str(c["id"])
        return None

    # =========================================================================
    # CONSTRUÇÃO DOS CONTROLES
    # =========================================================================
    def _construir_controles(self):
        # 1. Seletor de Tipo (SegmentedButton — Flet 1.0.1 exige selected como list[str], NUNCA set!)
        self.btn_tipo = ft.SegmentedButton(
            selected=[self.state.tipo],
            allow_multiple_selection=False,
            allow_empty_selection=False,
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
        cor_valor = (
            T.DESPESA
            if self.state.eh_despesa
            else (T.RECEITA if self.state.eh_receita else T.PRIMARY)
        )
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

        # 3. Chips de Data Rápida (Flet 1.0.1: usar on_select para renderizar estado selected)
        self.chip_hoje = ft.Chip(
            label=ft.Text("Hoje"),
            selected=False,
            on_select=lambda _: self._selecionar_data_rapida(date.today()),
        )
        self.chip_ontem = ft.Chip(
            label=ft.Text("Ontem"),
            selected=False,
            on_select=lambda _: self._selecionar_data_rapida(date.today() - timedelta(days=1)),
        )
        self.chip_outros = ft.Chip(
            label=ft.Text("Outros..."),
            selected=False,
            leading=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=16),
            on_select=self._abrir_seletor_data,
        )
        self.row_chips_data = ft.Row(
            controls=[self.chip_hoje, self.chip_ontem, self.chip_outros],
            spacing=8,
        )

        # 4. Switch de Status
        label_switch = "Foi paga" if self.state.eh_despesa else "Foi recebida"
        self.switch_status = ft.Switch(
            label=label_switch,
            value=self.state.status_pago,
            active_color=T.PRIMARY,
            on_change=self._ao_tocar_switch_status,
        )

        # 5. Descrição
        self.txt_descricao = ft.TextField(
            label="Descrição",
            hint_text="Ex: Supermercado, Aluguel, Salário...",
            value=self.state.descricao,
            border_radius=10,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            on_change=lambda e: setattr(self.state, "descricao", e.control.value or ""),
        )

        # 6. Forma de Movimentação (Sempre Visível na Área Principal - Decisão 5)
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
        self.btn_add_conta = _botao_add_verde(
            on_click=self._abrir_modal_nova_conta_ou_cartao,
            tooltip="Nova Conta",
        )
        self.row_conta = ft.Row(
            controls=[self.dd_conta, self.btn_add_conta],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

        # 8. Conta de Destino (Só Transferência)
        self.dd_destino = ft.Dropdown(
            label="Conta de destino *",
            value=self.state.destino_id,
            expand=True,
            on_select=self._ao_mudar_destino,
            **T.dropdown_estilo(),
        )
        self.btn_add_destino = _botao_add_verde(
            on_click=lambda _: self._abrir_modal_nova_conta(eh_destino=True),
            tooltip="Nova Conta de Destino",
        )
        self.row_destino = ft.Row(
            controls=[self.dd_destino, self.btn_add_destino],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            visible=self.state.eh_transferencia,
        )

        # 9. Parcelas (Só Crédito - Decisão 2)
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
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
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
        self.btn_add_categoria = _botao_add_verde(
            on_click=self._abrir_modal_nova_categoria,
            tooltip="Nova Categoria",
        )
        self.row_categoria = ft.Row(
            controls=[self.dd_categoria, self.btn_add_categoria],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            visible=(not self.state.eh_transferencia),
        )

        # =====================================================================
        # SEÇÃO PROGRESSIVE DISCLOSURE: "Mais detalhes" (Decisão 4)
        # =====================================================================
        # Subcategoria
        self.dd_subcategoria = ft.Dropdown(
            label="Subcategoria",
            value=self.state.subcategoria_id,
            expand=True,
            on_select=self._ao_mudar_subcategoria,
            **T.dropdown_estilo(),
        )
        self.btn_add_subcategoria = _botao_add_verde(
            on_click=self._abrir_modal_nova_subcategoria,
            tooltip="Nova Subcategoria",
        )
        self.row_subcategoria = ft.Row(
            controls=[self.dd_subcategoria, self.btn_add_subcategoria],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            visible=(not self.state.eh_transferencia),
        )

        # Subtipo
        self.dd_subtipo = ft.Dropdown(
            label="Subtipo",
            value=self.state.subtipo,
            expand=True,
            on_select=self._ao_mudar_subtipo,
            **T.dropdown_estilo(),
        )
        self.btn_add_subtipo = _botao_add_verde(
            on_click=self._abrir_modal_novo_subtipo,
            tooltip="Novo Subtipo",
        )
        self.row_subtipo = ft.Row(
            controls=[self.dd_subtipo, self.btn_add_subtipo],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        )

        # Regra 50/30/20 (Obrigatória em Despesa)
        self.dd_regra = ft.Dropdown(
            label="Classificação Orçamentária (Regra 50/30/20) *",
            value=self.state.regra or "Essencial",
            options=[ft.dropdown.Option(key=r, text=r) for r in REGRAS_5030],
            expand=True,
            on_select=self._ao_mudar_regra,
            **T.dropdown_estilo(),
        )

        # Hora
        self.txt_hora = ft.TextField(
            label="Hora do lançamento (0 a 23)",
            value=str(self.state.hora),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
            border_radius=10,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            on_change=self._ao_mudar_hora,
        )

        # Recorrência: Fixa e Repetir (Dentro de "Mais detalhes" - Decisão 4)
        self.switch_fixa = ft.Switch(
            label="Despesa Fixa" if self.state.eh_despesa else "Receita Fixa",
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
            label="Quantidade *",
            value=str(self.state.quantidade if self.state.quantidade >= 2 else 2),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=140,
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

        self.lbl_toggle_detalhes = ft.Text(
            "Menos detalhes" if self.state.mais_detalhes_aberto else "Mais detalhes",
            size=13,
            weight=ft.FontWeight.BOLD,
            color=T.PRIMARY,
        )
        self.ico_toggle_detalhes = ft.Icon(
            ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
            if self.state.mais_detalhes_aberto
            else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED,
            size=18,
            color=T.PRIMARY,
        )

        self.btn_toggle_detalhes = ft.TextButton(
            content=ft.Row(
                controls=[
                    self.lbl_toggle_detalhes,
                    self.ico_toggle_detalhes,
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

    def _carregar_subcategorias(self, cat_id: Optional[str]):
        cat_uuid = self._obter_cat_id(cat_id)
        if not cat_uuid:
            self.subcategorias = []
            self.dd_subcategoria.options = []
            self.dd_subcategoria.value = None
            self._safe_update(self.dd_subcategoria)
            return

        try:
            self.subcategorias = db.listar_subcategorias(cat_uuid)
            self.dd_subcategoria.options = [
                ft.dropdown.Option(key=str(s["id"]), text=s.get("nome", ""))
                for s in self.subcategorias
                if s.get("id")
            ]
            # Garante que subcategoria_id pertence às opções carregadas
            ids_validos = {str(s["id"]) for s in self.subcategorias if s.get("id")}
            if self.state.subcategoria_id not in ids_validos:
                self.state.subcategoria_id = None
            self.dd_subcategoria.value = self.state.subcategoria_id
            self._safe_update(self.dd_subcategoria)
        except Exception:
            self.subcategorias = []
            self.dd_subcategoria.options = []
            self.dd_subcategoria.value = None
            self._safe_update(self.dd_subcategoria)

    # =========================================================================
    # SINCRONIZAÇÃO E ATUALIZAÇÃO DA UI
    # =========================================================================
    def _sincronizar_estado_com_ui(self):
        # 0. SegmentedButton (SEMPRE list[str], NUNCA set!)
        self.btn_tipo.selected = [self.state.tipo]

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
        self.switch_status.visible = (not self.state.eh_transferencia)
        self.switch_status.label = "Foi recebida" if self.state.eh_receita else "Foi paga"

        # 3. Cores e Segmentos
        cor_tema = (
            T.DESPESA
            if self.state.eh_despesa
            else (T.RECEITA if self.state.eh_receita else T.PRIMARY)
        )
        self.txt_valor.color = cor_tema
        self.txt_valor.prefix.color = cor_tema
        self.txt_valor.focused_border_color = cor_tema

        # 4. Visibilidade de Campos Específicos
        is_transf = self.state.eh_transferencia
        is_credito = self.state.eh_credito

        self.row_destino.visible = is_transf
        self.row_categoria.visible = not is_transf
        self.row_subcategoria.visible = not is_transf
        self.row_parcelas.visible = is_credito
        self.dd_regra.visible = self.state.eh_despesa

        # Switches Fixa e Repetir: Ocultos em Transferência e em Despesa+Crédito (Decisão 2 e 3)
        self.row_switches_recorrencia.visible = (not is_transf and not is_credito)
        self.switch_fixa.label = "Receita Fixa" if self.state.eh_receita else "Despesa Fixa"

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
        if self.state.eh_receita:
            opcoes = list(FORMAS_RECEITA)
        elif self.state.eh_transferencia:
            opcoes = list(FORMAS_TRANSFERENCIA)
        else:  # Despesa
            opcoes = list(FORMAS_DESPESA)

        # Normaliza forma caso venha do banco sem acento ("Credito" -> "Crédito", "Debito" -> "Débito")
        forma_atual_norm = _norm(self.state.forma_movimentacao)
        forma_encontrada = None
        for op in opcoes:
            if _norm(op) == forma_atual_norm:
                forma_encontrada = op
                break

        if forma_encontrada:
            self.state.forma_movimentacao = forma_encontrada
        else:
            self.state.forma_movimentacao = "Pix" if "Pix" in opcoes else opcoes[0]

        self.dd_forma.options = [ft.dropdown.Option(key=op, text=op) for op in opcoes]
        self.dd_forma.value = self.state.forma_movimentacao
        self._safe_update(self.dd_forma)

    def _atualizar_opcoes_conta_ou_cartao(self):
        is_credito = self.state.eh_credito
        if is_credito:
            self.dd_conta.label = "Cartão de crédito *"
            self.btn_add_conta.tooltip = "Novo Cartão"
            self.dd_conta.options = [
                ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
                for c in self.cartoes
                if c.get("id")
            ]
            ids_cartoes = {str(c["id"]) for c in self.cartoes if c.get("id")}
            if self.state.cartao_id not in ids_cartoes:
                self.state.cartao_id = str(self.cartoes[0]["id"]) if self.cartoes else None
            self.dd_conta.value = self.state.cartao_id
        else:
            self.dd_conta.label = "Conta de origem *" if self.state.eh_transferencia else "Conta *"
            self.btn_add_conta.tooltip = "Nova Conta"
            self.dd_conta.options = [
                ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
                for c in self.contas
                if c.get("id")
            ]
            ids_contas = {str(c["id"]) for c in self.contas if c.get("id")}
            if self.state.conta_id not in ids_contas:
                self.state.conta_id = str(self.contas[0]["id"]) if self.contas else None
            self.dd_conta.value = self.state.conta_id

        # Conta de destino para Transferência
        self.dd_destino.options = [
            ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
            for c in self.contas
            if c.get("id")
        ]
        ids_contas = {str(c["id"]) for c in self.contas if c.get("id")}
        if self.state.destino_id not in ids_contas:
            if len(self.contas) > 1:
                # Escolhe uma conta diferente da conta de origem
                for c in self.contas:
                    cid = str(c["id"])
                    if cid != self.state.conta_id:
                        self.state.destino_id = cid
                        break
            elif self.contas:
                self.state.destino_id = str(self.contas[0]["id"])
            else:
                self.state.destino_id = None
        self.dd_destino.value = self.state.destino_id

        self._safe_update(self.row_conta)
        self._safe_update(self.row_destino)

    def _atualizar_opcoes_categoria(self):
        self.dd_categoria.options = [
            ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
            for c in self.categorias
            if c.get("id")
        ]
        ids_cats = {str(c["id"]) for c in self.categorias if c.get("id")}
        if self.state.categoria_id not in ids_cats:
            self.state.categoria_id = str(self.categorias[0]["id"]) if self.categorias else None
        self.dd_categoria.value = self.state.categoria_id
        self._safe_update(self.dd_categoria)

    def _atualizar_opcoes_subtipo(self):
        if self.state.eh_receita:
            opcoes = list(SUBTIPOS_RECEITA)
        elif self.state.eh_transferencia:
            opcoes = list(SUBTIPOS_TRANSFERENCIA)
        else:
            opcoes = list(SUBTIPOS_DESPESA)

        if self.state.subtipo and self.state.subtipo not in opcoes:
            opcoes.append(self.state.subtipo)

        if not self.state.subtipo and opcoes:
            self.state.subtipo = opcoes[0]

        self.dd_subtipo.options = [ft.dropdown.Option(key=op, text=op) for op in opcoes]
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
        sel = e.control.selected
        if isinstance(sel, (list, set, tuple)) and len(sel) > 0:
            novo = list(sel)[0]
        else:
            novo = self.state.tipo
        # Garante que e.control.selected seja sempre list[str] para o msgpack do Flet 1.0.1
        e.control.selected = [novo]

        self.state.mudar_tipo(novo)
        self._atualizar_opcoes_forma()
        self._atualizar_opcoes_conta_ou_cartao()
        self._atualizar_opcoes_categoria()
        self._atualizar_opcoes_subtipo()
        if self.state.categoria_id:
            self._carregar_subcategorias(self.state.categoria_id)
        else:
            self._carregar_subcategorias(None)
        self._sincronizar_estado_com_ui()
        self._safe_update(self)
        self._notificar_mudanca()

    def _ao_mudar_valor(self, e):
        texto = (e.control.value or "").replace("R$", "").strip().replace(".", "").replace(",", ".")
        try:
            val = float(texto)
            self.state.valor = max(0.0, val)
        except ValueError:
            self.state.valor = 0.0

        if self.state.eh_credito:
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
        # Restaura estado visual dos chips caso o usuário cancele o DatePicker
        self._sincronizar_estado_com_ui()
        self._safe_update(self.row_chips_data)

        def on_date_change(e):
            val = e.control.value
            if val:
                if isinstance(val, str):
                    try:
                        d = datetime.fromisoformat(val[:10]).date()
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
        nova_forma = e.data or e.control.value
        self.state.mudar_forma(nova_forma)
        self._atualizar_opcoes_conta_ou_cartao()
        self._sincronizar_estado_com_ui()
        self._safe_update(self)
        self._notificar_mudanca()

    def _ao_mudar_conta(self, e):
        val = e.data or e.control.value
        if self.state.eh_credito:
            self.state.cartao_id = self._obter_cartao_id(val)
        else:
            self.state.conta_id = self._obter_conta_id(val)
        self._notificar_mudanca()

    def _ao_mudar_destino(self, e):
        val = e.data or e.control.value
        self.state.destino_id = self._obter_conta_id(val)
        self._notificar_mudanca()

    def _ao_mudar_parcelas(self, e):
        val = e.data or e.control.value
        try:
            self.state.quantidade = int(str(val).replace("x", "").strip())
        except ValueError:
            self.state.quantidade = 1
        self._atualizar_resumo_parcelas()
        self._notificar_mudanca()

    def _ao_mudar_categoria(self, e):
        val = e.data or e.control.value
        nova_cat = self._obter_cat_id(val)
        self.state.mudar_categoria(nova_cat)
        self.dd_categoria.value = nova_cat
        self._carregar_subcategorias(nova_cat)
        self._notificar_mudanca()

    def _ao_mudar_subcategoria(self, e):
        val = e.data or e.control.value
        self.state.subcategoria_id = self._obter_subcat_id(val)
        self._notificar_mudanca()

    def _ao_mudar_subtipo(self, e):
        val = e.data or e.control.value
        self.state.subtipo = val
        self._notificar_mudanca()

    def _ao_mudar_regra(self, e):
        val = e.data or e.control.value
        self.state.regra = val
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
        val = e.data or e.control.value
        self.state.frequencia = val or "mensal"
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
        self.lbl_toggle_detalhes.value = (
            "Menos detalhes" if self.state.mais_detalhes_aberto else "Mais detalhes"
        )
        # Flet 1.0.1: Icon usa propriedade .icon (NUNCA .name!)
        self.ico_toggle_detalhes.icon = (
            ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
            if self.state.mais_detalhes_aberto
            else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
        )
        self._safe_update(self.btn_toggle_detalhes)
        self._safe_update(self.col_detalhes)

    # =========================================================================
    # MODAIS INLINE (+): Conta/Cartão, Categoria, Subcategoria, Subtipo
    # =========================================================================
    def _abrir_modal_nova_conta_ou_cartao(self, _):
        if self.state.eh_credito:
            self._abrir_modal_novo_cartao()
        else:
            self._abrir_modal_nova_conta(eh_destino=False)

    def _abrir_modal_nova_conta(self, eh_destino: bool = False):
        txt_nome = ft.TextField(
            label="Nome da Conta *",
            hint_text="Ex: Nubank, Itaú, Carteira",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = (txt_nome.value or "").strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o nome da conta.", "alerta")
                return
            try:
                res = db.criar_conta({"nome": nome, "tipo": "corrente", "cor": T.PRIMARY})
                modal.open = False
                self._page.update()
                self.contas = db.listar_contas()
                if res and res.data:
                    novo_id = str(res.data[0]["id"])
                    if eh_destino:
                        self.state.destino_id = novo_id
                    else:
                        self.state.conta_id = novo_id
                self._atualizar_opcoes_conta_ou_cartao()
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

    def _abrir_modal_novo_cartao(self):
        txt_nome = ft.TextField(
            label="Nome do Cartão *",
            hint_text="Ex: Nubank Ultravioleta, Inter...",
            autofocus=True,
            **T.campo_estilo(),
        )
        txt_limite = ft.TextField(
            label="Limite Total (R$)",
            value="5000",
            keyboard_type=ft.KeyboardType.NUMBER,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = (txt_nome.value or "").strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o nome do cartão.", "alerta")
                return
            try:
                lim = float((txt_limite.value or "0").replace(".", "").replace(",", "."))
            except ValueError:
                lim = 0.0
            try:
                res = db.criar_cartao({
                    "nome": nome,
                    "bandeira": "Mastercard",
                    "cor": T.PRIMARY,
                    "limite_total": lim,
                    "dia_fechamento": 1,
                    "dia_vencimento": 10,
                })
                modal.open = False
                self._page.update()
                self.cartoes = db.listar_cartoes()
                if res and res.data:
                    self.state.cartao_id = str(res.data[0]["id"])
                self._atualizar_opcoes_conta_ou_cartao()
                mostrar_feedback(self._page, f"Cartão '{nome}' criado!", "sucesso")
            except Exception as ex:
                mostrar_feedback(self._page, f"Erro ao criar cartão: {ex}", "erro")

        modal = ft.AlertDialog(
            title=ft.Text("Novo Cartão de Crédito", weight=ft.FontWeight.BOLD),
            content=ft.Column([txt_nome, txt_limite], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: (setattr(modal, "open", False), self._page.update())),
                ft.FilledButton("Criar Cartão", style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar),
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
            nome = (txt_nome.value or "").strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o nome da categoria.", "alerta")
                return
            try:
                res = db.criar_categoria({"nome": nome, "tipo": "ambos", "cor": T.PRIMARY, "icone": "category"})
                modal.open = False
                self._page.update()
                self.categorias = db.listar_categorias()
                if res and res.data:
                    self.state.categoria_id = str(res.data[0]["id"])
                self._atualizar_opcoes_categoria()
                if self.state.categoria_id:
                    self._carregar_subcategorias(self.state.categoria_id)
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
        cat_uuid = self._obter_cat_id(self.state.categoria_id)
        if not cat_uuid:
            mostrar_feedback(self._page, "Selecione uma categoria primeiro.", "alerta")
            return

        txt_nome = ft.TextField(
            label="Nome da Subcategoria *",
            hint_text="Ex: Notebook, Gasolina, Cursos...",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar(_):
            nome = (txt_nome.value or "").strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o nome da subcategoria.", "alerta")
                return
            try:
                res = db.criar_subcategoria(cat_uuid, nome)
                modal.open = False
                self._page.update()
                if res and res.data:
                    self.state.subcategoria_id = str(res.data[0]["id"])
                self._carregar_subcategorias(cat_uuid)
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
            nome = (txt_nome.value or "").strip()
            if not nome:
                mostrar_feedback(self._page, "Informe o subtipo.", "alerta")
                return
            self.state.subtipo = nome
            self._atualizar_opcoes_subtipo()
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
