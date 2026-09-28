import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

final supabaseServiceProvider = Provider<SupabaseService>((ref) {
  return SupabaseService(Supabase.instance.client);
});

class SupabaseService {
  final SupabaseClient _client;

  SupabaseService(this._client);

  // Auth operations
  Future<AuthResponse> signUp({required String email, required String password, required String nome}) async {
    return await _client.auth.signUp(
      email: email,
      password: password,
      data: {'nome': nome},
    );
  }

  Future<AuthResponse> signIn({required String email, required String password}) async {
    return await _client.auth.signInWithPassword(email: email, password: password);
  }

  Future<void> signOut() async {
    await _client.auth.signOut();
  }

  Session? get currentSession => _client.auth.currentSession;
  User? get currentUser => _client.auth.currentUser;
  Stream<AuthState> get authStateChanges => _client.auth.onAuthStateChange;

  // Profile CRUD
  Future<Map<String, dynamic>> readProfile() async {
    final user = currentUser;
    if (user == null) throw Exception('Usuário não autenticado');
    return await _client.from('perfis').select().eq('id', user.id).single();
  }

  Future<void> updateProfile(Map<String, dynamic> data) async {
    final user = currentUser;
    if (user == null) throw Exception('Usuário não autenticado');
    await _client.from('perfis').update(data).eq('id', user.id);
  }

  // Contas CRUD
  Future<Map<String, dynamic>> createConta(Map<String, dynamic> data) async {
    return await _client.from('contas').insert(data).select().single();
  }

  Future<List<Map<String, dynamic>>> listContas() async {
    return await _client.from('contas').select();
  }

  Future<void> updateConta(String id, Map<String, dynamic> data) async {
    await _client.from('contas').update(data).eq('id', id);
  }

  Future<void> deleteConta(String id) async {
    await _client.from('contas').delete().eq('id', id);
  }

  // Categorias CRUD
  Future<Map<String, dynamic>> createCategoria(Map<String, dynamic> data) async {
    return await _client.from('categorias').insert(data).select().single();
  }

  Future<List<Map<String, dynamic>>> listCategorias() async {
    return await _client.from('categorias').select();
  }

  Future<void> updateCategoria(String id, Map<String, dynamic> data) async {
    await _client.from('categorias').update(data).eq('id', id);
  }

  Future<void> deleteCategoria(String id) async {
    await _client.from('categorias').delete().eq('id', id);
  }

  // Destinos CRUD
  Future<Map<String, dynamic>> createDestino(Map<String, dynamic> data) async {
    return await _client.from('destinos').insert(data).select().single();
  }

  Future<List<Map<String, dynamic>>> listDestinos() async {
    return await _client.from('destinos').select();
  }

  Future<void> updateDestino(String id, Map<String, dynamic> data) async {
    await _client.from('destinos').update(data).eq('id', id);
  }

  Future<void> deleteDestino(String id) async {
    await _client.from('destinos').delete().eq('id', id);
  }

  // Lancamentos CRUD
  Future<Map<String, dynamic>> createLancamento(Map<String, dynamic> data) async {
    return await _client.from('lancamentos').insert(data).select().single();
  }

  Future<List<Map<String, dynamic>>> listLancamentos({DateTime? dataInicio, DateTime? dataFim, Map<String, dynamic>? filtros}) async {
    var query = _client.from('lancamentos').select('*, contas(nome), categorias(nome), destinos(nome)');
    
    if (dataInicio != null) {
      query = query.gte('data', dataInicio.toIso8601String());
    }
    if (dataFim != null) {
      query = query.lte('data', dataFim.toIso8601String());
    }
    
    if (filtros != null) {
      filtros.forEach((key, value) {
        query = query.eq(key, value);
      });
    }
    
    return await query.order('data', ascending: false);
  }

  Future<void> updateLancamento(String id, Map<String, dynamic> data) async {
    await _client.from('lancamentos').update(data).eq('id', id);
  }

  Future<void> deleteLancamento(String id) async {
    await _client.from('lancamentos').delete().eq('id', id);
  }

  // Dashboard RPC
  Future<Map<String, dynamic>> getDashboardTotals() async {
    final response = await _client.rpc('get_financial_totals');
    return response as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> getDashboardTotals50_30_20() async {
    final response = await _client.rpc('get_regra_50_30_20_summary');
    return response as Map<String, dynamic>;
  }
}
