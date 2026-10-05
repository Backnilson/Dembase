"""
=============================================================================
DemBase v3 — services/supabase_client.py
ÚNICO ponto de contato com o Supabase. Nenhuma view importa a lib diretamente.
Encapsula: Auth, CRUD de todas as tabelas e chamadas RPC.
=============================================================================
"""
import os
import ssl
import httpx
import httpx._config
import httpx._transports.default
from dotenv import load_dotenv

# Garante compatibilidade SSL nativa do Windows para httpx e Supabase
def _criar_ssl_context_nativo(*args, **kwargs):
    return ssl.create_default_context()

httpx.create_ssl_context = _criar_ssl_context_nativo
httpx._config.create_ssl_context = _criar_ssl_context_nativo
httpx._transports.default.create_ssl_context = _criar_ssl_context_nativo

from supabase import create_client, Client

load_dotenv()

_URL = os.environ.get("SUPABASE_URL", "")
_KEY = os.environ.get("SUPABASE_KEY", "")

if not _URL or not _KEY:
    raise EnvironmentError(
        "Credenciais do Supabase não encontradas. "
        "Verifique o arquivo .env (SUPABASE_URL e SUPABASE_KEY)."
    )

supabase: Client = create_client(_URL, _KEY)


# =============================================================================
# AUTH
# =============================================================================
def cadastrar_usuario(email: str, password: str, nome: str):
    """Cadastra novo usuário. O trigger no banco cria o perfil automaticamente."""
    return supabase.auth.sign_up({
        "email": email,
        "password": password,
        "options": {"data": {"full_name": nome}},
    })


def fazer_login(email: str, password: str):
    return supabase.auth.sign_in_with_password({"email": email, "password": password})


def fazer_logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass


def recuperar_senha(email: str):
    """Solicita envio de e-mail de recuperação de senha pelo Supabase."""
    return supabase.auth.reset_password_for_email(email.strip())


def login_social(provider: str, redirect_to: str = None) -> str:
    """
    Inicia autenticação OAuth (Google / Apple) via Supabase signInWithOAuth.
    Retorna a URL de redirecionamento/autorização pronta para abertura no navegador.
    """
    prov = provider.lower().strip()
    creds = {"provider": prov}
    if redirect_to:
        creds["options"] = {"redirect_to": redirect_to}
    resp = supabase.auth.sign_in_with_oauth(creds)
    return getattr(resp, "url", "") or ""


def abrir_url_navegador(url: str) -> bool:
    """Abre a URL de autenticação no navegador padrão do sistema operacional."""
    import webbrowser
    if url:
        return webbrowser.open(url)
    return False


def restaurar_sessao(access_token: str, refresh_token: str) -> bool:
    """Restaura sessão ativa a partir de tokens salvos."""
    try:
        if not access_token or not refresh_token:
            return False
        resp = supabase.auth.set_session(access_token, refresh_token)
        return bool(resp and resp.user)
    except Exception:
        return False


def sessao_atual():
    """Retorna a sessão atual ou None se não houver usuário logado."""
    return supabase.auth.get_session()


def usuario_atual():
    """Retorna o objeto User atual ou None."""
    try:
        resp = supabase.auth.get_user()
        return resp.user if resp else None
    except Exception:
        return None


# =============================================================================
# PERFIS
# =============================================================================
def ler_perfil() -> dict | None:
    user = usuario_atual()
    if not user:
        return None
    resp = supabase.table("perfis").select("*").eq("id", user.id).single().execute()
    return resp.data


def atualizar_perfil(dados: dict):
    user = usuario_atual()
    if not user:
        return None
    return supabase.table("perfis").update(dados).eq("id", user.id).execute()


# =============================================================================
# CONTAS BANCÁRIAS
# =============================================================================
def listar_contas() -> list:
    resp = (
        supabase.table("contas")
        .select("*")
        .eq("ativo", True)
        .order("nome")
        .execute()
    )
    return resp.data or []


def criar_conta(dados: dict):
    """
    dados deve conter: nome, tipo_conta, banco (opcional), cor, icone,
    saldo_inicial. user_id é injetado pelo RLS.
    """
    user = usuario_atual()
    if user:
        dados["user_id"] = user.id
        dados["perfil_id"] = user.id
    return supabase.table("contas").insert(dados).execute()


