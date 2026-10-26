"""
=============================================================================
DemBase v3 — views/widgets/sobra_card.py  (Flet 1.0.1)
Módulo de Gestão de Sobra / Caixa Livre do Período.
Independente dos 6 Potes originais: calcula estritamente
    Sobra = Total de Receitas do Período - Total de Despesas do Período
e permite ratear dinamicamente o lucro/resíduo entre dois Mini-Potes:
  1. "Destinado para Investimento/Poupança"
  2. "Livre de Culpa (Para Torrar)"
=============================================================================
"""
from __future__ import annotations

from typing import Callable
import flet as ft

from core import theme as T
from core import storage
from core.theme import pad, borda
from core.constants import formatar_moeda


COR_INVESTIMENTO = "#10B981"  # Esmeralda — patrimônio / poupança
COR_LIVRE_CULPA  = "#8B5CF6"  # Violeta — livre para torrar sem culpa


def calcular_rateio_sobra(
    receitas: float,
    despesas: float,
    pct_investimento: float = 50.0,
) -> dict:
    """
    Calcula a Sobra do Período e a divisão dinâmica nos dois Mini-Potes.
    Regra estrita:
        Sobra = Total de Receitas do Período - Total de Despesas do Período
    Não interfere nos 6 Potes originais.
    """
    rec = round(float(receitas or 0.0), 2)
    desp = round(float(despesas or 0.0), 2)
    sobra = round(rec - desp, 2)

    pct_inv = round(max(0.0, min(100.0, float(pct_investimento if pct_investimento is not None else 50.0))), 1)
    pct_livre = round(100.0 - pct_inv, 1)

    if sobra > 0:
        val_inv = round(sobra * (pct_inv / 100.0), 2)
        val_livre = round(sobra - val_inv, 2)
        deficit = 0.0
    else:
        val_inv = 0.0
        val_livre = 0.0
        deficit = round(abs(sobra), 2) if sobra < 0 else 0.0

    return {
        "receitas": rec,
        "despesas": desp,
        "sobra": sobra,
        "tem_sobra": sobra > 0,
        "zerada": abs(sobra) < 0.005,
        "em_deficit": sobra < -0.005,
        "deficit": deficit,
        "pct_investimento": pct_inv,
        "pct_livre": pct_livre,
        "valor_investimento": val_inv,
        "valor_livre_culpa": val_livre,
    }


def _fmt_pct(pct: float) -> str:
    if abs(pct - round(pct)) < 0.05:
        return f"{int(round(pct))}%"
    return f"{pct:.1f}%".replace(".", ",")


