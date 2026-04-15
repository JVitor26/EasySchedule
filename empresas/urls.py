from django.urls import path
from . import views

urlpatterns = [
    path('cadastro/', views.cadastro_empresa, name='cadastro_empresa'),
    path('selecionar/', views.selecionar_empresa, name='selecionar_empresa'),
    path('configuracoes/', views.empresa_configuracoes, name='empresa_configuracoes'),
    path('configuracoes/excluir-conta/', views.empresa_excluir_conta, name='empresa_excluir_conta'),
]
