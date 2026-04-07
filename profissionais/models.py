from django.db import models
from empresas.models import Empresa	

class Profissional(models.Model):
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
	nome = models.CharField(max_length=100)
	especialidade = models.CharField(max_length=100)
	telefone = models.CharField(max_length=20)
	email = models.EmailField(blank=True, null=True)
	cpf = models.CharField(max_length=14, blank=True, null=True)
	data_nascimento = models.DateField(blank=True, null=True)
	endereco = models.CharField(max_length=255, blank=True, null=True)
	ativo = models.BooleanField(default=True)
	observacoes = models.TextField(blank=True, null=True)

	def __str__(self):
		return self.nome
