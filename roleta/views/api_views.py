from django.shortcuts import redirect
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q
from roleta.models import PremioRoleta, ParticipanteRoleta, RouletteAsset, RoletaConfig, MembroClube, RegraPontuacao, ExtratoPontuacao, NivelClube, Cidade
from roleta.services.hubsoft_service import HubsoftService
from roleta.services.otp_service import OTPService
from roleta.services.sorteio_service import SorteioService
from roleta.services.gamification_service import GamificationService
import random
import requests
import time
from datetime import datetime

def roleta_init_dados(request):
    """
    JSON endpoint that provides all initial data for the frontend to render.
    """
    sorteado_pos = request.session.pop('sorteado_pos', None)
    nome_ganhador = request.session.pop('nome_ganhador', None)
    premio_nome = request.session.pop('premio_nome', None)
    erro = request.session.pop('erro_sorteio', None)
    saldo_atual = request.session.pop('saldo_atual', None)
    
    auth_membro_id = request.session.get('auth_membro_id')
    is_authenticated = False
    auth_saldo = 0
    auth_nome = ''
    auth_xp = 0
    auth_nivel = 'Iniciante'
    auth_prox_nivel_xp = 0
    auth_progresso_nivel = 0
    missoes = []
    
    if auth_membro_id:
        try:
            membro = MembroClube.objects.get(id=auth_membro_id)
            is_authenticated = True
            auth_saldo = membro.saldo
            auth_nome = membro.nome
            auth_xp = membro.xp_total
            auth_nivel = membro.nivel_atual
            prox = membro.proximo_nivel
            
            # Cálculo de progressão
            if prox:
                auth_prox_nivel_xp = prox.xp_necessario
                nivel_anterior = NivelClube.objects.filter(xp_necessario__lte=membro.xp_total).order_by('-xp_necessario').first()
                xp_base = nivel_anterior.xp_necessario if nivel_anterior else 0
                xp_para_subir = prox.xp_necessario - xp_base
                xp_ganho_neste_nivel = membro.xp_total - xp_base
                auth_progresso_nivel = int((xp_ganho_neste_nivel / xp_para_subir) * 100) if xp_para_subir > 0 else 100
            else:
                auth_prox_nivel_xp = auth_xp # MAX LEVEL
                auth_progresso_nivel = 100
                
            # Missões e Extrato
            regras_ativas = RegraPontuacao.objects.filter(ativo=True)
            for r in regras_ativas:
                conclusoes = ExtratoPontuacao.objects.filter(membro=membro, regra=r).count()
                missoes.append({
                    'id': r.id,
                    'nome': r.nome_exibicao,
                    'gatilho': r.gatilho,
                    'recompensa_giros': r.pontos_saldo,
                    'recompensa_xp': r.pontos_xp,
                    'limite': r.limite_por_membro,
                    'concluidas': conclusoes,
                    'disponivel': r.limite_por_membro == 0 or conclusoes < r.limite_por_membro
                })
        except MembroClube.DoesNotExist:
            request.session.pop('auth_membro_id', None)
            request.session.pop('auth_membro_nome', None)
            request.session.pop('auth_membro_cpf', None)
    
    config, _ = RoletaConfig.objects.get_or_create(id=1)
    cidades_disponiveis = Cidade.objects.filter(ativo=True).values_list('nome', flat=True).order_by('nome')
    assets = RouletteAsset.objects.filter(ativo=True).order_by('ordem')
    
    asset_list = []
    for a in assets:
        asset_list.append({
            'id': a.id,
            'ordem': a.ordem,
            'tipo': a.tipo,
            'imagem_url': a.imagem.url if a.imagem else ''
        })

    data = {
        'nome_clube': config.nome_clube,
        'custo_giro': config.custo_giro,
        'cidades': sorted(list(cidades_disponiveis)),
        'assets': asset_list,
        'sorteado_pos': sorteado_pos,
        'nome_ganhador': nome_ganhador,
        'premio_nome': premio_nome,
        'saldo_atual': saldo_atual,
        'is_authenticated': is_authenticated,
        'auth_saldo': auth_saldo,
        'auth_nome': auth_nome,
        'auth_xp': auth_xp,
        'auth_nivel': auth_nivel,
        'auth_prox_nivel_xp': auth_prox_nivel_xp,
        'auth_progresso_nivel': auth_progresso_nivel,
        'missoes': missoes,
        'erro': erro
    }
    return JsonResponse(data)

