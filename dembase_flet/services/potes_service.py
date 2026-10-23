"""
=============================================================================
DemBase v3 — services/potes_service.py
Orquestra a lógica de potes (core/potes.py) com a persistência
(services/supabase_client.py). Nenhum import de Flet aqui.
=============================================================================
"""
from __future__ import annotations

from decimal import Decimal

from core import potes as P
from services import supabase_client as db


def carregar_potes() -> list[P.Pote]:
    return P.potes_de_registros(db.listar_potes())


def salvar_configuracao(itens: list[dict]) -> list[P.Pote]:
    """
    Valida (soma == 100, nomes únicos...) e só então persiste, de forma atômica.
    itens: [{"id", "nome", "percentual"}]. Levanta P.ErroPotes se inválido.
    """
    P.exigir_configuracao_valida(itens)
    payload = [
        {
            "id": i["id"],
            "nome": str(i["nome"]).strip(),
            "percentual": float(P.para_decimal(i["percentual"])),
        }
        for i in itens
    ]
    try:
        return P.potes_de_registros(db.salvar_potes(payload))
    except Exception as ex:
        # Última barreira: o banco também rejeita configurações divergentes
        raise P.ErroPotes([_mensagem_banco(ex)]) from ex


def registrar_receita(dados_lancamento: dict) -> dict:
    """
    Entrada de receita com distribuição automática entre os 6 potes.

    1. Lê a configuração atual dos potes e distribui o valor (centavos exatos).
    2. Insere o lançamento (tipo Receita; pote_id fica NULL).
    3. Grava a distribuição atomicamente via RPC. Se falhar, desfaz o lançamento
       (compensação) para nunca deixar receita sem distribuição.

    Retorna {"lancamento": {...}, "distribuicao": [{pote_id, percentual, valor}]}.
    """
    valor = P.para_decimal(dados_lancamento.get("valor"))
    if valor <= Decimal("0"):
        raise P.ErroPotes(["O valor da receita deve ser maior que zero."])

    potes = carregar_potes()
    distribuicao = P.distribuir_valor(valor, potes)  # valida soma == 100

    dados = dict(dados_lancamento)
    dados["tipo"] = "Receita"
    dados["valor"] = float(valor.quantize(P.CENTAVO))
    dados["regra"] = None
    dados["pote_id"] = None

    resp = db.criar_lancamento(dados)
    if not resp.data:
        raise P.ErroPotes(["Não foi possível registrar a receita."])
    lancamento = resp.data[0]

    try:
        db.registrar_distribuicao_receita(lancamento["id"], distribuicao)
    except Exception as ex:
        try:
            db.deletar_lancamento(lancamento["id"])
        finally:
            raise P.ErroPotes([_mensagem_banco(ex)]) from ex

    return {"lancamento": lancamento, "distribuicao": distribuicao}


def _mensagem_banco(ex: Exception) -> str:
    texto = str(ex)
    for marcador in ("POTES_INVALIDOS:",):
        if marcador in texto:
            trecho = texto.split(marcador, 1)[1]
            return trecho.split('"')[0].split("'")[0].strip().rstrip("}").strip()
    return f"Erro ao salvar: {texto}"


def ler_renda_referencia() -> Decimal:
    return P.para_decimal(db.ler_renda_referencia(), Decimal("0"))


def salvar_renda_referencia(valor) -> Decimal:
    renda = P.para_decimal(valor, default=Decimal("0"))
    if renda < 0:
        raise P.ErroPotes(["A renda de referência não pode ser negativa."])
    renda = renda.quantize(P.CENTAVO)
    db.salvar_renda_referencia(float(renda))
    return renda

def redistribuir_receita(lancamento_id: str, valor) -> list[dict]:
    """Recalcula e regrava a distribuição de uma receita editada (valor novo)."""
    distribuicao = P.distribuir_valor(valor, carregar_potes())
    try:
        db.registrar_distribuicao_receita(lancamento_id, distribuicao)
    except Exception as ex:
        raise P.ErroPotes([_mensagem_banco(ex)]) from ex
    return distribuicao