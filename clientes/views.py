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
from django.db import transaction, connection
from django.db.utils import OperationalError
import logging

import random
from django.db.models import Count

logger = logging.getLogger(__name__)

def admin_required(user):
    return user.is_superuser

def marketing_required(user):
    return user.is_authenticated and user.groups.filter(name='marketing').exists()

@user_passes_test(admin_required, login_url='/admin/login/')
def lista_clientes(request):
    try:
        # Verificar e reabrir conexão se necessário
        try:
            connection.ensure_connection()
        except OperationalError:
            connection.close()
            connection.ensure_connection()
        
        configuracao = Configuracao.objects.first()
        if not configuracao:
            configuracao = Configuracao.objects.create()
        
        if request.method == 'POST' and configuracao and configuracao.botao_ativo:
            quantidade_exibida = configuracao.quantidade_exibida
            
            # Usar transação para garantir atomicidade
            try:
                with transaction.atomic():
                    # Resetar o status de sorteio de todos os clientes (otimizado)
                    Cliente.objects.filter(sorteado=True).update(sorteado=False)

                    # Obter todos os clientes com CPFs únicos (otimizado)
                    clientes_unicos = Cliente.objects.values('id', 'nome', 'cpf', 'ticket', 'cidade').annotate(count=Count('cpf')).filter(count=1).order_by('id')
                    
                    # Converter para lista e embaralhar
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
                    max_tentativas = 10
                    
                    while len(clientes_sorteados) < quantidade_exibida and tentativas < max_tentativas:
                        tentativas += 1
                        random.shuffle(clientes_unicos)
                        clientes_sorteados = selecionar_clientes_unicos(clientes_unicos, quantidade_exibida)
                    
                    if len(clientes_sorteados) < quantidade_exibida:
                        # Caso não tenha conseguido selecionar a quantidade desejada, selecionar o restante do total possível
                        for cliente in clientes_unicos:
                            if cliente not in clientes_sorteados:
                                clientes_sorteados.append(cliente)
                            if len(clientes_sorteados) == quantidade_exibida:
                                break
                    
                    # Atualizar o status de sorteio dos novos sorteados
                    ids_sorteados = [cliente['id'] for cliente in clientes_sorteados]
                    if ids_sorteados:
                        Cliente.objects.filter(id__in=ids_sorteados).update(sorteado=True)

                    # Recarregar os clientes sorteados com os dados completos
                    clientes_sorteados = Cliente.objects.filter(id__in=ids_sorteados)
            except OperationalError as e:
                logger.error(f"Erro de conexão com o banco de dados: {e}")
                messages.error(request, "Erro ao conectar com o banco de dados. Tente novamente.")
                # Tentar recarregar a conexão
                connection.close()
                clientes_sorteados = Cliente.objects.filter(sorteado=True)
            except Exception as e:
                logger.error(f"Erro inesperado durante o sorteio: {e}")
                messages.error(request, f"Erro ao realizar o sorteio: {str(e)}")
                clientes_sorteados = Cliente.objects.filter(sorteado=True)
        else:
            # Se não houver sorteio, mostrar todos os clientes sorteados
            try:
                clientes_sorteados = Cliente.objects.filter(sorteado=True)
            except OperationalError:
                connection.close()
                clientes_sorteados = Cliente.objects.filter(sorteado=True)
        
        config = ConfiguracaoSite.objects.first() 
        context = {
            'clientes': clientes_sorteados,
            'botao_ativo': configuracao.botao_ativo if configuracao else False,
            'config': config
        }
        return render(request, 'clientes/lista_clientes.html', context)
    except OperationalError as e:
        logger.error(f"Erro de conexão com o banco de dados: {e}")
        messages.error(request, "Erro ao conectar com o banco de dados. Por favor, verifique a conexão e tente novamente.")
        # Tentar recarregar a conexão
        try:
            connection.close()
            connection.ensure_connection()
            configuracao = Configuracao.objects.first()
            clientes_sorteados = Cliente.objects.filter(sorteado=True) if Cliente.objects.exists() else []
        except:
            clientes_sorteados = []
            configuracao = None
        
        config = ConfiguracaoSite.objects.first() if ConfiguracaoSite.objects.exists() else None
        context = {
            'clientes': clientes_sorteados,
            'botao_ativo': False,
            'config': config
        }
        return render(request, 'clientes/lista_clientes.html', context)
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        messages.error(request, f"Erro inesperado: {str(e)}")
        return render(request, 'clientes/lista_clientes.html', {
            'clientes': [],
            'botao_ativo': False,
            'config': None
        })
    
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
        'config': config,
        'user': request.user
    })
