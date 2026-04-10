PROFISSIONAL_ACCESS_DASHBOARD = "dashboard"
PROFISSIONAL_ACCESS_AGENDAMENTOS = "agendamentos"
PROFISSIONAL_ACCESS_CLIENTES = "clientes"
PROFISSIONAL_ACCESS_SERVICOS = "servicos"
PROFISSIONAL_ACCESS_PRODUTOS = "produtos"
PROFISSIONAL_ACCESS_RELATORIOS = "relatorios"

PROFISSIONAL_MODULE_CHOICES = [
    (PROFISSIONAL_ACCESS_AGENDAMENTOS, "Agenda"),
    (PROFISSIONAL_ACCESS_CLIENTES, "Clientes"),
    (PROFISSIONAL_ACCESS_SERVICOS, "Servicos"),
    (PROFISSIONAL_ACCESS_PRODUTOS, "Produtos"),
    (PROFISSIONAL_ACCESS_RELATORIOS, "Relatorios"),
]

PROFISSIONAL_MANAGED_MODULE_KEYS = tuple(key for key, _label in PROFISSIONAL_MODULE_CHOICES)
DEFAULT_PROFISSIONAL_MODULES = (PROFISSIONAL_ACCESS_AGENDAMENTOS,)


def is_global_admin(user):
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def get_profissional_profile(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "profissional_profile", None)


def is_profissional_user(user):
    return get_profissional_profile(user) is not None and not is_global_admin(user)


def normalize_profissional_modules(values):
    if not isinstance(values, (list, tuple, set)):
        values = []

    normalized = []
    for key in values:
        if key in PROFISSIONAL_MANAGED_MODULE_KEYS and key not in normalized:
            normalized.append(key)

    if not normalized:
        normalized = list(DEFAULT_PROFISSIONAL_MODULES)

    return normalized


def get_profissional_allowed_modules(user):
    profissional = get_profissional_profile(user)
    if not profissional:
        return []

    current = getattr(profissional, "acessos_modulos", [])
    return normalize_profissional_modules(current)


def user_can_access_module(user, module_key):
    if not user or not user.is_authenticated:
        return False

    if is_global_admin(user):
        return True

    profissional = get_profissional_profile(user)
    if not profissional:
        return True

    if module_key == PROFISSIONAL_ACCESS_DASHBOARD:
        return True

    return module_key in get_profissional_allowed_modules(user)


def user_module_access_map(user):
    is_profissional = is_profissional_user(user)
    return {
        "dashboard": user_can_access_module(user, PROFISSIONAL_ACCESS_DASHBOARD),
        "agendamentos": user_can_access_module(user, PROFISSIONAL_ACCESS_AGENDAMENTOS),
        "clientes": user_can_access_module(user, PROFISSIONAL_ACCESS_CLIENTES),
        "servicos": user_can_access_module(user, PROFISSIONAL_ACCESS_SERVICOS),
        "produtos": user_can_access_module(user, PROFISSIONAL_ACCESS_PRODUTOS),
        "relatorios": user_can_access_module(user, PROFISSIONAL_ACCESS_RELATORIOS),
        "is_profissional": is_profissional,
    }


def can_manage_empresa_settings(user, empresa):
    if not user or not user.is_authenticated or empresa is None:
        return False

    if is_global_admin(user):
        return True

    if is_profissional_user(user):
        return False

    try:
        return user.empresa.id == empresa.id
    except Exception:
        return False
