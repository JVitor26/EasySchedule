from django.db import models
from django.utils import timezone

from django.contrib.auth.models import User

from empresas.models import Empresa
from pessoa.models import Pessoa


class ClientePortalOTP(models.Model):
	CANAL_CHOICES = [
		("whatsapp", "WhatsApp"),
		("email", "Email"),
	]

	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
	cliente = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name="portal_otps")
	canal = models.CharField(max_length=20, choices=CANAL_CHOICES)
	codigo = models.CharField(max_length=6)
	expira_em = models.DateTimeField()
	usado_em = models.DateTimeField(blank=True, null=True)
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-criado_em"]

	@property
	def expirado(self):
		return timezone.now() >= self.expira_em

	@property
	def disponivel(self):
		return self.usado_em is None and not self.expirado


class ClientePortalPreferencia(models.Model):
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
	cliente = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name="portal_preferencias")
	receber_whatsapp = models.BooleanField(default=True)
	receber_email = models.BooleanField(default=True)
	receber_marketing = models.BooleanField(default=False)
	atualizado_em = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("empresa", "cliente")


class PasswordRecoveryCode(models.Model):
	CANAL_CHOICES = [
		("whatsapp", "WhatsApp"),
		("email", "Email"),
	]

	ACCOUNT_TYPE_CHOICES = [
		("internal", "Conta interna"),
		("client", "Cliente do portal"),
	]

	account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
	canal = models.CharField(max_length=20, choices=CANAL_CHOICES)
	codigo = models.CharField(max_length=6)
	expira_em = models.DateTimeField()
	usado_em = models.DateTimeField(blank=True, null=True)
	criado_em = models.DateTimeField(auto_now_add=True)
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="password_recovery_codes", blank=True, null=True)
	cliente = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name="password_recovery_codes", blank=True, null=True)
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="password_recovery_codes", blank=True, null=True)

	class Meta:
		ordering = ["-criado_em"]

	@property
	def expirado(self):
		return timezone.now() >= self.expira_em

	@property
	def disponivel(self):
		return self.usado_em is None and not self.expirado


class StripeTransaction(models.Model):
	"""
	Tracks all Stripe transactions for payments and subscriptions.
	Supports centralized model (all charges go to platform account).
	Ready for migration to Stripe Connect (each company has own account).
	"""

	OBJECT_TYPE_CHOICES = [
		("agendamento", "Agendamento"),
		("plano", "Plano mensal"),
	]

	STATUS_CHOICES = [
		("pending", "Pendente"),
		("processing", "Processando"),
		("succeeded", "Sucesso"),
		("failed", "Falha"),
		("canceled", "Cancelado"),
		("refunded", "Reembolsado"),
	]

	# Transaction info
	stripe_session_id = models.CharField(max_length=255, unique=True, db_index=True)  # Checkout Session ID
	stripe_payment_intent_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)  # Payment Intent ID
	stripe_customer_id = models.CharField(max_length=255, blank=True, null=True)  # Customer ID or None for guests
	
	# Link to our models
	empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="stripe_transactions")
	object_type = models.CharField(max_length=20, choices=OBJECT_TYPE_CHOICES)
	object_id = models.PositiveIntegerField()  # ID of Pagamento or PlanoMensal
	
	# Financial data
	amount_total = models.DecimalField(max_digits=10, decimal_places=2)  # Total in cents (from Stripe)
	currency = models.CharField(max_length=3, default='BRL')
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
	
	# Customer data
	customer_email = models.EmailField()
	customer_name = models.CharField(max_length=255, blank=True)
	
	# Stripe webhook info
	webhook_received_at = models.DateTimeField(blank=True, null=True)
	webhook_data = models.JSONField(default=dict, blank=True)  # Full webhook payload
	
	# Reconciliation
	synced_at = models.DateTimeField(blank=True, null=True)  # When we marked the payment as paid locally
	failure_reason = models.TextField(blank=True)
	refund_reason = models.TextField(blank=True)
	
	# Timestamps
	criado_em = models.DateTimeField(auto_now_add=True)
	atualizado_em = models.DateTimeField(auto_now=True)

	class Meta:
		ordering = ["-criado_em"]
		indexes = [
			models.Index(fields=['empresa', 'status']),
			models.Index(fields=['object_type', 'object_id']),
		]

	def __str__(self):
		return f"Stripe {self.object_type} - {self.stripe_session_id[:12]}... ({self.status})"

	@property
	def is_successful(self):
		return self.status == 'succeeded'

	@property
	def is_failed(self):
		return self.status in ['failed', 'canceled']

	@property
	def is_pending(self):
		return self.status in ['pending', 'processing']
