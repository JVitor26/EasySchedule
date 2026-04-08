import uuid

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils import timezone

from empresas.models import Empresa
from pessoa.models import Pessoa
from profissionais.models import Profissional
from servicos.models import Servico

from .plans import WEEKDAY_CHOICES, normalize_month_reference, sync_monthly_plan_schedule


PAYMENT_STATUS_CHOICES = [
    ("pendente", "Pendente"),
    ("pago", "Pago"),
    ("cancelado", "Cancelado"),
    ("expirado", "Expirado"),
]
PAYMENT_METHOD_CHOICES = [
    ("pix", "Pix"),
    ("cartao", "Cartao"),
]


class Agendamento(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("confirmado", "Confirmado"),
        ("cancelado", "Cancelado"),
        ("finalizado", "Finalizado"),
    ]
    FORMA_PAGAMENTO_CHOICES = [
        ("dinheiro", "Dinheiro"),
        ("cartao", "Cartão"),
        ("pix", "Pix"),
        ("outro", "Outro"),
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
    forma_pagamento = models.CharField(
        max_length=20,
        choices=FORMA_PAGAMENTO_CHOICES,
        blank=True,
        null=True,
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

    @property
    def payment_record(self):
        try:
            return self.pagamento
        except ObjectDoesNotExist:
            return None

    @property
    def payment_status_code(self):
        if self.plano_id:
            return "success" if self.plano.pagamento_status == "pago" else "warning"
        if self.payment_record:
            if self.payment_record.status == "pago":
                return "success"
            if self.payment_record.status == "pendente":
                return "warning"
            return "danger"
        return "info"

    @property
    def payment_status_label(self):
        if self.plano_id:
            prefix = "no pacote mensal"
            if self.plano.pagamento_status == "pago":
                return f"Pago {prefix}"
            return f"{self.plano.get_pagamento_status_display()} {prefix}"
        if self.payment_record:
            return self.payment_record.get_status_display()
        return "-"

    @property
    def payment_method_label(self):
        if self.plano_id and self.plano.metodo_pagamento:
            return self.plano.get_metodo_pagamento_display()
        return self.get_forma_pagamento_display() or "-"


class PlanoMensal(models.Model):
    STATUS_CHOICES = [
        ("pendente", "Pendente"),
        ("ativo", "Ativo"),
        ("cancelado", "Cancelado"),
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
        choices=PAYMENT_STATUS_CHOICES,
        default="pendente",
    )
    metodo_pagamento = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        blank=True,
    )
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantidade_encontros = models.PositiveIntegerField(default=0)
    referencia_publica = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    referencia_pagamento = models.CharField(max_length=40, unique=True, blank=True)
    codigo_pix = models.CharField(max_length=255, blank=True)
    detalhes_pagamento = models.CharField(max_length=255, blank=True)
    pago_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    # Stripe integration (centralized model)
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text="Stripe Checkout Session ID")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Payment Intent ID")
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Customer ID (optional for guests)")
    stripe_synced_at = models.DateTimeField(blank=True, null=True, help_text="Last sync with Stripe")

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
        update_fields = kwargs.get("update_fields")
        creating = self.pk is None

        if self.mes_referencia:
            self.mes_referencia = normalize_month_reference(self.mes_referencia)

        if not self.referencia_pagamento:
            self.referencia_pagamento = f"PLAN-{uuid.uuid4().hex[:12].upper()}"

        self.codigo_pix = (
            f"PLANOPIX|{self.empresa_id}|{self.pk or 'novo'}|"
            f"{self.valor_mensal:.2f}|{self.referencia_pagamento}"
        )

        self.clean()
        super().save(*args, **kwargs)

        refreshed_code = (
            f"PLANOPIX|{self.empresa_id}|{self.pk}|"
            f"{self.valor_mensal:.2f}|{self.referencia_pagamento}"
        )
        if creating or (update_fields and "valor_mensal" in update_fields):
            if self.codigo_pix != refreshed_code:
                self.codigo_pix = refreshed_code
                super().save(update_fields=["codigo_pix", "atualizado_em"])

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

        self.agendamentos.update(
            status="confirmado",
            forma_pagamento=self.metodo_pagamento or None,
        )

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


