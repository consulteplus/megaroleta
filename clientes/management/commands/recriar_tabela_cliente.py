"""
Management command para recriar a tabela clientes_cliente
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from clientes.models import Cliente


class Command(BaseCommand):
    help = 'Recria a tabela clientes_cliente'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Força a recriação mesmo se a tabela já existir',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        with connection.cursor() as cursor:
            # Verificar se a tabela existe
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'clientes_cliente'
                );
            """)
            tabela_existe = cursor.fetchone()[0]
            
            if tabela_existe:
                if not force:
                    self.stdout.write(
                        self.style.WARNING(
                            '⚠️  A tabela "clientes_cliente" já existe!\n'
                            'Use --force para excluí-la e recriar.'
                        )
                    )
                    return
                
                self.stdout.write('🗑️  Excluindo tabela existente...')
                with transaction.atomic():
                    cursor.execute("DROP TABLE IF EXISTS clientes_cliente CASCADE;")
                self.stdout.write(self.style.SUCCESS('✅ Tabela excluída.'))
            
            self.stdout.write('🔨 Criando tabela "clientes_cliente"...')
            
            # Criar a tabela usando SQL direto
            with transaction.atomic():
                sql_create = """
                CREATE TABLE clientes_cliente (
                    id BIGSERIAL PRIMARY KEY,
                    id_cliente VARCHAR(255) NOT NULL,
                    nome VARCHAR(255) NOT NULL,
                    numero VARCHAR(20) NOT NULL,
                    cpf VARCHAR(14) NOT NULL,
                    ticket INTEGER NOT NULL,
                    cidade VARCHAR(255),
                    sorteado BOOLEAN NOT NULL DEFAULT FALSE
                );
                """
                cursor.execute(sql_create)
            
            self.stdout.write(self.style.SUCCESS('✅ Tabela "clientes_cliente" criada com sucesso!'))
            
            # Verificar estrutura
            self.stdout.write('\n📋 Estrutura da tabela:')
            self.stdout.write('-' * 80)
            cursor.execute("""
                SELECT column_name, data_type, character_maximum_length, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'clientes_cliente'
                ORDER BY ordinal_position;
            """)
            
            self.stdout.write(f"{'Coluna':<25} {'Tipo':<25} {'Tamanho':<10} {'Null'}")
            self.stdout.write('-' * 80)
            for row in cursor.fetchall():
                coluna, tipo, tamanho, nullable = row
                tamanho_str = str(tamanho) if tamanho else '-'
                self.stdout.write(f"{coluna:<25} {tipo:<25} {tamanho_str:<10} {nullable}")
