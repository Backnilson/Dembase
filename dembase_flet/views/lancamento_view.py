"""
=============================================================================
DemBase v3 — views/lancamento_view.py  (Flet 1.0.1 compatible)
Cadastro de lançamentos financeiros com reatividade estrita, cálculo dinâmico
de parcelas no crédito, eliminação de destinos e criação inline de categorias/subcategorias.
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
    contas = db.listar_contas()
    categorias_lista = db.listar_categorias()

    def _opts(lst):
        return [ft.dropdown.Option(key=str(i["id"]), text=i["nome"]) for i in lst]

    def _campo(label, hint="", keyboard=ft.KeyboardType.TEXT, prefix=None, valor="", on_change=None):
        kw = T.campo_estilo()
        if prefix:
            kw["prefix"] = prefix
        return ft.TextField(
            label=label,
            hint_text=hint,
            keyboard_type=keyboard,
            value=valor,
            on_change=on_change,
            **kw
        )

    # ---- Dropdowns Principais ----
    dd_tipo = ft.Dropdown(
        label="Tipo *",
        value="Despesa",
        options=[ft.dropdown.Option(t) for t in TIPOS_LANCAMENTO],
        **T.dropdown_estilo(),
    )
    dd_subtipo = ft.Dropdown(
        label="Subtipo *",
        value="Despesa",
        options=[ft.dropdown.Option(s) for s in SUBTIPOS_DESPESA],
        **T.dropdown_estilo(),
    )
    dd_forma = ft.Dropdown(
        label="Forma de Movimentação *",
        value="Pix",
        options=[ft.dropdown.Option(f) for f in FORMAS_DESPESA],
        **T.dropdown_estilo(),
    )
    dd_conta = ft.Dropdown(
        label="Conta *",
        options=_opts(contas),
        value=str(contas[0]["id"]) if contas else None,
        **T.dropdown_estilo(),
    )
    dd_categoria = ft.Dropdown(
        label="Categoria *",
        options=_opts(categorias_lista),
        **T.dropdown_estilo(),
    )
    dd_subcategoria = ft.Dropdown(
        label="Subcategoria",
        hint_text="Selecione a categoria primeiro",
        disabled=True,
        options=[],
        **T.dropdown_estilo(),
    )
    dd_status = ft.Dropdown(
        label="Status *",
        value="Pago",
        options=[ft.dropdown.Option(s) for s in STATUS_OPCOES],
        **T.dropdown_estilo(),
    )
    dd_regra = ft.Dropdown(
        label="Regra 50/30/20 *",
        options=[ft.dropdown.Option(r) for r in REGRAS_5030],
        **T.dropdown_estilo(),
    )

    # ---- Campos Básicos ----
    txt_valor = _campo("Valor Total (R$)", "0,00", ft.KeyboardType.NUMBER, "R$ ")
    txt_desc = _campo("Descrição", "Ex: Aluguel de março, Notebook Dell...")
    txt_data = _campo("Data", "AAAA-MM-DD", valor=datetime.now().strftime("%Y-%m-%d"))
    txt_hora = _campo("Hora", "Ex: 14", ft.KeyboardType.NUMBER, valor=str(datetime.now().hour))

    row_regra = ft.Container(content=dd_regra, visible=True)

    # ---- Lógica de Crédito e Parcelamento Inteligente ----
    sw_parcelado = ft.Switch(
        label="Compra Parcelada no Cartão?",
        value=False,
        active_color=T.PRIMARY,
    )
    txt_num_parcelas = _campo("Quantidade de Parcelas", "Ex: 10", ft.KeyboardType.NUMBER, valor="2")
    txt_valor_parcela = _campo("Valor de Cada Parcela", "0,00", ft.KeyboardType.NUMBER, "R$ ")
    txt_fatura = _campo("Fatura / Mês Referência", "Ex: Março/2026")
    lbl_resumo_parcelamento = ft.Text(
        "Informe os dados do parcelamento",
        color=T.TEXT_MUTED,
        size=12,
        weight=ft.FontWeight.W_500,
    )

    def _recalcular_parcelas_por_parcela(_=None):
        try:
            val_parc = float(txt_valor_parcela.value.replace(",", ".").strip() or 0)
            n_parc = int(txt_num_parcelas.value.strip() or 1)
            if n_parc <= 0:
                n_parc = 1
            total = val_parc * n_parc
            if total > 0:
                txt_valor.value = f"{total:.2f}".replace(".", ",")
                lbl_resumo_parcelamento.value = (
                    f"✓ Total: R$ {total:,.2f} em {n_parc}x de R$ {val_parc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                lbl_resumo_parcelamento.color = T.RECEITA
            else:
                lbl_resumo_parcelamento.value = "Informe a quantidade e o valor da parcela"
                lbl_resumo_parcelamento.color = T.TEXT_MUTED
        except Exception:
            pass
        page.update()

    def _recalcular_parcelas_por_total(_=None):
        if not sw_parcelado.value or dd_forma.value != "Crédito":
            return
        try:
            total = float(txt_valor.value.replace(",", ".").strip() or 0)
            n_parc = int(txt_num_parcelas.value.strip() or 1)
            if n_parc <= 0:
                n_parc = 1
            if total > 0:
                parc = total / n_parc
                txt_valor_parcela.value = f"{parc:.2f}".replace(".", ",")
                lbl_resumo_parcelamento.value = (
                    f"✓ Total: R$ {total:,.2f} dividido em {n_parc}x de R$ {parc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                )
                lbl_resumo_parcelamento.color = T.RECEITA
        except Exception:
            pass
        page.update()

    txt_valor_parcela.on_change = _recalcular_parcelas_por_parcela
    txt_num_parcelas.on_change = _recalcular_parcelas_por_parcela
    txt_valor.on_change = _recalcular_parcelas_por_total

    campos_parcelamento = ft.Column(
        visible=False,
        spacing=10,
        controls=[
            ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                ft.Container(content=txt_num_parcelas,  col={"xs": 12, "sm": 6}),
                ft.Container(content=txt_valor_parcela, col={"xs": 12, "sm": 6}),
            ]),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CALCULATE_OUTLINED, size=18, color=T.PRIMARY),
                    lbl_resumo_parcelamento,
                ], spacing=8),
                padding=pad(h=12, v=8),
                bgcolor=T.SURFACE_ALT,
                border_radius=8,
                border=borda(),
            ),
            txt_fatura,
        ],
    )

    card_credito = ft.Container(
        visible=False,
        padding=pad(all_=16),
        bgcolor=T.SURFACE_ALT,
        border_radius=12,
        border=borda(),
        content=ft.Column(spacing=12, controls=[
            ft.Row([
                ft.Icon(ft.Icons.CREDIT_CARD_ROUNDED, color=T.PRIMARY, size=20),
                ft.Text("Opções de Cartão de Crédito", color=T.TEXT_PRIMARY, size=14, weight=ft.FontWeight.W_600),
            ], spacing=8),
            sw_parcelado,
            campos_parcelamento,
        ]),
    )

    def on_sw_parcelado_change(_):
        campos_parcelamento.visible = sw_parcelado.value
        if sw_parcelado.value:
            _recalcular_parcelas_por_total()
        page.update()

    sw_parcelado.on_change = on_sw_parcelado_change

    # ---- Reatividade Estrita: Tipo e Forma ----
    def on_tipo_change(_):
        is_despesa = (dd_tipo.value == "Despesa")
        # Subtipo reativo
        opcoes_subtipo = SUBTIPOS_DESPESA if is_despesa else SUBTIPOS_RECEITA
        dd_subtipo.options = [ft.dropdown.Option(s) for s in opcoes_subtipo]
        dd_subtipo.value = opcoes_subtipo[0]

        # Forma de movimentação reativa (Receita não tem Crédito)
        opcoes_forma = FORMAS_DESPESA if is_despesa else FORMAS_RECEITA
        dd_forma.options = [ft.dropdown.Option(f) for f in opcoes_forma]
        dd_forma.value = opcoes_forma[0]

        row_regra.visible = is_despesa
        on_forma_change(None)
        page.update()

    def on_forma_change(_):
        is_credito = (dd_forma.value == "Crédito" and dd_tipo.value == "Despesa")
        card_credito.visible = is_credito
        if not is_credito:
            sw_parcelado.value = False
            campos_parcelamento.visible = False
            txt_num_parcelas.value = "2"
            txt_valor_parcela.value = ""
            txt_fatura.value = ""
        page.update()

    dd_tipo.on_change = on_tipo_change
    dd_forma.on_change = on_forma_change

    # ---- Subcategoria Reativa à Categoria ----
    def carregar_subcategorias(cat_id: str, selecionar_id: str = None):
        if not cat_id:
            dd_subcategoria.options = []
            dd_subcategoria.value = None
            dd_subcategoria.disabled = True
            dd_subcategoria.hint_text = "Selecione a categoria primeiro"
            page.update()
            return

        try:
            subs = db.listar_subcategorias(categoria_id=cat_id)
            dd_subcategoria.options = [ft.dropdown.Option(key=str(s["id"]), text=s["nome"]) for s in subs]
            dd_subcategoria.disabled = False
            if subs:
                dd_subcategoria.hint_text = "Selecione a subcategoria (opcional)"
                if selecionar_id and any(str(s["id"]) == str(selecionar_id) for s in subs):
                    dd_subcategoria.value = str(selecionar_id)
                else:
                    dd_subcategoria.value = None
            else:
                dd_subcategoria.hint_text = "Nenhuma subcategoria (clique no + para criar)"
                dd_subcategoria.value = None
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao listar subcategorias: {ex}", "erro")
        page.update()

    def on_categoria_change(_):
        carregar_subcategorias(dd_categoria.value)

    dd_categoria.on_change = on_categoria_change

    # ---- Criação Inline de Categoria e Subcategoria (+) ----
    def abrir_modal_nova_categoria(_):
        txt_nome_cat = ft.TextField(
            label="Nome da Categoria *",
            hint_text="Ex: Alimentação, DJ, Investimento",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar_nova_cat(_):
            nome = txt_nome_cat.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da categoria.", "alerta")
                return
            try:
                nova = db.criar_categoria({"nome": nome, "tipo": "ambos", "cor": T.PRIMARY, "icone": "category"})
                modal_cat.open = False
                page.update()

                # Atualiza dropdown de categorias
                novas_cats = db.listar_categorias()
                dd_categoria.options = _opts(novas_cats)

                # Seleciona a categoria criada
                if nova and nova.data:
                    novo_id = str(nova.data[0]["id"])
                    dd_categoria.value = novo_id
                    carregar_subcategorias(novo_id)

                mostrar_feedback(page, f"Categoria '{nome}' criada com sucesso!", "sucesso")
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao criar categoria: {ex}", "erro")

        modal_cat = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.CATEGORY_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Nova Categoria Universal", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Text("Categorias universais podem ser usadas para Receitas e Despesas.", color=T.TEXT_MUTED, size=12),
                txt_nome_cat,
            ]),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: (setattr(modal_cat, "open", False), page.update()),
                ),
                ft.FilledButton(
                    content=ft.Text("Criar Categoria"),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar_nova_cat,
                ),
            ],
        )
        page.overlay.append(modal_cat)
        modal_cat.open = True
        page.update()

    def abrir_modal_nova_subcategoria(_):
        if not dd_categoria.value:
            mostrar_feedback(page, "Selecione uma Categoria primeiro para vincular a Subcategoria.", "alerta")
            return

        cat_nome = next((opt.text for opt in dd_categoria.options if opt.key == dd_categoria.value), "Categoria Selecionada")

        txt_nome_sub = ft.TextField(
            label="Nome da Subcategoria *",
            hint_text="Ex: Notebook, Gasolina, Cursos...",
            autofocus=True,
            **T.campo_estilo(),
        )

        def salvar_nova_sub(_):
            nome = txt_nome_sub.value.strip()
            if not nome:
                mostrar_feedback(page, "Informe o nome da subcategoria.", "alerta")
                return
            try:
                nova_sub = db.criar_subcategoria(categoria_id=dd_categoria.value, nome=nome)
                modal_sub.open = False
                page.update()

                novo_sub_id = nova_sub.data[0]["id"] if nova_sub and nova_sub.data else None
                carregar_subcategorias(dd_categoria.value, selecionar_id=novo_sub_id)
                mostrar_feedback(page, f"Subcategoria '{nome}' vinculada a '{cat_nome}' criada!", "sucesso")
            except Exception as ex:
                mostrar_feedback(page, f"Erro ao criar subcategoria: {ex}", "erro")

        modal_sub = ft.AlertDialog(
            title=ft.Row([
                ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT_ROUNDED, color=T.PRIMARY, size=22),
                ft.Text("Nova Subcategoria", size=18, weight=ft.FontWeight.BOLD),
            ], spacing=8),
            content=ft.Column(spacing=12, tight=True, controls=[
                ft.Container(
                    content=ft.Row([
                        ft.Text("Categoria Pai:", color=T.TEXT_MUTED, size=12),
                        ft.Text(cat_nome, color=T.PRIMARY, size=13, weight=ft.FontWeight.BOLD),
                    ], spacing=6),
                    padding=pad(h=12, v=8),
                    bgcolor=T.SURFACE_ALT,
                    border_radius=8,
                    border=borda(),
                ),
                txt_nome_sub,
            ]),
            actions=[
                ft.TextButton(
                    content=ft.Text("Cancelar", color=T.TEXT_MUTED),
                    on_click=lambda _: (setattr(modal_sub, "open", False), page.update()),
                ),
                ft.FilledButton(
                    content=ft.Text("Criar Subcategoria"),
                    style=ft.ButtonStyle(bgcolor=T.PRIMARY),
                    on_click=salvar_nova_sub,
                ),
            ],
        )
        page.overlay.append(modal_sub)
        modal_sub.open = True
        page.update()

    btn_add_cat = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
        icon_color=T.PRIMARY,
        icon_size=24,
        tooltip="Criar nova Categoria",
        on_click=abrir_modal_nova_categoria,
    )
    btn_add_subcat = ft.IconButton(
        icon=ft.Icons.ADD_CIRCLE_OUTLINE_ROUNDED,
        icon_color=T.PRIMARY,
        icon_size=24,
        tooltip="Criar nova Subcategoria vinculada",
        on_click=abrir_modal_nova_subcategoria,
    )

    campo_categoria_inline = ft.Row(
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(content=dd_categoria, expand=True),
            btn_add_cat,
        ],
    )

    campo_subcategoria_inline = ft.Row(
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        controls=[
            ft.Container(content=dd_subcategoria, expand=True),
            btn_add_subcat,
        ],
    )

    # ---- Salvar Lançamento ----
    spinner_s = ft.ProgressRing(color=ft.Colors.WHITE, width=18, height=18, stroke_width=2, visible=False)
    txt_btn_s = ft.Text("Salvar Lançamento", color=ft.Colors.WHITE, size=14, weight=ft.FontWeight.W_600)

    def on_salvar(_):
        erros = []
        try:
            v = float(txt_valor.value.replace(",", ".").strip() or 0)
        except ValueError:
            v = 0
        if v <= 0:
            erros.append("Informe um valor válido maior que zero.")
        if not txt_data.value:
            erros.append("Informe a data.")
        if not dd_categoria.value:
            erros.append("Selecione uma Categoria.")
        if dd_tipo.value == "Despesa" and not dd_regra.value:
            erros.append("Selecione a Regra 50/30/20.")

        if erros:
            mostrar_feedback(page, " | ".join(erros), "alerta")
            return

        spinner_s.visible = True
        page.update()
        try:
            dados = {
                "tipo": dd_tipo.value,
                "subtipo": dd_subtipo.value,
                "forma_movimentacao": dd_forma.value,
                "conta_id": dd_conta.value or None,
                "categoria_id": dd_categoria.value or None,
                "subcategoria_id": dd_subcategoria.value or None,
                "valor": v,
                "data": txt_data.value,
                "hora": int(txt_hora.value or 0),
                "descricao": txt_desc.value.strip() if txt_desc.value else "Lançamento",
                "status": dd_status.value,
                "regra": dd_regra.value if dd_tipo.value == "Despesa" else None,
            }

            if dd_forma.value == "Crédito" and dd_tipo.value == "Despesa":
                if sw_parcelado.value:
                    dados["parcela_atual"] = 1
                    dados["total_parcelas"] = int(txt_num_parcelas.value or 1)
                else:
                    dados["parcela_atual"] = 1
                    dados["total_parcelas"] = 1
                dados["fatura"] = txt_fatura.value.strip() or None

            db.criar_lancamento(dados)
            mostrar_feedback(page, "Lançamento salvo com sucesso!", "sucesso")
            navegar(page, ROTA_DASHBOARD)
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")
        finally:
            spinner_s.visible = False
            page.update()

    btn_salvar = ft.FilledButton(
        content=ft.Row([spinner_s, txt_btn_s], alignment=ft.MainAxisAlignment.CENTER, spacing=10, tight=True),
        on_click=on_salvar,
        expand=True,
        style=ft.ButtonStyle(
            bgcolor=T.PRIMARY,
            overlay_color=T.PRIMARY_DARK,
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=pad(h=24, v=16),
        ),
    )
    btn_cancelar = T.botao_outline(
        "Cancelar",
        on_click=lambda _: navegar(page, ROTA_DASHBOARD),
        icone=ft.Icons.ARROW_BACK_ROUNDED,
    )

    # ---- Layout Completo ----
    corpo = ft.Column(
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=0,
        controls=[
            # Cabeçalho
            ft.Row(spacing=8, controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_ROUNDED,
                    icon_color=T.TEXT_MUTED,
                    on_click=lambda _: navegar(page, ROTA_DASHBOARD),
                ),
                ft.Column(spacing=2, controls=[
                    ft.Text("Novo Lançamento", color=T.TEXT_PRIMARY, size=22, weight=ft.FontWeight.BOLD),
                    ft.Text("Preencha os dados do lançamento financeiro", color=T.TEXT_MUTED, size=12),
                ]),
            ]),
            ft.Container(height=16),

            # Card Principal
            ft.Container(
                padding=pad(all_=24),
                bgcolor=T.SURFACE,
                border_radius=16,
                border=borda(),
                content=ft.Column(spacing=14, controls=[
                    # 1. Classificação Principal
                    ft.Text("Classificação Principal", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                        ft.Container(content=dd_tipo,    col={"xs": 12, "sm": 4}),
                        ft.Container(content=dd_subtipo, col={"xs": 12, "sm": 4}),
                        ft.Container(content=dd_forma,   col={"xs": 12, "sm": 4}),
                    ]),

                    card_credito,
                    ft.Divider(color=T.BORDER, height=20),

                    # 2. Valores e Data
                    ft.Text("Valores e Informações de Data", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                        ft.Container(content=txt_valor, col={"xs": 12, "sm": 5}),
                        ft.Container(content=txt_data,  col={"xs": 12, "sm": 4}),
                        ft.Container(content=txt_hora,  col={"xs": 12, "sm": 3}),
                    ]),
                    ft.Divider(color=T.BORDER, height=20),

                    # 3. Categorização e Conta (Sem Destino)
                    ft.Text("Classificação por Conta e Categoria", color=T.TEXT_MUTED, size=12, weight=ft.FontWeight.W_600),
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                        ft.Container(content=dd_conta,                  col={"xs": 12, "sm": 4}),
                        ft.Container(content=campo_categoria_inline,    col={"xs": 12, "sm": 4}),
                        ft.Container(content=campo_subcategoria_inline, col={"xs": 12, "sm": 4}),
                    ]),
                    txt_desc,
                    ft.ResponsiveRow(spacing=10, run_spacing=10, controls=[
                        ft.Container(content=dd_status, col={"xs": 12, "sm": 6}),
                        ft.Container(content=row_regra,  col={"xs": 12, "sm": 6}),
                    ]),
                    ft.Divider(color=T.BORDER, height=24),

                    # Botões de Ação
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
