"""
=============================================================================
DemBase v3 — run_migrations.py
Script de migração executado via Supabase Management API ou MCP.
Cria todas as tabelas e RPCs necessárias.
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

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ieljnrkxxopqzpnlodfk.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
# A Management API (api.supabase.com) exige um Personal Access Token (PAT, sbp_...)
SUPABASE_ACCESS_TOKEN = os.environ.get("SUPABASE_ACCESS_TOKEN") or os.environ.get("SUPABASE_PAT") or SUPABASE_KEY

def executar_sql_migration(sql_content: str, nome: str):
    """Executa SQL via Supabase Management API."""
    project_ref = SUPABASE_URL.replace("https://", "").split(".")[0]
    url = f"https://api.supabase.com/v1/projects/{project_ref}/database/query"
    
    headers = {
        "Authorization": f"Bearer {SUPABASE_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {"query": sql_content}
    
    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=60)
        if resp.status_code in (200, 201):
            print(f"  [OK] {nome}")
            return True
        elif resp.status_code == 401:
            print(f"  [AVISO 401] {nome}: A API de gerenciamento exige um Personal Access Token (SUPABASE_ACCESS_TOKEN).")
            print(f"  As migrações podem ser aplicadas via SQL Editor do Supabase ou MCP.")
            return False
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
    print("DemBase v3 — Executando Migrations")
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
