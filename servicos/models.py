from django.db import models
from empresas.models import Empresa	

class Servico(models.Model):
	empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
 
	nome = models.CharField(max_length=255)
	categoria = models.CharField(max_length=50)
	descricao = models.TextField(blank=True, null=True)
	preco = models.DecimalField(max_digits=10, decimal_places=2)
	tempo = models.PositiveIntegerField(help_text='Duração em minutos')
	cor = models.CharField(max_length=7, default='#22c55e')
	ativo = models.BooleanField(default=True)
    
	def __str__(self):
		return self.nome