class PainelGestaoSobra:
    """
    Controlador visual e reativo do módulo de Destinação da Sobra (Caixa Livre).
    Mantém referências mutáveis para atualizar valores instantaneamente quando:
      - O filtro global de datas do Dashboard muda (novas receitas/despesas)
      - O usuário move o Slider, digita uma porcentagem ou clica em um atalho
      - O usuário clica no card KPI "Caixa Livre" para expandir/recolher
    """

    def __init__(
        self,
        page: ft.Page,
        mobile: bool = False,
        on_atualizar_kpi_subtitulo: Callable[[dict, bool], None] | None = None,
        on_lancar_investimento: Callable[[float], None] | None = None,
    ):
        self.page = page
        self.mobile = mobile
        self.on_atualizar_kpi_subtitulo = on_atualizar_kpi_subtitulo
        self.on_lancar_investimento = on_lancar_investimento

        self.receitas: float = 0.0
        self.despesas: float = 0.0
        self.pct_investimento: float = storage.obter_percentual_sobra_investimento(page, 50.0)
        self.expandido: bool = storage.obter_painel_sobra_expandido(page, False)

        # ── Controles mutáveis do cabeçalho e equação ─────────────────────────
        self.txt_equacao = ft.Text(
            "",
            size=11.5 if mobile else 12.5,
            color=T.TEXT_MUTED,
            weight=ft.FontWeight.W_500,
        )
        self.txt_badge_status = ft.Text(
            "",
            size=11,
            weight=ft.FontWeight.BOLD,
            color=T.PRIMARY,
        )
        self.box_badge_status = ft.Container(
            padding=pad(h=10, v=4),
            border_radius=20,
            bgcolor=f"{T.PRIMARY}18",
            content=self.txt_badge_status,
        )

        # ── Controles de ajuste de percentual (Slider + Input + Chips) ────────
        self.txt_pct_destaque = ft.Text(
            _fmt_pct(self.pct_investimento),
            size=15 if mobile else 16,
            weight=ft.FontWeight.BOLD,
            color=COR_INVESTIMENTO,
        )
        self.tf_pct = ft.TextField(
            value=str(int(round(self.pct_investimento))),
            suffix=ft.Text("%", color=T.TEXT_MUTED, size=12),
            width=78 if mobile else 86,
            height=38,
            text_size=13,
            text_align=ft.TextAlign.RIGHT,
            keyboard_type=ft.KeyboardType.NUMBER,
            content_padding=pad(h=8, v=6),
            bgcolor=T.BG,
            border_color=T.BORDER,
            focused_border_color=COR_INVESTIMENTO,
            border_radius=8,
            on_submit=self._on_input_pct_submit,
            on_blur=self._on_input_pct_submit,
        )
        self.slider_pct = ft.Slider(
            min=0,
            max=100,
            divisions=20,
            value=self.pct_investimento,
            active_color=COR_INVESTIMENTO,
            inactive_color=f"{COR_LIVRE_CULPA}45",
            thumb_color=COR_INVESTIMENTO,
            label="{value}% para investir",
            on_change=self._on_slider_change,
        )

        self.row_chips_atalho = ft.Row(
            spacing=6,
            run_spacing=6,
            wrap=True,
            controls=self._construir_chips_atalho(),
        )

        # ── Barra de proporção combinada (Termômetro Investimento x Livre) ────
        self.barra_split_inv = ft.Container(
            expand=max(1, int(round(self.pct_investimento))),
            height=8,
            bgcolor=COR_INVESTIMENTO,
            border_radius=ft.BorderRadius.only(top_left=6, bottom_left=6),
        )
        self.barra_split_livre = ft.Container(
            expand=max(1, int(round(100 - self.pct_investimento))),
            height=8,
            bgcolor=COR_LIVRE_CULPA,
            border_radius=ft.BorderRadius.only(top_right=6, bottom_right=6),
        )
        self.row_termometro_duplo = ft.Row(
            spacing=2,
            controls=[self.barra_split_inv, self.barra_split_livre],
        )

        # ── Mini-Pote 1: Destinado para Investimento / Poupança ───────────────
        self.txt_inv_valor = ft.Text(
            "R$ 0,00",
            size=18 if mobile else 22,
            weight=ft.FontWeight.BOLD,
            color=COR_INVESTIMENTO,
        )
        self.txt_inv_pct = ft.Text(
            _fmt_pct(self.pct_investimento),
            size=11.5,
            weight=ft.FontWeight.BOLD,
            color=COR_INVESTIMENTO,
        )
        self.pb_inv = ft.ProgressBar(
            value=self.pct_investimento / 100.0,
            color=COR_INVESTIMENTO,
            bgcolor=f"{COR_INVESTIMENTO}22",
            height=8,
            border_radius=6,
        )
        self.txt_inv_dica = ft.Text(
            "Separado da sobra do período para multiplicar seu patrimônio.",
            size=11,
            color=T.TEXT_MUTED,
        )
        self.btn_guardar_inv = ft.Container(
            padding=pad(h=12, v=7),
            border_radius=8,
            bgcolor=f"{COR_INVESTIMENTO}1F",
            border=borda(1, f"{COR_INVESTIMENTO}55"),
            ink=True,
            on_click=self._acao_lancar_investimento,
            tooltip="Registrar transferência ou aporte deste valor",
            content=ft.Row(
                spacing=6,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=COR_INVESTIMENTO, size=15),
                    ft.Text(
                        "Separar / Investir",
                        color=COR_INVESTIMENTO,
                        size=11.5,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
        )

        # ── Mini-Pote 2: Livre de Culpa (Para Torrar) ─────────────────────────
        self.txt_livre_valor = ft.Text(
            "R$ 0,00",
            size=18 if mobile else 22,
            weight=ft.FontWeight.BOLD,
            color=COR_LIVRE_CULPA,
        )
        self.txt_livre_pct = ft.Text(
            _fmt_pct(100.0 - self.pct_investimento),
            size=11.5,
            weight=ft.FontWeight.BOLD,
            color=COR_LIVRE_CULPA,
        )
        self.pb_livre = ft.ProgressBar(
            value=(100.0 - self.pct_investimento) / 100.0,
            color=COR_LIVRE_CULPA,
            bgcolor=f"{COR_LIVRE_CULPA}22",
            height=8,
            border_radius=6,
        )
        self.txt_livre_dica = ft.Text(
            "Disponível no Caixa Livre para gastar sem culpa e sem afetar os 6 Potes.",
            size=11,
            color=T.TEXT_MUTED,
        )
        self.badge_livre_status = ft.Container(
            padding=pad(h=10, v=6),
            border_radius=8,
            bgcolor=f"{COR_LIVRE_CULPA}18",
            border=borda(1, f"{COR_LIVRE_CULPA}40"),
            content=ft.Row(
                spacing=5,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.VERIFIED_ROUNDED, color=COR_LIVRE_CULPA, size=14),
                    ft.Text(
                        "100% Livre no Caixa",
                        color=COR_LIVRE_CULPA,
                        size=11,
                        weight=ft.FontWeight.W_600,
                    ),
                ],
            ),
        )

        # ── Banner de aviso quando não há sobra (zerada ou déficit) ───────────
        self.txt_aviso_sem_sobra = ft.Text(
            "",
            size=12,
            color=T.WARNING,
            weight=ft.FontWeight.W_500,
        )
        self.banner_sem_sobra = ft.Container(
            visible=False,
            padding=pad(h=12, v=10),
            border_radius=10,
            bgcolor=f"{T.WARNING}14",
            border=borda(1, f"{T.WARNING}40"),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE_ROUNDED, color=T.WARNING, size=16),
                    ft.Container(expand=True, content=self.txt_aviso_sem_sobra),
                ],
            ),
        )

        self.container = self._construir_container()
        self._sincronizar_ui(notificar_kpi=False)

    def _construir_chips_atalho(self) -> list[ft.Control]:
        opcoes = [
            (0.0, "0%"),
            (20.0, "20%"),
            (30.0, "30%"),
            (50.0, "50% (Meio a Meio)"),
            (70.0, "70%"),
            (100.0, "100% (Tudo)"),
        ]
        chips: list[ft.Control] = []
        for val, rotulo in opcoes:
            ativo = abs(self.pct_investimento - val) < 0.5
            chips.append(
                ft.Container(
                    padding=pad(h=10, v=5),
                    border_radius=16,
                    bgcolor=COR_INVESTIMENTO if ativo else T.BG,
                    border=borda(1, COR_INVESTIMENTO if ativo else T.BORDER),
                    ink=True,
                    on_click=lambda _, v=val: self.definir_percentual(v),
                    content=ft.Text(
                        rotulo,
                        size=11,
                        weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                        color="#FFFFFF" if ativo else T.TEXT_MUTED,
                    ),
                )
            )
        return chips

    def _construir_mini_pote_card(
        self,
        titulo: str,
        subtitulo_tag: str,
        icone: ft.IconData,
        cor: str,
        txt_valor: ft.Text,
        txt_pct: ft.Text,
        pb: ft.ProgressBar,
        txt_dica: ft.Text,
        acao_rodape: ft.Control,
    ) -> ft.Container:
        return ft.Container(
            col={"xs": 12, "sm": 6},
            padding=pad(all_=14 if self.mobile else 16),
            bgcolor=T.BG,
            border_radius=12,
            border=borda(1, f"{cor}38"),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        padding=pad(all_=7),
                                        border_radius=9,
                                        bgcolor=f"{cor}1F",
                                        content=ft.Icon(icone, color=cor, size=18),
                                    ),
                                    ft.Column(
                                        spacing=1,
                                        expand=True,
                                        controls=[
                                            ft.Text(
                                                titulo,
                                                size=13 if self.mobile else 14,
                                                weight=ft.FontWeight.BOLD,
                                                color=T.TEXT_PRIMARY,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                            ft.Text(
                                                subtitulo_tag,
                                                size=10.5,
                                                color=T.TEXT_MUTED,
                                                max_lines=1,
                                                overflow=ft.TextOverflow.ELLIPSIS,
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            ft.Container(
                                padding=pad(h=8, v=3),
                                border_radius=12,
                                bgcolor=f"{cor}18",
                                content=txt_pct,
                            ),
                        ],
                    ),
                    txt_valor,
                    pb,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Container(expand=True, content=txt_dica),
                            acao_rodape,
                        ],
                    ),
                ],
            ),
        )

    def _construir_container(self) -> ft.Container:
        card_investimento = self._construir_mini_pote_card(
            titulo="Destinado para Investimento/Poupança",
            subtitulo_tag="Mini-Pote 1 · Guardar e Multiplicar",
            icone=ft.Icons.SAVINGS_ROUNDED,
            cor=COR_INVESTIMENTO,
            txt_valor=self.txt_inv_valor,
            txt_pct=self.txt_inv_pct,
            pb=self.pb_inv,
            txt_dica=self.txt_inv_dica,
            acao_rodape=self.btn_guardar_inv,
        )

        card_livre_culpa = self._construir_mini_pote_card(
            titulo="Livre de Culpa (Para Torrar)",
            subtitulo_tag="Mini-Pote 2 · Permanece no Caixa Livre",
            icone=ft.Icons.CELEBRATION_ROUNDED,
            cor=COR_LIVRE_CULPA,
            txt_valor=self.txt_livre_valor,
            txt_pct=self.txt_livre_pct,
            pb=self.pb_livre,
            txt_dica=self.txt_livre_dica,
            acao_rodape=self.badge_livre_status,
        )

        bloco_controle_slider = ft.Container(
            padding=pad(h=14, v=12),
            bgcolor=T.BG,
            border_radius=12,
            border=borda(),
            content=ft.Column(
                spacing=8,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=6,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.TUNE_ROUNDED, color=COR_INVESTIMENTO, size=16),
                                    ft.Text(
                                        "Quanto da sobra você quer guardar/investir?",
                                        size=12.5 if self.mobile else 13,
                                        weight=ft.FontWeight.W_600,
                                        color=T.TEXT_PRIMARY,
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=6,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    self.tf_pct,
                                ],
                            ),
                        ],
                    ),
                    self.slider_pct,
                    self.row_termometro_duplo,
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Text(
                                "Atalhos rápidos:",
                                size=11,
                                color=T.TEXT_MUTED,
                            ),
                            ft.Container(expand=True, content=self.row_chips_atalho),
                        ],
                    ),
                ],
            ),
        )

        return ft.Container(
            visible=self.expandido,
            padding=pad(all_=14 if self.mobile else 18),
            bgcolor=T.SURFACE,
            border_radius=14,
            border=borda(1.5, f"{T.PRIMARY}55"),
            animate=ft.Animation(180, ft.AnimationCurve.DECELERATE),
            content=ft.Column(
                spacing=12,
                controls=[
                    # Cabeçalho do Módulo de Destinação da Sobra
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Row(
                                spacing=8,
                                expand=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Container(
                                        padding=pad(all_=7),
                                        border_radius=9,
                                        bgcolor=f"{T.PRIMARY}1F",
                                        content=ft.Icon(
                                            ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                                            color=T.PRIMARY,
                                            size=18,
                                        ),
                                    ),
                                    ft.Column(
                                        spacing=2,
                                        expand=True,
                                        controls=[
                                            ft.Row(
                                                spacing=8,
                                                wrap=True,
                                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                controls=[
                                                    ft.Text(
                                                        "Destinação do Caixa Livre (Sobra do Período)",
                                                        size=14 if self.mobile else 15.5,
                                                        weight=ft.FontWeight.BOLD,
                                                        color=T.TEXT_PRIMARY,
                                                    ),
                                                    self.box_badge_status,
                                                ],
                                            ),
                                            self.txt_equacao,
                                        ],
                                    ),
                                ],
                            ),
                            ft.IconButton(
                                icon=ft.Icons.KEYBOARD_ARROW_UP_ROUNDED,
                                icon_color=T.TEXT_MUTED,
                                tooltip="Recolher painel de Destinação da Sobra",
                                on_click=lambda _: self.alternar_expansao(),
                            ),
                        ],
                    ),
                    self.banner_sem_sobra,
                    bloco_controle_slider,
                    ft.ResponsiveRow(
                        spacing=12,
                        run_spacing=12,
                        controls=[card_investimento, card_livre_culpa],
                    ),
                ],
            ),
        )

    def _on_slider_change(self, e: ft.ControlEvent):
        try:
            novo_pct = round(float(e.control.value or 0.0), 0)
        except Exception:
            novo_pct = 50.0
        self.definir_percentual(novo_pct, atualizar_slider=False)

    def _on_input_pct_submit(self, e: ft.ControlEvent):
        texto = str(self.tf_pct.value or "").strip().replace(",", ".").replace("%", "")
        try:
            novo_pct = float(texto)
        except Exception:
            novo_pct = self.pct_investimento
        self.definir_percentual(novo_pct, atualizar_slider=True)

    def definir_percentual(self, novo_pct: float, atualizar_slider: bool = True):
        pct_limpo = round(max(0.0, min(100.0, float(novo_pct))), 1)
        self.pct_investimento = pct_limpo
        storage.salvar_percentual_sobra_investimento_sync(self.page, pct_limpo)
        if atualizar_slider:
            self.slider_pct.value = pct_limpo
        self.tf_pct.value = str(int(round(pct_limpo)))
        self.row_chips_atalho.controls = self._construir_chips_atalho()
        self._sincronizar_ui(notificar_kpi=True)
        try:
            self.page.update()
        except Exception:
            pass

    def atualizar_periodo(self, receitas: float, despesas: float):
        """Atualiza receitas e despesas do período selecionado e recalcula a Sobra e os Mini-Potes."""
        self.receitas = float(receitas or 0.0)
        self.despesas = float(despesas or 0.0)
        self._sincronizar_ui(notificar_kpi=True)

    def alternar_expansao(self, forcar: bool | None = None):
        """Expande ou recolhe a seção inline de Destinação da Sobra."""
        if forcar is None:
            self.expandido = not self.expandido
        else:
            self.expandido = bool(forcar)
        self.container.visible = self.expandido
        storage.salvar_painel_sobra_expandido_sync(self.page, self.expandido)
        dados = self.obter_dados_atuais()
        if self.on_atualizar_kpi_subtitulo:
            self.on_atualizar_kpi_subtitulo(dados, self.expandido)
        try:
            self.page.update()
        except Exception:
            pass

    def obter_dados_atuais(self) -> dict:
        return calcular_rateio_sobra(self.receitas, self.despesas, self.pct_investimento)

    def _acao_lancar_investimento(self, _e=None):
        dados = self.obter_dados_atuais()
        val_inv = float(dados.get("valor_investimento", 0.0) or 0.0)
        if self.on_lancar_investimento:
            self.on_lancar_investimento(val_inv)

    def _sincronizar_ui(self, notificar_kpi: bool = True):
        dados = self.obter_dados_atuais()
        rec = dados["receitas"]
        desp = dados["despesas"]
        sobra = dados["sobra"]
        pct_inv = dados["pct_investimento"]
        pct_livre = dados["pct_livre"]
        val_inv = dados["valor_investimento"]
        val_livre = dados["valor_livre_culpa"]

        self.txt_equacao.value = (
            f"Receitas ({formatar_moeda(rec)}) − Despesas ({formatar_moeda(desp)}) "
            f"= {formatar_moeda(sobra)}"
        )

        if dados["tem_sobra"]:
            self.txt_badge_status.value = f"Sobra Positiva: {formatar_moeda(sobra)}"
            self.txt_badge_status.color = COR_INVESTIMENTO
            self.box_badge_status.bgcolor = f"{COR_INVESTIMENTO}18"
            self.banner_sem_sobra.visible = False
        elif dados["em_deficit"]:
            self.txt_badge_status.value = f"Déficit no Período: {formatar_moeda(sobra)}"
            self.txt_badge_status.color = T.DESPESA
            self.box_badge_status.bgcolor = f"{T.DESPESA}18"
            self.txt_aviso_sem_sobra.value = (
                f"Neste período as despesas superaram as receitas em {formatar_moeda(dados['deficit'])}. "
                "Os Mini-Potes ficam zerados até que haja saldo residual positivo."
            )
            self.banner_sem_sobra.visible = True
        else:
            self.txt_badge_status.value = "Período Equilibrado (R$ 0,00)"
            self.txt_badge_status.color = T.TEXT_MUTED
            self.box_badge_status.bgcolor = f"{T.TEXT_MUTED}18"
            self.txt_aviso_sem_sobra.value = (
                "Não há sobra residual neste período (Receitas = Despesas). "
                "Defina já o percentual desejado para quando entrar nova receita."
            )
            self.banner_sem_sobra.visible = True

        self.txt_pct_destaque.value = _fmt_pct(pct_inv)
        self.txt_inv_pct.value = _fmt_pct(pct_inv)
        self.txt_livre_pct.value = _fmt_pct(pct_livre)

        self.txt_inv_valor.value = formatar_moeda(val_inv)
        self.txt_livre_valor.value = formatar_moeda(val_livre)

        self.pb_inv.value = max(0.0, min(1.0, pct_inv / 100.0))
        self.pb_livre.value = max(0.0, min(1.0, pct_livre / 100.0))

        # Atualiza termômetro duplo proporcional
        if pct_inv <= 0:
            self.barra_split_inv.visible = False
            self.barra_split_livre.visible = True
            self.barra_split_livre.expand = 100
        elif pct_inv >= 100:
            self.barra_split_inv.visible = True
            self.barra_split_inv.expand = 100
            self.barra_split_livre.visible = False
        else:
            self.barra_split_inv.visible = True
            self.barra_split_livre.visible = True
            self.barra_split_inv.expand = max(1, int(round(pct_inv)))
            self.barra_split_livre.expand = max(1, int(round(pct_livre)))

        if notificar_kpi and self.on_atualizar_kpi_subtitulo:
            self.on_atualizar_kpi_subtitulo(dados, self.expandido)
