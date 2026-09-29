"""
=============================================================================
DemBase v3 — views/widgets/date_filter.py  (Flet 1.0 compatible)
Barra de filtros flexíveis de data — o diferencial do DemBase.
=============================================================================
"""
import flet as ft
from datetime import date, timedelta
from core import theme as T
from core.theme import pad, borda
from core.constants import formatar_data_br, inicio_mes_atual, hoje


class DateFilterBar(ft.Column):
    OPCOES = ["Mês Atual", "7 dias", "30 dias", "Personalizado"]

    def __init__(self, on_change=None):
        super().__init__(spacing=10)
        self._cb = on_change
        self._sel = 0
        self._inicio = inicio_mes_atual()
        self._fim = hoje()
        self._rebuild()

    def _chip(self, i: int) -> ft.Container:
        ativo = i == self._sel
        return ft.Container(
            content=ft.Text(
                self.OPCOES[i],
                size=12,
                weight=ft.FontWeight.W_600 if ativo else ft.FontWeight.W_400,
                color=T.PRIMARY if ativo else T.TEXT_MUTED,
            ),
            padding=pad(h=14, v=8),
            bgcolor=f"{T.PRIMARY}1A" if ativo else T.SURFACE_ALT,
            border_radius=20,
            border=borda(1, T.PRIMARY) if ativo else borda(1, T.BORDER),
            on_click=lambda _, idx=i: self._selecionar(idx),
        )

    def _selecionar(self, idx: int):
        if idx == 3:
            self._abrir_picker()
            return
        self._sel = idx
        hoje_d = hoje()
        if idx == 0:
            self._inicio = inicio_mes_atual(); self._fim = hoje_d
        elif idx == 1:
            self._inicio = hoje_d - timedelta(days=7); self._fim = hoje_d
        elif idx == 2:
            self._inicio = hoje_d - timedelta(days=30); self._fim = hoje_d
        self._rebuild()
        self._emitir()

    def _abrir_picker(self):
        page = self.page
        if not page: return

        def on_change(e):
            if e.control.value:
                r = e.control.value
                self._inicio = r.start.date() if hasattr(r.start, "date") else r.start
                self._fim    = r.end.date()   if hasattr(r.end,   "date") else r.end
                self._sel = 3
                self._rebuild()
                self._emitir()

        picker = ft.DateRangePicker(
            first_date=date(2020, 1, 1),
            last_date=date(2030, 12, 31),
            on_change=on_change,
        )
        page.overlay.append(picker)
        picker.open = True
        page.update()

    def _rebuild(self):
        label = ft.Text(
            f"📅  {formatar_data_br(self._inicio)}  →  {formatar_data_br(self._fim)}",
            color=T.TEXT_MUTED, size=12, italic=True,
        )
        badge = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.AUTO_AWESOME, color=T.PRIMARY, size=12),
                    ft.Text("Filtros Flexíveis", color=T.PRIMARY, size=11, weight=ft.FontWeight.W_600),
                ],
                spacing=4, tight=True,
            ),
            bgcolor=f"{T.PRIMARY}1A",
            border_radius=20,
            padding=pad(h=10, v=5),
            border=borda(1, f"{T.PRIMARY}40"),
        )
        chips_row = ft.Row(
            controls=[self._chip(i) for i in range(len(self.OPCOES))],
            spacing=8,
            wrap=True,
        )
        self.controls = [
            ft.Row(
                controls=[chips_row, badge],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                wrap=True,
            ),
            label,
        ]
        
        # Flet 1.0 lança RuntimeError se acessar self.page antes de ser anexado
        try:
            if self.page:
                self.update()
        except RuntimeError:
            pass

    def _emitir(self):
        if self._cb:
            self._cb(str(self._inicio), str(self._fim))

    @property
    def data_inicio(self): return str(self._inicio)

    @property
    def data_fim(self): return str(self._fim)
