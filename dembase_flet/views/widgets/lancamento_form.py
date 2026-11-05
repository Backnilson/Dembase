"""
=============================================================================
DemBase v3 — views/widgets/lancamento_form.py (Flet 1.0.1)
Formulário Ultra-Rápido (< 5s) de Novo / Edição de Lançamento:
1. Descrição no Topo + Memória Inteligente Preditiva (Smart Auto-Fill em 0ms)
   + Pílulas de Atalhos Rápidos ("Mais usados / Recentes") com foco automático no Valor.
2. Seleção de 1 Clique (Chips / Pílulas Clicáveis):
   - Perfil Familiar: [👤 Denilson] [👤 Erika] ...
   - Forma de Movimentação: [Pix] [Crédito] [Débito] [Caixinha] com filtro dinâmico abaixo.
   - Pote Financeiro (6 Potes): Pílulas coloridas clicáveis em 1 toque + inferência por categoria.
3. Tela Única Escaneável (Fim do acordeão "Mais/Menos detalhes" e remoção do campo Subtipo):
   - Grid lado a lado para Categoria + Subcategoria.
   - Barra compacta unificada para Data + Hora + Status (Foi paga/recebida).
   - Rodapé compacto para Despesa Fixa / Repetir lançamento.
=============================================================================
"""
from __future__ import annotations

import re
import unicodedata
import uuid
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Callable, Optional

import flet as ft

from core.constants import (
    formatar_moeda,
    REGRAS_5030,
    FORMAS_RECEITA,
    FORMAS_DESPESA,
    FORMAS_TRANSFERENCIA,
    SUBTIPOS_RECEITA,
    SUBTIPOS_DESPESA,
    SUBTIPOS_TRANSFERENCIA,
)
from core.lancamento_state import LancamentoFormState, is_caixinha_str, is_credito_str
from core.recorrencia import resumo_parcelas
from core.potes import obter_regra_pote, POTES_PADRAO
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


def _limpar_sufixo_parcela(desc: Optional[str]) -> str:
    """Remove sufixos como '(1/10)' ou '- 2/12' para agrupar descrições do histórico."""
    if not desc:
        return ""
    limpo = re.sub(r"\s*\(\d+\s*/\s*\d+\)\s*$", "", str(desc).strip())
    limpo = re.sub(r"\s*-\s*\d+\s*/\s*\d+\s*$", "", limpo)
    return limpo.strip()


def _norm_desc(texto: Optional[str]) -> str:
    return _norm(_limpar_sufixo_parcela(texto))


def _is_uuid(val) -> bool:
    if not val:
        return False
    try:
        uuid.UUID(str(val).strip())
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def _emoji_para_descricao(texto: str) -> str:
    """Retorna um emoji intuitivo para os chips de Atalhos Rápidos."""
    n = _norm(texto)
    if any(k in n for k in ("cafe", "padaria", "pao", "lanche", "starbucks")):
        return "☕"
    if any(k in n for k in ("almoco", "jantar", "restaurante", "ifood", "comida", "refeicao", "pizza", "burger")):
        return "🍽️"
    if any(k in n for k in ("gasolina", "combustivel", "etanol", "posto", "abastecimento")):
        return "⛽"
    if any(k in n for k in ("mercado", "supermercado", "compras", "feira", "hortifruti", "atacadao", "assai")):
        return "🛒"
    if any(k in n for k in ("bebida", "cerveja", "bar", "adega", "vinho", "chopp", "festa")):
        return "🍺"
    if any(k in n for k in ("uber", "99", "taxi", "transporte", "pedagio", "estacionamento", "metro", "onibus")):
        return "🚗"
    if any(k in n for k in ("farmacia", "remedio", "medico", "consulta", "exame", "saude", "drogaria")):
        return "💊"
    if any(k in n for k in ("aluguel", "condominio", "iptu", "moradia", "casa")):
        return "🏠"
    if any(k in n for k in ("luz", "energia", "agua", "internet", "gas", "conta", "celular", " Vivo", "claro", "tim")):
        return "⚡"
    if any(k in n for k in ("netflix", "spotify", "prime", "youtube", "assinatura", "streaming", "hbo", "disney")):
        return "🎬"
    if any(k in n for k in ("curso", "livro", "educacao", "faculdade", "escola", "aula")):
        return "📚"
    if any(k in n for k in ("salario", "pagamento", "pro-labore", "freela", "pix recebido", "renda")):
        return "💰"
    if any(k in n for k in ("academia", "treino", "esporte", "futebol", "suplemento")):
        return "💪"
    if any(k in n for k in ("dj", "equipamento", "musica", "show", "evento")):
        return "🎧"
    if any(k in n for k in ("moto", "carro", "oficina", "manutencao", "capacete")):
        return "🏍️"
    if any(k in n for k in ("transf", "reserva", "aporte", "caixinha", "poupanca")):
        return "🔄"
    return "⚡"


def _tipo_normalizado_aba(tipo_raw: Optional[str]) -> str:
    """Normaliza qualquer variação de tipo para 'Despesa', 'Receita' ou 'Transferencia'."""
    n = _norm(tipo_raw)
    if "trans" in n:
        return "Transferencia"
    if "rec" in n:
        return "Receita"
    return "Despesa"


def _eh_lancamento_recorrente_ou_automatico(reg: dict) -> bool:
    """
    Identifica lançamentos de recorrência automática (fixa / assinatura mensal),
    séries parceladas/repetidas materializadas ou provisionamentos internos de caixinha,
    para que o Ranking Vivo de Atalhos Rápidos priorize apenas lançamentos manuais reais.
    """
    if not isinstance(reg, dict):
        return True
    if _norm(reg.get("subtipo")) == "provisionamento":
        return True
    t_rec = _norm(reg.get("tipo_recorrencia"))
    if t_rec in ("fixa", "recorrente", "parcelada", "repetida"):
        return True
    if reg.get("recorrente_id") or reg.get("serie_id"):
        return True
    try:
        if int(reg.get("total_parcelas") or 1) > 1 or int(reg.get("parcela_atual") or 1) > 1:
            return True
    except (ValueError, TypeError):
        pass
    desc_raw = str(reg.get("descricao") or "")
    if re.search(r"\(\d+\s*/\s*\d+\)", desc_raw) or re.search(r"-\s*\d+\s*/\s*\d+\s*$", desc_raw):
        return True
    return False