def atualizar_conta(conta_id: str, dados: dict):
    return supabase.table("contas").update(dados).eq("id", conta_id).execute()


def deletar_conta(conta_id: str):
    """Soft delete — preserva histórico de lançamentos."""
    return supabase.table("contas").update({"ativo": False}).eq("id", conta_id).execute()


def atualizar_saldo_conta(conta_id: str, saldo_atual: float, saldo_previsto: float):
    """Atualiza os saldos calculados de uma conta."""
    return supabase.table("contas").update({
        "saldo_atual": saldo_atual,
        "saldo_previsto": saldo_previsto,
    }).eq("id", conta_id).execute()


# =============================================================================
# CATEGORIAS
# =============================================================================
def listar_categorias(tipo: str = None) -> list:
    """Lista categorias. Filtra por tipo ('receita'|'despesa'|'ambos') se informado."""
    query = supabase.table("categorias").select("*").eq("ativo", True)
    if tipo:
        query = query.in_("tipo", [tipo, "ambos"])
    resp = query.order("nome").execute()
    return resp.data or []


def criar_categoria(dados: dict):
    """dados: nome, tipo, cor, icone"""
    user = usuario_atual()
    if user:
        dados["user_id"] = user.id
        dados["perfil_id"] = user.id
    return supabase.table("categorias").insert(dados).execute()


def atualizar_categoria(categoria_id: str, dados: dict):
    return supabase.table("categorias").update(dados).eq("id", categoria_id).execute()


def deletar_categoria(categoria_id: str):
    return supabase.table("categorias").update({"ativo": False}).eq("id", categoria_id).execute()


# =============================================================================
# SUBCATEGORIAS
# =============================================================================
def listar_subcategorias(categoria_id: str = None) -> list:
    query = supabase.table("subcategorias").select("*, categorias(nome)").eq("ativo", True)
    if categoria_id:
        cat_id_str = str(categoria_id).strip()
        is_uuid = False
        try:
            import uuid
            uuid.UUID(cat_id_str)
            is_uuid = True
        except (ValueError, TypeError, AttributeError):
            is_uuid = False

        if is_uuid:
            query = query.eq("categoria_id", cat_id_str)
        else:
            cat_resp = supabase.table("categorias").select("id").ilike("nome", cat_id_str).eq("ativo", True).execute()
            if cat_resp.data:
                query = query.eq("categoria_id", cat_resp.data[0]["id"])
            else:
                return []
    resp = query.order("nome").execute()
    return resp.data or []


def criar_subcategoria(categoria_id: str, nome: str, cor: str = "#94A3B8"):
    user = usuario_atual()
    cat_id_str = str(categoria_id).strip()
    try:
        import uuid
        uuid.UUID(cat_id_str)
    except Exception:
        c = supabase.table("categorias").select("id").ilike("nome", cat_id_str).eq("ativo", True).execute()
        if c.data:
            cat_id_str = c.data[0]["id"]
    dados = {"categoria_id": cat_id_str, "nome": nome, "cor": cor}
    if user:
        dados["user_id"] = user.id
    return supabase.table("subcategorias").insert(dados).execute()


def atualizar_subcategoria(subcategoria_id: str, dados: dict):
    return supabase.table("subcategorias").update(dados).eq("id", subcategoria_id).execute()


def obter_ou_criar_subcategoria(categoria_id: str, nome: str) -> dict:
    """Busca subcategoria pelo nome (case insensitive) na categoria. Se não existir, cria e retorna."""
    if not nome or not nome.strip():
        return None
    nome = nome.strip()
    cat_id_str = str(categoria_id).strip()
    try:
        import uuid
        uuid.UUID(cat_id_str)
    except Exception:
        c = supabase.table("categorias").select("id").ilike("nome", cat_id_str).eq("ativo", True).execute()
        if c.data:
            cat_id_str = c.data[0]["id"]
    # Tenta buscar
    resp = supabase.table("subcategorias").select("*").eq("categoria_id", cat_id_str).ilike("nome", nome).eq("ativo", True).execute()
    if resp.data:
        return resp.data[0]
    # Se não existe, cria
    c_resp = criar_subcategoria(cat_id_str, nome)
    return c_resp.data[0] if c_resp.data else None