@transaction.atomic
def cadastrar_participante(request):
    with open('roleta_debug.log', 'a') as f:
        f.write(f"\n--- CADASTRO INICIADO {datetime.now()} ---\n")
        if request.method == 'POST':
            f.write(f"POST DATA: {request.POST.dict()}\n")
            
            # Check if user is already authenticated via session
            auth_membro_id = request.session.get('auth_membro_id')
            membro = None
            created = False
            config, _ = RoletaConfig.objects.get_or_create(id=1)
            
            if auth_membro_id:
                try:
                    membro = MembroClube.objects.get(id=auth_membro_id)
                except MembroClube.DoesNotExist:
                    pass
            
            if membro:
                # Use data from the established authenticated session
                nome = membro.nome
                cpf = membro.cpf
                email = membro.email
                telefone = membro.telefone
                cep = membro.cep
                cidade = membro.cidade
                estado = membro.estado
                bairro = membro.bairro
                endereco_completo = membro.endereco
                canal = request.POST.get('canal', 'Online (Sessão)')
                perfil = 'sim'
                id_cliente_hubsoft = membro.id_cliente_hubsoft
                f.write(f"Sessão Autenticada Ativa para CPF {cpf}\n")
            else:
                # Normal POST data parsing
                nome = request.POST.get('nome') or "Participante"
                cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')
                email = request.POST.get('email')
                telefone = request.POST.get('telefone')
                cep = request.POST.get('cep')
                
                # Fetch Real City from Hubsoft PostgreSQL
                from roleta.services.hubsoft_service import HubsoftService
                cidade_hubsoft = HubsoftService.consultar_cidade_cliente_cpf(cpf)
                if cidade_hubsoft:
                    cidade = cidade_hubsoft
                else:
                    cidade = request.POST.get('cidade') or "Cidade Não Informada"
                    
                estado = request.POST.get('estado')
                bairro = request.POST.get('bairro')
                rua = request.POST.get('rua')
                numero_casa = request.POST.get('numero_casa')
                canal = request.POST.get('canal', 'Online')
                perfil = request.POST.get('perfil_cliente', 'nao')
                id_cliente_hubsoft = request.POST.get('id_cliente_hubsoft')
                if not id_cliente_hubsoft: id_cliente_hubsoft = None
                
                f.write(f"Parsed FROM POST: CPF={cpf}, Perfil={perfil}\n")
                
                # SEGURANÇA: Verificar OTP para clientes existentes apenas se não tiver auth_membro_id
                if perfil == 'sim':
                    if not request.session.get('otp_validado'):
                        request.session['erro_sorteio'] = "Verificação de segurança necessária."
                        return redirect('roleta_index')
                    # Resetado para segurança
                    request.session['otp_validado'] = False

                print(f"DEBUG: Cadastrando participante via POST. CPF: {cpf}")
                endereco_completo = f"{rua} Nº {numero_casa}"
                
                # Get or create Member
                membro, created = MembroClube.objects.update_or_create(
                    cpf=cpf,
                    defaults={
                        'nome': nome,
                        'email': email,
                        'telefone': telefone,
                        'cep': cep,
                        'endereco': endereco_completo,
                        'bairro': bairro,
                        'cidade': cidade,
                        'estado': estado,
                        'id_cliente_hubsoft': int(id_cliente_hubsoft) if id_cliente_hubsoft else None,
                    }
                )
                if created:
                    from roleta.models import RegraPontuacao
                    from roleta.services.gamification_service import GamificationService
                    
                    # Garante que a regra de cadastro existe
                    RegraPontuacao.objects.get_or_create(
                        gatilho='cadastro_inicial',
                        defaults={
                            'nome_exibicao': 'Bônus de Cadastro Inicial',
                            'pontos_saldo': config.custo_giro,
                            'pontos_xp': 0,
                            'limite_por_membro': 1,
                            'ativo': True
                        }
                    )
                    
                    # Salva o membro sem saldo primeiro para o extrato calcular certo
                    membro.saldo = 0
                    membro.save()
                    
                    GamificationService.atribuir_pontos(membro, 'cadastro_inicial', 'Primeiro acesso ao clube')
                    
                    membro.validado = True # Se for manual e chegou aqui, marcamos como validado
                    membro.save()
                
                if request.session.get('otp_validado'):
                    membro.validado = True
                    membro.save()

            print(f"DEBUG: Membro processado: {membro.nome}, Saldo: {membro.saldo}")
            request.session['otp_validado'] = False
        print(f"DEBUG: Membro: {membro.nome}, Saldo: {membro.saldo}, Created: {created}")
        
        # Assegura a autenticação na sessão
        request.session['auth_membro_id'] = membro.id
        request.session['auth_membro_nome'] = membro.nome
        request.session['auth_membro_cpf'] = membro.cpf
        request.session.modified = True
        
        acao = request.POST.get('acao')
        if acao != 'girar':
            # Se não for o botão explícito de girar, apenas efetuou login/cadastro.
            return redirect('roleta_index')
            
        # Check if already registered - only block if they DON'T have points for a new spin
        has_sufficient_points = membro.saldo >= config.custo_giro

        if not has_sufficient_points and ParticipanteRoleta.objects.filter(cpf=cpf).exists():
            request.session['erro_sorteio'] = 'jah_cadastrado'
            request.session['nome_ganhador'] = membro.nome
            request.session['premio_nome'] = ParticipanteRoleta.objects.filter(cpf=cpf).last().premio
            return redirect('roleta_index')

        if not has_sufficient_points:
            request.session['erro_sorteio'] = f"Saldo insuficiente! Você precisa de {config.custo_giro} pontos."
            return redirect('roleta_index')
            
        # Saldo será debitado dentro do SorteioService após validar prêmios disponíveis
            
        # Determine locality for prizes
        localidade = membro.cidade

        if not localidade:
            localidade = "Cidade Não Informada"
            
        f.write(f"Localidade final: {localidade}\n")
        # Find available prizes for the locality
        premios_disponiveis = list(PremioRoleta.objects.filter(
            Q(cidades_permitidas__nome__iexact=localidade) | Q(cidades_permitidas__isnull=True),
            quantidade__gt=0
        ).distinct())

        if not premios_disponiveis:
            f.write(f"ERRO CRITICO: Nenhum prêmio disponível em localidade={localidade}\n")
            request.session['erro_sorteio'] = 'acabou_premio'
            return redirect('roleta_index')
            
        new_saldo, premio_selecionado, roleta_pos = SorteioService.executar_giro_roleta(
            membro=membro,
            premios_disponiveis=premios_disponiveis,
            custo_giro=config.custo_giro
        )
        
        membro.saldo = new_saldo
        membro.xp_total += config.xp_por_giro
        membro.save()
        premio_selecionado.save()
        
        perfil_cliente = request.POST.get('perfil_cliente', 'nao')
        id_cliente_hubsoft = request.POST.get('id_cliente_hubsoft')
        if not id_cliente_hubsoft: id_cliente_hubsoft = None
        
        # Prepare for create

        # Create spin record
        ParticipanteRoleta.objects.create(
            membro=membro,
            nome=nome,
            cpf=cpf,
            email=email,
            telefone=telefone,
            cep=cep,
            endereco=endereco_completo,
            bairro=bairro,
            cidade=cidade,
            estado=estado,
            premio=premio_selecionado.nome,
            canal_origem=canal,
            perfil_cliente=perfil_cliente,
            id_cliente_hubsoft=id_cliente_hubsoft,
            saldo=new_saldo,
            status='reservado'
        )
        
        # Atualização de estoque já realizada dentro do SorteioService
        
        # Store in session for the roulette animation
        request.session['sorteado_pos'] = roleta_pos
        request.session['nome_ganhador'] = nome
        request.session['premio_nome'] = premio_selecionado.nome
        request.session['saldo_atual'] = new_saldo
        request.session.modified = True
        
        # Se for requisição ajax do botão authSpinForm, retornar json
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' and acao == 'girar':
            return JsonResponse({
                'success': True,
                'sorteado_pos': roleta_pos,
                'premio_nome': premio_selecionado.nome,
                'saldo_atual': new_saldo
            })
            
        return redirect('roleta_index')
        
    return redirect('roleta_index')

