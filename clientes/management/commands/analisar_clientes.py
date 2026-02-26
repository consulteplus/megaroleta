"""
Management command temporário para analisar os dados atuais da tabela Cliente
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Min, Max, Q
from clientes.models import Cliente
from collections import defaultdict


class Command(BaseCommand):
    help = 'Analisa os dados atuais da tabela Cliente'

    def handle(self, *args, **options):
        self.analisar_clientes()

    def analisar_clientes(self):
        """Analisa os dados atuais da tabela Cliente"""
        
        self.stdout.write("=" * 80)
        self.stdout.write("ANÁLISE DOS DADOS ATUAIS DA TABELA CLIENTE")
        self.stdout.write("=" * 80)
        
        # Estatísticas gerais
        total_registros = Cliente.objects.count()
        total_clientes_unicos = Cliente.objects.values('id_cliente').distinct().count()
        total_sorteados = Cliente.objects.filter(sorteado=True).count()
        
        self.stdout.write(f"\n📊 ESTATÍSTICAS GERAIS:")
        self.stdout.write(f"  Total de registros: {total_registros}")
        self.stdout.write(f"  Total de clientes únicos (id_cliente): {total_clientes_unicos}")
        self.stdout.write(f"  Registros sorteados: {total_sorteados}")
        self.stdout.write(f"  Registros não sorteados: {total_registros - total_sorteados}")
        
        # Análise de tickets
        if total_registros > 0:
            ticket_min = Cliente.objects.aggregate(Min('ticket'))['ticket__min']
            ticket_max = Cliente.objects.aggregate(Max('ticket'))['ticket__max']
            self.stdout.write(f"\n🎫 ANÁLISE DE TICKETS:")
            self.stdout.write(f"  Ticket mínimo: {ticket_min}")
            self.stdout.write(f"  Ticket máximo: {ticket_max}")
            self.stdout.write(f"  Intervalo: {ticket_max - ticket_min + 1}")
        
        # Análise por cliente (quantidade de tickets por id_cliente)
        self.stdout.write(f"\n👥 ANÁLISE POR CLIENTE (quantidade de tickets por id_cliente):")
        clientes_por_ticket = Cliente.objects.values('id_cliente').annotate(
            qtd_tickets=Count('id'),
            sorteados=Count('id', filter=Q(sorteado=True))
        ).order_by('-qtd_tickets')
        
        # Estatísticas de distribuição
        distribuicao = defaultdict(int)
        exemplos = []
        
        for cliente_info in clientes_por_ticket[:20]:  # Primeiros 20 para exemplo
            id_cliente = cliente_info['id_cliente']
            qtd = cliente_info['qtd_tickets']
            distribuicao[qtd] += 1
            
            if len(exemplos) < 5:
                # Buscar um exemplo deste cliente
                exemplo = Cliente.objects.filter(id_cliente=id_cliente).first()
                tickets_list = list(Cliente.objects.filter(
                    id_cliente=id_cliente
                ).values_list('ticket', flat=True).order_by('ticket')[:10])
                
                exemplos.append({
                    'id_cliente': id_cliente,
                    'qtd_tickets': qtd,
                    'nome': exemplo.nome if exemplo else 'N/A',
                    'tickets': tickets_list,
                    'sorteados': cliente_info['sorteados']
                })
        
        self.stdout.write(f"\n  Distribuição de quantidade de tickets por cliente:")
        for qtd, count in sorted(distribuicao.items()):
            self.stdout.write(f"    {qtd} ticket(s): {count} cliente(s)")
        
        self.stdout.write(f"\n  Exemplos de clientes (primeiros 5):")
        for exemplo in exemplos:
            tickets_str = ', '.join(map(str, exemplo['tickets']))
            total_tickets = Cliente.objects.filter(id_cliente=exemplo['id_cliente']).count()
            if len(exemplo['tickets']) < total_tickets:
                tickets_str += f" ... (total: {total_tickets})"
            self.stdout.write(f"    ID: {exemplo['id_cliente']} | Nome: {exemplo['nome'][:30]} | Tickets: {exemplo['qtd_tickets']} (sorteados: {exemplo['sorteados']}) | Lista: {tickets_str}")
        
        # Verificar se há clientes com tickets duplicados
        self.stdout.write(f"\n🔍 VERIFICAÇÕES DE INTEGRIDADE:")
        
        # Verificar tickets duplicados
        tickets_duplicados = Cliente.objects.values('ticket').annotate(
            count=Count('id')
        ).filter(count__gt=1)
        
        if tickets_duplicados.exists():
            self.stdout.write(self.style.WARNING(f"  ⚠️  ATENÇÃO: Encontrados {tickets_duplicados.count()} tickets duplicados!"))
            for dup in tickets_duplicados[:10]:
                self.stdout.write(f"    Ticket {dup['ticket']}: {dup['count']} registros")
        else:
            self.stdout.write(self.style.SUCCESS(f"  ✅ Todos os tickets são únicos"))
        
        # Verificar clientes com dados nulos ou vazios
        clientes_sem_nome = Cliente.objects.filter(Q(nome__isnull=True) | Q(nome=''))
        clientes_sem_cpf = Cliente.objects.filter(Q(cpf__isnull=True) | Q(cpf=''))
        
        if clientes_sem_nome.exists():
            self.stdout.write(self.style.WARNING(f"  ⚠️  {clientes_sem_nome.count()} registros sem nome"))
        if clientes_sem_cpf.exists():
            self.stdout.write(self.style.WARNING(f"  ⚠️  {clientes_sem_cpf.count()} registros sem CPF"))
        
        # Análise detalhada de alguns clientes
        self.stdout.write(f"\n📋 AMOSTRA DE REGISTROS (primeiros 10):")
        self.stdout.write(f"{'ID':<5} {'ID Cliente':<15} {'Nome':<30} {'Ticket':<10} {'CPF':<15} {'Cidade':<20} {'Sorteado':<10}")
        self.stdout.write("-" * 110)
        
        for cliente in Cliente.objects.all()[:10]:
            nome = (cliente.nome[:27] + '...') if len(cliente.nome) > 30 else cliente.nome
            cidade = (cliente.cidade[:17] + '...') if cliente.cidade and len(cliente.cidade) > 20 else (cliente.cidade or 'N/A')
            self.stdout.write(f"{cliente.id:<5} {cliente.id_cliente:<15} {nome:<30} {cliente.ticket:<10} {cliente.cpf:<15} {cidade:<20} {str(cliente.sorteado):<10}")
        
        # Análise de estrutura esperada vs atual
        self.stdout.write(f"\n🔧 ANÁLISE DE COMPATIBILIDADE COM SCRIPT DE SINCRONIZAÇÃO:")
        self.stdout.write(f"\n  Estrutura esperada pelo script:")
        self.stdout.write(f"    - Cada cliente (id_cliente) deve ter múltiplos registros")
        self.stdout.write(f"    - Cada registro representa um ticket único")
        self.stdout.write(f"    - Tickets devem ser sequenciais e únicos")
        self.stdout.write(f"    - Campos: id_cliente, nome, cpf, numero, cidade, ticket, sorteado")
        
        # Verificar se a estrutura atual está compatível
        clientes_com_multiplos_tickets = Cliente.objects.values('id_cliente').annotate(
            qtd=Count('id')
        ).filter(qtd__gt=1).count()
        
        self.stdout.write(f"\n  Status atual:")
        self.stdout.write(f"    - Clientes com múltiplos tickets: {clientes_com_multiplos_tickets}")
        self.stdout.write(f"    - Estrutura {'✅ COMPATÍVEL' if clientes_com_multiplos_tickets > 0 or total_registros == 0 else '⚠️  VERIFICAR'}")
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("ANÁLISE CONCLUÍDA")
        self.stdout.write("=" * 80)
