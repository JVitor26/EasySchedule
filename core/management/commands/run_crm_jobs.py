from django.core.management.base import BaseCommand

from empresas.models import Empresa
from core.jobs import run_reengagement_for_empresa, run_reminders_for_empresa


class Command(BaseCommand):
    help = "Executa jobs recorrentes de lembretes e reengajamento por empresa."

    def add_arguments(self, parser):
        parser.add_argument("--empresa-id", type=int, default=None)
        parser.add_argument("--skip-reminders", action="store_true")
        parser.add_argument("--skip-reengagement", action="store_true")

    def handle(self, *args, **options):
        empresa_id = options["empresa_id"]
        skip_reminders = options["skip_reminders"]
        skip_reengagement = options["skip_reengagement"]

        queryset = Empresa.objects.all().order_by("id")
        if empresa_id:
            queryset = queryset.filter(pk=empresa_id)

        total_empresas = 0
        for empresa in queryset:
            total_empresas += 1
            self.stdout.write(f"Empresa {empresa.id} - {empresa.nome}")

            if not skip_reminders:
                reminder_result = run_reminders_for_empresa(empresa)
                self.stdout.write(
                    f"  Lembretes enviados -> 24h: {reminder_result['24h']} | 2h: {reminder_result['2h']}"
                )

            if not skip_reengagement:
                reengagement_result = run_reengagement_for_empresa(empresa)
                self.stdout.write(
                    "  Reengajamento -> candidatos: "
                    f"{reengagement_result['candidatos']} | enviados: {reengagement_result['enviados']}"
                )

        self.stdout.write(self.style.SUCCESS(f"Jobs finalizados para {total_empresas} empresa(s)."))
