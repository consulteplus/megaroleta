import csv
from django.shortcuts import render, redirect
from django.contrib import messages
import random
from .models import Cliente, Configuracao  # Certifique-se de que Configuracao está importado
from .forms import CSVUploadForm
from io import StringIO
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.decorators import user_passes_test
from .models import ConfiguracaoSite

import random
from django.db.models import Count

def admin_required(user):
    return user.is_superuser

@user_passes_test(admin_required, login_url='/admin/login/')
def lista_clientes(request):
    configuracao = Configuracao.objects.first()
    
    if request.method == 'POST' and configuracao and configuracao.botao_ativo:
        quantidade_exibida = configuracao.quantidade_exibida

        # Resetar o status de sorteio de todos os clientes
        Cliente.objects.all().update(sorteado=False)

        # Obter todos os clientes com CPFs únicos
        clientes_unicos = Cliente.objects.values('id', 'nome', 'cpf', 'ticket', 'cidade').annotate(count=Count('cpf')).filter(count=1)
        
        # Embaralhar a lista de clientes para aleatoriedade
        clientes_unicos = list(clientes_unicos)
        random.shuffle(clientes_unicos)
        
        # Função para garantir que não haja CPFs duplicados
        def selecionar_clientes_unicos(clientes, quantidade):
            selecionados = []
            cpfs = set()
            for cliente in clientes:
                if cliente['cpf'] not in cpfs:
                    selecionados.append(cliente)
                    cpfs.add(cliente['cpf'])
                if len(selecionados) == quantidade:
                    break
            return selecionados
        
        clientes_sorteados = []
        tentativas = 0
        max_tentativas = 10  # Número máximo de tentativas para evitar loops infinitos
        
        while len(clientes_sorteados) < quantidade_exibida and tentativas < max_tentativas:
            tentativas += 1
            random.shuffle(clientes_unicos)
            clientes_sorteados = selecionar_clientes_unicos(clientes_unicos, quantidade_exibida)
        
        if len(clientes_sorteados) < quantidade_exibida:
            # Caso não tenha conseguido selecionar a quantidade desejada, selecionar o restante do total possível
            clientes_sorteados = clientes_unicos[:quantidade_exibida]
        
        # Atualizar o status de sorteio dos novos sorteados
        Cliente.objects.filter(id__in=[cliente['id'] for cliente in clientes_sorteados]).update(sorteado=True)

        # Recarregar os clientes sorteados com os dados completos
        clientes_sorteados = Cliente.objects.filter(id__in=[cliente['id'] for cliente in clientes_sorteados])
    else:
        # Se não houver sorteio, mostrar todos os clientes sorteados
        clientes_sorteados = Cliente.objects.filter(sorteado=True)
    config = ConfiguracaoSite.objects.first() 
    context = {
        'clientes': clientes_sorteados,
        'botao_ativo': configuracao.botao_ativo if configuracao else False,
        'config': config
    }
    return render(request, 'clientes/lista_clientes.html', context)
    
def home_page(request):
    form = CPFForm()
    ganhadores = Cliente.objects.filter(sorteado=True)
    return render(request, 'clientes/home_page.html', {'form': form, 'ganhadores': ganhadores})

def home(request):
    cpf_query = request.GET.get('cpf', '')
    clientes = Cliente.objects.filter(cpf=cpf_query) if cpf_query else []
    ganhadores = Cliente.objects.filter(sorteado=True)
    config = ConfiguracaoSite.objects.first()  # Pegue a primeira configuração
    
    return render(request, 'clientes/home.html', {
        'clientes': clientes,
        'cpf_query': cpf_query,
        'ganhadores': ganhadores,
        'config': config
    })