def deletar_subcategoria(subcategoria_id: str):
    return supabase.table("subcategorias").update({"ativo": False}).eq("id", subcategoria_id).execute()


# =============================================================================
# DESTINOS
# =============================================================================
def listar_destinos() -> list:
    resp = supabase.table("destinos").select("*").eq("ativo", True).order("nome").execute()
    return resp.data or []


def criar_destino(nome: str):
    user = usuario_atual()
    dados: dict = {"nome": nome}
    if user:
        dados["user_id"] = user.id
    return supabase.table("destinos").insert(dados).execute()


def atualizar_destino(destino_id: str, dados: dict):
    return supabase.table("destinos").update(dados).eq("id", destino_id).execute()


def deletar_destino(destino_id: str):
    return supabase.table("destinos").update({"ativo": False}).eq("id", destino_id).execute()


# =============================================================================
# CARTÕES DE CRÉDITO
# =============================================================================
def listar_cartoes() -> list:
    resp = (
        supabase.table("cartoes")
        .select("*")
        .eq("ativo", True)
        .order("nome")
        .execute()
    )
    return resp.data or []


def criar_cartao(dados: dict):
    """
    dados: nome, bandeira, cor, icone, limite_total,
           dia_vencimento, dia_fechamento, conta_debito_id (opcional)
    """
    user = usuario_atual()
    if user:
        dados["user_id"] = user.id
    # limite_disponivel começa igual ao limite_total
    dados.setdefault("limite_disponivel", dados.get("limite_total", 0))
    return supabase.table("cartoes").insert(dados).execute()


def atualizar_cartao(cartao_id: str, dados: dict):
    return supabase.table("cartoes").update(dados).eq("id", cartao_id).execute()


def deletar_cartao(cartao_id: str):
    return supabase.table("cartoes").update({"ativo": False}).eq("id", cartao_id).execute()


# =============================================================================
# FATURAS
# =============================================================================
def listar_faturas(cartao_id: str = None, status: str = None) -> list:
    query = supabase.table("faturas").select("*, cartoes(nome, bandeira, cor)")
    if cartao_id:
        query = query.eq("cartao_id", cartao_id)
    if status:
        query = query.eq("status", status)
    resp = query.order("data_vencimento", desc=True).execute()
    return resp.data or []


def obter_fatura_atual(cartao_id: str, mes: int, ano: int) -> dict | None:
    resp = (
        supabase.table("faturas")
        .select("*")
        .eq("cartao_id", cartao_id)
        .eq("mes", mes)
        .eq("ano", ano)
        .single()
        .execute()
    )
    return resp.data


def criar_ou_obter_fatura(cartao_id: str, mes: int, ano: int, data_vencimento: str, data_fechamento: str) -> dict:
    """Cria a fatura se não existir, ou retorna a existente. Padrão upsert seguro."""
    existente = obter_fatura_atual(cartao_id, mes, ano)
    if existente:
        return existente
    user = usuario_atual()
    resp = supabase.table("faturas").insert({
        "cartao_id": cartao_id,
        "user_id": user.id if user else None,
        "mes": mes,
        "ano": ano,
        "data_vencimento": data_vencimento,
        "data_fechamento": data_fechamento,
        "status": "aberta",
    }).execute()
    return resp.data[0] if resp.data else {}


def atualizar_fatura(fatura_id: str, dados: dict):
    return supabase.table("faturas").update(dados).eq("id", fatura_id).execute()


def pagar_fatura(fatura_id: str, valor_pago: float):
    """Marca fatura como paga e atualiza valor_pago."""
    return supabase.table("faturas").update({
        "valor_pago": valor_pago,
        "status": "paga",
    }).eq("id", fatura_id).execute()


# =============================================================================
# LANÇAMENTOS
# =============================================================================
def criar_lancamento(dados: dict):
    """Insere um lançamento. O trigger no banco define o status automático."""
    user = usuario_atual()
    if user:
        dados.setdefault("user_id", user.id)
        dados.setdefault("perfil_id", user.id)
    dados.setdefault("fonte_importacao", "manual")
    return supabase.table("lancamentos").insert(dados).execute()


