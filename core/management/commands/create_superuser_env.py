import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Cria superusuário a partir das variáveis DJANGO_SUPERUSER_EMAIL, USERNAME e PASSWORD"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip() or email
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        reset_password = os.environ.get("DJANGO_SUPERUSER_RESET_PASSWORD", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "Variáveis DJANGO_SUPERUSER_EMAIL e DJANGO_SUPERUSER_PASSWORD não definidas. Pulando."
            ))
            return

        existing = User.objects.filter(email=email).first()
        if existing:
            changed_fields = []

            if not existing.is_staff:
                existing.is_staff = True
                changed_fields.append("is_staff")

            if not existing.is_superuser:
                existing.is_superuser = True
                changed_fields.append("is_superuser")

            if username and existing.username != username and not User.objects.filter(username=username).exclude(pk=existing.pk).exists():
                existing.username = username
                changed_fields.append("username")

            if reset_password:
                existing.set_password(password)
                changed_fields.append("password")

            if changed_fields:
                existing.save(update_fields=changed_fields)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Superusuário '{email}' atualizado com sucesso ({', '.join(changed_fields)})."
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"Superusuário '{email}' já existe. Nenhuma ação."))
            return

        User.objects.create_superuser(username=username, email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Superusuário '{email}' criado com sucesso!"))