class Pagamento(models.Model):
    STATUS_CHOICES = PAYMENT_STATUS_CHOICES
    METODO_CHOICES = PAYMENT_METHOD_CHOICES

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    agendamento = models.OneToOneField(
        Agendamento,
        on_delete=models.CASCADE,
        related_name="pagamento",
    )
    cliente = models.ForeignKey(Pessoa, on_delete=models.CASCADE)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES, default="pix")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pendente")
    referencia_publica = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    referencia_pagamento = models.CharField(max_length=40, unique=True, blank=True)
    codigo_pix = models.CharField(max_length=255, blank=True)
    detalhes = models.CharField(max_length=255, blank=True)
    pago_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    # Stripe integration (centralized model)
    stripe_session_id = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text="Stripe Checkout Session ID")
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Payment Intent ID")
    stripe_customer_id = models.CharField(max_length=255, blank=True, null=True, help_text="Stripe Customer ID (optional for guests)")
    stripe_synced_at = models.DateTimeField(blank=True, null=True, help_text="Last sync with Stripe")

    class Meta:
        ordering = ["-criado_em"]

    def clean(self):
        errors = {}

        if self.empresa_id:
            if self.agendamento_id and self.agendamento.empresa_id != self.empresa_id:
                errors["agendamento"] = "O agendamento nao pertence a esta empresa."

            if self.cliente_id and self.cliente.empresa_id != self.empresa_id:
                errors["cliente"] = "O cliente do pagamento nao pertence a esta empresa."

        if self.agendamento_id and self.cliente_id and self.agendamento.cliente_id != self.cliente_id:
            errors["cliente"] = "O cliente do pagamento precisa ser o mesmo cliente do agendamento."

        if self.valor is not None and self.valor < 0:
            errors["valor"] = "O valor do pagamento nao pode ser negativo."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.referencia_pagamento:
            self.referencia_pagamento = f"PAY-{uuid.uuid4().hex[:12].upper()}"

        if self.agendamento_id:
            self.codigo_pix = (
                f"PIX|{self.empresa_id}|{self.agendamento_id}|"
                f"{self.valor:.2f}|{self.referencia_pagamento}"
            )

        self.clean()
        super().save(*args, **kwargs)

    def mark_as_paid(self, metodo=None, detalhes=""):
        if metodo:
            self.metodo = metodo

        self.status = "pago"
        self.pago_em = timezone.now()
        self.detalhes = detalhes or self.detalhes
        self.save()

        self.agendamento.forma_pagamento = self.metodo
        if self.agendamento.status == "pendente":
            self.agendamento.status = "confirmado"
        self.agendamento.save()
        
        # Processar produtos pagos
        self._process_paid_products()

    def _process_paid_products(self):
        """
        Ao confirmar pagamento, marca todos os produtos como pagos
        e deduz do estoque (sai de reservado para vendido)
        """
        produtos_agendamento = self.agendamento.produtos.filter(pagamento_status="reservado")
        for ap in produtos_agendamento:
            ap.marcar_como_pago()

    def marcar_apenas_servico_pago(self):
        """
        Se apenas o serviço foi pago e não os produtos,
        devolve os produtos para o estoque (cancela reserva)
        """
        produtos_agendamento = self.agendamento.produtos.filter(pagamento_status="reservado")
        for ap in produtos_agendamento:
            ap.desfazer_reserva()

    @classmethod
    def sync_for_agendamento(cls, agendamento):
        defaults = {
            "empresa": agendamento.empresa,
            "cliente": agendamento.cliente,
            "valor": agendamento.servico.preco,
        }
        pagamento, _created = cls.objects.get_or_create(
            agendamento=agendamento,
            defaults=defaults,
        )

        needs_save = False
        for field, value in defaults.items():
            if getattr(pagamento, field) != value:
                setattr(pagamento, field, value)
                needs_save = True

        if needs_save:
            pagamento.save()

        return pagamento

    def __str__(self):
        return f"Pagamento {self.referencia_pagamento} - {self.get_status_display()}"


class AgendamentoProduto(models.Model):
    """
    Modelo intermediário entre Agendamento e Produto para gerenciar:
    - Produtos adicionados ao agendamento
    - Quantidade de cada produto
    - Status de pagamento (reservado, pago ou cancelado)
    - Histórico de preço (em caso de alteração no catálogo)
    """
    PAGAMENTO_STATUS_CHOICES = [
        ("reservado", "Reservado"),
        ("pago", "Pago"),
        ("cancelado", "Cancelado"),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    agendamento = models.ForeignKey(
        Agendamento,
        on_delete=models.CASCADE,
        related_name="produtos",
    )
    produto = models.ForeignKey(
        "produtos.Produto",
        on_delete=models.CASCADE,
        related_name="agendamentos",
    )
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    pagamento_status = models.CharField(
        max_length=20,
        choices=PAGAMENTO_STATUS_CHOICES,
        default="reservado",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("agendamento", "produto")
        ordering = ["criado_em"]

    def clean(self):
        errors = {}

        if self.empresa_id:
            if self.agendamento_id and self.agendamento.empresa_id != self.empresa_id:
                errors["agendamento"] = "O agendamento não pertence a esta empresa."

            if self.produto_id and self.produto.empresa_id != self.empresa_id:
                errors["produto"] = "O produto não pertence a esta empresa."

        if self.quantidade is not None and self.quantidade <= 0:
            errors["quantidade"] = "A quantidade deve ser maior que zero."

        if self.preco_unitario is not None and self.preco_unitario < 0:
            errors["preco_unitario"] = "O preço não pode ser negativo."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self.preco_unitario:
            self.preco_unitario = self.produto.preco
        self.clean()
        super().save(*args, **kwargs)

    @property
    def preco_total(self):
        """Calcula o preço total do item (quantidade × preço unitário)"""
        return self.quantidade * self.preco_unitario

    def marcar_como_pago(self):
        """Marca o produto como pago e deduz do estoque"""
        self.pagamento_status = "pago"
        self.save()

        # Deduz do estoque
        self.produto.estoque -= self.quantidade
        self.produto.estoque_reservado -= self.quantidade
        self.produto.save()

    def desfazer_reserva(self):
        """Remove a reserva e devolve ao estoque disponível"""
        self.pagamento_status = "cancelado"
        self.save()

        # Devolve ao estoque
        self.produto.estoque_reservado -= self.quantidade
        self.produto.save()

    def __str__(self):
        return f"{self.agendamento} - {self.produto.nome} ({self.quantidade}x)"


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
