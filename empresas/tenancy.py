from .models import Empresa
from .permissions import get_profissional_profile, is_global_admin

EMPRESA_SESSION_KEY = "empresa_ativa_id"
_CACHE_MISSING = object()


def user_has_global_empresa_access(user):
    return is_global_admin(user)


def get_accessible_empresas(request):
    cached = getattr(request, "_cached_empresas_disponiveis", _CACHE_MISSING)
    if cached is not _CACHE_MISSING:
        return cached

    user = request.user

    if not user.is_authenticated:
        empresas = Empresa.objects.none()
    elif user_has_global_empresa_access(user):
        empresas = Empresa.objects.all().order_by("nome")
    else:
        profissional = get_profissional_profile(user)
        if profissional:
            empresas = Empresa.objects.filter(pk=profissional.empresa_id)
        else:
            try:
                empresa = user.empresa
            except Empresa.DoesNotExist:
                empresas = Empresa.objects.none()
            else:
                empresas = Empresa.objects.filter(pk=empresa.pk)

    request._cached_empresas_disponiveis = empresas
    return empresas


def get_active_empresa(request):
    cached = getattr(request, "_cached_empresa_atual", _CACHE_MISSING)
    if cached is not _CACHE_MISSING:
        return cached

    empresas = get_accessible_empresas(request)
    empresa = None

    if request.user.is_authenticated:
        if user_has_global_empresa_access(request.user):
            empresa_id = request.session.get(EMPRESA_SESSION_KEY)
            if empresa_id:
                empresa = empresas.filter(pk=empresa_id).first()

            if empresa is None:
                empresa = empresas.first()
                if empresa is not None:
                    request.session[EMPRESA_SESSION_KEY] = empresa.pk
        else:
            empresa = empresas.first()

    request._cached_empresa_atual = empresa
    return empresa


def set_active_empresa(request, empresa):
    request.session[EMPRESA_SESSION_KEY] = empresa.pk
    request._cached_empresa_atual = empresa
