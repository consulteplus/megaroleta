from django.urls import path
from . import views

urlpatterns = [
    path('', views.roleta_index, name='roleta_index'),
    path('cadastrar/', views.cadastrar_participante, name='cadastrar_participante'),
    
    # Custom Admin Dashboard
    path('dashboard/', views.dashboard_home, name='dashboard_home'),
    path('dashboard/login/', views.admin_login, name='admin_login'),
    path('dashboard/premios/', views.dashboard_premios, name='dashboard_premios'),
    path('dashboard/participantes/', views.dashboard_participantes, name='dashboard_participantes'),
    path('dashboard/participantes/<int:membro_id>/extrato/', views.dashboard_extrato_membro, name='dashboard_extrato_membro'),
    path('dashboard/giros/', views.dashboard_giros, name='dashboard_giros'),
    path('dashboard/cidades/', views.dashboard_cidades, name='dashboard_cidades'),
    path('dashboard/exportar/', views.exportar_csv, name='exportar_csv'),
    path('dashboard/assets/', views.dashboard_assets, name='dashboard_assets'),
    path('dashboard/config/', views.dashboard_config, name='dashboard_config'),
    path('dashboard/gamificacao/', views.dashboard_gamificacao, name='dashboard_gamificacao'),
    path('verificar-cliente/', views.verificar_cliente, name='verificar_cliente'),
    path('solicitar-otp/', views.solicitar_otp, name='solicitar_otp'),
    path('validar-otp/', views.validar_otp, name='validar_otp'),
    path('pre-cadastrar/', views.pre_cadastrar, name='pre_cadastrar'),
    path('api/init-dados/', views.roleta_init_dados, name='roleta_init_dados'),
    path('logout/', views.roleta_logout, name='roleta_logout'),
]
