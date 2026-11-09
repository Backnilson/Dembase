"""
=============================================================================
DemBase v3 — views/widgets/dashboard_charts.py  (Flet 1.0.1)
Catálogo Modular de Gráficos do Dashboard (Plug-and-Play + 100% Drill-down).
Permite renderizar N gráficos responsivos em Grid (1 col Mobile / 2 cols Desktop),
escolher quais gráficos exibir nas Configurações e clicar em qualquer barra,
fatia ou linha para abrir o relatório detalhado correspondente.
=============================================================================
"""
from __future__ import annotations
import calendar
from datetime import date
import flet as ft
from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_moeda
from core.periodo import obter_estado_periodo_atual
from core.report_context import ReportContext
from core.nav import (
    ir_cartoes,
    ir_relatorio_lancamentos,
    ir_relatorio_categoria,
    ir_relatorio_fluxo,
)
from core.router import navegar, ROTA_CAIXINHAS
from core.theme import mostrar_feedback, abrir_dialogo, fechar_dialogo
from datetime import datetime
import services.supabase_client as db


# Catálogo oficial de gráficos disponíveis para o Dashboard
DASHBOARD_CHARTS_CATALOG: list[dict] = [
    {
        "id": "minhas_caixinhas",
        "titulo": "Meus DemBoxes",
        "subtitulo": "Provisões do mês, quitação de dívidas e vínculo aos 6 Potes",
        "icone": ft.Icons.INVENTORY_2_ROUNDED,
        "cor": "#10B981",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "despesas_categoria",
        "titulo": "Despesas por Categoria",
        "subtitulo": "Toque em uma categoria para abrir o diagnóstico detalhado",
        "icone": ft.Icons.DONUT_LARGE_ROUNDED,
        "cor": "#EF4444",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "fluxo_diario",
        "titulo": "Ritmo Diário no Período",
        "subtitulo": "Toque em uma barra diária para filtrar os lançamentos do dia",
        "icone": ft.Icons.EQUALIZER_ROUNDED,
        "cor": "#3B82F6",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "balanco_semestral",
        "titulo": "Evolução Mensal (6 Meses)",
        "subtitulo": "Toque em um mês para ver o extrato ou abra o comparativo",
        "icone": ft.Icons.STACKED_BAR_CHART_ROUNDED,
        "cor": "#8B5CF6",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "receitas_categoria",
        "titulo": "Fontes de Receita",
        "subtitulo": "Toque em uma fonte para inspecionar as entradas do período",
        "icone": ft.Icons.TRENDING_UP_ROUNDED,
        "cor": "#10B981",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
    {
        "id": "formas_e_cartoes",
        "titulo": "Meios de Pagamento & Cartões",
        "subtitulo": "Toque na modalidade ou nos cartões para abrir o detalhamento",
        "icone": ft.Icons.CREDIT_SCORE_ROUNDED,
        "cor": "#F59E0B",
        "col": {"xs": 12, "sm": 12, "md": 6, "lg": 6},
    },
]

# Por padrão, todos os 6 gráficos vêm habilitados no início
GRAFICOS_PADRAO_IDS: list[str] = [item["id"] for item in DASHBOARD_CHARTS_CATALOG]


def _card_base_grafico(
    titulo: str,
    subtitulo: str,
    icone,
    cor_icone: str,
    corpo: ft.Control,
    col_span: dict,
    acao_extra: ft.Control | None = None,
) -> ft.Container:
    """Envelope visual padronizado para todos os gráficos do Dashboard."""
    header_controls = [
        ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            expand=True,
            controls=[
                ft.Container(
                    content=ft.Icon(icone, color=cor_icone, size=18),
                    bgcolor=f"{cor_icone}1F",
                    border_radius=10,
                    padding=pad(all_=8),
                ),
                ft.Column(
                    spacing=1,
                    expand=True,
                    controls=[
                        ft.Text(
                            titulo.strip(),
                            color=T.TEXT_PRIMARY,
                            size=14,
                            weight=ft.FontWeight.BOLD,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            subtitulo,
                            color=T.TEXT_MUTED,
                            size=11,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                    ],
                ),
            ],
        )
    ]
    if acao_extra:
        header_controls.append(acao_extra)

    return ft.Container(
        col=col_span,
        padding=pad(all_=18),
        bgcolor=T.SURFACE,
        border_radius=16,
        border=borda(),
        content=ft.Column(
            spacing=14,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=header_controls,
                ),
                ft.Divider(height=1, color=T.BORDER),
                corpo,
            ],
        ),
    )


def _estado_vazio(mensagem: str, icone=ft.Icons.INSERT_CHART_OUTLINED_ROUNDED) -> ft.Container:
    return ft.Container(
        padding=pad(v=28, h=12),
        alignment=ft.Alignment(0, 0),
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
            controls=[
                ft.Icon(icone, color=f"{T.TEXT_MUTED}70", size=34),
                ft.Text(
                    mensagem,
                    color=T.TEXT_MUTED,
                    size=12,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )


def _barra_empilhada_proporcional(fatias: list[tuple[float, str, str]]) -> ft.Container:
    """
    Renderiza uma barra horizontal segmentada proporcional (estilo Donut linear)
    totalmente compatível com Flet 1.0.1.
    fatias: [(percentual_0_a_100, cor_hex, tooltip_str), ...]
    """
    segmentos = []
    for perc, cor, dica in fatias:
        peso = max(1, int(round(perc)))
        if perc <= 0:
            continue
        segmentos.append(
            ft.Container(
                expand=peso,
                height=10,
                bgcolor=cor,
                border_radius=4,
                tooltip=dica,
            )
        )
    if not segmentos:
        segmentos.append(
            ft.Container(expand=1, height=10, bgcolor=T.SURFACE_ALT, border_radius=4)
        )
    return ft.Container(
        border_radius=6,
        clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
        content=ft.Row(spacing=2, controls=segmentos),
    )


def _chip_acao_header(label: str, cor: str, on_click) -> ft.Container:
    """Pílula clicável no canto superior direito do card de gráfico."""
    return ft.Container(
        padding=pad(h=10, v=4),
        bgcolor=f"{cor}18",
        border_radius=12,
        on_click=on_click,
        ink=True,
        content=ft.Row(
            spacing=3,
            tight=True,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(label, color=cor, size=11, weight=ft.FontWeight.BOLD),
                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=cor, size=14),
            ],
        ),
    )


