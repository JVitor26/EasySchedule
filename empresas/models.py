from django.db import models
from .business_profiles import get_business_profile, normalize_business_type

class Empresa(models.Model):    
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=50)
    cnpj = models.CharField(max_length=18, blank=True, null=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    usuario = models.OneToOneField('auth.User', on_delete=models.CASCADE, related_name='empresa')

    @property
    def business_profile(self):
        return get_business_profile(self.tipo)

    def save(self, *args, **kwargs):
        self.tipo = normalize_business_type(self.tipo)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nome
