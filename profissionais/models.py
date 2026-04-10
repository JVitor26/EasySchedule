from django.db import models
from django.contrib.auth.models import User
from empresas.models import Empresa	
from empresas.permissions import normalize_profissional_modules, PROFISSIONAL_MODULE_CHOICES

class Profissional(models.Model):
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
	usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='profissional_profile')
	acessos_modulos = models.JSONField(blank=True, default=list)
	nome = models.CharField(max_length=100)
	especialidade = models.CharField(max_length=100)
	telefone = models.CharField(max_length=20)
	email = models.EmailField(blank=True, null=True)
	cpf = models.CharField(max_length=14, blank=True, null=True)
	data_nascimento = models.DateField(blank=True, null=True)
	endereco = models.CharField(max_length=255, blank=True, null=True)
	ativo = models.BooleanField(default=True)
	observacoes = models.TextField(blank=True, null=True)

	MODULE_CHOICES = PROFISSIONAL_MODULE_CHOICES

	def get_allowed_modules(self):
		return normalize_profissional_modules(self.acessos_modulos)

	def has_module_access(self, module_key):
		if module_key == "dashboard":
			return True
		return module_key in self.get_allowed_modules()

	def save(self, *args, **kwargs):
		self.acessos_modulos = self.get_allowed_modules()
		super().save(*args, **kwargs)

	def __str__(self):
		return self.nome
