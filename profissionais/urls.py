from django.urls import path
from . import views

urlpatterns = [
    path('', views.profissionais_list, name='profissionais_list'),
    path('novo/', views.profissionais_form, name='profissionais_form'),
    path('<int:pk>/editar/', views.profissionais_form, name='profissionais_edit'),
    path('<int:pk>/deletar/', views.profissionais_delete, name='profissionais_delete'),
]
