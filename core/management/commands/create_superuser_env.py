import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models import Q


class Command(BaseCommand):
    help = "Cria superusuário a partir das variáveis DJANGO_SUPERUSER_EMAIL, USERNAME e PASSWORD"

    def handle(self, *args, **kwargs):
        User = get_user_model()

        email = (os.environ.get("DJANGO_SUPERUSER_EMAIL") or "").strip().lower()
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

        self.stdout.write(
            f"Bootstrap de superusuário: username='{username}', email='{email}', reset_password={reset_password}"
        )

        existing = (
            User.objects.filter(email__iexact=email).order_by("id").first()
            or User.objects.filter(username__iexact=username).order_by("id").first()
        )
        if existing:
            changed_fields = []

            if existing.email != email:
                existing.email = email
                changed_fields.append("email")

            if not existing.is_active:
                existing.is_active = True
                changed_fields.append("is_active")

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

        try:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superusuário '{email}' criado com sucesso!"))
        except IntegrityError:
            conflicted = User.objects.filter(Q(email__iexact=email) | Q(username__iexact=username)).order_by("id").first()
            if not conflicted:
                raise

            changed_fields = []
            if conflicted.email != email:
                conflicted.email = email
                changed_fields.append("email")
            if not conflicted.is_active:
                conflicted.is_active = True
                changed_fields.append("is_active")
            if not conflicted.is_staff:
                conflicted.is_staff = True
                changed_fields.append("is_staff")
            if not conflicted.is_superuser:
                conflicted.is_superuser = True
                changed_fields.append("is_superuser")
            if reset_password:
                conflicted.set_password(password)
                changed_fields.append("password")

            if changed_fields:
                conflicted.save(update_fields=changed_fields)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Superusuário '{email}' ajustado após conflito ({', '.join(changed_fields)})."
                    )
                )
            else:
                self.stdout.write(self.style.SUCCESS(f"Superusuário '{email}' já existe. Nenhuma ação."))
