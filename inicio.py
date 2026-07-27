import flet as ft



def main(page: ft.Page):

    lancamentos = [{"id": 1, "tipo": "receita", "descricao": "Salário", "valor": 5000.00, "data": "2024-06-01"}]

    area_conteudo = ft.Column(spacing=16, expand=True)

    mensagem = ft.Text(color=ft.Colors.RED)

    def mostrar_mensagem(texto, cor=ft.Colors.RED):
        mensagem.value = texto
        mensagem.color = cor
        page.update()
          
    def limpar_mensagem():      
        mensagem.value = ""
        page.update()



    def ir_para(tela):
            area_conteudo.controls.clear()
            area_conteudo.controls.append(tela())
            page.update()
    
    def  tela_principal():
            widget_dos_lançamentos = []
            for item in lancamentos:
                widget_dos_lançamentos.append(ft.Text(f"{item['descricao']} - R$ {item['valor']:.2f} - {item['data']}"))

            return ft.Column([ft.Text("Dembasse", size=30, weight=ft.FontWeight.BOLD),
                                ft.Text("Controle finaceiro pessoal", size=24, weight=ft.FontWeight.BOLD), *widget_dos_lançamentos,
                                ft.ElevatedButton("Novo Lançamento", on_click=lambda _: ir_para(tela_novo_lancamento))  ])

    
    def tela_novo_lancamento():
        campo_descricao = ft.TextField( label="Descrição", hint_text="Digite a descrição do lançamento")
        campo_tipo = ft.Dropdown(label="Tipo", options=[ft.dropdown.Option("Receita"), ft.dropdown.Option("Despesa")], value="Receita")
        campo_valor = ft.TextField(label="Valor", hint_text="Digite o valor do lançamento",keyboard_type=ft.KeyboardType.NUMBER)

        def salvar():
                    
            limpar_mensagem()

            if not campo_descricao.value or not campo_descricao.value.strip():
                mostrar_mensagem("Preencha a descrição.")
                return 

            try:
                valor_num = float(campo_valor.value.replace(",","."))
                if valor_num <= 0:
                    mostrar_mensagem("O valor deve ser maior que zero.")
                    return
                
            except ValueError:
                    mostrar_mensagem("O valor deve ser um número válido.")
                    return

                
            descricao = campo_descricao.value
            tipo = campo_tipo.value
            valor = float(campo_valor.value)
            lancamentos.append({"id": len(lancamentos) + 1, "tipo": tipo, "descricao": descricao, "valor": valor, "data": "2024-06-01"})
            ir_para(tela_principal)

        return ft.Column([
            campo_descricao,
            campo_tipo,
            campo_valor,
            ft.ElevatedButton("Salvar", on_click=lambda _: salvar()),
            ft.ElevatedButton("Voltar", on_click=lambda _: ir_para(tela_principal))]
        , spacing=16)

    page.add(area_conteudo, mensagem)
    page.title = "Dembasse"
    page.theme_mode = ft.ThemeMode.DARK
    ir_para(tela_principal)
    page.update()

ft.app(main)

