from django.urls import path
from . import views

urlpatterns = [
    path('', views.servicos_list, name='servicos_list'),
    path('novo/', views.servicos_form, name='servicos_form'),
    path('<int:pk>/editar/', views.servicos_form, name='servicos_edit'),
    path('<int:pk>/deletar/', views.servicos_delete, name='servicos_delete'),
]
