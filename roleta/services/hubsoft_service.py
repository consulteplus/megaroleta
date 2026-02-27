import requests

class HubsoftService:
    @staticmethod
    def consultar_cliente(cpf: str):
        """
        Consulta os dados do cliente no webhook do Hubsoft via n8n.
        Retorna o dicionário com dados do cliente ou None.
        """
        webhook_url = "https://automation-n8n.v4riem.easypanel.host/webhook/roletaconsultarcliente"
        try:
            response = requests.post(webhook_url, json={'cpf': cpf}, timeout=10)
            if response.status_code == 200:
                data = response.json()
                
                # Pega o primeiro item se for lista
                top_data = data[0] if isinstance(data, list) and len(data) > 0 else data
                
                if isinstance(top_data, dict) and top_data.get('status') == 'success':
                    clientes_list = top_data.get('clientes', [])
                    if isinstance(clientes_list, list) and len(clientes_list) > 0:
                        cliente_data = clientes_list[0]
                        
                        # Processa e oculta informações de numero
                        tel = cliente_data.get('telefone_primario', '')
                        masked_tel = ""
                        if tel and len(tel) > 2:
                            masked_tel = f"(**) ****-{tel[-4:]}"
                            
                        # Anexa ao retorno
                        cliente_data['masked_tel'] = masked_tel
                        return cliente_data
            return None
        except Exception as e:
            print(f"Erro ao comunicar com HubsoftService: {str(e)}")
            return None

    @staticmethod
    def checar_pontos_extras_cpf(cpf: str):
        import psycopg2
        import datetime
        from django.utils import timezone
        
        try:
            connection = psycopg2.connect(
                user="mega_leitura",
                password="4630a1512ee8e738f935a73a65cebf75b07fcab5",
                host="177.10.118.77",
                port="9432",
                database="hubsoft"
            )
            cursor = connection.cursor()
            
            # Format CPF to ensure compatibility with DB (usually stored with punctuation in Hubsoft, let's just query by numbers if necessary)
            # Se for buscar direto com pontuação:
            if len(cpf) == 11:
                cpf_formatted = f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
            elif len(cpf) == 14 and '.' not in cpf:
                cpf_formatted = f"{cpf[:2]}.{cpf[2:5]}.{cpf[5:8]}/{cpf[8:12]}-{cpf[12:]}"
            else:
                cpf_formatted = cpf # se já veio com pontuação da session
            
            # Queremos apenas 1 registro agregado sobre esse CPF
            sql_query = """
                SELECT DISTINCT ON (cli.codigo_cliente)
                    (CASE WHEN (
                        SELECT MIN(cc.id_cliente)
                        FROM cliente_cartao cc
                        WHERE cli.id_cliente = cc.id_cliente
                        AND cc.deleted_at IS NULL
                        AND cc.padrao
                    ) IS NOT NULL THEN 1 ELSE 0 END) AS pontos_recorrencia,
                    
                    (CASE WHEN (
                        SELECT MIN(cob.id_cobranca)
                        FROM cobranca cob
                        WHERE cob.id_cliente_servico = cs.id_cliente_servico
                        AND cob.data_pagamento <= cob.data_vencimento
                        AND date_trunc('month', cob.data_vencimento) = date_trunc('month', current_date)
                    ) IS NOT NULL THEN 1 ELSE 0 END) AS pontos_adiantado,
                    
                    (CASE WHEN (
                        SELECT MIN(cac.id_cliente_acesso_central)
                        FROM cliente_acesso_central cac
                        WHERE cac.id_cliente = cli.id_cliente
                        AND cac.status = 'success'
                        AND cac.origem = 'app_cliente'
                    ) IS NOT NULL THEN 1 ELSE 0 END) AS pontos_app
                FROM cliente_servico cs
                JOIN cliente cli ON cs.id_cliente = cli.id_cliente
                JOIN cliente_servico_endereco cse ON cs.id_cliente_servico = cse.id_cliente_servico
                JOIN cliente_servico_grupo csg ON csg.id_cliente_servico = cs.id_cliente_servico
                JOIN grupo_cliente_servico gcs ON gcs.id = csg.id_grupo_cliente_servico
                WHERE cse.tipo = 'instalacao'
                AND cs.id_servico_status IN (11)
                AND gcs.descricao = 'Varejo'
                AND REPLACE(REPLACE(REPLACE(cli.cpf_cnpj, '.', ''), '-', ''), '/', '') = %s
                LIMIT 1;
            """
            
            # Remove pontuações do CPF para busca segura e comparável
            cpf_clean = cpf.replace('.', '').replace('-', '').replace('/', '')
            
            cursor.execute(sql_query, [cpf_clean])
            row = cursor.fetchone()
            connection.close()
            
            if row:
                return {
                    'hubsoft_recorrencia': row[0] == 1,
                    'hubsoft_adiantado': row[1] == 1,
                    'hubsoft_app': row[2] == 1,
                }
            return None
        except Exception as e:
            print(f"Erro ao consultar_pontos_extras_cpf na HubsoftService: {e}")
            return None

    @staticmethod
    def consultar_cidade_cliente_cpf(cpf: str):
        import psycopg2
        
        try:
            connection = psycopg2.connect(
                user="mega_leitura",
                password="4630a1512ee8e738f935a73a65cebf75b07fcab5",
                host="177.10.118.77",
                port="9432",
                database="hubsoft"
            )
            cursor = connection.cursor()
            
            # Formatação de CPF segura para corresponder aos dados da Hubsoft
            cpf_clean = cpf.replace('.', '').replace('-', '').replace('/', '')
            
            sql_query = """
                SELECT
                    ci.nome as cidade
                FROM
                    cliente cli
                JOIN
                    cliente_servico cs on cli.id_cliente = cs.id_cliente
                JOIN
                    cliente_servico_endereco cse on cs.id_cliente_servico = cse.id_cliente_servico
                JOIN
                    endereco_numero en on cse.id_endereco_numero = en.id_endereco_numero
                JOIN
                    cidade ci on en.id_cidade = ci.id_cidade
                WHERE
                    cse.tipo = 'instalacao'
                    AND REPLACE(REPLACE(REPLACE(cli.cpf_cnpj, '.', ''), '-', ''), '/', '') = %s
                LIMIT 1;
            """
            
            cursor.execute(sql_query, [cpf_clean])
            row = cursor.fetchone()
            connection.close()
            
            if row and row[0]:
                return row[0].strip()
            return None
        except Exception as e:
            print(f"Erro ao consultar_cidade_cliente_cpf na HubsoftService: {e}")
            return None
