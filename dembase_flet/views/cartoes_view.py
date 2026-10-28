"""
=============================================================================
DemBase v3 — views/cartoes_view.py  (Flet 1.0.1)
Dashboard Inteligente de Cartões de Crédito, Limites e Gestão Inline de Faturas:
1. Ordem das Abas & Estado Padrão:
   - 1º "Meus Cartões" (Default ao abrir), 2º "Faturas Abertas", 3º "Faturas Fechadas".
2. Sincronização Estrita de Filtro de Mês/Ano:
   - "Faturas Abertas" e "Faturas Fechadas" respeitam rigorosamente o período global.
   - Não lista faturas de meses futuros/passados fora do mês/ano filtrado.
3. Cards Superiores Dinâmicos:
   - "Limite Total", "Limite Disponível", "Faturas Abertas" e "Faturas do Filtro".
4. Ordenação Inteligente & Recomendação de Compra:
   - Cálculo automático do melhor cartão para compras hoje (maior prazo de folga).
   - Banner de destaque com contagem regressiva e indicação de vencimento.
   - Melhor cartão no topo com badge especial.
5. Baixa em Lote Inline ("PAGAR FATURA"):
   - Modal com seleção de conta bancária de débito, verificação de saldo e baixa transacional.
=============================================================================
"""
from __future__ import annotations

import asyncio
import calendar
from datetime import date, datetime
import flet as ft

from core import theme as T
from core.theme import pad, borda, mostrar_feedback, abrir_dialogo, fechar_dialogo
from core.constants import formatar_moeda, formatar_data_br
from core.periodo import obter_estado_periodo_atual
from core.nav import ir_cartao, ir_relatorio_lancamentos
from core.report_context import ReportContext
from core.responsive import is_mobile
from views.shell_view import criar_shell, ROTA_CARTOES
from views.widgets.clickable_card import kpi_clicavel
import services.supabase_client as db

BANDEIRAS_OPCOES = [
    ("mastercard", "Mastercard"),
    ("visa", "Visa"),
    ("elo", "Elo"),
    ("amex", "American Express"),
    ("hipercard", "Hipercard"),
    ("outro", "Outra"),
]
LABELS_BANDEIRAS = dict(BANDEIRAS_OPCOES)

CORES_CARTOES = [
    {"label": "Roxo Nubank",   "hex": "#820AD1"},
    {"label": "Laranja Inter", "hex": "#FF7A00"},
    {"label": "Azul Escuro",   "hex": "#0F172A"},
    {"label": "Dourado Black", "hex": "#1E293B"},
    {"label": "Esmeralda",     "hex": "#10B981"},
    {"label": "Vermelho",      "hex": "#DC2626"},
    {"label": "Azul Itaú",     "hex": "#003399"},
]

MESES_NOMES = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
MESES_ABREV = [
    "", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez"
]


def calcular_detalhes_fechamento(cartao: dict, hoje: date | None = None) -> dict:
    """
    Calcula para o cartão:
    - dt_fech: data do próximo fechamento (virada da fatura)
    - dt_venc: data do vencimento correspondente às compras feitas hoje
    - dias_fech: dias até a virada
    - dias_venc: prazo total em dias até o pagamento (folga financeira)
    - virou_hoje: booleano indicando se a virada ocorreu exatamente hoje
    """
    if hoje is None:
        hoje = date.today()

    dia_fech = int(cartao.get("dia_fechamento") or 1)
    dia_venc = int(cartao.get("dia_vencimento") or 10)

    ano_fech = hoje.year
    mes_fech = hoje.month

    # Se hoje é >= dia de fechamento, a fatura atual já fechou!
    # Compras de hoje caem na fatura do próximo mês (máximo prazo de pagamento).
    if hoje.day >= dia_fech:
        if mes_fech == 12:
            mes_fech = 1
            ano_fech += 1
        else:
            mes_fech += 1

    ultimo_dia_fech = calendar.monthrange(ano_fech, mes_fech)[1]
    dt_fech = date(ano_fech, mes_fech, min(dia_fech, ultimo_dia_fech))
    dias_fech = (dt_fech - hoje).days

    ano_venc = ano_fech
    mes_venc = mes_fech
    if dia_venc <= dia_fech:
        if mes_venc == 12:
            mes_venc = 1
            ano_venc += 1
        else:
            mes_venc += 1

    ultimo_dia_venc = calendar.monthrange(ano_venc, mes_venc)[1]
    dt_venc = date(ano_venc, mes_venc, min(dia_venc, ultimo_dia_venc))
    dias_venc = (dt_venc - hoje).days

    return {
        "dt_fech": dt_fech,
        "dt_venc": dt_venc,
        "dias_fech": max(0, dias_fech),
        "dias_venc": max(0, dias_venc),
        "virou_hoje": hoje.day == dia_fech,
    }


def calcular_melhor_cartao(cartoes: list[dict], hoje: date | None = None) -> tuple[dict | None, dict | None]:
    """
    Identifica o cartão com maior prazo de folga até o vencimento (compras feitas hoje).
    Critério de desempate: maior limite disponível.
    """
    if not cartoes:
        return None, None

    if hoje is None:
        hoje = date.today()

    melhor_cartao = None
    melhor_info = None

    for c in cartoes:
        info = calcular_detalhes_fechamento(c, hoje)
        lim_disp = float(c.get("limite_disponivel", c.get("limite_total", 0)) or 0)

        if melhor_info is None:
            melhor_cartao = c
            melhor_info = info
        else:
            # Compara prazo em dias
            if info["dias_venc"] > melhor_info["dias_venc"]:
                melhor_cartao = c
                melhor_info = info
            elif info["dias_venc"] == melhor_info["dias_venc"]:
                # Desempate por limite disponível
                lim_melhor = float(melhor_cartao.get("limite_disponivel", melhor_cartao.get("limite_total", 0)) or 0)
                if lim_disp > lim_melhor:
                    melhor_cartao = c
                    melhor_info = info

    return melhor_cartao, melhor_info


def formatar_status_vencimento(
    dt_venc: date | None,
    status: str = "Aberta",
    valor_pendente: float = 0.0,
) -> tuple[str, str, str]:
    """
    Retorna (texto, cor_texto, cor_fundo) para badge visual de vencimento.
    - Se a fatura estiver paga: 'Paga' (Verde).
    - Se o valor pendente for R$ 0,00 (sem débito): 'Zerada' (Neutro), NUNCA 'Vencida'.
    - Se tiver valor pendente e data ultrapassada: 'Vencida (Xd)' (Vermelho).
    - Se tiver valor pendente e vencer no dia/futuro: 'Vence Hoje', 'Vence Amanhã', etc.
    """
    if str(status).lower() == "paga":
        return ("Paga", T.RECEITA, ft.Colors.with_opacity(0.12, T.RECEITA))

    if valor_pendente <= 0.01:
        return ("Zerada", T.TEXT_MUTED, ft.Colors.with_opacity(0.08, T.SURFACE_ALT))

    if not dt_venc:
        return ("Pendente", T.TEXT_MUTED, ft.Colors.with_opacity(0.08, T.SURFACE_ALT))

    hoje = date.today()
    diff = (dt_venc - hoje).days

    if diff < 0:
        dias_atr = abs(diff)
        return (f"Vencida ({dias_atr}d)", ft.Colors.WHITE, T.DESPESA)
    elif diff == 0:
        return ("Vence Hoje!", ft.Colors.WHITE, T.WARNING)
    elif diff == 1:
        return ("Vence Amanhã", T.WARNING, ft.Colors.with_opacity(0.15, T.WARNING))
    elif diff <= 5:
        return (f"Vence em {diff} dias", T.WARNING, ft.Colors.with_opacity(0.12, T.WARNING))
    else:
        return (f"Vence {dt_venc.strftime('%d/%m')}", T.TEXT_MUTED, ft.Colors.with_opacity(0.08, T.SURFACE_ALT))