@transaction.atomic
def verificar_cliente(request):
    if request.method == 'POST':
        cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')
        if not cpf:
            return JsonResponse({'error': 'CPF não fornecido'}, status=400)
            
        # Get existing member if any
        config, _ = RoletaConfig.objects.get_or_create(id=1)
            
        cliente_data = HubsoftService.consultar_cliente(cpf)
        if cliente_data:
            print(f"DEBUG: Cliente Hubsoft encontrado: {cliente_data.get('nome_razaosocial')}")
            
            # PERSISTÊNCIA IMEDIATA (Pedido pelo usuário)
            # Se não existe, cria. Se existe, atualiza com dados do Hubsoft
            membro, created = MembroClube.objects.update_or_create(
                cpf=cpf,
                defaults={
                    'nome': cliente_data.get('nome_razaosocial', 'Participante'),
                    'email': cliente_data.get('email_principal'),
                    'telefone': cliente_data.get('telefone_primario', ''),
                    'cep': cliente_data.get('cep'),
                    'endereco': cliente_data.get('endereco'),
                    'bairro': cliente_data.get('bairro'),
                    'cidade': cliente_data.get('nome_cidade') or cliente_data.get('cidade') or '',
                    'id_cliente_hubsoft': cliente_data.get('id_cliente')
                }
            )
            # Garante que começa como validado=False se for novo ou se já era pendente
            if created:
                from roleta.models import RegraPontuacao
                from roleta.services.gamification_service import GamificationService
                
                # Garante que a regra de cadastro existe
                RegraPontuacao.objects.get_or_create(
                    gatilho='cadastro_inicial',
                    defaults={
                        'nome_exibicao': 'Bônus de Cadastro Inicial',
                        'pontos_saldo': config.custo_giro,
                        'pontos_xp': 0,
                        'limite_por_membro': 1,
                        'ativo': True
                    }
                )
                
                membro.saldo = 0
                membro.validado = False
                membro.save()
                
                membro.refresh_from_db()
                saldo_final = membro.saldo
            else:
                saldo_final = membro.saldo
            
            return JsonResponse({
                'is_client': True,
                'nome_razaosocial': cliente_data.get('nome_razaosocial'),
                'email_principal': cliente_data.get('email_principal'),
                'telefone_primario': cliente_data.get('telefone_primario', ''),
                'masked_tel': cliente_data.get('masked_tel', ''),
                'id_cliente': cliente_data.get('id_cliente'),
                'saldo': saldo_final,
                'cep': cliente_data.get('cep'),
                'endereco': cliente_data.get('endereco'),
                'numero': cliente_data.get('numero'),
                'bairro': cliente_data.get('bairro'),
                'cidade': cliente_data.get('nome_cidade') or cliente_data.get('cidade') or ''
            })
        
        return JsonResponse({'is_client': False})
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

