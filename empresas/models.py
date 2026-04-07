from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from .business_profiles import get_business_profile, normalize_business_type

class Empresa(models.Model):    
    PLANO_START = "start"
    PLANO_SOLO = "solo"
    PLANO_ADMIN_ONLY = "admin_only"
    PLANO_CHOICES = [
        (PLANO_SOLO, "Solo (1 funcionario com acesso)"),
        (PLANO_START, "Start (ate 5 funcionarios)"),
        (PLANO_ADMIN_ONLY, "Gestao interna (somente administrador)"),
    ]

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    whatsapp = models.CharField(max_length=20, blank=True, default="")
    plano = models.CharField(max_length=20, choices=PLANO_CHOICES, default=PLANO_START)
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=147)
    limite_profissionais = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Limite comercial de profissionais ativos para esta empresa.",
    )
    data_cadastro = models.DateTimeField(auto_now_add=True)
    usuario = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='empresa')

    @property
    def business_profile(self):
        return get_business_profile(self.tipo)

    def save(self, *args, **kwargs):
        self.tipo = normalize_business_type(self.tipo)
        self.whatsapp = "".join(filter(str.isdigit, self.whatsapp or ""))

        if self.plano == self.PLANO_SOLO:
            self.limite_profissionais = 1
        elif self.plano == self.PLANO_ADMIN_ONLY and not self.limite_profissionais:
            self.limite_profissionais = 5

        self.limite_profissionais = min(max(self.limite_profissionais or 1, 1), 5)
        super().save(*args, **kwargs)

    @property
    def profissionais_ativos(self):
        return self.profissional_set.filter(ativo=True).count()

    @property
    def vagas_profissionais(self):
        return max(self.limite_profissionais - self.profissionais_ativos, 0)

    def can_add_profissional(self):
        return self.profissionais_ativos < self.limite_profissionais

    @property
    def permite_acesso_profissional(self):
        return self.plano != self.PLANO_ADMIN_ONLY

    def __str__(self):
        return self.nome
