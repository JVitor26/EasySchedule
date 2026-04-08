import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria superusuário a partir das variáveis DJANGO_SUPERUSER_EMAIL, USERNAME e PASSWORD"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "admin")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "Variáveis DJANGO_SUPERUSER_EMAIL e DJANGO_SUPERUSER_PASSWORD não definidas. Pulando."
            ))
            return

        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.SUCCESS(f"Superusuário '{email}' já existe. Nenhuma ação."))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superusuário '{email}' criado com sucesso!"))
