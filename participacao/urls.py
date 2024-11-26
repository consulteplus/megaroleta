# participacao/urls.py

from django.urls import path
from . import views
from .views import sincronizar_clientes_view


urlpatterns = [
    path('participe/', views.participar_sorteio, name='participar_sorteio'), 
    path('sincronizar-clientes/', sincronizar_clientes_view, name='sincronizar_clientes'), # Ajuste o nome da view conforme necessário
]
