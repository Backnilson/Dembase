"""
=============================================================================
DemBase v3 — views/widgets/potes_cards.py  (Flet 1.0.1)
Cards do Dashboard: Gasto Real vs Limite (Receita Real) dos 6 potes.
Apresentação puramente reativa e unificada:
  1. Custos Fixos (pos 1): Automático / Ajustado à despesa (ou piso R$ 1.150,00).
  2. Custos Semi Fixos (pos 2), Metas (pos 3), Conhecimento (pos 5):
     Orçamentos retidos / intocáveis (saldo disponível retido no pote para despesas futuras).
  3. Prazeres (pos 4) e Liberdade Financeira (pos 6):
     Conectados em tempo real ao Slider do Caixa Livre.
=============================================================================
"""
from __future__ import annotations

from typing import Callable, Any
import flet as ft
from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_moeda, MESES_NOMES

COR_EXCEDIDO = "#DC2626"


def _pct_br(valor: float) -> str:
    return f"{valor:.2f}%".replace(".", ",")


def _badge(texto: str, cor: str, bg: str | None = None) -> ft.Container:
    return ft.Container(
        content=ft.Text(texto, color=cor, size=11, weight=ft.FontWeight.W_600),
        padding=pad(h=10, v=3),
        border_radius=20,
        bgcolor=bg or f"{cor}22",
        border=borda(color=f"{cor}55"),
    )


def _caixa_valor(rotulo: str, valor: float, cor_valor: str) -> ft.Container:
    return ft.Container(
        expand=True,
        padding=pad(h=12, v=8),
        bgcolor=T.SURFACE_ALT,
        border_radius=10,
        border=borda(),
        content=ft.Column(
            spacing=2,
            controls=[
                ft.Text(rotulo, color=T.TEXT_MUTED, size=10, weight=ft.FontWeight.W_600),
                ft.Text(formatar_moeda(valor), color=cor_valor, size=14, weight=ft.FontWeight.BOLD),
            ],
        ),
    )