def _botao_add_verde(on_click, tooltip: str) -> ft.IconButton:
    """Botão verde (+) compacto colado ao lado direito do Dropdown (Flet 1.0.1)."""
    return ft.IconButton(
        icon=ft.Icons.ADD_ROUNDED,
        icon_color=ft.Colors.WHITE,
        icon_size=18,
        bgcolor=T.PRIMARY,
        width=38,
        height=38,
        tooltip=tooltip,
        on_click=on_click,
        style=ft.ButtonStyle(
            padding=pad(all_=0),
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
    Gerencia a reatividade dos controles, seleção em 1 clique e Memória Inteligente.
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

        # Listas de dados carregadas do Supabase (com cache RAM)
        self.contas: list[dict] = []
        self.cartoes: list[dict] = []
        self.categorias: list[dict] = []
        self.subcategorias: list[dict] = []
        self.todas_subcategorias: list[dict] = []
        self.caixinhas: list[dict] = []
        self.membros: list[dict] = []
        self.historico_memoria: list[dict] = []

        # Flags de controle de interação manual na sessão do modal
        self._pote_escolhido_manualmente: bool = bool(state.lancamento_id)
        self._ultimo_termo_autofill: str = ""

        # 1. Pré-carrega dados de negócio antes de montar controles para popular chips iniciais
        self._precarregar_dados_base()

        # 2. Constrói os controles filhos antes do super().__init__ (padrão dataclass Flet 1.0.1)
        controles_iniciais = self._construir_controles()
        super().__init__(
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            controls=controles_iniciais,
        )

        # 3. Sincroniza opções e estado inicial com a UI
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

    def _focar_campo_valor(self):
        """Move o foco do teclado diretamente para o campo de Valor (Flet 1.0.1 async focus)."""
        try:
            import inspect
            fn_focus = getattr(self.txt_valor, "focus", None)
            if callable(fn_focus):
                if inspect.iscoroutinefunction(fn_focus):
                    if self._page is not None and hasattr(self._page, "run_task"):
                        self._page.run_task(fn_focus)
                else:
                    fn_focus()
        except Exception:
            pass

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
        for s in (self.subcategorias or self.todas_subcategorias):
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

    def _obter_caixinha_id(self, val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        val_str = str(val).strip()
        if _is_uuid(val_str):
            return val_str
        for c in self.caixinhas:
            if str(c.get("id")) == val_str or str(c.get("nome", "")).strip().lower() == val_str.lower():
                return str(c["id"])
        return None

    # =========================================================================
    # PRÉ-CARREGAMENTO DE DADOS BASE E MEMÓRIA INTELIGENTE
    # =========================================================================
    def _precarregar_dados_base(self):
        try:
            self.contas = db.listar_contas() or []
        except Exception:
            self.contas = []
        try:
            self.cartoes = db.listar_cartoes() or []
        except Exception:
            self.cartoes = []
        try:
            self.categorias = db.listar_categorias() or []
        except Exception:
            self.categorias = []
        try:
            self.membros = db.listar_membros() or []
        except Exception:
            self.membros = []
        try:
            self.caixinhas = db.listar_caixinhas_opcoes() or []
        except Exception:
            self.caixinhas = []
        try:
            self.todas_subcategorias = db.listar_subcategorias(None) or []
        except Exception:
            self.todas_subcategorias = []
        try:
            if hasattr(db, "obter_memoria_lancamentos"):
                self.historico_memoria = db.obter_memoria_lancamentos() or []
            else:
                self.historico_memoria = []
        except Exception:
            self.historico_memoria = []
        try:
            self._potes_cache = potes_svc.carregar_potes() or []
        except Exception:
            self._potes_cache = []

    # =========================================================================
    # CONSTRUÇÃO DOS CONTROLES (ARQUITETURA TELA ÚNICA < 5 SEGUNDOS)
    # =========================================================================
    def _construir_controles(self) -> list[ft.Control]:
        is_edicao = bool(self.state.lancamento_id)

        # ---------------------------------------------------------------------
        # 1. Seletor de Tipo (SegmentedButton — Flet 1.0.1 exige selected como list[str])
        # ---------------------------------------------------------------------
        self.btn_tipo = ft.SegmentedButton(
            selected=[self.state.tipo],
            allow_multiple_selection=False,
            allow_empty_selection=False,
            segments=[
                ft.Segment(
                    value="Despesa",
                    label=ft.Text("Despesa", weight=ft.FontWeight.BOLD, size=13),
                    icon=ft.Icon(ft.Icons.ARROW_DOWNWARD_ROUNDED, color=T.DESPESA, size=17),
                ),
                ft.Segment(
                    value="Receita",
                    label=ft.Text("Receita", weight=ft.FontWeight.BOLD, size=13),
                    icon=ft.Icon(ft.Icons.ARROW_UPWARD_ROUNDED, color=T.RECEITA, size=17),
                ),
                ft.Segment(
                    value="Transferencia",
                    label=ft.Text("Transf.", weight=ft.FontWeight.BOLD, size=13),
                    icon=ft.Icon(ft.Icons.SWAP_HORIZ_ROUNDED, color=T.PRIMARY, size=17),
                ),
            ],
            on_change=self._ao_mudar_tipo,
        )

        # ---------------------------------------------------------------------
        # 2. Descrição no Topo + Atalhos Rápidos ("Mais usados / Recentes") + Badge Smart Auto-Fill
        # ---------------------------------------------------------------------
        self.txt_descricao = ft.TextField(
            label="Descrição",
            hint_text="Ex: Café, Almoço, Gasolina, Mercado...",
            value=self.state.descricao,
            autofocus=(not is_edicao and not bool(self.state.descricao)),
            prefix_icon=ft.Icons.AUTO_AWESOME_ROUNDED,
            border_radius=11,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            text_size=14,
            content_padding=pad(h=14, v=11),
            on_change=self._ao_mudar_descricao,
            on_submit=self._ao_submeter_descricao,
        )

        self.lbl_autofill_resumo = ft.Text(
            "",
            size=11,
            weight=ft.FontWeight.W_600,
            color=T.PRIMARY,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True,
        )
        self.badge_autofill = ft.Container(
            content=ft.Row(
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, size=14, color=T.PRIMARY),
                    self.lbl_autofill_resumo,
                ],
            ),
            padding=pad(h=10, v=4),
            bgcolor=f"{T.PRIMARY}16",
            border_radius=8,
            border=borda(1, f"{T.PRIMARY}45"),
            visible=False,
        )

        self.sugestoes_atuais: list[dict] = []
        self.col_sugestoes_autocomplete = ft.Column(spacing=4, tight=True)
        self.box_autocomplete = ft.Container(
            content=self.col_sugestoes_autocomplete,
            padding=pad(h=8, v=6),
            bgcolor=T.SURFACE_ALT,
            border_radius=10,
            border=borda(1.2, f"{T.PRIMARY}55"),
            visible=False,
        )

        self.row_atalhos_rapidos = ft.Row(
            spacing=6,
            run_spacing=6,
            wrap=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self._construir_chips_atalhos_rapidos()

        self.sec_descricao_topo = ft.Column(
            spacing=6,
            tight=True,
            controls=[
                self.txt_descricao,
                self.box_autocomplete,
                self.badge_autofill,
                self.row_atalhos_rapidos,
            ],
        )

        # ---------------------------------------------------------------------
        # 3. Input de Valor Destacado + Barra Compacta Data / Hora / Status
        # ---------------------------------------------------------------------
        cor_valor = (
            T.DESPESA
            if self.state.eh_despesa
            else (T.RECEITA if self.state.eh_receita else T.PRIMARY)
        )
        str_val = formatar_moeda_input(self.state.valor)
        self.txt_valor = ft.TextField(
            label="Valor da transação",
            value=str_val,
            prefix=ft.Text("R$ ", size=20, weight=ft.FontWeight.BOLD, color=cor_valor),
            text_size=24,
            text_align=ft.TextAlign.CENTER,
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=(is_edicao or bool(self.state.descricao)),
            color=cor_valor,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD),
            border_radius=12,
            border_color=T.BORDER,
            focused_border_color=cor_valor,
            content_padding=pad(h=14, v=10),
            on_change=self._ao_mudar_valor,
            on_blur=self._ao_sair_do_valor,
            on_focus=self._ao_focar_valor,
        )

        # Seletor de Data Compacto + Hora Compacta + Switch Status na mesma linha
        self.txt_data_label = ft.Text(
            formatar_data_amigavel(self.state.data_selecionada),
            size=12,
            weight=ft.FontWeight.BOLD,
            color=T.TEXT_PRIMARY,
        )
        self.card_seletor_data = ft.Container(
            content=ft.Row(
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=14),
                        padding=pad(all_=4),
                        bgcolor=f"{T.PRIMARY}18",
                        border_radius=6,
                    ),
                    self.txt_data_label,
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, color=T.TEXT_MUTED, size=16),
                ],
            ),
            padding=pad(h=8, v=5),
            bgcolor=T.SURFACE_ALT,
            border_radius=9,
            border=borda(1, T.BORDER),
            ink=True,
            on_click=self._abrir_seletor_data,
            tooltip="Clique para alterar a data",
        )

        self.txt_hora = ft.TextField(
            label="Hora",
            value=str(self.state.hora),
            suffix=ft.Text("h", size=11, color=T.TEXT_MUTED),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=72,
            text_size=12.5,
            text_align=ft.TextAlign.CENTER,
            border_radius=9,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            content_padding=pad(h=8, v=6),
            on_change=self._ao_mudar_hora,
            tooltip="Hora do lançamento (0 a 23)",
        )

        label_switch = "Paga" if self.state.eh_despesa else "Recebida"
        self.switch_status = ft.Switch(
            label=label_switch,
            value=self.state.status_pago,
            active_color=T.PRIMARY,
            height=32,
            on_change=self._ao_tocar_switch_status,
        )

        self.chip_hoje = ft.Container()
        self.chip_ontem = ft.Container()
        self.chip_amanha = ft.Container()
        self.chip_outros = ft.Container()
        self.row_chips_data = ft.Row(spacing=6, wrap=True)
        self._construir_chips_data()

        self.sec_data_hora_status = ft.Container(
            content=ft.Column(
                spacing=6,
                tight=True,
                controls=[
                    ft.Row(
                        controls=[
                            self.card_seletor_data,
                            ft.Row(
                                controls=[self.txt_hora, self.switch_status],
                                spacing=6,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    self.row_chips_data,
                ],
            ),
        )

        # ---------------------------------------------------------------------
        # 4. Perfil Familiar em 1 Clique (Chips Horizontais)
        # ---------------------------------------------------------------------
        # Mantemos self.dd_membro sincronizado em background para compatibilidade com testes
        self.dd_membro = ft.Dropdown(
            label="Perfil Familiar *",
            value=str(self.state.membro_id) if self.state.membro_id else None,
            on_select=self._ao_mudar_membro,
            visible=False,
        )
        self.row_chips_membro = ft.Row(spacing=8, run_spacing=6, wrap=True)
        self.sec_membro = ft.Column(
            spacing=5,
            tight=True,
            controls=[
                ft.Text("Perfil Familiar", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                self.row_chips_membro,
            ],
        )

        # ---------------------------------------------------------------------
        # 5. Forma de Movimentação em 1 Clique: [Pix] [Crédito] [Débito] [Caixinha]
        # ---------------------------------------------------------------------
        # Mantemos self.dd_forma sincronizado em background para compatibilidade com testes
        self.dd_forma = ft.Dropdown(
            label="Forma de movimentação *",
            value=self.state.forma_movimentacao,
            on_select=self._ao_mudar_forma,
            visible=False,
        )
        self.row_chips_forma = ft.Row(spacing=6, run_spacing=6, wrap=True)
        self.sec_forma = ft.Column(
            spacing=5,
            tight=True,
            controls=[
                ft.Text("Forma de Movimentação", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                self.row_chips_forma,
            ],
        )

        # ---------------------------------------------------------------------
        # 6. Seleção Dinâmica de Origem: Conta | Cartão de Crédito | Caixinha
        # ---------------------------------------------------------------------
        self.dd_conta = ft.Dropdown(
            label="Conta *",
            value=self.state.conta_id,
            expand=True,
            on_select=self._ao_mudar_conta,
            **T.dropdown_estilo(content_padding=pad(h=12, v=10), text_size=13),
        )
        self.btn_add_conta = _botao_add_verde(
            on_click=self._abrir_modal_nova_conta_ou_cartao,
            tooltip="Nova Conta",
        )
        self.row_conta = ft.Row(
            controls=[self.dd_conta, self.btn_add_conta],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            visible=(not self.state.eh_caixinha),
        )

        # Conta de Destino (Só Transferência)
        self.dd_destino = ft.Dropdown(
            label="Conta de destino *",
            value=self.state.destino_id,
            expand=True,
            on_select=self._ao_mudar_destino,
            **T.dropdown_estilo(content_padding=pad(h=12, v=10), text_size=13),
        )
        self.btn_add_destino = _botao_add_verde(
            on_click=lambda _: self._abrir_modal_nova_conta(eh_destino=True),
            tooltip="Nova Conta de Destino",
        )
        self.row_destino = ft.Row(
            controls=[self.dd_destino, self.btn_add_destino],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            visible=self.state.eh_transferencia,
        )

        # Caixinha (Visível imediatamente abaixo de Forma quando [Caixinha] é clicado)
        self.dd_caixinha = ft.Dropdown(
            label="Caixinha *",
            value=self.state.caixinha_id,
            options=[],
            expand=True,
            on_select=self._ao_mudar_caixinha,
            **T.dropdown_estilo(content_padding=pad(h=12, v=10), text_size=13),
        )
        self.badge_info_caixinha = ft.Container(
            padding=pad(h=10, v=6),
            bgcolor=f"{T.PRIMARY}14",
            border_radius=8,
            border=borda(1, f"{T.PRIMARY}40"),
            content=ft.Row(
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SHIELD_ROUNDED, color=T.PRIMARY, size=14),
                    ft.Text(
                        "Consumo de Provisão (Neutro no Banco e nos 6 Potes): desconta exclusivamente do saldo desta Caixinha.",
                        size=10.5,
                        color=T.TEXT_PRIMARY,
                        weight=ft.FontWeight.W_500,
                        expand=True,
                    ),
                ],
            ),
        )
        self.row_caixinha = ft.Column(
            spacing=6,
            tight=True,
            visible=self.state.eh_caixinha,
            controls=[
                ft.Row(
                    controls=[
                        ft.Container(
                            content=ft.Icon(ft.Icons.INVENTORY_2_ROUNDED, color=T.PRIMARY, size=18),
                            padding=pad(all_=8),
                            bgcolor=f"{T.PRIMARY}18",
                            border_radius=8,
                        ),
                        self.dd_caixinha,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                self.badge_info_caixinha,
            ],
        )

        # Fatura do Cartão (Seleção manual opcional quando Crédito está ativo)
        self.dd_fatura = ft.Dropdown(
            label="Fatura de destino (opcional)",
            value="",
            expand=True,
            on_select=self._ao_mudar_fatura,
            **T.dropdown_estilo(content_padding=pad(h=12, v=10), text_size=12.5),
        )
        self.row_fatura = ft.Row(
            controls=[self.dd_fatura],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            visible=False,
        )

        # Modalidade no Cartão de Crédito: Parcelas vs Recorrência Contínua
        self.seg_credito_tipo = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="parcelado",
                    label=ft.Text("Parcelas", size=12, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.PAYMENTS_ROUNDED, size=15),
                ),
                ft.Segment(
                    value="recorrente",
                    label=ft.Text("Recorrência", size=12, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.ALL_INCLUSIVE_ROUNDED, size=15),
                ),
            ],
            selected=["recorrente" if self.state.is_fixa else "parcelado"],
            on_change=self._ao_mudar_credito_tipo,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
            ),
        )

        self.seg_modo_parcela = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="total",
                    label=ft.Text("Valor Total", size=11, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.ATTACH_MONEY_ROUNDED, size=14),
                ),
                ft.Segment(
                    value="parcela",
                    label=ft.Text("Valor da Parcela", size=11, weight=ft.FontWeight.W_600),
                    icon=ft.Icon(ft.Icons.PAYMENTS_ROUNDED, size=14),
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

        self.lbl_badge_parcela = ft.Text(
            "",
            size=11.5,
            weight=ft.FontWeight.W_600,
            color=T.PRIMARY,
        )
        self.badge_edicao_parcela = ft.Container(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.LAYERS_ROUNDED, size=15, color=T.PRIMARY),
                    self.lbl_badge_parcela,
                ],
            ),
            padding=pad(h=10, v=5),
            bgcolor=f"{T.PRIMARY}18",
            border_radius=8,
            border=borda(1, f"{T.PRIMARY}40"),
            visible=False,
        )

        self.dd_parcelas = ft.Dropdown(
            label="Parcelas *",
            value=str(self.state.quantidade if self.state.quantidade > 1 else 1),
            options=[ft.dropdown.Option(key=str(i), text=f"{i}x") for i in range(1, 49)],
            width=130,
            on_select=self._ao_mudar_parcelas,
            **T.dropdown_estilo(content_padding=pad(h=10, v=9), text_size=12.5),
        )
        self.lbl_resumo_parcelas = ft.Text(
            "",
            size=11.5,
            weight=ft.FontWeight.W_500,
            color=T.TEXT_MUTED,
            expand=True,
        )
        self.row_detalhe_parcelas = ft.Row(
            controls=[self.dd_parcelas, self.lbl_resumo_parcelas],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            visible=(not self.state.is_fixa),
        )
        self.lbl_aviso_mudanca_parcelas = ft.Text(
            "",
            size=11,
            weight=ft.FontWeight.W_500,
            visible=False,
        )
        self.card_credito_recorrente_info = ft.Container(
            padding=pad(h=10, v=7),
            bgcolor=f"{T.PRIMARY}14",
            border_radius=9,
            border=borda(1, f"{T.PRIMARY}40"),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.AUTORENEW_ROUNDED, color=T.PRIMARY, size=17),
                    ft.Column(
                        spacing=1,
                        tight=True,
                        controls=[
                            ft.Text(
                                "Assinatura / Cobrança Fixa Contínua",
                                color=T.PRIMARY,
                                size=12,
                                weight=ft.FontWeight.BOLD,
                            ),
                            ft.Text(
                                "Cobrada mensalmente na fatura sem término de parcelas.",
                                color=T.TEXT_MUTED,
                                size=10.5,
                            ),
                        ],
                    ),
                ],
            ),
            visible=self.state.is_fixa,
        )
        self.row_parcelas = ft.Column(
            controls=[
                self.badge_edicao_parcela,
                ft.Row([self.seg_credito_tipo, self.row_modo_parcela], spacing=8, wrap=True),
                self.row_detalhe_parcelas,
                self.lbl_aviso_mudanca_parcelas,
                self.card_credito_recorrente_info,
            ],
            spacing=6,
            visible=False,
        )

        # ---------------------------------------------------------------------
        # 7. Grid Lado a Lado: Categoria + Subcategoria (Sempre Visíveis!)
        # ---------------------------------------------------------------------
        self.dd_categoria = ft.Dropdown(
            label="Categoria *",
            value=self.state.categoria_id,
            expand=True,
            on_select=self._ao_mudar_categoria,
            **T.dropdown_estilo(content_padding=pad(h=10, v=10), text_size=12.5),
        )
        self.btn_add_categoria = _botao_add_verde(
            on_click=self._abrir_modal_nova_categoria,
            tooltip="Nova Categoria",
        )
        self.row_categoria = ft.Row(
            controls=[self.dd_categoria, self.btn_add_categoria],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
            expand=1,
            visible=(not self.state.eh_transferencia),
        )

        self.dd_subcategoria = ft.Dropdown(
            label="Subcategoria",
            value=self.state.subcategoria_id,
            expand=True,
            on_select=self._ao_mudar_subcategoria,
            **T.dropdown_estilo(content_padding=pad(h=10, v=10), text_size=12.5),
        )
        self.btn_add_subcategoria = _botao_add_verde(
            on_click=self._abrir_modal_nova_subcategoria,
            tooltip="Nova Subcategoria",
        )
        self.row_subcategoria = ft.Row(
            controls=[self.dd_subcategoria, self.btn_add_subcategoria],
            alignment=ft.MainAxisAlignment.START,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
            expand=1,
            visible=(not self.state.eh_transferencia),
        )

        self.row_cat_subcat_grid = ft.Row(
            controls=[self.row_categoria, self.row_subcategoria],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            visible=(not self.state.eh_transferencia),
        )

        # Subtipo removido da interface (mantido internamente p/ compatibilidade de banco/testes)
        self.dd_subtipo = ft.Dropdown(
            label="Subtipo",
            value=self.state.subtipo or self.state.tipo,
            visible=False,
        )

        # ---------------------------------------------------------------------
        # 8. Pote Financeiro (6 Potes em Pílulas Coloridas de 1 Clique!)
        # ---------------------------------------------------------------------
        if self._potes_cache:
            def _p_id(p):
                val = getattr(p, "id", None)
                if val is None and isinstance(p, dict):
                    val = p.get("id")
                return str(val) if val is not None else ""

            def _p_nome(p):
                val = getattr(p, "nome", None)
                if val is None and isinstance(p, dict):
                    val = p.get("nome")
                return str(val) if val is not None else "Pote"

            def _p_perc(p):
                val = getattr(p, "percentual", None)
                if val is None and isinstance(p, dict):
                    val = p.get("percentual")
                try:
                    return float(val) if val is not None else 0.0
                except Exception:
                    return 0.0

            opcoes_regra = [
                ft.dropdown.Option(key=_p_id(p), text=f"{_p_nome(p)} ({_p_perc(p):g}%)")
                for p in self._potes_cache
            ]
            val_pote = (
                str(self.state.pote_id)
                if self.state.pote_id
                else (_p_id(self._potes_cache[0]) if self._potes_cache else None)
            )
            if not self.state.pote_id and self._potes_cache:
                self.state.pote_id = _p_id(self._potes_cache[0])
            self.state.regra = obter_regra_pote(self.state.pote_id or self.state.regra, self._potes_cache)
        else:
            opcoes_regra = [ft.dropdown.Option(key=r, text=r) for r in REGRAS_5030]
            val_pote = self.state.regra or "Essencial"
            self.state.regra = obter_regra_pote(self.state.regra)

        # Mantemos self.dd_regra sincronizado em background para compatibilidade com testes unitários
        self.dd_regra = ft.Dropdown(
            label="Pote Financeiro *",
            value=val_pote,
            options=opcoes_regra,
            on_select=self._ao_mudar_regra,
            visible=False,
        )

        self.lbl_macro_regra_pote = ft.Text(
            f"Pilar 50/30/20: {self.state.regra or 'Essencial'}",
            size=10.5,
            weight=ft.FontWeight.W_600,
            color=T.PRIMARY,
        )
        self.wrap_chips_potes = ft.Row(spacing=6, run_spacing=6, wrap=True)
        self.sec_potes = ft.Column(
            spacing=5,
            tight=True,
            visible=self.state.eh_despesa,
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Pote Financeiro (1 clique)", size=11.5, weight=ft.FontWeight.W_600, color=T.TEXT_MUTED),
                        self.lbl_macro_regra_pote,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.wrap_chips_potes,
            ],
        )
        self._construir_chips_potes()

        # ---------------------------------------------------------------------
        # 9. Rodapé Compacto de Recorrência: Despesa Fixa | Repetir Lançamento
        # ---------------------------------------------------------------------
        self.switch_fixa = ft.Switch(
            label="Despesa Fixa" if self.state.eh_despesa else "Receita Fixa",
            value=self.state.is_fixa,
            active_color=T.PRIMARY,
            height=30,
            on_change=self._ao_mudar_switch_fixa,
        )
        self.switch_repetir = ft.Switch(
            label="Repetir lançamento",
            value=self.state.is_repetir,
            active_color=T.PRIMARY,
            height=30,
            on_change=self._ao_mudar_switch_repetir,
        )
        self.row_switches_recorrencia = ft.Container(
            padding=pad(h=10, v=4),
            bgcolor=T.SURFACE_ALT,
            border_radius=10,
            border=borda(1, T.BORDER),
            content=ft.Row(
                controls=[self.switch_fixa, self.switch_repetir],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
            ),
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
            **T.dropdown_estilo(content_padding=pad(h=10, v=9), text_size=12.5),
        )

        self.txt_repetir_qtd = ft.TextField(
            label="Qtd *",
            value=str(self.state.quantidade if self.state.quantidade >= 2 else 2),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=100,
            border_radius=10,
            border_color=T.BORDER,
            focused_border_color=T.PRIMARY,
            content_padding=pad(h=10, v=9),
            text_size=12.5,
            on_change=self._ao_mudar_repetir_qtd,
        )

        self.lbl_resumo_repetir = ft.Text(
            "",
            size=11.5,
            weight=ft.FontWeight.W_500,
            color=T.PRIMARY,
        )

        self.col_opcoes_recorrencia = ft.Column(
            controls=[
                ft.Row([self.dd_frequencia, self.txt_repetir_qtd], spacing=8),
                self.lbl_resumo_repetir,
            ],
            spacing=6,
            visible=False,
        )

        # Container agrupador de recorrência (substitui o antigo col_detalhes escondido)
        self.col_detalhes = ft.Column(
            key="sec_detalhes",
            controls=[
                self.row_switches_recorrencia,
                self.col_opcoes_recorrencia,
            ],
            spacing=6,
            visible=True,
        )

        return [
            self.btn_tipo,
            self.sec_descricao_topo,
            self.txt_valor,
            self.sec_data_hora_status,
            self.sec_membro,
            self.sec_forma,
            self.row_conta,
            self.row_destino,
            self.row_caixinha,
            self.row_fatura,
            self.row_parcelas,
            self.row_cat_subcat_grid,
            self.sec_potes,
            self.col_detalhes,
        ]

    # =========================================================================
    # MEMÓRIA EVOLUTIVA (3 LETRAS) & RANKING VIVO POR ABA (DESPESA/RECEITA/TRANSF)
    # =========================================================================
    def _obter_lista_atalhos_rapidos(self, tipo_aba: Optional[str] = None) -> list[dict]:
        """
        Gera o Ranking Vivo de Atalhos Rápidos (Top 6) ordenado por Frequência de Uso
        (do mais lançado para o menos lançado, desempatando pelo mais recente),
        separado de forma independente por Aba (Despesa | Receita | Transferencia).
        Começa limpo (sem itens estáticos) e ignora recorrências automáticas / parcelas.
        Sempre vincula a 'Última Configuração Salva' para cada item do ranking.
        """
        alvo_tipo = _tipo_normalizado_aba(tipo_aba or self.state.tipo)
        contagem: Counter = Counter()
        ultimo_por_chave: dict[str, dict] = {}
        label_original: dict[str, str] = {}
        ordem_recencia: dict[str, int] = {}

        ignorados = {"lancamento", "despesa", "receita", "transferencia", "ajuste", "saldo"}

        for idx, reg in enumerate(self.historico_memoria or []):
            if _tipo_normalizado_aba(reg.get("tipo")) != alvo_tipo:
                continue

            desc_limpa = _limpar_sufixo_parcela(reg.get("descricao"))
            chave = _norm(desc_limpa)
            if not chave or len(chave) < 2 or chave in ignorados:
                continue

            # Ignora recorrências automáticas e clones de parcelamento no ranking manual
            if _eh_lancamento_recorrente_ou_automatico(reg):
                continue

            contagem[chave] += 1
            if chave not in ultimo_por_chave:
                ultimo_por_chave[chave] = dict(reg)
                label_original[chave] = desc_limpa
                ordem_recencia[chave] = idx

        # Ordena por Frequência de Uso (decrescente) e, em caso de empate, pelo mais recente (menor idx)
        chaves_ordenadas = sorted(
            ultimo_por_chave.keys(),
            key=lambda k: (contagem[k], -ordem_recencia[k]),
            reverse=True,
        )

        atalhos: list[dict] = []
        for k in chaves_ordenadas[:6]:
            lbl = label_original[k]
            atalhos.append({
                "chave": k,
                "label": lbl,
                "emoji": _emoji_para_descricao(lbl),
                "frequencia": contagem[k],
                "historico": ultimo_por_chave[k],
            })

        return atalhos

    def _construir_chips_atalhos_rapidos(self, filtro_texto: str = ""):
        atalhos = self._obter_lista_atalhos_rapidos()
        desc_atual_norm = _norm_desc(self.state.descricao)

        chips: list[ft.Control] = []
        for pos, item in enumerate(atalhos, start=1):
            ativo = (desc_atual_norm == item["chave"] and bool(desc_atual_norm))
            freq = int(item.get("frequencia") or 1)
            controles_chip: list[ft.Control] = [
                ft.Text(item["emoji"], size=11.5),
                ft.Text(
                    item["label"],
                    size=11,
                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                ),
            ]
            if freq > 1:
                controles_chip.append(
                    ft.Text(
                        f"{freq}x",
                        size=9.5,
                        weight=ft.FontWeight.W_600,
                        color=T.ON_PRIMARY if ativo else T.PRIMARY,
                    )
                )

            chips.append(
                ft.Container(
                    content=ft.Row(
                        spacing=4,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=controles_chip,
                    ),
                    padding=pad(h=8, v=4),
                    bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                    border_radius=12,
                    border=borda(1, T.PRIMARY if ativo else T.BORDER),
                    ink=True,
                    tooltip=f"#{pos} Mais usado ({freq}x): preencher '{item['label']}' com 1 toque",
                    on_click=lambda _, it=item: self._aplicar_atalho_rapido(it),
                )
            )

        self.row_atalhos_rapidos.controls = chips
        self.row_atalhos_rapidos.visible = bool(chips)

    def _formatar_resumo_config(self, cfg: dict) -> str:
        """Gera um resumo legível da configuração (Perfil · Forma · Conta/Cartão · Categoria · Pote)."""
        if not cfg:
            return ""
        partes: list[str] = []
        m_id = str(cfg.get("membro_id") or "")
        if m_id:
            m_obj = next((m for m in self.membros if str(m.get("id")) == m_id), None)
            if m_obj and m_obj.get("nome"):
                partes.append(str(m_obj["nome"]))

        forma = str(cfg.get("forma_movimentacao") or "Pix")
        cx_id = str(cfg.get("caixinha_id") or "")
        if cx_id and _norm(cfg.get("subtipo")) != "provisionamento" and _tipo_normalizado_aba(cfg.get("tipo")) == "Despesa":
            forma = "Caixinha"
        partes.append(forma)

        if _norm(forma) == "credito":
            k_id = str(cfg.get("cartao_id") or "")
            k_obj = next((k for k in self.cartoes if str(k.get("id")) == k_id), None)
            if k_obj and k_obj.get("nome"):
                partes.append(str(k_obj["nome"]))
        elif _norm(forma) == "caixinha":
            cx_obj = next((c for c in self.caixinhas if str(c.get("id")) == cx_id), None)
            if cx_obj and cx_obj.get("nome"):
                partes.append(str(cx_obj["nome"]))
        else:
            c_id = str(cfg.get("conta_id") or "")
            c_obj = next((c for c in self.contas if str(c.get("id")) == c_id), None)
            if c_obj and c_obj.get("nome"):
                partes.append(str(c_obj["nome"]))

        if _tipo_normalizado_aba(cfg.get("tipo")) != "Transferencia":
            cat_id = str(cfg.get("categoria_id") or "")
            sub_id = str(cfg.get("subcategoria_id") or "")
            cat_obj = next((c for c in self.categorias if str(c.get("id")) == cat_id), None)
            cat_txt = str(cat_obj["nome"]) if (cat_obj and cat_obj.get("nome")) else ""
            if sub_id:
                pool_s = self.todas_subcategorias or self.subcategorias or []
                sub_obj = next((s for s in pool_s if str(s.get("id")) == sub_id), None)
                if sub_obj and sub_obj.get("nome"):
                    cat_txt = f"{cat_txt} > {sub_obj['nome']}" if cat_txt else str(sub_obj["nome"])
            if cat_txt:
                partes.append(cat_txt)

        if _tipo_normalizado_aba(cfg.get("tipo")) == "Despesa":
            p_id = str(cfg.get("pote_id") or "")
            if p_id and self._potes_cache:
                for p in self._potes_cache:
                    pid = str(getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else ""))
                    if pid == p_id:
                        pnome = str(getattr(p, "nome", None) or (p.get("nome") if isinstance(p, dict) else ""))
                        if pnome:
                            partes.append(pnome)
                        break

        return " · ".join(partes)

    def _enriquecer_config_memoria(self, cfg: dict, desc_ref: str) -> dict:
        """Garante subcategoria_id/categoria_id se o registro histórico tiver esses campos vazios."""
        res = dict(cfg)
        termo_d = _norm_desc(desc_ref or res.get("descricao"))
        if not res.get("subcategoria_id") and termo_d:
            for s in (self.todas_subcategorias or self.subcategorias or []):
                if _norm(s.get("nome")) == termo_d:
                    res["subcategoria_id"] = str(s["id"])
                    if not res.get("categoria_id") and s.get("categoria_id"):
                        res["categoria_id"] = str(s["categoria_id"])
                    break
        return res

    def _obter_sugestoes_autocomplete(self, texto: str) -> list[dict]:
        """
        Retorna sugestões de Auto-Complete a partir de 3 letras digitadas.
        Prioriza rigorosamente a ÚLTIMA CONFIGURAÇÃO SALVA (Memória Evolutiva)
        para cada descrição encontrada no histórico.
        """
        termo = _norm_desc(texto)
        if not termo or len(termo) < 3:
            return []

        aba_atual = _tipo_normalizado_aba(self.state.tipo)
        ignorados = {"lancamento", "despesa", "receita", "transferencia", "ajuste", "saldo"}

        # Agrupa pelo nome limpo da descrição mantendo SEMPRE o registro mais recente (1º encontrado)
        candidatos_por_chave: dict[str, dict] = {}
        for idx, reg in enumerate(self.historico_memoria or []):
            if _norm(reg.get("subtipo")) == "provisionamento":
                continue
            desc_limpa = _limpar_sufixo_parcela(reg.get("descricao"))
            chave = _norm(desc_limpa)
            if not chave or len(chave) < 2 or chave in ignorados:
                continue

            # Verifica se a descrição casa com o termo de 3+ letras
            palavras = chave.split()
            if chave == termo:
                nivel_match = 0  # Match exato
            elif chave.startswith(termo):
                nivel_match = 1  # Prefixo direto (ex: "caf" -> "cafe", "gas" -> "gasolina")
            elif any(p.startswith(termo) for p in palavras):
                nivel_match = 2  # Prefixo de palavra
            elif termo in chave:
                nivel_match = 3  # Substring
            else:
                continue

            tipo_reg = _tipo_normalizado_aba(reg.get("tipo"))
            mesma_aba = (0 if tipo_reg == aba_atual else 1)

            if chave not in candidatos_por_chave:
                cfg_enriq = self._enriquecer_config_memoria(reg, desc_limpa)
                candidatos_por_chave[chave] = {
                    "chave": chave,
                    "label": desc_limpa,
                    "emoji": _emoji_para_descricao(desc_limpa),
                    "config": cfg_enriq,
                    "resumo": self._formatar_resumo_config(cfg_enriq),
                    "_score": (nivel_match, mesma_aba, idx),
                }

        sugestoes = sorted(candidatos_por_chave.values(), key=lambda x: x["_score"])
        if sugestoes:
            return sugestoes[:4]

        # Se não encontrou no histórico de lançamentos, verifica subcategorias / semântica para 3+ letras
        for s in (self.todas_subcategorias or self.subcategorias or []):
            s_nome_raw = str(s.get("nome") or "").strip()
            s_norm = _norm(s_nome_raw)
            if s_norm and (s_norm.startswith(termo) or any(p.startswith(termo) for p in s_norm.split())):
                cfg_sem = self._inferir_config_semantica(s_norm, s)
                if cfg_sem:
                    return [{
                        "chave": s_norm,
                        "label": s_nome_raw,
                        "emoji": _emoji_para_descricao(s_nome_raw),
                        "config": cfg_sem,
                        "resumo": self._formatar_resumo_config(cfg_sem),
                        "_score": (1, 0, 0),
                    }]

        cfg_fallback = self._inferir_config_semantica(termo, None)
        if cfg_fallback:
            lbl_sug = cfg_fallback.get("_label_sugerido") or texto.strip().capitalize()
            return [{
                "chave": _norm(lbl_sug),
                "label": lbl_sug,
                "emoji": _emoji_para_descricao(lbl_sug),
                "config": cfg_fallback,
                "resumo": self._formatar_resumo_config(cfg_fallback),
                "_score": (2, 0, 0),
            }]

        return []

    def _construir_box_autocomplete(self, texto: str):
        """Monta visualmente o dropdown de sugestão de Auto-Complete a partir de 3 letras."""
        sugestoes = self._obter_sugestoes_autocomplete(texto)
        self.sugestoes_atuais = sugestoes

        if not sugestoes:
            self.col_sugestoes_autocomplete.controls = []
            self.box_autocomplete.visible = False
            return

        linhas: list[ft.Control] = []
        for idx, sug in enumerate(sugestoes):
            destaque = (idx == 0)
            linhas.append(
                ft.Container(
                    content=ft.Row(
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(sug["emoji"], size=14),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                expand=True,
                                controls=[
                                    ft.Text(
                                        sug["label"],
                                        size=12.5,
                                        weight=ft.FontWeight.BOLD,
                                        color=T.PRIMARY if destaque else T.TEXT_PRIMARY,
                                    ),
                                    ft.Text(
                                        sug["resumo"] or "Última configuração salva",
                                        size=10.5,
                                        color=T.TEXT_MUTED,
                                        no_wrap=True,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                ],
                            ),
                            ft.Container(
                                content=ft.Text(
                                    "Completar ↵" if destaque else "Selecionar",
                                    size=10,
                                    weight=ft.FontWeight.W_600,
                                    color=T.PRIMARY,
                                ),
                                padding=pad(h=7, v=3),
                                bgcolor=f"{T.PRIMARY}18",
                                border_radius=6,
                            ),
                        ],
                    ),
                    padding=pad(h=8, v=5),
                    bgcolor=f"{T.PRIMARY}12" if destaque else ft.Colors.TRANSPARENT,
                    border_radius=8,
                    ink=True,
                    on_click=lambda _, s=sug: self._selecionar_sugestao_autocomplete(s),
                )
            )

        self.col_sugestoes_autocomplete.controls = linhas
        self.box_autocomplete.visible = True

    def _selecionar_sugestao_autocomplete(self, sugestao: dict):
        """
        Confirma a sugestão do Auto-Complete: completa o texto da Descrição,
        aplica a Última Configuração Salva de uma vez, oculta o box e foca no Valor!
        """
        if not sugestao:
            return
        lbl = str(sugestao.get("label") or "").strip()
        if lbl:
            self.state.descricao = lbl
            self.txt_descricao.value = lbl
            self._ultimo_termo_autofill = _norm_desc(lbl)

        cfg = sugestao.get("config") or self._buscar_config_memoria(lbl)
        if cfg:
            self._aplicar_config_memoria(cfg, atualizar_ui=False)

        self.box_autocomplete.visible = False
        self._construir_chips_atalhos_rapidos()
        self._safe_update(self)
        self._focar_campo_valor()
        self._notificar_mudanca()

    def _buscar_config_memoria(self, texto: str) -> Optional[dict]:
        """
        Busca na Memória Evolutiva a ÚLTIMA configuração salva para a descrição
        (a partir de 3 letras para prefixos, ou match exato).
        """
        termo = _norm_desc(texto)
        if not termo or len(termo) < 2:
            return None

        # 1. Busca match exato de descrição no histórico (o registro mais recente está no topo)
        for reg in (self.historico_memoria or []):
            if _norm(reg.get("subtipo")) == "provisionamento":
                continue
            if _norm_desc(reg.get("descricao")) == termo:
                return self._enriquecer_config_memoria(reg, texto)

        # 2. A partir de 3 letras, usa o motor de Auto-Complete (prefixo / palavra / última vez salva)
        if len(termo) >= 3:
            sugs = self._obter_sugestoes_autocomplete(texto)
            if sugs and sugs[0].get("config"):
                return dict(sugs[0]["config"])

        # 3. Verifica se existe uma Subcategoria com esse exato nome
        sub_match = None
        for s in (self.todas_subcategorias or self.subcategorias or []):
            if _norm(s.get("nome")) == termo:
                sub_match = s
                break

        if sub_match:
            sub_id_str = str(sub_match.get("id"))
            for reg in (self.historico_memoria or []):
                if str(reg.get("subcategoria_id") or "") == sub_id_str:
                    return self._enriquecer_config_memoria(reg, texto)

        # 4. Fallback Semântico Inteligente (para 1ª vez que digita)
        if len(termo) >= 3 or sub_match:
            return self._inferir_config_semantica(termo, sub_match)
        return None

    def _inferir_config_semantica(self, termo: str, sub_match: Optional[dict] = None) -> Optional[dict]:
        """
        Resolve Categoria, Subcategoria, Pote Financeiro, Perfil, Forma (Pix) e Conta
        automaticamente para itens do dia a dia (Café, Almoço, Gasolina, Mercado, Bebida, etc.)
        mesmo quando ainda não há lançamento prévio idêntico no histórico.
        """
        cat_id = None
        subcat_id = None
        pote_pos_alvo = None
        label_sugerido = None

        if sub_match and sub_match.get("id"):
            subcat_id = str(sub_match["id"])
            label_sugerido = str(sub_match.get("nome") or "").strip()
            if sub_match.get("categoria_id"):
                cat_id = str(sub_match["categoria_id"])

        # Dicionário semântico de itens cotidianos -> (gatilhos, label_padrao, palavras_cat, palavras_sub, posicao_pote)
        regras_cotidiano = [
            (("cafe", "padaria", "lanche", "acai", "sorvete", "doce"), "Café", ("aliment", "lazer"), ("cafe", "padaria", "lanche"), 4),
            (("almoco", "jantar", "restaurante", "refeicao", "marmita"), "Almoço", ("aliment",), ("almoco", "restaurante", "refeicao"), 2),
            (("ifood", "delivery", "pizza", "hamburguer", "burger", "sushi"), "iFood", ("aliment", "lazer"), ("ifood", "delivery", "restaurante", "lanche"), 4),
            (("bebida", "cerveja", "bar", "adega", "vinho", "chopp"), "Bebida", ("lazer", "aliment"), ("bebida", "bar", "adega"), 4),
            (("mercado", "supermercado", "feira", "hortifruti", "acougue"), "Mercado", ("aliment",), ("mercado", "supermercado", "feira"), 2),
            (("gasolina", "combustivel", "etanol", "posto", "abastecimento"), "Gasolina", ("transp",), ("gasolina", "combustivel"), 2),
            (("uber", "99", "taxi", "estacionamento", "pedagio", "onibus", "metro"), "Uber", ("transp",), ("uber", "aplicativo", "estacionamento", "transporte"), 2),
            (("farmacia", "remedio", "drogaria", "consulta", "exame"), "Farmácia", ("saud",), ("farmacia", "remedio", "consulta"), 2),
            (("aluguel", "condominio", "iptu", "luz", "energia", "agua", "internet"), "Aluguel", ("morad", "casa", "fix"), ("aluguel", "condominio", "luz", "internet", "agua"), 1),
            (("curso", "livro", "faculdade", "escola", "treinamento"), "Curso", ("educ", "conhec"), ("curso", "livro"), 5),
            (("dj", "equipamento", "controladora", "notebook"), "Equipamento DJ", ("dj", "invest", "meta"), ("equipamento", "notebook", "dj"), 3),
        ]

        regra_encontrada = None
        for gatilhos, lbl_pad, kw_cats, kw_subs, pos_pote in regras_cotidiano:
            if any(termo == g or g in termo.split() or (len(termo) >= 3 and g.startswith(termo)) for g in gatilhos):
                regra_encontrada = (kw_cats, kw_subs, pos_pote)
                if not label_sugerido:
                    label_sugerido = lbl_pad
                break

        # Verifica também se o termo bate com o nome de alguma Categoria cadastrada
        if not cat_id:
            for c in self.categorias:
                c_nome = _norm(c.get("nome"))
                if c_nome and (c_nome == termo or (regra_encontrada and any(k in c_nome for k in regra_encontrada[0]))):
                    cat_id = str(c["id"])
                    break

        if not sub_match and not regra_encontrada and not cat_id:
            return None

        if regra_encontrada:
            kw_cats, kw_subs, pote_pos_alvo = regra_encontrada
            if not cat_id and self.categorias:
                for c in self.categorias:
                    if any(k in _norm(c.get("nome")) for k in kw_cats):
                        cat_id = str(c["id"])
                        break
            if not subcat_id:
                pool_subs = [
                    s for s in (self.todas_subcategorias or self.subcategorias)
                    if not cat_id or str(s.get("categoria_id")) == str(cat_id)
                ]
                for s in pool_subs:
                    s_n = _norm(s.get("nome"))
                    if s_n == termo or any(k in s_n for k in kw_subs):
                        subcat_id = str(s["id"])
                        if not cat_id and s.get("categoria_id"):
                            cat_id = str(s["categoria_id"])
                        break

        if not cat_id and self.categorias:
            cat_id = str(self.categorias[0]["id"])

        # Resolve pote_id pela posição semântica ou pela categoria
        pote_id = self._obter_pote_id_por_posicao(pote_pos_alvo) if pote_pos_alvo else None
        if not pote_id:
            pote_id = self._inferir_pote_por_categoria(cat_id, subcat_id)

        # Resolve membro padrão e conta padrão
        membro_id = self.state.membro_id
        if not membro_id and self.membros:
            prin = next((m for m in self.membros if m.get("principal")), self.membros[0])
            membro_id = str(prin["id"])

        conta_id = self.state.conta_id
        if not conta_id and self.contas:
            conta_membro = next(
                (c for c in self.contas if membro_id and str(c.get("membro_id")) == str(membro_id)),
                self.contas[0],
            )
            conta_id = str(conta_membro["id"])

        return {
            "tipo": "Despesa",
            "membro_id": membro_id,
            "forma_movimentacao": "Pix",
            "conta_id": conta_id,
            "cartao_id": None,
            "caixinha_id": None,
            "categoria_id": cat_id,
            "subcategoria_id": subcat_id,
            "pote_id": pote_id,
            "regra": obter_regra_pote(pote_id, self._potes_cache),
            "_label_sugerido": label_sugerido,
        }

    def _obter_pote_id_por_posicao(self, posicao: int) -> Optional[str]:
        if not posicao or not self._potes_cache:
            return None
        for p in self._potes_cache:
            pos = getattr(p, "posicao", None)
            if pos is None and isinstance(p, dict):
                pos = p.get("posicao")
            try:
                if int(pos) == int(posicao):
                    pid = getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else None)
                    return str(pid) if pid else None
            except (ValueError, TypeError):
                pass
        return None

    def _inferir_pote_por_categoria(self, cat_id: Optional[str], subcat_id: Optional[str] = None) -> Optional[str]:
        """
        Infere o Pote Financeiro ideal com base na Categoria/Subcategoria selecionada:
        1º: Verifica qual pote foi usado por último no histórico para essa subcategoria ou categoria.
        2º: Aplica heurística semântica pelo nome da subcategoria/categoria nos 6 Potes.
        """
        if not self._potes_cache:
            return None

        ids_potes_validos = {
            str(getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else ""))
            for p in self._potes_cache
        }

        # 1. Histórico real do usuário para a subcategoria ou categoria
        if subcat_id:
            for reg in (self.historico_memoria or []):
                pid = str(reg.get("pote_id") or "")
                if str(reg.get("subcategoria_id") or "") == str(subcat_id) and pid in ids_potes_validos:
                    return pid

        if cat_id:
            for reg in (self.historico_memoria or []):
                pid = str(reg.get("pote_id") or "")
                if str(reg.get("categoria_id") or "") == str(cat_id) and pid in ids_potes_validos:
                    return pid

        # 2. Heurística semântica pelo nome da Subcategoria e Categoria
        nome_cat = ""
        for c in self.categorias:
            if str(c.get("id")) == str(cat_id):
                nome_cat = _norm(c.get("nome"))
                break

        nome_sub = ""
        for s in (self.todas_subcategorias or self.subcategorias or []):
            if str(s.get("id")) == str(subcat_id):
                nome_sub = _norm(s.get("nome"))
                break

        texto_ref = f"{nome_sub} {nome_cat}".strip()
        pos_alvo = 2  # Default: Custos Semi Fixos
        if any(k in texto_ref for k in ("cafe", "bar", "bebida", "lazer", "prazer", "restaurante", "ifood", "festa", "cinema", "viagem", "jogo", "streaming")):
            pos_alvo = 4  # Prazeres
        elif any(k in texto_ref for k in ("morad", "aluguel", "condominio", "luz", "agua", "internet", "fixo", "plano", "seguro")):
            pos_alvo = 1  # Custos Fixos
        elif any(k in texto_ref for k in ("educ", "conhec", "curso", "livro", "faculdade", "escola")):
            pos_alvo = 5  # Conhecimento
        elif any(k in texto_ref for k in ("invest", "liberdad", "poupanc", "reserva", "aporte", " Tesouro", "cdb", "acao")):
            pos_alvo = 6  # Liberdade Financeira
        elif any(k in texto_ref for k in ("meta", "dj", "equipamento", "sonho", "objetivo")):
            pos_alvo = 3  # Metas
        elif any(k in texto_ref for k in ("aliment", "mercado", "supermercado", "transp", "gasolina", "combustivel", "saud", "farmacia")):
            pos_alvo = 2  # Custos Semi Fixos

        return self._obter_pote_id_por_posicao(pos_alvo) or (next(iter(ids_potes_validos)) if ids_potes_validos else None)

    def _aplicar_config_memoria(self, cfg: dict, atualizar_ui: bool = True) -> bool:
        """
        Aplica os dados recuperados da Memória Inteligente (Tipo, Perfil, Forma,
        Conta/Cartão/Caixinha/Destino, Categoria, Subcategoria e Pote) no state e na UI.
        """
        if not cfg:
            return False

        # 1. Tipo (Despesa / Receita / Transferencia)
        tipo_mem = cfg.get("tipo")
        if tipo_mem:
            self.state.tipo = _tipo_normalizado_aba(tipo_mem)
            self.state.subtipo = "Transferência" if self.state.eh_transferencia else self.state.tipo

        # 2. Perfil Familiar (membro_id)
        m_id = str(cfg.get("membro_id") or "")
        ids_membros = {str(m.get("id")) for m in self.membros if m.get("id")}
        if m_id and m_id in ids_membros:
            self.state.membro_id = m_id

        # 3. Forma de Movimentação
        forma_mem = cfg.get("forma_movimentacao")
        cx_mem = str(cfg.get("caixinha_id") or "")
        subtipo_mem = _norm(cfg.get("subtipo"))
        if self.state.eh_despesa and cx_mem and subtipo_mem != "provisionamento":
            self.state.forma_movimentacao = "Caixinha"
            self.state.subtipo = "Consumo Caixinha"
        elif forma_mem:
            opcoes_validas = (
                FORMAS_RECEITA
                if self.state.eh_receita
                else (FORMAS_TRANSFERENCIA if self.state.eh_transferencia else FORMAS_DESPESA)
            )
            f_norm = _norm(forma_mem)
            f_match = next((op for op in opcoes_validas if _norm(op) == f_norm), None)
            if f_match:
                self.state.forma_movimentacao = f_match

        # 4. Conta / Cartão / Caixinha / Destino
        ids_contas = {str(c.get("id")) for c in self.contas if c.get("id")}
        ids_cartoes = {str(c.get("id")) for c in self.cartoes if c.get("id")}
        ids_caixinhas = {str(c.get("id")) for c in self.caixinhas if c.get("id")}

        if self.state.eh_credito:
            c_id = str(cfg.get("cartao_id") or "")
            if c_id in ids_cartoes:
                self.state.cartao_id = c_id
            elif self.cartoes and not self.state.cartao_id:
                self.state.cartao_id = str(self.cartoes[0]["id"])
            self.state.conta_id = None
            self.state.caixinha_id = None
        elif self.state.eh_caixinha:
            if cx_mem in ids_caixinhas:
                self.state.caixinha_id = cx_mem
            elif self.caixinhas and not self.state.caixinha_id:
                self.state.caixinha_id = str(self.caixinhas[0]["id"])
            self.state.conta_id = None
            self.state.cartao_id = None
        else:
            cnt_id = str(cfg.get("conta_id") or "")
            if cnt_id in ids_contas:
                self.state.conta_id = cnt_id
            elif self.contas and not self.state.conta_id:
                self.state.conta_id = str(self.contas[0]["id"])
            self.state.cartao_id = None
            self.state.caixinha_id = None

        if self.state.eh_transferencia:
            dest_id = str(cfg.get("destino_id") or "")
            if dest_id in ids_contas:
                self.state.destino_id = dest_id

        # 5. Categoria e Subcategoria
        if not self.state.eh_transferencia:
            ids_cats = {str(c.get("id")) for c in self.categorias if c.get("id")}
            cat_mem = str(cfg.get("categoria_id") or "")
            if cat_mem in ids_cats:
                self.state.categoria_id = cat_mem
            self._carregar_subcategorias(self.state.categoria_id, atualizar_ui=False)

            ids_subs = {str(s.get("id")) for s in self.subcategorias if s.get("id")}
            sub_mem = str(cfg.get("subcategoria_id") or "")
            if sub_mem in ids_subs:
                self.state.subcategoria_id = sub_mem
            else:
                termo_d = _norm_desc(cfg.get("descricao") or self.state.descricao)
                sub_por_nome = next(
                    (str(s["id"]) for s in self.subcategorias if _norm(s.get("nome")) == termo_d),
                    None,
                )
                self.state.subcategoria_id = sub_por_nome

        # 6. Pote Financeiro e Regra 50/30/20
        if self.state.eh_despesa:
            ids_potes = {
                str(getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else ""))
                for p in (self._potes_cache or [])
            }
            pote_mem = str(cfg.get("pote_id") or "")
            if pote_mem and pote_mem in ids_potes:
                self.state.pote_id = pote_mem
            else:
                pote_inf = self._inferir_pote_por_categoria(self.state.categoria_id, self.state.subcategoria_id)
                if pote_inf:
                    self.state.pote_id = pote_inf
            self.state.regra = obter_regra_pote(
                self.state.pote_id or cfg.get("regra") or self.state.regra,
                self._potes_cache,
            )
            self.dd_regra.value = self.state.pote_id or self.state.regra

        # 7. Monta resumo amigável no Badge de Auto-Preenchimento
        partes_resumo: list[str] = []
        if self.state.membro_id:
            m_obj = next((m for m in self.membros if str(m.get("id")) == str(self.state.membro_id)), None)
            if m_obj and m_obj.get("nome"):
                partes_resumo.append(str(m_obj["nome"]))
        partes_resumo.append(self.state.forma_movimentacao)

        if self.state.eh_credito and self.state.cartao_id:
            k_obj = next((k for k in self.cartoes if str(k.get("id")) == str(self.state.cartao_id)), None)
            if k_obj and k_obj.get("nome"):
                partes_resumo.append(str(k_obj["nome"]))
        elif self.state.eh_caixinha and self.state.caixinha_id:
            cx_obj = next((c for c in self.caixinhas if str(c.get("id")) == str(self.state.caixinha_id)), None)
            if cx_obj and cx_obj.get("nome"):
                partes_resumo.append(str(cx_obj["nome"]))
        elif self.state.conta_id:
            c_obj = next((c for c in self.contas if str(c.get("id")) == str(self.state.conta_id)), None)
            if c_obj and c_obj.get("nome"):
                partes_resumo.append(str(c_obj["nome"]))

        if not self.state.eh_transferencia and self.state.categoria_id:
            cat_obj = next((c for c in self.categorias if str(c.get("id")) == str(self.state.categoria_id)), None)
            cat_txt = str(cat_obj["nome"]) if (cat_obj and cat_obj.get("nome")) else ""
            if self.state.subcategoria_id:
                sub_obj = next((s for s in self.subcategorias if str(s.get("id")) == str(self.state.subcategoria_id)), None)
                if sub_obj and sub_obj.get("nome"):
                    cat_txt = f"{cat_txt} > {sub_obj['nome']}" if cat_txt else str(sub_obj["nome"])
            if cat_txt:
                partes_resumo.append(cat_txt)

        if self.state.eh_despesa and self.state.pote_id and self._potes_cache:
            for p in self._potes_cache:
                pid = str(getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else ""))
                if pid == str(self.state.pote_id):
                    pnome = str(getattr(p, "nome", None) or (p.get("nome") if isinstance(p, dict) else ""))
                    if pnome:
                        partes_resumo.append(pnome)
                    break

        self.lbl_autofill_resumo.value = "Auto-preenchido: " + " · ".join(partes_resumo)
        self.badge_autofill.visible = True

        # 8. Sincroniza controles com o novo estado
        self._atualizar_opcoes_membro(atualizar_ui=False)
        self._atualizar_opcoes_forma(atualizar_ui=False)
        self._atualizar_opcoes_conta_ou_cartao(atualizar_ui=False)
        self._atualizar_opcoes_caixinhas(atualizar_ui=False)
        self._atualizar_opcoes_fatura(atualizar_ui=False)
        self._atualizar_opcoes_categoria(atualizar_ui=False)
        if self.state.categoria_id:
            self._carregar_subcategorias(self.state.categoria_id, atualizar_ui=False)
        self._construir_chips_potes()
        self._sincronizar_estado_com_ui()

        if atualizar_ui:
            self._safe_update(self)
        self._notificar_mudanca()
        return True

    def _aplicar_atalho_rapido(self, item: dict):
        """
        Acionado ao tocar com 1 clique em um chip do Ranking Vivo (ex: ☕ Café).
        Preenche a Descrição, aplica a Última Configuração Salva e joga o foco para o Valor!
        """
        lbl = item.get("label") or ""
        self.state.descricao = lbl
        self.txt_descricao.value = lbl
        self._ultimo_termo_autofill = _norm_desc(lbl)
        self.box_autocomplete.visible = False

        cfg = item.get("historico") or self._buscar_config_memoria(lbl)
        if cfg:
            cfg_enriq = self._enriquecer_config_memoria(cfg, lbl)
            self._aplicar_config_memoria(cfg_enriq, atualizar_ui=False)

        self._construir_chips_atalhos_rapidos()
        self._safe_update(self)
        self._focar_campo_valor()
        self._notificar_mudanca()

    def _ao_mudar_descricao(self, e):
        texto = (e.control.value if (e and hasattr(e, "control") and e.control) else self.txt_descricao.value) or ""
        self.state.descricao = texto
        if self.txt_descricao.value != texto:
            self.txt_descricao.value = texto
        termo = _norm_desc(texto)

        # Menos de 3 letras: não dispara auto-complete (evita falsos positivos e mantém digitação livre)
        if len(termo) < 3:
            self.sugestoes_atuais = []
            if self.box_autocomplete.visible:
                self.box_autocomplete.visible = False
                self._safe_update(self.box_autocomplete)
            if self.badge_autofill.visible:
                self.badge_autofill.visible = False
                self._safe_update(self.badge_autofill)
            self._construir_chips_atalhos_rapidos()
            self._safe_update(self.row_atalhos_rapidos)
            self._notificar_mudanca()
            return

        # A partir de 3 letras: exibe imediatamente as sugestões de Auto-Complete e pré-preenche
        # todos os campos com base na Última Configuração Salva da melhor sugestão!
        self._construir_box_autocomplete(texto)

        if not self.state.lancamento_id and self.sugestoes_atuais:
            melhor = self.sugestoes_atuais[0]
            cfg = melhor.get("config")
            if cfg:
                self._ultimo_termo_autofill = termo
                self._aplicar_config_memoria(cfg, atualizar_ui=False)
                self._construir_chips_atalhos_rapidos()
                # Atualiza os blocos de configuração SEM re-renderizar txt_descricao (evita pulo de cursor)
                for ctrl in (
                    self.btn_tipo,
                    self.box_autocomplete,
                    self.badge_autofill,
                    self.row_atalhos_rapidos,
                    self.sec_membro,
                    self.sec_forma,
                    self.row_conta,
                    self.row_destino,
                    self.row_caixinha,
                    self.row_fatura,
                    self.row_parcelas,
                    self.row_cat_subcat_grid,
                    self.sec_potes,
                    self.col_detalhes,
                ):
                    self._safe_update(ctrl)
                return

        if self.badge_autofill.visible:
            self.badge_autofill.visible = False
            self._safe_update(self.badge_autofill)
        self._safe_update(self.box_autocomplete)
        self._construir_chips_atalhos_rapidos()
        self._safe_update(self.row_atalhos_rapidos)
        self._notificar_mudanca()

    def _ao_submeter_descricao(self, _=None):
        """
        Ao pressionar Enter na Descrição: se houver sugestão de Auto-Complete ativa,
        completa o nome completo da sugestão e pula o foco direto para o Valor!
        """
        if self.box_autocomplete.visible and self.sugestoes_atuais:
            self._selecionar_sugestao_autocomplete(self.sugestoes_atuais[0])
            return
        self._focar_campo_valor()

    # =========================================================================
    # CHIPS DE 1 CLIQUE: PERFIL FAMILIAR, FORMA DE MOVIMENTAÇÃO E 6 POTES
    # =========================================================================
    def _construir_chips_membro(self):
        chips: list[ft.Control] = []
        membro_sel = str(self.state.membro_id or "")

        for m in (self.membros or []):
            m_id = str(m.get("id") or "")
            if not m_id:
                continue
            ativo = (m_id == membro_sel)
            cor_m = str(m.get("cor") or T.PRIMARY)
            nome_m = str(m.get("nome") or "Membro")

            chips.append(
                ft.Container(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED if ativo else ft.Icons.PERSON_ROUNDED,
                                size=15,
                                color=cor_m if ativo else T.TEXT_MUTED,
                            ),
                            ft.Text(
                                nome_m,
                                size=12,
                                weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                color=T.TEXT_PRIMARY if ativo else T.TEXT_MUTED,
                            ),
                        ],
                    ),
                    padding=pad(h=12, v=6),
                    bgcolor=f"{cor_m}26" if ativo else T.SURFACE_ALT,
                    border_radius=10,
                    border=borda(1.8 if ativo else 1, cor_m if ativo else T.BORDER),
                    ink=True,
                    on_click=lambda _, mid=m_id: self._selecionar_membro_chip(mid),
                )
            )

        self.row_chips_membro.controls = chips
        self.sec_membro.visible = bool(chips)

    def _selecionar_membro_chip(self, membro_id: str):
        self.state.membro_id = str(membro_id) if membro_id else None
        self.dd_membro.value = self.state.membro_id
        self._construir_chips_membro()

        # Se o membro selecionado possuir uma conta ou cartão próprio, sugere automaticamente
        if self.state.membro_id:
            if self.state.eh_credito and self.cartoes:
                k_m = next((k for k in self.cartoes if str(k.get("membro_id")) == self.state.membro_id), None)
                if k_m and k_m.get("id"):
                    self.state.cartao_id = str(k_m["id"])
                    self.dd_conta.value = self.state.cartao_id
                    self._atualizar_opcoes_fatura(atualizar_ui=True)
                    self._safe_update(self.row_conta)
            elif not self.state.eh_caixinha and self.contas:
                c_m = next((c for c in self.contas if str(c.get("membro_id")) == self.state.membro_id), None)
                if c_m and c_m.get("id"):
                    self.state.conta_id = str(c_m["id"])
                    self.dd_conta.value = self.state.conta_id
                    self._safe_update(self.row_conta)

        self._safe_update(self.sec_membro)
        self._notificar_mudanca()

    def _construir_chips_forma(self):
        if self.state.eh_receita:
            opcoes = list(FORMAS_RECEITA)
        elif self.state.eh_transferencia:
            opcoes = list(FORMAS_TRANSFERENCIA)
        else:
            opcoes = list(FORMAS_DESPESA)
            # Se estiver editando um lançamento antigo em "Dinheiro", exibe a pílula também
            if _norm(self.state.forma_movimentacao) == "dinheiro" and "Dinheiro" not in opcoes:
                opcoes.append("Dinheiro")

        icones_forma = {
            "pix": ft.Icons.PIX_ROUNDED,
            "credito": ft.Icons.CREDIT_CARD_ROUNDED,
            "debito": ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
            "caixinha": ft.Icons.INVENTORY_2_ROUNDED,
            "dinheiro": ft.Icons.PAYMENTS_ROUNDED,
        }

        forma_sel_norm = _norm(self.state.forma_movimentacao)
        chips: list[ft.Control] = []

        for op in opcoes:
            op_norm = _norm(op)
            ativo = (op_norm == forma_sel_norm)
            icone = icones_forma.get(op_norm, ft.Icons.PAYMENTS_ROUNDED)

            chips.append(
                ft.Container(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                icone,
                                size=15,
                                color=T.ON_PRIMARY if ativo else T.PRIMARY,
                            ),
                            ft.Text(
                                op,
                                size=12,
                                weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_600,
                                color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                            ),
                        ],
                    ),
                    padding=pad(h=12, v=7),
                    bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                    border_radius=10,
                    border=borda(1.5 if ativo else 1, T.PRIMARY if ativo else T.BORDER),
                    ink=True,
                    on_click=lambda _, f=op: self._selecionar_forma_chip(f),
                )
            )

        self.row_chips_forma.controls = chips

    def _selecionar_forma_chip(self, nova_forma: str):
        self.state.mudar_forma(nova_forma)
        self.dd_forma.value = self.state.forma_movimentacao
        self._construir_chips_forma()
        self._atualizar_opcoes_conta_ou_cartao(atualizar_ui=False)
        self._atualizar_opcoes_caixinhas(atualizar_ui=False)
        self._atualizar_opcoes_fatura(atualizar_ui=False)
        self._sincronizar_estado_com_ui()
        self._safe_update(self)
        self._notificar_mudanca()

    def _construir_chips_potes(self):
        potes_lista = self._potes_cache if self._potes_cache else POTES_PADRAO
        pote_sel = str(self.state.pote_id or self.state.regra or "")

        icones_pos = {
            1: ft.Icons.LOCK_CLOCK_ROUNDED,      # Custos Fixos
            2: ft.Icons.SHOPPING_BAG_ROUNDED,    # Custos Semi Fixos
            3: ft.Icons.FLAG_ROUNDED,            # Metas
            4: ft.Icons.CELEBRATION_ROUNDED,     # Prazeres
            5: ft.Icons.SCHOOL_ROUNDED,          # Conhecimento
            6: ft.Icons.TRENDING_UP_ROUNDED,     # Liberdade Financeira
        }

        chips: list[ft.Control] = []
        for idx, p in enumerate(potes_lista, start=1):
            pid = str(getattr(p, "id", None) or (p.get("id") if isinstance(p, dict) else "") or f"pote-{idx}")
            pos = int(getattr(p, "posicao", None) or (p.get("posicao") if isinstance(p, dict) else idx) or idx)
            pnome = str(getattr(p, "nome", None) or (p.get("nome") if isinstance(p, dict) else f"Pote {pos}"))
            pcor = str(getattr(p, "cor", None) or (p.get("cor") if isinstance(p, dict) else "#00E676") or "#00E676")
            try:
                pperc = float(getattr(p, "percentual", None) or (p.get("percentual") if isinstance(p, dict) else 0.0) or 0.0)
            except Exception:
                pperc = 0.0

            # Ajusta cores muito escuras (como #800080 no tema escuro) para leitura vibrante
            cor_vis = "#A855F7" if pcor.upper() == "#800080" else pcor
            ativo = (pid == pote_sel or pnome.lower() == pote_sel.lower())
            icone = icones_pos.get(pos, ft.Icons.PIE_CHART_ROUNDED)

            chips.append(
                ft.Container(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(
                                ft.Icons.CHECK_CIRCLE_ROUNDED if ativo else icone,
                                size=14,
                                color=cor_vis,
                            ),
                            ft.Text(
                                f"{pnome}",
                                size=11.5,
                                weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                color=T.TEXT_PRIMARY if ativo else T.TEXT_MUTED,
                            ),
                            ft.Text(
                                f"{pperc:g}%",
                                size=10,
                                weight=ft.FontWeight.W_600,
                                color=cor_vis,
                            ),
                        ],
                    ),
                    padding=pad(h=10, v=6),
                    bgcolor=f"{cor_vis}28" if ativo else T.SURFACE_ALT,
                    border_radius=10,
                    border=borda(1.8 if ativo else 1, cor_vis if ativo else f"{cor_vis}40"),
                    ink=True,
                    on_click=lambda _, chave_p=pid: self._selecionar_pote_chip(chave_p, manual=True),
                )
            )

        self.wrap_chips_potes.controls = chips
        if hasattr(self, "lbl_macro_regra_pote"):
            self.lbl_macro_regra_pote.value = f"Pilar 50/30/20: {self.state.regra or 'Essencial'}"

    def _selecionar_pote_chip(self, pote_id: str, manual: bool = True):
        if manual:
            self._pote_escolhido_manualmente = True
        potes = getattr(self, "_potes_cache", None)
        if potes:
            self.state.pote_id = str(pote_id) if pote_id else None
            self.state.regra = obter_regra_pote(pote_id, potes)
        else:
            self.state.pote_id = None
            self.state.regra = obter_regra_pote(pote_id)
        self.dd_regra.value = self.state.pote_id or self.state.regra
        self._construir_chips_potes()
        self._safe_update(self.sec_potes)
        self._notificar_mudanca()

    # =========================================================================
    # CARREGAMENTO E ATUALIZAÇÃO DE OPÇÕES
    # =========================================================================
    def _carregar_dados_iniciais(self):
        self._atualizar_opcoes_membro(atualizar_ui=False)
        self._atualizar_opcoes_forma(atualizar_ui=False)
        self._atualizar_opcoes_conta_ou_cartao(atualizar_ui=False)
        self._atualizar_opcoes_caixinhas(atualizar_ui=False)
        self._atualizar_opcoes_fatura(atualizar_ui=False)
        self._atualizar_opcoes_categoria(atualizar_ui=False)

        if self.state.categoria_id:
            self._carregar_subcategorias(self.state.categoria_id, atualizar_ui=False)

        # Se for novo lançamento sem pote explícito, infere o pote inicial pela categoria padrão
        if not self.state.lancamento_id and self.state.eh_despesa and not self._pote_escolhido_manualmente:
            pote_sug = self._inferir_pote_por_categoria(self.state.categoria_id, self.state.subcategoria_id)
            if pote_sug:
                self.state.pote_id = pote_sug
                self.state.regra = obter_regra_pote(pote_sug, self._potes_cache)
                self.dd_regra.value = pote_sug
                self._construir_chips_potes()

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
            # Filtra em memória a partir de self.todas_subcategorias (0ms) ou consulta cache do db
            if self.todas_subcategorias:
                filtradas = [
                    s for s in self.todas_subcategorias
                    if str(s.get("categoria_id")) == str(cat_uuid)
                ]
                self.subcategorias = filtradas if filtradas else db.listar_subcategorias(cat_uuid)
            else:
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
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=12, color=T.ON_PRIMARY if ativo else T.TEXT_MUTED)
                        if eh_outros else ft.Container(),
                        ft.Text(
                            label,
                            size=11,
                            weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                            color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                        ),
                    ],
                ),
                padding=pad(h=9, v=4),
                bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                border_radius=11,
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
        self.switch_status.visible = (not self.state.eh_transferencia and not self.state.eh_caixinha)
        self.switch_status.label = "Recebida" if self.state.eh_receita else "Paga"

        # 3. Cores e Segmentos
        cor_tema = (
            T.DESPESA
            if self.state.eh_despesa
            else (T.RECEITA if self.state.eh_receita else T.PRIMARY)
        )
        self.txt_valor.color = cor_tema
        self.txt_valor.prefix.color = cor_tema
        self.txt_valor.focused_border_color = cor_tema

        # 4. Visibilidade Dinâmica conforme Tipo e Forma de Movimentação
        is_transf = self.state.eh_transferencia
        is_credito = self.state.eh_credito
        is_caixinha = self.state.eh_caixinha

        self.row_conta.visible = (not is_caixinha)
        self.row_destino.visible = is_transf
        self.row_caixinha.visible = is_caixinha
        self.row_fatura.visible = is_credito
        self.row_parcelas.visible = is_credito

        self.row_categoria.visible = not is_transf
        self.row_subcategoria.visible = not is_transf
        self.row_cat_subcat_grid.visible = not is_transf

        self.sec_potes.visible = self.state.eh_despesa
        self.dd_regra.visible = self.state.eh_despesa

        # Atualiza chips de 1 clique
        self._construir_chips_membro()
        self._construir_chips_forma()
        self._construir_chips_potes()

        # 5. Switches Fixa e Repetir: Ocultos em Transferência, Crédito e Caixinha
        mostrar_rec = (not is_transf and not is_credito and not is_caixinha)
        self.row_switches_recorrencia.visible = mostrar_rec
        self.col_detalhes.visible = mostrar_rec or self.state.is_fixa or self.state.is_repetir
        self.switch_fixa.label = "Receita Fixa" if self.state.eh_receita else "Despesa Fixa"

        if self.state.is_fixa and not is_credito:
            self.col_opcoes_recorrencia.visible = True
            self.txt_repetir_qtd.visible = False
            self.lbl_resumo_repetir.value = "Lançamento agendado e materializado para os próximos 12 meses."
            self.lbl_resumo_repetir.color = T.PRIMARY
        elif self.state.is_repetir and not is_credito:
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
            self.dd_parcelas.value = str(self.state.quantidade if self.state.quantidade > 0 else 1)
            self._atualizar_resumo_parcelas(atualizar_ui=False)
            self._atualizar_opcoes_fatura(atualizar_ui=False)

    def _atualizar_opcoes_forma(self, atualizar_ui: bool = True):
        if self.state.eh_receita:
            opcoes = list(FORMAS_RECEITA)
        elif self.state.eh_transferencia:
            opcoes = list(FORMAS_TRANSFERENCIA)
        else:
            opcoes = list(FORMAS_DESPESA)
            if _norm(self.state.forma_movimentacao) == "dinheiro" and "Dinheiro" not in opcoes:
                opcoes.append("Dinheiro")

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
        self._construir_chips_forma()
        if atualizar_ui:
            self._safe_update(self.sec_forma)

    def _atualizar_opcoes_conta_ou_cartao(self, atualizar_ui: bool = True):
        is_credito = self.state.eh_credito
        is_caixinha = self.state.eh_caixinha
        if is_caixinha:
            self.state.conta_id = None
            self.state.cartao_id = None
            self.dd_conta.value = None
        elif is_credito:
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

        if self.state.fatura_id and self.state.fatura_id not in self._faturas_opcoes_cache:
            try:
                fat_d = db.obter_fatura_por_id(self.state.fatura_id)
                if fat_d:
                    m = int(fat_d.get("mes") or 1)
                    a = int(fat_d.get("ano") or 2026)
                    st = (fat_d.get("status") or "Aberta").capitalize()
                    from core.constants import MESES_NOMES
                    m_label = MESES_NOMES[m - 1] if 1 <= m <= 12 else str(m)
                    lbl = f"{m_label}/{a} · {st}"
                    dropdown_opts.append(ft.dropdown.Option(key=self.state.fatura_id, text=lbl))
                    self._faturas_opcoes_cache[self.state.fatura_id] = {
                        "id": self.state.fatura_id,
                        "fatura_id_real": self.state.fatura_id,
                        "mes": m,
                        "ano": a,
                        "label": lbl,
                    }
                    self.state.fatura_manual_mes = m
                    self.state.fatura_manual_ano = a
            except Exception:
                pass

        self.dd_fatura.options = dropdown_opts
        if self.state.fatura_id and self.state.fatura_id in self._faturas_opcoes_cache:
            self.dd_fatura.value = self.state.fatura_id
            opt = self._faturas_opcoes_cache[self.state.fatura_id]
            self.state.fatura_manual_mes = opt.get("mes")
            self.state.fatura_manual_ano = opt.get("ano")
        else:
            self.dd_fatura.value = ""
            self.state.fatura_id = None
            self.state.fatura_manual_mes = None
            self.state.fatura_manual_ano = None

        if atualizar_ui:
            self._safe_update(self.row_fatura)

    def _atualizar_opcoes_caixinhas(self, atualizar_ui: bool = True):
        if not self.caixinhas:
            try:
                self.caixinhas = db.listar_caixinhas_opcoes() or []
            except Exception:
                self.caixinhas = []

        opcoes = []
        for c in self.caixinhas:
            saldo_str = formatar_moeda(c.get("saldo_atual", 0))
            opcoes.append(
                ft.dropdown.Option(
                    key=str(c["id"]),
                    text=f"{c.get('nome', 'Caixinha')} · Saldo: {saldo_str}",
                )
            )
        self.dd_caixinha.options = opcoes
        ids_cx = {str(c["id"]) for c in self.caixinhas if c.get("id")}
        if self.state.eh_caixinha and self.state.caixinha_id not in ids_cx:
            self.state.caixinha_id = str(self.caixinhas[0]["id"]) if self.caixinhas else None
            if self.state.caixinha_id:
                self._vincular_dados_da_caixinha(self.state.caixinha_id, atualizar_ui=False)
        self.dd_caixinha.value = self.state.caixinha_id or ""
        if atualizar_ui:
            self._safe_update(self.row_caixinha)

    def _vincular_dados_da_caixinha(self, caixinha_id: Optional[str], atualizar_ui: bool = True):
        if not caixinha_id:
            return
        for c in self.caixinhas:
            if str(c.get("id")) == str(caixinha_id):
                if c.get("pote_id"):
                    self.state.pote_id = str(c["pote_id"])
                    self.state.regra = obter_regra_pote(self.state.pote_id, getattr(self, "_potes_cache", None))
                    self.dd_regra.value = self.state.pote_id
                    self._construir_chips_potes()
                if c.get("categoria_id"):
                    self.state.categoria_id = str(c["categoria_id"])
                    self.dd_categoria.value = self.state.categoria_id
                    self._carregar_subcategorias(self.state.categoria_id, atualizar_ui=False)
                if c.get("subcategoria_id"):
                    self.state.subcategoria_id = str(c["subcategoria_id"])
                    self.dd_subcategoria.value = self.state.subcategoria_id
                if atualizar_ui:
                    self._safe_update(self)
                break

    def _ao_mudar_caixinha(self, e):
        val = e.data or (e.control.value if (e and hasattr(e, "control") and e.control) else None)
        cid = self._obter_caixinha_id(val)
        self.state.caixinha_id = cid
        if cid and self.state.eh_despesa:
            self.state.forma_movimentacao = "Caixinha"
            self.state.conta_id = None
            self.state.cartao_id = None
            self.state.subtipo = "Consumo Caixinha"
            self.state.status_pago = True
            self.dd_forma.value = "Caixinha"
            self._vincular_dados_da_caixinha(cid, atualizar_ui=False)
            self._sincronizar_estado_com_ui()
            self._safe_update(self)
        else:
            self._vincular_dados_da_caixinha(cid, atualizar_ui=True)
        self._notificar_mudanca()

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

    def _atualizar_opcoes_membro(self, atualizar_ui: bool = False):
        if not self.membros:
            try:
                self.membros = db.listar_membros() or []
            except Exception:
                self.membros = []

        opts = []
        for m in (self.membros or []):
            txt_lbl = f"👤 {m.get('nome', 'Membro')}" + (" (Principal)" if m.get("principal") else "")
            opts.append(ft.dropdown.Option(key=str(m["id"]), text=txt_lbl))

        self.dd_membro.options = opts
        if self.state.membro_id:
            self.dd_membro.value = str(self.state.membro_id)
        elif opts:
            prin = next((m for m in self.membros if m.get("principal")), self.membros[0])
            self.state.membro_id = str(prin["id"])
            self.dd_membro.value = self.state.membro_id

        self._construir_chips_membro()
        if atualizar_ui:
            self._safe_update(self.sec_membro)

    def _atualizar_resumo_parcelas(self, atualizar_ui: bool = True):
        if not self.state.eh_credito:
            return
        if self.state.is_fixa:
            self.lbl_resumo_parcelas.value = "Cobrança contínua todo mês na fatura do cartão."
            self.lbl_resumo_parcelas.color = T.PRIMARY
            if hasattr(self, "badge_edicao_parcela"):
                self.badge_edicao_parcela.visible = False
            if hasattr(self, "lbl_aviso_mudanca_parcelas"):
                self.lbl_aviso_mudanca_parcelas.visible = False
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

            if hasattr(self, "badge_edicao_parcela") and hasattr(self, "lbl_badge_parcela"):
                if self.state.is_compra_parcelada and self.state.parcela_atual:
                    tot_exib = self.state.total_parcelas_original or self.state.quantidade
                    self.lbl_badge_parcela.value = f"Editando Parcela {self.state.parcela_atual} de {tot_exib}x"
                    self.badge_edicao_parcela.visible = True
                else:
                    self.badge_edicao_parcela.visible = False

            if hasattr(self, "lbl_aviso_mudanca_parcelas"):
                if self.state.is_compra_parcelada and self.state.total_parcelas_original:
                    orig = self.state.total_parcelas_original
                    novo = self.state.quantidade
                    if novo < orig:
                        self.lbl_aviso_mudanca_parcelas.value = (
                            f"⚠️ Reduzir de {orig}x para {novo}x: as parcelas pendentes excedentes "
                            f"({orig - novo}) serão canceladas ao salvar."
                        )
                        self.lbl_aviso_mudanca_parcelas.color = T.WARNING
                        self.lbl_aviso_mudanca_parcelas.visible = True
                    elif novo > orig:
                        self.lbl_aviso_mudanca_parcelas.value = (
                            f"✨ Expandir de {orig}x para {novo}x: {novo - orig} novas parcelas "
                            f"serão geradas nos meses seguintes ao salvar."
                        )
                        self.lbl_aviso_mudanca_parcelas.color = T.PRIMARY
                        self.lbl_aviso_mudanca_parcelas.visible = True
                    else:
                        self.lbl_aviso_mudanca_parcelas.visible = False
                else:
                    self.lbl_aviso_mudanca_parcelas.visible = False

        if atualizar_ui:
            self._safe_update(self.lbl_resumo_parcelas)
            if hasattr(self, "badge_edicao_parcela"):
                self._safe_update(self.badge_edicao_parcela)
            if hasattr(self, "lbl_aviso_mudanca_parcelas"):
                self._safe_update(self.lbl_aviso_mudanca_parcelas)

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
        e.control.selected = [novo]

        self.state.mudar_tipo(novo)
        self.sugestoes_atuais = []
        if hasattr(self, "box_autocomplete"):
            self.box_autocomplete.visible = False
        if hasattr(self, "badge_autofill"):
            self.badge_autofill.visible = False
        self._construir_chips_atalhos_rapidos()
        self._atualizar_opcoes_forma(atualizar_ui=False)
        self._atualizar_opcoes_conta_ou_cartao(atualizar_ui=False)
        self._atualizar_opcoes_caixinhas(atualizar_ui=False)
        self._atualizar_opcoes_categoria(atualizar_ui=False)
        if self.state.categoria_id:
            self._carregar_subcategorias(self.state.categoria_id, atualizar_ui=False)
        else:
            self._carregar_subcategorias(None, atualizar_ui=False)
        self._sincronizar_estado_com_ui()
        self._safe_update(self.row_atalhos_rapidos)
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

        val_exibir = self.state.obter_valor_exibicao_input()
        self.txt_valor.value = formatar_moeda_input(val_exibir)

        if self.state.eh_credito:
            self._atualizar_resumo_parcelas()
        elif self.state.is_repetir:
            self._atualizar_resumo_repetir()
        self._notificar_mudanca()

    def _ao_sair_do_valor(self, e):
        val_exibir = self.state.obter_valor_exibicao_input()
        self.txt_valor.value = formatar_moeda_input(val_exibir)
        self._safe_update(self.txt_valor)

    def _ao_focar_valor(self, e):
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
        self._selecionar_forma_chip(nova_forma)

    def _ao_mudar_membro(self, e):
        val = e.data or e.control.value
        self._selecionar_membro_chip(str(val) if val else "")

    def _ao_mudar_conta(self, e):
        val = e.data or e.control.value
        if self.state.eh_credito:
            self.state.cartao_id = self._obter_cartao_id(val)
            self._atualizar_opcoes_fatura(atualizar_ui=True)
            if self.state.cartao_id and self.cartoes:
                k_sel = next((k for k in self.cartoes if str(k.get("id")) == str(self.state.cartao_id)), None)
                if k_sel and k_sel.get("membro_id"):
                    self.state.membro_id = str(k_sel["membro_id"])
                    self.dd_membro.value = self.state.membro_id
                    self._construir_chips_membro()
                    self._safe_update(self.sec_membro)
        else:
            self.state.conta_id = self._obter_conta_id(val)
            if self.state.conta_id and self.contas:
                c_sel = next((c for c in self.contas if str(c.get("id")) == str(self.state.conta_id)), None)
                if c_sel and c_sel.get("membro_id"):
                    self.state.membro_id = str(c_sel["membro_id"])
                    self.dd_membro.value = self.state.membro_id
                    self._construir_chips_membro()
                    self._safe_update(self.sec_membro)
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

        # Vínculo automático do Pote padrão baseado na Categoria escolhida (caso não travado manualmente)
        if self.state.eh_despesa and not self._pote_escolhido_manualmente:
            pote_sug = self._inferir_pote_por_categoria(nova_cat, self.state.subcategoria_id)
            if pote_sug:
                self._selecionar_pote_chip(pote_sug, manual=False)

        self._notificar_mudanca()

    def _ao_mudar_subcategoria(self, e):
        val = e.data or e.control.value
        self.state.subcategoria_id = self._obter_subcat_id(val)

        # Vínculo automático do Pote baseado na Subcategoria escolhida (caso não travado manualmente)
        if self.state.eh_despesa and not self._pote_escolhido_manualmente:
            pote_sug = self._inferir_pote_por_categoria(self.state.categoria_id, self.state.subcategoria_id)
            if pote_sug:
                self._selecionar_pote_chip(pote_sug, manual=False)

        self._notificar_mudanca()

    def _ao_mudar_regra(self, e):
        val = e.data or e.control.value
        self._selecionar_pote_chip(str(val) if val else "", manual=True)

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

    # =========================================================================
    # MODAIS INLINE (+): Conta/Cartão, Categoria e Subcategoria
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
            hint_text="Ex: Café, Gasolina, Notebook...",
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
                self.todas_subcategorias = db.listar_subcategorias(None) or []
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
