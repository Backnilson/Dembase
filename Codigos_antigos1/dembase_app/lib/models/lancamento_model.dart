class LancamentoModel {
  final String id;
  final String perfilId;
  final String tipo; // Receita, Despesa
  final String subtipo;
  final String formaMovimentacao;
  final String? contaId;
  final String? categoriaId;
  final String? destinoId;
  final double valor;
  final DateTime data;
  final int? hora;
  final String descricao;
  final String status;
  final String? regra; // Essencial, Estilo de Vida, Investimento (50/30/20)
  final int? parcelaAtual;
  final int? totalParcelas;
  final String? fatura;
  final DateTime? criadoEm;
  final DateTime? atualizadoEm;
  
  // Names of related entities for display (from joins)
  final String? contaNome;
  final String? categoriaNome;
  final String? destinoNome;

  LancamentoModel({
    required this.id,
    required this.perfilId,
    required this.tipo,
    required this.subtipo,
    required this.formaMovimentacao,
    this.contaId,
    this.categoriaId,
    this.destinoId,
    required this.valor,
    required this.data,
    this.hora,
    required this.descricao,
    required this.status,
    this.regra,
    this.parcelaAtual,
    this.totalParcelas,
    this.fatura,
    this.criadoEm,
    this.atualizadoEm,
    this.contaNome,
    this.categoriaNome,
    this.destinoNome,
  });

  factory LancamentoModel.fromJson(Map<String, dynamic> json) {
    return LancamentoModel(
      id: json['id'] as String,
      perfilId: json['perfil_id'] as String,
      tipo: json['tipo'] as String,
      subtipo: json['subtipo'] as String,
      formaMovimentacao: json['forma_movimentacao'] as String,
      contaId: json['conta_id'] as String?,
      categoriaId: json['categoria_id'] as String?,
      destinoId: json['destino_id'] as String?,
      valor: (json['valor'] as num).toDouble(),
      data: DateTime.parse(json['data'] as String),
      hora: json['hora'] as int?,
      descricao: json['descricao'] as String,
      status: json['status'] as String,
      regra: json['regra'] as String?,
      parcelaAtual: json['parcela_atual'] as int?,
      totalParcelas: json['total_parcelas'] as int?,
      fatura: json['fatura'] as String?,
      criadoEm: json['criado_em'] != null ? DateTime.parse(json['criado_em'] as String) : null,
      atualizadoEm: json['atualizado_em'] != null ? DateTime.parse(json['atualizado_em'] as String) : null,
      contaNome: json['contas']?['nome'] as String?,
      categoriaNome: json['categorias']?['nome'] as String?,
      destinoNome: json['destinos']?['nome'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'perfil_id': perfilId,
      'tipo': tipo,
      'subtipo': subtipo,
      'forma_movimentacao': formaMovimentacao,
      'conta_id': contaId,
      'categoria_id': categoriaId,
      'destino_id': destinoId,
      'valor': valor,
      'data': data.toIso8601String().split('T').first,
      'hora': hora,
      'descricao': descricao,
      'status': status,
      'regra': regra,
      'parcela_atual': parcelaAtual,
      'total_parcelas': totalParcelas,
      'fatura': fatura,
      'criado_em': criadoEm?.toIso8601String(),
      'atualizado_em': atualizadoEm?.toIso8601String(),
    };
  }

  LancamentoModel copyWith({
    String? id,
    String? perfilId,
    String? tipo,
    String? subtipo,
    String? formaMovimentacao,
    String? contaId,
    String? categoriaId,
    String? destinoId,
    double? valor,
    DateTime? data,
    int? hora,
    String? descricao,
    String? status,
    String? regra,
    int? parcelaAtual,
    int? totalParcelas,
    String? fatura,
    DateTime? criadoEm,
    DateTime? atualizadoEm,
    String? contaNome,
    String? categoriaNome,
    String? destinoNome,
  }) {
    return LancamentoModel(
      id: id ?? this.id,
      perfilId: perfilId ?? this.perfilId,
      tipo: tipo ?? this.tipo,
      subtipo: subtipo ?? this.subtipo,
      formaMovimentacao: formaMovimentacao ?? this.formaMovimentacao,
      contaId: contaId ?? this.contaId,
      categoriaId: categoriaId ?? this.categoriaId,
      destinoId: destinoId ?? this.destinoId,
      valor: valor ?? this.valor,
      data: data ?? this.data,
      hora: hora ?? this.hora,
      descricao: descricao ?? this.descricao,
      status: status ?? this.status,
      regra: regra ?? this.regra,
      parcelaAtual: parcelaAtual ?? this.parcelaAtual,
      totalParcelas: totalParcelas ?? this.totalParcelas,
      fatura: fatura ?? this.fatura,
      criadoEm: criadoEm ?? this.criadoEm,
      atualizadoEm: atualizadoEm ?? this.atualizadoEm,
      contaNome: contaNome ?? this.contaNome,
      categoriaNome: categoriaNome ?? this.categoriaNome,
      destinoNome: destinoNome ?? this.destinoNome,
    );
  }
}
