import sqlite3

def criar_banco():
    #Criando o banco de dados dembase.db se ele não existir
    conexao = sqlite3.connect('dembase.db')
    cursor = conexao.cursor()

    #Criando a tabela Usuario
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        regra_essencial REAL DEFAULT 0.5,
        regra_lazer REAL DEFAULT 0.3,
        regra_reserva REAL DEFAULT 0.2
    )
    ''')
    #fazendo commit e encerrando a conexão
    conexao.commit()
    conexao.close()
    print("Banco de dados e tabela 'usuarios' criados com sucesso!")

if __name__ == "__main__":
    criar_banco()