def listar_lancamentos(
    data_inicio: str = None,
    data_fim: str = None,
    filtros: dict = None,
) -> list:
    """
    Retorna lançamentos com joins para exibir nomes de conta/categoria/destino/cartão.
    Suporta filtros flexíveis de data.
    """
    query = supabase.table("lancamentos").select(
        "*, contas(nome,cor,icone), categorias(nome,cor,icone), "
        "destinos(nome), cartoes(nome,bandeira,cor), "
        "subcategorias(nome), faturas(mes,ano,status)"
    )
    if data_inicio:
        query = query.gte("data", data_inicio)
    if data_fim:
        query = query.lte("data", data_fim)
    if filtros:
        for chave, valor in filtros.items():
            query = query.eq(chave, valor)
    resp = query.order("data", desc=True).order("hora", desc=True).execute()
    return resp.data or []


def obter_lancamento(lancamento_id: str) -> dict | None:
    resp = (
        supabase.table("lancamentos")
        .select(
            "*, contas(nome,cor,icone), categorias(nome,cor,icone), "
            "destinos(nome), cartoes(nome,bandeira,cor), "
            "subcategorias(nome), faturas(mes,ano,status)"
        )
        .eq("id", lancamento_id)
        .single()
        .execute()
    )
    return resp.data


def atualizar_lancamento(lancamento_id: str, dados: dict):
    return supabase.table("lancamentos").update(dados).eq("id", lancamento_id).execute()


def deletar_lancamento(lancamento_id: str):
    return supabase.table("lancamentos").delete().eq("id", lancamento_id).execute()


def importar_lancamentos_csv(lista: list[dict]) -> dict:
    """
    Importação em lote. Usa upsert com external_id para evitar duplicatas.
    Retorna {'inseridos': N, 'ignorados': M, 'erros': [...]}.
    """
    user = usuario_atual()
    inseridos, erros = 0, []
    for item in lista:
        try:
            if user:
                item["user_id"] = user.id
            item.setdefault("fonte_importacao", "csv_mobills")
            supabase.table("lancamentos").upsert(
                item,
                on_conflict="user_id,external_id",
                ignore_duplicates=True,
            ).execute()
            inseridos += 1
        except Exception as ex:
            erros.append({"item": item, "erro": str(ex)})
    return {"inseridos": inseridos, "ignorados": len(lista) - inseridos - len(erros), "erros": erros}


# =============================================================================
# TRANSAÇÕES RECORRENTES
# =============================================================================
def listar_recorrentes() -> list:
    resp = (
        supabase.table("transacoes_recorrentes")
        .select("*, contas(nome), categorias(nome,cor), cartoes(nome)")
        .eq("ativo", True)
        .order("descricao")
        .execute()
    )
    return resp.data or []


def criar_recorrente(dados: dict):
    user = usuario_atual()
    if user:
        dados["user_id"] = user.id
    return supabase.table("transacoes_recorrentes").insert(dados).execute()


def desativar_recorrente(recorrente_id: str):
    return supabase.table("transacoes_recorrentes").update({"ativo": False}).eq("id", recorrente_id).execute()


# =============================================================================
# OBJETIVOS / METAS
# =============================================================================
def listar_objetivos() -> list:
    resp = (
        supabase.table("objetivos")
        .select("*")
        .eq("ativo", True)
        .order("data_limite")
        .execute()
    )
    return resp.data or []


def criar_objetivo(dados: dict):
    user = usuario_atual()
    if user:
        dados["user_id"] = user.id
    return supabase.table("objetivos").insert(dados).execute()


def atualizar_objetivo(objetivo_id: str, dados: dict):
    return supabase.table("objetivos").update(dados).eq("id", objetivo_id).execute()


def deletar_objetivo(objetivo_id: str):
    return supabase.table("objetivos").update({"ativo": False}).eq("id", objetivo_id).execute()


