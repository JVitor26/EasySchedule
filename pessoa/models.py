from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
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
    portal_password = models.CharField(max_length=128, blank=True)
    portal_password_updated_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.nome

    def campos_cadastro_pendentes(self):
        campos = []
        nome_normalizado = (self.nome or "").strip().lower()
        nomes_temporarios = {
            "cliente ia",
            "cliente nao cadastrado",
            "cliente não cadastrado",
            "cliente sem nome",
        }

        if not nome_normalizado or nome_normalizado in nomes_temporarios:
            campos.append("nome")
        if not self.email:
            campos.append("email")
        if not self.documento:
            campos.append("documento")
        if not self.data_nascimento:
            campos.append("data de nascimento")

        return campos

    @property
    def cadastro_completo(self):
        return not self.campos_cadastro_pendentes()

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

    @property
    def has_portal_password(self):
        return bool(self.portal_password)

    def set_portal_password(self, raw_password):
        self.portal_password = make_password(raw_password)
        self.portal_password_updated_at = timezone.now()

    def check_portal_password(self, raw_password):
        if not self.portal_password:
            return False
        return check_password(raw_password, self.portal_password)

    # 🔥 SALVAR PADRONIZADO NO BANCO
    def save(self, *args, **kwargs):
        if self.documento:
            self.documento = re.sub(r'\D', '', self.documento)

        if self.telefone:
            self.telefone = re.sub(r'\D', '', self.telefone)

        if self.email:
            self.email = self.email.strip().lower()

        super().save(*args, **kwargs)
