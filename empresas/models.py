from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import re
import uuid
from .business_profiles import get_business_profile, normalize_business_type


def _normalize_hex_color(value):
    raw = (value or "").strip().lower()
    if not raw:
        return ""

    if not raw.startswith("#"):
        raw = f"#{raw}"

    if re.fullmatch(r"#[0-9a-f]{6}", raw):
        return raw

    return ""

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
    logo = models.ImageField(upload_to="empresas/logos/", blank=True, null=True)
    logo_url = models.URLField(blank=True, default="")
    cor_primaria = models.CharField(max_length=7, blank=True, default="")
    cor_secundaria = models.CharField(max_length=7, blank=True, default="")
    texto_cabecalho = models.CharField(max_length=80, blank=True, default="")
    plano = models.CharField(max_length=20, choices=PLANO_CHOICES, default=PLANO_START)
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2, default=147)
    limite_profissionais = models.PositiveSmallIntegerField(
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text="Limite comercial de profissionais ativos para esta empresa.",
    )
    portal_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    usuario = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='empresa')

    @property
    def business_profile(self):
        return get_business_profile(self.tipo)

    def save(self, *args, **kwargs):
        self.tipo = normalize_business_type(self.tipo)
        self.whatsapp = "".join(filter(str.isdigit, self.whatsapp or ""))
        self.logo_url = (self.logo_url or "").strip()
        self.cor_primaria = _normalize_hex_color(self.cor_primaria)
        self.cor_secundaria = _normalize_hex_color(self.cor_secundaria)

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