# =============================================================================
# 1. CARD INTERATIVO: MINHAS CAIXINHAS (ADMINISTRAÇÃO & ACOMPANHAMENTO)
# =============================================================================
_MAPA_ICONES_CAIXINHAS = {
    "inventory_2": ft.Icons.INVENTORY_2_ROUNDED,
    "two_wheeler": ft.Icons.TWO_WHEELER_ROUNDED,
    "home": ft.Icons.HOME_ROUNDED,
    "person": ft.Icons.PERSON_ROUNDED,
    "handshake": ft.Icons.HANDSHAKE_ROUNDED,
    "warning": ft.Icons.WARNING_AMBER_ROUNDED,
    "directions_car": ft.Icons.DIRECTIONS_CAR_ROUNDED,
    "credit_card": ft.Icons.CREDIT_CARD_ROUNDED,
    "account_balance": ft.Icons.ACCOUNT_BALANCE_ROUNDED,
    "flag": ft.Icons.FLAG_ROUNDED,
    "local_gas_station": ft.Icons.LOCAL_GAS_STATION_ROUNDED,
    "shopping_cart": ft.Icons.SHOPPING_CART_ROUNDED,
    "restaurant": ft.Icons.RESTAURANT_ROUNDED,
    "local_pharmacy": ft.Icons.LOCAL_PHARMACY_ROUNDED,
    "celebration": ft.Icons.CELEBRATION_ROUNDED,
    "savings": ft.Icons.SAVINGS_ROUNDED,
    "bolt": ft.Icons.BOLT_ROUNDED,
    "school": ft.Icons.SCHOOL_ROUNDED,
}


def _notificar_refresh_dashboard(page: ft.Page, pacote: dict):
    fn_ref = pacote.get("on_refresh")
    if callable(fn_ref):
        try:
            fn_ref()
            return
        except Exception:
            pass
    try:
        if getattr(page, "views", None):
            v_top = page.views[-1]
            fn_v = getattr(v_top, "_dembase_refresh", None)
            if callable(fn_v):
                fn_v()
                return
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass


def _abrir_modal_abastecer_rapido(page: ft.Page, caixinha: dict, pacote: dict):
    cid = str(caixinha.get("id"))
    nome = caixinha.get("nome", "Caixinha")
    meta_v = float(caixinha.get("valor_meta", 0) or 0)
    saldo_v = float(caixinha.get("saldo_atual", 0) or 0)
    eh_pendente = saldo_v <= 0
    valor_sugerido = meta_v if eh_pendente else max(0.0, meta_v - saldo_v) or meta_v

    try:
        contas = db.listar_contas() or []
    except Exception:
        contas = []
    opcoes_contas = [ft.dropdown.Option(key=str(cta["id"]), text=cta.get("nome", "Conta")) for cta in contas]
    conta_id_padrao = str(caixinha.get("conta_id") or "")
    conta_sel_val = conta_id_padrao if any(opt.key == conta_id_padrao for opt in opcoes_contas) else (opcoes_contas[0].key if opcoes_contas else "")

    dd_conta = ft.Dropdown(
        label="Conta Bancária de Origem *",
        options=opcoes_contas,
        value=conta_sel_val,
        **T.dropdown_estilo(),
    )

    try:
        potes = db.listar_potes() or []
    except Exception:
        potes = []
    opcoes_potes = [
        ft.dropdown.Option(key=str(p["id"]), text=f"{p.get('nome', 'Pote')} ({p.get('percentual', 0)}%)")
        for p in potes
    ]
    pote_id_padrao = str(caixinha.get("pote_id") or "")
    pote_sel_val = pote_id_padrao if any(opt.key == pote_id_padrao for opt in opcoes_potes) else (opcoes_potes[0].key if opcoes_potes else "")

    dd_pote = ft.Dropdown(
        label="Pote Financeiro (6 Potes) *",
        options=opcoes_potes,
        value=pote_sel_val,
        **T.dropdown_estilo(),
    )

    txt_valor_pag = ft.TextField(
        label="Valor a Abastecer (R$) *",
        keyboard_type=ft.KeyboardType.NUMBER,
        prefix="R$ ",
        value=f"{valor_sugerido:.2f}".replace(".", ","),
        autofocus=True,
        **T.campo_estilo(),
    )

    modal_ab = None

    def _confirmar(_):
        val_str = (txt_valor_pag.value or "").replace(",", ".").replace("R$", "").strip()
        try:
            val_num = float(val_str or 0)
            if val_num <= 0:
                raise ValueError
        except ValueError:
            mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
            return

        conta_escolhida = (dd_conta.value or "").strip()
        if not conta_escolhida:
            mostrar_feedback(page, "Selecione a Conta Bancária de origem.", "alerta")
            return

        pote_escolhido = (dd_pote.value or "").strip()
        if not pote_escolhido:
            mostrar_feedback(page, "Selecione a qual dos 6 Potes este abastecimento pertence.", "alerta")
            return

        fechar_dialogo(page, modal_ab)
        try:
            if eh_pendente:
                db.pagar_provisao_caixinha(
                    caixinha_id=cid,
                    conta_id=conta_escolhida,
                    pote_id=pote_escolhido,
                    valor=val_num,
                    data_pagamento=date.today().isoformat(),
                )
            else:
                db.injetar_saldo_caixinha(
                    caixinha_id=cid,
                    valor=val_num,
                    descricao=f"Provisão Caixinha · {nome}",
                    conta_id=conta_escolhida,
                    pote_id=pote_escolhido,
                    data_aporte=date.today().isoformat(),
                    gerar_despesa=True,
                )
            mostrar_feedback(page, f"Caixinha '{nome}' abastecida com {formatar_moeda(val_num)}!", "sucesso")
            _notificar_refresh_dashboard(page, pacote)
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao abastecer caixinha: {ex}", "erro")

    modal_ab = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.Icons.SAVINGS_ROUNDED, color=T.PRIMARY, size=22),
            ft.Text(f"{'Encher Caixinha' if eh_pendente else 'Abastecer Caixinha'} · {nome}", size=16, weight=ft.FontWeight.BOLD),
        ], spacing=8),
        content=ft.Container(
            width=400,
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    txt_valor_pag,
                    dd_conta,
                    dd_pote,
                    ft.Container(
                        padding=pad(h=10, v=8),
                        bgcolor=f"{T.PRIMARY}12",
                        border_radius=8,
                        border=borda(1, f"{T.PRIMARY}30"),
                        content=ft.Row([
                            ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED, color=T.PRIMARY, size=16),
                            ft.Text(
                                "O valor diminui o saldo da Conta Bancária de origem, aumenta o saldo disponível da Caixinha e é contabilizado no Pote selecionado.",
                                size=11,
                                color=T.TEXT_PRIMARY,
                                expand=True,
                            ),
                        ], spacing=8),
                    ),
                ],
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal_ab)),
            ft.FilledButton(
                "Confirmar e Abastecer",
                on_click=_confirmar,
                style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8)),
            ),
        ],
    )
    abrir_dialogo(page, modal_ab)


