from django.urls import path

from . import views


urlpatterns = [
    path("", views.produtos_list, name="produtos_list"),
    path("novo/", views.produtos_form, name="produtos_form"),
    path("<int:pk>/editar/", views.produtos_form, name="produtos_edit"),
    path("<int:pk>/deletar/", views.produtos_delete, name="produtos_delete"),
    # Vendas — somente proprietário
    path("vendas/", views.vendas_list, name="vendas_list"),
    path("vendas/nova/", views.vendas_form, name="vendas_form"),
    path("vendas/<int:pk>/editar/", views.vendas_form, name="vendas_edit"),
    path("vendas/<int:pk>/excluir/", views.vendas_delete, name="vendas_delete"),
]

