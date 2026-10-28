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


def carregar_potes(mes: int | None = None, ano: int | None = None) -> list[P.Pote]:
    return P.potes_de_registros(db.listar_potes(mes=mes, ano=ano))


def carregar_potes_com_meta_mes(mes: int | None = None, ano: int | None = None) -> tuple[list[P.Pote], bool]:
    """
    Retorna `(lista_potes, herdado)` para o mês/ano informado.
    `herdado=True` indica que este mês ainda não possui snapshot próprio salvo
    e está herdando as porcentagens do mês anterior configurado (ou padrão base).
    """
    regs = db.listar_potes(mes=mes, ano=ano)
    herdado = bool(regs and any(bool(r.get("herdado")) for r in regs if isinstance(r, dict)))
    return P.potes_de_registros(regs), herdado


def carregar_contexto_mes(data_inicio: str, data_fim: str, piso_custos_fixos: float = 1150.0) -> dict:
    """
    Espelho dos números do Dashboard para o período: usa exatamente a mesma consulta
    (`obter_resumo_potes`, com o mesmo cache) para que Configuração e Dashboard nunca divirjam.
    Retorna {renda, gastos{posicao: R$}, qtd{posicao: n}, tem_receita}.
    """
    resumo = db.obter_resumo_potes(data_inicio, data_fim, piso_custos_fixos=float(piso_custos_fixos)) or {}
    renda = float(resumo.get("renda") or 0.0)
    gastos: dict[int, float] = {}
    qtd: dict[int, int] = {}
    for p in resumo.get("potes") or []:
        try:
            pos = int(p.get("posicao"))
        except (TypeError, ValueError):
            continue
        gastos[pos] = float(p.get("gasto") or 0.0)
        qtd[pos] = int(p.get("qtd_transacoes") or 0)
    return {"renda": renda, "gastos": gastos, "qtd": qtd, "tem_receita": renda > 0}


def obter_pct_investimento_db(mes: int, ano: int) -> tuple[float | None, bool]:
    """Percentual do slider do Caixa Livre salvo no banco para o mês: (pct, personalizado_no_mes)."""
    try:
        cfg = db.obter_config_caixa_livre_mes(mes, ano)
        if isinstance(cfg, dict) and "pct_investimento" in cfg:
            return float(cfg["pct_investimento"]), bool(cfg.get("personalizado_no_mes", False))
    except Exception:
        pass
    return None, False


def salvar_configuracao(
    itens: list[dict],
    mes: int | None = None,
    ano: int | None = None,
) -> list[P.Pote]:
    """
    Valida (soma == 100, nomes únicos...) e só então persiste de forma atômica,
    aplicando exclusivamente ao mês/ano informado (quando fornecido).
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
        return P.potes_de_registros(db.salvar_potes(payload, mes=mes, ano=ano))
    except Exception as ex:
        # Última barreira: o banco também rejeita configurações divergentes
        raise P.ErroPotes([_mensagem_banco(ex)]) from ex


def _extrair_mes_ano_data(data_str: str | None) -> tuple[int | None, int | None]:
    if not data_str:
        return None, None
    try:
        partes = str(data_str)[:10].split("-")
        if len(partes) >= 2:
            return int(partes[1]), int(partes[0])
    except Exception:
        pass
    return None, None


def registrar_receita(dados_lancamento: dict) -> dict:
    """
    Entrada de receita com distribuição automática entre os 6 potes do mês da receita.

    1. Lê a configuração dos potes do mês/ano do lançamento e distribui o valor (centavos exatos).
    2. Insere o lançamento (tipo Receita; pote_id fica NULL).
    3. Grava a distribuição atomicamente via RPC. Se falhar, desfaz o lançamento
       (compensação) para nunca deixar receita sem distribuição.

    Retorna {"lancamento": {...}, "distribuicao": [{pote_id, percentual, valor}]}.
    """
    valor = P.para_decimal(dados_lancamento.get("valor"))
    if valor <= Decimal("0"):
        raise P.ErroPotes(["O valor da receita deve ser maior que zero."])

    m_rec, a_rec = _extrair_mes_ano_data(dados_lancamento.get("data"))
    potes = carregar_potes(mes=m_rec, ano=a_rec)
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


def redistribuir_receita(lancamento_id: str, valor, data: str | None = None) -> list[dict]:
    """Recalcula e regrava a distribuição de uma receita editada (valor novo)."""
    m_rec, a_rec = _extrair_mes_ano_data(data)
    distribuicao = P.distribuir_valor(valor, carregar_potes(mes=m_rec, ano=a_rec))
    try:
        db.registrar_distribuicao_receita(lancamento_id, distribuicao)
    except Exception as ex:
        raise P.ErroPotes([_mensagem_banco(ex)]) from ex
    return distribuicao
