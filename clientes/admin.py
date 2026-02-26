# admin.py
import csv
from django.contrib import admin
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Cliente, Configuracao
from .forms import CSVUploadForm
from django.urls import path
from django.http import HttpResponse
from io import StringIO
from .models import CSVFile, Cliente
from .forms import CSVUploadForm
from .models import ConfiguracaoSite
@admin.register(CSVFile)
class CSVFileAdmin(admin.ModelAdmin):
    list_display = ('uploaded_at',)
    form = CSVUploadForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        # Processar o arquivo CSV
        csv_file = obj.file
        csv_data = csv_file.read().decode('utf-8')
        io_string = StringIO(csv_data)
        reader = csv.DictReader(io_string)
        
        for row in reader:
            Cliente.objects.create(
                id_cliente=row['id_cliente'],
                nome=row['nome'],
                numero=row['numero'],
                cpf=row['cpf'],
                ticket=row['ticket'],
                cidade=row['cidade']  
            )

# Ação personalizada para redefinir todos os clientes como não sorteados
def marcar_todos_nao_sorteados(modeladmin, request, queryset):
    queryset.update(sorteado=False)
    modeladmin.message_user(request, "Todos os clientes foram marcados como não sorteados.")

marcar_todos_nao_sorteados.short_description = "Marcar todos os clientes como não sorteados"

class ConfiguracaoAdmin(admin.ModelAdmin):
    list_display = ('botao_ativo', 'quantidade_exibida')
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nome', 'numero', 'cpf', 'ticket', 'cidade', 'sorteado')
    search_fields = ('nome', 'cpf', 'ticket')    
    actions = [marcar_todos_nao_sorteados]

@admin.register(ConfiguracaoSite)
class ConfiguracaoSiteAdmin(admin.ModelAdmin):
    list_display = ('__str__',)
    fields = ('titulo', 'imagem_fundo', 'banner', 'termos_arquivo')
admin.site.register(Cliente, ClienteAdmin)
admin.site.register(Configuracao, ConfiguracaoAdmin)
