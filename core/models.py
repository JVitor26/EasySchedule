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
