import flet as ft
from datetime import datetime
from backend import (
    criar_lancamento,
    listar_contas,
    listar_categorias,
    listar_destinos,
)
from ui_utils import (
    COLOR_BG, COLOR_SURFACE, COLOR_SURFACE_ALT, COLOR_BORDER,
    COLOR_PRIMARY, COLOR_PRIMARY_LIGHT, COLOR_TEXT_PRIMARY,
    COLOR_TEXT_MUTED, mostrar_feedback
)

def criar_view_lancamentos(page: ft.Page) -> ft.View:
    """
    Cria a View do formulário de Cadastro de Lançamentos.
    Possui lógica dinâmica para exibir campos de parcela quando for Crédito.
    """
    # --- Estilização padrão para campos ---
    estilo_campo = {
        "border_color": COLOR_BORDER,
        "focused_border_color": COLOR_PRIMARY,
        "border_radius": 10,
        "filled": True,
        "fill_color": COLOR_SURFACE_ALT,
        "cursor_color": COLOR_PRIMARY,
        "text_size": 13,
        "label_style": ft.TextStyle(color=COLOR_TEXT_MUTED, size=13),
        "content_padding": ft.padding.symmetric(horizontal=12, vertical=10),
    }

    # --- Elementos do Formulário ---
    # 1. Tipo
    dd_tipo = ft.Dropdown(
        label="Tipo",
        options=[
            ft.dropdown.Option("Receita"),
            ft.dropdown.Option("Despesa"),
        ],
        value="Despesa",
        **estilo_campo
    )

    # 2. Subtipo
    dd_subtipo = ft.Dropdown(
        label="Subtipo",
        options=[
            ft.dropdown.Option("Receita"),
            ft.dropdown.Option("Entrada"),
            ft.dropdown.Option("Despesa"),
            ft.dropdown.Option("Saída"),
            ft.dropdown.Option("Dívida"),
            ft.dropdown.Option("Empréstimo"),
        ],
        value="Despesa",
        **estilo_campo
    )

    # 3. Forma de Movimentação
    def on_forma_change(e):
        # Mostra ou oculta os campos de parcela com base na seleção
        if dd_forma_mov.value == "Credito":
            row_parcelas.visible = True
        else:
            row_parcelas.visible = False
            txt_parcela_atual.value = ""
            txt_total_parcelas.value = ""
        page.update()

    dd_forma_mov = ft.Dropdown(
        label="Forma de Mov.",
        options=[
            ft.dropdown.Option("Credito"),
            ft.dropdown.Option("Debito"),
            ft.dropdown.Option("Pix"),
            ft.dropdown.Option("Dinheiro"),
        ],
        value="Pix",
        on_change=on_forma_change,
        **estilo_campo
    )

    # Campos Dinâmicos (Crédito)
    txt_parcela_atual = ft.TextField(
        label="Parcela Atual",
        hint_text="Ex: 1",
        keyboard_type=ft.KeyboardType.NUMBER,
        **estilo_campo
    )
    txt_total_parcelas = ft.TextField(
        label="Total Parcelas",
        hint_text="Ex: 12",
        keyboard_type=ft.KeyboardType.NUMBER,
        **estilo_campo
    )
    
    row_parcelas = ft.ResponsiveRow(
        controls=[
            ft.Container(content=txt_parcela_atual, col={"xs": 6}),
            ft.Container(content=txt_total_parcelas, col={"xs": 6}),
        ],
        visible=False, # Oculto por padrão
        spacing=10,
        run_spacing=10,
    )

    # 4. Valor, Data, Hora
    txt_valor = ft.TextField(
        label="Valor (R$)",
        hint_text="0.00",
        keyboard_type=ft.KeyboardType.NUMBER,
        prefix_text="R$ ",
        **estilo_campo
    )

    data_hoje = datetime.now().strftime("%Y-%m-%d")
    hora_agora = datetime.now().strftime("%H:%M")

    txt_data = ft.TextField(
        label="Data",
        hint_text="AAAA-MM-DD",
        value=data_hoje,
        **estilo_campo
    )
    txt_hora = ft.TextField(
        label="Hora",
        hint_text="HH:MM",
        value=hora_agora,
        **estilo_campo
    )

    # 5. Dropdowns populados do banco (Conta, Categoria, Destino)
    dd_conta = ft.Dropdown(label="Conta", **estilo_campo)
    dd_categoria = ft.Dropdown(label="Categoria", **estilo_campo)
    dd_destino = ft.Dropdown(label="Destino", **estilo_campo)

    # Função para carregar opções do banco
    def carregar_opcoes():
        try:
            # Contas
            res_contas = listar_contas()
            if res_contas and res_contas.data:
                dd_conta.options = [ft.dropdown.Option(str(c["id"]), c["nome"]) for c in res_contas.data]
            
            # Categorias
            res_cat = listar_categorias()
            if res_cat and res_cat.data:
                dd_categoria.options = [ft.dropdown.Option(str(c["id"]), c["nome"]) for c in res_cat.data]
                
            # Destinos
            res_dest = listar_destinos()
            if res_dest and res_dest.data:
                dd_destino.options = [ft.dropdown.Option(str(c["id"]), c["nome"]) for c in res_dest.data]
                
        except Exception as ex:
            print("Erro ao carregar opções do banco:", ex)

    # Carrega as opções assim que a view é montada
    carregar_opcoes()

    # 6. Descrição
    txt_descricao = ft.TextField(
        label="Descrição",
        hint_text="O que foi esta movimentação?",
        multiline=True,
        max_lines=2,
        **estilo_campo
    )

    # --- Botão de Salvar ---
    spinner_loading = ft.ProgressRing(width=16, height=16, stroke_width=2.2, color=COLOR_TEXT_PRIMARY, visible=False)
    lbl_btn_salvar = ft.Text("Salvar Lançamento", size=14, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY)
    
    btn_salvar = ft.Container(
        content=ft.Row(
            controls=[spinner_loading, lbl_btn_salvar],
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=8,
        ),
        bgcolor=COLOR_PRIMARY,
        border_radius=10,
        height=48,
        alignment=ft.alignment.center,
        ink=True,
    )

    def acao_salvar(e):
        # Validações básicas
        if not txt_valor.value:
            mostrar_feedback(page, "O campo Valor é obrigatório.", "alerta")
            return
        if not dd_conta.value or not dd_categoria.value or not dd_destino.value:
            mostrar_feedback(page, "Selecione a Conta, Categoria e Destino.", "alerta")
            return

        # Montar payload
        try:
            valor_float = float(txt_valor.value.replace(",", "."))
        except ValueError:
            mostrar_feedback(page, "Valor inválido.", "erro")
            return

        dados = {
            "tipo": dd_tipo.value,
            "subtipo": dd_subtipo.value,
            "forma_movimentacao": dd_forma_mov.value,
            "valor": valor_float,
            "data": txt_data.value,
            "hora": txt_hora.value,
            "conta": dd_conta.value, # Estamos enviando o ID
            "categoria": dd_categoria.value, # ID
            "destino": dd_destino.value, # ID
            "descricao": txt_descricao.value or "",
        }

        if dd_forma_mov.value == "Credito":
            # Status é nulo no input pois o Trigger do Supabase cuida disso automaticamente,
            # mas precisamos enviar parcela atual e total
            if txt_parcela_atual.value.isdigit():
                dados["parcela_atual"] = int(txt_parcela_atual.value)
            if txt_total_parcelas.value.isdigit():
                dados["total_parcelas"] = int(txt_total_parcelas.value)

        # Inicia Loading
        spinner_loading.visible = True
        btn_salvar.disabled = True
        lbl_btn_salvar.value = "Salvando..."
        page.update()

        try:
            criar_lancamento(dados)
            mostrar_feedback(page, "Lançamento salvo com sucesso!", "sucesso")
            page.go("/dashboard")
        except Exception as ex:
            mostrar_feedback(page, f"Erro ao salvar: {ex}", "erro")
        finally:
            spinner_loading.visible = False
            btn_salvar.disabled = False
            lbl_btn_salvar.value = "Salvar Lançamento"
            page.update()

    btn_salvar.on_click = acao_salvar

    # --- Header da View ---
    header = ft.Container(
        content=ft.Row(
            controls=[
                ft.IconButton(
                    icon=ft.Icons.ARROW_BACK_ROUNDED,
                    icon_color=COLOR_TEXT_PRIMARY,
                    on_click=lambda e: page.go("/dashboard")
                ),
                ft.Text("Novo Lançamento", size=20, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
            ],
            alignment=ft.MainAxisAlignment.START,
        ),
        bgcolor=COLOR_SURFACE,
        border=ft.border.only(bottom=ft.BorderSide(1, COLOR_BORDER)),
        padding=ft.padding.symmetric(horizontal=16, vertical=14),
    )

    # --- Montagem do Formulário (Responsive) ---
    form_content = ft.ResponsiveRow(
        controls=[
            ft.Container(content=dd_tipo, col={"xs": 12, "md": 6}),
            ft.Container(content=dd_subtipo, col={"xs": 12, "md": 6}),
            
            ft.Container(content=dd_forma_mov, col={"xs": 12, "md": 6}),
            ft.Container(content=row_parcelas, col={"xs": 12, "md": 6}),
            
            ft.Container(content=txt_valor, col={"xs": 12, "md": 4}),
            ft.Container(content=txt_data, col={"xs": 12, "md": 4}),
            ft.Container(content=txt_hora, col={"xs": 12, "md": 4}),
            
            ft.Container(content=dd_conta, col={"xs": 12, "md": 4}),
            ft.Container(content=dd_categoria, col={"xs": 12, "md": 4}),
            ft.Container(content=dd_destino, col={"xs": 12, "md": 4}),
            
            ft.Container(content=txt_descricao, col={"xs": 12}),
        ],
        spacing=14,
        run_spacing=14,
    )

    card_form = ft.Container(
        content=ft.Column(
            controls=[
                form_content,
                ft.Container(height=10),
                btn_salvar
            ]
        ),
        bgcolor=COLOR_SURFACE,
        border=ft.border.all(1, COLOR_BORDER),
        border_radius=14,
        padding=24,
    )

    conteudo_principal = ft.Container(
        content=ft.Column(
            controls=[card_form],
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
        padding=24,
        expand=True,
    )

    return ft.View(
        route="/lancamentos",
        controls=[
            ft.Column(
                controls=[header, conteudo_principal],
                spacing=0,
                expand=True,
            )
        ],
        padding=0,
        bgcolor=COLOR_BG,
    )
