"""
=============================================================================
DemBase v3 — test_potes_enum_regra.py
Validação unitária e de integração da separação estrita entre pote_id (UUID)
e regra (enum regra_financeira), prevenindo o erro PostgreSQL 22P02.
=============================================================================
"""
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(__file__))

from core.potes import (
    obter_regra_pote,
    REGRAS_VALIDAS,
    REGRA_POR_POSICAO,
    REGRA_POR_ID,
)
from core.lancamento_state import LancamentoFormState
import services.supabase_client as db


def test_obter_regra_pote():
    print("--- 1. Testando mapeamento canônico obter_regra_pote ---")
    for r in REGRAS_VALIDAS:
        assert obter_regra_pote(r) == r, f"Deveria preservar enum válido '{r}'"

    prazeres_uuid = "c82b0736-fb01-419f-8155-923ebfec82b2"
    assert obter_regra_pote(prazeres_uuid) == "Estilo de Vida", "Prazeres deve mapear para 'Estilo de Vida'"
    assert obter_regra_pote("2df4dd2f-4353-42cc-a5c9-8983085a5301") == "Essencial"
    assert obter_regra_pote("da6e1d2b-c611-481d-b48d-065cc5d584b4") == "Essencial"
    assert obter_regra_pote("986da9e8-3042-4562-b1df-c1f5cf0138b9") == "Investimento"
    assert obter_regra_pote("1f1f7449-d985-4c2a-b807-0570a5526614") == "Investimento"
    assert obter_regra_pote("34a47be1-9879-46bd-96b1-4082703bf388") == "Investimento"

    # Mapeamento por lista de potes customizados
    potes_custom = [
        {"id": "uuid-custom-1", "posicao": 1, "nome": "Meu Pote Fixo"},
        {"id": "uuid-custom-4", "posicao": 4, "nome": "Meu Pote Diversao"},
    ]
    assert obter_regra_pote("uuid-custom-1", potes_custom) == "Essencial"
    assert obter_regra_pote("uuid-custom-4", potes_custom) == "Estilo de Vida"
    assert obter_regra_pote("Meu Pote Diversao", potes_custom) == "Estilo de Vida"

    # Fallback semântico e valores nulos
    assert obter_regra_pote(None) == "Essencial"
    assert obter_regra_pote("") == "Essencial"
    print("  [OK] obter_regra_pote validado com 100% de precisão.")


def test_lancamento_form_regra_e_pote():
    print("--- 2. Testando LancamentoForm: separação entre pote_id e regra ---")
    from views.widgets.lancamento_form import LancamentoForm
    page = MagicMock()
    page.client_storage = MagicMock()

    state = LancamentoFormState()
    prazeres_uuid = "c82b0736-fb01-419f-8155-923ebfec82b2"
    state.pote_id = prazeres_uuid
    state.regra = prazeres_uuid  # Simula estado que antes continha o UUID

    with patch("services.potes_service.carregar_potes", return_value=[
        {"id": prazeres_uuid, "posicao": 4, "nome": "Prazeres", "percentual": 11.0}
    ]), patch("services.supabase_client.listar_contas", return_value=[]), \
       patch("services.supabase_client.listar_cartoes", return_value=[]), \
       patch("services.supabase_client.listar_categorias", return_value=[]), \
       patch("services.supabase_client.listar_caixinhas", return_value=[]):
        form = LancamentoForm(page, state)

        # Na inicialização, form deve ter saneado state.regra para enum válido
        assert state.regra == "Estilo de Vida", f"Esperado 'Estilo de Vida', obtido: {state.regra}"
        assert state.pote_id == prazeres_uuid, f"Esperado {prazeres_uuid}, obtido: {state.pote_id}"
        assert form.dd_regra.value == prazeres_uuid, "Dropdown deve selecionar a chave do pote (UUID)"

        # Quando o usuário altera o dropdown de pote
        ev = MagicMock()
        custo_fixo_uuid = "2df4dd2f-4353-42cc-a5c9-8983085a5301"
        ev.control.value = custo_fixo_uuid
        ev.data = custo_fixo_uuid
        form._ao_mudar_regra(ev)

        assert state.pote_id == custo_fixo_uuid
        assert state.regra == "Essencial", f"Esperado 'Essencial', obtido: {state.regra}"

    print("  [OK] LancamentoForm separa rigorosamente pote_id de regra enum.")


def test_supabase_client_sanitizacao():
    print("--- 3. Testando sanitização de defesa em profundidade no supabase_client ---")
    prazeres_uuid = "c82b0736-fb01-419f-8155-923ebfec82b2"
    dados = {
        "descricao": "Adega",
        "pote_id": prazeres_uuid,
        "regra": prazeres_uuid,  # UUID incorreto
    }
    db._sanitizar_regra_lancamento(dados)
    assert dados["regra"] == "Estilo de Vida", f"Deveria ter convertido para 'Estilo de Vida', mas foi: {dados['regra']}"
    assert dados["pote_id"] == prazeres_uuid

    # Já válido
    dados_ok = {"regra": "Investimento"}
    db._sanitizar_regra_lancamento(dados_ok)
    assert dados_ok["regra"] == "Investimento"
    print("  [OK] supabase_client._sanitizar_regra_lancamento validado com sucesso.")


if __name__ == "__main__":
    test_obter_regra_pote()
    test_lancamento_form_regra_e_pote()
    test_supabase_client_sanitizacao()
    print("\n============================================================")
    print("TODOS OS TESTES DE POTES E REGRA ENUM PASSARAM COM SUCESSO!")
    print("============================================================")
