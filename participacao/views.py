from django.http import HttpResponse
from .models import Participante
from django.contrib import messages
from django.shortcuts import render, redirect

from .admin import sincronizar_clientes

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.messages import constants as message_constants
from .models import Participante
from .admin import sincronizar_clientes

def sincronizar_clientes_view(request):
    if request.method == 'POST':
        # Obtém todos os participantes para sincronizar
        participantes = Participante.objects.all()  # Ou aplique filtros conforme necessário
        
        # Chama a função de sincronização passando o objeto admin
        class DummyAdmin:
            def message_user(self, request, message, level=message_constants.INFO):
                messages.add_message(request, level, message)

        sincronizar_clientes(DummyAdmin(), request, participantes)
        
        return redirect('home')  # Redireciona para a página inicial após a sincronização

    return render(request, 'participacao/sincronizar.html')  # Renderiza uma página, se necessário

def participar_sorteio(request):
    canal = request.GET.get('canal')
    id_externo = request.GET.get('id_externo')

    # Verifica se os parâmetros estão presentes
    if canal and id_externo:
        if request.method == 'POST':
            # Tenta criar a participação
            participante, created = Participante.objects.get_or_create(canal=canal, id_externo=id_externo)

            # Verifica se a participação foi criada ou já existia
            if created:
                mensagem = 'Participação confirmada com sucesso!'
            else:
                mensagem = 'Você já possui participação neste canal.'

            return render(request, 'participacao/confirmacao.html', {
                'canal': canal,
                'id_externo': id_externo,
                'mensagem': mensagem
            })
        
        # Renderiza a página com o botão "Participar"
        return render(request, 'participacao/confirmacao.html', {
            'canal': canal,
            'id_externo': id_externo
        })
    
    # Retorna erro se os parâmetros não forem válidos
    return HttpResponse("Erro: Parâmetros inválidos ou ausentes.")
