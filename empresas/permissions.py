def is_global_admin(user):
    return bool(user.is_authenticated and (user.is_staff or user.is_superuser))


def get_profissional_profile(user):
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "profissional_profile", None)


def is_profissional_user(user):
    return get_profissional_profile(user) is not None and not is_global_admin(user)
