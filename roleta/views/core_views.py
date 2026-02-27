from django.shortcuts import render, redirect

def roleta_index(request):
    """
    Renders the plain HTML frontend without any context logic.
    All dynamic data is fetched via JS from /api/init-dados/
    """
    return render(request, 'roleta/index_frontend.html')

def roleta_logout(request):
    """
    Limpa os dados de autenticação da sessão e redireciona para o início.
    """
    keys_to_clear = [
        'auth_membro_id', 'auth_membro_nome', 'auth_membro_cpf', 
        'otp_validado', 'sorteado_pos', 'nome_ganhador', 'premio_nome', 
        'saldo_atual', 'erro_sorteio'
    ]
    for key in keys_to_clear:
        request.session.pop(key, None)
    
    request.session.modified = True
    return redirect('roleta_index')