def solicitar_otp(request):
    with open('roleta_debug.log', 'a') as f:
        f.write(f"\n--- SOLICITAR OTP INICIADO {datetime.now()} ---\n")
        if request.method == 'POST':
            # Basic rate limiting (60 seconds)
            last_request_time = request.session.get('last_otp_request_time')
            current_time = time.time()
            if last_request_time and (current_time - last_request_time) < 60:
                segundos_restantes = 60 - int(current_time - last_request_time)
                return JsonResponse({'error': f'Aguarde {segundos_restantes}s para solicitar um novo código.'}, status=429)

            cpf = request.POST.get('cpf', '').replace('.', '').replace('-', '')
            telefone = request.POST.get('telefone', '')
            f.write(f"Solicitando OTP para CPF: {cpf}, Telefone: {telefone}\n")
            
            if not cpf or not telefone:
                return JsonResponse({'error': 'CPF e Telefone são obrigatórios'}, status=400)
            
            # Update the rate limit timestamp
            request.session['last_otp_request_time'] = current_time
            
            # Gerar código via OTPService
            otp_code = OTPService.gerar_codigo()
            
            # Save to session
            request.session['otp_code'] = otp_code
            request.session['otp_cpf'] = cpf
            
            # Send via n8n webhook module
            sucesso, msg = OTPService.enviar_otp_whatsapp(cpf, telefone, otp_code)
            
            if sucesso:
                f.write(f"OTP {otp_code} enviado via serviço. Status: {msg}\n")
                return JsonResponse({'success': True})
            else:
                f.write(f"Erro ao enviar OTP via serviço: {msg}\n")
                return JsonResponse({'error': msg}, status=500)
            
    return JsonResponse({'error': 'Invalid request'}, status=400)