def _abrir_modal_gastar_rapido(page: ft.Page, caixinha: dict, pacote: dict):
    cid = str(caixinha.get("id"))
    nome = caixinha.get("nome", "Caixinha")
    saldo_atual = float(caixinha.get("saldo_atual", 0) or 0)

    txt_valor = ft.TextField(
        label="Valor Gasto (R$) *",
        hint_text="Ex: 50,00",
        keyboard_type=ft.KeyboardType.NUMBER,
        prefix="R$ ",
        autofocus=True,
        **T.campo_estilo(),
    )
    txt_desc = ft.TextField(
        label="Descrição do Gasto (Opcional)",
        hint_text="Ex: Abastecimento, compra rápida...",
        **T.campo_estilo(),
    )

    modal_g = None

    def _confirmar_deducao(_):
        val_str = (txt_valor.value or "").replace(",", ".").replace("R$", "").strip()
        try:
            val = float(val_str or 0)
            if val <= 0:
                raise ValueError
        except ValueError:
            mostrar_feedback(page, "Informe um valor válido maior que zero.", "alerta")
            return

        fechar_dialogo(page, modal_g)
        try:
            db.deduzir_saldo_caixinha(cid, val, txt_desc.value.strip())
            mostrar_feedback(page, f"{formatar_moeda(val)} deduzidos da caixinha '{nome}'!", "sucesso")
            _notificar_refresh_dashboard(page, pacote)
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao deduzir saldo: {ex}", "erro")

    modal_g = ft.AlertDialog(
        modal=True,
        title=ft.Row([
            ft.Icon(ft.Icons.MONEY_OFF_CSRED_ROUNDED, color=T.DESPESA, size=22),
            ft.Text(f"Registrar Gasto · {nome}", size=16, weight=ft.FontWeight.BOLD),
        ], spacing=8),
        content=ft.Container(
            width=380,
            content=ft.Column(
                spacing=12,
                tight=True,
                controls=[
                    ft.Text(f"Saldo atual disponível: {formatar_moeda(saldo_atual)}", color=T.TEXT_MUTED, size=12),
                    txt_valor,
                    txt_desc,
                ],
            ),
        ),
        actions=[
            ft.TextButton("Cancelar", on_click=lambda _: fechar_dialogo(page, modal_g)),
            ft.FilledButton(
                "Registrar Gasto",
                on_click=_confirmar_deducao,
                style=ft.ButtonStyle(bgcolor=T.DESPESA, shape=ft.RoundedRectangleBorder(radius=8)),
            ),
        ],
    )
    abrir_dialogo(page, modal_g)


