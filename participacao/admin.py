from .models import Participante
from django.contrib import admin
from clientes.models import Cliente
import psycopg2

# Função para conectar ao banco de dados externo
def conectar_banco_externo():
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
        print(f"Erro ao conectar ao banco de dados externo: {e}")
        return None

# Função para gerar o próximo ticket sequencial
def gerar_proximo_ticket():
    ultimo_cliente = Cliente.objects.all().order_by('ticket').last()
    if ultimo_cliente:
        return ultimo_cliente.ticket + 1
    else:
        return 1  # Caso não exista clientes ainda, começa em 1

# Função de sincronização para o admin
def sincronizar_clientes(modeladmin, request, queryset):
    participantes = queryset

    connection = conectar_banco_externo()
    if not connection:
        modeladmin.message_user(request, 'Erro ao conectar ao banco externo', level='error')
        return

    cursor = connection.cursor()

    for participante in participantes:
        id_externo = participante.id_externo
        canal = participante.canal  # Supondo que você tenha um campo canal em Participante

        try:
            # Realiza a consulta no banco externo usando o id_externo
            cursor.execute(""" 
                SELECT cli.nome_razaosocial, cli.telefone_primario, cli.cpf_cnpj, ci.nome as cidade 
                FROM cliente cli 
                LEFT JOIN cliente_servico cs ON cli.id_cliente = cs.id_cliente 
                LEFT JOIN cliente_servico_endereco cse ON cs.id_cliente_servico = cse.id_cliente_servico 
                LEFT JOIN endereco_numero en ON cse.id_endereco_numero = en.id_endereco_numero 
                LEFT JOIN cidade ci ON en.id_cidade = ci.id_cidade 
                WHERE cli.codigo_cliente = %s 
                LIMIT 1 
            """, [id_externo])

            row = cursor.fetchone()

            if row:
                nome_razaosocial = row[0]
                telefone_primario = row[1]
                cpf_cnpj = row[2]
                cidade = row[3]

                # Conta quantos registros do mesmo id_externo existem na tabela Participante
                count_participantes = participantes.filter(id_externo=id_externo).count()

                # Verifica se o cliente já existe na tabela Cliente
                existing_clients = Cliente.objects.filter(id_cliente=id_externo)

                # Calcula quantos registros novos precisamos criar
                registros_a_criar = count_participantes - existing_clients.count()

                if registros_a_criar > 0:
                    for _ in range(registros_a_criar):
                        # Gera um novo ticket
                        proximo_ticket = gerar_proximo_ticket()

                        try:
                            # Cria um novo cliente no banco de dados local
                            Cliente.objects.create(
                                id_cliente=id_externo,
                                nome=nome_razaosocial,
                                numero=telefone_primario,
                                cpf=cpf_cnpj,
                                cidade=cidade,
                                ticket=proximo_ticket,
                                sorteado=False
                            )
                            participante.incoerente = False  # Sincronização bem-sucedida

                        except Exception as e:
                            # Caso haja erro ao criar o cliente, marque como incoerente
                            print(f"Erro ao criar cliente local: {e}")
                            participante.incoerente = True
                else:
                    # Se não houver novos registros a criar, marque como incoerente se já estiver cadastrado
                    participante.incoerente = False
                    print('oi')

            else:
                # Caso não encontre resultados no banco externo
                participante.incoerente = True

        except Exception as e:
            # Captura qualquer erro ao realizar a consulta
            print(f"Erro na consulta externa para o participante {id_externo}: {e}")
            participante.incoerente = True  # Marcar como incoerente se a consulta falhar

        # Salvar o estado atualizado do participante
        participante.save()

    # Fechar a conexão e o cursor
    cursor.close()
    connection.close()

    modeladmin.message_user(request, 'Clientes sincronizados com sucesso!')

# Customizando o admin de Participante
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ('canal', 'id_externo', 'data_participacao', 'incoerente')
    actions = [sincronizar_clientes]

# Registrando o modelo Participante no admin
admin.site.register(Participante, ParticipanteAdmin)
