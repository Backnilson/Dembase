"""
=============================================================================
DemBase v3 â€” run_migrations.py
Script de migraÃ§Ã£o executado directamente via supabase-py (REST/RPC).
Cria todas as tabelas e RPCs necessÃ¡rias.
Execute: python run_migrations.py
=============================================================================
"""
import os
import sys
from pathlib import Path

# Garante que encontra o .env
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import httpx

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

# Para migrations, usamos a REST API do PostgREST via endpoint /rest/v1/rpc
# Mas para DDL (CREATE TABLE, ALTER TABLE), precisamos do endpoint de SQL
# O Supabase expÃµe isso no Management API ou via pg_net.
# A forma mais simples Ã© usar o endpoint /rest/v1/ com service_role key
# OU usar o mÃ³dulo supabase com postgrest

# ---------------------------------------------------------------------------
# Usamos httpx directo para o endpoint SQL do Supabase
# O endpoint correcto para SQL raw Ã©: POST /rest/v1/rpc/exec_sql
# Mas o Supabase Management API Ã© o caminho oficial para DDL
# ---------------------------------------------------------------------------

def executar_sql_migration(sql_content: str, nome: str):
    """Executa SQL via Supabase Management API."""
    # Extrair project ref da URL
    # https://ieljnrkxxopqzpnlodfk.supabase.co -> ieljnrkxxopqzpnlodfk
    project_ref = SUPABASE_URL.replace("https://", "").split(".")[0]
    
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    
    headers = {
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {"query": sql_content}
    
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            print(f"  [OK] {nome}")
            return True
        else:
            print(f"  [ERRO {resp.status_code}] {nome}: {resp.text[:300]}")
            return False
    except Exception as ex:
        print(f"  [EXCECAO] {nome}: {ex}")
        return False


def ler_migration(nome_arquivo: str) -> str:
    caminho = Path(__file__).parent / "migrations" / nome_arquivo
    return caminho.read_text(encoding="utf-8")


if __name__ == "__main__":
    print("=" * 60)
    print("DemBase v3 â€” Executando Migrations")
    print("=" * 60)
    
    migrations = [
        "001_alter_contas_categorias_lancamentos.sql",
        "002_create_cartoes_faturas_recorrentes_objetivos.sql",
        "003_rpcs_dashboard_graficos.sql",
        "004_fix_rls_categorias_subcategorias.sql",
        "005_recorrencia_lancamentos.sql",
        "006_periodo_flexivel_dashboard.sql",
        "007_fix_recorrencia_e_sincronizacao_saldos.sql",
        "008_rpcs_relatorios.sql",
        "009_potes_financeiros.sql",
    ]
    
    for m in migrations:
        print(f"\nExecutando: {m}")
        sql = ler_migration(m)
        executar_sql_migration(sql, m)
    
    print("\n" + "=" * 60)
    print("Migrations concluidas!")
    print("=" * 60)
