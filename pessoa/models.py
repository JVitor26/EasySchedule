from django.db import models
from empresas.models import Empresa
import re


class Pessoa(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE)

    nome = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20)
    documento = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField(blank=True, null=True)
    endereco = models.TextField(blank=True)
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return self.nome

    # 📅 DATA FORMATADA
    def data_nascimento_br(self):
        if self.data_nascimento:
            return self.data_nascimento.strftime('%d/%m/%Y')
        return ""

    # 🧾 DOCUMENTO FORMATADO
    def documento_formatado(self):
        if not self.documento:
            return ""

        doc = re.sub(r'\D', '', self.documento)

        if len(doc) == 11:
            return f'{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}'

        elif len(doc) == 14:
            return f'{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}'

        return self.documento

    # 📱 TELEFONE FORMATADO
    def telefone_formatado(self):
        if not self.telefone:
            return ""

        tel = re.sub(r'\D', '', self.telefone)

        if len(tel) == 11:
            return f'({tel[:2]}) {tel[2:7]}-{tel[7:]}'
        elif len(tel) == 10:
            return f'({tel[:2]}) {tel[2:6]}-{tel[6:]}'

        return self.telefone

    # 📧 EMAIL PADRONIZADO
    def email_formatado(self):
        if not self.email:
            return ""
        return self.email.strip().lower()

    # 🔥 SALVAR PADRONIZADO NO BANCO
    def save(self, *args, **kwargs):
        if self.documento:
            self.documento = re.sub(r'\D', '', self.documento)

        if self.telefone:
            self.telefone = re.sub(r'\D', '', self.telefone)

        if self.email:
            self.email = self.email.strip().lower()

        super().save(*args, **kwargs)
