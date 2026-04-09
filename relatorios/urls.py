from django.urls import path
from . import views
from .views import ExecutarRelatorioView, dashboard, dashboard_vendas

urlpatterns = [
    path('', views.relatorio_page, name='relatorio_page'),
    path('dashboard/', dashboard, name='relatorio_dashboard'),
    path('dashboard/vendas/', dashboard_vendas, name='relatorio_dashboard_vendas'),
    path('executar/<uuid:pk>/', ExecutarRelatorioView.as_view(), name='executar_relatorio'),
]
