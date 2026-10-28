"""
=============================================================================
DemBase v3 — views/widgets/sobra_card.py  (Flet 1.0.1)
Módulo de Gestão de Sobra / Caixa Livre do Período + Blindagem contra Sobra Falsa.
Integrado de forma unificada aos 6 Potes Financeiros:
  - Elimina o furo lógico onde o dinheiro reservado do mês (Semi Fixos / Gás, Metas, Conhecimento)
    era inflado no Caixa Livre.
  - Conecta diretamente o Card de Investimento ao Pote "Liberdade Financeira" (pos 6)
    e o Card Livre de Culpa ao Pote "Prazeres" (pos 4).
  - Mostra Teto do Mês vs Já Gasto/Investido e Restante Disponível Hoje.
  - Trava do Pior Dia (Teto Seguro) para impedir saldo negativo intermediário.
  - Sincronização em tempo real com a grade dos 6 Potes via Slider.
=============================================================================
"""
from __future__ import annotations

from typing import Callable, Any
import flet as ft

from core import theme as T
from core import storage
from core.theme import pad, borda
from core.constants import formatar_moeda, formatar_data_br, MESES_NOMES
from core.potes import calcular_arquitetura_unificada_potes, POTES_PADRAO
import services.supabase_client as db


COR_INVESTIMENTO = "#10B981"  # Esmeralda — Liberdade Financeira
COR_LIVRE_CULPA  = "#8B5CF6"  # Violeta — Prazeres / Livre sem culpa
COR_BLINDAGEM    = "#06B6D4"  # Ciano — proteção de fluxo de caixa / teto seguro
COR_GARGALO      = "#F59E0B"  # Âmbar — alerta de gargalo / sobra falsa


