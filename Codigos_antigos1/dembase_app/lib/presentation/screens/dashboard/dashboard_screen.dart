import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:dembase_app/core/theme/app_theme.dart';
import 'package:dembase_app/core/constants/app_constants.dart';
import 'package:dembase_app/data/services/supabase_service.dart';
import 'package:dembase_app/presentation/widgets/kpi_card.dart';
import 'package:dembase_app/presentation/widgets/date_filter_bar.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  bool _isLoading = true;
  String _userName = 'Usuário';
  double _receitas = 0.0;
  double _despesas = 0.0;
  double _saldo = 0.0;
  
  double _gastoEssencial = 0.0;
  double _gastoEstilo = 0.0;
  double _gastoInvestimento = 0.0;

  DateTime _startDate = DateTime.now().subtract(const Duration(days: 30));
  DateTime _endDate = DateTime.now();

  late String _motivationalQuote;

  @override
  void initState() {
    super.initState();
    // Seleciona frase motivacional aleatória criando uma cópia mutável da lista const
    final frases = List<String>.from(AppConstants.frases);
    _motivationalQuote = (frases..shuffle()).first;
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final supabaseService = ref.read(supabaseServiceProvider);

      // Carrega perfil do usuário
      try {
        final perfil = await supabaseService.readProfile();
        _userName = perfil['nome'] ?? 'Usuário';
      } catch (_) {
        // Tenta metadata do auth como fallback
        final user = supabaseService.currentUser;
        _userName = user?.userMetadata?['full_name'] ?? 
                    user?.userMetadata?['nome'] ?? 'Usuário';
      }

      // Carrega totais financeiros via RPC
      try {
        final totais = await supabaseService.getDashboardTotals();
        _receitas = (totais['receitas'] as num?)?.toDouble() ?? 0.0;
        _despesas = (totais['despesas'] as num?)?.toDouble() ?? 0.0;
        _saldo = (totais['saldo'] as num?)?.toDouble() ?? 0.0;
      } catch (_) {
        _receitas = 0.0;
        _despesas = 0.0;
        _saldo = 0.0;
      }

      // Carrega resumo da Regra 50/30/20 via RPC
      try {
        final regra = await supabaseService.getDashboardTotals50_30_20();
        _gastoEssencial = ((regra['essencial'] as Map?)?['gasto'] as num?)?.toDouble() ?? 0.0;
        _gastoEstilo = ((regra['estilo_vida'] as Map?)?['gasto'] as num?)?.toDouble() ?? 0.0;
        _gastoInvestimento = ((regra['investimento'] as Map?)?['gasto'] as num?)?.toDouble() ?? 0.0;
      } catch (_) {
        _gastoEssencial = 0.0;
        _gastoEstilo = 0.0;
        _gastoInvestimento = 0.0;
      }

    } catch (e) {
      debugPrint('Erro ao carregar dados: $e');
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  void _onDateRangeChanged(DateTime start, DateTime end) {
    _startDate = start;
    _endDate = end;
    _loadData();
  }

  void _logout() async {
    try {
      final supabaseService = ref.read(supabaseServiceProvider);
      await supabaseService.signOut();
      if (mounted) context.go('/login');
    } catch (e) {
      debugPrint('Erro ao sair: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B0F19),
      body: _isLoading 
        ? const Center(child: CircularProgressIndicator(color: Color(0xFF10B981)))
        : SafeArea(
            child: LayoutBuilder(
              builder: (context, constraints) {
                final isDesktop = constraints.maxWidth > 900;
                return SingleChildScrollView(
                  padding: EdgeInsets.symmetric(
                    horizontal: isDesktop ? constraints.maxWidth * 0.1 : 16,
                    vertical: 24,
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildAppBar(),
                      const SizedBox(height: 32),
                      _buildWelcomeSection(),
                      const SizedBox(height: 24),
                      _buildKpiCards(isDesktop),
                      const SizedBox(height: 32),
                      DateFilterBar(onDateRangeChanged: _onDateRangeChanged),
                      const SizedBox(height: 32),
                      if (isDesktop)
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(child: _buildRegra503020()),
                            const SizedBox(width: 24),
                            Expanded(child: _buildChartsPlaceholder()),
                          ],
                        )
                      else ...[
                        _buildRegra503020(),
                        const SizedBox(height: 32),
                        _buildChartsPlaceholder(),
                      ],
                      const SizedBox(height: 32),
                      _buildQuickActions(),
                      const SizedBox(height: 32),
                    ],
                  ),
                );
              }
            ),
          ),
    );
  }

  Widget _buildAppBar() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: const Color(0xFF151D2C),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF334155)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: const Color(0xFF10B981).withOpacity(0.12),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.account_balance_wallet, color: Color(0xFF10B981)),
              ),
              const SizedBox(width: 12),
              const Text(
                'DemBase',
                style: TextStyle(
                  color: Color(0xFFF8FAFC),
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(
                  color: const Color(0xFF1E293B),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.person_outline, color: Color(0xFF94A3B8), size: 16),
                    const SizedBox(width: 8),
                    Text(
                      _userName,
                      style: const TextStyle(color: Color(0xFFF8FAFC), fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 12),
              IconButton(
                icon: const Icon(Icons.logout, color: Color(0xFFEF4444)),
                onPressed: _logout,
                tooltip: 'Sair',
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildWelcomeSection() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Text(
                    'Olá, $_userName!',
                    style: const TextStyle(
                      color: Color(0xFFF8FAFC),
                      fontSize: 28,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  const SizedBox(width: 8),
                  const Icon(Icons.auto_awesome, color: Color(0xFF10B981), size: 24),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                '$_motivationalQuote',
                style: const TextStyle(
                  color: Color(0xFF94A3B8),
                  fontSize: 14,
                  fontStyle: FontStyle.italic,
                ),
              ),
            ],
          ),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF10B981).withOpacity(0.12),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: const Color(0xFF10B981).withOpacity(0.5)),
          ),
          child: Row(
            children: const [
              Icon(Icons.cloud_done_outlined, color: Color(0xFF10B981), size: 16),
              SizedBox(width: 8),
              Text(
                'Nuvem Supabase Conectada',
                style: TextStyle(
                  color: Color(0xFF10B981),
                  fontSize: 12,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildKpiCards(bool isDesktop) {
    return Wrap(
      spacing: 16,
      runSpacing: 16,
      alignment: WrapAlignment.spaceBetween,
      children: [
        SizedBox(
          width: isDesktop ? 300 : double.infinity,
          child: KpiCard(
            title: 'Total de Receitas',
            value: _receitas,
            icon: Icons.arrow_upward,
            accentColor: const Color(0xFF10B981),
            subtitle: 'No período selecionado',
          ),
        ),
        SizedBox(
          width: isDesktop ? 300 : double.infinity,
          child: KpiCard(
            title: 'Total de Despesas',
            value: _despesas,
            icon: Icons.arrow_downward,
            accentColor: const Color(0xFFEF4444),
            subtitle: 'No período selecionado',
          ),
        ),
        SizedBox(
          width: isDesktop ? 300 : double.infinity,
          child: KpiCard(
            title: 'Saldo em Conta',
            value: _saldo,
            icon: Icons.account_balance_wallet,
            accentColor: const Color(0xFF6366F1),
            subtitle: 'Atual',
          ),
        ),
      ],
    );
  }

  Widget _buildRegra503020() {
    double totalNet = _receitas;
    if (totalNet <= 0) totalNet = 1; 
    
    final percEssencial = (_gastoEssencial / totalNet) * 100;
    final percEstilo = (_gastoEstilo / totalNet) * 100;
    final percInvestimento = (_gastoInvestimento / totalNet) * 100;

    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: const Color(0xFF151D2C),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF334155)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: const [
              Icon(Icons.pie_chart_outline, color: Color(0xFFF8FAFC)),
              SizedBox(width: 8),
              Text(
                'Regra 50/30/20',
                style: TextStyle(
                  color: Color(0xFFF8FAFC),
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),
          _buildProgressRow('Essencial', _gastoEssencial, percEssencial, 50.0),
          const SizedBox(height: 16),
          _buildProgressRow('Estilo de Vida', _gastoEstilo, percEstilo, 30.0),
          const SizedBox(height: 16),
          _buildProgressRow('Investimento', _gastoInvestimento, percInvestimento, 20.0),
        ],
      ),
    );
  }

  Widget _buildProgressRow(String label, double value, double perc, double target) {
    Color barColor;
    if (perc <= target) {
      barColor = const Color(0xFF10B981); 
    } else if (perc <= target + 5) {
      barColor = const Color(0xFFF59E0B); 
    } else {
      barColor = const Color(0xFFEF4444); 
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              label,
              style: const TextStyle(color: Color(0xFF94A3B8), fontWeight: FontWeight.w500),
            ),
            Text(
              'R\$ ${value.toStringAsFixed(2)} (${perc.toStringAsFixed(1)}%)',
              style: TextStyle(color: barColor, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: perc / 100.0,
            backgroundColor: const Color(0xFF1E293B),
            color: barColor,
            minHeight: 8,
          ),
        ),
      ],
    );
  }

  Widget _buildChartsPlaceholder() {
    return Container(
      height: 250,
      width: double.infinity,
      decoration: BoxDecoration(
        color: const Color(0xFF1E293B),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: const Color(0xFF334155),
          style: BorderStyle.solid,
        ),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.bar_chart, color: Color(0xFF94A3B8), size: 48),
          const SizedBox(height: 16),
          const Text(
            'Fluxo de Caixa no Período',
            style: TextStyle(
              color: Color(0xFFF8FAFC),
              fontSize: 16,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Gráficos dinâmicos serão carregados aqui',
            style: TextStyle(
              color: const Color(0xFF94A3B8).withOpacity(0.8),
              fontSize: 12,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickActions() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Ações Rápidas',
          style: TextStyle(
            color: Color(0xFFF8FAFC),
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            ElevatedButton.icon(
              onPressed: () => context.push('/lancamentos'),
              icon: const Icon(Icons.add, color: Colors.white),
              label: const Text('Novo Lançamento', style: TextStyle(color: Colors.white)),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF10B981),
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
              ),
            ),
            _buildOutlinedButton('Contas', Icons.account_balance),
            _buildOutlinedButton('Categorias', Icons.category),
            _buildOutlinedButton('Destinos', Icons.place),
          ],
        ),
      ],
    );
  }

  Widget _buildOutlinedButton(String label, IconData icon) {
    return OutlinedButton.icon(
      onPressed: () {},
      icon: Icon(icon, color: const Color(0xFF94A3B8)),
      label: Text(label, style: const TextStyle(color: Color(0xFF94A3B8))),
      style: OutlinedButton.styleFrom(
        side: const BorderSide(color: Color(0xFF334155)),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
    );
  }
}
