from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from empresas.models import Empresa
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico

from .plans import WEEKDAY_CHOICES, normalize_month_reference, sync_monthly_plan_schedule


class Agendamento(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("confirmado", "Confirmado"),
        ("cancelado", "Cancelado"),
        ("finalizado", "Finalizado"),
    ]
    METODO_PAGAMENTO_CHOICES = [
        ("pix", "Pix"),
        ("cartao", "Cartão"),
        ("dinheiro", "Dinheiro"),
        ("transferencia", "Transferência"),
    ]
    PAGAMENTO_STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("pago", "Pago"),
        ("cancelado", "Cancelado"),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    plano = models.ForeignKey(
        "PlanoMensal",
        on_delete=models.CASCADE,
        related_name="agendamentos",
        blank=True,
        null=True,
    )
    cliente = models.ForeignKey(Pessoa, on_delete=models.CASCADE)
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE)
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE)
    data = models.DateField()
    hora = models.TimeField()
    observacoes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    metodo_pagamento = models.CharField(
        max_length=20,
        choices=METODO_PAGAMENTO_CHOICES,
        blank=True,
    )
    pagamento_status = models.CharField(
        max_length=20,
        choices=PAGAMENTO_STATUS_CHOICES,
        default="pendente",
    )

    def clean(self):
        errors = {}

        if self.data and self.data < timezone.localdate():
            original_date = None
            if self.pk:
                try:
                    original_date = self.__class__.objects.values_list('data', flat=True).get(pk=self.pk)
                except self.__class__.DoesNotExist:
                    original_date = None

            if original_date is None or original_date >= timezone.localdate():
                errors["data"] = "Não é possível agendar para uma data passada."

        if self.empresa_id:
            if self.cliente_id and self.cliente.empresa_id != self.empresa_id:
                errors["cliente"] = "O cliente selecionado não pertence a esta empresa."

            if self.servico_id and self.servico.empresa_id != self.empresa_id:
                errors["servico"] = "O serviço selecionado não pertence a esta empresa."

            if self.profissional_id and self.profissional.empresa_id != self.empresa_id:
                errors["profissional"] = "O profissional selecionado não pertence a esta empresa."

            if self.plano_id and self.plano.empresa_id != self.empresa_id:
                errors["plano"] = "O plano mensal selecionado não pertence a esta empresa."

        if self.plano_id:
            if self.cliente_id and self.plano.cliente_id != self.cliente_id:
                errors["cliente"] = "O cliente do agendamento precisa ser o mesmo do plano mensal."

            if self.servico_id and self.plano.servico_id != self.servico_id:
                errors["servico"] = "O serviço do agendamento precisa ser o mesmo do plano mensal."

            if self.profissional_id and self.plano.profissional_id != self.profissional_id:
                errors["profissional"] = "O profissional do agendamento precisa ser o mesmo do plano mensal."

        if self.data and self.hora and self.profissional_id and self.servico_id and self.empresa_id:
            from .availability import find_schedule_conflict

            conflito = find_schedule_conflict(
                empresa=self.empresa,
                profissional=self.profissional,
                servico=self.servico,
                data=self.data,
                hora=self.hora,
                exclude_agendamento_id=self.pk,
            )

            if conflito:
                errors["hora"] = (
                    f"Já existe um agendamento para {self.profissional.nome} em "
                    f'{self.data.strftime("%d/%m/%Y")} às {conflito.hora.strftime("%H:%M")}.'
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cliente} - {self.servico} em {self.data} {self.hora}"


class PlanoMensal(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("ativo", "Ativo"),
        ("cancelado", "Cancelado"),
    ]
    PAGAMENTO_STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("pago", "Pago"),
        ("cancelado", "Cancelado"),
        ("expirado", "Expirado"),
    ]
    METODO_PAGAMENTO_CHOICES = [
        ("pix", "Pix"),
        ("cartao", "Cartao"),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    cliente = models.ForeignKey(Pessoa, on_delete=models.CASCADE)
    servico = models.ForeignKey(Servico, on_delete=models.CASCADE)
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE)
    mes_referencia = models.DateField()
    dia_semana = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES)
    hora = models.TimeField()
    observacoes = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    pagamento_status = models.CharField(
        max_length=20,
        choices=PAGAMENTO_STATUS_CHOICES,
        default="pendente",
    )
    metodo_pagamento = models.CharField(
        max_length=20,
        choices=METODO_PAGAMENTO_CHOICES,
        blank=True,
    )
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantidade_encontros = models.PositiveIntegerField(default=0)
    detalhes_pagamento = models.CharField(max_length=255, blank=True)
    pago_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-mes_referencia", "-criado_em"]

    def clean(self):
        errors = {}
        mes_referencia = normalize_month_reference(self.mes_referencia)

        if mes_referencia and mes_referencia < normalize_month_reference(timezone.localdate()):
            errors["mes_referencia"] = "Escolha o mês atual ou um mês futuro para o pacote."

        if self.empresa_id:
            if self.cliente_id and self.cliente.empresa_id != self.empresa_id:
                errors["cliente"] = "O cliente do plano mensal nao pertence a esta empresa."

            if self.servico_id and self.servico.empresa_id != self.empresa_id:
                errors["servico"] = "O servico do plano mensal nao pertence a esta empresa."

            if self.profissional_id and self.profissional.empresa_id != self.empresa_id:
                errors["profissional"] = "O profissional do plano mensal nao pertence a esta empresa."

        if self.valor_mensal is not None and self.valor_mensal < 0:
            errors["valor_mensal"] = "O valor mensal nao pode ser negativo."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.mes_referencia:
            self.mes_referencia = normalize_month_reference(self.mes_referencia)

        self.clean()
        super().save(*args, **kwargs)

    def sync_schedule(self):
        return sync_monthly_plan_schedule(self)

    def mark_as_paid(self, metodo=None, detalhes=""):
        if metodo:
            self.metodo_pagamento = metodo

        self.pagamento_status = "pago"
        self.status = "ativo"
        self.pago_em = timezone.now()
        self.detalhes_pagamento = detalhes or self.detalhes_pagamento
        self.save()
        self.sync_schedule()

        self.agendamentos.update(status="confirmado")

    @property
    def first_occurrence(self):
        return self.agendamentos.order_by("data", "hora").first()

    @property
    def month_label(self):
        return self.mes_referencia.strftime("%m/%Y")

    def __str__(self):
        return (
            f"Plano mensal de {self.cliente} - {self.servico} "
            f"({self.get_dia_semana_display()} {self.hora.strftime('%H:%M')})"
        )


class NotificacaoProfissional(models.Model):
    profissional = models.ForeignKey(
        Profissional,
        on_delete=models.CASCADE,
        related_name="notificacoes",
    )
    agendamento = models.ForeignKey(
        Agendamento,
        on_delete=models.CASCADE,
        related_name="notificacoes_profissional",
    )
    titulo = models.CharField(max_length=120)
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criada_em"]

    def __str__(self):
        return f"{self.profissional.nome}: {self.titulo}"
