"""
URL configuration for easyschedule project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve


urlpatterns = [
    path("admin/", admin.site.urls),
    path("pessoa/", include("pessoa.urls")),
    path("servicos/", include("servicos.urls")),
    path("produtos/", include("produtos.urls")),
    path("profissionais/", include("profissionais.urls")),
    path("agendamentos/", include("agendamentos.urls")),
    path("relatorios/", include("relatorios.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("empresas/", include("empresas.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
