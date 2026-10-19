"""
=============================================================================
DemBase v3 — core/lancamento_state.py
Máquina de estado do formulário de lançamentos e regras de negócio/cascata.
Sem dependências de UI (Flet), 100% testável via terminal.
=============================================================================
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Tuple


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
    is_fixa: bool = False
    is_repetir: bool = False
    frequencia: str = "mensal"
    quantidade: int = 1  # Parcelas no crédito ou repetições no Repetir
    mais_detalhes_aberto: bool = False
    lancamento_id: Optional[str] = None
    serie_id: Optional[str] = None
    recorrente_id: Optional[str] = None

    def __post_init__(self):
        # Se for inicializado com data futura e status_manual=False, ajusta status para Pendente
        if not self.status_manual and self.data_selecionada > date.today():
            self.status_pago = False

    def atualizar_data(self, nova_data: date):
        self.data_selecionada = nova_data
        # Regra 6: Apenas se o usuário NÃO tiver tocado manualmente no Switch
        if not self.status_manual:
            self.status_pago = (nova_data <= date.today())

    def tocar_switch_status(self, novo_status: bool):
        self.status_pago = novo_status
        self.status_manual = True

    def mudar_tipo(self, novo_tipo: str):
        self.tipo = novo_tipo
        self.subtipo = None
        self.categoria_id = None
        self.subcategoria_id = None

        if self.tipo == "Transferencia":
            self.regra = None
            self.is_fixa = False
            self.is_repetir = False
            self.status_pago = True
            if self.forma_movimentacao == "Credito":
                self.forma_movimentacao = "Pix"
        elif self.tipo == "Receita":
            self.regra = None
            if self.forma_movimentacao == "Credito":
                self.forma_movimentacao = "Pix"
        elif self.tipo == "Despesa":
            if not self.regra:
                self.regra = "Essencial"

    def mudar_forma(self, nova_forma: str):
        self.forma_movimentacao = nova_forma
        if nova_forma == "Credito":
            # Decisão 2: Crédito só tem Parcelado, sem Fixa/Repetir
            self.is_fixa = False
            self.is_repetir = False
        else:
            self.cartao_id = None
            if not self.is_repetir:
                self.quantidade = 1

    def mudar_categoria(self, nova_cat_id: Optional[str]):
        self.categoria_id = nova_cat_id
        self.subcategoria_id = None

    def alternar_fixa(self, ativo: bool):
        self.is_fixa = ativo
        if ativo:
            self.is_repetir = False

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
        if self.tipo == "Transferencia":
            return "unica"
        if self.tipo == "Despesa" and self.forma_movimentacao == "Credito":
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

        if self.tipo == "Transferencia":
            if not self.conta_id:
                return False, "Selecione a conta de origem."
            if not self.destino_id:
                return False, "Selecione a conta de destino."
            if self.conta_id == self.destino_id:
                return False, "A conta de origem e destino não podem ser iguais."
            return True, None

        if self.tipo == "Despesa" and self.forma_movimentacao == "Credito":
            if not self.cartao_id:
                return False, "Selecione o cartão de crédito."
            if not self.categoria_id:
                return False, "Selecione uma categoria."
            if not self.regra:
                return False, "Classifique a despesa na regra 50/30/20."
            return True, None

        if not self.conta_id:
            return False, "Selecione uma conta."

        if not self.categoria_id:
            return False, "Selecione uma categoria."

        if self.tipo == "Despesa" and not self.regra:
            return False, "Classifique a despesa na regra 50/30/20."

        if self.is_repetir and self.quantidade < 2:
            return False, "Informe no mínimo 2 repetições."

        return True, None
