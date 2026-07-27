import flet as ft
from datetime import datetime


#Pagina principal do aplicativo
def main(page: ft.Page):
    #Armazena os lançamentos
    lancamentos = [{"id": 1, "tipo": "Receita", "descricao": "Salário", "valor": 5000.00, "data": datetime.now().strftime("%d/%m/%Y")},]

    #Usado para exibir ou apagar conteudo na tela
    area_conteudo = ft.Column(spacing=16, expand=True)

    #Usado para exibir mensagens de erro ou sucesso
    mensagem = ft.Text(color=ft.Colors.RED)

    #Função para exibir mensagens na tela
    def mostrar_mensagem(texto, cor=ft.Colors.RED):
        mensagem.value = texto
        mensagem.color = cor
        page.update()

    #Função para limpar a mensagem exibida na tela
    def limpar_mensagem():      
        mensagem.value = ""
        page.update()

    #Função para exibir a tela de listagem de lançamentos
    def tela_lista_lacamentos():
        def card_lancamento(item):
            valor_formatado = f"R$ {item['valor']:.2f}"
            sinal = "+" if item['tipo'] == "Receita" else "-"
            cor_valor = ft.Colors.GREEN if item['tipo'] == "Receita" else ft.Colors.RED

            return ft.Card(
                content=ft.Container(
                    padding=16,
                    content=ft.Column([
                        ft.Row([
                            ft.Text(item["descricao"],expand=True, weight=ft.FontWeight.BOLD),
                            ft.Text(f"{sinal} {valor_formatado}", color=cor_valor, weight=ft.FontWeight.BOLD),], 
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                            ft.Text(item["data"], size=13, color=ft.Colors.GREY_700),
                        ], spacing=4),
                ),
            )
        widget_dos_lancamentos = []

        #Adiciona cada lançamento na lista de widgets
        for item in lancamentos:

            widget_dos_lancamentos.append(card_lancamento(item))

        #Retorna a tela de listagem de lançamentos
        return ft.Column([
            ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: ir_para(tela_principal)),
            ft.Text("Lançamentos", size=30, weight=ft.FontWeight.BOLD), *widget_dos_lancamentos], spacing=16)

    #Função para navegar entre as telas
    def ir_para(tela):
            area_conteudo.controls.clear()
            area_conteudo.controls.append(tela())
            page.update()

    #Tela principal do aplicativo
    def  tela_principal():

        #Calcula o total de receitas, despesas e saldo
        total_receitas = sum(item["valor"]for item in lancamentos if item["tipo"] == "Receita")
        
        total_despesas = sum(item["valor"]for item in lancamentos if item["tipo"] == "Despesa")
        
        saldo = total_receitas - total_despesas   

        #Retorna a tela principal com os totais calculados
        return ft.Column([

            ft.Text("Dembasse", size=30, weight=ft.FontWeight.BOLD),

            ft.Text("Controle finaceiro pessoal", size=24, weight=ft.FontWeight.BOLD),

            #Exibe os totais de receitas, despesas e saldo em containers coloridos
            ft.Row([
                ft.Container(
                    content=ft.Column([ft.Text("Receitas"), ft.Text(f"R$ {total_receitas:.2f}")]),
                    bgcolor=ft.Colors.GREEN_50,
                    padding=16,
                    border_radius=8,
                    expand=True,
                    ),

                ft.Container(
                    content=ft.Column([ft.Text("Despesas"), ft.Text(f"R$ {total_despesas:.2f}")]),
                    bgcolor=ft.Colors.RED_50,
                    padding=16,
                    border_radius=8,
                    expand=True,),

                ft.Container(
                    content=ft.Column([ft.Text("Saldo"), ft.Text   (f"R$ {saldo:.2f}")]),
                    bgcolor=ft.Colors.BLUE_50,
                    padding=16,
                    border_radius=8,
                    expand=True,
                    ),

                ],spacing=12),
                                

            ft.ElevatedButton("Novo Lançamento", on_click=lambda _: ir_para(tela_novo_lancamento)),

            ft.ElevatedButton("Ver Lançamentos", on_click=lambda _: ir_para(tela_lista_lacamentos)),], spacing=16)

            

    #Tela para adicionar um novo lançamento
    def tela_novo_lancamento():

        #Variáveis para armazenar os campos de entrada do usuário
        campo_descricao = ft.TextField( label="Descrição", hint_text="Digite a descrição do lançamento")

        campo_tipo = ft.Dropdown(label="Tipo", options=[ft.dropdown.Option("Receita"), ft.dropdown.Option("Despesa")], value="Receita")

        campo_valor = ft.TextField(label="Valor", hint_text="Digite o valor do lançamento",keyboard_type=ft.KeyboardType.NUMBER)

        #Função para salvar o novo lançamento
        def salvar():
                    
            limpar_mensagem()

            #Valida se os campos foram preenchidos corretamente
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
            #Variável para armazenar os dados do lançamento
            descricao = campo_descricao.value
            tipo = campo_tipo.value
            valor = valor_num
            lancamentos.append({"id": len(lancamentos) + 1, "tipo": tipo, "descricao": descricao, "valor": valor, "data": datetime.now().strftime("%d/%m/%Y")})
            ir_para(tela_principal)
            mostrar_mensagem("Lançamento salvo com sucesso!", cor=ft.Colors.GREEN)

            
        #Mostra a tela de novo lançamento com os campos de entrada e botões de ação
        return ft.Column([
            ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: ir_para(tela_principal)),

            campo_descricao,
            campo_tipo,
            campo_valor,

            ft.ElevatedButton("Salvar", on_click=lambda _: salvar()),
            ]
        , spacing=16)

    
    #Adiciona a área de conteúdo e a mensagem à página, define o título e o tema, e exibe a tela principal
    page.add(area_conteudo, mensagem)
    page.title = "Dembasse"
    page.theme_mode = ft.ThemeMode.LIGHT
    ir_para(tela_principal)
    page.update()

# Inicia o aplicativo somente quando este arquivo é executado diretamente    
if __name__ == "__main__":     
    ft.app(main)

