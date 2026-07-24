import flet as ft
from datetime import datetime

# Lista em memória — os dados somem ao fechar o app (banco virá depois)
lancamentos = []

# Opções dos menus (mesmas do protótipo no terminal)
FORMAS_PAGAMENTO = ["Credito", "Debito", "Pix", "Dinheiro"]
FORMAS_RECEBIMENTO = ["Debito", "Pix", "Dinheiro"]
CONTAS = ["Santander", "Itaú", "Inter", "Dinheiro"]
CATEGORIAS = [
    "Alimentação", "Transporte", "Moradia", "Lazer", "Saúde",
    "Educação", "DJ", "Investimento", "Outros",
]
DESTINOS = ["Eu", "Casa", "Moto", "Carro", "DJ", "Família", "Outros"]
STATUS_OPCOES = ["Pago", "Pendente"]
REGRAS = ["Essencial", "Estilo de Vida", "Investimento"]


def main(page: ft.Page):
    page.title = "DemBase"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 24
    page.scroll = ft.ScrollMode.AUTO

    area_conteudo = ft.Column(spacing=16, expand=True)
    mensagem = ft.Text(color=ft.Colors.RED)

    def mostrar_mensagem(texto, cor=ft.Colors.RED):
        mensagem.value = texto
        mensagem.color = cor
        mensagem.update()

    def limpar_mensagem():
        mensagem.value = ""
        mensagem.update()

    def ir_para(tela):
        limpar_mensagem()
        area_conteudo.controls.clear()
        area_conteudo.controls.append(tela())
        page.update()

    def card_lancamento(item):
        valor_formatado = f"R$ {item['valor']:.2f}"
        sinal = "+" if item["tipo"] == "Receita" else "-"
        cor_valor = ft.Colors.GREEN_700 if item["tipo"] == "Receita" else ft.Colors.RED_700

        detalhes = [
            f"Tipo: {item['tipo']} / {item['subtipo']}",
            f"Forma: {item['forma_movimentacao']}",
            f"Data: {item['data']} às {item['hora']}h",
            f"Conta: {item['conta']}",
            f"Categoria: {item['categoria']} | Destino: {item['destino']}",
            f"Status: {item['status']} | Regra: {item['regra']}",
        ]

        if item["forma_movimentacao"] == "Credito":
            detalhes.append(
                f"Parcela: {item['parcela_atual']}/{item['total_parcelas']} | Fatura: {item['fatura']}"
            )

        return ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(f"#{item['id']}", weight=ft.FontWeight.BOLD),
                                ft.Text(item["descricao"], expand=True),
                                ft.Text(f"{sinal} {valor_formatado}", color=cor_valor, weight=ft.FontWeight.BOLD),
                            ],
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        ),
                        *[ft.Text(linha, size=13, color=ft.Colors.GREY_700) for linha in detalhes],
                    ],
                    spacing=4,
                ),
            ),
        )

    def tela_inicial():
        total_receitas = sum(l["valor"] for l in lancamentos if l["tipo"] == "Receita")
        total_despesas = sum(l["valor"] for l in lancamentos if l["tipo"] == "Despesa")
        saldo = total_receitas - total_despesas

        return ft.Column(
            [
                ft.Text("DemBase", size=32, weight=ft.FontWeight.BOLD),
                ft.Text("Controle financeiro pessoal", color=ft.Colors.GREY_700),
                ft.Divider(),
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Column(
                                [ft.Text("Receitas"), ft.Text(f"R$ {total_receitas:.2f}", size=20, color=ft.Colors.GREEN_700)],
                            ),
                            padding=16,
                            bgcolor=ft.Colors.GREEN_50,
                            border_radius=8,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [ft.Text("Despesas"), ft.Text(f"R$ {total_despesas:.2f}", size=20, color=ft.Colors.RED_700)],
                            ),
                            padding=16,
                            bgcolor=ft.Colors.RED_50,
                            border_radius=8,
                            expand=True,
                        ),
                        ft.Container(
                            content=ft.Column(
                                [ft.Text("Saldo"), ft.Text(f"R$ {saldo:.2f}", size=20, weight=ft.FontWeight.BOLD)],
                            ),
                            padding=16,
                            bgcolor=ft.Colors.BLUE_50,
                            border_radius=8,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                ),
                ft.ElevatedButton("Novo lançamento", icon=ft.Icons.ADD, on_click=lambda _: ir_para(tela_novo_lancamento)),
                ft.OutlinedButton("Ver lançamentos", icon=ft.Icons.LIST, on_click=lambda _: ir_para(tela_listar)),
            ],
            spacing=16,
        )

    def tela_listar():
        if not lancamentos:
            lista = ft.Text("Nenhum lançamento cadastrado ainda.", color=ft.Colors.GREY_700)
        else:
            lista = ft.Column([card_lancamento(item) for item in lancamentos], spacing=8)

        return ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: ir_para(tela_inicial)),
                        ft.Text("Lançamentos", size=24, weight=ft.FontWeight.BOLD),
                    ],
                ),
                lista,
            ],
            spacing=12,
        )

    def tela_novo_lancamento():
        tipo = ft.Dropdown(label="Tipo", options=[ft.dropdown.Option("Receita"), ft.dropdown.Option("Despesa")], value="Receita", width=200)
        subtipo = ft.Dropdown(label="Subtipo", width=200)
        forma = ft.Dropdown(label="Forma de movimentação", width=250)
        valor = ft.TextField(label="Valor (R$)", hint_text="Ex: 150,50", keyboard_type=ft.KeyboardType.NUMBER)
        data = ft.TextField(label="Data", hint_text="DD/MM/AAAA", value=datetime.now().strftime("%d/%m/%Y"))
        hora = ft.TextField(label="Hora (0-23)", hint_text="Ex: 11", value=str(datetime.now().hour), width=120)
        conta = ft.Dropdown(label="Conta / banco", options=[ft.dropdown.Option(c) for c in CONTAS], width=200)
        descricao = ft.TextField(label="Descrição", expand=True)
        categoria = ft.Dropdown(label="Categoria", options=[ft.dropdown.Option(c) for c in CATEGORIAS], width=200)
        destino = ft.Dropdown(label="Destino", options=[ft.dropdown.Option(d) for d in DESTINOS], width=200)
        status = ft.Dropdown(label="Status", options=[ft.dropdown.Option(s) for s in STATUS_OPCOES], value="Pago", width=200)
        regra = ft.Dropdown(label="Regra financeira", options=[ft.dropdown.Option(r) for r in REGRAS], visible=False, width=220)

        parcela_atual = ft.TextField(label="Parcela atual", visible=False, width=150, keyboard_type=ft.KeyboardType.NUMBER)
        total_parcelas = ft.TextField(label="Total de parcelas", visible=False, width=150, keyboard_type=ft.KeyboardType.NUMBER)
        fatura = ft.TextField(label="Fatura", visible=False, hint_text="Ex: Agosto/2026", width=200)
        campos_credito = ft.Row([parcela_atual, total_parcelas, fatura], visible=False, spacing=12)

        def atualizar_subtipo(e=None):
            if tipo.value == "Receita":
                subtipo.options = [ft.dropdown.Option("Receita"), ft.dropdown.Option("Entrada")]
                forma.options = [ft.dropdown.Option(f) for f in FORMAS_RECEBIMENTO]
                regra.visible = False
            elif tipo.value == "Despesa":
                subtipo.options = [
                    ft.dropdown.Option("Despesa"),
                    ft.dropdown.Option("Saída"),
                    ft.dropdown.Option("Dívida"),
                    ft.dropdown.Option("Empréstimo"),
                ]
                forma.options = [ft.dropdown.Option(f) for f in FORMAS_PAGAMENTO]
                regra.visible = True
            else:
                subtipo.options = []
                forma.options = []

            subtipo.value = subtipo.options[0].key if subtipo.options else None
            forma.value = forma.options[0].key if forma.options else None
            atualizar_credito()
            subtipo.update()
            forma.update()
            regra.update()
            page.update()

        def atualizar_credito(e=None):
            eh_credito = forma.value == "Credito"
            parcela_atual.visible = eh_credito
            total_parcelas.visible = eh_credito
            fatura.visible = eh_credito
            campos_credito.visible = eh_credito
            page.update()

        tipo.on_change = atualizar_subtipo
        forma.on_change = atualizar_credito

        def salvar(e):
            limpar_mensagem()

            campos_obrigatorios = [tipo.value, subtipo.value, forma.value, conta.value, categoria.value, destino.value, status.value]
            if tipo.value == "Despesa":
                campos_obrigatorios.append(regra.value)

            if not all(campos_obrigatorios):
                mostrar_mensagem("Preencha todos os campos obrigatórios.")
                return

            if not descricao.value or not descricao.value.strip():
                mostrar_mensagem("Informe uma descrição.")
                return

            try:
                valor_num = float(valor.value.replace(",", "."))
                if valor_num <= 0:
                    raise ValueError
            except (ValueError, AttributeError):
                mostrar_mensagem("Digite um valor válido maior que zero.")
                return

            try:
                data_formatada = datetime.strptime(data.value.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")
            except ValueError:
                mostrar_mensagem("Data inválida. Use o formato DD/MM/AAAA.")
                return

            try:
                hora_num = int(hora.value)
                if not 0 <= hora_num <= 23:
                    raise ValueError
            except ValueError:
                mostrar_mensagem("Hora inválida. Use um número de 0 a 23.")
                return

            par_atual = None
            par_total = None
            fatura_val = None

            if forma.value == "Credito":
                try:
                    par_atual = int(parcela_atual.value)
                    par_total = int(total_parcelas.value)
                    if par_atual <= 0 or par_total <= 0:
                        raise ValueError
                except (ValueError, TypeError):
                    mostrar_mensagem("Informe parcelas válidas (números maiores que zero).")
                    return

                if not fatura.value or not fatura.value.strip():
                    mostrar_mensagem("Informe a fatura do cartão.")
                    return

                fatura_val = fatura.value.strip()

            lancamentos.append(
                {
                    "id": len(lancamentos) + 1,
                    "tipo": tipo.value,
                    "subtipo": subtipo.value,
                    "forma_movimentacao": forma.value,
                    "valor": valor_num,
                    "data": data_formatada,
                    "hora": hora_num,
                    "conta": conta.value,
                    "descricao": descricao.value.strip(),
                    "categoria": categoria.value,
                    "destino": destino.value,
                    "parcela_atual": par_atual,
                    "total_parcelas": par_total,
                    "fatura": fatura_val,
                    "status": status.value,
                    "regra": regra.value if tipo.value == "Despesa" else None,
                }
            )

            ir_para(tela_inicial)
            mostrar_mensagem("Lançamento cadastrado com sucesso!", ft.Colors.GREEN_700)

        subtipo.value = [ft.dropdown.Option("Receita"),
                        ft.dropdown.Option("Despesa")]

        subtipo.value = "Receita"

        forma.options = [ft.dropdown.Option(f) for f in FORMAS_RECEBIMENTO]

        forma.value = "Debito"
        
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: ir_para(tela_inicial)),
                        ft.Text("Novo lançamento", size=24, weight=ft.FontWeight.BOLD),
                    ],
                ),
                ft.ResponsiveRow(
                    [
                        ft.Column([tipo, subtipo, forma], spacing=12, col={"xs": 12, "md": 4}),
                        ft.Column([valor, data, hora], spacing=12, col={"xs": 12, "md": 4}),
                        ft.Column([conta, status, regra], spacing=12, col={"xs": 12, "md": 4}),
                    ],
                    spacing=12,
                ),
                descricao,
                ft.ResponsiveRow(
                    [
                        ft.Column([categoria], col={"xs": 12, "md": 6}),
                        ft.Column([destino], col={"xs": 12, "md": 6}),
                    ],
                ),
                campos_credito,
                ft.Row(
                    [
                        ft.ElevatedButton("Salvar", icon=ft.Icons.SAVE, on_click=salvar),
                        ft.OutlinedButton("Cancelar", on_click=lambda _: ir_para(tela_inicial)),
                    ],
                    spacing=12,
                ),
            ],
            spacing=16,
        )

    page.add(area_conteudo, mensagem)
    ir_para(tela_inicial)


if __name__ == "__main__":
    ft.app(main)
