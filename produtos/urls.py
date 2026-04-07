from django.urls import path

from . import views


urlpatterns = [
    path("", views.produtos_list, name="produtos_list"),
    path("novo/", views.produtos_form, name="produtos_form"),
    path("<int:pk>/editar/", views.produtos_form, name="produtos_edit"),
    path("<int:pk>/deletar/", views.produtos_delete, name="produtos_delete"),
]

