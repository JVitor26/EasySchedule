from django.urls import path
from . import views
from .views import ExecutarRelatorioView, dashboard

urlpatterns = [
    path('', views.relatorio_page, name='relatorio_page'),
    path('dashboard/', dashboard, name='relatorio_dashboard'),
    path('executar/<uuid:pk>/', ExecutarRelatorioView.as_view(), name='executar_relatorio'),
]
