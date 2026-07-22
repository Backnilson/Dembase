from datetime import datetime

# =========================
# LISTA PRINCIPAL DE LANÇAMENTOS
# ============================================

lancamentos = []


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def escolher_opcao(titulo, opcoes):
    print(f"\n{titulo}")

    for i, opcao in enumerate(opcoes, start=1):
        print(f"{i} - {opcao}")

    while True:
        escolha = input("Escolha uma opção: ")

        if escolha.isdigit():
            escolha = int(escolha)

            if 1 <= escolha <= len(opcoes):
                return opcoes[escolha - 1]

        print("Opção inválida. Tente novamente.")

def escolher_forma_pagamento():
    return escolher_opcao(
        "Escolha a forma de pagamento:",
        ["Credito", "Debito", "Pix", "Dinheiro"]
    )
def escolher_forma_de_recebimento():
    return escolher_opcao(
        "Escolha a forma de recebimento:",
        ["Debito", "Pix", "Dinheiro"]
    )

def escolher_tipo():
    tipo = escolher_opcao(
        "Escolha o tipo do lançamento:",
        ["Receita", "Despesa"] #Transferencia,investimento
    )

    if tipo == "Receita":
        subtipo = escolher_opcao(
            "Escolha o subtipo da receita:",
            ["Receita", "Entrada"]
        )

        forma_movimentacao= escolher_forma_de_recebimento()

        return tipo, subtipo, forma_movimentacao

    elif tipo == "Despesa":
        subtipo = escolher_opcao(
            "Escolha o subtipo da despesa:",
            ["Despesa", "Saída", "Dívida", "Empréstimo"]
        )

        forma_movimentacao = escolher_forma_pagamento()

        return tipo, subtipo, forma_movimentacao


def criar_lancamento():

    print("\n==============================")
    print("      NOVO LANÇAMENTO")
    print("==============================")

    # Tipo e subtipo
    tipo, subtipo, forma_movimentacao = escolher_tipo()

    # Valor
    while True:
        try:
            valor = float(input("\nDigite o valor: R$ ").replace(",", "."))
            break
        except ValueError:
            print("Digite um valor válido.")

    # Data
    while True:
        data = input("Digite a data (DD/MM/AAAA): ")

        try:
            data_formatada = datetime.strptime(
                data,
                "%d/%m/%Y"
            ).strftime("%Y-%m-%d")

            break

        except ValueError:
            print("Data inválida. Exemplo: 22/07/2026")

    # Hora arredondada
    while True:
        hora = input("Digite a hora (exemplo: 11): ")

        if hora.isdigit() and 0 <= int(hora) <= 23:
            hora = int(hora)
            break

        print("Digite uma hora válida entre 0 e 23.")

    # Conta
    conta = escolher_opcao(
        "Escolha a conta/banco:",
        [
            "Santander",
            "Itaú",
            "Inter",
            "Dinheiro"
        ]
    )

    # Descrição
    descricao = input("\nDigite a descrição: ")

    # Categoria
    categoria = escolher_opcao(
        "Escolha a categoria:",
        [
            "Alimentação",
            "Transporte",
            "Moradia",
            "Lazer",
            "Saúde",
            "Educação",
            "DJ",
            "Investimento",
            "Outros"
        ]
    )

    # Destino
    destino = escolher_opcao(
        "Escolha o destino:",
        [
            "Eu",
            "Casa",
            "Moto",
            "Carro",
            "DJ",
            "Família",
            "Outros"
        ]
    )

    # Valores padrão
    parcela_atual = None
    total_parcelas = None
    fatura = None

    # Só aparece se for crédito
    if forma_movimentacao == "Credito":

        while True:
            try:
                parcela_atual = int(
                    input("\nParcela atual: ")
                )

                total_parcelas = int(
                    input("Total de parcelas: ")
                )

                if parcela_atual > 0 and total_parcelas > 0:
                    break

                print("As parcelas devem ser maiores que zero.")

            except ValueError:
                print("Digite números válidos.")

        fatura = input("Fatura (exemplo: Agosto/2026): ")

    # Status
    status = escolher_opcao(
        "Escolha o status:",
        [
            "Pago",
            "Pendente"
        ]
    )

    # Regra 50/40/10
    regra = escolher_opcao(
        "Escolha a regra financeira:",
        [
            "Essencial",
            "Estilo de Vida",
            "Investimento"
        ]
    )

    # Criando o lançamento
    novo_lancamento = {

        "id": len(lancamentos) + 1,

        "tipo": tipo,

        "subtipo": subtipo,

        "forma_movimentacao": forma_movimentacao,

        "valor": valor,

        "data": data_formatada,

        "hora": hora,

        "conta": conta,

        "descricao": descricao,

        "categoria": categoria,

        "destino": destino,

        "parcela_atual": parcela_atual,

        "total_parcelas": total_parcelas,

        "fatura": fatura,

        "status": status,

        "regra": regra
    }

    lancamentos.append(novo_lancamento)

    print("\nLançamento cadastrado com sucesso!")

    return novo_lancamento


# ============================================
# EXIBIR LANÇAMENTOS
# ============================================

def listar_lancamentos():

    print("\n==============================")
    print("       LANÇAMENTOS")
    print("==============================")

    if not lancamentos:
        print("Nenhum lançamento cadastrado.")
        return

    for lancamento in lancamentos:

        print("\n------------------------------")

        print(f"ID: {lancamento['id']}")
        print(f"Tipo: {lancamento['tipo']}")
        print(f"Subtipo: {lancamento['subtipo']}")
        print(f"Forma de movimentação: {lancamento['forma_movimentacao']}")
        print(f"Valor: R$ {lancamento['valor']:.2f}")
        print(f"Data: {lancamento['data']}")
        print(f"Hora: {lancamento['hora']}h")
        print(f"Conta: {lancamento['conta']}")
        print(f"Descrição: {lancamento['descricao']}")
        print(f"Categoria: {lancamento['categoria']}")
        print(f"Destino: {lancamento['destino']}")
        print(f"Parcela: {lancamento['parcela_atual']}")
        print(f"Total de parcelas: {lancamento['total_parcelas']}")
        print(f"Fatura: {lancamento['fatura']}")
        print(f"Status: {lancamento['status']}")
        print(f"Regra: {lancamento['regra']}")


# ============================================
# MENU PRINCIPAL
# ============================================

while True:

    print("\n==============================")
    print("          DEMBASE")
    print("==============================")

    print("1 - Novo lançamento")
    print("2 - Ver lançamentos")
    print("3 - Sair")

    opcao = input("\nEscolha uma opção: ")

    if opcao == "1":

        criar_lancamento()

    elif opcao == "2":

        listar_lancamentos()

    elif opcao == "3":

        print("Saindo do DemBase...")
        break

    else:

        print("Opção inválida.")



