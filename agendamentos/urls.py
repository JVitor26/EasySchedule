from django.urls import path
from . import views

urlpatterns = [
    path('', views.agendamentos_list, name='agendamentos_list'),
    path('novo/', views.agendamentos_form, name='agendamentos_form'),
    path('planos/', views.planos_list, name='planos_list'),
    path('planos/novo/', views.planos_form, name='planos_form'),
    path('planos/<int:pk>/editar/', views.planos_form, name='planos_edit'),
    path('planos/<int:pk>/deletar/', views.planos_delete, name='planos_delete'),
    path('<int:pk>/editar/', views.agendamentos_form, name='agendamentos_edit'),
    path('<int:pk>/deletar/', views.agendamentos_delete, name='agendamentos_delete'),
    path('<int:pk>/mover/', views.mover_agendamento, name='agendamentos_move'),
    path('api/', views.agendamentos_api, name='agendamentos_api'),
]