def calcular_rateio_sobra(
    receitas: float,
    despesas: float,
    pct_investimento: float = 50.0,
    protecao_fluxo: dict | None = None,
    travar_pelo_teto_seguro: bool = True,
    potes: list[dict] | None = None,
    piso_custos_fixos: float = 1150.0,
) -> dict:
    """
    Calcula a Sobra Projetada do Período, a divisão nos dois Mini-Potes e a
    Blindagem contra Sobra Falsa (Teto Seguro baseado no Pior Dia).
    Quando `potes` é informado, utiliza a Arquitetura Unificada eliminando
    a inclusão indevida dos saldos reservados de Semi Fixos, Metas e Conhecimento.
    """
    rec = round(float(receitas or 0.0), 2)
    desp = round(float(despesas or 0.0), 2)
    pct_inv = round(max(0.0, min(100.0, float(pct_investimento if pct_investimento is not None else 50.0))), 1)
    pct_livre = round(100.0 - pct_inv, 1)

    # Se há lista de potes estruturada, usa o motor da arquitetura unificada
    if potes and isinstance(potes, list) and len(potes) >= 1:
        resultado_unif = calcular_arquitetura_unificada_potes(
            receitas=rec,
            potes=potes,
            piso_custos_fixos=piso_custos_fixos,
            slider_pct_investimento=pct_inv,
            protecao_fluxo=protecao_fluxo,
            travar_pelo_teto_seguro=travar_pelo_teto_seguro,
        )
        cl = resultado_unif["caixa_livre"]
        b = resultado_unif["blindagem"]
        sobra_livre = cl["sobra_livre_disponivel"]
        sobra_proj = cl["sobra_livre_projetada"]

        return {
            "receitas": rec,
            "despesas": desp,
            "sobra": sobra_livre,
            "sobra_projetada": sobra_proj,
            "teto_caixa_livre": cl["teto_orcamento"],
            "pct_caixa_livre": cl["pct_orcamento"],
            "tem_sobra": sobra_livre > 0.005,
            "zerada": abs(sobra_livre) < 0.005,
            "em_deficit": (rec - desp) < -0.005,
            "deficit": round(abs(rec - desp), 2) if (rec - desp) < -0.005 else 0.0,
            "pct_investimento": pct_inv,
            "pct_livre": pct_livre,
            "valor_investimento": cl["liberdade_disponivel_hoje"],
            "valor_livre_culpa": cl["prazeres_disponivel_hoje"],
            "valor_investimento_projetado": cl["liberdade_restante_projetado"],
            "valor_livre_projetado": cl["prazeres_restante_projetado"],
            "teto_investimento": cl["liberdade_teto"],
            "teto_livre_culpa": cl["prazeres_teto"],
            "gasto_investimento": cl["liberdade_gasto"],
            "gasto_livre_culpa": cl["prazeres_gasto"],
            "nome_investimento": cl.get("liberdade_nome", "Liberdade Financeira"),
            "nome_livre_culpa": cl.get("prazeres_nome", "Prazeres"),
            "retido_outros_potes": resultado_unif["retido_outros_potes"],
            "menor_saldo_futuro": b["menor_saldo_futuro"],
            "teto_seguro_gasto": b["teto_seguro_gasto"],
            "sobra_falsa_travada": b["sobra_falsa_travada"],
            "tem_armadilha_fluxo": b["tem_armadilha_fluxo"],
            "fica_negativo_no_meio": b["fica_negativo_no_meio"],
            "data_gargalo": b["data_gargalo"],
            "proxima_entrada_data": b["proxima_entrada_data"],
            "proxima_entrada_valor": b["proxima_entrada_valor"],
            "travar_pelo_teto_seguro": bool(travar_pelo_teto_seguro),
            "potes_atualizados": resultado_unif["potes"],
            "soma_percentuais": resultado_unif["soma_percentuais"],
            "arquitetura_unificada": True,
        }

    # Fallback de compatibilidade (cálculo simples sobre rec - desp)
    sobra = round(rec - desp, 2)
    if sobra > 0:
        val_inv_proj = round(sobra * (pct_inv / 100.0), 2)
        val_livre_proj = round(sobra - val_inv_proj, 2)
        deficit = 0.0
    else:
        val_inv_proj = 0.0
        val_livre_proj = 0.0
        deficit = round(abs(sobra), 2) if sobra < 0 else 0.0

    pf = protecao_fluxo if isinstance(protecao_fluxo, dict) else {}
    tem_dados_pf = bool(pf and ("teto_seguro_gasto" in pf or "menor_saldo_futuro" in pf))
    if tem_dados_pf:
        menor_saldo_futuro = round(float(pf.get("menor_saldo_futuro", sobra) or 0.0), 2)
        teto_seguro = round(max(0.0, min(max(0.0, sobra), float(pf.get("teto_seguro_gasto", max(0.0, sobra)) or 0.0))), 2)
        sobra_falsa = round(max(0.0, max(0.0, sobra) - teto_seguro), 2)
        tem_armadilha = bool(sobra_falsa > 0.005 or menor_saldo_futuro < -0.005)
        fica_negativo_meio = bool(menor_saldo_futuro < -0.005)
        data_gargalo = pf.get("data_gargalo")
        prox_entrada_dt = pf.get("proxima_entrada_data")
        prox_entrada_val = round(float(pf.get("proxima_entrada_valor", 0.0) or 0.0), 2)
    else:
        menor_saldo_futuro = sobra
        teto_seguro = max(0.0, sobra)
        sobra_falsa = 0.0
        tem_armadilha = False
        fica_negativo_meio = sobra < -0.005
        data_gargalo = None
        prox_entrada_dt = None
        prox_entrada_val = 0.0

    if sobra > 0:
        if travar_pelo_teto_seguro and tem_dados_pf:
            base_segura = teto_seguro
            val_inv_seguro = round(base_segura * (pct_inv / 100.0), 2)
            val_livre_seguro = round(base_segura - val_inv_seguro, 2)
            val_livre_teto_absoluto = round(min(val_livre_proj, teto_seguro), 2)
        else:
            val_inv_seguro = val_inv_proj
            val_livre_seguro = val_livre_proj
            val_livre_teto_absoluto = val_livre_proj
    else:
        val_inv_seguro = 0.0
        val_livre_seguro = 0.0
        val_livre_teto_absoluto = 0.0

    val_inv_efetivo = val_inv_seguro if (travar_pelo_teto_seguro and tem_armadilha) else val_inv_proj
    val_livre_efetivo = val_livre_seguro if (travar_pelo_teto_seguro and tem_armadilha) else val_livre_proj

    return {
        "receitas": rec,
        "despesas": desp,
        "sobra": sobra,
        "sobra_projetada": sobra,
        "teto_caixa_livre": sobra,
        "pct_caixa_livre": round((sobra / rec * 100.0), 2) if rec > 0 else 0.0,
        "tem_sobra": sobra > 0,
        "zerada": abs(sobra) < 0.005,
        "em_deficit": sobra < -0.005,
        "deficit": deficit,
        "pct_investimento": pct_inv,
        "pct_livre": pct_livre,
        "valor_investimento": val_inv_efetivo,
        "valor_livre_culpa": val_livre_efetivo,
        "valor_investimento_projetado": val_inv_proj,
        "valor_livre_projetado": val_livre_proj,
        "valor_investimento_seguro": val_inv_seguro,
        "valor_livre_seguro": val_livre_seguro,
        "valor_livre_teto_absoluto": val_livre_teto_absoluto,
        "teto_investimento": val_inv_proj,
        "teto_livre_culpa": val_livre_proj,
        "gasto_investimento": 0.0,
        "gasto_livre_culpa": 0.0,
        "nome_investimento": "Liberdade Financeira",
        "nome_livre_culpa": "Prazeres",
        "retido_outros_potes": 0.0,
        "menor_saldo_futuro": menor_saldo_futuro,
        "teto_seguro_gasto": teto_seguro,
        "sobra_falsa_travada": sobra_falsa,
        "tem_armadilha_fluxo": tem_armadilha,
        "fica_negativo_no_meio": fica_negativo_meio,
        "data_gargalo": data_gargalo,
        "proxima_entrada_data": prox_entrada_dt,
        "proxima_entrada_valor": prox_entrada_val,
        "travar_pelo_teto_seguro": bool(travar_pelo_teto_seguro),
        "arquitetura_unificada": False,
    }


