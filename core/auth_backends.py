from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameModelBackend(ModelBackend):
    """Allow authentication using either username or e-mail."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)

        if username is None or password is None:
            return None

        login_value = str(username).strip()
        if not login_value:
            return None

        UserModel = get_user_model()
        users = UserModel._default_manager.filter(
            Q(username__iexact=login_value) | Q(email__iexact=login_value)
        ).order_by("id")

        for user in users[:5]:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None
