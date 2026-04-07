from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_home, name='dashboard_home'),
    path('configuracao/', views.dashboard_settings, name='dashboard_settings'),
]