def _fmt_pct(pct: float) -> str:
    if abs(pct - round(pct)) < 0.05:
        return f"{int(round(pct))}%"
    return f"{pct:.1f}%".replace(".", ",")


class PainelGestaoSobra:
    """
    Controlador visual e reativo do módulo de Destinação do Caixa Livre.
    Conectado diretamente aos Potes 'Liberdade Financeira' (investimento/poupança)
    e 'Prazeres' (livre para gastar sem culpa).
    """

    def __init__(
        self,
        page: ft.Page,
        mobile: bool = False,
        on_atualizar_kpi_subtitulo: Callable[[dict, bool], None] | None = None,
        on_lancar_investimento: Callable[[float], None] | None = None,
        on_potes_alterados: Callable[[list[dict]], None] | None = None,
    ):
        self.page = page
        self.mobile = mobile
        self.on_atualizar_kpi_subtitulo = on_atualizar_kpi_subtitulo
        self.on_lancar_investimento = on_lancar_investimento
        self.on_potes_alterados = on_potes_alterados

        self.receitas: float = 0.0
        self.despesas: float = 0.0
        self.mes_atual: int | None = None
        self.ano_atual: int | None = None
        self.herdado_mes: bool = False
        self.protecao_fluxo: dict = {}
        self.potes_dados: list[dict] = []
        self.piso_custos_fixos: float = storage.obter_piso_custos_fixos(page, 1150.0)

        self.pct_investimento: float = storage.obter_percentual_sobra_investimento(page, 50.0)
        self.travar_teto_seguro: bool = storage.obter_trava_teto_seguro_sobra(page, True)
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
        self.txt_badge_mes = ft.Text(
            "",
            size=10.5,
            weight=ft.FontWeight.W_600,
            color=COR_INVESTIMENTO,
        )
        self.box_badge_mes = ft.Container(
            visible=False,
            padding=pad(h=9, v=3),
            border_radius=16,
            bgcolor=f"{COR_INVESTIMENTO}16",
            border=borda(1, f"{COR_INVESTIMENTO}45"),
            content=self.txt_badge_mes,
        )

        # ── Painel de Blindagem de Fluxo de Caixa (Contra a "Sobra Falsa") ────
        self.txt_sobra_proj_card = ft.Text(
            "R$ 0,00",
            size=15 if mobile else 17,
            weight=ft.FontWeight.BOLD,
            color=T.TEXT_PRIMARY,
        )
        self.txt_sobra_proj_sub = ft.Text(
            "Se nada mudar até o fim do período",
            size=10.5,
            color=T.TEXT_MUTED,
        )

        self.txt_teto_seguro_card = ft.Text(
            "R$ 0,00",
            size=16 if mobile else 18,
            weight=ft.FontWeight.BOLD,
            color=COR_BLINDAGEM,
        )
        self.txt_teto_seguro_sub = ft.Text(
            "Menor saldo acumulado (Pior Dia)",
            size=10.5,
            color=T.TEXT_MUTED,
        )

        self.txt_sobra_falsa_card = ft.Text(
            "R$ 0,00",
            size=15 if mobile else 17,
            weight=ft.FontWeight.BOLD,
            color=COR_GARGALO,
        )
        self.txt_sobra_falsa_sub = ft.Text(
            "Receita que só entra após o gargalo",
            size=10.5,
            color=T.TEXT_MUTED,
        )

        self.txt_alerta_gargalo = ft.Text(
            "",
            size=11.5,
            color=T.TEXT_PRIMARY,
            weight=ft.FontWeight.W_500,
        )
        self.icone_alerta_gargalo = ft.Icon(
            ft.Icons.SHIELD_ROUNDED,
            color=COR_BLINDAGEM,
            size=18,
        )
        self.sw_trava_teto = ft.Switch(
            value=self.travar_teto_seguro,
            active_color=COR_BLINDAGEM,
            scale=0.82,
            tooltip="Quando ativo, limita o Caixa Livre e os Potes ao Teto Seguro do Pior Dia para impedir saldo negativo no meio do mês.",
            on_change=self._on_toggle_trava_teto,
        )
        self.box_trava_fluxo = self._construir_box_blindagem_fluxo()

        # ── Controles de ajuste de percentual (Slider + Input + Chips) ────────
        self.txt_titulo_slider = ft.Text(
            "Divisão do Caixa Livre: Liberdade Financeira x Prazeres",
            size=12.5 if self.mobile else 13,
            weight=ft.FontWeight.W_600,
            color=T.TEXT_PRIMARY,
        )
        self.txt_pct_destaque = ft.Text(
            _fmt_pct(self.pct_investimento),
            size=15 if mobile else 16,
            weight=ft.FontWeight.BOLD,
            color=COR_INVESTIMENTO,
        )
        self.tf_pct = ft.TextField(
            value=str(int(round(self.pct_investimento))),
            suffix=ft.Text("% Guardar", color=T.TEXT_MUTED, size=11.5),
            width=96 if mobile else 108,
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
            label="{value}% Liberdade Financeira",
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

        # ── Card 1: Liberdade Financeira (Mini-Pote 1 / Pote 6) ───────────────
        self.txt_inv_titulo = ft.Text(
            "Liberdade Financeira",
            size=13 if self.mobile else 14,
            weight=ft.FontWeight.BOLD,
            color=T.TEXT_PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.txt_inv_teto_info = ft.Text(
            "Teto: R$ 0,00 · Já investido: R$ 0,00",
            size=10.5,
            color=T.TEXT_MUTED,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
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
            "Disponível para aportar no mês · Conectado ao Pote 6",
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
            tooltip="Registrar aporte para Liberdade Financeira",
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

        # ── Card 2: Prazeres (Mini-Pote 2 / Pote 4 / Livre sem culpa) ─────────
        self.txt_livre_titulo = ft.Text(
            "Prazeres",
            size=13 if self.mobile else 14,
            weight=ft.FontWeight.BOLD,
            color=T.TEXT_PRIMARY,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
        self.txt_livre_teto_info = ft.Text(
            "Teto: R$ 0,00 · Já gasto: R$ 0,00",
            size=10.5,
            color=T.TEXT_MUTED,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
        )
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
            "Disponível para gastar livre sem culpa · Conectado ao Pote 4",
            size=11,
            color=T.TEXT_MUTED,
        )
        self.txt_badge_livre_status = ft.Text(
            "Livre sem Culpa",
            color=COR_LIVRE_CULPA,
            size=11,
            weight=ft.FontWeight.W_600,
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
                    self.txt_badge_livre_status,
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

    def _construir_box_blindagem_fluxo(self) -> ft.Container:
        def _mini_metrica(
            rotulo: str,
            icone: ft.IconData,
            cor: str,
            txt_val: ft.Text,
            txt_sub: ft.Text,
        ) -> ft.Container:
            return ft.Container(
                col={"xs": 12, "sm": 4},
                padding=pad(h=12, v=10),
                bgcolor=T.SURFACE,
                border_radius=10,
                border=borda(1, f"{cor}40"),
                content=ft.Column(
                    spacing=3,
                    controls=[
                        ft.Row(
                            spacing=6,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(icone, color=cor, size=14),
                                ft.Text(
                                    rotulo,
                                    size=10,
                                    weight=ft.FontWeight.BOLD,
                                    color=cor,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                    expand=True,
                                ),
                            ],
                        ),
                        txt_val,
                        txt_sub,
                    ],
                ),
            )

        return ft.Container(
            padding=pad(h=14, v=12),
            bgcolor=T.BG,
            border_radius=12,
            border=borda(1.2, f"{COR_BLINDAGEM}45"),
            content=ft.Column(
                spacing=10,
                controls=[
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                        controls=[
                            ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    self.icone_alerta_gargalo,
                                    ft.Text(
                                        "Blindagem de Fluxo de Caixa (Contra Sobra Falsa)",
                                        size=12.5 if self.mobile else 13,
                                        weight=ft.FontWeight.BOLD,
                                        color=T.TEXT_PRIMARY,
                                    ),
                                ],
                            ),
                            ft.Row(
                                spacing=4,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Icon(ft.Icons.LOCK_ROUNDED, size=13, color=COR_BLINDAGEM),
                                    ft.Text(
                                        "Travar pelo Pior Dia (Teto Seguro)",
                                        size=11,
                                        weight=ft.FontWeight.W_600,
                                        color=T.TEXT_PRIMARY,
                                    ),
                                    self.sw_trava_teto,
                                ],
                            ),
                        ],
                    ),
                    ft.ResponsiveRow(
                        spacing=10,
                        run_spacing=8,
                        controls=[
                            _mini_metrica(
                                "ORÇAMENTO CAIXA LIVRE (MÊS)",
                                ft.Icons.CALENDAR_MONTH_ROUNDED,
                                T.PRIMARY,
                                self.txt_sobra_proj_card,
                                self.txt_sobra_proj_sub,
                            ),
                            _mini_metrica(
                                "DISPONÍVEL AGORA S/ NEGATIVAR",
                                ft.Icons.VERIFIED_USER_ROUNDED,
                                COR_BLINDAGEM,
                                self.txt_teto_seguro_card,
                                self.txt_teto_seguro_sub,
                            ),
                            _mini_metrica(
                                "RETIDO / AGUARDANDO ENTRADA FUTURA",
                                ft.Icons.HOURGLASS_TOP_ROUNDED,
                                COR_GARGALO,
                                self.txt_sobra_falsa_card,
                                self.txt_sobra_falsa_sub,
                            ),
                        ],
                    ),
                    ft.Container(
                        padding=pad(h=10, v=7),
                        border_radius=8,
                        bgcolor=f"{COR_BLINDAGEM}12",
                        content=ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.TIPS_AND_UPDATES_ROUNDED, size=15, color=COR_BLINDAGEM),
                                ft.Container(expand=True, content=self.txt_alerta_gargalo),
                            ],
                        ),
                    ),
                ],
            ),
        )

    def _construir_chips_atalho(self) -> list[ft.Control]:
        opcoes = [
            (0.0, "0% Guardar"),
            (30.0, "30%"),
            (50.0, "50% (Meio a Meio)"),
            (70.0, "70%"),
            (80.0, "80%"),
            (100.0, "100% (Tudo p/ Guardar)"),
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
        txt_titulo: ft.Text,
        subtitulo_tag: str,
        icone: ft.IconData,
        cor: str,
        txt_teto_info: ft.Text,
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
                                            txt_titulo,
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
                    txt_teto_info,
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
            txt_titulo=self.txt_inv_titulo,
            subtitulo_tag="Mini-Pote 1 · Investimento (Pote 6)",
            icone=ft.Icons.SAVINGS_ROUNDED,
            cor=COR_INVESTIMENTO,
            txt_teto_info=self.txt_inv_teto_info,
            txt_valor=self.txt_inv_valor,
            txt_pct=self.txt_inv_pct,
            pb=self.pb_inv,
            txt_dica=self.txt_inv_dica,
            acao_rodape=self.btn_guardar_inv,
        )

        card_livre_culpa = self._construir_mini_pote_card(
            txt_titulo=self.txt_livre_titulo,
            subtitulo_tag="Mini-Pote 2 · Prazeres (Pote 4)",
            icone=ft.Icons.CELEBRATION_ROUNDED,
            cor=COR_LIVRE_CULPA,
            txt_teto_info=self.txt_livre_teto_info,
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
                                    self.txt_titulo_slider,
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
                        wrap=True if self.mobile else False,
                        spacing=6,
                        controls=[
                            ft.Text(
                                "Atalhos rápidos:",
                                size=11,
                                color=T.TEXT_MUTED,
                            ),
                            ft.Container(expand=True if not self.mobile else False, content=self.row_chips_atalho),
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
                                                    self.box_badge_mes,
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
                    self.box_trava_fluxo,
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

    def _on_toggle_trava_teto(self, e: ft.ControlEvent):
        self.travar_teto_seguro = bool(e.control.value)
        storage.salvar_trava_teto_seguro_sobra_sync(self.page, self.travar_teto_seguro)
        self._sincronizar_ui(notificar_kpi=True)
        try:
            self.page.update()
        except Exception:
            pass

    def _on_slider_change(self, e: ft.ControlEvent):
        try:
            novo_pct = round(float(e.control.value or 0.0), 0)
        except Exception:
            novo_pct = 50.0
        self.definir_percentual(novo_pct, atualizar_slider=False)

    def _on_input_pct_submit(self, e: ft.ControlEvent):
        texto = str(self.tf_pct.value or "").strip().replace(",", ".").replace("%", "").replace("Guardar", "").strip()
        try:
            novo_pct = float(texto)
        except Exception:
            novo_pct = self.pct_investimento
        self.definir_percentual(novo_pct, atualizar_slider=True)

    def definir_percentual(self, novo_pct: float, atualizar_slider: bool = True):
        pct_limpo = round(max(0.0, min(100.0, float(novo_pct))), 1)
        self.pct_investimento = pct_limpo
        self.herdado_mes = False
        storage.salvar_percentual_sobra_investimento_sync(
            self.page, pct_limpo, mes=self.mes_atual, ano=self.ano_atual
        )
        if self.mes_atual is not None and self.ano_atual is not None:
            try:
                db.salvar_config_caixa_livre_mes(self.mes_atual, self.ano_atual, pct_limpo)
            except Exception:
                pass

        if atualizar_slider:
            self.slider_pct.value = pct_limpo
        self.tf_pct.value = str(int(round(pct_limpo)))
        self.row_chips_atalho.controls = self._construir_chips_atalho()

        # Recalcula e sincroniza com a grade dos 6 potes
        dados = self._sincronizar_ui(notificar_kpi=True)
        if self.on_potes_alterados and "potes_atualizados" in dados:
            self.on_potes_alterados(dados["potes_atualizados"])

        try:
            self.page.update()
        except Exception:
            pass

    def atualizar_periodo(
        self,
        receitas: float,
        despesas: float,
        mes: int | None = None,
        ano: int | None = None,
        protecao_fluxo: dict | None = None,
        resumo_potes: dict | None = None,
        piso_custos_fixos: float | None = None,
    ):
        """
        Atualiza receitas, despesas, escopo de mês/ano, proteção de fluxo e dados dos 6 potes
        do período selecionado, recalculando a arquitetura unificada.
        """
        self.receitas = float(receitas or 0.0)
        self.despesas = float(despesas or 0.0)
        if isinstance(protecao_fluxo, dict):
            self.protecao_fluxo = protecao_fluxo
        if isinstance(resumo_potes, dict):
            self.potes_dados = resumo_potes.get("potes") or []
        if piso_custos_fixos is not None:
            self.piso_custos_fixos = float(piso_custos_fixos)

        if mes is not None and ano is not None:
            mudou_mes = (int(mes) != self.mes_atual or int(ano) != self.ano_atual)
            self.mes_atual = int(mes)
            self.ano_atual = int(ano)
            if mudou_mes:
                pct_carregado = storage.obter_percentual_sobra_investimento(
                    self.page, 50.0, mes=self.mes_atual, ano=self.ano_atual
                )
                try:
                    cfg_db = db.obter_config_caixa_livre_mes(self.mes_atual, self.ano_atual)
                    if isinstance(cfg_db, dict) and "pct_investimento" in cfg_db:
                        self.herdado_mes = bool(cfg_db.get("personalizado_no_mes", False) is False)
                        if not self.herdado_mes or pct_carregado == 50.0:
                            pct_carregado = float(cfg_db.get("pct_investimento", pct_carregado))
                            storage.salvar_percentual_sobra_investimento_sync(
                                self.page, pct_carregado, mes=self.mes_atual, ano=self.ano_atual
                            )
                except Exception:
                    pass
                self.pct_investimento = round(max(0.0, min(100.0, float(pct_carregado))), 1)
                self.slider_pct.value = self.pct_investimento
                self.tf_pct.value = str(int(round(self.pct_investimento)))
                self.row_chips_atalho.controls = self._construir_chips_atalho()

        dados = self._sincronizar_ui(notificar_kpi=True)
        if self.on_potes_alterados and "potes_atualizados" in dados:
            self.on_potes_alterados(dados["potes_atualizados"])

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
        return calcular_rateio_sobra(
            receitas=self.receitas,
            despesas=self.despesas,
            pct_investimento=self.pct_investimento,
            protecao_fluxo=self.protecao_fluxo,
            travar_pelo_teto_seguro=self.travar_teto_seguro,
            potes=self.potes_dados,
            piso_custos_fixos=self.piso_custos_fixos,
        )

    def _acao_lancar_investimento(self, _e=None):
        dados = self.obter_dados_atuais()
        val_inv = float(dados.get("valor_investimento", 0.0) or 0.0)
        if self.on_lancar_investimento:
            self.on_lancar_investimento(val_inv)

    def _sincronizar_ui(self, notificar_kpi: bool = True) -> dict:
        dados = self.obter_dados_atuais()
        rec = dados["receitas"]
        desp = dados["despesas"]
        sobra = dados["sobra"]
        pct_inv = dados["pct_investimento"]
        pct_livre = dados["pct_livre"]

        val_inv = dados["valor_investimento"]
        val_livre = dados["valor_livre_culpa"]
        teto_inv = dados.get("teto_investimento", val_inv)
        teto_livre = dados.get("teto_livre_culpa", val_livre)
        gasto_inv = dados.get("gasto_investimento", 0.0)
        gasto_livre = dados.get("gasto_livre_culpa", 0.0)
        val_inv_proj = dados["valor_investimento_projetado"]
        val_livre_proj = dados["valor_livre_projetado"]
        retido_outros = dados.get("retido_outros_potes", 0.0)
        teto_caixa = dados.get("teto_caixa_livre", sobra)

        # Nomes padrão ou editados dos dois cards
        nm_inv = dados.get("nome_investimento") or "Liberdade Financeira"
        nm_livre = dados.get("nome_livre_culpa") or "Prazeres"
        self.txt_inv_titulo.value = nm_inv
        self.txt_livre_titulo.value = nm_livre

        teto_seguro = dados["teto_seguro_gasto"]
        sobra_falsa = dados["sobra_falsa_travada"]
        menor_saldo = dados["menor_saldo_futuro"]
        tem_armadilha = dados["tem_armadilha_fluxo"]
        fica_negativo = dados["fica_negativo_no_meio"]
        dt_gargalo = dados.get("data_gargalo")
        prox_dt = dados.get("proxima_entrada_data")
        prox_val = dados.get("proxima_entrada_valor", 0.0)

        # Badge de escopo mensal
        if self.mes_atual and self.ano_atual:
            nm = MESES_NOMES[self.mes_atual - 1][:3] if 1 <= self.mes_atual <= 12 else str(self.mes_atual)
            rot_m = f"{nm}/{self.ano_atual}"
            self.txt_badge_mes.value = f"Regra de {rot_m}: {_fmt_pct(pct_inv)} {nm_inv} / {_fmt_pct(pct_livre)} {nm_livre}"
            self.box_badge_mes.visible = True
            self.txt_titulo_slider.value = f"Divisão do Caixa Livre ({rot_m}): {nm_inv} x {nm_livre}"
        else:
            self.box_badge_mes.visible = False
            self.txt_titulo_slider.value = f"Divisão do Caixa Livre: {nm_inv} x {nm_livre}"

        # Equação matemática unificada com transparência total
        if dados.get("arquitetura_unificada") and retido_outros > 0:
            self.txt_equacao.value = (
                f"Receitas ({formatar_moeda(rec)}) − Retido nos Potes ({formatar_moeda(retido_outros)}) "
                f"= Orçamento Caixa Livre {formatar_moeda(teto_caixa)} · "
                f"Disponível Hoje: {formatar_moeda(val_livre)} ({nm_livre}) + {formatar_moeda(val_inv)} ({nm_inv})"
            )
        else:
            self.txt_equacao.value = (
                f"Receitas ({formatar_moeda(rec)}) − Despesas ({formatar_moeda(desp)}) "
                f"= Sobra Projetada {formatar_moeda(sobra)}"
            )

        # Atualiza o Painel de Blindagem contra Sobra Falsa
        self.txt_sobra_proj_card.value = formatar_moeda(teto_caixa)
        self.txt_teto_seguro_card.value = formatar_moeda(teto_seguro)
        self.txt_sobra_falsa_card.value = formatar_moeda(sobra_falsa)

        dt_g_br = formatar_data_br(dt_gargalo) if dt_gargalo else "—"
        if fica_negativo:
            self.txt_teto_seguro_card.color = T.DESPESA
            self.txt_teto_seguro_sub.value = f"Vale crítico de {formatar_moeda(menor_saldo)} em {dt_g_br}"
            self.icone_alerta_gargalo.name = ft.Icons.WARNING_AMBER_ROUNDED
            self.icone_alerta_gargalo.color = T.DESPESA
            self.txt_alerta_gargalo.value = (
                f"🚨 Alerta de Descasamento: mesmo que o Caixa Livre totalize {formatar_moeda(teto_caixa)}, "
                f"seu saldo acumulado chega a {formatar_moeda(menor_saldo)} em {dt_g_br}. "
                f"Teto seguro para gastar agora sem agravar o negativo: R$ 0,00."
            )
        elif tem_armadilha:
            self.txt_teto_seguro_card.color = COR_BLINDAGEM
            self.txt_teto_seguro_sub.value = f"Menor saldo (Gargalo) em {dt_g_br}"
            self.icone_alerta_gargalo.name = ft.Icons.SHIELD_ROUNDED
            self.icone_alerta_gargalo.color = COR_GARGALO
            complemento_prox = (
                f" Próxima entrada: {formatar_moeda(prox_val)} em {formatar_data_br(prox_dt)}."
                if prox_dt and prox_val > 0
                else ""
            )
            self.txt_alerta_gargalo.value = (
                f"🛡️ Sobra Falsa detectada! Do Caixa Livre de {formatar_moeda(teto_caixa)}, "
                f"{formatar_moeda(sobra_falsa)} só entram depois do gargalo de {dt_g_br}. "
                f"Seu limite seguro hoje sem ficar negativo é {formatar_moeda(teto_seguro)}."
                + complemento_prox
            )
        else:
            self.txt_teto_seguro_card.color = COR_INVESTIMENTO
            self.txt_teto_seguro_sub.value = "Fluxo saudável sem gargalo intermediário"
            self.icone_alerta_gargalo.name = ft.Icons.VERIFIED_USER_ROUNDED
            self.icone_alerta_gargalo.color = COR_INVESTIMENTO
            self.txt_alerta_gargalo.value = (
                f"✅ Fluxo de caixa blindado: todo o Caixa Livre ({formatar_moeda(teto_caixa)}) "
                "está 100% disponível e protegido de gargalos intermediários."
            )

        if prox_dt and prox_val > 0:
            self.txt_sobra_falsa_sub.value = f"Aguarda {formatar_moeda(prox_val)} em {formatar_data_br(prox_dt)}"
        elif dt_gargalo and sobra_falsa > 0:
            self.txt_sobra_falsa_sub.value = f"Bloqueado até passar o dia {dt_g_br}"
        else:
            self.txt_sobra_falsa_sub.value = "Nenhuma receita retida por descasamento"

        if dados["tem_sobra"]:
            if tem_armadilha and self.travar_teto_seguro:
                self.txt_badge_status.value = f"🛡️ Teto Seguro: {formatar_moeda(teto_seguro)} (Mês: {formatar_moeda(teto_caixa)})"
                self.txt_badge_status.color = COR_BLINDAGEM
                self.box_badge_status.bgcolor = f"{COR_BLINDAGEM}18"
            else:
                self.txt_badge_status.value = f"Caixa Livre: {formatar_moeda(teto_caixa)}"
                self.txt_badge_status.color = COR_INVESTIMENTO
                self.box_badge_status.bgcolor = f"{COR_INVESTIMENTO}18"
            self.banner_sem_sobra.visible = False
        elif dados["em_deficit"]:
            self.txt_badge_status.value = f"Déficit no Período: {formatar_moeda(rec - desp)}"
            self.txt_badge_status.color = T.DESPESA
            self.box_badge_status.bgcolor = f"{T.DESPESA}18"
            self.txt_aviso_sem_sobra.value = (
                f"Neste período as despesas superaram as receitas em {formatar_moeda(dados['deficit'])}. "
                "O Caixa Livre fica zerado até que haja saldo residual positivo."
            )
            self.banner_sem_sobra.visible = True
        else:
            self.txt_badge_status.value = "Período Equilibrado (R$ 0,00)"
            self.txt_badge_status.color = T.TEXT_MUTED
            self.box_badge_status.bgcolor = f"{T.TEXT_MUTED}18"
            self.txt_aviso_sem_sobra.value = (
                "Não há sobra residual no Caixa Livre neste período. "
                "Ajuste os percentuais ou registre novas receitas."
            )
            self.banner_sem_sobra.visible = True

        self.txt_pct_destaque.value = _fmt_pct(pct_inv)
        self.txt_inv_pct.value = _fmt_pct(pct_inv)
        self.txt_livre_pct.value = _fmt_pct(pct_livre)

        # Valores disponíveis dos dois cards
        self.txt_inv_valor.value = formatar_moeda(val_inv)
        self.txt_livre_valor.value = formatar_moeda(val_livre)

        # Detalhamento Teto x Já Gasto
        self.txt_inv_teto_info.value = f"Teto do Mês: {formatar_moeda(teto_inv)} · Já aportado: {formatar_moeda(gasto_inv)}"
        self.txt_livre_teto_info.value = f"Teto do Mês: {formatar_moeda(teto_livre)} · Já gasto: {formatar_moeda(gasto_livre)}"

        if tem_armadilha and self.travar_teto_seguro and teto_caixa > 0:
            self.txt_inv_dica.value = (
                f"Disponível hoje s/ negativar. (Projetado do mês: {formatar_moeda(val_inv_proj)})"
            )
            self.txt_livre_dica.value = (
                f"Blindado pelo Pior Dia ({dt_g_br}). (Projetado do mês: {formatar_moeda(val_livre_proj)})"
            )
            self.txt_badge_livre_status.value = f"Blindado · Teto {formatar_moeda(teto_seguro)}"
        else:
            self.txt_inv_dica.value = f"Resta {formatar_moeda(val_inv)} para aportar em {nm_inv}."
            self.txt_livre_dica.value = f"Resta {formatar_moeda(val_livre)} livre para gastar em {nm_livre}."
            self.txt_badge_livre_status.value = "Livre sem Culpa"

        self.pb_inv.value = max(0.0, min(1.0, (val_inv / teto_inv) if teto_inv > 0 else 0.0))
        self.pb_livre.value = max(0.0, min(1.0, (val_livre / teto_livre) if teto_livre > 0 else 0.0))

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

        return dados
