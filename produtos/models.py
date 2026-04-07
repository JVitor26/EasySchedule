from django.db import models

from empresas.models import Empresa


class Produto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nome = models.CharField(max_length=255)
    categoria = models.CharField(max_length=100, blank=True)
    descricao = models.TextField(blank=True)
    especificacoes = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    estoque = models.PositiveIntegerField(default=0)
    estoque_reservado = models.PositiveIntegerField(default=0, help_text="Quantidade reservada em agendamentos não pagos")
    foto = models.FileField(upload_to="produtos/", blank=True)
    ativo = models.BooleanField(default=True)
    destaque_publico = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome"]

    @property
    def estoque_disponivel(self):
        """Calcula estoque disponível (total - reservado)"""
        return self.estoque - self.estoque_reservado

    def __str__(self):
        return self.nome

