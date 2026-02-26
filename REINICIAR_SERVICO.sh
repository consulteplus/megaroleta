#!/bin/bash
# Script para reiniciar o serviço gunicorn após instalar dependências

echo "🔄 Reiniciando serviço gunicorn..."
sudo systemctl restart gunicorn.service

echo "⏳ Aguardando 2 segundos..."
sleep 2

echo "📊 Verificando status do serviço..."
sudo systemctl status gunicorn.service --no-pager -l
