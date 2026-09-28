import os
from dotenv import load_dotenv
from supabase import create_client, Client

# ==========================================
# 1. Configuração da Conexão
# ==========================================
# Carrega as variáveis definidas no arquivo .env
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")  # Chave Anon

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Credenciais do Supabase não encontradas. Verifique o arquivo .env")

# Criação do cliente global para acessar o Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ==========================================
# 2. Funções de Autenticação
# ==========================================
def cadastrar_usuario(email: str, password: str, nome: str) -> dict:
    """
    Cadastra um novo usuário utilizando o Auth do Supabase.
    Passa o 'nome' no metadata. Um gatilho (Trigger) no banco criará
    automaticamente o registro correspondente na tabela 'perfis'.
    """
    response = supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {
            "data": {
                "full_name": nome
            }
        }
    })
    return response

def fazer_login(email: str, password: str) -> dict:
    """
    Realiza o login. 
    A sessão será mantida no objeto 'supabase', garantindo que 
    as requisições subsequentes passem pelas políticas de segurança (RLS).
    """
    response = supabase.auth.sign_in_with_password({
        "email": email,
        "password": password
    })
    return response

def fazer_logout():
    """Encerra a sessão do usuário atual."""
    supabase.auth.sign_out()

def obter_sessao_atual():
    """Retorna os dados da sessão/usuário atualmente logado, se houver."""
    return supabase.auth.get_session()


# ==========================================
# 3. Funções CRUD (Lógica Central)
# ==========================================
# Nota: Graças ao RLS (Row Level Security) no banco, todas essas chamadas
# alterarão e retornarão APENAS os dados pertencentes ao usuário logado.

# --- PERFIS ---
def ler_perfil_logado():
    """Lê os dados extras de perfil do usuário logado."""
    user = supabase.auth.get_user()
    if not user:
        return None
    return supabase.table("perfis").select("*").eq("id", user.user.id).single().execute()

def atualizar_perfil(dados: dict):
    """Atualiza informações como o nome do usuário."""
    user = supabase.auth.get_user()
    if not user:
        return None
    return supabase.table("perfis").update(dados).eq("id", user.user.id).execute()

# --- CONTAS ---
def criar_conta(nome: str):
    return supabase.table("contas").insert({"nome": nome}).execute()

def listar_contas():
    return supabase.table("contas").select("*").order("criado_em", desc=True).execute()

def atualizar_conta(conta_id: str, dados: dict):
    return supabase.table("contas").update(dados).eq("id", conta_id).execute()

def deletar_conta(conta_id: str):
    return supabase.table("contas").delete().eq("id", conta_id).execute()

# --- CATEGORIAS ---
def criar_categoria(nome: str):
    return supabase.table("categorias").insert({"nome": nome}).execute()

def listar_categorias():
    return supabase.table("categorias").select("*").order("criado_em", desc=True).execute()

def atualizar_categoria(categoria_id: str, dados: dict):
    return supabase.table("categorias").update(dados).eq("id", categoria_id).execute()

def deletar_categoria(categoria_id: str):
    return supabase.table("categorias").delete().eq("id", categoria_id).execute()

# --- DESTINOS ---
def criar_destino(nome: str):
    return supabase.table("destinos").insert({"nome": nome}).execute()

def listar_destinos():
    return supabase.table("destinos").select("*").order("criado_em", desc=True).execute()

def atualizar_destino(destino_id: str, dados: dict):
    return supabase.table("destinos").update(dados).eq("id", destino_id).execute()

def deletar_destino(destino_id: str):
    return supabase.table("destinos").delete().eq("id", destino_id).execute()

# --- LANÇAMENTOS ---
def criar_lancamento(dados: dict):
    """
    Insere um lançamento. 
    Exemplo de campos em 'dados': 
    tipo, subtipo, forma_movimentacao, valor, data, descricao, etc.
    """
    return supabase.table("lancamentos").insert(dados).execute()

def listar_lancamentos(filtros: dict = None, data_inicio: str = None, data_fim: str = None):
    """
    Retorna lançamentos. Atende à regra de 'filtros flexíveis de data' do MVP.
    """
    query = supabase.table("lancamentos").select("*")
    
    if data_inicio:
        query = query.gte("data", data_inicio)
    if data_fim:
        query = query.lte("data", data_fim)
        
    if filtros:
        for chave, valor in filtros.items():
            query = query.eq(chave, valor)
            
    return query.order("data", desc=True).execute()

def atualizar_lancamento(lancamento_id: str, dados: dict):
    return supabase.table("lancamentos").update(dados).eq("id", lancamento_id).execute()

def deletar_lancamento(lancamento_id: str):
    return supabase.table("lancamentos").delete().eq("id", lancamento_id).execute()


# ==========================================
# 4. Agregações Processadas no Banco
# ==========================================
def obter_totais_dashboard() -> dict:
    """
    Invoca a função (RPC) 'get_financial_totals' diretamente no PostgreSQL.
    O banco de dados calcula a soma de receitas, despesas e saldo,
    retornando apenas os totais finais (processamento ultra-rápido no lado servidor).
    """
    resposta = supabase.rpc("get_financial_totals", {}).execute()
    # A estrutura esperada é: {'receitas': X, 'despesas': Y, 'saldo': Z}
    return resposta.data

