"""
=============================================================================
DemBase v3 — core/lancamento_state.py
Máquina de estado do formulário de lançamentos e regras de negócio/cascata.
Sem dependências de UI (Flet), 100% testável via terminal.
=============================================================================
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Tuple


def _norm(texto: Optional[str]) -> str:
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(texto))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def is_credito_str(forma: Optional[str]) -> bool:
    return "cred" in _norm(forma)


def is_transferencia_str(tipo: Optional[str]) -> bool:
    return "trans" in _norm(tipo)


def is_despesa_str(tipo: Optional[str]) -> bool:
    return "desp" in _norm(tipo)


def is_receita_str(tipo: Optional[str]) -> bool:
    return "rec" in _norm(tipo)


@dataclass
class LancamentoFormState:
    tipo: str = "Despesa"  # "Despesa", "Receita", "Transferencia"
    valor: float = 0.0
    data_selecionada: date = field(default_factory=date.today)
    hora: int = 12
    status_pago: bool = True
    status_manual: bool = False  # True quando o usuário toca no Switch; data nunca mais o sobrescreve
    descricao: str = ""
    forma_movimentacao: str = "Pix"
    conta_id: Optional[str] = None
    cartao_id: Optional[str] = None
    destino_id: Optional[str] = None
    categoria_id: Optional[str] = None
    subcategoria_id: Optional[str] = None
    subtipo: Optional[str] = None
    regra: Optional[str] = "Essencial"  # Apenas para Despesa
    pote_id: Optional[str] = None       # Sistema dinâmico de 6 potes
    caixinha_id: Optional[str] = None   # Vínculo opcional com Caixinha de Teto
    membro_id: Optional[str] = None     # Vínculo com Perfil Familiar (Eu, Ela & Nós)
    is_fixa: bool = False
    is_repetir: bool = False
    frequencia: str = "mensal"
    fatura_id: Optional[str] = None     # Seleção manual de fatura sobrescrevendo fechamento
    fatura_manual_mes: Optional[int] = None
    fatura_manual_ano: Optional[int] = None
    modo_calculo_parcela: str = "total"  # "total" (divide) ou "parcela" (multiplica)
    valor_parcela_input: float = 0.0     # Armazena o valor unitário da parcela quando no modo "parcela"
    quantidade: int = 1
    parcela_atual: Optional[int] = None
    total_parcelas_original: Optional[int] = None
    fatura_id_original: Optional[str] = None
    serie_id: Optional[str] = None
    recorrente_id: Optional[str] = None
    lancamento_id: Optional[str] = None
    mais_detalhes_aberto: bool = False

    def definir_valor_total(self, total: float):
        self.valor = max(0.0, float(total or 0.0))
        qtd = max(1, self.quantidade)
        self.valor_parcela_input = self.valor / qtd

    def definir_valor_parcela(self, parcela: float):
        self.valor_parcela_input = max(0.0, float(parcela or 0.0))
        qtd = max(1, self.quantidade)
        self.valor = self.valor_parcela_input * qtd

    def obter_valor_parcela(self) -> float:
        qtd = max(1, self.quantidade)
        return self.valor / qtd if self.valor > 0 else 0.0

    def obter_valor_exibicao_input(self) -> float:
        """Retorna o valor que deve ser exibido no campo txt_valor conforme o modo."""
        if self.eh_credito and not self.is_fixa and self.modo_calculo_parcela == "parcela" and self.quantidade > 1:
            return self.obter_valor_parcela()
        return self.valor

    def __post_init__(self):
        # Normaliza tipo para evitar divergências ("Transferência" -> "Transferencia")
        if is_transferencia_str(self.tipo):
            self.tipo = "Transferencia"
        elif is_receita_str(self.tipo):
            self.tipo = "Receita"
        else:
            self.tipo = "Despesa"

        # Se for inicializado com data futura e status_manual=False, ajusta status para Pendente
        if not self.status_manual and self.data_selecionada > date.today():
            self.status_pago = False

    @property
    def eh_credito(self) -> bool:
        return is_despesa_str(self.tipo) and is_credito_str(self.forma_movimentacao)

    @property
    def eh_transferencia(self) -> bool:
        return is_transferencia_str(self.tipo)

    @property
    def eh_despesa(self) -> bool:
        return is_despesa_str(self.tipo)

    @property
    def eh_receita(self) -> bool:
        return is_receita_str(self.tipo)

    @property
    def is_compra_parcelada(self) -> bool:
        return bool(
            self.eh_credito
            and not self.is_fixa
            and not self.recorrente_id
            and (
                (self.quantidade and self.quantidade > 1)
                or (self.total_parcelas_original and self.total_parcelas_original > 1)
                or bool(self.parcela_atual)
            )
        )

    @property
    def fatura_foi_alterada(self) -> bool:
        if not self.fatura_id_original and not self.fatura_id:
            return False
        return str(self.fatura_id_original or "").strip() != str(self.fatura_id or "").strip()

    @property
    def quantidade_parcelas_alterada(self) -> bool:
        if not self.total_parcelas_original:
            return False
        return int(self.quantidade) != int(self.total_parcelas_original)

    def atualizar_data(self, nova_data: date):
        self.data_selecionada = nova_data
        # Regra 6: Apenas se o usuário NÃO tiver tocado manualmente no Switch
        if not self.status_manual:
            self.status_pago = (nova_data <= date.today())

    def tocar_switch_status(self, novo_status: bool):
        self.status_pago = novo_status
        self.status_manual = True

    def mudar_tipo(self, novo_tipo: str):
        if is_transferencia_str(novo_tipo):
            self.tipo = "Transferencia"
        elif is_receita_str(novo_tipo):
            self.tipo = "Receita"
        else:
            self.tipo = "Despesa"

        self.subtipo = None
        self.categoria_id = None
        self.subcategoria_id = None

        if self.eh_transferencia:
            self.regra = None
            self.is_fixa = False
            self.is_repetir = False
            self.status_pago = True
            if is_credito_str(self.forma_movimentacao):
                self.forma_movimentacao = "Pix"
        elif self.eh_receita:
            self.regra = None
            if is_credito_str(self.forma_movimentacao):
                self.forma_movimentacao = "Pix"
        elif self.eh_despesa:
            if not self.regra:
                self.regra = "Essencial"

    def mudar_forma(self, nova_forma: str):
        self.forma_movimentacao = nova_forma
        if is_credito_str(nova_forma):
            # Crédito suporta compras parceladas e recorrência contínua (assinaturas).
            # Repetições avulsas com término não se aplicam a cartão.
            self.is_repetir = False
        else:
            self.cartao_id = None
            if not self.is_repetir and not self.is_fixa:
                self.quantidade = 1

    def mudar_categoria(self, nova_cat_id: Optional[str]):
        self.categoria_id = nova_cat_id
        self.subcategoria_id = None

    def alternar_fixa(self, ativo: bool):
        self.is_fixa = ativo
        if ativo:
            self.is_repetir = False
            if self.eh_credito:
                self.quantidade = 1

    def alternar_repetir(self, ativo: bool):
        self.is_repetir = ativo
        if ativo:
            self.is_fixa = False
            if self.quantidade <= 1:
                self.quantidade = 2
        else:
            self.quantidade = 1

    def modo_recorrencia(self) -> str:
        """Determina o modo a ser gravado no banco."""
        if self.eh_transferencia:
            return "unica"
        if self.eh_credito:
            if self.is_fixa:
                return "fixa"
            return "parcelada" if self.quantidade > 1 else "unica"
        if self.is_fixa:
            return "fixa"
        if self.is_repetir and self.quantidade > 1:
            return "repetida"
        return "unica"

    def validar(self) -> Tuple[bool, Optional[str]]:
        """Validações de preenchimento."""
        if self.valor <= 0:
            return False, "Informe um valor maior que zero."

        if self.eh_transferencia:
            if not self.conta_id:
                return False, "Selecione a conta de origem."
            if not self.destino_id:
                return False, "Selecione a conta de destino."
            if self.conta_id == self.destino_id:
                return False, "A conta de origem e destino não podem ser iguais."
            return True, None

        if self.eh_credito:
            if not self.cartao_id:
                return False, "Selecione o cartão de crédito."
            if not self.categoria_id:
                return False, "Selecione uma categoria."
            if not (self.pote_id or self.regra):
                return False, "Selecione o pote da despesa."
            return True, None

        if not self.conta_id:
            return False, "Selecione uma conta."

        if not self.categoria_id:
            return False, "Selecione uma categoria."

        if self.eh_despesa and not (self.pote_id or self.regra):
            return False, "Selecione o pote da despesa."

        if self.is_repetir and self.quantidade < 2:
            return False, "Informe no mínimo 2 repetições."

        return True, None
