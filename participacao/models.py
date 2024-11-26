from django.db import models

class Participante(models.Model):
    canal = models.CharField(max_length=50)
    id_externo = models.CharField(max_length=50)
    data_participacao = models.DateTimeField(auto_now_add=True)
    incoerente = models.BooleanField(default=False)  # Novo campo para indicar status de sincronização

    def __str__(self):
        return f"Participante {self.id_externo} no canal {self.canal}"
