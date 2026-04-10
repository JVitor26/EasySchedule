from django.db import models

from empresas.models import Empresa
from pessoa.models import Pessoa


class Produto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    nome = models.CharField(max_length=255)
    categoria = models.CharField(max_length=100, blank=True)
    descricao = models.TextField(blank=True)
    especificacoes = models.TextField(blank=True)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    valor_compra = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Valor pago na compra/aquisição do produto")
    custo = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Custo operacional total do produto")
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Valor cobrado na venda ao cliente")
    estoque = models.PositiveIntegerField(default=0)
    estoque_reservado = models.PositiveIntegerField(default=0, help_text="Quantidade reservada em agendamentos não pagos")
    foto = models.ImageField(upload_to="produtos/", blank=True)
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


class VendaProduto(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="vendas_produtos")
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name="vendas")
    cliente = models.ForeignKey(
        Pessoa,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compras_produtos",
    )
    cliente_nome_avulso = models.CharField(max_length=255, blank=True, help_text="Nome do cliente se não cadastrado")
    valor_venda = models.DecimalField(max_digits=10, decimal_places=2, help_text="Valor cobrado na venda")
    data_venda = models.DateField(help_text="Data em que a venda foi realizada")
    data_pagamento = models.DateField(null=True, blank=True, help_text="Data em que o pagamento foi recebido")
    data_entrega = models.DateField(
        null=True,
        blank=True,
        help_text="Data prevista para retirada/entrega do produto",
    )
    agendamento = models.ForeignKey(
        "agendamentos.Agendamento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="vendas_produtos",
    )
    observacoes = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_venda", "-criado_em"]

    @property
    def nome_cliente(self):
        if self.cliente:
            return self.cliente.nome
        return self.cliente_nome_avulso or "—"

    @property
    def pago(self):
        return self.data_pagamento is not None

    def __str__(self):
        return f"{self.produto.nome} — {self.nome_cliente} em {self.data_venda}"

