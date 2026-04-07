from django.db import models
from django.contrib.auth.models import User
from empresas.models import Empresa
import uuid


class TipoRelatorio(models.TextChoices):
    AGENDAMENTOS = 'agendamentos', 'Agendamentos'
    FATURAMENTO = 'faturamento', 'Faturamento'
    PROFISSIONAIS = 'profissionais', 'Profissionais'
    CLIENTES = 'clientes', 'Clientes'
    CANCELAMENTOS = 'cancelamentos', 'Cancelamentos'
    OCUPACAO = 'ocupacao', 'Ocupação'
    PERSONALIZADO = 'personalizado', 'Personalizado'


class FormatoExportacao(models.TextChoices):
    PDF = 'pdf', 'PDF'
    EXCEL = 'excel', 'Excel'
    CSV = 'csv', 'CSV'


class Relatorio(models.Model):
    """
    Configuração do relatório
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    nome = models.CharField(max_length=255)
    descricao = models.TextField(blank=True)

    tipo = models.CharField(max_length=30, choices=TipoRelatorio.choices)

    # 🔎 Filtros principais (otimizados para seu sistema)
    data_inicio = models.DateField(blank=True, null=True)
    data_fim = models.DateField(blank=True, null=True)

    profissional = models.ForeignKey(
        'profissionais.Profissional',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    servico = models.ForeignKey(
        'servicos.Servico',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    cliente = models.ForeignKey(
        'pessoa.Pessoa',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    status = models.CharField(max_length=20, blank=True, null=True)

    # 🔥 Filtros avançados (flexível)
    filtros = models.JSONField(blank=True, null=True)

    # 📊 Configuração de visualização
    agrupar_por = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Ex: dia, mes, profissional, servico"
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    ativo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nome} ({self.empresa.nome})"


class ExecucaoRelatorio(models.Model):
    """
    Execução do relatório (histórico + arquivos)
    """
    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('processando', 'Processando'),
        ('concluido', 'Concluído'),
        ('erro', 'Erro'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)

    relatorio = models.ForeignKey(
        Relatorio,
        on_delete=models.CASCADE,
        related_name='execucoes'
    )

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pendente')

    formato = models.CharField(max_length=10, choices=FormatoExportacao.choices)

    arquivo = models.FileField(upload_to='relatorios/', blank=True, null=True)

    total_registros = models.IntegerField(default=0)

    iniciado_em = models.DateTimeField(auto_now_add=True)
    finalizado_em = models.DateTimeField(blank=True, null=True)

    erro = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.relatorio.nome} - {self.status}"


class AgendamentoRelatorio(models.Model):
    """
    Agendamento automático de relatórios
    """
    PERIODICIDADE = [
        ('diario', 'Diário'),
        ('semanal', 'Semanal'),
        ('mensal', 'Mensal'),
    ]

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)

    relatorio = models.ForeignKey(Relatorio, on_delete=models.CASCADE)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)

    periodicidade = models.CharField(max_length=20, choices=PERIODICIDADE)

    ativo = models.BooleanField(default=True)

    proxima_execucao = models.DateTimeField()
    ultima_execucao = models.DateTimeField(blank=True, null=True)

    enviar_email = models.BooleanField(default=False)
    email_destino = models.EmailField(blank=True, null=True)

    def __str__(self):
        return f"{self.relatorio.nome} ({self.periodicidade})"