def validar_otp(request):
    with open('roleta_debug.log', 'a') as f:
        log_time = datetime.now().strftime("%H:%M:%S")
        f.write(f"\n--- VALIDAR OTP [{log_time}] ---\n")
        if request.method == 'POST':
            codigo_usuario = str(request.POST.get('codigo', '')).strip()
            codigo_sessao = str(request.session.get('otp_code', '')).strip()
            cpf = request.session.get('otp_cpf')
            
            f.write(f"CPF Sessao: {cpf}\n")
            f.write(f"User Code: '{codigo_usuario}' (len:{len(codigo_usuario)})\n")
            f.write(f"Session Code: '{codigo_sessao}' (len:{len(codigo_sessao)})\n")
            
            if codigo_usuario and codigo_usuario == codigo_sessao:
                request.session['otp_validado'] = True
                if cpf:
                    membro = MembroClube.objects.filter(cpf=cpf).first()
                    if membro:
                        eh_primeira_validacao = not membro.validado
                        membro.validado = True
                        membro.save()
                        
                        # PERSIST AUTHENTICATED STATE
                        request.session['auth_membro_id'] = membro.id
                        request.session['auth_membro_nome'] = membro.nome
                        request.session['auth_membro_cpf'] = membro.cpf
                        request.session.modified = True
                        
                        f.write(f"Membro {cpf} VALIDADO no DB e SESSÃO iniciada\n")
                        
                        if eh_primeira_validacao:
                            # Garante que a regra existe
                            from roleta.models import RegraPontuacao
                            RegraPontuacao.objects.get_or_create(
                                gatilho='telefone_verificado',
                                defaults={
                                    'nome_exibicao': 'Validou seu WhatsApp',
                                    'pontos_saldo': 1,
                                    'pontos_xp': 10,
                                    'limite_por_membro': 1,
                                    'ativo': True
                                }
                            )
                            GamificationService.atribuir_pontos(membro, 'telefone_verificado', 'Validou WhatsApp')
                            
                        # MÓDULO DE SINCRONIZAÇÃO HUBSOFT (Sempre que validar)
                        try:
                            from roleta.services.hubsoft_service import HubsoftService
                            from roleta.models import RegraPontuacao, ExtratoPontuacao
                            from django.utils import timezone
                            
                            # Garantir que as regras base existam
                            regras = [
                                {'gatilho': 'hubsoft_recorrencia', 'nome': 'Ativou Pagamento Recorrente', 'pts': 3, 'xp': 30, 'lim': 1},
                                {'gatilho': 'hubsoft_adiantado', 'nome': 'Pagou Fatura Adiantada', 'pts': 5, 'xp': 50, 'lim': 0},
                                {'gatilho': 'hubsoft_app', 'nome': 'Baixou e usou o APP Central', 'pts': 2, 'xp': 20, 'lim': 1}
                            ]
                            for r in regras:
                                RegraPontuacao.objects.get_or_create(
                                    gatilho=r['gatilho'],
                                    defaults={
                                        'nome_exibicao': r['nome'], 'pontos_saldo': r['pts'],
                                        'pontos_xp': r['xp'], 'limite_por_membro': r['lim'], 'ativo': True
                                    }
                                )
                                
                            status_pontos = HubsoftService.checar_pontos_extras_cpf(membro.cpf)
                            if status_pontos:
                                # RECORRÊNCIA
                                if status_pontos.get('hubsoft_recorrencia'):
                                    r_rec = RegraPontuacao.objects.get(gatilho='hubsoft_recorrencia')
                                    if not ExtratoPontuacao.objects.filter(membro=membro, regra=r_rec).exists():
                                        GamificationService.atribuir_pontos(membro, 'hubsoft_recorrencia', 'Sincronização Hubsoft')
                                # APP
                                if status_pontos.get('hubsoft_app'):
                                    r_app = RegraPontuacao.objects.get(gatilho='hubsoft_app')
                                    if not ExtratoPontuacao.objects.filter(membro=membro, regra=r_app).exists():
                                        GamificationService.atribuir_pontos(membro, 'hubsoft_app', 'Sincronização Hubsoft')
                                # ADIANTADO (Mensal)
                                if status_pontos.get('hubsoft_adiantado'):
                                    r_adi = RegraPontuacao.objects.get(gatilho='hubsoft_adiantado')
                                    ja_ganhou_mes = ExtratoPontuacao.objects.filter(
                                        membro=membro, regra=r_adi,
                                        data_recebimento__year=timezone.now().year,
                                        data_recebimento__month=timezone.now().month
                                    ).exists()
                                    if not ja_ganhou_mes:
                                        GamificationService.atribuir_pontos(membro, 'hubsoft_adiantado', f"Mês {timezone.now().month}/{timezone.now().year}")

                            f.write("Sincronização Hubsoft finalizada com sucesso.\n")
                        except Exception as sync_e:
                            f.write(f"Erro na sincronização Hubsoft: {sync_e}\n")
                
                f.write("RES: SUCCESS=TRUE\n")
                return JsonResponse({'success': True})
            else:
                f.write(f"RES: SUCCESS=FALSE (Mismatch)\n")
                return JsonResponse({'success': False, 'error': 'Código inválido'})
                
        f.write("RES: SUCCESS=FALSE (Not POST)\n")
        return JsonResponse({'success': False, 'error': 'Método inválido'}, status=405)

