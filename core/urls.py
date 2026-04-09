from django.urls import path
from . import views

urlpatterns = [
    path('healthz/', views.healthz, name='healthz'),
    path('readyz/', views.readyz, name='readyz'),
    path('stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
    path('service-worker.js', views.service_worker_js, name='service_worker_js'),
    path('accounts/recuperar-senha/', views.password_recovery_request, name='password_recovery_request'),
    path('accounts/recuperar-senha/confirmar/', views.password_recovery_confirm, name='password_recovery_confirm'),
    path('accounts/login-redirect/', views.login_redirect, name='login_redirect'),
    path('', views.home, name='home'),
    path('cliente/', views.home, name='cliente_home'),
    path('cliente/empresa/<int:empresa_id>/', views.empresa_detail, name='cliente_empresa'),
    path('cliente/empresa/<int:empresa_id>/minha-conta/', views.cliente_minha_conta, name='cliente_minha_conta'),
    path('cliente/empresa/<int:empresa_id>/horarios/', views.available_slots_api, name='cliente_horarios'),
    path('cliente/empresa/<int:empresa_id>/api/horarios/hold/', views.slot_hold_api, name='cliente_slot_hold_api'),
    path('cliente/empresa/<int:empresa_id>/api/portal/login-senha/', views.portal_password_login_api, name='portal_password_login_api'),
    path('cliente/empresa/<int:empresa_id>/api/portal/enviar-otp/', views.portal_enviar_otp_api, name='portal_enviar_otp_api'),
    path('cliente/empresa/<int:empresa_id>/api/portal/validar-otp/', views.portal_validar_otp_api, name='portal_validar_otp_api'),
    path('cliente/empresa/<int:empresa_id>/api/portal/logout/', views.portal_logout_api, name='portal_logout_api'),
    path('cliente/empresa/<int:empresa_id>/api/agendamentos/', views.cliente_agendamentos_api, name='cliente_agendamentos_api'),
    path('cliente/empresa/<int:empresa_id>/api/agendamentos/<int:agendamento_id>/cancelar/', views.cliente_agendamento_cancelar_api, name='cliente_agendamento_cancelar_api'),
    path('cliente/empresa/<int:empresa_id>/api/agendamentos/<int:agendamento_id>/remarcar/', views.cliente_agendamento_remarcar_api, name='cliente_agendamento_remarcar_api'),
]
