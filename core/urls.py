from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('cliente/', views.home, name='cliente_home'),
    path('cliente/empresa/<int:empresa_id>/', views.empresa_detail, name='cliente_empresa'),
    path('cliente/empresa/<int:empresa_id>/horarios/', views.available_slots_api, name='cliente_horarios'),
    path('cliente/pagamento/<uuid:token>/', views.payment_detail, name='cliente_pagamento'),
    path('cliente/pacote/<uuid:token>/pagamento/', views.plan_payment_detail, name='cliente_plano_pagamento'),
]
