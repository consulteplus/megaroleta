"""
Management command para sincronizar clientes do banco externo.
Este comando consulta o banco externo e atualiza a tabela Cliente local.
"""
import psycopg2
from django.core.management.base import BaseCommand
from django.db import transaction
from clientes.models import Cliente
import logging
import time
import csv
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger('clientes')


class Command(BaseCommand):
    help = 'Sincroniza clientes do banco externo com a tabela local'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Executa sem fazer alterações no banco de dados',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Modo DRY-RUN ativado - nenhuma alteração será feita'))
        
        try:
            # Conectar ao banco externo
            connection = self._conectar_banco_externo()
            if not connection:
                self.stdout.write(self.style.ERROR('Erro ao conectar ao banco externo'))
                return

            # Executar a consulta SQL
            sql_query = self._obter_query_sql()
            clientes_externos = self._executar_consulta(connection, sql_query)
            
            if not clientes_externos:
                self.stdout.write(self.style.WARNING('Nenhum cliente encontrado na consulta externa'))
                connection.close()
                return

            self.stdout.write(f'Encontrados {len(clientes_externos)} clientes na consulta externa')
            self.stdout.write('Iniciando sincronização...')
            self.stdout.write('')

            # Processar sincronização
            stats = self._sincronizar_clientes(clientes_externos, dry_run)
            
            # Fechar conexão
            connection.close()

            # Exibir estatísticas
            self._exibir_estatisticas(stats, dry_run)

        except Exception as e:
            logger.error(f'Erro ao sincronizar clientes: {e}', exc_info=True)
            self.stdout.write(self.style.ERROR(f'Erro: {e}'))

    def _conectar_banco_externo(self):
        """Conecta ao banco de dados externo"""
        try:
            connection = psycopg2.connect(
                user="mega_leitura",
                password="4630a1512ee8e738f935a73a65cebf75b07fcab5",
                host="177.10.118.77",
                port="9432",
                database="hubsoft"
            )
            return connection
        except Exception as e:
            logger.error(f'Erro ao conectar ao banco externo: {e}')
            return None

    def _carregar_cpfs_colaboradores(self):
        """Carrega a lista de CPFs de colaboradores do arquivo CSV"""
        import os
        from pathlib import Path
        
        # Caminho do arquivo CSV (mesmo diretório do manage.py)
        base_dir = Path(__file__).parent.parent.parent.parent
        csv_path = base_dir / 'cpf_colaboradores.csv'
        
        cpfs = []
        try:
            if csv_path.exists():
                with open(csv_path, 'r', encoding='utf-8') as f:
                    # Pular o cabeçalho
                    next(f)
                    for linha in f:
                        cpf = linha.strip()
                        if cpf:  # Ignorar linhas vazias
                            # Garantir que o CPF tenha 11 dígitos (preenchendo com zeros à esquerda)
                            cpf_formatado = cpf.zfill(11)
                            cpfs.append(cpf_formatado)
                logger.info(f'Carregados {len(cpfs)} CPFs de colaboradores para exclusão')
            else:
                logger.warning(f'Arquivo cpf_colaboradores.csv não encontrado em {csv_path}')
        except Exception as e:
            logger.error(f'Erro ao carregar CPFs de colaboradores: {e}')
        
        return cpfs
    
    def _obter_query_sql(self):
        """Retorna a query SQL para buscar os clientes"""
        # Carregar CPFs de colaboradores
        cpfs_colaboradores = self._carregar_cpfs_colaboradores()
        
        # Construir a lista de CPFs para a cláusula NOT IN
        if cpfs_colaboradores:
            cpfs_formatados = "','".join(cpfs_colaboradores)
            clausula_cpf = f"and cli.cpf_cnpj not in ('{cpfs_formatados}')"
        else:
            clausula_cpf = ""
        
        return f"""
          select distinct on (cli.codigo_cliente)
                cli.codigo_cliente as id_cliente,
                cli.nome_razaosocial as nome,
                cli.cpf_cnpj as cpf,
                cli.telefone_primario as numero,
                ci.nome as cidade,
                (
                    case when
                        (
                            select min(cac.id_cliente_acesso_central)
                            from cliente_acesso_central cac
                            where cac.id_cliente = cli.id_cliente
                              and cac.status = 'success'
                              and cac.origem = 'app_cliente'
                        ) is not null then 5 else 0 end +
                        
		            case when (
		                select min(cob.id_cobranca)
		                from cobranca cob
		                where cob.id_cliente_servico = cs.id_cliente_servico
		                  and cob.ativo 
		                  and cob.status != 'aguardando'
		                  and date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
		            ) is not null then 1 else 0 end +

                    case when
                        (
                            select min(cob.id_cobranca)
                            from cobranca cob
                            where cob.id_cliente_servico = cs.id_cliente_servico
                              and cob.data_pagamento <= cob.data_vencimento
                              and date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                        ) is not null then 10 else 0 end +

                    case when
                        (
                            select min(cob.id_cobranca)
                            from cobranca cob
                            where cob.id_cliente_servico = cs.id_cliente_servico
                              and cob.data_pagamento is not null
                              and cob.status = 'baixado_pix'
                              and date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                        ) is not null then 5 else 0 end +

                    case when
                        (
                            select min(cc.id_cliente)
                            from cobranca cob
                            left join cliente_cartao cc
                                on cli.id_cliente = cc.id_cliente
                            where cob.id_cliente_servico = cs.id_cliente_servico
                              and cob.data_pagamento is not null
                              and cob.status = 'baixado_cartao'
                              and cc.deleted_at is null
                              and cc.padrao
                              and date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                        ) is not null then 20 else 0 end
                ) + 0 as qtd_tickets
            from
                cliente_servico cs
            join cliente cli on cs.id_cliente = cli.id_cliente
            join cliente_servico_endereco cse on cs.id_cliente_servico = cse.id_cliente_servico
            join endereco_numero en on cse.id_endereco_numero = en.id_endereco_numero
            join cidade ci on en.id_cidade = ci.id_cidade
            JOIN cliente_servico_grupo csg on csg.id_cliente_servico = cs.id_cliente_servico
            JOIN grupo_cliente_servico gcs on gcs.id = csg.id_grupo_cliente_servico
            where
                cse.tipo = 'instalacao'
                and cs.id_servico_status in (11)
                and gcs.descricao= 'Varejo'
                {clausula_cpf}
        """

    def _executar_consulta(self, connection, sql_query):
        """Executa a consulta SQL e retorna os resultados"""
        try:
            cursor = connection.cursor()
            cursor.execute(sql_query)
            
            # Obter nomes das colunas
            columns = [desc[0] for desc in cursor.description]
            
            # Converter resultados para dicionários
            resultados = []
            for row in cursor.fetchall():
                resultado = dict(zip(columns, row))
                # Garantir que qtd_tickets seja um inteiro
                resultado['qtd_tickets'] = int(resultado.get('qtd_tickets', 1))
                resultados.append(resultado)
            
            cursor.close()
            return resultados
        except Exception as e:
            logger.error(f'Erro ao executar consulta: {e}')
            return []

    def _gerar_proximo_ticket(self):
        """Gera o próximo ticket sequencial"""
        ultimo_cliente = Cliente.objects.all().order_by('ticket').last()
        if ultimo_cliente:
            return ultimo_cliente.ticket + 1
        else:
            return 1

    def _sincronizar_clientes(self, clientes_externos, dry_run=False):
        """Sincroniza os clientes externos com o banco local usando operações em lote"""
        stats = {
            'criados': 0,
            'atualizados': 0,
            'removidos': 0,
            'tickets_criados': 0,
            'tickets_removidos': 0,
        }

        inicio_tempo = time.time()
        total_clientes = len(clientes_externos)
        
        self.stdout.write(f'Carregando dados do banco local...')
        tempo_carregamento = time.time()
        
        # 1. Buscar TODOS os clientes existentes de uma vez (otimização)
        todos_clientes_existentes = Cliente.objects.all().order_by('id_cliente', 'ticket')
        
        # 2. Agrupar clientes existentes por id_cliente em memória
        clientes_existentes_por_id = {}
        for cliente in todos_clientes_existentes:
            id_cliente = str(cliente.id_cliente)
            if id_cliente not in clientes_existentes_por_id:
                clientes_existentes_por_id[id_cliente] = []
            clientes_existentes_por_id[id_cliente].append(cliente)
        
        tempo_carregamento_total = time.time() - tempo_carregamento
        self.stdout.write(f'✓ Carregados {len(todos_clientes_existentes)} registros existentes em {tempo_carregamento_total:.1f}s')
        self.stdout.write('=' * 80)
        self.stdout.write(f'Processando {total_clientes} clientes externos...')
        
        # 3. Preparar estruturas para operações em lote
        ids_externos = {str(cliente['id_cliente']) for cliente in clientes_externos}
        clientes_para_atualizar = []
        clientes_para_criar = []
        clientes_para_remover = []
        ids_para_remover = set()  # Para evitar duplicatas
        
        # 4. Obter o último ticket uma única vez
        ultimo_ticket_obj = Cliente.objects.all().order_by('ticket').last()
        proximo_ticket_global = (ultimo_ticket_obj.ticket + 1) if ultimo_ticket_obj else 1
        contador_ticket = proximo_ticket_global
        
        # 5. Processar cada cliente externo em memória
        inicio_processamento = time.time()
        ultimo_log = time.time()
        
        for idx, cliente_ext in enumerate(clientes_externos, 1):
            # Log de progresso
            tempo_atual = time.time()
            if (tempo_atual - ultimo_log >= 5) or (idx % max(1, total_clientes // 20) == 0) or (idx == total_clientes):
                percentual = (idx / total_clientes) * 100
                tempo_decorrido = tempo_atual - inicio_processamento
                velocidade = idx / tempo_decorrido if tempo_decorrido > 0 else 0
                self.stdout.write(
                    f'[{percentual:6.2f}%] Processando: {idx}/{total_clientes} | '
                    f'Tempo: {tempo_decorrido:.1f}s | '
                    f'Velocidade: {velocidade:.1f} clientes/s | '
                    f'Criados: {len(clientes_para_criar)} | '
                    f'Atualizados: {len(clientes_para_atualizar)} | '
                    f'Remover: {len(clientes_para_remover)}'
                )
                ultimo_log = tempo_atual
            
            id_cliente = str(cliente_ext['id_cliente'])
            qtd_tickets = cliente_ext['qtd_tickets']
            
            # Dados atualizados do cliente
            dados_atualizados = {
                'nome': cliente_ext.get('nome', '') or '',
                'cpf': cliente_ext.get('cpf', '') or '',
                'numero': cliente_ext.get('numero', '') or '',
                'cidade': cliente_ext.get('cidade', '') or '',
            }
            
            # Buscar registros existentes deste cliente (já em memória)
            clientes_existentes = clientes_existentes_por_id.get(id_cliente, [])
            qtd_existente = len(clientes_existentes)
            
            # Atualizar registros existentes
            for cliente_existente in clientes_existentes:
                precisa_atualizar = False
                for campo, valor in dados_atualizados.items():
                    if getattr(cliente_existente, campo) != valor:
                        precisa_atualizar = True
                        break
                
                if precisa_atualizar:
                    for campo, valor in dados_atualizados.items():
                        setattr(cliente_existente, campo, valor)
                    clientes_para_atualizar.append(cliente_existente)
            
            # Ajustar quantidade de tickets
            if qtd_existente < qtd_tickets:
                # Criar tickets faltantes
                tickets_faltantes = qtd_tickets - qtd_existente
                for i in range(tickets_faltantes):
                    clientes_para_criar.append(Cliente(
                        id_cliente=id_cliente,
                        ticket=contador_ticket,
                        sorteado=False,
                        **dados_atualizados
                    ))
                    contador_ticket += 1
                stats['criados'] += 1
                stats['tickets_criados'] += tickets_faltantes
                
            elif qtd_existente > qtd_tickets:
                # Remover tickets extras (manter os primeiros, remover os últimos)
                tickets_remover = qtd_existente - qtd_tickets
                # Ordenar por ticket e pegar os últimos
                clientes_ordenados = sorted(clientes_existentes, key=lambda x: x.ticket, reverse=True)
                clientes_para_remover_deste = clientes_ordenados[:tickets_remover]
                
                for cliente_remover in clientes_para_remover_deste:
                    # Não remover se já foi sorteado
                    if not cliente_remover.sorteado:
                        if cliente_remover.id not in ids_para_remover:
                            clientes_para_remover.append(cliente_remover)
                            ids_para_remover.add(cliente_remover.id)
                            stats['tickets_removidos'] += 1
                    else:
                        logger.warning(f'Cliente {id_cliente} com ticket {cliente_remover.ticket} não removido pois já foi sorteado')
                
                if len(clientes_para_remover_deste) > 0:
                    stats['removidos'] += 1
        
        tempo_processamento = time.time() - inicio_processamento
        self.stdout.write('=' * 80)
        self.stdout.write(f'✓ Análise concluída em {tempo_processamento:.1f}s')
        self.stdout.write(f'  - {len(clientes_para_criar)} tickets para criar')
        self.stdout.write(f'  - {len(clientes_para_atualizar)} registros para atualizar')
        self.stdout.write(f'  - {len(clientes_para_remover)} tickets para remover')
        
        # 6. Remover clientes que não aparecem na consulta externa
        self.stdout.write('Verificando clientes para remoção completa...')
        inicio_remocao_completa = time.time()
        
        # Buscar todos os clientes que não estão na lista externa
        for id_cliente_existente, clientes_deste_id in clientes_existentes_por_id.items():
            if id_cliente_existente not in ids_externos:
                # Este cliente não aparece na consulta externa, marcar todos para remoção
                tickets_removidos_deste = 0
                for cliente_remover in clientes_deste_id:
                    if not cliente_remover.sorteado:
                        # Evitar duplicatas usando set de IDs
                        if cliente_remover.id not in ids_para_remover:
                            clientes_para_remover.append(cliente_remover)
                            ids_para_remover.add(cliente_remover.id)
                            tickets_removidos_deste += 1
                            stats['tickets_removidos'] += 1
                
                # Contar como cliente removido se teve pelo menos um ticket removido
                if tickets_removidos_deste > 0:
                    stats['removidos'] += 1
        
        tempo_remocao_completa = time.time() - inicio_remocao_completa
        self.stdout.write(f'✓ Verificação concluída em {tempo_remocao_completa:.1f}s')
        self.stdout.write(f'  - Total de {len(clientes_para_remover)} tickets para remover')
        
        # 7. Executar operações em lote
        if not dry_run:
            self.stdout.write('=' * 80)
            self.stdout.write('Executando operações no banco de dados...')
            inicio_execucao = time.time()
            
            with transaction.atomic():
                # Atualizar em lote
                if clientes_para_atualizar:
                    self.stdout.write(f'Atualizando {len(clientes_para_atualizar)} registros...')
                    Cliente.objects.bulk_update(
                        clientes_para_atualizar,
                        ['nome', 'cpf', 'numero', 'cidade'],
                        batch_size=1000
                    )
                    stats['atualizados'] = len(clientes_para_atualizar)
                
                # Criar em lote
                if clientes_para_criar:
                    self.stdout.write(f'Criando {len(clientes_para_criar)} novos tickets...')
                    # Processar em lotes de 1000 para não sobrecarregar
                    batch_size = 1000
                    for i in range(0, len(clientes_para_criar), batch_size):
                        batch = clientes_para_criar[i:i + batch_size]
                        Cliente.objects.bulk_create(batch, batch_size=batch_size)
                        if i % (batch_size * 10) == 0:
                            self.stdout.write(f'  Criados {min(i + batch_size, len(clientes_para_criar))}/{len(clientes_para_criar)} tickets...')
                
                # Remover em lote
                if clientes_para_remover:
                    self.stdout.write(f'Removendo {len(clientes_para_remover)} tickets...')
                    # Usar delete em lote por IDs (já temos o set, converter para lista)
                    ids_para_remover_lista = list(ids_para_remover)
                    # Processar em lotes
                    batch_size = 1000
                    for i in range(0, len(ids_para_remover_lista), batch_size):
                        batch_ids = ids_para_remover_lista[i:i + batch_size]
                        Cliente.objects.filter(id__in=batch_ids).delete()
                        if i % (batch_size * 10) == 0 or i + batch_size >= len(ids_para_remover_lista):
                            self.stdout.write(f'  Removidos {min(i + batch_size, len(ids_para_remover_lista))}/{len(ids_para_remover_lista)} tickets...')
            
            tempo_execucao = time.time() - inicio_execucao
            self.stdout.write(f'✓ Operações concluídas em {tempo_execucao:.1f}s')
        else:
            self.stdout.write('(Modo DRY-RUN - nenhuma alteração foi feita)')

        tempo_total = time.time() - inicio_tempo
        self.stdout.write('=' * 80)
        self.stdout.write(f'✓ Sincronização concluída em {tempo_total:.1f}s')
        self.stdout.write('')
        
        # Gerar análise detalhada e CSV
        if dry_run:
            self._gerar_analise_detalhada(
                clientes_externos,
                clientes_existentes_por_id,
                clientes_para_criar,
                clientes_para_atualizar,
                clientes_para_remover,
                ids_externos
            )

        return stats
    
    def _gerar_analise_detalhada(self, clientes_externos, clientes_existentes_por_id, 
                                  clientes_para_criar, clientes_para_atualizar, 
                                  clientes_para_remover, ids_externos):
        """Gera análise detalhada e CSV para validação"""
        self.stdout.write('=' * 80)
        self.stdout.write('GERANDO ANÁLISE DETALHADA...')
        self.stdout.write('=' * 80)
        
        # 1. Análise de correspondência de IDs
        ids_existentes = set(clientes_existentes_por_id.keys())
        ids_nao_encontrados = ids_existentes - ids_externos
        ids_novos = ids_externos - ids_existentes
        ids_encontrados = ids_existentes & ids_externos
        
        self.stdout.write(f'\n📊 ANÁLISE DE CORRESPONDÊNCIA:')
        self.stdout.write(f'  IDs existentes no banco: {len(ids_existentes):,}')
        self.stdout.write(f'  IDs na consulta externa: {len(ids_externos):,}')
        self.stdout.write(f'  IDs encontrados (em ambos): {len(ids_encontrados):,}')
        self.stdout.write(f'  IDs que NÃO aparecem na consulta externa: {len(ids_nao_encontrados):,}')
        self.stdout.write(f'  IDs novos (não existem no banco): {len(ids_novos):,}')
        
        # Verificar tipos de IDs
        if ids_existentes:
            exemplo_id_existente = list(ids_existentes)[0]
            self.stdout.write(f'\n  Tipo de ID existente (exemplo): {type(exemplo_id_existente).__name__} = "{exemplo_id_existente}"')
        
        if ids_externos:
            exemplo_id_externo = list(ids_externos)[0]
            self.stdout.write(f'  Tipo de ID externo (exemplo): {type(exemplo_id_externo).__name__} = "{exemplo_id_externo}"')
        
        # Mostrar alguns exemplos de IDs não encontrados
        if ids_nao_encontrados:
            self.stdout.write(f'\n  Exemplos de IDs não encontrados (primeiros 5):')
            for i, id_nao_encontrado in enumerate(list(ids_nao_encontrados)[:5], 1):
                qtd_tickets = len(clientes_existentes_por_id.get(id_nao_encontrado, []))
                self.stdout.write(f'    {i}. ID: {id_nao_encontrado} (tem {qtd_tickets} tickets)')
        
        # 2. Análise de quantidade de tickets
        self.stdout.write(f'\n🎫 ANÁLISE DE TICKETS:')
        
        # Agrupar por id_cliente os que serão criados
        tickets_por_cliente_criar = defaultdict(int)
        for cliente in clientes_para_criar:
            tickets_por_cliente_criar[str(cliente.id_cliente)] += 1
        
        # Agrupar por id_cliente os que serão removidos
        tickets_por_cliente_remover = defaultdict(int)
        for cliente in clientes_para_remover:
            tickets_por_cliente_remover[str(cliente.id_cliente)] += 1
        
        # Verificar se a quantidade final está correta
        self.stdout.write(f'\n  Verificação de quantidade de tickets por cliente:')
        erros_quantidade = []
        for cliente_ext in clientes_externos[:20]:  # Verificar primeiros 20
            id_cliente = str(cliente_ext['id_cliente'])
            qtd_esperada = cliente_ext['qtd_tickets']
            qtd_existente = len(clientes_existentes_por_id.get(id_cliente, []))
            qtd_criar = tickets_por_cliente_criar.get(id_cliente, 0)
            qtd_remover = tickets_por_cliente_remover.get(id_cliente, 0)
            qtd_final = qtd_existente - qtd_remover + qtd_criar
            
            if qtd_final != qtd_esperada:
                erros_quantidade.append({
                    'id': id_cliente,
                    'esperado': qtd_esperada,
                    'final': qtd_final,
                    'existente': qtd_existente,
                    'criar': qtd_criar,
                    'remover': qtd_remover
                })
        
        if erros_quantidade:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Encontrados {len(erros_quantidade)} erros de quantidade:'))
            for erro in erros_quantidade[:5]:
                self.stdout.write(
                    f'    ID: {erro["id"]} | '
                    f'Esperado: {erro["esperado"]} | '
                    f'Final: {erro["final"]} | '
                    f'Existente: {erro["existente"]} | '
                    f'Criar: {erro["criar"]} | '
                    f'Remover: {erro["remover"]}'
                )
        else:
            self.stdout.write(self.style.SUCCESS('  ✅ Quantidades corretas nos primeiros 20 clientes'))
        
        # Análise de alguns clientes externos
        self.stdout.write(f'\n  Exemplos de clientes externos (primeiros 10):')
        for i, cliente_ext in enumerate(clientes_externos[:10], 1):
            id_cliente = str(cliente_ext['id_cliente'])
            qtd_tickets = cliente_ext['qtd_tickets']
            qtd_existente = len(clientes_existentes_por_id.get(id_cliente, []))
            qtd_criar = tickets_por_cliente_criar.get(id_cliente, 0)
            qtd_remover = tickets_por_cliente_remover.get(id_cliente, 0)
            
            status = 'OK' if qtd_existente == qtd_tickets else 'AJUSTAR'
            self.stdout.write(
                f'    {i}. ID: {id_cliente} | '
                f'Qtd esperada: {qtd_tickets} | '
                f'Qtd existente: {qtd_existente} | '
                f'Criar: {qtd_criar} | '
                f'Remover: {qtd_remover} | '
                f'Status: {status}'
            )
        
        # 3. Estatísticas finais esperadas
        total_tickets_final = 0
        for cliente_ext in clientes_externos:
            total_tickets_final += cliente_ext['qtd_tickets']
        
        total_registros_atual = len([c for clientes in clientes_existentes_por_id.values() for c in clientes])
        total_registros_final = (
            total_registros_atual 
            - len(clientes_para_remover) 
            + len(clientes_para_criar)
        )
        
        self.stdout.write(f'\n📈 ESTATÍSTICAS FINAIS ESPERADAS:')
        self.stdout.write(f'  Total de registros atuais: {total_registros_atual:,}')
        self.stdout.write(f'  Total de registros após sincronização: {total_registros_final:,}')
        self.stdout.write(f'  Total de tickets esperados (soma de qtd_tickets): {total_tickets_final:,}')
        self.stdout.write(f'  Diferença: {abs(total_registros_final - total_tickets_final):,}')
        
        # Verificação final
        if abs(total_registros_final - total_tickets_final) < 100:  # Tolerância de 100 registros
            self.stdout.write(self.style.SUCCESS(f'\n✅ VERIFICAÇÃO: Total de registros finais está CORRETO!'))
        else:
            self.stdout.write(self.style.WARNING(f'\n⚠️  ATENÇÃO: Diferença significativa entre registros finais e esperados!'))
            self.stdout.write(f'  Isso pode indicar um problema na lógica de sincronização.')
        
        # Verificar se cada cliente terá a quantidade correta
        self.stdout.write(f'\n🔍 VERIFICAÇÃO DETALHADA (amostra de 10 clientes):')
        for i, cliente_ext in enumerate(clientes_externos[:10], 1):
            id_cliente = str(cliente_ext['id_cliente'])
            qtd_esperada = cliente_ext['qtd_tickets']
            qtd_existente = len(clientes_existentes_por_id.get(id_cliente, []))
            qtd_criar = tickets_por_cliente_criar.get(id_cliente, 0)
            qtd_remover = tickets_por_cliente_remover.get(id_cliente, 0)
            qtd_final = qtd_existente - qtd_remover + qtd_criar
            
            status_icon = '✅' if qtd_final == qtd_esperada else '❌'
            self.stdout.write(
                f'  {status_icon} Cliente {i} (ID: {id_cliente}): '
                f'Esperado={qtd_esperada}, '
                f'Existente={qtd_existente}, '
                f'Criar={qtd_criar}, '
                f'Remover={qtd_remover}, '
                f'Final={qtd_final}'
            )
        
        # 4. Gerar CSV com amostra
        self._gerar_csv_amostra(
            clientes_externos,
            clientes_existentes_por_id,
            clientes_para_criar,
            ids_externos
        )
    
    def _gerar_csv_amostra(self, clientes_externos, clientes_existentes_por_id,
                           clientes_para_criar, ids_externos):
        """Gera CSV com amostra de como ficariam os dados"""
        import os
        from pathlib import Path
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'sincronizacao_amostra_{timestamp}.csv'
        # Salvar no diretório do projeto (mesmo nível do manage.py)
        # Subir 3 níveis: commands -> management -> clientes -> projeto
        base_dir = Path(__file__).parent.parent.parent.parent
        filepath = base_dir / filename
        
        self.stdout.write(f'\n📄 Gerando CSV de amostra: {filepath}')
        
        # Criar estrutura de dados final simulada
        dados_finais = []
        
        # Processar clientes externos (como ficariam após sincronização)
        for cliente_ext in clientes_externos[:100]:  # Primeiros 100 para amostra
            id_cliente = str(cliente_ext['id_cliente'])
            qtd_tickets = cliente_ext['qtd_tickets']
            
            # Buscar registros existentes
            clientes_existentes = clientes_existentes_por_id.get(id_cliente, [])
            
            # Ordenar por ticket
            clientes_existentes_ordenados = sorted(clientes_existentes, key=lambda x: x.ticket)
            
            # Pegar os primeiros (que serão mantidos)
            clientes_manter = clientes_existentes_ordenados[:qtd_tickets]
            
            # Dados atualizados
            dados_atualizados = {
                'nome': cliente_ext.get('nome', '') or '',
                'cpf': cliente_ext.get('cpf', '') or '',
                'numero': cliente_ext.get('numero', '') or '',
                'cidade': cliente_ext.get('cidade', '') or '',
            }
            
            # Adicionar registros existentes (atualizados)
            for cliente in clientes_manter:
                dados_finais.append({
                    'id_cliente': id_cliente,
                    'nome': dados_atualizados['nome'],
                    'cpf': dados_atualizados['cpf'],
                    'numero': dados_atualizados['numero'],
                    'cidade': dados_atualizados['cidade'],
                    'ticket': cliente.ticket,
                    'sorteado': cliente.sorteado,
                    'status': 'EXISTENTE_ATUALIZADO'
                })
            
            # Adicionar novos tickets (simulados - usar contador real)
            tickets_faltantes = qtd_tickets - len(clientes_manter)
            # Buscar tickets que serão criados para este cliente
            tickets_criar_este = [c.ticket for c in clientes_para_criar if str(c.id_cliente) == id_cliente]
            for i, ticket_num in enumerate(tickets_criar_este[:tickets_faltantes]):
                dados_finais.append({
                    'id_cliente': id_cliente,
                    'nome': dados_atualizados['nome'],
                    'cpf': dados_atualizados['cpf'],
                    'numero': dados_atualizados['numero'],
                    'cidade': dados_atualizados['cidade'],
                    'ticket': ticket_num,
                    'sorteado': False,
                    'status': 'NOVO_CRIAR'
                })
        
        # Escrever CSV
        try:
            with open(str(filepath), 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['id_cliente', 'nome', 'cpf', 'numero', 'cidade', 'ticket', 'sorteado', 'status']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for row in dados_finais:
                    writer.writerow(row)
            
            self.stdout.write(self.style.SUCCESS(f'✓ CSV gerado com sucesso: {str(filepath)}'))
            self.stdout.write(f'  Total de linhas: {len(dados_finais)}')
            self.stdout.write(f'  Clientes na amostra: {len(set(r["id_cliente"] for r in dados_finais))}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Erro ao gerar CSV: {e}'))
            logger.error(f'Erro ao gerar CSV: {e}', exc_info=True)

    def _exibir_estatisticas(self, stats, dry_run):
        """Exibe as estatísticas da sincronização"""
        modo = ' (DRY-RUN)' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(f'\n=== Estatísticas da Sincronização{modo} ==='))
        self.stdout.write(f'Clientes criados: {stats["criados"]}')
        self.stdout.write(f'Clientes atualizados: {stats["atualizados"]}')
        self.stdout.write(f'Clientes removidos: {stats["removidos"]}')
        self.stdout.write(f'Tickets criados: {stats["tickets_criados"]}')
        self.stdout.write(f'Tickets removidos: {stats["tickets_removidos"]}')
