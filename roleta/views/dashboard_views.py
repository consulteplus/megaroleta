from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from roleta.models import PremioRoleta, ParticipanteRoleta, RouletteAsset, RoletaConfig, MembroClube, NivelClube, RegraPontuacao, ExtratoPontuacao, Cidade
import csv
import json
from datetime import datetime, timedelta

def admin_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            return redirect('dashboard_home')
    else:
        form = AuthenticationForm()
    return render(request, 'roleta/dashboard/login.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_home(request):
    total_participantes = ParticipanteRoleta.objects.count()
    premios_restantes = PremioRoleta.objects.aggregate(total=Count('id', filter=Q(quantidade__gt=0)))['total']
    ultimos_ganhadores = ParticipanteRoleta.objects.order_by('-data_criacao')[:5]
    
    # 1. Funil de Conversao
    membros_iniciados = MembroClube.objects.count()
    membros_validados = MembroClube.objects.filter(validado=True).count()
    membros_jogadores = MembroClube.objects.filter(giros__isnull=False).distinct().count()
    
    # Validações caso 0 pra não dar divisão por zero
    tx_validacao = int((membros_validados / membros_iniciados * 100)) if membros_iniciados > 0 else 0
    tx_agressao = int((membros_jogadores / membros_iniciados * 100)) if membros_iniciados > 0 else 0

    # 2. Dados Gráfico Pizzas (Prêmios)
    premios_distribuicao = ParticipanteRoleta.objects.filter(status='ganhou').values('premio').annotate(total=Count('id')).order_by('-total')
    labels_premios = [p['premio'] for p in premios_distribuicao]
    data_premios = [p['total'] for p in premios_distribuicao]

    # 3. Dados Gráfico Linha (Giros dos últimos 7 dias)
    hoje = datetime.now().date()
    # Gera os últimos 7 dias
    dias_semana = [(hoje - timedelta(days=i)) for i in range(6, -1, -1)]
    
    # Agrupa do banco
    giros_por_dia_db = ParticipanteRoleta.objects.filter(data_criacao__date__gte=dias_semana[0]) \
        .annotate(dia=TruncDate('data_criacao')) \
        .values('dia') \
        .annotate(total=Count('id')) \
        .order_by('dia')
        
    giros_dict = {str(item['dia']): item['total'] for item in giros_por_dia_db}
    
    labels_giros = [d.strftime('%d/%m') for d in dias_semana]
    data_giros = [giros_dict.get(str(d), 0) for d in dias_semana] # preenche com zeros os dias vazios

    context = {
        'total': total_participantes,
        'premios_count': premios_restantes,
        'ganhadores': ultimos_ganhadores,
        
        # Funil
        'funil_iniciados': membros_iniciados,
        'funil_validados': membros_validados,
        'funil_jogadores': membros_jogadores,
        'tx_validacao': tx_validacao,
        'tx_jogadores': tx_agressao,
        
        # Charts - Converts to JSON strings for Javascript
        'chart_labels_premios': json.dumps(labels_premios),
        'chart_data_premios': json.dumps(data_premios),
        'chart_labels_giros': json.dumps(labels_giros),
        'chart_data_giros': json.dumps(data_giros),
    }
    return render(request, 'roleta/dashboard/home.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_premios(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'novo_premio':
            nome = request.POST.get('nome')
            cidades_ids = request.POST.getlist('cidades')
            quantidade = request.POST.get('quantidade', 0)
            probabilidade = request.POST.get('probabilidade', 1)
            posicoes = request.POST.get('posicoes', '1')
            
            premio = PremioRoleta.objects.create(
                nome=nome,
                quantidade=int(quantidade),
                probabilidade=int(probabilidade),
                posicoes=posicoes
            )
            
            if cidades_ids:
                premio.cidades_permitidas.set(cidades_ids)
                
            messages.success(request, f"Prêmio {nome} adicionado com sucesso!")
            
        elif action == 'excluir_premio':
            premio_id = request.POST.get('premio_id')
            if premio_id:
                get_object_or_404(PremioRoleta, id=premio_id).delete()
                messages.success(request, f"Prêmio removido com sucesso!")
                
        else:
            # Update
            premio_id = request.POST.get('premio_id')
            nova_qtd = request.POST.get('quantidade')
            novas_pos = request.POST.get('posicoes')
            nova_prob = request.POST.get('probabilidade', 1)
            cidades_ids = request.POST.getlist('cidades')
            
            if premio_id:
                premio = get_object_or_404(PremioRoleta, id=premio_id)
                premio.quantidade = int(nova_qtd)
                premio.probabilidade = int(nova_prob)
                if novas_pos:
                    premio.posicoes = novas_pos
                premio.save()
                
                premio.cidades_permitidas.set(cidades_ids)
                
                messages.success(request, f"Prêmio {premio.nome} atualizado!")
                
        return redirect('dashboard_premios')
        
    premios = PremioRoleta.objects.all().order_by('nome')
    cidades = Cidade.objects.filter(ativo=True).order_by('nome')
    return render(request, 'roleta/dashboard/premios.html', {'premios': premios, 'cidades': cidades})

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_participantes(request):
    """
    Shows unique members of the Clube MegaLink
    """
    if request.method == 'POST':
        membro_id = request.POST.get('membro_id')
        novo_saldo_input = request.POST.get('saldo')
        if membro_id and novo_saldo_input is not None:
            membro = get_object_or_404(MembroClube, id=membro_id)
            novo_saldo = int(novo_saldo_input)
            saldo_anterior = membro.saldo
            
            if novo_saldo != saldo_anterior:
                membro.saldo = novo_saldo
                membro.save()
                
                # Criar um extrato para registrar a mudança manual
                diferenca = novo_saldo - saldo_anterior
                regra_ajuste, _ = RegraPontuacao.objects.get_or_create(
                    gatilho='ajuste_manual_admin',
                    defaults={
                        'nome_exibicao': 'Ajuste Manual pelo Admin',
                        'pontos_saldo': 0,
                        'pontos_xp': 0,
                        'limite_por_membro': 0,
                        'ativo': True
                    }
                )
                
                ExtratoPontuacao.objects.create(
                    membro=membro,
                    regra=regra_ajuste,
                    pontos_saldo_ganhos=diferenca,
                    pontos_xp_ganhos=0,
                    descricao_extra=f"Ajuste manual de {saldo_anterior} para {novo_saldo}"
                )
                
            messages.success(request, f"Saldo de {membro.nome} atualizado.")
        return redirect('dashboard_participantes')

    q = request.GET.get('q', '')
    cidade = request.GET.get('cidade', '')
    
    membros = MembroClube.objects.all().order_by('-data_cadastro')
    
    if q:
        membros = membros.filter(Q(nome__icontains=q) | Q(cpf__icontains=q))
    if cidade:
        membros = membros.filter(cidade=cidade)
        
    # Fetch cities that have prizes defined
    todas_cidades = Cidade.objects.filter(ativo=True).values_list('nome', flat=True).order_by('nome')
    
    context = {
        'participantes': membros, # Keep 'participantes' key to minimize template changes
        'q': q,
        'cidade': cidade,
        'todas_cidades': sorted(list(todas_cidades))
    }
    return render(request, 'roleta/dashboard/participantes.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_extrato_membro(request, membro_id):
    """
    Shows the points history (ExtratoPontuacao) for a specific member
    """
    membro = get_object_or_404(MembroClube, id=membro_id)
    extrato = ExtratoPontuacao.objects.filter(membro=membro).order_by('-data_recebimento')
    
    return render(request, 'roleta/dashboard/extrato_membro.html', {'membro': membro, 'extrato': extrato})

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_giros(request):
    """
    Shows historical log of all roulette spins
    """
    q = request.GET.get('q', '')
    giros = ParticipanteRoleta.objects.all().order_by('-data_criacao')
    
    if q:
        giros = giros.filter(Q(nome__icontains=q) | Q(cpf__icontains=q) | Q(premio__icontains=q))
        
    return render(request, 'roleta/dashboard/giros.html', {'giros': giros, 'q': q})

@login_required
@user_passes_test(lambda u: u.is_staff)
def exportar_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="participantes_roleta.csv"'
    response.write(u'\ufeff'.encode('utf8')) # BOM for Excel

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Nome', 'CPF', 'Email', 'Telefone', 'Cidade', 'Bairro', 'Prêmio', 'Data'])

    for p in ParticipanteRoleta.objects.all():
        writer.writerow([p.nome, p.cpf, p.email, p.telefone, p.cidade, p.bairro, p.premio, p.data_criacao.strftime('%d/%m/%Y %H:%M')])

    return response

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_assets(request):
    if request.method == 'POST':
        asset_id = request.POST.get('asset_id')
        if asset_id:
            asset = get_object_or_404(RouletteAsset, id=asset_id)
            if 'delete' in request.POST:
                asset.delete()
            else:
                asset.ativo = not asset.ativo
                asset.save()
        else:
            tipo = request.POST.get('tipo')
            ordem = request.POST.get('ordem', 0)
            imagem = request.FILES.get('imagem')
            if imagem:
                # Update existing or create new
                RouletteAsset.objects.create(tipo=tipo, ordem=ordem, imagem=imagem)
        return redirect('dashboard_assets')

    frames = RouletteAsset.objects.filter(tipo='frame').order_by('ordem')
    outros = RouletteAsset.objects.exclude(tipo='frame')
    context = {
        'frames': frames,
        'outros': outros
    }
    return render(request, 'roleta/dashboard/assets.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_config(request):
    config, _ = RoletaConfig.objects.get_or_create(id=1)
    if request.method == 'POST':
        config.custo_giro = int(request.POST.get('custo_giro', 10))
        config.nome_clube = request.POST.get('nome_clube', 'Clube MegaLink')
        config.xp_por_giro = int(request.POST.get('xp_por_giro', 5))
        config.save()
        messages.success(request, "Configurações do Clube MegaLink atualizadas!")
        return redirect('dashboard_config')
    
    return render(request, 'roleta/dashboard/config.html', {'config': config})

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_gamificacao(request):
    """
    Manage Levels and Point Rules
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Gerenciar Nível
        if action == 'salvar_nivel':
            nivel_id = request.POST.get('nivel_id')
            nome = request.POST.get('nome')
            xp_necessario = int(request.POST.get('xp_necessario', 0))
            ordem = int(request.POST.get('ordem', 1))
            
            if nivel_id:
                nivel = get_object_or_404(NivelClube, id=nivel_id)
                nivel.nome = nome
                nivel.xp_necessario = xp_necessario
                nivel.ordem = ordem
                nivel.save()
                messages.success(request, f"Nível {nome} atualizado!")
            else:
                NivelClube.objects.create(nome=nome, xp_necessario=xp_necessario, ordem=ordem)
                messages.success(request, f"Nível {nome} criado!")
                
        elif action == 'excluir_nivel':
            nivel_id = request.POST.get('nivel_id')
            get_object_or_404(NivelClube, id=nivel_id).delete()
            messages.success(request, "Nível removido!")
            
        # Gerenciar Regras
        elif action == 'salvar_regra':
            regra_id = request.POST.get('regra_id')
            gatilho = request.POST.get('gatilho')
            nome_exibicao = request.POST.get('nome_exibicao')
            pontos_saldo = int(request.POST.get('pontos_saldo', 0))
            pontos_xp = int(request.POST.get('pontos_xp', 0))
            limite = int(request.POST.get('limite_por_membro', 1))
            ativo = request.POST.get('ativo') == 'on'
            
            if regra_id:
                regra = get_object_or_404(RegraPontuacao, id=regra_id)
                regra.gatilho = gatilho
                regra.nome_exibicao = nome_exibicao
                regra.pontos_saldo = pontos_saldo
                regra.pontos_xp = pontos_xp
                regra.limite_por_membro = limite
                regra.ativo = ativo
                regra.save()
                messages.success(request, f"Regra {nome_exibicao} atualizada!")
            else:
                RegraPontuacao.objects.create(
                    gatilho=gatilho, nome_exibicao=nome_exibicao, pontos_saldo=pontos_saldo, 
                    pontos_xp=pontos_xp, limite_por_membro=limite, ativo=ativo
                )
                messages.success(request, f"Regra {nome_exibicao} criada!")
                
        elif action == 'excluir_regra':
            regra_id = request.POST.get('regra_id')
            get_object_or_404(RegraPontuacao, id=regra_id).delete()
            messages.success(request, "Regra removida!")

        return redirect('dashboard_gamificacao')
        
    niveis = NivelClube.objects.all().order_by('xp_necessario')
    regras = RegraPontuacao.objects.all().order_by('-ativo', 'nome_exibicao')
    
    context = {
        'niveis': niveis,
        'regras': regras
    }
    return render(request, 'roleta/dashboard/gamificacao.html', context)

@login_required
@user_passes_test(lambda u: u.is_staff)
def dashboard_cidades(request):
    """
    Gestão de Cidades permitidas para os prêmios.
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'nova_cidade':
            nome = request.POST.get('nome')
            ativo = request.POST.get('ativo') == 'on'
            if nome:
                Cidade.objects.get_or_create(nome=nome, defaults={'ativo': ativo})
                messages.success(request, f"Cidade {nome} processada com sucesso!")
                
        elif action == 'excluir_cidade':
            cidade_id = request.POST.get('cidade_id')
            if cidade_id:
                get_object_or_404(Cidade, id=cidade_id).delete()
                messages.success(request, "Cidade removida com sucesso!")
                
        elif action == 'atualizar_cidade':
            cidade_id = request.POST.get('cidade_id')
            nome = request.POST.get('nome')
            ativo = request.POST.get('ativo') == 'on'
            if cidade_id and nome:
                cidade = get_object_or_404(Cidade, id=cidade_id)
                cidade.nome = nome
                cidade.ativo = ativo
                cidade.save()
                messages.success(request, f"Cidade {nome} atualizada!")
                
        return redirect('dashboard_cidades')
        
    cidades = Cidade.objects.all().order_by('nome')
    return render(request, 'roleta/dashboard/cidades.html', {'cidades': cidades})
