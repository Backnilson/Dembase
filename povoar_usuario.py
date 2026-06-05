import sqlite3

def inserir_usuario():
    #Fazendo conexao ao banco de dados
    conexao = sqlite3.connect('dembase.db')
    cursor = conexao.cursor()

    #Recebendo dados e os preparando
    nome_usuario = "Denilson Alves"
    essencial = 0.5
    lazer = 0.3
    reserva = 0.2

    #Preparando o INSERT na varialvel sql usando placeholders por segurança
    sql = """INSERT INTO usuarios (nome, regra_essencial, regra_lazer, regra_reserva)
    VALUES (?,?,?,?)"""

    #usando try, except para tratamento de possiveis erros
    try:
        #passando os dados recebidos para os placeholdes e executando o comando de INSERT
        cursor.execute(sql, (nome_usuario, essencial, lazer, reserva))

        #Dando o commit para que as informação sejam salvas no banco de dados
        conexao.commit()
        print("Comando executado com sucesso!")

    #Informa se houve algum erro ao inserir as informações no banco
    except sqlite3.Error as e:
        print(f"Erro nas informações fornecidas ao banco de dados:{e}")
    #Informa se houve algum erro no codigo
    except Exception as e:
        print(f"Erro no codigo:{e}")
    #Fecha a conexão houvendo erro ou não
    finally:
        conexao.close()


def conferindo_dados():
    #Fazendo conexao ao banco de dados
    conexao = sqlite3.connect('dembase.db')
    cursor = conexao.cursor()
    #Pegando informaçãon da tabela usuarios do banco de dados
    cursor.execute("SELECT * FROM usuarios")
    usuarios = cursor.fetchall()
    #Mostrando as informação no terminal
    print("\n --- Dados no Banco ---")
    for usuario in usuarios:
        print(usuario)
    #Fechando conexão
    conexao.close()

if __name__ == "__main__":
    inserir_usuario()
    conferindo_dados()