# urls.py
from django.urls import path
from . import views

app_name = 'clientes'

urlpatterns = [
    path('', views.home, name='home'),
    path('lista-clientes/', views.lista_clientes, name='lista_clientes'),
    path('sortear-clientes/', views.lista_clientes, name='sortear_clientes'),  # Adiciona a URL para sortear
]