@transaction.atomic
def pre_cadastrar(request):
    with open('roleta_debug.log', 'a') as f:
        f.write(f"\n--- PRE-CADASTRO (AJAX) INICIADO {datetime.now()} ---\n")
        if request.method == 'POST':
            data = request.POST.dict()
            f.write(f"Data recebida: {data}\n")
            cpf = data.get('cpf', '').replace('.', '').replace('-', '')
            if cpf:
                config, _ = RoletaConfig.objects.get_or_create(id=1)
                defaults = {
                    'nome': data.get('nome') or "Participante",
                    'telefone': data.get('telefone'),
                    'email': data.get('email'),
                }
                # Adiciona endereço se presente (vindo do Step 3 ou Hubsoft)
                if data.get('cidade'): defaults['cidade'] = data.get('cidade')
                if data.get('cep'): defaults['cep'] = data.get('cep')
                # Rua + Numero
                rua = data.get('rua')
                num = data.get('numero_casa') or data.get('numero')
                if rua: defaults['endereco'] = f"{rua} {num}" if num else rua
                if data.get('bairro'): defaults['bairro'] = data.get('bairro')
                if data.get('id_cliente'): defaults['id_cliente_hubsoft'] = data.get('id_cliente')

                membro, created = MembroClube.objects.update_or_create(
                    cpf=cpf,
                    defaults=defaults
                )
                if created:
                    from roleta.models import RegraPontuacao
                    from roleta.services.gamification_service import GamificationService
                    
                    # Garante que a regra de cadastro existe
                    RegraPontuacao.objects.get_or_create(
                        gatilho='cadastro_inicial',
                        defaults={
                            'nome_exibicao': 'Bônus de Cadastro Inicial',
                            'pontos_saldo': config.custo_giro,
                            'pontos_xp': 0,
                            'limite_por_membro': 1,
                            'ativo': True
                        }
                    )
                    
                    membro.saldo = 0
                    membro.save()
                    
                    GamificationService.atribuir_pontos(membro, 'cadastro_inicial', 'Primeiro acesso ao clube')
                    
                    membro.validado = False
                    membro.save()
                    f.write(f"Membro {cpf} PRÉ-CADASTRADO (Pendente)\n")
                else:
                    f.write(f"Membro {cpf} ATUALIZADO (Pre-registro)\n")
                return JsonResponse({'success': True})
    return JsonResponse({'success': False})
