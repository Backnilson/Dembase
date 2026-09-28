"""
=============================================================================
DemBase v3 — views/lancamento_view.py  (Flet 1.0 compatible)
=============================================================================
"""
import flet as ft
from datetime import datetime
from core import theme as T
from core.theme import pad, borda, mostrar_feedback
from core.constants import (
    TIPOS_LANCAMENTO, SUBTIPOS_RECEITA, SUBTIPOS_DESPESA,
    FORMAS_RECEITA, FORMAS_DESPESA, STATUS_OPCOES, REGRAS_5030,
)
from core.router import ROTA_DASHBOARD, navegar
import services.supabase_client as db


def criar_view_lancamento(page: ft.Page) -> ft.View:
    contas     = db.listar_contas()
    categorias = db.listar_categorias()
    destinos   = db.listar_destinos()

    def _opts(lst): return [ft.dropdown.Option(key=str(i["id"]), text=i["nome"]) for i in lst]

    def _campo(label, hint="", keyboard=ft.KeyboardType.TEXT, prefix=None, valor=""):
        kw = T.campo_estilo()
        if prefix: kw["prefix"] = prefix
        return ft.TextField(label=label, hint_text=hint, keyboard_type=keyboard, value=valor, **kw)

    def _dd(label, opts):
        return ft.Dropdown(label=label, options=opts, **T.dropdown_estilo())

    # ---- Dropdowns ----
    dd_tipo     = ft.Dropdown(label="Tipo", value="Despesa",
                              options=[ft.dropdown.Option(t) for t in TIPOS_LANCAMENTO], **T.dropdown_estilo())
    dd_subtipo  = ft.Dropdown(label="Subtipo", value="Despesa",
                              options=[ft.dropdown.Option(s) for s in SUBTIPOS_DESPESA], **T.dropdown_estilo())
    dd_forma    = ft.Dropdown(label="Forma de Movimentação", value="Pix",
                              options=[ft.dropdown.Option(f) for f in FORMAS_DESPESA], **T.dropdown_estilo())
    dd_conta    = _dd("Conta", _opts(contas))
    dd_categoria= _dd("Categoria", _opts(categorias))
    dd_destino  = _dd("Destino", _opts(destinos))
    dd_status   = ft.Dropdown(label="Status", value="Pago",
                              options=[ft.dropdown.Option(s) for s in STATUS_OPCOES], **T.dropdown_estilo())
    dd_regra    = ft.Dropdown(label="Regra 50/30/20 *",
                              options=[ft.dropdown.Option(r) for r in REGRAS_5030], **T.dropdown_estilo())

    # ---- Campos ----
    txt_valor   = _campo("Valor (R$)", "0,00", ft.KeyboardType.NUMBER, "R$ ")
    txt_desc    = _campo("Descrição", "Ex: Aluguel de março")
    txt_data    = _campo("Data", "AAAA-MM-DD", valor=datetime.now().strftime("%Y-%m-%d"))
    txt_hora    = _campo("Hora", "Ex: 14", ft.KeyboardType.NUMBER, valor=str(datetime.now().hour))
    txt_fatura  = _campo("Fatura / Referência", "Ex: Março/2026")
    txt_parcela = _campo("Parcela Atual", "Ex: 1", ft.KeyboardType.NUMBER)
    txt_total_p = _campo("Total Parcelas", "Ex: 12", ft.KeyboardType.NUMBER)

    row_parcelas = ft.ResponsiveRow(visible=False, spacing=10, run_spacing=10, controls=[
        ft.Container(content=txt_parcela, col={"xs": 12, "sm": 6}),
        ft.Container(content=txt_total_p, col={"xs": 12, "sm": 6}),
        ft.Container(content=txt_fatura,  col={"xs": 12}),
    ])
    row_regra = ft.Container(content=dd_regra, visible=True)

    def on_tipo(_):
        desp = dd_tipo.value == "Despesa"
        dd_subtipo.options = [ft.dropdown.Option(s) for s in (SUBTIPOS_DESPESA if desp else SUBTIPOS_RECEITA)]
        dd_subtipo.value = dd_subtipo.options[0].key
        dd_forma.options  = [ft.dropdown.Option(f) for f in (FORMAS_DESPESA if desp else FORMAS_RECEITA)]
        dd_forma.value = "Pix"
        row_regra.visible = desp
        row_parcelas.visible = False
        page.update()

    def on_forma(_):
        cred = dd_forma.value == "Crédito"
        row_parcelas.visible = cred
        if not cred:
            txt_parcela.value = txt_total_p.value = txt_fatura.value = ""
        page.update()

    dd_tipo.on_change  = on_tipo
    dd_forma.on_change = on_forma

    # ---- Salvar ----
    spinner_s = ft.ProgressRing(color=ft.Colors.WHITE, width=18, height=18, stroke_width=2, visible=False)
    txt_btn_s = ft.Text("Salvar Lançamento", color=ft.Colors.WHITE, size=14, weight=ft.FontWeight.W_600)

    def on_salvar(_):
        erros = []
        try:
            v = float(txt_valor.value.replace(",", ".") or 0)
        except ValueError:
            v = 0
        if v <= 0: erros.append("Valor inválido.")
        if not txt_data.value: erros.append("Informe a data.")
        if dd_tipo.value == "Despesa" and not dd_regra.value: erros.append("Selecione a Regra 50/30/20.")
        if erros:
            mostrar_feedback(page, " | ".join(erros), "alerta"); return

        spinner_s.visible = True; page.update()
        try:
            dados = {
                "tipo": dd_tipo.value, "subtipo": dd_subtipo.value,
                "forma_movimentacao": dd_forma.value,
                "conta_id": dd_conta.value or None,
                "categoria_id": dd_categoria.value or None,
                "destino_id": dd_destino.value or None,
                "valor": v, "data": txt_data.value,
                "hora": int(txt_hora.value or 0),
                "descricao": txt_desc.value,
                "status": dd_status.value,
                "regra": dd_regra.value if dd_tipo.value == "Despesa" else None,
            }
            if dd_forma.value == "Crédito":
                dados["parcela_atual"]  = int(txt_parcela.value or 1)
                dados["total_parcelas"] = int(txt_total_p.value or 1)
                dados["fatura"]         = txt_fatura.value or None
            db.criar_lancamento(dados)
            mostrar_feedback(page, "Lançamento salvo!", "sucesso")
            navegar(page, ROTA_DASHBOARD)
        except Exception as ex:
            mostrar_feedback(page, f"Erro: {ex}", "erro")
        finally:
            spinner_s.visible = False; page.update()

    btn_salvar = ft.FilledButton(
        content=ft.Row([spinner_s, txt_btn_s], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True),
        on_click=on_salvar, expand=True,
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY, overlay_color=T.PRIMARY_DARK,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=24, v=16),
        ),
    )
    btn_cancelar = T.botao_outline("Cancelar",
                                   on_click=lambda _: navegar(page, ROTA_DASHBOARD),
                                   icone=ft.Icons.ARROW_BACK_ROUNDED)

    # ---- Layout ----
    corpo = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=0,
        controls=[
            # Cabeçalho
            ft.Row(spacing=8, controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                              icon_color=T.TEXT_MUTED,
                              on_click=lambda _: navegar(page, ROTA_DASHBOARD)),
                ft.Column(spacing=2, controls=[
                    ft.Text("Novo Lançamento", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                    ft.Text("Preencha os dados abaixo", color=T.TEXT_MUTED, size=12),
                ]),
            ]),
            ft.Container(height=16),

            # Card do formulário
            ft.Container(
                padding=pad(all_=24),
                bgcolor=T.SURFACE, border_radius=16, border=borda(),
                content=ft.Column(spacing=12, controls=[
                    ft.Text("Classificação", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                        ft.Container(content=dd_tipo,    col={"xs": 12, "sm": 6}),
                        ft.Container(content=dd_subtipo, col={"xs": 12, "sm": 6}),
                        ft.Container(content=dd_forma,   col={"xs": 12, "sm": 6}),
                        ft.Container(content=dd_status,  col={"xs": 12, "sm": 6}),
                    ]),
                    row_parcelas,
                    ft.Divider(color=T.BORDER, height=24),

                    ft.Text("Valores e Data", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                        ft.Container(content=txt_valor, col={"xs": 12, "sm": 6}),
                        ft.Container(content=txt_data,  col={"xs": 12, "sm": 4}),
                        ft.Container(content=txt_hora,  col={"xs": 12, "sm": 2}),
                    ]),
                    ft.Divider(color=T.BORDER, height=24),

                    ft.Text("Classificação Financeira", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                        ft.Container(content=dd_conta,     col={"xs": 12, "sm": 4}),
                        ft.Container(content=dd_categoria, col={"xs": 12, "sm": 4}),
                        ft.Container(content=dd_destino,   col={"xs": 12, "sm": 4}),
                    ]),
                    txt_desc,
                    ft.Divider(color=T.BORDER, height=24),
                    row_regra,
                    ft.Container(height=8),

                    ft.ResponsiveRow(spacing=10, controls=[
                        ft.Container(content=btn_cancelar, col={"xs": 12, "sm": 4}),
                        ft.Container(content=btn_salvar,   col={"xs": 12, "sm": 8}),
                    ]),
                ]),
            ),
            ft.Container(height=24),
        ],
    )

    return ft.View(
        route="/lancamento",
        bgcolor=T.BG,
        padding=pad(all_=20),
        controls=[corpo],
    )