def criar_view_cartoes(
    page: ft.Page,
    match: dict | None = None,
    ctx: ReportContext | None = None,
) -> ft.View:
    mobile = is_mobile(page)
    est_p = obter_estado_periodo_atual(page)
    mes_sel = [int(est_p.get("mes") or date.today().month)]
    ano_sel = [int(est_p.get("ano") or date.today().year)]
    ult_init = calendar.monthrange(ano_sel[0], mes_sel[0])[1]
    di_raw = est_p.get("data_inicio")
    df_raw = est_p.get("data_fim")
    data_ini_sel = [
        di_raw.isoformat() if isinstance(di_raw, date)
        else (str(di_raw)[:10] if di_raw else date(ano_sel[0], mes_sel[0], 1).isoformat())
    ]
    data_fim_sel = [
        df_raw.isoformat() if isinstance(df_raw, date)
        else (str(df_raw)[:10] if df_raw else date(ano_sel[0], mes_sel[0], ult_init).isoformat())
    ]
    txt_sub_periodo_cartoes = ft.Text(
        f"Período ativo: {formatar_data_br(data_ini_sel[0])} a {formatar_data_br(data_fim_sel[0])} · "
        "Gerencie limites, identifique o melhor cartão e liquide faturas",
        color=T.TEXT_MUTED,
        size=12,
        max_lines=2,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    cartoes_lista: list[dict] = []
    faturas_lista: list[dict] = []
    faturas_prox_lista: list[dict] = []
    resumo_periodo: dict = {}
    # Regra 1: O estado padrão (default) ao carregar deve ser obrigatoriamente "Meus Cartões"
    aba_ativa: list[str] = ["cartoes"]

    spinner = ft.ProgressRing(color=T.PRIMARY, width=20, height=20, stroke_width=2, visible=False)

    tam_kpi = 15 if mobile else 18
    txt_total_limite     = ft.Text("R$ 0,00", color=T.TEXT_PRIMARY, size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_disponivel = ft.Text("R$ 0,00", color=T.PRIMARY,      size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_total_faturas    = ft.Text("R$ 0,00", color=T.WARNING,      size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
    txt_faturas_filtro   = ft.Text("R$ 0,00", color=T.INFO,         size=tam_kpi, weight=ft.FontWeight.BOLD, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)

    # Banner Inteligente de Destaque
    cnt_banner_melhor = ft.Container(visible=False)

    # Grade principal de conteúdo
    grid_conteudo = ft.ResponsiveRow(spacing=14, run_spacing=14, controls=[])

    def _safe_update():
        try:
            txt_total_limite.update()
            txt_total_disponivel.update()
            txt_total_faturas.update()
            txt_faturas_filtro.update()
            cnt_banner_melhor.update()
            grid_conteudo.update()
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass

    def _mudar_aba(nova_aba: str):
        aba_ativa[0] = nova_aba
        try:
            seg_aba.selected = [nova_aba]
            seg_aba.update()
        except Exception:
            pass
        renderizar_conteudo()
        _safe_update()

    # ── Segmented Button de Navegação Inline ─────────────────────────────────
    # Regra 1: Ordem visual da esquerda para a direita:
    # 1º "Meus Cartões", 2º "Faturas Abertas", 3º "Faturas Fechadas"
    seg_aba = ft.SegmentedButton(
        segments=[
            ft.Segment(
                value="cartoes",
                label=ft.Text("Meus Cartões", size=12 if mobile else 13, weight=ft.FontWeight.BOLD),
                icon=ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, size=16, color=T.PRIMARY),
            ),
            ft.Segment(
                value="abertas",
                label=ft.Text("Faturas Abertas", size=12 if mobile else 13, weight=ft.FontWeight.BOLD),
                icon=ft.Icon(ft.Icons.PENDING_ACTIONS_ROUNDED, size=16, color=T.WARNING),
            ),
            ft.Segment(
                value="fechadas",
                label=ft.Text("Faturas Fechadas", size=12 if mobile else 13, weight=ft.FontWeight.BOLD),
                icon=ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=16, color=T.RECEITA),
            ),
        ],
        selected=["cartoes"],
        allow_multiple_selection=False,
        allow_empty_selection=False,
        on_change=lambda e: _mudar_aba(e.control.selected[0] if getattr(e.control, "selected", None) else "cartoes"),
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
    )

    # ── Carregar Dados ────────────────────────────────────────────────────────
    def carregar_cartoes(inicial: bool = False, forcar: bool = False):
        if not inicial:
            spinner.visible = True
            _safe_update()

        nonlocal cartoes_lista, faturas_lista, faturas_prox_lista, resumo_periodo
        try:
            cartoes_lista = db.listar_cartoes(forcar_atualizacao=forcar or not inicial)

            # Regra 2: Carrega faturas estritamente para o mês/ano e período filtrado
            try:
                faturas_brutas = db.listar_faturas(mes=mes_sel[0], ano=ano_sel[0])
            except Exception as ex_fat:
                print(f"[CartoesView] Aviso ao listar faturas filtradas: {ex_fat}")
                faturas_brutas = []

            # Regra 3: Carrega prévia da 1ª semana do mês seguinte (vencimentos dias 01 a 07)
            mes_prox = 1 if mes_sel[0] == 12 else mes_sel[0] + 1
            ano_prox = ano_sel[0] + 1 if mes_sel[0] == 12 else ano_sel[0]
            try:
                faturas_prox_brutas = db.listar_faturas(mes=mes_prox, ano=ano_prox)
            except Exception as ex_prox:
                print(f"[CartoesView] Aviso ao listar faturas do próximo mês: {ex_prox}")
                faturas_prox_brutas = []

            faturas_prox_filtradas = []
            for fp in faturas_prox_brutas:
                dv_raw = str(fp.get("data_vencimento") or "")[:10]
                incluir_p = False
                if dv_raw:
                    try:
                        dv_dt = date.fromisoformat(dv_raw)
                        if dv_dt.year == ano_prox and dv_dt.month == mes_prox and 1 <= dv_dt.day <= 7:
                            incluir_p = True
                    except Exception:
                        pass
                else:
                    c_ref = next((c for c in cartoes_lista if str(c.get("id")) == str(fp.get("cartao_id"))), None)
                    if c_ref:
                        dia_v = int(c_ref.get("dia_vencimento") or 10)
                        if 1 <= dia_v <= 7:
                            incluir_p = True

                if incluir_p:
                    st_p = str(fp.get("status") or "").lower()
                    v_tot_p = float(fp.get("valor_total", 0) or 0)
                    v_pg_p = float(fp.get("valor_pago", 0) or 0)
                    if st_p != "paga" and (v_tot_p - v_pg_p) > 0.01:
                        faturas_prox_filtradas.append(fp)

            faturas_prox_lista = faturas_prox_filtradas

            ult_mes_atual = calendar.monthrange(ano_sel[0], mes_sel[0])[1]
            ini_mes_iso = date(ano_sel[0], mes_sel[0], 1).isoformat()
            fim_mes_iso = date(ano_sel[0], mes_sel[0], ult_mes_atual).isoformat()
            eh_periodo_parcial = (data_ini_sel[0] != ini_mes_iso or data_fim_sel[0] != fim_mes_iso)

            if eh_periodo_parcial:
                try:
                    d_i_dt = date.fromisoformat(data_ini_sel[0][:10])
                    d_f_dt = date.fromisoformat(data_fim_sel[0][:10])
                except Exception:
                    d_i_dt = date(ano_sel[0], mes_sel[0], 1)
                    d_f_dt = date(ano_sel[0], mes_sel[0], ult_mes_atual)

                mapa_cartoes_id = {str(c.get("id")): c for c in cartoes_lista}
                filtradas_faixa = []
                for f_item in faturas_brutas:
                    dv_raw = str(f_item.get("data_vencimento") or "")[:10]
                    incluir = False
                    if dv_raw:
                        try:
                            dv_dt = date.fromisoformat(dv_raw)
                            if d_i_dt <= dv_dt <= d_f_dt:
                                incluir = True
                            elif d_i_dt.month == d_f_dt.month and (d_i_dt.day <= dv_dt.day <= d_f_dt.day):
                                incluir = True
                        except Exception:
                            pass
                    else:
                        c_ref = mapa_cartoes_id.get(str(f_item.get("cartao_id"))) or {}
                        dia_v = int(c_ref.get("dia_vencimento") or 10)
                        if d_i_dt.day <= dia_v <= d_f_dt.day:
                            incluir = True
                    if incluir:
                        filtradas_faixa.append(f_item)
                faturas_lista = filtradas_faixa
            else:
                faturas_lista = faturas_brutas

            txt_sub_periodo_cartoes.value = (
                f"Período ativo: {formatar_data_br(data_ini_sel[0])} a {formatar_data_br(data_fim_sel[0])} · "
                "Gerencie limites, identifique o melhor cartão e liquide faturas"
            )

            resumo_periodo = {}
            try:
                resumo_periodo = db.obter_resumo_cartoes(mes_sel[0], ano_sel[0])
            except Exception:
                pass

            total_limite = sum(float(c.get("limite_total", 0) or 0) for c in cartoes_lista)
            total_disp   = sum(float(c.get("limite_disponivel", c.get("limite_total", 0)) or 0) for c in cartoes_lista)

            # Faturas Abertas: soma estrita de pendências das faturas abertas do período filtrado
            total_fat = sum(
                max(0.0, float(f.get("valor_total", 0) or 0) - float(f.get("valor_pago", 0) or 0))
                for f in faturas_lista
                if int(f.get("mes") or 0) == mes_sel[0] and int(f.get("ano") or 0) == ano_sel[0]
                and str(f.get("status", "")).lower() != "paga"
                and float(f.get("valor_total", 0) or 0) > 0.01
            )

            # Faturas do Filtro: soma de todos os gastos em fatura do período filtrado
            total_faturas_filtro = sum(
                float(f.get("valor_total", 0) or 0)
                for f in faturas_lista
                if int(f.get("mes") or 0) == mes_sel[0] and int(f.get("ano") or 0) == ano_sel[0]
            )
            if total_faturas_filtro == 0.0 and resumo_periodo.get("cartoes"):
                for cr in resumo_periodo["cartoes"]:
                    total_faturas_filtro += float(cr.get("fatura_valor", 0) or 0)

            txt_total_limite.value     = formatar_moeda(float(total_limite or 0))
            txt_total_disponivel.value = formatar_moeda(float(total_disp or 0))
            txt_total_faturas.value    = formatar_moeda(float(total_fat or 0))
            txt_faturas_filtro.value   = formatar_moeda(float(total_faturas_filtro or 0))

            atualizar_banner_melhor_cartao()
            renderizar_conteudo()
        except Exception as ex:
            if not inicial:
                mostrar_feedback(page, f"Erro ao listar cartões e faturas: {ex}", "erro")
        finally:
            spinner.visible = False
            _safe_update()

    # ── Banner de Destaque: O Melhor Cartão para Compras Hoje ─────────────────
    def atualizar_banner_melhor_cartao():
        if not cartoes_lista:
            cnt_banner_melhor.visible = False
            return

        hoje = date.today()
        melhor_c, melhor_info = calcular_melhor_cartao(cartoes_lista, hoje)
        if not melhor_c or not melhor_info:
            cnt_banner_melhor.visible = False
            return

        nome_c = melhor_c.get("nome", "Cartão")
        dias_fech = melhor_info["dias_fech"]
        dias_prazo = melhor_info["dias_venc"]
        dt_fech_str = melhor_info["dt_fech"].strftime("%d/%m")
        dt_venc_str = melhor_info["dt_venc"].strftime("%d/%m")
        mes_fatura_nome = MESES_NOMES[melhor_info["dt_venc"].month]

        texto_fechamento = (
            f"virou hoje! "
            if melhor_info["virou_hoje"]
            else f"fecha em {dias_fech} dia{'s' if dias_fech != 1 else ''} ({dt_fech_str}) "
        )

        cnt_banner_melhor.content = ft.Container(
            padding=pad(all_=14 if mobile else 16),
            bgcolor=ft.Colors.with_opacity(0.08, T.PRIMARY),
            border=borda(1.5, T.PRIMARY),
            border_radius=14,
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        padding=pad(all_=10),
                        bgcolor=ft.Colors.with_opacity(0.18, T.PRIMARY),
                        border_radius=10,
                        content=ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=T.PRIMARY, size=24),
                    ),
                    ft.Column(
                        spacing=3,
                        expand=True,
                        controls=[
                            ft.Row(
                                spacing=8,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                wrap=True,
                                controls=[
                                    ft.Text(
                                        f"O melhor cartão para comprar hoje é o {nome_c}",
                                        color=T.TEXT_PRIMARY,
                                        size=14 if mobile else 15.5,
                                        weight=ft.FontWeight.BOLD,
                                    ),
                                    ft.Container(
                                        padding=pad(h=8, v=2.5),
                                        bgcolor=T.PRIMARY,
                                        border_radius=6,
                                        content=ft.Text(
                                            f"+{dias_prazo} dias de prazo",
                                            color=ft.Colors.WHITE,
                                            size=11,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ),
                                ],
                            ),
                            ft.Text(
                                f"A fatura {texto_fechamento}e o vencimento será em {dt_venc_str}. "
                                f"Compras realizadas hoje só vencem na fatura de {mes_fatura_nome}.",
                                color=T.TEXT_MUTED,
                                size=11.5 if mobile else 12.5,
                            ),
                        ],
                    ),
                ],
            ),
        )
        cnt_banner_melhor.visible = True

    # ── Modal de Pagamento de Fatura (Liquidação em Lote) ────────────────────
    def abrir_modal_pagar_fatura(fatura: dict, cartao: dict):
        try:
            contas = db.listar_contas()
        except Exception:
            contas = []

        if not contas:
            mostrar_feedback(page, "Cadastre ao menos uma conta bancária antes de pagar a fatura.", "aviso")
            return

        valor_pendente = float(fatura.get("valor_pendente") or 0)
        if valor_pendente <= 0:
            val_tot = float(fatura.get("valor_total", 0) or 0)
            val_pg  = float(fatura.get("valor_pago", 0) or 0)
            valor_pendente = max(0.0, val_tot - val_pg)

        if valor_pendente <= 0:
            mostrar_feedback(page, "Esta fatura já está quitada ou não possui saldo pendente.", "aviso")
            return

        opcoes_contas: list[ft.dropdown.Option] = []
        conta_pref = cartao.get("conta_debito_id")
        conta_inicial = None

        for ct in contas:
            cid = str(ct.get("id"))
            nome = ct.get("nome", "Conta")
            banco = ct.get("banco") or ""
            saldo = float(ct.get("saldo_atual", 0) or 0)
            desc_saldo = f"Saldo: {formatar_moeda(saldo)}"
            rotulo = f"{nome} ({desc_saldo})" if not banco else f"{nome} · {banco} ({desc_saldo})"
            opcoes_contas.append(ft.dropdown.Option(key=cid, text=rotulo))
            if conta_pref and cid == str(conta_pref):
                conta_inicial = cid
            elif not conta_inicial and saldo >= valor_pendente:
                conta_inicial = cid

        if not conta_inicial and opcoes_contas:
            conta_inicial = opcoes_contas[0].key

        dd_conta_origem = ft.Dropdown(
            label="Conta Bancária de Origem (Saída do Dinheiro) *",
            hint_text="Selecione de onde sairá o dinheiro",
            value=conta_inicial,
            options=opcoes_contas,
            **T.dropdown_estilo(),
        )

        txt_data_pag = ft.TextField(
            label="Data do Pagamento",
            value=date.today().isoformat(),
            read_only=True,
            prefix_icon=ft.Icons.CALENDAR_TODAY_ROUNDED,
            **T.campo_estilo(),
        )

        txt_aviso_saldo = ft.Text(
            "",
            color=T.WARNING,
            size=11.5,
            visible=False,
        )

        def _verificar_saldo(e=None):
            cid = dd_conta_origem.value
            conta_sel = next((ct for ct in contas if str(ct.get("id")) == cid), None)
            if conta_sel:
                saldo = float(conta_sel.get("saldo_atual", 0) or 0)
                if saldo < valor_pendente:
                    txt_aviso_saldo.value = f"Atenção: O saldo atual desta conta ({formatar_moeda(saldo)}) é menor que o valor da fatura."
                    txt_aviso_saldo.visible = True
                else:
                    txt_aviso_saldo.visible = False
            else:
                txt_aviso_saldo.visible = False
            try:
                txt_aviso_saldo.update()
            except Exception:
                pass

        dd_conta_origem.on_select = _verificar_saldo
        _verificar_saldo()

        btn_confirmar = ft.FilledButton(
            content=ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                    ft.Text("Confirmar Pagamento", color=ft.Colors.WHITE, size=13.5, weight=ft.FontWeight.BOLD),
                ],
            ),
            style=ft.ButtonStyle(
                bgcolor=T.RECEITA,
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=pad(h=18, v=12),
            ),
        )

        async def _executar_pagamento(_):
            if not dd_conta_origem.value:
                mostrar_feedback(page, "Selecione a conta bancária de origem.", "aviso")
                return

            fid = fatura.get("id")
            # Se for fatura virtual/futura não persistida, garante a linha no banco primeiro
            if not fid or str(fid).startswith("virtual_") or str(fid).startswith("futura_"):
                f_mes = int(fatura.get("mes") or mes_sel[0])
                f_ano = int(fatura.get("ano") or ano_sel[0])
                try:
                    fat_real = await asyncio.to_thread(
                        db.obter_ou_criar_fatura_por_mes_ano,
                        str(cartao["id"]),
                        f_mes,
                        f_ano,
                    )
                    if fat_real and fat_real.get("id"):
                        fid = str(fat_real["id"])
                except Exception as ex_f:
                    print(f"[CartoesView] Erro ao assegurar fatura no banco: {ex_f}")

            if not fid:
                mostrar_feedback(page, "Não foi possível identificar o identificador da fatura.", "erro")
                return

            btn_confirmar.disabled = True
            btn_confirmar.content = ft.Row(
                spacing=6,
                tight=True,
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE),
                    ft.Text("Processando Baixa...", color=ft.Colors.WHITE, size=13),
                ],
            )
            modal_pagar.update()

            try:
                res = await asyncio.to_thread(
                    db.liquidar_pagamento_fatura,
                    fid,
                    dd_conta_origem.value,
                    txt_data_pag.value or date.today().isoformat(),
                    valor_pendente,
                )
                fechar_dialogo(page, modal_pagar)
                qtd = res.get("qtd_baixadas", 0)
                nome_c = cartao.get("nome", "Cartão")
                mostrar_feedback(
                    page,
                    f"Fatura de {nome_c} paga com sucesso! {qtd} despesa{'s' if qtd != 1 else ''} marcada{'s' if qtd != 1 else ''} como Paga.",
                    "sucesso",
                )
                carregar_cartoes(inicial=False, forcar=True)
            except Exception as ex_pag:
                btn_confirmar.disabled = False
                btn_confirmar.content = ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, color=ft.Colors.WHITE, size=18),
                        ft.Text("Confirmar Pagamento", color=ft.Colors.WHITE, size=13.5, weight=ft.FontWeight.BOLD),
                    ],
                )
                try:
                    modal_pagar.update()
                except Exception:
                    pass
                mostrar_feedback(page, f"Erro ao liquidar fatura: {ex_pag}", "erro")

        btn_confirmar.on_click = lambda e: page.run_task(_executar_pagamento, e)

        largura_m = min(460, int(page.width - 32)) if (getattr(page, "width", None) and page.width < 500) else 460
        nome_c = cartao.get("nome", "Cartão")
        mes_f = int(fatura.get("mes") or mes_sel[0])
        ano_f = int(fatura.get("ano") or ano_sel[0])

        modal_pagar = ft.AlertDialog(
            title=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Container(
                        padding=pad(all_=8),
                        bgcolor=ft.Colors.with_opacity(0.12, T.RECEITA),
                        border_radius=8,
                        content=ft.Icon(ft.Icons.PAYMENTS_ROUNDED, color=T.RECEITA, size=22),
                    ),
                    ft.Column(
                        spacing=1,
                        tight=True,
                        controls=[
                            ft.Text("Pagar Fatura do Cartão", size=16, color=T.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{nome_c} · {MESES_NOMES[mes_f]}/{ano_f}", size=12, color=T.TEXT_MUTED),
                        ],
                    ),
                ],
            ),
            content=ft.Container(
                width=largura_m,
                content=ft.Column(
                    spacing=14,
                    tight=True,
                    controls=[
                        ft.Container(
                            padding=pad(all_=14),
                            bgcolor=T.SURFACE,
                            border_radius=10,
                            border=borda(),
                            content=ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[
                                    ft.Column(
                                        spacing=2,
                                        tight=True,
                                        controls=[
                                            ft.Text("Valor a Pagar", size=11, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                                            ft.Text(formatar_moeda(valor_pendente), size=20, color=T.WARNING, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                    ft.Container(
                                        padding=pad(h=10, v=6),
                                        bgcolor=ft.Colors.with_opacity(0.08, T.PRIMARY),
                                        border_radius=8,
                                        content=ft.Row(
                                            spacing=5,
                                            tight=True,
                                            controls=[
                                                ft.Icon(ft.Icons.CHECKLIST_ROUNDED, size=15, color=T.PRIMARY),
                                                ft.Text("Baixa em Lote", size=12, color=T.PRIMARY, weight=ft.FontWeight.BOLD),
                                            ],
                                        ),
                                    ),
                                ],
                            ),
                        ),
                        ft.Text(
                            "O valor será deduzido da conta bancária escolhida e todas as compras vinculadas a esta fatura receberão baixa em lote para o status 'Pago'.",
                            size=12,
                            color=T.TEXT_MUTED,
                        ),
                        dd_conta_origem,
                        txt_aviso_saldo,
                        txt_data_pag,
                    ],
                ),
            ),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: fechar_dialogo(page, modal_pagar),
                ),
                btn_confirmar,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, modal_pagar)

    # ── Modal de Estorno de Pagamento de Fatura ──────────────────────────────
    def abrir_modal_estorno(fatura: dict, cartao: dict):
        fid = str(fatura.get("id") or "")
        if not fid:
            return

        async def _executar_estorno(_):
            btn_estornar.disabled = True
            btn_estornar.content = ft.Row(
                spacing=6, tight=True,
                controls=[
                    ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.WHITE),
                    ft.Text("Estornando...", color=ft.Colors.WHITE, size=13),
                ]
            )
            modal_est.update()

            try:
                await asyncio.to_thread(db.estornar_pagamento_fatura, fid)
                fechar_dialogo(page, modal_est)
                mostrar_feedback(page, f"Pagamento da fatura de {cartao.get('nome')} estornado com sucesso!", "sucesso")
                carregar_cartoes(inicial=False, forcar=True)
            except Exception as ex_est:
                btn_estornar.disabled = False
                btn_estornar.content = ft.Text("Confirmar Estorno", color=ft.Colors.WHITE)
                try:
                    modal_est.update()
                except Exception:
                    pass
                mostrar_feedback(page, f"Erro ao estornar: {ex_est}", "erro")

        btn_estornar = ft.FilledButton(
            content=ft.Text("Confirmar Estorno", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
            style=ft.ButtonStyle(bgcolor=T.DESPESA),
            on_click=lambda e: page.run_task(_executar_estorno, e),
        )

        val_pg = float(fatura.get("valor_pago", fatura.get("valor_total", 0)) or 0)
        modal_est = ft.AlertDialog(
            title=ft.Row(
                spacing=8,
                controls=[
                    ft.Icon(ft.Icons.RESTORE_ROUNDED, color=T.DESPESA, size=22),
                    ft.Text("Estornar Pagamento", size=16, color=T.TEXT_PRIMARY, weight=ft.FontWeight.BOLD),
                ],
            ),
            content=ft.Text(
                f"Deseja estornar o pagamento da fatura de {cartao.get('nome')} no valor de {formatar_moeda(val_pg)}? "
                f"O dinheiro retornará para a conta bancária e as compras associadas voltarão para o status 'Pendente'.",
                color=T.TEXT_MUTED,
                size=13.5,
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: fechar_dialogo(page, modal_est)),
                btn_estornar,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, modal_est)

    # ── Modal de Cadastro / Edição de Cartão ─────────────────────────────────
    def abrir_modal_cartao(cartao_edicao: dict | None = None):
        eh_edicao = cartao_edicao is not None
        titulo_modal = "Editar Cartão" if eh_edicao else "Novo Cartão de Crédito"

        txt_nome = ft.TextField(
            label="Nome do Cartão *",
            hint_text="Ex: Nubank Mastercard, XP Visa Infinite",
            value=cartao_edicao.get("nome", "") if eh_edicao else "",
            **T.campo_estilo(),
        )

        bandeira_inicial = (
            db.normalizar_bandeira_cartao(cartao_edicao.get("bandeira"))
            if eh_edicao
            else "mastercard"
        )
        dd_bandeira = ft.Dropdown(
            label="Bandeira *",
            options=[ft.dropdown.Option(key=k, text=lbl) for k, lbl in BANDEIRAS_OPCOES],
            value=bandeira_inicial,
            **T.dropdown_estilo(),
        )

        txt_limite = ft.TextField(
            label="Limite Total (R$) *",
            hint_text="Ex: 5000,00",
            keyboard_type=ft.KeyboardType.NUMBER,
            prefix="R$ ",
            value=str(cartao_edicao.get("limite_total", "")) if eh_edicao else "",
            **T.campo_estilo(),
        )

        txt_fechamento = ft.TextField(
            label="Dia Fechamento *",
            hint_text="1 a 31",
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(cartao_edicao.get("dia_fechamento", "1")) if eh_edicao else "1",
            **T.campo_estilo(),
        )

        txt_vencimento = ft.TextField(
            label="Dia Vencimento *",
            hint_text="1 a 31",
            keyboard_type=ft.KeyboardType.NUMBER,
            value=str(cartao_edicao.get("dia_vencimento", "10")) if eh_edicao else "10",
            **T.campo_estilo(),
        )

        contas_disponiveis = db.listar_contas()
        opts_contas = [ft.dropdown.Option(key="", text="Nenhuma (Manual)")] + [
            ft.dropdown.Option(key=str(c["id"]), text=c["nome"]) for c in contas_disponiveis
        ]
        dd_conta_debito = ft.Dropdown(
            label="Conta para Débito Automático (Opcional)",
            options=opts_contas,
            value=str(cartao_edicao.get("conta_debito_id") or "") if eh_edicao else "",
            **T.dropdown_estilo(),
        )

        cor_selecionada = [cartao_edicao.get("cor", CORES_CARTOES[0]["hex"]) if eh_edicao else CORES_CARTOES[0]["hex"]]

        def _selecionar_cor(hex_cor):
            cor_selecionada[0] = hex_cor
            for c_box in row_cores.controls:
                c_box.border = borda(2, ft.Colors.WHITE) if c_box.data == hex_cor else borda(1, T.BORDER)
            _safe_update()

        row_cores = ft.Row(
            spacing=8,
            controls=[
                ft.Container(
                    width=28,
                    height=28,
                    bgcolor=c["hex"],
                    border_radius=14,
                    data=c["hex"],
                    border=borda(2, ft.Colors.WHITE) if c["hex"] == cor_selecionada[0] else borda(1, T.BORDER),
                    tooltip=c["label"],
                    on_click=lambda _, h=c["hex"]: _selecionar_cor(h),
                )
                for c in CORES_CARTOES
            ],
        )

        def salvar_cartao(_):
            nome = txt_nome.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome do cartão.", "alerta")
                return

            try:
                limite_num = float(txt_limite.value.replace(",", ".").replace("R$", "").strip() or 0)
                if limite_num <= 0:
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Informe um limite válido maior que zero.", "alerta")
                return

            try:
                fech = int(txt_fechamento.value or 1)
                venc = int(txt_vencimento.value or 1)
                if not (1 <= fech <= 31 and 1 <= venc <= 31):
                    raise ValueError
            except ValueError:
                mostrar_feedback(page, "Dias de fechamento e vencimento devem ser entre 1 e 31.", "alerta")
                return

            dados = {
                "nome": nome,
                "bandeira": db.normalizar_bandeira_cartao(dd_bandeira.value),
                "cor": cor_selecionada[0],
                "icone": "credit_card",
                "limite_total": limite_num,
                "dia_fechamento": fech,
                "dia_vencimento": venc,
                "conta_debito_id": dd_conta_debito.value or None,
                "ativo": True,
            }

            try:
                if eh_edicao:
                    old_total = float(cartao_edicao.get("limite_total", 0) or 0)
                    old_disp  = float(cartao_edicao.get("limite_disponivel", old_total) or 0)
                    usado     = max(0.0, old_total - old_disp)
                    dados["limite_disponivel"] = max(0.0, limite_num - usado)
                    resp = db.atualizar_cartao(cartao_edicao["id"], dados)
                    if not (resp and resp.data):
                        raise RuntimeError("O banco de dados não confirmou a atualização do cartão.")
                    msg_ok = "Cartão atualizado com sucesso!"
                else:
                    dados["limite_disponivel"] = limite_num
                    resp = db.criar_cartao(dados)
                    if not (resp and resp.data):
                        raise RuntimeError("O banco de dados não confirmou a criação do cartão.")
                    msg_ok = "Cartão criado com sucesso!"

                fechar_dialogo(page, modal)
                mostrar_feedback(page, msg_ok, "sucesso")
                carregar_cartoes(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")

        def fechar_modal(_):
            fechar_dialogo(page, modal)

        grid_campos = ft.ResponsiveRow(
            spacing=10,
            run_spacing=10,
            controls=[
                ft.Container(content=txt_nome, col={"xs": 12}),
                ft.Container(content=dd_bandeira, col={"xs": 12, "sm": 6}),
                ft.Container(content=txt_limite, col={"xs": 12, "sm": 6}),
                ft.Container(content=txt_fechamento, col={"xs": 6, "sm": 6}),
                ft.Container(content=txt_vencimento, col={"xs": 6, "sm": 6}),
                ft.Container(content=dd_conta_debito, col={"xs": 12}),
            ],
        )

        largura_modal = min(450, int(page.width - 32)) if (getattr(page, "width", None) and page.width < 500) else (None if mobile else 450)

        modal = ft.AlertDialog(
            title=ft.Text(titulo_modal, color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                width=largura_modal,
                content=ft.Column(
                    spacing=12,
                    tight=True,
                    scroll=ft.ScrollMode.AUTO,
                    controls=[
                        grid_campos,
                        ft.Text("Cor do Cartão", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_500),
                        row_cores,
                    ],
                ),
            ),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=fechar_modal),
                ft.FilledButton(
                    content=ft.Text("Salvar Cartão", color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar_cartao,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        abrir_dialogo(page, modal)

    def confirmar_exclusao_cartao(cartao: dict):
        def _executar(_):
            fechar_dialogo(page, dialog)
            try:
                db.deletar_cartao(cartao["id"])
                mostrar_feedback(page, "Cartão inativado!", "sucesso")
                carregar_cartoes(inicial=False, forcar=True)
            except Exception as ex:
                mostrar_feedback(page, f"Erro: {ex}", "erro")

        dialog = ft.AlertDialog(
            title=ft.Text("Inativar Cartão", color=T.TEXT_PRIMARY, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Text(f"Deseja inativar o cartão '{cartao.get('nome')}'? As faturas existentes serão mantidas.", color=T.TEXT_MUTED, size=14),
            actions=[
                ft.TextButton(content=ft.Text("Cancelar", color=T.TEXT_MUTED), on_click=lambda _: fechar_dialogo(page, dialog)),
                ft.FilledButton(content=ft.Text("Inativar", color=ft.Colors.WHITE), style=ft.ButtonStyle(bgcolor=T.DESPESA), on_click=_executar),
            ],
        )
        abrir_dialogo(page, dialog)

    # ── Renderização Principal por Aba ───────────────────────────────────────
    def renderizar_conteudo():
        grid_conteudo.controls.clear()

        if not cartoes_lista:
            # Estado vazio: nenhum cartão cadastrado
            grid_conteudo.controls.append(
                ft.Container(
                    col={"xs": 12},
                    padding=pad(all_=50),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=12,
                        controls=[
                            ft.Icon(ft.Icons.CREDIT_CARD_OUTLINED, size=54, color=T.TEXT_MUTED),
                            ft.Text("Nenhum cartão cadastrado", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text("Cadastre seus cartões de crédito para controlar faturas, limites e parcelamentos.", color=T.TEXT_MUTED, size=13),
                            ft.Container(height=8),
                            ft.FilledButton(
                                content=ft.Row(
                                    spacing=6, tight=True,
                                    controls=[
                                        ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=16),
                                        ft.Text("Cadastrar Cartão", color=ft.Colors.WHITE, size=13, weight=ft.FontWeight.W_600),
                                    ],
                                ),
                                on_click=lambda _: abrir_modal_cartao(),
                                style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=8), padding=pad(h=16, v=12)),
                            ),
                        ],
                    ),
                )
            )
            return

        aba = aba_ativa[0]
        if aba == "cartoes":
            _renderizar_cartoes()
        elif aba == "abertas":
            _renderizar_faturas_abertas()
        elif aba == "fechadas":
            _renderizar_faturas_fechadas()
        else:
            _renderizar_cartoes()

        try:
            grid_conteudo.update()
        except Exception:
            pass

    # ── 1. Aba: Meus Cartões (Visual dos Cartões com Melhor Cartão no Topo) ────
    def _renderizar_cartoes():
        hoje = date.today()
        melhor_c, melhor_info = calcular_melhor_cartao(cartoes_lista, hoje)
        melhor_cid = str(melhor_c.get("id")) if melhor_c else None

        # Ordena a lista colocando o melhor cartão no topo
        def _chave_ordem_cartao(c):
            cid = str(c.get("id"))
            eh_melhor = (cid == melhor_cid)
            lim_dsp = float(c.get("limite_disponivel", 0) or 0)
            return (0 if eh_melhor else 1, -lim_dsp)

        cartoes_ordenados = sorted(cartoes_lista, key=_chave_ordem_cartao)

        for cartao in cartoes_ordenados:
            cid = str(cartao.get("id") or "")
            cor_cartao = cartao.get("cor") or "#1E293B"
            lim_total = float(cartao.get("limite_total", 0) or 0)
            lim_disp  = float(cartao.get("limite_disponivel", lim_total) or 0)
            fatura_est = max(0.0, lim_total - lim_disp)
            progresso = min(1.0, max(0.0, (lim_total - lim_disp) / lim_total)) if lim_total > 0 else 0.0

            fech = cartao.get("dia_fechamento", 1)
            venc = cartao.get("dia_vencimento", 10)
            bandeira_key = db.normalizar_bandeira_cartao(cartao.get("bandeira"))
            bandeira = LABELS_BANDEIRAS.get(bandeira_key, "Mastercard")
            eh_melhor = (cid == melhor_cid)

            def _ir_extrato_cartao(_=None, cartao_id_alvo=cid):
                if cartao_id_alvo:
                    ir_cartao(page, cartao_id_alvo)

            # Badge de Melhor Cartão para Compras Hoje
            badge_melhor = ft.Container(
                padding=pad(h=8, v=3),
                bgcolor=ft.Colors.with_opacity(0.18, ft.Colors.WHITE),
                border_radius=6,
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.AUTO_AWESOME_ROUNDED, color=ft.Colors.AMBER_300, size=13),
                        ft.Text("MELHOR P/ COMPRAR HOJE", color=ft.Colors.WHITE, size=10, weight=ft.FontWeight.BOLD),
                    ],
                ),
            ) if eh_melhor else ft.Container()

            corpo_clicavel = ft.Container(
                on_click=_ir_extrato_cartao,
                ink=True,
                border_radius=12,
                content=ft.Column(
                    spacing=14,
                    controls=[
                        # Visual do "Plástico" do Cartão
                        ft.Container(
                            padding=pad(all_=16),
                            bgcolor=cor_cartao,
                            border_radius=12,
                            content=ft.Column(
                                spacing=12,
                                controls=[
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Icon(ft.Icons.CONTACTLESS_ROUNDED, color=ft.Colors.WHITE_70, size=24),
                                            badge_melhor if eh_melhor else ft.Text(bandeira.upper(), color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                    ft.Container(height=4),
                                    ft.Text(cartao.get("nome", "Cartão"), color=ft.Colors.WHITE, size=16, weight=ft.FontWeight.BOLD),
                                    ft.Row(
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                        controls=[
                                            ft.Text(f"Fecha dia {fech}", color=ft.Colors.WHITE_70, size=11),
                                            ft.Text(f"Vence dia {venc}", color=ft.Colors.WHITE, size=11, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                ],
                            ),
                        ),
                        # Detalhes de Limite e Uso
                        ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text("Fatura Estimada", color=T.TEXT_MUTED, size=12),
                                        ft.Text(formatar_moeda(fatura_est), color=T.WARNING, size=13, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.ProgressBar(value=progresso, color=T.WARNING if progresso < 0.8 else T.DESPESA, bgcolor=T.SURFACE_ALT, height=6),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"Disponível: {formatar_moeda(lim_disp)}", color=T.PRIMARY, size=11, weight=ft.FontWeight.W_500),
                                        ft.Text(f"Limite: {formatar_moeda(lim_total)}", color=T.TEXT_MUTED, size=11),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )

            card = ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=18),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(1.5, T.PRIMARY if eh_melhor else T.BORDER),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        corpo_clicavel,
                        ft.Divider(height=1, color=T.BORDER),
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.TextButton(
                                    content=ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=15, color=T.PRIMARY),
                                            ft.Text("Ver Fatura / Extrato", color=T.PRIMARY, size=12, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                    on_click=_ir_extrato_cartao,
                                ),
                                ft.Row(
                                    spacing=4,
                                    tight=True,
                                    controls=[
                                        ft.IconButton(
                                            icon=ft.Icons.EDIT_OUTLINED,
                                            icon_size=16,
                                            icon_color=T.TEXT_MUTED,
                                            tooltip="Editar cartão",
                                            on_click=lambda _, c=cartao: abrir_modal_cartao(c),
                                        ),
                                        ft.IconButton(
                                            icon=ft.Icons.DELETE_OUTLINE,
                                            icon_size=16,
                                            icon_color=T.DESPESA,
                                            tooltip="Inativar cartão",
                                            on_click=lambda _, c=cartao: confirmar_exclusao_cartao(c),
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
            )
            grid_conteudo.controls.append(card)

    # ── 2. Aba: Faturas Abertas (Respeita Rigorosamente o Mês/Ano Filtrado) ───
    def _renderizar_faturas_abertas():
        cartao_dict = {str(c["id"]): c for c in cartoes_lista}
        hoje = date.today()

        # Helper para criação modular de cards de fatura (mês atual e prévia)
        def _criar_card_fatura(fat: dict, is_preview_proximo_mes: bool = False) -> ft.Container:
            c_obj = fat.get("cartao") or {}
            cid = str(fat.get("cartao_id") or "")
            nome_c = c_obj.get("nome", "Cartão")
            cor_c = c_obj.get("cor", "#1E293B")
            lim_tot = float(c_obj.get("limite_total", 0) or 0)
            lim_dsp = float(c_obj.get("limite_disponivel", lim_tot) or 0)
            valor_pend = float(fat.get("valor_pendente", 0) or 0)
            progresso = min(1.0, max(0.0, valor_pend / lim_tot)) if lim_tot > 0 else 0.0

            bandeira_key = db.normalizar_bandeira_cartao(c_obj.get("bandeira"))
            bandeira = LABELS_BANDEIRAS.get(bandeira_key, "Mastercard")

            dt_venc = None
            if fat.get("data_vencimento"):
                try:
                    dt_venc = datetime.fromisoformat(str(fat["data_vencimento"]).split("T")[0]).date()
                except Exception:
                    pass

            if is_preview_proximo_mes:
                lbl_venc = f"1ª Semana ({dt_venc.strftime('%d/%m') if dt_venc else 'Início'})"
                cor_txt_venc = T.INFO
                cor_bg_venc = ft.Colors.with_opacity(0.12, T.INFO)
            else:
                lbl_venc, cor_txt_venc, cor_bg_venc = formatar_status_vencimento(
                    dt_venc, fat.get("status", "Aberta"), valor_pendente=valor_pend
                )

            mes_f = int(fat.get("mes") or mes_sel[0])
            ano_f = int(fat.get("ano") or ano_sel[0])
            eh_zerada = (valor_pend <= 0.01)

            # Botão de Ação: Se zerada, exibe indicador de status sem dívida pendente
            if eh_zerada:
                btn_acao_fatura = ft.Container(
                    content=ft.Row(
                        spacing=5,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=15, color=T.PRIMARY),
                            ft.Text("Zerada", color=T.PRIMARY, size=12, weight=ft.FontWeight.W_600),
                        ],
                    ),
                    padding=pad(h=12, v=8),
                    bgcolor=ft.Colors.with_opacity(0.08, T.PRIMARY),
                    border_radius=8,
                )
            else:
                btn_acao_fatura = ft.FilledButton(
                    content=ft.Row(
                        spacing=6,
                        tight=True,
                        controls=[
                            ft.Icon(ft.Icons.PAYMENTS_ROUNDED, color=ft.Colors.WHITE, size=16),
                            ft.Text("PAGAR FATURA", color=ft.Colors.WHITE, size=12.5, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                    style=ft.ButtonStyle(
                        bgcolor=T.RECEITA,
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=pad(h=14, v=10),
                    ),
                    on_click=lambda _, f=fat, c=c_obj: abrir_modal_pagar_fatura(f, c),
                )

            cor_borda = (
                ft.Colors.with_opacity(0.45, T.INFO)
                if is_preview_proximo_mes
                else (T.WARNING if ("Vencida" in lbl_venc or "Hoje" in lbl_venc) else T.BORDER)
            )

            rotulo_fatura = (
                f"Fatura de {MESES_NOMES[mes_f]}/{ano_f} · Prévia"
                if is_preview_proximo_mes
                else f"Fatura de {MESES_NOMES[mes_f]}/{ano_f}"
            )

            return ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=18),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(1.5, cor_borda),
                content=ft.Column(
                    spacing=14,
                    controls=[
                        # Topo do Card: Identificação do Cartão + Badge de Vencimento
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    tight=True,
                                    controls=[
                                        ft.Container(
                                            width=12,
                                            height=12,
                                            bgcolor=cor_c,
                                            border_radius=6,
                                        ),
                                        ft.Text(nome_c, color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.Container(
                                    padding=pad(h=8, v=3.5),
                                    bgcolor=cor_bg_venc,
                                    border_radius=6,
                                    content=ft.Text(lbl_venc, color=cor_txt_venc, size=11, weight=ft.FontWeight.BOLD),
                                ),
                            ],
                        ),

                        # Subtítulo da Fatura & Valor Pendente em Destaque
                        ft.Column(
                            spacing=3,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(rotulo_fatura, color=T.TEXT_MUTED, size=12, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True),
                                        ft.Text(bandeira.upper(), color=T.TEXT_MUTED, size=11, weight=ft.FontWeight.W_500),
                                    ],
                                ),
                                ft.Text(
                                    formatar_moeda(valor_pend),
                                    color=T.TEXT_MUTED if eh_zerada else T.WARNING,
                                    size=24,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),

                        # Barra de Progresso do Limite
                        ft.Column(
                            spacing=6,
                            controls=[
                                ft.ProgressBar(
                                    value=progresso,
                                    color=T.WARNING if progresso < 0.8 else T.DESPESA,
                                    bgcolor=T.SURFACE_ALT,
                                    height=6,
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"Limite: {formatar_moeda(lim_tot)}", color=T.TEXT_MUTED, size=11),
                                        ft.Text(f"Disponível: {formatar_moeda(lim_dsp)}", color=T.PRIMARY, size=11, weight=ft.FontWeight.W_500),
                                    ],
                                ),
                            ],
                        ),

                        ft.Divider(height=1, color=T.BORDER),

                        # Ações Inline: PAGAR FATURA (ou Pill Zerada) e Ver Extrato
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                btn_acao_fatura,
                                ft.TextButton(
                                    content=ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=15, color=T.PRIMARY),
                                            ft.Text("Extrato", color=T.PRIMARY, size=12, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                    on_click=lambda _, target_id=cid: ir_cartao(page, target_id),
                                ),
                            ],
                        ),
                    ],
                ),
            )

        # ── 2.1 Monta Faturas do Mês Selecionado ──
        faturas_abertas_map: dict[str, dict] = {}
        cartoes_com_fatura_no_mes: set[str] = set()

        for fat in faturas_lista:
            f_mes = int(fat.get("mes") or 0)
            f_ano = int(fat.get("ano") or 0)
            # Sincronização estrita de filtro: faturas do mês selecionado
            if f_mes != mes_sel[0] or f_ano != ano_sel[0]:
                continue

            cid = str(fat.get("cartao_id") or "")
            cartoes_com_fatura_no_mes.add(cid)

            st = str(fat.get("status", "")).lower()
            val_tot = float(fat.get("valor_total", 0) or 0)
            val_pg  = float(fat.get("valor_pago", 0) or 0)
            pendente = max(0.0, val_tot - val_pg)

            if st == "paga" or val_tot <= 0.01 or pendente <= 0.01:
                continue

            c_obj = cartao_dict.get(cid, fat.get("cartoes") or {})
            chave = f"{cid}_{f_mes}_{f_ano}"
            faturas_abertas_map[chave] = {
                "id": fat.get("id"),
                "cartao_id": cid,
                "mes": f_mes,
                "ano": f_ano,
                "valor_total": val_tot,
                "valor_pago": val_pg,
                "valor_pendente": pendente,
                "status": fat.get("status", "Aberta"),
                "data_vencimento": fat.get("data_vencimento"),
                "data_fechamento": fat.get("data_fechamento"),
                "cartao": c_obj,
            }

        # Cartões com uso de limite no mês filtrado que ainda não possuem fatura no banco
        cartoes_resumo = resumo_periodo.get("cartoes", [])
        for cr in cartoes_resumo:
            cid = str(cr.get("id") or "")
            if cid in cartoes_com_fatura_no_mes:
                continue

            st_cr = str(cr.get("fatura_status", "")).lower()
            if st_cr == "paga":
                continue

            f_val = float(cr.get("fatura_valor", 0) or 0)
            f_pg  = float(cr.get("fatura_pago", 0) or 0)
            pend  = max(0.0, f_val - f_pg)

            c_obj = cartao_dict.get(cid, cr)
            chave = f"{cid}_{mes_sel[0]}_{ano_sel[0]}"
            if pend > 0.01 and chave not in faturas_abertas_map:
                dia_v = int(c_obj.get("dia_vencimento") or 10)
                ult_d_v = calendar.monthrange(ano_sel[0], mes_sel[0])[1]
                dt_v_calc = date(ano_sel[0], mes_sel[0], min(dia_v, ult_d_v))

                dia_f = int(c_obj.get("dia_fechamento") or 1)
                if dia_v < dia_f:
                    m_f_c = 12 if mes_sel[0] == 1 else mes_sel[0] - 1
                    a_f_c = ano_sel[0] - 1 if mes_sel[0] == 1 else ano_sel[0]
                else:
                    m_f_c = mes_sel[0]
                    a_f_c = ano_sel[0]
                ult_d_f = calendar.monthrange(a_f_c, m_f_c)[1]
                dt_f_calc = date(a_f_c, m_f_c, min(dia_f, ult_d_f))

                faturas_abertas_map[chave] = {
                    "id": cr.get("fatura_id") or f"virtual_{cid}_{mes_sel[0]}_{ano_sel[0]}",
                    "cartao_id": cid,
                    "mes": mes_sel[0],
                    "ano": ano_sel[0],
                    "valor_total": pend,
                    "valor_pago": f_pg,
                    "valor_pendente": pend,
                    "status": cr.get("fatura_status", "Aberta"),
                    "data_vencimento": cr.get("data_vencimento") or dt_v_calc.isoformat(),
                    "data_fechamento": dt_f_calc.isoformat(),
                    "cartao": c_obj,
                }

        lista_faturas = list(faturas_abertas_map.values())

        # ── 2.2 Monta Faturas da 1ª Semana do Mês Seguinte (Prévia) ──
        faturas_prox_map: dict[str, dict] = {}
        for fat in faturas_prox_lista:
            f_mes = int(fat.get("mes") or 0)
            f_ano = int(fat.get("ano") or 0)
            st = str(fat.get("status", "")).lower()
            val_tot = float(fat.get("valor_total", 0) or 0)
            val_pg  = float(fat.get("valor_pago", 0) or 0)
            pendente = max(0.0, val_tot - val_pg)

            if st == "paga" or val_tot <= 0.01 or pendente <= 0.01:
                continue

            cid = str(fat.get("cartao_id") or "")
            c_obj = cartao_dict.get(cid, fat.get("cartoes") or {})
            chave = f"{cid}_{f_mes}_{f_ano}"
            faturas_prox_map[chave] = {
                "id": fat.get("id"),
                "cartao_id": cid,
                "mes": f_mes,
                "ano": f_ano,
                "valor_total": val_tot,
                "valor_pago": val_pg,
                "valor_pendente": pendente,
                "status": fat.get("status", "Aberta"),
                "data_vencimento": fat.get("data_vencimento"),
                "data_fechamento": fat.get("data_fechamento"),
                "cartao": c_obj,
            }

        lista_faturas_prox = list(faturas_prox_map.values())

        # Ordenação rigorosa por data de vencimento crescente:
        def _chave_ordem_vencimento(item):
            dt_raw = item.get("data_vencimento")
            if dt_raw:
                try:
                    dt = datetime.fromisoformat(str(dt_raw).split("T")[0]).date()
                    return (0, dt)
                except Exception:
                    pass
            return (1, date.max)

        lista_faturas.sort(key=_chave_ordem_vencimento)
        lista_faturas_prox.sort(key=_chave_ordem_vencimento)

        # Se não há faturas no mês selecionado e nem no próximo
        if not lista_faturas and not lista_faturas_prox:
            grid_conteudo.controls.append(
                ft.Container(
                    col={"xs": 12},
                    padding=pad(all_=45),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=52, color=T.RECEITA),
                            ft.Text("Tudo em dia!", color=T.TEXT_PRIMARY, size=17, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"Você não possui nenhuma fatura aberta para {MESES_NOMES[mes_sel[0]]}/{ano_sel[0]}.",
                                color=T.TEXT_MUTED,
                                size=13,
                            ),
                        ],
                    ),
                )
            )
            return

        # 1. Seção Principal: Faturas do Mês Selecionado (Vencimento no Mês)
        if lista_faturas:
            if lista_faturas_prox:
                grid_conteudo.controls.append(
                    ft.Container(
                        col={"xs": 12},
                        margin=ft.Margin(left=0, top=0, right=0, bottom=2),
                        content=ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=18, color=T.WARNING),
                                ft.Text(
                                    f"Faturas de {MESES_NOMES[mes_sel[0]]}/{ano_sel[0]} (Vencimentos no Mês)",
                                    size=15 if mobile else 16,
                                    color=T.TEXT_PRIMARY,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ],
                        ),
                    )
                )
            for fat in lista_faturas:
                grid_conteudo.controls.append(_criar_card_fatura(fat, is_preview_proximo_mes=False))
        else:
            # Banner amigável indicando que o mês atual está pago / sem faturas
            grid_conteudo.controls.append(
                ft.Container(
                    col={"xs": 12},
                    padding=pad(h=20, v=16),
                    bgcolor=ft.Colors.with_opacity(0.04, T.SURFACE_ALT),
                    border=borda(1, T.BORDER),
                    border_radius=12,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Row(
                        spacing=10,
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED, size=22, color=T.RECEITA),
                            ft.Text(
                                f"Tudo em dia em {MESES_NOMES[mes_sel[0]]}/{ano_sel[0]}! Nenhuma fatura pendente com vencimento neste mês.",
                                color=T.TEXT_MUTED,
                                size=12.5,
                                weight=ft.FontWeight.W_500,
                            ),
                        ],
                    ),
                )
            )

        # 2. Seção Separada: Próximos Vencimentos (1ª Semana do Mês Seguinte)
        if lista_faturas_prox:
            mes_prox = 1 if mes_sel[0] == 12 else mes_sel[0] + 1
            ano_prox = ano_sel[0] + 1 if mes_sel[0] == 12 else ano_sel[0]
            grid_conteudo.controls.append(
                ft.Container(
                    col={"xs": 12},
                    margin=ft.Margin(left=0, top=14, right=0, bottom=4),
                    content=ft.Column(
                        spacing=8,
                        controls=[
                            ft.Divider(height=1, color=ft.Colors.with_opacity(0.4, T.BORDER)),
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                                wrap=True,
                                spacing=8,
                                controls=[
                                    ft.Row(
                                        spacing=8,
                                        expand=True,
                                        controls=[
                                            ft.Container(
                                                padding=pad(all_=6),
                                                bgcolor=ft.Colors.with_opacity(0.12, T.INFO),
                                                border_radius=8,
                                                content=ft.Icon(ft.Icons.UPCOMING_ROUNDED, color=T.INFO, size=18),
                                            ),
                                            ft.Column(
                                                spacing=1,
                                                expand=True,
                                                controls=[
                                                    ft.Text(
                                                        "Próximos Vencimentos (1ª Semana do Mês Seguinte)",
                                                        color=T.TEXT_PRIMARY,
                                                        size=14.5 if mobile else 16,
                                                        weight=ft.FontWeight.BOLD,
                                                    ),
                                                    ft.Text(
                                                        f"Faturas que vencem entre 01/{mes_prox:02d} e 07/{mes_prox:02d}/{ano_prox} · Prévia financeira",
                                                        color=T.TEXT_MUTED,
                                                        size=11.5 if mobile else 12,
                                                    ),
                                                ],
                                            ),
                                        ],
                                    ),
                                    ft.Container(
                                        padding=pad(h=8, v=3.5),
                                        bgcolor=ft.Colors.with_opacity(0.08, T.INFO),
                                        border=borda(1, ft.Colors.with_opacity(0.2, T.INFO)),
                                        border_radius=6,
                                        content=ft.Text(
                                            f"{len(lista_faturas_prox)} fatura{'s' if len(lista_faturas_prox) != 1 else ''} na 1ª semana",
                                            color=T.INFO,
                                            size=11,
                                            weight=ft.FontWeight.BOLD,
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                )
            )
            for fat_p in lista_faturas_prox:
                grid_conteudo.controls.append(_criar_card_fatura(fat_p, is_preview_proximo_mes=True))

    # ── 3. Aba: Faturas Fechadas (Respeita Rigorosamente o Mês/Ano Filtrado) ──
    def _renderizar_faturas_fechadas():
        cartao_dict = {str(c["id"]): c for c in cartoes_lista}

        # Regra 2: Filtra faturas pagas ESTRITAMENTE do mês e ano filtrado
        faturas_pagas = [
            f for f in faturas_lista
            if (int(f.get("mes") or 0) == mes_sel[0] and int(f.get("ano") or 0) == ano_sel[0])
            and (
                str(f.get("status", "")).lower() == "paga"
                or float(f.get("valor_pago", 0) or 0) >= float(f.get("valor_total", 0) or 0) > 0
                or float(f.get("valor_total", 0) or 0) <= 0.01
            )
        ]

        if not faturas_pagas:
            grid_conteudo.controls.append(
                ft.Container(
                    col={"xs": 12},
                    padding=pad(all_=45),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Column(
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=10,
                        controls=[
                            ft.Icon(ft.Icons.HISTORY_ROUNDED, size=52, color=T.TEXT_MUTED),
                            ft.Text("Nenhuma fatura fechada ou paga", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                            ft.Text(
                                f"Não há faturas liquidadas registradas para {MESES_NOMES[mes_sel[0]]}/{ano_sel[0]}.",
                                color=T.TEXT_MUTED,
                                size=13,
                            ),
                        ],
                    ),
                )
            )
            return

        for fat in faturas_pagas:
            cid = str(fat.get("cartao_id") or "")
            c_obj = cartao_dict.get(cid, fat.get("cartoes") or {})
            nome_c = c_obj.get("nome", "Cartão")
            cor_c = c_obj.get("cor", "#1E293B")
            val_pago = float(fat.get("valor_pago", fat.get("valor_total", 0)) or 0)
            mes_f = int(fat.get("mes") or mes_sel[0])
            ano_f = int(fat.get("ano") or ano_sel[0])

            dt_pag = fat.get("data_pagamento")
            dt_pag_txt = ""
            if dt_pag:
                try:
                    dt_p = datetime.fromisoformat(str(dt_pag).split("T")[0]).date()
                    dt_pag_txt = f"Pago em {dt_p.strftime('%d/%m/%Y')}"
                except Exception:
                    dt_pag_txt = f"Pago em {dt_pag}"
            elif val_pago <= 0.01:
                dt_pag_txt = "Sem Débito / Zerada"

            btn_estornar = ft.TextButton(
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.RESTORE_ROUNDED, size=15, color=T.DESPESA),
                        ft.Text("Estornar", color=T.DESPESA, size=12),
                    ],
                ),
                on_click=lambda _, f=fat, c=c_obj: abrir_modal_estorno(f, c),
            ) if val_pago > 0.01 else ft.Container()

            card_paga = ft.Container(
                col={"xs": 12, "sm": 6, "md": 4},
                padding=pad(all_=18),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(1, ft.Colors.with_opacity(0.35, T.RECEITA)),
                content=ft.Column(
                    spacing=12,
                    controls=[
                        # Topo: Cartão + Badge Verde Paga
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    tight=True,
                                    controls=[
                                        ft.Container(width=12, height=12, bgcolor=cor_c, border_radius=6),
                                        ft.Text(nome_c, color=T.TEXT_PRIMARY, size=15, weight=ft.FontWeight.BOLD),
                                    ],
                                ),
                                ft.Container(
                                    padding=pad(h=8, v=3),
                                    bgcolor=ft.Colors.with_opacity(0.12, T.RECEITA),
                                    border_radius=6,
                                    content=ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=13, color=T.RECEITA),
                                            ft.Text("Paga", color=T.RECEITA, size=11, weight=ft.FontWeight.BOLD),
                                        ],
                                    ),
                                ),
                            ],
                        ),

                        # Dados do Pagamento
                        ft.Column(
                            spacing=3,
                            controls=[
                                ft.Text(f"Fatura de {MESES_NOMES[mes_f]}/{ano_f}", color=T.TEXT_MUTED, size=12),
                                ft.Text(formatar_moeda(val_pago), color=T.RECEITA, size=22, weight=ft.FontWeight.BOLD),
                                ft.Text(dt_pag_txt or "Liquidada", color=T.TEXT_MUTED, size=11) if dt_pag_txt else ft.Container(),
                            ],
                        ),

                        ft.Divider(height=1, color=T.BORDER),

                        # Ações: Extrato e Estorno
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.TextButton(
                                    content=ft.Row(
                                        spacing=4,
                                        tight=True,
                                        controls=[
                                            ft.Icon(ft.Icons.RECEIPT_LONG_ROUNDED, size=15, color=T.PRIMARY),
                                            ft.Text("Ver Extrato", color=T.PRIMARY, size=12, weight=ft.FontWeight.W_600),
                                        ],
                                    ),
                                    on_click=lambda _, target_id=cid: ir_cartao(page, target_id),
                                ),
                                btn_estornar,
                            ],
                        ),
                    ],
                ),
            )
            grid_conteudo.controls.append(card_paga)

    # ── KPIs Topo Clicáveis (2x2 no Mobile, 1x4 no Desktop) ───────────────────
    kpis_topo = ft.ResponsiveRow(
        spacing=8 if mobile else 12, run_spacing=8 if mobile else 12,
        controls=[
            kpi_clicavel(
                titulo="Limite Total",
                valor_control=txt_total_limite,
                subtitulo="Soma dos cartões",
                icone=ft.Icons.ACCOUNT_BALANCE_WALLET_ROUNDED,
                cor=T.TEXT_PRIMARY,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
                on_click=lambda _: _mudar_aba("cartoes"),
            ),
            kpi_clicavel(
                titulo="Limite Disponível",
                valor_control=txt_total_disponivel,
                subtitulo="Folga para compras",
                icone=ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED,
                cor=T.PRIMARY,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
                on_click=lambda _: _mudar_aba("cartoes"),
            ),
            kpi_clicavel(
                titulo="Faturas Abertas",
                valor_control=txt_total_faturas,
                subtitulo="Total a pagar no filtro",
                icone=ft.Icons.PENDING_ACTIONS_ROUNDED,
                cor=T.WARNING,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
                on_click=lambda _: _mudar_aba("abertas"),
            ),
            kpi_clicavel(
                titulo="Faturas do Filtro",
                valor_control=txt_faturas_filtro,
                subtitulo="Total no período filtrado",
                icone=ft.Icons.CALENDAR_MONTH_ROUNDED,
                cor=T.INFO,
                col={"xs": 6, "sm": 6, "md": 3},
                mobile=mobile,
                compacto=mobile,
                on_click=lambda _: _mudar_aba("abertas"),
            ),
        ],
    )

    # ── Cabeçalho Responsivo (Mobile & Desktop) ──────────────────────────────
    btn_novo_cartao = ft.FilledButton(
        content=ft.Row(
            spacing=6,
            tight=not mobile,
            alignment=ft.MainAxisAlignment.CENTER if mobile else ft.MainAxisAlignment.START,
            controls=[
                ft.Icon(ft.Icons.ADD_ROUNDED, color=ft.Colors.WHITE, size=18),
                ft.Text("Novo Cartão", color=ft.Colors.WHITE, size=13.5, weight=ft.FontWeight.W_600),
            ],
        ),
        on_click=lambda _: abrir_modal_cartao(),
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            overlay_color=T.PRIMARY_DARK,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=16, v=12),
        ),
        expand=mobile or None,
    )

    cabecalho = ft.ResponsiveRow(
        spacing=8,
        run_spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(
                col={"xs": 12, "sm": 7, "md": 8},
                content=ft.Column(
                    spacing=2,
                    controls=[
                        ft.Row(
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Text(
                                    "Cartões de Crédito",
                                    color=T.TEXT_PRIMARY,
                                    size=20 if mobile else 22,
                                    weight=ft.FontWeight.BOLD,
                                ),
                                spinner,
                            ],
                        ),
                        txt_sub_periodo_cartoes,
                    ],
                ),
            ),
            ft.Container(
                col={"xs": 12, "sm": 5, "md": 4},
                alignment=ft.Alignment(-1, 0) if mobile else ft.Alignment(1, 0),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.START if mobile else ft.MainAxisAlignment.END,
                    controls=[btn_novo_cartao],
                ),
            ),
        ],
    )

    def on_mes_ano_change(m: int, a: int):
        est = obter_estado_periodo_atual(page)
        mes_sel[0] = m
        ano_sel[0] = a
        di_r = est.get("data_inicio")
        df_r = est.get("data_fim")
        if isinstance(di_r, date):
            data_ini_sel[0] = di_r.isoformat()
        if isinstance(df_r, date):
            data_fim_sel[0] = df_r.isoformat()
        carregar_cartoes(inicial=False)

    def on_periodo_change(d_ini: str, d_fim: str, m: int, a: int):
        mes_sel[0] = m
        ano_sel[0] = a
        data_ini_sel[0] = d_ini
        data_fim_sel[0] = d_fim
        carregar_cartoes(inicial=False)

    conteudo = ft.Column(
        spacing=0,
        controls=[
            cabecalho,
            ft.Container(height=16),
            kpis_topo,
            ft.Container(height=16),
            cnt_banner_melhor,
            ft.Container(height=16),
            ft.Row(
                alignment=ft.MainAxisAlignment.START,
                scroll=ft.ScrollMode.AUTO if mobile else None,
                controls=[seg_aba],
            ),
            ft.Container(height=16),
            grid_conteudo,
            ft.Container(height=30),
        ],
    )

    carregar_cartoes(inicial=True)

    return criar_shell(
        page,
        rota_ativa=ROTA_CARTOES,
        conteudo=conteudo,
        on_mes_ano_change=on_mes_ano_change,
        on_periodo_change=on_periodo_change,
        on_lancamento_saved=lambda: carregar_cartoes(inicial=False),
    )
