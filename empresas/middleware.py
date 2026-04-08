from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .permissions import get_profissional_profile


class AdminOnlyPlanProfessionalAccessMiddleware:
    """Blocks staff-professional logins for companies in admin-only plan."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if request.path_info in {
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/login-redirect/",
            "/accounts/recuperar-senha/",
            "/accounts/recuperar-senha/confirmar/",
        }:
            return self.get_response(request)

        if user and user.is_authenticated:
            profissional = get_profissional_profile(user)
            if profissional and not profissional.empresa.permite_acesso_profissional:
                logout(request)
                messages.error(
                    request,
                    "Esta empresa utiliza o plano somente administrador. "
                    "Funcionarios nao possuem acesso ao sistema.",
                )
                return redirect("login")

        return self.get_response(request)