# =============================================================================
# RPCs DO DASHBOARD E MÓDULOS (processamento no PostgreSQL)
# =============================================================================
def obter_overview_dashboard(mes: int = None, ano: int = None) -> dict:
    """
    Chama a RPC 'get_dashboard_overview'.
    Retorna: {receitas, despesas, saldo, saldo_contas, total_faturas, periodo_*}
    """
    params: dict = {}
    if mes:
        params["p_mes"] = mes
    if ano:
        params["p_ano"] = ano
    resp = supabase.rpc("get_dashboard_overview", params).execute()
    return resp.data or {}


def obter_despesas_por_categoria(mes: int = None, ano: int = None) -> dict:
    """Chama 'get_despesas_por_categoria'. Retorna {total, categorias: [...]}"""
    params: dict = {}
    if mes:
        params["p_mes"] = mes
    if ano:
        params["p_ano"] = ano
    resp = supabase.rpc("get_despesas_por_categoria", params).execute()
    return resp.data or {"total": 0, "categorias": []}


def obter_receitas_por_categoria(mes: int = None, ano: int = None) -> dict:
    """Chama 'get_receitas_por_categoria'. Retorna {total, categorias: [...]}"""
    params: dict = {}
    if mes:
        params["p_mes"] = mes
    if ano:
        params["p_ano"] = ano
    resp = supabase.rpc("get_receitas_por_categoria", params).execute()
    return resp.data or {"total": 0, "categorias": []}


def obter_balanco_6_meses() -> list:
    """Chama 'get_balanco_ultimos_6_meses'. Retorna [{mes, ano, label, receitas, despesas, saldo}]"""
    resp = supabase.rpc("get_balanco_ultimos_6_meses", {}).execute()
    return resp.data or []


def obter_frequencia_gastos(mes: int = None, ano: int = None) -> list:
    """Chama 'get_frequencia_gastos_mes'. Retorna [{data, dia, despesas, receitas}]"""
    params: dict = {}
    if mes:
        params["p_mes"] = mes
    if ano:
        params["p_ano"] = ano
    resp = supabase.rpc("get_frequencia_gastos_mes", params).execute()
    return resp.data or []


def obter_resumo_contas() -> dict:
    """Chama 'get_resumo_contas'. Retorna {saldo_total_atual, saldo_total_previsto, contas:[...]}"""
    resp = supabase.rpc("get_resumo_contas", {}).execute()
    return resp.data or {"saldo_total_atual": 0, "saldo_total_previsto": 0, "contas": []}


def obter_resumo_cartoes(mes: int = None, ano: int = None) -> dict:
    """Chama 'get_resumo_cartoes'. Retorna {total_limite, total_disponivel, total_faturas, cartoes:[...]}"""
    params: dict = {}
    if mes:
        params["p_mes"] = mes
    if ano:
        params["p_ano"] = ano
    resp = supabase.rpc("get_resumo_cartoes", params).execute()
    return resp.data or {"total_limite": 0, "total_disponivel": 0, "total_faturas": 0, "cartoes": []}


def obter_lancamentos_calendario(mes: int, ano: int) -> list:
    """Chama 'get_lancamentos_calendario'. Retorna [{data, dia, lancamentos:[...], total_despesas, total_receitas}]"""
    resp = supabase.rpc("get_lancamentos_calendario", {"p_mes": mes, "p_ano": ano}).execute()
    return resp.data or []


# Mantém compatibilidade com código antigo
def obter_totais_dashboard(data_inicio: str = None, data_fim: str = None) -> dict:
    """Legado — mantido para não quebrar dashboard_view.py atual."""
    params: dict = {}
    if data_inicio:
        params["p_data_inicio"] = data_inicio
    if data_fim:
        params["p_data_fim"] = data_fim
    resp = supabase.rpc("get_financial_totals", params).execute()
    return resp.data or {"receitas": 0, "despesas": 0, "saldo": 0}


def obter_resumo_5030(data_inicio: str = None, data_fim: str = None) -> dict:
    """Legado — mantido para não quebrar dashboard_view.py atual."""
    params: dict = {}
    if data_inicio:
        params["p_data_inicio"] = data_inicio
    if data_fim:
        params["p_data_fim"] = data_fim
    resp = supabase.rpc("get_regra_50_30_20_summary", params).execute()
    return resp.data or {}
