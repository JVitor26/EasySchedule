from django.urls import path
from . import views

urlpatterns = [
    path('service-worker.js', views.service_worker_js, name='service_worker_js'),
    path('accounts/recuperar-senha/', views.password_recovery_request, name='password_recovery_request'),
    path('accounts/recuperar-senha/confirmar/', views.password_recovery_confirm, name='password_recovery_confirm'),
    path('accounts/login-redirect/', views.login_redirect, name='login_redirect'),
    path('', views.home, name='home'),
    path('cliente/', views.home, name='cliente_home'),
    path('cliente/empresa/<int:empresa_id>/', views.empresa_detail, name='cliente_empresa'),
    path('cliente/empresa/<int:empresa_id>/minha-conta/', views.cliente_minha_conta, name='cliente_minha_conta'),
    path('cliente/empresa/<int:empresa_id>/horarios/', views.available_slots_api, name='cliente_horarios'),
    path('cliente/empresa/<int:empresa_id>/api/portal/login-senha/', views.portal_password_login_api, name='portal_password_login_api'),
    path('cliente/empresa/<int:empresa_id>/api/portal/enviar-otp/', views.portal_enviar_otp_api, name='portal_enviar_otp_api'),
    path('cliente/empresa/<int:empresa_id>/api/portal/validar-otp/', views.portal_validar_otp_api, name='portal_validar_otp_api'),
    path('cliente/empresa/<int:empresa_id>/api/portal/logout/', views.portal_logout_api, name='portal_logout_api'),
    path('cliente/empresa/<int:empresa_id>/api/agendamentos/', views.cliente_agendamentos_api, name='cliente_agendamentos_api'),
    path('cliente/empresa/<int:empresa_id>/api/agendamentos/<int:agendamento_id>/cancelar/', views.cliente_agendamento_cancelar_api, name='cliente_agendamento_cancelar_api'),
    path('cliente/empresa/<int:empresa_id>/api/agendamentos/<int:agendamento_id>/remarcar/', views.cliente_agendamento_remarcar_api, name='cliente_agendamento_remarcar_api'),
    path('cliente/empresa/<int:empresa_id>/loja/', views.loja_produtos, name='loja_produtos'),
    path('cliente/empresa/<int:empresa_id>/api/carrinho/listar/', views.api_carrinho_listar, name='api_carrinho_listar'),
    path('cliente/empresa/<int:empresa_id>/api/carrinho/adicionar/', views.api_carrinho_adicionar, name='api_carrinho_adicionar'),
    path('cliente/empresa/<int:empresa_id>/api/carrinho/remover/', views.api_carrinho_remover, name='api_carrinho_remover'),
    path('cliente/empresa/<int:empresa_id>/api/carrinho/atualizar/', views.api_carrinho_atualizar, name='api_carrinho_atualizar'),
    
    # 💳 Stripe Payment Integration
    path('stripe/checkout/agendamento/<int:pagamento_id>/api/', views.stripe_checkout_agendamento_api, name='stripe_checkout_agendamento_api'),
    path('stripe/checkout/plano/<int:plano_id>/api/', views.stripe_checkout_plano_api, name='stripe_checkout_plano_api'),
    path('stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('stripe/checkout/success/', views.stripe_checkout_success, name='stripe_checkout_success'),
    path('stripe/checkout/cancel/', views.stripe_checkout_cancel, name='stripe_checkout_cancel'),
    
    path('cliente/pagamento/<uuid:token>/', views.payment_detail, name='cliente_pagamento'),
    path('cliente/pacote/<uuid:token>/pagamento/', views.plan_payment_detail, name='cliente_plano_pagamento'),
]