def card_pote(pote: dict, on_click=None, on_liberar: Callable[[int, bool], None] | None = None) -> ft.Container:
    gasto = float(pote.get("gasto") or 0)
    previsto = float(pote.get("previsto") or 0)
    restante = previsto - gasto
    qtd = int(pote.get("qtd_transacoes") or 0)
    cor_pote = pote.get("cor") or T.PRIMARY
    perc_pote = float(pote.get("percentual") or 0)
    posicao = int(pote.get("posicao") or 0)
    tipo_comp = pote.get("tipo_comportamento") or ""

    excedido = gasto > previsto and previsto > 0
    sem_gastos = gasto == 0
    sem_receita = previsto == 0

    # Determinação visual específica de cada comportamento inteligente
    if sem_receita:
        pct = 100.0 if gasto > 0 else 0.0
        if gasto > 0:
            cor_barra, cor_valor = COR_EXCEDIDO, COR_EXCEDIDO
            badge = _badge("Sem receita", COR_EXCEDIDO)
            borda_card = borda(color=f"{COR_EXCEDIDO}80")
            txt_restante = ft.Text(f"{formatar_moeda(gasto)} sem receita no período", color=COR_EXCEDIDO, size=11)
        else:
            cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
            badge = _badge("Sem receita", T.TEXT_MUTED, bg=T.SURFACE_ALT)
            borda_card = borda()
            txt_restante = ft.Text("Sem movimentação", color=T.TEXT_MUTED, size=11)
    elif excedido:
        pct = (gasto / previsto * 100) if previsto > 0 else 0.0
        cor_barra, cor_valor = COR_EXCEDIDO, COR_EXCEDIDO
        badge = _badge("Excedido", COR_EXCEDIDO)
        borda_card = borda(color=f"{COR_EXCEDIDO}80")
        txt_restante = ft.Text(f"{formatar_moeda(abs(restante))} acima do limite", color=COR_EXCEDIDO, size=11)
    elif posicao == 1 or tipo_comp == "automatico_fixo":
        # Custos Fixos: Automático / Ajustado à despesa
        pct = (gasto / previsto * 100) if previsto > 0 else 0.0
        cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
        piso = float(pote.get("piso_configurado") or 1150.0)
        if gasto >= piso and previsto == gasto:
            badge = _badge(f"{_pct_br(perc_pote)} · Ajustado", cor_pote)
            txt_restante = ft.Text(f"Limite 100% ajustado às despesas", color=T.TEXT_MUTED, size=11)
        else:
            badge = _badge(f"{_pct_br(perc_pote)} · Piso {formatar_moeda(piso)}", cor_pote)
            txt_restante = ft.Text(f"+{formatar_moeda(restante)} reservado p/ fixos", color=T.RECEITA, size=11)
        borda_card = borda()
    elif posicao in (2, 3, 5) or tipo_comp == "retido_intocavel":
        # Custos Semi Fixos, Metas, Conhecimento: Orçamento Retido / Intocável
        pct = (gasto / previsto * 100) if previsto > 0 else 0.0
        cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
        badge = _badge(_pct_br(perc_pote), cor_pote, bg=f"{cor_pote}18")
        borda_card = borda()
        if pote.get("liberado"):
            txt_restante = ft.Text(
                f"Sobra liberada: +{formatar_moeda(float(pote.get('liberado_valor') or 0))} no Caixa Livre",
                color="#06B6D4", size=11, weight=ft.FontWeight.W_600,
            )
            borda_card = borda(color="#06B6D480")
        else:
            txt_restante = ft.Text(f"+{formatar_moeda(restante)} retido no pote", color=T.RECEITA, size=11)
    elif posicao == 4 or tipo_comp == "caixa_livre_prazeres":
        # Prazeres (Livre sem Culpa / Caixa Livre)
        pct = (gasto / previsto * 100) if previsto > 0 else 0.0
        cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
        badge = _badge(f"{_pct_br(perc_pote)} · Livre s/ Culpa", cor_pote, bg=f"{cor_pote}18")
        borda_card = borda(color=f"{cor_pote}40")
        txt_restante = ft.Text(f"+{formatar_moeda(restante)} livre no caixa", color=cor_pote, size=11, weight=ft.FontWeight.W_600)
    elif posicao == 6 or tipo_comp == "caixa_livre_investimento":
        # Liberdade Financeira (Investimento / Caixa Livre)
        pct = (gasto / previsto * 100) if previsto > 0 else 0.0
        cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
        badge = _badge(f"{_pct_br(perc_pote)} · Investir", cor_pote, bg=f"{cor_pote}18")
        borda_card = borda(color=f"{cor_pote}40")
        txt_restante = ft.Text(f"+{formatar_moeda(restante)} p/ aportar", color=cor_pote, size=11, weight=ft.FontWeight.W_600)
    else:
        pct = (gasto / previsto * 100) if previsto > 0 else 0.0
        cor_barra, cor_valor = cor_pote, T.TEXT_PRIMARY
        badge = _badge(_pct_br(pct), T.TEXT_PRIMARY, bg=T.SURFACE_ALT)
        borda_card = borda()
        txt_restante = ft.Text(f"+{formatar_moeda(restante)} disponível", color=T.RECEITA, size=11)

    rotulo_qtd = "transação" if qtd == 1 else "transações"

    # Ação rápida: liberar a sobra +Disponível dos potes manuais para o Caixa Livre
    acao_liberar: list[ft.Control] = []
    if on_liberar and posicao in (2, 3, 5):
        if pote.get("liberado"):
            acao_liberar.append(
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.UNDO_ROUNDED, size=15, color=T.TEXT_MUTED),
                            ft.Text("Restaurar reserva do pote", size=12, color=T.TEXT_MUTED,
                                    weight=ft.FontWeight.W_600),
                        ],
                    ),
                    on_click=lambda _, pos=posicao: on_liberar(pos, False),
                    style=ft.ButtonStyle(
                        side=ft.BorderSide(1, T.BORDER),
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=pad(h=12, v=8),
                    ),
                )
            )
        elif restante > 0.005 and previsto > 0:
            acao_liberar.append(
                ft.FilledTonalButton(
                    content=ft.Row(
                        spacing=6, tight=True, alignment=ft.MainAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.LOCK_OPEN_ROUNDED, size=15, color="#06B6D4"),
                            ft.Text("Liberar Sobra p/ Caixa Livre", size=12, color="#06B6D4",
                                    weight=ft.FontWeight.W_700),
                        ],
                    ),
                    tooltip=f"Ajusta o teto ao gasto real e envia {formatar_moeda(restante)} ao Caixa Livre",
                    on_click=lambda _, pos=posicao: on_liberar(pos, True),
                    style=ft.ButtonStyle(
                        bgcolor="#06B6D41A",
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=pad(h=12, v=8),
                    ),
                )
            )

    return ft.Container(
        col={"xs": 12, "sm": 6, "md": 4},
        padding=pad(all_=16),
        bgcolor=T.SURFACE,
        border_radius=14,
        border=borda_card,
        on_click=on_click,
        ink=bool(on_click),
        content=ft.Column(
            spacing=12,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(width=10, height=10, bgcolor=cor_pote, border_radius=5),
                                ft.Text(
                                    pote.get("nome", ""),
                                    color=T.TEXT_PRIMARY,
                                    size=14,
                                    weight=ft.FontWeight.BOLD,
                                    max_lines=1,
                                    overflow=ft.TextOverflow.ELLIPSIS,
                                ),
                            ],
                        ),
                        badge,
                    ],
                ),
                ft.ProgressBar(
                    value=min(pct / 100.0, 1.0),
                    bar_height=8,
                    color=cor_barra,
                    bgcolor=T.SURFACE_ALT,
                    border_radius=4,
                ),
                ft.Row(
                    spacing=10,
                    controls=[
                        _caixa_valor("GASTO REAL", gasto, cor_valor),
                        _caixa_valor(f"LIMITE ({perc_pote:.1f}%)", previsto, T.TEXT_PRIMARY),
                    ],
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        txt_restante,
                        ft.Row(
                            spacing=4,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.RECEIPT_LONG_OUTLINED, color=T.TEXT_MUTED, size=14),
                                ft.Text(f"{qtd} {rotulo_qtd}", color=T.TEXT_MUTED, size=11),
                            ],
                        ),
                    ],
                ),
                *acao_liberar,
            ],
        ),
    )


