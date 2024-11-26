from django.db import models

class Cliente(models.Model):
    id_cliente = models.CharField(max_length=255)
    nome = models.CharField(max_length=255)
    numero = models.CharField(max_length=20)
    cpf = models.CharField(max_length=14)
    ticket = models.IntegerField()
    cidade = models.CharField(max_length=255, blank=True, null=True)
    sorteado = models.BooleanField(default=False)

    def __str__(self):
        return self.nome
class Configuracao(models.Model):
    botao_ativo = models.BooleanField(default=False)
    quantidade_exibida = models.IntegerField(default=0)

    def __str__(self):
        return f'Configuração ({self.id})'

class CSVFile(models.Model):
    file = models.FileField(upload_to='csvs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"CSV importado em {self.uploaded_at}"

class ConfiguracaoSite(models.Model):
    imagem_fundo = models.ImageField(upload_to='backgrounds/', blank=True, null=True)
    termos_arquivo = models.FileField(upload_to='termos/', blank=True, null=True)
    def __str__(self):
        return "Configuração do Site"