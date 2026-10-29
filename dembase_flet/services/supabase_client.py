"""



=============================================================================



DemBase v3 — services/supabase_client.py



ÚNICO ponto de contato com o Supabase. Nenhuma view importa a lib diretamente.



Encapsula: Auth, CRUD de todas as tabelas e chamadas RPC.



=============================================================================



"""



import os



import time



import asyncio



from typing import Any, Callable, Optional, Dict, List, Union



import ssl



import httpx



import httpx._config



import httpx._transports.default



from dotenv import load_dotenv







# Garante compatibilidade SSL nativa do Windows para httpx e Supabase



try:



    def _criar_ssl_context_nativo(*args, **kwargs):



        return ssl.create_default_context()







    httpx.create_ssl_context = _criar_ssl_context_nativo



    if hasattr(httpx, "_config"):



        httpx._config.create_ssl_context = _criar_ssl_context_nativo



    if hasattr(httpx, "_transports") and hasattr(httpx._transports, "default"):



        httpx._transports.default.create_ssl_context = _criar_ssl_context_nativo



except Exception:



    pass







from supabase import create_client, Client







load_dotenv()







_DEFAULT_URL = "https://ieljnrkxxopqzpnlodfk.supabase.co"



_DEFAULT_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImllbGpucmt4eG9wcXpwbmxvZGZrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTAyMjUzNjQsImV4cCI6MjEwNTgwMTM2NH0.0mAJi0XgEJmjmLu3TrsDoKjVkejHZ3aof8dBhnZIzV0"







_URL = os.environ.get("SUPABASE_URL") or _DEFAULT_URL



_KEY = os.environ.get("SUPABASE_KEY") or _DEFAULT_KEY







if not _URL or not _KEY:



    raise EnvironmentError(



        "Credenciais do Supabase não encontradas. "



        "Verifique o arquivo .env (SUPABASE_URL e SUPABASE_KEY)."



    )







supabase: Client = create_client(_URL, _KEY)







# =============================================================================



# SISTEMA DE CACHE EM MEMÓRIA (RAM) E EXECUÇÃO ASSÍNCRONA SEM UI BLOCKING



# =============================================================================



_CACHE_RAM: dict[str, Any] = {



    "potes": {"dados": None, "expira_em": 0.0},



    "potes_resumo": {},          # chave (data_inicio_data_fim) -> {"dados": dict, "expira_em": float}



    "categorias": {"dados": None, "expira_em": 0.0},



    "categorias_por_tipo": {},  # tipo -> {"dados": list, "expira_em": float}



    "subcategorias": {},        # cat_id -> {"dados": list, "expira_em": float}



    "contas": {"dados": None, "expira_em": 0.0},



    "cartoes": {"dados": None, "expira_em": 0.0},

    "caixinhas": {"dados": None, "expira_em": 0.0},



    "perfil": {"dados": None, "expira_em": 0.0},



}







TTL_CADASTROS_BASE = 600.0   # 10 minutos para potes, categorias, contas e cartões



TTL_RESUMO_POTES   = 120.0   # 2 minutos para potes do período











def obter_cache(chave: str, subchave: Any = None) -> Any | None:



    """Recupera dados em memória se válidos e dentro do TTL."""



    agora = time.monotonic()



    if subchave is not None:



        subdict = _CACHE_RAM.get(chave)



        if isinstance(subdict, dict) and subchave in subdict:



            item = subdict[subchave]



            if isinstance(item, dict) and agora < item.get("expira_em", 0.0):



                return item.get("dados")



        return None



    item = _CACHE_RAM.get(chave)



    if isinstance(item, dict) and item.get("dados") is not None:



        if agora < item.get("expira_em", 0.0):



            return item.get("dados")



    return None











def salvar_cache(chave: str, dados: Any, subchave: Any = None, ttl: float = TTL_CADASTROS_BASE) -> None:



    """Armazena dados em memória com TTL calculado."""



    expira_em = time.monotonic() + ttl



    if subchave is not None:



        if chave not in _CACHE_RAM or not isinstance(_CACHE_RAM[chave], dict):



            _CACHE_RAM[chave] = {}



        _CACHE_RAM[chave][subchave] = {"dados": dados, "expira_em": expira_em}



    else:



        _CACHE_RAM[chave] = {"dados": dados, "expira_em": expira_em}











def invalidar_cache(tipo: str | None = None) -> None:



    """Invalida cirurgicamente ou totalmente o cache em memória."""



    if tipo == "potes":



        _CACHE_RAM["potes"] = {"dados": None, "expira_em": 0.0}



        _CACHE_RAM["potes_resumo"].clear()



    elif tipo == "categorias":



        _CACHE_RAM["categorias"] = {"dados": None, "expira_em": 0.0}



        _CACHE_RAM["categorias_por_tipo"].clear()



        _CACHE_RAM["subcategorias"].clear()



    elif tipo == "contas":



        _CACHE_RAM["contas"] = {"dados": None, "expira_em": 0.0}



    elif tipo == "cartoes":



        _CACHE_RAM["cartoes"] = {"dados": None, "expira_em": 0.0}



    elif tipo == "lancamentos":



        _CACHE_RAM["potes_resumo"].clear()



        _CACHE_RAM["contas"] = {"dados": None, "expira_em": 0.0}



        _CACHE_RAM["cartoes"] = {"dados": None, "expira_em": 0.0}



    elif tipo == "caixinhas":

        _CACHE_RAM["caixinhas"] = {"dados": None, "expira_em": 0.0}

    elif tipo == "perfil":



        _CACHE_RAM["caixinhas"] = {"dados": None, "expira_em": 0.0}

        _CACHE_RAM["perfil"] = {"dados": None, "expira_em": 0.0}



    else:



        # Invalidação total (ex: logout)



        _CACHE_RAM["potes"] = {"dados": None, "expira_em": 0.0}



        _CACHE_RAM["potes_resumo"].clear()



        _CACHE_RAM["categorias"] = {"dados": None, "expira_em": 0.0}



        _CACHE_RAM["categorias_por_tipo"].clear()



        _CACHE_RAM["subcategorias"].clear()



        _CACHE_RAM["contas"] = {"dados": None, "expira_em": 0.0}



        _CACHE_RAM["cartoes"] = {"dados": None, "expira_em": 0.0}



        _CACHE_RAM["perfil"] = {"dados": None, "expira_em": 0.0}











def aquecer_cache() -> None:



    """Pré-carrega potes, categorias, contas e cartões em background thread sem travar a interface."""



    import threading



    def _worker():



        try:



            listar_potes()



            listar_categorias()



            listar_contas()



            listar_cartoes()



            ler_perfil()



        except Exception:



            pass



    t = threading.Thread(target=_worker, daemon=True, name="dembase_cache_warmup")



    t.start()











async def aquecer_cache_async() -> None:



    await asyncio.to_thread(aquecer_cache)











async def executar_async(func: Callable, *args, **kwargs) -> Any:



    """Executa chamadas do Supabase em background thread sem bloquear o event loop da UI."""



    return await asyncio.to_thread(func, *args, **kwargs)











async def listar_potes_async(mes: int | None = None, ano: int | None = None) -> list:
    return await asyncio.to_thread(listar_potes, False, mes, ano)











async def listar_categorias_async(tipo: str = None) -> list:



    return await asyncio.to_thread(listar_categorias, tipo)











async def obter_resumo_potes_async(data_inicio: str, data_fim: str, piso_custos_fixos: float = 1150.00) -> dict:
    chave_p = f"{data_inicio}_{data_fim}_{float(piso_custos_fixos)}"
    cached = obter_cache("potes_resumo", subchave=chave_p)
    if cached is not None:
        return dict(cached)

    padrao = {"renda": 0, "total_gasto": 0, "saldo": 0,
              "percentual_renda_usado": 0, "potes": [],
              "sem_pote": {"qtd": 0, "total": 0}}
    try:
        resp = await asyncio.to_thread(
            lambda: supabase.rpc(
                "get_potes_resumo",
                {"p_data_inicio": data_inicio, "p_data_fim": data_fim, "p_piso_fixos": float(piso_custos_fixos)}
            ).execute()
        )
        dados = resp.data or padrao
        salvar_cache("potes_resumo", dados, subchave=chave_p, ttl=TTL_RESUMO_POTES)
        return dados
    except Exception as ex:
        # Fallback para RPC com 2 parâmetros se necessário
        try:
            resp = await asyncio.to_thread(
                lambda: supabase.rpc("get_potes_resumo", {"p_data_inicio": data_inicio, "p_data_fim": data_fim}).execute()
            )
            dados = resp.data or padrao
            salvar_cache("potes_resumo", dados, subchave=chave_p, ttl=TTL_RESUMO_POTES)
            return dados
        except Exception:
            logger.warning(f"Erro ao obter resumo potes async: {ex}")
            return padrao

async def obter_dashboard_periodo_async(data_inicio: str, data_fim: str) -> dict:



    return await asyncio.to_thread(obter_dashboard_periodo, data_inicio, data_fim)











async def obter_relatorio_cartao_async(cartao_id: str, data_inicio: str, data_fim: str, filtros: dict = None) -> dict:



    return await asyncio.to_thread(obter_relatorio_cartao, cartao_id, data_inicio, data_fim, filtros)











async def obter_relatorio_conta_async(conta_id: str, data_inicio: str, data_fim: str, filtros: dict = None) -> dict:



    return await asyncio.to_thread(obter_relatorio_conta, conta_id, data_inicio, data_fim, filtros)











async def obter_relatorio_lancamentos_async(**kwargs) -> dict:



    return await asyncio.to_thread(obter_relatorio_lancamentos, **kwargs)











async def obter_balanco_6_meses_async() -> list:



    return await asyncio.to_thread(obter_balanco_6_meses)











async def obter_overview_dashboard_async(mes: int = None, ano: int = None, data_inicio: str = None, data_fim: str = None) -> dict:



    return await asyncio.to_thread(obter_overview_dashboard, mes, ano, data_inicio=data_inicio, data_fim=data_fim)











async def obter_despesas_por_categoria_async(mes: int = None, ano: int = None, data_inicio: str = None, data_fim: str = None) -> dict:



    return await asyncio.to_thread(obter_despesas_por_categoria, mes, ano, data_inicio=data_inicio, data_fim=data_fim)











async def listar_faturas_async(cartao_id: str = None, status: str = None, mes: int = None, ano: int = None) -> list:



    return await asyncio.to_thread(listar_faturas, cartao_id, status, mes, ano)











async def obter_lista_contas_resumo_async(data_inicio: str = None, data_fim: str = None) -> dict:



    return await asyncio.to_thread(obter_lista_contas_resumo, data_inicio, data_fim)











