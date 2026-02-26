# Instruções para Instalar Dependências

## Arquivo atualizado: requirements.txt

O arquivo `requirements.txt` foi atualizado com todas as dependências necessárias, incluindo:

- **apscheduler==3.10.4** - Para o agendamento automático (execução diária às 7h)

## Comandos para Instalar

### 1. Ativar o ambiente virtual (se usar venv):
```bash
source venv/bin/activate
```

### 2. Instalar todas as dependências:
```bash
pip install -r requirements.txt
```

### 3. Ou instalar apenas o apscheduler (se as outras já estão instaladas):
```bash
pip install apscheduler==3.10.4
```

## Lista Completa de Dependências

```
asgiref==3.8.1
Django==4.2
gunicorn==23.0.0
packaging==24.1
pillow==10.4.0
psycopg2-binary==2.9.9
apscheduler==3.10.4
sqlparse==0.5.1
tzdata==2024.1
```

## Verificar se está instalado

Após instalar, verifique se o apscheduler está instalado:
```bash
pip list | grep apscheduler
```

Ou teste no Python:
```python
python -c "import apscheduler; print(apscheduler.__version__)"
```

## Reiniciar o serviço

Após instalar as dependências, reinicie o serviço do Django/Gunicorn:
```bash
sudo systemctl restart seu-servico-django
```

Ou se estiver usando supervisor:
```bash
sudo supervisorctl restart seu-servico-django
```