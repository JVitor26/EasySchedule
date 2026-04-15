from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

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
	receber_lembrete_24h = models.BooleanField(default=True)
	receber_lembrete_2h = models.BooleanField(default=True)
	atualizado_em = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("empresa", "cliente")


class ProgramaFidelidade(models.Model):
	empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="programa_fidelidade")
	ativo = models.BooleanField(default=False)
	pontos_por_real = models.DecimalField(max_digits=8, decimal_places=2, default=1)
	multiplicador_indicacao = models.DecimalField(max_digits=6, decimal_places=2, default=1.5)
	pontos_bonus_indicacao = models.PositiveIntegerField(default=50)
	ticket_minimo_indicacao = models.DecimalField(max_digits=10, decimal_places=2, default=0)
	atualizado_em = models.DateTimeField(auto_now=True)


class ClienteFidelidade(models.Model):
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="clientes_fidelidade")
	cliente = models.ForeignKey(Pessoa, on_delete=models.CASCADE, related_name="fidelidade")
	pontos_disponiveis = models.PositiveIntegerField(default=0)
	pontos_totais = models.PositiveIntegerField(default=0)
	codigo_indicacao = models.CharField(max_length=24, blank=True)
	indicador = models.ForeignKey(
		Pessoa,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="indicacoes_realizadas",
	)
	criado_em = models.DateTimeField(auto_now_add=True)
	atualizado_em = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("empresa", "cliente")


class FidelidadeMovimento(models.Model):
	ORIGEM_CHOICES = [
		("agendamento", "Agendamento"),
		("produto", "Produto"),
		("indicacao", "Indicacao"),
		("ajuste", "Ajuste"),
	]

	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
	cliente_fidelidade = models.ForeignKey(
		ClienteFidelidade,
		on_delete=models.CASCADE,
		related_name="movimentos",
	)
	origem = models.CharField(max_length=20, choices=ORIGEM_CHOICES)
	descricao = models.CharField(max_length=255, blank=True)
	pontos = models.IntegerField()
	referencia_id = models.CharField(max_length=64, blank=True)
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-criado_em"]


class NPSResposta(models.Model):
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="nps_respostas")
	cliente = models.ForeignKey(Pessoa, on_delete=models.SET_NULL, null=True, blank=True)
	agendamento = models.ForeignKey(
		"agendamentos.Agendamento",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="nps_respostas",
	)
	nota = models.PositiveSmallIntegerField()
	comentario = models.TextField(blank=True)
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-criado_em"]

	def clean(self):
		if self.nota < 0 or self.nota > 10:
			raise ValidationError({"nota": "A nota NPS deve estar entre 0 e 10."})


class AuditLog(models.Model):
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="audit_logs")
	ator_usuario = models.ForeignKey(
		User,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="audit_logs",
	)
	ator_cliente = models.ForeignKey(
		Pessoa,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="audit_logs",
	)
	acao = models.CharField(max_length=120)
	entidade = models.CharField(max_length=80, blank=True)
	entidade_id = models.CharField(max_length=64, blank=True)
	detalhes = models.JSONField(default=dict, blank=True)
	endereco_ip = models.GenericIPAddressField(blank=True, null=True)
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-criado_em"]


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


class StripeWebhookEvent(models.Model):
	PROCESSING_STATUS_CHOICES = [
		("processed", "Processed"),
		("ignored", "Ignored"),
		("failed", "Failed"),
	]

	event_id = models.CharField(max_length=255, unique=True, db_index=True)
	event_type = models.CharField(max_length=120)
	livemode = models.BooleanField(default=False)
	processing_status = models.CharField(
		max_length=20,
		choices=PROCESSING_STATUS_CHOICES,
		default="processed",
	)
	payload = models.JSONField(default=dict, blank=True)
	error_message = models.TextField(blank=True)
	criado_em = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-criado_em"]

	def __str__(self):
		return f"{self.event_type} ({self.event_id})"

