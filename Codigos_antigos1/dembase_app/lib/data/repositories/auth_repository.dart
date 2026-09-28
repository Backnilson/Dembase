import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../services/supabase_service.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  final supabaseService = ref.watch(supabaseServiceProvider);
  return AuthRepository(supabaseService);
});

class AuthRepository {
  final SupabaseService _supabaseService;

  AuthRepository(this._supabaseService);

  Future<void> signUp({required String email, required String password, required String nome}) async {
    try {
      await _supabaseService.signUp(email: email, password: password, nome: nome);
    } on AuthException catch (e) {
      throw _translateAuthException(e);
    } catch (e) {
      throw Exception('Ocorreu um erro inesperado. Tente novamente mais tarde.');
    }
  }

  Future<void> signIn({required String email, required String password}) async {
    try {
      await _supabaseService.signIn(email: email, password: password);
    } on AuthException catch (e) {
      throw _translateAuthException(e);
    } catch (e) {
      throw Exception('Ocorreu um erro inesperado. Tente novamente mais tarde.');
    }
  }

  Future<void> signOut() async {
    try {
      await _supabaseService.signOut();
    } catch (e) {
      throw Exception('Erro ao sair da conta.');
    }
  }

  Exception _translateAuthException(AuthException e) {
    switch (e.message) {
      case 'Invalid login credentials':
        return Exception('Credenciais inválidas. Verifique seu e-mail e senha.');
      case 'User already registered':
        return Exception('Este usuário já está cadastrado.');
      case 'Password should be at least 6 characters':
        return Exception('A senha deve ter pelo menos 6 caracteres.');
      default:
        return Exception(e.message);
    }
  }
}