def _render_minhas_caixinhas(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    resumo = pacote.get("resumo_caixinhas")
    if not isinstance(resumo, dict) or not resumo.get("caixinhas"):
        try:
            di = pacote.get("data_inicio")
            df = pacote.get("data_fim")
            resumo = db.obter_resumo_caixinhas(forcar_atualizacao=True, data_inicio=di, data_fim=df)
        except Exception:
            resumo = resumo if isinstance(resumo, dict) else {}

    caixinhas = resumo.get("caixinhas") or []
    tot_meta = float(resumo.get("total_meta", 0) or 0)
    tot_saldo = float(resumo.get("total_saldo", 0) or 0)
    tot_gasto = float(resumo.get("total_gasto", 0) or 0)

    btn_gerenciar_topo = _chip_acao_header(
        "Gerenciar",
        T.PRIMARY,
        lambda _: navegar(page, ROTA_CAIXINHAS),
    )

    if not caixinhas:
        corpo_vazio = ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
            controls=[
                _estado_vazio(
                    "Crie DemBoxes para provisionar despesas do mês (ex: Moto, Aluguel) ou juntar dinheiro para quitar dívidas.",
                    ft.Icons.INVENTORY_2_ROUNDED,
                ),
                ft.FilledButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.ADD_ROUNDED, size=16, color=T.ON_PRIMARY),
                            ft.Text("Criar / Gerenciar DemBoxes", size=12, weight=ft.FontWeight.BOLD, color=T.ON_PRIMARY),
                        ],
                    ),
                    on_click=lambda _: navegar(page, ROTA_CAIXINHAS),
                    style=ft.ButtonStyle(
                        bgcolor=T.PRIMARY,
                        shape=ft.RoundedRectangleBorder(radius=10),
                        padding=pad(h=16, v=10),
                    ),
                ),
            ],
        )
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            corpo_vazio,
            meta["col"],
            acao_extra=btn_gerenciar_topo,
        )

    fatias_topo = []
    itens_ui = []

    for c in caixinhas[:5]:
        nome = c.get("nome", "Caixinha")
        cor_c = c.get("cor") or T.PRIMARY
        meta_c = float(c.get("valor_meta", 0) or 0)
        saldo_c = float(c.get("saldo_atual", 0) or 0)
        gasto_c = float(c.get("total_gasto", 0) or 0)
        provisionado_c = float(c.get("valor_provisionado_periodo") or max(meta_c, saldo_c + gasto_c))
        pct_disp = min(1.0, max(0.0, saldo_c / provisionado_c)) if provisionado_c > 0 else 0.0
        pct_consumo = min(1.0, max(0.0, gasto_c / provisionado_c)) if provisionado_c > 0 else 0.0

        # Resolucao canonica do Pote Vinculado (NUNCA exibe rotulo generico "6 Potes")
        _MAPA_POTES_PADRAO = {
            1: ("Custos Fixos", "#007AFF"),
            2: ("Custos Semi Fixos", "#FF69B4"),
            3: ("Metas", "#800080"),
            4: ("Prazeres", "#FF7A00"),
            5: ("Conhecimento", "#FFD60A"),
            6: ("Liberdade Financeira", "#6C5CE7"),
        }
        pote_nome = ""
        pote_cor = cor_c
        pote_info = c.get("potes")
        if isinstance(pote_info, dict) and pote_info.get("nome") and str(pote_info.get("nome")).strip() not in ("6 Potes", "Pote Vinculado", ""):
            pote_nome = str(pote_info.get("nome")).strip()
            pote_cor = pote_info.get("cor") or cor_c
        if not pote_nome and c.get("pote_id"):
            pid_str = str(c.get("pote_id"))
            try:
                mapa_p = {str(p["id"]): p for p in (db.listar_potes() or []) if p.get("id")}
                p_item = mapa_p.get(pid_str)
                if p_item and p_item.get("nome") and str(p_item.get("nome")).strip() not in ("6 Potes", "Pote Vinculado", ""):
                    pote_nome = str(p_item.get("nome")).strip()
                    pote_cor = (p_item.get("cor") if p_item else None) or cor_c
                elif p_item and p_item.get("posicao") in _MAPA_POTES_PADRAO:
                    pote_nome, pote_cor = _MAPA_POTES_PADRAO[p_item["posicao"]]
            except Exception:
                pass
        if not pote_nome:
            n_lower = nome.lower()
            if any(k in n_lower for k in ("aluguel", "condom", "luz", "energia", "agua", "água", "internet", "seguro")):
                pote_nome, pote_cor = _MAPA_POTES_PADRAO[1]
            elif any(k in n_lower for k in ("moto", "carro", "combust", "mercado", "aliment", "feira", "ipva", "manuten")):
                pote_nome, pote_cor = _MAPA_POTES_PADRAO[2]
            elif any(k in n_lower for k in ("reserva", "emerg", "invest", "futuro")):
                pote_nome, pote_cor = _MAPA_POTES_PADRAO[6]
            elif any(k in n_lower for k in ("curso", "livro", "faculdade", "estudo")):
                pote_nome, pote_cor = _MAPA_POTES_PADRAO[5]
            elif any(k in n_lower for k in ("viagem", "reforma", "meta")):
                pote_nome, pote_cor = _MAPA_POTES_PADRAO[3]
            else:
                pote_nome, pote_cor = _MAPA_POTES_PADRAO[4]

        ic_nome = c.get("icone", "inventory_2")
        icone_c = _MAPA_ICONES_CAIXINHAS.get(ic_nome, ft.Icons.INVENTORY_2_ROUNDED)

        peso_fatia = (provisionado_c / tot_meta * 100.0) if tot_meta > 0 else (100.0 / max(1, len(caixinhas)))
        fatias_topo.append(
            (
                max(5.0, peso_fatia),
                cor_c,
                f"{nome} ({pote_nome}): Disponível {formatar_moeda(saldo_c)} de {formatar_moeda(provisionado_c)}",
            )
        )

        eh_divida = str(c.get("modalidade") or "provisao_mensal").strip().lower() in ("divida", "quitacao")
        guardado_c = float(c.get("total_guardado", saldo_c + gasto_c) or 0)
        falta_c = max(0.0, meta_c - guardado_c)
        pct_conq = min(1.0, max(0.0, guardado_c / meta_c)) if meta_c > 0 else 0.0

        eh_pendente = (saldo_c <= 0 and gasto_c <= 0 and not eh_divida)
        if eh_divida:
            cor_barra = T.PRIMARY if pct_conq >= 1.0 else cor_c
            if falta_c <= 0:
                status_lbl = "100% Conquistado!"
                cor_status = T.PRIMARY
            else:
                status_lbl = f"Falta {formatar_moeda(falta_c)} ({pct_conq * 100:.0f}%)"
                cor_status = T.INFO if guardado_c > 0 else T.TEXT_MUTED
            val_barra = pct_conq
            txt_rodape_esq = f"Guardado: {formatar_moeda(guardado_c)} · {status_lbl}"
        else:
            if eh_pendente:
                cor_barra = T.WARNING
                status_lbl = "Aguardando provisão"
                cor_status = T.WARNING
            elif pct_disp <= 0.20:
                cor_barra = T.DESPESA
                status_lbl = f"{pct_consumo * 100:.0f}% consumido"
                cor_status = T.DESPESA
            elif pct_disp <= 0.50:
                cor_barra = T.WARNING
                status_lbl = f"{pct_consumo * 100:.0f}% consumido"
                cor_status = T.WARNING
            else:
                cor_barra = cor_c
                status_lbl = f"{pct_disp * 100:.0f}% disponível"
                cor_status = T.RECEITA
            val_barra = pct_disp if not eh_pendente else 0.0
            txt_rodape_esq = f"Consumido: {formatar_moeda(gasto_c)} · {status_lbl}"

        # Botões de ação rápida inline
        acoes_rapidas_item = [
            ft.Container(
                padding=pad(h=8, v=4),
                bgcolor=T.SURFACE,
                border_radius=8,
                border=borda(1, T.PRIMARY),
                ink=True,
                tooltip="Guardar dinheiro neste DemBox" if eh_divida else "Abastecer / Pagar Provisão deste DemBox",
                on_click=lambda _, cx=c: _abrir_modal_abastecer_rapido(page, cx, pacote),
                content=ft.Row(
                    spacing=3,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.ADD_ROUNDED, color=T.PRIMARY, size=13),
                        ft.Text("Guardar" if eh_divida else ("Encher" if eh_pendente else "Abastecer"), color=T.PRIMARY, size=10.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            )
        ]
        if saldo_c > 0:
            acoes_rapidas_item.append(
                ft.Container(
                    padding=pad(h=8, v=4),
                    bgcolor=T.SURFACE,
                    border_radius=8,
                    border=borda(1, T.INFO if eh_divida else T.DESPESA),
                    ink=True,
                    tooltip="Abater / Pagar ao credor" if eh_divida else "Registrar gasto rápido neste DemBox",
                    on_click=lambda _, cx=c: _abrir_modal_gastar_rapido(page, cx, pacote),
                    content=ft.Row(
                        spacing=3,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_ROUNDED if eh_divida else ft.Icons.REMOVE_ROUNDED, color=T.INFO if eh_divida else T.DESPESA, size=13),
                            ft.Text("Abater" if eh_divida else "Gastar", color=T.INFO if eh_divida else T.DESPESA, size=10.5, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                )
            )

        itens_ui.append(
            ft.Container(
                padding=pad(h=10, v=9),
                bgcolor=T.SURFACE_ALT,
                border_radius=11,
                border=borda(1, f"{cor_c}30" if saldo_c > 0 else T.BORDER),
                on_click=lambda _: navegar(page, ROTA_CAIXINHAS),
                ink=True,
                content=ft.Column(
                    spacing=6,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    expand=True,
                                    controls=[
                                        ft.Container(
                                            padding=pad(all_=6),
                                            bgcolor=f"{cor_c}1F",
                                            border_radius=8,
                                            content=ft.Icon(icone_c, color=cor_c, size=15),
                                        ),
                                        ft.Column(
                                            spacing=2,
                                            expand=True,
                                            controls=[
                                                ft.Row(
                                                    spacing=6,
                                                    wrap=True,
                                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                                    controls=[
                                                        ft.Text(
                                                            nome,
                                                            color=T.TEXT_PRIMARY,
                                                            size=12.5,
                                                            weight=ft.FontWeight.BOLD,
                                                            max_lines=1,
                                                            overflow=ft.TextOverflow.ELLIPSIS,
                                                        ),
                                                        ft.Container(
                                                            padding=pad(h=6, v=1.5),
                                                            bgcolor=f"{pote_cor}18",
                                                            border_radius=6,
                                                            border=borda(1, f"{pote_cor}35"),
                                                            content=ft.Row(
                                                                spacing=3,
                                                                tight=True,
                                                                controls=[
                                                                    ft.Icon(ft.Icons.PIE_CHART_OUTLINE_ROUNDED, size=10, color=pote_cor),
                                                                    ft.Text(pote_nome, color=pote_cor, size=9.5, weight=ft.FontWeight.W_600),
                                                                ],
                                                            ),
                                                        ),
                                                    ],
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Row(
                                    spacing=6,
                                    tight=True,
                                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                    controls=[
                                        ft.Column(
                                            spacing=0,
                                            horizontal_alignment=ft.CrossAxisAlignment.END,
                                            controls=[
                                                ft.Text(
                                                    formatar_moeda(saldo_c),
                                                    color=T.PRIMARY if saldo_c > 0 else T.TEXT_MUTED,
                                                    size=13,
                                                    weight=ft.FontWeight.BOLD,
                                                ),
                                                ft.Text(
                                                    f"de {formatar_moeda(provisionado_c)}",
                                                    color=T.TEXT_MUTED,
                                                    size=10,
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=val_barra,
                            color=cor_barra,
                            bgcolor=T.SURFACE,
                            height=5,
                            border_radius=3,
                        ),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(
                                    txt_rodape_esq,
                                    color=cor_status,
                                    size=10.5,
                                    weight=ft.FontWeight.W_500,
                                ),
                                ft.Row(spacing=5, tight=True, controls=acoes_rapidas_item),
                            ],
                        ),
                    ],
                ),
            )
        )

    resumo_strip = ft.Container(
        padding=pad(h=10, v=8),
        bgcolor=T.SURFACE_ALT,
        border_radius=10,
        on_click=lambda _: navegar(page, ROTA_CAIXINHAS),
        ink=True,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    spacing=1,
                    controls=[
                        ft.Text("Disponível nos DemBoxes", color=T.TEXT_MUTED, size=10),
                        ft.Text(formatar_moeda(tot_saldo), color=T.PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Column(
                    spacing=1,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Consumido", color=T.TEXT_MUTED, size=10),
                        ft.Text(formatar_moeda(tot_gasto), color=T.WARNING, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.Column(
                    spacing=1,
                    horizontal_alignment=ft.CrossAxisAlignment.END,
                    controls=[
                        ft.Text("Total Provisionado", color=T.TEXT_MUTED, size=10),
                        ft.Text(formatar_moeda(tot_meta), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ],
        ),
    )

    corpo = ft.Column(
        spacing=8,
        controls=[
            _barra_empilhada_proporcional(fatias_topo),
            resumo_strip,
            *itens_ui,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=btn_gerenciar_topo,
    )


# =============================================================================
# 2. GRÁFICO: DESPESAS POR CATEGORIA
# =============================================================================
def _render_despesas_categoria(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    bloco = pacote.get("despesas_por_categoria") or {}
    lista = bloco.get("categorias") or []
    total = float(bloco.get("total", 0) or 0)

    if not lista or total <= 0:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Nenhuma despesa registrada neste período."),
            meta["col"],
        )

    fatias = []
    itens_ui = []
    for item in lista[:6]:
        cid = item.get("categoria_id") or item.get("id")
        nome = item.get("categoria") or item.get("nome") or "Outros"
        valor = float(item.get("valor") or item.get("total") or 0)
        cor = item.get("cor") or T.DESPESA
        perc = float(item.get("percentual") or ((valor / total * 100) if total > 0 else 0))
        fatias.append((perc, cor, f"{nome}: {formatar_moeda(valor)} ({perc:.1f}%)"))

        def _abrir_cat(_=None, cat_id=cid):
            if cat_id:
                ctx_cat = ReportContext.from_query(page).com(
                    tipo="Despesa",
                    categoria_id=str(cat_id),
                    origem="dashboard",
                )
                ir_relatorio_categoria(page, str(cat_id), ctx_cat)
            else:
                ir_relatorio_lancamentos(page, tipo="Despesa", origem="dashboard")

        itens_ui.append(
            ft.Container(
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=_abrir_cat,
                ink=True,
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                                        ft.Text(nome, color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                ft.Row(
                                    spacing=6,
                                    controls=[
                                        ft.Text(f"{perc:.1f}%", color=T.TEXT_MUTED, size=11),
                                        ft.Text(formatar_moeda(valor), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.BOLD),
                                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=15),
                                    ],
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, perc / 100.0)),
                            color=cor,
                            bgcolor=f"{T.BORDER}50",
                            height=5,
                            border_radius=3,
                        ),
                    ],
                ),
            )
        )

    badge_total = _chip_acao_header(
        formatar_moeda(total),
        T.DESPESA,
        lambda _: ir_relatorio_lancamentos(page, tipo="Despesa", origem="dashboard"),
    )

    corpo = ft.Column(
        spacing=8,
        controls=[
            _barra_empilhada_proporcional(fatias),
            *itens_ui,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=badge_total,
    )


# =============================================================================
# 3. GRÁFICO: RITMO DIÁRIO NO PERÍODO (HISTOGRAMA VERTICAL CLICÁVEL)
# =============================================================================
def _render_fluxo_diario(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    freq = pacote.get("frequencia_diaria") or []
    if not freq:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Sem movimentações diárias no período selecionado.", ft.Icons.BAR_CHART_ROUNDED),
            meta["col"],
        )

    est_p = obter_estado_periodo_atual(page)
    dt_base_fim: date = est_p["data_fim"]

    # Limita aos últimos 14 dias com movimento para caber perfeitamente em telas mobile
    amostra = freq[-14:]
    max_val = max(
        [max(float(d.get("despesas", 0) or 0), float(d.get("receitas", 0) or 0)) for d in amostra] + [1.0]
    )

    total_desp_periodo = sum(float(d.get("despesas", 0) or 0) for d in freq)
    maior_dia = max(freq, key=lambda d: float(d.get("despesas", 0) or 0))
    maior_gasto = float(maior_dia.get("despesas", 0) or 0)
    media_dia = total_desp_periodo / max(1, len(freq))

    def _resolver_data_item(item_d: dict) -> date:
        dt_raw = item_d.get("data")
        if dt_raw:
            try:
                return date.fromisoformat(str(dt_raw)[:10])
            except Exception:
                pass
        dia_num = int(item_d.get("dia", dt_base_fim.day) or dt_base_fim.day)
        ultimo_d = calendar.monthrange(dt_base_fim.year, dt_base_fim.month)[1]
        return date(dt_base_fim.year, dt_base_fim.month, min(max(1, dia_num), ultimo_d))

    colunas_barras = []
    ALTURA_MAX = 110

    for item in amostra:
        desp = float(item.get("despesas", 0) or 0)
        rec = float(item.get("receitas", 0) or 0)
        lbl = item.get("label") or f"{int(item.get('dia', 1)):02d}"
        dt_alvo = _resolver_data_item(item)

        h_desp = max(4, int((desp / max_val) * ALTURA_MAX)) if desp > 0 else 3
        h_rec = max(4, int((rec / max_val) * ALTURA_MAX)) if rec > 0 else 3

        dica = (
            f"Dia {lbl} (clique para ver lançamentos)\n"
            f"Saídas: {formatar_moeda(desp)}\n"
            f"Entradas: {formatar_moeda(rec)}"
        )

        def _abrir_dia(_=None, d_sel=dt_alvo):
            ctx_dia = ReportContext(
                data_inicio=d_sel,
                data_fim=d_sel,
                origem="dashboard",
            )
            ir_relatorio_lancamentos(page, ctx=ctx_dia)

        colunas_barras.append(
            ft.Container(
                expand=True,
                border_radius=6,
                on_click=_abrir_dia,
                ink=True,
                tooltip=dica,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.END,
                    spacing=4,
                    controls=[
                        ft.Container(
                            height=ALTURA_MAX + 6,
                            alignment=ft.Alignment(0, 1),
                            content=ft.Row(
                                spacing=2,
                                tight=True,
                                vertical_alignment=ft.CrossAxisAlignment.END,
                                controls=[
                                    ft.Container(
                                        width=7,
                                        height=h_rec,
                                        bgcolor=T.RECEITA if rec > 0 else f"{T.BORDER}40",
                                        border_radius=3,
                                        animate=ft.Animation(300, ft.AnimationCurve.DECELERATE),
                                    ),
                                    ft.Container(
                                        width=7,
                                        height=h_desp,
                                        bgcolor=T.DESPESA if desp > 0 else f"{T.BORDER}40",
                                        border_radius=3,
                                        animate=ft.Animation(300, ft.AnimationCurve.DECELERATE),
                                    ),
                                ],
                            ),
                        ),
                        ft.Text(
                            str(lbl).split("/")[0],
                            color=T.TEXT_MUTED,
                            size=10,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                ),
            )
        )

    dt_pico = _resolver_data_item(maior_dia)

    resumo_inferior = ft.Row(
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        controls=[
            ft.Container(
                expand=True,
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=lambda _: ir_relatorio_lancamentos(page, tipo="Despesa", origem="dashboard"),
                ink=True,
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Média / Dia Ativo", color=T.TEXT_MUTED, size=10),
                        ft.Text(formatar_moeda(media_dia), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ),
            ft.Container(
                expand=True,
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=lambda _: ir_relatorio_lancamentos(
                    page,
                    ctx=ReportContext(data_inicio=dt_pico, data_fim=dt_pico, tipo="Despesa", origem="dashboard"),
                ),
                ink=True,
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Pico de Saída", color=T.TEXT_MUTED, size=10),
                        ft.Text(formatar_moeda(maior_gasto), color=T.DESPESA, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ),
            ft.Container(
                expand=True,
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=lambda _: ir_relatorio_lancamentos(page, origem="dashboard"),
                ink=True,
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Text("Dias Movimentados", color=T.TEXT_MUTED, size=10),
                        ft.Text(f"{len(freq)} dias", color=T.INFO, size=12.5, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ),
        ],
    )

    corpo = ft.Column(
        spacing=12,
        controls=[
            ft.Container(
                padding=pad(h=8, v=10),
                bgcolor=T.SURFACE_ALT,
                border_radius=12,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                    controls=colunas_barras,
                ),
            ),
            resumo_inferior,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=_chip_acao_header("Extrato", T.INFO, lambda _: ir_relatorio_lancamentos(page, origem="dashboard")),
    )


# =============================================================================
# 4. GRÁFICO: EVOLUÇÃO MENSAL (6 MESES)
# =============================================================================
def _render_balanco_semestral(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    balanco = pacote.get("balanco_6_meses") or []
    if not balanco:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Histórico semestral ainda sem lançamentos pagos."),
            meta["col"],
        )

    max_v = max(
        [max(float(m.get("receitas", 0) or 0), float(m.get("despesas", 0) or 0)) for m in balanco] + [1.0]
    )

    linhas = []
    for m in balanco[-6:]:
        mes_num = int(m.get("mes", 0) or 0)
        ano_num = int(m.get("ano", 0) or 0)
        lbl = m.get("label") or f"{mes_num:02d}/{ano_num}"
        rec = float(m.get("receitas", 0) or 0)
        desp = float(m.get("despesas", 0) or 0)
        saldo = rec - desp
        cor_saldo = T.RECEITA if saldo >= 0 else T.DESPESA

        def _abrir_mes(_=None, mm=mes_num, aa=ano_num):
            if 1 <= mm <= 12 and aa >= 2000:
                d1 = date(aa, mm, 1)
                d2 = date(aa, mm, calendar.monthrange(aa, mm)[1])
                ir_relatorio_lancamentos(
                    page,
                    ctx=ReportContext(data_inicio=d1, data_fim=d2, origem="dashboard"),
                )
            else:
                ir_relatorio_fluxo(page)

        linhas.append(
            ft.Container(
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=_abrir_mes,
                ink=True,
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=4,
                                    controls=[
                                        ft.Text(lbl, color=T.TEXT_PRIMARY, size=12, weight=ft.FontWeight.BOLD),
                                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=14),
                                    ],
                                ),
                                ft.Row(
                                    spacing=10,
                                    controls=[
                                        ft.Text(f"+{formatar_moeda(rec)}", color=T.RECEITA, size=11),
                                        ft.Text(f"-{formatar_moeda(desp)}", color=T.DESPESA, size=11),
                                        ft.Container(
                                            padding=pad(h=6, v=2),
                                            bgcolor=f"{cor_saldo}1A",
                                            border_radius=6,
                                            content=ft.Text(
                                                formatar_moeda(saldo),
                                                color=cor_saldo,
                                                size=11,
                                                weight=ft.FontWeight.BOLD,
                                            ),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, rec / max_v)),
                            color=T.RECEITA,
                            bgcolor=f"{T.BORDER}40",
                            height=4,
                            border_radius=2,
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, desp / max_v)),
                            color=T.DESPESA,
                            bgcolor=f"{T.BORDER}40",
                            height=4,
                            border_radius=2,
                        ),
                    ],
                ),
            )
        )

    corpo = ft.Column(spacing=8, controls=linhas)
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=_chip_acao_header("Comparativo", "#8B5CF6", lambda _: ir_relatorio_fluxo(page)),
    )


# =============================================================================
# 5. GRÁFICO: FONTES DE RECEITA POR CATEGORIA
# =============================================================================
def _render_receitas_categoria(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    bloco = pacote.get("receitas_por_categoria") or {}
    lista = bloco.get("categorias") or []
    total = float(bloco.get("total", 0) or 0)

    if not lista or total <= 0:
        return _card_base_grafico(
            meta["titulo"],
            meta["subtitulo"],
            meta["icone"],
            meta["cor"],
            _estado_vazio("Nenhuma receita registrada no período selecionado."),
            meta["col"],
        )

    fatias = []
    itens_ui = []
    for item in lista[:6]:
        cid = item.get("categoria_id") or item.get("id")
        nome = item.get("categoria") or item.get("nome") or "Outros"
        valor = float(item.get("valor") or item.get("total") or 0)
        cor = item.get("cor") or T.RECEITA
        perc = float(item.get("percentual") or ((valor / total * 100) if total > 0 else 0))
        fatias.append((perc, cor, f"{nome}: {formatar_moeda(valor)} ({perc:.1f}%)"))

        def _abrir_cat_rec(_=None, cat_id=cid):
            if cat_id:
                ctx_cat = ReportContext.from_query(page).com(
                    tipo="Receita",
                    categoria_id=str(cat_id),
                    origem="dashboard",
                )
                ir_relatorio_categoria(page, str(cat_id), ctx_cat)
            else:
                ir_relatorio_lancamentos(page, tipo="Receita", origem="dashboard")

        itens_ui.append(
            ft.Container(
                padding=pad(h=10, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=_abrir_cat_rec,
                ink=True,
                content=ft.Column(
                    spacing=5,
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.Container(width=10, height=10, bgcolor=cor, border_radius=5),
                                        ft.Text(nome, color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                ft.Row(
                                    spacing=6,
                                    controls=[
                                        ft.Text(f"{perc:.1f}%", color=T.TEXT_MUTED, size=11),
                                        ft.Text(formatar_moeda(valor), color=T.RECEITA, size=12.5, weight=ft.FontWeight.BOLD),
                                        ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=15),
                                    ],
                                ),
                            ],
                        ),
                        ft.ProgressBar(
                            value=min(1.0, max(0.0, perc / 100.0)),
                            color=cor,
                            bgcolor=f"{T.BORDER}50",
                            height=5,
                            border_radius=3,
                        ),
                    ],
                ),
            )
        )

    badge_total = _chip_acao_header(
        formatar_moeda(total),
        T.RECEITA,
        lambda _: ir_relatorio_lancamentos(page, tipo="Receita", origem="dashboard"),
    )

    corpo = ft.Column(
        spacing=8,
        controls=[
            _barra_empilhada_proporcional(fatias),
            *itens_ui,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=badge_total,
    )


# =============================================================================
# 6. GRÁFICO: MEIOS DE PAGAMENTO & SAÚDE DOS CARTÕES
# =============================================================================
def _render_formas_e_cartoes(page: ft.Page, pacote: dict, meta: dict) -> ft.Container:
    formas = pacote.get("despesas_por_forma") or []
    resumo_cartoes = pacote.get("resumo_cartoes") or {}

    limite_total = float(resumo_cartoes.get("total_limite", 0) or 0)
    disponivel = float(resumo_cartoes.get("total_disponivel", 0) or 0)
    usado_cartao = max(0.0, limite_total - disponivel)
    pct_cartao = (usado_cartao / limite_total) if limite_total > 0 else 0.0

    cores_forma = {
        "Pix": "#10B981",
        "Crédito": "#F59E0B",
        "Débito": "#3B82F6",
        "Dinheiro": "#22C55E",
        "Boleto": "#8B5CF6",
        "Transferência": "#06B6D4",
    }

    bloco_cartao = ft.Container(
        padding=pad(h=12, v=10),
        bgcolor=T.SURFACE_ALT,
        border_radius=12,
        on_click=lambda _: ir_cartoes(page),
        ink=True,
        content=ft.Column(
            spacing=6,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color=T.WARNING, size=16),
                                ft.Text("Limite Consolidado de Cartões", color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        ft.Row(
                            spacing=4,
                            controls=[
                                ft.Text(f"{pct_cartao * 100:.1f}% em uso", color=T.WARNING, size=11.5, weight=ft.FontWeight.BOLD),
                                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=15),
                            ],
                        ),
                    ],
                ),
                ft.ProgressBar(
                    value=min(1.0, max(0.0, pct_cartao)),
                    color=T.DESPESA if pct_cartao > 0.8 else T.WARNING,
                    bgcolor=f"{T.BORDER}50",
                    height=6,
                    border_radius=4,
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text(f"Disponível: {formatar_moeda(disponivel)}", color=T.RECEITA, size=11),
                        ft.Text(f"Limite: {formatar_moeda(limite_total)}", color=T.TEXT_MUTED, size=11),
                    ],
                ),
            ],
        ),
    )

    itens_formas = []
    for f in formas[:5]:
        nome_f = f.get("forma") or "Outros"
        val_f = float(f.get("valor", 0) or 0)
        qtd_f = int(f.get("qtd", 0) or 0)
        perc_f = float(f.get("percentual", 0) or 0)
        cor_f = cores_forma.get(nome_f, T.PRIMARY)

        itens_formas.append(
            ft.Container(
                padding=pad(h=10, v=7),
                bgcolor=T.SURFACE_ALT,
                border_radius=10,
                on_click=lambda _, nf=nome_f: ir_relatorio_lancamentos(
                    page,
                    tipo="Despesa",
                    forma=nf,
                    origem="dashboard",
                ),
                ink=True,
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=8,
                            controls=[
                                ft.Container(width=8, height=8, bgcolor=cor_f, border_radius=4),
                                ft.Text(nome_f, color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.W_500),
                                ft.Text(f"({qtd_f}x)", color=T.TEXT_MUTED, size=11),
                            ],
                        ),
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Text(f"{perc_f:.1f}%", color=T.TEXT_MUTED, size=11),
                                ft.Text(formatar_moeda(val_f), color=T.TEXT_PRIMARY, size=12.5, weight=ft.FontWeight.BOLD),
                                ft.Icon(ft.Icons.CHEVRON_RIGHT_ROUNDED, color=T.TEXT_MUTED, size=15),
                            ],
                        ),
                    ],
                ),
            )
        )

    if not itens_formas:
        itens_formas.append(
            ft.Text("Sem despesas por modalidade neste período.", color=T.TEXT_MUTED, size=12)
        )

    corpo = ft.Column(
        spacing=8,
        controls=[
            bloco_cartao,
            ft.Text("Saídas por Modalidade no Período", color=T.TEXT_MUTED, size=11, weight=ft.FontWeight.W_600),
            *itens_formas,
        ],
    )
    return _card_base_grafico(
        meta["titulo"],
        meta["subtitulo"],
        meta["icone"],
        meta["cor"],
        corpo,
        meta["col"],
        acao_extra=_chip_acao_header("Cartões", T.WARNING, lambda _: ir_cartoes(page)),
    )


_RENDERERS = {
    "minhas_caixinhas": _render_minhas_caixinhas,
    "regra_5030": _render_minhas_caixinhas,
    "despesas_categoria": _render_despesas_categoria,
    "fluxo_diario": _render_fluxo_diario,
    "balanco_semestral": _render_balanco_semestral,
    "receitas_categoria": _render_receitas_categoria,
    "formas_e_cartoes": _render_formas_e_cartoes,
}


def construir_grid_graficos(
    page: ft.Page,
    pacote_dados: dict,
    ids_ativos: list[str] | None = None,
) -> list[ft.Control]:
    """
    Constrói dinamicamente a lista de cards de gráficos habilitados pelo usuário
    para popular o ft.ResponsiveRow do Dashboard.
    """
    ativos = ids_ativos if ids_ativos is not None else GRAFICOS_PADRAO_IDS
    catalogo_map = {item["id"]: item for item in DASHBOARD_CHARTS_CATALOG}

    cards: list[ft.Control] = []
    for cid in ativos:
        meta = catalogo_map.get(cid)
        renderer = _RENDERERS.get(cid)
        if meta and renderer:
            cards.append(renderer(page, pacote_dados, meta))
    return cards
