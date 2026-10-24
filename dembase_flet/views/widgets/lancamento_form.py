"""
=============================================================================
DemBase v3 — views/widgets/lancamento_form.py (Flet 1.0.1)
Formulário de Novo / Edição de Lançamento com UI/UX moderna, layout compacto,
chips de data rápida, switch de status, progressive disclosure e regras de negócio.
=============================================================================
"""
from __future__ import annotations

import re
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
from core.lancamento_state import LancamentoFormState
from core.recorrencia import resumo_parcelas
import core.theme as T
from core.theme import pad, borda, mostrar_feedback
from views.widgets.custom_date_picker import (
    abrir_seletor_data_modal,
    formatar_data_amigavel,
    formatar_data_curta_amigavel,
)
import services.supabase_client as db
import services.potes_service as potes_svc


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


def formatar_moeda_input(valor: float) -> str:
    """
    Formata valor numérico para exibição brasileira de moeda sem o prefixo R$
    (ex: 0.0 -> '0,00', 0.01 -> '0,01', 1.23 -> '1,23', 1234.56 -> '1.234,56').
    """
    centavos = int(round((valor or 0.0) * 100))
    inteiro = centavos // 100
    resto = centavos % 100
    return f"{inteiro:,}".replace(",", ".") + f",{resto:02d}"


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
        self._page = page
        self.state = state
        self.on_state_change = on_state_change

        # Listas de dados carregadas do Supabase
        self.contas: list[dict] = []
        self.cartoes: list[dict] = []
        self.categorias: list[dict] = []
        self.subcategorias: list[dict] = []

        # 1. Constrói os controles filhos antes do super().__init__ (padrão dataclass Flet 1.0.1)
        controles_iniciais = self._construir_controles()
        super().__init__(
            spacing=14,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=controles_iniciais,
        )

        # 2. Carrega dados do banco e sincroniza estado inicial
        self._carregar_dados_iniciais()
        self._sincronizar_estado_com_ui()

        # Limpa _dirty pós-construção para que o diff incremental do Flet 1.0.1 parta de base limpa
        if hasattr(self, "_dirty"):
            self._dirty.clear()

    def _safe_update(self, ctrl: Optional[ft.Control] = None):
        """Atualiza o controle específico e a página com segurança no Flet 1.0.1."""
        if ctrl is not None:
            try:
                ctrl.update()
            except Exception:
                pass
        try:
            self.update()
        except Exception:
            pass
        try:
            if self._page is not None:
                self._page.update()
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
    def _construir_controles(self) -> list[ft.Control]:
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
        str_val = formatar_moeda_input(self.state.valor)
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
            on_blur=self._ao_sair_do_valor,
            on_focus=self._ao_focar_valor,
        )

        # 3. Seletor de Data Estilo Mobills (Card Clicável + Atalhos Rápidos)
        self.txt_data_label = ft.Text(
            formatar_data_amigavel(self.state.data_selecionada),
            size=12.5,
            weight=ft.FontWeight.BOLD,
            color=T.TEXT_PRIMARY,
        )
        self.card_seletor_data = ft.Container(
            content=ft.Row(
                spacing=8,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=15),
                        padding=pad(all_=5),
                        bgcolor=f"{T.PRIMARY}18",
                        border_radius=7,
                    ),
                    self.txt_data_label,
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=T.TEXT_MUTED, size=18),
                ],
            ),
            padding=pad(h=10, v=6),
            bgcolor=T.SURFACE,
            border_radius=10,
            border=borda(1, T.BORDER),
            ink=True,
            on_click=self._abrir_seletor_data,
            tooltip="Clique para alterar a data",
        )

        self.chip_hoje = ft.Container()
        self.chip_ontem = ft.Container()
        self.chip_amanha = ft.Container()
        self.chip_outros = ft.Container()
        self.row_chips_data = ft.Row(spacing=6, wrap=True)
        self._construir_chips_data()

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

        # 8.1 Fatura do Cartão (Seleção manual opcional)
        self.dd_fatura = ft.Dropdown(
            label="Fatura de destino (opcional)",
            value="",
            expand=True,
            on_select=self._ao_mudar_fatura,
            **T.dropdown_estilo(),
        )
        self.row_fatura = ft.Row(
            controls=[self.dd_fatura],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            visible=False,
        )

        # 9. Modalidade no Cartão de Crédito: Parcelas vs Recorrência Contínua
        self.seg_credito_tipo = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="parcelado",
                    label=ft.Text("Parcelas", size=12.5, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.PAYMENTS_ROUNDED, size=16),
                ),
                ft.Segment(
                    value="recorrente",
                    label=ft.Text("Recorrência", size=12.5, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.ALL_INCLUSIVE_ROUNDED, size=16),
                ),
            ],
            selected=["recorrente" if self.state.is_fixa else "parcelado"],
            on_change=self._ao_mudar_credito_tipo,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        # 9.1 Seletor de Cálculo do Parcelamento (Valor Total vs Valor da Parcela)
        self.seg_modo_parcela = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="total",
                    label=ft.Text("Valor Total", size=11.5, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.ATTACH_MONEY_ROUNDED, size=15),
                ),
                ft.Segment(
                    value="parcela",
                    label=ft.Text("Valor da Parcela", size=11.5, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.PAYMENTS_ROUNDED, size=15),
                ),
            ],
            selected=[self.state.modo_calculo_parcela],
            on_change=self._ao_mudar_modo_calculo_parcela,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
        )
        self.row_modo_parcela = ft.Row(
            controls=[self.seg_modo_parcela],
            alignment=ft.MainAxisAlignment.START,
            visible=(not self.state.is_fixa),
        )

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
        self.row_detalhe_parcelas = ft.Row(
            controls=[self.dd_parcelas, self.lbl_resumo_parcelas],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
            visible=(not self.state.is_fixa),
        )
        self.card_credito_recorrente_info = ft.Container(
            padding=pad(h=12, v=8),
            bgcolor=f"{T.PRIMARY}14",
            border_radius=10,
            border=borda(1, f"{T.PRIMARY}40"),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.AUTORENEW_ROUNDED, color=T.PRIMARY, size=18),
                    ft.Column(
                        spacing=1,
                        tight=True,
                        controls=[
                            ft.Text(
                                "Assinatura / Cobrança Fixa Contínua",
                                color=T.PRIMARY,
                                size=12.5,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "Cobrada mensalmente na fatura sem término de parcelas.",
                                color=T.TEXT_MUTED,
                                size=11,
                            ),
                        ],
                    ),
                ],
            ),
            visible=self.state.is_fixa,
        )
        self.row_parcelas = ft.Column(
            controls=[
                self.seg_credito_tipo,
                self.row_modo_parcela,
                self.row_detalhe_parcelas,
                self.card_credito_recorrente_info,
            ],
            spacing=8,
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

        # Potes Financeiros (Obrigatório em Despesa)
        try:
            potes_usuario = potes_svc.carregar_potes()
        except Exception:
            potes_usuario = []

        if potes_usuario:
            def _p_id(p):
                val = getattr(p, "id", None)
                if val is None and isinstance(p, dict): val = p.get("id")
                return str(val) if val is not None else ""

            def _p_nome(p):
                val = getattr(p, "nome", None)
                if val is None and isinstance(p, dict): val = p.get("nome")
                return str(val) if val is not None else "Pote"

            def _p_perc(p):
                val = getattr(p, "percentual", None)
                if val is None and isinstance(p, dict): val = p.get("percentual")
                try: return float(val) if val is not None else 0.0
                except Exception: return 0.0

            opcoes_regra = [ft.dropdown.Option(key=_p_id(p), text=f"{_p_nome(p)} ({_p_perc(p):g}%)") for p in potes_usuario]
            val_pote = str(self.state.pote_id) if self.state.pote_id else (_p_id(potes_usuario[0]) if potes_usuario else None)
            if not self.state.pote_id and potes_usuario:
                self.state.pote_id = _p_id(potes_usuario[0])
        else:
            opcoes_regra = [ft.dropdown.Option(key=r, text=r) for r in REGRAS_5030]
            val_pote = self.state.regra or "Essencial"

        self.dd_regra = ft.Dropdown(
            label="Pote Financeiro *",
            value=val_pote,
            options=opcoes_regra,
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
            key="sec_detalhes",
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
                tight=True,
                spacing=4,
            ),
            on_click=self._toggle_mais_detalhes,
        )

        return [
            self.btn_tipo,
            self.txt_valor,
            ft.Container(
                content=ft.Column(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Row(
                            controls=[self.card_seletor_data, self.switch_status],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        self.row_chips_data,
                    ],
                ),
                padding=pad(bottom=4),
            ),
            self.txt_descricao,
            self.dd_forma,
            self.row_conta,
            self.row_destino,
            self.row_fatura,
            self.row_parcelas,
            self.row_categoria,
            ft.Divider(height=1, color=T.BORDER),
            ft.Row([self.btn_toggle_detalhes], alignment=ft.MainAxisAlignment.CENTER),
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

        self._atualizar_opcoes_forma(atualizar_ui=False)
        self._atualizar_opcoes_conta_ou_cartao(atualizar_ui=False)
        self._atualizar_opcoes_fatura(atualizar_ui=False)
        self._atualizar_opcoes_categoria(atualizar_ui=False)
        self._atualizar_opcoes_subtipo(atualizar_ui=False)

        if self.state.categoria_id:
            self._carregar_subcategorias(self.state.categoria_id, atualizar_ui=False)

    def _carregar_subcategorias(self, cat_id: Optional[str], atualizar_ui: bool = True):
        cat_uuid = self._obter_cat_id(cat_id)
        if not cat_uuid:
            self.subcategorias = []
            self.dd_subcategoria.options = []
            self.dd_subcategoria.value = None
            if atualizar_ui:
                self._safe_update(self.dd_subcategoria)
            return

        try:
            self.subcategorias = db.listar_subcategorias(cat_uuid)
            self.dd_subcategoria.options = [
                ft.dropdown.Option(key=str(s["id"]), text=s.get("nome", ""))
                for s in self.subcategorias
                if s.get("id")
            ]
            ids_validos = {str(s["id"]) for s in self.subcategorias if s.get("id")}
            if self.state.subcategoria_id not in ids_validos:
                self.state.subcategoria_id = None
            self.dd_subcategoria.value = self.state.subcategoria_id
            if atualizar_ui:
                self._safe_update(self.dd_subcategoria)
        except Exception:
            self.subcategorias = []
            self.dd_subcategoria.options = []
            self.dd_subcategoria.value = None
            if atualizar_ui:
                self._safe_update(self.dd_subcategoria)

    def _construir_chips_data(self):
        hoje = date.today()
        ontem = hoje - timedelta(days=1)
        amanha = hoje + timedelta(days=1)
        data_sel = self.state.data_selecionada

        def _criar_chip(label: str, dt_alvo: date | None, ativo: bool, eh_outros: bool = False):
            return ft.Container(
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=13, color=T.ON_PRIMARY if ativo else T.TEXT_MUTED)
                        if eh_outros else ft.Container(),
                        ft.Text(
                            label,
                            size=11,
                            weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                            color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                        ),
                    ],
                ),
                padding=pad(h=9, v=5),
                bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                border_radius=12,
                border=borda(1, T.PRIMARY if ativo else T.BORDER),
                ink=True,
                on_click=(lambda _: self._abrir_seletor_data()) if eh_outros else (lambda _, d=dt_alvo: self._selecionar_data_rapida(d)),
            )

        eh_hoje = (data_sel == hoje)
        eh_ontem = (data_sel == ontem)
        eh_amanha = (data_sel == amanha)
        eh_outra = not (eh_hoje or eh_ontem or eh_amanha)

        self.chip_ontem = _criar_chip("Ontem", ontem, eh_ontem)
        self.chip_hoje = _criar_chip("Hoje", hoje, eh_hoje)
        self.chip_amanha = _criar_chip("Amanhã", amanha, eh_amanha)
        label_outros = data_sel.strftime("%d/%m") if eh_outra else "Outros..."
        self.chip_outros = _criar_chip(label_outros, None, eh_outra, eh_outros=True)

        self.row_chips_data.controls = [
            self.chip_ontem,
            self.chip_hoje,
            self.chip_amanha,
            self.chip_outros,
        ]

    # =========================================================================
    # SINCRONIZAÇÃO E ATUALIZAÇÃO DA UI
    # =========================================================================
    def _sincronizar_estado_com_ui(self):
        # 0. SegmentedButton (SEMPRE list[str], NUNCA set!)
        self.btn_tipo.selected = [self.state.tipo]

        # 1. Seletor de Data e Chips
        self.txt_data_label.value = formatar_data_amigavel(self.state.data_selecionada)
        self._construir_chips_data()

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
        self.row_fatura.visible = is_credito
        self.row_parcelas.visible = is_credito
        self.dd_regra.visible = self.state.eh_despesa

        # Switches Fixa e Repetir: Ocultos em Transferência e em Despesa+Crédito (já que crédito usa o seletor dedicado)
        self.row_switches_recorrencia.visible = (not is_transf and not is_credito)
        self.switch_fixa.label = "Receita Fixa" if self.state.eh_receita else "Despesa Fixa"

        # Opções de Recorrência
        if self.state.is_fixa:
            self.col_opcoes_recorrencia.visible = True
            self.txt_repetir_qtd.visible = False
            if is_credito:
                self.lbl_resumo_repetir.value = "Assinatura contínua agendada e materializada na fatura do cartão para os próximos 12 meses."
            else:
                self.lbl_resumo_repetir.value = "Lançamento agendado e materializado para os próximos 12 meses."
            self.lbl_resumo_repetir.color = T.PRIMARY
        elif self.state.is_repetir:
            self.col_opcoes_recorrencia.visible = True
            self.txt_repetir_qtd.visible = True
            self._atualizar_resumo_repetir(atualizar_ui=False)
        else:
            self.col_opcoes_recorrencia.visible = False

        if is_credito:
            self.seg_credito_tipo.selected = ["recorrente" if self.state.is_fixa else "parcelado"]
            self.seg_modo_parcela.selected = [self.state.modo_calculo_parcela]
            self.row_modo_parcela.visible = not self.state.is_fixa
            self.row_detalhe_parcelas.visible = not self.state.is_fixa
            self.card_credito_recorrente_info.visible = self.state.is_fixa
            self._atualizar_resumo_parcelas(atualizar_ui=False)
            self._atualizar_opcoes_fatura(atualizar_ui=False)

    def _atualizar_opcoes_forma(self, atualizar_ui: bool = True):
        if self.state.eh_receita:
            opcoes = list(FORMAS_RECEITA)
        elif self.state.eh_transferencia:
            opcoes = list(FORMAS_TRANSFERENCIA)
        else:  # Despesa
            opcoes = list(FORMAS_DESPESA)

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
        if atualizar_ui:
            self._safe_update(self.dd_forma)

    def _atualizar_opcoes_conta_ou_cartao(self, atualizar_ui: bool = True):
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

        if atualizar_ui:
            self._safe_update(self.row_conta)
            self._safe_update(self.row_destino)

    def _atualizar_opcoes_fatura(self, atualizar_ui: bool = True):
        if not self.state.eh_credito:
            self.dd_fatura.options = []
            self.dd_fatura.value = ""
            self.row_fatura.visible = False
            if atualizar_ui:
                self._safe_update(self.row_fatura)
            return

        self.row_fatura.visible = True
        cartao_id = self._obter_cartao_id(self.state.cartao_id)
        opcoes = db.listar_faturas_opcoes_cartao(cartao_id) if cartao_id else []
        self._faturas_opcoes_cache = {str(opt["id"]): opt for opt in opcoes}

        dropdown_opts = [
            ft.dropdown.Option(key="", text="Automática (Dedução pelo fechamento)")
        ]
        for opt in opcoes:
            dropdown_opts.append(
                ft.dropdown.Option(key=str(opt["id"]), text=opt["label"])
            )

        self.dd_fatura.options = dropdown_opts
        if self.state.fatura_id and self.state.fatura_id in self._faturas_opcoes_cache:
            self.dd_fatura.value = self.state.fatura_id
        else:
            self.dd_fatura.value = ""
            self.state.fatura_id = None
            self.state.fatura_manual_mes = None
            self.state.fatura_manual_ano = None

        if atualizar_ui:
            self._safe_update(self.row_fatura)

    def _atualizar_opcoes_categoria(self, atualizar_ui: bool = True):
        self.dd_categoria.options = [
            ft.dropdown.Option(key=str(c["id"]), text=c.get("nome", ""))
            for c in self.categorias
            if c.get("id")
        ]
        ids_cats = {str(c["id"]) for c in self.categorias if c.get("id")}
        if self.state.categoria_id not in ids_cats:
            self.state.categoria_id = str(self.categorias[0]["id"]) if self.categorias else None
        self.dd_categoria.value = self.state.categoria_id
        if atualizar_ui:
            self._safe_update(self.dd_categoria)

    def _atualizar_opcoes_subtipo(self, atualizar_ui: bool = True):
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
        if atualizar_ui:
            self._safe_update(self.dd_subtipo)

    def _atualizar_resumo_parcelas(self, atualizar_ui: bool = True):
        if not self.state.eh_credito:
            return
        if self.state.is_fixa:
            self.lbl_resumo_parcelas.value = "Cobrança contínua todo mês na fatura do cartão."
            self.lbl_resumo_parcelas.color = T.PRIMARY
        else:
            qtd = max(1, self.state.quantidade)
            total = self.state.valor
            parcela = self.state.obter_valor_parcela()
            if qtd <= 1:
                self.lbl_resumo_parcelas.value = f"À vista: R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                self.lbl_resumo_parcelas.color = T.TEXT_MUTED
            else:
                p_str = f"R$ {parcela:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                t_str = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                if self.state.modo_calculo_parcela == "parcela":
                    self.lbl_resumo_parcelas.value = f"{qtd}x de {p_str} (Total: {t_str})"
                else:
                    self.lbl_resumo_parcelas.value = f"Total {t_str} em {qtd}x de {p_str}"
                self.lbl_resumo_parcelas.color = T.PRIMARY

        if atualizar_ui:
            self._safe_update(self.lbl_resumo_parcelas)

    def _atualizar_resumo_repetir(self, atualizar_ui: bool = True):
        res = resumo_parcelas(
            self.state.valor,
            self.state.quantidade,
            modo="repetido",
            frequencia=self.state.frequencia,
            data_inicio=self.state.data_selecionada,
        )
        self.lbl_resumo_repetir.value = res
        self.lbl_resumo_repetir.color = T.PRIMARY
        if atualizar_ui:
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
        self._atualizar_opcoes_forma(atualizar_ui=False)
        self._atualizar_opcoes_conta_ou_cartao(atualizar_ui=False)
        self._atualizar_opcoes_categoria(atualizar_ui=False)
        self._atualizar_opcoes_subtipo(atualizar_ui=False)
        if self.state.categoria_id:
            self._carregar_subcategorias(self.state.categoria_id, atualizar_ui=False)
        else:
            self._carregar_subcategorias(None, atualizar_ui=False)
        self._sincronizar_estado_com_ui()
        self._safe_update(self)
        self._notificar_mudanca()

    def _parse_input_valor(self, raw: str) -> float:
        if not raw:
            return 0.0
        digits = re.sub(r"\D", "", str(raw)).lstrip("0")
        if not digits:
            return 0.0
        if len(digits) > 11:
            digits = digits[:11]
        centavos = int(digits)
        return centavos / 100.0

    def _ao_mudar_valor(self, e):
        raw = e.control.value or ""
        valor = self._parse_input_valor(raw)

        if self.state.eh_credito and not self.state.is_fixa and self.state.modo_calculo_parcela == "parcela":
            self.state.definir_valor_parcela(valor)
        else:
            self.state.definir_valor_total(valor)

        # Anti-lag: Não reatribuir self.txt_valor.value nem chamar update() no txt_valor aqui!
        # Isso impede cursor jumps e latência de rede durante a digitação.
        if self.state.eh_credito:
            self._atualizar_resumo_parcelas()
        elif self.state.is_repetir:
            self._atualizar_resumo_repetir()
        self._notificar_mudanca()

    def _ao_sair_do_valor(self, e):
        # on_blur: Aplica formatação monetária estrita somente ao terminar a digitação
        val_exibir = self.state.obter_valor_exibicao_input()
        self.txt_valor.value = formatar_moeda_input(val_exibir)
        self._safe_update(self.txt_valor)

    def _ao_focar_valor(self, e):
        # on_focus: Se o valor for 0, limpa para o usuário digitar diretamente
        if self.state.valor == 0:
            self.txt_valor.value = ""
            self._safe_update(self.txt_valor)

    def _selecionar_data_rapida(self, dt: date):
        self.state.atualizar_data(dt)
        self._sincronizar_estado_com_ui()
        self._safe_update(self.card_seletor_data)
        self._safe_update(self.row_chips_data)
        self._safe_update(self.switch_status)
        self._notificar_mudanca()

    def _abrir_seletor_data(self, _=None):
        def _ao_selecionar(d: date):
            self.state.atualizar_data(d)
            self._sincronizar_estado_com_ui()
            self._safe_update(self.card_seletor_data)
            self._safe_update(self.row_chips_data)
            self._safe_update(self.switch_status)
            self._notificar_mudanca()

        abrir_seletor_data_modal(
            page=self._page,
            data_inicial=self.state.data_selecionada,
            on_select=_ao_selecionar,
            titulo="Data do Lançamento",
        )

    def _ao_tocar_switch_status(self, e):
        self.state.tocar_switch_status(bool(e.control.value))
        self._notificar_mudanca()

    def _ao_mudar_forma(self, e):
        nova_forma = e.data or e.control.value
        self.state.mudar_forma(nova_forma)
        self._atualizar_opcoes_conta_ou_cartao(atualizar_ui=False)
        self._atualizar_opcoes_fatura(atualizar_ui=False)
        self._sincronizar_estado_com_ui()
        self._safe_update(self)
        self._notificar_mudanca()

    def _ao_mudar_conta(self, e):
        val = e.data or e.control.value
        if self.state.eh_credito:
            self.state.cartao_id = self._obter_cartao_id(val)
            self._atualizar_opcoes_fatura(atualizar_ui=True)
        else:
            self.state.conta_id = self._obter_conta_id(val)
        self._notificar_mudanca()

    def _ao_mudar_destino(self, e):
        val = e.data or e.control.value
        self.state.destino_id = self._obter_conta_id(val)
        self._notificar_mudanca()

    def _ao_mudar_fatura(self, e):
        val = e.data or e.control.value or ""
        val = str(val).strip()
        if not val:
            self.state.fatura_id = None
            self.state.fatura_manual_mes = None
            self.state.fatura_manual_ano = None
        else:
            self.state.fatura_id = val
            cache = getattr(self, "_faturas_opcoes_cache", {})
            opt = cache.get(val, {})
            self.state.fatura_manual_mes = opt.get("mes")
            self.state.fatura_manual_ano = opt.get("ano")
        self._notificar_mudanca()

    def _ao_mudar_modo_calculo_parcela(self, e):
        sel = e.control.selected
        if isinstance(sel, (list, set, tuple)) and len(sel) > 0:
            novo_modo = list(sel)[0]
        else:
            novo_modo = "total"
        e.control.selected = [novo_modo]
        self.state.modo_calculo_parcela = novo_modo

        val_exibir = self.state.obter_valor_exibicao_input()
        self.txt_valor.value = formatar_moeda_input(val_exibir)
        self.txt_valor.label = "Valor da Parcela" if novo_modo == "parcela" else "Valor Total da Compra"
        self._safe_update(self.txt_valor)
        self._atualizar_resumo_parcelas()
        self._notificar_mudanca()

    def _ao_mudar_credito_tipo(self, e):
        sel = e.control.selected
        if isinstance(sel, (list, set, tuple)) and len(sel) > 0:
            tipo_escolhido = list(sel)[0]
        else:
            tipo_escolhido = "parcelado"
        e.control.selected = [tipo_escolhido]

        if tipo_escolhido == "recorrente":
            self.state.is_fixa = True
            self.state.is_repetir = False
            self.state.quantidade = 1
        else:
            self.state.is_fixa = False
            try:
                self.state.quantidade = int(str(self.dd_parcelas.value or 1).replace("x", "").strip())
            except Exception:
                self.state.quantidade = 1

        self._sincronizar_estado_com_ui()
        self._safe_update(self.row_parcelas)
        self._safe_update(self.col_detalhes)
        self._notificar_mudanca()

    def _ao_mudar_parcelas(self, e):
        val = e.data or e.control.value
        try:
            self.state.quantidade = max(1, int(str(val).replace("x", "").strip()))
        except ValueError:
            self.state.quantidade = 1

        if self.state.eh_credito and not self.state.is_fixa:
            if self.state.modo_calculo_parcela == "parcela":
                self.state.definir_valor_parcela(self.state.valor_parcela_input or self.state.obter_valor_parcela())
            else:
                self.state.definir_valor_total(self.state.valor)

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
        self.state.pote_id = val
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

    async def _rolar_para_detalhes(self):
        try:
            await self.scroll_to(offset=-1, duration=280)
        except Exception:
            pass

    def _toggle_mais_detalhes(self, _):
        self.state.mais_detalhes_aberto = not self.state.mais_detalhes_aberto
        aberto = self.state.mais_detalhes_aberto

        self.col_detalhes.visible = aberto
        self.lbl_toggle_detalhes.value = "Menos detalhes" if aberto else "Mais detalhes"
        # Flet 1.0.1: Icon usa propriedade .icon (NUNCA .name!)
        self.ico_toggle_detalhes.icon = (
            ft.Icons.KEYBOARD_ARROW_UP_ROUNDED
            if aberto
            else ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED
        )

        self._safe_update(self.btn_toggle_detalhes)
        self._safe_update(self.col_detalhes)
        self._notificar_mudanca()

        # Ao expandir, rola suavemente para exibir os novos controles
        if aberto and hasattr(self._page, "run_task"):
            try:
                self._page.run_task(self._rolar_para_detalhes)
            except Exception:
                pass

    # =========================================================================
    # MODAIS INLINE (+): Conta/Cartão, Categoria, Subcategoria, Subtipo
    # =========================================================================
    def _fechar_submodal(self, modal: ft.AlertDialog):
        try:
            self._page.pop_dialog()
        except Exception:
            pass
        if getattr(modal, "open", False):
            modal.open = False
            try:
                modal.update()
            except Exception:
                pass
        try:
            self._page.update()
        except Exception:
            pass

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
                res = db.criar_conta({"nome": nome, "tipo_conta": "corrente", "cor": T.PRIMARY})
                self._fechar_submodal(modal)
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
                ft.TextButton("Cancelar", on_click=lambda _: self._fechar_submodal(modal)),
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
                    "bandeira": "mastercard",
                    "cor": T.PRIMARY,
                    "limite_total": lim,
                    "dia_fechamento": 1,
                    "dia_vencimento": 10,
                })
                self._fechar_submodal(modal)
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
                ft.TextButton("Cancelar", on_click=lambda _: self._fechar_submodal(modal)),
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
                self._fechar_submodal(modal)
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
                ft.TextButton("Cancelar", on_click=lambda _: self._fechar_submodal(modal)),
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
                self._fechar_submodal(modal)
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
                ft.TextButton("Cancelar", on_click=lambda _: self._fechar_submodal(modal)),
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
            self._fechar_submodal(modal)
            mostrar_feedback(self._page, f"Subtipo '{nome}' selecionado!", "sucesso")

        modal = ft.AlertDialog(
            title=ft.Text("Novo Subtipo", weight=ft.FontWeight.BOLD),
            content=ft.Column([txt_nome], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancelar", on_click=lambda _: self._fechar_submodal(modal)),
                ft.FilledButton("Adicionar", style=ft.ButtonStyle(bgcolor=T.PRIMARY), on_click=salvar),
            ],
        )
        self._page.show_dialog(modal)
