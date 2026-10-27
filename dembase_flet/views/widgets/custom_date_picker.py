"""
=============================================================================
DemBase v3 — views/widgets/custom_date_picker.py  (Flet 1.0.1)
Seletor de Datas e Períodos estilo Mobills:
1. CustomCalendarGrid: Grade interativa de calendário com navegação rápida de
   mês/ano e suporte a seleção de data única ("single") e intervalo ("range").
2. abrir_seletor_data_modal: Modal elegante para seleção de data individual
   (Lançamentos, Vencimentos, etc.) com atalhos rápidos (Ontem, Hoje, Amanhã).
3. abrir_modal_periodo_mobills: Modal definitivo de períodos com:
   - Barra de "⭐ Filtros Salvos (Mais Usados)": 'Dia 05 a 20', 'Dia 20 a 30/31',
     '1ª Quinzena (01 a 15)', '2ª Quinzena (16 a 30/31)', 'Mês Inteiro', mais
     filtros personalizados salvos pelo usuário.
   - "Mensal": Grade 4x3 de 12 meses com seleção instantânea em 1 toque.
   - "Ciclos & Atalhos": Presets rápidos e ciclo flexível (dia de salário).
   - "Personalizado": Calendário visual de seleção de intervalo + botão para
     salvar qualquer intervalo nos Favoritos ("Mais Usados").
4. CampoSeletorData: Componente visual de campo para formulários com visual
   premium, atalhos rápidos e abertura integrada do modal.
=============================================================================
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Callable
import flet as ft

from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import formatar_data_br
from core.periodo import calcular_ciclo, calcular_intervalo_dias_mes
from core import storage

# =============================================================================
# CONSTANTES DE IDIOMA (PORTUGUÊS BRASIL)
# =============================================================================
MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]

MESES_CURTOS_PT = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez"
]

DIAS_SEMANA_ABREV = ["Dom", "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb"]

DIAS_SEMANA_COMPLETO = [
    "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
    "Sexta-feira", "Sábado", "Domingo"
]

DIAS_SEMANA_CURTO = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]


def formatar_data_amigavel(d: date, incluir_ano: bool = False) -> str:
    """Formata uma data de forma amigável (Ex: 'Hoje, 20 de Outubro')."""
    hoje = date.today()
    if d == hoje:
        return f"Hoje, {d.day} de {MESES_PT[d.month - 1]}"
    if d == hoje - timedelta(days=1):
        return f"Ontem, {d.day} de {MESES_PT[d.month - 1]}"
    if d == hoje + timedelta(days=1):
        return f"Amanhã, {d.day} de {MESES_PT[d.month - 1]}"

    nome_dia = DIAS_SEMANA_COMPLETO[d.weekday()]
    if d.year == hoje.year and not incluir_ano:
        return f"{nome_dia}, {d.day} de {MESES_PT[d.month - 1]}"
    return f"{nome_dia}, {d.day} de {MESES_PT[d.month - 1]} de {d.year}"


def formatar_data_curta_amigavel(d: date) -> str:
    """Formata uma data de forma concisa para chips e botões (Ex: 'Hoje', 'Ontem' ou '20/10')."""
    hoje = date.today()
    if d == hoje:
        return "Hoje"
    if d == hoje - timedelta(days=1):
        return "Ontem"
    if d == hoje + timedelta(days=1):
        return "Amanhã"
    return d.strftime("%d/%m")


# =============================================================================
# COMPONENTE 1: GRADE INTERATIVA DE CALENDÁRIO (SINGLE / RANGE)
# =============================================================================
class CustomCalendarGrid(ft.Container):
    """
    Grade de calendário customizada inspirada no Mobills.
    Suporta seleção individual (single) e de intervalo (range).
    Possui troca rápida de mês/ano com visualizador de 12 meses integrado.
    """

    def __init__(
        self,
        ano: int | None = None,
        mes: int | None = None,
        data_selecionada: date | None = None,
        range_inicio: date | None = None,
        range_fim: date | None = None,
        modo: str = "single",  # "single" ou "range"
        on_date_click: Callable[[date], None] | None = None,
        on_range_change: Callable[[date | None, date | None], None] | None = None,
        on_month_change: Callable[[int, int], None] | None = None,
    ):
        super().__init__()
        hoje = date.today()
        self.ano = ano or (data_selecionada.year if data_selecionada else hoje.year)
        self.mes = mes or (data_selecionada.month if data_selecionada else hoje.month)
        self.modo = modo
        self.data_selecionada = data_selecionada or hoje
        self.range_inicio = range_inicio
        self.range_fim = range_fim
        self.fixar_inicio_hoje = False
        self.on_date_click = on_date_click
        self.on_range_change = on_range_change
        self.on_month_change = on_month_change

        self.mostrar_grade_meses = False

        self.lbl_mes_ano = ft.Text(
            f"{MESES_PT[self.mes - 1]} {self.ano}",
            size=15,
            weight=ft.FontWeight.BOLD,
            color=T.TEXT_PRIMARY,
        )
        self.btn_nav_mes = ft.Container(
            content=ft.Row(
                spacing=4,
                tight=True,
                controls=[
                    self.lbl_mes_ano,
                    ft.Icon(ft.Icons.ARROW_DROP_DOWN_ROUNDED, size=18, color=T.PRIMARY),
                ],
            ),
            padding=pad(h=8, v=4),
            border_radius=8,
            ink=True,
            on_click=self._toggle_visao_meses,
            tooltip="Mudar mês ou ano",
        )

        self.col_dias = ft.Column(spacing=4, tight=True)
        self.col_meses = ft.Column(spacing=8, tight=True, visible=False)

        self.content = ft.Column(
            spacing=8,
            tight=True,
            controls=[
                self._construir_cabecalho_nav(),
                self.col_dias,
                self.col_meses,
            ],
        )
        self._reconstruir_grade()

    def _construir_cabecalho_nav(self) -> ft.Row:
        return ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                    icon_color=T.TEXT_PRIMARY,
                    icon_size=20,
                    tooltip="Mês anterior",
                    on_click=lambda _: self._mudar_mes(-1),
                ),
                self.btn_nav_mes,
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                    icon_color=T.TEXT_PRIMARY,
                    icon_size=20,
                    tooltip="Próximo mês",
                    on_click=lambda _: self._mudar_mes(1),
                ),
            ],
        )

    def _toggle_visao_meses(self, _=None):
        self.mostrar_grade_meses = not self.mostrar_grade_meses
        self.col_dias.visible = not self.mostrar_grade_meses
        self.col_meses.visible = self.mostrar_grade_meses
        if self.mostrar_grade_meses:
            self._reconstruir_grade_meses()
        self._safe_update()

    def _mudar_mes(self, passo: int):
        if self.mostrar_grade_meses:
            self.ano += passo
            self._reconstruir_grade_meses()
        else:
            m = self.mes + passo
            if m < 1:
                self.mes = 12
                self.ano -= 1
            elif m > 12:
                self.mes = 1
                self.ano += 1
            else:
                self.mes = m
            self._reconstruir_grade()

        self.lbl_mes_ano.value = f"{MESES_PT[self.mes - 1]} {self.ano}"
        if callable(self.on_month_change):
            self.on_month_change(self.mes, self.ano)
        self._safe_update()

    def _selecionar_mes_direto(self, novo_mes: int):
        self.mes = novo_mes
        self.mostrar_grade_meses = False
        self.col_dias.visible = True
        self.col_meses.visible = False
        self.lbl_mes_ano.value = f"{MESES_PT[self.mes - 1]} {self.ano}"
        self._reconstruir_grade()
        if callable(self.on_month_change):
            self.on_month_change(self.mes, self.ano)
        self._safe_update()

    def _reconstruir_grade_meses(self):
        """Constrói a grade 4x3 para seleção rápida de mês com seletor de ano."""
        hoje = date.today()
        self.lbl_mes_ano.value = f"Ano {self.ano}"

        linhas: list[ft.Row] = []
        for r in range(3):
            controles_linha: list[ft.Control] = []
            for c in range(4):
                idx_mes = r * 4 + c + 1
                nome_m = MESES_CURTOS_PT[idx_mes - 1]
                eh_selecionado = (idx_mes == self.mes)
                eh_mes_atual = (idx_mes == hoje.month and self.ano == hoje.year)

                cor_bg = T.PRIMARY if eh_selecionado else (f"{T.PRIMARY}18" if eh_mes_atual else T.SURFACE_ALT)
                cor_txt = T.ON_PRIMARY if eh_selecionado else (T.PRIMARY if eh_mes_atual else T.TEXT_PRIMARY)

                btn_m = ft.Container(
                    content=ft.Text(
                        nome_m,
                        size=13,
                        weight=ft.FontWeight.BOLD if eh_selecionado or eh_mes_atual else ft.FontWeight.W_500,
                        color=cor_txt,
                    ),
                    alignment=ft.Alignment(0, 0),
                    padding=pad(v=10),
                    bgcolor=cor_bg,
                    border_radius=10,
                    border=borda(1, T.PRIMARY if (eh_selecionado or eh_mes_atual) else T.BORDER),
                    expand=True,
                    ink=True,
                    on_click=lambda _, m=idx_mes: self._selecionar_mes_direto(m),
                )
                controles_linha.append(btn_m)
            linhas.append(ft.Row(controls=controles_linha, spacing=6))

        self.col_meses.controls = [
            ft.Text("Selecione um mês:", size=11.5, color=T.TEXT_MUTED),
            *linhas,
        ]

    def _reconstruir_grade(self):
        hoje = date.today()
        cal = calendar.Calendar(firstweekday=6)  # Domingo como primeiro dia da semana
        semanas = cal.monthdatescalendar(self.ano, self.mes)

        header_dias = ft.Row(
            spacing=2,
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Container(
                    width=38,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(d_nome, size=11, weight=ft.FontWeight.BOLD, color=T.TEXT_MUTED),
                )
                for d_nome in DIAS_SEMANA_ABREV
            ],
        )

        linhas_semanas: list[ft.Row] = []
        for sem in semanas:
            celulas: list[ft.Control] = []
            for d in sem:
                eh_mes_corrente = (d.month == self.mes)
                eh_hoje = (d == hoje)

                if self.modo == "single":
                    eh_selecionado = (d == self.data_selecionada)
                    esta_no_intervalo = False
                else:
                    eh_selecionado = (d == self.range_inicio or d == self.range_fim)
                    esta_no_intervalo = (
                        bool(self.range_inicio and self.range_fim)
                        and (self.range_inicio < d < self.range_fim)
                    )

                if eh_selecionado:
                    cor_bg = T.PRIMARY
                    cor_txt = T.ON_PRIMARY
                    peso_txt = ft.FontWeight.BOLD
                    radius = 19
                    border_ctrl = None
                elif esta_no_intervalo:
                    cor_bg = f"{T.PRIMARY}2B"
                    cor_txt = T.TEXT_PRIMARY
                    peso_txt = ft.FontWeight.W_600
                    radius = 4
                    border_ctrl = None
                elif eh_hoje:
                    cor_bg = f"{T.PRIMARY}15"
                    cor_txt = T.PRIMARY
                    peso_txt = ft.FontWeight.BOLD
                    radius = 19
                    border_ctrl = borda(1, T.PRIMARY)
                else:
                    cor_bg = "transparent"
                    cor_txt = T.TEXT_PRIMARY if eh_mes_corrente else T.TEXT_MUTED
                    peso_txt = ft.FontWeight.NORMAL
                    radius = 19
                    border_ctrl = None

                opacity = 1.0 if eh_mes_corrente else 0.35

                celula = ft.Container(
                    width=38,
                    height=36,
                    alignment=ft.Alignment(0, 0),
                    bgcolor=cor_bg,
                    border_radius=radius,
                    border=border_ctrl,
                    opacity=opacity,
                    ink=True,
                    on_click=lambda _, dia=d: self._clicar_dia(dia),
                    content=ft.Text(
                        str(d.day),
                        size=12.5,
                        weight=peso_txt,
                        color=cor_txt,
                    ),
                )
                celulas.append(celula)

            linhas_semanas.append(
                ft.Row(
                    spacing=2,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=celulas,
                )
            )

        self.col_dias.controls = [header_dias, *linhas_semanas]

    def _clicar_dia(self, d: date):
        if d.month != self.mes:
            self.mes = d.month
            self.ano = d.year
            self.lbl_mes_ano.value = f"{MESES_PT[self.mes - 1]} {self.ano}"
            if callable(self.on_month_change):
                self.on_month_change(self.mes, self.ano)

        if self.modo == "single":
            self.data_selecionada = d
            self._reconstruir_grade()
            self._safe_update()
            if callable(self.on_date_click):
                self.on_date_click(d)
        else:
            if getattr(self, "fixar_inicio_hoje", False):
                hoje_fix = date.today()
                self.range_inicio = hoje_fix
                self.range_fim = d if d >= hoje_fix else hoje_fix
            elif self.range_inicio is None or (self.range_inicio is not None and self.range_fim is not None):
                self.range_inicio = d
                self.range_fim = None
            else:
                if d < self.range_inicio:
                    self.range_inicio, self.range_fim = d, self.range_inicio
                else:
                    self.range_fim = d

            self._reconstruir_grade()
            self._safe_update()
            if callable(self.on_range_change):
                self.on_range_change(self.range_inicio, self.range_fim)

    def definir_data(self, d: date):
        """Atualiza a data selecionada externamente e redesenha."""
        self.data_selecionada = d
        self.mes = d.month
        self.ano = d.year
        self.lbl_mes_ano.value = f"{MESES_PT[self.mes - 1]} {self.ano}"
        self._reconstruir_grade()
        self._safe_update()

    def definir_range(self, d_ini: date | None, d_fim: date | None):
        """Atualiza o intervalo selecionado externamente e redesenha."""
        self.range_inicio = d_ini
        self.range_fim = d_fim
        if d_fim:
            self.mes = d_fim.month
            self.ano = d_fim.year
            self.lbl_mes_ano.value = f"{MESES_PT[self.mes - 1]} {self.ano}"
        self._reconstruir_grade()
        self._safe_update()

    def _safe_update(self):
        try:
            if self.page:
                self.update()
        except Exception:
            pass


# =============================================================================
# COMPONENTE 2: MODAL SELETOR DE DATA INDIVIDUAL (MOBILLS STYLE)
# =============================================================================
def abrir_seletor_data_modal(
    page: ft.Page,
    data_inicial: date | None = None,
    on_select: Callable[[date], None] | None = None,
    titulo: str = "Selecionar Data",
):
    data_sel = [data_inicial or date.today()]

    lbl_data_extenso = ft.Text(
        formatar_data_amigavel(data_sel[0]),
        size=15,
        weight=ft.FontWeight.BOLD,
        color=T.PRIMARY,
    )

    def _atualizar_label():
        lbl_data_extenso.value = formatar_data_amigavel(data_sel[0])
        try:
            lbl_data_extenso.update()
        except Exception:
            pass

    def _ao_clicar_data(d: date):
        data_sel[0] = d
        _atualizar_label()
        _atualizar_chips_atalhos()

    grid_cal = CustomCalendarGrid(
        ano=data_sel[0].year,
        mes=data_sel[0].month,
        data_selecionada=data_sel[0],
        modo="single",
        on_date_click=_ao_clicar_data,
    )

    def _aplicar_atalho(d: date):
        data_sel[0] = d
        grid_cal.definir_data(d)
        _atualizar_label()
        _atualizar_chips_atalhos()

    row_atalhos = ft.Row(spacing=6, tight=True)

    def _atualizar_chips_atalhos():
        hoje = date.today()
        opcoes = [
            ("Ontem", hoje - timedelta(days=1)),
            ("Hoje", hoje),
            ("Amanhã", hoje + timedelta(days=1)),
        ]
        row_atalhos.controls.clear()
        for lbl, dt_val in opcoes:
            ativo = (data_sel[0] == dt_val)
            row_atalhos.controls.append(
                ft.Container(
                    content=ft.Text(
                        lbl,
                        size=11.5,
                        weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                        color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                    ),
                    padding=pad(h=12, v=6),
                    bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                    border_radius=14,
                    border=borda(1, T.PRIMARY if ativo else T.BORDER),
                    ink=True,
                    on_click=lambda _, dt=dt_val: _aplicar_atalho(dt),
                )
            )
        try:
            row_atalhos.update()
        except Exception:
            pass

    _atualizar_chips_atalhos()

    def _confirmar(_):
        page.pop_dialog()
        if callable(on_select):
            on_select(data_sel[0])

    dlg = ft.AlertDialog(
        bgcolor=T.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=18),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=20),
                        ft.Text(titulo, color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_color=T.TEXT_MUTED,
                    icon_size=18,
                    on_click=lambda _: page.pop_dialog(),
                ),
            ],
        ),
        content=ft.Container(
            width=330,
            content=ft.Column(
                tight=True,
                spacing=12,
                controls=[
                    ft.Container(
                        padding=pad(h=12, v=10),
                        bgcolor=f"{T.PRIMARY}15",
                        border_radius=12,
                        border=borda(1, f"{T.PRIMARY}35"),
                        content=ft.Row(
                            spacing=8,
                            controls=[
                                ft.Icon(ft.Icons.EVENT_AVAILABLE_ROUNDED, color=T.PRIMARY, size=18),
                                lbl_data_extenso,
                            ],
                        ),
                    ),
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        controls=[row_atalhos],
                    ),
                    ft.Divider(height=1, color=T.BORDER),
                    grid_cal,
                ],
            ),
        ),
        actions=[
            ft.TextButton(
                "Cancelar",
                style=ft.ButtonStyle(color=T.TEXT_MUTED),
                on_click=lambda _: page.pop_dialog(),
            ),
            ft.FilledButton(
                content=ft.Row(
                    spacing=6,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.CHECK_ROUNDED, color=T.ON_PRIMARY, size=16),
                        ft.Text("Confirmar", color=T.ON_PRIMARY, weight=ft.FontWeight.BOLD),
                    ],
                ),
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                on_click=_confirmar,
            ),
        ],
    )
    page.show_dialog(dlg)


# =============================================================================
# COMPONENTE 3: MODAL DE PERÍODO DEFINITIVO (MOBILLS STYLE + FILTROS SALVOS)
# =============================================================================
def abrir_modal_periodo_mobills(
    page: ft.Page,
    estado_periodo: dict,
    on_confirm: Callable[[dict], None],
):
    """
    Modal de seleção de período flexível com usabilidade de alta performance:
    - Barra permanente de '⭐ Filtros Mais Usados (Salvos)':
      'Dia 05 a 20', 'Dia 20 a 30/31', '1ª Quinzena', '2ª Quinzena', 'Mês Inteiro'
      + filtros personalizados salvos pelo usuário (aplicação em 1 clique!).
    - Aba 'Mensal': Navegação de anos e grade de 12 meses.
    - Aba 'Ciclos & Atalhos': Ciclo Salarial configurável e atalhos rápidos.
    - Aba 'Personalizado': Calendário visual com seleção de intervalo (Início → Fim)
      e botão '⭐ Salvar nos Favoritos'.
    """
    d_ini_init = estado_periodo["data_inicio"]
    d_fim_init = estado_periodo["data_fim"]
    if isinstance(d_ini_init, str):
        d_ini_init = date.fromisoformat(d_ini_init[:10])
    if isinstance(d_fim_init, str):
        d_fim_init = date.fromisoformat(d_fim_init[:10])

    temp_ini = [d_ini_init]
    temp_fim = [d_fim_init]
    temp_modo = [estado_periodo.get("modo", "mes")]
    temp_dia_ciclo = [estado_periodo.get("dia_ciclo", 1)]
    temp_ano_mensal = [int(estado_periodo.get("ano", temp_fim[0].year))]
    temp_mes_mensal = [int(estado_periodo.get("mes", temp_fim[0].month))]
    temp_ate_fim_mes = [bool(estado_periodo.get("ate_fim_mes", False))]
    temp_filtro_id = [estado_periodo.get("filtro_id")]

    aba_ativa = [0 if temp_modo[0] == "mes" else (1 if temp_modo[0] == "ciclo" else 2)]

    # -------------------------------------------------------------------------
    # SEÇÃO GLOBAL: FILTROS SALVOS / MAIS USADOS (1-CLICK)
    # -------------------------------------------------------------------------
    row_filtros_salvos = ft.Row(spacing=6, wrap=True)

    def _aplicar_filtro_salvo(fav: dict):
        m = temp_mes_mensal[0]
        a = temp_ano_mensal[0]
        dia_i = int(fav.get("dia_ini") or 1)
        dia_f = int(fav.get("dia_fim") or 31)
        ate_fim = bool(fav.get("ate_fim_mes", False))
        fid = fav.get("id")

        d_i, d_f = calcular_intervalo_dias_mes(m, a, dia_i, dia_f, ate_fim_mes=ate_fim)
        ult_m = calendar.monthrange(a, m)[1]
        eh_mes_cheio = (d_i.day == 1 and d_f.day == ult_m)

        estado_res = {
            "modo": "mes" if eh_mes_cheio else "faixa_mes",
            "mes": m,
            "ano": a,
            "data_inicio": d_i,
            "data_fim": d_f,
            "dia_ciclo": temp_dia_ciclo[0],
            "ate_fim_mes": ate_fim,
            "filtro_id": fid,
        }
        page.pop_dialog()
        if callable(on_confirm):
            on_confirm(estado_res)

    def _remover_favorito_custom(fid: str):
        storage.remover_filtro_periodo_favorito_sync(page, fid)
        _reconstruir_chips_favoritos()
        try:
            page.update()
        except Exception:
            pass

    def _reconstruir_chips_favoritos():
        favoritos = storage.obter_filtros_periodo_favoritos(page)
        row_filtros_salvos.controls.clear()
        m = temp_mes_mensal[0]
        a = temp_ano_mensal[0]
        ult_m = calendar.monthrange(a, m)[1]

        for fav in favoritos:
            fid = str(fav.get("id") or "")
            nome_f = str(fav.get("nome") or "")
            d_i_f = int(fav.get("dia_ini") or 1)
            d_f_f = ult_m if fav.get("ate_fim_mes") else min(ult_m, int(fav.get("dia_fim") or ult_m))
            eh_fixo = bool(fav.get("fixo", True))

            ativo = (
                temp_ini[0].month == m
                and temp_fim[0].month == m
                and temp_ini[0].day == min(ult_m, d_i_f)
                and temp_fim[0].day == d_f_f
            )

            controles_chip: list[ft.Control] = [
                ft.Icon(
                    ft.Icons.BOOKMARK_ROUNDED if ativo else ft.Icons.BOOKMARK_BORDER_ROUNDED,
                    size=13,
                    color=T.ON_PRIMARY if ativo else T.PRIMARY,
                ),
                ft.Text(
                    nome_f,
                    size=11.5,
                    weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_600,
                    color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                ),
            ]
            if not eh_fixo:
                controles_chip.append(
                    ft.GestureDetector(
                        on_tap=lambda _, id_rm=fid: _remover_favorito_custom(id_rm),
                        content=ft.Icon(
                            ft.Icons.CLOSE_ROUNDED,
                            size=13,
                            color=T.ON_PRIMARY if ativo else T.TEXT_MUTED,
                        ),
                    )
                )

            row_filtros_salvos.controls.append(
                ft.Container(
                    padding=pad(h=10, v=6),
                    bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                    border_radius=12,
                    border=borda(1, T.PRIMARY if ativo else f"{T.PRIMARY}45"),
                    ink=True,
                    tooltip=f"Aplicar {nome_f} em {MESES_PT[m - 1]}/{a}",
                    on_click=lambda _, f_item=fav: _aplicar_filtro_salvo(f_item),
                    content=ft.Row(spacing=4, tight=True, controls=controles_chip),
                )
            )

        # Atalho Rápido de Projeção (De Hoje até Fim do Mês) e botão para Projeção Livre (Hoje → Data Futura)
        hoje_chip = date.today()
        ult_hoje = calendar.monthrange(hoje_chip.year, hoje_chip.month)[1]
        fim_mes_hoje = date(hoje_chip.year, hoje_chip.month, ult_hoje)
        ativo_proj_mes = (temp_ini[0] == hoje_chip and temp_fim[0] == fim_mes_hoje and temp_modo[0] != "mes")

        def _aplicar_projecao_fim_mes(_=None):
            estado_res = {
                "modo": "projecao",
                "mes": fim_mes_hoje.month,
                "ano": fim_mes_hoje.year,
                "data_inicio": hoje_chip,
                "data_fim": fim_mes_hoje,
                "dia_ciclo": temp_dia_ciclo[0],
                "ate_fim_mes": True,
                "filtro_id": "projecao_fim_mes",
            }
            page.pop_dialog()
            if callable(on_confirm):
                on_confirm(estado_res)

        row_filtros_salvos.controls.append(
            ft.Container(
                padding=pad(h=10, v=6),
                bgcolor=T.RECEITA if ativo_proj_mes else f"{T.RECEITA}18",
                border_radius=12,
                border=borda(1, T.RECEITA if ativo_proj_mes else f"{T.RECEITA}55"),
                ink=True,
                tooltip=f"Prever fluxo de caixa de Hoje ({formatar_data_br(hoje_chip)}) até {formatar_data_br(fim_mes_hoje)}",
                on_click=_aplicar_projecao_fim_mes,
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(
                            ft.Icons.TRENDING_UP_ROUNDED,
                            size=13,
                            color="#0F172A" if ativo_proj_mes else T.RECEITA,
                        ),
                        ft.Text(
                            "De Hoje até Fim do Mês",
                            size=11.5,
                            weight=ft.FontWeight.BOLD,
                            color="#0F172A" if ativo_proj_mes else T.RECEITA,
                        ),
                    ],
                ),
            )
        )

        row_filtros_salvos.controls.append(
            ft.Container(
                padding=pad(h=10, v=6),
                bgcolor=f"{T.PRIMARY}18",
                border_radius=12,
                border=borda(1, f"{T.PRIMARY}55"),
                ink=True,
                tooltip="Abrir aba Personalizado com início travado em Hoje para escolher a data futura alvo",
                on_click=lambda _: _ativar_modo_projecao_custom(),
                content=ft.Row(
                    spacing=4,
                    tight=True,
                    controls=[
                        ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, size=13, color=T.PRIMARY),
                        ft.Text(
                            "Projeção (Hoje → Data Futura)",
                            size=11.5,
                            weight=ft.FontWeight.BOLD,
                            color=T.PRIMARY,
                        ),
                    ],
                ),
            )
        )

    _reconstruir_chips_favoritos()

    bloco_filtros_salvos = ft.Container(
        padding=pad(h=10, v=8),
        bgcolor=f"{T.SURFACE_ALT}90",
        border_radius=12,
        border=borda(),
        content=ft.Column(
            spacing=6,
            tight=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=5,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.STAR_ROUNDED, size=15, color=T.WARNING),
                                ft.Text(
                                    "Filtros Salvos (Mais Usados):",
                                    size=11.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        ft.Text(
                            "1 clique para aplicar",
                            size=10,
                            color=T.TEXT_MUTED,
                        ),
                    ],
                ),
                row_filtros_salvos,
            ],
        ),
    )

    # -------------------------------------------------------------------------
    # ABA 1: VISÃO MENSAL (1-TAP INSTANTÂNEO)
    # -------------------------------------------------------------------------
    lbl_ano_mensal = ft.Text(str(temp_ano_mensal[0]), size=16, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY)

    def _mudar_ano_mensal(passo: int):
        temp_ano_mensal[0] += passo
        lbl_ano_mensal.value = str(temp_ano_mensal[0])
        _reconstruir_grid_12_meses()
        _reconstruir_chips_favoritos()
        try:
            page.update()
        except Exception:
            pass

    def _selecionar_mes_imediato(mes_num: int):
        temp_mes_mensal[0] = mes_num
        a = temp_ano_mensal[0]
        # Se o usuário estava com uma faixa salva ativa (ex: Dia 05 a 20 ou Dia 20 a 30/31),
        # mantém o mês atualizado mas aplica o mês cheio (ou permite clicar nos chips salvos acima)
        ult = calendar.monthrange(a, mes_num)[1]
        estado_resultado = {
            "modo": "mes",
            "mes": mes_num,
            "ano": a,
            "data_inicio": date(a, mes_num, 1),
            "data_fim": date(a, mes_num, ult),
            "dia_ciclo": temp_dia_ciclo[0],
            "ate_fim_mes": True,
            "filtro_id": "mes_inteiro",
        }
        page.pop_dialog()
        if callable(on_confirm):
            on_confirm(estado_resultado)

    col_12_meses = ft.Column(spacing=8, tight=True)

    def _reconstruir_grid_12_meses():
        hoje = date.today()
        col_12_meses.controls.clear()
        for r in range(3):
            linha: list[ft.Control] = []
            for c in range(4):
                idx = r * 4 + c + 1
                nome_m = MESES_CURTOS_PT[idx - 1]
                eh_ativo = (idx == temp_mes_mensal[0] and temp_ano_mensal[0] == estado_periodo.get("ano", hoje.year))
                eh_hoje = (idx == hoje.month and temp_ano_mensal[0] == hoje.year)

                cor_bg = T.PRIMARY if eh_ativo else (f"{T.PRIMARY}18" if eh_hoje else T.SURFACE_ALT)
                cor_txt = T.ON_PRIMARY if eh_ativo else (T.PRIMARY if eh_hoje else T.TEXT_PRIMARY)

                btn = ft.Container(
                    content=ft.Column(
                        alignment=ft.MainAxisAlignment.CENTER,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=2,
                        controls=[
                            ft.Text(
                                nome_m,
                                size=13.5,
                                weight=ft.FontWeight.BOLD if eh_ativo or eh_hoje else ft.FontWeight.W_500,
                                color=cor_txt,
                            ),
                            ft.Container(
                                width=4,
                                height=4,
                                border_radius=2,
                                bgcolor=T.ON_PRIMARY if eh_ativo else T.PRIMARY,
                                visible=eh_hoje,
                            ),
                        ],
                    ),
                    padding=pad(v=12),
                    bgcolor=cor_bg,
                    border_radius=12,
                    border=borda(1, T.PRIMARY if (eh_ativo or eh_hoje) else T.BORDER),
                    expand=True,
                    ink=True,
                    tooltip=f"Ver {MESES_PT[idx-1]} de {temp_ano_mensal[0]}",
                    on_click=lambda _, m=idx: _selecionar_mes_imediato(m),
                )
                linha.append(btn)
            col_12_meses.controls.append(ft.Row(controls=linha, spacing=8))

    _reconstruir_grid_12_meses()

    conteudo_aba_mensal = ft.Column(
        spacing=12,
        tight=True,
        controls=[
            ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_LEFT_ROUNDED,
                        icon_color=T.TEXT_PRIMARY,
                        tooltip="Ano anterior",
                        on_click=lambda _: _mudar_ano_mensal(-1),
                    ),
                    ft.Container(
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.CALENDAR_TODAY_ROUNDED, size=15, color=T.PRIMARY),
                                lbl_ano_mensal,
                            ],
                        ),
                        padding=pad(h=12, v=4),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=16,
                        border=borda(),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.CHEVRON_RIGHT_ROUNDED,
                        icon_color=T.TEXT_PRIMARY,
                        tooltip="Próximo ano",
                        on_click=lambda _: _mudar_ano_mensal(1),
                    ),
                ],
            ),
            col_12_meses,
            ft.Text(
                "💡 Dica: Escolha um filtro salvo acima (ex: 1ª Quinzena, 2ª Quinzena ou Projeção) ou toque em um mês.",
                size=11,
                color=T.TEXT_MUTED,
                italic=True,
            ),
        ],
    )

    # -------------------------------------------------------------------------
    # ABA 2: CICLOS & ATALHOS RÁPIDOS
    # -------------------------------------------------------------------------
    lbl_preview_ciclo = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=T.PRIMARY)
    row_chips_dias_ciclo = ft.Row(spacing=6, wrap=True)

    def _atualizar_preview_ciclo():
        d_i, d_f = calcular_ciclo(temp_mes_mensal[0], temp_ano_mensal[0], temp_dia_ciclo[0])
        qtd_dias = (d_f - d_i).days + 1
        lbl_preview_ciclo.value = f"{formatar_data_br(d_i)}  até  {formatar_data_br(d_f)}  ({qtd_dias} dias)"
        try:
            lbl_preview_ciclo.update()
        except Exception:
            pass

    def _selecionar_dia_ciclo(dia_novo: int):
        temp_dia_ciclo[0] = dia_novo
        temp_modo[0] = "ciclo"
        _atualizar_chips_ciclo()
        _atualizar_preview_ciclo()

    def _atualizar_chips_ciclo():
        row_chips_dias_ciclo.controls.clear()
        for d_cand in [1, 5, 10, 15, 20, 25]:
            ativo = (temp_dia_ciclo[0] == d_cand)
            lbl = "Mês Cheio (Dia 1)" if d_cand == 1 else f"Dia {d_cand}"
            row_chips_dias_ciclo.controls.append(
                ft.Container(
                    content=ft.Text(
                        lbl,
                        size=11.5,
                        weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                        color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                    ),
                    padding=pad(h=10, v=6),
                    bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                    border_radius=12,
                    border=borda(1, T.PRIMARY if ativo else T.BORDER),
                    ink=True,
                    on_click=lambda _, d=d_cand: _selecionar_dia_ciclo(d),
                )
            )
        try:
            row_chips_dias_ciclo.update()
        except Exception:
            pass

    _atualizar_chips_ciclo()
    _atualizar_preview_ciclo()

    def _aplicar_preset_rapido(codigo: str):
        hoje = date.today()
        temp_modo[0] = codigo
        if codigo == "mes_atual":
            ult = calendar.monthrange(hoje.year, hoje.month)[1]
            temp_ini[0] = date(hoje.year, hoje.month, 1)
            temp_fim[0] = date(hoje.year, hoje.month, ult)
            temp_mes_mensal[0] = hoje.month
            temp_ano_mensal[0] = hoje.year
            temp_ate_fim_mes[0] = True
        elif codigo == "30d":
            temp_fim[0] = hoje
            temp_ini[0] = hoje - timedelta(days=29)
            temp_ate_fim_mes[0] = False
        elif codigo == "7d":
            temp_fim[0] = hoje
            temp_ini[0] = hoje - timedelta(days=6)
            temp_ate_fim_mes[0] = False
        elif codigo == "ano_atual":
            temp_ini[0] = date(hoje.year, 1, 1)
            temp_fim[0] = date(hoje.year, 12, 31)
            temp_ate_fim_mes[0] = False

        _fechar_e_salvar()

    conteudo_aba_ciclos = ft.Column(
        spacing=12,
        tight=True,
        controls=[
            ft.Text("Atalhos Rápidos:", size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
            ft.Row(
                spacing=8,
                wrap=True,
                controls=[
                    ft.FilledButton(
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=15, color=T.ON_PRIMARY),
                                ft.Text("Mês Atual", color=T.ON_PRIMARY, size=12, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        style=ft.ButtonStyle(bgcolor=T.PRIMARY, shape=ft.RoundedRectangleBorder(radius=10)),
                        on_click=lambda _: _aplicar_preset_rapido("mes_atual"),
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Últimos 30 dias", size=12, color=T.TEXT_PRIMARY),
                        on_click=lambda _: _aplicar_preset_rapido("30d"),
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Últimos 7 dias", size=12, color=T.TEXT_PRIMARY),
                        on_click=lambda _: _aplicar_preset_rapido("7d"),
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Este Ano", size=12, color=T.TEXT_PRIMARY),
                        on_click=lambda _: _aplicar_preset_rapido("ano_atual"),
                    ),
                ],
            ),
            ft.Divider(height=1, color=T.BORDER),
            ft.Column(
                spacing=6,
                controls=[
                    ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.SYNC_ALT_ROUNDED, size=16, color=T.PRIMARY),
                            ft.Text("Ciclo Entre Meses (Ex: 20/Set a 19/Out):", size=12, weight=ft.FontWeight.BOLD, color=T.TEXT_PRIMARY),
                        ],
                    ),
                    ft.Text(
                        "Configure o dia em que seu ciclo entre meses se renova:",
                        size=11.5,
                        color=T.TEXT_MUTED,
                    ),
                ],
            ),
            row_chips_dias_ciclo,
            ft.Container(
                padding=pad(h=12, v=10),
                bgcolor=f"{T.PRIMARY}15",
                border_radius=10,
                border=borda(1, f"{T.PRIMARY}35"),
                content=ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.SCHEDULE_ROUNDED, color=T.PRIMARY, size=16),
                        lbl_preview_ciclo,
                    ],
                ),
            ),
            ft.FilledButton(
                content=ft.Text("Aplicar Ciclo Salarial", color=T.ON_PRIMARY, weight=ft.FontWeight.BOLD),
                style=ft.ButtonStyle(
                    bgcolor=T.PRIMARY,
                    shape=ft.RoundedRectangleBorder(radius=10),
                ),
                on_click=lambda _: _aplicar_ciclo_confirmado(),
            ),
        ],
    )

    def _aplicar_ciclo_confirmado():
        d_i, d_f = calcular_ciclo(temp_mes_mensal[0], temp_ano_mensal[0], temp_dia_ciclo[0])
        temp_ini[0] = d_i
        temp_fim[0] = d_f
        temp_modo[0] = "ciclo"
        temp_ate_fim_mes[0] = False
        _fechar_e_salvar()

    # -------------------------------------------------------------------------
    # ABA 3: PERSONALIZADO & PROJEÇÃO (VISUAL RANGE PICKER + SALVAR FAVORITOS)
    # -------------------------------------------------------------------------
    lbl_resumo_range = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=T.PRIMARY)
    modo_projecao_hoje = [temp_modo[0] == "projecao" or (temp_ini[0] == date.today() and temp_fim[0] >= date.today() and temp_modo[0] != "mes")]

    def _ao_mudar_range(ini: date | None, fim: date | None):
        if ini:
            temp_ini[0] = ini
        if fim:
            temp_fim[0] = fim
        elif ini:
            temp_fim[0] = ini
        temp_modo[0] = "projecao" if modo_projecao_hoje[0] else "custom"
        temp_mes_mensal[0] = temp_fim[0].month
        temp_ano_mensal[0] = temp_fim[0].year
        ult_f = calendar.monthrange(temp_fim[0].year, temp_fim[0].month)[1]
        temp_ate_fim_mes[0] = (
            temp_ini[0].month == temp_fim[0].month
            and temp_fim[0].day == ult_f
        )
        _atualizar_resumo_range()

    def _ao_mudar_mes_grid_custom(novo_m: int, novo_a: int):
        temp_mes_mensal[0] = novo_m
        temp_ano_mensal[0] = novo_a
        _reconstruir_chips_favoritos()
        try:
            row_filtros_salvos.update()
        except Exception:
            pass

    def _atualizar_resumo_range():
        d_i, d_f = temp_ini[0], temp_fim[0]
        if d_f < d_i:
            d_i, d_f = d_f, d_i
        qtd = (d_f - d_i).days + 1
        prefixo = "🚀 Projeção: " if modo_projecao_hoje[0] else ""
        lbl_resumo_range.value = f"{prefixo}{formatar_data_br(d_i)}  →  {formatar_data_br(d_f)}  ({qtd} dias)"
        try:
            lbl_resumo_range.update()
        except Exception:
            pass

    _atualizar_resumo_range()

    grid_range = CustomCalendarGrid(
        ano=temp_fim[0].year,
        mes=temp_fim[0].month,
        range_inicio=temp_ini[0],
        range_fim=temp_fim[0],
        modo="range",
        on_range_change=_ao_mudar_range,
        on_month_change=_ao_mudar_mes_grid_custom,
    )
    grid_range.fixar_inicio_hoje = modo_projecao_hoje[0]

    lbl_instrucao_custom = ft.Text(
        "🎯 Início travado em Hoje! Clique na data futura desejada no calendário:"
        if modo_projecao_hoje[0]
        else "Selecione o dia inicial e o dia final diretamente no calendário:",
        size=11.5,
        color=T.RECEITA if modo_projecao_hoje[0] else T.TEXT_MUTED,
        weight=ft.FontWeight.BOLD if modo_projecao_hoje[0] else ft.FontWeight.NORMAL,
    )

    sw_fixar_hoje = ft.Switch(
        value=modo_projecao_hoje[0],
        active_color=T.RECEITA,
        scale=0.82,
    )

    def _alternar_fixar_hoje(ativo_novo: bool):
        modo_projecao_hoje[0] = ativo_novo
        sw_fixar_hoje.value = ativo_novo
        grid_range.fixar_inicio_hoje = ativo_novo
        if ativo_novo:
            hoje_d = date.today()
            temp_ini[0] = hoje_d
            if temp_fim[0] < hoje_d:
                ult_h = calendar.monthrange(hoje_d.year, hoje_d.month)[1]
                temp_fim[0] = date(hoje_d.year, hoje_d.month, ult_h)
            temp_modo[0] = "projecao"
            grid_range.definir_range(temp_ini[0], temp_fim[0])
            lbl_instrucao_custom.value = "🎯 Início travado em Hoje! Clique na data futura desejada no calendário:"
            lbl_instrucao_custom.color = T.RECEITA
            lbl_instrucao_custom.weight = ft.FontWeight.BOLD
        else:
            temp_modo[0] = "custom"
            lbl_instrucao_custom.value = "Selecione o dia inicial e o dia final diretamente no calendário:"
            lbl_instrucao_custom.color = T.TEXT_MUTED
            lbl_instrucao_custom.weight = ft.FontWeight.NORMAL
        _atualizar_resumo_range()
        try:
            page.update()
        except Exception:
            pass

    sw_fixar_hoje.on_change = lambda e: _alternar_fixar_hoje(bool(e.control.value))

    def _aplicar_atalho_projecao_dias(dias_frente: int | None = None, fim_mes_atual: bool = False, fim_prox_mes: bool = False):
        hoje_d = date.today()
        modo_projecao_hoje[0] = True
        sw_fixar_hoje.value = True
        grid_range.fixar_inicio_hoje = True
        temp_ini[0] = hoje_d
        if fim_mes_atual:
            ult_h = calendar.monthrange(hoje_d.year, hoje_d.month)[1]
            temp_fim[0] = date(hoje_d.year, hoje_d.month, ult_h)
        elif fim_prox_mes:
            m_prox = 1 if hoje_d.month == 12 else hoje_d.month + 1
            a_prox = hoje_d.year + 1 if hoje_d.month == 12 else hoje_d.year
            ult_p = calendar.monthrange(a_prox, m_prox)[1]
            temp_fim[0] = date(a_prox, m_prox, ult_p)
        else:
            temp_fim[0] = hoje_d + timedelta(days=int(dias_frente or 15))
        temp_modo[0] = "projecao"
        temp_mes_mensal[0] = temp_fim[0].month
        temp_ano_mensal[0] = temp_fim[0].year
        grid_range.definir_range(temp_ini[0], temp_fim[0])
        _atualizar_resumo_range()
        try:
            page.update()
        except Exception:
            pass

    def _ativar_modo_projecao_custom():
        _alternar_fixar_hoje(True)
        _trocar_aba(2)

    barra_projecao_custom = ft.Container(
        padding=pad(h=10, v=6),
        bgcolor=f"{T.RECEITA}14",
        border_radius=10,
        border=borda(1, f"{T.RECEITA}45"),
        content=ft.Column(
            spacing=6,
            tight=True,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.ROCKET_LAUNCH_ROUNDED, color=T.RECEITA, size=15),
                                ft.Text(
                                    "Projeção de Caixa (Início fixo em Hoje)",
                                    size=11.5,
                                    weight=ft.FontWeight.BOLD,
                                    color=T.TEXT_PRIMARY,
                                ),
                            ],
                        ),
                        sw_fixar_hoje,
                    ],
                ),
                ft.Row(
                    spacing=6,
                    wrap=True,
                    controls=[
                        ft.Container(
                            padding=pad(h=8, v=4),
                            bgcolor=T.SURFACE,
                            border_radius=8,
                            border=borda(1, T.BORDER),
                            ink=True,
                            on_click=lambda _: _aplicar_atalho_projecao_dias(fim_mes_atual=True),
                            content=ft.Text("Hoje → Fim do Mês", size=10.5, weight=ft.FontWeight.W_600, color=T.RECEITA),
                        ),
                        ft.Container(
                            padding=pad(h=8, v=4),
                            bgcolor=T.SURFACE,
                            border_radius=8,
                            border=borda(1, T.BORDER),
                            ink=True,
                            on_click=lambda _: _aplicar_atalho_projecao_dias(dias_frente=15),
                            content=ft.Text("Hoje + 15 dias", size=10.5, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                        ),
                        ft.Container(
                            padding=pad(h=8, v=4),
                            bgcolor=T.SURFACE,
                            border_radius=8,
                            border=borda(1, T.BORDER),
                            ink=True,
                            on_click=lambda _: _aplicar_atalho_projecao_dias(dias_frente=30),
                            content=ft.Text("Hoje + 30 dias", size=10.5, weight=ft.FontWeight.W_600, color=T.TEXT_PRIMARY),
                        ),
                        ft.Container(
                            padding=pad(h=8, v=4),
                            bgcolor=T.SURFACE,
                            border_radius=8,
                            border=borda(1, T.BORDER),
                            ink=True,
                            on_click=lambda _: _aplicar_atalho_projecao_dias(fim_prox_mes=True),
                            content=ft.Text("Hoje → Fim Próx. Mês", size=10.5, weight=ft.FontWeight.W_600, color=T.PRIMARY),
                        ),
                    ],
                ),
            ],
        ),
    )

    def _salvar_intervalo_atual_nos_favoritos(_=None):
        d_i, d_f = temp_ini[0], temp_fim[0]
        if d_f < d_i:
            d_i, d_f = d_f, d_i
        ult_m = calendar.monthrange(d_f.year, d_f.month)[1]
        ate_fim = (d_i.month == d_f.month and d_f.day == ult_m)
        nome_sug = f"Dia {d_i.day:02d} a 30/31" if ate_fim else f"Dia {d_i.day:02d} a {d_f.day:02d}"
        storage.salvar_filtro_periodo_favorito_sync(
            page=page,
            nome=nome_sug,
            dia_ini=d_i.day,
            dia_fim=d_f.day,
            ate_fim_mes=ate_fim,
        )
        _reconstruir_chips_favoritos()
        mostrar_feedback(page, f"Filtro '{nome_sug}' salvo nos Mais Usados!", "sucesso")
        try:
            page.update()
        except Exception:
            pass

    conteudo_aba_custom = ft.Column(
        spacing=10,
        tight=True,
        controls=[
            barra_projecao_custom,
            lbl_instrucao_custom,
            ft.Container(
                padding=pad(h=12, v=8),
                bgcolor=f"{T.PRIMARY}15",
                border_radius=10,
                border=borda(1, f"{T.PRIMARY}35"),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(
                            spacing=6,
                            controls=[
                                ft.Icon(ft.Icons.DATE_RANGE_ROUNDED, color=T.PRIMARY, size=16),
                                lbl_resumo_range,
                            ],
                        ),
                    ],
                ),
            ),
            grid_range,
            ft.Row(
                spacing=8,
                controls=[
                    ft.OutlinedButton(
                        content=ft.Row(
                            spacing=4,
                            alignment=ft.MainAxisAlignment.CENTER,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.STAR_BORDER_ROUNDED, color=T.WARNING, size=16),
                                ft.Text("Salvar Filtro", color=T.TEXT_PRIMARY, size=12, weight=ft.FontWeight.W_600),
                            ],
                        ),
                        style=ft.ButtonStyle(
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        tooltip="Salvar este intervalo de dias nos Filtros Mais Usados",
                        on_click=_salvar_intervalo_atual_nos_favoritos,
                    ),
                    ft.FilledButton(
                        expand=True,
                        content=ft.Row(
                            spacing=6,
                            alignment=ft.MainAxisAlignment.CENTER,
                            controls=[
                                ft.Icon(ft.Icons.CHECK_ROUNDED, color=T.ON_PRIMARY, size=16),
                                ft.Text("Aplicar Intervalo", color=T.ON_PRIMARY, weight=ft.FontWeight.BOLD),
                            ],
                        ),
                        style=ft.ButtonStyle(
                            bgcolor=T.PRIMARY,
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        on_click=lambda _: _fechar_e_salvar(),
                    ),
                ],
            ),
        ],
    )

    # -------------------------------------------------------------------------
    # GESTÃO DAS ABAS SUPERIORES
    # -------------------------------------------------------------------------
    container_aba_conteudo = ft.Container(
        content=conteudo_aba_mensal if aba_ativa[0] == 0 else (
            conteudo_aba_ciclos if aba_ativa[0] == 1 else conteudo_aba_custom
        )
    )

    def _trocar_aba(novo_idx: int):
        aba_ativa[0] = novo_idx
        if novo_idx == 0:
            container_aba_conteudo.content = conteudo_aba_mensal
        elif novo_idx == 1:
            container_aba_conteudo.content = conteudo_aba_ciclos
        else:
            container_aba_conteudo.content = conteudo_aba_custom
        _atualizar_botoes_aba()
        try:
            page.update()
        except Exception:
            pass

    row_botoes_aba = ft.Row(spacing=4, expand=True)

    def _atualizar_botoes_aba():
        abas = [
            ("Mensal", ft.Icons.CALENDAR_MONTH_ROUNDED, 0),
            ("Ciclos / Atalhos", ft.Icons.TUNE_ROUNDED, 1),
            ("Personalizado", ft.Icons.EDIT_CALENDAR_ROUNDED, 2),
        ]
        row_botoes_aba.controls.clear()
        for titulo_a, icone_a, idx_a in abas:
            ativo = (aba_ativa[0] == idx_a)
            row_botoes_aba.controls.append(
                ft.Container(
                    content=ft.Row(
                        spacing=4,
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                        controls=[
                            ft.Icon(icone_a, size=14, color=T.PRIMARY if ativo else T.TEXT_MUTED),
                            ft.Text(
                                titulo_a,
                                size=11.5,
                                weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                                color=T.PRIMARY if ativo else T.TEXT_MUTED,
                            ),
                        ],
                    ),
                    padding=pad(h=8, v=7),
                    bgcolor=f"{T.PRIMARY}18" if ativo else "transparent",
                    border_radius=8,
                    border=borda(1, T.PRIMARY if ativo else "transparent"),
                    expand=True,
                    ink=True,
                    on_click=lambda _, i=idx_a: _trocar_aba(i),
                )
            )

    _atualizar_botoes_aba()

    def _fechar_e_salvar():
        d_i, d_f = temp_ini[0], temp_fim[0]
        if d_f < d_i:
            d_i, d_f = d_f, d_i

        ult_dia = calendar.monthrange(d_i.year, d_i.month)[1]
        if d_i.day == 1 and d_f == date(d_i.year, d_i.month, ult_dia) and temp_modo[0] != "ciclo":
            modo_final = "mes"
            ate_fim_final = True
        elif d_i.month == d_f.month and d_i.year == d_f.year and temp_modo[0] != "ciclo":
            modo_final = "faixa_mes"
            ate_fim_final = (d_f.day == ult_dia) or bool(temp_ate_fim_mes[0])
        else:
            modo_final = temp_modo[0]
            ate_fim_final = False

        res = {
            "modo": modo_final,
            "data_inicio": d_i,
            "data_fim": d_f,
            "dia_ciclo": temp_dia_ciclo[0],
            "mes": d_f.month,
            "ano": d_f.year,
            "ate_fim_mes": ate_fim_final,
            "filtro_id": temp_filtro_id[0],
        }
        page.pop_dialog()
        if callable(on_confirm):
            on_confirm(res)

    dlg_periodo = ft.AlertDialog(
        bgcolor=T.SURFACE,
        shape=ft.RoundedRectangleBorder(radius=18),
        title=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Row(
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.DATE_RANGE_ROUNDED, color=T.PRIMARY, size=20),
                        ft.Text("Filtrar Período", color=T.TEXT_PRIMARY, size=16, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.IconButton(
                    icon=ft.Icons.CLOSE_ROUNDED,
                    icon_color=T.TEXT_MUTED,
                    icon_size=18,
                    on_click=lambda _: page.pop_dialog(),
                ),
            ],
        ),
        content=ft.Container(
            width=400,
            content=ft.Column(
                tight=True,
                spacing=10,
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    bloco_filtros_salvos,
                    ft.Container(
                        padding=pad(all_=3),
                        bgcolor=T.SURFACE_ALT,
                        border_radius=10,
                        border=borda(),
                        content=row_botoes_aba,
                    ),
                    container_aba_conteudo,
                ],
            ),
        ),
    )
    page.show_dialog(dlg_periodo)


# =============================================================================
# COMPONENTE 4: CAMPO VISUAL DE SELEÇÃO DE DATA PARA FORMULÁRIOS
# =============================================================================
class CampoSeletorData(ft.Column):
    """
    Componente visual de data no estilo Mobills para formulários de transação:
    - Card clicável com ícone, data amigável e indicador de seta.
    - Atalhos rápidos em linha: Ontem, Hoje, Amanhã.
    - Clique no card abre o seletor modal Mobills completo.
    """

    def __init__(
        self,
        page: ft.Page,
        data_inicial: date | None = None,
        on_change: Callable[[date], None] | None = None,
        titulo: str = "Data do Lançamento",
    ):
        super().__init__(spacing=6, tight=True)
        self._page = page
        self._data: date = data_inicial or date.today()
        self._cb = on_change
        self.titulo = titulo

        self.txt_data_formatada = ft.Text(
            formatar_data_amigavel(self._data),
            size=13.5,
            weight=ft.FontWeight.BOLD,
            color=T.TEXT_PRIMARY,
        )

        self.card_data = ft.Container(
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        spacing=10,
                        tight=True,
                        controls=[
                            ft.Container(
                                content=ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, color=T.PRIMARY, size=18),
                                padding=pad(all_=6),
                                bgcolor=f"{T.PRIMARY}18",
                                border_radius=8,
                            ),
                            ft.Column(
                                spacing=1,
                                tight=True,
                                controls=[
                                    ft.Text(self.titulo, size=10.5, color=T.TEXT_MUTED, weight=ft.FontWeight.W_500),
                                    self.txt_data_formatada,
                                ],
                            ),
                        ],
                    ),
                    ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED, color=T.TEXT_MUTED, size=18),
                ],
            ),
            padding=pad(h=12, v=8),
            bgcolor=T.SURFACE,
            border_radius=12,
            border=borda(1, T.BORDER),
            ink=True,
            on_click=self._abrir_modal,
        )

        self.row_atalhos = ft.Row(spacing=6, wrap=True)
        self._reconstruir_atalhos()

        self.controls = [
            self.card_data,
            self.row_atalhos,
        ]

    def _reconstruir_atalhos(self):
        hoje = date.today()
        opcoes = [
            ("Ontem", hoje - timedelta(days=1)),
            ("Hoje", hoje),
            ("Amanhã", hoje + timedelta(days=1)),
        ]
        self.row_atalhos.controls.clear()
        for lbl, dt_val in opcoes:
            ativo = (self._data == dt_val)
            self.row_atalhos.controls.append(
                ft.Container(
                    content=ft.Text(
                        lbl,
                        size=11,
                        weight=ft.FontWeight.BOLD if ativo else ft.FontWeight.W_500,
                        color=T.ON_PRIMARY if ativo else T.TEXT_PRIMARY,
                    ),
                    padding=pad(h=10, v=4),
                    bgcolor=T.PRIMARY if ativo else T.SURFACE_ALT,
                    border_radius=12,
                    border=borda(1, T.PRIMARY if ativo else T.BORDER),
                    ink=True,
                    on_click=lambda _, dt=dt_val: self.definir_data(dt, emitir=True),
                )
            )

    def _abrir_modal(self, _=None):
        abrir_seletor_data_modal(
            page=self._page,
            data_inicial=self._data,
            on_select=lambda d: self.definir_data(d, emitir=True),
            titulo=self.titulo,
        )

    def definir_data(self, nova_data: date, emitir: bool = False):
        self._data = nova_data
        self.txt_data_formatada.value = formatar_data_amigavel(self._data)
        self._reconstruir_atalhos()
        try:
            if self.page:
                self.update()
        except Exception:
            pass
        if emitir and callable(self._cb):
            self._cb(self._data)

    @property
    def data(self) -> date:
        return self._data
