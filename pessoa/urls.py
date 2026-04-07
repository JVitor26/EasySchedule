from django.urls import path
from . import views

urlpatterns = [
    path('', views.pessoa_list, name='pessoa_list'),
    path('novo/', views.pessoa_form, name='pessoa_form'),
    path('<int:pk>/editar/', views.pessoa_form, name='pessoa_edit'),
    path('<int:pk>/deletar/', views.pessoa_delete, name='pessoa_delete'),
]
