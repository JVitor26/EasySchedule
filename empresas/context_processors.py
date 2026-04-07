from .tenancy import (
    get_accessible_empresas,
    get_active_empresa,
    user_has_global_empresa_access,
)
from .business_profiles import get_business_profile
from .permissions import is_profissional_user


def empresa_context(request):
    user = getattr(request, "user", None)

    if not user or not user.is_authenticated:
        return {}

    empresa_atual = get_active_empresa(request)

    return {
        "empresa_atual": empresa_atual,
        "empresas_disponiveis": get_accessible_empresas(request),
        "usuario_tem_acesso_global_empresa": user_has_global_empresa_access(user),
        "usuario_e_profissional": is_profissional_user(user),
        "business_profile": get_business_profile(empresa_atual.tipo if empresa_atual else None),
    }
