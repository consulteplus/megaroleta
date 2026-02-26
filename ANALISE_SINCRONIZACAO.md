# Análise de Compatibilidade - Script de Sincronização

## 📊 Dados Atuais no Banco

- **Total de registros**: 1.278.043
- **Total de clientes únicos (id_cliente)**: 25.693
- **Registros sorteados**: 0
- **Estrutura**: ✅ COMPATÍVEL

### Distribuição de Tickets por Cliente
- Maioria dos clientes tem entre 221-366 tickets
- Todos os tickets são únicos (sem duplicatas)
- Tickets são sequenciais (1 a 1.278.043)

## ✅ Compatibilidade com o Script

### Estrutura Esperada vs Atual
| Aspecto | Esperado | Atual | Status |
|---------|----------|-------|--------|
| Múltiplos registros por cliente | ✅ | ✅ | ✅ OK |
| Tickets únicos | ✅ | ✅ | ✅ OK |
| Campos: id_cliente, nome, cpf, numero, cidade, ticket, sorteado | ✅ | ✅ | ✅ OK |
| Proteção de registros sorteados | ✅ | ✅ | ✅ OK |

## 🔍 Pontos de Atenção

### 1. Geração de Novos Tickets
- ✅ **OK**: O método `_gerar_proximo_ticket()` busca o último ticket e adiciona 1
- ✅ **OK**: Garante que novos tickets serão únicos e sequenciais
- ⚠️ **ATENÇÃO**: Se houver muitos novos tickets, pode demorar um pouco

### 2. Remoção de Clientes
- ⚠️ **ATENÇÃO**: O script remove TODOS os clientes que não aparecem na consulta externa
- ✅ **PROTEÇÃO**: Não remove registros já sorteados
- 📝 **RECOMENDAÇÃO**: Testar primeiro com `--dry-run` para ver quantos seriam removidos

### 3. Atualização de Dados
- ✅ **OK**: Atualiza apenas campos que mudaram (nome, cpf, numero, cidade)
- ✅ **OK**: Mantém tickets e status de sorteado intactos

### 4. Ajuste de Quantidade de Tickets
- ✅ **OK**: Cria tickets faltantes quando `qtd_existente < qtd_tickets`
- ✅ **OK**: Remove tickets extras quando `qtd_existente > qtd_tickets`
- ✅ **PROTEÇÃO**: Mantém os primeiros tickets, remove os últimos (não sorteados)

## 🎯 Conclusão

O script de sincronização está **COMPATÍVEL** com a estrutura atual dos dados. A lógica implementada:

1. ✅ Preserva a integridade dos tickets (únicos e sequenciais)
2. ✅ Protege registros já sorteados
3. ✅ Atualiza dados quando necessário
4. ✅ Ajusta quantidade de tickets conforme a consulta externa
5. ✅ Remove clientes que não aparecem na consulta (com proteção para sorteados)

## 📝 Recomendações

1. **Testar primeiro com `--dry-run`**:
   ```bash
   python manage.py sincronizar_clientes --dry-run
   ```

2. **Verificar quantos registros seriam afetados** antes de executar de verdade

3. **Fazer backup do banco** antes da primeira execução real

4. **Monitorar os logs** durante a execução para identificar possíveis problemas

## ⚙️ Funcionamento do Script

1. Conecta ao banco externo (hubsoft)
2. Executa a query SQL do arquivo `sql.txt`
3. Para cada cliente retornado:
   - Atualiza dados se necessário
   - Cria tickets faltantes (se `qtd_existente < qtd_tickets`)
   - Remove tickets extras (se `qtd_existente > qtd_tickets`)
4. Remove clientes que não aparecem na consulta externa (protegendo sorteados)
5. Gera estatísticas da sincronização
