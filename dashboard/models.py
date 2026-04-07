from django.db import models
from django.contrib.auth.models import User
from empresas.models import Empresa


class DashboardLog(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    acao = models.CharField(max_length=255)
    data = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} - {self.acao}"