class SecaoPotesController:
    """
    Controlador da Seção dos 6 Potes com capacidade de sincronização em tempo real (.update())
    quando o usuário arrasta o Slider no módulo de Destinação do Caixa Livre.
    """

    def __init__(
        self,
        page: ft.Page | None,
        resumo: dict,
        nav_func: Callable[[str], None] | None = None,
        on_ajustar: Callable[[Any], None] | None = None,
        on_liberar: Callable[[int, bool], None] | None = None,
    ):
        self.page = page
        self.on_liberar = on_liberar
        self.resumo = resumo
        self.nav_func = nav_func
        self.on_ajustar = on_ajustar
        self.potes = resumo.get("potes") or []

        self.row_cards = ft.ResponsiveRow(
            spacing=14,
            run_spacing=14,
            controls=self._montar_cards(),
        )

        self.column = self._construir_coluna()

    def _montar_cards(self) -> list[ft.Control]:
        return [
            card_pote(
                p,
                (lambda _, pid=p.get("id"): self.nav_func(pid)) if self.nav_func else None,
                on_liberar=self.on_liberar,
            )
            for p in self.potes
        ]

    def _construir_coluna(self) -> ft.Column:
        sem_pote = self.resumo.get("sem_pote") or {}
        renda = float(self.resumo.get("renda") or 0)
        mes_ref = self.resumo.get("mes_referencia")
        ano_ref = self.resumo.get("ano_referencia")

        rot_mes = ""
        if mes_ref and ano_ref:
            try:
                m_idx = int(mes_ref)
                nm = MESES_NOMES[m_idx - 1][:3] if 1 <= m_idx <= 12 else str(mes_ref)
                rot_mes = f"Metas de {nm}/{ano_ref}"
            except Exception:
                pass

        if renda > 0:
            subtitulo = f"Limite calculado sobre a receita real do período ({formatar_moeda(renda)}) · Total: 100,00%"
            badge_header = _badge(f"Receita: {formatar_moeda(renda)}", T.PRIMARY)
        else:
            subtitulo = "Sem receitas registradas no período selecionado — orçamentos zerados"
            badge_header = _badge("0 Receitas", T.WARNING)

        badges_row = [
            ft.Text("Metas Financeiras (6 Potes)", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
            badge_header,
        ]
        if rot_mes:
            badges_row.append(_badge(rot_mes, T.RECEITA))

        cabecalho = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.END,
            controls=[
                ft.Column(
                    spacing=3,
                    expand=True,
                    controls=[
                        ft.Row(spacing=8, wrap=True, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=badges_row),
                        ft.Text(subtitulo, color=T.TEXT_MUTED, size=12),
                    ],
                ),
                ft.TextButton(
                    content=ft.Text("Ajustar metas do mês ›", color=T.WARNING, size=12, weight=ft.FontWeight.W_600),
                    on_click=self.on_ajustar,
                ) if self.on_ajustar else ft.Container(),
            ],
        )

        controles: list[ft.Control] = [cabecalho, ft.Container(height=12), self.row_cards]

        qtd_sem = int(sem_pote.get("qtd") or 0)
        if qtd_sem > 0:
            controles += [
                ft.Container(height=12),
                ft.Container(
                    padding=pad(h=16, v=12),
                    bgcolor=T.SURFACE,
                    border_radius=12,
                    border=borda(color=f"{T.WARNING}66"),
                    content=ft.Row(
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=T.WARNING, size=18),
                            ft.Text(
                                f"{qtd_sem} despesa(s) sem pote no período — {formatar_moeda(float(sem_pote.get('total') or 0))}",
                                color=T.TEXT_PRIMARY,
                                size=12,
                                expand=True,
                            ),
                        ],
                    ),
                ),
            ]

        return ft.Column(spacing=0, controls=controles)

    def atualizar_potes_em_tempo_real(self, novos_potes: list[dict]):
        """Atualiza imediatamente os cards dos 6 potes na tela via .update()."""
        if not novos_potes:
            return
        self.potes = novos_potes
        self.row_cards.controls = self._montar_cards()
        if self.page:
            try:
                self.page.update()
            except Exception:
                pass


def secao_potes(resumo: dict, nav_func=None, on_ajustar=None, page: ft.Page | None = None, on_liberar=None) -> ft.Column | SecaoPotesController:
    """Constrói a seção visual dos 6 Potes do período filtrado."""
    ctrl = SecaoPotesController(page=page, resumo=resumo, nav_func=nav_func, on_ajustar=on_ajustar, on_liberar=on_liberar)
    # Atribui o método atualizar_potes_em_tempo_real diretamente na coluna para fácil chamada
    col = ctrl.column
    col.controller = ctrl
    col.atualizar_potes = ctrl.atualizar_potes_em_tempo_real
    return col