def listar_faturas_opcoes_cartao(cartao_id: str) -> list[dict]:



    """



    Retorna opções amigáveis de faturas para seleção no formulário de compra no cartão.



    Inclui faturas abertas existentes e opções calculadas para os próximos 12 meses.



    """



    if not cartao_id:



        return []



    try:



        faturas_db = listar_faturas(cartao_id=cartao_id)



    except Exception:



        faturas_db = []







    faturas_map = {}



    for f in faturas_db:



        m = f.get("mes")



        a = f.get("ano")



        if m and a:



            faturas_map[(int(m), int(a))] = f







    meses_pt = [



        "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",



        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"



    ]







    from datetime import date



    hoje = date.today()



    opcoes = []







    # Gera opções cobrindo do mês anterior até os próximos 12 meses



    for offset_mes in range(-1, 13):



        ano_alvo = hoje.year + ((hoje.month + offset_mes - 1) // 12)



        mes_alvo = ((hoje.month + offset_mes - 1) % 12) + 1



        



        fatura_existente = faturas_map.get((mes_alvo, ano_alvo))



        nome_mes = meses_pt[mes_alvo] if 1 <= mes_alvo <= 12 else str(mes_alvo)



        



        status_label = ""



        f_id = None



        if fatura_existente:



            f_id = str(fatura_existente.get("id"))



            st = str(fatura_existente.get("status") or "").lower()



            if st == "aberta":



                status_label = " (Aberta)"



            elif st == "fechada":



                status_label = " (Fechada)"



            elif st == "paga":



                status_label = " (Paga)"



        



        opcoes.append({



            "id": f_id or f"futura_{mes_alvo}_{ano_alvo}",



            "fatura_id_real": f_id,



            "mes": mes_alvo,



            "ano": ano_alvo,



            "label": f"{nome_mes}/{ano_alvo}{status_label}",



        })



    return opcoes











def obter_ou_criar_fatura_por_mes_ano(cartao_id: str, mes: int, ano: int) -> dict:



    """Garante que a fatura do mês/ano exista para o cartão selecionado."""



    if not cartao_id or not mes or not ano:



        return {}



    existente = obter_fatura_atual(cartao_id, mes, ano)



    if existente:



        return existente



    



    # Busca dados do cartão para compor vencimento e fechamento



    user = usuario_atual()



    try:



        cartao_resp = supabase.table("cartoes").select("*").eq("id", cartao_id).maybe_single().execute()



        cartao = cartao_resp.data or {}



    except Exception:



        cartao = {}



    dia_fech = int(cartao.get("dia_fechamento") or 1)
    dia_venc = int(cartao.get("dia_vencimento") or 10)

    import calendar
    # REGRA DE OURO: mes e ano representam o MÊS e ANO DO VENCIMENTO da fatura
    last_day_venc = calendar.monthrange(ano, mes)[1]
    dv_dia = min(dia_venc, last_day_venc)
    data_venc = f"{ano:04d}-{mes:02d}-{dv_dia:02d}"

    # Se dia_vencimento < dia_fechamento, a fatura fechou no mês anterior
    if dia_venc < dia_fech:
        if mes == 1:
            mes_fech = 12
            ano_fech = ano - 1
        else:
            mes_fech = mes - 1
            ano_fech = ano
    else:
        mes_fech = mes
        ano_fech = ano

    last_day_fech = calendar.monthrange(ano_fech, mes_fech)[1]
    df_dia = min(dia_fech, last_day_fech)
    data_fech = f"{ano_fech:04d}-{mes_fech:02d}-{df_dia:02d}"

    return criar_ou_obter_fatura(
        cartao_id=cartao_id,
        mes=mes,
        ano=ano,
        data_vencimento=data_venc,
        data_fechamento=data_fech,
    )











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



def ler_perfil(forcar_atualizacao: bool = False) -> dict | None:



    if not forcar_atualizacao:



        cached = obter_cache("perfil")



        if cached is not None:



            return cached



    user = usuario_atual()



    if not user:



        return None



    resp = supabase.table("perfis").select("*").eq("id", user.id).single().execute()



    dados = resp.data



    if dados:



        salvar_cache("perfil", dados, ttl=TTL_CADASTROS_BASE)



    return dados











def atualizar_perfil(dados: dict):



    invalidar_cache('perfil')



    user = usuario_atual()



    if not user:



        return None



    return supabase.table("perfis").update(dados).eq("id", user.id).execute()











# =============================================================================



# CONTAS BANCÁRIAS



# =============================================================================



def listar_contas(forcar_atualizacao: bool = False) -> list:



    if not forcar_atualizacao:



        cached = obter_cache("contas")



        if cached is not None:



            return list(cached)



    resp = (



        supabase.table("contas")



        .select("*")



        .eq("ativo", True)



        .order("nome")



        .execute()



    )



    dados = resp.data or []



    salvar_cache("contas", dados, ttl=TTL_CADASTROS_BASE)



    return dados











MAPA_TIPOS_CONTA = {



    "corrente": "corrente",



    "conta corrente": "corrente",



    "poupanca": "poupanca",



    "poupança": "poupanca",



    "conta poupanca": "poupanca",



    "conta poupança": "poupanca",



    "dinheiro": "dinheiro",



    "carteira": "dinheiro",



    "carteira / dinheiro": "dinheiro",



    "investimento": "investimento",



    "investimentos": "investimento",



    "outro": "outro",



    "outros": "outro",



    "outra": "outro",



}











def normalizar_tipo_conta(tipo: str | None) -> str:



    """Normaliza o tipo de conta para respeitar a constraint contas_tipo_conta_check."""



    if not tipo:



        return "corrente"



    chave = str(tipo).strip().lower()



    return MAPA_TIPOS_CONTA.get(chave, "outro")











def criar_conta(dados: dict):



    """



    dados deve conter: nome, tipo_conta, banco (opcional), cor, icone,



    saldo_inicial. user_id é injetado pelo RLS.



    """



    payload = dict(dados)



    if "tipo" in payload:



        tipo_legado = payload.pop("tipo")



        payload.setdefault("tipo_conta", tipo_legado)



    payload["tipo_conta"] = normalizar_tipo_conta(payload.get("tipo_conta"))



    saldo_ini = float(payload.get("saldo_inicial", 0) or 0)



    payload.setdefault("saldo_inicial", saldo_ini)



    payload.setdefault("saldo_atual", saldo_ini)



    payload.setdefault("saldo_previsto", saldo_ini)







    user = usuario_atual()



    if user:



        payload["user_id"] = user.id



        payload["perfil_id"] = user.id



    resp = supabase.table("contas").insert(payload).execute()



    if user:



        recalcular_saldos_usuario(user.id)



    return resp











def recalcular_saldos_usuario(user_id: str = None) -> bool:



    """Invoca a RPC atômica fn_recalcular_saldos_usuario no PostgreSQL se disponível."""



    try:



        uid = user_id



        if not uid:



            u = usuario_atual()



            uid = u.id if u else None



        if not uid:



            return False



        supabase.rpc("fn_recalcular_saldos_usuario", {"p_user_id": str(uid)}).execute()



        return True



    except Exception:



        return False











def atualizar_conta(conta_id: str, dados: dict):



    """



    Atualiza dados de uma conta com invalidação de cache, tipagem segura de números



    e sincronização automática de saldos.



    """



    invalidar_cache('contas')



    payload = dict(dados)



    if "tipo" in payload:



        tipo_legado = payload.pop("tipo")



        payload.setdefault("tipo_conta", tipo_legado)



    if "tipo_conta" in payload:



        payload["tipo_conta"] = normalizar_tipo_conta(payload["tipo_conta"])







    # Conversão estrita de tipos para números decimais



    for campo_num in ("saldo_inicial", "saldo_atual", "saldo_previsto"):



        if campo_num in payload and payload[campo_num] is not None:



            try:



                payload[campo_num] = float(round(float(payload[campo_num]), 2))



            except (ValueError, TypeError):



                pass







    user = usuario_atual()



    resp = supabase.table("contas").update(payload).eq("id", conta_id).execute()







    # Se resp.data vier vazio, tenta associar user_id caso tenha sido criado sem ele



    if not (resp and resp.data) and user:



        payload_rec = dict(payload)



        payload_rec["user_id"] = user.id



        resp = supabase.table("contas").update(payload_rec).eq("id", conta_id).execute()







    if user:



        recalcular_saldos_usuario(user.id)







    return resp











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



def listar_categorias(tipo: str = None, forcar_atualizacao: bool = False) -> list:



    """Lista categorias. Filtra por tipo com suporte a RAM cache instantâneo."""



    if not forcar_atualizacao:



        if tipo:



            cached_sub = obter_cache("categorias_por_tipo", subchave=tipo)



            if cached_sub is not None:



                return list(cached_sub)



        else:



            cached = obter_cache("categorias")



            if cached is not None:



                return list(cached)







    query = supabase.table("categorias").select("*").eq("ativo", True)



    if tipo:



        query = query.in_("tipo", [tipo, "ambos"])



    resp = query.order("nome").execute()



    dados = resp.data or []



    if tipo:



        salvar_cache("categorias_por_tipo", dados, subchave=tipo, ttl=TTL_CADASTROS_BASE)



    else:



        salvar_cache("categorias", dados, ttl=TTL_CADASTROS_BASE)



    return dados











def normalizar_tipo_categoria(tipo: str | None) -> str:



    """Normaliza o tipo de categoria para respeitar a constraint categorias_tipo_check."""



    if not tipo:



        return "ambos"



    chave = str(tipo).strip().lower()



    return chave if chave in ("receita", "despesa", "ambos") else "ambos"











def criar_categoria(dados: dict):



    """dados: nome, tipo, cor, icone"""



    invalidar_cache('categorias')



    payload = dict(dados)



    payload["tipo"] = normalizar_tipo_categoria(payload.get("tipo"))



    user = usuario_atual()



    if user:



        payload["user_id"] = user.id



        payload["perfil_id"] = user.id



    return supabase.table("categorias").insert(payload).execute()











def atualizar_categoria(categoria_id: str, dados: dict):



    invalidar_cache('categorias')



    payload = dict(dados)



    if "tipo" in payload:



        payload["tipo"] = normalizar_tipo_categoria(payload["tipo"])



    return supabase.table("categorias").update(payload).eq("id", categoria_id).execute()











def deletar_categoria(categoria_id: str):



    invalidar_cache('categorias')



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



    invalidar_cache('categorias')



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



    invalidar_cache('categorias')



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



def listar_cartoes(forcar_atualizacao: bool = False) -> list:



    if not forcar_atualizacao:



        cached = obter_cache("cartoes")



        if cached is not None:



            return list(cached)



    resp = (



        supabase.table("cartoes")



        .select("*")



        .eq("ativo", True)



        .order("nome")



        .execute()



    )



    dados = resp.data or []



    salvar_cache("cartoes", dados, ttl=TTL_CADASTROS_BASE)



    return dados











MAPA_BANDEIRAS_CARTAO = {



    "mastercard": "mastercard",



    "master": "mastercard",



    "visa": "visa",



    "elo": "elo",



    "amex": "amex",



    "american express": "amex",



    "american_express": "amex",



    "hipercard": "hipercard",



    "hiper": "hipercard",



    "outro": "outro",



    "outra": "outro",



    "outros": "outro",



}











def normalizar_bandeira_cartao(bandeira: str | None) -> str:



    """Normaliza a bandeira do cartão para respeitar a constraint cartoes_bandeira_check."""



    if not bandeira:



        return "mastercard"



    chave = str(bandeira).strip().lower()



    return MAPA_BANDEIRAS_CARTAO.get(chave, "outro")











def criar_cartao(dados: dict):



    """



    dados: nome, bandeira, cor, icone, limite_total,



           dia_vencimento, dia_fechamento, conta_debito_id (opcional)



    """



    payload = dict(dados)



    payload["bandeira"] = normalizar_bandeira_cartao(payload.get("bandeira"))



    user = usuario_atual()



    if user:



        payload["user_id"] = user.id



    # limite_disponivel começa igual ao limite_total



    payload.setdefault("limite_disponivel", payload.get("limite_total", 0))



    resp = supabase.table("cartoes").insert(payload).execute()



    invalidar_cache('cartoes')



    invalidar_cache('dashboard')



    return resp











def atualizar_cartao(cartao_id: str, dados: dict):



    invalidar_cache('cartoes')



    invalidar_cache('dashboard')



    payload = dict(dados)



    if "bandeira" in payload:



        payload["bandeira"] = normalizar_bandeira_cartao(payload["bandeira"])



    resp = supabase.table("cartoes").update(payload).eq("id", cartao_id).execute()

    # Cascata: se alterou dia de vencimento ou fechamento, sincroniza faturas abertas/fechadas
    if "dia_vencimento" in payload or "dia_fechamento" in payload:
        try:
            sincronizar_faturas_do_cartao(cartao_id)
        except Exception as ex:
            print(f"[atualizar_cartao] Falha na cascata de faturas: {ex}")
            raise
        invalidar_cache()

    return resp


def calcular_datas_fatura(mes: int, ano: int, dia_fech: int, dia_venc: int) -> tuple[str, str]:
    """Calcula (data_vencimento, data_fechamento) em formato ISO. mes e ano representam o vencimento."""
    import calendar
    dv = min(dia_venc, calendar.monthrange(ano, mes)[1])
    if dia_venc < dia_fech:
        mf, af = (12, ano - 1) if mes == 1 else (mes - 1, ano)
    else:
        mf, af = mes, ano
    df = min(dia_fech, calendar.monthrange(af, mf)[1])
    return f"{ano:04d}-{mes:02d}-{dv:02d}", f"{af:04d}-{mf:02d}-{df:02d}"


def sincronizar_faturas_do_cartao(cartao_id: str, cliente=None) -> int:
    """
    Recalcula data_vencimento e data_fechamento das faturas NÃO pagas (status 'aberta' ou 'fechada')
    de um cartão de acordo com os dias atuais cadastrados. Preserva faturas pagas/históricas.
    """
    cli = cliente or supabase
    c = (cli.table("cartoes").select("dia_fechamento,dia_vencimento").eq("id", cartao_id).single().execute().data) or {}
    dia_fech = int(c.get("dia_fechamento") or 1)
    dia_venc = int(c.get("dia_vencimento") or 10)
    faturas = (
        cli.table("faturas").select("id,mes,ano,data_vencimento,data_fechamento,status")
        .eq("cartao_id", cartao_id).in_("status", ["aberta", "fechada"]).execute().data
    ) or []
    alteradas = 0
    for f in faturas:
        novo_v, novo_f = calcular_datas_fatura(int(f["mes"]), int(f["ano"]), dia_fech, dia_venc)
        if str(f.get("data_vencimento") or "")[:10] != novo_v or str(f.get("data_fechamento") or "")[:10] != novo_f:
            cli.table("faturas").update({"data_vencimento": novo_v, "data_fechamento": novo_f}).eq("id", f["id"]).execute()
            alteradas += 1
    return alteradas











def deletar_cartao(cartao_id: str):



    invalidar_cache('cartoes')



    invalidar_cache('dashboard')



    return supabase.table("cartoes").update({"ativo": False}).eq("id", cartao_id).execute()











def obter_cartao(cartao_id: str) -> dict | None:



    """Busca um cartão específico pelo seu ID (UUID) com fallback de cache."""



    if not cartao_id:



        return None



    try:



        resp = supabase.table("cartoes").select("*").eq("id", str(cartao_id)).maybe_single().execute()



        if resp and resp.data:



            return resp.data



    except Exception:



        pass



    # Fallback: varre listar_cartoes



    try:



        for c in listar_cartoes():



            if str(c.get("id")) == str(cartao_id):



                return c



    except Exception:



        pass



    return None











def obter_total_em_uso_cartao(cartao_id: str) -> float:



    """



    Calcula o total de compras em aberto no cartão (faturas não pagas).



    Representa o valor real comprometido no limite do cartão de crédito.



    """



    if not cartao_id:



        return 0.0



    try:



        resp = (



            supabase.table("lancamentos")



            .select("valor, fatura_id, status, tipo")



            .eq("cartao_id", str(cartao_id))



            .execute()



        )



        itens = resp.data or []



        if not itens:



            return 0.0







        fatura_ids = list({str(it["fatura_id"]) for it in itens if it.get("fatura_id")})



        faturas_pagas = set()



        if fatura_ids:



            try:



                f_resp = supabase.table("faturas").select("id, status").in_("id", fatura_ids).execute()



                for f in (f_resp.data or []):



                    if str(f.get("status") or "").lower() == "paga":



                        faturas_pagas.add(str(f["id"]))



            except Exception:



                pass







        total_usado = 0.0



        for it in itens:



            fid = str(it.get("fatura_id") or "")



            if fid in faturas_pagas:



                continue



            tp = str(it.get("tipo") or "").lower()



            val = float(it.get("valor", 0) or 0)



            if tp == "receita":



                total_usado -= val



            else:



                total_usado += val



        return max(0.0, total_usado)



    except Exception as ex:



        print(f"[SupabaseClient] Erro ao obter total em uso do cartão: {ex}")



        return 0.0











# =============================================================================



# FATURAS



# =============================================================================



def listar_faturas(cartao_id: str = None, status: str = None, mes: int = None, ano: int = None) -> list:



    query = supabase.table("faturas").select("*, cartoes(nome, bandeira, cor, limite_total, limite_disponivel, dia_fechamento, dia_vencimento, conta_debito_id)")



    if cartao_id:



        query = query.eq("cartao_id", cartao_id)



    if status:



        query = query.eq("status", status)
    if mes is not None:
        query = query.eq("mes", mes)
    if ano is not None:
        query = query.eq("ano", ano)



    resp = query.order("data_vencimento", desc=True).execute()



    return resp.data or []











def obter_fatura_por_id(fatura_id: str) -> dict | None:



    """Busca uma fatura específica pelo seu ID (UUID)."""



    if not fatura_id:



        return None



    try:



        resp = supabase.table("faturas").select("*").eq("id", str(fatura_id)).maybe_single().execute()



        return resp.data if resp else None



    except Exception:



        return None











def obter_fatura_atual(cartao_id: str, mes: int, ano: int) -> dict | None:



    """Busca a fatura do cartão para o mês/ano especificado de forma segura sem erro PGRST116."""



    try:



        resp = (



            supabase.table("faturas")



            .select("*")



            .eq("cartao_id", cartao_id)



            .eq("mes", mes)



            .eq("ano", ano)



            .maybe_single()



            .execute()



        )



        return resp.data



    except Exception:



        resp = (



            supabase.table("faturas")



            .select("*")



            .eq("cartao_id", cartao_id)



            .eq("mes", mes)



            .eq("ano", ano)



            .limit(1)



            .execute()



        )



        return resp.data[0] if (resp and resp.data) else None











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











def liquidar_pagamento_fatura(
    fatura_id: str,
    conta_id: str,
    data_pagamento: Optional[str] = None,
    valor_pago: Optional[float] = None,
) -> dict:
    """
    Executa a baixa em lote e liquidação da fatura do cartão via RPC PostgreSQL:
    1. Vincula despesas órfãs do período à fatura.
    2. Altera status de todas as despesas vinculadas de 'Pendente' para 'Pago'.
    3. Registra débito na conta bancária de origem (tipo 'Transferência', subtipo 'Pagamento de Fatura').
    4. Marca a fatura como 'paga' com data e valor liquidado.
    5. Recalcula saldos das contas e restaura o limite disponível do cartão.
    """
    params = {
        "p_fatura_id": str(fatura_id),
        "p_conta_id": str(conta_id),
        "p_data_pagamento": str(data_pagamento) if data_pagamento else None,
        "p_valor_pago": float(valor_pago) if valor_pago is not None else None,
    }
    resp = supabase.rpc("liquidar_pagamento_fatura", params).execute()
    invalidar_cache("contas")
    invalidar_cache("cartoes")
    invalidar_cache("lancamentos")
    invalidar_cache("potes_resumo")
    return resp.data or {}


def estornar_pagamento_fatura(fatura_id: str) -> dict:
    """
    Estorna o pagamento de uma fatura liquidada:
    1. Remove o lançamento de débito na conta bancária.
    2. Devolve o saldo à conta bancária.
    3. Reabre a fatura ('aberta' ou 'fechada') e limpa metadados de pagamento.
    4. Restaura os lançamentos de crédito futuros para 'Pendente'.
    5. Recalibra o limite utilizado do cartão.
    """
    params = {"p_fatura_id": str(fatura_id)}
    resp = supabase.rpc("estornar_pagamento_fatura", params).execute()
    invalidar_cache("contas")
    invalidar_cache("cartoes")
    invalidar_cache("lancamentos")
    invalidar_cache("potes_resumo")
    return resp.data or {}


def pagar_fatura(fatura_id: str, valor_pago: float, conta_id: Optional[str] = None, data_pagamento: Optional[str] = None):
    """Marca fatura como paga. Se conta_id for fornecida, utiliza o fluxo completo de liquidação."""
    if conta_id:
        return liquidar_pagamento_fatura(fatura_id, conta_id, data_pagamento=data_pagamento, valor_pago=valor_pago)
    return supabase.table("faturas").update({
        "valor_pago": valor_pago,
        "status": "paga",
    }).eq("id", fatura_id).execute()











# =============================================================================



# LANÇAMENTOS



# =============================================================================




def _sanitizar_regra_lancamento(dados: dict) -> None:
    if isinstance(dados, dict) and "regra" in dados and dados["regra"] is not None:
        if dados["regra"] not in ("Essencial", "Estilo de Vida", "Investimento"):
            from core.potes import obter_regra_pote
            dados["regra"] = obter_regra_pote(dados["regra"] or dados.get("pote_id"))

def criar_lancamento(dados: dict):



    """Insere um lançamento. O trigger no banco define o status automático."""



    invalidar_cache('lancamentos')



    user = usuario_atual()



    if user:



        dados.setdefault("user_id", user.id)



        dados.setdefault("perfil_id", user.id)



    _sanitizar_regra_lancamento(dados)
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



        "cartoes(nome,bandeira,cor), subcategorias(nome), faturas!fk_lancamentos_fatura(mes,ano,status)"



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



    try:



        resp = (



            supabase.table("lancamentos")



            .select(



                "*, contas(nome,cor,icone), categorias(nome,cor,icone), "



                "cartoes(nome,bandeira,cor), subcategorias(nome), faturas!fk_lancamentos_fatura(mes,ano,status)"



            )



            .eq("id", lancamento_id)



            .maybe_single()



            .execute()



        )



        return resp.data



    except Exception:



        resp = (



            supabase.table("lancamentos")



            .select(



                "*, contas(nome,cor,icone), categorias(nome,cor,icone), "



                "cartoes(nome,bandeira,cor), subcategorias(nome), faturas!fk_lancamentos_fatura(mes,ano,status)"



            )



            .eq("id", lancamento_id)



            .limit(1)



            .execute()



        )



        return resp.data[0] if (resp and resp.data) else None











def atualizar_lancamento(lancamento_id: str, dados: dict):



    invalidar_cache('lancamentos')



    invalidar_cache('cartoes')
    _sanitizar_regra_lancamento(dados)
    return supabase.table("lancamentos").update(dados).eq("id", str(lancamento_id)).execute()











def deletar_lancamento(lancamento_id: str):



    invalidar_cache('lancamentos')



    return supabase.table("lancamentos").delete().eq("id", lancamento_id).execute()











def importar_lancamentos_csv(lista: list[dict]) -> dict:



    """



    Importação em lote. Usa upsert com external_id para evitar duplicatas.



    Retorna {'inseridos': N, 'ignorados': M, 'erros': [...]}.



    """



    invalidar_cache("lancamentos")



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











def criar_lancamento_recorrente(



    dados: dict,



    modo: str = "unica",



    frequencia: str = "mensal",



    quantidade: int = 1,



    valor_modo: str = "parcelado",



) -> dict:



    """



    Cria lançamentos com regras de recorrência atômicas (RPC).



    Modos: 'unica', 'parcelada', 'repetida', 'fixa'.



    """



    user = usuario_atual()



    if user and "user_id" not in dados:
        dados["user_id"] = user.id
    _sanitizar_regra_lancamento(dados)







    params = {



        "p_dados": dados,



        "p_modo": modo,



        "p_frequencia": frequencia,



        "p_quantidade": quantidade,



        "p_valor_modo": valor_modo,



    }



    resp = supabase.rpc("criar_lancamento_com_recorrencia", params).execute()



    return resp.data or {}











def gerar_recorrentes_pendentes(ate: str = None) -> dict:



    """



    Executa a materialização de lançamentos de fixas pendentes até uma data limite.



    Idempotente: chamada automaticamente ao iniciar o app.



    """



    params = {}



    if ate:



        params["p_ate"] = ate



    resp = supabase.rpc("gerar_lancamentos_recorrentes", params).execute()



    return resp.data or {}











def atualizar_serie(serie_id: str, dados: dict, a_partir_de: str = None) -> dict:
    _sanitizar_regra_lancamento(dados)



    """



    Atualiza lançamentos de uma série. Se a_partir_de for informado,



    atualiza apenas os lançamentos a partir daquela data (ex: 'este e os próximos').



    """



    params = {



        "p_serie_id": serie_id,



        "p_dados": dados,



    }



    if a_partir_de:



        params["p_a_partir_de"] = a_partir_de



    resp = supabase.rpc("atualizar_serie", params).execute()



    return resp.data or {}











def excluir_serie(serie_id: str, a_partir_de: str = None) -> dict:



    """



    Exclui lançamentos de uma série. Se a_partir_de for informado,



    exclui apenas os lançamentos a partir daquela data (ex: 'este e os próximos').



    """



    params = {



        "p_serie_id": serie_id,



    }



    if a_partir_de:



        params["p_a_partir_de"] = a_partir_de



    resp = supabase.rpc("excluir_serie", params).execute()



    return resp.data or {}


def recalcular_totais_faturas(faturas_ids: list[str]) -> dict:
    """
    Recalcula atomicamente o valor_total de uma lista de faturas via RPC no Supabase.
    """
    if not faturas_ids:
        return {"sucesso": True}
    try:
        clean_ids = [str(f) for f in faturas_ids if f]
        resp = supabase.rpc("fn_recalcular_totais_faturas", {"p_faturas_ids": clean_ids}).execute()
        return {"sucesso": True, "data": resp.data}
    except Exception as ex:
        print(f"[Supabase] Erro ao recalcular totais das faturas: {ex}")
        return {"sucesso": False, "erro": str(ex)}


def deslocar_faturas_parcelamento(lancamento_id: str, nova_fatura_id: str, aplicar_cascata: bool = True) -> dict:
    """
    Desloca a fatura do lançamento informado e, opcionalmente, de todas as parcelas
    subsequentes da mesma série em efeito cascata.
    """
    if not lancamento_id or not nova_fatura_id:
        return {"sucesso": False, "erro": "Parâmetros inválidos"}
    try:
        resp = supabase.rpc("fn_deslocar_faturas_parcelamento", {
            "p_lancamento_id": lancamento_id,
            "p_nova_fatura_id": nova_fatura_id,
            "p_aplicar_cascata": aplicar_cascata,
        }).execute()
        return resp.data or {}
    except Exception as ex:
        print(f"[Supabase] Erro ao deslocar faturas parcelamento: {ex}")
        return {"sucesso": False, "erro": str(ex)}


def redimensionar_parcelamento(serie_id: str, novo_total: int, novo_valor_parcela: float = None) -> dict:
    """
    Altera o número total de parcelas de uma compra parcelada (redução segura ou extensão).
    """
    if not serie_id or novo_total < 1:
        return {"sucesso": False, "erro": "Parâmetros inválidos"}
    try:
        params = {
            "p_serie_id": serie_id,
            "p_novo_total": int(novo_total),
        }
        if novo_valor_parcela is not None:
            params["p_novo_valor_parcela"] = float(novo_valor_parcela)
        resp = supabase.rpc("fn_redimensionar_parcelamento", params).execute()
        return resp.data or {}
    except Exception as ex:
        print(f"[Supabase] Erro ao redimensionar parcelamento: {ex}")
        return {"sucesso": False, "erro": str(ex)}


def obter_resumo_serie_parcelamento(serie_id: str) -> dict:
    """
    Retorna o resumo detalhado das parcelas de uma compra parcelada pelo serie_id.
    """
    if not serie_id:
        return {"sucesso": False, "total": 0, "pagas": 0, "parcelas": []}
    try:
        resp = supabase.table("lancamentos") \
            .select("id, parcela_atual, total_parcelas, fatura_id, status, data, valor, descricao, cartao_id") \
            .eq("serie_id", serie_id) \
            .order("parcela_atual", desc=False) \
            .execute()
        parcelas = resp.data or []
        pagas = sum(1 for p in parcelas if p.get("status") == "Pago")
        return {
            "sucesso": True,
            "total": len(parcelas),
            "max_parcela": max((p.get("parcela_atual") or 0) for p in parcelas) if parcelas else 0,
            "pagas": pagas,
            "pendentes": len(parcelas) - pagas,
            "parcelas": parcelas,
        }
    except Exception as ex:
        print(f"[Supabase] Erro ao obter resumo da série: {ex}")
        return {"sucesso": False, "total": 0, "pagas": 0, "parcelas": []}
















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



def obter_dashboard_periodo(data_inicio: str, data_fim: str) -> dict:



    """



    Chama a RPC consolidada 'get_dashboard_periodo' para qualquer intervalo de datas.



    Retorna: {



      overview: {receitas, despesas, saldo, saldo_contas, total_faturas, periodo_inicio, periodo_fim},



      despesas_por_categoria: {total, categorias: [...]},



      receitas_por_categoria: {total, categorias: [...]},



      frequencia_diaria: [...],



      despesas_por_forma: [...]



    }



    """



    params = {



        "p_data_inicio": str(data_inicio),



        "p_data_fim": str(data_fim),



    }



    resp = supabase.rpc("get_dashboard_periodo", params).execute()



    return resp.data or {}











def obter_overview_dashboard(



    mes: int = None,



    ano: int = None,



    data_inicio: str = None,



    data_fim: str = None,



) -> dict:



    """



    Chama a RPC 'get_dashboard_overview' (ou 'get_dashboard_periodo' quando período livre).



    Retorna: {receitas, despesas, saldo, saldo_contas, total_faturas, periodo_*}



    """



    if data_inicio and data_fim:



        pacote = obter_dashboard_periodo(data_inicio, data_fim)



        if isinstance(pacote, dict) and "overview" in pacote:



            return pacote["overview"] or {}



    params: dict = {}



    if mes:



        params["p_mes"] = mes



    if ano:



        params["p_ano"] = ano



    resp = supabase.rpc("get_dashboard_overview", params).execute()



    return resp.data or {}











def obter_despesas_por_categoria(



    mes: int = None,



    ano: int = None,



    data_inicio: str = None,



    data_fim: str = None,



) -> dict:



    """Chama 'get_despesas_por_categoria' (ou via período livre). Retorna {total, categorias: [...]}"""



    if data_inicio and data_fim:



        pacote = obter_dashboard_periodo(data_inicio, data_fim)



        if isinstance(pacote, dict) and "despesas_por_categoria" in pacote:



            return pacote["despesas_por_categoria"] or {"total": 0, "categorias": []}



    params: dict = {}



    if mes:



        params["p_mes"] = mes



    if ano:



        params["p_ano"] = ano



    resp = supabase.rpc("get_despesas_por_categoria", params).execute()



    return resp.data or {"total": 0, "categorias": []}











def obter_receitas_por_categoria(



    mes: int = None,



    ano: int = None,



    data_inicio: str = None,



    data_fim: str = None,



) -> dict:



    """Chama 'get_receitas_por_categoria' (ou via período livre). Retorna {total, categorias: [...]}"""



    if data_inicio and data_fim:



        pacote = obter_dashboard_periodo(data_inicio, data_fim)



        if isinstance(pacote, dict) and "receitas_por_categoria" in pacote:



            return pacote["receitas_por_categoria"] or {"total": 0, "categorias": []}



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











def obter_frequencia_gastos(



    mes: int = None,



    ano: int = None,



    data_inicio: str = None,



    data_fim: str = None,



) -> list:



    """Chama 'get_frequencia_gastos_mes' (ou via período livre). Retorna [{data, dia, despesas, receitas}]"""



    if data_inicio and data_fim:



        pacote = obter_dashboard_periodo(data_inicio, data_fim)



        if isinstance(pacote, dict) and "frequencia_diaria" in pacote:



            return pacote["frequencia_diaria"] or []



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



    """Legado - mantido para nao quebrar dashboard_view.py atual."""



    params: dict = {}



    if data_inicio:



        params["p_data_inicio"] = data_inicio



    if data_fim:



        params["p_data_fim"] = data_fim



    resp = supabase.rpc("get_financial_totals", params).execute()



    return resp.data or {"receitas": 0, "despesas": 0, "saldo": 0}











def obter_resumo_5030(data_inicio: str = None, data_fim: str = None) -> dict:



    """Retorna o resumo da Regra 50/30/20 filtrado por período."""



    params: dict = {}



    if data_inicio:



        params["p_data_inicio"] = str(data_inicio)



    if data_fim:



        params["p_data_fim"] = str(data_fim)



    resp = supabase.rpc("get_regra_50_30_20_summary", params).execute()



    return resp.data or {}











# =============================================================================



# RELATÓRIOS MODULARES & DRILL-DOWN (RPCs Migração 008)



# =============================================================================



def obter_relatorio_lancamentos(



    data_inicio: str,



    data_fim: str,



    filtros: dict | None = None,



    limite: int = 50,



    offset: int = 0,



) -> dict:



    """



    Chama 'get_relatorio_lancamentos'.



    Retorna {totais, por_categoria, por_subcategoria, por_dia, por_forma, lancamentos, total_registros}.



    """



    vazio = {



        "totais": {



            "receitas": 0.0,



            "despesas": 0.0,



            "transferencias": 0.0,



            "saldo": 0.0,



            "total_filtrado": 0.0,



            "pago": 0.0,



            "pendente": 0.0,



            "qtd": 0,



            "media_diaria": 0.0,



        },



        "por_categoria": [],



        "por_subcategoria": [],



        "por_dia": [],



        "por_forma": [],



        "lancamentos": [],



        "total_registros": 0,



    }



    params = {



        "p_data_inicio": str(data_inicio)[:10],



        "p_data_fim": str(data_fim)[:10],



        "p_filtros": filtros or {},



        "p_limite": int(limite),



        "p_offset": int(offset),



    }



    resp = supabase.rpc("get_relatorio_lancamentos", params).execute()



    if isinstance(resp.data, dict):



        return {**vazio, **resp.data}



    return vazio











def obter_lista_contas_resumo(



    data_inicio: str | None = None,



    data_fim: str | None = None,



) -> dict:



    """



    Chama 'get_lista_contas_resumo'.



    Retorna {saldo_total_atual, saldo_total_previsto, entradas_periodo_total, saidas_periodo_total, contas: [...]}.



    """



    vazio = {



        "saldo_total_atual": 0.0,



        "saldo_total_previsto": 0.0,



        "entradas_periodo_total": 0.0,



        "saidas_periodo_total": 0.0,



        "contas": [],



    }



    params: dict = {}



    if data_inicio:



        params["p_data_inicio"] = str(data_inicio)[:10]



    if data_fim:



        params["p_data_fim"] = str(data_fim)[:10]



    resp = supabase.rpc("get_lista_contas_resumo", params).execute()



    if isinstance(resp.data, dict):



        return {**vazio, **resp.data}



    return vazio











def obter_relatorio_conta(



    conta_id: str,



    data_inicio: str,



    data_fim: str,



    filtros: dict | None = None,



    limite: int = 50,



    offset: int = 0,



) -> dict:



    """



    Chama 'get_relatorio_conta'.



    Retorna {conta, saldo_inicial, entradas, saidas, saldo_final, saldo_previsto_fim, evolucao_saldo, por_categoria, lancamentos, total_registros}.



    """



    vazio = {



        "conta": None,



        "saldo_inicial": 0.0,



        "entradas": 0.0,



        "saidas": 0.0,



        "entradas_pendentes": 0.0,



        "saidas_pendentes": 0.0,



        "saldo_final": 0.0,



        "saldo_previsto_fim": 0.0,



        "evolucao_saldo": [],



        "por_categoria": [],



        "lancamentos": [],



        "total_registros": 0,



    }



    params = {



        "p_conta_id": str(conta_id),



        "p_data_inicio": str(data_inicio)[:10],



        "p_data_fim": str(data_fim)[:10],



        "p_filtros": filtros or {},



        "p_limite": int(limite),



        "p_offset": int(offset),



    }



    resp = supabase.rpc("get_relatorio_conta", params).execute()



    if isinstance(resp.data, dict):



        return {**vazio, **resp.data}



    return vazio











def obter_relatorio_cartao(



    cartao_id: str,



    data_inicio: str,



    data_fim: str,



    filtros: dict | None = None,



    limite: int = 50,



    offset: int = 0,



) -> dict:



    """



    Chama 'get_relatorio_cartao'.



    Retorna {cartao, totais, kpis, faturas, por_categoria, lancamentos, total_registros}.



    """



    vazio = {



        "cartao": None,



        "totais": {



            "gasto_periodo": 0.0,



            "total_gasto_periodo": 0.0,



            "qtd_compras": 0,



            "ticket_medio": 0.0,



            "total_parcelado": 0.0,



            "total_avista": 0.0,



            "total_a_vista": 0.0,



        },



        "kpis": {



            "gasto_periodo": 0.0,



            "total_gasto_periodo": 0.0,



            "qtd_compras": 0,



            "ticket_medio": 0.0,



            "total_parcelado": 0.0,



            "total_avista": 0.0,



            "total_a_vista": 0.0,



            "limite_total": 0.0,



            "limite_disponivel": 0.0,



        },



        "faturas": [],



        "fatura_selecionada": {},



        "por_categoria": [],



        "lancamentos": [],



        "total_registros": 0,



    }



    params = {



        "p_cartao_id": str(cartao_id),



        "p_data_inicio": str(data_inicio)[:10],



        "p_data_fim": str(data_fim)[:10],



        "p_filtros": filtros or {},



        "p_limite": int(limite),



        "p_offset": int(offset),



    }



    try:



        resp = supabase.rpc("get_relatorio_cartao", params).execute()



        if isinstance(resp.data, dict) and not resp.data.get("erro"):



            d = {**vazio, **resp.data}



        else:



            d = dict(vazio)



    except Exception as ex:



        print(f"[SupabaseClient] Erro ao chamar get_relatorio_cartao: {ex}")



        d = dict(vazio)







    # 1. Hidratação e garantia de integridade do cartão de crédito



    c_obj = d.get("cartao")



    if not c_obj or not isinstance(c_obj, dict) or float(c_obj.get("limite_total", 0) or 0) == 0:



        c_fallback = obter_cartao(cartao_id)



        if c_fallback:



            d["cartao"] = {**(c_obj or {}), **c_fallback}



            c_obj = d["cartao"]







    tot = d.get("totais") or {}



    kpis = d.get("kpis") or {}



    gasto = float(tot.get("gasto_periodo") or kpis.get("total_gasto_periodo") or tot.get("total_gasto_periodo") or 0)



    tot_parc = float(tot.get("total_parcelado") or kpis.get("total_parcelado") or 0)



    tot_av = float(tot.get("total_avista") or kpis.get("total_a_vista") or tot.get("total_a_vista") or 0)



    qtd = int(tot.get("qtd_compras") or kpis.get("qtd_compras") or len(d.get("lancamentos") or []))







    # 2. Recálculo e sincronização de limites e saldo devedor



    lim_tot_card = float((c_obj or {}).get("limite_total") or kpis.get("limite_total") or 0.0)



    saldo_usado = obter_total_em_uso_cartao(cartao_id)



    usado_final = max(saldo_usado, gasto)



    lim_disp_card = max(0.0, lim_tot_card - usado_final) if lim_tot_card > 0 else 0.0







    consolidado = {



        "gasto_periodo": gasto,



        "total_gasto_periodo": gasto,



        "qtd_compras": qtd,



        "total_parcelado": tot_parc,



        "total_avista": tot_av,



        "total_a_vista": tot_av,



        "limite_total": lim_tot_card,



        "limite_disponivel": lim_disp_card,



        "limite_usado": usado_final,



    }



    d["totais"] = {**tot, **consolidado}



    d["kpis"] = {**kpis, **consolidado}



    if isinstance(d.get("cartao"), dict):



        d["cartao"]["limite_total"] = lim_tot_card



        d["cartao"]["limite_disponivel"] = lim_disp_card



        d["cartao"]["limite_usado"] = usado_final







    return d











# =============================================================================



# POTES FINANCEIROS (6 potes fixos — migração 009)



# =============================================================================



def garantir_potes() -> None:



    """Auto-cura: cria os 6 potes padrão caso o usuário ainda não os possua."""



    supabase.rpc("garantir_potes", {}).execute()











def listar_potes(
    forcar_atualizacao: bool = False,
    mes: int | None = None,
    ano: int | None = None,
) -> list:
    """
    Retorna os 6 potes do usuário ordenados por posição para o mês/ano informado
    (ou mês/ano atual caso omitido). Usa `listar_potes_mes` no Supabase com herança inteligente.
    """
    sub_k = f"{int(ano)}_{int(mes)}" if (mes is not None and ano is not None) else None
    if not forcar_atualizacao:
        cached = obter_cache("potes", subchave=sub_k)
        if cached is not None:
            return list(cached)

    dados: list = []
    try:
        params: dict[str, Any] = {}
        if mes is not None:
            params["p_mes"] = int(mes)
        if ano is not None:
            params["p_ano"] = int(ano)
        resp_m = supabase.rpc("listar_potes_mes", params).execute()
        if isinstance(resp_m.data, list) and len(resp_m.data) == 6:
            dados = resp_m.data
    except Exception:
        dados = []

    if not dados:
        resp = supabase.table("potes").select("*").order("posicao").execute()
        if not resp.data:
            garantir_potes()
            resp = supabase.table("potes").select("*").order("posicao").execute()
        dados = resp.data or []

    salvar_cache("potes", dados, subchave=sub_k, ttl=TTL_CADASTROS_BASE)
    return dados


def salvar_potes(
    itens: list[dict],
    mes: int | None = None,
    ano: int | None = None,
) -> list:
    """
    Atualiza nome/percentual dos 6 potes de forma atômica para o mês/ano específico
    (sem sobrescrever as metas de outros meses).
    itens: [{"id", "nome", "percentual"}]. O banco revalida a soma == 100.
    """
    dados: list = []
    try:
        params: dict[str, Any] = {"p_potes": itens}
        if mes is not None:
            params["p_mes"] = int(mes)
        if ano is not None:
            params["p_ano"] = int(ano)
        resp = supabase.rpc("salvar_potes_mes", params).execute()
        dados = resp.data or []
    except Exception:
        resp = supabase.rpc("salvar_potes", {"p_potes": itens}).execute()
        dados = resp.data or []

    invalidar_cache("potes")
    invalidar_cache("potes_resumo")
    sub_k = f"{int(ano)}_{int(mes)}" if (mes is not None and ano is not None) else None
    salvar_cache("potes", dados, subchave=sub_k, ttl=TTL_CADASTROS_BASE)
    return dados


def obter_config_caixa_livre_mes(
    mes: int | None = None,
    ano: int | None = None,
    forcar_atualizacao: bool = False,
) -> dict:
    """
    Retorna a configuração mensal de retenção do Caixa Livre (Sobra do Período)
    para o mês/ano informado ({mes, ano, pct_investimento, personalizado_no_mes}).
    """
    from datetime import date as _date
    hoje_d = _date.today()
    m = int(mes) if mes is not None else hoje_d.month
    a = int(ano) if ano is not None else hoje_d.year
    sub_k = f"{a}_{m}"

    if not forcar_atualizacao:
        cached = obter_cache("caixa_livre_config", subchave=sub_k)
        if isinstance(cached, dict):
            return dict(cached)

    padrao = {
        "mes": m,
        "ano": a,
        "pct_investimento": 50.0,
        "personalizado_no_mes": False,
        "mes_origem": m,
        "ano_origem": a,
    }
    try:
        resp = supabase.rpc("obter_config_caixa_livre_mes", {"p_mes": m, "p_ano": a}).execute()
        if isinstance(resp.data, dict):
            res = {**padrao, **resp.data}
            salvar_cache("caixa_livre_config", res, subchave=sub_k, ttl=TTL_CADASTROS_BASE)
            return res
    except Exception:
        pass
    return padrao


def salvar_config_caixa_livre_mes(
    mes: int,
    ano: int,
    pct_investimento: float,
) -> dict:
    """
    Salva no Supabase o percentual de retenção (Investimento/Poupança vs Livre)
    do Caixa Livre exclusivamente para o mês/ano informado.
    """
    m = max(1, min(12, int(mes)))
    a = int(ano)
    pct = round(max(0.0, min(100.0, float(pct_investimento))), 1)
    sub_k = f"{a}_{m}"
    res = {
        "mes": m,
        "ano": a,
        "pct_investimento": pct,
        "personalizado_no_mes": True,
        "mes_origem": m,
        "ano_origem": a,
    }
    try:
        resp = supabase.rpc(
            "salvar_config_caixa_livre_mes",
            {"p_mes": m, "p_ano": a, "p_pct_investimento": pct},
        ).execute()
        if isinstance(resp.data, dict):
            res.update(resp.data)
    except Exception:
        pass
    invalidar_cache("caixa_livre_config")
    salvar_cache("caixa_livre_config", res, subchave=sub_k, ttl=TTL_CADASTROS_BASE)
    return res











def ler_renda_referencia() -> float:



    perfil = ler_perfil() or {}



    return float(perfil.get("renda_referencia") or 0)











def salvar_renda_referencia(valor: float):



    return atualizar_perfil({"renda_referencia": valor})











def registrar_distribuicao_receita(lancamento_id: str, itens: list[dict]) -> int:



    """Grava a distribuição (1 linha por pote) de uma receita já inserida."""



    resp = supabase.rpc(



        "registrar_distribuicao_receita",



        {"p_lancamento_id": lancamento_id, "p_itens": itens},



    ).execute()



    return resp.data or 0











def obter_resumo_potes(data_inicio: str, data_fim: str, forcar_atualizacao: bool = False, piso_custos_fixos: float = 1150.00) -> dict:
    """
    Chama 'get_potes_resumo' com cache de curta duração em RAM (120s) para evitar UI blocking.
    Aplica a arquitetura unificada com piso de custos fixos e conexão com Caixa Livre.
    """
    chave_p = f"{data_inicio}_{data_fim}_{float(piso_custos_fixos)}"
    if not forcar_atualizacao:
        cached = obter_cache("potes_resumo", subchave=chave_p)
        if cached is not None:
            return dict(cached)

    padrao = {"renda": 0, "total_gasto": 0, "saldo": 0,
              "percentual_renda_usado": 0, "potes": [],
              "sem_pote": {"qtd": 0, "total": 0}}
    try:
        resp = supabase.rpc(
            "get_potes_resumo",
            {"p_data_inicio": data_inicio, "p_data_fim": data_fim, "p_piso_fixos": float(piso_custos_fixos)},
        ).execute()
        dados = resp.data or padrao
    except Exception:
        try:
            resp = supabase.rpc(
                "get_potes_resumo",
                {"p_data_inicio": data_inicio, "p_data_fim": data_fim},
            ).execute()
            dados = resp.data or padrao
        except Exception:
            dados = padrao

    salvar_cache("potes_resumo", dados, subchave=chave_p, ttl=TTL_RESUMO_POTES)
    return dados


def _tratar_erro_caixinha(ex: Exception) -> str:
    """Retorna mensagem amigável caso a tabela ou RPC ainda não tenham sido migradas no Supabase."""
    err_str = str(ex)
    if "public.caixinhas_teto" in err_str or "PGRST205" in err_str or "schema cache" in err_str:
        return (
            "A tabela 'caixinhas_teto' ainda não foi criada no banco de dados do Supabase. "
            "Por favor, execute o script SQL da migração '016_create_caixinhas_teto.sql' no painel do Supabase (SQL Editor)."
        )
    return err_str


def recalcular_saldo_caixinha(caixinha_id: str) -> dict:
    """
    Recalcula o saldo da caixinha em tempo real:
    Saldo = Valor Provisionado (Injeções/Meta) - Soma das Despesas Vinculadas.
    """
    if not caixinha_id:
        return {}
    cid = str(caixinha_id)
    try:
        resp = supabase.rpc("fn_recalcular_saldo_caixinha", {"p_caixinha_id": cid}).execute()
        if resp and resp.data:
            invalidar_cache("caixinhas")
            return resp.data
    except Exception:
        pass

    # Fallback em Python: calcula diretamente via queries
    try:
        c_resp = supabase.table("caixinhas_teto").select("*").eq("id", cid).maybe_single().execute()
        caixinha = c_resp.data if c_resp else None
        if not caixinha:
            return {}

        meta = float(caixinha.get("valor_meta", 0) or 0)

        # Soma das injeções
        try:
            mov_resp = (
                supabase.table("caixinhas_teto_movimentacoes")
                .select("valor")
                .eq("caixinha_id", cid)
                .eq("tipo", "injecao")
                .execute()
            )
            injecoes = sum(float(m.get("valor", 0) or 0) for m in (mov_resp.data or []))
        except Exception:
            injecoes = 0.0

        # Soma das deduções manuais
        try:
            ded_resp = (
                supabase.table("caixinhas_teto_movimentacoes")
                .select("valor")
                .eq("caixinha_id", cid)
                .eq("tipo", "deducao")
                .execute()
            )
            deducoes = sum(float(m.get("valor", 0) or 0) for m in (ded_resp.data or []))
        except Exception:
            deducoes = 0.0

        valor_provisionado = injecoes

        # Soma das despesas vinculadas a essa caixinha (excluindo o lançamento do próprio provisionamento)
        try:
            lanc_resp = (
                supabase.table("lancamentos")
                .select("valor, subtipo")
                .eq("caixinha_id", cid)
                .eq("tipo", "Despesa")
                .execute()
            )
            itens_lanc = lanc_resp.data or []
            despesas_vinculadas = sum(
                float(it.get("valor", 0) or 0)
                for it in itens_lanc
                if str(it.get("subtipo") or "").lower() != "provisionamento"
            )
        except Exception:
            despesas_vinculadas = 0.0

        saldo_novo = max(0.0, valor_provisionado - deducoes - despesas_vinculadas)
        try:
            supabase.table("caixinhas_teto").update({"saldo_atual": saldo_novo}).eq("id", cid).execute()
        except Exception:
            pass

        invalidar_cache("caixinhas")
        return {
            "sucesso": True,
            "caixinha_id": cid,
            "valor_provisionado": valor_provisionado,
            "total_despesas_vinculadas": despesas_vinculadas,
            "saldo_atual": saldo_novo,
        }
    except Exception as ex:
        print(f"[SupabaseClient] Erro ao recalcular saldo da caixinha: {ex}")
        return {}


def listar_caixinhas(forcar_atualizacao: bool = False) -> list[dict]:
    """Retorna a lista de caixinhas ativas com dados calculados em tempo real."""
    if not forcar_atualizacao:
        cached = obter_cache("caixinhas")
        if cached is not None:
            return list(cached)
    dados = []
    try:
        resp = (
            supabase.table("caixinhas_teto")
            .select("*, categorias(nome, icone, cor), subcategorias(nome), potes(id, nome, percentual, cor), contas(id, nome, cor, icone)")
            .eq("ativo", True)
            .order("criado_em")
            .execute()
        )
        dados = resp.data or []
    except Exception as ex_join:
        # Fallback caso subcategorias/potes ainda não tenham mapeamento de FK
        try:
            resp = (
                supabase.table("caixinhas_teto")
                .select("*, categorias(nome, icone, cor)")
                .eq("ativo", True)
                .order("criado_em")
                .execute()
            )
            dados = resp.data or []
        except Exception as ex:
            msg_erro = _tratar_erro_caixinha(ex)
            print(f"[SupabaseClient] {msg_erro}")
            dados = []

    # Recalcula e sincroniza despesas vinculadas em tempo real para cada caixinha
    if dados:
        try:
            cids = [str(c.get("id")) for c in dados if c.get("id")]
            if cids:
                l_resp = (
                    supabase.table("lancamentos")
                    .select("caixinha_id, valor, subtipo")
                    .in_("caixinha_id", cids)
                    .eq("tipo", "Despesa")
                    .execute()
                )
                despesas_por_caixinha: dict[str, float] = {}
                for l_item in (l_resp.data or []):
                    cid_it = str(l_item.get("caixinha_id"))
                    subt = str(l_item.get("subtipo") or "").lower()
                    if subt != "provisionamento":
                        despesas_por_caixinha[cid_it] = despesas_por_caixinha.get(cid_it, 0.0) + float(l_item.get("valor", 0) or 0)

                # Busca lançamentos de provisionamento das caixinhas
                prov_resp = (
                    supabase.table("lancamentos")
                    .select("id, caixinha_id, valor, subtipo, status, data, tipo, conta_id, destino_id")
                    .in_("caixinha_id", cids)
                    .eq("subtipo", "Provisionamento")
                    .order("criado_em", desc=True)
                    .execute()
                )
                provisao_por_caixinha: dict[str, dict] = {}
                # Ordena por data crescente para priorizar a provisão pendente do ciclo atual/mais próximo
                itens_prov = sorted(prov_resp.data or [], key=lambda x: str(x.get("data") or ""))
                for p_item in itens_prov:
                    cid_p = str(p_item.get("caixinha_id"))
                    if cid_p not in provisao_por_caixinha:
                        provisao_por_caixinha[cid_p] = p_item
                    elif provisao_por_caixinha[cid_p].get("status") != "Pendente" and p_item.get("status") == "Pendente":
                        provisao_por_caixinha[cid_p] = p_item

                # Mapa de contas para enriquecer origem e destino
                try:
                    contas_todas = listar_contas()
                    mapa_contas = {str(cta.get("id")): cta for cta in contas_todas if cta.get("id")}
                except Exception:
                    mapa_contas = {}

                for c in dados:
                    cid_c = str(c.get("id"))
                    meta_val = float(c.get("valor_meta", 0) or 0)
                    saldo_banco = float(c.get("saldo_atual", 0) if c.get("saldo_atual") is not None else meta_val)
                    gasto_vinculado = despesas_por_caixinha.get(cid_c, 0.0)
                    c["total_despesas_vinculadas"] = gasto_vinculado

                    # O saldo atual é mantido e auditado em tempo real pelos triggers no banco
                    c["saldo_atual"] = saldo_banco
                    c["total_gasto"] = gasto_vinculado

                    # Metadados de contas
                    if not c.get("contas") and c.get("conta_id"):
                        c["contas"] = mapa_contas.get(str(c.get("conta_id")))
                    if c.get("conta_destino_id"):
                        c["conta_destino"] = mapa_contas.get(str(c.get("conta_destino_id")))

                    # Metadados de provisão
                    prov_info = provisao_por_caixinha.get(cid_c)
                    if prov_info:
                        c["tem_provisao"] = True
                        c["provisao_id"] = str(prov_info.get("id"))
                        c["provisao_status"] = prov_info.get("status")
                        c["provisao_data"] = prov_info.get("data")
                        c["provisao_tipo"] = prov_info.get("tipo")
                        c["provisao_valor"] = float(prov_info.get("valor", 0) or 0)
                        c["eh_provisao_pendente"] = (prov_info.get("status") == "Pendente")
                    else:
                        c["tem_provisao"] = False
                        c["eh_provisao_pendente"] = False
        except Exception as ex_calc:
            print(f"[SupabaseClient] Aviso ao calcular despesas vinculadas das caixinhas: {ex_calc}")

    salvar_cache("caixinhas", dados, ttl=TTL_CADASTROS_BASE)
    return dados


def obter_caixinha(caixinha_id: str) -> dict | None:
    """Busca uma caixinha específica pelo ID com seus vínculos."""
    if not caixinha_id:
        return None
    try:
        resp = (
            supabase.table("caixinhas_teto")
            .select("*, categorias(nome, icone, cor), subcategorias(nome), potes(id, nome, percentual, cor), contas(id, nome, cor, icone)")
            .eq("id", str(caixinha_id))
            .maybe_single()
            .execute()
        )
        if resp and resp.data:
            return resp.data
    except Exception:
        try:
            resp = (
                supabase.table("caixinhas_teto")
                .select("*, categorias(nome, icone, cor)")
                .eq("id", str(caixinha_id))
                .maybe_single()
                .execute()
            )
            if resp and resp.data:
                return resp.data
        except Exception:
            pass
    for c in listar_caixinhas():
        if str(c.get("id")) == str(caixinha_id):
            return c
    return None


def criar_caixinha(dados: dict) -> dict:
    """
    Cria uma nova caixinha de teto e gera automaticamente o agendamento da provisão PENDENTE:
    - A caixinha nasce com saldo_atual = 0.00.
    - É gerado um lançamento (Despesa ou Transferência) com status 'Pendente' para a data_provisao definida (ex: dia 5).
    - Quando o usuário pagar a provisão (na lista de lançamentos ou no card), o cofrinho enche automaticamente com o valor da meta!
    """
    from datetime import date
    payload = dict(dados)
    user = usuario_atual()
    if user:
        payload["user_id"] = user.id

    # A caixinha nasce com saldo_atual = 0.00 (esperando pagamento da provisão)
    payload["saldo_atual"] = 0.00
    if "conta_id" in payload and not payload["conta_id"]:
        payload["conta_id"] = None
    if "conta_destino_id" in payload and not payload["conta_destino_id"]:
        payload["conta_destino_id"] = None

    try:
        resp = supabase.table("caixinhas_teto").insert(payload).execute()
    except Exception as ex_ins:
        msg_erro = _tratar_erro_caixinha(ex_ins)
        raise RuntimeError(msg_erro) from ex_ins

    nova_caixinha = resp.data[0] if resp and resp.data else {}
    cid = nova_caixinha.get("id")

    # Gera automaticamente a provisão PENDENTE para a data definida pelo usuário (ex: dia 5)
    if cid and payload.get("conta_id"):
        _sincronizar_lancamento_provisao(cid, payload)

    invalidar_cache("caixinhas")
    invalidar_cache("dashboard")
    return nova_caixinha


def _sincronizar_lancamento_provisao(caixinha_id: str, payload: dict) -> None:
    """
    Sincroniza o lançamento de provisionamento PENDENTE da caixinha em 'lancamentos'.
    - Garante que a provisão exista e entre imediatamente em Despesas Pendentes do mês selecionado.
    - Se já existir lançamento com subtipo='Provisionamento' e status='Pendente', atualiza com os novos dados.
    - Se não existir pendente nem pago, insere um novo lançamento com status='Pendente'.
    """
    from datetime import date
    try:
        cid = str(caixinha_id)
        conta_origem = payload.get("conta_id")
        if not conta_origem:
            return

        meta_val = float(payload.get("valor_meta", 0) or 0)
        dt_prov = str(payload.get("data_provisao") or date.today().isoformat())
        nome_cx = payload.get("nome", "Caixinha")
        pote_id = payload.get("pote_id") or None
        cat_id = payload.get("categoria_id") or None
        subcat_id = payload.get("subcategoria_id") or None
        tipo_prov = payload.get("tipo_provisao") or "despesa"
        conta_dest = payload.get("conta_destino_id") or None

        user = usuario_atual()
        user_id = user.id if user else payload.get("user_id")

        eh_transf = bool(tipo_prov == "transferencia" and conta_dest and str(conta_dest) != str(conta_origem))

        dados_base = {
            "valor": meta_val,
            "data": dt_prov,
            "subtipo": "Provisionamento",
            "pote_id": pote_id,
            "conta_id": str(conta_origem),
        }

        if eh_transf:
            dados_base.update({
                "tipo": "Transferência",
                "forma_movimentacao": "Transferência",
                "destino_id": str(conta_dest),
                "descricao": f"Transferência Provisão · {nome_cx}",
            })
        else:
            dados_base.update({
                "tipo": "Despesa",
                "forma_movimentacao": "Débito",
                "categoria_id": cat_id,
                "subcategoria_id": subcat_id,
                "descricao": f"Provisão Caixinha · {nome_cx}",
            })

        # Verifica se já existe lançamento de provisionamento para esta caixinha
        resp = supabase.table("lancamentos") \
            .select("id, status, tipo") \
            .eq("caixinha_id", cid) \
            .ilike("subtipo", "%provisionamento%") \
            .execute()
        existentes = resp.data or []

        pendente = next((l for l in existentes if l.get("status") == "Pendente"), None)
        if pendente:
            supabase.table("lancamentos").update(dados_base).eq("id", pendente["id"]).execute()
        elif not any(l.get("status") == "Pago" for l in existentes):
            novo_lanc = dict(dados_base)
            novo_lanc.update({
                "caixinha_id": cid,
                "status": "Pendente",
                "user_id": user_id,
                "perfil_id": user_id,
            })
            supabase.table("lancamentos").insert(novo_lanc).execute()

        invalidar_cache("lancamentos")
        invalidar_cache("contas")
        invalidar_cache("dashboard")
    except Exception as ex_sync:
        print(f"[SupabaseClient] Aviso ao sincronizar provisão da caixinha: {ex_sync}")


def atualizar_caixinha(caixinha_id: str, dados: dict) -> dict:
    """Atualiza dados de uma caixinha existente e sincroniza a provisão pendente."""
    payload = dict(dados)
    payload.pop("id", None)
    payload.pop("user_id", None)

    # Se houve alteração de saldo manual na edição, registra a movimentação de ajuste
    novo_saldo = payload.get("saldo_atual")
    if novo_saldo is not None:
        try:
            c_ant = obter_caixinha(caixinha_id)
            if c_ant:
                ant_saldo = float(c_ant.get("saldo_atual", 0) or 0)
                diff = float(novo_saldo) - ant_saldo
                if abs(diff) > 0.001:
                    user = usuario_atual()
                    from datetime import date
                    tipo_mov = "injecao" if diff > 0 else "deducao"
                    supabase.table("caixinhas_teto_movimentacoes").insert({
                        "caixinha_id": str(caixinha_id),
                        "user_id": user.id if user else None,
                        "tipo": tipo_mov,
                        "valor": abs(diff),
                        "saldo_anterior": ant_saldo,
                        "saldo_posterior": float(novo_saldo),
                        "descricao": "Ajuste manual de saldo",
                        "data": str(date.today()),
                    }).execute()
        except Exception as ex_mov:
            print(f"[SupabaseClient] Aviso ao registrar ajuste de saldo: {ex_mov}")

    try:
        resp = supabase.table("caixinhas_teto").update(payload).eq("id", str(caixinha_id)).execute()
    except Exception as ex_upd:
        msg_erro = _tratar_erro_caixinha(ex_upd)
        raise RuntimeError(msg_erro) from ex_upd

    # Sincroniza o lançamento de provisionamento pendente (data, valor, conta, etc.)
    _sincronizar_lancamento_provisao(caixinha_id, payload)

    invalidar_cache("caixinhas")
    invalidar_cache("dashboard")
    return resp.data[0] if resp and resp.data else {}


def pagar_provisao_caixinha(caixinha_id: str) -> dict:
    """
    Efetiva o pagamento da provisão da caixinha:
    Atualiza o lançamento de provisionamento pendente para 'Pago'.
    O trigger no banco de dados automaticamente injeta o saldo e enche o cofrinho!
    """
    cid = str(caixinha_id)
    try:
        # Busca o lançamento de provisionamento pendente
        l_resp = (
            supabase.table("lancamentos")
            .select("id, valor, data, conta_id, tipo, destino_id")
            .eq("caixinha_id", cid)
            .eq("subtipo", "Provisionamento")
            .eq("status", "Pendente")
            .order("criado_em", desc=True)
            .limit(1)
            .execute()
        )
        lanc = l_resp.data[0] if l_resp and l_resp.data else None
        if lanc:
            lid = lanc["id"]
            supabase.table("lancamentos").update({"status": "Pago"}).eq("id", lid).execute()
            recalcular_saldo_caixinha(cid)
            invalidar_cache("caixinhas")
            invalidar_cache("lancamentos")
            invalidar_cache("contas")
            return {"sucesso": True, "lancamento_id": lid, "valor": lanc.get("valor")}
        else:
            # Fallback: se não houver lançamento pendente, injeta o valor teto diretamente
            c = obter_caixinha(cid)
            if c:
                val = float(c.get("valor_meta", 0) or 0)
                cta = c.get("conta_id")
                return injetar_saldo_caixinha(
                    caixinha_id=cid,
                    valor=val,
                    descricao=f"Provisão Caixinha · {c.get('nome')}",
                    conta_id=cta,
                    gerar_despesa=True,
                )
            return {"erro": "Caixinha não encontrada"}
    except Exception as ex:
        msg_erro = _tratar_erro_caixinha(ex)
        raise RuntimeError(msg_erro) from ex


def deletar_caixinha(caixinha_id: str) -> bool:
    """Inativa uma caixinha (soft delete) e remove provisões pendentes não pagas."""
    try:
        resp = supabase.table("caixinhas_teto").update({"ativo": False}).eq("id", str(caixinha_id)).execute()
        try:
            supabase.table("lancamentos") \
                .delete() \
                .eq("caixinha_id", str(caixinha_id)) \
                .eq("status", "Pendente") \
                .ilike("subtipo", "%provisionamento%") \
                .execute()
            invalidar_cache("lancamentos")
        except Exception:
            pass
    except Exception as ex_del:
        msg_erro = _tratar_erro_caixinha(ex_del)
        raise RuntimeError(msg_erro) from ex_del

    invalidar_cache("caixinhas")
    invalidar_cache("dashboard")
    return bool(resp and resp.data)


def injetar_saldo_caixinha(
    caixinha_id: str,
    valor: float,
    descricao: str = "",
    conta_id: str | None = None,
    data_aporte: str | None = None,
    gerar_despesa: bool = True
) -> dict:
    """
    Aumenta o saldo provisionado da caixinha (aporte).
    Se conta_id for fornecido e gerar_despesa=True, registra o provisionamento
    como Despesa com status 'Pendente' (reserva de capital / previsão de gastos)
    vinculada ao Pote correspondente da caixinha, sem debitar o saldo real da conta imediatamente.
    """
    v = float(valor)
    if v <= 0:
        return {"erro": "Valor deve ser maior que zero"}

    from datetime import date
    dt_final = str(data_aporte or date.today().isoformat())

    c = obter_caixinha(caixinha_id)
    pote_id_alvo = c.get("pote_id") if c else None
    conta_id_alvo = conta_id or (c.get("conta_id") if c else None)
    cat_id_alvo = c.get("categoria_id") if c else None
    subcat_id_alvo = c.get("subcategoria_id") if c else None
    nome_caixinha = c.get("nome", "Caixinha") if c else "Caixinha"

    resultado = {}
    try:
        resp = supabase.rpc("injetar_saldo_caixinha", {
            "p_caixinha_id": str(caixinha_id),
            "p_valor": v,
            "p_descricao": str(descricao or "Aporte de saldo"),
        }).execute()
        resultado = resp.data or {}
    except Exception:
        # Fallback se a RPC ainda não estiver instalada no Supabase
        if c:
            ant = float(c.get("saldo_atual", 0) or 0)
            novo = ant + v
            atualizar_caixinha(caixinha_id, {"saldo_atual": novo})
            try:
                user = usuario_atual()
                supabase.table("caixinhas_teto_movimentacoes").insert({
                    "caixinha_id": str(caixinha_id),
                    "user_id": user.id if user else None,
                    "tipo": "injecao",
                    "valor": v,
                    "saldo_anterior": ant,
                    "saldo_posterior": novo,
                    "descricao": descricao or "Aporte de saldo",
                    "data": dt_final,
                }).execute()
            except Exception:
                pass
            resultado = {"sucesso": True, "saldo_anterior": ant, "saldo_atual": novo, "valor_injetado": v}
        else:
            return {"erro": "Caixinha não encontrada"}

    # Registra despesa pendente de provisionamento (reserva de capital / previsão sem abater saldo real)
    if gerar_despesa and v > 0:
        try:
            user = usuario_atual()
            dados_despesa = {
                "tipo": "Despesa",
                "subtipo": "Provisionamento",
                "forma_movimentacao": "Débito",
                "valor": v,
                "data": dt_final,
                "status": "Pendente",
                "descricao": f"Provisão Caixinha · {nome_caixinha}",
                "caixinha_id": str(caixinha_id),
                "conta_id": conta_id_alvo or None,
                "pote_id": pote_id_alvo or None,
                "categoria_id": cat_id_alvo or None,
                "subcategoria_id": subcat_id_alvo or None,
            }
            if user:
                dados_despesa["user_id"] = user.id
                dados_despesa["perfil_id"] = user.id
            supabase.table("lancamentos").insert(dados_despesa).execute()
            invalidar_cache("lancamentos")
            invalidar_cache("contas")
            invalidar_cache("potes_resumo")
        except Exception as ex_lanc:
            print(f"[SupabaseClient] Erro ao registrar despesa do aporte: {ex_lanc}")

    recalcular_saldo_caixinha(caixinha_id)
    invalidar_cache("caixinhas")
    invalidar_cache("dashboard")
    return resultado


def deduzir_saldo_caixinha(caixinha_id: str, valor: float, descricao: str = "") -> dict:
    """Subtrai valor do saldo da caixinha (gasto/dedução). Não debita o banco novamente."""
    try:
        resp = supabase.rpc("deduzir_saldo_caixinha", {
            "p_caixinha_id": str(caixinha_id),
            "p_valor": float(valor),
            "p_descricao": str(descricao or "Gasto registrado"),
        }).execute()
        recalcular_saldo_caixinha(caixinha_id)
        invalidar_cache("caixinhas")
        return resp.data or {}
    except Exception:
        # Fallback se a RPC ainda não estiver instalada no Supabase
        c = obter_caixinha(caixinha_id)
        if c:
            from datetime import date
            ant = float(c.get("saldo_atual", 0) or 0)
            novo = max(0.0, ant - float(valor))
            atualizar_caixinha(caixinha_id, {"saldo_atual": novo})
            try:
                user = usuario_atual()
                supabase.table("caixinhas_teto_movimentacoes").insert({
                    "caixinha_id": str(caixinha_id),
                    "user_id": user.id if user else None,
                    "tipo": "deducao",
                    "valor": float(valor),
                    "saldo_anterior": ant,
                    "saldo_posterior": novo,
                    "descricao": descricao or "Gasto registrado",
                    "data": str(date.today()),
                }).execute()
            except Exception:
                pass
            invalidar_cache("caixinhas")
            return {"sucesso": True, "saldo_anterior": ant, "saldo_atual": novo, "valor_deduzido": valor}
        return {"erro": "Caixinha não encontrada"}


def listar_caixinhas_opcoes() -> list[dict]:
    """
    Retorna opções simplificadas das caixinhas para formulários de lançamentos:
    [{'id': str, 'nome': str, 'saldo_atual': float, 'cor': str, 'valor_meta': float}]
    """
    itens = listar_caixinhas()
    return [
        {
            "id": str(c.get("id")),
            "nome": c.get("nome", "Caixinha"),
            "saldo_atual": float(c.get("saldo_atual", 0) or 0),
            "cor": c.get("cor", "#10B981"),
            "valor_meta": float(c.get("valor_meta", 0) or 0),
            "pote_id": c.get("pote_id"),
            "conta_id": c.get("conta_id"),
            "categoria_id": c.get("categoria_id"),
            "subcategoria_id": c.get("subcategoria_id"),
        }
        for c in itens
    ]


def obter_resumo_caixinhas(forcar_atualizacao: bool = False) -> dict:
    """
    Calcula os KPIs consolidados de todas as caixinhas ativas com dados em tempo real:
    - total_meta: soma dos tetos alocados
    - total_saldo: soma do saldo restante disponível (Provisionado - Despesas Vinculadas)
    - total_gasto: total consumido por despesas vinculadas
    - percentual_restante: % do valor inicial ainda disponível
    - ritmo_diario_total: média de gastos diários seguros até a data alvo
    """
    itens = listar_caixinhas(forcar_atualizacao=forcar_atualizacao)
    from datetime import date
    hoje = date.today()
    tot_meta = sum(float(c.get("valor_meta", 0) or 0) for c in itens)
    tot_saldo = sum(float(c.get("saldo_atual", 0) or 0) for c in itens)
    tot_gasto = sum(float(c.get("total_gasto", 0) or 0) for c in itens)
    pct_rest = (tot_saldo / tot_meta * 100) if tot_meta > 0 else 0.0

    ritmo_total = 0.0
    for c in itens:
        s = float(c.get("saldo_atual", 0) or 0)
        dt_str = c.get("data_alvo")
        if dt_str and s > 0:
            try:
                from datetime import datetime
                d_alvo = datetime.strptime(str(dt_str)[:10], "%Y-%m-%d").date()
                dias = max(1, (d_alvo - hoje).days + 1)
                ritmo_total += (s / dias)
            except Exception:
                pass

    return {
        "total_meta": tot_meta,
        "total_saldo": tot_saldo,
        "total_gasto": tot_gasto,
        "percentual_restante": pct_rest,
        "qtd_caixinhas": len(itens),
        "ritmo_diario_total": ritmo_total,
        "caixinhas": itens,
    }



# =============================================================================
# CALENDÁRIO FINANCEIRO INTERATIVO (MAPA DE CALOR + ROSCA + FATURAS)
# =============================================================================
def obter_saldo_consolidado_contas(contas_lista: list | None = None) -> float:
    """
    Retorna a soma consolidada do saldo atual das contas bancárias ativas do usuário
    (posição real de liquidez/estoque em caixa).
    """
    if contas_lista is None:
        try:
            contas_lista = listar_contas()
        except Exception:
            contas_lista = []
    total = 0.0
    for c in (contas_lista or []):
        try:
            total += float(c.get("saldo_atual", c.get("saldo_inicial", 0.0)) or 0.0)
        except Exception:
            pass
    return round(total, 2)


def recalcular_modo_calendario(
    pacote: dict,
    modo: str,
    saldo_contas: float | None = None,
) -> dict:
    """
    Recalcula instantaneamente em O(N) client-side o Calendário Financeiro e a Proteção de Fluxo:
    - 'isolado': Começa do R$ 0,00 no primeiro dia do filtro (resultado operacional puro).
    - 'com_saldo': Começa do saldo real consolidado das contas bancárias (posição real de caixa).
    """
    if not isinstance(pacote, dict) or "dias" not in pacote:
        return pacote

    m_modo = "com_saldo" if modo == "com_saldo" else "isolado"
    s_contas = float(
        saldo_contas
        if saldo_contas is not None
        else (pacote.get("saldo_contas_consolidado") or 0.0)
    )
    s_base = s_contas if m_modo == "com_saldo" else 0.0

    d_ini_str = str(pacote.get("filtro_inicio") or "")[:10]
    d_fim_str = str(pacote.get("filtro_fim") or "")[:10]
    grid_ini_s = str(pacote.get("grid_inicio") or d_ini_str)[:10]
    grid_fim_s = str(pacote.get("grid_fim") or d_fim_str)[:10]
    dias_lista = pacote.get("dias") or []

    pacote["modo_saldo"] = m_modo
    pacote["saldo_base_inicial"] = s_base
    pacote["saldo_contas_consolidado"] = s_contas
    pacote["acumulados_por_dia"] = _calcular_acumulados_calendario(
        dias_lista, d_ini_str, d_fim_str, grid_ini_s, grid_fim_s, saldo_base_inicial=s_base
    )
    pacote["protecao_fluxo"] = calcular_protecao_fluxo_caixa(
        dias_lista, pacote["acumulados_por_dia"], d_ini_str, d_fim_str
    )
    if isinstance(pacote.get("kpis"), dict):
        pacote["kpis"]["modo_saldo"] = m_modo
        pacote["kpis"]["saldo_base_inicial"] = s_base
        pacote["kpis"]["saldo_contas_consolidado"] = s_contas
        res_m = float(pacote["kpis"].get("resultado_mes", 0.0) or 0.0)
        pacote["kpis"]["saldo_projetado_com_contas"] = round(s_contas + res_m, 2)

    return pacote


def _calcular_acumulados_calendario(
    dias_lista: list[dict],
    d_ini_str: str,
    d_fim_str: str,
    grid_ini_str: str,
    grid_fim_str: str,
    saldo_base_inicial: float = 0.0,
) -> dict[str, dict]:
    """
    Pré-calcula em O(N) a soma contínua acumulada (Running Sum) de receitas,
    despesas em conta, despesas no cartão e saldo líquido desde o primeiro dia
    do filtro ativo (`d_ini_str`) até cada data da grade.
    Garante performance instantânea (O(1)) no Hover/Tooltip sem recalcular nada no movimento do mouse.
    """
    from datetime import date as _date, timedelta as _td

    mapa_por_data: dict[str, dict] = {}
    for d_it in (dias_lista or []):
        dt_k = str(d_it.get("data") or "")[:10]
        if dt_k:
            mapa_por_data[dt_k] = d_it

    try:
        dt_ini_f = _date.fromisoformat(d_ini_str[:10])
        dt_fim_f = _date.fromisoformat(d_fim_str[:10])
        dt_grid_i = _date.fromisoformat(grid_ini_str[:10])
        dt_grid_f = _date.fromisoformat(grid_fim_str[:10])
    except Exception:
        return {}

    dt_start = min(dt_ini_f, dt_grid_i)
    dt_end = max(dt_fim_f, dt_grid_f)

    acumulados: dict[str, dict] = {}
    rec_acum = 0.0
    desp_cta_acum = 0.0
    desp_crt_acum = 0.0
    desp_tot_acum = 0.0
    qtd_acum = 0

    cur = dt_start
    while cur <= dt_end:
        iso_c = cur.isoformat()
        info_c = mapa_por_data.get(iso_c) or {}
        r_d = float(info_c.get("total_receitas", 0) or 0)
        sc_d = float(info_c.get("despesas_conta", 0) or 0)
        sr_d = float(info_c.get("despesas_cartao", 0) or 0)
        st_d = float(info_c.get("total_despesas", sc_d + sr_d) or 0)
        q_d = int(info_c.get("qtd_lancamentos", 0) or 0)

        if dt_ini_f <= cur <= dt_fim_f:
            rec_acum += r_d
            desp_cta_acum += sc_d
            desp_crt_acum += sr_d
            desp_tot_acum += st_d
            qtd_acum += q_d
            saldo_acum_calc = round(saldo_base_inicial + rec_acum - desp_tot_acum, 2)
            acum_item = {
                "data_inicio_filtro": d_ini_str[:10],
                "data_ate": iso_c,
                "no_periodo_filtro": True,
                "dias_corridos": (cur - dt_ini_f).days + 1,
                "receitas_acum": round(rec_acum, 2),
                "despesas_conta_acum": round(desp_cta_acum, 2),
                "despesas_cartao_acum": round(desp_crt_acum, 2),
                "despesas_total_acum": round(desp_tot_acum, 2),
                "saldo_acum": saldo_acum_calc,
                "saldo_base_inicial": round(saldo_base_inicial, 2),
                "modo_saldo": "com_saldo" if abs(saldo_base_inicial) > 0.001 else "isolado",
                "qtd_lancamentos_acum": qtd_acum,
            }
        elif cur < dt_ini_f:
            acum_item = {
                "data_inicio_filtro": d_ini_str[:10],
                "data_ate": iso_c,
                "no_periodo_filtro": False,
                "dias_corridos": 0,
                "receitas_acum": round(r_d, 2),
                "despesas_conta_acum": round(sc_d, 2),
                "despesas_cartao_acum": round(sr_d, 2),
                "despesas_total_acum": round(st_d, 2),
                "saldo_acum": round(r_d - st_d, 2),
                "qtd_lancamentos_acum": q_d,
            }
        else:
            # Data após o fim do filtro mantém o acumulado final fechado do período
            saldo_acum_calc = round(saldo_base_inicial + rec_acum - desp_tot_acum, 2)
            acum_item = {
                "data_inicio_filtro": d_ini_str[:10],
                "data_ate": iso_c,
                "no_periodo_filtro": False,
                "dias_corridos": (dt_fim_f - dt_ini_f).days + 1,
                "receitas_acum": round(rec_acum, 2),
                "despesas_conta_acum": round(desp_cta_acum, 2),
                "despesas_cartao_acum": round(desp_crt_acum, 2),
                "despesas_total_acum": round(desp_tot_acum, 2),
                "saldo_acum": saldo_acum_calc,
                "saldo_base_inicial": round(saldo_base_inicial, 2),
                "modo_saldo": "com_saldo" if abs(saldo_base_inicial) > 0.001 else "isolado",
                "qtd_lancamentos_acum": qtd_acum,
            }

        acumulados[iso_c] = acum_item
        if iso_c in mapa_por_data:
            mapa_por_data[iso_c]["acumulado"] = acum_item

        cur += _td(days=1)

    return acumulados


def calcular_protecao_fluxo_caixa(
    dias_lista: list[dict],
    acumulados_por_dia: dict[str, dict],
    d_ini_str: str,
    d_fim_str: str,
    data_ref_str: str | None = None,
) -> dict:
    """
    Calcula em O(N) a Inteligência de Proteção de Fluxo de Caixa (Contra a "Sobra Falsa"):
    - Teto Seguro de Gasto (Baseado no Pior Dia / Gargalo entre a data de referência e o fim do período).
    - Sobra Falsa Travada (Receitas que só entram depois do gargalo e não podem ser gastas antes).
    - Janelas de Sobrevivência entre entradas de receita (dias de pagamento).
    - Anota em cada dia de `dias_lista` e `acumulados_por_dia`:
      `teto_seguro_apos_dia`, `menor_saldo_apos_dia`, `data_gargalo_apos_dia`,
      `eh_gargalo_principal`, `eh_gargalo_janela`, `eh_dia_negativo`.
    """
    from datetime import date as _date, timedelta as _td

    vazio_prot = {
        "sobra_projetada": 0.0,
        "menor_saldo_futuro": 0.0,
        "data_gargalo": None,
        "data_inicio_gargalo": None,
        "teto_seguro_gasto": 0.0,
        "sobra_falsa_travada": 0.0,
        "tem_armadilha_fluxo": False,
        "fica_negativo_no_meio": False,
        "proxima_entrada_data": None,
        "proxima_entrada_valor": 0.0,
        "teto_ate_proxima_entrada": 0.0,
        "data_referencia": d_ini_str[:10] if d_ini_str else "",
        "janelas_sobrevivencia": [],
        "dias_criticos": [],
    }

    try:
        dt_ini = _date.fromisoformat(str(d_ini_str)[:10])
        dt_fim = _date.fromisoformat(str(d_fim_str)[:10])
        if dt_fim < dt_ini:
            dt_ini, dt_fim = dt_fim, dt_ini
    except Exception:
        return vazio_prot

    hoje = _date.today()
    if data_ref_str:
        try:
            dt_ref = _date.fromisoformat(str(data_ref_str)[:10])
        except Exception:
            dt_ref = hoje if (dt_ini <= hoje <= dt_fim) else dt_ini
    else:
        dt_ref = hoje if (dt_ini <= hoje <= dt_fim) else dt_ini

    if dt_ref < dt_ini or dt_ref > dt_fim:
        dt_ref = dt_ini

    mapa_dias: dict[str, dict] = {}
    for d_it in (dias_lista or []):
        dt_k = str(d_it.get("data") or "")[:10]
        if dt_k:
            mapa_dias[dt_k] = d_it
            d_it["eh_gargalo_principal"] = False
            d_it["eh_gargalo_janela"] = False
            d_it["eh_dia_negativo"] = False

    # Constrói série diária ordenada no intervalo [dt_ini, dt_fim]
    serie: list[dict] = []
    cur = dt_ini
    rec_tot = 0.0
    desp_tot = 0.0
    primeiro_mov_dt: _date | None = None

    while cur <= dt_fim:
        iso_c = cur.isoformat()
        d_info = mapa_dias.get(iso_c) or {}
        ac_info = (acumulados_por_dia or {}).get(iso_c) or {}

        r_d = float(d_info.get("total_receitas", 0) or 0)
        sc_d = float(d_info.get("despesas_conta", 0) or 0)
        sr_d = float(d_info.get("despesas_cartao", 0) or 0)
        s_d = float(d_info.get("total_despesas", sc_d + sr_d) or 0)

        rec_tot += r_d
        desp_tot += s_d
        saldo_c = float(ac_info.get("saldo_acum", round(rec_tot - desp_tot, 2)))

        if (r_d > 0.005 or s_d > 0.005) and primeiro_mov_dt is None:
            primeiro_mov_dt = cur

        serie.append({
            "date": cur,
            "iso": iso_c,
            "receita": round(r_d, 2),
            "despesa": round(s_d, 2),
            "saldo_acum": round(saldo_c, 2),
        })
        cur += _td(days=1)

    if not serie:
        return vazio_prot

    sobra_projetada = round(serie[-1]["saldo_acum"], 2)

    # Passo reverso O(N): para cada dia d, encontra o menor saldo acumulado em [d, dt_fim].
    # Em caso de empate de saldo mínimo (vale plano entre uma saída e a próxima receita),
    # prioriza o último dia do vale imediatamente anterior a uma entrada (ex: dia 29 antes do dia 30).
    n_dias = len(serie)
    min_val_running = float("inf")
    min_iso_running = serie[-1]["iso"]

    for idx in range(n_dias - 1, -1, -1):
        item = serie[idx]
        s_val = item["saldo_acum"]
        prox_tem_rec = (idx + 1 < n_dias and serie[idx + 1]["receita"] > 0.005)

        if s_val < min_val_running - 0.005:
            min_val_running = s_val
            min_iso_running = item["iso"]
        elif abs(s_val - min_val_running) <= 0.005:
            if prox_tem_rec:
                min_iso_running = item["iso"]

        teto_apos = round(max(0.0, min_val_running), 2)
        menor_apos = round(min_val_running, 2)
        item["menor_saldo_apos_dia"] = menor_apos
        item["teto_seguro_apos_dia"] = teto_apos
        item["data_gargalo_apos_dia"] = min_iso_running

        iso_k = item["iso"]
        if iso_k in (acumulados_por_dia or {}):
            acumulados_por_dia[iso_k]["menor_saldo_apos_dia"] = menor_apos
            acumulados_por_dia[iso_k]["teto_seguro_apos_dia"] = teto_apos
            acumulados_por_dia[iso_k]["data_gargalo_apos_dia"] = min_iso_running
            acumulados_por_dia[iso_k]["eh_dia_negativo"] = bool(s_val < -0.005)
        if iso_k in mapa_dias:
            mapa_dias[iso_k]["menor_saldo_apos_dia"] = menor_apos
            mapa_dias[iso_k]["teto_seguro_apos_dia"] = teto_apos
            mapa_dias[iso_k]["data_gargalo_apos_dia"] = min_iso_running
            mapa_dias[iso_k]["eh_dia_negativo"] = bool(s_val < -0.005)

    # Determina o início efetivo da análise de gargalo para evitar falso zero
    # em dias vazios no início do mês antes do primeiro lançamento existir.
    if primeiro_mov_dt is None:
        return {
            **vazio_prot,
            "sobra_projetada": sobra_projetada,
            "data_referencia": dt_ref.isoformat(),
        }

    dt_inicio_analise = max(dt_ref, primeiro_mov_dt)
    serie_analise = [x for x in serie if x["date"] >= dt_inicio_analise]
    if not serie_analise:
        serie_analise = serie

    # Menor saldo futuro no intervalo [dt_inicio_analise, dt_fim]
    menor_saldo_futuro = min(x["saldo_acum"] for x in serie_analise)
    menor_saldo_futuro = round(menor_saldo_futuro, 2)

    # Identifica o primeiro dia em que atinge esse piso e a véspera da recuperação (gargalo principal)
    candidatos_min = [
        i for i, x in enumerate(serie_analise)
        if abs(x["saldo_acum"] - menor_saldo_futuro) <= 0.005
    ]
    data_inicio_gargalo = serie_analise[candidatos_min[0]]["iso"] if candidatos_min else serie_analise[0]["iso"]
    data_gargalo = data_inicio_gargalo

    for idx_c in candidatos_min:
        # Se o dia seguinte tem entrada de receita, este candidato é o ápice da pressão (ex: dia 29 antes do dia 30)
        if idx_c + 1 < len(serie_analise) and serie_analise[idx_c + 1]["receita"] > 0.005:
            data_gargalo = serie_analise[idx_c]["iso"]
            break
    else:
        if candidatos_min:
            # Se nenhum tem receita imediatamente no dia seguinte, pega o primeiro dia em que houve saída para chegar ao vale
            escolhido = serie_analise[candidatos_min[0]]["iso"]
            for idx_c in candidatos_min:
                if serie_analise[idx_c]["despesa"] > 0.005:
                    escolhido = serie_analise[idx_c]["iso"]
            data_gargalo = escolhido

    teto_seguro_gasto = round(max(0.0, min(sobra_projetada, menor_saldo_futuro)), 2)
    sobra_falsa_travada = round(max(0.0, sobra_projetada - teto_seguro_gasto), 2)
    fica_negativo_no_meio = bool(menor_saldo_futuro < -0.005)
    tem_armadilha_fluxo = bool(sobra_falsa_travada > 0.005 or fica_negativo_no_meio)

    # Próxima entrada de receita após dt_ref (ou após dt_inicio_analise)
    proxima_entrada_data: str | None = None
    proxima_entrada_valor: float = 0.0
    for x in serie:
        if x["date"] > dt_ref and x["receita"] > 0.005:
            proxima_entrada_data = x["iso"]
            proxima_entrada_valor = x["receita"]
            break

    if proxima_entrada_data:
        ate_prox = [
            x["saldo_acum"] for x in serie
            if dt_inicio_analise <= x["date"] < _date.fromisoformat(proxima_entrada_data)
        ]
        if ate_prox:
            teto_ate_proxima_entrada = round(max(0.0, min(ate_prox)), 2)
        else:
            teto_ate_proxima_entrada = teto_seguro_gasto
    else:
        teto_ate_proxima_entrada = teto_seguro_gasto

    # Construção das Janelas de Sobrevivência entre entradas de receita
    indices_entradas = [i for i, x in enumerate(serie) if x["receita"] > 0.005]
    pontos_corte: list[int] = []
    idx_primeiro_mov = next((i for i, x in enumerate(serie) if x["date"] >= primeiro_mov_dt), 0)
    if not indices_entradas or indices_entradas[0] > idx_primeiro_mov:
        pontos_corte.append(idx_primeiro_mov)
    for ie in indices_entradas:
        if ie not in pontos_corte:
            pontos_corte.append(ie)

    janelas_sobrevivencia: list[dict] = []
    for w_idx, start_i in enumerate(pontos_corte):
        end_i = (pontos_corte[w_idx + 1] - 1) if (w_idx + 1 < len(pontos_corte)) else (len(serie) - 1)
        if end_i < start_i:
            end_i = start_i
        fatia = serie[start_i : end_i + 1]
        if not fatia:
            continue

        rec_ini = round(fatia[0]["receita"], 2)
        desp_jan = round(sum(f["despesa"] for f in fatia), 2)
        menor_jan = round(min(f["saldo_acum"] for f in fatia), 2)

        # Escolhe a data do gargalo da janela (preferindo o último dia da janela se empatado antes da próxima receita)
        cands_j = [f for f in fatia if abs(f["saldo_acum"] - menor_jan) <= 0.005]
        dt_garg_jan = cands_j[-1]["iso"] if cands_j else fatia[-1]["iso"]

        prox_dt_w = serie[end_i + 1]["iso"] if (end_i + 1 < len(serie)) else None
        prox_val_w = round(serie[end_i + 1]["receita"], 2) if (end_i + 1 < len(serie)) else 0.0
        teto_livre_jan = round(max(0.0, menor_jan), 2)
        eh_atual = bool(fatia[0]["date"] <= dt_ref <= fatia[-1]["date"])

        if menor_jan < -0.005:
            st_jan = "critico"
        elif menor_jan < sobra_projetada - 0.005 or (rec_ini > 0 and menor_jan < rec_ini * 0.25):
            st_jan = "atencao"
        else:
            st_jan = "seguro"

        janelas_sobrevivencia.append({
            "indice": w_idx + 1,
            "data_inicio": fatia[0]["iso"],
            "data_fim": fatia[-1]["iso"],
            "dias_janela": len(fatia),
            "receita_inicio": rec_ini,
            "despesas_janela": desp_jan,
            "menor_saldo_janela": menor_jan,
            "data_gargalo_janela": dt_garg_jan,
            "proxima_entrada_data": prox_dt_w,
            "proxima_entrada_valor": prox_val_w,
            "teto_livre_janela": teto_livre_jan,
            "eh_janela_atual": eh_atual,
            "eh_gargalo_do_mes": bool(abs(menor_jan - menor_saldo_futuro) <= 0.005),
            "status": st_jan,
        })

        # Marca gargalo de janela nos mapas diários
        if dt_garg_jan in mapa_dias and (desp_jan > 0.005 or menor_jan < sobra_projetada - 0.005):
            mapa_dias[dt_garg_jan]["eh_gargalo_janela"] = True
        if dt_garg_jan in (acumulados_por_dia or {}) and (desp_jan > 0.005 or menor_jan < sobra_projetada - 0.005):
            acumulados_por_dia[dt_garg_jan]["eh_gargalo_janela"] = True

    # Marca o gargalo principal do período
    if data_gargalo:
        if data_gargalo in mapa_dias:
            mapa_dias[data_gargalo]["eh_gargalo_principal"] = True
        if data_gargalo in (acumulados_por_dia or {}):
            acumulados_por_dia[data_gargalo]["eh_gargalo_principal"] = True
        # Garante que se o dia do gargalo não tinha lançamento próprio (ex: dia 29 véspera do dia 30),
        # ele também exista ou seja referenciado em dias_criticos
    if data_inicio_gargalo and data_inicio_gargalo != data_gargalo:
        if data_inicio_gargalo in mapa_dias:
            mapa_dias[data_inicio_gargalo]["eh_gargalo_janela"] = True
        if data_inicio_gargalo in (acumulados_por_dia or {}):
            acumulados_por_dia[data_inicio_gargalo]["eh_gargalo_janela"] = True

    dias_criticos = [
        {
            "data": x["iso"],
            "saldo_acum": x["saldo_acum"],
            "despesa_dia": x["despesa"],
            "receita_dia": x["receita"],
            "eh_negativo": bool(x["saldo_acum"] < -0.005),
            "eh_gargalo_principal": bool(x["iso"] == data_gargalo or x["iso"] == data_inicio_gargalo),
        }
        for x in serie_analise
        if x["saldo_acum"] < -0.005 or x["iso"] in (data_gargalo, data_inicio_gargalo)
    ]

    return {
        "sobra_projetada": sobra_projetada,
        "menor_saldo_futuro": menor_saldo_futuro,
        "data_gargalo": data_gargalo,
        "data_inicio_gargalo": data_inicio_gargalo,
        "teto_seguro_gasto": teto_seguro_gasto,
        "sobra_falsa_travada": sobra_falsa_travada,
        "tem_armadilha_fluxo": tem_armadilha_fluxo,
        "fica_negativo_no_meio": fica_negativo_no_meio,
        "proxima_entrada_data": proxima_entrada_data,
        "proxima_entrada_valor": proxima_entrada_valor,
        "teto_ate_proxima_entrada": teto_ate_proxima_entrada,
        "data_referencia": dt_ref.isoformat(),
        "janelas_sobrevivencia": janelas_sobrevivencia,
        "dias_criticos": dias_criticos,
    }


def _aplicar_filtro_periodo_ao_calendario(
    dados: dict,
    d_ini_str: str,
    d_fim_str: str,
    saldo_base_inicial: float = 0.0,
) -> dict:
    """
    Sincroniza o pacote do Calendário Financeiro com o intervalo global [d_ini_str, d_fim_str].
    Marca cada dia com 'no_periodo_filtro', calcula o mapa O(1) de saldos acumulativos
    ('acumulados_por_dia') e recalcula KPIs e categorias da rosca estritamente dentro do intervalo filtrado.
    """
    ini_mes = str(dados.get("inicio_mes") or d_ini_str)[:10]
    fim_mes = str(dados.get("fim_mes") or d_fim_str)[:10]
    eh_parcial = (d_ini_str != ini_mes or d_fim_str != fim_mes)
    eh_multi_mes = (d_ini_str[:7] != d_fim_str[:7])

    dados["filtro_inicio"] = d_ini_str
    dados["filtro_fim"] = d_fim_str
    dados["eh_periodo_parcial"] = eh_parcial
    dados["eh_multi_mes"] = eh_multi_mes

    dias_lista = dados.get("dias") or []
    for d_item in dias_lista:
        dt_k = str(d_item.get("data") or "")[:10]
        d_item["no_periodo_filtro"] = bool(dt_k and (d_ini_str <= dt_k <= d_fim_str))

    grid_ini_s = str(dados.get("grid_inicio") or d_ini_str)[:10]
    grid_fim_s = str(dados.get("grid_fim") or d_fim_str)[:10]
    s_contas = float(dados.get("saldo_contas_consolidado") or 0.0)
    dados["saldo_base_inicial"] = round(saldo_base_inicial, 2)
    dados["modo_saldo"] = "com_saldo" if abs(saldo_base_inicial) > 0.001 else "isolado"
    dados["acumulados_por_dia"] = _calcular_acumulados_calendario(
        dias_lista, d_ini_str, d_fim_str, grid_ini_s, grid_fim_s, saldo_base_inicial=saldo_base_inicial
    )
    dados["protecao_fluxo"] = calcular_protecao_fluxo_caixa(
        dias_lista, dados["acumulados_por_dia"], d_ini_str, d_fim_str
    )

    if not eh_parcial:
        return dados

    rec_p = 0.0
    desp_p = 0.0
    desp_cta_p = 0.0
    desp_crt_p = 0.0
    dias_s_set = set()
    dias_e_set = set()
    qtd_p = 0
    maior_s = 0.0
    desp_cat_map: dict[str, dict] = {}
    rec_cat_map: dict[str, dict] = {}

    for d_item in dias_lista:
        if not d_item.get("no_periodo_filtro"):
            continue
        dt_k = str(d_item.get("data") or "")[:10]
        r_d = float(d_item.get("total_receitas", 0) or 0)
        s_d = float(d_item.get("total_despesas", 0) or 0)
        sc_d = float(d_item.get("despesas_conta", 0) or 0)
        sr_d = float(d_item.get("despesas_cartao", 0) or 0)
        q_d = int(d_item.get("qtd_lancamentos", 0) or 0)

        rec_p += r_d
        desp_p += s_d
        desp_cta_p += sc_d
        desp_crt_p += sr_d
        qtd_p += q_d
        if r_d > 0:
            dias_e_set.add(dt_k)
        if s_d > 0:
            dias_s_set.add(dt_k)
            if s_d > maior_s:
                maior_s = s_d

        for l_it in (d_item.get("lancamentos") or []):
            tp_l = str(l_it.get("tipo") or "Despesa")
            val_l = float(l_it.get("valor", 0) or 0)
            cat_id_l = l_it.get("categoria_id")
            cat_nm_l = l_it.get("categoria_nome") or "Sem Categoria"
            cat_cor_l = l_it.get("categoria_cor") or "#64748B"
            ch_c = str(cat_id_l or cat_nm_l)
            if tp_l == "Receita":
                if ch_c not in rec_cat_map:
                    rec_cat_map[ch_c] = {"categoria_id": cat_id_l, "categoria": cat_nm_l, "cor": cat_cor_l, "total": 0.0, "qtd": 0}
                rec_cat_map[ch_c]["total"] += val_l
                rec_cat_map[ch_c]["qtd"] += 1
            elif tp_l == "Despesa":
                if ch_c not in desp_cat_map:
                    desp_cat_map[ch_c] = {"categoria_id": cat_id_l, "categoria": cat_nm_l, "cor": cat_cor_l, "total": 0.0, "qtd": 0}
                desp_cat_map[ch_c]["total"] += val_l
                desp_cat_map[ch_c]["qtd"] += 1

    desp_cats = sorted(desp_cat_map.values(), key=lambda x: x["total"], reverse=True)
    for dc in desp_cats:
        dc["percentual"] = round((dc["total"] / desp_p * 100.0), 1) if desp_p > 0 else 0.0
    rec_cats = sorted(rec_cat_map.values(), key=lambda x: x["total"], reverse=True)
    for rc in rec_cats:
        rc["percentual"] = round((rc["total"] / rec_p * 100.0), 1) if rec_p > 0 else 0.0

    dados["kpis"] = {
        "receitas_mes": rec_p,
        "despesas_mes": desp_p,
        "resultado_mes": rec_p - desp_p,
        "despesas_conta_mes": desp_cta_p,
        "despesas_cartao_mes": desp_crt_p,
        "dias_com_saida": len(dias_s_set),
        "dias_com_entrada": len(dias_e_set),
        "qtd_lancamentos_mes": qtd_p,
        "maior_saida_dia": maior_s,
    }
    dados["despesas_por_categoria"] = desp_cats
    dados["receitas_por_categoria"] = rec_cats
    return dados


def obter_calendario_financeiro_mes(
    mes: int,
    ano: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
    saldo_base_inicial: float = 0.0,
) -> dict:
    """
    Chama a RPC 'get_calendario_financeiro_mes' (com fallback em Python) e aplica:
    - Regra de Cartão de Crédito: despesas em cartão aparecem exclusivamente na data de vencimento da fatura.
    - Suporte a Multi-Meses: expande a grade quando o filtro cruza meses.
    - Acumulado Contínuo (Running Sum): pré-calcula o saldo acumulado de data_inicio até cada dia.
    """
    import calendar as _cal
    from datetime import date as _date, timedelta as _td

    m = max(1, min(12, int(mes)))
    a = int(ano)
    inicio_mes = _date(a, m, 1)
    ult_dia = _cal.monthrange(a, m)[1]
    fim_mes = _date(a, m, ult_dia)
    d_ini_str = str(data_inicio)[:10] if data_inicio else inicio_mes.isoformat()
    d_fim_str = str(data_fim)[:10] if data_fim else fim_mes.isoformat()

    try:
        dt_ini_obj = _date.fromisoformat(d_ini_str)
        dt_fim_obj = _date.fromisoformat(d_fim_str)
        if dt_fim_obj < dt_ini_obj:
            dt_ini_obj, dt_fim_obj = dt_fim_obj, dt_ini_obj
            d_ini_str, d_fim_str = dt_ini_obj.isoformat(), dt_fim_obj.isoformat()
    except Exception:
        dt_ini_obj, dt_fim_obj = inicio_mes, fim_mes

    eh_multi_mes = (dt_ini_obj.month != dt_fim_obj.month or dt_ini_obj.year != dt_fim_obj.year)
    base_ini = dt_ini_obj if eh_multi_mes else min(inicio_mes, dt_ini_obj)
    base_fim = dt_fim_obj if eh_multi_mes else max(fim_mes, dt_fim_obj)

    # Domingo = 0 na grade visual (em Python weekday(): Seg=0..Dom=6 -> offset = (weekday + 1) % 7)
    offset_dom = (base_ini.weekday() + 1) % 7
    grid_inicio = base_ini - _td(days=offset_dom)
    offset_sab = 6 - ((base_fim.weekday() + 1) % 7)
    fim_sab = base_fim + _td(days=offset_sab)
    grid_fim = fim_sab if eh_multi_mes else max(grid_inicio + _td(days=41), fim_sab)

    try:
        s_consolidado = float(obter_saldo_consolidado_contas())
    except Exception:
        s_consolidado = 0.0

    vazio = {
        "mes": m,
        "ano": a,
        "inicio_mes": inicio_mes.isoformat(),
        "fim_mes": fim_mes.isoformat(),
        "filtro_inicio": d_ini_str,
        "filtro_fim": d_fim_str,
        "eh_periodo_parcial": (d_ini_str != inicio_mes.isoformat() or d_fim_str != fim_mes.isoformat()),
        "eh_multi_mes": eh_multi_mes,
        "grid_inicio": grid_inicio.isoformat(),
        "grid_fim": grid_fim.isoformat(),
        "saldo_contas_consolidado": s_consolidado,
        "saldo_base_inicial": float(saldo_base_inicial),
        "modo_saldo": "com_saldo" if abs(saldo_base_inicial) > 0.001 else "isolado",
        "kpis": {
            "receitas_mes": 0.0,
            "despesas_mes": 0.0,
            "resultado_mes": 0.0,
            "despesas_conta_mes": 0.0,
            "despesas_cartao_mes": 0.0,
            "dias_com_saida": 0,
            "dias_com_entrada": 0,
            "qtd_lancamentos_mes": 0,
            "maior_saida_dia": 0.0,
        },
        "dias": [],
        "acumulados_por_dia": {},
        "cartoes_faturas": [],
        "despesas_por_categoria": [],
        "receitas_por_categoria": [],
    }

    try:
        resp = supabase.rpc(
            "get_calendario_financeiro_mes",
            {
                "p_mes": m,
                "p_ano": a,
                "p_data_inicio": d_ini_str,
                "p_data_fim": d_fim_str,
            },
        ).execute()
        if isinstance(resp.data, dict) and "dias" in resp.data:
            dados = {**vazio, **resp.data}
            if isinstance(resp.data.get("kpis"), dict):
                dados["kpis"] = {**vazio["kpis"], **resp.data["kpis"]}
            return _aplicar_filtro_periodo_ao_calendario(dados, d_ini_str, d_fim_str, saldo_base_inicial=saldo_base_inicial)
    except Exception:
        try:
            resp2 = supabase.rpc("get_calendario_financeiro_mes", {"p_mes": m, "p_ano": a}).execute()
            if isinstance(resp2.data, dict) and "dias" in resp2.data and not eh_multi_mes:
                dados = {**vazio, **resp2.data}
                if isinstance(resp2.data.get("kpis"), dict):
                    dados["kpis"] = {**vazio["kpis"], **resp2.data["kpis"]}
                return _aplicar_filtro_periodo_ao_calendario(dados, d_ini_str, d_fim_str, saldo_base_inicial=saldo_base_inicial)
        except Exception:
            pass

    # Fallback em Python respeitando a regra de vencimento de fatura de cartão de crédito
    try:
        # Busca janela ampliada (60 dias antes de grid_inicio) para capturar compras de cartão
        # cuja fatura vence dentro da grade atual
        busca_ini = (grid_inicio - _td(days=65)).isoformat()
        busca_fim = (grid_fim + _td(days=5)).isoformat()
        lancs = listar_lancamentos(data_inicio=busca_ini, data_fim=busca_fim)

        # Mapa de faturas (id -> data_vencimento) e cartões (id -> dia_vencimento/dia_fechamento)
        faturas_map: dict[str, str] = {}
        cartoes_map: dict[str, dict] = {}
        try:
            resp_f = supabase.table("faturas").select("id,cartao_id,mes,ano,data_vencimento,valor_total,valor_pago,status").execute()
            for rf in (resp_f.data or []):
                if rf.get("id") and rf.get("data_vencimento"):
                    faturas_map[str(rf["id"])] = str(rf["data_vencimento"])[:10]
        except Exception:
            pass
        try:
            for c_it in listar_cartoes():
                if c_it.get("id"):
                    cartoes_map[str(c_it["id"])] = c_it
        except Exception:
            pass

        dias_map: dict[str, dict] = {}
        desp_cat_map: dict[str, dict] = {}
        rec_cat_map: dict[str, dict] = {}
        rec_mes = 0.0
        desp_mes = 0.0
        desp_conta_mes = 0.0
        desp_cartao_mes = 0.0
        dias_saida_set = set()
        dias_entrada_set = set()
        qtd_mes = 0

        grid_ini_iso = grid_inicio.isoformat()
        grid_fim_iso = grid_fim.isoformat()

        for it in lancs:
            dt_compra_str = str(it.get("data") or "")[:10]
            if not dt_compra_str:
                continue

            tem_cartao = bool(it.get("cartao_id"))
            dt_efetiva_str = dt_compra_str
            if tem_cartao:
                fid = str(it.get("fatura_id") or "")
                if fid and fid in faturas_map:
                    dt_efetiva_str = faturas_map[fid]
                else:
                    cid = str(it.get("cartao_id") or "")
                    c_info = cartoes_map.get(cid) or (it.get("cartoes") or {})
                    dia_v = int(c_info.get("dia_vencimento") or 10)
                    dia_f = int(c_info.get("dia_fechamento") or 1)
                    try:
                        yc, mc, _ = [int(p) for p in dt_compra_str.split("-")]
                        if dia_v < dia_f:
                            mc = 1 if mc == 12 else mc + 1
                            yc = yc + 1 if mc == 1 else yc
                        ult_vc = _cal.monthrange(yc, mc)[1]
                        dt_efetiva_str = _date(yc, mc, min(dia_v, ult_vc)).isoformat()
                    except Exception:
                        dt_efetiva_str = dt_compra_str

            if not (grid_ini_iso <= dt_efetiva_str <= grid_fim_iso):
                continue

            try:
                y_i, m_i, d_i = [int(p) for p in dt_efetiva_str.split("-")]
            except Exception:
                continue
            no_mes = (y_i == a and m_i == m)
            no_periodo = (d_ini_str <= dt_efetiva_str <= d_fim_str)
            tp = str(it.get("tipo") or "Despesa")
            val = float(it.get("valor", 0) or 0)
            cat_obj = it.get("categorias") or {}
            sub_obj = it.get("subcategorias") or {}
            cta_obj = it.get("contas") or {}
            crt_obj = it.get("cartoes") or {}

            cat_nome = cat_obj.get("nome") or "Sem Categoria"
            cat_cor = cat_obj.get("cor") or "#64748B"
            cat_id = it.get("categoria_id")

            if dt_efetiva_str not in dias_map:
                dias_map[dt_efetiva_str] = {
                    "data": dt_efetiva_str,
                    "dia": d_i,
                    "mes": m_i,
                    "ano": y_i,
                    "no_mes_atual": no_mes,
                    "no_periodo_filtro": no_periodo,
                    "total_receitas": 0.0,
                    "total_despesas": 0.0,
                    "despesas_conta": 0.0,
                    "despesas_cartao": 0.0,
                    "qtd_lancamentos": 0,
                    "lancamentos": [],
                }
            bucket = dias_map[dt_efetiva_str]
            bucket["qtd_lancamentos"] += 1
            if tp == "Receita":
                bucket["total_receitas"] += val
            elif tp == "Despesa":
                bucket["total_despesas"] += val
                if tem_cartao:
                    bucket["despesas_cartao"] += val
                else:
                    bucket["despesas_conta"] += val

            bucket["lancamentos"].append({
                "id": it.get("id"),
                "data": dt_efetiva_str,
                "data_compra": dt_compra_str,
                "hora": it.get("hora"),
                "tipo": tp,
                "subtipo": it.get("subtipo"),
                "valor": val,
                "descricao": it.get("descricao"),
                "status": it.get("status"),
                "regra": it.get("regra"),
                "forma_movimentacao": it.get("forma_movimentacao"),
                "parcela_atual": it.get("parcela_atual"),
                "total_parcelas": it.get("total_parcelas"),
                "fatura": it.get("fatura"),
                "fatura_id": it.get("fatura_id"),
                "conta_id": it.get("conta_id"),
                "cartao_id": it.get("cartao_id"),
                "categoria_id": cat_id,
                "subcategoria_id": it.get("subcategoria_id"),
                "categoria_nome": cat_nome,
                "categoria_cor": cat_cor,
                "subcategoria_nome": sub_obj.get("nome"),
                "conta_nome": cta_obj.get("nome"),
                "cartao_nome": crt_obj.get("nome"),
                "cartao_cor": crt_obj.get("cor"),
                "caixinha_id": it.get("caixinha_id"),
                "caixinha_nome": (it.get("caixinhas_teto") or {}).get("nome") if isinstance(it.get("caixinhas_teto"), dict) else it.get("caixinha_nome"),
                "caixinha_cor": (it.get("caixinhas_teto") or {}).get("cor") if isinstance(it.get("caixinhas_teto"), dict) else it.get("caixinha_cor"),
                "caixinha_icone": (it.get("caixinhas_teto") or {}).get("icone") if isinstance(it.get("caixinhas_teto"), dict) else it.get("caixinha_icone"),
            })

            if no_periodo:
                qtd_mes += 1
                if tp == "Receita":
                    rec_mes += val
                    if val > 0:
                        dias_entrada_set.add(dt_efetiva_str)
                    ch_c = str(cat_id or cat_nome)
                    if ch_c not in rec_cat_map:
                        rec_cat_map[ch_c] = {"categoria_id": cat_id, "categoria": cat_nome, "cor": cat_cor, "total": 0.0, "qtd": 0}
                    rec_cat_map[ch_c]["total"] += val
                    rec_cat_map[ch_c]["qtd"] += 1
                elif tp == "Despesa":
                    desp_mes += val
                    if val > 0:
                        dias_saida_set.add(dt_efetiva_str)
                    if tem_cartao:
                        desp_cartao_mes += val
                    else:
                        desp_conta_mes += val
                    ch_c = str(cat_id or cat_nome)
                    if ch_c not in desp_cat_map:
                        desp_cat_map[ch_c] = {"categoria_id": cat_id, "categoria": cat_nome, "cor": cat_cor, "total": 0.0, "qtd": 0}
                    desp_cat_map[ch_c]["total"] += val
                    desp_cat_map[ch_c]["qtd"] += 1

        maior_saida = max(
            (d["total_despesas"] for d in dias_map.values() if d.get("no_periodo_filtro")),
            default=0.0,
        )
        desp_cats = sorted(desp_cat_map.values(), key=lambda x: x["total"], reverse=True)
        for dc in desp_cats:
            dc["percentual"] = round((dc["total"] / desp_mes * 100.0), 1) if desp_mes > 0 else 0.0
        rec_cats = sorted(rec_cat_map.values(), key=lambda x: x["total"], reverse=True)
        for rc in rec_cats:
            rc["percentual"] = round((rc["total"] / rec_mes * 100.0), 1) if rec_mes > 0 else 0.0

        vazio["kpis"] = {
            "receitas_mes": rec_mes,
            "despesas_mes": desp_mes,
            "resultado_mes": rec_mes - desp_mes,
            "despesas_conta_mes": desp_conta_mes,
            "despesas_cartao_mes": desp_cartao_mes,
            "dias_com_saida": len(dias_saida_set),
            "dias_com_entrada": len(dias_entrada_set),
            "qtd_lancamentos_mes": qtd_mes,
            "maior_saida_dia": maior_saida,
        }
        vazio["dias"] = sorted(dias_map.values(), key=lambda x: x["data"])
        vazio["despesas_por_categoria"] = desp_cats
        vazio["receitas_por_categoria"] = rec_cats
        return _aplicar_filtro_periodo_ao_calendario(vazio, d_ini_str, d_fim_str, saldo_base_inicial=saldo_base_inicial)
    except Exception:
        pass

    return _aplicar_filtro_periodo_ao_calendario(vazio, d_ini_str, d_fim_str, saldo_base_inicial=saldo_base_inicial)


async def obter_calendario_financeiro_mes_async(
    mes: int,
    ano: int,
    data_inicio: str | None = None,
    data_fim: str | None = None,
) -> dict:
    return await asyncio.to_thread(obter_calendario_financeiro_mes, mes, ano, data_inicio, data_fim)


# =============================================================================
# COFRES DE INVESTIMENTO & PATRIMÔNIO ("Meu Cofre")
# =============================================================================

def garantir_cofres_padrao(user_id: str = None) -> None:
    """Garante a existência dos dois cofres padrão: Porquinho e Renda Fixa 102% CDI."""
    try:
        u = usuario_atual()
        uid = user_id or (u.id if u else None)
        if not uid:
            return
        # Tenta via RPC
        try:
            supabase.rpc("fn_garantir_cofres_padrao", {"p_user_id": str(uid)}).execute()
            return
        except Exception:
            pass

        # Fallback direto via Python
        resp = supabase.table("cofres_investimento").select("id, tipo").eq("user_id", str(uid)).eq("ativo", True).execute()
        tipos_existentes = {r.get("tipo") for r in (resp.data or [])}

        if "reserva_emergencia" not in tipos_existentes:
            supabase.table("cofres_investimento").insert({
                "user_id": str(uid),
                "nome": "Porquinho (Reserva de Emergência)",
                "tipo": "reserva_emergencia",
                "cor": "#10B981",
                "icone": "savings",
                "meta_valor": 10000.00,
                "percentual_cdi": 100.00,
                "ordem": 1,
            }).execute()

        if "renda_fixa" not in tipos_existentes:
            supabase.table("cofres_investimento").insert({
                "user_id": str(uid),
                "nome": "Renda Fixa (102% CDI)",
                "tipo": "renda_fixa",
                "cor": "#00E676",
                "icone": "trending_up",
                "meta_valor": 50000.00,
                "percentual_cdi": 102.00,
                "ordem": 2,
            }).execute()

        # Config de CDI
        cfg_resp = supabase.table("cofres_config").select("user_id").eq("user_id", str(uid)).maybe_single().execute()
        if not (cfg_resp and cfg_resp.data):
            supabase.table("cofres_config").insert({
                "user_id": str(uid),
                "taxa_cdi_anual": 10.75,
            }).execute()
    except Exception as ex:
        print(f"[AVISO] garantir_cofres_padrao: {ex}")


def listar_cofres_investimento(forcar_atualizacao: bool = False) -> list[dict]:
    """Retorna a lista de cofres ativos do usuário autenticado."""
    u = usuario_atual()
    if not u:
        return []
    uid = str(u.id)
    cache_k = f"cofres_investimento_{uid}"
    if not forcar_atualizacao:
        cached = obter_cache(cache_k)
        if cached is not None:
            return cached

    garantir_cofres_padrao(uid)
    try:
        resp = (
            supabase.table("cofres_investimento")
            .select("*")
            .eq("user_id", uid)
            .eq("ativo", True)
            .order("ordem")
            .execute()
        )
        itens = resp.data or []
        for it in itens:
            it["saldo_atual"] = float(it.get("saldo_atual", 0.0) or 0.0)
            it["total_aportado"] = float(it.get("total_aportado", 0.0) or 0.0)
            it["total_rendimentos"] = float(it.get("total_rendimentos", 0.0) or 0.0)
            it["total_resgatado"] = float(it.get("total_resgatado", 0.0) or 0.0)
            it["meta_valor"] = float(it.get("meta_valor", 0.0) or 0.0)
            it["percentual_cdi"] = float(it.get("percentual_cdi", 102.0) or 102.0)
        salvar_cache(cache_k, itens, ttl=60)
        return itens
    except Exception as ex:
        print(f"[ERRO] listar_cofres_investimento: {ex}")
        return []


def obter_cofre_por_id(cofre_id: str) -> dict | None:
    """Busca detalhes de um cofre por ID."""
    try:
        resp = supabase.table("cofres_investimento").select("*").eq("id", str(cofre_id)).maybe_single().execute()
        if resp and resp.data:
            it = resp.data
            it["saldo_atual"] = float(it.get("saldo_atual", 0.0) or 0.0)
            it["total_aportado"] = float(it.get("total_aportado", 0.0) or 0.0)
            it["total_rendimentos"] = float(it.get("total_rendimentos", 0.0) or 0.0)
            it["total_resgatado"] = float(it.get("total_resgatado", 0.0) or 0.0)
            it["meta_valor"] = float(it.get("meta_valor", 0.0) or 0.0)
            it["percentual_cdi"] = float(it.get("percentual_cdi", 102.0) or 102.0)
            return it
    except Exception as ex:
        print(f"[ERRO] obter_cofre_por_id: {ex}")
    return None


def criar_cofre_investimento(dados: dict) -> dict:
    """Cria um novo cofre personalizado."""
    u = usuario_atual()
    if not u:
        raise ValueError("Usuário não autenticado.")
    uid = str(u.id)
    payload = {
        "user_id": uid,
        "nome": str(dados.get("nome", "Novo Cofre")).strip(),
        "tipo": dados.get("tipo", "renda_fixa"),
        "cor": dados.get("cor", "#00E676"),
        "icone": dados.get("icone", "savings"),
        "meta_valor": float(dados.get("meta_valor", 0.0) or 0.0),
        "percentual_cdi": float(dados.get("percentual_cdi", 102.0) or 102.0),
        "ordem": int(dados.get("ordem", 10)),
        "saldo_atual": 0.0,
        "total_aportado": 0.0,
        "total_rendimentos": 0.0,
        "total_resgatado": 0.0,
        "ativo": True,
    }
    resp = supabase.table("cofres_investimento").insert(payload).execute()
    invalidar_cache(f"cofres_investimento_{uid}")
    item = resp.data[0] if resp.data else payload
    return item


def atualizar_cofre_investimento(cofre_id: str, dados: dict) -> dict:
    """Atualiza dados do cofre (nome, meta, taxa, cor, icone)."""
    payload = {}
    if "nome" in dados:
        payload["nome"] = str(dados["nome"]).strip()
    if "meta_valor" in dados:
        payload["meta_valor"] = float(dados["meta_valor"] or 0.0)
    if "percentual_cdi" in dados:
        payload["percentual_cdi"] = float(dados["percentual_cdi"] or 102.0)
    if "cor" in dados:
        payload["cor"] = str(dados["cor"])
    if "icone" in dados:
        payload["icone"] = str(dados["icone"])
    if "ativo" in dados:
        payload["ativo"] = bool(dados["ativo"])

    resp = supabase.table("cofres_investimento").update(payload).eq("id", str(cofre_id)).execute()
    u = usuario_atual()
    if u:
        invalidar_cache(f"cofres_investimento_{u.id}")
    return resp.data[0] if resp.data else {}


def excluir_cofre_investimento(cofre_id: str) -> bool:
    """Desativa um cofre."""
    try:
        supabase.table("cofres_investimento").update({"ativo": False}).eq("id", str(cofre_id)).execute()
        u = usuario_atual()
        if u:
            invalidar_cache(f"cofres_investimento_{u.id}")
        return True
    except Exception as ex:
        print(f"[ERRO] excluir_cofre_investimento: {ex}")
        return False


def registrar_aporte_cofre(
    cofre_id: str,
    valor: float,
    data: str = None,
    descricao: str = "",
    conta_origem_id: str = None,
    lancar_no_extrato: bool = False,
) -> dict:
    """Registra um aporte (saiu do bolso) no cofre."""
    from datetime import date
    val = round(float(valor or 0.0), 2)
    if val <= 0:
        raise ValueError("O valor do aporte deve ser maior que zero.")

    cofre = obter_cofre_por_id(cofre_id)
    if not cofre:
        raise ValueError("Cofre não encontrado.")

    u = usuario_atual()
    if not u:
        raise ValueError("Usuário não autenticado.")
    uid = str(u.id)

    saldo_ant = cofre["saldo_atual"]
    saldo_pos = round(saldo_ant + val, 2)
    tot_aport = round(cofre["total_aportado"] + val, 2)
    dt = data or date.today().isoformat()

    lanc_id = None
    if lancar_no_extrato and conta_origem_id:
        try:
            lanc = criar_lancamento({
                "tipo": "Despesa",
                "subtipo": "Investimento",
                "forma_movimentacao": "Débito",
                "valor": val,
                "data": dt,
                "conta_id": conta_origem_id,
                "descricao": descricao or f"Aporte: {cofre['nome']}",
                "regra": "Investimento",
                "status": "Pago",
            })
            if lanc and isinstance(lanc, dict):
                lanc_id = lanc.get("id")
        except Exception as ex:
            print(f"[AVISO] Falha ao criar lançamento de débito do aporte: {ex}")

    mov_resp = supabase.table("cofres_movimentacoes").insert({
        "cofre_id": str(cofre_id),
        "user_id": uid,
        "tipo": "aporte",
        "valor": val,
        "saldo_anterior": saldo_ant,
        "saldo_posterior": saldo_pos,
        "descricao": descricao or "Aporte",
        "data": dt,
        "conta_origem_id": conta_origem_id,
        "lancamento_id": lanc_id,
    }).execute()

    supabase.table("cofres_investimento").update({
        "saldo_atual": saldo_pos,
        "total_aportado": tot_aport,
    }).eq("id", str(cofre_id)).execute()

    invalidar_cache(f"cofres_investimento_{uid}")
    return mov_resp.data[0] if mov_resp.data else {}


def registrar_resgate_cofre(
    cofre_id: str,
    valor: float,
    data: str = None,
    descricao: str = "",
    conta_destino_id: str = None,
    lancar_no_extrato: bool = False,
) -> dict:
    """Registra um resgate (voltou pro caixa) do cofre."""
    from datetime import date
    from core.constants import formatar_moeda
    val = round(float(valor or 0.0), 2)
    if val <= 0:
        raise ValueError("O valor do resgate deve ser maior que zero.")

    cofre = obter_cofre_por_id(cofre_id)
    if not cofre:
        raise ValueError("Cofre não encontrado.")

    saldo_ant = cofre["saldo_atual"]
    if val > (saldo_ant + 0.005):
        raise ValueError(f"Saldo insuficiente no cofre ({formatar_moeda(saldo_ant)}) para resgate de {formatar_moeda(val)}.")

    u = usuario_atual()
    if not u:
        raise ValueError("Usuário não autenticado.")
    uid = str(u.id)

    saldo_pos = round(max(0.0, saldo_ant - val), 2)
    tot_resg = round(cofre["total_resgatado"] + val, 2)
    dt = data or date.today().isoformat()

    lanc_id = None
    if lancar_no_extrato and conta_destino_id:
        try:
            lanc = criar_lancamento({
                "tipo": "Receita",
                "subtipo": "Entrada",
                "forma_movimentacao": "Pix",
                "valor": val,
                "data": dt,
                "conta_id": conta_destino_id,
                "descricao": descricao or f"Resgate: {cofre['nome']}",
                "status": "Pago",
            })
            if lanc and isinstance(lanc, dict):
                lanc_id = lanc.get("id")
        except Exception as ex:
            print(f"[AVISO] Falha ao criar lançamento de receita do resgate: {ex}")

    mov_resp = supabase.table("cofres_movimentacoes").insert({
        "cofre_id": str(cofre_id),
        "user_id": uid,
        "tipo": "resgate",
        "valor": val,
        "saldo_anterior": saldo_ant,
        "saldo_posterior": saldo_pos,
        "descricao": descricao or "Resgate",
        "data": dt,
        "conta_origem_id": conta_destino_id,
        "lancamento_id": lanc_id,
    }).execute()

    supabase.table("cofres_investimento").update({
        "saldo_atual": saldo_pos,
        "total_resgatado": tot_resg,
    }).eq("id", str(cofre_id)).execute()

    invalidar_cache(f"cofres_investimento_{uid}")
    return mov_resp.data[0] if mov_resp.data else {}


def registrar_rendimento_direto(
    cofre_id: str,
    valor: float,
    data: str = None,
    descricao: str = "",
) -> dict:
    """Opção A: Informa diretamente o valor que rendeu no dia ou mês (juros ganhos)."""
    from datetime import date
    val = round(float(valor or 0.0), 2)
    if val <= 0:
        raise ValueError("O valor do rendimento deve ser maior que zero.")

    cofre = obter_cofre_por_id(cofre_id)
    if not cofre:
        raise ValueError("Cofre não encontrado.")

    u = usuario_atual()
    if not u:
        raise ValueError("Usuário não autenticado.")
    uid = str(u.id)

    saldo_ant = cofre["saldo_atual"]
    saldo_pos = round(saldo_ant + val, 2)
    tot_rend = round(cofre["total_rendimentos"] + val, 2)
    dt = data or date.today().isoformat()

    mov_resp = supabase.table("cofres_movimentacoes").insert({
        "cofre_id": str(cofre_id),
        "user_id": uid,
        "tipo": "rendimento",
        "valor": val,
        "saldo_anterior": saldo_ant,
        "saldo_posterior": saldo_pos,
        "descricao": descricao or "Rendimento Direto",
        "data": dt,
    }).execute()

    supabase.table("cofres_investimento").update({
        "saldo_atual": saldo_pos,
        "total_rendimentos": tot_rend,
    }).eq("id", str(cofre_id)).execute()

    invalidar_cache(f"cofres_investimento_{uid}")
    return mov_resp.data[0] if mov_resp.data else {}


def registrar_ajuste_por_saldo_atual(
    cofre_id: str,
    saldo_digitado: float,
    data: str = None,
    descricao: str = "",
) -> dict:
    """
    Opção B (Ajuste por Saldo Atual - Inteligente):
    Compara o saldo líquido digitado com o saldo anterior do cofre e registra a diferença
    positiva como Rendimento do Período automaticamente!
    """
    from datetime import date
    from core.constants import formatar_moeda
    novo_saldo = round(float(saldo_digitado or 0.0), 2)
    cofre = obter_cofre_por_id(cofre_id)
    if not cofre:
        raise ValueError("Cofre não encontrado.")

    u = usuario_atual()
    if not u:
        raise ValueError("Usuário não autenticado.")
    uid = str(u.id)

    saldo_ant = cofre["saldo_atual"]
    diff = round(novo_saldo - saldo_ant, 2)
    dt = data or date.today().isoformat()

    if abs(diff) < 0.005:
        return {
            "tipo_ajuste": "sem_alteracao",
            "diferenca": 0.0,
            "saldo_anterior": saldo_ant,
            "saldo_novo": novo_saldo,
            "mensagem": "O saldo digitado é idêntico ao saldo atual do cofre.",
        }

    if diff > 0:
        tot_rend = round(cofre["total_rendimentos"] + diff, 2)
        mov_resp = supabase.table("cofres_movimentacoes").insert({
            "cofre_id": str(cofre_id),
            "user_id": uid,
            "tipo": "rendimento",
            "valor": diff,
            "saldo_anterior": saldo_ant,
            "saldo_posterior": novo_saldo,
            "descricao": descricao or f"Rendimento automático por ajuste de saldo ({formatar_moeda(saldo_ant)} → {formatar_moeda(novo_saldo)})",
            "data": dt,
        }).execute()

        supabase.table("cofres_investimento").update({
            "saldo_atual": novo_saldo,
            "total_rendimentos": tot_rend,
        }).eq("id", str(cofre_id)).execute()

        invalidar_cache(f"cofres_investimento_{uid}")
        return {
            "tipo_ajuste": "rendimento",
            "diferenca": diff,
            "saldo_anterior": saldo_ant,
            "saldo_novo": novo_saldo,
            "movimentacao": mov_resp.data[0] if mov_resp.data else {},
            "mensagem": f"Rendimento de +{formatar_moeda(diff)} registrado com sucesso!",
        }
    else:
        val_resg = abs(diff)
        tot_resg = round(cofre["total_resgatado"] + val_resg, 2)
        mov_resp = supabase.table("cofres_movimentacoes").insert({
            "cofre_id": str(cofre_id),
            "user_id": uid,
            "tipo": "resgate",
            "valor": val_resg,
            "saldo_anterior": saldo_ant,
            "saldo_posterior": novo_saldo,
            "descricao": descricao or f"Ajuste de saldo ({formatar_moeda(saldo_ant)} → {formatar_moeda(novo_saldo)})",
            "data": dt,
        }).execute()

        supabase.table("cofres_investimento").update({
            "saldo_atual": novo_saldo,
            "total_resgatado": tot_resg,
        }).eq("id", str(cofre_id)).execute()

        invalidar_cache(f"cofres_investimento_{uid}")
        return {
            "tipo_ajuste": "resgate",
            "diferenca": diff,
            "saldo_anterior": saldo_ant,
            "saldo_novo": novo_saldo,
            "movimentacao": mov_resp.data[0] if mov_resp.data else {},
            "mensagem": f"Ajuste de {formatar_moeda(val_resg)} aplicado ao saldo.",
        }


def obter_movimentacoes_cofres(cofre_id: str = None, limite: int = 50) -> list[dict]:
    """Retorna o histórico recente de movimentações dos cofres."""
    u = usuario_atual()
    if not u:
        return []
    uid = str(u.id)
    try:
        query = (
            supabase.table("cofres_movimentacoes")
            .select("*, cofres_investimento(nome, tipo, cor, icone)")
            .eq("user_id", uid)
        )
        if cofre_id:
            query = query.eq("cofre_id", str(cofre_id))
        resp = query.order("data", desc=True).order("criado_em", desc=True).limit(limite).execute()
        itens = resp.data or []
        for it in itens:
            it["valor"] = float(it.get("valor", 0.0) or 0.0)
            it["saldo_anterior"] = float(it.get("saldo_anterior", 0.0) or 0.0)
            it["saldo_posterior"] = float(it.get("saldo_posterior", 0.0) or 0.0)
            cinfo = it.get("cofres_investimento") or {}
            it["cofre_nome"] = cinfo.get("nome", "Cofre")
            it["cofre_cor"] = cinfo.get("cor", "#00E676")
            it["cofre_icone"] = cinfo.get("icone", "savings")
        return itens
    except Exception as ex:
        print(f"[ERRO] obter_movimentacoes_cofres: {ex}")
        return []


def excluir_movimentacao_cofre(movimentacao_id: str) -> bool:
    """Exclui uma movimentação e recalcula atomicamente os saldos do cofre."""
    try:
        resp = supabase.table("cofres_movimentacoes").select("*").eq("id", str(movimentacao_id)).maybe_single().execute()
        if not (resp and resp.data):
            return False
        mov = resp.data
        cid = mov["cofre_id"]
        supabase.table("cofres_movimentacoes").delete().eq("id", str(movimentacao_id)).execute()

        todas = supabase.table("cofres_movimentacoes").select("*").eq("cofre_id", cid).order("data").order("criado_em").execute()
        tot_ap = 0.0
        tot_rend = 0.0
        tot_resg = 0.0
        saldo_corr = 0.0
        for m in (todas.data or []):
            tp = m.get("tipo")
            v = float(m.get("valor", 0.0) or 0.0)
            if tp == "aporte":
                tot_ap += v
                saldo_corr += v
            elif tp == "rendimento":
                tot_rend += v
                saldo_corr += v
            elif tp == "resgate":
                tot_resg += v
                saldo_corr = max(0.0, saldo_corr - v)

        supabase.table("cofres_investimento").update({
            "saldo_atual": round(saldo_corr, 2),
            "total_aportado": round(tot_ap, 2),
            "total_rendimentos": round(tot_rend, 2),
            "total_resgatado": round(tot_resg, 2),
        }).eq("id", str(cid)).execute()

        u = usuario_atual()
        if u:
            invalidar_cache(f"cofres_investimento_{u.id}")
        return True
    except Exception as ex:
        print(f"[ERRO] excluir_movimentacao_cofre: {ex}")
        return False


def obter_config_taxa_cdi() -> float:
    """Retorna a taxa CDI anual configurada (padrão 10.75% a.a.)."""
    u = usuario_atual()
    if not u:
        return 10.75
    uid = str(u.id)
    try:
        resp = supabase.table("cofres_config").select("taxa_cdi_anual").eq("user_id", uid).maybe_single().execute()
        if resp and resp.data:
            return float(resp.data.get("taxa_cdi_anual", 10.75) or 10.75)
    except Exception:
        pass
    return 10.75


def salvar_config_taxa_cdi(taxa: float) -> bool:
    """Salva a taxa CDI anual configurada."""
    u = usuario_atual()
    if not u:
        return False
    uid = str(u.id)
    t = round(float(taxa or 10.75), 2)
    try:
        supabase.table("cofres_config").upsert({
            "user_id": uid,
            "taxa_cdi_anual": t,
        }).execute()
        return True
    except Exception as ex:
        print(f"[ERRO] salvar_config_taxa_cdi: {ex}")
        return False


def obter_resumo_investimentos_patrimonio(forcar_atualizacao: bool = False) -> dict:
    """
    Retorna o pacote consolidado de Wealth Management:
    - Patrimônio Total Acumulado
    - Meu Suor (Total Aportado Líquido) vs Juros (Rendimento Acumulado)
    - Lucro % sobre o capital investido
    - Estimativa da Máquina de Renda Passiva (R$/mês e R$/dia)
    - Cards dos Ativos individuais (Porquinho e 102% CDI)
    - Séries de dados para os Gráficos
    - Badges de gamificação e marcos atingidos
    """
    from datetime import date
    from collections import defaultdict
    from core.constants import MESES_NOMES, formatar_moeda

    cofres = listar_cofres_investimento(forcar_atualizacao=forcar_atualizacao)
    taxa_cdi = obter_config_taxa_cdi()
    movs = obter_movimentacoes_cofres(limite=200)

    patrimonio_total = sum(c["saldo_atual"] for c in cofres)
    total_aportado_bruto = sum(c["total_aportado"] for c in cofres)
    total_resgatado = sum(c["total_resgatado"] for c in cofres)
    total_aportado_liquido = max(0.0, total_aportado_bruto - total_resgatado)
    total_rendimentos = sum(c["total_rendimentos"] for c in cofres)

    lucro_pct = (
        round((total_rendimentos / total_aportado_liquido) * 100.0, 2)
        if total_aportado_liquido > 0.005
        else 0.0
    )

    # Taxa CDI efetiva média (considerando Renda Fixa a 102% CDI)
    taxa_anual_efetiva = (taxa_cdi * 1.02) / 100.0
    # Taxa mensal equivalente: (1 + taxa_anual)^(1/12) - 1
    taxa_mensal_efetiva = ((1.0 + taxa_anual_efetiva) ** (1.0 / 12.0)) - 1.0
    renda_mensal_estimada = round(patrimonio_total * taxa_mensal_efetiva, 2)
    renda_diaria_estimada = round(renda_mensal_estimada / 30.0, 2)

    # Agregação por mês (últimos 6 meses)
    meses_ordem = []
    hoje_dt = date.today()
    for i in range(5, -1, -1):
        m = hoje_dt.month - i
        a = hoje_dt.year
        while m <= 0:
            m += 12
            a -= 1
        meses_ordem.append(f"{a:04d}-{m:02d}")

    aportes_por_mes = defaultdict(float)
    rendimentos_por_mes = defaultdict(float)
    resgates_por_mes = defaultdict(float)

    for mv in movs:
        dt_str = str(mv.get("data", ""))[:7]
        tp = mv.get("tipo")
        v = float(mv.get("valor", 0.0) or 0.0)
        if tp == "aporte":
            aportes_por_mes[dt_str] += v
        elif tp == "rendimento":
            rendimentos_por_mes[dt_str] += v
        elif tp == "resgate":
            resgates_por_mes[dt_str] += v

    historico_mensal = []
    for ym in meses_ordem:
        ano_i, mes_i = int(ym[:4]), int(ym[5:7])
        lbl_mes = f"{MESES_NOMES[mes_i - 1][:3]}/{str(ano_i)[2:]}"
        ap_mes = round(aportes_por_mes[ym], 2)
        rend_mes = round(rendimentos_por_mes[ym], 2)
        resg_mes = round(resgates_por_mes[ym], 2)
        historico_mensal.append({
            "mes_chave": ym,
            "label": lbl_mes,
            "aportes": ap_mes,
            "rendimentos": rend_mes,
            "resgates": resg_mes,
            "saldo_liquido_mes": round(ap_mes + rend_mes - resg_mes, 2),
        })

    # Simulação da curva acumulada retroativa que converge exatamente para os saldos atuais
    saldo_atual_running = patrimonio_total
    aporte_atual_running = total_aportado_liquido
    rendimento_atual_running = total_rendimentos

    evol_reversa = []
    evol_reversa.append({
        "label": historico_mensal[-1]["label"] if historico_mensal else "Atual",
        "mes_chave": meses_ordem[-1] if meses_ordem else "",
        "aporte_acumulado": aporte_atual_running,
        "rendimento_acumulado": rendimento_atual_running,
        "patrimonio_total": saldo_atual_running,
    })

    for i in range(len(historico_mensal) - 2, -1, -1):
        item_prox = historico_mensal[i + 1]
        saldo_atual_running = max(0.0, saldo_atual_running - item_prox["saldo_liquido_mes"])
        liq_ap = item_prox["aportes"] - item_prox["resgates"]
        aporte_atual_running = max(0.0, aporte_atual_running - liq_ap)
        rendimento_atual_running = max(0.0, rendimento_atual_running - item_prox["rendimentos"])
        evol_reversa.append({
            "label": historico_mensal[i]["label"],
            "mes_chave": historico_mensal[i]["mes_chave"],
            "aporte_acumulado": round(aporte_atual_running, 2),
            "rendimento_acumulado": round(rendimento_atual_running, 2),
            "patrimonio_total": round(saldo_atual_running, 2),
        })

    evolucao_patrimonial = list(reversed(evol_reversa))

    # Gamificação: Conquistas e Marcos
    qtd_meses_aportados = sum(1 for hm in historico_mensal if hm["aportes"] > 0)
    badges = [
        {
            "id": "primeiro_passo",
            "titulo": "Primeiro Tijolo",
            "descricao": "Primeiro aporte realizado no cofre.",
            "icone": "emoji_events",
            "atingido": total_aportado_bruto > 0,
            "meta_label": "1º Aporte",
            "progresso": 1.0 if total_aportado_bruto > 0 else 0.0,
        },
        {
            "id": "mil_reais",
            "titulo": "Reserva Inicial",
            "descricao": "Atingiu R$ 1.000,00 de patrimônio.",
            "icone": "military_tech",
            "atingido": patrimonio_total >= 1000.0,
            "meta_label": "R$ 1.000",
            "progresso": min(1.0, patrimonio_total / 1000.0),
        },
        {
            "id": "cinco_mil",
            "titulo": "Clube dos 5K",
            "descricao": "Acumulou R$ 5.000,00 de patrimônio.",
            "icone": "shield",
            "atingido": patrimonio_total >= 5000.0,
            "meta_label": "R$ 5.000",
            "progresso": min(1.0, patrimonio_total / 5000.0),
        },
        {
            "id": "dez_mil",
            "titulo": "Fortaleza 10K",
            "descricao": "Alcançou R$ 10.000,00 no cofre.",
            "icone": "workspace_premium",
            "atingido": patrimonio_total >= 10000.0,
            "meta_label": "R$ 10.000",
            "progresso": min(1.0, patrimonio_total / 10000.0),
        },
        {
            "id": "constancia",
            "titulo": "Constância Lendária",
            "descricao": "Aportou em 3 ou mais meses recentes.",
            "icone": "local_fire_department",
            "atingido": qtd_meses_aportados >= 3,
            "meta_label": f"{qtd_meses_aportados}/3 Meses",
            "progresso": min(1.0, qtd_meses_aportados / 3.0),
        },
        {
            "id": "renda_ativa",
            "titulo": "Máquina Ligada",
            "descricao": "Ganhou mais de R$ 50,00 só com juros.",
            "icone": "auto_awesome",
            "atingido": total_rendimentos >= 50.0,
            "meta_label": f"{formatar_moeda(total_rendimentos)} / R$ 50",
            "progresso": min(1.0, total_rendimentos / 50.0),
        },
    ]

    return {
        "patrimonio_total": patrimonio_total,
        "total_aportado_bruto": total_aportado_bruto,
        "total_resgatado": total_resgatado,
        "total_aportado_liquido": total_aportado_liquido,
        "total_rendimentos": total_rendimentos,
        "lucro_pct": lucro_pct,
        "taxa_cdi_anual": taxa_cdi,
        "renda_mensal_estimada": renda_mensal_estimada,
        "renda_diaria_estimada": renda_diaria_estimada,
        "cofres": cofres,
        "movimentacoes_recentes": movs[:20],
        "historico_mensal": historico_mensal,
        "evolucao_patrimonial": evolucao_patrimonial,
        "badges": badges,
    }


async def listar_cofres_investimento_async(forcar_atualizacao: bool = False) -> list[dict]:
    return await asyncio.to_thread(listar_cofres_investimento, forcar_atualizacao)

async def obter_resumo_investimentos_patrimonio_async(forcar_atualizacao: bool = False) -> dict:
    return await asyncio.to_thread(obter_resumo_investimentos_patrimonio, forcar_atualizacao)

async def registrar_aporte_cofre_async(**kwargs) -> dict:
    return await asyncio.to_thread(registrar_aporte_cofre, **kwargs)

async def registrar_resgate_cofre_async(**kwargs) -> dict:
    return await asyncio.to_thread(registrar_resgate_cofre, **kwargs)

async def registrar_rendimento_direto_async(**kwargs) -> dict:
    return await asyncio.to_thread(registrar_rendimento_direto, **kwargs)

async def registrar_ajuste_por_saldo_atual_async(**kwargs) -> dict:
    return await asyncio.to_thread(registrar_ajuste_por_saldo_atual, **kwargs)

